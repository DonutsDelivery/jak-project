#pragma once

#include <mutex>
#include <string>

#include "game/graphics/opengl_renderer/BucketRenderer.h"

// MPEG2 FMV player for Jak X.
// Game thread calls request_play/request_stop/is_done.
// Render thread calls render_frame each frame (no-ops when idle).
class FMVPlayer {
 public:
  FMVPlayer();
  ~FMVPlayer();
  FMVPlayer(const FMVPlayer&) = delete;
  FMVPlayer& operator=(const FMVPlayer&) = delete;

  // Called from game thread (GOAL pc-function callbacks)
  void request_play(const std::string& iso_relative_path);
  void request_stop();
  bool is_done() const;
  bool is_active() const;

  // Called from render thread once per frame
  void render_frame(SharedRenderState* render_state, ScopedProfilerNode& prof);

 private:
  // ffmpeg opaque pointers (void* to avoid pulling ffmpeg headers into the .h)
  void* m_fmt_ctx = nullptr;
  void* m_codec_ctx = nullptr;
  void* m_packet = nullptr;
  void* m_frame = nullptr;
  void* m_rgb_frame = nullptr;
  void* m_sws_ctx = nullptr;
  int m_video_stream_idx = -1;

  // RGB pixel buffer (owned, matched to frame dimensions)
  uint8_t* m_rgb_buf = nullptr;
  int m_rgb_buf_size = 0;
  int m_frame_width = 0;
  int m_frame_height = 0;

  // GL resources
  GLuint m_vao = 0;
  GLuint m_vbo = 0;
  GLuint m_texture = 0;

  // PTS timing
  double m_play_start_wall = 0.0;
  double m_stream_time_base = 0.0;
  double m_current_pts_secs = 0.0;    // PTS of the frame currently in m_texture
  double m_frame_duration_secs = 0.0; // nominal duration of one frame (from pkt_duration)

  // State machine — all transitions guarded by m_mutex
  enum class Phase { IDLE, PLAY_REQ, PLAYING, STOP_REQ, DONE };
  mutable std::mutex m_mutex;
  Phase m_phase = Phase::IDLE;
  std::string m_pending_path;

  void open_file(const std::string& path);
  void close_file();
  bool decode_and_draw(SharedRenderState* render_state, ScopedProfilerNode& prof);
};

// Global singleton — set by OpenGLRenderer constructor, read by pc_fmv_* callbacks.
namespace Gfx {
extern FMVPlayer* g_fmv_player;
}
