#!/usr/bin/env python3
"""Multi-game (jak1+jak2+jak3) -> jakx function bytecode fingerprint matcher.

Generalization of the jak3-only spike (`jak3_fingerprint_match.py`) that
widens the reference corpus to all three earlier ports. Jak1 and jak2 are
years-old polished ports — substantially more curated than jak3 (still in
beta) — so signatures harvested from them are higher-quality reference data
for transferring known-correct GOAL types into the in-progress jakx port.

Approach:
  1. Parse all `decompiler_out/<corpus>/*_ir2.asm` files for each requested
     source corpus (default: jak1, jak2, jak3) AND `decompiler_out/jakx/*`.
  2. Build per-corpus fingerprint dicts: fp -> [(file, fn_name, n_instr)].
  3. For each jakx function, look up its fingerprint across all corpora.
     If any corpus has exactly one twin, that's a high-confidence match for
     that corpus.
  4. When multiple corpora match, prefer signatures from the more-polished
     corpus, in priority order: jak2 > jak1 > jak3. (jak2 had the longest
     polish lifecycle, jak1 is similarly mature, jak3 just hit beta.)
  5. Harvest config knowledge (all-types.gc + ntsc_v1/{type_casts,hacks,
     stack_structures}.jsonc) from the chosen source corpus.
  6. Diff against jakx's current config; emit candidate patches.

Outputs:
  - .jakx_watch/multigame_fn_fingerprint.json (raw match data, source_corpus
    annotated per match)
  - .jakx_watch/research/MULTIGAME_FINGERPRINT_MATCHES.md (human-readable,
    breakdown by source corpus)

The original `jak3_fingerprint_match.py` is preserved and remains usable as
a verifier baseline.

Self-contained Python 3 stdlib only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DECOMP_OUT = ROOT / "decompiler_out"
CONFIG_DIR = ROOT / "decompiler" / "config"
JAKX_IR2 = DECOMP_OUT / "jakx"
JAKX_CFG = CONFIG_DIR / "jakx"
OUT_DIR = ROOT / ".jakx_watch"
OUT_RESEARCH = OUT_DIR / "research"
OUT_JSON = OUT_DIR / "multigame_fn_fingerprint.json"
OUT_MD = OUT_RESEARCH / "MULTIGAME_FINGERPRINT_MATCHES.md"

# Priority: when multiple corpora have the same fingerprint, prefer this one.
# jak2 > jak1 > jak3 (jak2/jak1 are mature polished ports; jak3 is beta).
DEFAULT_PRIORITY = ["jak2", "jak1", "jak3"]

# Branch opcodes (used for the secondary "branch-skeleton" hash).
BRANCH_OPCODES = frozenset({
    "b", "beq", "bne", "bgez", "bgtz", "blez", "bltz", "bc1f", "bc1t",
    "beql", "bnel", "bgezl", "bgtzl", "blezl", "bltzl", "bc1fl", "bc1tl",
    "bgezal", "bltzal", "j", "jal", "jr", "jalr",
})

RE_FN_HEADER = re.compile(r"^;\s*\.function\s+(.+?)\s*$")
RE_FN_END = re.compile(r"^;;\s*\.endfunction")
RE_BLOCK_HDR = re.compile(r"^B\d+:\s*$")
RE_INSTR = re.compile(r"^\s+([a-z][a-z0-9_.]*)\b")

# Real-clean classifier: a source disasm.gc file must have at least one
# defun/defmethod and zero ERROR / FAILED_STUB markers to be considered
# authoritative reference data. Same logic as scripts/jakx_watch/measure.py.
RE_HAS_DEFUN = re.compile(r"^\(def(un|method)[\s*]", re.MULTILINE)

MIN_INSTR = 4  # ignore tiny stubs (mostly noise: addiu/jr ra/sll)


def is_real_clean_disasm(disasm_path: Path) -> bool:
    """A source file is real-clean (authoritative) iff it has at least one
    defun/defmethod and contains no ERROR / FAILED_STUB sentinels.

    Applied to source corpora (jak1/jak2/jak3) only — jakx is always parsed
    in full because the goal is to FIX broken jakx files."""
    if not disasm_path.exists():
        return False
    try:
        text = disasm_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return False
    if "\n;; ERROR:" in text or text.startswith(";; ERROR:"):
        return False
    if ("\n;; FAILED_STUB_NEVER_EMITTED_SENTINEL:" in text
            or text.startswith(";; FAILED_STUB_NEVER_EMITTED_SENTINEL:")):
        return False
    if not RE_HAS_DEFUN.search(text):
        return False
    return True


# ---------------------------------------------------------------------------
# IR2 parser
# ---------------------------------------------------------------------------


def parse_function_name(raw: str) -> str:
    return raw.strip()


def parse_ir2_file(path: Path) -> list[dict]:
    funcs: list[dict] = []
    cur_name: str | None = None
    cur_opcodes: list[str] = []
    cur_branches: list[str] = []
    in_fn = False
    in_block = False

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        print(f"[warn] failed to read {path}: {e}", file=sys.stderr)
        return funcs

    for line in text.splitlines():
        if not in_fn:
            m = RE_FN_HEADER.match(line)
            if m:
                cur_name = parse_function_name(m.group(1))
                cur_opcodes = []
                cur_branches = []
                in_fn = True
                in_block = False
            continue

        if RE_FN_END.match(line):
            if cur_name is not None and cur_opcodes:
                joined = "\n".join(cur_opcodes)
                fp = hashlib.sha256(joined.encode()).hexdigest()
                bjoined = "\n".join(cur_branches)
                bfp = hashlib.sha256(bjoined.encode()).hexdigest() if bjoined else ""
                funcs.append({
                    "name": cur_name,
                    "fp": fp,
                    "branch_fp": bfp,
                    "n_instr": len(cur_opcodes),
                    "n_branches": len(cur_branches),
                })
            cur_name = None
            cur_opcodes = []
            cur_branches = []
            in_fn = False
            in_block = False
            continue

        if RE_BLOCK_HDR.match(line):
            in_block = True
            continue

        if not in_block:
            m = RE_INSTR.match(line)
            if m:
                op = m.group(1).lower()
                cur_opcodes.append(op)
                if op in BRANCH_OPCODES:
                    cur_branches.append(op)
            continue

        m = RE_INSTR.match(line)
        if m:
            op = m.group(1).lower()
            cur_opcodes.append(op)
            if op in BRANCH_OPCODES:
                cur_branches.append(op)

    return funcs


def parse_dir(label: str, ir2_dir: Path,
              real_clean_only: bool = False) -> tuple[dict[str, list[dict]], dict]:
    """Parse all *_ir2.asm files in ir2_dir.

    If real_clean_only=True, also probe each file's sibling _disasm.gc
    and SKIP files that are not real-clean (have ERROR / FAILED_STUB
    markers, or have no functions). This is used for source corpora where
    we want only authoritative reference data.

    Returns (funcs_by_file, stats) where stats has counts of files seen,
    real-clean kept, and dirty skipped.
    """
    all_files = sorted(ir2_dir.glob("*_ir2.asm"))
    stats = {
        "total_files": len(all_files),
        "real_clean_kept": 0,
        "dirty_skipped": 0,
    }
    if real_clean_only:
        files = []
        for f in all_files:
            disasm = f.with_name(f.name[: -len("_ir2.asm")] + "_disasm.gc")
            if is_real_clean_disasm(disasm):
                files.append(f)
                stats["real_clean_kept"] += 1
            else:
                stats["dirty_skipped"] += 1
        print(f"[{label}] real-clean filter: {len(files)}/{len(all_files)} "
              f"files kept ({stats['dirty_skipped']} dirty skipped)",
              file=sys.stderr)
    else:
        files = all_files
        stats["real_clean_kept"] = len(all_files)
        print(f"[{label}] parsing {len(files)} ir2.asm files from {ir2_dir} ...",
              file=sys.stderr)

    out: dict[str, list[dict]] = {}
    if not files:
        return out, stats
    t0 = time.time()
    with ProcessPoolExecutor() as ex:
        futs = {ex.submit(parse_ir2_file, f): f for f in files}
        for fut in as_completed(futs):
            f = futs[fut]
            basename = f.name[: -len("_ir2.asm")]
            out[basename] = fut.result()
    print(f"[{label}] parsed {sum(len(v) for v in out.values())} functions in "
          f"{time.time()-t0:.1f}s", file=sys.stderr)
    return out, stats


# ---------------------------------------------------------------------------
# Config harvesting (jsonc + all-types)
# ---------------------------------------------------------------------------


def strip_jsonc(text: str) -> str:
    out: list[str] = []
    i = 0
    n = len(text)
    in_str = False
    str_quote = ""
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == str_quote:
                in_str = False
            i += 1
            continue
        if c == '"' or c == "'":
            in_str = True
            str_quote = c
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


def load_jsonc(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    try:
        return json.loads(strip_jsonc(path.read_text(encoding="utf-8")))
    except Exception as e:
        print(f"[warn] failed to parse {path}: {e}", file=sys.stderr)
        return None


# --- all-types.gc indexing -------------------------------------------------

RE_DEFINE_EXTERN = re.compile(r"^\(define-extern\s+(\S+)\s+(.+)\)\s*$")
RE_DEFTYPE_HEADER = re.compile(r"^\(deftype\s+(\S+)\s+\((\S+)\)")
RE_METHOD_LINE = re.compile(
    r"^\s*\((\S+)\s+(?:\"[^\"]*\"\s+)?(.+?)\s+(\S+?)\)\s*(?:;;\s*(\d+))?\s*$"
)
# v7: multi-line method declarations span paren-balanced blocks (often with a
# multi-line docstring before args). RE_METHOD_LINE_FLAT applies to the joined
# single-line form (whitespace collapsed). DOTALL not needed since we collapse.
RE_METHOD_LINE_FLAT = re.compile(
    r"^\s*\((\S+)\s+(?:\"[^\"]*\"\s+)?(.+?)\s+(\S+?)\)\s*(?:;;\s*(\d+))?\s*$"
)


def _collapse_method_span(span: str) -> str:
    """Flatten a multi-line method declaration into a single line.

    Removes interior comments (;; ...) on each constituent line EXCEPT the
    trailing slot-index comment (;; N at end of declaration). Handles strings
    by leaving them intact (we never strip inside them — a paren in a string
    will still bias paren-counting upstream, but jakx all-types.gc has no such
    cases).
    """
    out_lines = []
    for ln in span.splitlines():
        # Drop inline comments BUT preserve the final ;; N slot index
        # (only on the last line of the span; we'll deal with that out-of-band).
        if ";;" in ln and not re.search(r";;\s*\d+\s*$", ln):
            ln = ln[: ln.index(";;")].rstrip()
        out_lines.append(ln.strip())
    return " ".join(x for x in out_lines if x)


def index_all_types(path: Path) -> dict:
    out = {
        "externs": {},
        "methods": {},
        "methods_by_name": defaultdict(list),
        "state_methods": {},
        "states": {},
        "deftypes": {},
    }
    if not path.exists():
        return out
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    cur_type: str | None = None
    cur_parent: str | None = None
    paren_depth = 0
    in_methods = False
    in_state_methods = False
    in_states = False
    cur_block: list[str] = []

    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        m = RE_DEFINE_EXTERN.match(line)
        if m and cur_type is None:
            name, form = m.group(1), m.group(2)
            out["externs"][name] = f"(define-extern {name} {form})"
            i += 1
            continue

        m = RE_DEFTYPE_HEADER.match(line)
        if m:
            cur_type = m.group(1)
            cur_parent = m.group(2)
            paren_depth = line.count("(") - line.count(")")
            in_methods = in_state_methods = in_states = False
            cur_block = [line]
            i += 1
            continue

        if cur_type is None:
            i += 1
            continue

        cur_block.append(line)
        paren_depth += line.count("(") - line.count(")")

        stripped = line.strip()
        if "(:methods" in stripped:
            in_methods = True
            in_state_methods = False
            in_states = False
            i += 1
            continue
        if "(:state-methods" in stripped:
            in_state_methods = True
            in_methods = False
            in_states = False
            i += 1
            continue
        if "(:states" in stripped:
            in_states = True
            in_methods = False
            in_state_methods = False
            i += 1
            continue

        if stripped == ")":
            # End of any sub-block.
            in_methods = in_state_methods = in_states = False
            if paren_depth <= 0:
                # Whole deftype closed.
                out["deftypes"][cur_type] = "\n".join(cur_block)
                cur_type = None
                cur_parent = None
                cur_block = []
            i += 1
            continue

        if in_methods and stripped.startswith("("):
            # v7: accumulate paren-balanced span in case the method declaration
            # spans multiple lines (multi-line docstring is the common cause).
            span_lines = [line]
            d = line.count("(") - line.count(")")
            j = i
            # Bound the span so we never escape the deftype.
            while d > 0 and j + 1 < n:
                j += 1
                ln = lines[j]
                d += ln.count("(") - ln.count(")")
                span_lines.append(ln)
                cur_block.append(ln)
                paren_depth += ln.count("(") - ln.count(")")
                if d <= 0:
                    break
            joined = _collapse_method_span("\n".join(span_lines))
            mm = RE_METHOD_LINE_FLAT.match(joined)
            if mm:
                mname = mm.group(1)
                sig_args = mm.group(2)
                ret = mm.group(3)
                idx = int(mm.group(4)) if mm.group(4) else None
                sig = f"({mname} {sig_args} {ret})"
                method_key = (
                    f"(method {idx} {cur_type})" if idx is not None
                    else f"(method ? {cur_type})"
                )
                # Keep the FIRST line as `raw` (apply step uses this as anchor;
                # multi-line spans can't be replaced by single-line raw match).
                out["methods"][(cur_type, mname)] = {
                    "sig": sig, "idx": idx, "parent": cur_parent,
                    "method_key": method_key, "raw": span_lines[0],
                    "raw_span": "\n".join(span_lines),
                    "span_line_count": len(span_lines),
                }
                out["methods_by_name"][mname].append((cur_type, sig, idx))
            i = j + 1
            continue
        elif in_state_methods and stripped and not stripped.startswith(")"):
            tok = stripped.split(";")[0].strip()
            if tok and tok != ")":
                idxm = re.search(r";;\s*(\d+)", stripped)
                idx = int(idxm.group(1)) if idxm else None
                out["state_methods"][(cur_type, tok)] = idx
        elif in_states and stripped and not stripped.startswith(")"):
            tok = stripped.split(";")[0].strip()
            if tok and tok != ")":
                idxm = re.search(r";;\s*(\d+)", stripped)
                idx = int(idxm.group(1)) if idxm else None
                out["states"][(cur_type, tok)] = idx

        if paren_depth <= 0:
            out["deftypes"][cur_type] = "\n".join(cur_block)
            cur_type = None
            cur_parent = None
            in_methods = in_state_methods = in_states = False
            cur_block = []
        i += 1

    return out


# --- function name parsing ------------------------------------------------

RE_METHOD_FN_NAME = re.compile(r"^\(method\s+(\d+)\s+(\S+)\)$")
RE_STATE_FN_NAME = re.compile(r"^\((\S+)\s+(\S+)\s+(\S+)\)$")


def lookup_signature(fn_name: str, types_idx: dict) -> dict | None:
    m = RE_METHOD_FN_NAME.match(fn_name)
    if m:
        idx = int(m.group(1))
        type_name = m.group(2)
        for (tn, mname), info in types_idx["methods"].items():
            if tn == type_name and info["idx"] == idx:
                return {
                    "kind": "method",
                    "sig": info["sig"],
                    "method_key": info["method_key"],
                    "method_name": mname,
                    "type": type_name,
                    "idx": idx,
                }
        return {
            "kind": "method-missing",
            "sig": None,
            "method_key": fn_name,
            "type": type_name,
            "idx": idx,
        }

    m = RE_STATE_FN_NAME.match(fn_name)
    if m:
        handler, state_name, type_name = m.group(1), m.group(2), m.group(3)
        return {
            "kind": "state-handler",
            "sig": None,
            "state_name": state_name,
            "type": type_name,
            "handler": handler,
        }

    if fn_name in types_idx["externs"]:
        return {
            "kind": "extern",
            "sig": types_idx["externs"][fn_name],
            "fn_name": fn_name,
        }
    return {"kind": "unknown", "sig": None, "fn_name": fn_name}


# ---------------------------------------------------------------------------
# Per-corpus loader
# ---------------------------------------------------------------------------


def load_corpus(corpus: str) -> dict:
    """Load a source-corpus bundle: ir2 funcs + all-types + jsonc.

    Returns:
      {
        'name': str,
        'available': bool,                # False if decompiler_out/<corpus>/ missing
        'funcs_by_file': {file: [fn_dicts]},
        'fp_db': {fp: [(file, fn, n_instr)]},
        'types': index_all_types(),
        'type_casts': {} | dict,
        'hacks': {} | dict,
        'stack_structs': {} | dict,
      }
    """
    ir2_dir = DECOMP_OUT / corpus
    cfg_dir = CONFIG_DIR / corpus
    bundle = {"name": corpus, "available": False}

    if not ir2_dir.exists() or not list(ir2_dir.glob("*_ir2.asm")):
        print(f"[{corpus}] decompiler_out/{corpus}/*_ir2.asm not found — "
              f"skipping corpus", file=sys.stderr)
        bundle.update({
            "funcs_by_file": {}, "fp_db": defaultdict(list),
            "types": index_all_types(Path("/dev/null")),  # empty
            "type_casts": {}, "hacks": {}, "stack_structs": {},
        })
        return bundle

    bundle["available"] = True
    funcs_by_file, parse_stats = parse_dir(corpus, ir2_dir, real_clean_only=True)
    bundle["funcs_by_file"] = funcs_by_file
    bundle["parse_stats"] = parse_stats

    fp_db: dict[str, list] = defaultdict(list)
    total = 0
    for fname, fns in bundle["funcs_by_file"].items():
        for fn in fns:
            total += 1
            if fn["n_instr"] < MIN_INSTR:
                continue
            fp_db[fn["fp"]].append((fname, fn["name"], fn["n_instr"]))
    bundle["fp_db"] = fp_db
    bundle["total_funcs"] = total
    bundle["unique_fps"] = len(fp_db)
    print(f"[{corpus}] real-clean db: {len(fp_db)} unique fingerprints from "
          f"{total} functions across {parse_stats['real_clean_kept']} "
          f"real-clean files (skipped {parse_stats['dirty_skipped']} dirty)",
          file=sys.stderr)

    # Config — try ntsc_v1 first, fall back to pal_v1 if absent.
    print(f"[{corpus}] loading all-types + jsonc ...", file=sys.stderr)
    bundle["types"] = index_all_types(cfg_dir / "all-types.gc")

    version_dirs = ["ntsc_v1", "ntsc_v2", "pal_v1", "pal"]
    chosen_version_dir: Path | None = None
    for vd in version_dirs:
        p = cfg_dir / vd
        if p.exists() and (p / "type_casts.jsonc").exists():
            chosen_version_dir = p
            break
    if chosen_version_dir is None:
        # Just take the first existing subdir
        for vd in version_dirs:
            p = cfg_dir / vd
            if p.exists():
                chosen_version_dir = p
                break
    bundle["version_dir"] = chosen_version_dir.name if chosen_version_dir else None

    bundle["type_casts"] = (load_jsonc(chosen_version_dir / "type_casts.jsonc") if chosen_version_dir else None) or {}
    bundle["hacks"] = (load_jsonc(chosen_version_dir / "hacks.jsonc") if chosen_version_dir else None) or {}
    bundle["stack_structs"] = (load_jsonc(chosen_version_dir / "stack_structures.jsonc") if chosen_version_dir else None) or {}

    return bundle


# ---------------------------------------------------------------------------
# Harvest + diff
# ---------------------------------------------------------------------------


def harvest_for_match(fn_name: str, corpus_bundle: dict) -> dict:
    info = lookup_signature(fn_name, corpus_bundle["types"])
    out: dict = {"signature": info}

    if fn_name in corpus_bundle["type_casts"]:
        out["type_casts"] = corpus_bundle["type_casts"][fn_name]

    if fn_name in corpus_bundle["stack_structs"]:
        out["stack_structure"] = corpus_bundle["stack_structs"][fn_name]

    hacks = corpus_bundle["hacks"]
    if hacks:
        hacks_for_fn: dict = {}
        for key in (
            "asm_functions_by_name",
            "no_type_analysis_functions_by_name",
            "mips2c_functions_by_name",
            "mips2c_jump_table_functions",
            "cond_with_else_max_lengths",
        ):
            v = hacks.get(key)
            if v is None:
                continue
            if isinstance(v, list):
                for item in v:
                    if isinstance(item, str) and item == fn_name:
                        hacks_for_fn.setdefault(key, []).append(item)
                    elif isinstance(item, list) and item and item[0] == fn_name:
                        hacks_for_fn.setdefault(key, []).append(item)
            elif isinstance(v, dict) and fn_name in v:
                hacks_for_fn[key] = {fn_name: v[fn_name]}
        if hacks_for_fn:
            out["hacks"] = hacks_for_fn

    return out


def diff_against_jakx(
    fn_name: str,
    src_payload: dict,
    jakx_types: dict,
    jakx_type_casts: dict,
    jakx_hacks: dict,
    jakx_stack_structs: dict,
) -> dict:
    candidate: dict = {}

    src_sig = src_payload.get("signature") or {}
    jakx_sig = lookup_signature(fn_name, jakx_types)

    j3 = src_sig.get("sig")
    jx = jakx_sig.get("sig")
    if j3 and j3 != jx:
        candidate["signature_diff"] = {
            "source": j3,
            "jakx": jx,
            "source_kind": src_sig.get("kind"),
            "jakx_kind": jakx_sig.get("kind"),
        }

    j3_tc = src_payload.get("type_casts")
    jx_tc = jakx_type_casts.get(fn_name) if jakx_type_casts else None
    if j3_tc is not None and j3_tc != jx_tc:
        candidate["type_casts_diff"] = {"source": j3_tc, "jakx": jx_tc}

    j3_ss = src_payload.get("stack_structure")
    jx_ss = jakx_stack_structs.get(fn_name) if jakx_stack_structs else None
    if j3_ss is not None and j3_ss != jx_ss:
        candidate["stack_structure_diff"] = {"source": j3_ss, "jakx": jx_ss}

    j3_h = src_payload.get("hacks")
    if j3_h:
        h_diff: dict = {}
        for cat, j3_val in j3_h.items():
            jx_cat = jakx_hacks.get(cat) if jakx_hacks else None
            present_in_jakx = False
            if isinstance(jx_cat, list):
                for item in jx_cat:
                    if (isinstance(item, str) and item == fn_name) or (
                        isinstance(item, list) and item and item[0] == fn_name
                    ):
                        present_in_jakx = True
                        break
            elif isinstance(jx_cat, dict):
                present_in_jakx = fn_name in jx_cat
            if not present_in_jakx:
                h_diff[cat] = j3_val
        if h_diff:
            candidate["hacks_diff"] = h_diff

    return candidate


# ---------------------------------------------------------------------------
# Cross-corpus signature disagreement detection
# ---------------------------------------------------------------------------


def find_signature_disagreements(jakx_fn_name: str, payloads_by_corpus: dict) -> dict | None:
    """If two or more corpora have a signature for this function and they
    differ, surface them for human review."""
    sigs = {}
    for corpus, payload in payloads_by_corpus.items():
        sig = (payload.get("signature") or {}).get("sig")
        if sig:
            sigs[corpus] = sig
    if len(set(sigs.values())) <= 1:
        return None
    return sigs


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Multi-game (jak1+jak2+jak3) -> jakx fingerprint matcher."
    )
    parser.add_argument(
        "--source-corpora",
        nargs="+",
        default=["jak1", "jak2", "jak3"],
        help="Source corpora to fingerprint. Default: jak1 jak2 jak3.",
    )
    parser.add_argument(
        "--priority",
        nargs="+",
        default=DEFAULT_PRIORITY,
        help="Tie-break priority order when multiple corpora match. "
             "Default: jak2 jak1 jak3.",
    )
    args = parser.parse_args()

    OUT_DIR.mkdir(exist_ok=True)
    OUT_RESEARCH.mkdir(exist_ok=True)

    requested = list(args.source_corpora)
    priority = [c for c in args.priority if c in requested]

    print(f"[main] source corpora: {requested}", file=sys.stderr)
    print(f"[main] tie-break priority: {priority}", file=sys.stderr)

    # Load all source corpora
    corpora = {}
    for c in requested:
        corpora[c] = load_corpus(c)

    available_corpora = [c for c in requested if corpora[c]["available"]]
    print(f"[main] available corpora: {available_corpora}", file=sys.stderr)

    if not available_corpora:
        print("[fatal] no source corpora available — nothing to match against",
              file=sys.stderr)
        sys.exit(2)

    # Load jakx — IMPORTANT: no real-clean filter here, because jakx is the
    # TARGET being matched. We want jakx functions found regardless of file
    # cleanliness (the whole point of this pipeline is to fix broken jakx).
    jakx_funcs_by_file, jakx_parse_stats = parse_dir(
        "jakx", JAKX_IR2, real_clean_only=False
    )
    jakx_types = index_all_types(JAKX_CFG / "all-types.gc")
    jakx_type_casts = load_jsonc(JAKX_CFG / "ntsc_v1" / "type_casts.jsonc") or {}
    jakx_hacks = load_jsonc(JAKX_CFG / "ntsc_v1" / "hacks.jsonc") or {}
    jakx_stack = load_jsonc(JAKX_CFG / "ntsc_v1" / "stack_structures.jsonc") or {}

    # File-level error counts (heuristic: ;; ERROR lines in the ir2.asm).
    jakx_file_errors: dict[str, int] = {}
    for f in JAKX_IR2.glob("*_ir2.asm"):
        try:
            t = f.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        jakx_file_errors[f.name[: -len("_ir2.asm")]] = t.count(";; ERROR")

    # ---- Match jakx functions against every source corpus
    matches: list[dict] = []           # high-confidence (1 candidate in chosen corpus)
    no_match: list[dict] = []          # no corpus has any twin
    ambiguous: list[dict] = []         # all corpora that have hits have >1
    disagreements: list[dict] = []     # functions where corpora differ on signature

    jakx_total = 0
    counts_by_source = defaultdict(int)

    for fname, fns in jakx_funcs_by_file.items():
        for fn in fns:
            jakx_total += 1
            if fn["n_instr"] < MIN_INSTR:
                continue

            # Look up in every available corpus
            cands_by_corpus: dict[str, list] = {}
            for c in available_corpora:
                cands = corpora[c]["fp_db"].get(fn["fp"], [])
                if cands:
                    cands_by_corpus[c] = cands

            if not cands_by_corpus:
                no_match.append({
                    "jakx_file": fname,
                    "jakx_fn": fn["name"],
                    "n_instr": fn["n_instr"],
                })
                continue

            # Pick chosen corpus by priority among those with exactly 1 hit;
            # if none has exactly 1 hit, fall back to priority among all hits
            # (still ambiguous).
            chosen_corpus = None
            for p in priority:
                if p in cands_by_corpus and len(cands_by_corpus[p]) == 1:
                    chosen_corpus = p
                    break
            if chosen_corpus is None:
                # No single-hit corpus — ambiguous. Note the priority hit, but
                # mark as ambiguous unless the user's tools want to disambig.
                # We still pick the priority corpus so caller has a hint.
                for p in priority:
                    if p in cands_by_corpus:
                        chosen_corpus = p
                        break
                if chosen_corpus is None:
                    chosen_corpus = next(iter(cands_by_corpus))

            entry = {
                "jakx_file": fname,
                "jakx_fn": fn["name"],
                "n_instr": fn["n_instr"],
                "fp": fn["fp"],
                "branch_fp": fn["branch_fp"],
                "source_corpus": chosen_corpus,
                "candidates_by_corpus": {
                    c: [{"file": cf, "fn": cn, "n_instr": ci} for cf, cn, ci in clist]
                    for c, clist in cands_by_corpus.items()
                },
            }

            if len(cands_by_corpus[chosen_corpus]) == 1:
                matches.append(entry)
                counts_by_source[chosen_corpus] += 1
            else:
                ambiguous.append(entry)

    print(f"[jakx] {jakx_total} functions; high-conf={len(matches)}, "
          f"ambiguous={len(ambiguous)}, no-match={len(no_match)}",
          file=sys.stderr)
    for c in available_corpora:
        print(f"  source={c}: {counts_by_source[c]} matches", file=sys.stderr)

    # ---- Harvest + diff on every match
    print("[harvest] collecting source config payloads + diffing vs jakx ...",
          file=sys.stderr)
    auto_apply: list[dict] = []
    no_diff: list[dict] = []
    same_name_matches = 0
    diff_name_matches = 0

    for m in matches:
        chosen = m["source_corpus"]
        src_fn = m["candidates_by_corpus"][chosen][0]["fn"]
        if m["jakx_fn"] == src_fn:
            same_name_matches += 1
        else:
            diff_name_matches += 1

        payload = harvest_for_match(src_fn, corpora[chosen])
        candidate = diff_against_jakx(
            m["jakx_fn"], payload, jakx_types,
            jakx_type_casts, jakx_hacks, jakx_stack,
        )
        m["source_payload"] = payload
        m["candidate_patch"] = candidate
        m["jakx_file_errors"] = jakx_file_errors.get(m["jakx_file"], 0)

        # Cross-corpus signature disagreement check
        if len(m["candidates_by_corpus"]) > 1:
            payloads_all: dict = {}
            for c, clist in m["candidates_by_corpus"].items():
                if len(clist) == 1:
                    payloads_all[c] = harvest_for_match(clist[0]["fn"], corpora[c])
            disagree = find_signature_disagreements(m["jakx_fn"], payloads_all)
            if disagree:
                disagreements.append({
                    "jakx_fn": m["jakx_fn"],
                    "jakx_file": m["jakx_file"],
                    "signatures": disagree,
                })

        if candidate:
            auto_apply.append(m)
        else:
            no_diff.append(m)

    print(f"[harvest] same-name={same_name_matches}, "
          f"diff-name={diff_name_matches}, with-candidate-patch="
          f"{len(auto_apply)}, no-diff={len(no_diff)}, "
          f"signature-disagreements={len(disagreements)}", file=sys.stderr)

    # Rank top auto-apply candidates by file error count.
    auto_apply.sort(key=lambda m: (-m["jakx_file_errors"], -m["n_instr"]))
    top_for_md = auto_apply[:20]

    # Identify "new" matches — those resolved via jak1 or jak2 (would be
    # missing from jak3-only run).
    new_via_non_jak3 = [m for m in auto_apply if m["source_corpus"] != "jak3"]

    matches_in_error_bearing = sum(
        1 for m in matches if m["jakx_file_errors"] > 0
    )

    # ---- JSON output
    json_payload = {
        "summary": {
            "source_corpora_requested": requested,
            "source_corpora_available": available_corpora,
            "tie_break_priority": priority,
            "min_instr_threshold": MIN_INSTR,
            "per_corpus": {
                c: {
                    "total_funcs": corpora[c].get("total_funcs", 0),
                    "unique_fingerprints": corpora[c].get("unique_fps", 0),
                    "version_dir": corpora[c].get("version_dir"),
                    "real_clean_files_kept": corpora[c].get("parse_stats", {}).get("real_clean_kept", 0),
                    "dirty_files_skipped": corpora[c].get("parse_stats", {}).get("dirty_skipped", 0),
                    "total_files": corpora[c].get("parse_stats", {}).get("total_files", 0),
                }
                for c in available_corpora
            },
            "jakx_functions": jakx_total,
            "high_conf_matches": len(matches),
            "ambiguous_matches": len(ambiguous),
            "no_match": len(no_match),
            "matches_with_candidate_patch": len(auto_apply),
            "matches_with_no_diff_needed": len(no_diff),
            "matches_in_error_bearing_files": matches_in_error_bearing,
            "matches_by_source_corpus": dict(counts_by_source),
            "same_name_matches": same_name_matches,
            "diff_name_matches": diff_name_matches,
            "new_matches_via_non_jak3_corpora": len(new_via_non_jak3),
            "cross_corpus_signature_disagreements": len(disagreements),
        },
        "matches": matches,
        "ambiguous": ambiguous,
        "disagreements": disagreements,
        "no_match_count": len(no_match),
    }
    OUT_JSON.write_text(json.dumps(json_payload, indent=2, default=str))
    print(f"[out] wrote {OUT_JSON}", file=sys.stderr)

    # ---- Markdown output
    md = []
    md.append("# Multi-Game Function Fingerprint Matches (jak1+jak2+jak3 -> jakx)\n")
    md.append("Generalization of the jak3-only spike: opcode-sequence fingerprint "
              "matcher across multiple source corpora. Source signatures from "
              "more-polished ports (jak2 > jak1 > jak3) take priority when "
              "multiple corpora match.\n")

    md.append("## Summary\n")
    md.append(f"- source corpora requested: `{requested}`")
    md.append(f"- source corpora available: `{available_corpora}`")
    md.append(f"- tie-break priority: `{priority}`")
    md.append(f"- min instruction threshold: **{MIN_INSTR}**\n")

    md.append("### Per-corpus fingerprint database (real-clean filtered)")
    md.append("Source files filtered to real-clean only (no `;; ERROR:` / "
              "`;; FAILED_STUB_NEVER_EMITTED_SENTINEL:`, must contain "
              "defun/defmethod). Dirty files are skipped — their type "
              "annotations are not authoritative.\n")
    md.append("| corpus | total files | real-clean kept | dirty skipped | functions | unique fingerprints | config version |")
    md.append("|---|---|---|---|---|---|---|")
    for c in available_corpora:
        info = corpora[c]
        ps = info.get("parse_stats", {})
        md.append(f"| {c} | {ps.get('total_files', 0)} | "
                  f"{ps.get('real_clean_kept', 0)} | "
                  f"{ps.get('dirty_skipped', 0)} | "
                  f"{info.get('total_funcs', 0)} | "
                  f"{info.get('unique_fps', 0)} | "
                  f"{info.get('version_dir', '?')} |")
    md.append("")

    md.append("### Match breakdown")
    md.append(f"- jakx functions parsed: **{jakx_total}**")
    md.append(f"- jakx high-confidence matches (1 twin in chosen corpus): "
              f"**{len(matches)}**")
    md.append(f"  - same-name matches: {same_name_matches}")
    md.append(f"  - different-name matches: {diff_name_matches}")
    md.append(f"  - matches in error-bearing jakx files: "
              f"{matches_in_error_bearing}")
    md.append(f"- jakx ambiguous matches (>1 twin in every corpus that hits): "
              f"**{len(ambiguous)}**")
    md.append(f"- jakx no-match: **{len(no_match)}**")
    md.append(f"- matches with candidate patch (config diff): "
              f"**{len(auto_apply)}**")
    md.append(f"- matches with no diff needed (already same): "
              f"**{len(no_diff)}**")
    md.append(f"- new matches resolved via jak1/jak2 (not in jak3): "
              f"**{len(new_via_non_jak3)}**\n")

    md.append("### Matches by source corpus")
    md.append("| source corpus | high-conf matches |")
    md.append("|---|---|")
    for c in available_corpora:
        md.append(f"| {c} | {counts_by_source[c]} |")
    md.append("")

    md.append("## Top 20 Highest-Leverage Matches\n")
    md.append("Ranked by (jakx file error count desc, function size desc). "
              "Fixing these should clear the most decompiler errors.\n")
    for i, m in enumerate(top_for_md, 1):
        chosen = m["source_corpus"]
        src_fn = m["candidates_by_corpus"][chosen][0]
        cand = m["candidate_patch"]
        md.append(f"### {i}. `{m['jakx_fn']}` in `{m['jakx_file']}` "
                  f"(file errors: {m['jakx_file_errors']}, "
                  f"n_instr: {m['n_instr']}, source: {chosen})")
        md.append(f"- {chosen} twin: `{src_fn['fn']}` in `{src_fn['file']}`")
        if "signature_diff" in cand:
            sd = cand["signature_diff"]
            md.append(f"- **signature** {chosen} vs jakx:")
            md.append(f"  - {chosen} ({sd['source_kind']}): `{sd['source']}`")
            md.append(f"  - jakx ({sd['jakx_kind']}): `{sd['jakx']}`")
        if "type_casts_diff" in cand:
            md.append(f"- **type_casts** missing/different on jakx side: "
                      f"`{json.dumps(cand['type_casts_diff']['source'])[:200]}`")
        if "stack_structure_diff" in cand:
            md.append(f"- **stack_structure** missing/different: "
                      f"`{json.dumps(cand['stack_structure_diff']['source'])}`")
        if "hacks_diff" in cand:
            md.append(f"- **hacks** missing on jakx side: "
                      f"`{list(cand['hacks_diff'].keys())}`")
        md.append("")

    md.append("## Top 30 New Matches (via jak1 or jak2 — not in jak3-only run)\n")
    md.append("These are the headline win for the corpus widening: matches "
              "that would not be present if only jak3 were used as source.\n")
    new_via_non_jak3.sort(key=lambda m: (-m["jakx_file_errors"], -m["n_instr"]))
    md.append("| jakx fn | jakx file | n_instr | source | source fn | source file | jakx errors | diff kinds |")
    md.append("|---|---|---|---|---|---|---|---|")
    for m in new_via_non_jak3[:30]:
        chosen = m["source_corpus"]
        src_fn = m["candidates_by_corpus"][chosen][0]
        kinds = ",".join(sorted(m["candidate_patch"].keys()))
        md.append(f"| `{m['jakx_fn']}` | {m['jakx_file']} | {m['n_instr']} | "
                  f"{chosen} | `{src_fn['fn']}` | {src_fn['file']} | "
                  f"{m['jakx_file_errors']} | {kinds} |")
    md.append("")

    md.append("## Cross-Corpus Signature Disagreements\n")
    md.append(f"Functions where jak1/jak2/jak3 give different signatures for the "
              f"same fingerprint — flagged for human review. Total: "
              f"**{len(disagreements)}**. (First 30 listed.)\n")
    md.append("| jakx fn | jakx file | signatures by corpus |")
    md.append("|---|---|---|")
    for d in disagreements[:30]:
        sigs_str = "; ".join(f"{c}: `{s}`" for c, s in d["signatures"].items())
        md.append(f"| `{d['jakx_fn']}` | {d['jakx_file']} | {sigs_str} |")
    md.append("")

    md.append("## Auto-Applicable Cluster (full list, top 200)\n")
    md.append(f"Functions where source corpus has config knowledge that jakx lacks "
              f"(or has differently). Total: **{len(auto_apply)}**.\n")
    md.append("| jakx fn | jakx file | source | source fn | source file | diff kinds | n_instr | jakx errors |")
    md.append("|---|---|---|---|---|---|---|---|")
    for m in auto_apply[:200]:
        chosen = m["source_corpus"]
        src_fn = m["candidates_by_corpus"][chosen][0]
        kinds = ",".join(sorted(m["candidate_patch"].keys()))
        md.append(f"| `{m['jakx_fn']}` | {m['jakx_file']} | {chosen} | "
                  f"`{src_fn['fn']}` | {src_fn['file']} | {kinds} | "
                  f"{m['n_instr']} | {m['jakx_file_errors']} |")
    md.append("")

    md.append("## Ambiguous Matches\n")
    md.append(f"jakx functions whose fingerprint matches >1 source function "
              f"in every corpus that hits — needs human disambiguation. "
              f"Total: **{len(ambiguous)}**. Top 50 by size.\n")
    ambiguous.sort(key=lambda m: -m["n_instr"])
    md.append("| jakx fn | jakx file | n_instr | candidates_by_corpus |")
    md.append("|---|---|---|---|")
    for m in ambiguous[:50]:
        cands_str_parts = []
        for c, clist in m["candidates_by_corpus"].items():
            head = ", ".join(f"`{x['fn']}`@{x['file']}" for x in clist[:3])
            more = "" if len(clist) <= 3 else f" (+{len(clist)-3})"
            cands_str_parts.append(f"{c}: {head}{more}")
        md.append(f"| `{m['jakx_fn']}` | {m['jakx_file']} | {m['n_instr']} | "
                  f"{'; '.join(cands_str_parts)} |")
    md.append("")

    OUT_MD.write_text("\n".join(md))
    print(f"[out] wrote {OUT_MD}", file=sys.stderr)

    # ---- Summary to stdout (captured for task report)
    print("\n===== SUMMARY =====")
    print(f"source corpora requested:                 {requested}")
    print(f"source corpora available:                 {available_corpora}")
    print(f"tie-break priority:                       {priority}")
    print()
    for c in available_corpora:
        info = corpora[c]
        ps = info.get("parse_stats", {})
        print(f"  {c}: {info.get('total_funcs', 0):>6} funcs, "
              f"{info.get('unique_fps', 0):>6} unique fp, "
              f"{ps.get('real_clean_kept', 0):>4}/{ps.get('total_files', 0):>4} "
              f"real-clean files used "
              f"(cfg: {info.get('version_dir', '?')})")
    print()
    print(f"jakx functions parsed:                    {jakx_total}")
    print(f"jakx high-confidence matches:             {len(matches)}")
    print(f"  same-name (sanity):                     {same_name_matches}")
    print(f"  different-name (interesting):           {diff_name_matches}")
    print(f"  in error-bearing jakx files:            {matches_in_error_bearing}")
    print()
    for c in available_corpora:
        print(f"  matches sourced from {c}:               "
              f"{counts_by_source[c]}")
    print()
    print(f"jakx ambiguous matches:                   {len(ambiguous)}")
    print(f"jakx no-match (diverged/specific):        {len(no_match)}")
    print(f"matches w/ candidate patch (config diff): {len(auto_apply)}")
    print(f"matches w/ no diff needed (already same): {len(no_diff)}")
    print(f"new matches via jak1/jak2 (not jak3):     {len(new_via_non_jak3)}")
    print(f"cross-corpus signature disagreements:     {len(disagreements)}")


if __name__ == "__main__":
    main()
