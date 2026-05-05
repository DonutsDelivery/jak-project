//--------------------------MIPS2C---------------------
// clang-format off
#include "game/mips2c/mips2c_private.h"
#include "game/kernel/jakx/kscheme.h"
using ::jakx::intern_from_c;
namespace Mips2C::jakx {
namespace method_64_wvehicle {
struct Cache {
  void* default_dead_pool; // *default-dead-pool*
  void* fake_scratchpad_data; // *fake-scratchpad-data*
  void* part_group_id_table; // *part-group-id-table*
  void* part_local_space_engine; // *part-local-space-engine*
  void* rigid_body_queue_manager; // *rigid-body-queue-manager*
  void* sp_particle_system_2d; // *sp-particle-system-2d*
  void* stdebug; // *stdebug*
  void* find_parent_method; // find-parent-method
  void* format; // format
  void* gunmount_drawable_init_by_other; // gunmount-drawable-init-by-other
  void* gunmount_generic_drawable; // gunmount-generic-drawable
  void* local_space_proc_joint; // local-space-proc-joint
  void* matrix_identity; // matrix-identity!
  void* process; // process
  void* quaternion_copy; // quaternion-copy!
  void* run_function_in_process; // run-function-in-process
  void* sparticle_subsampler; // sparticle-subsampler
  void* type; // type?
  void* v_drone; // v-drone
  void* vehicle_antenna_spawn; // vehicle-antenna-spawn
  void* wvehicle; // wvehicle
} cache;

u64 execute(void* ctxt) {
  auto* c = (ExecutionContext*)ctxt;
  bool bc = false;
  u32 call_addr = 0;
  bool cop1_bc = false;
  c->daddiu(sp, sp, -208);                          // daddiu sp, sp, -208
  c->sd(ra, 0, sp);                                 // sd ra, 0(sp)
  c->sd(fp, 8, sp);                                 // sd fp, 8(sp)
  c->mov64(fp, t9);                                 // or fp, t9, r0
  c->sq(s3, 144, sp);                               // sq s3, 144(sp)
  c->sq(s4, 160, sp);                               // sq s4, 160(sp)
  c->sq(s5, 176, sp);                               // sq s5, 176(sp)
  c->sq(gp, 192, sp);                               // sq gp, 192(sp)
  c->mov64(gp, a0);                                 // or gp, a0, r0
  c->mov64(s5, a1);                                 // or s5, a1, r0
  c->sw(s5, 252, gp);                               // sw s5, 252(gp)
  c->addiu(s4, r0, 0);                              // addiu s4, r0, 0
  //beq r0, r0, L18                                 // beq r0, r0, L18
  // nop                                            // sll r0, r0, 0
  goto block_5;                                     // branch always

  
block_1:
  c->ld(v1, 260, gp);                               // ld v1, 260(gp)
  c->andi(v1, v1, 1024);                            // andi v1, v1, 1024
  bc = c->sgpr64(v1) == 0;                          // beq v1, r0, L16
  // nop                                            // sll r0, r0, 0
  if (bc) {goto block_3;}                           // branch non-likely

  c->lui(v1, 16256);                                // lui v1, 16256
  //beq r0, r0, L17                                 // beq r0, r0, L17
  // nop                                            // sll r0, r0, 0
  goto block_4;                                     // branch always

  
block_3:
  c->lui(v1, 16128);                                // lui v1, 16128
  
block_4:
  c->mtc1(f0, v1);                                  // mtc1 f0, v1
  c->load_symbol2(v1, cache.sparticle_subsampler);  // lw v1, sparticle-subsampler(s7)
  c->lwu(t9, 16, v1);                               // lwu t9, 16(v1)
  c->load_symbol_addr(a0, cache.process);           // daddiu a0, s7, process
  c->load_symbol2(a1, cache.sparticle_subsampler);  // lw a1, sparticle-subsampler(s7)
  c->load_symbol2(a2, cache.sp_particle_system_2d); // lw a2, *sp-particle-system-2d*(s7)
  c->addiu(a3, r0, 263);                            // addiu a3, r0, 263
  c->lui(v1, 16384);                                // lui v1, 16384
  c->mtc1(f1, v1);                                  // mtc1 f1, v1
  c->muls(f0, f1, f0);                              // mul.s f0, f1, f0
  c->mfc1(t0, f0);                                  // mfc1 t0, f0
  c->daddiu(t1, s7, 4);                             // daddiu t1, s7, #t
  c->addiu(t2, r0, 0);                              // addiu t2, r0, 0
  c->mov64(t3, s6);                                 // or t3, s6, r0
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->dsll(v1, s4, 2);                               // dsll v1, s4, 2
  c->daddu(v1, v1, gp);                             // daddu v1, v1, gp
  c->sw(v0, 4596, v1);                              // sw v0, 4596(v1)
  c->mov64(v1, v0);                                 // or v1, v0, r0
  c->daddiu(s4, s4, 1);                             // daddiu s4, s4, 1
  
block_5:
  c->slti(v1, s4, 2);                               // slti v1, s4, 2
  bc = c->sgpr64(v1) != 0;                          // bne v1, r0, L15
  // nop                                            // sll r0, r0, 0
  if (bc) {goto block_1;}                           // branch non-likely

  c->mov64(v1, s7);                                 // or v1, s7, r0
  c->mov64(v1, s7);                                 // or v1, s7, r0
  c->lui(v1, -16385);                               // lui v1, -16385
  c->ori(v1, v1, 65535);                            // ori v1, v1, 65535
  c->ld(a0, 260, gp);                               // ld a0, 260(gp)
  c->and_(v1, v1, a0);                              // and v1, v1, a0
  c->sd(v1, 260, gp);                               // sd v1, 260(gp)
  c->daddiu(s4, sp, 16);                            // daddiu s4, sp, 16
  c->daddu(v1, r0, s4);                             // daddu v1, r0, s4
  c->lwu(a0, 184, gp);                              // lwu a0, 184(gp)
  c->daddiu(a0, a0, 12);                            // daddiu a0, a0, 12
  c->lq(a0, 0, a0);                                 // lq a0, 0(a0)
  c->sq(a0, 0, v1);                                 // sq a0, 0(v1)
  c->load_symbol2(t9, cache.quaternion_copy);       // lw t9, quaternion-copy!(s7)
  c->daddiu(a0, s4, 16);                            // daddiu a0, s4, 16
  c->lwu(v1, 184, gp);                              // lwu v1, 184(gp)
  c->daddiu(a1, v1, 28);                            // daddiu a1, v1, 28
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mov64(a0, gp);                                 // or a0, gp, r0
  c->lwu(v1, -4, a0);                               // lwu v1, -4(a0)
  c->lwu(t9, 460, v1);                              // lwu t9, 460(v1)
  c->daddu(a1, r0, s4);                             // daddu a1, r0, s4
  c->daddiu(a2, s4, 16);                            // daddiu a2, s4, 16
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mov64(v1, v0);                                 // or v1, v0, r0
  c->addiu(v1, r0, 0);                              // addiu v1, r0, 0
  //beq r0, r0, L20                                 // beq r0, r0, L20
  // nop                                            // sll r0, r0, 0
  goto block_8;                                     // branch always

  
block_7:
  c->addiu(a0, r0, 288);                            // addiu a0, r0, 288
  c->mult3(a0, a0, v1);                             // mult3 a0, a0, v1
  c->daddiu(a0, a0, 2476);                          // daddiu a0, a0, 2476
  c->daddu(a0, a0, gp);                             // daddu a0, a0, gp
  c->sd(s7, 8, a0);                                 // sd s7, 8(a0)
  c->sd(s7, 280, a0);                               // sd s7, 280(a0)
  c->mov64(a0, s7);                                 // or a0, s7, r0
  c->daddiu(v1, v1, 1);                             // daddiu v1, v1, 1
  
block_8:
  c->slti(a0, v1, 4);                               // slti a0, v1, 4
  bc = c->sgpr64(a0) != 0;                          // bne a0, r0, L19
  // nop                                            // sll r0, r0, 0
  if (bc) {goto block_7;}                           // branch non-likely

  c->mov64(v1, s7);                                 // or v1, s7, r0
  c->mov64(v1, s7);                                 // or v1, s7, r0
  c->sd(s7, 2148, gp);                              // sd s7, 2148(gp)
  c->sd(s7, 2156, gp);                              // sd s7, 2156(gp)
  c->sd(s7, 3924, gp);                              // sd s7, 3924(gp)
  c->sd(s7, 3932, gp);                              // sd s7, 3932(gp)
  c->sw(r0, 3880, gp);                              // sw r0, 3880(gp)
  c->sw(r0, 3860, gp);                              // sw r0, 3860(gp)
  c->sw(r0, 3864, gp);                              // sw r0, 3864(gp)
  c->sw(r0, 4652, gp);                              // sw r0, 4652(gp)
  c->load_symbol2(t9, cache.find_parent_method);    // lw t9, find-parent-method(s7)
  c->load_symbol2(a0, cache.wvehicle);              // lw a0, wvehicle(s7)
  c->addiu(a1, r0, 64);                             // addiu a1, r0, 64
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mov64(t9, v0);                                 // or t9, v0, r0
  c->mov64(a0, gp);                                 // or a0, gp, r0
  c->mov64(a1, s5);                                 // or a1, s5, r0
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->sw(s7, 468, gp);                               // sw s7, 468(gp)
  c->mtc1(f0, r0);                                  // mtc1 f0, r0
  c->swc1(f0, 2380, gp);                            // swc1 f0, 2380(gp)
  c->lui(v1, 16256);                                // lui v1, 16256
  c->mtc1(f0, v1);                                  // mtc1 f0, v1
  c->swc1(f0, 2356, gp);                            // swc1 f0, 2356(gp)
  c->addiu(v1, r0, 1);                              // addiu v1, r0, 1
  c->sb(v1, 2461, gp);                              // sb v1, 2461(gp)
  c->mov64(a0, gp);                                 // or a0, gp, r0
  c->lwu(v1, -4, a0);                               // lwu v1, -4(a0)
  c->lwu(t9, 916, v1);                              // lwu t9, 916(v1)
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mov64(v1, v0);                                 // or v1, v0, r0
  c->lui(v1, 16256);                                // lui v1, 16256
  c->mtc1(f0, v1);                                  // mtc1 f0, v1
  c->swc1(f0, 2428, gp);                            // swc1 f0, 2428(gp)
  c->mtc1(f0, r0);                                  // mtc1 f0, r0
  c->swc1(f0, 2432, gp);                            // swc1 f0, 2432(gp)
  c->lui(v1, 16256);                                // lui v1, 16256
  c->mtc1(f0, v1);                                  // mtc1 f0, v1
  c->swc1(f0, 2444, gp);                            // swc1 f0, 2444(gp)
  c->lui(v1, 16256);                                // lui v1, 16256
  c->mtc1(f0, v1);                                  // mtc1 f0, v1
  c->swc1(f0, 4100, gp);                            // swc1 f0, 4100(gp)
  c->lwu(v1, 228, gp);                              // lwu v1, 228(gp)
  c->lhu(v1, 0, v1);                                // lhu v1, 0(v1)
  c->ori(v1, v1, 4128);                             // ori v1, v1, 4128
  c->lwu(a0, 228, gp);                              // lwu a0, 228(gp)
  c->sh(v1, 0, a0);                                 // sh v1, 0(a0)
  c->daddiu(v1, sp, 48);                            // daddiu v1, sp, 48
  c->lwu(a0, 184, gp);                              // lwu a0, 184(gp)
  c->daddiu(a1, a0, 60);                            // daddiu a1, a0, 60
  c->lwu(a0, 228, gp);                              // lwu a0, 228(gp)
  c->daddiu(a0, a0, 204);                           // daddiu a0, a0, 204
  c->lwc1(f0, 0, a1);                               // lwc1 f0, 0(a1)
  c->lwc1(f1, 4, a1);                               // lwc1 f1, 4(a1)
  c->lwc1(f2, 8, a1);                               // lwc1 f2, 8(a1)
  c->lwc1(f3, 0, a0);                               // lwc1 f3, 0(a0)
  c->lwc1(f4, 4, a0);                               // lwc1 f4, 4(a0)
  c->lwc1(f5, 8, a0);                               // lwc1 f5, 8(a0)
  // Unknown instr: mula.s f0, f3
  // Unknown instr: madda.s f1, f4
  // Unknown instr: madd.s f0, f2, f5
  c->mfc1(a0, f0);                                  // mfc1 a0, f0
  c->mtc1(f0, a0);                                  // mtc1 f0, a0
  c->swc1(f0, 12, v1);                              // swc1 f0, 12(v1)
  c->sb(r0, 0, v1);                                 // sb r0, 0(v1)
  c->mtc1(f0, r0);                                  // mtc1 f0, r0
  c->swc1(f0, 4, v1);                               // swc1 f0, 4(v1)
  c->addiu(a0, r0, 0);                              // addiu a0, r0, 0
  //beq r0, r0, L25                                 // beq r0, r0, L25
  // nop                                            // sll r0, r0, 0
  goto block_16;                                    // branch always

  
block_10:
  c->addiu(a1, r0, 288);                            // addiu a1, r0, 288
  c->mult3(a1, a1, a0);                             // mult3 a1, a1, a0
  c->daddiu(a1, a1, 2476);                          // daddiu a1, a1, 2476
  c->daddu(a1, a1, gp);                             // daddu a1, a1, gp
  c->lwu(a2, 0, a1);                                // lwu a2, 0(a1)
  c->addiu(a3, r0, 1);                              // addiu a3, r0, 1
  c->andi(t0, a0, 1);                               // andi t0, a0, 1
  bc = c->sgpr64(t0) != c->sgpr64(a3);              // bne t0, a3, L22
  // nop                                            // sll r0, r0, 0
  if (bc) {goto block_12;}                          // branch non-likely

  c->lui(a3, -16512);                               // lui a3, -16512
  //beq r0, r0, L23                                 // beq r0, r0, L23
  // nop                                            // sll r0, r0, 0
  goto block_13;                                    // branch always

  
block_12:
  c->lui(a3, 16256);                                // lui a3, 16256
  
block_13:
  c->mtc1(f0, a3);                                  // mtc1 f0, a3
  c->swc1(f0, 204, a1);                             // swc1 f0, 204(a1)
  c->sw(s7, 176, a1);                               // sw s7, 176(a1)
  c->lwc1(f0, 32, a2);                              // lwc1 f0, 32(a2)
  c->lwc1(f1, 44, a2);                              // lwc1 f1, 44(a2)
  c->muls(f0, f0, f1);                              // mul.s f0, f0, f1
  c->swc1(f0, 8, v1);                               // swc1 f0, 8(v1)
  c->lwc1(f0, 12, v1);                              // lwc1 f0, 12(v1)
  c->lwc1(f1, 8, v1);                               // lwc1 f1, 8(v1)
  c->divs(f0, f0, f1);                              // div.s f0, f0, f1
  c->swc1(f0, 200, a1);                             // swc1 f0, 200(a1)
  c->ld(a3, 16, a2);                                // ld a3, 16(a2)
  c->andi(a3, a3, 1);                               // andi a3, a3, 1
  bc = c->sgpr64(a3) == 0;                          // beq a3, r0, L24
  c->mov64(a3, s7);                                 // or a3, s7, r0
  if (bc) {goto block_15;}                          // branch non-likely

  c->lb(a3, 0, v1);                                 // lb a3, 0(v1)
  c->daddiu(a3, a3, 1);                             // daddiu a3, a3, 1
  c->sb(a3, 0, v1);                                 // sb a3, 0(v1)
  c->lwc1(f0, 4, v1);                               // lwc1 f0, 4(v1)
  c->lwc1(f1, 8, v1);                               // lwc1 f1, 8(v1)
  c->adds(f0, f0, f1);                              // add.s f0, f0, f1
  c->swc1(f0, 4, v1);                               // swc1 f0, 4(v1)
  c->lui(a3, 16256);                                // lui a3, 16256
  c->mtc1(f0, a3);                                  // mtc1 f0, a3
  c->swc1(f0, 220, a1);                             // swc1 f0, 220(a1)
  c->mfc1(a3, f0);                                  // mfc1 a3, f0
  
block_15:
  c->lwc1(f0, 28, a2);                              // lwc1 f0, 28(a2)
  c->swc1(f0, 188, a1);                             // swc1 f0, 188(a1)
  c->daddiu(a2, a1, 32);                            // daddiu a2, a1, 32
  // daddiu a3, fp, L374 — const vector (0, -1.0, 0, 1.0); hand-emit:
  c->lui(a3, 0xbf80); c->sw(r0, 0, a2); c->sw(a3, 4, a2);
  c->sw(r0, 8, a2);   c->lui(a3, 0x3f80); c->sw(a3, 12, a2);
  c->lq(a3, 0, a2);                                 // sq a3, 0(a2) (reload as 128b)
  c->daddiu(a1, a1, 48);                            // daddiu a1, a1, 48
  // daddiu a2, fp, L373 — const vector (1.0, 0, 0, 1.0); hand-emit:
  c->lui(a2, 0x3f80); c->sw(a2, 0, a1); c->sw(r0, 4, a1);
  c->sw(r0, 8, a1);   c->sw(a2, 12, a1);
  c->lq(a2, 0, a1);                                 // sq a2, 0(a1) (reload as 128b)
  c->daddiu(a0, a0, 1);                             // daddiu a0, a0, 1
  
block_16:
  c->slti(a1, a0, 4);                               // slti a1, a0, 4
  bc = c->sgpr64(a1) != 0;                          // bne a1, r0, L21
  // nop                                            // sll r0, r0, 0
  if (bc) {goto block_10;}                          // branch non-likely

  c->mov64(a0, s7);                                 // or a0, s7, r0
  c->mov64(a0, s7);                                 // or a0, s7, r0
  c->lwc1(f0, 4, v1);                               // lwc1 f0, 4(v1)
  c->lb(a0, 0, v1);                                 // lb a0, 0(v1)
  c->mtc1(f1, a0);                                  // mtc1 f1, a0
  c->cvtsw(f1, f1);                                 // cvt.s.w f1, f1
  c->divs(f0, f0, f1);                              // div.s f0, f0, f1
  c->swc1(f0, 2400, gp);                            // swc1 f0, 2400(gp)
  c->lwc1(f0, 12, v1);                              // lwc1 f0, 12(v1)
  c->lwc1(f1, 2400, gp);                            // lwc1 f1, 2400(gp)
  c->divs(f0, f0, f1);                              // div.s f0, f0, f1
  c->swc1(f0, 2360, gp);                            // swc1 f0, 2360(gp)
  c->mtc1(f0, r0);                                  // mtc1 f0, r0
  c->lwc1(f1, 12, v1);                              // lwc1 f1, 12(v1)
  cop1_bc = c->fprs[f0] < c->fprs[f1];              // c.lt.s f0, f1
  bc = !cop1_bc;                                    // bc1f L26
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_19;}                          // branch non-likely

  c->lb(v1, 312, s5);                               // lb v1, 312(s5)
  c->daddiu(v1, v1, -1);                            // daddiu v1, v1, -1
  c->sb(v1, 2461, gp);                              // sb v1, 2461(gp)
  c->lwc1(f0, 220, s5);                             // lwc1 f0, 220(s5)
  c->lui(v1, 15830);                                // lui v1, 15830
  c->ori(v1, v1, 30544);                            // ori v1, v1, 30544
  c->mtc1(f1, v1);                                  // mtc1 f1, v1
  c->muls(f0, f1, f0);                              // mul.s f0, f1, f0
  c->mfc1(v1, f0);                                  // mfc1 v1, f0
  c->mtc1(f0, v1);                                  // mtc1 f0, v1
  c->swc1(f0, 2324, gp);                            // swc1 f0, 2324(gp)
  c->mfc1(v1, f0);                                  // mfc1 v1, f0
  
block_19:
  c->daddiu(a0, sp, 64);                            // daddiu a0, sp, 64
  c->lwu(v1, 184, gp);                              // lwu v1, 184(gp)
  c->lwu(v1, 156, v1);                              // lwu v1, 156(v1)
  c->lui(a1, -128);                                 // lui a1, -128
  c->mtc1(f0, a1);                                  // mtc1 f0, a1
  c->swc1(f0, 32, a0);                              // swc1 f0, 32(a0)
  c->lui(a1, 32640);                                // lui a1, 32640
  c->mtc1(f0, a1);                                  // mtc1 f0, a1
  c->swc1(f0, 36, a0);                              // swc1 f0, 36(a0)
  c->lui(a1, -128);                                 // lui a1, -128
  c->mtc1(f0, a1);                                  // mtc1 f0, a1
  c->swc1(f0, 40, a0);                              // swc1 f0, 40(a0)
  c->lui(a1, 32640);                                // lui a1, 32640
  c->mtc1(f0, a1);                                  // mtc1 f0, a1
  c->swc1(f0, 44, a0);                              // swc1 f0, 44(a0)
  c->addiu(a1, r0, 0);                              // addiu a1, r0, 0
  //beq r0, r0, L28                                 // beq r0, r0, L28
  // nop                                            // sll r0, r0, 0
  goto block_21;                                    // branch always

  
block_20:
  c->daddu(a2, r0, a0);                             // daddu a2, r0, a0
  c->addiu(a3, r0, 80);                             // addiu a3, r0, 80
  c->dsll(t0, a1, 1);                               // dsll t0, a1, 1
  c->mult3(a3, a3, t0);                             // mult3 a3, a3, t0
  c->daddiu(a3, a3, 44);                            // daddiu a3, a3, 44
  c->lwu(t0, 64, v1);                               // lwu t0, 64(v1)
  c->daddu(a3, a3, t0);                             // daddu a3, a3, t0
  c->lq(a3, 0, a3);                                 // lq a3, 0(a3)
  c->sq(a3, 0, a2);                                 // sq a3, 0(a2)
  c->lwc1(f0, 4, a0);                               // lwc1 f0, 4(a0)
  c->lui(a2, -16576);                               // lui a2, -16576
  c->mtc1(f1, a2);                                  // mtc1 f1, a2
  c->lwc1(f2, 12, a0);                              // lwc1 f2, 12(a0)
  c->muls(f1, f1, f2);                              // mul.s f1, f1, f2
  c->adds(f0, f0, f1);                              // add.s f0, f0, f1
  c->swc1(f0, 16, a0);                              // swc1 f0, 16(a0)
  c->lwc1(f0, 4, a0);                               // lwc1 f0, 4(a0)
  c->lui(a2, -16768);                               // lui a2, -16768
  c->mtc1(f1, a2);                                  // mtc1 f1, a2
  c->lwc1(f2, 12, a0);                              // lwc1 f2, 12(a0)
  c->muls(f1, f1, f2);                              // mul.s f1, f1, f2
  c->adds(f0, f0, f1);                              // add.s f0, f0, f1
  c->swc1(f0, 20, a0);                              // swc1 f0, 20(a0)
  c->lwc1(f0, 32, a0);                              // lwc1 f0, 32(a0)
  c->lwc1(f1, 16, a0);                              // lwc1 f1, 16(a0)
  c->maxs(f0, f0, f1);                              // max.s f0, f0, f1
  c->swc1(f0, 32, a0);                              // swc1 f0, 32(a0)
  c->lwc1(f0, 36, a0);                              // lwc1 f0, 36(a0)
  c->lwc1(f1, 20, a0);                              // lwc1 f1, 20(a0)
  c->mins(f0, f0, f1);                              // min.s f0, f0, f1
  c->swc1(f0, 36, a0);                              // swc1 f0, 36(a0)
  c->lwc1(f0, 0, a0);                               // lwc1 f0, 0(a0)
  c->lui(a2, 16000);                                // lui a2, 16000
  c->mtc1(f1, a2);                                  // mtc1 f1, a2
  c->lwc1(f2, 12, a0);                              // lwc1 f2, 12(a0)
  c->muls(f1, f1, f2);                              // mul.s f1, f1, f2
  c->adds(f0, f0, f1);                              // add.s f0, f0, f1
  c->swc1(f0, 24, a0);                              // swc1 f0, 24(a0)
  c->lwc1(f0, 0, a0);                               // lwc1 f0, 0(a0)
  c->lui(a2, 16192);                                // lui a2, 16192
  c->mtc1(f1, a2);                                  // mtc1 f1, a2
  c->lwc1(f2, 12, a0);                              // lwc1 f2, 12(a0)
  c->muls(f1, f1, f2);                              // mul.s f1, f1, f2
  c->adds(f0, f0, f1);                              // add.s f0, f0, f1
  c->swc1(f0, 28, a0);                              // swc1 f0, 28(a0)
  c->lwc1(f0, 40, a0);                              // lwc1 f0, 40(a0)
  c->lwc1(f1, 24, a0);                              // lwc1 f1, 24(a0)
  c->maxs(f0, f0, f1);                              // max.s f0, f0, f1
  c->swc1(f0, 40, a0);                              // swc1 f0, 40(a0)
  c->lwc1(f0, 44, a0);                              // lwc1 f0, 44(a0)
  c->lwc1(f1, 28, a0);                              // lwc1 f1, 28(a0)
  c->mins(f0, f0, f1);                              // min.s f0, f0, f1
  c->swc1(f0, 44, a0);                              // swc1 f0, 44(a0)
  c->daddiu(a1, a1, 1);                             // daddiu a1, a1, 1
  
block_21:
  c->slti(a2, a1, 2);                               // slti a2, a1, 2
  bc = c->sgpr64(a2) != 0;                          // bne a2, r0, L27
  // nop                                            // sll r0, r0, 0
  if (bc) {goto block_20;}                          // branch non-likely

  c->mov64(a1, s7);                                 // or a1, s7, r0
  c->mov64(a1, s7);                                 // or a1, s7, r0
  c->lui(a1, 16128);                                // lui a1, 16128
  c->mtc1(f0, a1);                                  // mtc1 f0, a1
  c->lwc1(f1, 32, a0);                              // lwc1 f1, 32(a0)
  c->lwc1(f2, 36, a0);                              // lwc1 f2, 36(a0)
  c->adds(f1, f1, f2);                              // add.s f1, f1, f2
  c->muls(f0, f0, f1);                              // mul.s f0, f0, f1
  c->swc1(f0, 676, gp);                             // swc1 f0, 676(gp)
  c->lui(a1, 16128);                                // lui a1, 16128
  c->mtc1(f0, a1);                                  // mtc1 f0, a1
  c->lwc1(f1, 40, a0);                              // lwc1 f1, 40(a0)
  c->lwc1(f2, 44, a0);                              // lwc1 f2, 44(a0)
  c->adds(f1, f1, f2);                              // add.s f1, f1, f2
  c->muls(f0, f0, f1);                              // mul.s f0, f0, f1
  c->swc1(f0, 680, gp);                             // swc1 f0, 680(gp)
  c->addiu(a0, r0, 0);                              // addiu a0, r0, 0
  //beq r0, r0, L30                                 // beq r0, r0, L30
  // nop                                            // sll r0, r0, 0
  goto block_24;                                    // branch always

  
block_23:
  c->lwu(a1, 64, v1);                               // lwu a1, 64(v1)
  c->addiu(a2, r0, 80);                             // addiu a2, r0, 80
  c->mult3(a2, a2, a0);                             // mult3 a2, a2, a0
  c->daddu(a1, a1, a2);                             // daddu a1, a1, a2
  c->addiu(a2, r0, 1);                              // addiu a2, r0, 1
  c->sb(a2, 68, a1);                                // sb a2, 68(a1)
  c->daddiu(a2, a0, 2);                             // daddiu a2, a0, 2
  c->sb(a2, 69, a1);                                // sb a2, 69(a1)
  c->daddiu(a0, a0, 1);                             // daddiu a0, a0, 1
  
block_24:
  c->slti(a1, a0, 2);                               // slti a1, a0, 2
  bc = c->sgpr64(a1) != 0;                          // bne a1, r0, L29
  // nop                                            // sll r0, r0, 0
  if (bc) {goto block_23;}                          // branch non-likely

  c->mov64(v1, s7);                                 // or v1, s7, r0
  c->mov64(v1, s7);                                 // or v1, s7, r0
  c->addiu(s4, r0, 0);                              // addiu s4, r0, 0
  //beq r0, r0, L32                                 // beq r0, r0, L32
  // nop                                            // sll r0, r0, 0
  goto block_27;                                    // branch always

  
block_26:
  c->load_symbol2(v1, cache.part_group_id_table);   // lw v1, *part-group-id-table*(s7)
  c->lwu(a0, 920, v1);                              // lwu a0, 920(v1)
  c->lwu(v1, -4, a0);                               // lwu v1, -4(a0)
  c->lwu(t9, 52, v1);                               // lwu t9, 52(v1)
  c->mov64(a1, gp);                                 // or a1, gp, r0
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mov64(v1, v0);                                 // or v1, v0, r0
  c->dsll(a0, s4, 2);                               // dsll a0, s4, 2
  c->daddu(a0, a0, gp);                             // daddu a0, a0, gp
  c->sw(v1, 4604, a0);                              // sw v1, 4604(a0)
  c->load_symbol2(v1, cache.part_group_id_table);   // lw v1, *part-group-id-table*(s7)
  c->lwu(a0, 916, v1);                              // lwu a0, 916(v1)
  c->lwu(v1, -4, a0);                               // lwu v1, -4(a0)
  c->lwu(t9, 52, v1);                               // lwu t9, 52(v1)
  c->mov64(a1, gp);                                 // or a1, gp, r0
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mov64(v1, v0);                                 // or v1, v0, r0
  c->dsll(a0, s4, 2);                               // dsll a0, s4, 2
  c->daddu(a0, a0, gp);                             // daddu a0, a0, gp
  c->sw(v1, 4620, a0);                              // sw v1, 4620(a0)
  c->daddiu(s4, s4, 1);                             // daddiu s4, s4, 1
  
block_27:
  c->slti(v1, s4, 4);                               // slti v1, s4, 4
  bc = c->sgpr64(v1) != 0;                          // bne v1, r0, L31
  // nop                                            // sll r0, r0, 0
  if (bc) {goto block_26;}                          // branch non-likely

  c->mov64(v1, s7);                                 // or v1, s7, r0
  c->mov64(v1, s7);                                 // or v1, s7, r0
  c->addiu(v1, r0, 0);                              // addiu v1, r0, 0
  //beq r0, r0, L34                                 // beq r0, r0, L34
  // nop                                            // sll r0, r0, 0
  goto block_30;                                    // branch always

  
block_29:
  c->dsll(a0, v1, 3);                               // dsll a0, v1, 3
  c->daddu(a0, a0, gp);                             // daddu a0, a0, gp
  c->sd(s7, 3948, a0);                              // sd s7, 3948(a0)
  c->daddiu(v1, v1, 1);                             // daddiu v1, v1, 1
  
block_30:
  c->slti(a0, v1, 16);                              // slti a0, v1, 16
  bc = c->sgpr64(a0) != 0;                          // bne a0, r0, L33
  // nop                                            // sll r0, r0, 0
  if (bc) {goto block_29;}                          // branch non-likely

  c->mov64(v1, s7);                                 // or v1, s7, r0
  c->mov64(v1, s7);                                 // or v1, s7, r0
  c->daddiu(v1, gp, 3644);                          // daddiu v1, gp, 3644
  c->sqc2(vf0, 0, v1);                              // sqc2 vf0, 0(v1)
  c->lb(v1, 2116, gp);                              // lb v1, 2116(gp)
  c->slt(v1, v1, r0);                               // slt v1, v1, r0
  c->daddiu(a0, s7, 4);                             // daddiu a0, s7, 4
  c->movn(a0, s7, v1);                              // movn a0, s7, v1
  if (((s64)c->sgpr64(s7)) == ((s64)c->sgpr64(a0))) {// beql s7, a0, L35
    c->mov64(v1, a0);                               // or v1, a0, r0
    goto block_34;
  }
  
block_33:
  c->lb(v1, 2116, gp);                              // lb v1, 2116(gp)
  c->slti(a0, v1, 16);                              // slti a0, v1, 16
  c->daddiu(v1, s7, 4);                             // daddiu v1, s7, 4
  c->movz(v1, s7, a0);                              // movz v1, s7, a0
  
block_34:
  bc = c->sgpr64(s7) == c->sgpr64(v1);              // beq s7, v1, L36
  // nop                                            // sll r0, r0, 0
  if (bc) {goto block_36;}                          // branch non-likely

  c->lb(v1, 2116, gp);                              // lb v1, 2116(gp)
  c->dsubu(v1, r0, v1);                             // dsubu v1, r0, v1
  //beq r0, r0, L37                                 // beq r0, r0, L37
  // nop                                            // sll r0, r0, 0
  goto block_37;                                    // branch always

  
block_36:
  c->lb(v1, 2116, gp);                              // lb v1, 2116(gp)
  c->daddiu(v1, v1, -15);                           // daddiu v1, v1, -15
  
block_37:
  c->lui(a0, 15658);                                // lui a0, 15658
  c->ori(a0, a0, 43691);                            // ori a0, a0, 43691
  c->mtc1(f0, a0);                                  // mtc1 f0, a0
  c->mtc1(f1, v1);                                  // mtc1 f1, v1
  c->cvtsw(f1, f1);                                 // cvt.s.w f1, f1
  c->muls(f0, f0, f1);                              // mul.s f0, f0, f1
  c->swc1(f0, 4076, gp);                            // swc1 f0, 4076(gp)
  c->gprs[v1].du64[0] = 0;                          // or v1, r0, r0
  c->mov64(a0, gp);                                 // or a0, gp, r0
  c->lwu(v1, -4, a0);                               // lwu v1, -4(a0)
  c->lwu(t9, 744, v1);                              // lwu t9, 744(v1)
  c->lui(a1, 16256);                                // lui a1, 16256
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mov64(v1, v0);                                 // or v1, v0, r0
  c->sd(s7, 4500, gp);                              // sd s7, 4500(gp)
  c->sd(s7, 4508, gp);                              // sd s7, 4508(gp)
  c->sd(s7, 4516, gp);                              // sd s7, 4516(gp)
  c->sd(s7, 4524, gp);                              // sd s7, 4524(gp)
  c->sd(s7, 4532, gp);                              // sd s7, 4532(gp)
  c->sd(s7, 4540, gp);                              // sd s7, 4540(gp)
  c->sd(s7, 4548, gp);                              // sd s7, 4548(gp)
  c->sw(r0, 4580, gp);                              // sw r0, 4580(gp)
  c->sd(s7, 4468, gp);                              // sd s7, 4468(gp)
  c->sd(s7, 4476, gp);                              // sd s7, 4476(gp)
  c->sd(s7, 4556, gp);                              // sd s7, 4556(gp)
  c->sd(s7, 4564, gp);                              // sd s7, 4564(gp)
  c->load_symbol2(t9, cache.type);                  // lw t9, type?(s7)
  c->mov64(a0, gp);                                 // or a0, gp, r0
  c->load_symbol2(a1, cache.v_drone);               // lw a1, v-drone(s7)
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  bc = c->sgpr64(s7) != c->sgpr64(v0);              // bne s7, v0, L51
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_63;}                          // branch non-likely

  c->load_symbol2(a0, cache.default_dead_pool);     // lw a0, *default-dead-pool*(s7)
  c->lwu(v1, -4, a0);                               // lwu v1, -4(a0)
  c->lwu(t9, 76, v1);                               // lwu t9, 76(v1)
  c->load_symbol2(a1, cache.gunmount_generic_drawable);// lw a1, gunmount-generic-drawable(s7)
  c->addiu(a2, r0, 16384);                          // addiu a2, r0, 16384
  c->addiu(a3, r0, 1);                              // addiu a3, r0, 1
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mov64(s4, v0);                                 // or s4, v0, r0
  bc = c->sgpr64(s7) == c->sgpr64(s4);              // beq s7, s4, L38
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_40;}                          // branch non-likely

  c->load_symbol2(v1, cache.gunmount_generic_drawable);// lw v1, gunmount-generic-drawable(s7)
  c->lwu(t9, 52, v1);                               // lwu t9, 52(v1)
  c->mov64(a0, s4);                                 // or a0, s4, r0
  c->load_symbol2(a1, cache.rigid_body_queue_manager);// lw a1, *rigid-body-queue-manager*(s7)
  // daddiu a2, fp, L372  — string "gunmount-generic-drawable" (debug name arg); pass NULL
  c->mov64(a2, r0);
  get_fake_spad_addr2(v1, cache.fake_scratchpad_data, 0, c);// lui v1, 28672
  c->ori(a3, v1, 16384);                            // ori a3, v1, 16384
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->load_symbol2(t9, cache.run_function_in_process);// lw t9, run-function-in-process(s7)
  c->mov64(a0, s4);                                 // or a0, s4, r0
  c->load_symbol2(a1, cache.gunmount_drawable_init_by_other);// lw a1, gunmount-drawable-init-by-other(s7)
  c->mov64(a2, gp);                                 // or a2, gp, r0
  c->addiu(a3, r0, 0);                              // addiu a3, r0, 0
  c->addiu(t0, r0, 0);                              // addiu t0, r0, 0
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->lwu(v1, 28, s4);                               // lwu v1, 28(s4)
  
block_40:
  bc = c->sgpr64(s7) == c->sgpr64(v1);              // beq s7, v1, L39
  c->mov64(a0, s7);                                 // or a0, s7, r0
  if (bc) {goto block_42;}                          // branch non-likely

  c->lwu(v1, 0, v1);                                // lwu v1, 0(v1)
  c->lwu(a0, 32, v1);                               // lwu a0, 32(v1)
  
block_42:
  bc = c->sgpr64(s7) == c->sgpr64(a0);              // beq s7, a0, L40
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_44;}                          // branch non-likely

  c->lwu(v1, 28, a0);                               // lwu v1, 28(a0)
  
block_44:
  bc = c->sgpr64(s7) == c->sgpr64(v1);              // beq s7, v1, L41
  // nop                                            // sll r0, r0, 0
  if (bc) {goto block_46;}                          // branch non-likely

  c->lwu(a0, 0, v1);                                // lwu a0, 0(v1)
  c->lw(a0, 48, a0);                                // lw a0, 48(a0)
  c->dsll32(a0, a0, 0);                             // dsll32 a0, a0, 0
  //beq r0, r0, L42                                 // beq r0, r0, L42
  // nop                                            // sll r0, r0, 0
  goto block_47;                                    // branch always

  
block_46:
  c->addiu(a0, r0, 0);                              // addiu a0, r0, 0
  
block_47:
  c->sllv(v1, v1, r0);                              // sllv v1, v1, r0
  c->or_(v1, a0, v1);                               // or v1, a0, v1
  c->sd(v1, 4556, gp);                              // sd v1, 4556(gp)
  c->load_symbol2(a0, cache.default_dead_pool);     // lw a0, *default-dead-pool*(s7)
  c->lwu(v1, -4, a0);                               // lwu v1, -4(a0)
  c->lwu(t9, 76, v1);                               // lwu t9, 76(v1)
  c->load_symbol2(a1, cache.gunmount_generic_drawable);// lw a1, gunmount-generic-drawable(s7)
  c->addiu(a2, r0, 16384);                          // addiu a2, r0, 16384
  c->addiu(a3, r0, 1);                              // addiu a3, r0, 1
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mov64(s4, v0);                                 // or s4, v0, r0
  bc = c->sgpr64(s7) == c->sgpr64(s4);              // beq s7, s4, L43
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_49;}                          // branch non-likely

  c->load_symbol2(v1, cache.gunmount_generic_drawable);// lw v1, gunmount-generic-drawable(s7)
  c->lwu(t9, 52, v1);                               // lwu t9, 52(v1)
  c->mov64(a0, s4);                                 // or a0, s4, r0
  c->load_symbol2(a1, cache.rigid_body_queue_manager);// lw a1, *rigid-body-queue-manager*(s7)
  // daddiu a2, fp, L372  — string "gunmount-generic-drawable" (debug name arg); pass NULL
  c->mov64(a2, r0);
  get_fake_spad_addr2(v1, cache.fake_scratchpad_data, 0, c);// lui v1, 28672
  c->ori(a3, v1, 16384);                            // ori a3, v1, 16384
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->load_symbol2(t9, cache.run_function_in_process);// lw t9, run-function-in-process(s7)
  c->mov64(a0, s4);                                 // or a0, s4, r0
  c->load_symbol2(a1, cache.gunmount_drawable_init_by_other);// lw a1, gunmount-drawable-init-by-other(s7)
  c->mov64(a2, gp);                                 // or a2, gp, r0
  c->addiu(a3, r0, 1);                              // addiu a3, r0, 1
  c->addiu(t0, r0, 1);                              // addiu t0, r0, 1
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->lwu(v1, 28, s4);                               // lwu v1, 28(s4)
  
block_49:
  bc = c->sgpr64(s7) == c->sgpr64(v1);              // beq s7, v1, L44
  c->mov64(a0, s7);                                 // or a0, s7, r0
  if (bc) {goto block_51;}                          // branch non-likely

  c->lwu(v1, 0, v1);                                // lwu v1, 0(v1)
  c->lwu(a0, 32, v1);                               // lwu a0, 32(v1)
  
block_51:
  bc = c->sgpr64(s7) == c->sgpr64(a0);              // beq s7, a0, L45
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_53;}                          // branch non-likely

  c->lwu(v1, 28, a0);                               // lwu v1, 28(a0)
  
block_53:
  bc = c->sgpr64(s7) == c->sgpr64(v1);              // beq s7, v1, L46
  // nop                                            // sll r0, r0, 0
  if (bc) {goto block_55;}                          // branch non-likely

  c->lwu(a0, 0, v1);                                // lwu a0, 0(v1)
  c->lw(a0, 48, a0);                                // lw a0, 48(a0)
  c->dsll32(a0, a0, 0);                             // dsll32 a0, a0, 0
  //beq r0, r0, L47                                 // beq r0, r0, L47
  // nop                                            // sll r0, r0, 0
  goto block_56;                                    // branch always

  
block_55:
  c->addiu(a0, r0, 0);                              // addiu a0, r0, 0
  
block_56:
  c->sllv(v1, v1, r0);                              // sllv v1, v1, r0
  c->or_(v1, a0, v1);                               // or v1, a0, v1
  c->sd(v1, 4564, gp);                              // sd v1, 4564(gp)
  c->daddiu(v1, sp, 112);                           // daddiu v1, sp, 112
  c->daddu(a0, r0, v1);                             // daddu a0, r0, v1
  c->daddiu(a1, s5, 3168);                          // daddiu a1, s5, 3168
  c->lq(a1, 0, a1);                                 // lq a1, 0(a1)
  c->sq(a1, 0, a0);                                 // sq a1, 0(a0)
  c->lui(a0, -15005);                               // lui a0, -15005
  c->ori(a0, a0, 36409);                            // ori a0, a0, 36409
  c->mtc1(f0, a0);                                  // mtc1 f0, a0
  c->swc1(f0, 16, v1);                              // swc1 f0, 16(v1)
  c->sw(gp, 20, v1);                                // sw gp, 20(v1)
  c->sw(s7, 24, v1);                                // sw s7, 24(v1)
  c->lwu(a0, 64, gp);                               // lwu a0, 64(gp)
  c->sw(a0, 28, v1);                                // sw a0, 28(v1)
  c->daddu(a0, r0, v1);                             // daddu a0, r0, v1
  c->load_symbol2(t9, cache.vehicle_antenna_spawn); // lw t9, vehicle-antenna-spawn(s7)
  c->daddu(a0, r0, v1);                             // daddu a0, r0, v1
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mov64(a0, v0);                                 // or a0, v0, r0
  bc = c->sgpr64(s7) == c->sgpr64(a0);              // beq s7, a0, L51
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_63;}                          // branch non-likely

  bc = c->sgpr64(s7) == c->sgpr64(a0);              // beq s7, a0, L48
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_59;}                          // branch non-likely

  c->lwu(v1, 28, a0);                               // lwu v1, 28(a0)
  
block_59:
  bc = c->sgpr64(s7) == c->sgpr64(v1);              // beq s7, v1, L49
  // nop                                            // sll r0, r0, 0
  if (bc) {goto block_61;}                          // branch non-likely

  c->lwu(a0, 0, v1);                                // lwu a0, 0(v1)
  c->lw(a0, 48, a0);                                // lw a0, 48(a0)
  c->dsll32(a0, a0, 0);                             // dsll32 a0, a0, 0
  //beq r0, r0, L50                                 // beq r0, r0, L50
  // nop                                            // sll r0, r0, 0
  goto block_62;                                    // branch always

  
block_61:
  c->addiu(a0, r0, 0);                              // addiu a0, r0, 0
  
block_62:
  c->sllv(v1, v1, r0);                              // sllv v1, v1, r0
  c->or_(v1, a0, v1);                               // or v1, a0, v1
  c->sd(v1, 2148, gp);                              // sd v1, 2148(gp)
  
block_63:
  c->sd(s7, 4484, gp);                              // sd s7, 4484(gp)
  c->load_symbol2(v1, cache.part_group_id_table);   // lw v1, *part-group-id-table*(s7)
  c->lwu(a0, 1132, v1);                             // lwu a0, 1132(v1)
  c->lwu(v1, -4, a0);                               // lwu v1, -4(a0)
  c->lwu(t9, 52, v1);                               // lwu t9, 52(v1)
  c->mov64(a1, gp);                                 // or a1, gp, r0
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mov64(v1, v0);                                 // or v1, v0, r0
  c->sw(v1, 4588, gp);                              // sw v1, 4588(gp)
  c->sb(r0, 4592, gp);                              // sb r0, 4592(gp)
  c->load_symbol2(v1, cache.part_group_id_table);   // lw v1, *part-group-id-table*(s7)
  c->lwu(a0, 1104, v1);                             // lwu a0, 1104(v1)
  c->lwu(v1, -4, a0);                               // lwu v1, -4(a0)
  c->lwu(t9, 52, v1);                               // lwu t9, 52(v1)
  c->mov64(a1, gp);                                 // or a1, gp, r0
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mov64(v1, v0);                                 // or v1, v0, r0
  c->sw(v1, 4584, gp);                              // sw v1, 4584(gp)
  c->lwu(s5, 4584, gp);                             // lwu s5, 4584(gp)
  c->lwu(v1, -4, s5);                               // lwu v1, -4(s5)
  c->lwu(s4, 96, v1);                               // lwu s4, 96(v1)
  c->load_symbol2(a0, cache.part_local_space_engine);// lw a0, *part-local-space-engine*(s7)
  c->lwu(v1, -4, a0);                               // lwu v1, -4(a0)
  c->lwu(t9, 76, v1);                               // lwu t9, 76(v1)
  c->mov64(a1, gp);                                 // or a1, gp, r0
  c->load_symbol2(a2, cache.local_space_proc_joint);// lw a2, local-space-proc-joint(s7)
  c->addiu(a3, r0, 0);                              // addiu a3, r0, 0
  c->addiu(t0, r0, 0);                              // addiu t0, r0, 0
  c->addiu(t1, r0, 0);                              // addiu t1, r0, 0
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mov64(s3, v0);                                 // or s3, v0, r0
  c->mov64(a0, gp);                                 // or a0, gp, r0
  bc = c->sgpr64(s7) == c->sgpr64(a0);              // beq s7, a0, L52
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_65;}                          // branch non-likely

  c->lwu(v1, 28, a0);                               // lwu v1, 28(a0)
  
block_65:
  bc = c->sgpr64(s7) == c->sgpr64(v1);              // beq s7, v1, L53
  // nop                                            // sll r0, r0, 0
  if (bc) {goto block_67;}                          // branch non-likely

  c->lwu(a0, 0, v1);                                // lwu a0, 0(v1)
  c->lw(a0, 48, a0);                                // lw a0, 48(a0)
  c->dsll32(a0, a0, 0);                             // dsll32 a0, a0, 0
  //beq r0, r0, L54                                 // beq r0, r0, L54
  // nop                                            // sll r0, r0, 0
  goto block_68;                                    // branch always

  
block_67:
  c->addiu(a0, r0, 0);                              // addiu a0, r0, 0
  
block_68:
  c->sllv(v1, v1, r0);                              // sllv v1, v1, r0
  c->or_(v1, a0, v1);                               // or v1, a0, v1
  bc = c->sgpr64(s7) == c->sgpr64(s3);              // beq s7, s3, L59
  // nop                                            // sll r0, r0, 0
  if (bc) {goto block_77;}                          // branch non-likely

  bc = c->sgpr64(v1) != c->sgpr64(s7);              // bne v1, s7, L58
  c->mov64(a0, s7);                                 // or a0, s7, r0
  if (bc) {goto block_76;}                          // branch non-likely

  c->mov64(a0, gp);                                 // or a0, gp, r0
  bc = c->sgpr64(s7) == c->sgpr64(a0);              // beq s7, a0, L55
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_72;}                          // branch non-likely

  c->lwu(v1, 28, a0);                               // lwu v1, 28(a0)
  
block_72:
  bc = c->sgpr64(s7) == c->sgpr64(v1);              // beq s7, v1, L56
  // nop                                            // sll r0, r0, 0
  if (bc) {goto block_74;}                          // branch non-likely

  c->lwu(a0, 0, v1);                                // lwu a0, 0(v1)
  c->lw(a0, 48, a0);                                // lw a0, 48(a0)
  c->dsll32(a0, a0, 0);                             // dsll32 a0, a0, 0
  //beq r0, r0, L57                                 // beq r0, r0, L57
  // nop                                            // sll r0, r0, 0
  goto block_75;                                    // branch always

  
block_74:
  c->addiu(a0, r0, 0);                              // addiu a0, r0, 0
  
block_75:
  c->sllv(v1, v1, r0);                              // sllv v1, v1, r0
  c->or_(v1, a0, v1);                               // or v1, a0, v1
  c->mov64(a0, v1);                                 // or a0, v1, r0
  
block_76:
  c->sd(v1, 160, s3);                               // sd v1, 160(s3)
  c->load_symbol2(t9, cache.matrix_identity);       // lw t9, matrix-identity!(s7)
  c->daddiu(a0, s3, 96);                            // daddiu a0, s3, 96
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->load_symbol2(t9, cache.matrix_identity);       // lw t9, matrix-identity!(s7)
  c->daddiu(a0, s3, 32);                            // daddiu a0, s3, 32
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->sw(r0, 168, s3);                               // sw r0, 168(s3)
  //beq r0, r0, L60                                 // beq r0, r0, L60
  // nop                                            // sll r0, r0, 0
  goto block_78;                                    // branch always

  
block_77:
  c->load_symbol2(t9, cache.format);                // lw t9, format(s7)
  c->addiu(a0, r0, 0);                              // addiu a0, r0, 0
  // daddiu a1, fp, L371  — string "out of local-space connections. ~A~%"; pass NULL
  c->mov64(a1, r0);
  c->mov64(a2, gp);                                 // or a2, gp, r0
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->load_symbol2(t9, cache.format);                // lw t9, format(s7)
  c->load_symbol2(a0, cache.stdebug);               // lw a0, *stdebug*(s7)
  // daddiu a1, fp, L371  — string "out of local-space connections. ~A~%"; pass NULL
  c->mov64(a1, r0);
  c->mov64(a2, gp);                                 // or a2, gp, r0
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mov64(s3, s7);                                 // or s3, s7, r0
  
block_78:
  c->mov64(t9, s4);                                 // or t9, s4, r0
  c->mov64(a0, s5);                                 // or a0, s5, r0
  c->mov64(a1, s3);                                 // or a1, s3, r0
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mov64(v1, v0);                                 // or v1, v0, r0
  c->mtc1(f0, r0);                                  // mtc1 f0, r0
  c->swc1(f0, 704, gp);                             // swc1 f0, 704(gp)
  c->mfc1(v0, f0);                                  // mfc1 v0, f0
  c->ld(ra, 0, sp);                                 // ld ra, 0(sp)
  c->ld(fp, 8, sp);                                 // ld fp, 8(sp)
  c->lq(gp, 192, sp);                               // lq gp, 192(sp)
  c->lq(s5, 176, sp);                               // lq s5, 176(sp)
  c->lq(s4, 160, sp);                               // lq s4, 160(sp)
  c->lq(s3, 144, sp);                               // lq s3, 144(sp)
  //jr ra                                           // jr ra
  c->daddiu(sp, sp, 208);                           // daddiu sp, sp, 208
  goto end_of_function;                             // return

  // nop                                            // sll r0, r0, 0
  // nop                                            // sll r0, r0, 0
end_of_function:
  return c->gprs[v0].du64[0];
}

void link() {
  cache.default_dead_pool = intern_from_c(-1, 0, "*default-dead-pool*").c();
  cache.fake_scratchpad_data = intern_from_c(-1, 0, "*fake-scratchpad-data*").c();
  cache.part_group_id_table = intern_from_c(-1, 0, "*part-group-id-table*").c();
  cache.part_local_space_engine = intern_from_c(-1, 0, "*part-local-space-engine*").c();
  cache.rigid_body_queue_manager = intern_from_c(-1, 0, "*rigid-body-queue-manager*").c();
  cache.sp_particle_system_2d = intern_from_c(-1, 0, "*sp-particle-system-2d*").c();
  cache.stdebug = intern_from_c(-1, 0, "*stdebug*").c();
  cache.find_parent_method = intern_from_c(-1, 0, "find-parent-method").c();
  cache.format = intern_from_c(-1, 0, "format").c();
  cache.gunmount_drawable_init_by_other = intern_from_c(-1, 0, "gunmount-drawable-init-by-other").c();
  cache.gunmount_generic_drawable = intern_from_c(-1, 0, "gunmount-generic-drawable").c();
  cache.local_space_proc_joint = intern_from_c(-1, 0, "local-space-proc-joint").c();
  cache.matrix_identity = intern_from_c(-1, 0, "matrix-identity!").c();
  cache.process = intern_from_c(-1, 0, "process").c();
  cache.quaternion_copy = intern_from_c(-1, 0, "quaternion-copy!").c();
  cache.run_function_in_process = intern_from_c(-1, 0, "run-function-in-process").c();
  cache.sparticle_subsampler = intern_from_c(-1, 0, "sparticle-subsampler").c();
  cache.type = intern_from_c(-1, 0, "type?").c();
  cache.v_drone = intern_from_c(-1, 0, "v-drone").c();
  cache.vehicle_antenna_spawn = intern_from_c(-1, 0, "vehicle-antenna-spawn").c();
  cache.wvehicle = intern_from_c(-1, 0, "wvehicle").c();
  gLinkedFunctionTable.reg("(method 64 wvehicle)", execute, 208);
}

} // namespace method_64_wvehicle
} // namespace Mips2C::jakx
