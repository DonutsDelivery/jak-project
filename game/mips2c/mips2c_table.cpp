#include "mips2c_table.h"

#include "common/log/log.h"
#include "common/symbols.h"

#include "game/kernel/common/kmalloc.h"
#include "game/kernel/common/kscheme.h"
#include "game/kernel/jak1/kscheme.h"
#include "game/kernel/jak2/kscheme.h"
#include "game/kernel/jak3/kscheme.h"
#include "game/kernel/jakx/kscheme.h"
#include "game/runtime.h"

extern "C" {
#ifdef __linux__
void _mips2c_call_systemv();
#elif defined __APPLE__ && defined __x86_64__
void _mips2c_call_systemv() asm("_mips2c_call_systemv");
#endif
void _mips2c_call_windows();
}

// clang-format off
namespace Mips2C {

namespace jak1 {
namespace draw_string { extern void link(); }
namespace particle_adgif { extern void link(); }
namespace sp_launch_particles_var { extern void link(); }
namespace sp_process_block_3d { extern void link(); }
namespace sp_process_block_2d { extern void link(); }
namespace draw_large_polygon { extern void link(); }
namespace init_sky_regs { extern void link(); }
namespace clip_polygon_against_positive_hyperplane { extern void link(); }
namespace render_sky_quad { extern void link(); }
namespace render_sky_tri { extern void link(); }
namespace set_tex_offset { extern void link(); }
namespace set_sky_vf27 { extern void link(); }
namespace set_sky_vf23_value { extern void link(); }
namespace adgif_shader_texture_with_update { extern void link(); }
namespace init_boundary_regs { extern void link(); }
namespace render_boundary_quad { extern void link(); }
namespace render_boundary_tri { extern void link(); }
namespace draw_boundary_polygon { extern void link(); }
namespace draw_inline_array_tfrag { extern void link(); }
namespace stats_tfrag_asm { extern void link(); }
namespace time_of_day_interp_colors_scratch { extern void link(); }
namespace collide_do_primitives { extern void link(); }
namespace moving_sphere_triangle_intersect { extern void link(); }
namespace method_12_collide_mesh { extern void link(); }
namespace method_11_collide_mesh { extern void link(); }
namespace collide_probe_node { extern void link(); }
namespace collide_probe_instance_tie { extern void link(); }
namespace method_26_collide_cache { extern void link(); }
namespace method_32_collide_cache { extern void link(); }
namespace pc_upload_collide_frag { extern void link(); }
namespace method_28_collide_cache { extern void link(); }
namespace method_27_collide_cache { extern void link(); }
namespace method_29_collide_cache { extern void link(); }
namespace method_12_collide_shape_prim_mesh { extern void link(); }
namespace method_14_collide_shape_prim_mesh { extern void link(); }
namespace method_13_collide_shape_prim_mesh { extern void link(); }
namespace method_30_collide_cache { extern void link(); }
namespace method_9_collide_cache_prim { extern void link(); }
namespace method_10_collide_cache_prim { extern void link(); }
namespace method_10_collide_puss_work { extern void link(); }
namespace method_9_collide_puss_work { extern void link(); }
namespace method_15_collide_mesh { extern void link(); }
namespace method_14_collide_mesh { extern void link(); }
namespace method_16_collide_edge_work { extern void link(); }
namespace method_15_collide_edge_work { extern void link(); }
namespace method_10_collide_edge_hold_list { extern void link(); }
namespace method_18_collide_edge_work { extern void link(); }
namespace calc_animation_from_spr { extern void link(); }
namespace bones_mtx_calc { extern void link(); }
namespace cspace_parented_transformq_joint { extern void link(); }
namespace draw_bones_merc { extern void link(); }
namespace draw_bones_check_longest_edge_asm { extern void link(); }
namespace blerc_execute { extern void link(); }
namespace setup_blerc_chains_for_one_fragment { extern void link(); }
namespace generic_merc_init_asm { extern void link(); }
namespace generic_merc_execute_asm { extern void link(); }
namespace mercneric_convert { extern void link(); }
namespace generic_prepare_dma_double { extern void link(); }
namespace generic_light_proc { extern void link(); }
namespace generic_envmap_proc { extern void link(); }
namespace high_speed_reject { extern void link(); }
namespace generic_prepare_dma_single { extern void link(); }
namespace ripple_create_wave_table { extern void link(); }
namespace ripple_execute_init { extern void link(); }
namespace ripple_apply_wave_table { extern void link(); }
namespace ripple_matrix_scale { extern void link(); }
namespace init_ocean_far_regs { extern void link(); }
namespace render_ocean_quad { extern void link(); }
namespace draw_large_polygon_ocean { extern void link(); }
namespace ocean_interp_wave { extern void link(); }
namespace ocean_generate_verts { extern void link(); }
namespace shadow_execute { extern void link(); }
namespace shadow_add_double_edges { extern void link(); }
namespace shadow_add_double_tris { extern void link(); }
namespace shadow_add_single_edges { extern void link(); }
namespace shadow_add_facing_single_tris { extern void link(); }
namespace shadow_add_verts { extern void link(); }
namespace shadow_find_double_edges { extern void link(); }
namespace shadow_find_facing_double_tris { extern void link(); }
namespace shadow_find_single_edges { extern void link(); }
namespace shadow_find_facing_single_tris { extern void link(); }
namespace shadow_init_vars { extern void link(); }
namespace shadow_scissor_top { extern void link(); }
namespace shadow_scissor_edges { extern void link(); }
namespace shadow_calc_dual_verts { extern void link(); }
namespace shadow_xform_verts { extern void link(); }
namespace draw_inline_array_instance_tie { extern void link(); }
namespace draw_inline_array_prototype_tie_generic_asm { extern void link(); }
namespace generic_tie_dma_to_spad_sync { extern void link(); }
namespace generic_envmap_dproc { extern void link(); }
namespace generic_interp_dproc { extern void link(); }
namespace generic_no_light_dproc { extern void link(); }
namespace generic_tie_convert { extern void link(); }
}  // namespace jak1

namespace jak2 {
namespace collide_do_primitives { extern void link(); }
namespace moving_sphere_triangle_intersect { extern void link(); }
namespace calc_animation_from_spr { extern void link(); }
namespace cspace_parented_transformq_joint { extern void link(); }
namespace draw_string_asm { extern void link(); }
namespace get_string_length { extern void link(); }
namespace adgif_shader_texture_with_update { extern void link(); }
namespace debug_line_clip { extern void link(); }
namespace init_boundary_regs { extern void link(); }
namespace render_boundary_tri { extern void link(); }
namespace render_boundary_quad { extern void link(); }
namespace set_sky_vf27 { extern void link(); }
namespace set_sky_vf23_value { extern void link(); }
namespace draw_boundary_polygon { extern void link(); }
namespace particle_adgif { extern void link(); }
namespace sp_launch_particles_var { extern void link(); }
namespace sparticle_motion_blur { extern void link(); }
namespace sp_process_block_2d { extern void link(); }
namespace sp_process_block_3d { extern void link(); }
namespace set_tex_offset { extern void link(); }
namespace draw_large_polygon { extern void link(); }
namespace render_sky_quad { extern void link(); }
namespace render_sky_tri { extern void link(); }
namespace method_16_sky_work { extern void link(); }
namespace method_17_sky_work { extern void link(); }
namespace method_32_sky_work { extern void link(); }
namespace method_33_sky_work { extern void link(); }
namespace method_28_sky_work { extern void link(); }
namespace method_29_sky_work { extern void link(); }
namespace method_30_sky_work { extern void link(); }
namespace method_11_collide_hash { extern void link(); }
namespace method_12_collide_hash { extern void link(); }
namespace fill_bg_using_box_new { extern void link(); }
namespace fill_bg_using_line_sphere_new { extern void link(); }
namespace method_12_collide_mesh { extern void link(); }
namespace method_14_collide_mesh { extern void link(); }
namespace method_15_collide_mesh { extern void link(); }
namespace method_10_collide_edge_hold_list { extern void link(); }
namespace method_19_collide_edge_work { extern void link(); }
namespace method_9_edge_grab_info { extern void link(); }
namespace method_16_collide_edge_work { extern void link(); }
namespace method_17_collide_edge_work { extern void link(); }
namespace method_18_collide_edge_work { extern void link(); }
namespace init_ocean_far_regs { extern void link(); }
namespace draw_large_polygon_ocean { extern void link(); }
namespace render_ocean_quad { extern void link(); }
namespace method_16_ocean { extern void link(); }
namespace method_15_ocean { extern void link(); }
namespace method_14_ocean { extern void link(); }
namespace method_18_grid_hash { extern void link(); }
namespace method_19_grid_hash { extern void link(); }
namespace method_20_grid_hash { extern void link(); }
namespace method_22_grid_hash { extern void link(); }
namespace method_28_sphere_hash { extern void link(); }
namespace method_33_sphere_hash { extern void link(); }
namespace method_29_sphere_hash { extern void link(); }
namespace method_30_sphere_hash { extern void link(); }
namespace method_31_sphere_hash { extern void link(); }
namespace method_32_sphere_hash { extern void link(); }
namespace method_33_spatial_hash { extern void link(); }
namespace method_39_spatial_hash { extern void link(); }
namespace method_36_spatial_hash { extern void link(); }
namespace method_37_spatial_hash { extern void link(); }
namespace method_35_spatial_hash { extern void link(); }
namespace method_10_collide_shape_prim_mesh { extern void link(); }
namespace method_10_collide_shape_prim_sphere { extern void link(); }
namespace method_10_collide_shape_prim_group { extern void link(); }
namespace method_11_collide_shape_prim_mesh { extern void link(); }
namespace method_11_collide_shape_prim_sphere { extern void link(); }
namespace method_11_collide_shape_prim_group { extern void link(); }
namespace method_9_collide_cache_prim { extern void link(); }
namespace method_10_collide_cache_prim { extern void link(); }
namespace method_17_collide_cache { extern void link(); }
namespace method_9_collide_puss_work { extern void link(); }
namespace method_10_collide_puss_work { extern void link(); }
namespace bones_mtx_calc { extern void link(); }
namespace foreground_check_longest_edge_asm { extern void link(); }
namespace foreground_merc { extern void link(); }
namespace add_light_sphere_to_light_group { extern void link(); }
namespace light_hash_add_items { extern void link(); }
namespace light_hash_count_items { extern void link(); }
namespace light_hash_get_bucket_index { extern void link(); }
namespace nav_state_patch_pointers { extern void link(); }
namespace method_45_nav_mesh { extern void link(); }
namespace method_20_nav_engine { extern void link(); }
namespace method_43_nav_mesh { extern void link(); }
namespace nav_dma_send_to_spr_no_flush { extern void link(); }
namespace nav_dma_send_from_spr_no_flush { extern void link(); }
namespace method_17_nav_engine { extern void link(); }
namespace method_39_nav_state { extern void link(); }
namespace method_17_nav_engine { extern void link(); }
namespace method_18_nav_engine { extern void link(); }
namespace method_21_nav_engine { extern void link(); }
namespace setup_blerc_chains_for_one_fragment { extern void link(); }
namespace blerc_execute { extern void link(); }
namespace ripple_execute_init { extern void link(); }
namespace ripple_create_wave_table { extern void link(); }
namespace ripple_apply_wave_table { extern void link(); }
namespace ripple_matrix_scale { extern void link(); }
namespace method_53_squid { extern void link(); }
namespace init_vortex_regs { extern void link(); }
namespace draw_large_polygon_vortex { extern void link(); }
namespace render_vortex_quad { extern void link(); }
namespace foreground_generic_merc { extern void link(); }
namespace generic_merc_init_asm { extern void link(); }
namespace mercneric_convert { extern void link(); }
namespace high_speed_reject { extern void link(); }
namespace generic_translucent { extern void link(); }
namespace generic_merc_query { extern void link(); }
namespace generic_merc_death { extern void link(); }
namespace generic_merc_execute_asm { extern void link(); }
namespace generic_merc_do_chain { extern void link(); }
namespace generic_light_proc { extern void link(); }
namespace generic_envmap_proc { extern void link(); }
namespace generic_prepare_dma_double { extern void link(); }
namespace generic_prepare_dma_single { extern void link(); }
namespace generic_warp_source_proc { extern void link(); }
namespace generic_warp_dest_proc { extern void link(); }
namespace generic_warp_dest { extern void link(); }
namespace generic_warp_envmap_dest { extern void link(); }
namespace generic_no_light_proc { extern void link(); }
namespace foreground_draw_hud { extern void link(); }
namespace shadow_execute { extern void link(); }
namespace shadow_add_double_edges { extern void link(); }
namespace shadow_add_double_tris { extern void link(); }
namespace shadow_add_single_tris { extern void link(); }
namespace shadow_add_single_edges { extern void link(); }
namespace shadow_add_facing_single_tris { extern void link(); }
namespace shadow_add_verts { extern void link(); }
namespace shadow_find_double_edges { extern void link(); }
namespace shadow_find_facing_double_tris { extern void link(); }
namespace shadow_find_single_edges { extern void link(); }
namespace shadow_find_facing_single_tris { extern void link(); }
namespace shadow_init_vars { extern void link(); }
namespace shadow_scissor_top { extern void link(); }
namespace shadow_scissor_edges { extern void link(); }
namespace shadow_calc_dual_verts { extern void link(); }
namespace shadow_xform_verts { extern void link(); }
}
namespace jak3 {
namespace light_hash_get_bucket_index { extern void link(); }
namespace add_light_sphere_to_light_group { extern void link(); }
namespace light_hash_count_items { extern void link(); }
namespace light_hash_add_items { extern void link(); }
namespace debug_line_clip { extern void link(); }
namespace init_boundary_regs { extern void link(); }
namespace draw_boundary_polygon { extern void link(); }
namespace render_boundary_quad { extern void link(); }
namespace render_boundary_tri { extern void link(); }
namespace set_sky_vf27 { extern void link(); }
namespace generic_light_proc { extern void link(); }
namespace generic_envmap_proc { extern void link(); }
namespace generic_prepare_dma_double { extern void link(); }
namespace generic_prepare_dma_single { extern void link(); }
namespace generic_warp_source_proc { extern void link(); }
namespace generic_warp_dest_proc { extern void link(); }
namespace generic_warp_dest { extern void link(); }
namespace generic_warp_envmap_dest { extern void link(); }
namespace generic_no_light_proc { extern void link(); }
namespace method_9_font_work { extern void link(); }
namespace draw_string_asm { extern void link(); }
namespace get_string_length { extern void link(); }
namespace adgif_shader_texture_with_update { extern void link(); }
namespace moving_sphere_triangle_intersect { extern void link(); }
namespace collide_do_primitives { extern void link(); }
namespace cspace_parented_transformq_joint { extern void link(); }
namespace foreground_check_longest_edge_asm { extern void link(); }
namespace foreground_merc { extern void link(); }
namespace foreground_generic_merc { extern void link(); }
namespace live_func_curve { extern void link(); }
namespace birth_func_curve { extern void link(); }
namespace method_11_collide_hash { extern void link(); }
namespace method_12_collide_hash { extern void link(); }
namespace fill_bg_using_box_new { extern void link(); }
namespace fill_bg_using_line_sphere_new { extern void link(); }
namespace method_12_collide_mesh { extern void link(); }
namespace method_14_collide_mesh { extern void link(); }
namespace method_15_collide_mesh { extern void link(); }
namespace method_10_collide_shape_prim_mesh { extern void link(); }
namespace method_10_collide_shape_prim_sphere { extern void link(); }
namespace method_10_collide_shape_prim_group { extern void link(); }
namespace method_11_collide_shape_prim_mesh { extern void link(); }
namespace method_11_collide_shape_prim_sphere { extern void link(); }
namespace method_11_collide_shape_prim_group { extern void link(); }
namespace method_9_collide_cache_prim { extern void link(); }
namespace method_10_collide_cache_prim { extern void link(); }
namespace method_17_collide_cache { extern void link(); }
namespace method_9_collide_puss_work { extern void link(); }
namespace method_10_collide_puss_work { extern void link(); }
namespace method_10_collide_edge_hold_list { extern void link(); }
namespace method_19_collide_edge_work { extern void link(); }
namespace method_9_edge_grab_info { extern void link(); }
namespace method_17_collide_edge_work { extern void link(); }
namespace method_16_collide_edge_work { extern void link(); }
namespace method_18_collide_edge_work { extern void link(); }
namespace method_18_grid_hash { extern void link(); }
namespace method_19_grid_hash { extern void link(); }
namespace method_20_grid_hash { extern void link(); }
namespace method_22_grid_hash { extern void link(); }
namespace method_28_sphere_hash { extern void link(); }
namespace method_32_sphere_hash { extern void link(); }
namespace method_29_sphere_hash { extern void link(); }
namespace method_30_sphere_hash { extern void link(); }
namespace method_31_sphere_hash { extern void link(); }
namespace method_32_spatial_hash { extern void link(); }
namespace method_38_spatial_hash { extern void link(); }
namespace method_35_spatial_hash { extern void link(); }
namespace method_36_spatial_hash { extern void link(); }
namespace method_34_spatial_hash { extern void link(); }
namespace sparticle_motion_blur { extern void link(); }
namespace sp_launch_particles_var { extern void link(); }
namespace particle_adgif { extern void link(); }
namespace sp_init_fields { extern void link(); }
namespace sp_process_block_2d { extern void link(); }
namespace sp_process_block_3d { extern void link(); }
namespace method_39_nav_state { extern void link(); }
namespace method_21_nav_engine { extern void link(); }
namespace method_20_nav_engine { extern void link(); }
namespace method_18_nav_engine { extern void link(); }
namespace method_17_nav_engine { extern void link(); }
namespace nav_state_patch_pointers { extern void link(); }
namespace nav_dma_send_from_spr_no_flush { extern void link(); }
namespace nav_dma_send_to_spr_no_flush { extern void link(); }
namespace blerc_execute { extern void link(); }
namespace setup_blerc_chains_for_one_fragment { extern void link(); }
namespace sparticle_motion_blur_dirt { extern void link(); }
namespace foreground_draw_hud { extern void link(); }
namespace ripple_matrix_scale { extern void link(); }
namespace ripple_apply_wave_table { extern void link(); }
namespace ripple_create_wave_table { extern void link(); }
namespace ripple_execute_init { extern void link(); }
namespace method_14_ocean { extern void link(); }
namespace method_15_ocean { extern void link(); }
namespace method_16_ocean { extern void link(); }
namespace init_ocean_far_regs { extern void link(); }
namespace draw_large_polygon_ocean { extern void link(); }
namespace render_ocean_quad { extern void link(); }
namespace generic_merc_do_chain { extern void link(); }
namespace generic_merc_execute_asm { extern void link(); }
namespace generic_merc_death { extern void link(); }
namespace generic_merc_query { extern void link(); }
namespace generic_translucent { extern void link(); }
namespace high_speed_reject { extern void link(); }
namespace mercneric_convert { extern void link(); }
namespace generic_merc_init_asm { extern void link(); }
namespace set_tex_offset { extern void link(); }
namespace draw_large_polygon { extern void link(); }
namespace render_sky_quad { extern void link(); }
namespace render_sky_tri { extern void link(); }
namespace method_17_sky_work { extern void link(); }
namespace method_18_sky_work { extern void link(); }
namespace method_29_sky_work { extern void link(); }
namespace method_30_sky_work { extern void link(); }
namespace method_31_sky_work { extern void link(); }
namespace method_34_sky_work { extern void link(); }
namespace method_35_sky_work { extern void link(); }
namespace method_32_sky_work { extern void link(); }
namespace set_sky_vf23_value { extern void link(); }
namespace shadow_xform_verts { extern void link(); }
namespace shadow_calc_dual_verts { extern void link(); }
namespace shadow_scissor_edges { extern void link(); }
namespace shadow_scissor_top { extern void link(); }
namespace shadow_init_vars { extern void link(); }
namespace shadow_find_facing_single_tris { extern void link(); }
namespace shadow_find_facing_double_tris { extern void link(); }
namespace shadow_find_single_edges { extern void link(); }
namespace shadow_find_double_edges { extern void link(); }
namespace shadow_add_verts { extern void link(); }
namespace shadow_add_facing_single_tris { extern void link(); }
namespace shadow_add_single_edges { extern void link(); }
namespace shadow_add_double_edges { extern void link(); }
namespace shadow_add_single_tris { extern void link(); }
namespace shadow_add_double_tris { extern void link(); }
namespace shadow_execute { extern void link(); }
namespace method_21_cloth_system { extern void link(); }

}

namespace jakx {
namespace get_string_length_asm { extern void link(); }
namespace draw_string_asm_packed { extern void link(); }
namespace draw_string_init_justify { extern void link(); }
namespace method_10_font_context { extern void link(); }
// sky.cpp ports (see game/mips2c/jakx_functions/sky.cpp)
namespace set_tex_offset { extern void link(); }
namespace render_sky_tri { extern void link(); }
namespace render_sky_quad { extern void link(); }
namespace draw_large_polygon { extern void link(); }
namespace clip_polygon_against_positive_hyperplane { extern void link(); }
namespace clip_polygon_against_negative_hyperplane { extern void link(); }
namespace method_17_sky_work { extern void link(); }
namespace method_18_sky_work { extern void link(); }
namespace method_29_sky_work { extern void link(); }
namespace method_30_sky_work { extern void link(); }
namespace method_31_sky_work { extern void link(); }
namespace method_32_sky_work { extern void link(); }
namespace method_34_sky_work { extern void link(); }
namespace method_35_sky_work { extern void link(); }
namespace set_sky_vf23_value { extern void link(); }
// joint.cpp port (see game/mips2c/jakx_functions/joint.cpp)
namespace cspace_parented_transformq_joint { extern void link(); }
// texture.cpp port (see game/mips2c/jakx_functions/texture.cpp)
namespace adgif_shader_texture_with_update { extern void link(); }
// debug.cpp port (see game/mips2c/jakx_functions/debug.cpp)
namespace debug_line_clip { extern void link(); }
namespace init_boundary_regs { extern void link(); }
namespace draw_boundary_polygon { extern void link(); }
namespace render_boundary_quad { extern void link(); }
namespace render_boundary_tri { extern void link(); }
// shadow.cpp port (see game/mips2c/jakx_functions/shadow.cpp)
namespace shadow_xform_verts { extern void link(); }
namespace shadow_calc_dual_verts { extern void link(); }
namespace shadow_scissor_edges { extern void link(); }
namespace shadow_scissor_top { extern void link(); }
namespace shadow_init_vars { extern void link(); }
namespace shadow_find_facing_single_tris { extern void link(); }
namespace shadow_find_single_edges { extern void link(); }
namespace shadow_find_facing_double_tris { extern void link(); }
namespace shadow_find_double_edges { extern void link(); }
namespace shadow_add_verts { extern void link(); }
namespace shadow_add_facing_single_tris { extern void link(); }
namespace shadow_add_single_edges { extern void link(); }
namespace shadow_add_single_tris { extern void link(); }
namespace shadow_add_double_tris { extern void link(); }
namespace shadow_add_double_edges { extern void link(); }
namespace shadow_execute { extern void link(); }
// sparticle_launcher.cpp port (see game/mips2c/jakx_functions/sparticle_launcher.cpp)
namespace sparticle_motion_blur { extern void link(); }
namespace particle_adgif { extern void link(); }
namespace sp_init_fields { extern void link(); }
namespace sp_launch_particles_var { extern void link(); }
// particle_curves.cpp port (see game/mips2c/jakx_functions/particle_curves.cpp)
namespace live_func_curve { extern void link(); }
namespace birth_func_curve { extern void link(); }
// wvehicle_part.cpp port (see game/mips2c/jakx_functions/wvehicle_part.cpp)
namespace sparticle_motion_blur_dirt { extern void link(); }
// wvehicle.cpp port (see game/mips2c/jakx_functions/wvehicle.cpp)
namespace method_61_wvehicle { extern void link(); }
namespace method_64_wvehicle { extern void link(); }
namespace method_129_wvehicle { extern void link(); }
namespace method_134_wvehicle { extern void link(); }
namespace method_214_wvehicle { extern void link(); }
namespace method_215_wvehicle { extern void link(); }
namespace method_217_wvehicle { extern void link(); }
namespace method_218_wvehicle { extern void link(); }
namespace method_219_wvehicle { extern void link(); }
namespace method_157_wvehicle { extern void link(); }
namespace method_220_wvehicle { extern void link(); }
namespace method_224_wvehicle { extern void link(); }
namespace method_133_wvehicle { extern void link(); }
namespace method_112_wvehicle { extern void link(); }
namespace wv_player_post_move_update { extern void link(); }
namespace plot_x_with_transform { extern void link(); }
namespace plot_engine_torque_curve { extern void link(); }
namespace estimate_eng_torque_from_gear { extern void link(); }
// wcar-base.cpp port (see game/mips2c/jakx_functions/wcar-base.cpp)
namespace method_115_wcar_base { extern void link(); }
// net_player.cpp port (see game/mips2c/jakx_functions/net_player.cpp)
namespace net_player_init_local { extern void link(); }
// ripple.cpp port (see game/mips2c/jakx_functions/ripple.cpp)
namespace ripple_matrix_scale { extern void link(); }
namespace ripple_apply_wave_table { extern void link(); }
namespace ripple_create_wave_table { extern void link(); }
namespace ripple_execute_init { extern void link(); }
// ocean.cpp port (see game/mips2c/jakx_functions/ocean.cpp)
namespace init_ocean_far_regs { extern void link(); }
namespace draw_large_polygon_ocean { extern void link(); }
namespace render_ocean_quad { extern void link(); }
// generic_effect.cpp port (see game/mips2c/jakx_functions/generic_effect.cpp)
namespace generic_light_proc { extern void link(); }
namespace generic_envmap_proc { extern void link(); }
namespace generic_prepare_dma_double { extern void link(); }
namespace generic_prepare_dma_single { extern void link(); }
namespace generic_warp_source_proc { extern void link(); }
namespace generic_warp_dest_proc { extern void link(); }
namespace generic_warp_dest { extern void link(); }
namespace generic_warp_envmap_dest { extern void link(); }
namespace generic_no_light_proc { extern void link(); }
// generic_merc.cpp port (see game/mips2c/jakx_functions/generic_merc.cpp)
namespace generic_merc_init_asm { extern void link(); }
namespace mercneric_convert { extern void link(); }
namespace high_speed_reject { extern void link(); }
namespace generic_translucent { extern void link(); }
namespace generic_merc_query { extern void link(); }
namespace generic_merc_death { extern void link(); }
namespace generic_merc_execute_asm { extern void link(); }
namespace generic_merc_do_chain { extern void link(); }
// sparticle.cpp port (see game/mips2c/jakx_functions/sparticle.cpp)
namespace sp_process_block_2d { extern void link(); }
namespace sp_process_block_3d { extern void link(); }
// foreground.cpp port (see game/mips2c/jakx_functions/foreground.cpp)
namespace foreground_check_longest_edge_asm { extern void link(); }
namespace foreground_merc { extern void link(); }
namespace foreground_generic_merc { extern void link(); }
namespace foreground_draw_hud { extern void link(); }
// collide_hash.cpp port (see game/mips2c/jakx_functions/collide_hash.cpp)
namespace method_11_collide_hash { extern void link(); }
namespace method_12_collide_hash { extern void link(); }
namespace fill_bg_using_box_new { extern void link(); }
namespace fill_bg_using_line_sphere_new { extern void link(); }
// collide_mesh.cpp port (see game/mips2c/jakx_functions/collide_mesh.cpp)
namespace method_12_collide_mesh { extern void link(); }
namespace method_14_collide_mesh { extern void link(); }
namespace method_15_collide_mesh { extern void link(); }
// collide_cache.cpp port (see game/mips2c/jakx_functions/collide_cache.cpp)
namespace method_10_collide_shape_prim_mesh { extern void link(); }
namespace method_10_collide_shape_prim_sphere { extern void link(); }
namespace method_10_collide_shape_prim_group { extern void link(); }
namespace method_11_collide_shape_prim_mesh { extern void link(); }
namespace method_11_collide_shape_prim_sphere { extern void link(); }
namespace method_11_collide_shape_prim_group { extern void link(); }
namespace method_9_collide_cache_prim { extern void link(); }
namespace method_10_collide_cache_prim { extern void link(); }
namespace method_17_collide_cache { extern void link(); }
namespace method_9_collide_puss_work { extern void link(); }
namespace method_10_collide_puss_work { extern void link(); }
// collide_edge_grab.cpp port (see game/mips2c/jakx_functions/collide_edge_grab.cpp)
namespace method_10_collide_edge_hold_list { extern void link(); }
namespace method_19_collide_edge_work { extern void link(); }
namespace method_9_edge_grab_info { extern void link(); }
namespace method_17_collide_edge_work { extern void link(); }
namespace method_16_collide_edge_work { extern void link(); }
namespace method_18_collide_edge_work { extern void link(); }
// collide_func.cpp port (see game/mips2c/jakx_functions/collide_func.cpp)
namespace moving_sphere_triangle_intersect { extern void link(); }
namespace collide_do_primitives { extern void link(); }
// lights.cpp port (see game/mips2c/jakx_functions/lights.cpp)
namespace light_hash_add_items { extern void link(); }
namespace light_hash_count_items { extern void link(); }
namespace add_light_sphere_to_light_group { extern void link(); }
namespace light_hash_get_bucket_index { extern void link(); }
// merc_blend_shape.cpp port (see game/mips2c/jakx_functions/merc_blend_shape.cpp)
namespace blerc_execute { extern void link(); }
namespace setup_blerc_chains_for_one_fragment { extern void link(); }
// nav_control.cpp port (see game/mips2c/jakx_functions/nav_control.cpp)
namespace method_39_nav_state { extern void link(); }
// nav_engine.cpp port (see game/mips2c/jakx_functions/nav_engine.cpp)
namespace method_21_nav_engine { extern void link(); }
namespace method_20_nav_engine { extern void link(); }
namespace method_18_nav_engine { extern void link(); }
namespace method_17_nav_engine { extern void link(); }
namespace nav_state_patch_pointers { extern void link(); }
namespace nav_dma_send_from_spr_no_flush { extern void link(); }
namespace nav_dma_send_to_spr_no_flush { extern void link(); }
// ocean_vu0.cpp port (see game/mips2c/jakx_functions/ocean_vu0.cpp)
namespace method_14_ocean { extern void link(); }
namespace method_15_ocean { extern void link(); }
namespace method_16_ocean { extern void link(); }
// spatial_hash.cpp port (see game/mips2c/jakx_functions/spatial_hash.cpp)
namespace method_18_grid_hash { extern void link(); }
namespace method_19_grid_hash { extern void link(); }
namespace method_20_grid_hash { extern void link(); }
namespace method_22_grid_hash { extern void link(); }
namespace method_28_sphere_hash { extern void link(); }
namespace method_32_sphere_hash { extern void link(); }
namespace method_29_sphere_hash { extern void link(); }
namespace method_30_sphere_hash { extern void link(); }
namespace method_31_sphere_hash { extern void link(); }
namespace method_32_spatial_hash { extern void link(); }
namespace method_38_spatial_hash { extern void link(); }
namespace method_35_spatial_hash { extern void link(); }
namespace method_36_spatial_hash { extern void link(); }
namespace method_34_spatial_hash { extern void link(); }
// cloth.cpp port (see game/mips2c/jakx_functions/cloth.cpp)
namespace method_21_cloth_system { extern void link(); }
}
// clang-format on

LinkedFunctionTable gLinkedFunctionTable;
Rng gRng;
PerGameVersion<std::unordered_map<std::string, std::vector<void (*)()>>> gMips2CLinkCallbacks = {
    //////// JAK 1
    {{"font", {jak1::draw_string::link}},
     {"sparticle-launcher", {jak1::particle_adgif::link, jak1::sp_launch_particles_var::link}},
     {"sparticle", {jak1::sp_process_block_3d::link, jak1::sp_process_block_2d::link}},
     {"texture", {jak1::adgif_shader_texture_with_update::link}},
     {"sky-tng",
      {jak1::draw_large_polygon::link, jak1::init_sky_regs::link,
       jak1::clip_polygon_against_positive_hyperplane::link, jak1::render_sky_quad::link,
       jak1::render_sky_tri::link, jak1::set_tex_offset::link, jak1::set_sky_vf27::link,
       jak1::set_sky_vf23_value::link}},
     {"load-boundary",
      {jak1::init_boundary_regs::link, jak1::render_boundary_quad::link,
       jak1::render_boundary_tri::link, jak1::draw_boundary_polygon::link}},
     {"tfrag", {jak1::draw_inline_array_tfrag::link, jak1::stats_tfrag_asm::link}},
     {"time-of-day", {jak1::time_of_day_interp_colors_scratch::link}},
     {"collide-func",
      {jak1::collide_do_primitives::link, jak1::moving_sphere_triangle_intersect::link}},
     {"collide-probe", {jak1::collide_probe_node::link, jak1::collide_probe_instance_tie::link}},
     {"collide-mesh",
      {jak1::method_12_collide_mesh::link, jak1::method_11_collide_mesh::link,
       jak1::method_15_collide_mesh::link, jak1::method_14_collide_mesh::link}},
     {"collide-cache",
      {jak1::method_26_collide_cache::link, jak1::method_32_collide_cache::link,
       jak1::pc_upload_collide_frag::link, jak1::method_28_collide_cache::link,
       jak1::method_27_collide_cache::link, jak1::method_29_collide_cache::link,
       jak1::method_12_collide_shape_prim_mesh::link, jak1::method_14_collide_shape_prim_mesh::link,
       jak1::method_13_collide_shape_prim_mesh::link, jak1::method_30_collide_cache::link,
       jak1::method_9_collide_cache_prim::link, jak1::method_10_collide_cache_prim::link,
       jak1::method_10_collide_puss_work::link, jak1::method_9_collide_puss_work::link}},
     {"collide-edge-grab",
      {jak1::method_16_collide_edge_work::link, jak1::method_15_collide_edge_work::link,
       jak1::method_10_collide_edge_hold_list::link, jak1::method_18_collide_edge_work::link}},
     {"joint", {jak1::calc_animation_from_spr::link, jak1::cspace_parented_transformq_joint::link}},
     {"bones",
      {jak1::bones_mtx_calc::link, jak1::draw_bones_merc::link,
       jak1::draw_bones_check_longest_edge_asm::link}},
     {"merc-blend-shape",
      {jak1::blerc_execute::link, jak1::setup_blerc_chains_for_one_fragment::link}},
     {"generic-merc",
      {jak1::generic_merc_init_asm::link, jak1::generic_merc_execute_asm::link,
       jak1::mercneric_convert::link, jak1::high_speed_reject::link}},
     {"generic-effect",
      {jak1::generic_prepare_dma_double::link, jak1::generic_light_proc::link,
       jak1::generic_envmap_proc::link, jak1::generic_prepare_dma_single::link,
       jak1::generic_envmap_dproc::link, jak1::generic_interp_dproc::link,
       jak1::generic_no_light_dproc::link}},
     {"ripple",
      {jak1::ripple_execute_init::link, jak1::ripple_create_wave_table::link,
       jak1::ripple_apply_wave_table::link, jak1::ripple_matrix_scale::link}},
     {"ocean",
      {jak1::init_ocean_far_regs::link, jak1::render_ocean_quad::link,
       jak1::draw_large_polygon_ocean::link}},
     {"ocean-vu0", {jak1::ocean_interp_wave::link, jak1::ocean_generate_verts::link}},
     {"shadow-cpu",
      {jak1::shadow_execute::link, jak1::shadow_add_double_edges::link,
       jak1::shadow_add_double_tris::link, jak1::shadow_add_single_edges::link,
       jak1::shadow_add_facing_single_tris::link, jak1::shadow_add_verts::link,
       jak1::shadow_find_double_edges::link, jak1::shadow_find_facing_double_tris::link,
       jak1::shadow_find_single_edges::link, jak1::shadow_find_facing_single_tris::link,
       jak1::shadow_init_vars::link, jak1::shadow_scissor_top::link,
       jak1::shadow_scissor_edges::link, jak1::shadow_calc_dual_verts::link,
       jak1::shadow_xform_verts::link}},
     {"tie-methods",
      {jak1::draw_inline_array_instance_tie::link,
       jak1::draw_inline_array_prototype_tie_generic_asm::link}},
     {"generic-tie", {jak1::generic_tie_dma_to_spad_sync::link, jak1::generic_tie_convert::link}}},
    /////////// JAK 2
    {{"collide-func",
      {jak2::collide_do_primitives::link, jak2::moving_sphere_triangle_intersect::link}},
     {"joint", {jak2::calc_animation_from_spr::link, jak2::cspace_parented_transformq_joint::link}},
     {"font", {jak2::get_string_length::link, jak2::draw_string_asm::link}},
     {"texture", {jak2::adgif_shader_texture_with_update::link}},
     {"debug",
      {jak2::debug_line_clip::link, jak2::init_boundary_regs::link,
       jak2::render_boundary_quad::link, jak2::render_boundary_tri::link, jak2::set_sky_vf27::link,
       jak2::draw_boundary_polygon::link}},
     {"sparticle-launcher",
      {jak2::particle_adgif::link, jak2::sp_launch_particles_var::link,
       jak2::sparticle_motion_blur::link}},
     {"sparticle", {jak2::sp_process_block_2d::link, jak2::sp_process_block_3d::link}},
     {"sky-tng",
      {jak2::set_tex_offset::link, jak2::draw_large_polygon::link, jak2::render_sky_quad::link,
       jak2::render_sky_tri::link, jak2::method_16_sky_work::link, jak2::method_17_sky_work::link,
       jak2::method_32_sky_work::link, jak2::method_33_sky_work::link,
       jak2::method_28_sky_work::link, jak2::method_29_sky_work::link,
       jak2::method_30_sky_work::link, jak2::set_sky_vf23_value::link}},
     {"collide-hash",
      {jak2::method_11_collide_hash::link, jak2::method_12_collide_hash::link,
       jak2::fill_bg_using_box_new::link, jak2::fill_bg_using_line_sphere_new::link}},
     {"collide-mesh",
      {jak2::method_12_collide_mesh::link, jak2::method_14_collide_mesh::link,
       jak2::method_15_collide_mesh::link}},
     {"collide-edge-grab",
      {jak2::method_10_collide_edge_hold_list::link, jak2::method_19_collide_edge_work::link,
       jak2::method_9_edge_grab_info::link, jak2::method_16_collide_edge_work::link,
       jak2::method_17_collide_edge_work::link, jak2::method_18_collide_edge_work::link}},
     {"ocean-vu0",
      {jak2::method_16_ocean::link, jak2::method_15_ocean::link, jak2::method_14_ocean::link}},
     {"ocean",
      {jak2::init_ocean_far_regs::link, jak2::draw_large_polygon_ocean::link,
       jak2::render_ocean_quad::link}},
     {"spatial-hash",
      {jak2::method_18_grid_hash::link, jak2::method_19_grid_hash::link,
       jak2::method_20_grid_hash::link, jak2::method_22_grid_hash::link,
       jak2::method_28_sphere_hash::link, jak2::method_33_sky_work::link,
       jak2::method_29_sphere_hash::link, jak2::method_30_sphere_hash::link,
       jak2::method_31_sphere_hash::link, jak2::method_32_sphere_hash::link,
       jak2::method_33_spatial_hash::link, jak2::method_39_spatial_hash::link,
       jak2::method_36_spatial_hash::link, jak2::method_37_spatial_hash::link,
       jak2::method_35_spatial_hash::link, jak2::method_33_sphere_hash::link}},
     {"collide-cache",
      {jak2::method_10_collide_shape_prim_mesh::link,
       jak2::method_10_collide_shape_prim_sphere::link,
       jak2::method_10_collide_shape_prim_group::link,
       jak2::method_11_collide_shape_prim_mesh::link,
       jak2::method_11_collide_shape_prim_sphere::link,
       jak2::method_11_collide_shape_prim_group::link, jak2::method_9_collide_cache_prim::link,
       jak2::method_10_collide_cache_prim::link, jak2::method_17_collide_cache::link,
       jak2::method_9_collide_puss_work::link, jak2::method_10_collide_puss_work::link}},
     {"bones", {jak2::bones_mtx_calc::link}},
     {"foreground",
      {jak2::foreground_check_longest_edge_asm::link, jak2::foreground_merc::link,
       jak2::foreground_generic_merc::link, jak2::foreground_draw_hud::link}},
     {"lights",
      {jak2::add_light_sphere_to_light_group::link, jak2::light_hash_add_items::link,
       jak2::light_hash_count_items::link, jak2::light_hash_get_bucket_index::link}},
     {"nav-control", {jak2::method_39_nav_state::link}},
     {"nav-mesh",
      {jak2::nav_state_patch_pointers::link, jak2::method_45_nav_mesh::link,
       jak2::method_20_nav_engine::link, jak2::method_43_nav_mesh::link,
       jak2::nav_dma_send_to_spr_no_flush::link, jak2::nav_dma_send_from_spr_no_flush::link,
       jak2::method_17_nav_engine::link, jak2::method_18_nav_engine::link,
       jak2::method_21_nav_engine::link}},
     {"merc-blend-shape",
      {jak2::setup_blerc_chains_for_one_fragment::link, jak2::blerc_execute::link}},
     {"ripple",
      {jak2::ripple_execute_init::link, jak2::ripple_create_wave_table::link,
       jak2::ripple_apply_wave_table::link, jak2::ripple_matrix_scale::link}},
     {"squid-setup", {jak2::method_53_squid::link}},
     {"vortex",
      {jak2::init_vortex_regs::link, jak2::draw_large_polygon_vortex::link,
       jak2::render_vortex_quad::link}},
     {"generic-merc",
      {jak2::generic_merc_init_asm::link, jak2::mercneric_convert::link,
       jak2::high_speed_reject::link, jak2::generic_translucent::link,
       jak2::generic_merc_query::link, jak2::generic_merc_death::link,
       jak2::generic_merc_execute_asm::link, jak2::generic_merc_do_chain::link}},
     {"generic-effect",
      {jak2::generic_light_proc::link, jak2::generic_envmap_proc::link,
       jak2::generic_prepare_dma_double::link, jak2::generic_prepare_dma_single::link,
       jak2::generic_warp_source_proc::link, jak2::generic_warp_dest_proc::link,
       jak2::generic_warp_dest::link, jak2::generic_warp_envmap_dest::link,
       jak2::generic_no_light_proc::link}},
     {"shadow-cpu",
      {jak2::shadow_execute::link, jak2::shadow_add_double_edges::link,
       jak2::shadow_add_double_tris::link, jak2::shadow_add_single_tris::link,
       jak2::shadow_add_single_edges::link, jak2::shadow_add_facing_single_tris::link,
       jak2::shadow_add_verts::link, jak2::shadow_find_double_edges::link,
       jak2::shadow_find_facing_double_tris::link, jak2::shadow_find_single_edges::link,
       jak2::shadow_find_facing_single_tris::link, jak2::shadow_init_vars::link,
       jak2::shadow_scissor_top::link, jak2::shadow_scissor_edges::link,
       jak2::shadow_calc_dual_verts::link, jak2::shadow_xform_verts::link}}},
    /////////// JAK 3
    {{"lights",
      {jak3::light_hash_get_bucket_index::link, jak3::add_light_sphere_to_light_group::link,
       jak3::light_hash_count_items::link, jak3::light_hash_add_items::link}},
     {"debug",
      {jak3::debug_line_clip::link, jak3::init_boundary_regs::link,
       jak3::draw_boundary_polygon::link, jak3::render_boundary_quad::link,
       jak3::render_boundary_tri::link, jak3::set_sky_vf27::link}},
     {"generic-effect",
      {jak3::generic_light_proc::link, jak3::generic_envmap_proc::link,
       jak3::generic_prepare_dma_double::link, jak3::generic_prepare_dma_single::link,
       jak3::generic_warp_source_proc::link, jak3::generic_warp_dest_proc::link,
       jak3::generic_warp_dest::link, jak3::generic_warp_envmap_dest::link,
       jak3::generic_no_light_proc::link}},
     {"font",
      {jak3::method_9_font_work::link, jak3::draw_string_asm::link, jak3::get_string_length::link}},
     {"texture", {jak3::adgif_shader_texture_with_update::link}},
     {"collide-func",
      {jak3::moving_sphere_triangle_intersect::link, jak3::collide_do_primitives::link}},
     {"joint", {jak3::cspace_parented_transformq_joint::link}},
     {"foreground",
      {jak3::foreground_check_longest_edge_asm::link, jak3::foreground_generic_merc::link,
       jak3::foreground_merc::link, jak3::foreground_draw_hud::link}},
     {"particle-curves", {jak3::live_func_curve::link, jak3::birth_func_curve::link}},
     {"collide-hash",
      {jak3::method_11_collide_hash::link, jak3::method_12_collide_hash::link,
       jak3::fill_bg_using_box_new::link, jak3::fill_bg_using_line_sphere_new::link}},
     {"collide-mesh",
      {jak3::method_12_collide_mesh::link, jak3::method_14_collide_mesh::link,
       jak3::method_15_collide_mesh::link, jak3::method_10_collide_shape_prim_mesh::link}},
     {"collide-cache",
      {jak3::method_10_collide_shape_prim_mesh::link,
       jak3::method_10_collide_shape_prim_sphere::link,
       jak3::method_10_collide_shape_prim_group::link,
       jak3::method_11_collide_shape_prim_mesh::link,
       jak3::method_11_collide_shape_prim_sphere::link,
       jak3::method_11_collide_shape_prim_group::link, jak3::method_9_collide_cache_prim::link,
       jak3::method_10_collide_cache_prim::link, jak3::method_17_collide_cache::link,
       jak3::method_9_collide_puss_work::link, jak3::method_10_collide_puss_work::link}},
     {"collide-edge-grab",
      {jak3::method_10_collide_edge_hold_list::link, jak3::method_19_collide_edge_work::link,
       jak3::method_9_edge_grab_info::link, jak3::method_17_collide_edge_work::link,
       jak3::method_16_collide_edge_work::link, jak3::method_18_collide_edge_work::link}},
     {"spatial-hash",
      {jak3::method_18_grid_hash::link, jak3::method_19_grid_hash::link,
       jak3::method_20_grid_hash::link, jak3::method_22_grid_hash::link,
       jak3::method_28_sphere_hash::link, jak3::method_32_sphere_hash::link,
       jak3::method_29_sphere_hash::link, jak3::method_30_sphere_hash::link,
       jak3::method_31_sphere_hash::link, jak3::method_32_spatial_hash::link,
       jak3::method_38_spatial_hash::link, jak3::method_35_spatial_hash::link,
       jak3::method_36_spatial_hash::link, jak3::method_34_spatial_hash::link}},
     {"sparticle-launcher",
      {jak3::sparticle_motion_blur::link, jak3::sp_launch_particles_var::link,
       jak3::particle_adgif::link, jak3::sp_init_fields::link}},
     {"sparticle", {jak3::sp_process_block_2d::link, jak3::sp_process_block_3d::link}},
     {"nav-engine",
      {jak3::method_21_nav_engine::link, jak3::method_20_nav_engine::link,
       jak3::method_18_nav_engine::link, jak3::method_17_nav_engine::link,
       jak3::nav_state_patch_pointers::link, jak3::nav_dma_send_from_spr_no_flush::link,
       jak3::nav_dma_send_to_spr_no_flush::link}},
     {"nav-control", {jak3::method_39_nav_state::link}},
     {"merc-blend-shape",
      {jak3::blerc_execute::link, jak3::setup_blerc_chains_for_one_fragment::link}},
     {"wvehicle-part", {jak3::sparticle_motion_blur_dirt::link}},
     {"ripple",
      {jak3::ripple_matrix_scale::link, jak3::ripple_apply_wave_table::link,
       jak3::ripple_create_wave_table::link, jak3::ripple_execute_init::link}},
     {"ocean-vu0",
      {jak3::method_14_ocean::link, jak3::method_15_ocean::link, jak3::method_16_ocean::link}},
     {"ocean",
      {jak3::init_ocean_far_regs::link, jak3::draw_large_polygon_ocean::link,
       jak3::render_ocean_quad::link}},
     {"generic-merc",
      {jak3::generic_merc_do_chain::link, jak3::generic_merc_execute_asm::link,
       jak3::generic_merc_death::link, jak3::generic_merc_query::link,
       jak3::generic_translucent::link, jak3::high_speed_reject::link,
       jak3::mercneric_convert::link, jak3::generic_merc_init_asm::link}},
     {"sky-tng",
      {jak3::set_tex_offset::link, jak3::render_sky_quad::link, jak3::render_sky_tri::link,
       jak3::method_17_sky_work::link, jak3::method_18_sky_work::link,
       jak3::method_29_sky_work::link, jak3::method_30_sky_work::link,
       jak3::method_31_sky_work::link, jak3::method_34_sky_work::link,
       jak3::method_35_sky_work::link, jak3::method_32_sky_work::link,
       jak3::set_sky_vf23_value::link, jak3::draw_large_polygon::link}},
     {"shadow-cpu",
      {jak3::shadow_xform_verts::link, jak3::shadow_execute::link,
       jak3::shadow_calc_dual_verts::link, jak3::shadow_scissor_edges::link,
       jak3::shadow_scissor_top::link, jak3::shadow_init_vars::link,
       jak3::shadow_find_facing_single_tris::link, jak3::shadow_find_facing_double_tris::link,
       jak3::shadow_find_single_edges::link, jak3::shadow_find_double_edges::link,
       jak3::shadow_add_verts::link, jak3::shadow_add_facing_single_tris::link,
       jak3::shadow_add_single_edges::link, jak3::shadow_add_double_edges::link,
       jak3::shadow_add_single_tris::link, jak3::shadow_add_double_tris::link}},
     {"cloth", {jak3::method_21_cloth_system::link}}},
    /////////// JAK X
    // JakX reuses jak3's mips2c implementations — same engine, same assembly routines.
    // Complete copy of jak3's table to avoid missing any functions.
    // Exceptions: routines where jakx's font-context / font-work layouts
    // diverged from jak3 have jakx-native ports in mips2c/jakx_functions/.
    // lights: jakx-native ports — structurally identical to jak3;
    // jakx namespace only. See game/mips2c/jakx_functions/lights.cpp.
    {{"lights",
      {jakx::light_hash_get_bucket_index::link, jakx::add_light_sphere_to_light_group::link,
       jakx::light_hash_count_items::link, jakx::light_hash_add_items::link}},
     {"debug",
      {jakx::debug_line_clip::link, jakx::init_boundary_regs::link,
       jakx::draw_boundary_polygon::link, jakx::render_boundary_quad::link,
       jakx::render_boundary_tri::link, jak3::set_sky_vf27::link}},
     // generic-effect: jakx-native ports — structurally identical to jak3;
     // jakx namespace only. See game/mips2c/jakx_functions/generic_effect.cpp.
     {"generic-effect",
      {jakx::generic_light_proc::link, jakx::generic_envmap_proc::link,
       jakx::generic_prepare_dma_double::link, jakx::generic_prepare_dma_single::link,
       jakx::generic_warp_source_proc::link, jakx::generic_warp_dest_proc::link,
       jakx::generic_warp_dest::link, jakx::generic_warp_envmap_dest::link,
       jakx::generic_no_light_proc::link}},
     {"font",
      {jak3::method_9_font_work::link, jak3::draw_string_asm::link,
       // JakX-native: font-context flags at offset 12 (jak3: 64), font-work
       // size vectors at 320/336/368/384 (jak3: 208/224/256/272), save slot
       // at 496 (jak3: 464). See game/mips2c/jakx_functions/font.cpp.
       jakx::get_string_length_asm::link,
       jakx::draw_string_asm_packed::link,
       jakx::draw_string_init_justify::link,
       jakx::method_10_font_context::link}},
     {"texture", {jakx::adgif_shader_texture_with_update::link}},
     // collide-func: jakx-native ports — structurally identical to jak3;
     // jakx namespace only. See game/mips2c/jakx_functions/collide_func.cpp.
     {"collide-func",
      {jakx::moving_sphere_triangle_intersect::link, jakx::collide_do_primitives::link}},
     // joint — jakx-native port; structurally identical to jak3 but lives
     // in the jakx namespace so future divergence (if any) can be expressed
     // without touching jak3's copy. See game/mips2c/jakx_functions/joint.cpp.
     {"joint", {jakx::cspace_parented_transformq_joint::link}},
     // foreground: jakx-native ports — structurally identical to jak3;
     // jakx namespace only. See game/mips2c/jakx_functions/foreground.cpp.
     {"foreground",
      {jakx::foreground_check_longest_edge_asm::link, jakx::foreground_generic_merc::link,
       jakx::foreground_merc::link, jakx::foreground_draw_hud::link}},
     // particle-curves — jakx-native ports; structurally identical to jak3
     // but in jakx namespace so future divergence is localized.
     // See game/mips2c/jakx_functions/particle_curves.cpp.
     {"particle-curves", {jakx::live_func_curve::link, jakx::birth_func_curve::link}},
     // collide-hash: jakx-native ports — structurally identical to jak3;
     // jakx namespace only. See game/mips2c/jakx_functions/collide_hash.cpp.
     {"collide-hash",
      {jakx::method_11_collide_hash::link, jakx::method_12_collide_hash::link,
       jakx::fill_bg_using_box_new::link, jakx::fill_bg_using_line_sphere_new::link}},
     // collide-mesh / collide-cache: jakx-native ports — structurally
     // identical to jak3; jakx namespace only.
     // See game/mips2c/jakx_functions/collide_mesh.cpp and collide_cache.cpp.
     {"collide-mesh",
      {jakx::method_12_collide_mesh::link, jakx::method_14_collide_mesh::link,
       jakx::method_15_collide_mesh::link, jakx::method_10_collide_shape_prim_mesh::link}},
     {"collide-cache",
      {jakx::method_10_collide_shape_prim_mesh::link,
       jakx::method_10_collide_shape_prim_sphere::link,
       jakx::method_10_collide_shape_prim_group::link,
       jakx::method_11_collide_shape_prim_mesh::link,
       jakx::method_11_collide_shape_prim_sphere::link,
       jakx::method_11_collide_shape_prim_group::link, jakx::method_9_collide_cache_prim::link,
       jakx::method_10_collide_cache_prim::link, jakx::method_17_collide_cache::link,
       jakx::method_9_collide_puss_work::link, jakx::method_10_collide_puss_work::link}},
     // collide-edge-grab / spatial-hash: jakx-native ports — structurally
     // identical to jak3; jakx namespace only.
     {"collide-edge-grab",
      {jakx::method_10_collide_edge_hold_list::link, jakx::method_19_collide_edge_work::link,
       jakx::method_9_edge_grab_info::link, jakx::method_17_collide_edge_work::link,
       jakx::method_16_collide_edge_work::link, jakx::method_18_collide_edge_work::link}},
     {"spatial-hash",
      {jakx::method_18_grid_hash::link, jakx::method_19_grid_hash::link,
       jakx::method_20_grid_hash::link, jakx::method_22_grid_hash::link,
       jakx::method_28_sphere_hash::link, jakx::method_32_sphere_hash::link,
       jakx::method_29_sphere_hash::link, jakx::method_30_sphere_hash::link,
       jakx::method_31_sphere_hash::link, jakx::method_32_spatial_hash::link,
       jakx::method_38_spatial_hash::link, jakx::method_35_spatial_hash::link,
       jakx::method_36_spatial_hash::link, jakx::method_34_spatial_hash::link}},
     // All four sparticle_launcher.cpp functions are now jakx-native ports
     // (see game/mips2c/jakx_functions/sparticle_launcher.cpp).
     {"sparticle-launcher",
      {jakx::sparticle_motion_blur::link, jakx::sp_launch_particles_var::link,
       jakx::particle_adgif::link, jakx::sp_init_fields::link}},
     // sparticle: jakx-native ports — structurally identical to jak3;
     // jakx namespace only. See game/mips2c/jakx_functions/sparticle.cpp.
     {"sparticle", {jakx::sp_process_block_2d::link, jakx::sp_process_block_3d::link}},
     // nav-engine / nav-control / merc-blend-shape: jakx-native ports —
     // structurally identical to jak3; jakx namespace only.
     {"nav-engine",
      {jakx::method_21_nav_engine::link, jakx::method_20_nav_engine::link,
       jakx::method_18_nav_engine::link, jakx::method_17_nav_engine::link,
       jakx::nav_state_patch_pointers::link, jakx::nav_dma_send_from_spr_no_flush::link,
       jakx::nav_dma_send_to_spr_no_flush::link}},
     {"nav-control", {jakx::method_39_nav_state::link}},
     {"merc-blend-shape",
      {jakx::blerc_execute::link, jakx::setup_blerc_chains_for_one_fragment::link}},
     // wvehicle-part: jakx-native sparticle-motion-blur-dirt (target access
     // via view-get-active-target + offset-184 control handle).
     {"wvehicle-part", {jakx::sparticle_motion_blur_dirt::link}},
     // wvehicle: jakx-native methods that fail to decompile to GOAL expressions
     // (decompiler emits raw mips2c instead). See game/mips2c/jakx_functions/wvehicle.cpp.
     {"wvehicle", {jakx::method_61_wvehicle::link, jakx::method_64_wvehicle::link, jakx::method_129_wvehicle::link, jakx::method_134_wvehicle::link, jakx::method_157_wvehicle::link, jakx::method_214_wvehicle::link, jakx::method_215_wvehicle::link, jakx::method_217_wvehicle::link, jakx::method_218_wvehicle::link, jakx::method_219_wvehicle::link, jakx::method_220_wvehicle::link, jakx::method_224_wvehicle::link, jakx::method_133_wvehicle::link, jakx::method_112_wvehicle::link, jakx::wv_player_post_move_update::link, jakx::plot_x_with_transform::link, jakx::plot_engine_torque_curve::link, jakx::estimate_eng_torque_from_gear::link}},
     // wcar-base: shock-joint updater (method 115) — dense VU stack math + 4-wheel iteration.
     // See game/mips2c/jakx_functions/wcar-base.cpp.
     {"wcar-base", {jakx::method_115_wcar_base::link}},
     // net-player: BAD-PROLOGUE asm function (net-player-init-local) — process-spawn
     // :init handler called from net-game-mgr-method-52. See game/mips2c/jakx_functions/net_player.cpp.
     {"net-player", {jakx::net_player_init_local::link}},
     // ripple: jakx-native ports (see game/mips2c/jakx_functions/ripple.cpp).
     // All four functions are structurally identical to jak3; jakx namespace only.
     {"ripple",
      {jakx::ripple_matrix_scale::link, jakx::ripple_apply_wave_table::link,
       jakx::ripple_create_wave_table::link, jakx::ripple_execute_init::link}},
     // ocean-vu0: jakx-native ports — structurally identical to jak3;
     // jakx namespace only. See game/mips2c/jakx_functions/ocean_vu0.cpp.
     {"ocean-vu0",
      {jakx::method_14_ocean::link, jakx::method_15_ocean::link, jakx::method_16_ocean::link}},
     {"ocean",
      {jakx::init_ocean_far_regs::link, jakx::draw_large_polygon_ocean::link,
       jakx::render_ocean_quad::link}},
     // generic-merc: jakx-native ports — structurally identical to jak3;
     // jakx namespace only. See game/mips2c/jakx_functions/generic_merc.cpp.
     {"generic-merc",
      {jakx::generic_merc_do_chain::link, jakx::generic_merc_execute_asm::link,
       jakx::generic_merc_death::link, jakx::generic_merc_query::link,
       jakx::generic_translucent::link, jakx::high_speed_reject::link,
       jakx::mercneric_convert::link, jakx::generic_merc_init_asm::link}},
     {"sky-tng",
      // JakX-native ports — see game/mips2c/jakx_functions/sky.cpp.
      // Simple funcs (set-tex-offset, render-sky-quad/tri, draw-large-polygon,
      // clip-polygon-against-*) are structurally identical to jak3. The
      // sky-work methods (17/18/29-35) DIVERGE between jak3 and jakx —
      // the current bindings use jak3 bodies and should be rewritten per
      // method from jakx sky-tng_ir2.asm.
      {jakx::set_tex_offset::link, jakx::render_sky_quad::link, jakx::render_sky_tri::link,
       jakx::method_17_sky_work::link, jakx::method_18_sky_work::link,
       jakx::method_29_sky_work::link, jakx::method_30_sky_work::link,
       jakx::method_31_sky_work::link, jakx::method_34_sky_work::link,
       jakx::method_35_sky_work::link, jakx::method_32_sky_work::link,
       jakx::set_sky_vf23_value::link, jakx::draw_large_polygon::link,
       jakx::clip_polygon_against_positive_hyperplane::link,
       jakx::clip_polygon_against_negative_hyperplane::link}},
     {"shadow-cpu",
      {jakx::shadow_xform_verts::link, jakx::shadow_execute::link,
       jakx::shadow_calc_dual_verts::link, jakx::shadow_scissor_edges::link,
       jakx::shadow_scissor_top::link, jakx::shadow_init_vars::link,
       jakx::shadow_find_facing_single_tris::link, jakx::shadow_find_facing_double_tris::link,
       jakx::shadow_find_single_edges::link, jakx::shadow_find_double_edges::link,
       jakx::shadow_add_verts::link, jakx::shadow_add_facing_single_tris::link,
       jakx::shadow_add_single_edges::link, jakx::shadow_add_double_edges::link,
       jakx::shadow_add_single_tris::link, jakx::shadow_add_double_tris::link}},
     // cloth: jakx-native port — structurally identical to jak3; jakx
     // namespace only. See game/mips2c/jakx_functions/cloth.cpp.
     {"cloth", {jakx::method_21_cloth_system::link}}}};

void LinkedFunctionTable::reg(const std::string& name, u64 (*exec)(void*), u32 stack_size) {
  const auto& it = m_executes.insert({name, {exec, Ptr<u8>()}});
  if (!it.second) {
    lg::error("MIPS2C Function {} is registered multiple times, ignoring later registrations.",
              name);
  }

  // this is short stub that will jump to the appropriate function.
  Ptr<u8> jump_to_asm;
  switch (g_game_version) {
    case GameVersion::Jak1:
      jump_to_asm = Ptr<u8>(::jak1::alloc_heap_object(s7.offset + jak1_symbols::FIX_SYM_GLOBAL_HEAP,
                                                      *(s7 + jak1_symbols::FIX_SYM_FUNCTION_TYPE),
                                                      0x40, UNKNOWN_PP));
      break;
    case GameVersion::Jak2:
      jump_to_asm = Ptr<u8>(::jak2::alloc_heap_object(
          s7.offset + jak2_symbols::FIX_SYM_GLOBAL_HEAP,
          ::jak2::u32_in_fixed_sym(jak2_symbols::FIX_SYM_FUNCTION_TYPE), 0x40, UNKNOWN_PP));
      break;
    case GameVersion::Jak3:
      jump_to_asm = Ptr<u8>(::jak3::alloc_heap_object(
          s7.offset + jak3_symbols::FIX_SYM_GLOBAL_HEAP,
          ::jak3::u32_in_fixed_sym(jak3_symbols::FIX_SYM_FUNCTION_TYPE), 0x40, UNKNOWN_PP));
      break;
    case GameVersion::JakX:
      jump_to_asm = Ptr<u8>(::jakx::alloc_heap_object(
          s7.offset + jakx_symbols::FIX_SYM_GLOBAL_HEAP,
          ::jakx::u32_in_fixed_sym(jakx_symbols::FIX_SYM_FUNCTION_TYPE), 0x40, UNKNOWN_PP));
      break;
    default:
      ASSERT(false);
  }

  it.first->second.goal_trampoline = jump_to_asm;

  u8* ptr = jump_to_asm.c();

  {
    // linux

    // push the function
    u64 addr = (u64)exec;
    *ptr = 0x48;
    ptr++;
    *ptr = 0xb8;
    ptr++;
    memcpy(ptr, &addr, 8);
    ptr += 8;
    *ptr = 0x50;
    ptr++;

    // push the stack size
    addr = stack_size;
    *ptr = 0x48;
    ptr++;
    *ptr = 0xb8;
    ptr++;
    memcpy(ptr, &addr, 8);
    ptr += 8;
    *ptr = 0x50;
    ptr++;

    // call the other function
#ifdef __linux__
    addr = (u64)_mips2c_call_systemv;
#elif defined __APPLE__ && defined __x86_64__
    addr = (u64)_mips2c_call_systemv;
#elif _WIN32
    addr = (u64)_mips2c_call_windows;
#endif

    *ptr = 0x48;
    ptr++;
    *ptr = 0xb8;
    ptr++;
    memcpy(ptr, &addr, 8);
    ptr += 8;

    // jumps to the mips2c call, which will return to the caller of this stub.
    *ptr = 0xff;
    ptr++;
    *ptr = 0xe0;
  }
}

u32 LinkedFunctionTable::get(const std::string& name) {
  auto it = m_executes.find(name);
  if (it == m_executes.end()) {
    ASSERT_NOT_REACHED_MSG(fmt::format("mips2c function {} is unknown", name));
  }
  return it->second.goal_trampoline.offset;
}
}  // namespace Mips2C
