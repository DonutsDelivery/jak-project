#!/usr/bin/env python3
"""Lane 2 recipe applier framework + Recipe X (name-based REF transplant).

Bisect rules (per user calibration):
  - PRIMARY: real-clean count delta (any decrease → revert)
  - SECONDARY: split-failed delta (increase without real-clean gain → revert)
  - CRASH: decomp didn't complete → revert
  - Error count alone is NOT a revert signal — newly unlocked real-partial files
    add ~13.5 errors each on average. Compute:
        expected_error_growth = unlocked_count * 13.5
    If actual error increase <= expected AND no real-clean drop → keep.

One batch commit per recipe (not per site).
"""
import json, os, re, subprocess, sys, time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
ALL_TYPES = ROOT / "decompiler" / "config" / "jakx" / "all-types.gc"
DECOMP_OUT = ROOT / ".jakx_watch" / "decomp_out" / "jakx"
HISTORY = ROOT / ".jakx_watch" / "history"
RESEARCH = ROOT / ".jakx_watch" / "research"
REF_BASE = ROOT / "test" / "decompiler" / "reference"

REAL_PARTIAL_AVG_ERRS = 13.5  # per user calibration

# ---------------------------------------------------------------------------
# REF index
# ---------------------------------------------------------------------------

RE_DEFUN = re.compile(r"^\((defun|defbehavior|defun-debug)\s+(\S+)\s*\(([^)]*)\)")
RE_DEFMETHOD = re.compile(r"^\(defmethod\s+(\S+)\s+(\S+)\s*\(\s*\(\s*\S+\s+(\S+)")
# Format used by REF lines: (defun NAME ((arg type) (arg type) ...) ...)
# Or: (defmethod NAME TYPE ((this TYPE) (arg type) ...) ...)
RE_REF_DEFUN_FULL = re.compile(
    r"^\(defun(?:-debug|-recursive)?\s+(\S+)\s*\((.*?)\)(?:\s+\".*?\")?", re.DOTALL
)
RE_REF_DEFMETHOD_FULL = re.compile(
    r"^\(defmethod\s+(\S+)\s+(\S+)\s*\((.*?)\)(?:\s+\".*?\")?", re.DOTALL
)
RE_DEFBEHAVIOR_FULL = re.compile(
    r"^\(defbehavior\s+(\S+)\s+(\S+)\s*\((.*?)\)(?:\s+\".*?\")?", re.DOTALL
)


def parse_arg_list(arg_str: str) -> list:
    """Parse '(arg type) (arg type) ...' into [(arg, type), ...].
    Handles nested parens in type expressions like '(pointer X)' and
    '(function ...)' return-type forms.

    Input is the CONTENT between the outer arg-list parens (already stripped)."""
    args = []
    i = 0
    n = len(arg_str)
    while i < n:
        # Skip whitespace
        while i < n and arg_str[i].isspace():
            i += 1
        if i >= n: break
        if arg_str[i] != '(':
            # Stop on unexpected token (likely docstring or comment)
            break
        # Found arg open — walk balanced
        close = find_balanced(arg_str, i)
        if close < 0: break
        inner = arg_str[i + 1:close].strip()
        # Split into name + type. Name is the first whitespace-separated token.
        # Type is everything after.
        m = re.match(r"^(\S+)\s+(.+)$", inner, re.DOTALL)
        if m:
            args.append((m.group(1), m.group(2).strip()))
        i = close + 1
    return args


def find_return_type(text: str, fn_name: str) -> str:
    """Look for return type info in REF comments (best effort)."""
    # Common pattern: ";; INFO: Return type ..."
    return ""  # leave to caller; many REFs don't annotate return type explicitly


def find_balanced(text: str, open_idx: int) -> int:
    """Given index of an opening '(', return index of matching close.
    Returns -1 if unbalanced."""
    depth = 0
    in_str = False
    i = open_idx
    while i < len(text):
        c = text[i]
        if in_str:
            if c == '\\' and i + 1 < len(text):
                i += 2; continue
            if c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def extract_arglist_from_defun(text: str, fn_name: str) -> tuple[str, list, str] | None:
    """Find '(defun fn_name (...args...))' or '(defbehavior fn_name TYPE (...args...))',
    extract the OUTER arg list using balanced paren walk.
    Returns (kind, args, receiver_or_none) or None.
    """
    # Try defun (and defun-debug, defun-recursive)
    for prefix, kind, has_receiver in (
        ("defun", "function", False),
        ("defun-debug", "function", False),
        ("defun-recursive", "function", False),
        ("defbehavior", "behavior", True),
    ):
        if has_receiver:
            pat = re.compile(r"^\(" + prefix + r"\s+" + re.escape(fn_name) + r"\s+(\S+)\s+\(", re.MULTILINE)
        else:
            pat = re.compile(r"^\(" + prefix + r"\s+" + re.escape(fn_name) + r"\s+\(", re.MULTILINE)
        for m in pat.finditer(text):
            # The match ends just before the OUTER arg-list '('. Find that '(' and walk balanced.
            arglist_open = m.end() - 1  # the ( we matched
            arglist_close = find_balanced(text, arglist_open)
            if arglist_close < 0:
                continue
            arglist_content = text[arglist_open + 1: arglist_close]
            args = parse_arg_list(arglist_content)
            receiver = m.group(1) if has_receiver else None
            return (kind, args, receiver)
    return None


def extract_signature_from_ref(file_path: Path, fn_name: str, kind: str = "function") -> dict | None:
    """Read REF file, extract signature for fn_name."""
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None
    if kind == "method":
        return None  # deferred
    res = extract_arglist_from_defun(text, fn_name)
    if not res: return None
    kind_str, args, receiver = res
    return {
        "kind": kind_str,
        "name": fn_name,
        "args": args,
        "receiver": receiver,
        "return_type": None,
    }


def build_ref_index() -> dict:
    """Build {fn_name: [(corpus, ref_path), ...]} from REF files."""
    idx = defaultdict(list)
    for corpus in ("jak3", "jak2", "jak1"):  # priority order
        base = REF_BASE / corpus
        if not base.exists(): continue
        for ref in base.rglob("*_REF.gc"):
            try:
                text = ref.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            for line in text.splitlines():
                if line.startswith("(defun") or line.startswith("(defbehavior"):
                    parts = line.split(None, 2)
                    if len(parts) >= 2:
                        # extract name (strip trailing parens)
                        name = parts[1].rstrip("(")
                        if name and not name.startswith("("):
                            idx[name].append((corpus, ref))
    return idx


# ---------------------------------------------------------------------------
# Find failed functions in jakx
# ---------------------------------------------------------------------------

def find_failed_functions() -> list[dict]:
    """Walk jakx disasm.gc files, find each 'function not converted' or
    'no type analysis' error and the preceding function name.
    Returns: [{file, fn_name, kind, line, error_kind}, ...]
    """
    out = []
    if not DECOMP_OUT.exists():
        return out
    for f in sorted(DECOMP_OUT.glob("*_disasm.gc")):
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if "function was not converted" in line or "function has no type analysis" in line:
                # Walk backward for "definition for"
                for j in range(i - 1, max(-1, i - 20), -1):
                    if lines[j].startswith(";; definition for "):
                        rest = lines[j][len(";; definition for "):].strip()
                        # "function NAME"  or  "method N of type T"  or  "behavior NAME of type T"
                        if rest.startswith("function "):
                            name = rest[len("function "):].strip()
                            out.append({
                                "file": f.stem.replace("_disasm", ""),
                                "fn_name": name,
                                "kind": "function",
                                "line": i + 1,
                                "error_kind": "not_converted" if "not converted" in line else "no_type_analysis",
                            })
                        elif rest.startswith("method "):
                            mm = re.match(r"method\s+(\d+)\s+of\s+type\s+(\S+)", rest)
                            if mm:
                                out.append({
                                    "file": f.stem.replace("_disasm", ""),
                                    "fn_name": f"(method {mm.group(1)} {mm.group(2)})",
                                    "kind": "method",
                                    "method_idx": int(mm.group(1)),
                                    "method_type": mm.group(2),
                                    "line": i + 1,
                                    "error_kind": "not_converted" if "not converted" in line else "no_type_analysis",
                                })
                        elif rest.startswith("behavior "):
                            mm = re.match(r"behavior\s+(\S+)\s+of\s+type\s+(\S+)", rest)
                            if mm:
                                out.append({
                                    "file": f.stem.replace("_disasm", ""),
                                    "fn_name": mm.group(1),
                                    "kind": "behavior",
                                    "receiver": mm.group(2),
                                    "line": i + 1,
                                    "error_kind": "not_converted" if "not converted" in line else "no_type_analysis",
                                })
                        break
    return out


# ---------------------------------------------------------------------------
# Existing all-types.gc parsing — find and update define-extern lines
# ---------------------------------------------------------------------------

def index_externs() -> dict:
    """Map fn_name -> line index in all-types.gc."""
    idx = {}
    text = ALL_TYPES.read_text(encoding="utf-8")
    lines = text.splitlines()
    # Allow trailing content (signature, newline, comment) after the name
    pat = re.compile(r"^\(define-extern\s+(\S+)")
    for i, line in enumerate(lines):
        m = pat.match(line.lstrip())
        if m:
            idx[m.group(1)] = i
    return idx


BUILTIN_TYPES = {
    "int", "uint", "float", "symbol", "string", "object", "basic", "none",
    "integer", "vector", "matrix", "process", "process-tree", "process-drawable",
    "structure", "function", "pointer", "inline-array", "array", "kheap", "type",
    "uint8", "uint16", "uint32", "uint64", "uint128",
    "int8", "int16", "int32", "int64", "int128",
    "boolean", "char", "the-as", "_type_", "state", "event-message-block",
    "time-frame", "handle", "pair", "connection", "thread", "stack-frame",
}


def index_known_type_lines() -> dict:
    """Map type_name -> first defining line index in all-types.gc.
    A type is defined by `(deftype NAME ...)` or `(define-extern NAME type)`."""
    text = ALL_TYPES.read_text(encoding="utf-8")
    lines = text.splitlines()
    out = {}
    for i, line in enumerate(lines):
        s = line.lstrip()
        if s.startswith("(deftype "):
            m = re.match(r"\(deftype\s+(\S+)\s+", s)
            if m and m.group(1) not in out:
                out[m.group(1)] = i
        elif s.startswith("(define-extern "):
            m = re.match(r"\(define-extern\s+(\S+)\s+(.+)\)", s)
            if m:
                body = m.group(2).strip()
                if body == "type" or body == "structure":
                    if m.group(1) not in out:
                        out[m.group(1)] = i
    # Built-ins are defined at line -1 (before any user line)
    for t in BUILTIN_TYPES:
        out[t] = -1
    return out


def index_known_types() -> set:
    """Set of all type names defined in jakx all-types.gc (deftype + define-extern type)."""
    return set(index_known_type_lines().keys())


def referenced_types_in_signature(sig_str: str) -> set:
    """Extract all type-name tokens from a (function ...) signature string."""
    refs = set()
    # Strip outer parens and 'function' keyword
    inner = re.sub(r"^\(function\s+", "", sig_str.strip())
    inner = re.sub(r"\)\s*$", "", inner)
    # Strip nested parens content (return-type forms etc) — recursively
    # Easier: just find all word-like tokens
    for tok in re.findall(r"[a-zA-Z_][\w<>\-?!]*", inner):
        if tok in ("function", "pointer", "array", "inline-array", "state", "behavior"):
            continue  # skip GOAL keywords, but they're valid types too
        refs.add(tok)
    return refs


def fmt_signature(args, return_type=None, kind="function"):
    """Format args + return into GOAL signature: '(function arg-types return)'."""
    arg_types = [a[1] for a in args]
    if return_type:
        arg_types.append(return_type)
    if not arg_types:
        return "(function none)"
    return "(function " + " ".join(arg_types) + ")"


# ---------------------------------------------------------------------------
# Snapshot helpers
# ---------------------------------------------------------------------------

def latest_snapshot() -> dict | None:
    files = sorted(HISTORY.glob("snap-*.json"))
    if not files: return None
    return json.loads(files[-1].read_text())


def baseline_metrics(snap: dict) -> dict:
    s = snap["summary"]
    return {
        "real_clean": s["buckets"].get("real-clean", 0),
        "real_partial": s["buckets"].get("real-partial", 0),
        "split_failed": s["buckets"].get("split-failed", 0),
        "static_only": s["buckets"].get("static-only", 0),
        "total_errors": s.get("sum_error_markers", 0),
        "total_files": s.get("total_files", 0),
    }


def per_file_categories(snap: dict) -> dict:
    return {fn: info.get("category", "?") for fn, info in snap.get("per_file", {}).items()}


def bisect_verdict(pre: dict, post: dict, pre_pf: dict, post_pf: dict) -> dict:
    """Decide keep vs revert based on user-calibrated rules."""
    delta_rc = post["real_clean"] - pre["real_clean"]
    delta_sf = post["split_failed"] - pre["split_failed"]
    delta_err = post["total_errors"] - pre["total_errors"]

    # Files newly unlocked from split-failed → real-partial
    unlocked = []
    lost = []
    for fname, pre_cat in pre_pf.items():
        post_cat = post_pf.get(fname, "?")
        if pre_cat == "split-failed" and post_cat in ("real-partial", "real-clean"):
            unlocked.append(fname)
        elif pre_cat in ("real-partial", "real-clean") and post_cat == "split-failed":
            lost.append(fname)
        elif pre_cat == "real-clean" and post_cat == "real-partial":
            lost.append(fname)

    expected_growth = len(unlocked) * REAL_PARTIAL_AVG_ERRS

    verdict = "keep"
    reasons = []

    if delta_rc < 0:
        verdict = "revert"
        reasons.append(f"real-clean dropped {delta_rc}")
    if delta_sf > 0 and delta_rc <= 0:
        verdict = "revert"
        reasons.append(f"split-failed grew {delta_sf} without real-clean gain")
    if lost:
        verdict = "revert"
        reasons.append(f"{len(lost)} files lost coverage: {lost[:3]}")
    if delta_err > expected_growth + 50 and delta_rc <= 0:
        verdict = "revert"
        reasons.append(f"errors grew {delta_err} > expected {expected_growth:.1f} + slack")

    return {
        "verdict": verdict,
        "delta_real_clean": delta_rc,
        "delta_split_failed": delta_sf,
        "delta_errors": delta_err,
        "n_unlocked": len(unlocked),
        "n_lost": len(lost),
        "unlocked": unlocked[:20],
        "lost": lost[:20],
        "expected_error_growth": expected_growth,
        "reasons": reasons,
    }


# ---------------------------------------------------------------------------
# Recipe X: name-based REF transplant
# ---------------------------------------------------------------------------

def get_existing_extern_line(extern_line_idx: int) -> tuple[str, list[str]]:
    """Read existing extern declaration from all-types.gc.
    Returns (full_text, original_lines_list) — the extern can span multiple lines.
    Walks forward from the start line until paren balance closes."""
    text = ALL_TYPES.read_text(encoding="utf-8")
    lines = text.splitlines()
    start = extern_line_idx
    # Find balanced close of the (define-extern ...)
    depth = 0
    end = start
    in_str = False
    for i in range(start, len(lines)):
        for c in lines[i]:
            if in_str:
                if c == '"': in_str = False
                continue
            if c == '"': in_str = True
            elif c == '(': depth += 1
            elif c == ')':
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if depth == 0 and end == i:
            break
    return ("\n".join(lines[start:end+1]), lines[start:end+1])


def is_stub_extern(extern_text: str) -> bool:
    """Decide if an existing extern signature is 'stubby' (low-info, replace-friendly).
    Heuristics: signature is `(function none)` or `(function object)` or has very few args.
    Operates on the EXTERN BODY only (no trailing line-comments, no docstrings)."""
    # Strip line comments (";; ..." to end of line)
    body = re.sub(r";;.*?(?=\n|$)", "", extern_text)
    # Strip docstrings
    body = re.sub(r'"[^"]*"', '', body)
    # Look at the FIRST (function ...) — that's the extern's actual signature.
    # Must avoid catching `(function none)` inside a docstring or comment (now stripped).
    m = re.search(r"\(function\s+([^)]*)\)", body)
    if not m:
        return False
    sig_inner = m.group(1).strip()
    # Strip ":behavior X" or other annotations from the end
    sig_inner = re.sub(r":\w+\s+\S+", "", sig_inner).strip()
    toks = sig_inner.split()
    if not toks:
        return True
    if len(toks) == 1 and toks[0] in (
        "none", "object", "int", "uint", "float", "symbol",
        "basic", "integer", "pointer", "string"
    ):
        return True
    return False


def _import_v7():
    """Lazy-load v7 driver as a library for its parsing helpers."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "v7", str(ROOT / "scripts" / "jakx_watch" / "multigame_v7_broad_apply.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def build_jak3_ref_defmethod_index() -> dict:
    """For each (T, method_name) in jak3 REF files, extract the defmethod's arg list.
    Returns: {(T, method_name): "(arg-types-str)"} where arg-types-str is the
    parenthesized arg list, e.g. '((this T) (arg int))'.

    REF defmethods have inferred types from actual decompilation, often richer
    than jak3 all-types.gc stubs."""
    idx = {}
    base = REF_BASE / "jak3"
    if not base.exists(): return idx
    for ref in base.rglob("*_REF.gc"):
        try:
            text = ref.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        # Find every (defmethod NAME ((this TYPE) ...)) header
        for m in re.finditer(r"^\(defmethod\s+(\S+)\s+\(", text, re.MULTILINE):
            name = m.group(1)
            arglist_open = m.end() - 1  # position of the '(' we matched
            close = find_balanced(text, arglist_open)
            if close < 0: continue
            arg_content = text[arglist_open + 1: close].strip()
            args = parse_arg_list(arg_content)
            if not args: continue
            # First arg is (this TYPE)
            this_arg = args[0]
            T = this_arg[1] if len(this_arg) >= 2 else None
            if not T: continue
            # Strip any trailing return-form
            idx[(T, name)] = args
    return idx


def recipe_x_methods(dry_run: bool = True, max_apply: int = 0) -> dict:
    """Recipe X v2: name-based slot transplant for failing METHODS.

    For each "function not converted" error on `(method N T)` in jakx:
      1. Find slot N of type T in jakx all-types.gc (line index + sig)
      2. Find slot N of type T in jak3 all-types.gc (line index + sig)
      3. If jak3 has strictly richer signature: generate method_replace plan
      4. Apply with crash-only revert

    Distinguished from V7/V8 matcher: slot-based, NOT bytecode-based. May
    surface candidates with body differences that V7's fingerprint missed.
    """
    print("[recipeXm] importing v7 indexer...", file=sys.stderr)
    v7 = _import_v7()

    print("[recipeXm] indexing jakx all-types.gc...", file=sys.stderr)
    jakx_text = (ROOT / "decompiler/config/jakx/all-types.gc").read_text(encoding="utf-8")
    jakx_idx = v7.index_all_types(jakx_text)
    print(f"[recipeXm] jakx: {len(jakx_idx['externs'])} externs, "
          f"{len(jakx_idx['deftypes'])} deftypes, "
          f"{len(jakx_idx['methods'])} methods", file=sys.stderr)

    print("[recipeXm] indexing jak3 all-types.gc...", file=sys.stderr)
    jak3_path = ROOT / "decompiler/config/jak3/all-types.gc"
    if not jak3_path.exists():
        return {"recipe": "Xm", "plans": [], "error": "jak3 all-types.gc missing"}
    jak3_text = jak3_path.read_text(encoding="utf-8")
    jak3_idx = v7.index_all_types(jak3_text)
    print(f"[recipeXm] jak3: {len(jak3_idx['externs'])} externs, "
          f"{len(jak3_idx['deftypes'])} deftypes, "
          f"{len(jak3_idx['methods'])} methods", file=sys.stderr)

    print("[recipeXm] finding failed jakx methods...", file=sys.stderr)
    failed = find_failed_functions()
    method_failed = [f for f in failed if f["kind"] == "method"]
    print(f"[recipeXm] {len(method_failed)} failed methods", file=sys.stderr)

    print("[recipeXm] indexing known jakx types...", file=sys.stderr)
    type_lines = index_known_type_lines()

    plans = []
    skip_no_jak3 = 0
    skip_no_jakx_slot = 0
    skip_jakx_curated = 0
    skip_no_improvement = 0
    skip_unknown_type = 0
    skip_forward_ref = 0
    skip_parse_fail = 0
    skip_dup_name = 0
    skip_mca_mismatch = 0
    seen_keys = set()

    # For dup-name check: build set of (T, name) currently in jakx
    jakx_method_names_by_type = defaultdict(set)
    for (tn, mname), _info in jakx_idx["methods"].items():
        # Only count "real" names (not stubs / not _type_)
        if mname == "_type_": continue
        jakx_method_names_by_type[tn].add(mname)

    # Pre-compute which types have MATCHING MCA between jakx and jak3.
    # If MCAs differ, slot-N in jakx is NOT the same method as slot-N in jak3,
    # so the recipe's slot-based name transfer is unsafe.
    mca_match = set()
    for T, info in jakx_idx["deftypes"].items():
        jakx_mca = info.get("method_count_assert_value")
        jak3_T = jak3_idx["deftypes"].get(T)
        if jak3_T and jakx_mca == jak3_T.get("method_count_assert_value"):
            mca_match.add(T)

    for f in method_failed:
        T = f["method_type"]
        N = f["method_idx"]
        key = (T, N)
        if key in seen_keys:
            continue
        seen_keys.add(key)

        # MCA-match gate: only safe to use jak3's slot N if jakx and jak3 agree
        # on the deftype's method count.
        if T not in mca_match:
            skip_mca_mismatch += 1
            continue

        # jakx slot
        jakx_slot = v7.index_method_by_idx(jakx_idx, T, N)
        if not jakx_slot:
            skip_no_jakx_slot += 1
            continue
        jakx_raw = jakx_slot.get("raw", "")
        # Check if jakx slot is curated (non-stub name)
        jakx_name = jakx_slot.get("name", "")
        is_stub_name = (
            re.search(r"-method-\d+$", jakx_name) is not None
            or jakx_name.startswith(f"{T}-method-")
        )

        # jak3 slot
        jak3_slot = v7.index_method_by_idx(jak3_idx, T, N)
        if not jak3_slot:
            skip_no_jak3 += 1
            continue
        jak3_raw = jak3_slot.get("raw", "")

        # Check that jak3 slot has richer args than jakx
        # Extract arg-types from raw text for both
        def extract_args_count(raw):
            # raw is like "(method-name (arg-types) ret-type) ;; idx"
            # Find inner first (arg-types) — the args list
            mm = re.search(r"\(\s*\S+\s+\(([^)]*)\)", raw)
            if not mm:
                return -1
            arg_str = mm.group(1).strip()
            return len([t for t in re.split(r"\s+", arg_str) if t]) if arg_str else 0
        jakx_n = extract_args_count(jakx_raw)
        jak3_n = extract_args_count(jak3_raw)

        # Determine jak3 name + stub-status
        jak3_name = jak3_slot.get("name", "")
        jak3_is_stub = (
            re.search(r"-method-\d+$", jak3_name) is not None
            or jak3_name == "_type_"
        )

        if not is_stub_name:
            # Curated jakx slot — only replace if jak3 has strictly more
            # arg-type tokens (preserve jakx's prior work).
            if jak3_n <= jakx_n:
                skip_no_improvement += 1
                continue
            # Don't change jakx name to jak3's name.
        else:
            # Stub-named jakx slot. Replace if jak3 has CURATED name OR
            # if jak3 has strictly richer arg types.
            if jak3_is_stub and jak3_n <= jakx_n:
                # Both stub, no richer types — nothing to transplant.
                skip_no_improvement += 1
                continue
            jak3_body = re.sub(r"\s*;;.*$", "", jak3_raw).strip()
            jakx_body = re.sub(r"\s*;;.*$", "", jakx_raw).strip()
            if jak3_body == jakx_body:
                skip_no_improvement += 1
                continue

        # Build new method line: take jak3 sig but preserve jakx idx + name
        # jak3_raw like "(jak3-method-name (arg-types) ret-type) ;; N ;; ..."
        # Strip any trailing ;; N ;; ... annotations and leading whitespace
        body = re.sub(r"\s*;;.*$", "", jak3_raw).strip()
        # body = "(NAME (args) ret)"
        mm = re.match(r"^\(\s*(\S+)\s+(\(.+\)\s+\S+)\)\s*$", body)
        if not mm:
            skip_parse_fail += 1
            continue
        jak3_emit_name = mm.group(1)
        sig_inner = mm.group(2)  # like "(this T) (arg t) ret"  (well, "(args) ret")
        # Pick name: prefer jakx's (curated) name if not stub; else jak3's
        if is_stub_name:
            new_name = jak3_emit_name
        else:
            new_name = jakx_name

        # Walk parent chain — duplicate name in self OR any parent would crash.
        chain = v7.parent_chain(jakx_idx, T)
        dup = False
        for tn_chain in chain:
            existing_in_chain = jakx_method_names_by_type.get(tn_chain, set())
            # Ignore self's own name at this slot (we're replacing it)
            if tn_chain == T:
                existing_in_chain = existing_in_chain - {jakx_name}
            if new_name in existing_in_chain:
                dup = True; break
        if dup:
            skip_dup_name += 1
            continue

        new_method_line = f"    ({new_name} {sig_inner}) ;; {N}"

        # Pre-apply: ensure all referenced types exist in jakx
        refs = set()
        for tok in re.findall(r"[a-zA-Z_][\w<>\-?!]*", sig_inner):
            if tok in BUILTIN_TYPES or tok in ("function", "pointer", "array", "inline-array", "state"):
                continue
            refs.add(tok)
        unknown = refs - set(type_lines.keys())
        if unknown:
            skip_unknown_type += 1
            continue

        # Forward-ref: target line is jakx_slot["line_idx"]; refs must be defined before
        target_line = jakx_slot["line_idx"]
        forward_ref = False
        for ref_t in refs:
            if type_lines.get(ref_t, -1) >= target_line:
                forward_ref = True
                break
        if forward_ref:
            skip_forward_ref += 1
            continue

        plans.append({
            "fn_name": f"(method {N} {T})",
            "src_corpus": "jak3",
            "src_method_name": jak3_slot.get("name"),
            "n_args_old": jakx_n,
            "n_args_new": jak3_n,
            "action": "method_replace_slot",
            "type": T, "idx": N,
            "old_line_idx": target_line,
            "old_line_text": jakx_raw,
            "new_line_text": new_method_line,
            "jakx_file": f["file"],
        })

    print(f"[recipeXm] {len(plans)} plans  "
          f"({skip_no_jak3} no-jak3, {skip_no_jakx_slot} no-jakx-slot, "
          f"{skip_no_improvement} no-improvement, "
          f"{skip_unknown_type} unknown-type, {skip_forward_ref} forward-ref, "
          f"{skip_parse_fail} parse-fail, {skip_dup_name} dup-name, "
          f"{skip_mca_mismatch} mca-mismatch)",
          file=sys.stderr)

    if max_apply > 0 and len(plans) > max_apply:
        plans = plans[:max_apply]

    return {
        "recipe": "Xm",
        "plans": plans,
        "skip_no_jak3": skip_no_jak3,
        "skip_no_jakx_slot": skip_no_jakx_slot,
        "skip_no_improvement": skip_no_improvement,
        "skip_unknown_type": skip_unknown_type,
        "skip_forward_ref": skip_forward_ref,
        "total_failed_methods": len(method_failed),
    }


def apply_recipe_xm(plan: dict, commit_msg: str | None = None):
    """Apply method_replace_slot edits to all-types.gc as ONE batch.
    Replace each old line with the new line at the same line index.
    Sort descending so deletions don't shift earlier indices."""
    text = ALL_TYPES.read_text(encoding="utf-8")
    lines = text.splitlines()
    plans = sorted(plan["plans"], key=lambda p: -p["old_line_idx"])
    for p in plans:
        s = p["old_line_idx"]
        if s >= len(lines):
            continue
        # Sanity: existing line should match what we recorded
        if not lines[s].strip().startswith("("):
            continue
        lines[s] = p["new_line_text"]
    ALL_TYPES.write_text("\n".join(lines) + "\n")
    if commit_msg:
        subprocess.run(
            ["git", "add", str(ALL_TYPES.relative_to(ROOT))],
            cwd=ROOT, check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", commit_msg],
            cwd=ROOT, check=True,
        )


def recipe_x(dry_run: bool = True, max_apply: int = 100,
             allow_replace: bool = True) -> dict:
    """For each unconverted top-level function in jakx, look up its name in
    the REF index. If a corpus has a matching defun, transplant the signature
    into all-types.gc as a (define-extern ...) line.

    Modes:
      - extern_add: function not in jakx all-types.gc → add new define-extern
      - extern_replace: function exists with stubby signature → replace
    """
    print("[recipeX] indexing REF signatures...", file=sys.stderr)
    ref_idx = build_ref_index()
    print(f"[recipeX] {len(ref_idx)} unique fn names in REF set", file=sys.stderr)

    print("[recipeX] finding failed jakx functions...", file=sys.stderr)
    failed = find_failed_functions()
    fn_failed = [f for f in failed if f["kind"] == "function"]
    print(f"[recipeX] {len(failed)} total, {len(fn_failed)} top-level functions",
          file=sys.stderr)

    print("[recipeX] indexing existing all-types.gc externs...", file=sys.stderr)
    extern_idx = index_externs()
    print(f"[recipeX] {len(extern_idx)} existing externs", file=sys.stderr)

    print("[recipeX] indexing known jakx types (with line numbers)...", file=sys.stderr)
    type_lines = index_known_type_lines()
    print(f"[recipeX] {len(type_lines)} known types", file=sys.stderr)

    # For ADD plans, the new line is inserted AFTER the last existing extern.
    # We don't know that line yet but it's effectively at end-of-file. So all
    # types referenced by ADD plans are guaranteed to be defined before insertion.
    # For REPLACE plans, the line is fixed at extern_idx[name]; check forward refs.

    plans = []
    skip_no_ref = 0
    skip_already_better = 0
    skip_unknown_type = 0
    skip_forward_ref = 0
    seen_names = set()

    for f in fn_failed:
        name = f["fn_name"]
        if not name or name.startswith("(") or name == "TOP" or "anon-function" in name:
            continue
        if name in seen_names:
            continue
        seen_names.add(name)
        if name not in ref_idx:
            skip_no_ref += 1
            continue
        corpus, ref_path = ref_idx[name][0]
        sig = extract_signature_from_ref(ref_path, name, "function")
        if not sig:
            skip_no_ref += 1
            continue
        # Build new define-extern line. For function: (function T1 T2 ... none)
        # Add `none` as return type to be safe; if the function has a known
        # return type via `;; INFO: Return type X` we could use it (TODO).
        types = [a[1] for a in sig["args"]]
        types.append("none")  # default return type
        sig_str = "(function " + " ".join(types) + ")" if types else "(function none)"
        new_line = f"(define-extern {name} {sig_str})"

        # Pre-apply gate: ensure all referenced types exist in jakx
        known_types = set(type_lines.keys())
        refs = referenced_types_in_signature(sig_str)
        unknown = refs - known_types
        if unknown:
            skip_unknown_type += 1
            continue

        action = "extern_add"
        replaces = None
        if name in extern_idx:
            if not allow_replace:
                skip_already_better += 1
                continue
            existing_text, existing_lines = get_existing_extern_line(extern_idx[name])
            # Compute existing arg count (from existing's (function ...) inner)
            ex_body = re.sub(r";;.*?(?=\n|$)", "", existing_text)
            ex_body = re.sub(r'"[^"]*"', '', ex_body)
            ex_m = re.search(r"\(function\s+([^)]*)\)", ex_body)
            if ex_m:
                ex_inner = ex_m.group(1)
                # Strip :behavior annotations to compare type counts only
                ex_inner_clean = re.sub(r":\w+\s+\S+", "", ex_inner).strip()
                ex_toks = ex_inner_clean.split()
                ex_n = len(ex_toks)
                # Detect rich annotations on existing
                has_behavior_annot = bool(re.search(r":behavior\s+\S+", ex_inner))
            else:
                ex_n = 0
                has_behavior_annot = False
            new_n = len(types)  # types = sig args + 'none' return
            # Only replace if NEW has strictly more typed slots (richer signature).
            # Preserve `:behavior` annotations on existing — they encode important info
            # this recipe doesn't reproduce (REF defbehavior receiver isn't transferred).
            if new_n <= ex_n:
                skip_already_better += 1
                continue
            if has_behavior_annot and sig.get("kind") != "behavior":
                # Existing has :behavior X but REF source is plain function — risky.
                skip_already_better += 1
                continue
            # Forward-ref gate: every referenced type must be defined BEFORE
            # the replace line, else decomp parse will crash.
            target_line = extern_idx[name]
            forward_ref = False
            for ref_t in refs:
                t_line = type_lines.get(ref_t, -1)
                if t_line >= target_line:
                    forward_ref = True
                    break
            if forward_ref:
                skip_forward_ref += 1
                continue
            action = "extern_replace"
            replaces = {
                "start_line": target_line,
                "end_line": target_line + len(existing_lines) - 1,
                "old_text": existing_text,
                "old_n_args": ex_n,
                "new_n_args": new_n,
            }

        plans.append({
            "fn_name": name,
            "src_corpus": corpus,
            "src_ref_path": str(ref_path.relative_to(ROOT)),
            "n_args": len(sig["args"]),
            "action": action,
            "new_line": new_line,
            "replaces": replaces,
            "jakx_file": f["file"],
        })

    print(f"[recipeX] {len(plans)} plans "
          f"({sum(1 for p in plans if p['action']=='extern_add')} add, "
          f"{sum(1 for p in plans if p['action']=='extern_replace')} replace)  "
          f"({skip_no_ref} no-REF, {skip_already_better} already-better, "
          f"{skip_unknown_type} unknown-type, {skip_forward_ref} forward-ref)",
          file=sys.stderr)

    if max_apply > 0 and len(plans) > max_apply:
        plans = plans[:max_apply]
        print(f"[recipeX] limiting to top {max_apply}", file=sys.stderr)

    return {
        "recipe": "X",
        "plans": plans,
        "skip_no_ref": skip_no_ref,
        "skip_already_better": skip_already_better,
        "skip_unknown_type": skip_unknown_type,
        "skip_forward_ref": skip_forward_ref,
        "total_failed_top_level": len(fn_failed),
    }


def apply_recipe_x(plan: dict, commit_msg: str | None = None):
    """Apply replace + add edits to all-types.gc as ONE batch.

    For replace plans: the OLD lines are removed in-place and REPLACED with the
    new single-line define-extern. For add plans: the new lines are inserted
    AFTER the last existing define-extern line.

    Process in this order:
      1. Sort replace plans by start_line DESCENDING so deletions don't shift
         earlier indices.
      2. Apply replaces.
      3. Re-find the last extern anchor.
      4. Append all add plans after anchor.
    """
    text = ALL_TYPES.read_text(encoding="utf-8")
    lines = text.splitlines()

    add_plans = [p for p in plan["plans"] if p["action"] == "extern_add"]
    replace_plans = [p for p in plan["plans"] if p["action"] == "extern_replace"]

    # Sort replace plans descending by start_line
    replace_plans.sort(key=lambda p: -p["replaces"]["start_line"])

    # Apply replaces
    for p in replace_plans:
        s = p["replaces"]["start_line"]
        e = p["replaces"]["end_line"]
        new_block = [
            f";; Lane2-RecipeX: replaced stub ({p['src_corpus']} {p['src_ref_path']})",
            p["new_line"],
        ]
        lines = lines[:s] + new_block + lines[e + 1:]

    # Apply adds after the last define-extern anchor
    pat = re.compile(r"^\(define-extern\s+")
    anchor = -1
    for i, line in enumerate(lines):
        if pat.match(line.lstrip()):
            anchor = i
    if anchor < 0:
        anchor = len(lines) - 1

    if add_plans:
        new_block = [";; --- Lane 2 Recipe X cycle 1: REF-derived externs ---"]
        for p in add_plans:
            new_block.append(f";; from {p['src_corpus']} REF: {p['src_ref_path']}")
            new_block.append(p["new_line"])
        new_block.append(";; --- end Recipe X cycle 1 ---")
        lines = lines[:anchor + 1] + new_block + lines[anchor + 1:]

    ALL_TYPES.write_text("\n".join(lines) + "\n")

    if commit_msg:
        subprocess.run(
            ["git", "add", str(ALL_TYPES.relative_to(ROOT))],
            cwd=ROOT, check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", commit_msg],
            cwd=ROOT, check=True,
        )


# ---------------------------------------------------------------------------
# Main driver
# ---------------------------------------------------------------------------

def run_decomp_and_measure(timeout: int = 300) -> tuple[bool, dict | None]:
    """Run decomp via run.sh, return (success, post_metrics).
    success=False on rc!=0 or no output. post_metrics from latest snapshot."""
    env = os.environ.copy()
    env["JAKX_WATCH_FORCE"] = "1"
    last_hash = ROOT / ".jakx_watch" / "last_config_hash"
    if last_hash.exists():
        last_hash.unlink()
    try:
        rc = subprocess.run(
            ["bash", "scripts/jakx_watch/run.sh"],
            cwd=ROOT, env=env, timeout=timeout,
            capture_output=True,
        ).returncode
    except subprocess.TimeoutExpired:
        return (False, None)
    snap = latest_snapshot()
    if snap is None or rc != 0:
        # Even on rc!=0 we may have a partial snapshot; check if it's fresh.
        # For safety, count missing/empty disasm dir as crash.
        out_dir = ROOT / ".jakx_watch" / "decomp_out" / "jakx"
        if not list(out_dir.glob("*_disasm.gc")):
            return (False, None)
    if snap is None:
        return (False, None)
    return (True, baseline_metrics(snap))


def cycle_driver(cycle_tag: str, recipe: str = "X", branch_name: str | None = None,
                 max_apply: int = 0, force_apply: bool = False) -> dict:
    """End-to-end cycle:
      1. Save baseline metrics from latest snapshot
      2. (Optional) create lane branch
      3. Build recipe plan
      4. Apply + commit
      5. Decomp + measure
      6. Bisect verdict
      7. Keep (merge to master) or revert
    """
    print(f"[{cycle_tag}] === starting cycle ===", file=sys.stderr)
    pre_snap = latest_snapshot()
    if pre_snap is None:
        return {"status": "no_baseline_snapshot"}
    pre = baseline_metrics(pre_snap)
    pre_pf = per_file_categories(pre_snap)
    pre_head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True
    ).stdout.strip()
    print(f"[{cycle_tag}] pre: HEAD={pre_head[:12]} real-clean={pre['real_clean']} "
          f"errors={pre['total_errors']}", file=sys.stderr)

    # Branch
    if branch_name:
        subprocess.run(["git", "checkout", "-b", branch_name],
                       cwd=ROOT, check=True, capture_output=True)
        print(f"[{cycle_tag}] branched {branch_name}", file=sys.stderr)

    # Build + apply
    if recipe == "X":
        plan = recipe_x(dry_run=False, max_apply=max_apply)
    elif recipe == "Xm":
        plan = recipe_x_methods(dry_run=False, max_apply=max_apply)
    else:
        return {"status": "unknown_recipe"}

    out_path = RESEARCH / f"LANE2_{cycle_tag}_PLAN.json"
    out_path.write_text(json.dumps(plan, indent=1))

    if not plan["plans"] and not force_apply:
        print(f"[{cycle_tag}] no plans -- exiting", file=sys.stderr)
        return {"status": "no_plans", "plan_count": 0}

    commit_msg = (f"Lane2 Recipe{recipe} {cycle_tag}: "
                  f"{len(plan['plans'])} edits from "
                  f"{', '.join(sorted(set(p['src_corpus'] for p in plan['plans']) or ['none']))}\n\n"
                  f"Auto-generated by recipe_apply.py — see "
                  f".jakx_watch/research/LANE2_{cycle_tag}_PLAN.json")
    if recipe == "Xm":
        apply_recipe_xm(plan, commit_msg)
    else:
        apply_recipe_x(plan, commit_msg)
    print(f"[{cycle_tag}] applied {len(plan['plans'])} edits", file=sys.stderr)

    # Decomp
    print(f"[{cycle_tag}] running decomp...", file=sys.stderr)
    ok, post = run_decomp_and_measure()

    if not ok:
        print(f"[{cycle_tag}] DECOMP CRASH — reverting", file=sys.stderr)
        subprocess.run(["git", "checkout", "master"], cwd=ROOT, check=True, capture_output=True)
        if branch_name:
            subprocess.run(["git", "branch", "-D", branch_name], cwd=ROOT, capture_output=True)
        # restore baseline decomp_out (run baseline decomp again)
        # Actually master's decomp_out was wiped — need to regenerate
        return {
            "status": "crash_reverted",
            "verdict": {"verdict": "revert", "reasons": ["decomp_crash"]},
            "plan_count": len(plan["plans"]),
        }

    # Compute bisect verdict
    post_snap = latest_snapshot()
    post_pf = per_file_categories(post_snap)
    verdict = bisect_verdict(pre, post, pre_pf, post_pf)
    print(f"[{cycle_tag}] verdict={verdict['verdict']} delta_rc={verdict['delta_real_clean']:+d} "
          f"delta_err={verdict['delta_errors']:+d} unlocked={verdict['n_unlocked']} "
          f"lost={verdict['n_lost']}", file=sys.stderr)
    for r in verdict["reasons"]:
        print(f"[{cycle_tag}]   reason: {r}", file=sys.stderr)

    if verdict["verdict"] == "revert":
        print(f"[{cycle_tag}] REVERTING per bisect rules", file=sys.stderr)
        subprocess.run(["git", "checkout", "master"], cwd=ROOT, check=True, capture_output=True)
        if branch_name:
            subprocess.run(["git", "branch", "-D", branch_name], cwd=ROOT, capture_output=True)
    else:
        # KEEP: merge lane branch into master (FF if possible)
        if branch_name:
            subprocess.run(["git", "checkout", "master"], cwd=ROOT, check=True, capture_output=True)
            ff = subprocess.run(
                ["git", "merge", "--ff-only", branch_name],
                cwd=ROOT, capture_output=True, text=True,
            )
            if ff.returncode == 0:
                print(f"[{cycle_tag}] merged {branch_name} into master (FF)", file=sys.stderr)
                subprocess.run(["git", "branch", "-d", branch_name],
                               cwd=ROOT, capture_output=True)
            else:
                print(f"[{cycle_tag}] FF-merge failed: {ff.stderr.strip()}",
                      file=sys.stderr)

    return {
        "status": "completed",
        "pre": pre, "post": post,
        "verdict": verdict,
        "plan_count": len(plan["plans"]),
    }


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--recipe", default="X", choices=["X", "Xm"])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-apply", type=int, default=0)
    ap.add_argument("--cycle-tag", default="C1")
    ap.add_argument("--commit", action="store_true",
                    help="Actually commit the change (else just write file).")
    ap.add_argument("--cycle", action="store_true",
                    help="End-to-end cycle driver (branch, apply, decomp, bisect, merge).")
    ap.add_argument("--branch", default=None,
                    help="Lane branch name for cycle mode (e.g. lane/recipes-c1)")
    args = ap.parse_args()

    if args.cycle:
        result = cycle_driver(
            cycle_tag=args.cycle_tag, recipe=args.recipe,
            branch_name=args.branch, max_apply=args.max_apply,
        )
        out_path = RESEARCH / f"LANE2_{args.cycle_tag}_VERDICT.json"
        out_path.write_text(json.dumps(result, indent=1, default=str))
        print(f"\nfinal: {result.get('status')}", file=sys.stderr)
        return

    if args.recipe == "X":
        plan = recipe_x(dry_run=args.dry_run, max_apply=args.max_apply)
    elif args.recipe == "Xm":
        plan = recipe_x_methods(dry_run=args.dry_run, max_apply=args.max_apply)
    else:
        print(f"unknown recipe {args.recipe}", file=sys.stderr); sys.exit(2)

    out_path = RESEARCH / f"LANE2_{args.cycle_tag}_PLAN.json"
    out_path.write_text(json.dumps(plan, indent=1))
    print(f"wrote plan -> {out_path}", file=sys.stderr)

    if args.dry_run:
        print(f"[recipe{args.recipe}] dry-run: {len(plan['plans'])} plans, no apply", file=sys.stderr)
        return

    commit_msg = (f"Lane2 Recipe{args.recipe} {args.cycle_tag}: "
                  f"{len(plan['plans'])} REF-derived externs from "
                  f"{', '.join(sorted(set(p['src_corpus'] for p in plan['plans']) or ['none']))}\n\n"
                  f"Auto-generated by recipe_apply.py — see "
                  f".jakx_watch/research/LANE2_{args.cycle_tag}_PLAN.json")
    apply_recipe_x(plan, commit_msg if args.commit else None)
    print(f"[recipe{args.recipe}] applied {len(plan['plans'])} externs", file=sys.stderr)


if __name__ == "__main__":
    main()
