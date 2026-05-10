//--------------------------MIPS2C---------------------
// clang-format off
#include "game/mips2c/mips2c_private.h"
#include "game/kernel/jakx/kscheme.h"
using ::jakx::intern_from_c;
namespace Mips2C::jakx {

// (method 100 v-bobcat) -- writes 7 stride-80 control vectors into a struct
// that lives at (-> this root root-prim *opaque*+64), then chains to
// (method-of-type wcar-base method-100). Decompiler can't type-prop +64 (the
// destination struct is not in any all-types layout we have); wrapped Tier 2.
//
// L96-L102 vector data (from wcar-bobcat_ir2.asm:3122..):
//   L96 (0.0,        2048.0,  -6963.2,  4915.2)   -> v1+524
//   L97 (0.0,        4096.0,   1638.4,  6144.0)   -> v1+444
//   L98 (0.0,         819.2,  13926.4,  4096.0)   -> v1+364
//   L99 (-7782.4,    1638.4,  -6144.0,  4505.6)   -> v1+284
//   L100 (7782.4,    1638.4,  -6144.0,  4505.6)   -> v1+204
//   L101 (-7782.4,   1228.8,  12185.6,  4505.6)   -> v1+124
//   L102 (7782.4,    1228.8,  12185.6,  4505.6)   -> v1+44
namespace method_100_v_bobcat {
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

  // L102 -> v1+44  (7782.4, 1228.8, 12185.6, 4505.6)
  c->lui(a2, 0x45f3); c->ori(a2, a2, 0x3333); c->sw(a2, 44, v1);
  c->lui(a2, 0x4499); c->ori(a2, a2, 0x999a); c->sw(a2, 48, v1);
  c->lui(a2, 0x463e); c->ori(a2, a2, 0x6666); c->sw(a2, 52, v1);
  c->lui(a2, 0x458c); c->ori(a2, a2, 0xcccd); c->sw(a2, 56, v1);
  // L101 -> v1+124 (-7782.4, 1228.8, 12185.6, 4505.6)
  c->lui(a2, 0xc5f3); c->ori(a2, a2, 0x3333); c->sw(a2, 124, v1);
  c->lui(a2, 0x4499); c->ori(a2, a2, 0x999a); c->sw(a2, 128, v1);
  c->lui(a2, 0x463e); c->ori(a2, a2, 0x6666); c->sw(a2, 132, v1);
  c->lui(a2, 0x458c); c->ori(a2, a2, 0xcccd); c->sw(a2, 136, v1);
  // L100 -> v1+204 (7782.4, 1638.4, -6144.0, 4505.6)
  c->lui(a2, 0x45f3); c->ori(a2, a2, 0x3333); c->sw(a2, 204, v1);
  c->lui(a2, 0x44cc); c->ori(a2, a2, 0xcccd); c->sw(a2, 208, v1);
  c->lui(a2, 0xc5c0); c->ori(a2, a2, 0x0000); c->sw(a2, 212, v1);
  c->lui(a2, 0x458c); c->ori(a2, a2, 0xcccd); c->sw(a2, 216, v1);
  // L99 -> v1+284 (-7782.4, 1638.4, -6144.0, 4505.6)
  c->lui(a2, 0xc5f3); c->ori(a2, a2, 0x3333); c->sw(a2, 284, v1);
  c->lui(a2, 0x44cc); c->ori(a2, a2, 0xcccd); c->sw(a2, 288, v1);
  c->lui(a2, 0xc5c0); c->ori(a2, a2, 0x0000); c->sw(a2, 292, v1);
  c->lui(a2, 0x458c); c->ori(a2, a2, 0xcccd); c->sw(a2, 296, v1);
  // L98 -> v1+364 (0.0, 819.2, 13926.4, 4096.0)
  c->sw(r0, 364, v1);
  c->lui(a2, 0x444c); c->ori(a2, a2, 0xcccd); c->sw(a2, 368, v1);
  c->lui(a2, 0x4659); c->ori(a2, a2, 0x999a); c->sw(a2, 372, v1);
  c->lui(a2, 0x4580); c->ori(a2, a2, 0x0000); c->sw(a2, 376, v1);
  // L97 -> v1+444 (0.0, 4096.0, 1638.4, 6144.0)
  c->sw(r0, 444, v1);
  c->lui(a2, 0x4580); c->ori(a2, a2, 0x0000); c->sw(a2, 448, v1);
  c->lui(a2, 0x44cc); c->ori(a2, a2, 0xcccd); c->sw(a2, 452, v1);
  c->lui(a2, 0x45c0); c->ori(a2, a2, 0x0000); c->sw(a2, 456, v1);
  // L96 -> v1+524 (0.0, 2048.0, -6963.2, 4915.2)
  c->sw(r0, 524, v1);
  c->lui(a2, 0x4500); c->ori(a2, a2, 0x0000); c->sw(a2, 528, v1);
  c->lui(a2, 0xc5d9); c->ori(a2, a2, 0x999a); c->sw(a2, 532, v1);
  c->lui(a2, 0x4599); c->ori(a2, a2, 0x999a); c->sw(a2, 536, v1);

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
  gLinkedFunctionTable.reg("(method 100 v-bobcat)", execute, 16);
}

} // namespace method_100_v_bobcat

// (method 115 v-bobcat) -- 4-iteration shock-joint quaternion updater.
// Build a steering quaternion from this+480 (steering angle * 4096), copy
// to this+4124, then loop 4 wheels: read wheel-state at this+2476+288*i,
// build a roll quaternion from (l.f +248) and (1.0 + l.f +252), normalize,
// build axis-angle, multiply, store at this+4300+48*i.
// Three IR2 ERRORs: stack-guess fail (sp+16 quaternion staging), FPR->GPR
// uninit at op 73 (lwc1 +32 from sp-staged float array). Same VU/quaternion
// scratch-space pattern as wcar-base method-115 — wrapped Tier 2 mips2c.
namespace method_115_v_bobcat {
struct Cache {
  void* sin;
  void* cos;
  void* quaternion_set;        // quaternion-set!
  void* quaternion_copy;       // quaternion-copy!
  void* quaternion_normalize;  // quaternion-normalize!
  void* quaternion_axis_angle; // quaternion-axis-angle!
  void* quaternion_mul;        // quaternion*!
} cache;

u64 execute(void* ctxt) {
  auto* c = (ExecutionContext*)ctxt;
  bool bc = false;
  u32 call_addr = 0;
  c->daddiu(sp, sp, -208);                          // daddiu sp, sp, -208
  c->sd(ra, 0, sp);                                 // sd ra, 0(sp)
  c->sq(s0, 80, sp);                                // sq s0, 80(sp)
  c->sq(s1, 96, sp);                                // sq s1, 96(sp)
  c->sq(s2, 112, sp);                               // sq s2, 112(sp)
  c->sq(s3, 128, sp);                               // sq s3, 128(sp)
  c->sq(s4, 144, sp);                               // sq s4, 144(sp)
  c->sq(s5, 160, sp);                               // sq s5, 160(sp)
  c->sq(gp, 176, sp);                               // sq gp, 176(sp)
  c->swc1(f30, 192, sp);                            // swc1 f30, 192(sp)
  // B0:
  c->mov64(gp, a0);                                 // or gp, a0, r0
  c->daddiu(s5, sp, 16);                            // daddiu s5, sp, 16
  c->lui(v1, 17792);                                // lui v1, 17792 (=4096.0)
  c->mtc1(f0, v1);                                  // mtc1 f0, v1
  c->lwc1(f1, 480, gp);                             // lwc1 f1, 480(gp)
  c->muls(f30, f0, f1);                             // mul.s f30, f0, f1
  c->load_symbol2(s4, cache.quaternion_set);        // lw s4, quaternion-set!(s7)
  c->daddu(s3, r0, s5);                             // daddu s3, r0, s5
  c->addiu(s2, r0, 0);                              // addiu s2, r0, 0
  c->load_symbol2(t9, cache.sin);                   // lw t9, sin(s7)
  c->mfc1(a0, f30);                                 // mfc1 a0, f30
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9 (sin)
  c->mov64(s1, v0);                                 // or s1, v0, r0
  c->addiu(s0, r0, 0);                              // addiu s0, r0, 0
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
  c->daddiu(v1, s5, 32);                            // daddiu v1, s5, 32
  c->mtc1(f0, r0);                                  // mtc1 f0, r0  (= 0.0)
  c->swc1(f0, 0, v1);                               // swc1 f0, 0(v1)
  c->mtc1(f0, r0);                                  // mtc1 f0, r0
  c->swc1(f0, 4, v1);                               // swc1 f0, 4(v1)
  c->lui(a0, 17635);                                // lui a0, 17635
  c->ori(a0, a0, 36409);                            // ori a0, a0, 36409 (= 1820.4445)
  c->mtc1(f0, a0);                                  // mtc1 f0, a0
  c->swc1(f0, 8, v1);                               // swc1 f0, 8(v1)
  c->lui(a0, 17635);                                // lui a0, 17635
  c->ori(a0, a0, 36409);                            // ori a0, a0, 36409
  c->mtc1(f0, a0);                                  // mtc1 f0, a0
  c->swc1(f0, 12, v1);                              // swc1 f0, 12(v1)
  c->addiu(s4, r0, 0);                              // addiu s4, r0, 0
  // beq r0, r0, L37 (always taken, jumps over body to test)
  goto loop_test;

loop_body:
  // L36:
  c->addiu(v1, r0, 288);                            // addiu v1, r0, 288
  c->mult3(v1, v1, s4);                             // mult3 v1, v1, s4
  c->daddiu(v1, v1, 2476);                          // daddiu v1, v1, 2476
  c->daddu(v1, v1, gp);                             // daddu v1, v1, gp
  c->lwu(a0, 0, v1);                                // lwu a0, 0(v1) (dead — overwritten)
  c->load_symbol2(t9, cache.quaternion_set);        // lw t9, quaternion-set!(s7)
  c->daddu(a0, r0, s5);                             // daddu a0, r0, s5
  c->addiu(a1, r0, 0);                              // addiu a1, r0, 0
  c->addiu(a2, r0, 0);                              // addiu a2, r0, 0
  c->lwc1(f0, 248, v1);                             // lwc1 f0, 248(v1)
  c->mfc1(a3, f0);                                  // mfc1 a3, f0
  c->lui(t0, 16256);                                // lui t0, 16256 (= 1.0)
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
  c->load_symbol2(t9, cache.quaternion_axis_angle); // lw t9, quaternion-axis-angle!(s7)
  c->daddiu(a0, s5, 16);                            // daddiu a0, s5, 16
  c->addiu(a1, r0, 0);                              // addiu a1, r0, 0
  c->addiu(a2, r0, 0);                              // addiu a2, r0, 0
  c->lui(a3, 16256);                                // lui a3, 16256 (= 1.0)
  c->dsll(v1, s4, 2);                               // dsll v1, s4, 2
  c->daddu(v1, v1, s5);                             // daddu v1, v1, s5
  c->lwc1(f0, 32, v1);                              // lwc1 f0, 32(v1)
  c->mfc1(t0, f0);                                  // mfc1 t0, f0
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9 (quaternion-axis-angle!)
  c->addiu(v1, r0, 48);                             // addiu v1, r0, 48
  c->mult3(v1, v1, s4);                             // mult3 v1, v1, s4
  c->daddiu(v1, v1, 4268);                          // daddiu v1, v1, 4268
  c->daddu(v1, v1, gp);                             // daddu v1, v1, gp
  c->load_symbol2(t9, cache.quaternion_mul);        // lw t9, quaternion*!(s7)
  c->daddiu(a0, v1, 32);                            // daddiu a0, v1, 32
  c->daddu(a1, r0, s5);                             // daddu a1, r0, s5
  c->daddiu(a2, s5, 16);                            // daddiu a2, s5, 16
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9 (quaternion*!)
  c->gprs[v1].du64[0] = 0;                          // or v1, r0, r0
  c->daddiu(s4, s4, 1);                             // daddiu s4, s4, 1

loop_test:
  // L37:
  c->slti(v1, s4, 4);                               // slti v1, s4, 4
  bc = (c->sgpr64(v1) != 0);                        // bne v1, r0, L36
  if (bc) { goto loop_body; }

  // B3:
  c->mov64(v1, s7);                                 // or v1, s7, r0
  c->mov64(v1, s7);                                 // or v1, s7, r0
  c->gprs[v0].du64[0] = 0;                          // or v0, r0, r0
  c->ld(ra, 0, sp);                                 // ld ra, 0(sp)
  c->lwc1(f30, 192, sp);                            // lwc1 f30, 192(sp)
  c->lq(gp, 176, sp);                               // lq gp, 176(sp)
  c->lq(s5, 160, sp);                               // lq s5, 160(sp)
  c->lq(s4, 144, sp);                               // lq s4, 144(sp)
  c->lq(s3, 128, sp);                               // lq s3, 128(sp)
  c->lq(s2, 112, sp);                               // lq s2, 112(sp)
  c->lq(s1, 96, sp);                                // lq s1, 96(sp)
  c->lq(s0, 80, sp);                                // lq s0, 80(sp)
  //jr ra                                           // jr ra
  c->daddiu(sp, sp, 208);                           // daddiu sp, sp, 208
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
  cache.quaternion_axis_angle = intern_from_c(-1, 0, "quaternion-axis-angle!").c();
  cache.quaternion_mul = intern_from_c(-1, 0, "quaternion*!").c();
  gLinkedFunctionTable.reg("(method 115 v-bobcat)", execute, 208);
}

} // namespace method_115_v_bobcat
} // namespace Mips2C
