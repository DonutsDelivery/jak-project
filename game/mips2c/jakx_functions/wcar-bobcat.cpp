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
} // namespace Mips2C
