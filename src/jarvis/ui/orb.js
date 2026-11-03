// Jarvis's orb: a liquid sphere (4 Nov, Adhi's choice of three original designs). WebGL, no libraries.
//
//   JarvisOrb.start(canvas)     -> true when WebGL works (else index.html draws the old particle sphere)
//   JarvisOrb.voice(env, step)  Jarvis is about to say a sentence: its loudness every `step` seconds, 0-1
//   JarvisOrb.mic(level)        while you speak: your loudness now, 0-1
//
// The surface is a sphere pushed in and out by 3D noise, drawn by ray marching in a fragment shader. What
// Jarvis is doing (body[data-mode]) sets how it moves: idle breathes slowly; listening draws in, calm, and
// ripples with your voice; thinking swirls; speaking swells and ripples with his own voice. The colour is
// --accent: gold for Jarvis, teal for Friday.
window.JarvisOrb = (function () {
  "use strict";
  const VERT = "attribute vec2 p; void main(){ gl_Position = vec4(p, 0.0, 1.0); }";
  const FRAG = `
precision highp float;
uniform vec2 uRes; uniform float uTime; uniform vec3 uCol;
uniform float uAmp, uFreq, uSpeed, uSwirl, uRadius, uGlow, uLevel, uRipple, uWhite;
float hash(vec3 p) { p = fract(p * 0.3183099 + 0.1); p *= 17.0; return fract(p.x * p.y * p.z * (p.x + p.y + p.z)); }
float noise(vec3 x) {
  vec3 i = floor(x), f = fract(x); f = f * f * (3.0 - 2.0 * f);
  return mix(mix(mix(hash(i), hash(i + vec3(1,0,0)), f.x), mix(hash(i + vec3(0,1,0)), hash(i + vec3(1,1,0)), f.x), f.y),
             mix(mix(hash(i + vec3(0,0,1)), hash(i + vec3(1,0,1)), f.x), mix(hash(i + vec3(0,1,1)), hash(i + vec3(1,1,1)), f.x), f.y), f.z);
}
float fbm(vec3 p) { float a = 0.5, s = 0.0; for (int i = 0; i < 3; i++) { s += a * noise(p); p = p * 2.03 + vec3(1.7, 9.2, 3.1); a *= 0.38; } return s; }
mat2 rot(float a) { float c = cos(a), s = sin(a); return mat2(c, -s, s, c); }
float field(vec3 p) {
  vec3 q = p;
  q.xz = rot(uTime * 0.25 * uSwirl + q.y * 1.4 * uSwirl) * q.xz;              // thinking: the liquid turns
  float n = fbm(q * uFreq + vec3(0.0, uTime * uSpeed, uTime * uSpeed * 0.7));
  float r = length(p);
  float ripple = sin(14.0 * acos(clamp(p.y / max(r, 1e-4), -1.0, 1.0)) - uTime * 7.0) * uRipple;   // rings with the voice
  return r - uRadius - uAmp * (n - 0.5) * 2.0 - 0.025 * ripple;
}
vec3 normalAt(vec3 p) {
  vec2 e = vec2(0.0025, 0.0);
  return normalize(vec3(field(p + e.xyy) - field(p - e.xyy), field(p + e.yxy) - field(p - e.yxy),
                        field(p + e.yyx) - field(p - e.yyx)));
}
void main() {
  vec2 uv = (gl_FragCoord.xy * 2.0 - uRes) / min(uRes.x, uRes.y);
  vec3 ro = vec3(0.0, 0.0, 3.2), rd = normalize(vec3(uv, -2.3));
  float bound = uRadius + uAmp + 0.08;
  float b = dot(ro, rd), c = dot(ro, ro) - bound * bound, h = b * b - c;
  float dmin = length(cross(ro, rd));                                         // the ray's nearest pass to the centre
  // the glow fades to nothing well inside the square, so the canvas's edge never shows (4 Nov)
  float halo = uGlow * exp(-max(dmin - uRadius, 0.0) * 9.0) * 0.55 * (1.0 - smoothstep(0.80, 0.99, length(uv)));
  if (h < 0.0) { gl_FragColor = vec4(uCol * halo, halo); return; }
  float t = -b - sqrt(h), tEnd = -b + sqrt(h);
  bool hit = false; vec3 p;
  for (int i = 0; i < 56; i++) {
    p = ro + rd * t;
    float d = field(p);
    if (d < 0.0015) { hit = true; break; }
    t += d * 0.75;
    if (t > tEnd) break;
  }
  if (!hit) { gl_FragColor = vec4(uCol * halo, halo); return; }
  vec3 n = normalAt(p), v = -rd, L = normalize(vec3(-0.5, 0.7, 0.6));
  float diff = max(dot(n, L), 0.0);
  float spec = pow(max(dot(reflect(-L, n), v), 0.0), 60.0);
  float fres = pow(1.0 - max(dot(n, v), 0.0), 3.0);
  vec3 r = reflect(rd, n);
  vec3 tint = mix(uCol, vec3(1.0), uWhite);
  vec3 env = mix(vec3(0.015, 0.025, 0.045), tint * 0.85, smoothstep(-0.3, 0.9, r.y))
           + vec3(0.9) * pow(max(r.x * 0.5 + 0.5, 0.0), 14.0) * 0.35;
  float facing = max(dot(n, v), 0.0);
  vec3 inner = tint * pow(facing, 2.5) * (0.30 + 0.55 * uLevel);                  // light inside the liquid
  vec3 body = tint * 0.045 + tint * diff * 0.16;
  vec3 col = body + inner + env * (0.12 + 0.88 * fres) + vec3(1.0, 0.97, 0.92) * spec * 0.95
           + tint * fres * 0.75 * uGlow;
  gl_FragColor = vec4(col, 1.0);
}`;
  // How each state moves: amplitude, noise scale, flow speed, swirl, radius, glow, ripple, whiteness
  const LOOK = {
    idle:      { amp: 0.045, freq: 1.6, speed: 0.22, swirl: 0.0, radius: 0.92, glow: 0.75, ripple: 0.0, white: 0.0 },
    listening: { amp: 0.030, freq: 2.2, speed: 0.55, swirl: 0.0, radius: 0.86, glow: 1.15, ripple: 0.0, white: 0.08 },
    thinking:  { amp: 0.070, freq: 1.4, speed: 0.35, swirl: 1.0, radius: 0.90, glow: 0.95, ripple: 0.0, white: 0.12 },
    speaking:  { amp: 0.050, freq: 1.9, speed: 0.80, swirl: 0.0, radius: 0.94, glow: 1.05, ripple: 0.9, white: 0.04 },
    paused:    { amp: 0.015, freq: 1.2, speed: 0.08, swirl: 0.0, radius: 0.88, glow: 0.35, ripple: 0.0, white: 0.0 },
    gesture:   { amp: 0.040, freq: 2.0, speed: 0.40, swirl: 0.0, radius: 0.90, glow: 0.95, ripple: 0.0, white: 0.06 },
  };
  let gl, prog, uni = {}, canvas, cur = Object.assign({}, LOOK.idle), col = [1, 0.7, 0.23];
  let voiceEnv = null, voiceStart = 0, voiceStep = 0.05, micLevel = 0, micAt = 0, level = 0, last = 0;

  function hexToRgb(text) {
    const m = /#?([0-9a-f]{6})/i.exec(text || "");
    if (!m) return [1, 0.7, 0.23];
    const v = parseInt(m[1], 16);
    return [(v >> 16 & 255) / 255, (v >> 8 & 255) / 255, (v & 255) / 255];
  }
  function compile(type, src) {
    const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
    return s;
  }
  function resize() {
    const css = canvas.getBoundingClientRect().width || 480;
    const px = Math.round(Math.min(720, css * Math.min(window.devicePixelRatio || 1, 1.5)));
    if (canvas.width !== px) { canvas.width = px; canvas.height = px; }
  }
  function targetLevel(now) {
    const mode = document.body.dataset.mode;
    if (mode === "speaking" && voiceEnv) {
      const i = Math.floor((now - voiceStart) / 1000 / voiceStep);
      return i >= 0 && i < voiceEnv.length ? voiceEnv[i] : 0;
    }
    if (mode === "listening" && now - micAt < 400) return micLevel;
    return 0;
  }
  function frame(now) {
    const dt = Math.min(0.05, (now - (last || now)) / 1000); last = now;
    resize();
    const mode = document.body.dataset.mode, look = LOOK[mode] || LOOK.idle, k = 1 - Math.exp(-dt * 4);
    for (const key in look) cur[key] += (look[key] - cur[key]) * k;
    const want = targetLevel(now);
    level += (want - level) * (1 - Math.exp(-dt * (want > level ? 25 : 8)));     // fast up, slower down
    const accent = hexToRgb(getComputedStyle(document.body).getPropertyValue("--accent").trim());
    for (let i = 0; i < 3; i++) col[i] += (accent[i] - col[i]) * k;
    const t = now / 1000, breathe = 0.012 * Math.sin(t * 1.3);
    const speakingAmp = mode === "speaking" ? 0.09 * level : 0, listeningAmp = mode === "listening" ? 0.06 * level : 0;
    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT);
    gl.uniform2f(uni.uRes, canvas.width, canvas.height);
    gl.uniform1f(uni.uTime, t);
    gl.uniform3f(uni.uCol, col[0], col[1], col[2]);
    gl.uniform1f(uni.uAmp, cur.amp + speakingAmp + listeningAmp);
    gl.uniform1f(uni.uFreq, cur.freq);
    gl.uniform1f(uni.uSpeed, cur.speed + (mode === "speaking" ? level * 0.5 : 0));
    gl.uniform1f(uni.uSwirl, cur.swirl);
    gl.uniform1f(uni.uRadius, cur.radius + breathe + (mode === "speaking" ? level * 0.05 : 0) - listeningAmp * 0.2);
    gl.uniform1f(uni.uGlow, cur.glow + level * 0.4);
    gl.uniform1f(uni.uLevel, level);
    gl.uniform1f(uni.uRipple, cur.ripple * level);
    gl.uniform1f(uni.uWhite, cur.white + (mode === "thinking" ? 0.08 * (0.5 + 0.5 * Math.sin(t * 2.2)) : 0));
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    requestAnimationFrame(frame);                  // the browser pauses this when the window is hidden
  }
  function start(c) {
    canvas = c;
    try {
      gl = canvas.getContext("webgl", { premultipliedAlpha: true, alpha: true, antialias: false });
      if (!gl) return false;
      prog = gl.createProgram();
      gl.attachShader(prog, compile(gl.VERTEX_SHADER, VERT));
      gl.attachShader(prog, compile(gl.FRAGMENT_SHADER, FRAG));
      gl.linkProgram(prog);
      if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(prog));
      gl.useProgram(prog);
      const buf = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, buf);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);   // one big triangle
      const loc = gl.getAttribLocation(prog, "p");
      gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
      for (const name of ["uRes", "uTime", "uCol", "uAmp", "uFreq", "uSpeed", "uSwirl", "uRadius", "uGlow", "uLevel",
                          "uRipple", "uWhite"]) uni[name] = gl.getUniformLocation(prog, name);
    } catch (err) {
      console.warn("orb: no WebGL, the particle sphere instead", err);
      return false;
    }
    requestAnimationFrame(frame);
    return true;
  }
  return {
    start,
    voice(env, step) { voiceEnv = env || null; voiceStep = step || 0.05; voiceStart = performance.now(); },
    mic(value) { micLevel = Math.max(0, Math.min(1, value || 0)); micAt = performance.now(); },
  };
})();
