//--------------------------MIPS2C---------------------
// clang-format off
#include "game/mips2c/mips2c_private.h"
#include "game/kernel/jakx/kscheme.h"
using ::jakx::intern_from_c;
namespace Mips2C::jakx {
namespace net_player_init_local {
struct Cache {
  void* game_info; // *game-info*
  void* net_mgr; // *net-mgr*
  void* net_players; // *net-players*
  void* net_world; // *net-world*
  void* enter_state; // enter-state
  void* update_active_net_players; // update-active-net-players
} cache;

u64 execute(void* ctxt) {
  auto* c = (ExecutionContext*)ctxt;
  bool bc = false;
  u32 call_addr = 0;
  bool cop1_bc = false;
  c->daddiu(sp, sp, -32);                           // daddiu sp, sp, -32
  c->sd(ra, 0, sp);                                 // sd ra, 0(sp)
  c->sq(gp, 16, sp);                                // sq gp, 16(sp)
  c->mov64(gp, a0);                                 // or gp, a0, r0
  c->mov64(a0, s6);                                 // or a0, s6, r0
  c->lwu(v1, -4, a0);                               // lwu v1, -4(a0)
  c->lwu(t9, 220, v1);                              // lwu t9, 220(v1)
  c->mov64(a1, gp);                                 // or a1, gp, r0
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mov64(v1, v0);                                 // or v1, v0, r0
  c->lb(v1, 284, s6);                               // lb v1, 284(s6)
  c->dsll(v1, v1, 2);                               // dsll v1, v1, 2
  c->load_symbol2(a0, cache.net_players);           // lw a0, *net-players*(s7)
  c->daddu(v1, v1, a0);                             // daddu v1, v1, a0
  c->sw(s6, 12, v1);                                // sw s6, 12(v1)
  c->load_symbol2(v1, cache.net_world);             // lw v1, *net-world*(s7)
  c->dsll(a0, gp, 5);                               // dsll a0, gp, 5
  c->daddu(v1, v1, a0);                             // daddu v1, v1, a0
  c->lbu(v1, 203, v1);                              // lbu v1, 203(v1)
  c->sb(v1, 237, s6);                               // sb v1, 237(s6)
  c->load_symbol2(v1, cache.game_info);             // lw v1, *game-info*(s7)
  c->ld(v1, 1084, v1);                              // ld v1, 1084(v1)
  c->andi(v1, v1, 1);                               // andi v1, v1, 1
  if (((s64)c->sgpr64(v1)) == ((s64)0)) {           // beql v1, r0, L228
    c->mov64(v1, s7);                               // or v1, s7, r0
    goto block_4;
  }

//block_2:
  c->load_symbol2(a0, cache.game_info);             // lw a0, *game-info*(s7)
  c->lwu(v1, -4, a0);                               // lwu v1, -4(a0)
  c->lwu(t9, 128, v1);                              // lwu t9, 128(v1)
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mov64(v1, v0);                                 // or v1, v0, r0
  c->mtc1(f0, v1);                                  // mtc1 f0, v1
  c->lui(v1, 17096);                                // lui v1, 17096
  c->mtc1(f1, v1);                                  // mtc1 f1, v1
  cop1_bc = c->fprs[f0] == c->fprs[f1];             // c.eq.s f0, f1
  bc = cop1_bc;                                     // bc1t L228
  c->daddiu(v1, s7, 4);                             // daddiu v1, s7, 4
  if (bc) {goto block_4;}                           // branch non-likely

  c->mov64(v1, s7);                                 // or v1, s7, r0

block_4:
  bc = c->sgpr64(s7) == c->sgpr64(v1);              // beq s7, v1, L229
  c->mov64(v1, s7);                                 // or v1, s7, r0
  if (bc) {goto block_6;}                           // branch non-likely

  c->lbu(v1, 285, s6);                              // lbu v1, 285(s6)
  c->ori(v1, v1, 16);                               // ori v1, v1, 16
  c->sb(v1, 285, s6);                               // sb v1, 285(s6)

block_6:
  c->load_symbol2(t9, cache.update_active_net_players);// lw t9, update-active-net-players(s7)
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mov64(a0, s6);                                 // or a0, s6, r0
  c->lwu(v1, -4, a0);                               // lwu v1, -4(a0)
  c->lwu(t9, 152, v1);                              // lwu t9, 152(v1)
  c->slt(v1, gp, r0);                               // slt v1, gp, r0
  c->daddiu(a1, s7, 4);                             // daddiu a1, s7, 4
  c->movn(a1, s7, v1);                              // movn a1, s7, v1
  if (((s64)c->sgpr64(s7)) == ((s64)c->sgpr64(a1))) {// beql s7, a1, L230
    c->mov64(v1, a1);                               // or v1, a1, r0
    goto block_9;
  }

//block_8:
  c->slti(a1, gp, 16);                              // slti a1, gp, 16
  c->daddiu(v1, s7, 4);                             // daddiu v1, s7, 4
  c->movz(v1, s7, a1);                              // movz v1, s7, a1

block_9:
  bc = c->sgpr64(s7) == c->sgpr64(v1);              // beq s7, v1, L233
  // nop                                            // sll r0, r0, 0
  if (bc) {goto block_14;}                          // branch non-likely

  c->load_symbol2(v1, cache.net_mgr);               // lw v1, *net-mgr*(s7)
  bc = c->sgpr64(s7) == c->sgpr64(v1);              // beq s7, v1, L231
  // nop                                            // sll r0, r0, 0
  if (bc) {goto block_12;}                          // branch non-likely

  c->load_symbol2(v1, cache.net_mgr);               // lw v1, *net-mgr*(s7)
  c->lw(a1, 152, v1);                               // lw a1, 152(v1)
  //beq r0, r0, L232                                // beq r0, r0, L232
  // nop                                            // sll r0, r0, 0
  goto block_13;                                    // branch always


block_12:
  c->addiu(a1, r0, 0);                              // addiu a1, r0, 0

block_13:
  //beq r0, r0, L234                                // beq r0, r0, L234
  // nop                                            // sll r0, r0, 0
  goto block_15;                                    // branch always


block_14:
  c->addiu(a1, r0, 8);                              // addiu a1, r0, 8

block_15:
  c->daddiu(a2, gp, 1000);                          // daddiu a2, gp, 1000
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->mov64(v1, v0);                                 // or v1, v0, r0
  c->load_symbol2(t9, cache.enter_state);           // lw t9, enter-state(s7)
  c->lwu(v1, -4, s6);                               // lwu v1, -4(s6)
  c->lwu(v1, 184, v1);                              // lwu v1, 184(v1)
  c->sw(v1, 76, s6);                                // sw v1, 76(s6)
  call_addr = c->gprs[t9].du32[0];                  // function call:
  c->sll(v0, ra, 0);                                // sll v0, ra, 0
  c->jalr(call_addr);                               // jalr ra, t9
  c->gprs[v0].du64[0] = 0;                          // or v0, r0, r0
  c->ld(ra, 0, sp);                                 // ld ra, 0(sp)
  c->lq(gp, 16, sp);                                // lq gp, 16(sp)
  //jr ra                                           // jr ra
  c->daddiu(sp, sp, 32);                            // daddiu sp, sp, 32
  goto end_of_function;                             // return

  // nop                                            // sll r0, r0, 0
  // nop                                            // sll r0, r0, 0
  // nop                                            // sll r0, r0, 0
end_of_function:
  return c->gprs[v0].du64[0];
}

void link() {
  cache.game_info = intern_from_c(-1, 0, "*game-info*").c();
  cache.net_mgr = intern_from_c(-1, 0, "*net-mgr*").c();
  cache.net_players = intern_from_c(-1, 0, "*net-players*").c();
  cache.net_world = intern_from_c(-1, 0, "*net-world*").c();
  cache.enter_state = intern_from_c(-1, 0, "enter-state").c();
  cache.update_active_net_players = intern_from_c(-1, 0, "update-active-net-players").c();
  gLinkedFunctionTable.reg("net-player-init-local", execute, 32);
}

} // namespace net_player_init_local
} // namespace Mips2C::jakx
