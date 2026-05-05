#include "TFragment.h"

#include <unordered_set>

#include "game/graphics/opengl_renderer/dma_helpers.h"

#include "third-party/imgui/imgui.h"

namespace {
bool looks_like_tfragment_dma(const DmaFollower& follow) {
  return follow.current_tag_vifcode0().kind == VifCode::Kind::STCYCL;
}

bool looks_like_tfrag_init(const DmaFollower& follow) {
  return follow.current_tag_vifcode0().kind == VifCode::Kind::NOP &&
         follow.current_tag_vifcode1().kind == VifCode::Kind::DIRECT &&
         follow.current_tag_vifcode1().immediate == 2;
}

// JAKX BOOT-PATH 2026-05-05: instrumentation gate. Logs per-bucket state on
// first render() call, then stays silent. Confirms or rejects the
// "chain shape doesn't match handle_initialization" hypothesis without spam.
std::unordered_set<int> g_jakx_tfrag_render_logged;
}  // namespace

TFragment::TFragment(const std::string& name,
                     int my_id,
                     const std::vector<tfrag3::TFragmentTreeKind>& trees,
                     bool child_mode,
                     int level_id,
                     const std::vector<GLuint>* anim_slot_array)
    : BucketRenderer(name, my_id),
      m_child_mode(child_mode),
      m_tree_kinds(trees),
      m_level_id(level_id),
      m_anim_slot_array(anim_slot_array) {
  for (auto& buf : m_buffered_data) {
    for (auto& x : buf.pad) {
      x = 0xff;
    }
  }

  glGenVertexArrays(1, &m_debug_vao);
  glBindVertexArray(m_debug_vao);
  glGenBuffers(1, &m_debug_verts);
  glBindBuffer(GL_ARRAY_BUFFER, m_debug_verts);
  glBufferData(GL_ARRAY_BUFFER, DEBUG_TRI_COUNT * 3 * sizeof(DebugVertex), nullptr,
               GL_DYNAMIC_DRAW);
  glEnableVertexAttribArray(0);
  glEnableVertexAttribArray(1);
  glVertexAttribPointer(0,                                      // location 0 in the shader
                        3,                                      // 3 values per vert
                        GL_FLOAT,                               // floats
                        GL_FALSE,                               // normalized
                        sizeof(DebugVertex),                    // stride
                        (void*)offsetof(DebugVertex, position)  // offset (0)
  );

  glVertexAttribPointer(1,                                  // location 1 in the shader
                        4,                                  // 4 values per vert
                        GL_FLOAT,                           // floats
                        GL_FALSE,                           // normalized
                        sizeof(DebugVertex),                // stride
                        (void*)offsetof(DebugVertex, rgba)  // offset (0)
  );
  glBindVertexArray(0);
  // regardless of how many we use some fixed max
  // we won't actually interp or upload to gpu the unused ones, but we need a fixed maximum so
  // indexing works properly.
  m_color_result.resize(TIME_OF_DAY_COLOR_COUNT);
}

TFragment::~TFragment() {
  discard_tree_cache();
  glDeleteVertexArrays(1, &m_debug_vao);
}

void TFragment::render(DmaFollower& dma,
                       SharedRenderState* render_state,
                       ScopedProfilerNode& prof) {
  if (!m_enabled) {
    while (dma.current_tag_offset() != render_state->next_bucket) {
      dma.read_and_advance();
    }
    return;
  }

  // First thing should be a NEXT with two nops.
  // unless we are a child, in which case our parent took this already.
  if (!m_child_mode) {
    auto data0 = dma.read_and_advance();
    ASSERT(data0.vifcode1().kind == VifCode::Kind::NOP);
    ASSERT(data0.vif0() == 0 || data0.vifcode0().kind == VifCode::Kind::MARK);
    ASSERT(data0.size_bytes == 0);
  }

  if (dma.current_tag().kind == DmaTag::Kind::CALL) {
    // renderer didn't run, let's just get out of here.
    static bool s_logged_call = false;
    if (!s_logged_call) {
      s_logged_call = true;
      fmt::print("[TFragment:{}] first CALL bail — vif0={} vif1={}\n", m_name,
                 (int)dma.current_tag_vifcode0().kind, (int)dma.current_tag_vifcode1().kind);
    }
    for (int i = 0; i < 4; i++) {
      dma.read_and_advance();
    }
    ASSERT(dma.current_tag_offset() == render_state->next_bucket);
    return;
  }

  if (m_my_id == render_state->bucket_for_vis_copy &&
      dma.current_tag_vifcode1().kind == VifCode::Kind::PC_PORT) {
    DmaTransfer transfers[20];
    for (int i = 0; i < render_state->num_vis_to_copy; i++) {
      transfers[i] = dma.read_and_advance();
      auto next0 = dma.read_and_advance();
      ASSERT(next0.size_bytes == 0);
    }

    for (int i = 0; i < render_state->num_vis_to_copy; i++) {
      if (transfers[i].size_bytes == 128 * 16) {
        if (render_state->use_occlusion_culling) {
          render_state->occlusion_vis[i].valid = true;
          memcpy(render_state->occlusion_vis[i].data, transfers[i].data, 128 * 16);
        }
      } else {
        ASSERT(transfers[i].size_bytes == 16);
      }
    }
  }

  if (dma.current_tag().kind == DmaTag::Kind::CALL) {
    // renderer didn't run, let's just get out of here.
    static bool s_logged_call2 = false;
    if (!s_logged_call2) {
      s_logged_call2 = true;
      fmt::print("[TFragment:{}] second CALL bail (post-vis-copy)\n", m_name);
    }
    for (int i = 0; i < 4; i++) {
      dma.read_and_advance();
    }
    ASSERT(dma.current_tag_offset() == render_state->next_bucket);
    return;
  }

  // JAKX BOOT-PATH 2026-05-05: log first render call per bucket. Captures
  // first DMA tag shape + looks_like_tfrag_init result + bail point so we can
  // confirm/reject the chain-shape hypothesis without instrumenting GOAL side.
  bool jakx_log = g_jakx_tfrag_render_logged.insert(m_my_id).second;
  if (jakx_log) {
    auto vc0 = dma.current_tag_vifcode0();
    auto vc1 = dma.current_tag_vifcode1();
    fmt::print("[TFragment-instr/{}] first-render: vif0.kind={} vif0.imm={} vif1.kind={} vif1.imm={} "
               "looks_like_init={} (need vif0=NOP[{}] vif1=DIRECT[{}] vif1.imm=2)\n",
               m_name, (int)vc0.kind, vc0.immediate, (int)vc1.kind, vc1.immediate,
               looks_like_tfrag_init(dma) ? "YES" : "NO",
               (int)VifCode::Kind::NOP, (int)VifCode::Kind::DIRECT);
  }

  std::string level_name;
  while (looks_like_tfrag_init(dma)) {
    if (jakx_log) {
      fmt::print("[TFragment-instr/{}] entering handle_initialization\n", m_name);
    }
    handle_initialization(dma);
    if (level_name.empty()) {
      level_name = m_pc_port_data.level_name;
    } else if (level_name != m_pc_port_data.level_name) {
      ASSERT(false);
    }

    while (looks_like_tfragment_dma(dma)) {
      dma.read_and_advance();
    }
  }

  while (dma.current_tag_offset() != render_state->next_bucket) {
    dma.read_and_advance();
  }

  if (level_name.empty()) {
    if (jakx_log) {
      fmt::print("[TFragment-instr/{}] BAIL: level_name empty after init loop\n", m_name);
    }
    return;
  }
  if (jakx_log) {
    fmt::print("[TFragment-instr/{}] PROCEED: level_name='{}' — calling render_matching_trees\n",
               m_name, level_name);
  }
  {
    setup_for_level(m_tree_kinds, level_name, render_state);
    TfragRenderSettings settings;

    settings.camera = m_pc_port_data.camera;
    settings.tree_idx = 0;
    if (render_state->occlusion_vis[m_level_id].valid) {
      settings.occlusion_culling = render_state->occlusion_vis[m_level_id].data;
    }

    update_render_state_from_pc_settings(render_state, m_pc_port_data);

    static int s_tfrag_render_calls = 0;
    s_tfrag_render_calls++;
    if (s_tfrag_render_calls <= 4 || s_tfrag_render_calls % 30 == 0) {
      fmt::print("[TFragment/{}] render call#{} level='{}' trees[lod={}]={}\n",
                 m_name, s_tfrag_render_calls, level_name, lod(), m_cached_trees[lod()].size());
    }

    auto t3prof = prof.make_scoped_child("t3");
    render_matching_trees(lod(), m_tree_kinds, settings, render_state, t3prof);
  }

  while (dma.current_tag_offset() != render_state->next_bucket) {
    auto tag = dma.current_tag().print();
    dma.read_and_advance();
  }
}

void TFragment::draw_debug_window() {
  for (int i = 0; i < (int)m_cached_trees.at(lod()).size(); i++) {
    auto& tree = m_cached_trees.at(lod()).at(i);
    if (tree.kind == tfrag3::TFragmentTreeKind::INVALID) {
      continue;
    }
    ImGui::PushID(i);
    ImGui::Text("[%d] %10s", i, tfrag3::tfrag_tree_names[(int)m_cached_trees[lod()][i].kind]);
    ImGui::SameLine();
    ImGui::Checkbox("Allow?", &tree.allowed);
    ImGui::SameLine();
    ImGui::Checkbox("Force?", &tree.forced);
    ImGui::SameLine();
    ImGui::Checkbox("cull debug (slow)", &tree.cull_debug);
    ImGui::PopID();
    if (tree.rendered_this_frame) {
      ImGui::Checkbox("freeze itimes", &tree.freeze_itimes);
      ImGui::Text("  tris: %d draws: %d", tree.tris_this_frame, tree.draws_this_frame);
      for (int j = 0; j < 4; j++) {
        ImGui::Text(" itimes[%d] 0x%x 0x%x 0x%x 0x%x", j, tree.itimes_debug[j][0],
                    tree.itimes_debug[j][1], tree.itimes_debug[j][2], tree.itimes_debug[j][3]);
      }
    }
  }
}

void TFragment::init_shaders(ShaderLibrary& shaders) {
  m_uniforms.decal = glGetUniformLocation(shaders[ShaderId::TFRAG3].id(), "decal");
}

void TFragment::handle_initialization(DmaFollower& dma) {
  // Set up test (different between different renderers)
  auto setup_test = dma.read_and_advance();
  ASSERT(setup_test.vif0() == 0);
  ASSERT(setup_test.vifcode1().kind == VifCode::Kind::DIRECT);
  ASSERT(setup_test.vifcode1().immediate == 2);
  ASSERT(setup_test.size_bytes == 32);
  memcpy(m_test_setup, setup_test.data, 32);

  // matrix 0
  auto mat0_upload = dma.read_and_advance();
  unpack_to_stcycl(&m_buffered_data[0].pad[TFragDataMem::TFragMatrix0 * 16], mat0_upload,
                   VifCode::Kind::UNPACK_V4_32, 4, 4, 64, TFragDataMem::TFragMatrix0, false, false);

  // matrix 1
  auto mat1_upload = dma.read_and_advance();
  unpack_to_stcycl(&m_buffered_data[1].pad[TFragDataMem::TFragMatrix0 * 16], mat1_upload,
                   VifCode::Kind::UNPACK_V4_32, 4, 4, 64, TFragDataMem::TFragMatrix1, false, false);

  // data
  auto data_upload = dma.read_and_advance();
  (void)data_upload;

  // call the setup program
  auto mscal_setup = dma.read_and_advance();
  verify_mscal(mscal_setup, TFragProgMem::TFragSetup);

  auto pc_port_data = dma.read_and_advance();
  ASSERT(pc_port_data.size_bytes == sizeof(TfragPcPortData));
  memcpy(&m_pc_port_data, pc_port_data.data, sizeof(TfragPcPortData));
  m_pc_port_data.level_name[11] = '\0';

  // setup double buffering.
  auto db_setup = dma.read_and_advance();
  ASSERT(db_setup.size_bytes == 0);
  ASSERT(db_setup.vifcode0().kind == VifCode::Kind::BASE &&
         db_setup.vifcode0().immediate == Buffer0_Start);
  ASSERT(db_setup.vifcode1().kind == VifCode::Kind::OFFSET &&
         db_setup.vifcode1().immediate == (Buffer1_Start - Buffer0_Start));
}

std::string TFragData::print() const {
  std::string result;
  result += fmt::format("fog: {}\n", fog.to_string_aligned());
  result += fmt::format("val: {}\n", val.to_string_aligned());
  result += fmt::format("str-gif: {}\n", str_gif.print());
  result += fmt::format("fan-gif: {}\n", fan_gif.print());
  result += fmt::format("ad-gif: {}\n", ad_gif.print());
  result += fmt::format("hvdf_offset: {}\n", hvdf_offset.to_string_aligned());
  result += fmt::format("hmge_scale: {}\n", hmge_scale.to_string_aligned());
  result += fmt::format("invh_scale: {}\n", invh_scale.to_string_aligned());
  result += fmt::format("ambient: {}\n", ambient.to_string_aligned());
  result += fmt::format("guard: {}\n", guard.to_string_aligned());
  result += fmt::format("k0s[0]: {}\n", k0s[0].to_string_aligned());
  result += fmt::format("k0s[1]: {}\n", k0s[1].to_string_aligned());
  result += fmt::format("k1s[0]: {}\n", k1s[0].to_string_aligned());
  result += fmt::format("k1s[1]: {}\n", k1s[1].to_string_aligned());
  return result;
}

void TFragment::update_load(const std::vector<tfrag3::TFragmentTreeKind>& tree_kinds,
                            const LevelData* loader_data) {
  const auto* lev_data = loader_data->level.get();
  discard_tree_cache();
  for (int geom = 0; geom < GEOM_MAX; ++geom) {
    m_cached_trees[geom].clear();
  }

  u32 time_of_day_count = 0;
  size_t vis_temp_len = 0;
  size_t max_draws = 0;
  size_t max_num_grps = 0;
  size_t max_inds = 0;

  for (int geom = 0; geom < GEOM_MAX; ++geom) {
    for (size_t tree_idx = 0; tree_idx < lev_data->tfrag_trees[geom].size(); tree_idx++) {
      const auto& tree = lev_data->tfrag_trees[geom][tree_idx];

      fmt::print("[update_load/{}] geo={} tree_idx={} kind={} match={}\n",
                 m_name, geom, tree_idx, (int)tree.kind,
                 std::find(tree_kinds.begin(), tree_kinds.end(), tree.kind) != tree_kinds.end());
      if (std::find(tree_kinds.begin(), tree_kinds.end(), tree.kind) != tree_kinds.end()) {
        auto& tree_cache = m_cached_trees[geom].emplace_back();
        tree_cache.kind = tree.kind;
        max_draws = std::max(tree.draws.size(), max_draws);
        size_t num_grps = 0;
        for (auto& draw : tree.draws) {
          num_grps += draw.vis_groups.size();
        }
        max_num_grps = std::max(max_num_grps, num_grps);
        max_inds = std::max(tree.unpacked.indices.size(), max_inds);
        time_of_day_count = std::max(tree.colors.color_count, time_of_day_count);
        u32 verts = tree.packed_vertices.vertices.size();
        glGenVertexArrays(1, &tree_cache.vao);
        glBindVertexArray(tree_cache.vao);
        // glGenBuffers(1, &tree_cache.vertex_buffer);
        tree_cache.vertex_buffer = loader_data->tfrag_vertex_data[geom][tree_idx];
        tree_cache.vert_count = verts;
        tree_cache.draws = &tree.draws;  // todo - should we just copy this?
        tree_cache.colors = &tree.colors;
        tree_cache.vis = &tree.bvh;
        tree_cache.index_data = tree.unpacked.indices.data();
        tree_cache.draw_mode = tree.use_strips ? GL_TRIANGLE_STRIP : GL_TRIANGLES;
        vis_temp_len = std::max(vis_temp_len, tree.bvh.vis_nodes.size());
        glBindBuffer(GL_ARRAY_BUFFER, tree_cache.vertex_buffer);
        //            glBufferData(GL_ARRAY_BUFFER, verts * sizeof(tfrag3::PreloadedVertex),
        //            nullptr,
        //                         GL_STREAM_DRAW);
        glEnableVertexAttribArray(0);
        glEnableVertexAttribArray(1);
        glEnableVertexAttribArray(2);

        glVertexAttribPointer(0,                                // location 0 in the shader
                              3,                                // 3 values per vert
                              GL_FLOAT,                         // floats
                              GL_FALSE,                         // normalized
                              sizeof(tfrag3::PreloadedVertex),  // stride
                              (void*)offsetof(tfrag3::PreloadedVertex, x)  // offset (0)
        );

        glVertexAttribPointer(1,                                // location 1 in the shader
                              3,                                // 3 values per vert
                              GL_FLOAT,                         // floats
                              GL_FALSE,                         // normalized
                              sizeof(tfrag3::PreloadedVertex),  // stride
                              (void*)offsetof(tfrag3::PreloadedVertex, s)  // offset (0)
        );

        glVertexAttribIPointer(2,                                // location 2 in the shader
                               2,                                // 1 values per vert
                               GL_UNSIGNED_SHORT,                // u16
                               sizeof(tfrag3::PreloadedVertex),  // stride
                               (void*)offsetof(tfrag3::PreloadedVertex, color_index)  // offset (0)
        );
        glGenBuffers(1, &tree_cache.single_draw_index_buffer);
        glGenBuffers(1, &tree_cache.index_buffer);
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, tree_cache.index_buffer);
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, tree.unpacked.indices.size() * sizeof(u32),
                     tree.unpacked.indices.data(), GL_STREAM_DRAW);

        glGenTextures(1, &tree_cache.time_of_day_texture);
        glBindTexture(GL_TEXTURE_1D, tree_cache.time_of_day_texture);
        glTexImage1D(GL_TEXTURE_1D, 0, GL_RGBA, TIME_OF_DAY_COLOR_COUNT, 0, GL_RGBA,
                     GL_UNSIGNED_INT_8_8_8_8, nullptr);
        glTexParameteri(GL_TEXTURE_1D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
        glTexParameteri(GL_TEXTURE_1D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
        glBindVertexArray(0);
      }
    }
  }

  m_cache.vis_temp.resize(vis_temp_len);
  m_cache.multidraw_offset_per_stripdraw.resize(max_draws);
  m_cache.multidraw_count_buffer.resize(max_num_grps);
  m_cache.multidraw_index_offset_buffer.resize(max_num_grps);
  m_cache.draw_idx_temp.resize(max_draws);
  m_cache.index_temp.resize(max_inds);
  ASSERT(time_of_day_count <= TIME_OF_DAY_COLOR_COUNT);
}

bool TFragment::setup_for_level(const std::vector<tfrag3::TFragmentTreeKind>& tree_kinds,
                                const std::string& level,
                                SharedRenderState* render_state) {
  // make sure we have the level data.
  Timer tfrag3_setup_timer;
  auto lev_data = render_state->loader->get_tfrag3_level(level);

  if (!lev_data) {
    // not loaded
    if (m_has_level || m_level_name != level) {
      fmt::print("[TFragment] setup_for_level: '{}' not in loader (not yet loaded or wrong name)\n",
                 level);
    }
    m_has_level = false;
    m_textures = nullptr;
    // Don't set m_level_name here — if we set it to `level` while data isn't ready,
    // the next successful call sees m_level_name == level and skips update_load entirely,
    // leaving m_cached_trees empty. Keep m_level_name at "" (or prior) so the next
    // successful load triggers update_load and populates the tree cache.
    m_level_name = "";
    discard_tree_cache();
    return false;
  }

  if (m_has_level && lev_data->load_id != m_load_id) {
    m_has_level = false;
    m_textures = nullptr;
    m_level_name = "";
    discard_tree_cache();
    return setup_for_level(tree_kinds, level, render_state);
  }

  m_load_id = lev_data->load_id;

  if (m_level_name != level) {
    update_load(tree_kinds, lev_data);
    m_has_level = true;
    m_textures = &lev_data->textures;
    m_level_name = level;
    fmt::print("[setup_for_level/{}] update_load done: trees[0]={} trees[1]={} trees[2]={}\n",
               m_name, m_cached_trees[0].size(), m_cached_trees[1].size(), m_cached_trees[2].size());
  } else {
    m_has_level = true;
  }

  if (tfrag3_setup_timer.getMs() > 5) {
    lg::info("TFRAG setup: {:.1f}ms", tfrag3_setup_timer.getMs());
  }

  return m_has_level;
}

void TFragment::render_tree(int geom,
                            const TfragRenderSettings& settings,
                            SharedRenderState* render_state,
                            ScopedProfilerNode& prof) {
  if (!m_has_level) {
    return;
  }
  auto& tree = m_cached_trees.at(geom).at(settings.tree_idx);
  [[maybe_unused]] const auto* itimes = settings.camera.itimes;

  if (tree.freeze_itimes) {
    itimes = tree.itimes_debug;
  } else {
    for (int i = 0; i < 4; i++) {
      tree.itimes_debug[i] = settings.camera.itimes[i];
    }
  }

  ASSERT(tree.kind != tfrag3::TFragmentTreeKind::INVALID);

  if (m_color_result.size() < tree.colors->color_count) {
    m_color_result.resize(tree.colors->color_count);
  }
  // Fallback: if GOAL hasn't set up mood/itimes (no target process in stripped loop),
  // use palette 0 at full weight so geometry renders with color instead of black.
  const math::Vector<s32, 4>* itimes_to_use = settings.camera.itimes;
  math::Vector<s32, 4> fallback_itimes[4] = {};
  bool all_zero = true;
  for (int i = 0; i < 4; i++) {
    if (settings.camera.itimes[i].x() || settings.camera.itimes[i].y() ||
        settings.camera.itimes[i].z() || settings.camera.itimes[i].w()) {
      all_zero = false;
      break;
    }
  }
  if (all_zero) {
    // interp_time_of_day extracts per-channel weights as 8-bit values packed in 32-bit words:
    //   word[0] low byte  → component R (channel 0)
    //   word[0] high word → component G (channel 1, bits 16-23)
    //   word[1] low byte  → component B (channel 2)
    //   word[1] high word → component A (channel 3, bits 16-23)
    // 64 = full weight (maps to 1.0 after /64 in update-mood-itimes scale).
    // All four channels must be non-zero or alpha=0 discards all fragments.
    s32 packed = 64 | (64 << 16);  // low+high bytes both 64
    fallback_itimes[0] = math::Vector<s32, 4>{packed, packed, 0, 0};
    itimes_to_use = fallback_itimes;
  }
  interp_time_of_day(itimes_to_use, *tree.colors, m_color_result.data());

  // log itimes and first color result on first few calls
  {
    static std::unordered_map<std::string, int> s_color_log_count;
    auto& cnt = s_color_log_count[m_name];
    cnt++;
    if (cnt <= 3) {
      auto& it = settings.camera.itimes[0];
      u32 first_color = m_color_result.empty() ? 0u
          : ((u32)m_color_result[0].x() | ((u32)m_color_result[0].y() << 8) |
             ((u32)m_color_result[0].z() << 16) | ((u32)m_color_result[0].w() << 24));
      fmt::print("[tfrag-color/{}] call#{} itimes[0]={{{},{},{},{}}} colors={} first_rgba={:#010x}\n",
                 m_name, cnt,
                 it.x(), it.y(), it.z(), it.w(),
                 (int)tree.colors->color_count, first_color);
    }
  }

  glActiveTexture(GL_TEXTURE10);
  glBindTexture(GL_TEXTURE_1D, tree.time_of_day_texture);
  glTexSubImage1D(GL_TEXTURE_1D, 0, 0, tree.colors->color_count, GL_RGBA,
                  GL_UNSIGNED_INT_8_8_8_8_REV, m_color_result.data());

  first_tfrag_draw_setup(settings.camera, render_state, ShaderId::TFRAG3);

  glBindVertexArray(tree.vao);
  glBindBuffer(GL_ARRAY_BUFFER, tree.vertex_buffer);
  glBindBuffer(GL_ELEMENT_ARRAY_BUFFER,
               render_state->no_multidraw ? tree.single_draw_index_buffer : tree.index_buffer);
  glActiveTexture(GL_TEXTURE0);
  glEnable(GL_PRIMITIVE_RESTART);
  glPrimitiveRestartIndex(UINT32_MAX);

  cull_check_all_slow(settings.camera.planes, tree.vis->vis_nodes, settings.occlusion_culling,
                      m_cache.vis_temp.data());

  // JAKX BOOT-PATH 2026-05-05: discriminator instrumentation. Logs first call per
  // bucket only (so it doesn't spam). Captures vis_temp content + camera planes/trans
  // + occlusion_culling pointer + per-draw frustum/multidraw outcome for the first 5
  // draws. Three discriminator outcomes:
  //   A) vis_temp all-zero  → GOAL not computing visibility / planes wrong
  //   B) vis_temp non-zero but multidraw_indices.second==0 for all → vis_groups
  //      reference different nodes than vis_temp populates (data binding mismatch)
  //   C) multidraw counts non-zero but num_triangles==0 → empty draws.
  static std::unordered_set<std::string> s_render_disc_logged;
  bool disc_log = s_render_disc_logged.insert(m_name).second;
  if (disc_log) {
    size_t vis_node_count = tree.vis ? tree.vis->vis_nodes.size() : 0;
    size_t vis_temp_size = m_cache.vis_temp.size();
    size_t check_bytes = std::min<size_t>(vis_node_count, vis_temp_size);
    int nonzero_vis_count = 0;
    for (size_t i = 0; i < check_bytes; i++) {
      if (m_cache.vis_temp[i]) nonzero_vis_count++;
    }
    fmt::print("[render_disc/{}] vis_nodes={} vis_temp_nonzero={}/{} occl_ptr={} occl_valid={}\n",
               m_name, (int)vis_node_count, nonzero_vis_count, (int)check_bytes,
               (settings.occlusion_culling ? "non-null" : "NULL"),
               render_state->occlusion_vis[m_level_id].valid ? "true" : "false");
    if (settings.occlusion_culling) {
      const u8* p = settings.occlusion_culling;
      fmt::print("[render_disc/{}] occl_first16: "
                 "{:02x} {:02x} {:02x} {:02x} {:02x} {:02x} {:02x} {:02x} "
                 "{:02x} {:02x} {:02x} {:02x} {:02x} {:02x} {:02x} {:02x}\n",
                 m_name, p[0], p[1], p[2], p[3], p[4], p[5], p[6], p[7],
                 p[8], p[9], p[10], p[11], p[12], p[13], p[14], p[15]);
    }
    if (check_bytes > 0) {
      const u8* v = m_cache.vis_temp.data();
      size_t print_n = std::min<size_t>(check_bytes, 16);
      fmt::print("[render_disc/{}] vis_temp_first{}:", m_name, (int)print_n);
      for (size_t i = 0; i < print_n; i++) fmt::print(" {:02x}", v[i]);
      fmt::print("\n");
    }
    const auto& cam = settings.camera;
    fmt::print("[render_disc/{}] cam.planes[0]=({:.3f},{:.3f},{:.3f},{:.3f}) "
               "cam.trans=({:.3f},{:.3f},{:.3f},{:.3f})\n",
               m_name,
               cam.planes[0].x(), cam.planes[0].y(), cam.planes[0].z(), cam.planes[0].w(),
               cam.trans.x(), cam.trans.y(), cam.trans.z(), cam.trans.w());
    fmt::print("[render_disc/{}] cam.planes[1]=({:.3f},{:.3f},{:.3f},{:.3f}) "
               "cam.planes[2]=({:.3f},{:.3f},{:.3f},{:.3f}) "
               "cam.planes[3]=({:.3f},{:.3f},{:.3f},{:.3f})\n",
               m_name,
               cam.planes[1].x(), cam.planes[1].y(), cam.planes[1].z(), cam.planes[1].w(),
               cam.planes[2].x(), cam.planes[2].y(), cam.planes[2].z(), cam.planes[2].w(),
               cam.planes[3].x(), cam.planes[3].y(), cam.planes[3].z(), cam.planes[3].w());
    // sample a draw: count how many vis_groups reference UINT16_MAX (always-visible)
    // vs index-into-vis-array, and how many of the indexed ones are non-zero.
    if (tree.draws && !tree.draws->empty()) {
      size_t sample_n = std::min<size_t>(tree.draws->size(), 5);
      for (size_t di = 0; di < sample_n; di++) {
        const auto& draw = tree.draws->operator[](di);
        size_t vg_total = draw.vis_groups.size();
        int vg_alwaysvis = 0, vg_indexed_vis = 0, vg_indexed_total = 0, vg_oob = 0;
        u32 vg_tris_visible = 0;
        for (const auto& grp : draw.vis_groups) {
          if (grp.vis_idx_in_pc_bvh == UINT16_MAX) {
            vg_alwaysvis++;
            vg_tris_visible += grp.num_tris;
          } else {
            vg_indexed_total++;
            if (grp.vis_idx_in_pc_bvh < check_bytes) {
              if (m_cache.vis_temp[grp.vis_idx_in_pc_bvh]) {
                vg_indexed_vis++;
                vg_tris_visible += grp.num_tris;
              }
            } else {
              vg_oob++;
            }
          }
        }
        fmt::print("[render_disc/{}] draw#{} vg_total={} alwaysvis={} idx_total={} idx_vis={} "
                   "oob={} num_tris_total={} tris_visible={} idx_first={}\n",
                   m_name, (int)di, (int)vg_total, vg_alwaysvis, vg_indexed_total,
                   vg_indexed_vis, vg_oob, (int)draw.num_triangles, (int)vg_tris_visible,
                   (int)draw.unpacked.idx_of_first_idx_in_full_buffer);
      }
    }
  }

  u32 total_tris;
  if (render_state->no_multidraw) {
    u32 idx_buffer_size = make_index_list_from_vis_string(
        m_cache.draw_idx_temp.data(), m_cache.index_temp.data(), *tree.draws, m_cache.vis_temp,
        tree.index_data, &total_tris);
    glBufferData(GL_ELEMENT_ARRAY_BUFFER, idx_buffer_size * sizeof(u32), m_cache.index_temp.data(),
                 GL_STREAM_DRAW);
  } else {
    total_tris = make_multidraws_from_vis_string(
        m_cache.multidraw_offset_per_stripdraw.data(), m_cache.multidraw_count_buffer.data(),
        m_cache.multidraw_index_offset_buffer.data(), *tree.draws, m_cache.vis_temp);
  }

  prof.add_tri(total_tris);

  // JAKX BOOT-PATH 2026-05-05: post-multidraw per-draw outcome (paired with
  // pre-multidraw discriminator above).
  if (disc_log) {
    if (tree.draws && !tree.draws->empty()) {
      size_t sample_n = std::min<size_t>(tree.draws->size(), 5);
      for (size_t di = 0; di < sample_n; di++) {
        const auto& draw = tree.draws->operator[](di);
        const auto& md = m_cache.multidraw_offset_per_stripdraw[di];
        const auto& sd = m_cache.draw_idx_temp[di];
        fmt::print("[render_disc/{}] post-md draw#{} num_tris_total={} "
                   "multidraw=(first={},second={}) singledraw=(first={},second={})\n",
                   m_name, (int)di, (int)draw.num_triangles,
                   md.first, md.second, sd.first, sd.second);
      }
    }
  }

  // draw-call count log — first 3 calls per instance
  {
    static std::unordered_map<std::string, int> s_render_call_count;
    auto& cnt = s_render_call_count[m_name];
    cnt++;
    if (cnt <= 3) {
      fmt::print("[render_tree/{}] call#{} geom={} total_tris={} draws={}\n",
                 m_name, cnt, geom, total_tris, (int)tree.draws->size());
    }
  }

  for (size_t draw_idx = 0; draw_idx < tree.draws->size(); draw_idx++) {
    const auto& draw = tree.draws->operator[](draw_idx);
    const auto& multidraw_indices = m_cache.multidraw_offset_per_stripdraw[draw_idx];
    const auto& singledraw_indices = m_cache.draw_idx_temp[draw_idx];

    if (render_state->no_multidraw) {
      if (singledraw_indices.second == 0) {
        continue;
      }
    } else {
      if (multidraw_indices.second == 0) {
        continue;
      }
    }

    ASSERT(m_textures);
    s32 tex_idx = draw.tree_tex_id;
    if (tex_idx >= 0) {
      glBindTexture(GL_TEXTURE_2D, m_textures->at(draw.tree_tex_id));
    } else {
      glBindTexture(GL_TEXTURE_2D, m_anim_slot_array->at(-(tex_idx + 1)));
    }
    auto double_draw = setup_tfrag_shader(render_state, draw.mode, ShaderId::TFRAG3);
    glUniform1i(m_uniforms.decal, draw.mode.get_decal() ? 1 : 0);
    tree.tris_this_frame += draw.num_triangles;
    tree.draws_this_frame++;

    prof.add_draw_call();
    if (render_state->no_multidraw) {
      glDrawElements(tree.draw_mode, singledraw_indices.second, GL_UNSIGNED_INT,
                     (void*)(singledraw_indices.first * sizeof(u32)));
    } else {
      glMultiDrawElements(tree.draw_mode, &m_cache.multidraw_count_buffer[multidraw_indices.first],
                          GL_UNSIGNED_INT,
                          &m_cache.multidraw_index_offset_buffer[multidraw_indices.first],
                          multidraw_indices.second);
    }

    switch (double_draw.kind) {
      case DoubleDrawKind::NONE:
        break;
      case DoubleDrawKind::AFAIL_NO_DEPTH_WRITE:
        prof.add_draw_call();
        glUniform1f(glGetUniformLocation(render_state->shaders[ShaderId::TFRAG3].id(), "alpha_min"),
                    -10.f);
        glUniform1f(glGetUniformLocation(render_state->shaders[ShaderId::TFRAG3].id(), "alpha_max"),
                    double_draw.aref_second);
        glDepthMask(GL_FALSE);
        if (render_state->no_multidraw) {
          glDrawElements(tree.draw_mode, singledraw_indices.second, GL_UNSIGNED_INT,
                         (void*)(singledraw_indices.first * sizeof(u32)));
        } else {
          glMultiDrawElements(
              tree.draw_mode, &m_cache.multidraw_count_buffer[multidraw_indices.first],
              GL_UNSIGNED_INT, &m_cache.multidraw_index_offset_buffer[multidraw_indices.first],
              multidraw_indices.second);
        }
        break;
      default:
        ASSERT(false);
    }
  }
  glBindVertexArray(0);
}

/*!
 * Render all trees with settings for the given tree.
 * This is intended to be used only for debugging when we can't easily get commands for all trees
 * working.
 */
void TFragment::render_all_trees(int geom,
                                 const TfragRenderSettings& settings,
                                 SharedRenderState* render_state,
                                 ScopedProfilerNode& prof) {
  TfragRenderSettings settings_copy = settings;
  for (size_t i = 0; i < m_cached_trees[geom].size(); i++) {
    if (m_cached_trees[geom][i].kind != tfrag3::TFragmentTreeKind::INVALID) {
      settings_copy.tree_idx = i;
      render_tree(geom, settings_copy, render_state, prof);
    }
  }
}

void TFragment::render_matching_trees(int geom,
                                      const std::vector<tfrag3::TFragmentTreeKind>& trees,
                                      const TfragRenderSettings& settings,
                                      SharedRenderState* render_state,
                                      ScopedProfilerNode& prof) {
  TfragRenderSettings settings_copy = settings;
  for (size_t i = 0; i < m_cached_trees[geom].size(); i++) {
    auto& tree = m_cached_trees[geom][i];
    tree.reset_stats();
    if (!tree.allowed) {
      continue;
    }
    if (std::find(trees.begin(), trees.end(), tree.kind) != trees.end() || tree.forced) {
      tree.rendered_this_frame = true;
      settings_copy.tree_idx = i;
      render_tree(geom, settings_copy, render_state, prof);
      if (tree.cull_debug) {
        render_tree_cull_debug(settings_copy, render_state, prof);
      }
    }
  }
}

void TFragment::discard_tree_cache() {
  m_textures = nullptr;
  for (int geom = 0; geom < GEOM_MAX; ++geom) {
    for (auto& tree : m_cached_trees[geom]) {
      if (tree.kind != tfrag3::TFragmentTreeKind::INVALID) {
        glBindTexture(GL_TEXTURE_1D, tree.time_of_day_texture);
        glDeleteTextures(1, &tree.time_of_day_texture);
        glDeleteBuffers(1, &tree.single_draw_index_buffer);
        glDeleteBuffers(1, &tree.index_buffer);
        glDeleteVertexArrays(1, &tree.vao);
      }
    }
    m_cached_trees[geom].clear();
  }
}

namespace {

float frac(float in) {
  return in - (int)in;
}

void debug_vis_draw(int first_root,
                    int tree,
                    int num,
                    int depth,
                    const std::vector<tfrag3::VisNode>& nodes,
                    std::vector<TFragment::DebugVertex>& verts_out) {
  for (int ki = 0; ki < num; ki++) {
    auto& node = nodes.at(ki + tree - first_root);
    ASSERT(node.child_id != 0xffff);
    math::Vector4f rgba{frac(0.4 * depth), frac(0.7 * depth), frac(0.2 * depth), 0.06};
    math::Vector3f center = node.bsphere.xyz();
    float rad = node.bsphere.w();
    math::Vector3f corners[8] = {center, center, center, center};
    corners[0].x() += rad;
    corners[1].x() += rad;
    corners[2].x() -= rad;
    corners[3].x() -= rad;

    corners[0].y() += rad;
    corners[1].y() -= rad;
    corners[2].y() += rad;
    corners[3].y() -= rad;

    for (int i = 0; i < 4; i++) {
      corners[i + 4] = corners[i];
      corners[i].z() += rad;
      corners[i + 4].z() -= rad;
    }

    if (true) {
      for (int i : {0, 4}) {
        verts_out.push_back({corners[0 + i], rgba});
        verts_out.push_back({corners[1 + i], rgba});
        verts_out.push_back({corners[2 + i], rgba});

        verts_out.push_back({corners[1 + i], rgba});  // 0
        verts_out.push_back({corners[3 + i], rgba});
        verts_out.push_back({corners[2 + i], rgba});
      }

      for (int i : {2, 6, 7, 2, 3, 7, 0, 4, 5, 0, 5, 1, 0, 6, 4, 0, 6, 2, 1, 3, 7, 1, 5, 7}) {
        verts_out.push_back({corners[i], rgba});
      }

      constexpr int border0[12] = {0, 4, 6, 2, 2, 6, 3, 7, 0, 1, 2, 3};
      constexpr int border1[12] = {1, 5, 7, 3, 0, 4, 1, 5, 4, 5, 6, 7};
      rgba.w() = 1.0;

      for (int i = 0; i < 12; i++) {
        auto p0 = corners[border0[i]];
        auto p1 = corners[border1[i]];
        auto diff = (p1 - p0).normalized();
        math::Vector3f px = diff.z() == 0 ? math::Vector3f{1, 0, 1} : math::Vector3f{0, 1, 1};
        auto off = diff.cross(px) * 2000;

        verts_out.push_back({p0 + off, rgba});
        verts_out.push_back({p0 - off, rgba});
        verts_out.push_back({p1 - off, rgba});

        verts_out.push_back({p0 + off, rgba});
        verts_out.push_back({p1 + off, rgba});
        verts_out.push_back({p1 - off, rgba});
      }
    }

    if (node.flags) {
      debug_vis_draw(first_root, node.child_id, node.num_kids, depth + 1, nodes, verts_out);
    }
  }
}

}  // namespace

void TFragment::render_tree_cull_debug(const TfragRenderSettings& settings,
                                       SharedRenderState* render_state,
                                       ScopedProfilerNode& prof) {
  // generate debug verts:
  m_debug_vert_data.clear();
  auto& tree = m_cached_trees.at(settings.tree_idx).at(lod());

  debug_vis_draw(tree.vis->first_root, tree.vis->first_root, tree.vis->num_roots, 1,
                 tree.vis->vis_nodes, m_debug_vert_data);

  render_state->shaders[ShaderId::TFRAG3_NO_TEX].activate();
  glUniformMatrix4fv(
      glGetUniformLocation(render_state->shaders[ShaderId::TFRAG3_NO_TEX].id(), "camera"), 1,
      GL_FALSE, settings.camera.camera[0].data());
  glUniform4f(
      glGetUniformLocation(render_state->shaders[ShaderId::TFRAG3_NO_TEX].id(), "hvdf_offset"),
      settings.camera.hvdf_off[0], settings.camera.hvdf_off[1], settings.camera.hvdf_off[2],
      settings.camera.hvdf_off[3]);
  glUniform1f(
      glGetUniformLocation(render_state->shaders[ShaderId::TFRAG3_NO_TEX].id(), "fog_constant"),
      settings.camera.fog.x());
  // glDisable(GL_DEPTH_TEST);
  glEnable(GL_DEPTH_TEST);
  glDepthFunc(GL_GEQUAL);
  glEnable(GL_BLEND);
  glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);  // ?
  glDepthMask(GL_FALSE);

  glBindVertexArray(m_debug_vao);
  glBindBuffer(GL_ARRAY_BUFFER, m_debug_verts);

  int remaining = m_debug_vert_data.size();
  int start = 0;

  while (remaining > 0) {
    int to_do = std::min(DEBUG_TRI_COUNT * 3, remaining);

    glBufferSubData(GL_ARRAY_BUFFER, 0, to_do * sizeof(DebugVertex),
                    m_debug_vert_data.data() + start);
    glDrawArrays(GL_TRIANGLES, 0, to_do);
    prof.add_draw_call();
    prof.add_tri(to_do / 3);

    remaining -= to_do;
    start += to_do;
  }
}
