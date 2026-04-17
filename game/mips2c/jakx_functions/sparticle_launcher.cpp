
//--------------------------MIPS2C---------------------
// clang-format off
#include "game/mips2c/mips2c_private.h"
#include "game/kernel/jakx/kscheme.h"
using ::jakx::intern_from_c;
namespace Mips2C::jakx {
// sparticle-motion-blur — jakx-native port.
//
// Diverges from jak3 at the camera-lookup prologue: jak3 loads
// *math-camera* directly (single camera), whereas jakx (split-screen
// racing) calls `view-get-active-math-camera` to get the active
// per-viewport camera. The rest of the routine is structurally
// identical to jak3's (same VU math, same clip/Q pipeline, same fall-
// through to L68/L69).
//
// Source: .jakx_watch/decomp_out/jakx/sparticle-launcher_ir2.asm:7968-8131
// Compare: game/mips2c/jak3_functions/sparticle_launcher.cpp:1373-1559
namespace sparticle_motion_blur {
struct Cache {
  void* view_get_active_math_camera;  // view-get-active-math-camera
  void* atan;                         // atan
} cache;

u64 execute(void* ctxt) {
  auto* c = (ExecutionContext*)ctxt;
  bool bc = false;
  u32 call_addr = 0;
  bool cop1_bc = false;
  uint32_t Clipping = 0;
  c->daddiu(sp, sp, -80);                           // daddiu sp, sp, -80
  c->sd(ra, 0, sp);                                 // sd ra, 0(sp)
  c->sq(s3, 16, sp);                                // sq s3, 16(sp)
  c->sq(s4, 32, sp);                                // sq s4, 32(sp)
  c->sq(s5, 48, sp);                                // sq s5, 48(sp)
  c->sq(gp, 64, sp);                                // sq gp, 64(sp)
  c->mov64(s3, a1);                                 // or s3, a1, r0
  c->mov64(gp, a2);                                 // or gp, a2, r0
  c->ori(s5, r0, 65535);                            // ori s5, r0, 65535
  // JakX-specific: call view-get-active-math-camera() instead of
  // loading *math-camera* symbol directly (split-screen support).
  c->load_symbol2(t9, cache.view_get_active_math_camera);  // lw t9, view-get-active-math-camera(s7)
  call_addr = c->gprs[t9].du32[0];
  c->sll(v0, ra, 0);
  c->jalr(call_addr);                               // jalr ra, t9
  c->mov64(v1, v0);                                 // or v1, v0, r0

  c->dsll32(a1, s5, 16);                            // dsll32 a1, s5, 16
  c->lq(a0, 16, s3);                                // lq a0, 16(s3)
  c->lqc2(vf1, 0, gp);                              // lqc2 vf1, 0(gp)
  c->pceqw(a2, a0, r0);                             // pceqw a2, a0, r0
  c->lqc2(vf24, 572, v1);                           // lqc2 vf24, 572(v1)
  c->ppach(a2, r0, a2);                             // ppach a2, r0, a2
  c->lqc2(vf25, 588, v1);                           // lqc2 vf25, 588(v1)
  c->or_(a1, a2, a1);                               // or a1, a2, a1
  c->lqc2(vf26, 604, v1);                           // lqc2 vf26, 604(v1)
  c->daddiu(a1, a1, 1);                             // daddiu a1, a1, 1
  c->lqc2(vf27, 620, v1);                           // lqc2 vf27, 620(v1)
  bc = c->sgpr64(a1) == 0;                          // beq a1, r0, L68
  c->mov128_vf_gpr(vf4, a0);                        // qmtc2.i vf4, a0
  if (bc) {goto block_5;}                           // branch non-likely

  c->lui(a0, 16896);                                // lui a0, 16896
  c->lqc2(vf30, 812, v1);                           // lqc2 vf30, 812(v1)
  c->lqc2(vf29, 780, v1);                           // lqc2 vf29, 780(v1)
  c->vmula_bc(DEST::xyzw, BC::x, vf24, vf1);        // vmulax.xyzw acc, vf24, vf1
  c->vmadda_bc(DEST::xyzw, BC::y, vf25, vf1);       // vmadday.xyzw acc, vf25, vf1
  c->vmadda_bc(DEST::xyzw, BC::z, vf26, vf1);       // vmaddaz.xyzw acc, vf26, vf1
  c->vmadd_bc(DEST::xyzw, BC::w, vf10, vf27, vf0);  // vmaddw.xyzw vf10, vf27, vf0
  c->mov128_vf_gpr(vf5, a0);                        // qmtc2.i vf5, a0
  c->vmul(DEST::xyzw, vf12, vf10, vf29);            // vmul.xyzw vf12, vf10, vf29
  c->vmula_bc(DEST::xyzw, BC::w, vf1, vf0);         // vmulaw.xyzw acc, vf1, vf0
  c->vmadd_bc(DEST::xyzw, BC::x, vf1, vf4, vf5);    // vmaddx.xyzw vf1, vf4, vf5
  c->vdiv(vf0, BC::w, vf12, BC::w);                 // vdiv Q, vf0.w, vf12.w
  Clipping = c->clip(vf12, vf12, Clipping);         // vclip.xyz vf12, vf12
  c->vmula_bc(DEST::xyzw, BC::x, vf24, vf1);        // vmulax.xyzw acc, vf24, vf1
  c->vmadda_bc(DEST::xyzw, BC::y, vf25, vf1);       // vmadday.xyzw acc, vf25, vf1
  c->vmadda_bc(DEST::xyzw, BC::z, vf26, vf1);       // vmaddaz.xyzw acc, vf26, vf1
  c->vmadd_bc(DEST::xyzw, BC::w, vf11, vf27, vf0);  // vmaddw.xyzw vf11, vf27, vf0
  c->vwaitq();                                      // vwaitq
  c->gprs[v1].du64[0] = Clipping;                   // cfc2.i v1, Clipping
  c->vmulq(DEST::xyz, vf10, vf10);                  // vmulq.xyz vf10, vf10, Q
  c->vmul(DEST::xyzw, vf13, vf11, vf29);            // vmul.xyzw vf13, vf11, vf29
  c->andi(v1, v1, 63);                              // andi v1, v1, 63
  bc = c->sgpr64(v1) != 0;                          // bne v1, r0, L68
  c->vadd(DEST::xyzw, vf10, vf10, vf30);            // vadd.xyzw vf10, vf10, vf30
  if (bc) {goto block_5;}                           // branch non-likely

  c->vdiv(vf0, BC::w, vf13, BC::w);                 // vdiv Q, vf0.w, vf13.w
  Clipping = c->clip(vf13, vf13, Clipping);         // vclip.xyz vf13, vf13
  c->vmax_bc(DEST::w, BC::x, vf10, vf10, vf0);      // vmaxx.w vf10, vf10, vf0
  c->vftoi4(DEST::xyzw, vf2, vf10);                 // vftoi4.xyzw vf2, vf10
  c->vwaitq();                                      // vwaitq
  c->vmulq(DEST::xyz, vf11, vf11);                  // vmulq.xyz vf11, vf11, Q
  c->gprs[v1].du64[0] = Clipping;                   // cfc2.i v1, Clipping
  c->vitof0(DEST::xyzw, vf6, vf2);                  // vitof0.xyzw vf6, vf2
  c->vadd(DEST::xyzw, vf11, vf11, vf30);            // vadd.xyzw vf11, vf11, vf30
  c->andi(v1, v1, 63);                              // andi v1, v1, 63
  bc = c->sgpr64(v1) != 0;                          // bne v1, r0, L68
  c->vdiv(vf0, BC::w, vf6, BC::z);                  // vdiv Q, vf0.w, vf6.z
  if (bc) {goto block_5;}                           // branch non-likely

  c->vmax_bc(DEST::w, BC::x, vf11, vf11, vf0);      // vmaxx.w vf11, vf11, vf0
  c->vadd_bc(DEST::x, BC::w, vf9, vf0, vf0);        // vaddw.x vf9, vf0, vf0
  c->vftoi4(DEST::xyzw, vf3, vf11);                 // vftoi4.xyzw vf3, vf11
  c->vitof0(DEST::xyzw, vf7, vf3);                  // vitof0.xyzw vf7, vf3
  c->vsub(DEST::xy, vf8, vf7, vf6);                 // vsub.xy vf8, vf7, vf6
  c->mov128_gpr_vf(s4, vf8);                        // qmfc2.i s4, vf8
  c->dsra32(s5, s4, 0);                             // dsra32 s5, s4, 0
  c->vmulq(DEST::x, vf9, vf9);                      // vmulq.x vf9, vf9, Q
  c->load_symbol2(t9, cache.atan);                  // lw t9, atan(s7)
  c->mov64(a0, s4);                                 // or a0, s4, r0
  c->mov64(a1, s5);                                 // or a1, s5, r0
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mov64(a0, v0);                                 // or a0, v0, r0
  c->lw(v1, 12, s3);                                // lw v1, 12(s3)
  c->lui(a1, -14720);                               // lui a1, -14720
  c->mtc1(f0, a1);                                  // mtc1 f0, a1
  c->mtc1(f1, a0);                                  // mtc1 f1, a0
  c->adds(f0, f0, f1);                              // add.s f0, f0, f1
  c->swc1(f0, 24, gp);                              // swc1 f0, 24(gp)
  bc = c->sgpr64(v1) == 0;                          // beq v1, r0, L69
  c->mov128_gpr_vf(a0, vf9);                        // qmfc2.i a0, vf9
  if (bc) {goto block_7;}                           // branch non-likely

  c->mtc1(f2, a0);                                  // mtc1 f2, a0
  c->lui(a0, 16256);                                // lui a0, 16256
  c->mtc1(f1, r0);                                  // mtc1 f1, r0
  c->lui(a1, 13702);                                // lui a1, 13702
  c->ori(a1, a1, 14269);                            // ori a1, a1, 14269
  c->lui(a2, 13337);                                // lui a2, 13337
  c->ori(a2, a2, 25670);                            // ori a2, a2, 25670
  c->mtc1(f0, a0);                                  // mtc1 f0, a0
  c->mtc1(f3, a1);                                  // mtc1 f3, a1
  c->mtc1(f4, a2);                                  // mtc1 f4, a2
  c->subs(f2, f2, f3);                              // sub.s f2, f2, f3
  c->subs(f3, f4, f3);                              // sub.s f3, f4, f3
  c->divs(f2, f2, f3);                              // div.s f2, f2, f3
  c->mtc1(f3, s4);                                  // mtc1 f3, s4
  c->mtc1(f4, s5);                                  // mtc1 f4, s5
  // Unknown instr: mula.s f3, f3
  // Unknown instr: madd.s f3, f4, f4
  {
    float f3 = c->fprs[3];
    float f4 = c->fprs[4];
    c->fprs[3] = (f3 * f3) + (f4 * f4);
  }
  c->maxs(f2, f2, f1);                              // max.s f2, f2, f1
  c->sqrts(f1, f3);                                 // sqrt.s f1, f3
  c->mins(f2, f2, f0);                              // min.s f2, f2, f0
  c->lui(a0, 16448);                                // lui a0, 16448
  c->subs(f0, f0, f2);                              // sub.s f0, f0, f2
  c->lui(a1, 16000);                                // lui a1, 16000
  c->mtc1(f3, a0);                                  // mtc1 f3, a0
  c->mtc1(f5, a1);                                  // mtc1 f5, a1
  c->mtc1(f4, v1);                                  // mtc1 f4, v1
  // Unknown instr: mula.s f0, f3
  // Unknown instr: madd.s f0, f2, f5
  {
    float f0 = c->fprs[0];
    float f2 = c->fprs[2];
    float f3 = c->fprs[3];
    float f5 = c->fprs[5];
    c->fprs[0] = (f0 * f3) + (f2 * f5);
  }
  c->muls(f0, f0, f1);                              // mul.s f0, f0, f1
  c->muls(f0, f0, f4);                              // mul.s f0, f0, f4
  //beq r0, r0, L69                                 // beq r0, r0, L69
  c->swc1(f0, 12, gp);                              // swc1 f0, 12(gp)
  goto block_7;                                     // branch always


block_5:
  c->lwc1(f0, 12, s3);                              // lwc1 f0, 12(s3)
  c->mtc1(f1, r0);                                  // mtc1 f1, r0
  cop1_bc = c->fprs[f0] == c->fprs[f1];             // c.eq.s f0, f1
  bc = cop1_bc;                                     // bc1t L69
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_7;}                           // branch non-likely

  c->mtc1(f0, r0);                                  // mtc1 f0, r0
  c->swc1(f0, 12, gp);                              // swc1 f0, 12(gp)
  c->mfc1(v1, f0);                                  // mfc1 v1, f0

block_7:
  c->gprs[v0].du64[0] = 0;                          // or v0, r0, r0
  c->ld(ra, 0, sp);                                 // ld ra, 0(sp)
  c->lq(gp, 64, sp);                                // lq gp, 64(sp)
  c->lq(s5, 48, sp);                                // lq s5, 48(sp)
  c->lq(s4, 32, sp);                                // lq s4, 32(sp)
  c->lq(s3, 16, sp);                                // lq s3, 16(sp)
  //jr ra                                           // jr ra
  c->daddiu(sp, sp, 80);                            // daddiu sp, sp, 80
  goto end_of_function;                             // return

end_of_function:
  return c->gprs[v0].du64[0];
}

void link() {
  cache.view_get_active_math_camera =
      intern_from_c(-1, 0, "view-get-active-math-camera").c();
  cache.atan = intern_from_c(-1, 0, "atan").c();
  gLinkedFunctionTable.reg("sparticle-motion-blur", execute, 128);
}

}  // namespace sparticle_motion_blur
}  // namespace Mips2C::jakx

namespace Mips2C::jakx {
// particle-adgif — jakx-native port.
//
// Structurally identical to jak3's particle-adgif (same 102 ops, same
// labels L357-L361, same Cache layout). Present in jakx namespace for
// consistency with other jakx mips2c ports and to isolate from jak3's
// copy should binary divergence surface later.
//
// Source: .jakx_watch/decomp_out/jakx/sparticle-launcher_ir2.asm:19804-19918
// Compare: game/mips2c/jak3_functions/sparticle_launcher.cpp:439-570
namespace particle_adgif {
struct Cache {
  void* particle_adgif_cache;  // *particle-adgif-cache*
  void* particle_setup_adgif;  // particle-setup-adgif
} cache;

u64 execute(void* ctxt) {
  auto* c = (ExecutionContext*)ctxt;
  bool bc = false;
  u32 call_addr = 0;
  c->dsra(a3, a1, 20);                              // dsra a3, a1, 20
  c->load_symbol2(t1, cache.particle_adgif_cache);  // lw t1, *particle-adgif-cache*(s7)
  c->dsra(t0, a1, 8);                               // dsra t0, a1, 8
  c->lw(t2, 0, t1);                                 // lw t2, 0(t1)
  c->xor_(a3, a3, t0);                              // xor a3, a3, t0
  c->lhu(v1, 4, t1);                                // lhu v1, 4(t1)
  c->andi(a3, a3, 65535);                           // andi a3, a3, 65535
  c->lw(t4, 8, t1);                                 // lw t4, 8(t1)
  bc = c->sgpr64(v1) == c->sgpr64(a3);              // beq v1, a3, L360
  c->daddiu(t3, t1, 12);                            // daddiu t3, t1, 12
  if (bc) {goto block_7;}

  bc = c->sgpr64(t2) == 0;                          // beq t2, r0, L359
  c->daddiu(t4, t1, 172);                           // daddiu t4, t1, 172
  if (bc) {goto block_4;}


block_2:
  c->lhu(v1, 0, t3);                                // lhu v1, 0(t3)
  c->daddiu(t3, t3, 2);                             // daddiu t3, t3, 2
  bc = c->sgpr64(v1) == c->sgpr64(a3);              // beq v1, a3, L360
  c->daddiu(t2, t2, -1);                            // daddiu t2, t2, -1
  if (bc) {goto block_7;}

  bc = c->sgpr64(t2) != 0;                          // bne t2, r0, L358
  c->daddiu(t4, t4, 80);                            // daddiu t4, t4, 80
  if (bc) {goto block_2;}


block_4:
  c->daddiu(sp, sp, -16);                           // daddiu sp, sp, -16
  c->lw(v1, 0, t1);                                 // lw v1, 0(t1)
  c->daddiu(v1, v1, -80);                           // daddiu v1, v1, -80
  c->sw(a0, 0, sp);                                 // sw a0, 0(sp)
  bc = c->sgpr64(v1) == 0;                          // beq v1, r0, L361
  c->daddiu(v1, v1, 81);                            // daddiu v1, v1, 81
  if (bc) {goto block_8;}

  c->sh(a3, 0, t3);                                 // sh a3, 0(t3)
  c->sw(t4, 4, sp);                                 // sw t4, 4(sp)
  c->mov64(a0, t4);                                 // or a0, t4, r0
  c->load_symbol2(t9, cache.particle_setup_adgif);  // lw t9, particle-setup-adgif(s7)
  c->sw(ra, 8, sp);                                 // sw ra, 8(sp)
  call_addr = c->gprs[t9].du32[0];
  c->sw(v1, 0, t1);                                 // sw v1, 0(t1)
  c->jalr(call_addr);                               // jalr ra, t9
  c->lw(v1, 8, t4);                                 // lw v1, 8(t4)
  c->lw(a0, 0, sp);                                 // lw a0, 0(sp)
  c->lw(t4, 4, sp);                                 // lw t4, 4(sp)
  c->andi(v1, v1, 1024);                            // andi v1, v1, 1024
  c->lw(ra, 8, sp);                                 // lw ra, 8(sp)
  c->daddiu(sp, sp, 16);                            // daddiu sp, sp, 16
  bc = c->sgpr64(v1) == 0;                          // beq v1, r0, L360
  c->lw(v1, 0, t1);                                 // lw v1, 0(t1)
  if (bc) {goto block_7;}

  c->daddiu(v1, v1, -1);                            // daddiu v1, v1, -1
  c->sw(v1, 0, t1);                                 // sw v1, 0(t1)

block_7:
  c->lqc2(vf16, 0, t4);                             // lqc2 vf16, 0(t4)
  c->lqc2(vf17, 16, t4);                            // lqc2 vf17, 16(t4)
  c->lqc2(vf18, 32, t4);                            // lqc2 vf18, 32(t4)
  c->lqc2(vf19, 48, t4);                            // lqc2 vf19, 48(t4)
  c->lqc2(vf20, 64, t4);                            // lqc2 vf20, 64(t4)
  c->sqc2(vf16, 0, a0);                             // sqc2 vf16, 0(a0)
  c->sqc2(vf17, 16, a0);                            // sqc2 vf17, 16(a0)
  c->sqc2(vf18, 32, a0);                            // sqc2 vf18, 32(a0)
  c->sqc2(vf19, 48, a0);                            // sqc2 vf19, 48(a0)
  c->sqc2(vf20, 64, a0);                            // sqc2 vf20, 64(a0)
  c->sw(t4, 8, t1);                                 // sw t4, 8(t1)
  c->sh(a3, 4, t1);                                 // sh a3, 4(t1)
  goto end_of_function;


block_8:
  c->sw(t4, 4, sp);                                 // sw t4, 4(sp)
  c->load_symbol2(t9, cache.particle_setup_adgif);  // lw t9, particle-setup-adgif(s7)
  c->sw(ra, 8, sp);                                 // sw ra, 8(sp)
  call_addr = c->gprs[t9].du32[0];
  c->jalr(call_addr);                               // jalr ra, t9
  c->lw(t4, 4, sp);                                 // lw t4, 4(sp)
  c->lw(ra, 8, sp);                                 // lw ra, 8(sp)
  c->daddiu(sp, sp, 16);                            // daddiu sp, sp, 16
  goto end_of_function;

end_of_function:
  return c->gprs[v0].du64[0];
}

void link() {
  cache.particle_adgif_cache = intern_from_c(-1, 0, "*particle-adgif-cache*").c();
  cache.particle_setup_adgif = intern_from_c(-1, 0, "particle-setup-adgif").c();
  gLinkedFunctionTable.reg("particle-adgif", execute, 128);
}

}  // namespace particle_adgif
}  // namespace Mips2C::jakx
