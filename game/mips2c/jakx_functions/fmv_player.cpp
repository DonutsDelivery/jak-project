//--------------------------MIPS2C---------------------
// clang-format off
#include <cstring>
#include "game/mips2c/mips2c_private.h"
#include "game/kernel/jakx/kscheme.h"
#include "game/graphics/opengl_renderer/FMVPlayer.h"
using ::jakx::intern_from_c;

// JakX-native PC bridges for the four fmv-player functions that cannot be
// decompiled to GOAL:
//
//   fmv-file-init  — BAD PROLOGUE (sd s7 + bgezal r0 PIC pattern)
//   fmv-get-time   — BAD PROLOGUE (same)
//   fmv-file-read  — BAD PROLOGUE (same)
//   fmv-memcpy     — 128-bit lq/sq instructions (no GOAL type-system equivalent)
//
// On PS2 these drove the IPU MPEG-2 hardware directly.  On PC, the C++
// FMVPlayer (game/graphics/opengl_renderer/FMVPlayer.cpp) runs in the render
// thread and handles decode/display/timing autonomously.  The GOAL fmv-player
// state machine still calls these via function-pointer; the stubs make it
// happy without touching PS2 hardware.

namespace Mips2C::jakx {

// ---------------------------------------------------------------------------
// fmv-memcpy(dst=a0, src=a1, count=a2)
// PS2: 128-bit aligned block copy using lq/sq.  PC: plain memcpy.
// ---------------------------------------------------------------------------
namespace fmv_memcpy {
u64 execute(void* ctxt) {
  auto* c = (ExecutionContext*)ctxt;
  u32 dst   = c->gprs[a0].du32[0];
  u32 src   = c->gprs[a1].du32[0];
  u32 count = c->gprs[a2].du32[0];
  if (count && dst && src)
    memcpy(g_ee_main_mem + dst, g_ee_main_mem + src, count);
  c->gprs[v0].du64[0] = 0;
  return c->gprs[v0].du64[0];
}
void link() {
  gLinkedFunctionTable.reg("fmv-memcpy", execute, 128);
}
} // namespace fmv_memcpy

// ---------------------------------------------------------------------------
// fmv-file-read()
// PS2: feeds one disc sector to the IPU bitstream FIFO via IOP RPC.
// PC: no-op — ffmpeg decode runs in the render thread.
// ---------------------------------------------------------------------------
namespace fmv_file_read {
u64 execute(void* ctxt) {
  auto* c = (ExecutionContext*)ctxt;
  c->gprs[v0].du64[0] = 0;
  return c->gprs[v0].du64[0];
}
void link() {
  gLinkedFunctionTable.reg("fmv-file-read", execute, 64);
}
} // namespace fmv_file_read

// ---------------------------------------------------------------------------
// fmv-get-time()
// PS2: returns current PTS from IOP sound-clock register.
// PC: returns 0 while the C++ FMVPlayer is active, -2 when done.
//   -2 is the value the PS2 code returned on IOP error/end-of-stream, which
//   the GOAL state machine treats as "stop looping".
// ---------------------------------------------------------------------------
namespace fmv_get_time {
u64 execute(void* ctxt) {
  auto* c = (ExecutionContext*)ctxt;
  bool done = Gfx::g_fmv_player && Gfx::g_fmv_player->is_done();
  c->gprs[v0].ds64[0] = done ? -2 : 0;
  return c->gprs[v0].du64[0];
}
void link() {
  gLinkedFunctionTable.reg("fmv-get-time", execute, 64);
}
} // namespace fmv_get_time

// ---------------------------------------------------------------------------
// fmv-file-init(flag=a0)
// PS2: if flag=#f, resets fmv-work.finished; if truthy, initialises work
//   struct fields and opens the IOP disc stream.
// PC: replicates the struct initialisation so downstream GOAL code sees
//   consistent state.  When flag is truthy also triggers the C++ FMVPlayer
//   using *fmv-m2v-name* (set by fmv-player-init-by-other before this call).
// ---------------------------------------------------------------------------
namespace fmv_file_init {
struct Cache {
  void* fmv_work;      // *fmv-work*
  void* fmv_m2v_name;  // *fmv-m2v-name*
} cache;

u64 execute(void* ctxt) {
  auto* c = (ExecutionContext*)ctxt;
  u32 flag = c->gprs[a0].du32[0];

  // Dereference *fmv-work* symbol to get the fmv-work struct pointer.
  u32 work = 0;
  memcpy(&work, (u8*)cache.fmv_work - 1, 4);

  if (!work)
    goto done;

  if (!flag) {
    // Reset fmv-work.finished (offset 76) to #f.
    u32 false_val = c->gprs[s7].du32[0];  // s7 = #f in GOAL
    memcpy(g_ee_main_mem + work + 76, &false_val, 4);
  } else {
    // Initialise work struct fields (mirror PS2 asm).
    u32 false_val = c->gprs[s7].du32[0];
    u32 zero = 0;
    u32 neg1 = 0xffffffffu;
    memcpy(g_ee_main_mem + work + 68, &false_val, 4);  // own-rpc  = #f
    memcpy(g_ee_main_mem + work + 40, &zero,      4);  // cursor   = 0
    memcpy(g_ee_main_mem + work +  0, &zero,      4);  // current-buffer = 0
    memcpy(g_ee_main_mem + work +  8, &neg1,      4);  // buffers[0].y = 0xffffffff
    memcpy(g_ee_main_mem + work + 24, &neg1,      4);  // buffers[1].y = 0xffffffff

    // Trigger C++ FMVPlayer — read filename from *fmv-m2v-name*.
    if (Gfx::g_fmv_player) {
      u32 name_ptr = 0;
      memcpy(&name_ptr, (u8*)cache.fmv_m2v_name - 1, 4);
      if (name_ptr > 8) {
        // GOAL string layout: 4-byte type tag, 4-byte allocated-length, then chars.
        const char* path = (const char*)(g_ee_main_mem + name_ptr + 8);
        Gfx::g_fmv_player->request_play(path);
      }
    }
  }

done:
  c->gprs[v0].du64[0] = 0;
  return c->gprs[v0].du64[0];
}

void link() {
  cache.fmv_work     = intern_from_c(-1, 0, "*fmv-work*").c();
  cache.fmv_m2v_name = intern_from_c(-1, 0, "*fmv-m2v-name*").c();
  gLinkedFunctionTable.reg("fmv-file-init", execute, 128);
}
} // namespace fmv_file_init

} // namespace Mips2C::jakx
