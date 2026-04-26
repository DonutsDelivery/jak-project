#!/usr/bin/env python3
"""op_idx_drift.py — filter cross_game_config_port candidates by op-shape match.

The cross_game_config_port lane keeps reverting (de7d6b282, then ~6:34am
2026-04-26) because it ports type_cast entries by op_idx without checking
that the SAME op_idx in the target game is the SAME shape of instruction.
A cast meant for `lwu` at op 12 in jak3 hits `addiu` at op 12 in jakx if
the function structure has drifted, producing wrong types and regressions.

Per the convergence_metric: jakx's failed_type_prop = 2622 is the largest
unworked error pile by a wide margin (~5× jak3's 1898 / jak2's 469). The
cross-port lane is the right donor pool; the missing piece is shape matching.

API:
  parse_ir2_ops(ir2_path, function_name) -> list[Op] | None
  shape_match(op_a, op_b) -> bool
  drift_check(function_name, op_spec, src_game, dst_game) -> DriftResult

  Op = (op_idx, mnemonic, dest_reg, kind)
  DriftResult.transferable: bool
  DriftResult.reason: str — why not transferable (for blacklist)
"""
from __future__ import annotations

import dataclasses
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def decomp_out_dir(game: str) -> Path:
    primary = ROOT / f".{game}_watch" / "decomp_out" / game
    if primary.exists() and any(primary.glob("*_ir2.asm")):
        return primary
    return ROOT / "decompiler_out" / game


# Op kinds we care about for type_cast purposes — the ones type_casts.jsonc
# actually targets. Loads dominate, then ALU ops, then calls.
LOAD_MNEMONICS = {"lw", "lwu", "lh", "lhu", "lb", "lbu", "ld", "lq", "lqc2"}
STORE_MNEMONICS = {"sw", "sh", "sb", "sd", "sq", "sqc2"}
ALU_MNEMONICS = {"daddiu", "addiu", "addu", "subu", "or", "ori", "and", "andi",
                 "sll", "srl", "sra", "dsll", "dsra", "xor", "xori"}
CALL_MNEMONICS = {"jalr", "jal", "bgezal"}
BRANCH_MNEMONICS = {"beq", "bne", "blez", "bgtz", "bltz", "bgez", "j", "b"}

# Function-start marker in IR2:
#   ;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
#   ; .function NAME
#   ;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
RE_FUNCTION_HEADER = re.compile(r"^;\s+\.function\s+(?P<name>\S+)\s*$")
# Some headers wrap method names: "; .function (method N type-name)"
RE_FUNCTION_HEADER_METHOD = re.compile(r"^;\s+\.function\s+\((method\s+\d+\s+\S+)\)")
# Op line:  "    lwu  t9, 16(v1)            ;; [  N] ..."
RE_OP_LINE = re.compile(
    r"^\s+(?P<mnem>[a-z][a-z0-9.]+)"     # mnemonic
    r"\s+(?P<dest>\S+)"                  # first operand (often dest reg)
    r"(?:\s*,\s*(?P<rest>[^;]*))?"       # rest
    r"\s+;;\s*\[\s*(?P<idx>\d+)\s*\]"    # ;; [  N]
)


@dataclasses.dataclass
class Op:
    idx: int
    mnemonic: str
    dest: str
    rest: str

    @property
    def kind(self) -> str:
        m = self.mnemonic
        if m in LOAD_MNEMONICS:
            return "load"
        if m in STORE_MNEMONICS:
            return "store"
        if m in ALU_MNEMONICS:
            return "alu"
        if m in CALL_MNEMONICS:
            return "call"
        if m in BRANCH_MNEMONICS:
            return "branch"
        return "other"


@dataclasses.dataclass
class DriftResult:
    transferable: bool
    reason: str = ""
    src_op: Op | None = None
    dst_op: Op | None = None


def _func_name_to_search_pattern(name: str) -> str:
    """type_casts.jsonc uses keys like 'inspect-process-heap' or
    '(method 0 cpu-thread)'. Convert to a search pattern that matches the
    IR2 .function header.
    """
    return name.strip()


def parse_ir2_ops(ir2_path: Path, function_name: str) -> list[Op] | None:
    """Return ops in the named function, or None if function not found.

    Function names in type_casts can be either:
      - "(method N type-name)"  — matched against ".function (method N type-name)"
      - "function-name"          — matched against ".function function-name"
      - "(method N type-name)" with anonymous-fn naming — see decompiler emit
    """
    if not ir2_path.exists():
        return None
    text = ir2_path.read_text(errors="replace")
    name_search = _func_name_to_search_pattern(function_name)

    # Find function header line
    in_func = False
    func_lines: list[str] = []
    for line in text.splitlines():
        if in_func:
            # End of function = next header or end of file
            if (RE_FUNCTION_HEADER.match(line) or
                    RE_FUNCTION_HEADER_METHOD.match(line)):
                # Hit next function — done
                break
            func_lines.append(line)
            continue
        # Look for our function header
        # The header format puts the name on a comment line, e.g.
        #   ; .function spatial-hash-init
        #   ; .function (method 0 cpu-thread)
        m = RE_FUNCTION_HEADER.match(line)
        if m:
            if m.group("name") == name_search:
                in_func = True
            continue
        m2 = RE_FUNCTION_HEADER_METHOD.match(line)
        if m2:
            method_name = f"({m2.group(1)})"
            if method_name == name_search:
                in_func = True

    if not in_func and not func_lines:
        return None

    # Parse op lines from func_lines
    ops: list[Op] = []
    for line in func_lines:
        m = RE_OP_LINE.match(line)
        if not m:
            continue
        ops.append(Op(
            idx=int(m.group("idx")),
            mnemonic=m.group("mnem"),
            dest=m.group("dest").rstrip(","),
            rest=(m.group("rest") or "").strip(),
        ))
    return ops


def shape_match(src: Op, dst: Op) -> bool:
    """Two ops have compatible shape for type_cast transfer.

    Compatible if:
      - same instruction kind (load/store/alu/call/branch/other), AND
      - same destination register (so the cast targets the same slot)

    Mnemonic-exact match would be too strict (lwu vs lw differ only in
    sign-extension, but both are loads to the same dest); kind-match is
    the right granularity for type_cast safety.
    """
    if src.kind != dst.kind:
        return False
    if src.dest != dst.dest:
        return False
    return True


def drift_check(
    function_name: str,
    op_spec,  # int OR [start, end]
    src_game: str = "jak3",
    dst_game: str = "jakx",
) -> DriftResult:
    """Check whether a type_cast for (function, op_spec) can transfer
    src_game → dst_game without drift.

    op_spec from type_casts.jsonc can be:
      - single int (one op)
      - [start, end] range (apply at every op from start..end inclusive)

    For a range, we require shape_match at BOTH endpoints. Range casts
    that span drifted middles are still risky but we accept them — the
    common case is a load-and-use pattern that's stable inside the range.
    """
    src_basename = _ir2_path_for_func(function_name, src_game)
    dst_basename = _ir2_path_for_func(function_name, dst_game)

    if not src_basename:
        return DriftResult(False, f"function {function_name!r} not found in any {src_game} IR2")
    if not dst_basename:
        return DriftResult(False, f"function {function_name!r} not found in any {dst_game} IR2")

    src_ir2 = decomp_out_dir(src_game) / src_basename
    dst_ir2 = decomp_out_dir(dst_game) / dst_basename

    src_ops = parse_ir2_ops(src_ir2, function_name)
    dst_ops = parse_ir2_ops(dst_ir2, function_name)

    if src_ops is None:
        return DriftResult(False, f"function {function_name!r} not found in {src_game}")
    if dst_ops is None:
        return DriftResult(False, f"function {function_name!r} not found in {dst_game}")

    # Coarse function-shape check: if op counts differ wildly, skip.
    src_max = max((o.idx for o in src_ops), default=-1)
    dst_max = max((o.idx for o in dst_ops), default=-1)
    if src_max < 0 or dst_max < 0:
        return DriftResult(False, "no parseable ops in either source")

    # Allow ±15% function-length skew before declaring full drift
    if abs(src_max - dst_max) > max(5, src_max * 0.15):
        return DriftResult(
            False,
            f"function length differs significantly: {src_game} max op={src_max}, "
            f"{dst_game} max op={dst_max}"
        )

    # Resolve op_spec into the indices we need to check
    if isinstance(op_spec, list) and len(op_spec) == 2:
        check_indices = [op_spec[0], op_spec[1]]
    elif isinstance(op_spec, int):
        check_indices = [op_spec]
    else:
        return DriftResult(False, f"unrecognized op_spec format: {op_spec!r}")

    src_by_idx = {o.idx: o for o in src_ops}
    dst_by_idx = {o.idx: o for o in dst_ops}

    for idx in check_indices:
        if idx not in src_by_idx:
            return DriftResult(False, f"op {idx} not present in {src_game}")
        if idx not in dst_by_idx:
            return DriftResult(False, f"op {idx} not present in {dst_game}")
        if not shape_match(src_by_idx[idx], dst_by_idx[idx]):
            return DriftResult(
                False,
                f"op {idx} shape mismatch: {src_game}={src_by_idx[idx].kind}/"
                f"{src_by_idx[idx].dest} vs {dst_game}={dst_by_idx[idx].kind}/"
                f"{dst_by_idx[idx].dest}",
                src_op=src_by_idx[idx],
                dst_op=dst_by_idx[idx],
            )

    return DriftResult(True, "ok")


# Heuristic: type_casts.jsonc keys map to IR2 file names. For function-name
# keys ("inspect-process-heap"), the file is the GOAL source file containing
# that function — we can find it by grepping ".function inspect-process-heap"
# across IR2s. For method keys ("(method 0 process)"), the file is the type's
# definition file.
#
# Cheap approximation: cache a function→file index built once per game.
_func_index_cache: dict[str, dict[str, str]] = {}


def _build_func_index(game: str) -> dict[str, str]:
    """Build {function_name: ir2_basename} index for game's decomp_out."""
    out: dict[str, str] = {}
    decomp = decomp_out_dir(game)
    if not decomp.exists():
        return out
    for ir2 in decomp.glob("*_ir2.asm"):
        try:
            text = ir2.read_text(errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            m = RE_FUNCTION_HEADER.match(line)
            if m:
                out[m.group("name")] = ir2.name
                continue
            m2 = RE_FUNCTION_HEADER_METHOD.match(line)
            if m2:
                out[f"({m2.group(1)})"] = ir2.name
    return out


def _ir2_path_for_func(function_name: str, game: str) -> str:
    """Return ir2 basename for function in game, or empty string if missing."""
    cache = _func_index_cache.get(game)
    if cache is None:
        cache = _build_func_index(game)
        _func_index_cache[game] = cache
    return cache.get(function_name, "")


# ---- CLI ----
def _main() -> int:
    import argparse
    import json
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="jak3")
    ap.add_argument("--dst", default="jakx")
    ap.add_argument("--function", required=True,
                    help="function key from type_casts.jsonc, "
                         "e.g. 'inspect-process-heap' or '(method 0 process)'")
    ap.add_argument("--op", required=True,
                    help="op spec: '5' for single, '[5,12]' for range")
    args = ap.parse_args()

    op_spec = json.loads(args.op) if args.op.startswith("[") else int(args.op)
    r = drift_check(args.function, op_spec, args.src, args.dst)
    print(f"transferable: {r.transferable}")
    print(f"reason: {r.reason}")
    if r.src_op:
        print(f"src op: idx={r.src_op.idx} {r.src_op.mnemonic} {r.src_op.dest}, "
              f"{r.src_op.rest}")
    if r.dst_op:
        print(f"dst op: idx={r.dst_op.idx} {r.dst_op.mnemonic} {r.dst_op.dest}, "
              f"{r.dst_op.rest}")
    return 0 if r.transferable else 2


if __name__ == "__main__":
    raise SystemExit(_main())
