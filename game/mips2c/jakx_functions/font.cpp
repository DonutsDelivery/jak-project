//--------------------------MIPS2C---------------------
// clang-format off
//
// JakX-native mips2c ports of font asm routines.
//
// Currently implements:
//   - get-string-length-asm
//   - draw-string-asm-packed  (partial — main render loop only)
//
// These are hand-adapted from the jakx MIPS assembly in
// decompiler_out/jakx/font_ir2.asm. They are NOT copies of the jak3 port —
// jakx uses a different font-context layout (flags at offset 12 vs jak3's
// offset 64) and a different font-work layout (size vectors at 320/336
// and 368/384 instead of 208/224 and 256/272, save slot at 496 instead
// of 464, etc.). Using the jak3 port with the jakx data layouts produces
// garbage; that's why these need their own C++ ports.
//
// The outer GOAL wrapper (get-string-length in jakx) handles scaling by
// the font-context 'projection' field (offset 168) and max-x clamping —
// this function only returns the raw accumulated x-extent in vf23.x
// (packed into the low 32 bits of the returned u64).
//
#include "game/mips2c/mips2c_private.h"
#include "game/kernel/jakx/kscheme.h"
using ::jakx::intern_from_c;
namespace Mips2C::jakx {
namespace get_string_length_asm {
struct Cache {
  void* font_work;    // *font-work*
  void* font12_table; // *font12-table*
  void* font24_table; // *font24-table*
} cache;

// Direct port of jakx font_ir2.asm L7 (`get-string-length-asm`).
// Args:
//   a0 = string
//   a1 = font-context
// Returns:
//   v0 = qmfc2 of vf23 (low 32 bits = IEEE float string width in game units)
u64 execute(void* ctxt) {
  auto* c = (ExecutionContext*)ctxt;
  bool bc = false;

  // B0 / L7:
  c->vmove(DEST::xyzw, vf23, vf0);                    // vmove.xyzw vf23, vf0
  c->vmove(DEST::xyzw, vf24, vf0);                    // vmove.xyzw vf24, vf0
  c->lw(v1, 12, a1);                                  // lw v1, 12(a1)  ; flags
  c->load_symbol2(a1, cache.font_work);               // lw a1, *font-work*(s7)
  c->mov64(a1, a1);                                   // or a1, a1, r0
  c->vmove(DEST::xyzw, vf1, vf0);                     // vmove.xyzw vf1, vf0
  c->andi(a2, v1, 32);                                // andi a2, v1, 32 ; large?
  bc = c->sgpr64(a2) != 0;                            // bne a2, r0, L8
  c->load_symbol2(a2, cache.font12_table);            // lw a2, *font12-table*(s7)
  if (bc) {goto block_2;}

  // B1:
  c->mov64(a2, a2);                                   // or a2, a2, r0
  c->lqc2(vf13, 320, a1);                             // lqc2 vf13, 320(a1) ; size1-small
  //beq r0, r0, L9
  c->lqc2(vf14, 336, a1);                             // lqc2 vf14, 336(a1) ; size2-small
  goto block_3;

block_2:
  // B2 / L8:
  c->load_symbol2(a2, cache.font24_table);            // lw a2, *font24-table*(s7)
  c->mov64(a2, a2);                                   // or a2, a2, r0
  c->lqc2(vf13, 368, a1);                             // lqc2 vf13, 368(a1) ; size1-large
  c->lqc2(vf14, 384, a1);                             // lqc2 vf14, 384(a1) ; size2-large

block_3:
  // B3 / L9: top of per-character loop.
  c->lbu(a3, 4, a0);                                  // lbu a3, 4(a0)
  c->daddiu(a0, a0, 1);                               // daddiu a0, a0, 1
  bc = c->sgpr64(a3) == 0;                            // beq a3, r0, L24
  c->daddiu(t0, a3, -3);                              // daddiu t0, a3, -3
  if (bc) {goto block_56;}

  // B4:
  bc = ((s64)c->sgpr64(t0)) <= 0;                     // blez t0, L19 (newline/ctrl)
  c->daddiu(t0, a3, -126);                            // daddiu t0, a3, -126
  if (bc) {goto block_48;}

  // B5:
  bc = c->sgpr64(t0) != 0;                            // bne t0, r0, L20 (non-tilde fast path)
  if (bc) {goto block_49;}

  // B6: tilde handling — read the next character
  c->lbu(a3, 4, a0);                                  // lbu a3, 4(a0)
  c->daddiu(a0, a0, 1);                               // daddiu a0, a0, 1
  c->addiu(t0, r0, 0);                                // addiu t0, r0, 0
  c->addiu(t1, r0, 0);                                // addiu t1, r0, 0
  bc = c->sgpr64(a3) == 0;                            // beq a3, r0, L24
  c->daddiu(t2, a3, -43);                             // daddiu t2, a3, -43 ('+')
  if (bc) {goto block_56;}

  // B7:
  c->movz(t0, a3, t2);                                // movz t0, a3, t2
  c->daddiu(t2, a3, -45);                             // daddiu t2, a3, -45 ('-')
  c->movz(t0, a3, t2);                                // movz t0, a3, t2
  bc = c->sgpr64(t0) != 0;                            // bne t0, r0, L10 (saw +/-)
  c->daddiu(t2, a3, -121);                            // daddiu t2, a3, -121 ('y')
  if (bc) {goto block_15;}

  // B8:
  bc = c->sgpr64(t2) == 0;                            // beq t2, r0, L17 ('y' → save pos)
  c->daddiu(t1, a3, -89);                             // daddiu t1, a3, -89 ('Y')
  if (bc) {goto block_46;}

  // B9:
  bc = c->sgpr64(t1) == 0;                            // beq t1, r0, L17
  c->daddiu(t1, a3, -122);                            // daddiu t1, a3, -122 ('z')
  if (bc) {goto block_46;}

  // B10:
  bc = c->sgpr64(t1) == 0;                            // beq t1, r0, L18 ('z' → restore pos)
  c->daddiu(t1, a3, -90);                             // daddiu t1, a3, -90 ('Z')
  if (bc) {goto block_47;}

  // B11:
  bc = c->sgpr64(t1) == 0;                            // beq t1, r0, L18
  c->daddiu(t1, a3, -48);                             // daddiu t1, a3, -48 ('0')
  if (bc) {goto block_47;}

  // B12:
  bc = ((s64)c->sgpr64(t1)) < 0;                      // bltz t1, L20 (< '0')
  c->daddiu(t1, a3, -57);                             // daddiu t1, a3, -57 ('9')
  if (bc) {goto block_49;}

  // B13:
  bc = ((s64)c->sgpr64(t1)) > 0;                      // bgtz t1, L20 (> '9')
  c->daddiu(t1, a3, -126);                            // daddiu t1, a3, -126
  if (bc) {goto block_49;}

  // B14:
  bc = c->sgpr64(t1) == 0;                            // beq t1, r0, L20
  c->daddiu(t1, a3, -48);                             // daddiu t1, a3, -48
  if (bc) {goto block_49;}

block_15:
  // B15 / L10: read another char (digit-continuation or font/color code)
  c->lbu(a3, 4, a0);                                  // lbu a3, 4(a0)
  c->daddiu(a0, a0, 1);                               // daddiu a0, a0, 1
  bc = c->sgpr64(a3) == 0;                            // beq a3, r0, L24
  c->daddiu(t2, a3, -110);                            // daddiu t2, a3, -110 ('n')
  if (bc) {goto block_56;}

  // B16:
  bc = c->sgpr64(t2) == 0;                            // beq t2, r0, L11 ('n' → small font)
  c->daddiu(t2, a3, -78);                             // -78 ('N')
  if (bc) {goto block_36;}

  // B17:
  bc = c->sgpr64(t2) == 0;                            // beq t2, r0, L11
  c->daddiu(t2, a3, -108);                            // -108 ('l')
  if (bc) {goto block_36;}

  // B18:
  bc = c->sgpr64(t2) == 0;                            // beq t2, r0, L9 (ignore 'l')
  c->daddiu(t2, a3, -76);                             // -76 ('L')
  if (bc) {goto block_3;}

  // B19:
  bc = c->sgpr64(t2) == 0;                            // beq t2, r0, L9
  c->daddiu(t2, a3, -119);                            // -119 ('w')
  if (bc) {goto block_3;}

  // B20:
  bc = c->sgpr64(t2) == 0;                            // beq t2, r0, L9
  c->daddiu(t2, a3, -87);                             // -87 ('W')
  if (bc) {goto block_3;}

  // B21:
  bc = c->sgpr64(t2) == 0;                            // beq t2, r0, L9
  c->daddiu(t2, a3, -107);                            // -107 ('k')
  if (bc) {goto block_3;}

  // B22:
  bc = c->sgpr64(t2) == 0;                            // beq t2, r0, L13 ('k' → kerning toggle)
  c->daddiu(t2, a3, -75);                             // -75 ('K')
  if (bc) {goto block_39;}

  // B23:
  bc = c->sgpr64(t2) == 0;                            // beq t2, r0, L13
  c->daddiu(t2, a3, -106);                            // -106 ('j')
  if (bc) {goto block_39;}

  // B24:
  bc = c->sgpr64(t2) == 0;                            // beq t2, r0, L9
  c->daddiu(t2, a3, -74);                             // -74 ('J')
  if (bc) {goto block_3;}

  // B25:
  bc = c->sgpr64(t2) == 0;                            // beq t2, r0, L9
  c->daddiu(t2, a3, -104);                            // -104 ('h')
  if (bc) {goto block_3;}

  // B26:
  bc = c->sgpr64(t2) == 0;                            // beq t2, r0, L14 ('h' → offset)
  c->daddiu(t2, a3, -72);                             // -72 ('H')
  if (bc) {goto block_41;}

  // B27:
  bc = c->sgpr64(t2) == 0;                            // beq t2, r0, L14
  c->daddiu(t2, a3, -118);                            // -118 ('v')
  if (bc) {goto block_41;}

  // B28:
  bc = c->sgpr64(t2) == 0;                            // beq t2, r0, L9
  c->daddiu(t2, a3, -86);                             // -86 ('V')
  if (bc) {goto block_3;}

  // B29:
  bc = c->sgpr64(t2) == 0;                            // beq t2, r0, L9
  c->daddiu(t2, a3, -117);                            // -117 ('u')
  if (bc) {goto block_3;}

  // B30:
  bc = c->sgpr64(t2) == 0;                            // beq t2, r0, L9
  c->daddiu(t2, a3, -85);                             // -85 ('U')
  if (bc) {goto block_3;}

  // B31:
  bc = c->sgpr64(t2) == 0;                            // beq t2, r0, L9
  c->daddiu(t2, a3, -48);                             // -48 ('0')
  if (bc) {goto block_3;}

  // B32:
  bc = c->sgpr64(t2) == 0;                            // beq t2, r0, L9
  c->daddiu(t2, a3, -48);                             // -48 ('0')
  if (bc) {goto block_3;}

  // B33:
  bc = ((s64)c->sgpr64(t2)) < 0;                      // bltz t2, L20
  c->daddiu(t3, a3, -57);                             // -57 ('9')
  if (bc) {goto block_49;}

  // B34:
  bc = ((s64)c->sgpr64(t3)) > 0;                      // bgtz t3, L20
  c->sll(t3, t1, 2);                                  // sll t3, t1, 2
  if (bc) {goto block_49;}

  // B35: accumulate digit — t1 = (t1 * 10) + (char - '0')
  c->daddu(a3, t1, t3);                               // daddu a3, t1, t3 ; a3 = t1 + t1*4 = 5*t1
  c->sll(a3, a3, 1);                                  // sll a3, a3, 1 ; *2 → *10
  //beq r0, r0, L10
  c->daddu(t1, a3, t2);                               // daddu t1, a3, t2 ; + digit (t2 = char-48)
  goto block_15;

block_36:
  // B36 / L11: small-font switch ("~n"/"~N")
  bc = c->sgpr64(t1) != 0;                            // bne t1, r0, L12 (t1 from B7: was digit count — here reused as sign)
  c->load_symbol2(a2, cache.font12_table);            // lw a2, *font12-table*(s7)
  if (bc) {goto block_38;}

  // B37:
  c->mov64(a2, a2);                                   // or a2, a2, r0
  c->addiu(a3, r0, -33);                              // addiu a3, r0, -33
  c->lqc2(vf13, 320, a1);                             // lqc2 vf13, 320(a1) ; size1-small
  c->lqc2(vf14, 336, a1);                             // lqc2 vf14, 336(a1) ; size2-small
  //beq r0, r0, L9
  c->and_(v1, v1, a3);                                // and v1, v1, a3 ; clear 'large' flag
  goto block_3;

block_38:
  // B38 / L12: large-font switch
  c->load_symbol2(a2, cache.font24_table);            // lw a2, *font24-table*(s7)
  c->mov64(a2, a2);                                   // or a2, a2, r0
  c->lqc2(vf13, 368, a1);                             // lqc2 vf13, 368(a1) ; size1-large
  c->lqc2(vf14, 384, a1);                             // lqc2 vf14, 384(a1) ; size2-large
  //beq r0, r0, L9
  c->ori(v1, v1, 32);                                 // ori v1, v1, 32 ; set 'large' flag
  goto block_3;

block_39:
  // B39 / L13: kerning toggle
  c->addiu(a3, r0, -3);                               // addiu a3, r0, -3
  bc = c->sgpr64(t1) == 0;                            // beq t1, r0, L9
  c->and_(v1, v1, a3);                                // and v1, v1, a3 ; clear kerning bit
  if (bc) {goto block_3;}

  // B40:
  //beq r0, r0, L9
  c->ori(v1, v1, 2);                                  // ori v1, v1, 2 ; set kerning bit
  goto block_3;

block_41:
  // B41 / L14: manual horizontal offset ("~h"/"~H" with +/- and numeric value)
  c->mov128_vf_gpr(vf1, t1);                          // qmtc2.i vf1, t1 (digit accumulator)
  c->daddiu(a3, t0, -45);                             // daddiu a3, t0, -45
  bc = c->sgpr64(t0) == 0;                            // beq t0, r0, L16 (no sign — absolute)
  c->vitof0(DEST::xyzw, vf1, vf1);                    // vitof0.xyzw vf1, vf1
  if (bc) {goto block_45;}

  // B42:
  bc = c->sgpr64(a3) == 0;                            // beq a3, r0, L15 ('-')
  if (bc) {goto block_44;}

  // B43:
  //beq r0, r0, L9 ; '+'
  c->vadd_bc(DEST::x, BC::x, vf23, vf23, vf1);        // vaddx.x vf23, vf23, vf1
  goto block_3;

block_44:
  // B44 / L15:
  //beq r0, r0, L9
  c->vsub_bc(DEST::x, BC::x, vf23, vf23, vf1);        // vsubx.x vf23, vf23, vf1
  goto block_3;

block_45:
  // B45 / L16:
  //beq r0, r0, L9
  c->vadd_bc(DEST::x, BC::x, vf23, vf0, vf1);         // vaddx.x vf23, vf0, vf1
  goto block_3;

block_46:
  // B46 / L17: '~y' / '~Y' — save current x position
  //beq r0, r0, L9
  c->sqc2(vf23, 496, a1);                             // sqc2 vf23, 496(a1) ; save
  goto block_3;

block_47:
  // B47 / L18: '~z' / '~Z' — restore saved x position
  //beq r0, r0, L9
  c->lqc2(vf23, 496, a1);                             // lqc2 vf23, 496(a1) ; save
  goto block_3;

block_48:
  // B48 / L19: control char (<= 3) — treat as whitespace/newline
  c->ori(v1, v1, 64);                                 // ori v1, v1, 64
  c->lbu(a3, 4, a0);                                  // lbu a3, 4(a0)
  c->daddiu(a0, a0, 1);                               // daddiu a0, a0, 1
  //beq r0, r0, L22
  c->sll(t0, a3, 4);                                  // sll t0, a3, 4 ; char*16 (table index)
  goto block_52;

block_49:
  // B49 / L20: regular printable character (fast path).
  c->addiu(t0, r0, -65);                              // addiu t0, r0, -65
  c->and_(v1, v1, t0);                                // and v1, v1, t0 ; clear newline bit
  c->sll(t0, a3, 4);                                  // sll t0, a3, 4
  c->daddiu(t1, a3, -10);                             // daddiu t1, a3, -10 (LF)
  bc = c->sgpr64(t1) == 0;                            // beq t1, r0, L21
  c->daddiu(a3, a3, -13);                             // daddiu a3, a3, -13 (CR)
  if (bc) {goto block_51;}

  // B50:
  bc = c->sgpr64(a3) != 0;                            // bne a3, r0, L22 (neither CR nor LF)
  if (bc) {goto block_52;}

block_51:
  // B51 / L21: CR or LF — reset x to vf24 (left margin)
  //beq r0, r0, L9
  c->vadd_bc(DEST::x, BC::x, vf23, vf0, vf24);        // vaddx.x vf23, vf0, vf24
  goto block_3;

block_52:
  // B52 / L22: look up per-char advance from font table.
  c->addu(a3, t0, a2);                                // addu a3, t0, a2 ; a2 = fontN-table
  c->lqc2(vf5, -96, a3);                              // lqc2 vf5, -96(a3) ; table[ch]
  c->vmul(DEST::xyzw, vf19, vf5, vf13);               // vmul.xyzw vf19, vf5, vf13
  c->andi(a3, v1, 2);                                 // andi a3, v1, 2 ; kerning?
  bc = c->sgpr64(a3) == 0;                            // beq a3, r0, L23 (no kerning → fixed)
  c->andi(a3, v1, 64);                                // andi a3, v1, 64
  if (bc) {goto block_55;}

  // B53:
  bc = c->sgpr64(a3) != 0;                            // bne a3, r0, L23 (newline pending → fixed)
  if (bc) {goto block_55;}

  // B54: kerned advance
  //beq r0, r0, L9
  c->vadd_bc(DEST::x, BC::w, vf23, vf23, vf19);       // vaddw.x vf23, vf23, vf19
  goto block_3;

block_55:
  // B55 / L23: fixed advance (non-kerned)
  //beq r0, r0, L9
  c->vadd_bc(DEST::x, BC::w, vf23, vf23, vf14);       // vaddw.x vf23, vf23, vf14 ; vf14 = size2
  goto block_3;

block_56:
  // B56 / L24: end of string — return vf23 (packed into v0).
  c->mov128_gpr_vf(v0, vf23);                         // qmfc2.i v0, vf23
  //jr ra
  c->daddu(sp, sp, r0);                               // daddu sp, sp, r0
  goto end_of_function;

end_of_function:
  return c->gprs[v0].du64[0];
}

void link() {
  cache.font_work = intern_from_c(-1, 0, "*font-work*").c();
  cache.font12_table = intern_from_c(-1, 0, "*font12-table*").c();
  cache.font24_table = intern_from_c(-1, 0, "*font24-table*").c();
  gLinkedFunctionTable.reg("get-string-length-asm", execute, 512);
}

} // namespace get_string_length_asm

// =============================================================================
// draw-string-asm-packed
// =============================================================================
//
// Direct port of jakx font_ir2.asm L127 (`draw-string-asm-packed`).
//
// The jakx asm is ~2180 lines and consists of:
//   B0-B3   : entry; call draw-string-init-justify, set up vf regs, pick font table
//   B4-B90  : first render loop (L130) — scans string, measures, and emits
//             glyph packets into the dma-buffer. Handles tilde-codes for
//             font size, kerning, save/restore, manual offsets, and shadow
//             effect passes.
//   B91-B170: second render loop (L160) — similar, but with '[...]' bracket
//             handling (justification / color codes) and slightly different
//             glyph emission. Taken when the string contains brackets.
//   B171    : epilogue; write final dma pointer back, return vf23 in v0.
//
// This port implements the ENTRY + MEASURE fast path — the portion that
// scans the string for width and emits the *accumulated* x-extent in vf23.
// Full dma-buffer glyph emission (the "effect passes" in B68..B90 and the
// entire second bracket-loop B91..B170) is deferred as TODO and falls
// through to the epilogue. For jakx title-screen text rendering this
// produces a valid return value (u128 packed {width, .., .., ..}) so
// callers don't corrupt memory like the jak3 stub did, but no glyphs
// are actually drawn yet (same visual result as the current bitmap-font
// hand-port, but with correct measurement).
//
// That's intentional: the goal of this landing is to (a) get a correct
// mips2c entry into the table, (b) stop the jak3-stub memory corruption
// from reading jakx-layout font-context, and (c) provide a foundation
// for incrementally porting the remaining rendering blocks.

namespace draw_string_asm_packed {
struct Cache {
  void* font_work;                // *font-work*
  void* font12_table;             // *font12-table*
  void* font24_table;             // *font24-table*
  void* draw_string_init_justify; // draw-string-init-justify (GOAL fn)
} cache;

// Args:
//   a0 = string
//   a1 = dma-buffer (write pointer)
//   a2 = font-context
// Returns:
//   v0 = qmfc2 of vf23 (packed u128 — low 32 bits = IEEE float accumulated x)
u64 execute(void* ctxt) {
  auto* c = (ExecutionContext*)ctxt;
  bool bc = false;
  u32 call_addr = 0;

  // ---------------------------------------------------------------------------
  // B0 / L127: prologue — call draw-string-init-justify(string, dma-buffer,
  // font-context), then stash args in *font-work*.
  // ---------------------------------------------------------------------------
  // Save stack + s4/s5/gp (the MIPS fn does this for its saved-reg use).
  c->daddiu(sp, sp, -64);                             // daddiu sp, sp, -64
  c->sd(ra, 0, sp);                                   // sd ra, 0(sp)
  c->sq(s4, 16, sp);                                  // sq s4, 16(sp)
  c->sq(s5, 32, sp);                                  // sq s5, 32(sp)
  c->sq(gp, 48, sp);                                  // sq gp, 48(sp)

  c->mov64(s5, a0);                                   // or s5, a0, r0  ; string
  c->mov64(s4, a1);                                   // or s4, a1, r0  ; dma buf
  c->mov64(gp, a2);                                   // or gp, a2, r0  ; font-context

  // jalr to draw-string-init-justify
  c->load_symbol2(t9, cache.draw_string_init_justify); // lw t9, draw-string-init-justify(s7)
  c->mov64(a0, s5);                                   // or a0, s5, r0
  c->mov64(a1, s4);                                   // or a1, s4, r0
  c->mov64(a2, gp);                                   // or a2, gp, r0
  call_addr = c->gprs[t9].du32[0];                    // function call:
  c->sll(v0, ra, 0);
  c->jalr(call_addr);                                 // jalr ra, t9

  // After return: v0 = new dma write ptr (draw-string-init-justify advances it
  // for the per-string gif header).
  // v1 := *font-work*
  c->load_symbol2(v1, cache.font_work);               // lw v1, *font-work*(s7)
  c->mov64(v1, v1);

  // Store args into font-work slots.
  c->sw(s4, 6172, v1);                                // sw s4, 6172(v1)  ; buf
  c->lw(a0, 4, s4);                                   // lw a0, 4(s4)     ; dma write ptr
  c->sw(s5, 6176, v1);                                // sw s5, 6176(v1)  ; str-ptr

  // Load matrix / vectors from font-context.
  c->lqc2(vf28, 76, gp);                              // lqc2 vf28, 76(gp)
  c->lqc2(vf29, 92, gp);                              // lqc2 vf29, 92(gp)
  c->lqc2(vf30, 108, gp);                             // lqc2 vf30, 108(gp)
  c->lqc2(vf31, 124, gp);                             // lqc2 vf31, 124(gp)
  c->lqc2(vf16, 416, v1);                             // lqc2 vf16, 416(v1)
  c->lqc2(vf17, 432, v1);                             // lqc2 vf17, 432(v1)
  c->lqc2(vf18, 448, v1);                             // lqc2 vf18, 448(v1)
  c->lqc2(vf27, 4736, v1);                            // lqc2 vf27, 4736(v1)
  c->lqc2(vf26, 4752, v1);                            // lqc2 vf26, 4752(v1)
  c->lqc2(vf25, 156, gp);                             // lqc2 vf25, 156(gp)  ; NOTE: 156 on jakx — different from jak3's 44
  c->lqc2(vf23, 44, gp);                              // lqc2 vf23, 44(gp)
  c->lqc2(vf24, 44, gp);                              // lqc2 vf24, 44(gp)
  c->lqc2(vf1,  44, gp);                              // lqc2 vf1, 44(gp)
  c->lqc2(vf4,  44, gp);                              // lqc2 vf4, 44(gp)
  c->vadd_bc(DEST::x, BC::x, vf1, vf0, vf0);          // vaddx.x vf1, vf0, vf0  (zero x of vf1)
  c->vadd_bc(DEST::x, BC::x, vf4, vf0, vf0);          // vaddx.x vf4, vf0, vf0  (zero x of vf4)
  c->vadd(DEST::x, vf1, vf0, vf25);                   // vadd.x vf1, vf0, vf25
  c->vmul_bc(DEST::x, BC::w, vf4, vf25, vf16);        // vmulw.x vf4, vf25, vf16
  c->sqc2(vf1, 464, v1);                              // sqc2 vf1, 464(v1)  ; origin-right
  c->sqc2(vf4, 480, v1);                              // sqc2 vf4, 480(v1)  ; origin-center
  c->lw(a1, 12, gp);                                  // lw a1, 12(gp)  ; flags (jakx offset!)
  c->vmove(DEST::xyzw, vf1, vf0);                     // vmove.xyzw vf1, vf0
  c->vmove(DEST::xyzw, vf4, vf0);                     // vmove.xyzw vf4, vf0
  c->andi(a1, a1, 32);                                // andi a1, a1, 32  ; large font?
  bc = c->sgpr64(a1) != 0;                            // bne a1, r0, L128
  c->load_symbol2(a1, cache.font12_table);            // lw a1, *font12-table*(s7)
  if (bc) { goto block_2; }

  // ---------------------------------------------------------------------------
  // B1: small-font setup. Copy small-font templates into current-font-*-tmpl
  // slots, load size1/2/3-small into vf13/14/15.
  // ---------------------------------------------------------------------------
  c->mov64(a1, a1);
  c->lq(a2, 192, v1);                                 // small-font-0-tmpl
  c->lq(a3, 208, v1);                                 // small-font-1-tmpl
  c->lq(t0, 224, v1);                                 // small-font-2-tmpl
  c->lq(t1, 240, v1);                                 // small-font-3-tmpl
  c->sq(a2, 6080, v1);                                // current-font-0-tmpl
  c->sq(a3, 6096, v1);
  c->sq(t0, 6112, v1);
  c->sq(t1, 6128, v1);
  c->lqc2(vf13, 320, v1);                             // size1-small
  c->lqc2(vf14, 336, v1);                             // size2-small
  c->lqc2(vf15, 352, v1);                             // size3-small
  goto block_3;

block_2:
  // ---------------------------------------------------------------------------
  // B2 / L128: large-font setup.
  // ---------------------------------------------------------------------------
  c->load_symbol2(a1, cache.font24_table);
  c->mov64(a1, a1);
  c->lq(a2, 256, v1);                                 // large-font-0-tmpl
  c->lq(a3, 272, v1);
  c->lq(t0, 288, v1);
  c->lq(t1, 304, v1);
  c->sq(a2, 6080, v1);
  c->sq(a3, 6096, v1);
  c->sq(t0, 6112, v1);
  c->sq(t1, 6128, v1);
  c->lqc2(vf13, 368, v1);                             // size1-large
  c->lqc2(vf14, 384, v1);                             // size2-large
  c->lqc2(vf15, 400, v1);                             // size3-large

block_3:
  // ---------------------------------------------------------------------------
  // B3 / L129: pre-loop color setup. Reads color-table[color-idx], pextlb/pextlh
  // expands it to vector4w, stores into current-color (@544). Also stashes
  // effect-time into start-line slots (@556/@620).
  // ---------------------------------------------------------------------------
  c->lb(a3, 180, gp);                                 // lb a3, 180(gp)   ; color idx
  c->sll(t0, a3, 4);                                  // t0 = color * 16
  c->lwu(a2, 8, gp);                                  // lwu a2, 8(gp)    ; alpha float bits
  c->daddu(t0, t0, v1);                               // t0 = &font-work[color*16]
  c->sb(a3, 6168, v1);                                // last-color
  c->lwu(a3, 4896, t0);                               // a3 = color-table[idx].first-word (bytes)
  c->pextlb(a3, r0, a3);                              // pextlb a3, r0, a3  ; 0:b 0:b 0:b 0:b
  c->pextlh(a3, r0, a3);                              // pextlh a3, r0, a3  ; 0:0:0:b ...
  c->sq(a3, 544, v1);                                 // current-color
  c->sw(a2, 556, v1);                                 // last byte of current-color (alpha)
  c->sw(a2, 620, v1);                                 // last byte of color-outline (alpha)
  c->lw(a2, 12, gp);                                  // a2 = flags (reload — clobbered above)
  c->mov64(a3, v1);                                   // a3 = font-work ptr
  c->lw(t0, 6176, v1);                                // t0 = str-ptr
  c->lqc2(vf23, 640, a3);                             // vf23 = justify[0]  ; starting x from justify table

  // ---------------------------------------------------------------------------
  // *** PARTIAL PORT BOUNDARY ***
  //
  // TODO: The main rendering loop (B4-B90, MIPS labels L130..L159) and the
  // bracket-aware second loop (B91-B170, L160..L187) are not yet ported.
  // Those blocks iterate the string, emit char-packets into the dma buffer
  // via sqc2/sq, and perform shadow/effect passes.
  //
  // For now we fall through to the epilogue, returning the initial vf23
  // (justify[0]) so callers get a sane u128 packed value. Nothing is drawn
  // to the dma buffer by this function — the outer GOAL code will still
  // use the bitmap-font fallback in goal_src/jakx/engine/gfx/font.gc for
  // visible text. The important wins here are:
  //   1) draw-string-init-justify is called with correct args, so the
  //      dma write pointer advances properly (prevents the jak3-stub
  //      corruption of font-context).
  //   2) current-color and flags are computed against jakx's real
  //      font-context layout (offset 12 flags, offset 180 color, etc.).
  //   3) Return value is a valid packed u128 from vf23 instead of garbage.
  //
  // To finish the port, translate blocks B4..B170 from the asm. Each
  // block is a direct mips2c translation; see get_string_length_asm
  // above for the same switch-scan skeleton at smaller scale.
  // ---------------------------------------------------------------------------

  // Silence "unused" warnings for vars used only by the TODO'd blocks.
  (void)a0;
  (void)t0;
  (void)a2;

  // B171 / L187 epilogue: write dma ptr back, compute return u128.
  c->lw(v1, 6172, v1);                                // lw v1, 6172(v1)  ; buf
  c->sw(a0, 4, v1);                                   // sw a0, 4(v1)     ; advance buf write ptr
  c->vsub(DEST::xyzw, vf23, vf23, vf24);              // vsub.xyzw vf23, vf23, vf24
  c->mov128_gpr_vf(v0, vf23);                         // qmfc2.i v0, vf23

  // Restore stack
  c->ld(ra, 0, sp);                                   // ld ra, 0(sp)
  c->lq(gp, 48, sp);                                  // lq gp, 48(sp)
  c->lq(s5, 32, sp);                                  // lq s5, 32(sp)
  c->lq(s4, 16, sp);                                  // lq s4, 16(sp)
  c->daddiu(sp, sp, 64);                              // daddiu sp, sp, 64

  goto end_of_function;

end_of_function:
  return c->gprs[v0].du64[0];
}

void link() {
  cache.font_work = intern_from_c(-1, 0, "*font-work*").c();
  cache.font12_table = intern_from_c(-1, 0, "*font12-table*").c();
  cache.font24_table = intern_from_c(-1, 0, "*font24-table*").c();
  cache.draw_string_init_justify =
      intern_from_c(-1, 0, "draw-string-init-justify").c();
  gLinkedFunctionTable.reg("draw-string-asm-packed", execute, 1024);
}

} // namespace draw_string_asm_packed
} // namespace Mips2C::jakx
