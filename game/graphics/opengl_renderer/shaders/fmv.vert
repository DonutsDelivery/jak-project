#version 410 core

layout (location = 0) in vec2 position_in;

out vec2 tex_coord;

void main() {
  gl_Position = vec4(position_in, 0.0, 1.0);
  // flip Y: video frames have (0,0) at top-left, GL textures at bottom-left
  tex_coord = vec2((position_in.x + 1.0) * 0.5, 1.0 - (position_in.y + 1.0) * 0.5);
}
