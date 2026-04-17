//--------------------------MIPS2C---------------------
// clang-format off
//
// JakX-native mips2c ports of font asm routines.
//
// Currently implements:
//   - get-string-length-asm
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
} // namespace Mips2C::jakx
