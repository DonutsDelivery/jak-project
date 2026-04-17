//--------------------------MIPS2C---------------------
// clang-format off
//
// JakX-native mips2c ports of font asm routines.
//
// Currently implements:
//   - get-string-length-asm
//   - draw-string-asm-packed     (COMPLETE — all 171 blocks / both
//                                 render loops ported)
//   - draw-string-init-justify   (COMPLETE — all 79 blocks; justify
//                                 pre-pass called by draw-string-asm-
//                                 packed at entry)
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
// This port is COMPLETE — all 171 blocks of the jakx asm are now
// translated. The function consists of two render loops:
//
//   First loop  (B0-B91, L127..L159)   — primary pass with 5-layer
//                                         outline/shadow effect rendering
//                                         gated by flag bit 4096.
//   Second loop (B92-B171, L160..L187) — secondary pass with bracket-
//                                         aware '[...]' color state
//                                         push/pop and '~l'/'~L'/'~u'/'~U'
//                                         color code handling. Always
//                                         emits exactly one packet per
//                                         glyph (no effect gate) and
//                                         uses hvdf-offset (vf27) as
//                                         the primary offset vector
//                                         instead of hvdf-shadow (vf26).
//
// Both loops share a single epilogue (block_171) that writes the
// advanced dma pointer back to font-work[buf] and returns vf23
// packed into v0.

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
  // Register roster on entry to B4 / L130 (per asm lines 6603..6605):
  //   a0 = dma write ptr (from lw a0, 4(s4))
  //   a1 = fontN-table base
  //   a2 = flags (reloaded from font-context @ 12)
  //   a3 = font-work ptr (= v1) — used as the justify[] cursor
  //   t0 = str-ptr
  //   v1 = *font-work*
  //   vf13/14/15 = size1/2/3 for selected font
  //   vf16/17/18 = size-st1/2/3
  //   vf23 = current cursor (= justify[0] at start)
  //   vf24 = origin (from font-context @ 44)
  //   vf25 = strip-gif (font-context @ 156, jakx layout)
  //   vf26 = hvdf-shadow (@ 4752), vf27 = hvdf-offset (@ 4736)
  //   vf28..vf31 = calc-mat rows
  // ---------------------------------------------------------------------------

block_4:
  // B4 / L130: top of render loop. Fetch next char from str-ptr, load
  // current-font-0-tmpl (for the emitted packet's gif tag).
  c->lbu(t1, 4, t0);                                  // lbu t1, 4(t0) ; char
  c->daddiu(t0, t0, 1);                               // daddiu t0, t0, 1
  c->lqc2(vf20, 6080, v1);                            // lqc2 vf20, 6080(v1) ; current-font-0-tmpl
  bc = c->sgpr64(t1) == 0;                            // beq t1, r0, L159 ; end-of-string
  c->daddiu(t2, t1, -3);                              // daddiu t2, t1, -3
  if (bc) { goto block_91; }

  // B5:
  bc = ((s64)c->sgpr64(t2)) <= 0;                     // blez t2, L144 (ctrl char)
  c->daddiu(t2, t1, -126);                            // daddiu t2, t1, -126 ('~')
  if (bc) { goto block_57; }

  // B6:
  bc = c->sgpr64(t2) != 0;                            // bne t2, r0, L148 (printable)
  if (bc) { goto block_63; }

  // B7: tilde-code: read next char
  c->lbu(t1, 4, t0);                                  // lbu t1, 4(t0)
  c->daddiu(t0, t0, 1);                               // daddiu t0, t0, 1
  c->addiu(t2, r0, 0);                                // addiu t2, r0, 0 ; sign accumulator
  c->addiu(t3, r0, 0);                                // addiu t3, r0, 0 ; digit accumulator
  bc = c->sgpr64(t1) == 0;                            // beq t1, r0, L159
  c->daddiu(t4, t1, -43);                             // '+'
  if (bc) { goto block_91; }

  // B8:
  c->movz(t2, t1, t4);                                // movz t2, t1, t4
  c->daddiu(t4, t1, -45);                             // '-'
  c->movz(t2, t1, t4);                                // movz t2, t1, t4
  bc = c->sgpr64(t2) != 0;                            // bne t2, r0, L131 (saw +/-)
  c->daddiu(t4, t1, -91);                             // '['
  if (bc) { goto block_18; }

  // B9:
  bc = c->sgpr64(t4) == 0;                            // beq t4, r0, L130 (ignore '[')
  c->daddiu(t3, t1, -93);                             // ']'
  if (bc) { goto block_4; }

  // B10:
  bc = c->sgpr64(t3) == 0;                            // beq t3, r0, L130 (ignore ']')
  c->daddiu(t3, t1, -121);                            // 'y'
  if (bc) { goto block_4; }

  // B11:
  bc = c->sgpr64(t3) == 0;                            // beq t3, r0, L142 ('y' save)
  c->daddiu(t3, t1, -89);                             // 'Y'
  if (bc) { goto block_55; }

  // B12:
  bc = c->sgpr64(t3) == 0;                            // beq t3, r0, L142 ('Y' save)
  c->daddiu(t3, t1, -122);                            // 'z'
  if (bc) { goto block_55; }

  // B13:
  bc = c->sgpr64(t3) == 0;                            // beq t3, r0, L143 ('z' restore)
  c->daddiu(t3, t1, -90);                             // 'Z'
  if (bc) { goto block_56; }

  // B14:
  bc = c->sgpr64(t3) == 0;                            // beq t3, r0, L143 ('Z' restore)
  c->daddiu(t3, t1, -48);                             // '0'
  if (bc) { goto block_56; }

  // B15:
  bc = ((s64)c->sgpr64(t3)) < 0;                      // bltz t3, L148 (< '0' non-tilde printable)
  c->daddiu(t3, t1, -57);                             // '9'
  if (bc) { goto block_63; }

  // B16:
  bc = ((s64)c->sgpr64(t3)) > 0;                      // bgtz t3, L148 (> '9')
  c->daddiu(t3, t1, -126);                            // '~'
  if (bc) { goto block_63; }

  // B17:
  bc = c->sgpr64(t3) == 0;                            // beq t3, r0, L148 ('~' again — printable)
  c->daddiu(t3, t1, -48);                             // digit value
  if (bc) { goto block_63; }

block_18:
  // B18 / L131: read another char (code selector or digit continuation)
  c->lbu(t1, 4, t0);                                  // lbu t1, 4(t0)
  c->daddiu(t0, t0, 1);                               // daddiu t0, t0, 1
  bc = c->sgpr64(t1) == 0;                            // beq t1, r0, L159
  c->daddiu(t4, t1, -110);                            // 'n'
  if (bc) { goto block_91; }

  // B19:
  bc = c->sgpr64(t4) == 0;                            // beq t4, r0, L132 ('n' small)
  c->daddiu(t4, t1, -78);                             // 'N'
  if (bc) { goto block_38; }

  // B20:
  bc = c->sgpr64(t4) == 0;                            // beq t4, r0, L132 ('N' small)
  c->daddiu(t4, t1, -108);                            // 'l'
  if (bc) { goto block_38; }

  // B21:
  bc = c->sgpr64(t4) == 0;                            // beq t4, r0, L130 (ignore 'l')
  c->daddiu(t4, t1, -76);                             // 'L'
  if (bc) { goto block_4; }

  // B22:
  bc = c->sgpr64(t4) == 0;                            // beq t4, r0, L130 (ignore 'L')
  c->daddiu(t4, t1, -119);                            // 'w'
  if (bc) { goto block_4; }

  // B23:
  bc = c->sgpr64(t4) == 0;                            // beq t4, r0, L134 ('w')
  c->daddiu(t4, t1, -87);                             // 'W'
  if (bc) { goto block_41; }

  // B24:
  bc = c->sgpr64(t4) == 0;                            // beq t4, r0, L134 ('W')
  c->daddiu(t4, t1, -107);                            // 'k'
  if (bc) { goto block_41; }

  // B25:
  bc = c->sgpr64(t4) == 0;                            // beq t4, r0, L135 ('k' kerning)
  c->daddiu(t4, t1, -75);                             // 'K'
  if (bc) { goto block_43; }

  // B26:
  bc = c->sgpr64(t4) == 0;                            // beq t4, r0, L135 ('K')
  c->daddiu(t4, t1, -106);                            // 'j'
  if (bc) { goto block_43; }

  // B27:
  bc = c->sgpr64(t4) == 0;                            // beq t4, r0, L130 (ignore 'j')
  c->daddiu(t4, t1, -74);                             // 'J'
  if (bc) { goto block_4; }

  // B28:
  bc = c->sgpr64(t4) == 0;                            // beq t4, r0, L130
  c->daddiu(t4, t1, -104);                            // 'h'
  if (bc) { goto block_4; }

  // B29:
  bc = c->sgpr64(t4) == 0;                            // beq t4, r0, L136 ('h' h-offset)
  c->daddiu(t4, t1, -72);                             // 'H'
  if (bc) { goto block_45; }

  // B30:
  bc = c->sgpr64(t4) == 0;                            // beq t4, r0, L136 ('H')
  c->daddiu(t4, t1, -118);                            // 'v'
  if (bc) { goto block_45; }

  // B31:
  bc = c->sgpr64(t4) == 0;                            // beq t4, r0, L139 ('v' v-offset)
  c->daddiu(t4, t1, -86);                             // 'V'
  if (bc) { goto block_50; }

  // B32:
  bc = c->sgpr64(t4) == 0;                            // beq t4, r0, L139 ('V')
  c->daddiu(t4, t1, -117);                            // 'u'
  if (bc) { goto block_50; }

  // B33:
  bc = c->sgpr64(t4) == 0;                            // beq t4, r0, L130 (ignore 'u')
  c->daddiu(t4, t1, -85);                             // 'U'
  if (bc) { goto block_4; }

  // B34:
  bc = c->sgpr64(t4) == 0;                            // beq t4, r0, L130
  c->daddiu(t4, t1, -48);                             // '0'
  if (bc) { goto block_4; }

  // B35:
  bc = ((s64)c->sgpr64(t4)) < 0;                      // bltz t4, L148 (< '0' — treat as printable)
  c->daddiu(t5, t1, -57);                             // '9'
  if (bc) { goto block_63; }

  // B36:
  bc = ((s64)c->sgpr64(t5)) > 0;                      // bgtz t5, L148 (> '9')
  c->sll(t5, t3, 2);                                  // sll t5, t3, 2
  if (bc) { goto block_63; }

  // B37: digit accumulator: t3 = (t3 * 10) + (char - '0')
  c->daddu(t1, t3, t5);                               // t3 + t3*4 = 5*t3
  c->sll(t1, t1, 1);                                  // *2 → *10
  c->daddu(t3, t1, t4);                               // + digit
  goto block_18;

block_38:
  // B38 / L132: "~n"/"~N" — small font switch. If t3 (digit count) != 0,
  // jump to large-font path (L133).
  bc = c->sgpr64(t3) != 0;                            // bne t3, r0, L133
  c->addiu(t1, r0, -33);                              // -33 = ~32 (clear 'large' bit)
  if (bc) { goto block_40; }

  // B39: install small font templates/table/sizes, clear 'large' flag.
  c->lq(a1, 192, v1);                                 // small-font-0-tmpl
  c->lq(t2, 208, v1);
  c->lq(t3, 224, v1);
  c->lq(t4, 240, v1);
  c->sq(a1, 6080, v1);                                // current-font-0-tmpl
  c->sq(t2, 6096, v1);
  c->sq(t3, 6112, v1);
  c->sq(t4, 6128, v1);
  c->load_symbol2(a1, cache.font12_table);
  c->mov64(a1, a1);
  c->lqc2(vf13, 320, v1);                             // size1-small
  c->lqc2(vf14, 336, v1);                             // size2-small
  c->lqc2(vf15, 352, v1);                             // size3-small
  c->and_(a2, a2, t1);                                // clear bit 5 (large)
  goto block_4;

block_40:
  // B40 / L133: install large font templates/table/sizes, set 'large' flag.
  c->lq(a1, 256, v1);                                 // large-font-0-tmpl
  c->lq(t1, 272, v1);
  c->lq(t2, 288, v1);
  c->lq(t3, 304, v1);
  c->sq(a1, 6080, v1);
  c->sq(t1, 6096, v1);
  c->sq(t2, 6112, v1);
  c->sq(t3, 6128, v1);
  c->load_symbol2(a1, cache.font24_table);
  c->mov64(a1, a1);
  c->lqc2(vf13, 368, v1);
  c->lqc2(vf14, 384, v1);
  c->lqc2(vf15, 400, v1);
  c->ori(a2, a2, 32);                                 // set bit 5 (large)
  goto block_4;

block_41:
  // B41 / L134: "~w"/"~W" — toggle flag bit 0 (word-wrap? — flag 1).
  // If digit (t3)==0 → clear; else → set.
  c->addiu(t1, r0, -2);                               // -2 = ~1
  bc = c->sgpr64(t3) == 0;                            // beq t3, r0, L130
  c->and_(a2, a2, t1);                                // clear bit 0
  if (bc) { goto block_4; }

  // B42:
  c->ori(a2, a2, 1);                                  // set bit 0
  goto block_4;

block_43:
  // B43 / L135: "~k"/"~K" — toggle kerning (bit 1).
  c->addiu(t1, r0, -3);                               // -3 = ~2
  bc = c->sgpr64(t3) == 0;                            // beq t3, r0, L130
  c->and_(a2, a2, t1);                                // clear bit 1
  if (bc) { goto block_4; }

  // B44:
  c->ori(a2, a2, 2);                                  // set bit 1
  goto block_4;

block_45:
  // B45 / L136: "~h"/"~H" — horizontal offset with sign (t2) and digits (t3).
  c->mov128_vf_gpr(vf1, t3);                          // qmtc2.i vf1, t3
  c->daddiu(t1, t2, -45);                             // '-' check
  bc = c->sgpr64(t2) == 0;                            // beq t2, r0, L138 (no sign → absolute)
  c->vitof0(DEST::xyzw, vf1, vf1);                    // vitof0.xyzw vf1, vf1
  if (bc) { goto block_49; }

  // B46:
  bc = c->sgpr64(t1) == 0;                            // beq t1, r0, L137 ('-')
  if (bc) { goto block_48; }

  // B47: '+' → vf23.x += vf1.x
  c->vadd_bc(DEST::x, BC::x, vf23, vf23, vf1);        // vaddx.x vf23, vf23, vf1
  goto block_4;

block_48:
  // B48 / L137: '-' → vf23.x -= vf1.x
  c->vsub_bc(DEST::x, BC::x, vf23, vf23, vf1);        // vsubx.x vf23, vf23, vf1
  goto block_4;

block_49:
  // B49 / L138: absolute → vf23.x = vf1.x (via vf0 + vf1.x)
  c->vadd_bc(DEST::x, BC::x, vf23, vf0, vf1);         // vaddx.x vf23, vf0, vf1
  goto block_4;

block_50:
  // B50 / L139: "~v"/"~V" — vertical offset with sign (t2) and digits (t3).
  c->mov128_vf_gpr(vf1, t3);                          // qmtc2.i vf1, t3
  c->daddiu(t1, t2, -45);                             // '-' check
  bc = c->sgpr64(t2) == 0;                            // beq t2, r0, L141 (no sign → absolute)
  c->vitof0(DEST::xyzw, vf1, vf1);                    // vitof0.xyzw vf1, vf1
  if (bc) { goto block_54; }

  // B51:
  bc = c->sgpr64(t1) == 0;                            // beq t1, r0, L140
  if (bc) { goto block_53; }

  // B52: '+' → vf23.y += vf1.x
  c->vadd_bc(DEST::y, BC::x, vf23, vf23, vf1);        // vaddx.y vf23, vf23, vf1
  goto block_4;

block_53:
  // B53 / L140: '-' → vf23.y -= vf1.x
  c->vsub_bc(DEST::y, BC::x, vf23, vf23, vf1);        // vsubx.y vf23, vf23, vf1
  goto block_4;

block_54:
  // B54 / L141: absolute → vf23.y = vf1.x
  c->vadd_bc(DEST::y, BC::x, vf23, vf0, vf1);         // vaddx.y vf23, vf0, vf1
  goto block_4;

block_55:
  // B55 / L142: "~y"/"~Y" — save current cursor to font-work[496]
  c->sqc2(vf23, 496, v1);                             // sqc2 vf23, 496(v1) ; save
  goto block_4;

block_56:
  // B56 / L143: "~z"/"~Z" — restore saved cursor.
  c->lqc2(vf23, 496, v1);                             // lqc2 vf23, 496(v1) ; save
  goto block_4;

block_57:
  // B57 / L144: control char (≤ 3) — flag bit 6 + pick current-font-N-tmpl
  // based on char (1, 2, or 3).
  c->daddiu(t2, t1, -3);                              // t1==3?
  c->ori(a2, a2, 64);                                 // set bit 6 (newline pending)
  bc = c->sgpr64(t2) == 0;                            // beq t2, r0, L146 (t1==3)
  c->daddiu(t1, t1, -2);                              // t1==2?
  if (bc) { goto block_61; }

  // B58:
  bc = c->sgpr64(t1) == 0;                            // beq t1, r0, L145 (t1==2)
  if (bc) { goto block_60; }

  // B59: t1==1 — use current-font-1-tmpl
  c->lqc2(vf20, 6096, v1);                            // lqc2 vf20, 6096(v1)
  goto block_62;

block_60:
  // B60 / L145: t1==2 — use current-font-2-tmpl
  c->lqc2(vf20, 6112, v1);                            // lqc2 vf20, 6112(v1)
  goto block_62;

block_61:
  // B61 / L146: t1==3 — use current-font-3-tmpl
  c->lqc2(vf20, 6128, v1);                            // lqc2 vf20, 6128(v1)
  // fall through

block_62:
  // B62 / L147: common tail after ctrl char — fetch next char, compute
  // glyph cell index = char*16, set vf4 = vf23 + vf15 (cell offset),
  // vf1 = vf25 - vf23 (remaining x), jump to L150.
  c->lbu(t1, 4, t0);                                  // lbu t1, 4(t0)
  c->daddiu(t0, t0, 1);                               // daddiu t0, t0, 1
  c->vadd(DEST::xyz, vf4, vf23, vf15);                // vadd.xyz vf4, vf23, vf15
  c->sll(t2, t1, 4);                                  // t2 = char*16
  c->vsub(DEST::xyzw, vf1, vf25, vf23);               // vsub.xyzw vf1, vf25, vf23
  goto block_66;                                      // branch to L150

block_63:
  // B63 / L148: regular printable fast path. Clear bit 6 (newline pending),
  // compute cell index, check for CR/LF.
  c->sll(t2, t1, 4);                                  // t2 = char*16
  c->addiu(t3, r0, -65);                              // -65 = ~64
  c->vadd(DEST::xyz, vf4, vf23, vf15);                // vadd.xyz vf4, vf23, vf15
  c->and_(a2, a2, t3);                                // clear bit 6 (and ?? — mask -65 clears 64)
  c->vsub(DEST::xyzw, vf1, vf25, vf23);               // vsub.xyzw vf1, vf25, vf23
  c->daddiu(t3, t1, -10);                             // LF?
  bc = c->sgpr64(t3) == 0;                            // beq t3, r0, L149
  c->daddiu(t1, t1, -13);                             // CR?
  if (bc) { goto block_65; }

  // B64:
  bc = c->sgpr64(t1) != 0;                            // bne t1, r0, L150 (neither CR nor LF)
  if (bc) { goto block_66; }

block_65:
  // B65 / L149: CR/LF — advance to next justify row: a3 += 16; vf23 = justify[next]
  c->daddiu(a3, a3, 16);                              // daddiu a3, a3, 16
  c->lqc2(vf23, 640, a3);                             // vf23 = justify[next]
  goto block_4;

block_66:
  // B66 / L150: look up glyph advance vector, check if cursor still within
  // the max-x (vf1.x = vf25.x - vf23.x — sign bit of float says "overflow").
  c->addu(t1, t2, a1);                                // addu t1, t2, a1 (glyph ptr base)
  c->lqc2(vf5, -96, t1);                              // lqc2 vf5, -96(t1) ; glyph st+advance
  c->mov128_gpr_vf(t1, vf1);                          // qmfc2.i t1, vf1
  bc = ((s64)c->sgpr64(t1)) < 0;                      // bltz t1, L159 (hit max-x → bail)
  c->vadd(DEST::xyz, vf8, vf5, vf18);                 // vadd.xyz vf8, vf5, vf18 (outline offset)
  if (bc) { goto block_91; }

  // B67: sra t1, t1, 31 — if vf1.x float had sign bit set, t1 becomes -1.
  // This is a second-pass sign check on the FLOAT bit pattern.
  c->sra(t1, t1, 31);
  bc = ((s64)c->sgpr64(t1)) < 0;                      // bltz t1, L130 (skip this glyph but continue)
  if (bc) { goto block_4; }

  // B68: rendering gate — check if flag bits 0 | 4096 set. If neither,
  // skip the glyph (it still advanced via vf19 computation).
  c->vadd(DEST::xyz, vf1, vf23, vf0);                 // vadd.xyz vf1, vf23, vf0
  c->andi(t1, a2, 4097);                              // flag bits 0 | 4096
  c->vmul(DEST::xyzw, vf19, vf5, vf13);               // vmul.xyzw vf19, vf5, vf13 (glyph advance)
  bc = c->sgpr64(t1) == 0;                            // beq t1, r0, L130
  if (bc) { goto block_4; }

  // B69: full transform — project vf1 (glyph bottom-left) and vf4 (top-right)
  // through calc-mat (vf28..vf31), divide by w, write the char-packet
  // (tmpl @0..16 + color vf20 + shadow vf9 + pos vf2/vf3 + st vf5/vf8).
  c->vmula_bc(DEST::xyzw, BC::w, vf31, vf0);          // vmulaw.xyzw acc, vf31, vf0
  c->vmadda_bc(DEST::xyzw, BC::x, vf28, vf1);         // vmaddax.xyzw acc, vf28, vf1
  c->vmadda_bc(DEST::xyzw, BC::y, vf29, vf1);         // vmadday.xyzw acc, vf29, vf1
  c->vmadd_bc(DEST::xyzw, BC::z, vf1, vf30, vf1);     // vmaddz.xyzw vf1, vf30, vf1

  c->vmula_bc(DEST::xyzw, BC::w, vf31, vf0);
  c->vmadda_bc(DEST::xyzw, BC::x, vf28, vf4);
  c->vmadda_bc(DEST::xyzw, BC::y, vf29, vf4);
  c->vmadd_bc(DEST::xyzw, BC::z, vf4, vf30, vf4);

  c->vdiv(vf25, BC::z, vf1, BC::w);                   // vdiv Q, vf25.z, vf1.w
  c->lq(t2, 0, v1);                                   // tag low qword
  c->lq(t1, 16, v1);                                  // tag high qword
  c->lqc2(vf9, 608, v1);                              // color-shadow
  c->sq(t2, 0, a0);                                   // emit tag @ +0
  c->sq(t1, 16, a0);                                  // emit tag @ +16
  c->sqc2(vf20, 32, a0);                              // emit font-tmpl @ +32
  c->sqc2(vf9, 48, a0);                               // emit shadow color @ +48
  c->vmulq(DEST::xyz, vf1, vf1);                      // vmulq.xyz vf1, vf1 (proj divide)
  c->vmulq(DEST::xyz, vf5, vf5);                      // vmulq.xyz vf5, vf5
  c->vdiv(vf25, BC::z, vf4, BC::w);                   // vdiv Q, vf25.z, vf4.w
  c->andi(t2, a2, 2);                                 // kerning?
  c->vadd(DEST::xyzw, vf2, vf1, vf26);                // vf2 = vf1 + hvdf-shadow
  bc = c->sgpr64(t2) == 0;                            // beq t2, r0, L151 (no kern → fixed)
  c->andi(t2, a2, 64);                                // flag 64 = newline pending
  if (bc) { goto block_72; }

  // B70:
  bc = c->sgpr64(t2) != 0;                            // bne t2, r0, L151
  if (bc) { goto block_72; }

  // B71: kerned advance: vf23.x += vf19.w
  c->vadd_bc(DEST::x, BC::w, vf23, vf23, vf19);       // vaddw.x vf23, vf23, vf19
  goto block_73;

block_72:
  // B72 / L151: fixed advance: vf23.x += vf14.w
  c->vadd_bc(DEST::x, BC::w, vf23, vf23, vf14);       // vaddw.x vf23, vf23, vf14
  // fall through

block_73:
  // B73 / L152: convert positions to gs-format ints, emit remaining fields,
  // do y/x on-screen clip test.
  c->vftoi4(DEST::xyzw, vf2, vf2);                    // vftoi4.xyzw vf2, vf2
  c->sqc2(vf5, 64, a0);                               // st0
  c->vmulq(DEST::xyz, vf4, vf4);                      // vmulq.xyz vf4, vf4
  c->vmulq(DEST::xyz, vf8, vf8);                      // vmulq.xyz vf8, vf8
  c->vadd(DEST::xyzw, vf3, vf4, vf26);                // vf3 = vf4 + hvdf-shadow
  c->sqc2(vf8, 96, a0);                               // st1 (outline)
  c->vftoi4(DEST::xyzw, vf3, vf3);                    // vftoi4.xyzw vf3, vf3
  c->andi(t2, a2, 256);                               // flag 256 = depth-from-vf23 hack
  bc = c->sgpr64(t2) == 0;                            // beq t2, r0, L153
  if (bc) { goto block_75; }

  // B74: depth override — use vf23.z for z slot.
  c->vftoi0(DEST::z, vf2, vf23);                      // vftoi0.z vf2, vf23
  c->vftoi0(DEST::z, vf3, vf23);                      // vftoi0.z vf3, vf23
  // fall through

block_75:
  // B75 / L153: emit pos0 @ +80, pos1 @ +112, then clip check.
  c->sqc2(vf2, 80, a0);                               // pos0
  c->sqc2(vf3, 112, a0);                              // pos1
  c->lw(t3, 80, a0);                                  // pos0.x (int)
  c->lw(t2, 84, a0);                                  // pos0.y (int)
  c->ori(t4, r0, 36864);                              // x min-clip const
  c->dsubu(t3, t3, t4);
  c->lw(t4, 112, a0);                                 // pos1.x
  c->ori(t5, r0, 36096);                              // y min-clip const
  c->dsubu(t2, t2, t5);
  c->lw(t5, 116, a0);                                 // pos1.y
  bc = ((s64)c->sgpr64(t3)) > 0;                      // bgtz t3, L130 (clipped — skip)
  c->daddiu(t3, t4, -28672);
  if (bc) { goto block_4; }

  // B76:
  bc = ((s64)c->sgpr64(t2)) > 0;                      // bgtz t2, L130
  c->daddiu(t2, t5, -29440);
  if (bc) { goto block_4; }

  // B77:
  bc = ((s64)c->sgpr64(t3)) < 0;                      // bltz t3, L130
  if (bc) { goto block_4; }

  // B78:
  bc = ((s64)c->sgpr64(t2)) < 0;                      // bltz t2, L130
  if (bc) { goto block_4; }

  // B79: glyph passed clip. Check flag 1 (draw enabled) → advance dma by 128.
  c->andi(t2, a2, 1);                                 // flag 1
  bc = c->sgpr64(t2) == 0;                            // beq t2, r0, L154
  if (bc) { goto block_81; }

  // B80: advance dma pointer by 128 (one char-packet).
  c->daddiu(a0, a0, 128);                             // daddiu a0, a0, 128

block_81:
  // B81 / L154: effect-draw gate — flag 4096 enables the 5-pass outline/shadow
  // effects (B82..B90). If clear, just loop back.
  c->andi(t2, a2, 4096);
  bc = c->sgpr64(t2) == 0;
  if (bc) { goto block_4; }

  // B82: effect pass 1 — outline layer 1 (vf26 = hvdf-outline1 @ 4784).
  c->lqc2(vf26, 4784, v1);                            // lqc2 vf26, 4784(v1)
  c->lq(t2, 0, v1);                                   // tag low
  c->sq(t1, 16, a0);                                  // tag high (t1 still loaded from B69)
  c->sqc2(vf20, 32, a0);
  c->sqc2(vf9, 48, a0);
  c->sq(t2, 0, a0);
  c->vadd(DEST::xyzw, vf2, vf1, vf26);
  c->vftoi4(DEST::xyzw, vf2, vf2);
  c->sqc2(vf5, 64, a0);
  c->vadd(DEST::xyzw, vf3, vf4, vf26);
  c->sqc2(vf8, 96, a0);
  c->vftoi4(DEST::xyzw, vf3, vf3);
  c->andi(t2, a2, 256);
  bc = c->sgpr64(t2) == 0;
  if (bc) { goto block_84; }

  // B83: depth-override for effect pass 1.
  c->vftoi0(DEST::z, vf2, vf23);
  c->vftoi0(DEST::z, vf3, vf23);

block_84:
  // B84 / L155: emit pass 1 pos, advance dma; start effect pass 2
  // (vf26 = hvdf-outline2 @ 4800).
  c->sqc2(vf2, 80, a0);
  c->sqc2(vf3, 112, a0);
  c->daddiu(a0, a0, 128);
  c->lqc2(vf26, 4800, v1);                            // hvdf-outline2
  c->lq(t2, 0, v1);
  c->sq(t1, 16, a0);
  c->sqc2(vf20, 32, a0);
  c->sqc2(vf9, 48, a0);
  c->sq(t2, 0, a0);
  c->vadd(DEST::xyzw, vf2, vf1, vf26);
  c->vftoi4(DEST::xyzw, vf2, vf2);
  c->sqc2(vf5, 64, a0);
  c->vadd(DEST::xyzw, vf3, vf4, vf26);
  c->sqc2(vf8, 96, a0);
  c->vftoi4(DEST::xyzw, vf3, vf3);
  c->andi(t2, a2, 256);
  bc = c->sgpr64(t2) == 0;
  if (bc) { goto block_86; }

  // B85: depth-override for effect pass 2.
  c->vftoi0(DEST::z, vf2, vf23);
  c->vftoi0(DEST::z, vf3, vf23);

block_86:
  // B86 / L156: emit pass 2 pos, advance dma; start pass 3
  // (vf26 = hvdf-outline3 @ 4816).
  c->sqc2(vf2, 80, a0);
  c->sqc2(vf3, 112, a0);
  c->daddiu(a0, a0, 128);
  c->lqc2(vf26, 4816, v1);                            // hvdf-outline3
  c->lq(t2, 0, v1);
  c->sq(t1, 16, a0);
  c->sqc2(vf20, 32, a0);
  c->sqc2(vf9, 48, a0);
  c->sq(t2, 0, a0);
  c->vadd(DEST::xyzw, vf2, vf1, vf26);
  c->vftoi4(DEST::xyzw, vf2, vf2);
  c->sqc2(vf5, 64, a0);
  c->vadd(DEST::xyzw, vf3, vf4, vf26);
  c->sqc2(vf8, 96, a0);
  c->vftoi4(DEST::xyzw, vf3, vf3);
  c->andi(t2, a2, 256);
  bc = c->sgpr64(t2) == 0;
  if (bc) { goto block_88; }

  // B87: depth-override for effect pass 3.
  c->vftoi0(DEST::z, vf2, vf23);
  c->vftoi0(DEST::z, vf3, vf23);

block_88:
  // B88 / L157: emit pass 3 pos, advance dma; start pass 4
  // (vf26 = hvdf-outline0 @ 4768).
  c->sqc2(vf2, 80, a0);
  c->sqc2(vf3, 112, a0);
  c->daddiu(a0, a0, 128);
  c->lqc2(vf26, 4768, v1);                            // hvdf-outline0
  c->lq(t2, 0, v1);
  c->sq(t1, 16, a0);
  c->sqc2(vf20, 32, a0);
  c->sqc2(vf9, 48, a0);
  c->sq(t2, 0, a0);
  c->vadd(DEST::xyzw, vf2, vf1, vf26);
  c->vftoi4(DEST::xyzw, vf2, vf2);
  c->sqc2(vf5, 64, a0);
  c->vadd(DEST::xyzw, vf3, vf4, vf26);
  c->sqc2(vf8, 96, a0);
  c->vftoi4(DEST::xyzw, vf3, vf3);
  c->andi(t1, a2, 256);
  bc = c->sgpr64(t1) == 0;
  if (bc) { goto block_90; }

  // B89: depth-override for effect pass 4.
  c->vftoi0(DEST::z, vf2, vf23);
  c->vftoi0(DEST::z, vf3, vf23);

block_90:
  // B90 / L158: emit pass 4 pos, restore vf26 to hvdf-shadow (@ 4752),
  // advance dma, loop back.
  c->sqc2(vf2, 80, a0);
  c->sqc2(vf3, 112, a0);
  c->lqc2(vf26, 4752, v1);                            // restore hvdf-shadow
  c->daddiu(a0, a0, 128);
  goto block_4;

block_91:
  // B91 / L159: end of first render loop. Re-initialize state for the
  // second pass: reload flags (a2 = font-context flags @12), reset the
  // justify-row cursor (a3 = font-work), reload str-ptr (t0 from
  // font-work @6176, re-set by draw-string-init-justify), and reset
  // vf23 from justify[0].
  c->lw(a2, 12, gp);                                  // lw a2, 12(gp)  ; flags
  c->mov64(a3, v1);                                   // or a3, v1, r0
  c->lw(t0, 6176, v1);                                // lw t0, 6176(v1) ; str-ptr
  c->lqc2(vf23, 640, a3);                             // lqc2 vf23, 640(a3) ; justify[0]
  // fall through to block_92

block_92:
  // B92 / L160: top of second render loop. Mirrors B4 / L130.
  c->lbu(t1, 4, t0);                                  // lbu t1, 4(t0)
  c->daddiu(t0, t0, 1);                               // daddiu t0, t0, 1
  c->lqc2(vf20, 6080, v1);                            // lqc2 vf20, 6080(v1)
  bc = c->sgpr64(t1) == 0;                            // beq t1, r0, L187
  c->daddiu(t2, t1, -3);                              // daddiu t2, t1, -3
  if (bc) { goto block_171; }

  // B93:
  bc = ((s64)c->sgpr64(t2)) <= 0;                     // blez t2, L177 (ctrl char)
  c->daddiu(t2, t1, -126);                            // daddiu t2, t1, -126 ('~')
  if (bc) { goto block_149; }

  // B94:
  bc = c->sgpr64(t2) != 0;                            // bne t2, r0, L181 (printable)
  if (bc) { goto block_155; }

  // B95: tilde-code begin — read next char.
  c->lbu(t1, 4, t0);                                  // lbu t1, 4(t0)
  c->daddiu(t0, t0, 1);                               // daddiu t0, t0, 1
  c->addiu(t2, r0, 0);                                // addiu t2, r0, 0 ; sign accumulator
  c->addiu(t3, r0, 0);                                // addiu t3, r0, 0 ; digit accumulator
  bc = c->sgpr64(t1) == 0;                            // beq t1, r0, L187
  c->daddiu(t4, t1, -43);                             // '+'
  if (bc) { goto block_171; }

  // B96:
  c->movz(t2, t1, t4);                                // movz t2, t1, t4
  c->daddiu(t4, t1, -45);                             // '-'
  c->movz(t2, t1, t4);                                // movz t2, t1, t4
  bc = c->sgpr64(t2) != 0;                            // bne t2, r0, L161 (saw +/-)
  c->daddiu(t4, t1, -91);                             // '['
  if (bc) { goto block_106; }

  // B97: '[' — push color state (→ L173)
  bc = c->sgpr64(t4) == 0;                            // beq t4, r0, L173
  c->daddiu(t3, t1, -93);                             // ']'
  if (bc) { goto block_145; }

  // B98: ']' — pop color state (→ L174)
  bc = c->sgpr64(t3) == 0;                            // beq t3, r0, L174
  c->daddiu(t3, t1, -121);                            // 'y'
  if (bc) { goto block_146; }

  // B99: 'y' — save cursor (→ L175)
  bc = c->sgpr64(t3) == 0;                            // beq t3, r0, L175
  c->daddiu(t3, t1, -89);                             // 'Y'
  if (bc) { goto block_147; }

  // B100: 'Y' — save cursor (→ L175)
  bc = c->sgpr64(t3) == 0;                            // beq t3, r0, L175
  c->daddiu(t3, t1, -122);                            // 'z'
  if (bc) { goto block_147; }

  // B101: 'z' — restore cursor (→ L176)
  bc = c->sgpr64(t3) == 0;                            // beq t3, r0, L176
  c->daddiu(t3, t1, -90);                             // 'Z'
  if (bc) { goto block_148; }

  // B102: 'Z' — restore cursor (→ L176)
  bc = c->sgpr64(t3) == 0;                            // beq t3, r0, L176
  c->daddiu(t3, t1, -48);                             // '0'
  if (bc) { goto block_148; }

  // B103:
  bc = ((s64)c->sgpr64(t3)) < 0;                      // bltz t3, L181 (< '0' → treat as printable)
  c->daddiu(t3, t1, -57);                             // '9'
  if (bc) { goto block_155; }

  // B104:
  bc = ((s64)c->sgpr64(t3)) > 0;                      // bgtz t3, L181 (> '9')
  c->daddiu(t3, t1, -126);                            // '~'
  if (bc) { goto block_155; }

  // B105:
  bc = c->sgpr64(t3) == 0;                            // beq t3, r0, L181 ('~' again)
  c->daddiu(t3, t1, -48);                             // digit value
  if (bc) { goto block_155; }

block_106:
  // B106 / L161: read another char (code selector or digit continuation).
  // Mirrors B18 / L131 but second-loop branch targets differ:
  //   n/N → L162 (small font)        [same idea as first loop]
  //   l/L → L164 (color-by-name)     [NEW: first loop ignored l/L]
  //   w/W → L160 (ignore, loop top)  [NEW: first loop used w/W as flag toggle]
  //   k/K → L166 (kerning toggle)    [same]
  //   j/J → L160 (ignore)
  //   h/H → L167 (h-offset)
  //   v/V → L170 (v-offset)
  //   u/U → L165 (color-by-index)    [NEW: first loop ignored u/U]
  //   digits → accumulate in t3, loop L161
  //   other → L181 (treat as printable)
  c->lbu(t1, 4, t0);                                  // lbu t1, 4(t0)
  c->daddiu(t0, t0, 1);                               // daddiu t0, t0, 1
  bc = c->sgpr64(t1) == 0;                            // beq t1, r0, L187
  c->daddiu(t4, t1, -110);                            // 'n'
  if (bc) { goto block_171; }

  // B107:
  bc = c->sgpr64(t4) == 0;                            // beq t4, r0, L162 ('n' → small)
  c->daddiu(t4, t1, -78);                             // 'N'
  if (bc) { goto block_126; }

  // B108:
  bc = c->sgpr64(t4) == 0;                            // beq t4, r0, L162
  c->daddiu(t4, t1, -108);                            // 'l'
  if (bc) { goto block_126; }

  // B109:
  bc = c->sgpr64(t4) == 0;                            // beq t4, r0, L164 ('l' → color-by-name)
  c->daddiu(t4, t1, -76);                             // 'L'
  if (bc) { goto block_129; }

  // B110:
  bc = c->sgpr64(t4) == 0;                            // beq t4, r0, L164
  c->daddiu(t4, t1, -119);                            // 'w'
  if (bc) { goto block_129; }

  // B111: 'w' ignored in second loop (→ L160 = loop top)
  bc = c->sgpr64(t4) == 0;                            // beq t4, r0, L160
  c->daddiu(t4, t1, -87);                             // 'W'
  if (bc) { goto block_92; }

  // B112: 'W' ignored
  bc = c->sgpr64(t4) == 0;                            // beq t4, r0, L160
  c->daddiu(t4, t1, -107);                            // 'k'
  if (bc) { goto block_92; }

  // B113: 'k' → L166 (kerning)
  bc = c->sgpr64(t4) == 0;                            // beq t4, r0, L166
  c->daddiu(t4, t1, -75);                             // 'K'
  if (bc) { goto block_133; }

  // B114:
  bc = c->sgpr64(t4) == 0;                            // beq t4, r0, L166
  c->daddiu(t4, t1, -106);                            // 'j'
  if (bc) { goto block_133; }

  // B115: 'j' ignored
  bc = c->sgpr64(t4) == 0;                            // beq t4, r0, L160
  c->daddiu(t4, t1, -74);                             // 'J'
  if (bc) { goto block_92; }

  // B116:
  bc = c->sgpr64(t4) == 0;                            // beq t4, r0, L160
  c->daddiu(t4, t1, -104);                            // 'h'
  if (bc) { goto block_92; }

  // B117: 'h' → L167 (h-offset)
  bc = c->sgpr64(t4) == 0;                            // beq t4, r0, L167
  c->daddiu(t4, t1, -72);                             // 'H'
  if (bc) { goto block_135; }

  // B118:
  bc = c->sgpr64(t4) == 0;                            // beq t4, r0, L167
  c->daddiu(t4, t1, -118);                            // 'v'
  if (bc) { goto block_135; }

  // B119: 'v' → L170 (v-offset)
  bc = c->sgpr64(t4) == 0;                            // beq t4, r0, L170
  c->daddiu(t4, t1, -86);                             // 'V'
  if (bc) { goto block_140; }

  // B120:
  bc = c->sgpr64(t4) == 0;                            // beq t4, r0, L170
  c->daddiu(t4, t1, -117);                            // 'u'
  if (bc) { goto block_140; }

  // B121: 'u' → L165 (color-by-index)
  bc = c->sgpr64(t4) == 0;                            // beq t4, r0, L165
  c->daddiu(t4, t1, -85);                             // 'U'
  if (bc) { goto block_131; }

  // B122: 'U' → L165 (color-by-index)
  bc = c->sgpr64(t4) == 0;                            // beq t4, r0, L165
  c->daddiu(t4, t1, -48);                             // '0'
  if (bc) { goto block_131; }

  // B123:
  bc = ((s64)c->sgpr64(t4)) < 0;                      // bltz t4, L181 (< '0' → printable)
  c->daddiu(t5, t1, -57);                             // '9'
  if (bc) { goto block_155; }

  // B124:
  bc = ((s64)c->sgpr64(t5)) > 0;                      // bgtz t5, L181
  c->sll(t5, t3, 2);                                  // sll t5, t3, 2
  if (bc) { goto block_155; }

  // B125: digit accumulator: t3 = (t3 * 10) + (char - '0')
  c->daddu(t1, t3, t5);                               // t3 + t3*4 = 5*t3
  c->sll(t1, t1, 1);                                  // *2 → *10
  c->daddu(t3, t1, t4);                               // + digit
  goto block_106;                                     // loop back to L161

block_126:
  // B126 / L162: "~n"/"~N" — small-font switch in second loop.
  // If t3 (digit count) != 0 → large-font branch (L163).
  bc = c->sgpr64(t3) != 0;                            // bne t3, r0, L163
  c->addiu(t1, r0, -33);                              // -33 = ~32 (clear 'large')
  if (bc) { goto block_128; }

  // B127: install small-font templates/table/sizes, clear 'large' flag.
  c->lq(a1, 192, v1);                                 // small-font-0-tmpl
  c->lq(t2, 208, v1);
  c->lq(t3, 224, v1);
  c->lq(t4, 240, v1);
  c->sq(a1, 6080, v1);
  c->sq(t2, 6096, v1);
  c->sq(t3, 6112, v1);
  c->sq(t4, 6128, v1);
  c->load_symbol2(a1, cache.font12_table);
  c->mov64(a1, a1);
  c->lqc2(vf13, 320, v1);
  c->lqc2(vf14, 336, v1);
  c->lqc2(vf15, 352, v1);
  c->and_(a2, a2, t1);                                // clear bit 5 (large)
  goto block_92;                                      // L160

block_128:
  // B128 / L163: large-font switch.
  c->lq(a1, 256, v1);
  c->lq(t1, 272, v1);
  c->lq(t2, 288, v1);
  c->lq(t3, 304, v1);
  c->sq(a1, 6080, v1);
  c->sq(t1, 6096, v1);
  c->sq(t2, 6112, v1);
  c->sq(t3, 6128, v1);
  c->load_symbol2(a1, cache.font24_table);
  c->mov64(a1, a1);
  c->lqc2(vf13, 368, v1);
  c->lqc2(vf14, 384, v1);
  c->lqc2(vf15, 400, v1);
  c->ori(a2, a2, 32);                                 // set bit 5 (large)
  goto block_92;

block_129:
  // B129 / L164: color-by-name ("~l<digits>" / "~L<digits>"). Writes
  // last-color = t3 (digit), then if flag bit 128 is set, bails back
  // to loop top without applying the color. Otherwise falls into B130
  // to compute color-table[t3] and store into current-color.
  c->andi(t1, a2, 128);                               // flag 128 (color-lock?)
  c->sll(t2, t3, 4);                                  // t2 = t3 * 16 (color-table stride)
  bc = c->sgpr64(t1) != 0;                            // bne t1, r0, L160 (locked — skip)
  c->sb(t3, 6168, v1);                                // last-color = t3 (unconditional delay slot)
  if (bc) { goto block_92; }

  // B130: compute color-table[t3] at offset 4896 + t3*16, expand via
  // pextlb/pextlh from byte to vector4w, store to current-color (@544),
  // and write the alpha float bits from font-context @8 into the w slot.
  c->daddu(t1, t2, v1);                               // t1 = &font-work + t3*16
  c->lwu(t1, 4896, t1);                               // load first 4 bytes of color
  c->pextlb(t2, r0, t1);                              // bytes → halfs
  c->lwu(t1, 8, gp);                                  // alpha bits from font-context @8
  c->pextlh(t2, r0, t2);                              // halfs → words
  c->sq(t2, 544, v1);                                 // current-color
  c->sw(t1, 556, v1);                                 // current-color.w (alpha)
  goto block_92;

block_131:
  // B131 / L165: color-by-index ("~u<digits>" / "~U<digits>"). t3 is
  // already the color value (raw bytes from the digit accumulator) —
  // no table indirection. Bails on flag 128.
  c->andi(t1, a2, 128);
  bc = c->sgpr64(t1) != 0;                            // bne t1, r0, L160
  if (bc) { goto block_92; }

  // B132: pextlb/pextlh on t3 directly.
  c->pextlb(t2, r0, t3);                              // bytes → halfs
  c->lw(t1, 8, gp);                                   // alpha bits
  c->pextlh(t2, r0, t2);                              // halfs → words
  c->sq(t2, 544, v1);                                 // current-color
  c->sw(t1, 556, v1);                                 // alpha
  goto block_92;

block_133:
  // B133 / L166: "~k"/"~K" — kerning toggle (identical to B43/L135).
  c->addiu(t1, r0, -3);                               // -3 = ~2
  bc = c->sgpr64(t3) == 0;                            // beq t3, r0, L160
  c->and_(a2, a2, t1);                                // clear bit 1
  if (bc) { goto block_92; }

  // B134:
  c->ori(a2, a2, 2);                                  // set bit 1
  goto block_92;

block_135:
  // B135 / L167: "~h"/"~H" — horizontal offset (identical to B45/L136).
  c->mov128_vf_gpr(vf1, t3);                          // qmtc2.i vf1, t3
  c->daddiu(t1, t2, -45);                             // '-'
  bc = c->sgpr64(t2) == 0;                            // beq t2, r0, L169
  c->vitof0(DEST::xyzw, vf1, vf1);
  if (bc) { goto block_139; }

  // B136:
  bc = c->sgpr64(t1) == 0;                            // beq t1, r0, L168
  if (bc) { goto block_138; }

  // B137: '+' → vf23.x += vf1.x
  c->vadd_bc(DEST::x, BC::x, vf23, vf23, vf1);
  goto block_92;

block_138:
  // B138 / L168: '-' → vf23.x -= vf1.x
  c->vsub_bc(DEST::x, BC::x, vf23, vf23, vf1);
  goto block_92;

block_139:
  // B139 / L169: absolute → vf23.x = vf1.x
  c->vadd_bc(DEST::x, BC::x, vf23, vf0, vf1);
  goto block_92;

block_140:
  // B140 / L170: "~v"/"~V" — vertical offset (identical to B50/L139).
  c->mov128_vf_gpr(vf1, t3);
  c->daddiu(t1, t2, -45);
  bc = c->sgpr64(t2) == 0;                            // beq t2, r0, L172
  c->vitof0(DEST::xyzw, vf1, vf1);
  if (bc) { goto block_144; }

  // B141:
  bc = c->sgpr64(t1) == 0;                            // beq t1, r0, L171
  if (bc) { goto block_143; }

  // B142: '+' → vf23.y += vf1.x
  c->vadd_bc(DEST::y, BC::x, vf23, vf23, vf1);
  goto block_92;

block_143:
  // B143 / L171: '-' → vf23.y -= vf1.x
  c->vsub_bc(DEST::y, BC::x, vf23, vf23, vf1);
  goto block_92;

block_144:
  // B144 / L172: absolute → vf23.y = vf1.x
  c->vadd_bc(DEST::y, BC::x, vf23, vf0, vf1);
  goto block_92;

block_145:
  // B145 / L173: '[' — push color state.
  //   save-last-color (@6169) = last-color (@6168)
  //   save-color (@512) = current-color (@544)
  c->lb(t1, 6168, v1);
  c->lqc2(vf9, 544, v1);
  c->sb(t1, 6169, v1);
  c->sqc2(vf9, 512, v1);
  goto block_92;

block_146:
  // B146 / L174: ']' — pop color state.
  //   last-color (@6168) = save-last-color (@6169)
  //   current-color (@544) = save-color (@512)
  c->lb(t1, 6169, v1);
  c->lqc2(vf9, 512, v1);
  c->sb(t1, 6168, v1);
  c->sqc2(vf9, 544, v1);
  goto block_92;

block_147:
  // B147 / L175: 'y'/'Y' — save cursor + color state.
  //   save-last-color ← last-color
  //   save-color ← current-color
  //   save (@496) ← vf23
  c->lb(t1, 6168, v1);
  c->lqc2(vf9, 544, v1);
  c->sb(t1, 6169, v1);
  c->sqc2(vf9, 512, v1);
  c->sqc2(vf23, 496, v1);                             // save cursor
  goto block_92;

block_148:
  // B148 / L176: 'z'/'Z' — restore cursor + color state.
  //   last-color ← save-last-color
  //   current-color ← save-color
  //   vf23 ← save (@496)
  c->lb(t1, 6169, v1);
  c->lqc2(vf9, 512, v1);
  c->sb(t1, 6168, v1);
  c->sqc2(vf9, 544, v1);
  c->lqc2(vf23, 496, v1);                             // restore cursor
  goto block_92;

block_149:
  // B149 / L177: control char (≤3). Mirrors B57/L144 but second loop
  // branches into the L183 common render tail instead of L147.
  c->daddiu(t2, t1, -3);                              // t1==3?
  c->ori(a2, a2, 64);                                 // set bit 6 (newline pending)
  bc = c->sgpr64(t2) == 0;                            // beq t2, r0, L179 (t1==3)
  c->daddiu(t1, t1, -2);                              // t1==2?
  if (bc) { goto block_153; }

  // B150:
  bc = c->sgpr64(t1) == 0;                            // beq t1, r0, L178 (t1==2)
  if (bc) { goto block_152; }

  // B151: t1==1 — current-font-1-tmpl
  c->lqc2(vf20, 6096, v1);
  goto block_154;                                     // L180

block_152:
  // B152 / L178: t1==2 — current-font-2-tmpl
  c->lqc2(vf20, 6112, v1);
  goto block_154;

block_153:
  // B153 / L179: t1==3 — current-font-3-tmpl
  c->lqc2(vf20, 6128, v1);
  // fall through

block_154:
  // B154 / L180: common tail — fetch next char, compute cell index,
  // vf4 = vf23 + vf15, vf1 = vf25 - vf23, jump to L183 (render path).
  c->lbu(t1, 4, t0);
  c->daddiu(t0, t0, 1);
  c->vadd(DEST::xyz, vf4, vf23, vf15);
  c->sll(t2, t1, 4);
  c->vsub(DEST::xyzw, vf1, vf25, vf23);
  goto block_158;                                     // L183 (second-loop render tail — TODO)

block_155:
  // B155 / L181: regular printable fast path. Mirrors B63/L148 but
  // branches to L182 (CR/LF) / L183 (render) — both in the second loop.
  c->addiu(t2, r0, -65);                              // -65 = ~64
  c->and_(a2, a2, t2);                                // clear bit 6
  c->vadd(DEST::xyz, vf4, vf23, vf15);
  c->sll(t2, t1, 4);                                  // cell index
  c->vsub(DEST::xyzw, vf1, vf25, vf23);
  c->daddiu(t3, t1, -10);                             // LF?
  bc = c->sgpr64(t3) == 0;                            // beq t3, r0, L182
  c->daddiu(t1, t1, -13);                             // CR?
  if (bc) { goto block_157; }

  // B156:
  bc = c->sgpr64(t1) != 0;                            // bne t1, r0, L183 (neither)
  if (bc) { goto block_158; }

block_157:
  // B157 / L182: CR/LF — advance justify cursor, reload vf23.
  c->daddiu(a3, a3, 16);
  c->lqc2(vf23, 640, a3);
  goto block_92;                                      // L160

block_158:
  // B158 / L183: second-loop glyph lookup + max-x bailout. Mirrors
  // B66/L150 but the render tail that follows differs (see B160).
  c->addu(t1, t2, a1);                                // glyph ptr base
  c->lqc2(vf5, -96, t1);                              // glyph st+advance
  c->mov128_gpr_vf(t1, vf1);                          // qmfc2.i t1, vf1
  bc = ((s64)c->sgpr64(t1)) < 0;                      // bltz t1, L187 (overflow)
  if (bc) { goto block_171; }

  // B159: second sign check (on float pattern).
  c->sra(t1, t1, 31);
  bc = ((s64)c->sgpr64(t1)) < 0;                      // bltz t1, L160 (skip glyph but continue)
  c->vadd(DEST::xyz, vf8, vf5, vf18);                 // vf8 = vf5 + vf18 (outline st)
  if (bc) { goto block_92; }

  // B160: full transform + char-packet emit. Differences from first
  // loop's B69:
  //   - No rendering gate (flag 4097) — the second pass always draws.
  //   - vf9 = current-color (@544) not color-shadow (@608).
  //   - Offset vector is hvdf-offset (vf27) not hvdf-shadow (vf26) — so
  //     the "primary" pass goes through vf27 here while the first loop
  //     used vf26.
  //   - Position regs are vf1/vf4 (reused) instead of vf2/vf3.
  c->vadd(DEST::xyz, vf1, vf23, vf0);                 // vadd.xyz vf1, vf23, vf0
  c->vadd(DEST::xyz, vf4, vf23, vf15);                // vadd.xyz vf4, vf23, vf15
  c->vmul(DEST::xyzw, vf19, vf5, vf13);               // vmul.xyzw vf19, vf5, vf13

  c->vmula_bc(DEST::xyzw, BC::w, vf31, vf0);
  c->vmadda_bc(DEST::xyzw, BC::x, vf28, vf1);
  c->vmadda_bc(DEST::xyzw, BC::y, vf29, vf1);
  c->vmadd_bc(DEST::xyzw, BC::z, vf1, vf30, vf1);

  c->vmula_bc(DEST::xyzw, BC::w, vf31, vf0);
  c->vmadda_bc(DEST::xyzw, BC::x, vf28, vf4);
  c->vmadda_bc(DEST::xyzw, BC::y, vf29, vf4);
  c->vmadd_bc(DEST::xyzw, BC::z, vf4, vf30, vf4);

  c->vdiv(vf25, BC::z, vf1, BC::w);                   // vdiv Q, vf25.z, vf1.w
  c->lq(t1, 0, v1);                                   // tag low
  c->lq(t2, 16, v1);                                  // tag high
  c->lqc2(vf9, 544, v1);                              // vf9 = current-color (second loop!)
  c->sq(t1, 0, a0);
  c->sq(t2, 16, a0);
  c->sqc2(vf20, 32, a0);                              // font-tmpl
  c->sqc2(vf9, 48, a0);                               // current-color
  c->vmulq(DEST::xyz, vf1, vf1);                      // project divide
  c->vmulq(DEST::xyz, vf5, vf5);
  c->vdiv(vf25, BC::z, vf4, BC::w);                   // vdiv Q, vf25.z, vf4.w
  c->andi(t1, a2, 2);                                 // kerning?
  c->vadd(DEST::xyzw, vf1, vf1, vf27);                // vf1 += hvdf-offset (NOT shadow)
  bc = c->sgpr64(t1) == 0;                            // beq t1, r0, L184 (no kern)
  c->andi(t1, a2, 64);                                // flag 64 newline pending
  if (bc) { goto block_163; }

  // B161:
  bc = c->sgpr64(t1) != 0;                            // bne t1, r0, L184
  if (bc) { goto block_163; }

  // B162: kerned advance
  c->vadd_bc(DEST::x, BC::w, vf23, vf23, vf19);
  goto block_164;

block_163:
  // B163 / L184: fixed advance.
  c->vadd_bc(DEST::x, BC::w, vf23, vf23, vf14);
  // fall through

block_164:
  // B164 / L185: convert position regs to ints, emit remaining fields.
  c->vftoi4(DEST::xyzw, vf1, vf1);                    // vftoi4.xyzw vf1, vf1
  c->sqc2(vf5, 64, a0);                               // st0
  c->vmulq(DEST::xyz, vf4, vf4);
  c->vmulq(DEST::xyz, vf8, vf8);
  c->vadd(DEST::xyzw, vf4, vf4, vf27);                // vf4 += hvdf-offset
  c->sqc2(vf8, 96, a0);                               // st1 (outline)
  c->vftoi4(DEST::xyzw, vf4, vf4);
  c->andi(t1, a2, 256);                               // depth-override flag
  bc = c->sgpr64(t1) == 0;                            // beq t1, r0, L186
  if (bc) { goto block_166; }

  // B165: depth-override — use vf23.z.
  c->vftoi0(DEST::z, vf1, vf23);
  c->vftoi0(DEST::z, vf4, vf23);
  // fall through

block_166:
  // B166 / L186: emit pos0/pos1 and do on-screen clip test.
  c->sqc2(vf1, 80, a0);                               // pos0
  c->sqc2(vf4, 112, a0);                              // pos1
  c->lw(t2, 80, a0);                                  // pos0.x
  c->lw(t1, 84, a0);                                  // pos0.y
  c->ori(t3, r0, 36864);
  c->dsubu(t2, t2, t3);
  c->lw(t3, 112, a0);                                 // pos1.x
  c->ori(t4, r0, 36096);
  c->dsubu(t1, t1, t4);
  c->lw(t4, 116, a0);                                 // pos1.y
  bc = ((s64)c->sgpr64(t2)) > 0;                      // bgtz t2, L160 (clip → skip)
  c->daddiu(t2, t3, -28672);
  if (bc) { goto block_92; }

  // B167:
  bc = ((s64)c->sgpr64(t1)) > 0;                      // bgtz t1, L160
  c->daddiu(t1, t4, -29440);
  if (bc) { goto block_92; }

  // B168:
  bc = ((s64)c->sgpr64(t2)) < 0;                      // bltz t2, L160
  if (bc) { goto block_92; }

  // B169:
  bc = ((s64)c->sgpr64(t1)) < 0;                      // bltz t1, L160
  if (bc) { goto block_92; }

  // B170: glyph passed clip — unconditionally advance dma by 128 (no
  // flag-1 gate in the second loop — every glyph that makes it here
  // draws), then loop back.
  c->daddiu(a0, a0, 128);
  goto block_92;                                      // L160

block_171:
  // ---------------------------------------------------------------------------
  // B171 / L187 epilogue: write dma ptr back, compute return u128.
  // ---------------------------------------------------------------------------
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

// =============================================================================
// draw-string-init-justify
// =============================================================================
//
// Direct port of jakx font_ir2.asm L285 (`draw-string-init-justify`),
// lines 12466-12978 (blocks B0-B78).
//
// This is the justify pre-pass. It walks the input string once and for
// each line-break writes the starting-x position of the next line into
// font-work.justify[N] (@640 + N*16). The later render pass reads these
// entries so multi-line strings are positioned correctly relative to
// the font-context's origin and its left/center/right justify flags.
//
// Args:
//   a0 = string
//   a1 = dma-buffer (only used for writing *font-work*.buf @6172)
//   a2 = font-context
// Returns:
//   v0 = qmfc2 of vf23 after final vsub — packed u128 whose low 32 bits
//        are the last-line width as a float. The caller (draw-string-
//        asm-packed) discards v0, so this is mostly a formality.
//
// Unlike draw-string-asm-packed, this function has total stack = 0 —
// no saved regs, no sp adjustment beyond the delay-slot daddu sp,sp,r0.
// It also has no '[...]' bracket logic; those are only in the render
// pass.
//
// Register roster in the main loop (B4 onward):
//   a0 = str-ptr (advances per char)
//   a1 = flags (from font-context @12)
//   a2 = fontN-table base (small or large)
//   a3 = justify cursor (= font-work; advances by 16 per line written)
//   v1 = *font-work*
//   vf13/14/15 = size1/2/3 for selected font
//   vf23 = running cursor x (in font-context origin coords)
//   vf24 = origin (font-context @44)
//   vf25 = strip-gif vector (font-context @156, jakx layout)
//   vf16 = size-st1 (for center-justify math)
//
// Flag bits referenced:
//   1  — (nothing in this function; draw-enable in the render pass)
//   2  — kerning
//   4  — right-justify ("~j" / "~J")
//   16 — center-justify
//   32 — large font
//   64 — "newline pending" (set on ctrl chars)

namespace draw_string_init_justify {
struct Cache {
  void* font_work;    // *font-work*
  void* font12_table; // *font12-table*
  void* font24_table; // *font24-table*
} cache;

u64 execute(void* ctxt) {
  auto* c = (ExecutionContext*)ctxt;
  bool bc = false;

  // ---------------------------------------------------------------------------
  // B0 / L285: prologue. Same vf/register setup as draw-string-asm-packed's
  // B0, minus the jalr to init-justify (this IS init-justify).
  // ---------------------------------------------------------------------------
  c->load_symbol2(v1, cache.font_work);               // lw v1, *font-work*(s7)
  c->mov64(v1, v1);                                   // or v1, v1, r0
  c->sw(a1, 6172, v1);                                // sw a1, 6172(v1)  ; buf
  c->lw(a1, 4, a1);                                   // lw a1, 4(a1)     ; dma write ptr (unused here)
  c->sw(a0, 6176, v1);                                // sw a0, 6176(v1)  ; str-ptr

  c->lqc2(vf28, 76, a2);                              // calc-mat row 0
  c->lqc2(vf29, 92, a2);                              // calc-mat row 1
  c->lqc2(vf30, 108, a2);                             // calc-mat row 2
  c->lqc2(vf31, 124, a2);                             // calc-mat row 3
  c->lqc2(vf16, 416, v1);                             // size-st1
  c->lqc2(vf17, 432, v1);                             // size-st2
  c->lqc2(vf18, 448, v1);                             // size-st3
  c->lqc2(vf27, 4736, v1);                            // hvdf-offset
  c->lqc2(vf26, 4752, v1);                            // hvdf-shadow
  c->lqc2(vf25, 156, a2);                             // strip-gif (jakx @156)
  c->lqc2(vf23, 44, a2);                              // origin
  c->lqc2(vf24, 44, a2);                              // origin
  c->lqc2(vf1,  44, a2);                              // origin
  c->lqc2(vf2,  44, a2);                              // origin
  c->vadd_bc(DEST::x, BC::x, vf1, vf0, vf0);          // zero vf1.x
  c->vadd_bc(DEST::x, BC::x, vf2, vf0, vf0);          // zero vf2.x
  c->vadd(DEST::x, vf1, vf0, vf25);                   // vf1.x = vf25.x
  c->vmul_bc(DEST::x, BC::w, vf2, vf25, vf16);        // vf2.x = vf25.x * vf16.w
  c->sqc2(vf1, 464, v1);                              // origin-right
  c->sqc2(vf2, 480, v1);                              // origin-center

  c->lw(a1, 12, a2);                                  // a1 = flags (jakx @12)
  c->vmove(DEST::xyzw, vf1, vf0);
  c->vmove(DEST::xyzw, vf2, vf0);
  c->vmove(DEST::xyzw, vf3, vf0);
  c->vmove(DEST::xyzw, vf4, vf0);

  c->andi(a2, a1, 32);                                // flag 32 = large font?
  bc = c->sgpr64(a2) != 0;                            // bne a2, r0, L286
  c->load_symbol2(a2, cache.font12_table);
  if (bc) { goto block_2; }

  // B1: small-font setup.
  c->mov64(a2, a2);
  c->lq(a3, 192, v1);                                 // small-font-0-tmpl
  c->lq(t0, 208, v1);
  c->lq(t1, 224, v1);
  c->lq(t2, 240, v1);
  c->sq(a3, 6080, v1);                                // current-font-0-tmpl
  c->sq(t0, 6096, v1);
  c->sq(t1, 6112, v1);
  c->sq(t2, 6128, v1);
  c->lqc2(vf13, 320, v1);                             // size1-small
  c->lqc2(vf14, 336, v1);                             // size2-small
  c->lqc2(vf15, 352, v1);                             // size3-small
  goto block_3;

block_2:
  // B2 / L286: large-font setup.
  c->load_symbol2(a2, cache.font24_table);
  c->mov64(a2, a2);
  c->lq(a3, 256, v1);                                 // large-font-0-tmpl
  c->lq(t0, 272, v1);
  c->lq(t1, 288, v1);
  c->lq(t2, 304, v1);
  c->sq(a3, 6080, v1);
  c->sq(t0, 6096, v1);
  c->sq(t1, 6112, v1);
  c->sq(t2, 6128, v1);
  c->lqc2(vf13, 368, v1);
  c->lqc2(vf14, 384, v1);
  c->lqc2(vf15, 400, v1);

block_3:
  // B3 / L287: initialize justify cursor a3 = font-work.
  c->mov64(a3, v1);

block_4:
  // B4 / L288: top of scanner loop.
  c->lbu(t0, 4, a0);                                  // lbu t0, 4(a0)
  c->daddiu(a0, a0, 1);                               // daddiu a0, a0, 1
  c->lqc2(vf20, 6080, v1);                            // lqc2 vf20, 6080(v1) (seeded; unused in this fn)
  bc = c->sgpr64(t0) == 0;                            // beq t0, r0, L311 (end of string)
  c->daddiu(t1, t0, -3);                              // daddiu t1, t0, -3
  if (bc) { goto block_73; }

  // B5:
  bc = ((s64)c->sgpr64(t1)) <= 0;                     // blez t1, L303 (ctrl char)
  c->daddiu(t1, t0, -126);                            // daddiu t1, t0, -126 ('~')
  if (bc) { goto block_59; }

  // B6:
  bc = c->sgpr64(t1) != 0;                            // bne t1, r0, L304 (printable)
  if (bc) { goto block_60; }

  // B7: tilde-code begin — read next char.
  c->lbu(t0, 4, a0);                                  // lbu t0, 4(a0)
  c->daddiu(a0, a0, 1);                               // daddiu a0, a0, 1
  c->addiu(t1, r0, 0);                                // t1 = sign accumulator
  c->addiu(t2, r0, 0);                                // t2 = digit accumulator
  bc = c->sgpr64(t0) == 0;                            // beq t0, r0, L311
  c->daddiu(t3, t0, -43);                             // '+'
  if (bc) { goto block_73; }

  // B8:
  c->movz(t1, t0, t3);                                // movz t1, t0, t3
  c->daddiu(t3, t0, -45);                             // '-'
  c->movz(t1, t0, t3);                                // movz t1, t0, t3
  bc = c->sgpr64(t1) != 0;                            // bne t1, r0, L289
  c->daddiu(t3, t0, -91);                             // '['
  if (bc) { goto block_18; }

  // B9: '[' — ignored in init-justify (→ L288 loop top)
  bc = c->sgpr64(t3) == 0;                            // beq t3, r0, L288
  c->daddiu(t2, t0, -93);                             // ']'
  if (bc) { goto block_4; }

  // B10: ']' — ignored
  bc = c->sgpr64(t2) == 0;                            // beq t2, r0, L288
  c->daddiu(t2, t0, -121);                            // 'y'
  if (bc) { goto block_4; }

  // B11: 'y' → L301 (save cursor)
  bc = c->sgpr64(t2) == 0;                            // beq t2, r0, L301
  c->daddiu(t2, t0, -89);                             // 'Y'
  if (bc) { goto block_57; }

  // B12:
  bc = c->sgpr64(t2) == 0;                            // beq t2, r0, L301
  c->daddiu(t2, t0, -122);                            // 'z'
  if (bc) { goto block_57; }

  // B13: 'z' → L302 (restore cursor)
  bc = c->sgpr64(t2) == 0;                            // beq t2, r0, L302
  c->daddiu(t2, t0, -90);                             // 'Z'
  if (bc) { goto block_58; }

  // B14:
  bc = c->sgpr64(t2) == 0;                            // beq t2, r0, L302
  c->daddiu(t2, t0, -48);                             // '0'
  if (bc) { goto block_58; }

  // B15:
  bc = ((s64)c->sgpr64(t2)) < 0;                      // bltz t2, L304 (non-digit → printable)
  c->daddiu(t2, t0, -57);                             // '9'
  if (bc) { goto block_60; }

  // B16:
  bc = ((s64)c->sgpr64(t2)) > 0;                      // bgtz t2, L304
  c->daddiu(t2, t0, -126);                            // '~'
  if (bc) { goto block_60; }

  // B17:
  bc = c->sgpr64(t2) == 0;                            // beq t2, r0, L304 ('~' again)
  c->daddiu(t2, t0, -48);                             // digit value
  if (bc) { goto block_60; }

block_18:
  // B18 / L289: tilde letter scanner.
  c->lbu(t0, 4, a0);                                  // lbu t0, 4(a0)
  c->daddiu(a0, a0, 1);                               // daddiu a0, a0, 1
  bc = c->sgpr64(t0) == 0;                            // beq t0, r0, L311
  c->daddiu(t3, t0, -110);                            // 'n'
  if (bc) { goto block_73; }

  // B19:
  bc = c->sgpr64(t3) == 0;                            // beq t3, r0, L290 (small)
  c->daddiu(t3, t0, -78);                             // 'N'
  if (bc) { goto block_38; }

  // B20:
  bc = c->sgpr64(t3) == 0;                            // beq t3, r0, L290
  c->daddiu(t3, t0, -108);                            // 'l'
  if (bc) { goto block_38; }

  // B21: 'l' ignored (→ L288)
  bc = c->sgpr64(t3) == 0;                            // beq t3, r0, L288
  c->daddiu(t3, t0, -76);                             // 'L'
  if (bc) { goto block_4; }

  // B22: 'L' ignored
  bc = c->sgpr64(t3) == 0;                            // beq t3, r0, L288
  c->daddiu(t3, t0, -119);                            // 'w'
  if (bc) { goto block_4; }

  // B23: 'w' ignored (unlike draw-string-asm-packed which had L134 handler)
  bc = c->sgpr64(t3) == 0;                            // beq t3, r0, L288
  c->daddiu(t3, t0, -87);                             // 'W'
  if (bc) { goto block_4; }

  // B24: 'W' ignored
  bc = c->sgpr64(t3) == 0;                            // beq t3, r0, L288
  c->daddiu(t3, t0, -107);                            // 'k'
  if (bc) { goto block_4; }

  // B25: 'k' → L292 (kerning toggle)
  bc = c->sgpr64(t3) == 0;                            // beq t3, r0, L292
  c->daddiu(t3, t0, -75);                             // 'K'
  if (bc) { goto block_41; }

  // B26:
  bc = c->sgpr64(t3) == 0;                            // beq t3, r0, L292
  c->daddiu(t3, t0, -106);                            // 'j'
  if (bc) { goto block_41; }

  // B27: 'j' → L293 (right-justify flag toggle)
  bc = c->sgpr64(t3) == 0;                            // beq t3, r0, L293
  c->daddiu(t3, t0, -74);                             // 'J'
  if (bc) { goto block_43; }

  // B28:
  bc = c->sgpr64(t3) == 0;                            // beq t3, r0, L293
  c->daddiu(t3, t0, -104);                            // 'h'
  if (bc) { goto block_43; }

  // B29: 'h' → L295 (h-offset)
  bc = c->sgpr64(t3) == 0;                            // beq t3, r0, L295
  c->daddiu(t3, t0, -72);                             // 'H'
  if (bc) { goto block_47; }

  // B30:
  bc = c->sgpr64(t3) == 0;                            // beq t3, r0, L295
  c->daddiu(t3, t0, -118);                            // 'v'
  if (bc) { goto block_47; }

  // B31: 'v' → L298 (v-offset)
  bc = c->sgpr64(t3) == 0;                            // beq t3, r0, L298
  c->daddiu(t3, t0, -86);                             // 'V'
  if (bc) { goto block_52; }

  // B32:
  bc = c->sgpr64(t3) == 0;                            // beq t3, r0, L298
  c->daddiu(t3, t0, -117);                            // 'u'
  if (bc) { goto block_52; }

  // B33: 'u' ignored in init-justify
  bc = c->sgpr64(t3) == 0;                            // beq t3, r0, L288
  c->daddiu(t3, t0, -85);                             // 'U'
  if (bc) { goto block_4; }

  // B34:
  bc = c->sgpr64(t3) == 0;                            // beq t3, r0, L288
  c->daddiu(t3, t0, -48);                             // '0'
  if (bc) { goto block_4; }

  // B35:
  bc = ((s64)c->sgpr64(t3)) < 0;                      // bltz t3, L304 (< '0' → printable)
  c->daddiu(t4, t0, -57);                             // '9'
  if (bc) { goto block_60; }

  // B36:
  bc = ((s64)c->sgpr64(t4)) > 0;                      // bgtz t4, L304
  c->sll(t4, t2, 2);
  if (bc) { goto block_60; }

  // B37: digit accumulator: t2 = t2 * 10 + digit (where digit = char - '0')
  c->daddu(t0, t2, t4);                               // t0 = t2 + t2*4 = 5*t2
  c->sll(t0, t0, 1);                                  // *2 → *10
  c->daddu(t2, t0, t3);                               // + (char - '0')
  goto block_18;

block_38:
  // B38 / L290: "~n"/"~N" — small-font switch. If digits nonzero → large.
  bc = c->sgpr64(t2) != 0;                            // bne t2, r0, L291
  c->addiu(t0, r0, -33);                              // -33 = ~32 (clear 'large')
  if (bc) { goto block_40; }

  // B39: install small-font state, clear 'large' flag.
  c->load_symbol2(a2, cache.font12_table);
  c->mov64(a2, a2);
  c->lqc2(vf13, 320, v1);
  c->lqc2(vf14, 336, v1);
  c->lqc2(vf15, 352, v1);
  c->and_(a1, a1, t0);                                // clear bit 5
  goto block_4;

block_40:
  // B40 / L291: large-font switch.
  c->load_symbol2(a2, cache.font24_table);
  c->mov64(a2, a2);
  c->lqc2(vf13, 368, v1);
  c->lqc2(vf14, 384, v1);
  c->lqc2(vf15, 400, v1);
  c->ori(a1, a1, 32);                                 // set bit 5
  goto block_4;

block_41:
  // B41 / L292: "~k"/"~K" — kerning toggle (flag bit 1).
  c->addiu(t0, r0, -3);                               // -3 = ~2
  bc = c->sgpr64(t2) == 0;                            // beq t2, r0, L288
  c->and_(a1, a1, t0);                                // clear bit 1
  if (bc) { goto block_4; }

  // B42:
  c->ori(a1, a1, 2);                                  // set bit 1
  goto block_4;

block_43:
  // B43 / L293: "~j"/"~J" — justify mode toggle.
  // If digits == 0: clear flag bits 16 AND 4 (clear both center and right).
  // If digits == 2: set bit 4 (right-justify).
  // Else:          set bit 16 (center-justify).
  c->addiu(t0, r0, -21);                              // -21 = ~(16|4) = ~20
  c->daddiu(t1, t2, -2);                              // digits == 2?
  bc = c->sgpr64(t2) == 0;                            // beq t2, r0, L288
  c->and_(a1, a1, t0);                                // clear bits 16+4 (delay slot)
  if (bc) { goto block_4; }

  // B44:
  bc = c->sgpr64(t1) == 0;                            // beq t1, r0, L294
  if (bc) { goto block_46; }

  // B45: digits != 0 and != 2 → center-justify (bit 16)
  c->ori(a1, a1, 16);
  goto block_4;

block_46:
  // B46 / L294: digits == 2 → right-justify (bit 4)
  c->ori(a1, a1, 4);
  goto block_4;

block_47:
  // B47 / L295: "~h"/"~H" — horizontal offset (qmtc2 digits → vitof0 → +/-/=).
  c->mov128_vf_gpr(vf1, t2);                          // qmtc2.i vf1, t2
  c->daddiu(t0, t1, -45);                             // '-' check
  bc = c->sgpr64(t1) == 0;                            // beq t1, r0, L297 (absolute)
  c->vitof0(DEST::xyzw, vf1, vf1);
  if (bc) { goto block_51; }

  // B48:
  bc = c->sgpr64(t0) == 0;                            // beq t0, r0, L296 ('-')
  if (bc) { goto block_50; }

  // B49: '+' → vf23.x += vf1.x
  c->vadd_bc(DEST::x, BC::x, vf23, vf23, vf1);
  goto block_4;

block_50:
  // B50 / L296: '-' → vf23.x -= vf1.x
  c->vsub_bc(DEST::x, BC::x, vf23, vf23, vf1);
  goto block_4;

block_51:
  // B51 / L297: absolute → vf23.x = vf1.x
  c->vadd_bc(DEST::x, BC::x, vf23, vf0, vf1);
  goto block_4;

block_52:
  // B52 / L298: "~v"/"~V" — vertical offset.
  c->mov128_vf_gpr(vf1, t2);
  c->daddiu(t0, t1, -45);
  bc = c->sgpr64(t1) == 0;                            // beq t1, r0, L300 (absolute)
  c->vitof0(DEST::xyzw, vf1, vf1);
  if (bc) { goto block_56; }

  // B53:
  bc = c->sgpr64(t0) == 0;                            // beq t0, r0, L299 ('-')
  if (bc) { goto block_55; }

  // B54: '+' → vf23.y += vf1.x
  c->vadd_bc(DEST::y, BC::x, vf23, vf23, vf1);
  goto block_4;

block_55:
  // B55 / L299: '-' → vf23.y -= vf1.x
  c->vsub_bc(DEST::y, BC::x, vf23, vf23, vf1);
  goto block_4;

block_56:
  // B56 / L300: absolute → vf23.y = vf1.x
  c->vadd_bc(DEST::y, BC::x, vf23, vf0, vf1);
  goto block_4;

block_57:
  // B57 / L301: '~y'/'~Y' — save cursor.
  c->sqc2(vf23, 496, v1);
  goto block_4;

block_58:
  // B58 / L302: '~z'/'~Z' — restore cursor.
  c->lqc2(vf23, 496, v1);
  goto block_4;

block_59:
  // B59 / L303: control char (≤ 3). Set newline-pending (bit 6), fetch
  // next char, compute cell index, fall into L308 via the common
  // advance path. Also computes vf1 = vf25 - vf23 in the delay slot
  // so L308 can test for overflow.
  c->ori(a1, a1, 64);                                 // set bit 6
  c->lbu(t0, 4, a0);
  c->daddiu(a0, a0, 1);
  c->sll(t1, t0, 4);                                  // cell index
  c->vsub(DEST::xyzw, vf1, vf25, vf23);
  goto block_67;                                      // L308

block_60:
  // B60 / L304: regular printable. Clear newline-pending (bit 6), check CR/LF.
  c->addiu(t1, r0, -65);                              // -65 = ~64
  c->and_(a1, a1, t1);                                // clear bit 6
  c->sll(t1, t0, 4);                                  // cell index
  c->vsub(DEST::xyzw, vf1, vf25, vf23);
  c->daddiu(t2, t0, -10);                             // LF?
  bc = c->sgpr64(t2) == 0;                            // beq t2, r0, L305
  c->daddiu(t0, t0, -13);                             // CR?
  if (bc) { goto block_62; }

  // B61:
  bc = c->sgpr64(t0) != 0;                            // bne t0, r0, L308 (regular glyph)
  if (bc) { goto block_67; }

block_62:
  // B62 / L305: CR or LF — end of line. Compute vf1 = vf23 - vf24
  // (line width from origin). Pick left/center/right by flags 16 / 4
  // and write the next line's starting-x to justify[a3].
  c->vsub(DEST::xyzw, vf1, vf23, vf24);
  c->andi(t0, a1, 16);                                // center flag
  bc = c->sgpr64(t0) != 0;                            // bne t0, r0, L306
  c->andi(t0, a1, 4);                                 // right flag (delay slot)
  if (bc) { goto block_65; }

  // B63:
  bc = c->sgpr64(t0) != 0;                            // bne t0, r0, L307
  if (bc) { goto block_66; }

  // B64: left-justify — next line starts at origin; advance justify cursor.
  //    vf23 = vf0 + vf24  (reset to origin x)
  //    justify[a3] = vf23 (before the vaddw below — BEWARE delay slot:
  //                       the sqc2 is the NON-delay instruction that
  //                       stores the reset vf23; the vaddw adjusts
  //                       vf23.y AFTER the store)
  c->vadd_bc(DEST::x, BC::x, vf23, vf0, vf24);        // vaddx.x vf23, vf0, vf24
  c->sqc2(vf23, 640, a3);                             // store justify[next]
  c->vadd_bc(DEST::y, BC::w, vf23, vf23, vf15);       // advance y by size3.w
  c->daddiu(a3, a3, 16);                              // bump cursor
  goto block_4;

block_65:
  // B65 / L306: center-justify — start this line at origin-right - line-width.
  //    vf2 = origin-right (@464)
  //    vf23.x = vf2.x - vf1.x
  //    justify[a3] = vf23
  //    then reset for the NEXT line.
  c->lqc2(vf2, 464, v1);                              // origin-right
  c->vsub(DEST::x, vf23, vf2, vf1);
  c->sqc2(vf23, 640, a3);                             // store current line's start
  c->vadd_bc(DEST::x, BC::x, vf23, vf0, vf24);        // reset cursor
  c->vadd_bc(DEST::y, BC::w, vf23, vf23, vf15);       // advance y
  c->daddiu(a3, a3, 16);
  goto block_4;

block_66:
  // B66 / L307: right-justify — same structure but uses origin-center (@480)
  // and scales vf1.x by vf16.w first.
  c->lqc2(vf2, 480, v1);                              // origin-center
  c->vmul_bc(DEST::x, BC::w, vf1, vf1, vf16);         // vf1.x *= vf16.w
  c->vsub(DEST::x, vf23, vf2, vf1);
  c->sqc2(vf23, 640, a3);
  c->vadd_bc(DEST::x, BC::x, vf23, vf0, vf24);
  c->vadd_bc(DEST::y, BC::w, vf23, vf23, vf15);
  c->daddiu(a3, a3, 16);
  goto block_4;

block_67:
  // B67 / L308: glyph advance. Load glyph vector (st+advance) and check
  // for max-x overflow.
  c->addu(t0, t1, a2);                                // t0 = &fontN-table + char*16
  c->lqc2(vf5, -96, t0);                              // glyph st+advance
  c->mov128_gpr_vf(t0, vf1);                          // qmfc2.i t0, vf1
  bc = ((s64)c->sgpr64(t0)) < 0;                      // bltz t0, L311 (end-of-line clamp)
  c->sra(t0, t0, 31);                                 // (delay slot; not read here)
  if (bc) { goto block_73; }

  // B68: compute kerned advance (vf19 = vf5 * vf13).
  c->vmul(DEST::xyzw, vf19, vf5, vf13);
  c->andi(t0, a1, 2);                                 // kerning?
  bc = c->sgpr64(t0) == 0;                            // beq t0, r0, L309
  c->andi(t0, a1, 64);                                // newline-pending?
  if (bc) { goto block_71; }

  // B69:
  bc = c->sgpr64(t0) != 0;                            // bne t0, r0, L309
  if (bc) { goto block_71; }

  // B70: kerned advance: vf23.x += vf19.w
  c->vadd_bc(DEST::x, BC::w, vf23, vf23, vf19);
  goto block_72;

block_71:
  // B71 / L309: fixed advance: vf23.x += vf14.w
  c->vadd_bc(DEST::x, BC::w, vf23, vf23, vf14);

block_72:
  // B72 / L310: fall-through back to loop.
  goto block_4;

block_73:
  // B73 / L311: end of string. Handle the last line's justify (same
  // 3-way split: left writes vf23 as-is (after reset to origin x);
  // center uses origin-right - line-width; right uses origin-center -
  // line-width*vf16.w).
  c->vsub(DEST::xyzw, vf1, vf23, vf24);               // vf1 = line width
  c->andi(a0, a1, 16);                                // center?
  bc = c->sgpr64(a0) != 0;                            // bne a0, r0, L312
  c->andi(a0, a1, 4);                                 // right?
  if (bc) { goto block_76; }

  // B74:
  bc = c->sgpr64(a0) != 0;                            // bne a0, r0, L313
  if (bc) { goto block_77; }

  // B75: left-justify last line — store origin x.
  c->vadd_bc(DEST::x, BC::x, vf23, vf0, vf24);        // reset vf23.x to origin x
  c->sqc2(vf23, 640, a3);                             // store
  goto block_78;

block_76:
  // B76 / L312: center-justify last line.
  c->lqc2(vf2, 464, v1);                              // origin-right
  c->vsub(DEST::x, vf23, vf2, vf1);
  c->sqc2(vf23, 640, a3);
  goto block_78;

block_77:
  // B77 / L313: right-justify last line.
  c->lqc2(vf2, 480, v1);                              // origin-center
  c->vmul_bc(DEST::x, BC::w, vf1, vf1, vf16);
  c->vsub(DEST::x, vf23, vf2, vf1);
  c->sqc2(vf23, 640, a3);

block_78:
  // B78 / L314: compute return value (vf23 - vf24) and return.
  c->vsub(DEST::xyzw, vf23, vf23, vf24);
  c->mov128_gpr_vf(v0, vf23);
  // jr ra / daddu sp, sp, r0 — no stack to restore (frame size 0).
  goto end_of_function;

end_of_function:
  return c->gprs[v0].du64[0];
}

void link() {
  cache.font_work = intern_from_c(-1, 0, "*font-work*").c();
  cache.font12_table = intern_from_c(-1, 0, "*font12-table*").c();
  cache.font24_table = intern_from_c(-1, 0, "*font24-table*").c();
  gLinkedFunctionTable.reg("draw-string-init-justify", execute, 1024);
}

} // namespace draw_string_init_justify
} // namespace Mips2C::jakx
