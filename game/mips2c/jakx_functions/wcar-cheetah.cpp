//--------------------------MIPS2C---------------------
// clang-format off
#include "game/mips2c/mips2c_private.h"
#include "game/kernel/jakx/kscheme.h"
using ::jakx::intern_from_c;
namespace Mips2C::jakx {

// (method 100 v-cheetah) -- writes 7 stride-80 control vectors into a struct
// that lives at (-> this root root-prim *opaque*+64), then chains to
// (method-of-type wcar-base method-100). Same shape as the other v-* m100
// siblings; L-labels and floats differ. Wrapped Tier 2 mips2c.
//
// L95-L101 vector data (from wcar-cheetah_ir2.asm:2747..):
//   L95  (0.0,       4915.2,  -10240.0,  6144.0)   -> v1+524
//   L96  (0.0,       4505.6,    3276.8,  6144.0)   -> v1+444
//   L97  (0.0,       1228.8,   18432.0,  4096.0)   -> v1+364
//   L98  (-9830.4,   2867.2,   -7536.64, 4505.6)   -> v1+284
//   L99  ( 9830.4,   2867.2,   -7536.64, 4505.6)   -> v1+204
//   L100 (-9830.4,   1228.8,   17530.88, 4505.6)   -> v1+124
//   L101 ( 9830.4,   1228.8,   17530.88, 4505.6)   -> v1+44
namespace method_100_v_cheetah {
struct Cache {
  void* wcar_base; // wcar-base
} cache;

u64 execute(void* ctxt) {
  auto* c = (ExecutionContext*)ctxt;
  u32 call_addr = 0;
  c->daddiu(sp, sp, -16);                           // daddiu sp, sp, -16
  c->sd(ra, 0, sp);                                 // sd ra, 0(sp)
  c->sd(fp, 8, sp);                                 // sd fp, 8(sp)
  c->mov64(fp, t9);                                 // or fp, t9, r0
  // B0:
  c->lwu(v1, 184, a0);                              // lwu v1, 184(a0)  (this->root)
  c->lwu(v1, 156, v1);                              // lwu v1, 156(v1)  (-> root-prim)
  c->lwu(v1, 64, v1);                               // lwu v1, 64(v1)   (opaque struct ptr)

  // L101 -> v1+44  (9830.4, 1228.8, 17530.88, 4505.6)
  c->lui(a2, 0x4619); c->ori(a2, a2, 0x999a); c->sw(a2, 44, v1);
  c->lui(a2, 0x4499); c->ori(a2, a2, 0x999a); c->sw(a2, 48, v1);
  c->lui(a2, 0x4688); c->ori(a2, a2, 0xf5c3); c->sw(a2, 52, v1);
  c->lui(a2, 0x458c); c->ori(a2, a2, 0xcccd); c->sw(a2, 56, v1);
  // L100 -> v1+124 (-9830.4, 1228.8, 17530.88, 4505.6)
  c->lui(a2, 0xc619); c->ori(a2, a2, 0x999a); c->sw(a2, 124, v1);
  c->lui(a2, 0x4499); c->ori(a2, a2, 0x999a); c->sw(a2, 128, v1);
  c->lui(a2, 0x4688); c->ori(a2, a2, 0xf5c3); c->sw(a2, 132, v1);
  c->lui(a2, 0x458c); c->ori(a2, a2, 0xcccd); c->sw(a2, 136, v1);
  // L99 -> v1+204 (9830.4, 2867.2, -7536.64, 4505.6)
  c->lui(a2, 0x4619); c->ori(a2, a2, 0x999a); c->sw(a2, 204, v1);
  c->lui(a2, 0x4533); c->ori(a2, a2, 0x3333); c->sw(a2, 208, v1);
  c->lui(a2, 0xc5eb); c->ori(a2, a2, 0x851f); c->sw(a2, 212, v1);
  c->lui(a2, 0x458c); c->ori(a2, a2, 0xcccd); c->sw(a2, 216, v1);
  // L98 -> v1+284 (-9830.4, 2867.2, -7536.64, 4505.6)
  c->lui(a2, 0xc619); c->ori(a2, a2, 0x999a); c->sw(a2, 284, v1);
  c->lui(a2, 0x4533); c->ori(a2, a2, 0x3333); c->sw(a2, 288, v1);
  c->lui(a2, 0xc5eb); c->ori(a2, a2, 0x851f); c->sw(a2, 292, v1);
  c->lui(a2, 0x458c); c->ori(a2, a2, 0xcccd); c->sw(a2, 296, v1);
  // L97 -> v1+364 (0.0, 1228.8, 18432.0, 4096.0)
  c->sw(r0, 364, v1);
  c->lui(a2, 0x4499); c->ori(a2, a2, 0x999a); c->sw(a2, 368, v1);
  c->lui(a2, 0x4690); c->ori(a2, a2, 0x0000); c->sw(a2, 372, v1);
  c->lui(a2, 0x4580); c->ori(a2, a2, 0x0000); c->sw(a2, 376, v1);
  // L96 -> v1+444 (0.0, 4505.6, 3276.8, 6144.0)
  c->sw(r0, 444, v1);
  c->lui(a2, 0x458c); c->ori(a2, a2, 0xcccd); c->sw(a2, 448, v1);
  c->lui(a2, 0x454c); c->ori(a2, a2, 0xcccd); c->sw(a2, 452, v1);
  c->lui(a2, 0x45c0); c->ori(a2, a2, 0x0000); c->sw(a2, 456, v1);
  // L95 -> v1+524 (0.0, 4915.2, -10240.0, 6144.0)
  c->sw(r0, 524, v1);
  c->lui(a2, 0x4599); c->ori(a2, a2, 0x999a); c->sw(a2, 528, v1);
  c->lui(a2, 0xc620); c->ori(a2, a2, 0x0000); c->sw(a2, 532, v1);
  c->lui(a2, 0x45c0); c->ori(a2, a2, 0x0000); c->sw(a2, 536, v1);

  // call wcar-base.method-100(this)  -- a0 still holds 'this' from entry
  c->load_symbol2(v1, cache.wcar_base);             // lw v1, wcar-base(s7)
  c->lwu(t9, 416, v1);                              // lwu t9, 416(v1)  vtable[method-100]
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0  (delay slot)
  c->jalr(call_addr);                               // jalr ra, t9

  c->gprs[v0].du64[0] = 0;                          // or v0, r0, r0
  c->ld(ra, 0, sp);                                 // ld ra, 0(sp)
  c->ld(fp, 8, sp);                                 // ld fp, 8(sp)
  //jr ra                                           // jr ra
  c->daddiu(sp, sp, 16);                            // daddiu sp, sp, 16
  goto end_of_function;                             // return

end_of_function:
  return c->gprs[v0].du64[0];
}

void link() {
  cache.wcar_base = intern_from_c(-1, 0, "wcar-base").c();
  gLinkedFunctionTable.reg("(method 100 v-cheetah)", execute, 16);
}

} // namespace method_100_v_cheetah

// (method 115 v-cheetah) -- 4-iteration shock-joint quaternion updater.
// Same overall shape as v-cougar method 115 (steering quat from this+480
// ×-4096.0, copy to this+4124, 4-wheel quaternion-set! + normalize + copy
// to this+4300+48*i). Differs only in quaternion-set! arg layout: cheetah
// uses (l.f +248, 0, 0, 1.0+l.f +252) — X-axis rotation — vs cougar's
// (0, 0, l.f +248, 1.0+l.f +252) — Z-axis rotation. Stack 176, Tier 2.
namespace method_115_v_cheetah {
struct Cache {
  void* sin;
  void* cos;
  void* quaternion_set;        // quaternion-set!
  void* quaternion_copy;       // quaternion-copy!
  void* quaternion_normalize;  // quaternion-normalize!
} cache;

u64 execute(void* ctxt) {
  auto* c = (ExecutionContext*)ctxt;
  bool bc = false;
  u32 call_addr = 0;
  c->daddiu(sp, sp, -176);                          // daddiu sp, sp, -176
  c->sd(ra, 0, sp);                                 // sd ra, 0(sp)
  c->sq(s0, 48, sp);                                // sq s0, 48(sp)
  c->sq(s1, 64, sp);                                // sq s1, 64(sp)
  c->sq(s2, 80, sp);                                // sq s2, 80(sp)
  c->sq(s3, 96, sp);                                // sq s3, 96(sp)
  c->sq(s4, 112, sp);                               // sq s4, 112(sp)
  c->sq(s5, 128, sp);                               // sq s5, 128(sp)
  c->sq(gp, 144, sp);                               // sq gp, 144(sp)
  c->swc1(f30, 160, sp);                            // swc1 f30, 160(sp)
  // B0:
  c->mov64(gp, a0);                                 // or gp, a0, r0
  c->daddiu(s5, sp, 16);                            // daddiu s5, sp, 16
  c->lui(v1, -14976);                               // lui v1, -14976 (=-4096.0)
  c->mtc1(f0, v1);                                  // mtc1 f0, v1
  c->lwc1(f1, 480, gp);                             // lwc1 f1, 480(gp)
  c->muls(f30, f0, f1);                             // mul.s f30, f0, f1
  c->load_symbol2(s4, cache.quaternion_set);        // lw s4, quaternion-set!(s7)
  c->daddu(s3, r0, s5);                             // daddu s3, r0, s5
  c->addiu(s2, r0, 0);                              // addiu s2, r0, 0
  c->addiu(s1, r0, 0);                              // addiu s1, r0, 0
  c->load_symbol2(t9, cache.sin);                   // lw t9, sin(s7)
  c->mfc1(a0, f30);                                 // mfc1 a0, f30
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9 (sin)
  c->mov64(s0, v0);                                 // or s0, v0, r0
  c->load_symbol2(t9, cache.cos);                   // lw t9, cos(s7)
  c->mfc1(a0, f30);                                 // mfc1 a0, f30
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9 (cos)
  c->mov64(t0, v0);                                 // or t0, v0, r0
  c->mov64(t9, s4);                                 // or t9, s4, r0
  c->mov64(a0, s3);                                 // or a0, s3, r0
  c->mov64(a1, s2);                                 // or a1, s2, r0
  c->mov64(a2, s1);                                 // or a2, s1, r0
  c->mov64(a3, s0);                                 // or a3, s0, r0
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9 (quaternion-set!)
  c->mov64(v1, v0);                                 // or v1, v0, r0
  c->daddiu(v1, gp, 4108);                          // daddiu v1, gp, 4108
  c->load_symbol2(t9, cache.quaternion_copy);       // lw t9, quaternion-copy!(s7)
  c->daddiu(a0, v1, 16);                            // daddiu a0, v1, 16
  c->daddu(a1, r0, s5);                             // daddu a1, r0, s5
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9 (quaternion-copy!)

  c->gprs[v1].du64[0] = 0;                          // or v1, r0, r0
  c->daddiu(s5, sp, 32);                            // daddiu s5, sp, 32
  c->addiu(s4, r0, 0);                              // addiu s4, r0, 0
  goto loop_test;                                   // beq r0, r0, L36

loop_body:
  // L35:
  c->addiu(v1, r0, 288);                            // addiu v1, r0, 288
  c->mult3(v1, v1, s4);                             // mult3 v1, v1, s4
  c->daddiu(v1, v1, 2476);                          // daddiu v1, v1, 2476
  c->daddu(v1, v1, gp);                             // daddu v1, v1, gp
  c->lwu(a0, 0, v1);                                // lwu a0, 0(v1) (dead)
  c->load_symbol2(t9, cache.quaternion_set);        // lw t9, quaternion-set!(s7)
  c->daddu(a0, r0, s5);                             // daddu a0, r0, s5
  // v-cheetah specific: a1 = l.f +248 (X-axis rotation)
  c->lwc1(f0, 248, v1);                             // lwc1 f0, 248(v1)
  c->mfc1(a1, f0);                                  // mfc1 a1, f0
  c->addiu(a2, r0, 0);                              // addiu a2, r0, 0
  c->addiu(a3, r0, 0);                              // addiu a3, r0, 0
  c->lui(t0, 16256);                                // lui t0, 16256 (=1.0)
  c->mtc1(f0, t0);                                  // mtc1 f0, t0
  c->lwc1(f1, 252, v1);                             // lwc1 f1, 252(v1)
  c->adds(f0, f0, f1);                              // add.s f0, f0, f1
  c->mfc1(t0, f0);                                  // mfc1 t0, f0
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9 (quaternion-set!)
  c->load_symbol2(t9, cache.quaternion_normalize);  // lw t9, quaternion-normalize!(s7)
  c->daddu(a0, r0, s5);                             // daddu a0, r0, s5
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9 (quaternion-normalize!)
  c->addiu(v1, r0, 48);                             // addiu v1, r0, 48
  c->mult3(v1, v1, s4);                             // mult3 v1, v1, s4
  c->daddiu(v1, v1, 4268);                          // daddiu v1, v1, 4268
  c->daddu(v1, v1, gp);                             // daddu v1, v1, gp
  c->load_symbol2(t9, cache.quaternion_copy);       // lw t9, quaternion-copy!(s7)
  c->daddiu(a0, v1, 32);                            // daddiu a0, v1, 32
  c->daddu(a1, r0, s5);                             // daddu a1, r0, s5
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9 (quaternion-copy!)
  c->gprs[v1].du64[0] = 0;                          // or v1, r0, r0
  c->daddiu(s4, s4, 1);                             // daddiu s4, s4, 1

loop_test:
  // L36:
  c->slti(v1, s4, 4);                               // slti v1, s4, 4
  bc = (c->sgpr64(v1) != 0);                        // bne v1, r0, L35
  if (bc) { goto loop_body; }

  // B3:
  c->mov64(v1, s7);                                 // or v1, s7, r0
  c->mov64(v1, s7);                                 // or v1, s7, r0
  c->gprs[v0].du64[0] = 0;                          // or v0, r0, r0
  c->ld(ra, 0, sp);                                 // ld ra, 0(sp)
  c->lwc1(f30, 160, sp);                            // lwc1 f30, 160(sp)
  c->lq(gp, 144, sp);                               // lq gp, 144(sp)
  c->lq(s5, 128, sp);                               // lq s5, 128(sp)
  c->lq(s4, 112, sp);                               // lq s4, 112(sp)
  c->lq(s3, 96, sp);                                // lq s3, 96(sp)
  c->lq(s2, 80, sp);                                // lq s2, 80(sp)
  c->lq(s1, 64, sp);                                // lq s1, 64(sp)
  c->lq(s0, 48, sp);                                // lq s0, 48(sp)
  //jr ra                                           // jr ra
  c->daddiu(sp, sp, 176);                           // daddiu sp, sp, 176
  goto end_of_function;
end_of_function:
  return c->gprs[v0].du64[0];
}

void link() {
  cache.sin = intern_from_c(-1, 0, "sin").c();
  cache.cos = intern_from_c(-1, 0, "cos").c();
  cache.quaternion_set = intern_from_c(-1, 0, "quaternion-set!").c();
  cache.quaternion_copy = intern_from_c(-1, 0, "quaternion-copy!").c();
  cache.quaternion_normalize = intern_from_c(-1, 0, "quaternion-normalize!").c();
  gLinkedFunctionTable.reg("(method 115 v-cheetah)", execute, 176);
}

} // namespace method_115_v_cheetah
} // namespace Mips2C
