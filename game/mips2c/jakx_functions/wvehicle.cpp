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

namespace method_134_wvehicle {
struct Cache {
  void* game_info; // *game-info*
  void* net_players; // *net-players*
  void* sound_info; // *sound-info*
  void* cos; // cos
  void* is_friendly_fire_helper; // is-friendly-fire-helper
  void* make_sound_instance; // make-sound-instance
  void* seek; // seek
  void* send_event_function; // send-event-function
  void* sign; // sign
  void* sin; // sin
  void* tan; // tan
  void* undisable_turbo; // undisable-turbo
} cache;

u64 execute(void* ctxt) {
  auto* c = (ExecutionContext*)ctxt;
  bool bc = false;
  u32 call_addr = 0;
  bool cop1_bc = false;
  c->daddiu(sp, sp, -304);                          // daddiu sp, sp, -304
  c->sd(ra, 0, sp);                                 // sd ra, 0(sp)
  c->sd(fp, 8, sp);                                 // sd fp, 8(sp)
  c->mov64(fp, t9);                                 // or fp, t9, r0
  c->sq(s2, 208, sp);                               // sq s2, 208(sp)
  c->sq(s3, 224, sp);                               // sq s3, 224(sp)
  c->sq(s4, 240, sp);                               // sq s4, 240(sp)
  c->sq(s5, 256, sp);                               // sq s5, 256(sp)
  c->sq(gp, 272, sp);                               // sq gp, 272(sp)
  c->swc1(f30, 288, sp);                            // swc1 f30, 288(sp)
  c->mov64(gp, a0);                                 // or gp, a0, r0
  c->lwu(s4, 252, gp);                              // lwu s4, 252(gp)
  c->daddiu(s5, sp, 16);                            // daddiu s5, sp, 16
  c->lwc1(f0, 480, gp);                             // lwc1 f0, 480(gp)
  c->swc1(f0, 76, s5);                              // swc1 f0, 76(s5)
  c->lwc1(f0, 328, s4);                             // lwc1 f0, 328(s4)
  c->lwc1(f1, 76, s5);                              // lwc1 f1, 76(s5)
  c->muls(f0, f0, f1);                              // mul.s f0, f0, f1
  c->swc1(f0, 32, s5);                              // swc1 f0, 32(s5)
  c->lwc1(f0, 32, s5);                              // lwc1 f0, 32(s5)
  c->lui(v1, 16256);                                // lui v1, 16256
  c->mtc1(f1, v1);                                  // mtc1 f1, v1
  c->lwc1(f2, 340, s4);                             // lwc1 f2, 340(s4)
  c->lwc1(f3, 76, s5);                              // lwc1 f3, 76(s5)
  c->abss(f3, f3);                                  // abs.s f3, f3
  c->muls(f2, f2, f3);                              // mul.s f2, f2, f3
  c->adds(f1, f1, f2);                              // add.s f1, f1, f2
  c->muls(f0, f0, f1);                              // mul.s f0, f0, f1
  c->swc1(f0, 36, s5);                              // swc1 f0, 36(s5)
  c->lwc1(f0, 2420, gp);                            // lwc1 f0, 2420(gp)
  c->swc1(f0, 60, s5);                              // swc1 f0, 60(s5)
  c->lwc1(f0, 2424, gp);                            // lwc1 f0, 2424(gp)
  c->swc1(f0, 64, s5);                              // swc1 f0, 64(s5)
  c->lwc1(f0, 2416, gp);                            // lwc1 f0, 2416(gp)
  c->swc1(f0, 68, s5);                              // swc1 f0, 68(s5)
  c->lwc1(f0, 60, s5);                              // lwc1 f0, 60(s5)
  c->lui(v1, 16384);                                // lui v1, 16384
  c->mtc1(f1, v1);                                  // mtc1 f1, v1
  c->lwc1(f2, 2856, s4);                            // lwc1 f2, 2856(s4)
  c->muls(f1, f1, f2);                              // mul.s f1, f1, f2
  c->subs(f0, f0, f1);                              // sub.s f0, f0, f1
  c->swc1(f0, 56, s5);                              // swc1 f0, 56(s5)
  c->mtc1(f0, r0);                                  // mtc1 f0, r0
  c->swc1(f0, 72, s5);                              // swc1 f0, 72(s5)
  c->lui(v1, 16785);                                // lui v1, 16785
  c->ori(v1, v1, 41652);                            // ori v1, v1, 41652
  c->mtc1(f0, v1);                                  // mtc1 f0, v1
  c->lwc1(f1, 32, s5);                              // lwc1 f1, 32(s5)
  c->abss(f1, f1);                                  // abs.s f1, f1
  cop1_bc = c->fprs[f0] < c->fprs[f1];              // c.lt.s f0, f1
  bc = !cop1_bc;                                    // bc1f L64
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_5;}                           // branch non-likely

  c->ld(v1, 2944, s4);                              // ld v1, 2944(s4)
  c->andi(v1, v1, 16);                              // andi v1, v1, 16
  bc = c->sgpr64(v1) == 0;                          // beq v1, r0, L62
  // nop                                            // sll r0, r0, 0
  if (bc) {goto block_3;}                           // branch non-likely

  c->lui(v1, 16128);                                // lui v1, 16128
  c->mtc1(f0, v1);                                  // mtc1 f0, v1
  c->lwc1(f1, 68, s5);                              // lwc1 f1, 68(s5)
  c->muls(f30, f0, f1);                             // mul.s f30, f0, f1
  c->load_symbol2(t9, cache.sin);                   // lw t9, sin(s7)
  c->lwc1(f0, 32, s5);                              // lwc1 f0, 32(s5)
  c->abss(f0, f0);                                  // abs.s f0, f0
  c->mfc1(a0, f0);                                  // mfc1 a0, f0
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mtc1(f0, v0);                                  // mtc1 f0, v0
  c->divs(f0, f30, f0);                             // div.s f0, f30, f0
  c->swc1(f0, 52, s5);                              // swc1 f0, 52(s5)
  c->lwc1(f30, 52, s5);                             // lwc1 f30, 52(s5)
  c->load_symbol2(t9, cache.cos);                   // lw t9, cos(s7)
  c->lwc1(f0, 32, s5);                              // lwc1 f0, 32(s5)
  c->abss(f0, f0);                                  // abs.s f0, f0
  c->mfc1(a0, f0);                                  // mfc1 a0, f0
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mtc1(f0, v0);                                  // mtc1 f0, v0
  c->muls(f0, f30, f0);                             // mul.s f0, f30, f0
  c->lwc1(f1, 64, s5);                              // lwc1 f1, 64(s5)
  c->lui(v1, 16384);                                // lui v1, 16384
  c->mtc1(f2, v1);                                  // mtc1 f2, v1
  c->lwc1(f3, 2968, s4);                            // lwc1 f3, 2968(s4)
  c->muls(f2, f2, f3);                              // mul.s f2, f2, f3
  c->subs(f1, f1, f2);                              // sub.s f1, f1, f2
  c->subs(f0, f0, f1);                              // sub.s f0, f0, f1
  c->lui(v1, 16128);                                // lui v1, 16128
  c->mtc1(f1, v1);                                  // mtc1 f1, v1
  c->lwc1(f2, 68, s5);                              // lwc1 f2, 68(s5)
  c->muls(f1, f1, f2);                              // mul.s f1, f1, f2
  c->muls(f1, f1, f1);                              // mul.s f1, f1, f1
  c->mfc1(v1, f1);                                  // mfc1 v1, f1
  c->mtc1(f1, v1);                                  // mtc1 f1, v1
  c->muls(f0, f0, f0);                              // mul.s f0, f0, f0
  c->mfc1(v1, f0);                                  // mfc1 v1, f0
  c->mtc1(f0, v1);                                  // mtc1 f0, v1
  c->adds(f0, f1, f0);                              // add.s f0, f1, f0
  c->sqrts(f0, f0);                                 // sqrt.s f0, f0
  c->swc1(f0, 48, s5);                              // swc1 f0, 48(s5)
  c->mfc1(v1, f0);                                  // mfc1 v1, f0
  c->lwc1(f0, 52, s5);                              // lwc1 f0, 52(s5)
  c->lwc1(f1, 2968, s4);                            // lwc1 f1, 2968(s4)
  c->adds(f0, f0, f1);                              // add.s f0, f0, f1
  c->swc1(f0, 52, s5);                              // swc1 f0, 52(s5)
  c->lwc1(f0, 48, s5);                              // lwc1 f0, 48(s5)
  c->lwc1(f1, 2968, s4);                            // lwc1 f1, 2968(s4)
  c->subs(f0, f0, f1);                              // sub.s f0, f0, f1
  c->swc1(f0, 48, s5);                              // swc1 f0, 48(s5)
  c->mfc1(v1, f0);                                  // mfc1 v1, f0
  //beq r0, r0, L63                                 // beq r0, r0, L63
  // nop                                            // sll r0, r0, 0
  goto block_4;                                     // branch always

  
block_3:
  c->lwc1(f30, 68, s5);                             // lwc1 f30, 68(s5)
  c->load_symbol2(t9, cache.tan);                   // lw t9, tan(s7)
  c->lwc1(f0, 32, s5);                              // lwc1 f0, 32(s5)
  c->abss(f0, f0);                                  // abs.s f0, f0
  c->mfc1(a0, f0);                                  // mfc1 a0, f0
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mtc1(f0, v0);                                  // mtc1 f0, v0
  c->divs(f0, f30, f0);                             // div.s f0, f30, f0
  c->swc1(f0, 52, s5);                              // swc1 f0, 52(s5)
  c->lwc1(f0, 52, s5);                              // lwc1 f0, 52(s5)
  c->lui(v1, 16128);                                // lui v1, 16128
  c->mtc1(f1, v1);                                  // mtc1 f1, v1
  c->lwc1(f2, 64, s5);                              // lwc1 f2, 64(s5)
  c->lwc1(f3, 56, s5);                              // lwc1 f3, 56(s5)
  c->subs(f2, f2, f3);                              // sub.s f2, f2, f3
  c->muls(f1, f1, f2);                              // mul.s f1, f1, f2
  c->adds(f0, f0, f1);                              // add.s f0, f0, f1
  c->swc1(f0, 52, s5);                              // swc1 f0, 52(s5)
  c->lwc1(f0, 52, s5);                              // lwc1 f0, 52(s5)
  c->lwc1(f1, 64, s5);                              // lwc1 f1, 64(s5)
  c->subs(f0, f0, f1);                              // sub.s f0, f0, f1
  c->swc1(f0, 48, s5);                              // swc1 f0, 48(s5)
  c->mfc1(v1, f0);                                  // mfc1 v1, f0
  
block_4:
  c->lwc1(f0, 52, s5);                              // lwc1 f0, 52(s5)
  c->lwc1(f1, 48, s5);                              // lwc1 f1, 48(s5)
  c->subs(f0, f0, f1);                              // sub.s f0, f0, f1
  c->lwc1(f1, 52, s5);                              // lwc1 f1, 52(s5)
  c->lwc1(f2, 48, s5);                              // lwc1 f2, 48(s5)
  c->adds(f1, f1, f2);                              // add.s f1, f1, f2
  c->divs(f0, f0, f1);                              // div.s f0, f0, f1
  c->swc1(f0, 72, s5);                              // swc1 f0, 72(s5)
  c->mfc1(v1, f0);                                  // mfc1 v1, f0
  
block_5:
  c->lui(v1, 16256);                                // lui v1, 16256
  c->mtc1(f0, v1);                                  // mtc1 f0, v1
  c->lwc1(f1, 72, s5);                              // lwc1 f1, 72(s5)
  c->subs(f0, f0, f1);                              // sub.s f0, f0, f1
  c->swc1(f0, 40, s5);                              // swc1 f0, 40(s5)
  c->lui(v1, 16256);                                // lui v1, 16256
  c->mtc1(f0, v1);                                  // mtc1 f0, v1
  c->lwc1(f1, 72, s5);                              // lwc1 f1, 72(s5)
  c->adds(f0, f0, f1);                              // add.s f0, f0, f1
  c->swc1(f0, 44, s5);                              // swc1 f0, 44(s5)
  c->lwc1(f0, 32, s5);                              // lwc1 f0, 32(s5)
  c->mtc1(f1, r0);                                  // mtc1 f1, r0
  cop1_bc = c->fprs[f0] < c->fprs[f1];              // c.lt.s f0, f1
  bc = !cop1_bc;                                    // bc1f L65
  // nop                                            // sll r0, r0, 0
  if (bc) {goto block_7;}                           // branch non-likely

  c->lwc1(f0, 32, s5);                              // lwc1 f0, 32(s5)
  c->swc1(f0, 0, s5);                               // swc1 f0, 0(s5)
  c->lwc1(f0, 36, s5);                              // lwc1 f0, 36(s5)
  c->swc1(f0, 4, s5);                               // swc1 f0, 4(s5)
  c->lwc1(f0, 44, s5);                              // lwc1 f0, 44(s5)
  c->swc1(f0, 16, s5);                              // swc1 f0, 16(s5)
  c->lwc1(f0, 40, s5);                              // lwc1 f0, 40(s5)
  c->swc1(f0, 20, s5);                              // swc1 f0, 20(s5)
  c->mfc1(v1, f0);                                  // mfc1 v1, f0
  //beq r0, r0, L66                                 // beq r0, r0, L66
  // nop                                            // sll r0, r0, 0
  goto block_8;                                     // branch always

  
block_7:
  c->lwc1(f0, 36, s5);                              // lwc1 f0, 36(s5)
  c->swc1(f0, 0, s5);                               // swc1 f0, 0(s5)
  c->lwc1(f0, 32, s5);                              // lwc1 f0, 32(s5)
  c->swc1(f0, 4, s5);                               // swc1 f0, 4(s5)
  c->lwc1(f0, 40, s5);                              // lwc1 f0, 40(s5)
  c->swc1(f0, 16, s5);                              // swc1 f0, 16(s5)
  c->lwc1(f0, 44, s5);                              // lwc1 f0, 44(s5)
  c->swc1(f0, 20, s5);                              // swc1 f0, 20(s5)
  c->mfc1(v1, f0);                                  // mfc1 v1, f0
  
block_8:
  c->addiu(s4, r0, 0);                              // addiu s4, r0, 0
  //beq r0, r0, L70                                 // beq r0, r0, L70
  // nop                                            // sll r0, r0, 0
  goto block_14;                                    // branch always

  
block_9:
  c->addiu(v1, r0, 288);                            // addiu v1, r0, 288
  c->mult3(v1, v1, s4);                             // mult3 v1, v1, s4
  c->daddiu(v1, v1, 2476);                          // daddiu v1, v1, 2476
  c->daddu(s3, v1, gp);                             // daddu s3, v1, gp
  c->lwu(s2, 0, s3);                                // lwu s2, 0(s3)
  c->ld(v1, 16, s2);                                // ld v1, 16(s2)
  c->andi(v1, v1, 16);                              // andi v1, v1, 16
  bc = c->sgpr64(v1) == 0;                          // beq v1, r0, L68
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_11;}                          // branch non-likely

  c->andi(v1, s4, 1);                               // andi v1, s4, 1
  c->dsll(v1, v1, 2);                               // dsll v1, v1, 2
  c->daddu(v1, v1, s5);                             // daddu v1, v1, s5
  c->lwc1(f30, 0, v1);                              // lwc1 f30, 0(v1)
  c->load_symbol2(t9, cache.sign);                  // lw t9, sign(s7)
  c->lwc1(f0, 8, s2);                               // lwc1 f0, 8(s2)
  c->mfc1(a0, f0);                                  // mfc1 a0, f0
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mtc1(f0, v0);                                  // mtc1 f0, v0
  c->muls(f0, f30, f0);                             // mul.s f0, f30, f0
  c->swc1(f0, 192, s3);                             // swc1 f0, 192(s3)
  c->mfc1(v1, f0);                                  // mfc1 v1, f0
  
block_11:
  c->ld(v1, 16, s2);                                // ld v1, 16(s2)
  c->andi(v1, v1, 1);                               // andi v1, v1, 1
  bc = c->sgpr64(v1) == 0;                          // beq v1, r0, L69
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_13;}                          // branch non-likely

  c->andi(v1, s4, 1);                               // andi v1, s4, 1
  c->dsll(v1, v1, 2);                               // dsll v1, v1, 2
  c->daddu(v1, v1, s5);                             // daddu v1, v1, s5
  c->lwc1(f0, 16, v1);                              // lwc1 f0, 16(v1)
  c->swc1(f0, 220, s3);                             // swc1 f0, 220(s3)
  c->mfc1(v1, f0);                                  // mfc1 v1, f0
  
block_13:
  c->daddiu(s4, s4, 1);                             // daddiu s4, s4, 1
  
block_14:
  c->slti(v1, s4, 4);                               // slti v1, s4, 4
  bc = c->sgpr64(v1) != 0;                          // bne v1, r0, L67
  // nop                                            // sll r0, r0, 0
  if (bc) {goto block_9;}                           // branch non-likely

  c->mov64(v1, s7);                                 // or v1, s7, r0
  c->mov64(v1, s7);                                 // or v1, s7, r0
  c->addiu(s5, r0, 0);                              // addiu s5, r0, 0
  //beq r0, r0, L72                                 // beq r0, r0, L72
  // nop                                            // sll r0, r0, 0
  goto block_17;                                    // branch always

  
block_16:
  c->addiu(v1, r0, 288);                            // addiu v1, r0, 288
  c->mult3(v1, v1, s5);                             // mult3 v1, v1, s5
  c->daddiu(v1, v1, 2476);                          // daddiu v1, v1, 2476
  c->daddu(s3, v1, gp);                             // daddu s3, v1, gp
  c->daddiu(s4, s3, 48);                            // daddiu s4, s3, 48
  c->load_symbol2(t9, cache.cos);                   // lw t9, cos(s7)
  c->lwc1(f0, 192, s3);                             // lwc1 f0, 192(s3)
  c->mfc1(a0, f0);                                  // mfc1 a0, f0
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mtc1(f0, v0);                                  // mtc1 f0, v0
  c->swc1(f0, 0, s4);                               // swc1 f0, 0(s4)
  c->mtc1(f0, r0);                                  // mtc1 f0, r0
  c->swc1(f0, 4, s4);                               // swc1 f0, 4(s4)
  c->load_symbol2(t9, cache.sin);                   // lw t9, sin(s7)
  c->lwc1(f0, 192, s3);                             // lwc1 f0, 192(s3)
  c->mfc1(a0, f0);                                  // mfc1 a0, f0
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mtc1(f0, v0);                                  // mtc1 f0, v0
  c->negs(f0, f0);                                  // neg.s f0, f0
  c->swc1(f0, 8, s4);                               // swc1 f0, 8(s4)
  c->lui(v1, 16256);                                // lui v1, 16256
  c->mtc1(f0, v1);                                  // mtc1 f0, v1
  c->swc1(f0, 12, s4);                              // swc1 f0, 12(s4)
  c->daddiu(s5, s5, 1);                             // daddiu s5, s5, 1
  
block_17:
  c->slti(v1, s5, 4);                               // slti v1, s5, 4
  bc = c->sgpr64(v1) != 0;                          // bne v1, r0, L71
  // nop                                            // sll r0, r0, 0
  if (bc) {goto block_16;}                          // branch non-likely

  c->mov64(v1, s7);                                 // or v1, s7, r0
  c->mov64(v1, s7);                                 // or v1, s7, r0
  c->daddiu(s5, sp, 96);                            // daddiu s5, sp, 96
  c->lwu(v1, 8, s6);                                // lwu v1, 8(s6)
  c->ld(v1, 20, v1);                                // ld v1, 20(v1)
  c->sw(v1, 0, s5);                                 // sw v1, 0(s5)
  c->lbu(v1, 500, gp);                              // lbu v1, 500(gp)
  c->andi(v1, v1, 1);                               // andi v1, v1, 1
  if (((s64)c->sgpr64(v1)) == ((s64)0)) {           // beql v1, r0, L73
    c->mov64(v1, s7);                               // or v1, s7, r0
    goto block_25;
  }
  
block_20:
  c->lbu(v1, 501, gp);                              // lbu v1, 501(gp)
  c->andi(v1, v1, 1);                               // andi v1, v1, 1
  if (((s64)c->sgpr64(v1)) != ((s64)0)) {           // bnel v1, r0, L73
    c->mov64(v1, s7);                               // or v1, s7, r0
    goto block_25;
  }
  
block_22:
  c->addiu(v1, r0, 45);                             // addiu v1, r0, 45
  c->lwu(a0, 0, s5);                                // lwu a0, 0(s5)
  c->lwu(a1, 3908, gp);                             // lwu a1, 3908(gp)
  c->dsubu(a0, a0, a1);                             // dsubu a0, a0, a1
  c->sltu(v1, v1, a0);                              // sltu v1, v1, a0
  c->daddiu(a0, s7, 4);                             // daddiu a0, s7, 4
  c->movz(a0, s7, v1);                              // movz a0, s7, v1
  if (((s64)c->sgpr64(s7)) == ((s64)c->sgpr64(a0))) {// beql s7, a0, L73
    c->mov64(v1, a0);                               // or v1, a0, r0
    goto block_25;
  }
  
block_24:
  c->addiu(v1, r0, 45);                             // addiu v1, r0, 45
  c->lwu(a0, 0, s5);                                // lwu a0, 0(s5)
  c->lwu(a1, 3904, gp);                             // lwu a1, 3904(gp)
  c->dsubu(a0, a0, a1);                             // dsubu a0, a0, a1
  c->sltu(a0, v1, a0);                              // sltu a0, v1, a0
  c->daddiu(v1, s7, 4);                             // daddiu v1, s7, 4
  c->movz(v1, s7, a0);                              // movz v1, s7, a0
  
block_25:
  bc = c->sgpr64(s7) == c->sgpr64(v1);              // beq s7, v1, L79
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_39;}                          // branch non-likely

  c->addiu(v1, r0, 0);                              // addiu v1, r0, 0
  c->addiu(a0, r0, 0);                              // addiu a0, r0, 0
  //beq r0, r0, L77                                 // beq r0, r0, L77
  // nop                                            // sll r0, r0, 0
  goto block_34;                                    // branch always

  
block_27:
  c->addiu(a1, r0, 288);                            // addiu a1, r0, 288
  c->mult3(a1, a1, a0);                             // mult3 a1, a1, a0
  c->daddiu(a1, a1, 2476);                          // daddiu a1, a1, 2476
  c->daddu(a1, a1, gp);                             // daddu a1, a1, gp
  c->lbu(a2, 4, a1);                                // lbu a2, 4(a1)
  c->andi(a2, a2, 1);                               // andi a2, a2, 1
  if (((s64)c->sgpr64(a2)) == ((s64)0)) {           // beql a2, r0, L75
    c->mov64(a1, s7);                               // or a1, s7, r0
    goto block_31;
  }
  
block_29:
  c->mtc1(f0, r0);                                  // mtc1 f0, r0
  c->lwc1(f1, 216, a1);                             // lwc1 f1, 216(a1)
  cop1_bc = c->fprs[f0] < c->fprs[f1];              // c.lt.s f0, f1
  bc = cop1_bc;                                     // bc1t L75
  c->daddiu(a1, s7, 4);                             // daddiu a1, s7, 4
  if (bc) {goto block_31;}                          // branch non-likely

  c->mov64(a1, s7);                                 // or a1, s7, r0
  
block_31:
  bc = c->sgpr64(s7) == c->sgpr64(a1);              // beq s7, a1, L76
  c->mov64(a1, s7);                                 // or a1, s7, r0
  if (bc) {goto block_33;}                          // branch non-likely

  c->daddiu(v1, v1, 1);                             // daddiu v1, v1, 1
  c->mov64(a1, v1);                                 // or a1, v1, r0
  
block_33:
  c->daddiu(a0, a0, 1);                             // daddiu a0, a0, 1
  
block_34:
  c->slti(a1, a0, 4);                               // slti a1, a0, 4
  bc = c->sgpr64(a1) != 0;                          // bne a1, r0, L74
  // nop                                            // sll r0, r0, 0
  if (bc) {goto block_27;}                          // branch non-likely

  c->mov64(a0, s7);                                 // or a0, s7, r0
  c->mov64(a0, s7);                                 // or a0, s7, r0
  c->slti(v1, v1, 2);                               // slti v1, v1, 2
  bc = c->sgpr64(v1) != 0;                          // bne v1, r0, L79
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_39;}                          // branch non-likely

  c->daddiu(v1, sp, 112);                           // daddiu v1, sp, 112
  c->daddu(a0, r0, v1);                             // daddu a0, r0, v1
  c->lwu(a1, 228, gp);                              // lwu a1, 228(gp)
  c->daddiu(a1, a1, 188);                           // daddiu a1, a1, 188
  c->lui(a2, 16025);                                // lui a2, 16025
  c->ori(a2, a2, 39322);                            // ori a2, a2, 39322
  c->mtc1(f0, a2);                                  // mtc1 f0, a2
  c->lwu(a2, 228, gp);                              // lwu a2, 228(gp)
  c->lwc1(f1, 192, a2);                             // lwc1 f1, 192(a2)
  c->muls(f0, f0, f1);                              // mul.s f0, f0, f1
  c->lwu(a2, 252, gp);                              // lwu a2, 252(gp)
  c->lwc1(f1, 4, a2);                               // lwc1 f1, 4(a2)
  c->muls(f0, f0, f1);                              // mul.s f0, f0, f1
  c->lwu(a2, 252, gp);                              // lwu a2, 252(gp)
  c->lwc1(f1, 188, a2);                             // lwc1 f1, 188(a2)
  c->muls(f0, f0, f1);                              // mul.s f0, f0, f1
  c->lwu(a2, 252, gp);                              // lwu a2, 252(gp)
  c->lwc1(f1, 380, a2);                             // lwc1 f1, 380(a2)
  c->muls(f0, f0, f1);                              // mul.s f0, f0, f1
  c->lqc2(vf1, 0, a1);                              // lqc2 vf1, 0(a1)
  c->mfc1(a1, f0);                                  // mfc1 a1, f0
  c->mov128_vf_gpr(vf2, a1);                        // qmtc2.i vf2, a1
  c->vadd_bc(DEST::w, BC::x, vf1, vf0, vf0);        // vaddx.w vf1, vf0, vf0
  c->vmul_bc(DEST::xyz, BC::x, vf1, vf1, vf2);      // vmulx.xyz vf1, vf1, vf2
  c->sqc2(vf1, 0, a0);                              // sqc2 vf1, 0(a0)
  c->lwu(a0, 228, gp);                              // lwu a0, 228(gp)
  c->lwu(a1, -4, a0);                               // lwu a1, -4(a0)
  c->lwu(t9, 96, a1);                               // lwu t9, 96(a1)
  c->daddu(a1, r0, v1);                             // daddu a1, r0, v1
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mov64(v1, v0);                                 // or v1, v0, r0
  c->lwu(a0, 228, gp);                              // lwu a0, 228(gp)
  c->lwu(v1, -4, a0);                               // lwu v1, -4(a0)
  c->lwu(t9, 64, v1);                               // lwu t9, 64(v1)
  c->lui(a1, 16256);                                // lui a1, 16256
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mov64(v1, v0);                                 // or v1, v0, r0
  c->lwu(a0, 228, gp);                              // lwu a0, 228(gp)
  c->lwu(v1, -4, a0);                               // lwu v1, -4(a0)
  c->lwu(t9, 68, v1);                               // lwu t9, 68(v1)
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mov64(v1, v0);                                 // or v1, v0, r0
  c->lwu(v1, 0, s5);                                // lwu v1, 0(s5)
  c->sw(v1, 3908, gp);                              // sw v1, 3908(gp)
  c->load_symbol2(t9, cache.make_sound_instance);   // lw t9, make-sound-instance(s7)
  c->lwu(v1, 252, gp);                              // lwu v1, 252(gp)
  c->lhu(v1, 546, v1);                              // lhu v1, 546(v1)
  c->dsll(v1, v1, 2);                               // dsll v1, v1, 2
  c->load_symbol2(a0, cache.sound_info);            // lw a0, *sound-info*(s7)
  c->daddu(v1, v1, a0);                             // daddu v1, v1, a0
  c->lwu(a0, 12, v1);                               // lwu a0, 12(v1)
  c->addiu(a1, r0, 0);                              // addiu a1, r0, 0
  c->mov64(a2, s7);                                 // or a2, s7, r0
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mov64(v1, v0);                                 // or v1, v0, r0
  bc = c->sgpr64(s7) == c->sgpr64(v1);              // beq s7, v1, L78
  // nop                                            // sll r0, r0, 0
  if (bc) {goto block_38;}                          // branch non-likely

  c->lwu(v1, 80, v1);                               // lwu v1, 80(v1)
  //beq r0, r0, L79                                 // beq r0, r0, L79
  // nop                                            // sll r0, r0, 0
  goto block_39;                                    // branch always

  
block_38:
  c->addiu(v1, r0, 0);                              // addiu v1, r0, 0
  
block_39:
  c->lui(v1, 16384);                                // lui v1, 16384
  c->ld(a0, 260, gp);                               // ld a0, 260(gp)
  c->and_(v1, v1, a0);                              // and v1, v1, a0
  bc = c->sgpr64(v1) == 0;                          // beq v1, r0, L80
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_42;}                          // branch non-likely

  c->addiu(v1, r0, 450);                            // addiu v1, r0, 450
  c->lwu(a0, 0, s5);                                // lwu a0, 0(s5)
  c->lwu(a1, 824, gp);                              // lwu a1, 824(gp)
  c->dsubu(a0, a0, a1);                             // dsubu a0, a0, a1
  c->sltu(v1, v1, a0);                              // sltu v1, v1, a0
  bc = c->sgpr64(v1) == 0;                          // beq v1, r0, L80
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_42;}                          // branch non-likely

  c->lui(v1, -16385);                               // lui v1, -16385
  c->ori(v1, v1, 65535);                            // ori v1, v1, 65535
  c->ld(a0, 260, gp);                               // ld a0, 260(gp)
  c->and_(v1, v1, a0);                              // and v1, v1, a0
  c->sd(v1, 260, gp);                               // sd v1, 260(gp)
  
block_42:
  c->addiu(v1, r0, 16384);                          // addiu v1, r0, 16384
  c->dsll32(v1, v1, 0);                             // dsll32 v1, v1, 0
  c->ld(a0, 260, gp);                               // ld a0, 260(gp)
  c->and_(v1, v1, a0);                              // and v1, v1, a0
  bc = c->sgpr64(v1) == 0;                          // beq v1, r0, L81
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_45;}                          // branch non-likely

  c->addiu(v1, r0, 600);                            // addiu v1, r0, 600
  c->lwu(a0, 0, s5);                                // lwu a0, 0(s5)
  c->lwu(a1, 828, gp);                              // lwu a1, 828(gp)
  c->dsubu(a0, a0, a1);                             // dsubu a0, a0, a1
  c->sltu(v1, v1, a0);                              // sltu v1, v1, a0
  bc = c->sgpr64(v1) == 0;                          // beq v1, r0, L81
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_45;}                          // branch non-likely

  // Unknown instr: ld v1, L384(fp)
  c->ld(a0, 260, gp);                               // ld a0, 260(gp)
  c->and_(v1, v1, a0);                              // and v1, v1, a0
  c->sd(v1, 260, gp);                               // sd v1, 260(gp)
  
block_45:
  c->lui(v1, 16128);                                // lui v1, 16128
  c->mtc1(f0, v1);                                  // mtc1 f0, v1
  c->lwc1(f1, 488, gp);                             // lwc1 f1, 488(gp)
  c->lwc1(f2, 496, gp);                             // lwc1 f2, 496(gp)
  c->adds(f1, f1, f2);                              // add.s f1, f1, f2
  cop1_bc = c->fprs[f0] < c->fprs[f1];              // c.lt.s f0, f1
  bc = cop1_bc;                                     // bc1t L82
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_47;}                          // branch non-likely

  c->lwu(v1, 0, s5);                                // lwu v1, 0(s5)
  c->sw(v1, 808, gp);                               // sw v1, 808(gp)
  
block_47:
  // Unknown instr: ld v1, L383(fp)
  c->ld(a0, 260, gp);                               // ld a0, 260(gp)
  c->and_(v1, v1, a0);                              // and v1, v1, a0
  c->sd(v1, 260, gp);                               // sd v1, 260(gp)
  c->addiu(v1, r0, 150);                            // addiu v1, r0, 150
  c->lwu(a0, 0, s5);                                // lwu a0, 0(s5)
  c->lwu(a1, 808, gp);                              // lwu a1, 808(gp)
  c->dsubu(a0, a0, a1);                             // dsubu a0, a0, a1
  c->sltu(v1, v1, a0);                              // sltu v1, v1, a0
  bc = c->sgpr64(v1) == 0;                          // beq v1, r0, L83
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_49;}                          // branch non-likely

  c->addiu(v1, r0, 4096);                           // addiu v1, r0, 4096
  c->dsll32(v1, v1, 0);                             // dsll32 v1, v1, 0
  c->ld(a0, 260, gp);                               // ld a0, 260(gp)
  c->or_(v1, v1, a0);                               // or v1, v1, a0
  c->sd(v1, 260, gp);                               // sd v1, 260(gp)
  
block_49:
  c->lwu(v1, 0, s5);                                // lwu v1, 0(s5)
  c->lwu(a0, 812, gp);                              // lwu a0, 812(gp)
  c->sltu(v1, v1, a0);                              // sltu v1, v1, a0
  bc = c->sgpr64(v1) == 0;                          // beq v1, r0, L84
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_51;}                          // branch non-likely

  c->lui(v1, 16256);                                // lui v1, 16256
  c->mtc1(f0, v1);                                  // mtc1 f0, v1
  c->swc1(f0, 700, gp);                             // swc1 f0, 700(gp)
  c->mfc1(v1, f0);                                  // mfc1 v1, f0
  
block_51:
  c->load_symbol2(v1, cache.game_info);             // lw v1, *game-info*(s7)
  c->lb(v1, 1468, v1);                              // lb v1, 1468(v1)
  c->mov64(s4, gp);                                 // or s4, gp, r0
  c->mov64(a0, v1);                                 // or a0, v1, r0
  c->slt(a1, a0, r0);                               // slt a1, a0, r0
  c->daddiu(a2, s7, 4);                             // daddiu a2, s7, 4
  c->movn(a2, s7, a1);                              // movn a2, s7, a1
  if (((s64)c->sgpr64(s7)) == ((s64)c->sgpr64(a2))) {// beql s7, a2, L85
    c->mov64(a0, a2);                               // or a0, a2, r0
    goto block_56;
  }
  
block_53:
  c->slti(a1, a0, 24);                              // slti a1, a0, 24
  c->daddiu(a2, s7, 4);                             // daddiu a2, s7, 4
  c->movz(a2, s7, a1);                              // movz a2, s7, a1
  if (((s64)c->sgpr64(s7)) == ((s64)c->sgpr64(a2))) {// beql s7, a2, L85
    c->mov64(a0, a2);                               // or a0, a2, r0
    goto block_56;
  }
  
block_55:
  c->dsll(a0, a0, 2);                               // dsll a0, a0, 2
  c->load_symbol2(a1, cache.net_players);           // lw a1, *net-players*(s7)
  c->daddu(a0, a0, a1);                             // daddu a0, a0, a1
  c->lwu(a0, 12, a0);                               // lwu a0, 12(a0)
  
block_56:
  if (((s64)c->sgpr64(s7)) == ((s64)c->sgpr64(a0))) {// beql s7, a0, L86
    c->mov64(v1, a0);                               // or v1, a0, r0
    goto block_62;
  }
  
block_58:
  c->lb(a0, 2116, s4);                              // lb a0, 2116(s4)
  c->dsubu(a0, v1, a0);                             // dsubu a0, v1, a0
  c->daddiu(a1, s7, 4);                             // daddiu a1, s7, 4
  c->movz(a1, s7, a0);                              // movz a1, s7, a0
  if (((s64)c->sgpr64(s7)) == ((s64)c->sgpr64(a1))) {// beql s7, a1, L86
    c->mov64(v1, a1);                               // or v1, a1, r0
    goto block_62;
  }
  
block_60:
  c->load_symbol2(s3, cache.is_friendly_fire_helper);// lw s3, is-friendly-fire-helper(s7)
  c->dsll(v1, v1, 2);                               // dsll v1, v1, 2
  c->load_symbol2(a0, cache.net_players);           // lw a0, *net-players*(s7)
  c->daddu(v1, v1, a0);                             // daddu v1, v1, a0
  c->lwu(a0, 12, v1);                               // lwu a0, 12(v1)
  c->lwu(v1, -4, a0);                               // lwu v1, -4(a0)
  c->lwu(t9, 212, v1);                              // lwu t9, 212(v1)
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mov64(a0, v0);                                 // or a0, v0, r0
  c->mov64(t9, s3);                                 // or t9, s3, r0
  c->mov64(a1, s4);                                 // or a1, s4, r0
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  bc = c->sgpr64(s7) == c->sgpr64(v0);              // beq s7, v0, L86
  c->daddiu(v1, s7, 4);                             // daddiu v1, s7, 4
  if (bc) {goto block_62;}                          // branch non-likely

  c->mov64(v1, s7);                                 // or v1, s7, r0
  
block_62:
  if (((s64)c->sgpr64(s7)) == ((s64)c->sgpr64(v1))) {// beql s7, v1, L90
    c->mov64(v1, v1);                               // or v1, v1, r0
    goto block_73;
  }
  
block_64:
  c->daddiu(a1, sp, 128);                           // daddiu a1, sp, 128
  c->mov64(v1, s6);                                 // or v1, s6, r0
  bc = c->sgpr64(s7) == c->sgpr64(v1);              // beq s7, v1, L87
  c->mov64(a0, s7);                                 // or a0, s7, r0
  if (bc) {goto block_66;}                          // branch non-likely

  c->lwu(a0, 28, v1);                               // lwu a0, 28(v1)
  
block_66:
  c->sw(a0, 8, a1);                                 // sw a0, 8(a1)
  c->sw(r0, 68, a1);                                // sw r0, 68(a1)
  c->load_symbol_addr(v1, cache.undisable_turbo);   // daddiu v1, s7, undisable-turbo
  c->sw(v1, 64, a1);                                // sw v1, 64(a1)
  c->load_symbol2(t9, cache.send_event_function);   // lw t9, send-event-function(s7)
  c->ld(v1, 4500, gp);                              // ld v1, 4500(gp)
  c->subu(a0, v1, s7);                              // subu a0, v1, s7
  if (((s64)c->sgpr64(a0)) == ((s64)0)) {           // beql a0, r0, L89
    c->mov64(a0, s7);                               // or a0, s7, r0
    goto block_71;
  }
  
block_68:
  c->sllv(a0, v1, r0);                              // sllv a0, v1, r0
  c->lwu(a2, 0, a0);                                // lwu a2, 0(a0)
  c->lw(a0, 48, a2);                                // lw a0, 48(a2)
  c->dsra32(v1, v1, 0);                             // dsra32 v1, v1, 0
  bc = c->sgpr64(v1) != c->sgpr64(a0);              // bne v1, a0, L88
  c->mov64(a0, s7);                                 // or a0, s7, r0
  if (bc) {goto block_70;}                          // branch non-likely

  c->mov64(a0, a2);                                 // or a0, a2, r0
  
block_70:
  c->mov64(v1, a0);                                 // or v1, a0, r0
  
block_71:
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mov64(v1, v0);                                 // or v1, v0, r0
  bc = c->sgpr64(s7) == c->sgpr64(v1);              // beq s7, v1, L90
  c->daddiu(v1, s7, 4);                             // daddiu v1, s7, 4
  if (bc) {goto block_73;}                          // branch non-likely

  c->mov64(v1, s7);                                 // or v1, s7, r0
  
block_73:
  bc = c->sgpr64(s7) == c->sgpr64(v1);              // beq s7, v1, L94
  // nop                                            // sll r0, r0, 0
  if (bc) {goto block_84;}                          // branch non-likely

  c->ld(v1, 260, gp);                               // ld v1, 260(gp)
  c->andi(v1, v1, 1024);                            // andi v1, v1, 1024
  if (((s64)c->sgpr64(v1)) == ((s64)0)) {           // beql v1, r0, L91
    c->mov64(v1, s7);                               // or v1, s7, r0
    goto block_79;
  }
  
block_76:
  c->lbu(v1, 500, gp);                              // lbu v1, 500(gp)
  c->andi(v1, v1, 2);                               // andi v1, v1, 2
  if (((s64)c->sgpr64(v1)) == ((s64)0)) {           // beql v1, r0, L91
    c->mov64(v1, s7);                               // or v1, s7, r0
    goto block_79;
  }
  
block_78:
  c->daddiu(v1, s7, 4);                             // daddiu v1, s7, 4
  c->lbu(a0, 524, gp);                              // lbu a0, 524(gp)
  c->andi(a0, a0, 2);                               // andi a0, a0, 2
  c->movn(v1, s7, a0);                              // movn v1, s7, a0
  
block_79:
  bc = c->sgpr64(s7) == c->sgpr64(v1);              // beq s7, v1, L93
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_83;}                          // branch non-likely

  c->load_symbol2(t9, cache.make_sound_instance);   // lw t9, make-sound-instance(s7)
  c->load_symbol2(v1, cache.sound_info);            // lw v1, *sound-info*(s7)
  c->lwu(a0, 1352, v1);                             // lwu a0, 1352(v1)
  c->addiu(a1, r0, 0);                              // addiu a1, r0, 0
  c->mov64(a2, s7);                                 // or a2, s7, r0
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mov64(v1, v0);                                 // or v1, v0, r0
  bc = c->sgpr64(s7) == c->sgpr64(v1);              // beq s7, v1, L92
  // nop                                            // sll r0, r0, 0
  if (bc) {goto block_82;}                          // branch non-likely

  c->lwu(v1, 80, v1);                               // lwu v1, 80(v1)
  //beq r0, r0, L93                                 // beq r0, r0, L93
  // nop                                            // sll r0, r0, 0
  goto block_83;                                    // branch always

  
block_82:
  c->addiu(v1, r0, 0);                              // addiu v1, r0, 0
  
block_83:
  // Unknown instr: ld v1, L379(fp)
  c->ld(a0, 260, gp);                               // ld a0, 260(gp)
  c->and_(v1, v1, a0);                              // and v1, v1, a0
  c->sd(v1, 260, gp);                               // sd v1, 260(gp)
  //beq r0, r0, L101                                // beq r0, r0, L101
  // nop                                            // sll r0, r0, 0
  goto block_106;                                   // branch always

  
block_84:
  c->ld(v1, 260, gp);                               // ld v1, 260(gp)
  c->andi(v1, v1, 32768);                           // andi v1, v1, 32768
  bc = c->sgpr64(v1) == 0;                          // beq v1, r0, L98
  // nop                                            // sll r0, r0, 0
  if (bc) {goto block_95;}                          // branch non-likely

  c->lwc1(f0, 700, gp);                             // lwc1 f0, 700(gp)
  c->mtc1(f1, r0);                                  // mtc1 f1, r0
  cop1_bc = c->fprs[f0] == c->fprs[f1];             // c.eq.s f0, f1
  bc = cop1_bc;                                     // bc1t L95
  c->daddiu(v1, s7, 4);                             // daddiu v1, s7, 4
  if (bc) {goto block_87;}                          // branch non-likely

  c->mov64(v1, s7);                                 // or v1, s7, r0
  
block_87:
  if (((s64)c->sgpr64(s7)) != ((s64)c->sgpr64(v1))) {// bnel s7, v1, L96
    c->mov64(v1, v1);                               // or v1, v1, r0
    goto block_92;
  }
  
block_89:
  c->lbu(v1, 500, gp);                              // lbu v1, 500(gp)
  c->andi(v1, v1, 2);                               // andi v1, v1, 2
  if (((s64)c->sgpr64(v1)) != ((s64)0)) {           // bnel v1, r0, L96
    c->mov64(v1, s7);                               // or v1, s7, r0
    goto block_92;
  }
  
block_91:
  c->addiu(v1, r0, 90);                             // addiu v1, r0, 90
  c->lwu(a0, 0, s5);                                // lwu a0, 0(s5)
  c->lwu(a1, 816, gp);                              // lwu a1, 816(gp)
  c->dsubu(a0, a0, a1);                             // dsubu a0, a0, a1
  c->sltu(a0, v1, a0);                              // sltu a0, v1, a0
  c->daddiu(v1, s7, 4);                             // daddiu v1, s7, 4
  c->movz(v1, s7, a0);                              // movz v1, s7, a0
  
block_92:
  bc = c->sgpr64(s7) == c->sgpr64(v1);              // beq s7, v1, L97
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_94;}                          // branch non-likely

  // Unknown instr: ld v1, L379(fp)
  c->ld(a0, 260, gp);                               // ld a0, 260(gp)
  c->and_(v1, v1, a0);                              // and v1, v1, a0
  c->sd(v1, 260, gp);                               // sd v1, 260(gp)
  
block_94:
  //beq r0, r0, L101                                // beq r0, r0, L101
  // nop                                            // sll r0, r0, 0
  goto block_106;                                   // branch always

  
block_95:
  c->ori(v1, r0, 32768);                            // ori v1, r0, 32768
  c->dsll(v1, v1, 16);                              // dsll v1, v1, 16
  c->ld(a0, 260, gp);                               // ld a0, 260(gp)
  c->and_(v1, v1, a0);                              // and v1, v1, a0
  if (((s64)c->sgpr64(v1)) != ((s64)0)) {           // bnel v1, r0, L100
    c->daddiu(v1, s7, 4);                           // daddiu v1, s7, 4
    goto block_104;
  }
  
block_97:
  c->lbu(v1, 500, gp);                              // lbu v1, 500(gp)
  c->andi(v1, v1, 2);                               // andi v1, v1, 2
  if (((s64)c->sgpr64(v1)) == ((s64)0)) {           // beql v1, r0, L100
    c->mov64(v1, s7);                               // or v1, s7, r0
    goto block_104;
  }
  
block_99:
  c->lui(v1, 15692);                                // lui v1, 15692
  c->ori(v1, v1, 52429);                            // ori v1, v1, 52429
  c->mtc1(f0, v1);                                  // mtc1 f0, v1
  c->lwc1(f1, 700, gp);                             // lwc1 f1, 700(gp)
  cop1_bc = c->fprs[f0] < c->fprs[f1];              // c.lt.s f0, f1
  bc = cop1_bc;                                     // bc1t L99
  c->daddiu(v1, s7, 4);                             // daddiu v1, s7, 4
  if (bc) {goto block_101;}                         // branch non-likely

  c->mov64(v1, s7);                                 // or v1, s7, r0
  
block_101:
  if (((s64)c->sgpr64(s7)) != ((s64)c->sgpr64(v1))) {// bnel s7, v1, L100
    c->mov64(v1, v1);                               // or v1, v1, r0
    goto block_104;
  }
  
block_103:
  c->daddiu(v1, s7, 4);                             // daddiu v1, s7, 4
  c->ld(a0, 260, gp);                               // ld a0, 260(gp)
  c->andi(a0, a0, 2048);                            // andi a0, a0, 2048
  c->movz(v1, s7, a0);                              // movz v1, s7, a0
  
block_104:
  bc = c->sgpr64(s7) == c->sgpr64(v1);              // beq s7, v1, L101
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_106;}                         // branch non-likely

  c->ld(v1, 260, gp);                               // ld v1, 260(gp)
  c->ori(v1, v1, 32768);                            // ori v1, v1, 32768
  c->sd(v1, 260, gp);                               // sd v1, 260(gp)
  
block_106:
  c->ori(v1, r0, 32768);                            // ori v1, r0, 32768
  c->dsll(v1, v1, 16);                              // dsll v1, v1, 16
  c->ld(a0, 260, gp);                               // ld a0, 260(gp)
  c->and_(v1, v1, a0);                              // and v1, v1, a0
  bc = c->sgpr64(v1) == 0;                          // beq v1, r0, L105
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_115;}                         // branch non-likely

  c->mtc1(f0, r0);                                  // mtc1 f0, r0
  c->lwc1(f1, 700, gp);                             // lwc1 f1, 700(gp)
  cop1_bc = c->fprs[f0] < c->fprs[f1];              // c.lt.s f0, f1
  bc = cop1_bc;                                     // bc1t L102
  c->daddiu(v1, s7, 4);                             // daddiu v1, s7, 4
  if (bc) {goto block_109;}                         // branch non-likely

  c->mov64(v1, s7);                                 // or v1, s7, r0
  
block_109:
  if (((s64)c->sgpr64(s7)) == ((s64)c->sgpr64(v1))) {// beql s7, v1, L103
    c->mov64(v1, v1);                               // or v1, v1, r0
    goto block_112;
  }
  
block_111:
  c->lwu(v1, 0, s5);                                // lwu v1, 0(s5)
  c->lwu(a0, 840, gp);                              // lwu a0, 840(gp)
  c->dsubu(v1, v1, a0);                             // dsubu v1, v1, a0
  c->lhu(a0, 844, gp);                              // lhu a0, 844(gp)
  c->sltu(a0, v1, a0);                              // sltu a0, v1, a0
  c->daddiu(v1, s7, 4);                             // daddiu v1, s7, 4
  c->movz(v1, s7, a0);                              // movz v1, s7, a0
  
block_112:
  bc = c->sgpr64(s7) == c->sgpr64(v1);              // beq s7, v1, L104
  // nop                                            // sll r0, r0, 0
  if (bc) {goto block_114;}                         // branch non-likely

  c->ld(v1, 260, gp);                               // ld v1, 260(gp)
  c->ori(v1, v1, 32768);                            // ori v1, v1, 32768
  c->sd(v1, 260, gp);                               // sd v1, 260(gp)
  //beq r0, r0, L105                                // beq r0, r0, L105
  // nop                                            // sll r0, r0, 0
  goto block_115;                                   // branch always

  
block_114:
  // Unknown instr: ld v1, L381(fp)
  c->ld(a0, 260, gp);                               // ld a0, 260(gp)
  c->and_(v1, v1, a0);                              // and v1, v1, a0
  c->sd(v1, 260, gp);                               // sd v1, 260(gp)
  
block_115:
  c->ld(v1, 260, gp);                               // ld v1, 260(gp)
  c->andi(v1, v1, 32768);                           // andi v1, v1, 32768
  bc = c->sgpr64(v1) == 0;                          // beq v1, r0, L109
  c->mov64(v0, s7);                                 // or v0, s7, r0
  if (bc) {goto block_124;}                         // branch non-likely

  c->ld(v1, 260, gp);                               // ld v1, 260(gp)
  c->andi(v1, v1, 1024);                            // andi v1, v1, 1024
  if (((s64)c->sgpr64(v1)) == ((s64)0)) {           // beql v1, r0, L106
    c->mov64(v1, s7);                               // or v1, s7, r0
    goto block_119;
  }
  
block_118:
  c->daddiu(v1, s7, 4);                             // daddiu v1, s7, 4
  c->ld(a0, 460, gp);                               // ld a0, 460(gp)
  c->andi(a0, a0, 32768);                           // andi a0, a0, 32768
  c->movn(v1, s7, a0);                              // movn v1, s7, a0
  
block_119:
  bc = c->sgpr64(s7) == c->sgpr64(v1);              // beq s7, v1, L108
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_123;}                         // branch non-likely

  c->lui(v1, 2);                                    // lui v1, 2
  c->ld(a0, 260, gp);                               // ld a0, 260(gp)
  c->and_(v1, v1, a0);                              // and v1, v1, a0
  bc = c->sgpr64(v1) == 0;                          // beq v1, r0, L107
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_122;}                         // branch non-likely

  c->mov64(a0, gp);                                 // or a0, gp, r0
  c->lwu(v1, -4, a0);                               // lwu v1, -4(a0)
  c->lwu(t9, 1096, v1);                             // lwu t9, 1096(v1)
  c->lui(v1, 16307);                                // lui v1, 16307
  c->ori(a1, v1, 13107);                            // ori a1, v1, 13107
  c->addiu(a2, r0, -1);                             // addiu a2, r0, -1
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mov64(v1, v0);                                 // or v1, v0, r0
  
block_122:
  c->lwu(v1, 0, s5);                                // lwu v1, 0(s5)
  c->sw(v1, 816, gp);                               // sw v1, 816(gp)
  
block_123:
  c->load_symbol2(t9, cache.seek);                  // lw t9, seek(s7)
  c->lwc1(f0, 700, gp);                             // lwc1 f0, 700(gp)
  c->mfc1(a0, f0);                                  // mfc1 a0, f0
  c->addiu(a1, r0, 0);                              // addiu a1, r0, 0
  c->lwc1(f0, 716, gp);                             // lwc1 f0, 716(gp)
  c->lwu(v1, 8, s6);                                // lwu v1, 8(s6)
  c->lwc1(f1, 76, v1);                              // lwc1 f1, 76(v1)
  c->muls(f0, f0, f1);                              // mul.s f0, f0, f1
  c->mfc1(a2, f0);                                  // mfc1 a2, f0
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mtc1(f0, v0);                                  // mtc1 f0, v0
  c->swc1(f0, 700, gp);                             // swc1 f0, 700(gp)
  c->mfc1(v0, f0);                                  // mfc1 v0, f0
  
block_124:
  c->ld(ra, 0, sp);                                 // ld ra, 0(sp)
  c->ld(fp, 8, sp);                                 // ld fp, 8(sp)
  c->lwc1(f30, 288, sp);                            // lwc1 f30, 288(sp)
  c->lq(gp, 272, sp);                               // lq gp, 272(sp)
  c->lq(s5, 256, sp);                               // lq s5, 256(sp)
  c->lq(s4, 240, sp);                               // lq s4, 240(sp)
  c->lq(s3, 224, sp);                               // lq s3, 224(sp)
  c->lq(s2, 208, sp);                               // lq s2, 208(sp)
  //jr ra                                           // jr ra
  c->daddiu(sp, sp, 304);                           // daddiu sp, sp, 304
  goto end_of_function;                             // return

  // nop                                            // sll r0, r0, 0
  // nop                                            // sll r0, r0, 0
end_of_function:
  return c->gprs[v0].du64[0];
}

void link() {
  cache.game_info = intern_from_c(-1, 0, "*game-info*").c();
  cache.net_players = intern_from_c(-1, 0, "*net-players*").c();
  cache.sound_info = intern_from_c(-1, 0, "*sound-info*").c();
  cache.cos = intern_from_c(-1, 0, "cos").c();
  cache.is_friendly_fire_helper = intern_from_c(-1, 0, "is-friendly-fire-helper").c();
  cache.make_sound_instance = intern_from_c(-1, 0, "make-sound-instance").c();
  cache.seek = intern_from_c(-1, 0, "seek").c();
  cache.send_event_function = intern_from_c(-1, 0, "send-event-function").c();
  cache.sign = intern_from_c(-1, 0, "sign").c();
  cache.sin = intern_from_c(-1, 0, "sin").c();
  cache.tan = intern_from_c(-1, 0, "tan").c();
  cache.undisable_turbo = intern_from_c(-1, 0, "undisable-turbo").c();
  gLinkedFunctionTable.reg("(method 134 wvehicle)", execute, 304);
}

} // namespace method_134_wvehicle


namespace wv_player_post_move_update {
struct Cache {
  void* freeze_hangtime; // *freeze-hangtime*
  void* net_game_mgr; // *net-game-mgr*
  void* net_mgr; // *net-mgr*
  void* net_players; // *net-players*
  void* random_generator; // *random-generator*
  void* setting_control; // *setting-control*
  void* sound_info; // *sound-info*
  void* viewport_array; // *viewport-array*
  void* add_hang_time; // add-hang-time
  void* kill_hud; // kill-hud
  void* make_sound_instance; // make-sound-instance
  void* process_focusable; // process-focusable
  void* rand_uint31_gen; // rand-uint31-gen
  void* revive_hud; // revive-hud
  void* send_event_function; // send-event-function
  void* set_slide_distance; // set-slide-distance
  void* sound_stop; // sound-stop
  void* spawn_hang_time_hud_single; // spawn-hang-time-hud-single
  void* spawn_power_slide_hud_single; // spawn-power-slide-hud-single
  void* stats_biggest_air; // stats-biggest-air
  void* type; // type?
} cache;

u64 execute(void* ctxt) {
  auto* c = (ExecutionContext*)ctxt;
  bool bc = false;
  u32 call_addr = 0;
  bool cop1_bc = false;
  c->daddiu(sp, sp, -160);                          // daddiu sp, sp, -160
  c->sd(ra, 0, sp);                                 // sd ra, 0(sp)
  c->sq(s4, 96, sp);                                // sq s4, 96(sp)
  c->sq(s5, 112, sp);                               // sq s5, 112(sp)
  c->sq(gp, 128, sp);                               // sq gp, 128(sp)
  c->swc1(f30, 144, sp);                            // swc1 f30, 144(sp)
  c->mov64(gp, a0);                                 // or gp, a0, r0
  c->mov64(s4, a1);                                 // or s4, a1, r0
  c->mov64(s5, a2);                                 // or s5, a2, r0
  c->load_symbol2(v1, cache.freeze_hangtime);       // lw v1, *freeze-hangtime*(s7)
  if (((s64)c->sgpr64(s7)) != ((s64)c->sgpr64(v1))) {// bnel s7, v1, L260
    c->mov64(v1, v1);                               // or v1, v1, r0
    goto block_5;
  }
  
block_2:
  c->ld(v1, 260, gp);                               // ld v1, 260(gp)
  c->andi(v1, v1, 32);                              // andi v1, v1, 32
  if (((s64)c->sgpr64(v1)) == ((s64)0)) {           // beql v1, r0, L260
    c->mov64(v1, s7);                               // or v1, s7, r0
    goto block_5;
  }
  
block_4:
  c->daddiu(v1, s7, 4);                             // daddiu v1, s7, 4
  c->lui(a0, 1);                                    // lui a0, 1
  c->dsll32(a0, a0, 0);                             // dsll32 a0, a0, 0
  c->ld(a1, 260, gp);                               // ld a1, 260(gp)
  c->and_(a0, a0, a1);                              // and a0, a0, a1
  c->movn(v1, s7, a0);                              // movn v1, s7, a0
  
block_5:
  bc = c->sgpr64(s7) == c->sgpr64(v1);              // beq s7, v1, L300
  // nop                                            // sll r0, r0, 0
  if (bc) {goto block_99;}                          // branch non-likely

  c->sw(s4, 3904, gp);                              // sw s4, 3904(gp)
  c->lui(v1, 15194);                                // lui v1, 15194
  c->ori(v1, v1, 29710);                            // ori v1, v1, 29710
  c->mtc1(f0, v1);                                  // mtc1 f0, v1
  c->lwu(v1, 796, gp);                              // lwu v1, 796(gp)
  c->dsubu(v1, s4, v1);                             // dsubu v1, s4, v1
  c->mtc1(f1, v1);                                  // mtc1 f1, v1
  c->cvtsw(f1, f1);                                 // cvt.s.w f1, f1
  c->muls(f30, f0, f1);                             // mul.s f30, f0, f1
  c->swc1(f30, 3940, gp);                           // swc1 f30, 3940(gp)
  c->lui(v1, 16192);                                // lui v1, 16192
  c->mtc1(f0, v1);                                  // mtc1 f0, v1
  cop1_bc = c->fprs[f0] < c->fprs[f30];             // c.lt.s f0, f30
  bc = !cop1_bc;                                    // bc1f L295
  // nop                                            // sll r0, r0, 0
  if (bc) {goto block_89;}                          // branch non-likely

  c->mov64(a0, gp);                                 // or a0, gp, r0
  c->lwu(v1, -4, a0);                               // lwu v1, -4(a0)
  c->lwu(t9, 116, v1);                              // lwu t9, 116(v1)
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mov64(v1, v0);                                 // or v1, v0, r0
  bc = c->sgpr64(s7) == c->sgpr64(v1);              // beq s7, v1, L267
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_22;}                          // branch non-likely

  c->lb(v1, 2116, gp);                              // lb v1, 2116(gp)
  c->load_symbol2(a0, cache.net_mgr);               // lw a0, *net-mgr*(s7)
  bc = c->sgpr64(s7) == c->sgpr64(a0);              // beq s7, a0, L261
  // nop                                            // sll r0, r0, 0
  if (bc) {goto block_10;}                          // branch non-likely

  c->load_symbol2(a0, cache.net_mgr);               // lw a0, *net-mgr*(s7)
  c->lw(a0, 152, a0);                               // lw a0, 152(a0)
  //beq r0, r0, L262                                // beq r0, r0, L262
  // nop                                            // sll r0, r0, 0
  goto block_11;                                    // branch always

  
block_10:
  c->addiu(a0, r0, 0);                              // addiu a0, r0, 0
  
block_11:
  c->dsll(a0, a0, 1);                               // dsll a0, a0, 1
  c->daddiu(a0, a0, 1);                             // daddiu a0, a0, 1
  c->dsubu(v1, v1, a0);                             // dsubu v1, v1, a0
  c->daddiu(a0, s7, 4);                             // daddiu a0, s7, 4
  c->movn(a0, s7, v1);                              // movn a0, s7, v1
  if (((s64)c->sgpr64(s7)) != ((s64)c->sgpr64(a0))) {// bnel s7, a0, L265
    c->mov64(v1, a0);                               // or v1, a0, r0
    goto block_17;
  }
  
block_13:
  c->lb(v1, 2116, gp);                              // lb v1, 2116(gp)
  c->load_symbol2(a0, cache.net_mgr);               // lw a0, *net-mgr*(s7)
  bc = c->sgpr64(s7) == c->sgpr64(a0);              // beq s7, a0, L263
  // nop                                            // sll r0, r0, 0
  if (bc) {goto block_15;}                          // branch non-likely

  c->load_symbol2(a0, cache.net_mgr);               // lw a0, *net-mgr*(s7)
  c->lw(a0, 152, a0);                               // lw a0, 152(a0)
  //beq r0, r0, L264                                // beq r0, r0, L264
  // nop                                            // sll r0, r0, 0
  goto block_16;                                    // branch always

  
block_15:
  c->addiu(a0, r0, 0);                              // addiu a0, r0, 0
  
block_16:
  c->dsll(a0, a0, 1);                               // dsll a0, a0, 1
  c->dsubu(a0, v1, a0);                             // dsubu a0, v1, a0
  c->daddiu(v1, s7, 4);                             // daddiu v1, s7, 4
  c->movn(v1, s7, a0);                              // movn v1, s7, a0
  
block_17:
  bc = c->sgpr64(s7) == c->sgpr64(v1);              // beq s7, v1, L267
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_22;}                          // branch non-likely

  c->daddiu(a1, sp, 16);                            // daddiu a1, sp, 16
  c->mov64(v1, s6);                                 // or v1, s6, r0
  bc = c->sgpr64(s7) == c->sgpr64(v1);              // beq s7, v1, L266
  c->mov64(a0, s7);                                 // or a0, s7, r0
  if (bc) {goto block_20;}                          // branch non-likely

  c->lwu(a0, 28, v1);                               // lwu a0, 28(v1)
  
block_20:
  c->sw(a0, 8, a1);                                 // sw a0, 8(a1)
  c->addiu(v1, r0, 1);                              // addiu v1, r0, 1
  c->sw(v1, 68, a1);                                // sw v1, 68(a1)
  c->load_symbol_addr(v1, cache.stats_biggest_air); // daddiu v1, s7, stats-biggest-air
  c->sw(v1, 64, a1);                                // sw v1, 64(a1)
  c->lui(v1, 17302);                                // lui v1, 17302
  c->mtc1(f0, v1);                                  // mtc1 f0, v1
  c->muls(f0, f0, f30);                             // mul.s f0, f0, f30
  c->mfc1(v1, f0);                                  // mfc1 v1, f0
  c->sd(v1, 16, a1);                                // sd v1, 16(a1)
  c->load_symbol2(t9, cache.send_event_function);   // lw t9, send-event-function(s7)
  c->load_symbol2(a0, cache.net_game_mgr);          // lw a0, *net-game-mgr*(s7)
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mov64(v1, v0);                                 // or v1, v0, r0
  c->lb(v1, 2116, gp);                              // lb v1, 2116(gp)
  c->dsll(v1, v1, 2);                               // dsll v1, v1, 2
  c->load_symbol2(a0, cache.net_players);           // lw a0, *net-players*(s7)
  c->daddu(v1, v1, a0);                             // daddu v1, v1, a0
  c->lwu(a0, 12, v1);                               // lwu a0, 12(v1)
  bc = c->sgpr64(s7) == c->sgpr64(a0);              // beq s7, a0, L267
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_22;}                          // branch non-likely

  c->lwu(v1, -4, a0);                               // lwu v1, -4(a0)
  c->lwu(t9, 276, v1);                              // lwu t9, 276(v1)
  c->lui(v1, 17302);                                // lui v1, 17302
  c->mtc1(f0, v1);                                  // mtc1 f0, v1
  c->muls(f0, f0, f30);                             // mul.s f0, f0, f30
  c->cvtws(f0, f0);                                 // cvt.w.s f0, f0
  c->mfc1(a1, f0);                                  // mfc1 a1, f0
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mov64(v1, v0);                                 // or v1, v0, r0
  
block_22:
  c->daddiu(a1, sp, 16);                            // daddiu a1, sp, 16
  c->mov64(v1, s6);                                 // or v1, s6, r0
  bc = c->sgpr64(s7) == c->sgpr64(v1);              // beq s7, v1, L268
  c->mov64(a0, s7);                                 // or a0, s7, r0
  if (bc) {goto block_24;}                          // branch non-likely

  c->lwu(a0, 28, v1);                               // lwu a0, 28(v1)
  
block_24:
  c->sw(a0, 8, a1);                                 // sw a0, 8(a1)
  c->addiu(v1, r0, 1);                              // addiu v1, r0, 1
  c->sw(v1, 68, a1);                                // sw v1, 68(a1)
  c->load_symbol_addr(v1, cache.add_hang_time);     // daddiu v1, s7, add-hang-time
  c->sw(v1, 64, a1);                                // sw v1, 64(a1)
  c->lui(v1, 15194);                                // lui v1, 15194
  c->ori(v1, v1, 29710);                            // ori v1, v1, 29710
  c->mtc1(f0, v1);                                  // mtc1 f0, v1
  c->lwu(v1, 8, s6);                                // lwu v1, 8(s6)
  c->ld(v1, 20, v1);                                // ld v1, 20(v1)
  c->lwu(a0, 8, s6);                                // lwu a0, 8(s6)
  c->ld(a0, 28, a0);                                // ld a0, 28(a0)
  c->dsubu(v1, v1, a0);                             // dsubu v1, v1, a0
  c->mtc1(f1, v1);                                  // mtc1 f1, v1
  c->cvtsw(f1, f1);                                 // cvt.s.w f1, f1
  c->muls(f0, f0, f1);                              // mul.s f0, f0, f1
  c->mfc1(v1, f0);                                  // mfc1 v1, f0
  c->sd(v1, 16, a1);                                // sd v1, 16(a1)
  c->load_symbol2(t9, cache.send_event_function);   // lw t9, send-event-function(s7)
  c->ld(v1, 3932, gp);                              // ld v1, 3932(gp)
  c->subu(a0, v1, s7);                              // subu a0, v1, s7
  if (((s64)c->sgpr64(a0)) == ((s64)0)) {           // beql a0, r0, L270
    c->mov64(a0, s7);                               // or a0, s7, r0
    goto block_29;
  }
  
block_26:
  c->sllv(a0, v1, r0);                              // sllv a0, v1, r0
  c->lwu(a2, 0, a0);                                // lwu a2, 0(a0)
  c->lw(a0, 48, a2);                                // lw a0, 48(a2)
  c->dsra32(v1, v1, 0);                             // dsra32 v1, v1, 0
  bc = c->sgpr64(v1) != c->sgpr64(a0);              // bne v1, a0, L269
  c->mov64(a0, s7);                                 // or a0, s7, r0
  if (bc) {goto block_28;}                          // branch non-likely

  c->mov64(a0, a2);                                 // or a0, a2, r0
  
block_28:
  c->mov64(v1, a0);                                 // or v1, a0, r0
  
block_29:
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mov64(v1, v0);                                 // or v1, v0, r0
  c->ld(v1, 260, gp);                               // ld v1, 260(gp)
  c->andi(v1, v1, 32);                              // andi v1, v1, 32
  if (((s64)c->sgpr64(v1)) == ((s64)0)) {           // beql v1, r0, L273
    c->mov64(v1, s7);                               // or v1, s7, r0
    goto block_40;
  }
  
block_31:
  c->load_symbol2(v1, cache.setting_control);       // lw v1, *setting-control*(s7)
  c->lwc1(f0, 492, v1);                             // lwc1 f0, 492(v1)
  c->mtc1(f1, r0);                                  // mtc1 f1, r0
  cop1_bc = c->fprs[f0] == c->fprs[f1];             // c.eq.s f0, f1
  bc = cop1_bc;                                     // bc1t L271
  c->daddiu(v1, s7, 4);                             // daddiu v1, s7, 4
  if (bc) {goto block_33;}                          // branch non-likely

  c->mov64(v1, s7);                                 // or v1, s7, r0
  
block_33:
  if (((s64)c->sgpr64(s7)) == ((s64)c->sgpr64(v1))) {// beql s7, v1, L273
    c->mov64(v1, v1);                               // or v1, v1, r0
    goto block_40;
  }
  
block_35:
  c->ld(v1, 3932, gp);                              // ld v1, 3932(gp)
  c->subu(a0, v1, s7);                              // subu a0, v1, s7
  if (((s64)c->sgpr64(a0)) == ((s64)0)) {           // beql a0, r0, L273
    c->mov64(v1, s7);                               // or v1, s7, r0
    goto block_40;
  }
  
block_37:
  c->sllv(a0, v1, r0);                              // sllv a0, v1, r0
  c->lwu(a0, 0, a0);                                // lwu a0, 0(a0)
  c->lw(a1, 48, a0);                                // lw a1, 48(a0)
  c->dsra32(v1, v1, 0);                             // dsra32 v1, v1, 0
  bc = c->sgpr64(v1) != c->sgpr64(a1);              // bne v1, a1, L272
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_39;}                          // branch non-likely

  c->mov64(v1, a0);                                 // or v1, a0, r0
  
block_39:
  c->mov64(a0, v1);                                 // or a0, v1, r0
  
block_40:
  bc = c->sgpr64(s7) == c->sgpr64(v1);              // beq s7, v1, L276
  // nop                                            // sll r0, r0, 0
  if (bc) {goto block_45;}                          // branch non-likely

  c->load_symbol2(t9, cache.make_sound_instance);   // lw t9, make-sound-instance(s7)
  c->load_symbol2(v1, cache.sound_info);            // lw v1, *sound-info*(s7)
  c->lwu(a0, 1296, v1);                             // lwu a0, 1296(v1)
  c->lwu(a1, 3880, gp);                             // lwu a1, 3880(gp)
  c->mov64(a2, s7);                                 // or a2, s7, r0
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mov64(v1, v0);                                 // or v1, v0, r0
  bc = c->sgpr64(s7) == c->sgpr64(v1);              // beq s7, v1, L274
  // nop                                            // sll r0, r0, 0
  if (bc) {goto block_43;}                          // branch non-likely

  c->lwu(v1, 80, v1);                               // lwu v1, 80(v1)
  //beq r0, r0, L275                                // beq r0, r0, L275
  // nop                                            // sll r0, r0, 0
  goto block_44;                                    // branch always

  
block_43:
  c->addiu(v1, r0, 0);                              // addiu v1, r0, 0
  
block_44:
  c->sw(v1, 3880, gp);                              // sw v1, 3880(gp)
  //beq r0, r0, L277                                // beq r0, r0, L277
  // nop                                            // sll r0, r0, 0
  goto block_46;                                    // branch always

  
block_45:
  c->load_symbol2(t9, cache.sound_stop);            // lw t9, sound-stop(s7)
  c->lwu(a0, 3880, gp);                             // lwu a0, 3880(gp)
  c->daddiu(a1, s7, 4);                             // daddiu a1, s7, #t
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->sw(r0, 3880, gp);                              // sw r0, 3880(gp)
  c->gprs[v1].du64[0] = 0;                          // or v1, r0, r0
  
block_46:
  c->ld(v1, 3924, gp);                              // ld v1, 3924(gp)
  c->subu(a0, v1, s7);                              // subu a0, v1, s7
  if (((s64)c->sgpr64(a0)) == ((s64)0)) {           // beql a0, r0, L279
    c->mov64(v1, s7);                               // or v1, s7, r0
    goto block_51;
  }
  
block_48:
  c->sllv(a0, v1, r0);                              // sllv a0, v1, r0
  c->lwu(a0, 0, a0);                                // lwu a0, 0(a0)
  c->lw(a1, 48, a0);                                // lw a1, 48(a0)
  c->dsra32(v1, v1, 0);                             // dsra32 v1, v1, 0
  bc = c->sgpr64(v1) != c->sgpr64(a1);              // bne v1, a1, L278
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_50;}                          // branch non-likely

  c->mov64(v1, a0);                                 // or v1, a0, r0
  
block_50:
  c->mov64(a0, v1);                                 // or a0, v1, r0
  
block_51:
  bc = c->sgpr64(s7) != c->sgpr64(v1);              // bne s7, v1, L294
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_88;}                          // branch non-likely

  c->ld(v1, 260, gp);                               // ld v1, 260(gp)
  c->andi(v1, v1, 8);                               // andi v1, v1, 8
  if (((s64)c->sgpr64(v1)) != ((s64)0)) {           // bnel v1, r0, L286
    c->mov64(v1, s7);                               // or v1, s7, r0
    goto block_71;
  }
  
block_54:
  c->ld(v1, 3932, gp);                              // ld v1, 3932(gp)
  c->subu(a0, v1, s7);                              // subu a0, v1, s7
  if (((s64)c->sgpr64(a0)) == ((s64)0)) {           // beql a0, r0, L281
    c->mov64(v1, s7);                               // or v1, s7, r0
    goto block_59;
  }
  
block_56:
  c->sllv(a0, v1, r0);                              // sllv a0, v1, r0
  c->lwu(a0, 0, a0);                                // lwu a0, 0(a0)
  c->lw(a1, 48, a0);                                // lw a1, 48(a0)
  c->dsra32(v1, v1, 0);                             // dsra32 v1, v1, 0
  bc = c->sgpr64(v1) != c->sgpr64(a1);              // bne v1, a1, L280
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_58;}                          // branch non-likely

  c->mov64(v1, a0);                                 // or v1, a0, r0
  
block_58:
  c->mov64(a0, v1);                                 // or a0, v1, r0
  
block_59:
  if (((s64)c->sgpr64(s7)) == ((s64)c->sgpr64(v1))) {// beql s7, v1, L285
    c->mov64(v1, v1);                               // or v1, v1, r0
    goto block_69;
  }
  
block_61:
  c->daddiu(a1, sp, 16);                            // daddiu a1, sp, 16
  c->mov64(v1, s6);                                 // or v1, s6, r0
  bc = c->sgpr64(s7) == c->sgpr64(v1);              // beq s7, v1, L282
  c->mov64(a0, s7);                                 // or a0, s7, r0
  if (bc) {goto block_63;}                          // branch non-likely

  c->lwu(a0, 28, v1);                               // lwu a0, 28(v1)
  
block_63:
  c->sw(a0, 8, a1);                                 // sw a0, 8(a1)
  c->sw(r0, 68, a1);                                // sw r0, 68(a1)
  c->load_symbol_addr(v1, cache.revive_hud);        // daddiu v1, s7, revive-hud
  c->sw(v1, 64, a1);                                // sw v1, 64(a1)
  c->load_symbol2(t9, cache.send_event_function);   // lw t9, send-event-function(s7)
  c->ld(v1, 3932, gp);                              // ld v1, 3932(gp)
  c->subu(a0, v1, s7);                              // subu a0, v1, s7
  if (((s64)c->sgpr64(a0)) == ((s64)0)) {           // beql a0, r0, L284
    c->mov64(a0, s7);                               // or a0, s7, r0
    goto block_68;
  }
  
block_65:
  c->sllv(a0, v1, r0);                              // sllv a0, v1, r0
  c->lwu(a2, 0, a0);                                // lwu a2, 0(a0)
  c->lw(a0, 48, a2);                                // lw a0, 48(a2)
  c->dsra32(v1, v1, 0);                             // dsra32 v1, v1, 0
  bc = c->sgpr64(v1) != c->sgpr64(a0);              // bne v1, a0, L283
  c->mov64(a0, s7);                                 // or a0, s7, r0
  if (bc) {goto block_67;}                          // branch non-likely

  c->mov64(a0, a2);                                 // or a0, a2, r0
  
block_67:
  c->mov64(v1, a0);                                 // or v1, a0, r0
  
block_68:
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mov64(v1, v0);                                 // or v1, v0, r0
  
block_69:
  bc = c->sgpr64(s7) == c->sgpr64(v1);              // beq s7, v1, L286
  c->daddiu(v1, s7, 4);                             // daddiu v1, s7, 4
  if (bc) {goto block_71;}                          // branch non-likely

  c->mov64(v1, s7);                                 // or v1, s7, r0
  
block_71:
  bc = c->sgpr64(s7) == c->sgpr64(v1);              // beq s7, v1, L294
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_88;}                          // branch non-likely

  c->load_symbol2(v1, cache.viewport_array);        // lw v1, *viewport-array*(s7)
  c->lwu(v1, 0, v1);                                // lwu v1, 0(v1)
  bc = c->sgpr64(v1) != 0;                          // bne v1, r0, L290
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_79;}                          // branch non-likely

  c->load_symbol2(t9, cache.spawn_hang_time_hud_single);// lw t9, spawn-hang-time-hud-single(s7)
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mov64(a0, v0);                                 // or a0, v0, r0
  bc = c->sgpr64(s7) == c->sgpr64(a0);              // beq s7, a0, L287
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_75;}                          // branch non-likely

  c->lwu(v1, 28, a0);                               // lwu v1, 28(a0)
  
block_75:
  bc = c->sgpr64(s7) == c->sgpr64(v1);              // beq s7, v1, L288
  // nop                                            // sll r0, r0, 0
  if (bc) {goto block_77;}                          // branch non-likely

  c->lwu(a0, 0, v1);                                // lwu a0, 0(v1)
  c->lw(a0, 48, a0);                                // lw a0, 48(a0)
  c->dsll32(a0, a0, 0);                             // dsll32 a0, a0, 0
  //beq r0, r0, L289                                // beq r0, r0, L289
  // nop                                            // sll r0, r0, 0
  goto block_78;                                    // branch always

  
block_77:
  c->addiu(a0, r0, 0);                              // addiu a0, r0, 0
  
block_78:
  c->sllv(v1, v1, r0);                              // sllv v1, v1, r0
  c->or_(v1, a0, v1);                               // or v1, a0, v1
  c->sd(v1, 3932, gp);                              // sd v1, 3932(gp)
  
block_79:
  c->daddiu(a1, sp, 16);                            // daddiu a1, sp, 16
  c->mov64(v1, s6);                                 // or v1, s6, r0
  bc = c->sgpr64(s7) == c->sgpr64(v1);              // beq s7, v1, L291
  c->mov64(a0, s7);                                 // or a0, s7, r0
  if (bc) {goto block_81;}                          // branch non-likely

  c->lwu(a0, 28, v1);                               // lwu a0, 28(v1)
  
block_81:
  c->sw(a0, 8, a1);                                 // sw a0, 8(a1)
  c->addiu(v1, r0, 1);                              // addiu v1, r0, 1
  c->sw(v1, 68, a1);                                // sw v1, 68(a1)
  c->load_symbol_addr(v1, cache.add_hang_time);     // daddiu v1, s7, add-hang-time
  c->sw(v1, 64, a1);                                // sw v1, 64(a1)
  c->lui(v1, 16192);                                // lui v1, 16192
  c->sd(v1, 16, a1);                                // sd v1, 16(a1)
  c->load_symbol2(t9, cache.send_event_function);   // lw t9, send-event-function(s7)
  c->ld(v1, 3932, gp);                              // ld v1, 3932(gp)
  c->subu(a0, v1, s7);                              // subu a0, v1, s7
  if (((s64)c->sgpr64(a0)) == ((s64)0)) {           // beql a0, r0, L293
    c->mov64(a0, s7);                               // or a0, s7, r0
    goto block_86;
  }
  
block_83:
  c->sllv(a0, v1, r0);                              // sllv a0, v1, r0
  c->lwu(a2, 0, a0);                                // lwu a2, 0(a0)
  c->lw(a0, 48, a2);                                // lw a0, 48(a2)
  c->dsra32(v1, v1, 0);                             // dsra32 v1, v1, 0
  bc = c->sgpr64(v1) != c->sgpr64(a0);              // bne v1, a0, L292
  c->mov64(a0, s7);                                 // or a0, s7, r0
  if (bc) {goto block_85;}                          // branch non-likely

  c->mov64(a0, a2);                                 // or a0, a2, r0
  
block_85:
  c->mov64(v1, a0);                                 // or v1, a0, r0
  
block_86:
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mov64(v1, v0);                                 // or v1, v0, r0
  c->load_symbol2(t9, cache.rand_uint31_gen);       // lw t9, rand-uint31-gen(s7)
  c->load_symbol2(a0, cache.random_generator);      // lw a0, *random-generator*(s7)
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mov64(v1, v0);                                 // or v1, v0, r0
  c->dsra(v1, v1, 8);                               // dsra v1, v1, 8
  c->lui(a0, 16256);                                // lui a0, 16256
  c->or_(v1, a0, v1);                               // or v1, a0, v1
  c->lui(a0, -16512);                               // lui a0, -16512
  c->mtc1(f0, a0);                                  // mtc1 f0, a0
  c->mtc1(f1, v1);                                  // mtc1 f1, v1
  c->adds(f0, f0, f1);                              // add.s f0, f0, f1
  c->mfc1(v1, f0);                                  // mfc1 v1, f0
  c->mtc1(f0, v1);                                  // mtc1 f0, v1
  c->lui(v1, 15820);                                // lui v1, 15820
  c->ori(v1, v1, 52429);                            // ori v1, v1, 52429
  c->mtc1(f1, v1);                                  // mtc1 f1, v1
  cop1_bc = c->fprs[f0] < c->fprs[f1];              // c.lt.s f0, f1
  bc = !cop1_bc;                                    // bc1f L294
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_88;}                          // branch non-likely

  c->lb(v1, 2116, gp);                              // lb v1, 2116(gp)
  c->dsll(v1, v1, 2);                               // dsll v1, v1, 2
  c->load_symbol2(a0, cache.net_players);           // lw a0, *net-players*(s7)
  c->daddu(v1, v1, a0);                             // daddu v1, v1, a0
  c->lwu(a0, 12, v1);                               // lwu a0, 12(v1)
  c->lwu(v1, -4, a0);                               // lwu v1, -4(a0)
  c->lwu(t9, 368, v1);                              // lwu t9, 368(v1)
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mov64(v1, v0);                                 // or v1, v0, r0
  
block_88:
  //beq r0, r0, L299                                // beq r0, r0, L299
  // nop                                            // sll r0, r0, 0
  goto block_98;                                    // branch always

  
block_89:
  c->load_symbol2(v1, cache.freeze_hangtime);       // lw v1, *freeze-hangtime*(s7)
  bc = c->sgpr64(s7) != c->sgpr64(v1);              // bne s7, v1, L299
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_98;}                          // branch non-likely

  c->daddiu(a1, sp, 16);                            // daddiu a1, sp, 16
  c->mov64(v1, s6);                                 // or v1, s6, r0
  bc = c->sgpr64(s7) == c->sgpr64(v1);              // beq s7, v1, L296
  c->mov64(a0, s7);                                 // or a0, s7, r0
  if (bc) {goto block_92;}                          // branch non-likely

  c->lwu(a0, 28, v1);                               // lwu a0, 28(v1)
  
block_92:
  c->sw(a0, 8, a1);                                 // sw a0, 8(a1)
  c->addiu(v1, r0, 1);                              // addiu v1, r0, 1
  c->sw(v1, 68, a1);                                // sw v1, 68(a1)
  c->load_symbol_addr(v1, cache.kill_hud);          // daddiu v1, s7, kill-hud
  c->sw(v1, 64, a1);                                // sw v1, 64(a1)
  c->addiu(v1, r0, 150);                            // addiu v1, r0, 150
  c->sd(v1, 16, a1);                                // sd v1, 16(a1)
  c->load_symbol2(t9, cache.send_event_function);   // lw t9, send-event-function(s7)
  c->ld(v1, 3932, gp);                              // ld v1, 3932(gp)
  c->subu(a0, v1, s7);                              // subu a0, v1, s7
  if (((s64)c->sgpr64(a0)) == ((s64)0)) {           // beql a0, r0, L298
    c->mov64(a0, s7);                               // or a0, s7, r0
    goto block_97;
  }
  
block_94:
  c->sllv(a0, v1, r0);                              // sllv a0, v1, r0
  c->lwu(a2, 0, a0);                                // lwu a2, 0(a0)
  c->lw(a0, 48, a2);                                // lw a0, 48(a2)
  c->dsra32(v1, v1, 0);                             // dsra32 v1, v1, 0
  bc = c->sgpr64(v1) != c->sgpr64(a0);              // bne v1, a0, L297
  c->mov64(a0, s7);                                 // or a0, s7, r0
  if (bc) {goto block_96;}                          // branch non-likely

  c->mov64(a0, a2);                                 // or a0, a2, r0
  
block_96:
  c->mov64(v1, a0);                                 // or v1, a0, r0
  
block_97:
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mov64(v1, v0);                                 // or v1, v0, r0
  c->sd(s7, 3932, gp);                              // sd s7, 3932(gp)
  c->load_symbol2(t9, cache.sound_stop);            // lw t9, sound-stop(s7)
  c->lwu(a0, 3880, gp);                             // lwu a0, 3880(gp)
  c->daddiu(a1, s7, 4);                             // daddiu a1, s7, #t
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->sw(r0, 3880, gp);                              // sw r0, 3880(gp)
  c->mtc1(f0, r0);                                  // mtc1 f0, r0
  c->swc1(f0, 3940, gp);                            // swc1 f0, 3940(gp)
  c->mfc1(v1, f0);                                  // mfc1 v1, f0
  
block_98:
  //beq r0, r0, L304                                // beq r0, r0, L304
  // nop                                            // sll r0, r0, 0
  goto block_108;                                   // branch always

  
block_99:
  c->load_symbol2(v1, cache.freeze_hangtime);       // lw v1, *freeze-hangtime*(s7)
  bc = c->sgpr64(s7) != c->sgpr64(v1);              // bne s7, v1, L304
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_108;}                         // branch non-likely

  c->daddiu(a1, sp, 16);                            // daddiu a1, sp, 16
  c->mov64(v1, s6);                                 // or v1, s6, r0
  bc = c->sgpr64(s7) == c->sgpr64(v1);              // beq s7, v1, L301
  c->mov64(a0, s7);                                 // or a0, s7, r0
  if (bc) {goto block_102;}                         // branch non-likely

  c->lwu(a0, 28, v1);                               // lwu a0, 28(v1)
  
block_102:
  c->sw(a0, 8, a1);                                 // sw a0, 8(a1)
  c->addiu(v1, r0, 1);                              // addiu v1, r0, 1
  c->sw(v1, 68, a1);                                // sw v1, 68(a1)
  c->load_symbol_addr(v1, cache.kill_hud);          // daddiu v1, s7, kill-hud
  c->sw(v1, 64, a1);                                // sw v1, 64(a1)
  c->addiu(v1, r0, 150);                            // addiu v1, r0, 150
  c->sd(v1, 16, a1);                                // sd v1, 16(a1)
  c->load_symbol2(t9, cache.send_event_function);   // lw t9, send-event-function(s7)
  c->ld(v1, 3932, gp);                              // ld v1, 3932(gp)
  c->subu(a0, v1, s7);                              // subu a0, v1, s7
  if (((s64)c->sgpr64(a0)) == ((s64)0)) {           // beql a0, r0, L303
    c->mov64(a0, s7);                               // or a0, s7, r0
    goto block_107;
  }
  
block_104:
  c->sllv(a0, v1, r0);                              // sllv a0, v1, r0
  c->lwu(a2, 0, a0);                                // lwu a2, 0(a0)
  c->lw(a0, 48, a2);                                // lw a0, 48(a2)
  c->dsra32(v1, v1, 0);                             // dsra32 v1, v1, 0
  bc = c->sgpr64(v1) != c->sgpr64(a0);              // bne v1, a0, L302
  c->mov64(a0, s7);                                 // or a0, s7, r0
  if (bc) {goto block_106;}                         // branch non-likely

  c->mov64(a0, a2);                                 // or a0, a2, r0
  
block_106:
  c->mov64(v1, a0);                                 // or v1, a0, r0
  
block_107:
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mov64(v1, v0);                                 // or v1, v0, r0
  c->sd(s7, 3932, gp);                              // sd s7, 3932(gp)
  c->load_symbol2(t9, cache.sound_stop);            // lw t9, sound-stop(s7)
  c->lwu(a0, 3880, gp);                             // lwu a0, 3880(gp)
  c->daddiu(a1, s7, 4);                             // daddiu a1, s7, #t
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->sw(r0, 3880, gp);                              // sw r0, 3880(gp)
  c->mtc1(f0, r0);                                  // mtc1 f0, r0
  c->swc1(f0, 3940, gp);                            // swc1 f0, 3940(gp)
  c->mfc1(v1, f0);                                  // mfc1 v1, f0
  
block_108:
  c->lui(v1, 15872);                                // lui v1, 15872
  c->mtc1(f0, v1);                                  // mtc1 f0, v1
  c->lwc1(f1, 2448, gp);                            // lwc1 f1, 2448(gp)
  cop1_bc = c->fprs[f0] < c->fprs[f1];              // c.lt.s f0, f1
  bc = !cop1_bc;                                    // bc1f L332
  // nop                                            // sll r0, r0, 0
  if (bc) {goto block_177;}                         // branch non-likely

  c->mtc1(f0, r0);                                  // mtc1 f0, r0
  c->lui(v1, -16768);                               // lui v1, -16768
  c->mtc1(f1, v1);                                  // mtc1 f1, v1
  c->lui(v1, 15194);                                // lui v1, 15194
  c->ori(v1, v1, 29710);                            // ori v1, v1, 29710
  c->mtc1(f2, v1);                                  // mtc1 f2, v1
  c->lwu(v1, 2452, gp);                             // lwu v1, 2452(gp)
  c->dsubu(v1, s4, v1);                             // dsubu v1, s4, v1
  c->mtc1(f3, v1);                                  // mtc1 f3, v1
  c->cvtsw(f3, f3);                                 // cvt.s.w f3, f3
  c->muls(f2, f2, f3);                              // mul.s f2, f2, f3
  c->adds(f1, f1, f2);                              // add.s f1, f1, f2
  c->maxs(f30, f0, f1);                             // max.s f30, f0, f1
  c->sw(r0, 3912, gp);                              // sw r0, 3912(gp)
  c->lwc1(f0, 3916, gp);                            // lwc1 f0, 3916(gp)
  c->lwu(v1, 228, gp);                              // lwu v1, 228(gp)
  c->daddiu(v1, v1, 140);                           // daddiu v1, v1, 140
  c->lqc2(vf1, 0, v1);                              // lqc2 vf1, 0(v1)
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
  c->mov128_gpr_vf(v1, vf1);                        // qmfc2.i v1, vf1
  c->mtc1(f1, v1);                                  // mtc1 f1, v1
  c->mtc1(f2, s5);                                  // mtc1 f2, s5
  c->muls(f1, f1, f2);                              // mul.s f1, f1, f2
  c->adds(f0, f0, f1);                              // add.s f0, f0, f1
  c->swc1(f0, 3916, gp);                            // swc1 f0, 3916(gp)
  c->lui(v1, 18504);                                // lui v1, 18504
  c->mtc1(f0, v1);                                  // mtc1 f0, v1
  c->lwc1(f1, 3916, gp);                            // lwc1 f1, 3916(gp)
  cop1_bc = c->fprs[f0] < c->fprs[f1];              // c.lt.s f0, f1
  bc = cop1_bc;                                     // bc1t L305
  c->daddiu(v1, s7, 4);                             // daddiu v1, s7, 4
  if (bc) {goto block_111;}                         // branch non-likely

  c->mov64(v1, s7);                                 // or v1, s7, r0
  
block_111:
  if (((s64)c->sgpr64(s7)) == ((s64)c->sgpr64(v1))) {// beql s7, v1, L308
    c->mov64(v1, v1);                               // or v1, v1, r0
    goto block_120;
  }
  
block_113:
  c->ld(v1, 3932, gp);                              // ld v1, 3932(gp)
  c->subu(a0, v1, s7);                              // subu a0, v1, s7
  if (((s64)c->sgpr64(a0)) == ((s64)0)) {           // beql a0, r0, L307
    c->mov64(v1, s7);                               // or v1, s7, r0
    goto block_118;
  }
  
block_115:
  c->sllv(a0, v1, r0);                              // sllv a0, v1, r0
  c->lwu(a0, 0, a0);                                // lwu a0, 0(a0)
  c->lw(a1, 48, a0);                                // lw a1, 48(a0)
  c->dsra32(v1, v1, 0);                             // dsra32 v1, v1, 0
  bc = c->sgpr64(v1) != c->sgpr64(a1);              // bne v1, a1, L306
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_117;}                         // branch non-likely

  c->mov64(v1, a0);                                 // or v1, a0, r0
  
block_117:
  c->mov64(a0, v1);                                 // or a0, v1, r0
  
block_118:
  bc = c->sgpr64(s7) == c->sgpr64(v1);              // beq s7, v1, L308
  c->daddiu(v1, s7, 4);                             // daddiu v1, s7, 4
  if (bc) {goto block_120;}                         // branch non-likely

  c->mov64(v1, s7);                                 // or v1, s7, r0
  
block_120:
  bc = c->sgpr64(s7) == c->sgpr64(v1);              // beq s7, v1, L331
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_176;}                         // branch non-likely

  c->daddiu(a1, sp, 16);                            // daddiu a1, sp, 16
  c->mov64(v1, s6);                                 // or v1, s6, r0
  bc = c->sgpr64(s7) == c->sgpr64(v1);              // beq s7, v1, L309
  c->mov64(a0, s7);                                 // or a0, s7, r0
  if (bc) {goto block_123;}                         // branch non-likely

  c->lwu(a0, 28, v1);                               // lwu a0, 28(v1)
  
block_123:
  c->sw(a0, 8, a1);                                 // sw a0, 8(a1)
  c->addiu(v1, r0, 1);                              // addiu v1, r0, 1
  c->sw(v1, 68, a1);                                // sw v1, 68(a1)
  c->load_symbol_addr(v1, cache.set_slide_distance);// daddiu v1, s7, set-slide-distance
  c->sw(v1, 64, a1);                                // sw v1, 64(a1)
  c->lwc1(f0, 3916, gp);                            // lwc1 f0, 3916(gp)
  c->mfc1(v1, f0);                                  // mfc1 v1, f0
  c->sd(v1, 16, a1);                                // sd v1, 16(a1)
  c->load_symbol2(t9, cache.send_event_function);   // lw t9, send-event-function(s7)
  c->ld(v1, 3924, gp);                              // ld v1, 3924(gp)
  c->subu(a0, v1, s7);                              // subu a0, v1, s7
  if (((s64)c->sgpr64(a0)) == ((s64)0)) {           // beql a0, r0, L311
    c->mov64(a0, s7);                               // or a0, s7, r0
    goto block_128;
  }
  
block_125:
  c->sllv(a0, v1, r0);                              // sllv a0, v1, r0
  c->lwu(a2, 0, a0);                                // lwu a2, 0(a0)
  c->lw(a0, 48, a2);                                // lw a0, 48(a2)
  c->dsra32(v1, v1, 0);                             // dsra32 v1, v1, 0
  bc = c->sgpr64(v1) != c->sgpr64(a0);              // bne v1, a0, L310
  c->mov64(a0, s7);                                 // or a0, s7, r0
  if (bc) {goto block_127;}                         // branch non-likely

  c->mov64(a0, a2);                                 // or a0, a2, r0
  
block_127:
  c->mov64(v1, a0);                                 // or v1, a0, r0
  
block_128:
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mov64(v1, v0);                                 // or v1, v0, r0
  c->ld(v1, 260, gp);                               // ld v1, 260(gp)
  c->andi(v1, v1, 8);                               // andi v1, v1, 8
  if (((s64)c->sgpr64(v1)) != ((s64)0)) {           // bnel v1, r0, L318
    c->mov64(v1, s7);                               // or v1, s7, r0
    goto block_147;
  }
  
block_130:
  c->ld(v1, 3924, gp);                              // ld v1, 3924(gp)
  c->subu(a0, v1, s7);                              // subu a0, v1, s7
  if (((s64)c->sgpr64(a0)) == ((s64)0)) {           // beql a0, r0, L313
    c->mov64(v1, s7);                               // or v1, s7, r0
    goto block_135;
  }
  
block_132:
  c->sllv(a0, v1, r0);                              // sllv a0, v1, r0
  c->lwu(a0, 0, a0);                                // lwu a0, 0(a0)
  c->lw(a1, 48, a0);                                // lw a1, 48(a0)
  c->dsra32(v1, v1, 0);                             // dsra32 v1, v1, 0
  bc = c->sgpr64(v1) != c->sgpr64(a1);              // bne v1, a1, L312
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_134;}                         // branch non-likely

  c->mov64(v1, a0);                                 // or v1, a0, r0
  
block_134:
  c->mov64(a0, v1);                                 // or a0, v1, r0
  
block_135:
  if (((s64)c->sgpr64(s7)) == ((s64)c->sgpr64(v1))) {// beql s7, v1, L317
    c->mov64(v1, v1);                               // or v1, v1, r0
    goto block_145;
  }
  
block_137:
  c->daddiu(a1, sp, 16);                            // daddiu a1, sp, 16
  c->mov64(v1, s6);                                 // or v1, s6, r0
  bc = c->sgpr64(s7) == c->sgpr64(v1);              // beq s7, v1, L314
  c->mov64(a0, s7);                                 // or a0, s7, r0
  if (bc) {goto block_139;}                         // branch non-likely

  c->lwu(a0, 28, v1);                               // lwu a0, 28(v1)
  
block_139:
  c->sw(a0, 8, a1);                                 // sw a0, 8(a1)
  c->sw(r0, 68, a1);                                // sw r0, 68(a1)
  c->load_symbol_addr(v1, cache.revive_hud);        // daddiu v1, s7, revive-hud
  c->sw(v1, 64, a1);                                // sw v1, 64(a1)
  c->load_symbol2(t9, cache.send_event_function);   // lw t9, send-event-function(s7)
  c->ld(v1, 3924, gp);                              // ld v1, 3924(gp)
  c->subu(a0, v1, s7);                              // subu a0, v1, s7
  if (((s64)c->sgpr64(a0)) == ((s64)0)) {           // beql a0, r0, L316
    c->mov64(a0, s7);                               // or a0, s7, r0
    goto block_144;
  }
  
block_141:
  c->sllv(a0, v1, r0);                              // sllv a0, v1, r0
  c->lwu(a2, 0, a0);                                // lwu a2, 0(a0)
  c->lw(a0, 48, a2);                                // lw a0, 48(a2)
  c->dsra32(v1, v1, 0);                             // dsra32 v1, v1, 0
  bc = c->sgpr64(v1) != c->sgpr64(a0);              // bne v1, a0, L315
  c->mov64(a0, s7);                                 // or a0, s7, r0
  if (bc) {goto block_143;}                         // branch non-likely

  c->mov64(a0, a2);                                 // or a0, a2, r0
  
block_143:
  c->mov64(v1, a0);                                 // or v1, a0, r0
  
block_144:
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mov64(v1, v0);                                 // or v1, v0, r0
  
block_145:
  bc = c->sgpr64(s7) == c->sgpr64(v1);              // beq s7, v1, L318
  c->daddiu(v1, s7, 4);                             // daddiu v1, s7, 4
  if (bc) {goto block_147;}                         // branch non-likely

  c->mov64(v1, s7);                                 // or v1, s7, r0
  
block_147:
  bc = c->sgpr64(s7) == c->sgpr64(v1);              // beq s7, v1, L322
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_155;}                         // branch non-likely

  c->load_symbol2(v1, cache.viewport_array);        // lw v1, *viewport-array*(s7)
  c->lwu(v1, 0, v1);                                // lwu v1, 0(v1)
  bc = c->sgpr64(v1) != 0;                          // bne v1, r0, L322
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_155;}                         // branch non-likely

  c->load_symbol2(t9, cache.spawn_power_slide_hud_single);// lw t9, spawn-power-slide-hud-single(s7)
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mov64(a0, v0);                                 // or a0, v0, r0
  bc = c->sgpr64(s7) == c->sgpr64(a0);              // beq s7, a0, L319
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_151;}                         // branch non-likely

  c->lwu(v1, 28, a0);                               // lwu v1, 28(a0)
  
block_151:
  bc = c->sgpr64(s7) == c->sgpr64(v1);              // beq s7, v1, L320
  // nop                                            // sll r0, r0, 0
  if (bc) {goto block_153;}                         // branch non-likely

  c->lwu(a0, 0, v1);                                // lwu a0, 0(v1)
  c->lw(a0, 48, a0);                                // lw a0, 48(a0)
  c->dsll32(a0, a0, 0);                             // dsll32 a0, a0, 0
  //beq r0, r0, L321                                // beq r0, r0, L321
  // nop                                            // sll r0, r0, 0
  goto block_154;                                   // branch always

  
block_153:
  c->addiu(a0, r0, 0);                              // addiu a0, r0, 0
  
block_154:
  c->sllv(v1, v1, r0);                              // sllv v1, v1, r0
  c->or_(v1, a0, v1);                               // or v1, a0, v1
  c->sd(v1, 3924, gp);                              // sd v1, 3924(gp)
  c->mtc1(f0, r0);                                  // mtc1 f0, r0
  c->swc1(f0, 3944, gp);                            // swc1 f0, 3944(gp)
  c->mfc1(v1, f0);                                  // mfc1 v1, f0
  
block_155:
  c->ld(v1, 3924, gp);                              // ld v1, 3924(gp)
  c->subu(a0, v1, s7);                              // subu a0, v1, s7
  if (((s64)c->sgpr64(a0)) == ((s64)0)) {           // beql a0, r0, L324
    c->mov64(v1, s7);                               // or v1, s7, r0
    goto block_160;
  }
  
block_157:
  c->sllv(a0, v1, r0);                              // sllv a0, v1, r0
  c->lwu(a0, 0, a0);                                // lwu a0, 0(a0)
  c->lw(a1, 48, a0);                                // lw a1, 48(a0)
  c->dsra32(v1, v1, 0);                             // dsra32 v1, v1, 0
  bc = c->sgpr64(v1) != c->sgpr64(a1);              // bne v1, a1, L323
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_159;}                         // branch non-likely

  c->mov64(v1, a0);                                 // or v1, a0, r0
  
block_159:
  c->mov64(a0, v1);                                 // or a0, v1, r0
  
block_160:
  if (((s64)c->sgpr64(s7)) == ((s64)c->sgpr64(v1))) {// beql s7, v1, L326
    c->mov64(v1, v1);                               // or v1, v1, r0
    goto block_168;
  }
  
block_162:
  c->lwc1(f0, 3944, gp);                            // lwc1 f0, 3944(gp)
  c->lwc1(f1, 3916, gp);                            // lwc1 f1, 3916(gp)
  cop1_bc = c->fprs[f0] < c->fprs[f1];              // c.lt.s f0, f1
  bc = cop1_bc;                                     // bc1t L325
  c->daddiu(v1, s7, 4);                             // daddiu v1, s7, 4
  if (bc) {goto block_164;}                         // branch non-likely

  c->mov64(v1, s7);                                 // or v1, s7, r0
  
block_164:
  if (((s64)c->sgpr64(s7)) == ((s64)c->sgpr64(v1))) {// beql s7, v1, L326
    c->mov64(v1, v1);                               // or v1, v1, r0
    goto block_168;
  }
  
block_166:
  c->load_symbol2(v1, cache.setting_control);       // lw v1, *setting-control*(s7)
  c->lwc1(f0, 492, v1);                             // lwc1 f0, 492(v1)
  c->mtc1(f1, r0);                                  // mtc1 f1, r0
  cop1_bc = c->fprs[f0] == c->fprs[f1];             // c.eq.s f0, f1
  bc = cop1_bc;                                     // bc1t L326
  c->daddiu(v1, s7, 4);                             // daddiu v1, s7, 4
  if (bc) {goto block_168;}                         // branch non-likely

  c->mov64(v1, s7);                                 // or v1, s7, r0
  
block_168:
  bc = c->sgpr64(s7) == c->sgpr64(v1);              // beq s7, v1, L331
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_176;}                         // branch non-likely

  c->load_symbol2(t9, cache.make_sound_instance);   // lw t9, make-sound-instance(s7)
  c->load_symbol2(v1, cache.sound_info);            // lw v1, *sound-info*(s7)
  c->lwu(a0, 1300, v1);                             // lwu a0, 1300(v1)
  c->addiu(a1, r0, 0);                              // addiu a1, r0, 0
  c->mov64(a2, s7);                                 // or a2, s7, r0
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mov64(v1, v0);                                 // or v1, v0, r0
  bc = c->sgpr64(s7) == c->sgpr64(v1);              // beq s7, v1, L327
  // nop                                            // sll r0, r0, 0
  if (bc) {goto block_171;}                         // branch non-likely

  c->lwu(v1, 80, v1);                               // lwu v1, 80(v1)
  //beq r0, r0, L328                                // beq r0, r0, L328
  // nop                                            // sll r0, r0, 0
  goto block_172;                                   // branch always

  
block_171:
  c->addiu(v1, r0, 0);                              // addiu v1, r0, 0
  
block_172:
  //beq r0, r0, L330                                // beq r0, r0, L330
  // nop                                            // sll r0, r0, 0
  goto block_174;                                   // branch always

  
block_173:
  c->lui(v1, 18080);                                // lui v1, 18080
  c->mtc1(f0, v1);                                  // mtc1 f0, v1
  c->lwc1(f1, 3944, gp);                            // lwc1 f1, 3944(gp)
  c->adds(f0, f0, f1);                              // add.s f0, f0, f1
  c->swc1(f0, 3944, gp);                            // swc1 f0, 3944(gp)
  
block_174:
  c->lwc1(f0, 3944, gp);                            // lwc1 f0, 3944(gp)
  c->lwc1(f1, 3916, gp);                            // lwc1 f1, 3916(gp)
  cop1_bc = c->fprs[f0] < c->fprs[f1];              // c.lt.s f0, f1
  bc = cop1_bc;                                     // bc1t L329
  // nop                                            // sll r0, r0, 0
  if (bc) {goto block_173;}                         // branch non-likely

  c->mov64(v1, s7);                                 // or v1, s7, r0
  
block_176:
  c->lui(v1, 16256);                                // lui v1, 16256
  c->mtc1(f0, v1);                                  // mtc1 f0, v1
  c->lwc1(f1, 700, gp);                             // lwc1 f1, 700(gp)
  c->lui(v1, 16128);                                // lui v1, 16128
  c->mtc1(f2, v1);                                  // mtc1 f2, v1
  c->muls(f2, f2, f30);                             // mul.s f2, f2, f30
  c->mtc1(f3, s5);                                  // mtc1 f3, s5
  c->muls(f2, f2, f3);                              // mul.s f2, f2, f3
  c->adds(f1, f1, f2);                              // add.s f1, f1, f2
  c->mins(f0, f0, f1);                              // min.s f0, f0, f1
  c->swc1(f0, 700, gp);                             // swc1 f0, 700(gp)
  c->mfc1(v1, f0);                                  // mfc1 v1, f0
  //beq r0, r0, L343                                // beq r0, r0, L343
  // nop                                            // sll r0, r0, 0
  goto block_200;                                   // branch always

  
block_177:
  c->lwu(v1, 3912, gp);                             // lwu v1, 3912(gp)
  c->lwu(a0, 8, s6);                                // lwu a0, 8(s6)
  c->ld(a0, 20, a0);                                // ld a0, 20(a0)
  c->lwu(a1, 8, s6);                                // lwu a1, 8(s6)
  c->ld(a1, 28, a1);                                // ld a1, 28(a1)
  c->dsubu(a0, a0, a1);                             // dsubu a0, a0, a1
  c->daddu(v1, v1, a0);                             // daddu v1, v1, a0
  c->sw(v1, 3912, gp);                              // sw v1, 3912(gp)
  c->addiu(v1, r0, 75);                             // addiu v1, r0, 75
  c->lwu(a0, 3912, gp);                             // lwu a0, 3912(gp)
  c->sltu(v1, v1, a0);                              // sltu v1, v1, a0
  bc = c->sgpr64(v1) == 0;                          // beq v1, r0, L333
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_179;}                         // branch non-likely

  c->mtc1(f0, r0);                                  // mtc1 f0, r0
  c->swc1(f0, 3916, gp);                            // swc1 f0, 3916(gp)
  c->mfc1(v1, f0);                                  // mfc1 v1, f0
  
block_179:
  c->mov64(a0, gp);                                 // or a0, gp, r0
  c->lwu(v1, -4, a0);                               // lwu v1, -4(a0)
  c->lwu(t9, 116, v1);                              // lwu t9, 116(v1)
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mov64(v1, v0);                                 // or v1, v0, r0
  bc = c->sgpr64(s7) == c->sgpr64(v1);              // beq s7, v1, L339
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_192;}                         // branch non-likely

  c->lb(v1, 2116, gp);                              // lb v1, 2116(gp)
  c->load_symbol2(a0, cache.net_mgr);               // lw a0, *net-mgr*(s7)
  bc = c->sgpr64(s7) == c->sgpr64(a0);              // beq s7, a0, L334
  // nop                                            // sll r0, r0, 0
  if (bc) {goto block_182;}                         // branch non-likely

  c->load_symbol2(a0, cache.net_mgr);               // lw a0, *net-mgr*(s7)
  c->lw(a0, 152, a0);                               // lw a0, 152(a0)
  //beq r0, r0, L335                                // beq r0, r0, L335
  // nop                                            // sll r0, r0, 0
  goto block_183;                                   // branch always

  
block_182:
  c->addiu(a0, r0, 0);                              // addiu a0, r0, 0
  
block_183:
  c->dsll(a0, a0, 1);                               // dsll a0, a0, 1
  c->dsubu(v1, v1, a0);                             // dsubu v1, v1, a0
  c->daddiu(a0, s7, 4);                             // daddiu a0, s7, 4
  c->movn(a0, s7, v1);                              // movn a0, s7, v1
  if (((s64)c->sgpr64(s7)) != ((s64)c->sgpr64(a0))) {// bnel s7, a0, L338
    c->mov64(v1, a0);                               // or v1, a0, r0
    goto block_189;
  }
  
block_185:
  c->lb(v1, 2116, gp);                              // lb v1, 2116(gp)
  c->load_symbol2(a0, cache.net_mgr);               // lw a0, *net-mgr*(s7)
  bc = c->sgpr64(s7) == c->sgpr64(a0);              // beq s7, a0, L336
  // nop                                            // sll r0, r0, 0
  if (bc) {goto block_187;}                         // branch non-likely

  c->load_symbol2(a0, cache.net_mgr);               // lw a0, *net-mgr*(s7)
  c->lw(a0, 152, a0);                               // lw a0, 152(a0)
  //beq r0, r0, L337                                // beq r0, r0, L337
  // nop                                            // sll r0, r0, 0
  goto block_188;                                   // branch always

  
block_187:
  c->addiu(a0, r0, 0);                              // addiu a0, r0, 0
  
block_188:
  c->dsll(a0, a0, 1);                               // dsll a0, a0, 1
  c->daddiu(a0, a0, 1);                             // daddiu a0, a0, 1
  c->dsubu(a0, v1, a0);                             // dsubu a0, v1, a0
  c->daddiu(v1, s7, 4);                             // daddiu v1, s7, 4
  c->movn(v1, s7, a0);                              // movn v1, s7, a0
  
block_189:
  bc = c->sgpr64(s7) == c->sgpr64(v1);              // beq s7, v1, L339
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_192;}                         // branch non-likely

  c->lb(v1, 2116, gp);                              // lb v1, 2116(gp)
  c->dsll(v1, v1, 2);                               // dsll v1, v1, 2
  c->load_symbol2(a0, cache.net_players);           // lw a0, *net-players*(s7)
  c->daddu(v1, v1, a0);                             // daddu v1, v1, a0
  c->lwu(a0, 12, v1);                               // lwu a0, 12(v1)
  bc = c->sgpr64(s7) == c->sgpr64(a0);              // beq s7, a0, L339
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_192;}                         // branch non-likely

  c->lwu(v1, -4, a0);                               // lwu v1, -4(a0)
  c->lwu(t9, 280, v1);                              // lwu t9, 280(v1)
  c->lui(v1, 14720);                                // lui v1, 14720
  c->mtc1(f0, v1);                                  // mtc1 f0, v1
  c->lwc1(f1, 3916, gp);                            // lwc1 f1, 3916(gp)
  c->muls(f0, f0, f1);                              // mul.s f0, f0, f1
  c->mfc1(a1, f0);                                  // mfc1 a1, f0
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mov64(v1, v0);                                 // or v1, v0, r0
  
block_192:
  c->daddiu(a1, sp, 16);                            // daddiu a1, sp, 16
  c->mov64(v1, s6);                                 // or v1, s6, r0
  bc = c->sgpr64(s7) == c->sgpr64(v1);              // beq s7, v1, L340
  c->mov64(a0, s7);                                 // or a0, s7, r0
  if (bc) {goto block_194;}                         // branch non-likely

  c->lwu(a0, 28, v1);                               // lwu a0, 28(v1)
  
block_194:
  c->sw(a0, 8, a1);                                 // sw a0, 8(a1)
  c->addiu(v1, r0, 1);                              // addiu v1, r0, 1
  c->sw(v1, 68, a1);                                // sw v1, 68(a1)
  c->load_symbol_addr(v1, cache.kill_hud);          // daddiu v1, s7, kill-hud
  c->sw(v1, 64, a1);                                // sw v1, 64(a1)
  c->addiu(v1, r0, 300);                            // addiu v1, r0, 300
  c->sd(v1, 16, a1);                                // sd v1, 16(a1)
  c->load_symbol2(t9, cache.send_event_function);   // lw t9, send-event-function(s7)
  c->ld(v1, 3924, gp);                              // ld v1, 3924(gp)
  c->subu(a0, v1, s7);                              // subu a0, v1, s7
  if (((s64)c->sgpr64(a0)) == ((s64)0)) {           // beql a0, r0, L342
    c->mov64(a0, s7);                               // or a0, s7, r0
    goto block_199;
  }
  
block_196:
  c->sllv(a0, v1, r0);                              // sllv a0, v1, r0
  c->lwu(a2, 0, a0);                                // lwu a2, 0(a0)
  c->lw(a0, 48, a2);                                // lw a0, 48(a2)
  c->dsra32(v1, v1, 0);                             // dsra32 v1, v1, 0
  bc = c->sgpr64(v1) != c->sgpr64(a0);              // bne v1, a0, L341
  c->mov64(a0, s7);                                 // or a0, s7, r0
  if (bc) {goto block_198;}                         // branch non-likely

  c->mov64(a0, a2);                                 // or a0, a2, r0
  
block_198:
  c->mov64(v1, a0);                                 // or v1, a0, r0
  
block_199:
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mov64(v1, v0);                                 // or v1, v0, r0
  c->sd(s7, 3924, gp);                              // sd s7, 3924(gp)
  c->sw(s4, 2452, gp);                              // sw s4, 2452(gp)
  
block_200:
  c->addiu(s5, r0, 0);                              // addiu s5, r0, 0
  //beq r0, r0, L350                                // beq r0, r0, L350
  // nop                                            // sll r0, r0, 0
  goto block_214;                                   // branch always

  
block_201:
  c->dsll(v1, s5, 3);                               // dsll v1, s5, 3
  c->daddu(v1, v1, gp);                             // daddu v1, v1, gp
  c->ld(v1, 3948, v1);                              // ld v1, 3948(v1)
  c->subu(a0, v1, s7);                              // subu a0, v1, s7
  if (((s64)c->sgpr64(a0)) == ((s64)0)) {           // beql a0, r0, L346
    c->mov64(s4, s7);                               // or s4, s7, r0
    goto block_206;
  }
  
block_203:
  c->sllv(a0, v1, r0);                              // sllv a0, v1, r0
  c->lwu(a0, 0, a0);                                // lwu a0, 0(a0)
  c->lw(a1, 48, a0);                                // lw a1, 48(a0)
  c->dsra32(v1, v1, 0);                             // dsra32 v1, v1, 0
  bc = c->sgpr64(v1) != c->sgpr64(a1);              // bne v1, a1, L345
  c->mov64(s4, s7);                                 // or s4, s7, r0
  if (bc) {goto block_205;}                         // branch non-likely

  c->mov64(s4, a0);                                 // or s4, a0, r0
  
block_205:
  c->mov64(v1, s4);                                 // or v1, s4, r0
  
block_206:
  c->load_symbol2(t9, cache.type);                  // lw t9, type?(s7)
  c->mov64(a0, s4);                                 // or a0, s4, r0
  c->load_symbol2(a1, cache.process_focusable);     // lw a1, process-focusable(s7)
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  bc = c->sgpr64(s7) == c->sgpr64(v0);              // beq s7, v0, L347
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_208;}                         // branch non-likely

  c->mov64(v1, s4);                                 // or v1, s4, r0
  
block_208:
  if (((s64)c->sgpr64(s7)) == ((s64)c->sgpr64(v1))) {// beql s7, v1, L348
    c->mov64(a0, v1);                               // or a0, v1, r0
    goto block_211;
  }
  
block_210:
  c->daddiu(a0, s7, 4);                             // daddiu a0, s7, 4
  c->ld(a1, 244, v1);                               // ld a1, 244(v1)
  c->andi(a1, a1, 16384);                           // andi a1, a1, 16384
  c->movz(a0, s7, a1);                              // movz a0, s7, a1
  
block_211:
  bc = c->sgpr64(s7) == c->sgpr64(a0);              // beq s7, a0, L349
  c->mov64(a0, s7);                                 // or a0, s7, r0
  if (bc) {goto block_213;}                         // branch non-likely

  c->mov64(a0, gp);                                 // or a0, gp, r0
  c->lwu(a1, -4, a0);                               // lwu a1, -4(a0)
  c->lwu(t9, 932, a1);                              // lwu t9, 932(a1)
  c->lwu(v1, 184, v1);                              // lwu v1, 184(v1)
  c->daddiu(a1, v1, 12);                            // daddiu a1, v1, 12
  c->mov64(a2, s5);                                 // or a2, s5, r0
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mov64(a0, v0);                                 // or a0, v0, r0
  
block_213:
  c->daddiu(s5, s5, 1);                             // daddiu s5, s5, 1
  
block_214:
  c->lwu(v1, 252, gp);                              // lwu v1, 252(gp)
  c->lb(v1, 3041, v1);                              // lb v1, 3041(v1)
  c->slt(v1, s5, v1);                               // slt v1, s5, v1
  bc = c->sgpr64(v1) != 0;                          // bne v1, r0, L344
  // nop                                            // sll r0, r0, 0
  if (bc) {goto block_201;}                         // branch non-likely

  c->mov64(v1, s7);                                 // or v1, s7, r0
  c->mov64(v1, s7);                                 // or v1, s7, r0
  c->gprs[v0].du64[0] = 0;                          // or v0, r0, r0
  c->ld(ra, 0, sp);                                 // ld ra, 0(sp)
  c->lwc1(f30, 144, sp);                            // lwc1 f30, 144(sp)
  c->lq(gp, 128, sp);                               // lq gp, 128(sp)
  c->lq(s5, 112, sp);                               // lq s5, 112(sp)
  c->lq(s4, 96, sp);                                // lq s4, 96(sp)
  //jr ra                                           // jr ra
  c->daddiu(sp, sp, 160);                           // daddiu sp, sp, 160
  goto end_of_function;                             // return

  // nop                                            // sll r0, r0, 0
  // nop                                            // sll r0, r0, 0
end_of_function:
  return c->gprs[v0].du64[0];
}

void link() {
  cache.freeze_hangtime = intern_from_c(-1, 0, "*freeze-hangtime*").c();
  cache.net_game_mgr = intern_from_c(-1, 0, "*net-game-mgr*").c();
  cache.net_mgr = intern_from_c(-1, 0, "*net-mgr*").c();
  cache.net_players = intern_from_c(-1, 0, "*net-players*").c();
  cache.random_generator = intern_from_c(-1, 0, "*random-generator*").c();
  cache.setting_control = intern_from_c(-1, 0, "*setting-control*").c();
  cache.sound_info = intern_from_c(-1, 0, "*sound-info*").c();
  cache.viewport_array = intern_from_c(-1, 0, "*viewport-array*").c();
  cache.add_hang_time = intern_from_c(-1, 0, "add-hang-time").c();
  cache.kill_hud = intern_from_c(-1, 0, "kill-hud").c();
  cache.make_sound_instance = intern_from_c(-1, 0, "make-sound-instance").c();
  cache.process_focusable = intern_from_c(-1, 0, "process-focusable").c();
  cache.rand_uint31_gen = intern_from_c(-1, 0, "rand-uint31-gen").c();
  cache.revive_hud = intern_from_c(-1, 0, "revive-hud").c();
  cache.send_event_function = intern_from_c(-1, 0, "send-event-function").c();
  cache.set_slide_distance = intern_from_c(-1, 0, "set-slide-distance").c();
  cache.sound_stop = intern_from_c(-1, 0, "sound-stop").c();
  cache.spawn_hang_time_hud_single = intern_from_c(-1, 0, "spawn-hang-time-hud-single").c();
  cache.spawn_power_slide_hud_single = intern_from_c(-1, 0, "spawn-power-slide-hud-single").c();
  cache.stats_biggest_air = intern_from_c(-1, 0, "stats-biggest-air").c();
  cache.type = intern_from_c(-1, 0, "type?").c();
  gLinkedFunctionTable.reg("wv-player-post-move-update", execute, 160);
}

} // namespace wv_player_post_move_update

namespace method_219_wvehicle {
struct Cache {
  void* quaternion; // quaternion*!
  void* quaternion_copy; // quaternion-copy!
  void* quaternion_vector_angle; // quaternion-vector-angle!
  void* vector_matrix; // vector-matrix*!
} cache;

u64 execute(void* ctxt) {
  auto* c = (ExecutionContext*)ctxt;
  bool bc = false;
  u32 call_addr = 0;
  c->daddiu(sp, sp, -320);                          // daddiu sp, sp, -320
  c->sd(ra, 0, sp);                                 // sd ra, 0(sp)
  c->sq(s3, 256, sp);                               // sq s3, 256(sp)
  c->sq(s4, 272, sp);                               // sq s4, 272(sp)
  c->sq(s5, 288, sp);                               // sq s5, 288(sp)
  c->sq(gp, 304, sp);                               // sq gp, 304(sp)
  c->mov64(s3, a0);                                 // or s3, a0, r0
  c->mov64(s5, a1);                                 // or s5, a1, r0
  c->mov64(s4, a2);                                 // or s4, a2, r0
  c->daddiu(gp, sp, 16);                            // daddiu gp, sp, 16
  c->daddiu(v1, gp, 128);                           // daddiu v1, gp, 128
  c->lui(a0, 16256);                                // lui a0, 16256
  c->mtc1(f0, a0);                                  // mtc1 f0, a0
  c->swc1(f0, 0, v1);                               // swc1 f0, 0(v1)
  c->mtc1(f0, r0);                                  // mtc1 f0, r0
  c->swc1(f0, 4, v1);                               // swc1 f0, 4(v1)
  c->mtc1(f0, r0);                                  // mtc1 f0, r0
  c->swc1(f0, 8, v1);                               // swc1 f0, 8(v1)
  c->lui(a0, 16256);                                // lui a0, 16256
  c->mtc1(f0, a0);                                  // mtc1 f0, a0
  c->swc1(f0, 12, v1);                              // swc1 f0, 12(v1)
  c->daddiu(v1, gp, 144);                           // daddiu v1, gp, 144
  c->mtc1(f0, r0);                                  // mtc1 f0, r0
  c->swc1(f0, 0, v1);                               // swc1 f0, 0(v1)
  c->lui(a0, 16256);                                // lui a0, 16256
  c->mtc1(f0, a0);                                  // mtc1 f0, a0
  c->swc1(f0, 4, v1);                               // swc1 f0, 4(v1)
  c->mtc1(f0, r0);                                  // mtc1 f0, r0
  c->swc1(f0, 8, v1);                               // swc1 f0, 8(v1)
  c->lui(a0, 16256);                                // lui a0, 16256
  c->mtc1(f0, a0);                                  // mtc1 f0, a0
  c->swc1(f0, 12, v1);                              // swc1 f0, 12(v1)
  c->load_symbol2(t9, cache.quaternion_copy);       // lw t9, quaternion-copy!(s7)
  c->daddiu(a0, gp, 112);                           // daddiu a0, gp, 112
  c->lwu(v1, 184, s3);                              // lwu v1, 184(s3)
  c->daddiu(a1, v1, 28);                            // daddiu a1, v1, 28
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->daddu(v1, r0, gp);                             // daddu v1, r0, gp
  c->lwu(a0, 228, s3);                              // lwu a0, 228(s3)
  c->daddiu(a3, a0, 172);                           // daddiu a3, a0, 172
  c->lq(a0, 0, a3);                                 // lq a0, 0(a3)
  c->lq(a1, 16, a3);                                // lq a1, 16(a3)
  c->lq(a2, 32, a3);                                // lq a2, 32(a3)
  c->lq(a3, 48, a3);                                // lq a3, 48(a3)
  c->sq(a0, 0, v1);                                 // sq a0, 0(v1)
  c->sq(a1, 16, v1);                                // sq a1, 16(v1)
  c->sq(a2, 32, v1);                                // sq a2, 32(v1)
  c->sq(a3, 48, v1);                                // sq a3, 48(v1)
  c->daddiu(v1, gp, 160);                           // daddiu v1, gp, 160
  c->daddu(a0, r0, s4);                             // daddu a0, r0, s4
  c->lq(a0, 0, a0);                                 // lq a0, 0(a0)
  c->sq(a0, 0, v1);                                 // sq a0, 0(v1)
  c->lwc1(f0, 160, gp);                             // lwc1 f0, 160(gp)
  c->lwc1(f1, 36, s4);                              // lwc1 f1, 36(s4)
  c->adds(f0, f0, f1);                              // add.s f0, f0, f1
  c->swc1(f0, 160, gp);                             // swc1 f0, 160(gp)
  c->lwc1(f0, 160, gp);                             // lwc1 f0, 160(gp)
  c->lwc1(f1, 204, s5);                             // lwc1 f1, 204(s5)
  c->muls(f0, f0, f1);                              // mul.s f0, f0, f1
  c->swc1(f0, 160, gp);                             // swc1 f0, 160(gp)
  c->lwc1(f0, 164, gp);                             // lwc1 f0, 164(gp)
  c->lwc1(f1, 56, s4);                              // lwc1 f1, 56(s4)
  c->adds(f0, f0, f1);                              // add.s f0, f0, f1
  c->swc1(f0, 164, gp);                             // swc1 f0, 164(gp)
  c->daddiu(v1, s5, 16);                            // daddiu v1, s5, 16
  c->daddiu(a0, gp, 160);                           // daddiu a0, gp, 160
  c->daddiu(a1, s5, 48);                            // daddiu a1, s5, 48
  c->lwc1(f0, 40, s4);                              // lwc1 f0, 40(s4)
  c->lwc1(f1, 204, s5);                             // lwc1 f1, 204(s5)
  c->muls(f0, f0, f1);                              // mul.s f0, f0, f1
  c->lqc2(vf2, 0, a1);                              // lqc2 vf2, 0(a1)
  c->lqc2(vf1, 0, a0);                              // lqc2 vf1, 0(a0)
  c->mfc1(a0, f0);                                  // mfc1 a0, f0
  c->mov128_vf_gpr(vf3, a0);                        // qmtc2.i vf3, a0
  c->vadd_bc(DEST::w, BC::x, vf4, vf0, vf0);        // vaddx.w vf4, vf0, vf0
  c->vmula_bc(DEST::xyzw, BC::x, vf2, vf3);         // vmulax.xyzw acc, vf2, vf3
  c->vmadd_bc(DEST::xyz, BC::w, vf4, vf1, vf0);     // vmaddw.xyz vf4, vf1, vf0
  c->sqc2(vf4, 0, v1);                              // sqc2 vf4, 0(v1)
  c->lwc1(f0, 56, s4);                              // lwc1 f0, 56(s4)
  c->lwc1(f1, 32, s4);                              // lwc1 f1, 32(s4)
  c->lwc1(f2, 44, s4);                              // lwc1 f2, 44(s4)
  c->muls(f1, f1, f2);                              // mul.s f1, f1, f2
  c->adds(f0, f0, f1);                              // add.s f0, f0, f1
  c->lui(v1, -16512);                               // lui v1, -16512
  c->mtc1(f1, v1);                                  // mtc1 f1, v1
  c->lwc1(f2, 184, s5);                             // lwc1 f2, 184(s5)
  c->muls(f1, f1, f2);                              // mul.s f1, f1, f2
  c->lwc1(f2, 48, s4);                              // lwc1 f2, 48(s4)
  c->muls(f1, f1, f2);                              // mul.s f1, f1, f2
  c->adds(f0, f0, f1);                              // add.s f0, f0, f1
  c->swc1(f0, 224, gp);                             // swc1 f0, 224(gp)
  c->daddiu(v1, gp, 160);                           // daddiu v1, gp, 160
  c->daddu(a0, r0, s4);                             // daddu a0, r0, s4
  c->lq(a0, 0, a0);                                 // lq a0, 0(a0)
  c->sq(a0, 0, v1);                                 // sq a0, 0(v1)
  c->lwc1(f0, 160, gp);                             // lwc1 f0, 160(gp)
  c->lwc1(f1, 204, s5);                             // lwc1 f1, 204(s5)
  c->muls(f0, f0, f1);                              // mul.s f0, f0, f1
  c->swc1(f0, 160, gp);                             // swc1 f0, 160(gp)
  c->lwc1(f0, 164, gp);                             // lwc1 f0, 164(gp)
  c->lwc1(f1, 224, gp);                             // lwc1 f1, 224(gp)
  c->adds(f0, f0, f1);                              // add.s f0, f0, f1
  c->swc1(f0, 164, gp);                             // swc1 f0, 164(gp)
  c->daddiu(v1, gp, 160);                           // daddiu v1, gp, 160
  c->daddiu(a0, gp, 160);                           // daddiu a0, gp, 160
  c->daddiu(a1, s5, 48);                            // daddiu a1, s5, 48
  c->lwc1(f0, 40, s4);                              // lwc1 f0, 40(s4)
  c->lwc1(f1, 204, s5);                             // lwc1 f1, 204(s5)
  c->muls(f0, f0, f1);                              // mul.s f0, f0, f1
  c->lqc2(vf2, 0, a1);                              // lqc2 vf2, 0(a1)
  c->lqc2(vf1, 0, a0);                              // lqc2 vf1, 0(a0)
  c->mfc1(a0, f0);                                  // mfc1 a0, f0
  c->mov128_vf_gpr(vf3, a0);                        // qmtc2.i vf3, a0
  c->vadd_bc(DEST::w, BC::x, vf4, vf0, vf0);        // vaddx.w vf4, vf0, vf0
  c->vmula_bc(DEST::xyzw, BC::x, vf2, vf3);         // vmulax.xyzw acc, vf2, vf3
  c->vmadd_bc(DEST::xyz, BC::w, vf4, vf1, vf0);     // vmaddw.xyz vf4, vf1, vf0
  c->sqc2(vf4, 0, v1);                              // sqc2 vf4, 0(v1)
  c->load_symbol2(t9, cache.vector_matrix);         // lw t9, vector-matrix*!(s7)
  c->daddiu(a0, gp, 176);                           // daddiu a0, gp, 176
  c->daddiu(a1, gp, 160);                           // daddiu a1, gp, 160
  c->daddu(a2, r0, gp);                             // daddu a2, r0, gp
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->load_symbol2(t9, cache.quaternion_vector_angle);// lw t9, quaternion-vector-angle!(s7)
  c->daddiu(a0, gp, 96);                            // daddiu a0, gp, 96
  c->daddiu(a1, gp, 144);                           // daddiu a1, gp, 144
  c->lwc1(f0, 192, s5);                             // lwc1 f0, 192(s5)
  c->mfc1(a2, f0);                                  // mfc1 a2, f0
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->load_symbol2(t9, cache.quaternion_vector_angle);// lw t9, quaternion-vector-angle!(s7)
  c->daddiu(a0, gp, 80);                            // daddiu a0, gp, 80
  c->daddiu(a1, gp, 128);                           // daddiu a1, gp, 128
  c->lwc1(f0, 196, s5);                             // lwc1 f0, 196(s5)
  c->mfc1(a2, f0);                                  // mfc1 a2, f0
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->load_symbol2(t9, cache.quaternion);            // lw t9, quaternion*!(s7)
  c->daddiu(a0, gp, 64);                            // daddiu a0, gp, 64
  c->daddiu(a1, gp, 96);                            // daddiu a1, gp, 96
  c->daddiu(a2, gp, 80);                            // daddiu a2, gp, 80
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->load_symbol2(t9, cache.quaternion);            // lw t9, quaternion*!(s7)
  c->daddiu(a0, s5, 128);                           // daddiu a0, s5, 128
  c->daddiu(a1, gp, 112);                           // daddiu a1, gp, 112
  c->daddiu(a2, gp, 64);                            // daddiu a2, gp, 64
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->daddiu(v1, s5, 112);                           // daddiu v1, s5, 112
  c->daddiu(a0, gp, 176);                           // daddiu a0, gp, 176
  c->lq(a0, 0, a0);                                 // lq a0, 0(a0)
  c->sq(a0, 0, v1);                                 // sq a0, 0(v1)
  c->gprs[v0].du64[0] = 0;                          // or v0, r0, r0
  c->ld(ra, 0, sp);                                 // ld ra, 0(sp)
  c->lq(gp, 304, sp);                               // lq gp, 304(sp)
  c->lq(s5, 288, sp);                               // lq s5, 288(sp)
  c->lq(s4, 272, sp);                               // lq s4, 272(sp)
  c->lq(s3, 256, sp);                               // lq s3, 256(sp)
  //jr ra                                           // jr ra
  c->daddiu(sp, sp, 320);                           // daddiu sp, sp, 320
  goto end_of_function;                             // return

  // nop                                            // sll r0, r0, 0
  // nop                                            // sll r0, r0, 0
  // nop                                            // sll r0, r0, 0
end_of_function:
  return c->gprs[v0].du64[0];
}

void link() {
  cache.quaternion = intern_from_c(-1, 0, "quaternion*!").c();
  cache.quaternion_copy = intern_from_c(-1, 0, "quaternion-copy!").c();
  cache.quaternion_vector_angle = intern_from_c(-1, 0, "quaternion-vector-angle!").c();
  cache.vector_matrix = intern_from_c(-1, 0, "vector-matrix*!").c();
  gLinkedFunctionTable.reg("(method 219 wvehicle)", execute, 320);
}

} // namespace method_219_wvehicle

} // namespace Mips2C::jakx
