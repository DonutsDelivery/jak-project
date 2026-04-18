#version 410 core

uniform sampler2D tex_T0;
in vec2 tex_coord;
out vec4 color;

void main() {
  color = vec4(texture(tex_T0, tex_coord).rgb, 1.0);
}
