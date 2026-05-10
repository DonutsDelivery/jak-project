//--------------------------MIPS2C---------------------
// clang-format off
#include "game/mips2c/mips2c_private.h"
#include "game/kernel/jakx/kscheme.h"
using ::jakx::intern_from_c;
namespace Mips2C::jakx {
namespace method_115_wcar_base {
struct Cache {
  void* atan; // atan
  void* quaternion; // quaternion*!
  void* quaternion_axis_angle; // quaternion-axis-angle!
  void* quaternion_normalize; // quaternion-normalize!
  void* quaternion_set; // quaternion-set!
} cache;

u64 execute(void* ctxt) {
  auto* c = (ExecutionContext*)ctxt;
  bool bc = false;
  u32 call_addr = 0;
  c->daddiu(sp, sp, -416);                          // daddiu sp, sp, -416
  c->sd(ra, 0, sp);                                 // sd ra, 0(sp)
  c->sd(fp, 8, sp);                                 // sd fp, 8(sp)
  c->mov64(fp, t9);                                 // or fp, t9, r0
  c->sq(s3, 336, sp);                               // sq s3, 336(sp)
  c->sq(s4, 352, sp);                               // sq s4, 352(sp)
  c->sq(s5, 368, sp);                               // sq s5, 368(sp)
  c->sq(gp, 384, sp);                               // sq gp, 384(sp)
  c->swc1(f30, 400, sp);                            // swc1 f30, 400(sp)
  c->mov64(gp, a0);                                 // or gp, a0, r0
  c->daddiu(s5, sp, 16);                            // daddiu s5, sp, 16
  c->daddiu(v1, s5, 32);                            // daddiu v1, s5, 32
  c->lui(a0, 17544);                                // lui a0, 17544
  c->ori(a0, a0, 34953);                            // ori a0, a0, 34953
  c->mtc1(f0, a0);                                  // mtc1 f0, a0
  c->swc1(f0, 0, v1);                               // swc1 f0, 0(v1)
  c->lui(a0, 17544);                                // lui a0, 17544
  c->ori(a0, a0, 34953);                            // ori a0, a0, 34953
  c->mtc1(f0, a0);                                  // mtc1 f0, a0
  c->swc1(f0, 4, v1);                               // swc1 f0, 4(v1)
  c->mtc1(f0, r0);                                  // mtc1 f0, r0
  c->swc1(f0, 8, v1);                               // swc1 f0, 8(v1)
  c->mtc1(f0, r0);                                  // mtc1 f0, r0
  c->swc1(f0, 12, v1);                              // swc1 f0, 12(v1)
  c->addiu(s4, r0, 0);                              // addiu s4, r0, 0
  //beq r0, r0, L3                                  // beq r0, r0, L3
  // nop                                            // sll r0, r0, 0
  goto block_2;                                     // branch always


block_1:
  c->addiu(v1, r0, 288);                            // addiu v1, r0, 288
  c->mult3(v1, v1, s4);                             // mult3 v1, v1, s4
  c->daddiu(v1, v1, 2476);                          // daddiu v1, v1, 2476
  c->daddu(s3, v1, gp);                             // daddu s3, v1, gp
  c->lwu(v1, 0, s3);                                // lwu v1, 0(s3)
  c->load_symbol2(t9, cache.quaternion_set);        // lw t9, quaternion-set!(s7)
  c->daddu(a0, r0, s5);                             // daddu a0, r0, s5
  c->addiu(a1, r0, 0);                              // addiu a1, r0, 0
  c->addiu(a2, r0, 0);                              // addiu a2, r0, 0
  c->lwc1(f0, 248, s3);                             // lwc1 f0, 248(s3)
  c->lwc1(f1, 204, s3);                             // lwc1 f1, 204(s3)
  c->muls(f0, f0, f1);                              // mul.s f0, f0, f1
  c->mfc1(a3, f0);                                  // mfc1 a3, f0
  c->lui(v1, 16256);                                // lui v1, 16256
  c->mtc1(f0, v1);                                  // mtc1 f0, v1
  c->lwc1(f1, 252, s3);                             // lwc1 f1, 252(s3)
  c->adds(f0, f0, f1);                              // add.s f0, f0, f1
  c->mfc1(t0, f0);                                  // mfc1 t0, f0
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->load_symbol2(t9, cache.quaternion_normalize);  // lw t9, quaternion-normalize!(s7)
  c->daddu(a0, r0, s5);                             // daddu a0, r0, s5
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->load_symbol2(t9, cache.quaternion_axis_angle); // lw t9, quaternion-axis-angle!(s7)
  c->daddiu(a0, s5, 16);                            // daddiu a0, s5, 16
  c->addiu(a1, r0, 0);                              // addiu a1, r0, 0
  c->addiu(a2, r0, 0);                              // addiu a2, r0, 0
  c->lwc1(f0, 204, s3);                             // lwc1 f0, 204(s3)
  c->mfc1(a3, f0);                                  // mfc1 a3, f0
  c->dsll(v1, s4, 2);                               // dsll v1, s4, 2
  c->daddu(v1, v1, s5);                             // daddu v1, v1, s5
  c->lwc1(f0, 32, v1);                              // lwc1 f0, 32(v1)
  c->mfc1(t0, f0);                                  // mfc1 t0, f0
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->addiu(v1, r0, 48);                             // addiu v1, r0, 48
  c->mult3(v1, v1, s4);                             // mult3 v1, v1, s4
  c->daddiu(v1, v1, 4268);                          // daddiu v1, v1, 4268
  c->daddu(v1, v1, gp);                             // daddu v1, v1, gp
  c->load_symbol2(t9, cache.quaternion);            // lw t9, quaternion*!(s7)
  c->daddiu(a0, v1, 32);                            // daddiu a0, v1, 32
  c->daddu(a1, r0, s5);                             // daddu a1, r0, s5
  c->daddiu(a2, s5, 16);                            // daddiu a2, s5, 16
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->gprs[v1].du64[0] = 0;                          // or v1, r0, r0
  c->daddiu(s4, s4, 1);                             // daddiu s4, s4, 1

block_2:
  c->slti(v1, s4, 4);                               // slti v1, s4, 4
  bc = c->sgpr64(v1) != 0;                          // bne v1, r0, L2
  // nop                                            // sll r0, r0, 0
  if (bc) {goto block_1;}                           // branch non-likely

  c->mov64(v1, s7);                                 // or v1, s7, r0
  c->mov64(v1, s7);                                 // or v1, s7, r0
  c->daddiu(s5, sp, 64);                            // daddiu s5, sp, 64
  c->daddu(v1, r0, s5);                             // daddu v1, r0, s5
  c->lwu(a0, 188, gp);                              // lwu a0, 188(gp)
  c->lwu(a0, 28, a0);                               // lwu a0, 28(a0)
  c->daddu(a3, r0, a0);                             // daddu a3, r0, a0
  c->lq(a0, 0, a3);                                 // lq a0, 0(a3)
  c->lq(a1, 16, a3);                                // lq a1, 16(a3)
  c->lq(a2, 32, a3);                                // lq a2, 32(a3)
  c->lq(a3, 48, a3);                                // lq a3, 48(a3)
  c->sq(a0, 0, v1);                                 // sq a0, 0(v1)
  c->sq(a1, 16, v1);                                // sq a1, 16(v1)
  c->sq(a2, 32, v1);                                // sq a2, 32(v1)
  c->sq(a3, 48, v1);                                // sq a3, 48(v1)
  c->daddiu(v1, s5, 64);                            // daddiu v1, s5, 64
  // daddiu a0, fp, L11 — const v4 (0x456b851f, 0x45666666, 0x45d33333, 0x3f800000); hand-emit:
  c->lui(a0, 0x456b); c->ori(a0, a0, 0x851f); c->sw(a0, 0, v1);
  c->lui(a0, 0x4566); c->ori(a0, a0, 0x6666); c->sw(a0, 4, v1);
  c->lui(a0, 0x45d3); c->ori(a0, a0, 0x3333); c->sw(a0, 8, v1);
  c->lui(a0, 0x3f80); c->sw(a0, 12, v1);
  c->lq(a0, 0, v1);                                 // sq a0, 0(v1) (reload as 128b)
  c->daddiu(v1, s5, 80);                            // daddiu v1, s5, 80
  // daddiu a0, fp, L10 — const v4 (0x456b851f, 0x45666666, 0x45d33333, 0x3f800000); hand-emit:
  c->lui(a0, 0x456b); c->ori(a0, a0, 0x851f); c->sw(a0, 0, v1);
  c->lui(a0, 0x4566); c->ori(a0, a0, 0x6666); c->sw(a0, 4, v1);
  c->lui(a0, 0x45d3); c->ori(a0, a0, 0x3333); c->sw(a0, 8, v1);
  c->lui(a0, 0x3f80); c->sw(a0, 12, v1);
  c->lq(a0, 0, v1);                                 // sq a0, 0(v1) (reload as 128b)
  c->daddiu(v1, s5, 96);                            // daddiu v1, s5, 96
  // daddiu a0, fp, L9 — const v4 (0x45b5c28f, 0x45a3d70a, 0xc63ae148, 0x3f800000); hand-emit:
  c->lui(a0, 0x45b5); c->ori(a0, a0, 0xc28f); c->sw(a0, 0, v1);
  c->lui(a0, 0x45a3); c->ori(a0, a0, 0xd70a); c->sw(a0, 4, v1);
  c->lui(a0, 0xc63a); c->ori(a0, a0, 0xe148); c->sw(a0, 8, v1);
  c->lui(a0, 0x3f80); c->sw(a0, 12, v1);
  c->lq(a0, 0, v1);                                 // sq a0, 0(v1) (reload as 128b)
  c->daddiu(v1, s5, 112);                           // daddiu v1, s5, 112
  // daddiu a0, fp, L8 — const v4 (0x45b5c28f, 0x45a3d70a, 0xc63ae148, 0x3f800000); hand-emit:
  c->lui(a0, 0x45b5); c->ori(a0, a0, 0xc28f); c->sw(a0, 0, v1);
  c->lui(a0, 0x45a3); c->ori(a0, a0, 0xd70a); c->sw(a0, 4, v1);
  c->lui(a0, 0xc63a); c->ori(a0, a0, 0xe148); c->sw(a0, 8, v1);
  c->lui(a0, 0x3f80); c->sw(a0, 12, v1);
  c->lq(a0, 0, v1);                                 // sq a0, 0(v1) (reload as 128b)
  c->daddiu(v1, s5, 128);                           // daddiu v1, s5, 128
  c->lui(a0, 18119);                                // lui a0, 18119
  c->ori(a0, a0, 7282);                             // ori a0, a0, 7282
  c->mtc1(f0, a0);                                  // mtc1 f0, a0
  c->swc1(f0, 0, v1);                               // swc1 f0, 0(v1)
  c->lui(a0, 18119);                                // lui a0, 18119
  c->ori(a0, a0, 7282);                             // ori a0, a0, 7282
  c->mtc1(f0, a0);                                  // mtc1 f0, a0
  c->swc1(f0, 4, v1);                               // swc1 f0, 4(v1)
  c->lui(a0, 18147);                                // lui a0, 18147
  c->ori(a0, a0, 36409);                            // ori a0, a0, 36409
  c->mtc1(f0, a0);                                  // mtc1 f0, a0
  c->swc1(f0, 8, v1);                               // swc1 f0, 8(v1)
  c->lui(a0, 18147);                                // lui a0, 18147
  c->ori(a0, a0, 36409);                            // ori a0, a0, 36409
  c->mtc1(f0, a0);                                  // mtc1 f0, a0
  c->swc1(f0, 12, v1);                              // swc1 f0, 12(v1)
  c->addiu(s4, r0, 0);                              // addiu s4, r0, 0
  //beq r0, r0, L5                                  // beq r0, r0, L5
  // nop                                            // sll r0, r0, 0
  goto block_5;                                     // branch always


block_4:
  c->addiu(v1, r0, 288);                            // addiu v1, r0, 288
  c->mult3(v1, v1, s4);                             // mult3 v1, v1, s4
  c->daddiu(v1, v1, 2476);                          // daddiu v1, v1, 2476
  c->daddu(s3, v1, gp);                             // daddu s3, v1, gp
  c->lwu(v1, 0, s3);                                // lwu v1, 0(s3)
  c->lui(a0, -15104);                               // lui a0, -15104
  c->mtc1(f0, a0);                                  // mtc1 f0, a0
  c->lwc1(f1, 36, v1);                              // lwc1 f1, 36(v1)
  c->adds(f0, f0, f1);                              // add.s f0, f0, f1
  c->swc1(f0, 256, s5);                             // swc1 f0, 256(s5)
  c->daddiu(a0, s5, 176);                           // daddiu a0, s5, 176
  c->dsll(a1, s4, 4);                               // dsll a1, s4, 4
  c->daddiu(a1, a1, 64);                            // daddiu a1, a1, 64
  c->daddu(a1, a1, s5);                             // daddu a1, a1, s5
  c->lq(a1, 0, a1);                                 // lq a1, 0(a1)
  c->sq(a1, 0, a0);                                 // sq a1, 0(a0)
  c->daddiu(a0, s5, 144);                           // daddiu a0, s5, 144
  c->daddu(v1, r0, v1);                             // daddu v1, r0, v1
  c->lq(v1, 0, v1);                                 // lq v1, 0(v1)
  c->sq(v1, 0, a0);                                 // sq v1, 0(a0)
  c->lwc1(f0, 144, s5);                             // lwc1 f0, 144(s5)
  c->lwc1(f1, 256, s5);                             // lwc1 f1, 256(s5)
  c->lwc1(f2, 252, s3);                             // lwc1 f2, 252(s3)
  c->muls(f1, f1, f2);                              // mul.s f1, f1, f2
  c->adds(f0, f0, f1);                              // add.s f0, f0, f1
  c->swc1(f0, 144, s5);                             // swc1 f0, 144(s5)
  c->lwc1(f0, 148, s5);                             // lwc1 f0, 148(s5)
  c->lwc1(f1, 256, s5);                             // lwc1 f1, 256(s5)
  c->lwc1(f2, 248, s3);                             // lwc1 f2, 248(s3)
  c->muls(f1, f1, f2);                              // mul.s f1, f1, f2
  c->adds(f0, f0, f1);                              // add.s f0, f0, f1
  c->swc1(f0, 148, s5);                             // swc1 f0, 148(s5)
  c->daddiu(v1, s5, 192);                           // daddiu v1, s5, 192
  c->daddiu(a0, s5, 144);                           // daddiu a0, s5, 144
  c->lq(a0, 0, a0);                                 // lq a0, 0(a0)
  c->sq(a0, 0, v1);                                 // sq a0, 0(v1)
  c->lwc1(f0, 192, s5);                             // lwc1 f0, 192(s5)
  c->lwc1(f1, 204, s3);                             // lwc1 f1, 204(s3)
  c->muls(f0, f0, f1);                              // mul.s f0, f0, f1
  c->swc1(f0, 192, s5);                             // swc1 f0, 192(s5)
  c->lwc1(f0, 176, s5);                             // lwc1 f0, 176(s5)
  c->lwc1(f1, 204, s3);                             // lwc1 f1, 204(s3)
  c->muls(f0, f0, f1);                              // mul.s f0, f0, f1
  c->swc1(f0, 176, s5);                             // swc1 f0, 176(s5)
  c->daddiu(a1, s5, 208);                           // daddiu a1, s5, 208
  c->daddiu(v1, s5, 192);                           // daddiu v1, s5, 192
  c->daddiu(a0, s5, 176);                           // daddiu a0, s5, 176
  c->lqc2(vf4, 0, v1);                              // lqc2 vf4, 0(v1)
  c->lqc2(vf5, 0, a0);                              // lqc2 vf5, 0(a0)
  c->vmove(DEST::w, vf6, vf0);                      // vmove.w vf6, vf0
  c->vsub(DEST::xyz, vf6, vf4, vf5);                // vsub.xyz vf6, vf4, vf5
  c->sqc2(vf6, 0, a1);                              // sqc2 vf6, 0(a1)
  c->dsll(v1, s4, 2);                               // dsll v1, s4, 2
  c->daddu(v1, v1, s5);                             // daddu v1, v1, s5
  c->lwc1(f30, 128, v1);                            // lwc1 f30, 128(v1)
  c->load_symbol2(t9, cache.atan);                  // lw t9, atan(s7)
  c->lwc1(f0, 208, s5);                             // lwc1 f0, 208(s5)
  c->mfc1(a0, f0);                                  // mfc1 a0, f0
  c->lwc1(f0, 212, s5);                             // lwc1 f0, 212(s5)
  c->mfc1(a1, f0);                                  // mfc1 a1, f0
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mtc1(f0, v0);                                  // mtc1 f0, v0
  c->lwc1(f1, 204, s3);                             // lwc1 f1, 204(s3)
  c->muls(f0, f0, f1);                              // mul.s f0, f0, f1
  c->subs(f0, f30, f0);                             // sub.s f0, f30, f0
  c->swc1(f0, 260, s5);                             // swc1 f0, 260(s5)
  c->dsll(v1, s4, 5);                               // dsll v1, s4, 5
  c->daddiu(v1, v1, 4668);                          // daddiu v1, v1, 4668
  c->daddu(v1, v1, gp);                             // daddu v1, v1, gp
  c->load_symbol2(t9, cache.quaternion_axis_angle); // lw t9, quaternion-axis-angle!(s7)
  c->daddiu(a0, v1, 16);                            // daddiu a0, v1, 16
  c->addiu(a1, r0, 0);                              // addiu a1, r0, 0
  c->addiu(a2, r0, 0);                              // addiu a2, r0, 0
  c->lui(a3, 16256);                                // lui a3, 16256
  c->lwc1(f0, 260, s5);                             // lwc1 f0, 260(s5)
  c->mfc1(t0, f0);                                  // mfc1 t0, f0
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->gprs[v1].du64[0] = 0;                          // or v1, r0, r0
  c->dsll(v1, s4, 6);                               // dsll v1, s4, 6
  c->daddiu(v1, v1, 4796);                          // daddiu v1, v1, 4796
  c->daddu(v1, v1, gp);                             // daddu v1, v1, gp
  c->lui(a0, -16512);                               // lui a0, -16512
  c->mtc1(f0, a0);                                  // mtc1 f0, a0
  c->lui(a0, -15028);                               // lui a0, -15028
  c->ori(a0, a0, 52429);                            // ori a0, a0, 52429
  c->mtc1(f1, a0);                                  // mtc1 f1, a0
  c->daddiu(a0, s5, 208);                           // daddiu a0, s5, 208
  c->lqc2(vf1, 0, a0);                              // lqc2 vf1, 0(a0)
  c->vmul(DEST::xyzw, vf1, vf1, vf1);               // vmul.xyzw vf1, vf1, vf1
  c->vmula_bc(DEST::w, BC::x, vf0, vf1);            // vmulax.w acc, vf0, vf1
  c->vmadda_bc(DEST::w, BC::y, vf0, vf1);           // vmadday.w acc, vf0, vf1
  c->vmadd_bc(DEST::w, BC::z, vf1, vf0, vf1);       // vmaddz.w vf1, vf0, vf1
  c->vsqrt(vf1, BC::w);                             // vsqrt Q, vf1.w
  c->vadd_bc(DEST::x, BC::w, vf1, vf0, vf0);        // vaddw.x vf1, vf0, vf0
  c->vwaitq();                                      // vwaitq
  c->vmulq(DEST::x, vf1, vf1);                      // vmulq.x vf1, vf1, Q
  // nop                                            // vnop
  // nop                                            // vnop
  c->mov128_gpr_vf(a0, vf1);                        // qmfc2.i a0, vf1
  c->mtc1(f2, a0);                                  // mtc1 f2, a0
  c->adds(f1, f1, f2);                              // add.s f1, f1, f2
  c->muls(f0, f0, f1);                              // mul.s f0, f0, f1
  c->lwc1(f1, 204, s3);                             // lwc1 f1, 204(s3)
  c->muls(f0, f0, f1);                              // mul.s f0, f0, f1
  c->swc1(f0, 20, v1);                              // swc1 f0, 20(v1)
  c->gprs[v1].du64[0] = 0;                          // or v1, r0, r0
  c->gprs[v1].du64[0] = 0;                          // or v1, r0, r0
  c->daddiu(s4, s4, 1);                             // daddiu s4, s4, 1

block_5:
  c->slti(v1, s4, 4);                               // slti v1, s4, 4
  bc = c->sgpr64(v1) != 0;                          // bne v1, r0, L4
  // nop                                            // sll r0, r0, 0
  if (bc) {goto block_4;}                           // branch non-likely

  c->mov64(v1, s7);                                 // or v1, s7, r0
  c->mov64(v1, s7);                                 // or v1, s7, r0
  c->gprs[v0].du64[0] = 0;                          // or v0, r0, r0
  c->ld(ra, 0, sp);                                 // ld ra, 0(sp)
  c->ld(fp, 8, sp);                                 // ld fp, 8(sp)
  c->lwc1(f30, 400, sp);                            // lwc1 f30, 400(sp)
  c->lq(gp, 384, sp);                               // lq gp, 384(sp)
  c->lq(s5, 368, sp);                               // lq s5, 368(sp)
  c->lq(s4, 352, sp);                               // lq s4, 352(sp)
  c->lq(s3, 336, sp);                               // lq s3, 336(sp)
  //jr ra                                           // jr ra
  c->daddiu(sp, sp, 416);                           // daddiu sp, sp, 416
  goto end_of_function;                             // return

  // nop                                            // sll r0, r0, 0
  // nop                                            // sll r0, r0, 0
  // nop                                            // sll r0, r0, 0
end_of_function:
  return c->gprs[v0].du64[0];
}

void link() {
  cache.atan = intern_from_c(-1, 0, "atan").c();
  cache.quaternion = intern_from_c(-1, 0, "quaternion*!").c();
  cache.quaternion_axis_angle = intern_from_c(-1, 0, "quaternion-axis-angle!").c();
  cache.quaternion_normalize = intern_from_c(-1, 0, "quaternion-normalize!").c();
  cache.quaternion_set = intern_from_c(-1, 0, "quaternion-set!").c();
  gLinkedFunctionTable.reg("(method 115 wcar-base)", execute, 416);
}

} // namespace method_115_wcar_base
} // namespace Mips2C
