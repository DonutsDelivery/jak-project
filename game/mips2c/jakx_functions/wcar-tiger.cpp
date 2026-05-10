//--------------------------MIPS2C---------------------
// clang-format off
#include "game/mips2c/mips2c_private.h"
#include "game/kernel/jakx/kscheme.h"
using ::jakx::intern_from_c;
namespace Mips2C::jakx {

// (method 100 v-tiger) -- writes 7 stride-80 control vectors into a struct
// that lives at (-> this root root-prim *opaque*+64), then chains to
// (method-of-type wcar-base method-100). Same shape as the bobcat/cougar/
// wolf/leopard/cheetah m100, but v-tiger's static labels are shifted by 1
// (L96..L102 vs L95..L101) because v-tiger reserves L95 for the
// "skel-tiger-chassis" string used by m66.
//
// L96..L102 vector data (from wcar-tiger_ir2.asm:3716-3750):
//   L96  (0.0,      3686.4, -8192.0,   6144.0)   -> v1+524
//   L97  (0.0,      4505.6,  1638.4,   7372.8)   -> v1+444
//   L98  (0.0,      1638.4, 13312.0,   4915.2)   -> v1+364
//   L99  (-9011.2,  2048.0, -15093.76, 4096.0)   -> v1+284
//   L100 (9011.2,   2048.0, -15093.76, 4096.0)   -> v1+204
//   L101 (-9011.2,   819.2,  16179.2,  4096.0)   -> v1+124
//   L102 (9011.2,    819.2,  16179.2,  4096.0)   -> v1+44
namespace method_100_v_tiger {
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

  // L102 -> v1+44  (9011.2, 819.2, 16179.2, 4096.0)
  c->lui(a2, 0x460c); c->ori(a2, a2, 0xcccd); c->sw(a2, 44, v1);
  c->lui(a2, 0x444c); c->ori(a2, a2, 0xcccd); c->sw(a2, 48, v1);
  c->lui(a2, 0x467c); c->ori(a2, a2, 0xcccd); c->sw(a2, 52, v1);
  c->lui(a2, 0x4580); c->ori(a2, a2, 0x0000); c->sw(a2, 56, v1);
  // L101 -> v1+124 (-9011.2, 819.2, 16179.2, 4096.0)
  c->lui(a2, 0xc60c); c->ori(a2, a2, 0xcccd); c->sw(a2, 124, v1);
  c->lui(a2, 0x444c); c->ori(a2, a2, 0xcccd); c->sw(a2, 128, v1);
  c->lui(a2, 0x467c); c->ori(a2, a2, 0xcccd); c->sw(a2, 132, v1);
  c->lui(a2, 0x4580); c->ori(a2, a2, 0x0000); c->sw(a2, 136, v1);
  // L100 -> v1+204 (9011.2, 2048.0, -15093.76, 4096.0)
  c->lui(a2, 0x460c); c->ori(a2, a2, 0xcccd); c->sw(a2, 204, v1);
  c->lui(a2, 0x4500); c->ori(a2, a2, 0x0000); c->sw(a2, 208, v1);
  c->lui(a2, 0xc66b); c->ori(a2, a2, 0xd70a); c->sw(a2, 212, v1);
  c->lui(a2, 0x4580); c->ori(a2, a2, 0x0000); c->sw(a2, 216, v1);
  // L99 -> v1+284 (-9011.2, 2048.0, -15093.76, 4096.0)
  c->lui(a2, 0xc60c); c->ori(a2, a2, 0xcccd); c->sw(a2, 284, v1);
  c->lui(a2, 0x4500); c->ori(a2, a2, 0x0000); c->sw(a2, 288, v1);
  c->lui(a2, 0xc66b); c->ori(a2, a2, 0xd70a); c->sw(a2, 292, v1);
  c->lui(a2, 0x4580); c->ori(a2, a2, 0x0000); c->sw(a2, 296, v1);
  // L98 -> v1+364 (0.0, 1638.4, 13312.0, 4915.2)
  c->sw(r0, 364, v1);
  c->lui(a2, 0x44cc); c->ori(a2, a2, 0xcccd); c->sw(a2, 368, v1);
  c->lui(a2, 0x4650); c->ori(a2, a2, 0x0000); c->sw(a2, 372, v1);
  c->lui(a2, 0x4599); c->ori(a2, a2, 0x999a); c->sw(a2, 376, v1);
  // L97 -> v1+444 (0.0, 4505.6, 1638.4, 7372.8)
  c->sw(r0, 444, v1);
  c->lui(a2, 0x458c); c->ori(a2, a2, 0xcccd); c->sw(a2, 448, v1);
  c->lui(a2, 0x44cc); c->ori(a2, a2, 0xcccd); c->sw(a2, 452, v1);
  c->lui(a2, 0x45e6); c->ori(a2, a2, 0x6666); c->sw(a2, 456, v1);
  // L96 -> v1+524 (0.0, 3686.4, -8192.0, 6144.0)
  c->sw(r0, 524, v1);
  c->lui(a2, 0x4566); c->ori(a2, a2, 0x6666); c->sw(a2, 528, v1);
  c->lui(a2, 0xc600); c->ori(a2, a2, 0x0000); c->sw(a2, 532, v1);
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
  gLinkedFunctionTable.reg("(method 100 v-tiger)", execute, 16);
}

} // namespace method_100_v_tiger

// (method 115 v-tiger) -- novel 4-iteration shock-joint quaternion updater.
// Differs from bobcat (no quaternion-mul, no normalize), differs from
// cougar/leopard/wolf/cheetah (uses quaternion-axis-angle! + quaternion-copy!
// in the loop instead of quaternion-set! + normalize! + copy!). Uses an
// in-stack float array of constants (-1740.8 -1740.8 -2048.0 -2048.0) at
// sp+48 (s5+16 after s5 is reassigned to sp+32), reads per-wheel state at
// gp+2476+288*i and per-wheel info at deref(s2)+48; writes a per-wheel
// scalar at gp+4268+48*i+20 (=gp+4288+48*i) and copies the axis-angle
// quaternion to gp+4268+48*i+32 (=gp+4300+48*i).
//
// Translation is verbatim from wcar-tiger_ir2.asm:2967-3099 (mips2c
// auto-emit; valid since IR2 only failed at the type-prop layer).
namespace method_115_v_tiger {
struct Cache {
  void* cos;                   // cos
  void* quaternion_axis_angle; // quaternion-axis-angle!
  void* quaternion_copy;       // quaternion-copy!
  void* quaternion_set;        // quaternion-set!
  void* sin;                   // sin
} cache;

u64 execute(void* ctxt) {
  auto* c = (ExecutionContext*)ctxt;
  bool bc = false;
  u32 call_addr = 0;
  c->daddiu(sp, sp, -192);                          // daddiu sp, sp, -192
  c->sd(ra, 0, sp);                                 // sd ra, 0(sp)
  c->sq(s0, 64, sp);                                // sq s0, 64(sp)
  c->sq(s1, 80, sp);                                // sq s1, 80(sp)
  c->sq(s2, 96, sp);                                // sq s2, 96(sp)
  c->sq(s3, 112, sp);                               // sq s3, 112(sp)
  c->sq(s4, 128, sp);                               // sq s4, 128(sp)
  c->sq(s5, 144, sp);                               // sq s5, 144(sp)
  c->sq(gp, 160, sp);                               // sq gp, 160(sp)
  c->swc1(f30, 176, sp);                            // swc1 f30, 176(sp)
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
  c->daddiu(a0, v1, 16);                            // daddiu a0, v1, 16  (= gp+4124)
  c->daddu(a1, r0, s5);                             // daddu a1, r0, s5
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9 (quaternion-copy!)
  c->gprs[v1].du64[0] = 0;                          // or v1, r0, r0
  c->daddiu(s5, sp, 32);                            // daddiu s5, sp, 32
  c->daddiu(v1, s5, 16);                            // daddiu v1, s5, 16 (= sp+48)
  // Constants block: (-1740.8, -1740.8, -2048.0, -2048.0)
  c->lui(a0, -15079);                               // lui a0, -15079 (=0xc4d9)
  c->ori(a0, a0, 39322);                            // ori a0, a0, 39322 (=0x999a; -1740.8)
  c->mtc1(f0, a0);                                  // mtc1 f0, a0
  c->swc1(f0, 0, v1);                               // swc1 f0, 0(v1)
  c->lui(a0, -15079);                               // lui a0, -15079
  c->ori(a0, a0, 39322);                            // ori a0, a0, 39322
  c->mtc1(f0, a0);                                  // mtc1 f0, a0
  c->swc1(f0, 4, v1);                               // swc1 f0, 4(v1)
  c->lui(a0, -15040);                               // lui a0, -15040 (=0xc500; -2048.0)
  c->mtc1(f0, a0);                                  // mtc1 f0, a0
  c->swc1(f0, 8, v1);                               // swc1 f0, 8(v1)
  c->lui(a0, -15040);                               // lui a0, -15040
  c->mtc1(f0, a0);                                  // mtc1 f0, a0
  c->swc1(f0, 12, v1);                              // swc1 f0, 12(v1)
  c->addiu(s4, r0, 0);                              // addiu s4, r0, 0
  // beq r0, r0, L36 (always taken, jumps over body to test)
  goto loop_test;

loop_body:
  // L35:
  c->addiu(v1, r0, 288);                            // addiu v1, r0, 288
  c->mult3(v1, v1, s4);                             // mult3 v1, v1, s4
  c->daddiu(v1, v1, 2476);                          // daddiu v1, v1, 2476
  c->daddu(s2, v1, gp);                             // s2 = gp + 2476 + 288*s4 (wheel-state)
  c->lwu(s3, 0, s2);                                // s3 = wheel-info ptr
  c->load_symbol2(t9, cache.quaternion_axis_angle); // lw t9, quaternion-axis-angle!
  c->daddu(a0, r0, s5);                             // a0 = s5 (sp+32)
  c->addiu(a1, r0, 0);                              // a1 = 0
  c->lwc1(f0, 204, s2);                             // f0 = (l.f +204 s2)
  c->mfc1(a2, f0);                                  // a2 = f0
  c->addiu(a3, r0, 0);                              // a3 = 0
  c->lwc1(f0, 192, s2);                             // f0 = (l.f +192 s2)
  c->mfc1(t0, f0);                                  // t0 = f0
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9 (quaternion-axis-angle!)
  c->addiu(v1, r0, 48);                             // addiu v1, r0, 48
  c->mult3(v1, v1, s4);                             // mult3 v1, v1, s4
  c->daddiu(v1, v1, 4268);                          // daddiu v1, v1, 4268
  c->daddu(v1, v1, gp);                             // v1 = gp + 4268 + 48*s4
  c->dsll(a0, s4, 2);                               // dsll a0, s4, 2
  c->daddu(a0, a0, s5);                             // a0 = s5 + s4*4 (sp+32 + s4*4)
  c->lwc1(f0, 16, a0);                              // f0 = (l.f +16 a0) = sp+48+s4*4 (constant scratch)
  c->lui(a0, 16256);                                // lui a0, 16256 (= 1.0)
  c->mtc1(f1, a0);                                  // mtc1 f1, a0
  c->lwc1(f2, 184, s2);                             // lwc1 f2, 184(s2)
  c->subs(f1, f1, f2);                              // f1 = 1.0 - (l.f +184 s2)
  c->lwc1(f2, 48, s3);                              // lwc1 f2, 48(s3)
  c->muls(f1, f1, f2);                              // f1 = f1 * (l.f +48 s3)
  c->adds(f0, f0, f1);                              // f0 = f0 + f1
  c->swc1(f0, 20, v1);                              // swc1 f0, 20(v1) -- gp+4288+48*s4
  c->load_symbol2(t9, cache.quaternion_copy);       // lw t9, quaternion-copy!
  c->daddiu(a0, v1, 32);                            // daddiu a0, v1, 32 (= gp+4300+48*s4)
  c->daddu(a1, r0, s5);                             // daddu a1, r0, s5
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9 (quaternion-copy!)
  c->gprs[v1].du64[0] = 0;                          // or v1, r0, r0
  c->daddiu(s4, s4, 1);                             // daddiu s4, s4, 1

loop_test:
  // L36:
  c->slti(v1, s4, 4);                               // slti v1, s4, 4
  bc = c->sgpr64(v1) != 0;                          // bne v1, r0, L35
  if (bc) { goto loop_body; }

  // B3:
  c->mov64(v1, s7);                                 // or v1, s7, r0
  c->mov64(v1, s7);                                 // or v1, s7, r0
  c->gprs[v0].du64[0] = 0;                          // or v0, r0, r0
  c->ld(ra, 0, sp);                                 // ld ra, 0(sp)
  c->lwc1(f30, 176, sp);                            // lwc1 f30, 176(sp)
  c->lq(gp, 160, sp);                               // lq gp, 160(sp)
  c->lq(s5, 144, sp);                               // lq s5, 144(sp)
  c->lq(s4, 128, sp);                               // lq s4, 128(sp)
  c->lq(s3, 112, sp);                               // lq s3, 112(sp)
  c->lq(s2, 96, sp);                                // lq s2, 96(sp)
  c->lq(s1, 80, sp);                                // lq s1, 80(sp)
  c->lq(s0, 64, sp);                                // lq s0, 64(sp)
  //jr ra                                           // jr ra
  c->daddiu(sp, sp, 192);                           // daddiu sp, sp, 192
  goto end_of_function;
end_of_function:
  return c->gprs[v0].du64[0];
}

void link() {
  cache.cos = intern_from_c(-1, 0, "cos").c();
  cache.quaternion_axis_angle = intern_from_c(-1, 0, "quaternion-axis-angle!").c();
  cache.quaternion_copy = intern_from_c(-1, 0, "quaternion-copy!").c();
  cache.quaternion_set = intern_from_c(-1, 0, "quaternion-set!").c();
  cache.sin = intern_from_c(-1, 0, "sin").c();
  gLinkedFunctionTable.reg("(method 115 v-tiger)", execute, 192);
}

} // namespace method_115_v_tiger
} // namespace Mips2C
