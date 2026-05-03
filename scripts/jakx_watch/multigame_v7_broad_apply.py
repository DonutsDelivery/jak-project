#!/usr/bin/env python3
"""V6 broad-apply driver for multi-game fingerprint candidates.

V6 additions over V5:
  - extern-add: when source has (define-extern X form) but jakx doesn't,
    INSERT a new line (low-risk: no existing entry to overwrite). Was
    'extern-not-in-jakx' skip in V5 (~30 candidates).
  - method-add: when source has a method but jakx's deftype doesn't have
    that slot, INSERT a new method line into the :methods block and
    bump :method-count-assert if needed. Was 'jakx-method-line-not-found'
    skip in V5 (~112 candidates). Riskier — guarded by:
      * src method name must be non-stub and parseable
      * jakx_method_idx must be reasonable (within current_max + 8)
      * adding must not create a duplicate name in the deftype
      * deftype must already have a (:methods ...) block

V6 keeps everything V5 had:
  - paren-balance, fwd-ref, type-blacklist gates
  - skip-zero-error-files, skip-curated-slots
  - jakx-name preservation on method replace

Reads .jakx_watch/multigame_fn_fingerprint.json (produced by
`multigame_fingerprint_match.py`) and applies candidate diffs as
ONE GIT COMMIT PER CANDIDATE so that per-file regression bisect
can revert losers individually.

V3 filter philosophy:
  - PRE-APPLY GATES (crash-only): keep only filters that prevent
    parse failures (decompiler can't load all-types.gc):
      * type-not-in-jakx  (referenced type doesn't exist) — DROP candidate
      * fwd-ref           (signature references a type defined later
                           in all-types.gc — DROP)
      * existing-entry    (jakx already has a non-stub entry that
                           differs — for type_casts/stack_structures
                           we still apply; for signatures we skip if
                           the existing sig is itself non-stub and
                           the source is from jak1 tier-B only)
                           Actually: the v2 "no-change" skip just means
                           the diff is empty → not in our list at all.
  - DROPPED gates (v2 used these and lost 116 candidates):
      * method-idx-mismatch        — REMAP to jakx index
      * cross-rename-non-stub      — apply rename anyway
      * method-line-not-found      — try harder (search by method name)
      * no-change                  — N/A (filtered upstream by matcher)
  - METHOD INDEX REMAP: when source signature is `(foo ... ) ;; 17`
    but jakx has `(foo ... ) ;; 23`, transfer the SIG and renumber
    to 23 (jakx's index).

Per-candidate workflow:
  1. Build patch (in-memory edit of all-types.gc / jsonc).
  2. Validate patch doesn't crash all-types parse (re-index).
  3. Write file, git add, git commit with structured message.
  4. Move to next candidate.

Usage:
  python3 multigame_v3_broad_apply.py [--max N] [--limit-corpus jak2,jak3]
                                       [--dry-run]

Output:
  /tmp/jak-mfp-v3/.jakx_watch/research/V3_APPLY_LOG.md
  Per-commit: cand: <name> @ <file> <- <corpus> (tier-A/B)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = ROOT / "decompiler" / "config" / "jakx"
ALL_TYPES = CONFIG_DIR / "all-types.gc"
NTSC_DIR = CONFIG_DIR / "ntsc_v1"
TYPE_CASTS = NTSC_DIR / "type_casts.jsonc"
STACK_STRUCTS = NTSC_DIR / "stack_structures.jsonc"
JSON_INPUT = ROOT / ".jakx_watch" / "multigame_fn_fingerprint.json"
# v6 outputs default — cycle-N driver passes --cycle-tag (V6, V7, ...)
LOG_OUT_DEFAULT = ROOT / ".jakx_watch" / "research" / "V6_APPLY_LOG.md"
CAND_LIST_OUT_DEFAULT = ROOT / ".jakx_watch" / "research" / "V6_CANDIDATE_LIST.json"
# Type blacklist from prior cycle (cumulative — V5_TYPE_BLACKLIST is the latest)
TYPE_BLACKLIST_PATH = ROOT / ".jakx_watch" / "research" / "V5_TYPE_BLACKLIST.json"

RE_DEFINE_EXTERN = re.compile(r"^\(define-extern\s+(\S+)\s+(.+)\)\s*$")
RE_DEFTYPE_HEADER = re.compile(r"^\(deftype\s+(\S+)\s+\((\S+)\)")
# v7-fix: tolerate ANY trailing content after `;; <digits>`. jakx all-types.gc
# has 430+ method lines with chained `;; N ;; description` AND lines like
# `;; 14 - slot placeholder, no defstate` (no second `;;`). Match the digit
# group, then permit any non-newline tail.
RE_METHOD_LINE = re.compile(
    r"^(\s*)\((\S+)\s+(?:\"[^\"]*\"\s+)?(.+?)\s+(\S+?)\)\s*(?:;;\s*(\d+).*)?\s*$"
)


def strip_jsonc(text: str) -> str:
    out = []
    i = 0
    n = len(text)
    in_str = False
    str_q = ""
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == str_q:
                in_str = False
            i += 1
            continue
        if c in ('"', "'"):
            in_str = True
            str_q = c
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def load_jsonc(p: Path):
    if not p.exists():
        return {}
    return json.loads(strip_jsonc(p.read_text(encoding="utf-8")))


# ----------------------------------------------------------------------------
# all-types.gc indexing
# ----------------------------------------------------------------------------

RE_METHOD_COUNT_ASSERT = re.compile(r"^(\s*):method-count-assert\s+(\d+)\s*$")


def index_all_types(text: str):
    """Index types: returns
        externs: name -> line_idx (0-based)
        deftypes: type_name -> {start, end, parent,
                                 methods_block_open_line, methods_block_close_line,
                                 method_count_assert_line, method_count_assert_value,
                                 last_extern_line_before}
        methods: (type, mname) -> {idx, line_idx, sig_text}
        last_extern_line: int — index of the last (define-extern ...) line
                                in the file (for extern-add insertion).
    """
    lines = text.splitlines()
    externs = {}
    deftypes = {}
    methods = {}
    last_extern_line = -1
    cur_type = None
    cur_parent = None
    cur_start = None
    paren_depth = 0
    in_methods = False
    in_state_methods = False
    in_states = False
    methods_open_line = None
    methods_close_line = None
    methods_paren_depth = 0
    states_paren_depth = 0
    state_methods_paren_depth = 0
    mca_line = None
    mca_value = None
    decl_count_total = 0  # all methods + state-methods + states for current type
    for i, line in enumerate(lines):
        m = RE_DEFINE_EXTERN.match(line)
        if m and cur_type is None:
            externs[m.group(1)] = i
            last_extern_line = i
            continue

        m = RE_DEFTYPE_HEADER.match(line)
        if m:
            cur_type = m.group(1)
            cur_parent = m.group(2)
            cur_start = i
            paren_depth = line.count("(") - line.count(")")
            in_methods = False
            in_state_methods = False
            in_states = False
            methods_open_line = None
            methods_close_line = None
            methods_paren_depth = 0
            states_paren_depth = 0
            state_methods_paren_depth = 0
            mca_line = None
            mca_value = None
            decl_count_total = 0
            continue

        if cur_type is None:
            continue

        paren_depth += line.count("(") - line.count(")")
        stripped = line.strip()

        # Track :method-count-assert
        mca_m = RE_METHOD_COUNT_ASSERT.match(line)
        if mca_m:
            mca_line = i
            mca_value = int(mca_m.group(2))

        # Track (:methods ... ) block start/end via paren depth. v7-fix: a
        # deftype can contain MULTIPLE `:methods` blocks (and may interleave
        # with `:state-methods` / `:states`). Index methods from ALL of them;
        # remember the LAST close-line as the insert anchor for method_add.
        if "(:methods" in stripped:
            in_methods = True
            in_state_methods = False
            in_states = False
            if methods_open_line is None:
                methods_open_line = i
            methods_paren_depth = line.count("(") - line.count(")")
        elif "(:state-methods" in stripped:
            in_state_methods = True
            in_methods = False
            in_states = False
            state_methods_paren_depth = line.count("(") - line.count(")")
        elif "(:states" in stripped:
            in_states = True
            in_methods = False
            in_state_methods = False
            states_paren_depth = line.count("(") - line.count(")")
        elif in_methods:
            methods_paren_depth += line.count("(") - line.count(")")
            if methods_paren_depth <= 0:
                in_methods = False
                methods_close_line = i
        elif in_state_methods:
            state_methods_paren_depth += line.count("(") - line.count(")")
            if state_methods_paren_depth <= 0:
                in_state_methods = False
        elif in_states:
            states_paren_depth += line.count("(") - line.count(")")
            if states_paren_depth <= 0:
                in_states = False

        if in_methods and stripped.startswith("(") and i != methods_open_line:
            mm = RE_METHOD_LINE.match(line)
            if mm:
                mname = mm.group(2)
                cmt_idx = int(mm.group(5)) if mm.group(5) else None
                # v7-fix: prefer the idx encoded in the placeholder name
                # `<prefix>-method-N` over the `;; N` annotation. Some
                # all-types.gc lines have stale `;; N` comments that
                # disagree with the canonical slot in the name (e.g.
                # `joint-exploder-method-51 ... ;; 21 ;; (TODO-RENAME-21
                # ...)`). When the name embeds an idx, that's the truth.
                name_idx_m = re.search(r"-method-(\d+)$", mname)
                if name_idx_m:
                    idx = int(name_idx_m.group(1))
                else:
                    idx = cmt_idx
                if idx is not None:
                    methods[(cur_type, mname)] = {
                        "idx": idx, "line_idx": i, "raw": line,
                    }
                    decl_count_total += 1
        elif (in_state_methods or in_states) and stripped and not stripped.startswith(";") \
                and not stripped.startswith("(:"):
            # State-methods / states entries are bare names, optionally with
            # `;; N` annotation. Each non-empty, non-comment line is one decl.
            tok = stripped.split(";")[0].strip()
            if tok and tok != ")" and tok != "(":
                decl_count_total += 1

        if paren_depth <= 0:
            deftypes[cur_type] = {
                "start": cur_start, "end": i, "parent": cur_parent,
                "methods_block_open_line": methods_open_line,
                "methods_block_close_line": methods_close_line,
                "method_count_assert_line": mca_line,
                "method_count_assert_value": mca_value,
                "decl_count_total": decl_count_total,
            }
            cur_type = None
            cur_parent = None
            in_methods = False
            methods_open_line = None
            methods_close_line = None
            mca_line = None
            mca_value = None

    return {"externs": externs, "deftypes": deftypes, "methods": methods,
            "lines": lines, "last_extern_line": last_extern_line}


def index_method_by_idx(types_idx, type_name, idx):
    """Find existing method at (type_name, idx). Returns method dict or None."""
    for (tn, mname), info in types_idx["methods"].items():
        if tn == type_name and info["idx"] == idx:
            return {"name": mname, **info}
    return None


def parent_chain(types_idx, type_name):
    """Walk parent chain of type_name. Returns list starting with type_name itself."""
    out = [type_name]
    seen = {type_name}
    cur = type_name
    while cur in types_idx["deftypes"]:
        info = types_idx["deftypes"][cur]
        p = info.get("parent")
        if not p or p in seen:
            break
        out.append(p)
        seen.add(p)
        cur = p
    return out


def parent_mca(types_idx, type_name):
    """Return the parent's :method-count-assert value, or None if unknown.
    Walks one step up and reads MCA from the parent deftype."""
    info = types_idx["deftypes"].get(type_name) or {}
    p = info.get("parent")
    if not p:
        return None
    p_info = types_idx["deftypes"].get(p) or {}
    return p_info.get("method_count_assert_value")


def find_parent_method_collision(types_idx, type_name, mname):
    """Walk parent chain (excluding type_name itself); return first parent type
    that already declares a method named `mname`. Returns dict
    {parent, raw, idx} or None."""
    chain = parent_chain(types_idx, type_name)
    for p in chain[1:]:
        for (tn, mn), info in types_idx["methods"].items():
            if tn == p and mn == mname:
                return {"parent": p, "raw": info["raw"], "idx": info["idx"]}
    return None


def normalize_sig_body(sig_text):
    """Normalize a method signature for comparison: strip docstrings, trailing
    `;; N` slot annotation, collapse whitespace.

    Inputs may be `(name (args) ret)` or `(name "doc" (args) ret) ;; N`.
    Returns normalized `(name (args) ret)` string.
    """
    # Strip trailing slot index comment
    s = re.sub(r"\s*;;\s*\d+\s*$", "", sig_text.strip())
    # Strip docstring inside the form (first quoted string after the name)
    s = re.sub(r'^(\(\S+)\s+"[^"]*"\s+', r"\1 ", s)
    # Collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s


# ----------------------------------------------------------------------------
# v3 candidate planning (pre-apply gates - crash only)
# ----------------------------------------------------------------------------

def is_stub_method_line(raw_line):
    """A jakx method slot is 'stub' if its name matches typeName-method-N pattern
    OR its args are just (_type_) / (_type_ _type_) / similar generic placeholder.
    Returns True if the existing slot is curated (non-stub) — meaning we should
    NOT overwrite it lightly."""
    # Extract method name
    mm = re.match(r"^\s*\(([^\s]+)\s+", raw_line)
    if not mm:
        return True  # can't parse → treat as stub, allow overwrite
    name = mm.group(1)
    # Pattern: typeNameOrPrefix-method-N
    if re.search(r"-method-\d+$", name):
        return True
    # If args are pure _type_ placeholders, consider stub
    body = re.sub(r";;.*$", "", raw_line).strip()
    args_m = re.search(r"\(([^\)]*)\)\s+\S+\)\s*$", body)
    if args_m:
        args = args_m.group(1).strip()
        if args == "_type_" or args == "":
            return True
    return False


def classify_candidate(m, types_idx, ctx=None):
    """Decide v4 fate for a single match. Returns {action, reason, plan}.

    ctx: dict with optional keys
        - jakx_file_errors: dict file -> error count
        - banned_types: set of types blocked this cycle
        - skip_zero_error_files: bool — skip if jakx file has 0 errors
        - skip_curated_slots: bool — skip if jakx slot is non-stub already
    """
    if ctx is None:
        ctx = {}
    cand = m.get("candidate_patch") or {}
    if not cand:
        return {"action": "skip", "reason": "no-diff", "plan": None}

    fn_name = m["jakx_fn"]
    src_corpus = m["source_corpus"]
    sig = m.get("source_payload", {}).get("signature") or {}
    kind = sig.get("kind")

    # v7 G4: kind-mismatch fast-skip — source signature is method-kind but
    # jakx_fn is anon-function/state-handler/top-level. The fingerprint match
    # is technically valid (the bodies hash the same) but the signature
    # transplant target is wrong: we'd be writing a method declaration over a
    # function that isn't a method. Skip cleanly.
    if kind == "method" and not re.match(r"^\(method\s+\d+\s+\S+\)$", fn_name):
        if fn_name.startswith("(anon-function"):
            return {"action": "skip", "reason": "kind-mismatch:method-vs-anon", "plan": None}
        if fn_name.startswith("("):
            # state-handler form, e.g. "(enter idle some-type)"
            return {"action": "skip", "reason": "kind-mismatch:method-vs-state-handler", "plan": None}
        return {"action": "skip", "reason": "kind-mismatch:method-vs-top-level", "plan": None}

    # v4: skip blacklisted types
    banned_types = ctx.get("banned_types", set())
    if banned_types:
        # extract type name from fn_name
        mm = re.match(r"^\(method\s+\d+\s+(\S+)\)$", fn_name)
        if mm and mm.group(1) in banned_types:
            return {"action": "skip", "reason": f"type-blacklisted:{mm.group(1)}", "plan": None}

    # v4: skip if jakx file has 0 errors (no leverage; pure risk)
    if ctx.get("skip_zero_error_files"):
        jf_errs = ctx.get("jakx_file_errors", {}).get(m["jakx_file"], -1)
        if jf_errs == 0:
            return {"action": "skip", "reason": "jakx-file-clean-no-leverage", "plan": None}

    plan = {"jakx_fn": fn_name, "src_corpus": src_corpus,
            "jakx_file": m["jakx_file"], "actions": []}

    # Tier classification: tier-A = multi-corpus agreement, tier-B = single.
    n_corpora_with_match = len(m.get("candidates_by_corpus", {}))
    tier = "tier-A" if n_corpora_with_match >= 2 else "tier-B"
    plan["tier"] = tier
    plan["n_corpora"] = n_corpora_with_match

    # v7 confidence score for apply order. Higher = more confident.
    #   +2.0 tier-A (multi-corpus agreement)
    #   +0.5 jakx file has errors (more leverage when applied)
    #   +0.5 jak2 source corpus (highest port quality)
    #   +0.3 jak3 source corpus
    #   +0.1 jak1 source corpus
    #   +0.5 sig.kind == "extern" (lower-risk action)
    #   -0.5 sig.kind == "method" + missing slot (method_add path; risky)
    score = 0.0
    if tier == "tier-A":
        score += 2.0
    if (m.get("jakx_file_errors") or 0) > 0:
        score += 0.5
    if src_corpus == "jak2":
        score += 0.5
    elif src_corpus == "jak3":
        score += 0.3
    elif src_corpus == "jak1":
        score += 0.1
    if kind == "extern":
        score += 0.5
    plan["score"] = score

    # ---- Signature diff
    if "signature_diff" in cand:
        sd = cand["signature_diff"]
        src_sig = sd["source"]
        jx_sig = sd["jakx"]

        if kind == "extern":
            # Drop the source name; transplant signature using JAKX name.
            # source = "(define-extern <src_name> <form>)"
            # Parens balance check first
            if src_sig.count("(") != src_sig.count(")"):
                return {"action": "skip", "reason": "extern-sig-unbalanced-parens", "plan": None}
            mm = re.match(r"^\(define-extern\s+(\S+)\s+(.+)\)\s*$", src_sig)
            if not mm:
                return {"action": "skip", "reason": f"extern-parse-fail:{src_sig[:40]}", "plan": None}
            src_form = mm.group(2)
            # Form must also balance parens
            if src_form.count("(") != src_form.count(")"):
                return {"action": "skip", "reason": "extern-form-unbalanced-parens", "plan": None}
            jakx_extern_idx = types_idx["externs"].get(fn_name)
            new_line = f"(define-extern {fn_name} {src_form})"
            if jakx_extern_idx is None:
                # V6: extern-add path. Insert a new (define-extern ...) line
                # at the end of the existing extern cluster (right after the
                # last extern in the file). Low risk: no overwrite, no name
                # collision risk because we already know fn_name isn't in
                # externs. Forward-ref check still applies.
                if not ctx.get("enable_extern_add", True):
                    return {"action": "skip", "reason": "extern-not-in-jakx", "plan": None}
                last_ext = types_idx.get("last_extern_line", -1)
                if last_ext < 0:
                    # No existing externs at all — degenerate; skip.
                    return {"action": "skip", "reason": "extern-add-no-anchor", "plan": None}
                plan["actions"].append({
                    "kind": "extern_add",
                    "after_line_idx": last_ext,
                    "new_line": new_line,
                    "src_sig": src_sig,
                    "extern_name": fn_name,
                })
            else:
                plan["actions"].append({
                    "kind": "extern_replace",
                    "line_idx": jakx_extern_idx,
                    "new_line": new_line,
                    "src_sig": src_sig,
                })
        elif kind == "method":
            # Source sig like "(name (args) ret)" — transplant body, RENUMBER to jakx idx.
            jakx_idx = sig.get("idx")
            if jakx_idx is None:
                # method-missing in source side — shouldn't happen for kind=method
                return {"action": "skip", "reason": "method-no-src-idx", "plan": None}
            # Detect existing line on jakx side (lookup by jakx_fn = "(method N type)")
            mm = re.match(r"^\(method\s+(\d+)\s+(\S+)\)$", fn_name)
            if not mm:
                return {"action": "skip", "reason": "method-name-parse-fail", "plan": None}
            jakx_method_idx = int(mm.group(1))
            type_name = mm.group(2)
            if type_name not in types_idx["deftypes"]:
                return {"action": "skip", "reason": f"type-not-in-jakx:{type_name}", "plan": None}

            # Find existing method line at (type, jakx_method_idx)
            existing = index_method_by_idx(types_idx, type_name, jakx_method_idx)
            if existing is None:
                # V6: method-add path. Insert a new method line into the
                # type's :methods block, bumping :method-count-assert if
                # needed. Riskier than replace: changes vtable shape, can
                # trigger method-count-assert mismatches at decomp.
                if not ctx.get("enable_method_add", True):
                    return {"action": "skip", "reason": "jakx-method-line-not-found", "plan": None}

                tdef = types_idx["deftypes"].get(type_name)
                if not tdef:
                    return {"action": "skip", "reason": f"type-not-in-jakx:{type_name}", "plan": None}

                # Source sig must be parseable and non-stub.
                src_method_name = sig.get("method_name", "")
                if src_method_name in ("_type_", "", None):
                    return {"action": "skip", "reason": f"src-sig-corrupted-method-name:{src_method_name}", "plan": None}
                src_sig = sd["source"]
                if src_sig.count("(") != src_sig.count(")") or not src_sig.startswith("("):
                    return {"action": "skip", "reason": "method-add-src-malformed", "plan": None}
                src_mm = re.match(r"^\((\S+)\s+(.+?)\s+(\S+?)\)\s*$", src_sig)
                if not src_mm:
                    return {"action": "skip", "reason": "method-add-src-parse-fail", "plan": None}
                src_mname_p = src_mm.group(1)
                src_args = src_mm.group(2)
                src_ret = src_mm.group(3)
                if src_mname_p != src_method_name:
                    return {"action": "skip", "reason": "method-add-src-name-mismatch", "plan": None}
                if not src_args.startswith("("):
                    return {"action": "skip", "reason": "method-add-src-args-not-paren", "plan": None}

                # Reject if name would duplicate an existing method in this type
                if (type_name, src_mname_p) in types_idx["methods"]:
                    return {"action": "skip", "reason": "method-add-duplicate-name", "plan": None}

                # v7 G1: parent-class method-name collision check.
                # If any ancestor declares a method named src_mname_p with a
                # different signature, adding here would either shadow with
                # a conflicting sig (decompiler rejects) or be redundant
                # (already inherited).
                parent_collision = find_parent_method_collision(
                    types_idx, type_name, src_mname_p
                )
                if parent_collision:
                    src_norm = normalize_sig_body(f"({src_mname_p} {src_args} {src_ret})")
                    par_norm = normalize_sig_body(parent_collision["raw"])
                    if src_norm == par_norm:
                        return {
                            "action": "skip",
                            "reason": f"method-add-inherited-from:{parent_collision['parent']}",
                            "plan": None,
                        }
                    return {
                        "action": "skip",
                        "reason": f"method-add-parent-collision:{parent_collision['parent']}.{src_mname_p}",
                        "plan": None,
                    }

                # Methods block must exist
                close_line = tdef.get("methods_block_close_line")
                open_line = tdef.get("methods_block_open_line")
                if close_line is None or open_line is None:
                    # Type has no :methods block. Adding one is structurally
                    # complex (need to splice it before the closing paren of
                    # the deftype). Defer for now.
                    return {"action": "skip", "reason": "method-add-no-methods-block", "plan": None}

                # Bound jakx_method_idx — don't insert wildly out-of-range slots.
                # Find current max index in this type.
                cur_max = -1
                for (tn, mn), info in types_idx["methods"].items():
                    if tn == type_name and info["idx"] is not None:
                        if info["idx"] > cur_max:
                            cur_max = info["idx"]
                mca_val = tdef.get("method_count_assert_value")
                if mca_val is None:
                    return {"action": "skip", "reason": "method-add-no-count-assert", "plan": None}

                # v7 G2: strict MCA gate.
                # The binary's vtable size is fixed and equal to MCA. We can
                # ONLY fill in slots 0..MCA-1 that aren't already declared.
                # Bumping MCA crashes decomp with "type X has N methods, but
                # :method-count-assert was set to M". Hard cap: idx < MCA.
                if jakx_method_idx < 9 or jakx_method_idx >= mca_val:
                    return {
                        "action": "skip",
                        "reason": (
                            f"method-add-idx-out-of-range:"
                            f"idx={jakx_method_idx}/cur_max={cur_max}/mca={mca_val}"
                        ),
                        "plan": None,
                    }

                # v7 G2b: count budget. The decompiler asserts
                #   count(declared in deftype incl. :methods + :state-methods
                #         + :states) + parent.MCA == this.MCA
                # Adding a method line increments declared count. If declared
                # + 1 + parent.MCA > MCA, the decomp crashes with "type X has
                # N methods, but :method-count-assert was set to M". The
                # `declared_in_deftype` counter also includes :state-methods
                # and :states blocks (vehicle has 4 state-methods that count).
                p_mca = parent_mca(types_idx, type_name)
                declared_count = tdef.get("decl_count_total")
                if p_mca is not None and declared_count is not None and \
                        declared_count + 1 + p_mca > mca_val:
                    return {
                        "action": "skip",
                        "reason": (
                            f"method-add-count-budget-exceeded:"
                            f"declared={declared_count}+1+parent_mca={p_mca}>mca={mca_val}"
                        ),
                        "plan": None,
                    }

                # Soft cap: don't fill slots way out of range from cur_max.
                # If cur_max == -1 (no methods yet declared), allow any
                # valid (< MCA) slot. Otherwise allow up to cur_max +
                # method_add_max_gap.
                max_gap = ctx.get("method_add_max_gap", 12)
                if cur_max >= 0 and jakx_method_idx > cur_max + max_gap:
                    return {
                        "action": "skip",
                        "reason": (
                            f"method-add-gap-too-large:"
                            f"idx={jakx_method_idx}/cur_max={cur_max}/gap={jakx_method_idx-cur_max}/max_gap={max_gap}"
                        ),
                        "plan": None,
                    }

                # Pick indent from existing method line if any
                indent = "    "
                # Find any method line in this type to copy its indent
                for (tn, mn), info in types_idx["methods"].items():
                    if tn == type_name:
                        m_ind = re.match(r"^(\s*)", info["raw"])
                        if m_ind:
                            indent = m_ind.group(1)
                        break

                new_method_line = f"{indent}({src_mname_p} {src_args} {src_ret}) ;; {jakx_method_idx}"
                # v7: NEVER bump MCA — gate G2 already enforces idx < mca_val.
                new_mca = mca_val

                plan["actions"].append({
                    "kind": "method_add",
                    "type_name": type_name,
                    "insert_before_line": close_line,
                    "new_method_line": new_method_line,
                    "src_idx": sig.get("idx"),
                    "jakx_idx": jakx_method_idx,
                    "src_mname": src_mname_p,
                    "mca_line": tdef.get("method_count_assert_line"),
                    "old_mca": mca_val,
                    "new_mca": new_mca,
                })
                # Skip the rest of the method-replace logic; method_add is the
                # complete signature transfer.
                continue_to_other_diffs = True
                # Process type_casts/stack_structure diffs if present, then return.
                if "type_casts_diff" in cand:
                    tcd = cand["type_casts_diff"]
                    plan["actions"].append({
                        "kind": "type_casts_set",
                        "fn_name": fn_name,
                        "value": tcd["source"],
                        "had_existing": tcd.get("jakx") is not None,
                    })
                if "stack_structure_diff" in cand:
                    ssd = cand["stack_structure_diff"]
                    plan["actions"].append({
                        "kind": "stack_structure_set",
                        "fn_name": fn_name,
                        "value": ssd["source"],
                        "had_existing": ssd.get("jakx") is not None,
                    })
                return {"action": "apply", "reason": "ok-method-add", "plan": plan}

            # v4: skip if jakx slot is already curated (non-stub method name + meaningful args).
            # Risk: overwriting human-curated work.
            if ctx.get("skip_curated_slots"):
                if not is_stub_method_line(existing["raw"]):
                    return {"action": "skip", "reason": "jakx-slot-curated-non-stub", "plan": None}

            # Build the new method line.
            # src_sig is "(method-name (args) ret)" — replace any trailing ;; N with jakx idx
            # MATCHER BUG WORKAROUND: matcher's RE_METHOD_LINE is single-line, so for
            # multi-line jak2 method declarations (with docstrings on prior lines),
            # source sig is corrupted to just "(args) ret)" with method_name="_type_"
            # or some arg token. Validate src_sig: must start with `(`, must contain
            # exactly balanced parens, must have method name that is NOT _type_.
            # Also: the matcher's signature method_name field is authoritative;
            # check it's a real method name (not a placeholder).
            src_method_name = sig.get("method_name", "")
            if src_method_name in ("_type_", "", None):
                return {"action": "skip", "reason": f"src-sig-corrupted-method-name:{src_method_name}", "plan": None}
            # Parens balance check
            if src_sig.count("(") != src_sig.count(")"):
                return {"action": "skip", "reason": f"src-sig-unbalanced-parens", "plan": None}
            # Must start with "("
            if not src_sig.startswith("("):
                return {"action": "skip", "reason": f"src-sig-malformed:{src_sig[:30]}", "plan": None}
            src_mm = re.match(r"^\((\S+)\s+(.+?)\s+(\S+?)\)\s*$", src_sig)
            if not src_mm:
                return {"action": "skip", "reason": f"src-sig-parse-fail:{src_sig[:40]}", "plan": None}
            src_mname = src_mm.group(1)
            # Sanity: src_mname from regex should match sig['method_name']
            if src_mname != src_method_name:
                return {"action": "skip", "reason": f"src-sig-name-mismatch:regex={src_mname}/sig={src_method_name}", "plan": None}
            src_args = src_mm.group(2)
            src_ret = src_mm.group(3)
            # Args portion must be a parenthesized type list, e.g. "(_type_ vector)"
            # or contain a docstring-like string. If it doesn't start with "(", the
            # matcher likely chewed off real method content.
            if not src_args.startswith("("):
                return {"action": "skip", "reason": f"src-args-not-paren-list:{src_args[:30]}", "plan": None}
            indent_match = re.match(r"^(\s*)", existing["raw"])
            indent = indent_match.group(1) if indent_match else "    "
            # CRITICAL: keep JAKX's method name to preserve jakx's namespace
            # layout. Renaming methods can create duplicate-name collisions
            # within the same deftype, and the parser then under-counts methods
            # (triggering method-count-assert failures). Only the signature
            # body (args + return type) is transferred from source.
            jakx_mname = existing["name"]
            new_line = f"{indent}({jakx_mname} {src_args} {src_ret}) ;; {jakx_method_idx}"
            plan["actions"].append({
                "kind": "method_replace",
                "line_idx": existing["line_idx"],
                "new_line": new_line,
                "old_line": existing["raw"],
                "type_name": type_name,
                "src_idx": sig.get("idx"),
                "jakx_idx": jakx_method_idx,
                "src_mname": src_mname,
                "kept_mname": jakx_mname,
                "old_mname": existing["name"],
            })
        else:
            return {"action": "skip", "reason": f"sig-kind-unsupported:{kind}", "plan": None}

    # ---- type_casts diff: merge under jakx fn_name
    if "type_casts_diff" in cand:
        tcd = cand["type_casts_diff"]
        plan["actions"].append({
            "kind": "type_casts_set",
            "fn_name": fn_name,
            "value": tcd["source"],
            "had_existing": tcd.get("jakx") is not None,
        })

    # ---- stack_structure diff
    if "stack_structure_diff" in cand:
        ssd = cand["stack_structure_diff"]
        plan["actions"].append({
            "kind": "stack_structure_set",
            "fn_name": fn_name,
            "value": ssd["source"],
            "had_existing": ssd.get("jakx") is not None,
        })

    if not plan["actions"]:
        return {"action": "skip", "reason": "empty-plan", "plan": None}

    return {"action": "apply", "reason": "ok", "plan": plan}


# ----------------------------------------------------------------------------
# Forward-ref check (post-build of new line, before commit)
# ----------------------------------------------------------------------------

def has_fwd_ref(new_line: str, line_idx: int, types_idx):
    """Heuristic: extract candidate type names referenced in `new_line` and
    ensure they're either jakx-builtins or defined at or before line_idx.

    Also catches types entirely absent from jakx (the decompiler will throw
    'Type X is unknown' on those)."""
    BUILTINS = {"_type_", "none", "object", "symbol", "string", "int", "uint",
                "int8", "int16", "int32", "int64", "uint8", "uint16", "uint32",
                "uint64", "uint128", "float", "type", "function", "pointer",
                "inline-array", "array", "boolean", "vu-function", "structure",
                "basic", "process-tree", "process", "thread", "binteger",
                "cpu-thread", "kernel-context", "stack-frame", "catch-frame",
                "protect-frame", "handle", "meters", "seconds", "degrees",
                "uchar", "char", "short", "long", "ulong", "ushort",
                "time-frame", "byte", "field", "method", "state", "mips2c-stub"}
    # Strip leading "(" and trailing comment/idx
    body = re.sub(r";;.*$", "", new_line).strip()
    # Tokens we look at: anything matching identifier-like pattern, but NOT
    # the position-0 method name (jakx's method name is just an identifier
    # we already trust). Skip the indent + "(" + first token.
    # Simplification: tokenize the entire line, but skip token position 0
    # (the method/extern name). For methods, that's "(name args ret)".
    # Just scan all tokens — method names that already exist in jakx pass anyway.
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9?!*\-]*", body)
    # Skip first token (the name being declared)
    for tok in tokens[1:] if len(tokens) > 1 else []:
        if tok in BUILTINS:
            continue
        if tok in types_idx["deftypes"]:
            tdef_line = types_idx["deftypes"][tok]["start"]
            if tdef_line > line_idx:
                return f"{tok}(fwd@{tdef_line})"
            continue
        # Type is referenced but not in jakx deftypes at all.
        # Could be a primitive we missed, or a real fwd-ref / unknown type.
        # Skip pure-numeric tokens, opcode-like tokens, etc.
        if re.fullmatch(r"[a-zA-Z]+\d+", tok):
            # things like t9, v0, a0 — registers. unlikely in sigs but possible
            continue
        # If the token starts uppercase, it's not a GOAL type
        if tok[0].isupper():
            continue
        # Only flag if it looks like a hyphenated GOAL identifier
        if "-" in tok or len(tok) > 5:
            return f"{tok}(unknown)"
    return None


# ----------------------------------------------------------------------------
# Apply a single plan
# ----------------------------------------------------------------------------

def apply_plan(plan, all_types_text, type_casts, stack_structs, types_idx,
               check_fwd_ref=True):
    """Apply plan to in-memory state. Returns (new_all_types_text or None,
    new_type_casts, new_stack_structs, error_or_None)."""
    lines = all_types_text.splitlines(keepends=False)
    new_lines = list(lines)
    new_tc = dict(type_casts)
    new_ss = dict(stack_structs)
    diff_summary = []

    # Sort actions: do INSERT actions (extern_add, method_add) AFTER replace
    # actions and after the highest line index, to keep line indices stable.
    # Actually simpler: sort INSERTS in reverse line order so earlier inserts
    # don't shift later inserts' positions. Replaces don't shift line counts.
    inserts = [a for a in plan["actions"] if a["kind"] in ("extern_add", "method_add")]
    others = [a for a in plan["actions"] if a["kind"] not in ("extern_add", "method_add")]
    # Inserts in reverse-line-index order so insertions don't shift each other.
    def _ins_key(a):
        if a["kind"] == "extern_add":
            return a["after_line_idx"]
        return a["insert_before_line"]
    inserts.sort(key=_ins_key, reverse=True)
    ordered_actions = others + inserts

    for act in ordered_actions:
        kind = act["kind"]
        if kind == "extern_replace":
            i = act["line_idx"]
            # Sanity: new line must have balanced parens
            nl = act["new_line"]
            if nl.count("(") != nl.count(")"):
                return None, None, None, f"new-line-unbalanced-parens"
            if check_fwd_ref:
                fwd = has_fwd_ref(act["new_line"], i, types_idx)
                if fwd:
                    return None, None, None, f"fwd-ref:{fwd}"
            old = new_lines[i]
            new_lines[i] = act["new_line"]
            diff_summary.append(f"extern[{i}]: {old.strip()[:60]} -> {act['new_line'].strip()[:60]}")
        elif kind == "extern_add":
            # Insert new (define-extern X form) line right after the last
            # extern in the file. Forward-ref: any type referenced in the new
            # line must be defined at or before the insert point.
            after = act["after_line_idx"]
            nl = act["new_line"]
            if nl.count("(") != nl.count(")"):
                return None, None, None, f"new-line-unbalanced-parens"
            if check_fwd_ref:
                fwd = has_fwd_ref(act["new_line"], after, types_idx)
                if fwd:
                    return None, None, None, f"fwd-ref:{fwd}"
            new_lines.insert(after + 1, act["new_line"])
            diff_summary.append(f"extern_add[{act['extern_name']}@line {after+1}]: {nl.strip()[:60]}")
        elif kind == "method_add":
            # Insert new method line into the :methods block (just before its
            # closing line) AND update the :method-count-assert if needed.
            close_line = act["insert_before_line"]
            mca_line = act["mca_line"]
            new_mca = act["new_mca"]
            old_mca = act["old_mca"]
            nl = act["new_method_line"]
            nl_no_comment = re.sub(r";;.*$", "", nl).rstrip()
            if nl_no_comment.count("(") != nl_no_comment.count(")"):
                return None, None, None, f"new-line-unbalanced-parens"
            if check_fwd_ref:
                fwd = has_fwd_ref(nl, close_line, types_idx)
                if fwd:
                    return None, None, None, f"fwd-ref:{fwd}"
            # Update method-count-assert first (if needed) — unaffected by
            # the subsequent line insertion.
            if new_mca != old_mca and mca_line is not None:
                old_mca_line = new_lines[mca_line]
                # Replace just the integer; keep formatting.
                new_lines[mca_line] = re.sub(
                    r"(:method-count-assert\s+)\d+",
                    rf"\g<1>{new_mca}",
                    old_mca_line,
                )
                diff_summary.append(f"mca[{mca_line}]: {old_mca}->{new_mca}")
            # Insert new method line BEFORE the closing line of :methods
            new_lines.insert(close_line, nl)
            diff_summary.append(f"method_add[{act['type_name']} idx={act['jakx_idx']}]: {nl.strip()[:60]}")
        elif kind == "method_replace":
            i = act["line_idx"]
            nl = act["new_line"]
            # Strip the trailing comment for paren count check
            nl_no_comment = re.sub(r";;.*$", "", nl).rstrip()
            if nl_no_comment.count("(") != nl_no_comment.count(")"):
                return None, None, None, f"new-line-unbalanced-parens"
            if check_fwd_ref:
                fwd = has_fwd_ref(act["new_line"], i, types_idx)
                if fwd:
                    return None, None, None, f"fwd-ref:{fwd}"
            old = new_lines[i]
            new_lines[i] = act["new_line"]
            diff_summary.append(f"method[{i} {act['type_name']} idx={act['jakx_idx']}]: "
                                f"renumber src={act['src_idx']}->jakx={act['jakx_idx']} "
                                f"name={act['old_mname']}->{act['src_mname']}")
        elif kind == "type_casts_set":
            new_tc[act["fn_name"]] = act["value"]
            diff_summary.append(f"type_casts[{act['fn_name']}] set ({len(act['value'])} entries, had_existing={act['had_existing']})")
        elif kind == "stack_structure_set":
            new_ss[act["fn_name"]] = act["value"]
            diff_summary.append(f"stack_structure[{act['fn_name']}] set ({len(act['value'])} entries, had_existing={act['had_existing']})")
        else:
            return None, None, None, f"unknown-action:{kind}"

    return "\n".join(new_lines) + "\n", new_tc, new_ss, ", ".join(diff_summary)


def write_jsonc_with_header(path, data, header_comment):
    """Write JSON with a leading line comment (jsonc style)."""
    body = json.dumps(data, indent=2)
    text = f"// {header_comment}\n" + body + "\n"
    path.write_text(text)


def write_jsonc_preserving_format(path, data):
    """Plain rewrite — we lose existing comments but jsonc is OK with pure JSON."""
    path.write_text(json.dumps(data, indent=2) + "\n")


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------

def run_git(args, check=True):
    r = subprocess.run(["git"] + args, cwd=ROOT, capture_output=True, text=True)
    if check and r.returncode != 0:
        sys.stderr.write(f"git {args} FAILED: {r.stderr}\n")
        sys.exit(1)
    return r


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max", type=int, default=500,
                        help="Max candidates to apply this run (default 500).")
    parser.add_argument("--limit-corpus", default=None,
                        help="Comma-separated corpus filter (e.g. jak2,jak3).")
    parser.add_argument("--limit-tier", default=None,
                        help="tier-A or tier-B")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--input", default=str(JSON_INPUT))
    parser.add_argument("--list-only", action="store_true",
                        help="Just emit candidate list, don't apply.")
    parser.add_argument("--cycle-tag", default="V6",
                        help="Tag for output artifact names (V6, V7, ...)")
    parser.add_argument("--blacklist-json", default=str(TYPE_BLACKLIST_PATH))
    parser.add_argument("--no-skip-zero-error", action="store_true")
    parser.add_argument("--no-skip-curated", action="store_true")
    parser.add_argument("--no-method-add", action="store_true",
                        help="Disable method-add path (riskier; default ON in v6).")
    parser.add_argument("--no-extern-add", action="store_true",
                        help="Disable extern-add path (low-risk; default ON in v6).")
    parser.add_argument("--method-add-max-gap", type=int, default=4,
                        help="Max gap above current method-count-assert "
                             "for method-add insertions (default 4).")
    parser.add_argument("--extra-blacklist-json", action="append", default=[],
                        help="Additional blacklist JSON files to merge into "
                             "banned types (cumulative across cycles).")
    args = parser.parse_args()
    LOG_OUT = ROOT / ".jakx_watch" / "research" / f"{args.cycle_tag}_APPLY_LOG.md"
    CAND_LIST_OUT = ROOT / ".jakx_watch" / "research" / f"{args.cycle_tag}_CANDIDATE_LIST.json"

    print(f"[{args.cycle_tag}] loading {args.input}", file=sys.stderr)
    data = json.loads(Path(args.input).read_text())

    print(f"[{args.cycle_tag}] indexing all-types.gc ...", file=sys.stderr)
    all_types_text = ALL_TYPES.read_text(encoding="utf-8")
    types_idx = index_all_types(all_types_text)

    type_casts = load_jsonc(TYPE_CASTS) if TYPE_CASTS.exists() else {}
    stack_structs = load_jsonc(STACK_STRUCTS) if STACK_STRUCTS.exists() else {}

    matches = data.get("matches", [])
    print(f"[{args.cycle_tag}] {len(matches)} matches in input, {sum(1 for m in matches if m.get('candidate_patch'))} with patches", file=sys.stderr)

    # Build context for v6
    banned_types = set()
    if Path(args.blacklist_json).exists():
        bl = json.loads(Path(args.blacklist_json).read_text())
        banned_types = set(bl.get("banned_types", []))
        print(f"[{args.cycle_tag}] loaded {len(banned_types)} banned types from {args.blacklist_json}", file=sys.stderr)
    for extra in args.extra_blacklist_json:
        if Path(extra).exists():
            bl = json.loads(Path(extra).read_text())
            extra_banned = set(bl.get("banned_types", []))
            new_count = len(extra_banned - banned_types)
            banned_types |= extra_banned
            print(f"[{args.cycle_tag}] +{new_count} banned types from {extra} (total {len(banned_types)})", file=sys.stderr)
    # Compute jakx file errors (from current decompiler_out)
    jakx_file_errors = {}
    jakx_ir2_dir = ROOT / "decompiler_out" / "jakx"
    if jakx_ir2_dir.exists():
        for f in jakx_ir2_dir.glob("*_ir2.asm"):
            try:
                t = f.read_text(encoding="utf-8", errors="replace")
                jakx_file_errors[f.name[:-len("_ir2.asm")]] = t.count(";; ERROR")
            except Exception:
                pass
    print(f"[{args.cycle_tag}] indexed {len(jakx_file_errors)} jakx files for error counts", file=sys.stderr)

    ctx = {
        "banned_types": banned_types,
        "jakx_file_errors": jakx_file_errors,
        "skip_zero_error_files": not args.no_skip_zero_error,
        "skip_curated_slots": not args.no_skip_curated,
        "enable_extern_add": not args.no_extern_add,
        "enable_method_add": not args.no_method_add,
        "method_add_max_gap": args.method_add_max_gap,
    }

    # Classify
    plans = []
    skips = defaultdict(list)
    for m in matches:
        if not m.get("candidate_patch"):
            continue
        if args.limit_corpus and m["source_corpus"] not in args.limit_corpus.split(","):
            continue
        decision = classify_candidate(m, types_idx, ctx=ctx)
        if decision["action"] == "apply":
            if args.limit_tier and decision["plan"]["tier"] != args.limit_tier:
                continue
            plans.append(decision["plan"])
        else:
            skips[decision["reason"]].append((m["jakx_fn"], m["jakx_file"], m["source_corpus"]))

    print(f"[{args.cycle_tag}] classify: {len(plans)} apply, {sum(len(v) for v in skips.values())} skip", file=sys.stderr)
    for reason, items in sorted(skips.items(), key=lambda kv: -len(kv[1])):
        print(f"   skip {reason}: {len(items)}", file=sys.stderr)

    # v7 rank: by confidence score (descending), then file-error desc, then n_instr.
    rank_lookup = {(m["jakx_fn"], m["jakx_file"]): m for m in matches}
    def rank_key(p):
        m = rank_lookup[(p["jakx_fn"], p["jakx_file"])]
        return (
            -p.get("score", 0.0),
            -m.get("jakx_file_errors", 0),
            -m["n_instr"],
        )
    plans.sort(key=rank_key)

    plans_to_apply = plans[: args.max]
    print(f"[{args.cycle_tag}] applying top {len(plans_to_apply)} of {len(plans)} eligible plans", file=sys.stderr)

    # Save full candidate list
    CAND_LIST_OUT.parent.mkdir(parents=True, exist_ok=True)
    CAND_LIST_OUT.write_text(json.dumps({
        "total_eligible": len(plans),
        "applied_this_run": len(plans_to_apply),
        "skip_summary": {k: len(v) for k, v in skips.items()},
        "skips": {k: v for k, v in skips.items()},
        "plans": plans_to_apply,
    }, indent=2, default=str))
    print(f"[{args.cycle_tag}] wrote candidate list -> {CAND_LIST_OUT}", file=sys.stderr)

    if args.list_only or args.dry_run:
        if args.dry_run:
            # Simulate apply
            for p in plans_to_apply[:20]:
                d = apply_plan(p, all_types_text, type_casts, stack_structs, types_idx)
                print(f"  PLAN {p['jakx_fn']}: {d[3] if d[0] else 'FAIL '+d[3]}", file=sys.stderr)
        return

    # ---- Apply loop: one commit per plan
    log_lines = ["# V3 broad-apply log\n"]
    log_lines.append(f"## Stats\n")
    log_lines.append(f"- input: {args.input}\n")
    log_lines.append(f"- eligible plans: {len(plans)}\n")
    log_lines.append(f"- applied this run: {len(plans_to_apply)}\n")
    log_lines.append(f"- skip summary: {dict((k, len(v)) for k, v in skips.items())}\n\n")

    applied = 0
    fwd_ref_skip = 0
    apply_fail = 0
    runtime_ok = 0

    # V6 line-drift fix: don't trust pre-built plan["actions"] line indices —
    # they go stale after method_add / extern_add INSERT shifts the file.
    # Build a list of (plan, original_match) pairs then RE-CLASSIFY each from
    # the original match using the FRESH types_idx at apply time.
    plan_to_match = {(p["jakx_fn"], p["jakx_file"]): rank_lookup[(p["jakx_fn"], p["jakx_file"])]
                     for p in plans_to_apply}

    for n, plan in enumerate(plans_to_apply, 1):
        # FRESH RE-CLASSIFY against current types_idx — picks up new line numbers
        # post-prior INSERTs. Skip if classification suddenly fails (e.g. parent
        # plan added a duplicate name).
        m = plan_to_match[(plan["jakx_fn"], plan["jakx_file"])]
        decision = classify_candidate(m, types_idx, ctx=ctx)
        if decision["action"] != "apply":
            log_lines.append(f"- SKIP `{plan['jakx_fn']}` @ {plan['jakx_file']} (reclassify): {decision['reason']}\n")
            apply_fail += 1
            continue
        plan = decision["plan"]
        new_at, new_tc, new_ss, info = apply_plan(
            plan, all_types_text, type_casts, stack_structs, types_idx
        )
        if new_at is None:
            log_lines.append(f"- SKIP `{plan['jakx_fn']}` @ {plan['jakx_file']} <- {plan['src_corpus']} ({plan['tier']}): {info}\n")
            if info and info.startswith("fwd-ref"):
                fwd_ref_skip += 1
            else:
                apply_fail += 1
            continue

        # Write changes
        ALL_TYPES.write_text(new_at)
        if new_tc != type_casts:
            write_jsonc_preserving_format(TYPE_CASTS, new_tc)
        if new_ss != stack_structs:
            write_jsonc_preserving_format(STACK_STRUCTS, new_ss)

        # Re-index for subsequent plans (so method/extern lookups stay valid)
        all_types_text = new_at
        type_casts = new_tc
        stack_structs = new_ss
        types_idx = index_all_types(all_types_text)

        # Commit
        files_to_add = ["decompiler/config/jakx/all-types.gc"]
        if new_tc != load_jsonc(TYPE_CASTS) or True:  # always include if touched
            pass
        # Detect which files actually changed
        run_git(["add", "decompiler/config/jakx/all-types.gc",
                 "decompiler/config/jakx/ntsc_v1/type_casts.jsonc",
                 "decompiler/config/jakx/ntsc_v1/stack_structures.jsonc"])

        score = plan.get("score", 0.0)
        msg_lines = [
            f"cand: {plan['jakx_fn']} @ {plan['jakx_file']} <- {plan['src_corpus']} ({plan['tier']}) score={score:.2f}",
            "",
            f"{args.cycle_tag}-broad-apply candidate #{n}",
            f"actions: {info}",
        ]
        commit_msg = "\n".join(msg_lines)
        r = subprocess.run(
            ["git", "commit", "-m", commit_msg, "--allow-empty"],
            cwd=ROOT, capture_output=True, text=True,
        )
        if r.returncode != 0:
            sys.stderr.write(f"[{args.cycle_tag}] commit failed for {plan['jakx_fn']}: {r.stderr}\n")
            apply_fail += 1
            continue

        sha = run_git(["rev-parse", "HEAD"]).stdout.strip()[:9]
        log_lines.append(f"- APPLY `{plan['jakx_fn']}` @ {plan['jakx_file']} <- {plan['src_corpus']} ({plan['tier']}) sha={sha}: {info}\n")
        applied += 1
        if n % 20 == 0:
            print(f"[{args.cycle_tag}] {n}/{len(plans_to_apply)} ({applied} applied)", file=sys.stderr)

    log_lines.append(f"\n## Final tally\n- applied: {applied}\n- fwd-ref skipped: {fwd_ref_skip}\n- apply-fail: {apply_fail}\n")
    LOG_OUT.parent.mkdir(parents=True, exist_ok=True)
    LOG_OUT.write_text("".join(log_lines))
    print(f"\n[" + args.cycle_tag + "] DONE: applied={applied} fwd-ref={fwd_ref_skip} fail={apply_fail}", file=sys.stderr)
    print(f"[{args.cycle_tag}] log -> {LOG_OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
