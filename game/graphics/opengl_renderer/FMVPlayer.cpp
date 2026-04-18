#include "FMVPlayer.h"

extern "C" {
#include <libavcodec/avcodec.h>
#include <libavformat/avformat.h>
#include <libavutil/imgutils.h>
#include <libswscale/swscale.h>
}

#include <chrono>

#include "common/log/log.h"

#include "game/graphics/opengl_renderer/Shader.h"

namespace Gfx {
FMVPlayer* g_fmv_player = nullptr;
}

static double wall_time_now() {
  using namespace std::chrono;
  return duration<double>(steady_clock::now().time_since_epoch()).count();
}

// fullscreen quad: two triangles covering NDC [-1,1]x[-1,1]
static constexpr float kQuadVerts[] = {
    -1.f, -1.f,  // bottom-left
    1.f,  -1.f,  // bottom-right
    -1.f, 1.f,   // top-left
    1.f,  -1.f,  // bottom-right
    1.f,  1.f,   // top-right
    -1.f, 1.f,   // top-left
};

FMVPlayer::FMVPlayer() {
  glGenVertexArrays(1, &m_vao);
  glGenBuffers(1, &m_vbo);
  glBindVertexArray(m_vao);
  glBindBuffer(GL_ARRAY_BUFFER, m_vbo);
  glBufferData(GL_ARRAY_BUFFER, sizeof(kQuadVerts), kQuadVerts, GL_STATIC_DRAW);
  glEnableVertexAttribArray(0);
  glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 2 * sizeof(float), nullptr);
  glBindBuffer(GL_ARRAY_BUFFER, 0);
  glBindVertexArray(0);

  glGenTextures(1, &m_texture);
  glBindTexture(GL_TEXTURE_2D, m_texture);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
  glBindTexture(GL_TEXTURE_2D, 0);

  m_packet = av_packet_alloc();
  m_frame = av_frame_alloc();
  m_rgb_frame = av_frame_alloc();
}

FMVPlayer::~FMVPlayer() {
  close_file();
  if (m_packet)
    av_packet_free(reinterpret_cast<AVPacket**>(&m_packet));
  if (m_frame)
    av_frame_free(reinterpret_cast<AVFrame**>(&m_frame));
  if (m_rgb_frame)
    av_frame_free(reinterpret_cast<AVFrame**>(&m_rgb_frame));
  if (m_texture)
    glDeleteTextures(1, &m_texture);
  if (m_vbo)
    glDeleteBuffers(1, &m_vbo);
  if (m_vao)
    glDeleteVertexArrays(1, &m_vao);
}

void FMVPlayer::request_play(const std::string& iso_relative_path) {
  std::lock_guard<std::mutex> lk(m_mutex);
  m_pending_path = iso_relative_path;
  m_phase = Phase::PLAY_REQ;
}

void FMVPlayer::request_stop() {
  std::lock_guard<std::mutex> lk(m_mutex);
  if (m_phase == Phase::PLAYING || m_phase == Phase::PLAY_REQ) {
    m_phase = Phase::STOP_REQ;
  }
}

bool FMVPlayer::is_done() const {
  std::lock_guard<std::mutex> lk(m_mutex);
  return m_phase == Phase::DONE;
}

bool FMVPlayer::is_active() const {
  std::lock_guard<std::mutex> lk(m_mutex);
  return m_phase != Phase::IDLE && m_phase != Phase::DONE;
}

void FMVPlayer::open_file(const std::string& path) {
  auto* fmt_ctx = avformat_alloc_context();
  if (avformat_open_input(&fmt_ctx, path.c_str(), nullptr, nullptr) != 0) {
    lg::warn("[FMV] Failed to open: {}", path);
    avformat_free_context(fmt_ctx);
    return;
  }
  if (avformat_find_stream_info(fmt_ctx, nullptr) < 0) {
    lg::warn("[FMV] No stream info in: {}", path);
    avformat_close_input(&fmt_ctx);
    return;
  }

  int video_idx = av_find_best_stream(fmt_ctx, AVMEDIA_TYPE_VIDEO, -1, -1, nullptr, 0);
  if (video_idx < 0) {
    lg::warn("[FMV] No video stream in: {}", path);
    avformat_close_input(&fmt_ctx);
    return;
  }

  AVStream* stream = fmt_ctx->streams[video_idx];
  const AVCodec* codec = avcodec_find_decoder(stream->codecpar->codec_id);
  if (!codec) {
    lg::warn("[FMV] No decoder for codec {}", (int)stream->codecpar->codec_id);
    avformat_close_input(&fmt_ctx);
    return;
  }

  auto* codec_ctx = avcodec_alloc_context3(codec);
  avcodec_parameters_to_context(codec_ctx, stream->codecpar);
  if (avcodec_open2(codec_ctx, codec, nullptr) < 0) {
    lg::warn("[FMV] Failed to open codec");
    avcodec_free_context(&codec_ctx);
    avformat_close_input(&fmt_ctx);
    return;
  }

  m_fmt_ctx = fmt_ctx;
  m_codec_ctx = codec_ctx;
  m_video_stream_idx = video_idx;
  m_stream_time_base = av_q2d(stream->time_base);
  m_play_start_wall = wall_time_now();

  lg::info("[FMV] Opened {}: {}x{} @ {:.2f} fps", path, codec_ctx->width, codec_ctx->height,
           av_q2d(stream->avg_frame_rate));
}

void FMVPlayer::close_file() {
  if (m_sws_ctx) {
    sws_freeContext(reinterpret_cast<SwsContext*>(m_sws_ctx));
    m_sws_ctx = nullptr;
  }
  if (m_rgb_buf) {
    av_free(m_rgb_buf);
    m_rgb_buf = nullptr;
    m_rgb_buf_size = 0;
  }
  if (m_codec_ctx) {
    avcodec_free_context(reinterpret_cast<AVCodecContext**>(&m_codec_ctx));
    m_codec_ctx = nullptr;
  }
  if (m_fmt_ctx) {
    avformat_close_input(reinterpret_cast<AVFormatContext**>(&m_fmt_ctx));
    m_fmt_ctx = nullptr;
  }
  m_video_stream_idx = -1;
  m_frame_width = 0;
  m_frame_height = 0;
}

bool FMVPlayer::decode_and_draw(SharedRenderState* render_state, ScopedProfilerNode& prof) {
  auto* fmt_ctx = reinterpret_cast<AVFormatContext*>(m_fmt_ctx);
  auto* codec_ctx = reinterpret_cast<AVCodecContext*>(m_codec_ctx);
  auto* packet = reinterpret_cast<AVPacket*>(m_packet);
  auto* frame = reinterpret_cast<AVFrame*>(m_frame);
  auto* rgb_frame = reinterpret_cast<AVFrame*>(m_rgb_frame);

  // Read packets until we get a decoded video frame
  bool got_frame = false;
  while (!got_frame) {
    int ret = av_read_frame(fmt_ctx, packet);
    if (ret < 0) {
      // EOF or error — flush
      avcodec_send_packet(codec_ctx, nullptr);
      if (avcodec_receive_frame(codec_ctx, frame) >= 0) {
        got_frame = true;
      } else {
        return false;  // truly done
      }
      break;
    }

    if (packet->stream_index == m_video_stream_idx) {
      avcodec_send_packet(codec_ctx, packet);
      av_packet_unref(packet);
      if (avcodec_receive_frame(codec_ctx, frame) >= 0) {
        got_frame = true;
      }
    } else {
      av_packet_unref(packet);
    }
  }

  if (!got_frame)
    return false;

  // PTS-based timing: skip frames that haven't arrived yet
  if (frame->pts != AV_NOPTS_VALUE) {
    double frame_ts = frame->pts * m_stream_time_base;
    double wall_elapsed = wall_time_now() - m_play_start_wall;
    if (frame_ts > wall_elapsed + 0.005) {
      // Too early — don't upload, re-display last frame this render tick
      av_frame_unref(frame);
      return true;
    }
  }

  int w = codec_ctx->width;
  int h = codec_ctx->height;

  // (Re)allocate sws context and RGB buffer if dimensions changed
  if (w != m_frame_width || h != m_frame_height) {
    if (m_sws_ctx)
      sws_freeContext(reinterpret_cast<SwsContext*>(m_sws_ctx));
    if (m_rgb_buf)
      av_free(m_rgb_buf);
    m_sws_ctx = sws_getContext(w, h, codec_ctx->pix_fmt, w, h, AV_PIX_FMT_RGB24, SWS_BILINEAR,
                               nullptr, nullptr, nullptr);
    m_rgb_buf_size = av_image_get_buffer_size(AV_PIX_FMT_RGB24, w, h, 1);
    m_rgb_buf = reinterpret_cast<uint8_t*>(av_malloc(m_rgb_buf_size));
    av_image_fill_arrays(rgb_frame->data, rgb_frame->linesize, m_rgb_buf, AV_PIX_FMT_RGB24, w, h,
                         1);
    m_frame_width = w;
    m_frame_height = h;

    // (Re)allocate texture
    glBindTexture(GL_TEXTURE_2D, m_texture);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, w, h, 0, GL_RGB, GL_UNSIGNED_BYTE, nullptr);
    glBindTexture(GL_TEXTURE_2D, 0);
  }

  sws_scale(reinterpret_cast<SwsContext*>(m_sws_ctx),
            reinterpret_cast<const uint8_t* const*>(frame->data), frame->linesize, 0, h,
            rgb_frame->data, rgb_frame->linesize);
  av_frame_unref(frame);

  // Upload RGB frame to GL texture
  glBindTexture(GL_TEXTURE_2D, m_texture);
  glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, w, h, GL_RGB, GL_UNSIGNED_BYTE, m_rgb_buf);
  glBindTexture(GL_TEXTURE_2D, 0);

  // Draw fullscreen quad with FMV shader
  auto& shader = render_state->shaders[ShaderId::FMV];
  shader.activate();
  glActiveTexture(GL_TEXTURE0);
  glBindTexture(GL_TEXTURE_2D, m_texture);
  glUniform1i(glGetUniformLocation(shader.id(), "tex_T0"), 0);

  glDisable(GL_DEPTH_TEST);
  glDisable(GL_BLEND);
  glBindVertexArray(m_vao);
  prof.add_tri(2);
  prof.add_draw_call();
  glDrawArrays(GL_TRIANGLES, 0, 6);
  glBindVertexArray(0);
  glBindTexture(GL_TEXTURE_2D, 0);
  glEnable(GL_DEPTH_TEST);

  return true;
}

void FMVPlayer::render_frame(SharedRenderState* render_state, ScopedProfilerNode& prof) {
  Phase phase;
  std::string path_to_open;

  {
    std::lock_guard<std::mutex> lk(m_mutex);
    phase = m_phase;
    if (phase == Phase::PLAY_REQ) {
      path_to_open = std::move(m_pending_path);
      m_pending_path.clear();
    }
  }

  switch (phase) {
    case Phase::IDLE:
    case Phase::DONE:
      return;

    case Phase::PLAY_REQ: {
      close_file();
      open_file(path_to_open);
      std::lock_guard<std::mutex> lk(m_mutex);
      m_phase = m_fmt_ctx ? Phase::PLAYING : Phase::DONE;
      return;
    }

    case Phase::STOP_REQ:
      close_file();
      {
        std::lock_guard<std::mutex> lk(m_mutex);
        m_phase = Phase::IDLE;
      }
      return;

    case Phase::PLAYING: {
      bool still_playing = decode_and_draw(render_state, prof);
      if (!still_playing) {
        close_file();
        std::lock_guard<std::mutex> lk(m_mutex);
        m_phase = Phase::DONE;
      }
      return;
    }
  }
}
