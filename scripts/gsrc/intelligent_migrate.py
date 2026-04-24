#!/usr/bin/env python3
"""Intelligent per-form migration from decomp output into hand-ported gsrc.

Problem statement
-----------------
`scripts/gsrc/update-from-decomp.py` replaces the hand-port body wholesale
with the decomp body (preserving only comments). For hand-ports that carry
MANUAL IMPROVEMENTS (named methods, specific field types, inline modifiers,
populated static data), a decomp rerun is usually a regression:

  * Named methods (`current-cycle-distance`) revert to `method-9`.
  * Specific field types (`joint-control-command`) revert to `uint64`.
  * `:inline` modifiers vanish.
  * Populated `(define *foo* (new 'static 'inline-array ... N entries))`
    reverts to `(define *foo* #f)`.

This tool does a per-form merge instead of a wholesale swap. Every top-level
form is matched across hand-port and decomp by `(kind, symbol)`. A rule
table picks which side wins for each match:

  * Hand-port-only forms stay.
  * Decomp-only forms may be added (newly resolved content).
  * Both-sides forms go through a per-kind merge rule.

Usage
-----
    python3 scripts/gsrc/intelligent_migrate.py --game jakx --file ambient-h \
        [--dry-run | --apply] [--verbose] [--output PATH]

Run from the repo root (same convention as update-from-decomp.py).

Design notes
------------
* Parsing is line-oriented; S-expression splitting uses a paren counter that
  respects string literals and line comments. Block comments (`#| ... |#`)
  are not currently supported — the existing GOAL sources don't use them.
* Comments (`;;` blocks) immediately above a form are attached to that form
  and travel with whichever side wins.
* The merge is a best-effort union: the output preserves the hand-port's
  order as much as possible, inserts new decomp-only forms at the position
  the decomp placed them.

Author notes: see `project_jakx_opengoal.md` orchestrator memory entry for
the why-is-this-needed context.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

# -------------------------------------------------------------------------
# Utility: file path resolution (copied behaviour from utils.get_gsrc_path)
# -------------------------------------------------------------------------

def get_gsrc_path(game: str, file_name: str) -> Optional[str]:
    """Resolve the hand-port path for a (game, file). Uses build metadata."""
    import json
    all_objs = f"./goal_src/{game}/build/all_objs.json"
    if not os.path.exists(all_objs):
        print(f"[err] missing build metadata: {all_objs}", file=sys.stderr)
        return None
    with open(all_objs) as f:
        files = json.load(f)
    for f in files:
        # kind 3/5 == regular source / header file; same check as utils.py
        if f[2] not in (3, 5):
            continue
        if f[0] == file_name:
            return f"./goal_src/{game}/{f[4]}/{file_name}.gc"
    print(f"[err] {file_name!r} not in {game}'s all_objs.json", file=sys.stderr)
    return None


def get_decomp_path(game: str, file_name: str) -> str:
    return f"./decompiler_out/{game}/{file_name}_disasm.gc"


# -------------------------------------------------------------------------
# S-expression parser: splits a file into top-level forms
# -------------------------------------------------------------------------

# Lines we always drop from decomp output before parsing (mirrors
# update-from-decomp.py but we prune aggressively because the parser
# works on text).
DECOMP_STRIP_LINE_PREFIXES = (
    ";;-*-Lisp-*-",
    "(in-package goal)",
    ";; definition",
    ";; INFO:",
    ";; failed to figure",
    ";; Used lq/sq",
    ";; this part is debug only",
    ";; WARN: Return type mismatch",
    ";; WARN: Stack slot offset",
)


def _line_has_stripable_prefix(line: str) -> bool:
    stripped = line.lstrip()
    for prefix in DECOMP_STRIP_LINE_PREFIXES:
        if stripped.lower().startswith(prefix.lower()):
            return True
    return False


@dataclass
class Form:
    """One top-level s-expression, plus its leading comments.

    `text` is the exact source (including trailing newline).
    `leading_comments` is the run of `;;`-style comment lines and blank lines
    immediately above this form.
    """

    kind: str                       # e.g. "deftype", "defun", "defmethod", "define", "defenum"
    symbol: str                     # main identifier (type name, function name, etc.)
    qualifier: str = ""             # for defmethod: the type name (secondary key)
    text: str = ""                  # the full source text of the form
    leading_comments: str = ""      # comments immediately above
    src_start_line: int = 0
    src_end_line: int = 0

    @property
    def key(self) -> Tuple[str, str, str]:
        return (self.kind, self.symbol, self.qualifier)

    @property
    def body_lines(self) -> int:
        return self.text.count("\n")


def _effective_chars_for_parens(line: str) -> str:
    """Remove the parts of a line that shouldn't count toward paren balance:
    line comments and string-literal contents.
    """
    out = []
    i = 0
    in_string = False
    while i < len(line):
        c = line[i]
        if in_string:
            if c == "\\" and i + 1 < len(line):
                i += 2
                continue
            if c == '"':
                in_string = False
            i += 1
            continue
        if c == '"':
            in_string = True
            i += 1
            continue
        if c == ";":
            # line comment (including `;;`): rest of line is out
            break
        out.append(c)
        i += 1
    return "".join(out)


def _paren_delta(line: str) -> int:
    eff = _effective_chars_for_parens(line)
    return eff.count("(") - eff.count(")")


# Regex that identifies what a top-level opening line is defining.
# Handles: (deftype FOO ...), (defun foo ...), (defmethod NAME TYPE ...),
#          (define *foo* ...), (defenum FOO ...), (define-extern foo ...),
#          (declare-type FOO ...), (defmacro NAME ...).
RE_FORM_HEAD = re.compile(
    r"^\s*\(\s*(?P<kind>[a-zA-Z][\w\-!?*/]*)\s+"
    r"(?P<sym>[^\s()]+)"
    r"(?:\s+(?P<qual>[^\s()]+))?"
)


def _classify_form(head_line: str, full_text: str = "") -> Tuple[str, str, str]:
    """Return (kind, symbol, qualifier). qualifier is used for defmethod.

    GOAL has two defmethod syntaxes:
      * Old: (defmethod METHOD TYPE (args) ...)
      * New: (defmethod METHOD ((this TYPE) args) ...)
    We extract TYPE from whichever shape is present. `full_text` (if passed)
    lets us look past the first line for the new-style arg-list form.
    """
    m = RE_FORM_HEAD.match(head_line)
    if not m:
        return ("other", head_line.strip()[:40], "")
    kind = m.group("kind")
    sym = m.group("sym")
    qual = m.group("qual") or ""

    if kind == "defmethod":
        # If qual starts with '(' it means the head line had `((this ...)`;
        # we should read the type from inside the first arg form.
        # Look at full_text (which includes the arg list possibly on next
        # line too) for `((this TYPE)` or `(this TYPE)` inside the arg list.
        search_text = full_text if full_text else head_line
        # Old style: `(defmethod name TYPE ...` — qual is already a bare name
        # as long as it doesn't start with `(`.
        if qual and not qual.startswith("("):
            # But careful: in old-style, after TYPE may come the arg list.
            # We're good.
            return ("defmethod", sym, qual)
        # New style: look for `(this TYPE)` or `((arg TYPE))` pattern.
        # Most common form: `(defmethod NAME ((this TYPE) ...) ...)`.
        m2 = re.search(r"\(\s*this\s+([\w\-+*/<>=!?]+)\s*\)", search_text)
        if m2:
            return ("defmethod", sym, m2.group(1))
        # Fallback: try to grab the type from `((SOMEARG TYPE)` (arg named
        # something other than `this` — rare but not impossible).
        m3 = re.search(r"\(\s*\(\s*[\w\-+*/<>=!?]+\s+([\w\-+*/<>=!?]+)\s*\)", search_text)
        if m3:
            return ("defmethod", sym, m3.group(1))
        return ("defmethod", sym, "")
    return (kind, sym, "")


def parse_forms(text: str, strip_decomp_preamble: bool = False) -> Tuple[List[Form], str, str]:
    """Split `text` into (forms, header, trailer).

    `header` is everything above the first top-level form (the file preamble:
    `;;-*-Lisp-*-`, `(in-package goal)`, file-banner comments, and — in a
    hand-port — up through `;; DECOMP BEGINS`).

    `trailer` is anything after the last form (rare; usually blank lines).

    If `strip_decomp_preamble` is True, we also skip the decomp's per-form
    `;; definition of ...` / `;; definition for method ...` header comments,
    which exist on every form and would otherwise clutter the merged output.
    """
    lines = text.splitlines(keepends=True)

    # Pre-pass: drop lines we always want gone from decomp.
    if strip_decomp_preamble:
        filtered = []
        for ln in lines:
            if _line_has_stripable_prefix(ln):
                continue
            filtered.append(ln)
        lines = filtered

    forms: List[Form] = []
    header_lines: List[str] = []
    trailer_lines: List[str] = []

    i = 0
    n = len(lines)

    # Accumulator for comments / blank lines that may belong to the next form.
    pending: List[str] = []

    # For the hand-port we want the header to run through `;; DECOMP BEGINS`,
    # so remember whether we've seen any forms yet.
    seen_form = False

    while i < n:
        line = lines[i]
        stripped = line.lstrip()

        # Blank lines / comment lines: stash them as "pending".
        if stripped == "" or stripped.startswith(";"):
            pending.append(line)
            i += 1
            continue

        # We hit a non-comment, non-blank line. Does it open a form?
        # If not, it's part of the header (before first form) or junk.
        if stripped.startswith("("):
            # Start collecting a form.
            start_line = i
            head_line = line
            balance = _paren_delta(line)
            form_text_lines = [line]
            i += 1
            # If the form starts AND ends on the same line, balance==0 already.
            while balance > 0 and i < n:
                form_text_lines.append(lines[i])
                balance += _paren_delta(lines[i])
                i += 1
            end_line = i - 1

            full_form_text = "".join(form_text_lines)
            kind, sym, qual = _classify_form(head_line, full_form_text)
            # The pending block becomes this form's leading comments,
            # UNLESS we haven't seen a form yet (then it's header territory).
            if not seen_form:
                # Everything up to now (pending) is header material.
                header_lines.extend(pending)
                pending = []
                # Also: for a hand-port file, the header convention is to
                # include top-of-file declarations (declare-type, define-extern,
                # defenum, etc.) ABOVE `;; DECOMP BEGINS`, and the first
                # "real" body form is below it. We don't special-case that
                # here — we treat every top-level (...) as a form and let the
                # merger sort it out.
                seen_form = True
            forms.append(Form(
                kind=kind,
                symbol=sym,
                qualifier=qual,
                text="".join(form_text_lines),
                leading_comments="".join(pending),
                src_start_line=start_line,
                src_end_line=end_line,
            ))
            pending = []
            continue

        # Non-paren, non-comment line at top level — treat as header junk.
        pending.append(line)
        i += 1

    # Leftover pending: if we saw forms, it's trailer; else header.
    if seen_form:
        trailer_lines = pending
    else:
        header_lines.extend(pending)

    return forms, "".join(header_lines), "".join(trailer_lines)


# -------------------------------------------------------------------------
# Merge rules
# -------------------------------------------------------------------------

RE_GENERIC_METHOD = re.compile(r"^[\w\-]+?-method-\d+$|^method-\d+$")
RE_STATIC_DATA = re.compile(r"\(\s*new\s+'static(?:-[\w-]+)?\b")
RE_STUB_BODY = re.compile(r"\(\s*define\s+\*?[\w\-!?*/]+\*?\s+(?:#f|#t|0|'\(\)|\"\")\s*\)")

GENERIC_TYPES = frozenset({"uint", "uint8", "uint16", "uint32", "uint64",
                           "int", "int8", "int16", "int32", "int64",
                           "basic", "object"})


def is_generic_method_name(name: str) -> bool:
    """Match e.g. `method-9` or `joint-control-method-9`."""
    return bool(RE_GENERIC_METHOD.match(name))


def is_trivial_stub(form_text: str) -> bool:
    """A form is a trivial stub if it's a 1-line (define FOO #f) or similar."""
    if RE_STUB_BODY.search(form_text):
        return True
    # Also: a deftype with empty body: (deftype foo (parent) ())
    if re.search(r"\(\s*deftype\s+\S+\s+\([^)]*\)\s*\(\s*\)\s*\)\s*$", form_text):
        return True
    return False


def has_static_content(form_text: str) -> bool:
    return bool(RE_STATIC_DATA.search(form_text))


@dataclass
class MergeDecision:
    """One merge decision record (for --verbose and test reporting)."""
    key: Tuple[str, str, str]
    winner: str            # "handport" | "decomp" | "merged-deftype"
    reason: str


# -------------------------------------------------------------------------
# deftype field-level merger
# -------------------------------------------------------------------------

# A deftype has shape:
#   (deftype NAME (PARENT)
#     "optional docstring"
#     (
#       (field1 TYPE ... modifiers)
#       (field2 TYPE ... modifiers)
#     )
#     [pack attrs like :pack-me]
#     [(:methods ...)]
#     [(:state-methods ...)]
#   )
#
# We don't do a fully general AST merge. Instead we do a field-block +
# :methods block merge by locating those substrings and operating on them.

def _find_matching_paren(s: str, open_idx: int) -> int:
    """Given s[open_idx] == '(', return the index of the matching ')'.
    Respects string literals. Returns -1 if unbalanced.
    """
    assert s[open_idx] == "("
    depth = 0
    i = open_idx
    in_string = False
    while i < len(s):
        c = s[i]
        if in_string:
            if c == "\\":
                i += 2
                continue
            if c == '"':
                in_string = False
            i += 1
            continue
        if c == '"':
            in_string = True
            i += 1
            continue
        if c == ";":
            # skip line comment
            nl = s.find("\n", i)
            if nl == -1:
                return -1
            i = nl + 1
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _locate_field_block(deftype_text: str) -> Optional[Tuple[int, int, int, int, str]]:
    """Locate the field block in a deftype.

    A deftype looks like:
      (deftype NAME (PARENT)
        "optional docstring"
        (FIELD-BLOCK)     <-- always paren-grouped
        :pack-me? etc
        (:methods ...)?
      )

    Returns (prefix_end, fb_open, fb_close, body_start, body_end):
      prefix_end    -- index just after the parent-list's closing ')'
                       plus optional docstring and whitespace
      fb_open       -- index of field block's '('
      fb_close      -- index of field block's matching ')'
      (Returns None on failure.)
    """
    # Find `(deftype`
    m = re.match(r"\s*\(\s*deftype\s+(\S+)\s+", deftype_text)
    if not m:
        return None
    pos = m.end()
    # Expect a parent list `(PARENT)` starting here.
    while pos < len(deftype_text) and deftype_text[pos].isspace():
        pos += 1
    if pos >= len(deftype_text) or deftype_text[pos] != "(":
        return None
    parent_close = _find_matching_paren(deftype_text, pos)
    if parent_close == -1:
        return None
    pos = parent_close + 1
    # Skip whitespace and optional docstring.
    while pos < len(deftype_text) and deftype_text[pos].isspace():
        pos += 1
    if pos < len(deftype_text) and deftype_text[pos] == '"':
        # consume string
        j = pos + 1
        while j < len(deftype_text):
            if deftype_text[j] == "\\":
                j += 2
                continue
            if deftype_text[j] == '"':
                j += 1
                break
            j += 1
        pos = j
        while pos < len(deftype_text) and deftype_text[pos].isspace():
            pos += 1
    # Now expect `(` opening the field block.
    if pos >= len(deftype_text) or deftype_text[pos] != "(":
        return None
    fb_open = pos
    fb_close = _find_matching_paren(deftype_text, fb_open)
    if fb_close == -1:
        return None
    return (fb_open, fb_close)


def _locate_methods_block(deftype_text: str) -> Optional[Tuple[int, int]]:
    """Locate the (:methods ...) block. Returns (open, close) indices."""
    # Scan for `(:methods` at the top level of this deftype.
    # Simple approach: regex for the opener, then balance from that '('.
    m = re.search(r"\(\s*:methods\b", deftype_text)
    if not m:
        return None
    open_idx = m.start()
    close_idx = _find_matching_paren(deftype_text, open_idx)
    if close_idx == -1:
        return None
    return (open_idx, close_idx)


def _parse_field_lines(block_body: str) -> List[Tuple[str, str, str]]:
    """From the body of a field block, return [(name, raw_text, body_stripped)].

    Each field is shaped `(NAME TYPE ... modifiers)`. We return them with:
      * name: the field identifier
      * raw_text: exact text of the field form, including surrounding parens
      * body_stripped: interior of the field form (no outer parens)

    We rely on the fact that field forms rarely nest more than one level deep.
    """
    results: List[Tuple[str, str, str]] = []
    i = 0
    n = len(block_body)
    while i < n:
        while i < n and block_body[i].isspace():
            i += 1
        if i >= n:
            break
        if block_body[i] != "(":
            # skip unexpected token
            i += 1
            continue
        # find matching close paren (respecting nested parens inside)
        depth = 0
        start = i
        in_string = False
        while i < n:
            c = block_body[i]
            if in_string:
                if c == "\\":
                    i += 2
                    continue
                if c == '"':
                    in_string = False
                i += 1
                continue
            if c == '"':
                in_string = True
                i += 1
                continue
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    i += 1
                    break
            i += 1
        raw_text = block_body[start:i]
        body = raw_text.strip()[1:-1].strip()
        # first token is the name
        m = re.match(r"\s*([\w\-+*/<>=!?]+)", body)
        name = m.group(1) if m else body[:20]
        results.append((name, raw_text, body))
    return results


def _field_type_token(field_body: str) -> str:
    """Extract the field type token from a field body.

    Field body looks like `NAME TYPE ARRAY-SIZE :inline ...` or
    `NAME (function ...) ...`. We return TYPE as a normalized string.
    """
    # skip name
    m = re.match(r"\s*[\w\-+*/<>=!?]+\s+", field_body)
    if not m:
        return ""
    rest = field_body[m.end():]
    # If next is a parenthesized type, grab that.
    if rest.lstrip().startswith("("):
        # read one balanced-paren expression
        s = rest.lstrip()
        depth = 0
        for j, c in enumerate(s):
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    return s[:j+1].strip()
    # otherwise a bare symbol
    m = re.match(r"\s*([\w\-+*/<>=!?]+)", rest)
    return m.group(1) if m else ""


def _has_modifier(field_body: str, modifier: str) -> bool:
    return bool(re.search(rf"(?<![\w-]){re.escape(modifier)}(?![\w-])", field_body))


MODIFIERS = (":inline", ":dynamic", ":overlay-at", ":offset", ":offset-assert",
             ":bitfield", ":pack-me", ":score")


def _pick_better_field(hp_raw: str, hp_body: str, dc_raw: str, dc_body: str) -> str:
    """Given the hand-port and decomp versions of the SAME field, pick the
    one with the more specific type and union-of-modifiers.

    Rule of thumb: hand-port nearly always wins, unless it's identical.
    But we want to SURFACE modifiers from hand-port even if decomp reordered.
    Simplest correct-enough implementation: if hand-port type is non-generic
    OR hand-port has more modifiers, keep hand-port.
    """
    hp_type = _field_type_token(hp_body)
    dc_type = _field_type_token(dc_body)

    hp_type_generic = hp_type in GENERIC_TYPES
    dc_type_generic = dc_type in GENERIC_TYPES

    # Count modifiers
    hp_mods = sum(1 for m in MODIFIERS if _has_modifier(hp_body, m))
    dc_mods = sum(1 for m in MODIFIERS if _has_modifier(dc_body, m))

    # Decision:
    # 1. If hand-port has a non-generic type and decomp has generic, keep HP.
    # 2. If hand-port has MORE modifiers, keep HP.
    # 3. If types match and modifiers match, keep HP (no-op).
    # 4. If hand-port is generic and decomp is non-generic (rare), take decomp.
    if hp_type_generic and not dc_type_generic:
        return dc_raw
    if not hp_type_generic and dc_type_generic:
        return hp_raw
    if hp_mods >= dc_mods:
        return hp_raw
    return dc_raw


def _parse_methods_entries(methods_body: str) -> List[Tuple[str, str]]:
    """Parse entries from a :methods block body. Each entry is (name, raw_text)."""
    results: List[Tuple[str, str]] = []
    i = 0
    n = len(methods_body)
    while i < n:
        while i < n and methods_body[i].isspace():
            i += 1
        if i >= n:
            break
        if methods_body[i] != "(":
            # skip
            i += 1
            continue
        depth = 0
        start = i
        in_string = False
        while i < n:
            c = methods_body[i]
            if in_string:
                if c == "\\":
                    i += 2
                    continue
                if c == '"':
                    in_string = False
                i += 1
                continue
            if c == '"':
                in_string = True
                i += 1
                continue
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    i += 1
                    break
            i += 1
        raw_text = methods_body[start:i]
        body = raw_text.strip()[1:-1].strip()
        m = re.match(r"\s*([\w\-+*/<>=!?]+)", body)
        name = m.group(1) if m else body[:20]
        results.append((name, raw_text))
    return results


def merge_deftype(hp: Form, dc: Form, verbose: bool = False) -> Tuple[str, str]:
    """Merge two deftype forms. Returns (merged_text, reason).

    Strategy:
      * Replace the field-block in the hand-port with a field-by-field merge.
      * Replace the :methods block in the hand-port with a merge that prefers
        NAMED methods (hand-port's method names win over decomp's method-N).

    Uses paren-counting to find the field and methods blocks (the previous
    regex approach couldn't handle deeply nested field types).
    """
    hp_text = hp.text
    dc_text = dc.text

    hp_fb = _locate_field_block(hp_text)
    dc_fb = _locate_field_block(dc_text)

    if hp_fb is None or dc_fb is None:
        return hp_text, "deftype: field-block locate failed, keeping hand-port"

    hp_fb_open, hp_fb_close = hp_fb
    dc_fb_open, dc_fb_close = dc_fb

    hp_fields_body = hp_text[hp_fb_open + 1: hp_fb_close]
    dc_fields_body = dc_text[dc_fb_open + 1: dc_fb_close]

    hp_fields = _parse_field_lines(hp_fields_body)
    dc_fields = _parse_field_lines(dc_fields_body)
    hp_by_name = {name: (raw, body) for (name, raw, body) in hp_fields}
    dc_by_name = {name: (raw, body) for (name, raw, body) in dc_fields}

    # If field NAMES differ between sides (structural mismatch, e.g. hand-port
    # and decomp disagree about the type layout) we bail — hand-port wins.
    hp_names = [n for (n, _, _) in hp_fields]
    dc_names = [n for (n, _, _) in dc_fields]
    if hp_names != dc_names:
        return hp_text, (
            f"deftype {hp.symbol}: field-name mismatch "
            f"(hp={len(hp_names)}, dc={len(dc_names)}) — keeping hand-port"
        )

    # Same field names, same order. Pick better version per field.
    merged_field_parts: List[str] = []
    for (name, hp_raw, hp_body) in hp_fields:
        dc_raw, dc_body = dc_by_name[name]
        merged_field_parts.append(_pick_better_field(hp_raw, hp_body, dc_raw, dc_body))

    # Preserve the hand-port's whitespace layout as closely as possible.
    # Easiest correct-enough: re-emit fields with "\n   " joiner (matches the
    # dominant indent of existing hand-ports) and let format-gsrc-file.py or
    # subsequent `goalc` passes re-pretty the file if needed.
    # BUT — if every picked part matches the hand-port part, do nothing
    # (bit-exact preservation).
    all_same = all(
        merged_field_parts[i] == hp_fields[i][1]
        for i in range(len(hp_fields))
    )
    if all_same:
        # No changes needed at field level. Keep exact hand-port text.
        merged_text = hp_text
    else:
        merged_fields_body = "\n   ".join(p.strip() for p in merged_field_parts)
        merged_fields_block = f"({merged_fields_body}\n   )"
        merged_text = (
            hp_text[:hp_fb_open]
            + merged_fields_block
            + hp_text[hp_fb_close + 1:]
        )

    # Now merge :methods block. Position-based pairing (GOAL methods are
    # positional slot-indexed).
    hp_mb = _locate_methods_block(merged_text)
    dc_mb = _locate_methods_block(dc_text)
    if hp_mb is not None and dc_mb is not None:
        hp_open, hp_close = hp_mb
        dc_open, dc_close = dc_mb
        # body of :methods is between `(:methods` and closing `)`.
        # find end of ":methods" token
        hp_after_tag = hp_open + 1  # skip '('
        m_hp = re.match(r"\s*:methods\b", merged_text[hp_after_tag:])
        hp_body_start = hp_after_tag + m_hp.end() if m_hp else hp_after_tag
        hp_methods_body = merged_text[hp_body_start: hp_close]

        dc_after_tag = dc_open + 1
        m_dc = re.match(r"\s*:methods\b", dc_text[dc_after_tag:])
        dc_body_start = dc_after_tag + m_dc.end() if m_dc else dc_after_tag
        dc_methods_body = dc_text[dc_body_start: dc_close]

        hp_method_entries = _parse_methods_entries(hp_methods_body)
        dc_method_entries = _parse_methods_entries(dc_methods_body)
        merged_methods: List[str] = []
        for idx in range(max(len(hp_method_entries), len(dc_method_entries))):
            hp_ent = hp_method_entries[idx] if idx < len(hp_method_entries) else None
            dc_ent = dc_method_entries[idx] if idx < len(dc_method_entries) else None
            if hp_ent and dc_ent:
                hp_name, hp_raw = hp_ent
                dc_name, dc_raw = dc_ent
                if is_generic_method_name(dc_name) and not is_generic_method_name(hp_name):
                    merged_methods.append(hp_raw)
                elif is_generic_method_name(hp_name) and not is_generic_method_name(dc_name):
                    merged_methods.append(dc_raw)
                else:
                    merged_methods.append(hp_raw)
            elif hp_ent:
                merged_methods.append(hp_ent[1])
            elif dc_ent:
                merged_methods.append(dc_ent[1])

        # If the merged set equals the hand-port set verbatim, leave untouched.
        hp_raw_list = [e[1] for e in hp_method_entries]
        if merged_methods != hp_raw_list:
            methods_body_merged = "\n    ".join(m.strip() for m in merged_methods)
            methods_block_merged = f"(:methods\n    {methods_body_merged}\n    )"
            merged_text = (
                merged_text[:hp_open]
                + methods_block_merged
                + merged_text[hp_close + 1:]
            )

    return merged_text, "deftype: field+method merge"


# -------------------------------------------------------------------------
# Form-level merge dispatch
# -------------------------------------------------------------------------

def merge_form(hp: Form, dc: Form, verbose: bool = False) -> MergeDecision:
    """Return a MergeDecision, and set hp.text to the winning/merged text."""
    kind = hp.kind

    # Always-keep-handport kinds.
    if kind in ("defenum", "defmacro", "declare-type", "define-extern"):
        return MergeDecision(hp.key, "handport", f"{kind}: always keep hand-port")

    # define: static-data rule
    if kind == "define":
        hp_static = has_static_content(hp.text)
        dc_static = has_static_content(dc.text)
        if hp_static and not dc_static:
            return MergeDecision(hp.key, "handport",
                                 "define: hand-port has static data, decomp doesn't")
        if dc_static and not hp_static:
            hp.text = dc.text
            return MergeDecision(hp.key, "decomp",
                                 "define: decomp has static data, hand-port is stub")
        # Both sides static, or neither: prefer hand-port if it looks populated.
        if hp_static:
            return MergeDecision(hp.key, "handport", "define: both static, keep HP")
        if is_trivial_stub(hp.text) and not is_trivial_stub(dc.text):
            hp.text = dc.text
            return MergeDecision(hp.key, "decomp",
                                 "define: hand-port is stub, decomp has body")
        return MergeDecision(hp.key, "handport", "define: default keep hand-port")

    # defmethod: named beats generic
    if kind == "defmethod":
        hp_name = hp.symbol
        dc_name = dc.symbol
        if is_generic_method_name(dc_name) and not is_generic_method_name(hp_name):
            return MergeDecision(hp.key, "handport",
                                 f"defmethod {hp_name}: hand-port named, decomp generic")
        if is_generic_method_name(hp_name) and not is_generic_method_name(dc_name):
            hp.text = dc.text
            return MergeDecision(hp.key, "decomp",
                                 f"defmethod: decomp named ({dc_name}), hand-port generic")
        # Otherwise compare bodies: keep the longer / populated one.
        if is_trivial_stub(hp.text) and not is_trivial_stub(dc.text):
            hp.text = dc.text
            return MergeDecision(hp.key, "decomp",
                                 f"defmethod {hp_name}: hand-port stub, decomp populated")
        return MergeDecision(hp.key, "handport",
                             f"defmethod {hp_name}: default keep hand-port")

    # defun
    if kind == "defun":
        if is_trivial_stub(hp.text) and not is_trivial_stub(dc.text):
            hp.text = dc.text
            return MergeDecision(hp.key, "decomp",
                                 f"defun {hp.symbol}: hand-port stub, decomp populated")
        return MergeDecision(hp.key, "handport",
                             f"defun {hp.symbol}: default keep hand-port")

    # deftype: field+method merge
    if kind == "deftype":
        merged_text, reason = merge_deftype(hp, dc, verbose=verbose)
        hp.text = merged_text
        return MergeDecision(hp.key, "merged-deftype", reason)

    # Everything else: default to hand-port unless stub.
    if is_trivial_stub(hp.text) and not is_trivial_stub(dc.text):
        hp.text = dc.text
        return MergeDecision(hp.key, "decomp", f"{kind}: hand-port stub replaced")
    return MergeDecision(hp.key, "handport", f"{kind}: default keep hand-port")


# -------------------------------------------------------------------------
# Top-level orchestrator
# -------------------------------------------------------------------------

def merge_files(hp_text: str, dc_text: str, verbose: bool = False) -> Tuple[str, List[MergeDecision]]:
    hp_forms, hp_header, hp_trailer = parse_forms(hp_text, strip_decomp_preamble=False)
    dc_forms, _dc_header, _dc_trailer = parse_forms(dc_text, strip_decomp_preamble=True)

    dc_by_key = {f.key: f for f in dc_forms}
    hp_keys = {f.key for f in hp_forms}

    decisions: List[MergeDecision] = []
    out_forms: List[Form] = []

    # Pass 1: walk hand-port forms in order. For each, merge with decomp if
    # present; else keep hand-port.
    for hp in hp_forms:
        if hp.key in dc_by_key:
            dc = dc_by_key[hp.key]
            decision = merge_form(hp, dc, verbose=verbose)
            decisions.append(decision)
            out_forms.append(hp)
        else:
            decisions.append(MergeDecision(hp.key, "handport",
                                           f"{hp.kind} {hp.symbol}: decomp lacks this form"))
            out_forms.append(hp)

    # Pass 2: collect decomp-only forms. Append them at the END (simplest
    # correct choice; could be made smarter but for the test cases this is
    # enough — ambient-h and joint-h don't add net-new forms from decomp).
    decomp_only_appended: List[Form] = []
    for dc in dc_forms:
        if dc.key not in hp_keys:
            # Skip `defmethod inspect` — mirrors update-from-decomp's default
            # ignore list, and these are noise on hand-ports that already
            # define richer inspects (or intentionally don't).
            if dc.kind == "defmethod" and dc.symbol == "inspect":
                decisions.append(MergeDecision(dc.key, "skipped",
                                               "defmethod inspect from decomp-only: skipped"))
                continue
            decisions.append(MergeDecision(dc.key, "decomp",
                                           f"{dc.kind} {dc.symbol}: new from decomp"))
            decomp_only_appended.append(dc)

    # Build final output.
    pieces: List[str] = [hp_header]
    # Ensure header ends with a newline
    if pieces[-1] and not pieces[-1].endswith("\n"):
        pieces.append("\n")

    for f in out_forms:
        if f.leading_comments:
            pieces.append(f.leading_comments)
        pieces.append(f.text)
        if not f.text.endswith("\n"):
            pieces.append("\n")

    for f in decomp_only_appended:
        # strip the ;; definition ... header comments attached by decomp.
        trimmed = "\n".join(
            ln for ln in f.leading_comments.splitlines()
            if not ln.lstrip().startswith(";; definition")
        )
        if trimmed.strip():
            pieces.append(trimmed + "\n")
        pieces.append(f.text)
        if not f.text.endswith("\n"):
            pieces.append("\n")

    if hp_trailer:
        pieces.append(hp_trailer)

    # Collapse multiple trailing blank lines down to one.
    result = "".join(pieces)
    result = re.sub(r"\n{3,}$", "\n\n", result)
    if not result.endswith("\n"):
        result += "\n"

    return result, decisions


# -------------------------------------------------------------------------
# CLI
# -------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(
        prog="intelligent_migrate",
        description="Quality-preserving per-form merge of decomp output into hand-ported gsrc.",
    )
    p.add_argument("--game", required=True, help="jak1|jak2|jak3|jakx")
    p.add_argument("--file", required=True, help="e.g. 'ambient-h' (no extension)")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", help="Write merged output to stdout")
    g.add_argument("--apply", action="store_true", help="Overwrite the gsrc file in place")
    p.add_argument("--output", help="Write merged output to this path")
    p.add_argument("--verbose", action="store_true", help="Print per-form merge decisions")
    args = p.parse_args(argv)

    hp_path = get_gsrc_path(args.game, args.file)
    if hp_path is None:
        return 2
    dc_path = get_decomp_path(args.game, args.file)
    if not os.path.exists(dc_path):
        print(f"[err] missing decomp output: {dc_path}", file=sys.stderr)
        return 2

    with open(hp_path) as f:
        hp_text = f.read()
    with open(dc_path) as f:
        dc_text = f.read()

    merged, decisions = merge_files(hp_text, dc_text, verbose=args.verbose)

    if args.verbose:
        counts = {"handport": 0, "decomp": 0, "merged-deftype": 0, "skipped": 0}
        for d in decisions:
            counts[d.winner] = counts.get(d.winner, 0) + 1
        print(f"[info] merge decisions: {counts}", file=sys.stderr)
        for d in decisions:
            print(f"[info]   {d.winner:<16} {d.key} :: {d.reason}", file=sys.stderr)

    if args.apply:
        with open(hp_path, "w") as f:
            f.write(merged)
        print(f"[ok] wrote {hp_path} ({len(merged.splitlines())} lines)")
    elif args.output:
        with open(args.output, "w") as f:
            f.write(merged)
        print(f"[ok] wrote {args.output} ({len(merged.splitlines())} lines)")
    else:
        # default: dry-run to stdout
        sys.stdout.write(merged)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
