// Jarvis's visual lessons: the scenes his window can show while he explains (knowledge/lessons.py).
// Every scene is our own tested code: the model only picks a scene and its numbers. The one
// exception, a "sketch", runs the model's code in a sandboxed frame with no network and no access
// to Jarvis. Text from the model is always set as text (never as HTML); formulas go through
// KaTeX with trust off, diagrams through Mermaid in strict mode.
"use strict";
window.JarvisLesson = (function () {
  const LIBS = {
    three: "https://cdn.jsdelivr.net/npm/three@0.149.0/build/three.min.js",
    mermaid: "https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js",
  };
  const loaded = {};
  function load(name) {
    if (!loaded[name]) loaded[name] = new Promise((ok, fail) => {
      const s = document.createElement("script");
      s.src = LIBS[name]; s.onload = ok; s.onerror = () => fail(new Error("couldn't load " + name));
      document.head.append(s);
    });
    return loaded[name];
  }
  const css = n => getComputedStyle(document.body).getPropertyValue(n).trim();
  const C = () => ({ text: css("--text") || "#eaf5ff", muted: css("--muted") || "#8fa7ba", cyan: css("--cyan") || "#4de1ff",
    amber: css("--amber") || "#ffb43b", teal: css("--teal") || "#4ce2c4", red: css("--red") || "#ff766f",
    green: css("--green") || "#64efb7", line: css("--line") || "#12314a", panel: css("--panel") || "#091522",
    bg: css("--bg") || "#03070d" });
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text; return e; };
  const fmt = (v, d = 2) => Number(v).toFixed(d).replace(/\.?0+$/, "");

  // ---- shared: a 2D canvas that fills its box and redraws every frame ----
  function canvas2d(box, draw) {
    const cv = el("canvas"); cv.style.cssText = "width:100%;height:100%;display:block";
    box.append(cv);
    const ctx = cv.getContext("2d");
    let alive = true, last = performance.now(), t = 0;
    function frame(now) {
      if (!alive) return;
      const dt = Math.min(0.05, (now - last) / 1000); last = now; t += dt;
      const r = window.devicePixelRatio || 1, w = cv.clientWidth, h = cv.clientHeight;
      if (cv.width !== Math.round(w * r) || cv.height !== Math.round(h * r)) { cv.width = Math.round(w * r); cv.height = Math.round(h * r); }
      ctx.setTransform(r, 0, 0, r, 0, 0); ctx.clearRect(0, 0, w, h);
      draw(ctx, w, h, dt, t);
      requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
    return { stop() { alive = false; } };
  }
  function readout(box) { const r = el("div", "readout"); box.append(r); return r; }
  function label(ctx, text, x, y, colour, size = 13, align = "left") {
    ctx.fillStyle = colour; ctx.font = `${size}px Segoe UI, system-ui, sans-serif`; ctx.textAlign = align; ctx.fillText(text, x, y);
  }
  function log10Choose(n, k) { let s = 0; for (let i = 1; i <= k; i++) s += Math.log10((n - k + i) / i); return s; }

  // ---- shared: a Three.js scene you can turn by dragging ----
  async function three(box, build) {
    await load("three");
    const T = window.THREE;
    const renderer = new T.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
    box.append(renderer.domElement);
    renderer.domElement.style.cssText = "width:100%;height:100%;display:block;cursor:grab;touch-action:none";
    const scene = new T.Scene(), camera = new T.PerspectiveCamera(40, 1, 0.1, 500);
    scene.add(new T.AmbientLight(0xffffff, 0.55));
    const sun = new T.DirectionalLight(0xffffff, 0.8); sun.position.set(6, 14, 8); scene.add(sun);
    const view = { yaw: 0.7, pitch: 0.7, dist: 30 };
    let drag = null, alive = true, t = 0, last = performance.now(), hovering = false;
    const dom = renderer.domElement;
    if (getComputedStyle(box).position === "static") box.style.position = "relative";
    const tip = el("div", "tip3d"); tip.style.cssText = "position:absolute;pointer-events:none;display:none;background:#03070dee;" +
      "border:1px solid #1c4766;border-radius:6px;padding:4px 8px;font:12px Segoe UI,system-ui,sans-serif;color:#eaf5ff;" +
      "white-space:nowrap;z-index:3";
    box.append(tip);
    const ray = new T.Raycaster(), mouse = new T.Vector2();
    ray.params.Line = { threshold: 0.35 };
    dom.addEventListener("pointerdown", e => { drag = [e.clientX, e.clientY, view.yaw, view.pitch]; dom.setPointerCapture(e.pointerId); });
    dom.addEventListener("pointermove", e => { if (!drag) return; view.yaw = drag[2] - (e.clientX - drag[0]) * 0.01;
      view.pitch = Math.max(-1.4, Math.min(1.45, drag[3] + (e.clientY - drag[1]) * 0.01)); });
    dom.addEventListener("pointerup", () => { drag = null; });
    dom.addEventListener("wheel", e => { e.preventDefault(); view.dist = Math.max(8, Math.min(90, view.dist * (e.deltaY > 0 ? 1.1 : 0.9))); }, { passive: false });
    const api = build(T, scene, view);
    dom.addEventListener("pointermove", e => {
      hovering = true;
      if (drag || !api.pick) { tip.style.display = "none"; return; }
      const r = dom.getBoundingClientRect();
      mouse.set((e.clientX - r.left) / r.width * 2 - 1, -(e.clientY - r.top) / r.height * 2 + 1);
      ray.setFromCamera(mouse, camera);
      const text = api.pick(ray);
      if (!text) { tip.style.display = "none"; return; }
      tip.textContent = text; tip.style.display = "block";
      tip.style.left = Math.min(r.width - tip.offsetWidth - 4, e.clientX - r.left + 14) + "px";
      tip.style.top = Math.min(r.height - 30, e.clientY - r.top + 10) + "px";
    });
    dom.addEventListener("pointerleave", () => { hovering = false; tip.style.display = "none"; });
    function frame(now) {
      if (!alive) return;
      const dt = Math.min(0.05, (now - last) / 1000); last = now; t += dt;
      const w = box.clientWidth || 600, h = box.clientHeight || 400;
      if (dom.width !== Math.round(w * renderer.getPixelRatio())) { renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix(); }
      if (!drag && !hovering && api.spin) view.yaw += dt * api.spin;
      camera.position.set(view.dist * Math.cos(view.pitch) * Math.sin(view.yaw), view.dist * Math.sin(view.pitch),
        view.dist * Math.cos(view.pitch) * Math.cos(view.yaw));
      camera.lookAt(0, 0, 0);
      if (api.tick) api.tick(t, dt);
      renderer.render(scene, camera);
      requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
    return { update: p => api.update && api.update(p), stop() { alive = false; renderer.dispose(); } };
  }

  // ======================= the library =======================
  const SCENES = {};

  SCENES.gas_box = (box, p0) => {
    let p = p0, parts = [], wall = p.wall;
    const out = readout(box);
    function reset() {
      parts = Array.from({ length: p.molecules }, () => {
        const a = Math.random() * 2 * Math.PI;
        return { x: Math.random() * (p.wall ? 0.48 : 0.98) + 0.01, y: Math.random() * 0.96 + 0.02, a, s: 0.6 + Math.random() * 0.8 };
      });
      parts.forEach(q => { q.left = q.x < 0.5; });
    }
    reset();
    const view = canvas2d(box, (ctx, w, h, dt) => {
      const c = C(), speed = 0.22 * Math.sqrt(p.temperature);
      const W = Math.min(w - 20, (h - 50) * 1.6), H = W / 1.6, x0 = (w - W) / 2, y0 = 10;
      ctx.strokeStyle = c.muted; ctx.lineWidth = 2; ctx.strokeRect(x0, y0, W, H);
      if (wall) { ctx.strokeStyle = c.amber; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(x0 + W / 2, y0); ctx.lineTo(x0 + W / 2, y0 + H); ctx.stroke(); }
      let left = 0;
      for (const q of parts) {
        const wasLeft = q.x < 0.5;                     // which side it was on: the wall can't be jumped in one frame
        q.x += Math.cos(q.a) * q.s * speed * dt; q.y += Math.sin(q.a) * q.s * speed * dt * 1.6;
        const hi = wall && wasLeft ? 0.495 : 0.995, lo = wall && !wasLeft ? 0.505 : 0.005;
        if (q.x < lo || q.x > hi) { q.a = Math.PI - q.a; q.x = Math.min(Math.max(q.x, lo), hi); }
        if (q.y < 0.01 || q.y > 0.99) { q.a = -q.a; q.y = Math.min(Math.max(q.y, 0.01), 0.99); }
        if (q.x < 0.5) left++;
        ctx.fillStyle = p.colour_by_side ? (q.left ? c.cyan : c.amber) : c.cyan;
        ctx.beginPath(); ctx.arc(x0 + q.x * W, y0 + q.y * H, Math.max(2.5, W / 160), 0, 7); ctx.fill();
      }
      const n = parts.length, lg = log10Choose(n, left);
      out.textContent = `left ${left} · right ${n - left} · ways to arrange W = C(${n}, ${left}) ≈ 10^${fmt(lg, 1)}  ·  temperature ×${fmt(p.temperature)}`;
    });
    return { update(np) { const rebuild = np.molecules !== p.molecules; p = np; wall = np.wall; if (rebuild) reset(); }, stop: view.stop };
  };

  SCENES.waves_3d = (box, p0) => three(box, (T, scene, view) => {
    let p = p0;
    view.dist = 32; view.pitch = 0.75;
    const N = 110, S = 24, geo = new T.PlaneGeometry(S, S, N, N); geo.rotateX(-Math.PI / 2);
    const colors = new Float32Array(geo.attributes.position.count * 3);
    geo.setAttribute("color", new T.BufferAttribute(colors, 3));
    scene.add(new T.Mesh(geo, new T.MeshStandardMaterial({ vertexColors: true, side: T.DoubleSide, roughness: 0.55 })));
    const dots = [0, 1].map(() => { const m = new T.Mesh(new T.SphereGeometry(0.35, 16, 16), new T.MeshStandardMaterial({ color: 0xffb43b })); scene.add(m); return m; });
    const lo = new T.Color(0x0c447c), hi = new T.Color(0x4de1ff), c = new T.Color();
    let phase = 0;
    return {
      update(np) { p = np; },
      tick(t, dt) {
        phase += dt * 2.2 * p.speed;
        const d = p.sources === 2 ? p.separation / 2 : 0, k = 2 * Math.PI / p.wavelength;
        dots[0].position.set(-d, 0.4, 0); dots[1].position.set(d, 0.4, 0); dots[1].visible = p.sources === 2;
        const pos = geo.attributes.position;
        for (let i = 0; i < pos.count; i++) {
          const x = pos.getX(i), z = pos.getZ(i);
          const r1 = Math.hypot(x + d, z) + 0.6, r2 = Math.hypot(x - d, z) + 0.6;
          let y = Math.sin(k * r1 - phase) / Math.sqrt(r1);
          if (p.sources === 2) y += Math.sin(k * r2 - phase) / Math.sqrt(r2);
          y *= 1.6; pos.setY(i, y);
          c.copy(lo).lerp(hi, Math.min(1, Math.max(0, (y + 1.6) / 3.2)));
          colors[3 * i] = c.r; colors[3 * i + 1] = c.g; colors[3 * i + 2] = c.b;
        }
        pos.needsUpdate = true; geo.attributes.color.needsUpdate = true; geo.computeVertexNormals();
      },
    };
  });

  SCENES.string_wave = (box, p0) => {
    let p = p0; const out = readout(box);
    const v = canvas2d(box, (ctx, w, h, dt, t) => {
      const c = C(), L = w - 80, x0 = 40, mid = h / 2 - 10, A = Math.min(h * 0.3, 110), n = p.harmonic, om = 2.4;
      ctx.strokeStyle = c.line; ctx.beginPath(); ctx.moveTo(x0, mid); ctx.lineTo(x0 + L, mid); ctx.stroke();
      ctx.fillStyle = c.muted; ctx.fillRect(x0 - 6, mid - 30, 6, 60); ctx.fillRect(x0 + L, mid - 30, 6, 60);
      ctx.strokeStyle = c.cyan; ctx.lineWidth = 3; ctx.beginPath();
      for (let i = 0; i <= 300; i++) {
        const s = i / 300, y = p.standing ? A * Math.sin(n * Math.PI * s) * Math.cos(om * t) : A * Math.sin(n * Math.PI * s - om * t);
        const X = x0 + s * L, Y = mid - y; i ? ctx.lineTo(X, Y) : ctx.moveTo(X, Y);
      }
      ctx.stroke();
      if (p.standing) {
        ctx.globalAlpha = 0.25; ctx.strokeStyle = c.cyan; ctx.lineWidth = 1;
        for (const sign of [1, -1]) { ctx.beginPath(); for (let i = 0; i <= 200; i++) { const s = i / 200; const Y = mid - sign * A * Math.sin(n * Math.PI * s); i ? ctx.lineTo(x0 + s * L, Y) : ctx.moveTo(x0 + s * L, Y); } ctx.stroke(); }
        ctx.globalAlpha = 1;
        if (p.show_nodes) for (let m = 0; m <= n; m++) { ctx.fillStyle = c.amber; ctx.beginPath(); ctx.arc(x0 + m / n * L, mid, 5, 0, 7); ctx.fill(); }
        if (p.show_nodes) for (let m = 0; m < n; m++) label(ctx, "A", x0 + (m + 0.5) / n * L, mid + A + 22, c.teal, 12, "center");
      }
      out.textContent = p.standing ? `harmonic ${n}: ${n + 1} nodes (orange), ${n} antinodes · wavelength = 2L/${n} · frequency = ${n} × fundamental`
        : `travelling wave · wavelength = 2L/${n}`;
    });
    return { update(np) { p = np; }, stop: v.stop };
  };

  SCENES.pendulum = (box, p0) => {
    let p = p0, th = p0.amplitude * Math.PI / 180, om = 0; const out = readout(box);
    const v = canvas2d(box, (ctx, w, h, dt) => {
      const c = C(), steps = 8, g = p.gravity, L = p.length;
      for (let i = 0; i < steps; i++) { const a = -(g / L) * Math.sin(th) - 2 * p.damping * om; om += a * dt / steps; th += om * dt / steps; }
      const scale = (h - 90) / Math.max(1.6, L * 1.1), px = w * (p.show_energy ? 0.42 : 0.5), py = 30, len = L * scale;
      const bx = px + len * Math.sin(th), by = py + len * Math.cos(th);
      ctx.strokeStyle = c.muted; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(px - 40, py); ctx.lineTo(px + 40, py); ctx.stroke();
      ctx.setLineDash([4, 6]); ctx.strokeStyle = c.line; ctx.beginPath(); ctx.moveTo(px, py); ctx.lineTo(px, py + len + 20); ctx.stroke(); ctx.setLineDash([]);
      ctx.strokeStyle = c.text; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(px, py); ctx.lineTo(bx, by); ctx.stroke();
      ctx.fillStyle = c.amber; ctx.beginPath(); ctx.arc(bx, by, 14, 0, 7); ctx.fill();
      const m = 1, ke = 0.5 * m * (L * om) ** 2, pe = m * g * L * (1 - Math.cos(th)), tot = Math.max(1e-9, ke + pe),
        top = m * g * L * (1 - Math.cos(p.amplitude * Math.PI / 180));
      if (p.show_energy) {
        const bx0 = w * 0.78, bh = h - 110, scaleE = bh / Math.max(top, tot, 1e-9);
        [["kinetic", ke, c.cyan], ["potential", pe, c.amber]].forEach(([name, e, col], i) => {
          const x = bx0 + i * 46; ctx.fillStyle = col; ctx.fillRect(x, 40 + bh - e * scaleE, 30, e * scaleE);
          ctx.strokeStyle = c.line; ctx.strokeRect(x, 40, 30, bh); label(ctx, name, x + 15, 40 + bh + 18, c.muted, 11, "center");
        });
      }
      const T0 = 2 * Math.PI * Math.sqrt(L / g);
      out.textContent = `length ${fmt(L)} m · g ${fmt(g)} m/s² · small-angle period T = 2π√(L/g) = ${fmt(T0)} s · angle ${fmt(th * 180 / Math.PI, 0)}°`;
    });
    return { update(np) { const restart = np.amplitude !== p.amplitude || np.length !== p.length; p = np; if (restart) { th = np.amplitude * Math.PI / 180; om = 0; } }, stop: v.stop };
  };

  SCENES.projectile = (box, p0) => {
    let p = p0, path = [], t = 0, s = null, done = 0; const out = readout(box);
    function fly() {
      const a = p.angle * Math.PI / 180; let x = 0, y = 0, vx = p.speed * Math.cos(a), vy = p.speed * Math.sin(a), tt = 0, top = 0;
      const pts = [[0, 0, vx, vy]];
      while (y >= 0 && tt < 60) { const sp = Math.hypot(vx, vy); vx -= p.drag * sp * vx * 0.005; vy -= (p.gravity + p.drag * sp * vy) * 0.005;
        x += vx * 0.005; y += vy * 0.005; tt += 0.005; top = Math.max(top, y); if (pts.length < 20000) pts.push([x, y, vx, vy]); }
      return { pts, range: x, top, time: tt };
    }
    function restart() { s = fly(); path = []; t = 0; done = 0; }
    restart();
    const v = canvas2d(box, (ctx, w, h, dt) => {
      const c = C(), m = 40, sx = (w - 2 * m) / Math.max(s.range, 1), sy = (h - 2 * m - 10) / Math.max(s.top, 1), sc = Math.min(sx, sy, 60);
      const X = x => m + x * sc, Y = y => h - m - y * sc;
      ctx.strokeStyle = c.line; ctx.beginPath(); ctx.moveTo(m, h - m); ctx.lineTo(w - m, h - m); ctx.stroke();
      t += dt; const i = Math.min(s.pts.length - 1, Math.floor(t / 0.005));
      ctx.strokeStyle = c.cyan; ctx.lineWidth = 2; ctx.beginPath(); for (let k = 0; k <= i; k += 4) { const q = s.pts[k]; k ? ctx.lineTo(X(q[0]), Y(q[1])) : ctx.moveTo(X(q[0]), Y(q[1])); } ctx.stroke();
      const q = s.pts[i];
      ctx.fillStyle = c.amber; ctx.beginPath(); ctx.arc(X(q[0]), Y(q[1]), 7, 0, 7); ctx.fill();
      if (p.show_vectors) {
        const k = 1.2;
        const arrow = (dx, dy, col) => { ctx.strokeStyle = col; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(X(q[0]), Y(q[1])); ctx.lineTo(X(q[0]) + dx * k, Y(q[1]) - dy * k); ctx.stroke(); };
        arrow(q[2], 0, c.teal); arrow(0, q[3], c.red); arrow(q[2], q[3], c.text);
      }
      if (i === s.pts.length - 1) { done += dt; if (done > 2) restart(); }
      out.textContent = `speed ${fmt(p.speed)} m/s at ${fmt(p.angle, 0)}° · range ${fmt(s.range, 1)} m · highest ${fmt(s.top, 1)} m · flight ${fmt(s.time, 2)} s` +
        (p.drag ? " · with air resistance" : " · no air resistance") + (p.show_vectors ? " · arrows: horizontal (teal) and vertical (red) velocity" : "");
    });
    return { update(np) { p = np; restart(); }, stop: v.stop };
  };

  SCENES.rc_circuit = (box, p0) => {
    let p = p0, t = 0; const out = readout(box);
    const v = canvas2d(box, (ctx, w, h, dt) => {
      const c = C(), tau = p.resistance_kohm * 1e3 * p.capacitance_uf * 1e-6, gx = 60, gy = 30, gw = w - 100, gh = h - 100;
      t += dt / 6; if (t > 1.05) t = 0;
      ctx.strokeStyle = c.line; ctx.beginPath(); ctx.moveTo(gx, gy); ctx.lineTo(gx, gy + gh); ctx.lineTo(gx + gw, gy + gh); ctx.stroke();
      for (let k = 1; k <= 5; k++) { const x = gx + k / 5 * gw; ctx.setLineDash([3, 5]); ctx.beginPath(); ctx.moveTo(x, gy); ctx.lineTo(x, gy + gh); ctx.stroke(); ctx.setLineDash([]);
        label(ctx, `${k}τ`, x, gy + gh + 18, c.muted, 12, "center"); }
      label(ctx, `${fmt(p.voltage)} V`, gx - 8, gy + 5, c.muted, 12, "right"); label(ctx, "0", gx - 8, gy + gh, c.muted, 12, "right");
      const Vc = s => p.discharge ? Math.exp(-5 * s) : 1 - Math.exp(-5 * s);
      ctx.strokeStyle = c.cyan; ctx.lineWidth = 3; ctx.beginPath();
      for (let i = 0; i <= 300; i++) { const s = i / 300; const X = gx + s * gw, Y = gy + gh - Vc(s) * gh; i ? ctx.lineTo(X, Y) : ctx.moveTo(X, Y); } ctx.stroke();
      const s = Math.min(1, t); ctx.fillStyle = c.amber; ctx.beginPath(); ctx.arc(gx + s * gw, gy + gh - Vc(s) * gh, 7, 0, 7); ctx.fill();
      const at1 = p.discharge ? "37%" : "63%";
      label(ctx, `after one τ: ${at1} of the way`, gx + gw / 5 + 10, gy + gh - (p.discharge ? Math.exp(-1) : 1 - Math.exp(-1)) * gh + (p.discharge ? -12 : 22), c.teal, 12);
      out.textContent = `capacitor voltage while ${p.discharge ? "discharging" : "charging"} · R = ${fmt(p.resistance_kohm)} kΩ, C = ${fmt(p.capacitance_uf)} µF · τ = RC = ${tau >= 1 ? fmt(tau, 2) + " s" : fmt(tau * 1000, 1) + " ms"} · ` +
        (p.discharge ? "V = V₀ e^(−t/RC)" : "V = V₀ (1 − e^(−t/RC))");
    });
    return { update(np) { p = np; t = 0; }, stop: v.stop };
  };

  SCENES.fourier = (box, p0) => {
    let p = p0; const out = readout(box);
    const target = x => { const u = ((x % (2 * Math.PI)) + 2 * Math.PI) % (2 * Math.PI);
      if (p.shape === "square") return u < Math.PI ? 1 : -1;
      if (p.shape === "sawtooth") return u < Math.PI ? u / Math.PI : u / Math.PI - 2;
      return u < Math.PI ? 1 - 2 * u / Math.PI : -1 + 2 * (u - Math.PI) / Math.PI; };
    const term = (k, x) => {
      if (p.shape === "square") return k % 2 ? 4 / Math.PI * Math.sin(k * x) / k : 0;
      if (p.shape === "sawtooth") return 2 / Math.PI * (k % 2 ? 1 : -1) * Math.sin(k * x) / k;
      return k % 2 ? 8 / (Math.PI ** 2) * ((k - 1) / 2 % 2 ? -1 : 1) * Math.sin(k * x) / (k * k) : 0; };
    const v = canvas2d(box, (ctx, w, h, dt, t) => {
      const c = C(), m = 30, mid = h / 2 - 10, A = (h - 100) / 2.6, X = x => m + (x + Math.PI) / (4 * Math.PI) * (w - 2 * m);
      ctx.strokeStyle = c.line; ctx.beginPath(); ctx.moveTo(m, mid); ctx.lineTo(w - m, mid); ctx.stroke();
      const shown = Math.max(1, Math.min(p.terms, Math.floor(t * 3) + 1));
      const drawFn = (f, col, lw, alpha) => { ctx.globalAlpha = alpha; ctx.strokeStyle = col; ctx.lineWidth = lw; ctx.beginPath();
        for (let i = 0; i <= 700; i++) { const x = -Math.PI + i / 700 * 4 * Math.PI, Y = mid - f(x) * A; i ? ctx.lineTo(X(x), Y) : ctx.moveTo(X(x), Y); } ctx.stroke(); ctx.globalAlpha = 1; };
      drawFn(target, c.muted, 1.5, 0.6);
      let k = shown; while (k > 1 && term(k, 1.0) === 0) k--;
      drawFn(x => term(k, x), c.amber, 1.5, 0.7);
      drawFn(x => { let s = 0; for (let j = 1; j <= shown; j++) s += term(j, x); return s; }, c.cyan, 2.5, 1);
      const used = Array.from({ length: shown }, (_, j) => j + 1).filter(j => term(j, 1.0) !== 0).length;
      out.textContent = `${p.shape} wave (grey) · sum of the first ${used} sine terms (cyan) · the newest term (orange)` +
        (p.shape === "square" ? " · the overshoot at each jump stays about 9%: the Gibbs effect" : "");
    });
    return { update(np) { p = np; }, stop: v.stop };
  };

  SCENES.field_3d = (box, p0) => three(box, (T, scene, view) => {
    let p = p0, group = null; view.dist = 26; view.pitch = 0.5;
    function build() {
      if (group) scene.remove(group);
      group = new T.Group(); scene.add(group);
      const d = p.separation / 2;
      const charges = p.arrangement === "single" ? [[0, 0, 0, 1]] : p.arrangement === "dipole" ? [[-d, 0, 0, 1], [d, 0, 0, -1]] : [[-d, 0, 0, 1], [d, 0, 0, 1]];
      for (const [x, y, z, q] of charges) {
        const m = new T.Mesh(new T.SphereGeometry(0.55, 24, 24), new T.MeshStandardMaterial({ color: q > 0 ? 0xff766f : 0x4de1ff }));
        m.position.set(x, y, z); group.add(m);
      }
      const lo = new T.Color(0x185fa5), hi = new T.Color(0xffb43b), col = new T.Color();
      for (let x = -8; x <= 8; x += 1.6) for (let y = -4.8; y <= 4.8; y += 1.6) for (let z = -4.8; z <= 4.8; z += 1.6) {
        let ex = 0, ey = 0, ez = 0, near = false;
        for (const [cx, cy, cz, q] of charges) { const rx = x - cx, ry = y - cy, rz = z - cz, r = Math.hypot(rx, ry, rz);
          if (r < 0.9) near = true; const k = q / (r ** 3); ex += k * rx; ey += k * ry; ez += k * rz; }
        const mag = Math.hypot(ex, ey, ez); if (near || mag < 1e-6) continue;
        const s = Math.min(1, Math.max(0, (Math.log10(mag) + 2.2) / 2.2));
        col.copy(lo).lerp(hi, s);
        group.add(new T.ArrowHelper(new T.Vector3(ex / mag, ey / mag, ez / mag), new T.Vector3(x, y, z), 0.5 + 0.8 * s, col.getHex(), 0.3, 0.2));
      }
    }
    build();
    return { spin: 0.12, update(np) { p = np; build(); } };
  });

  SCENES.orbit = (box, p0) => {
    let p = p0, M = 0; const out = readout(box);
    const v = canvas2d(box, (ctx, w, h, dt) => {
      const c = C(), e = p.eccentricity, a = Math.min(w * 0.38, (h - 60) / 2 / Math.sqrt(1 - e * e) * 0.95), b = a * Math.sqrt(1 - e * e);
      const cx = w / 2 - a * e * 0.5, cy = h / 2 - 15, fx = cx + a * e;   // the Sun at +ae: M = E - e sin E sweeps equal areas about it
      M += dt * 0.9; if (M > 2 * Math.PI) M -= 2 * Math.PI;
      const ecc = mean => { let E = mean; for (let i = 0; i < 12; i++) E -= (E - e * Math.sin(E) - mean) / (1 - e * Math.cos(E)); return E; };
      const pos = mean => { const E = ecc(mean); return [cx + a * Math.cos(E), cy + b * Math.sin(E)]; };
      if (p.show_areas) {
        for (const [m0, col] of [[-0.25, c.amber], [Math.PI - 0.25, c.cyan]]) {     // near the Sun, and far from it
          ctx.globalAlpha = 0.3; ctx.fillStyle = col; ctx.beginPath(); ctx.moveTo(fx, cy);
          for (let k = 0; k <= 30; k++) { const q = pos(m0 + 0.5 * k / 30); ctx.lineTo(q[0], q[1]); } ctx.closePath(); ctx.fill(); ctx.globalAlpha = 1;
        }
      }
      ctx.strokeStyle = c.muted; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.ellipse(cx, cy, a, b, 0, 0, 7); ctx.stroke();
      ctx.fillStyle = c.amber; ctx.beginPath(); ctx.arc(fx, cy, 12, 0, 7); ctx.fill();
      const q = pos(M); ctx.fillStyle = c.cyan; ctx.beginPath(); ctx.arc(q[0], q[1], 7, 0, 7); ctx.fill();
      ctx.strokeStyle = c.line; ctx.beginPath(); ctx.moveTo(fx, cy); ctx.lineTo(q[0], q[1]); ctx.stroke();
      out.textContent = `eccentricity ${fmt(e)} · the Sun at one focus · fastest at the closest point: ${fmt((1 + e) / (1 - e), 2)}× the speed at the farthest` +
        (p.show_areas ? " · the two shaded areas are swept in equal times (Kepler's second law)" : "");
    });
    return { update(np) { p = np; }, stop: v.stop };
  };

  SCENES.lens = (box, p0) => {
    let p = p0; const out = readout(box);
    const v = canvas2d(box, (ctx, w, h) => {
      const c = C(), f = p.converging ? p.focal_length : -p.focal_length, u = p.object_distance;
      const vimg = Math.abs(1 / f - 1 / u) < 1e-6 ? Infinity : 1 / (1 / f - 1 / u), mag = -vimg / u;
      const span = Math.max(u, Math.abs(f) * 1.6, isFinite(vimg) ? Math.min(Math.abs(vimg), 80) : 0) * 1.15;
      const cx = w / 2, cy = h / 2 - 10, sc = (w / 2 - 30) / span, ho = 3, X = x => cx + x * sc, Y = y => cy - y * sc * 0.9 * Math.min(1, 40 / span) * span / 40;
      const ys = Math.min((h / 2 - 40) / Math.max(ho, Math.min(Math.abs(mag * ho), 12)), sc), YY = y => cy - y * ys;
      ctx.strokeStyle = c.line; ctx.beginPath(); ctx.moveTo(10, cy); ctx.lineTo(w - 10, cy); ctx.stroke();
      ctx.strokeStyle = c.cyan; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(cx, cy - h * 0.38); ctx.lineTo(cx, cy + h * 0.38); ctx.stroke();
      for (const s of [-1, 1]) { ctx.fillStyle = c.muted; ctx.beginPath(); ctx.arc(X(s * Math.abs(f)), cy, 4, 0, 7); ctx.fill(); label(ctx, "F", X(s * Math.abs(f)), cy + 18, c.muted, 12, "center"); }
      const arrow = (x, y, col, dashed) => { ctx.setLineDash(dashed ? [6, 5] : []); ctx.strokeStyle = col; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(X(x), cy); ctx.lineTo(X(x), YY(y)); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(X(x) - 6, YY(y) + Math.sign(y) * 10); ctx.lineTo(X(x), YY(y)); ctx.lineTo(X(x) + 6, YY(y) + Math.sign(y) * 10); ctx.stroke(); ctx.setLineDash([]); };
      arrow(-u, ho, c.amber, false);
      const tip = [-u, ho];
      const ray = (pts, col, dashed) => { ctx.setLineDash(dashed ? [5, 5] : []); ctx.strokeStyle = col; ctx.lineWidth = 1.5; ctx.beginPath();
        pts.forEach((q, i) => i ? ctx.lineTo(X(q[0]), YY(q[1])) : ctx.moveTo(X(q[0]), YY(q[1]))); ctx.stroke(); ctx.setLineDash([]); };
      const far = span * 1.2;
      // 1: parallel to the axis, then through (or away from) the far focus
      const slope1 = -ho / f; ray([tip, [0, ho], [far, ho + slope1 * far]], c.teal);
      // 2: through the centre, undeviated
      ray([tip, [far, -ho / u * far]], c.teal);
      if (isFinite(vimg)) {
        const yi = mag * ho;
        if (vimg < 0) { ray([[0, ho], [vimg, yi]], c.teal, true); ray([[0, 0], [vimg, yi]], c.teal, true); }
        arrow(vimg, yi, c.red, vimg < 0);
      }
      const kind = !isFinite(vimg) ? "no image (object at the focus: the rays leave parallel)" :
        `${vimg > 0 ? "real, inverted" : "virtual, upright"} image at ${fmt(Math.abs(vimg), 1)} ${vimg > 0 ? "on the other side" : "on the same side"}, magnification ${fmt(mag, 2)}`;
      out.textContent = `${p.converging ? "converging" : "diverging"} lens, f = ${fmt(Math.abs(f))} · object at ${fmt(u)} · 1/f = 1/u + 1/v · ${kind}`;
    });
    return { update(np) { p = np; }, stop: v.stop };
  };

  // ---- maths from SymPy: a 3D surface and graphs ----
  const surface = (box, vis) => three(box, (T, scene, view) => {
    const z = vis.z, n = z.length, m = z[0].length, flat = z.flat().filter(v => v !== null);
    const zmin = Math.min(...flat), zmax = Math.max(...flat), zs = 6 / Math.max(1e-9, zmax - zmin), S = 16;
    const geo = new T.PlaneGeometry(S, S, m - 1, n - 1); geo.rotateX(-Math.PI / 2);
    const pos = geo.attributes.position, colors = new Float32Array(pos.count * 3), lo = new T.Color(0x0c447c), hi = new T.Color(0xffb43b), c = new T.Color();
    for (let i = 0; i < pos.count; i++) {
      const row = Math.floor(i / m), col = i % m, v = z[n - 1 - row][col];
      const y = v === null ? 0 : (v - (zmin + zmax) / 2) * zs; pos.setY(i, y);
      c.copy(lo).lerp(hi, v === null ? 0 : (v - zmin) / Math.max(1e-9, zmax - zmin));
      colors[3 * i] = c.r; colors[3 * i + 1] = c.g; colors[3 * i + 2] = c.b;
    }
    geo.setAttribute("color", new T.BufferAttribute(colors, 3)); geo.computeVertexNormals();
    const mesh = new T.Mesh(geo, new T.MeshStandardMaterial({ vertexColors: true, side: T.DoubleSide, roughness: 0.6 }));
    scene.add(mesh);
    const xr = Array.isArray(vis.x) && vis.x.length === 2 ? vis.x : [0, m - 1], yr = Array.isArray(vis.y) && vis.y.length === 2 ? vis.y : [0, n - 1];
    const f5 = v => String(+Number(v).toPrecision(5)), here = new T.Vector3();
    const pick = ray => {
      const hit = ray.intersectObject(mesh)[0]; if (!hit || !hit.face) return null;
      let best = hit.face.a, bd = Infinity;
      for (const i of [hit.face.a, hit.face.b, hit.face.c]) { const d = hit.point.distanceTo(here.fromBufferAttribute(pos, i)); if (d < bd) { bd = d; best = i; } }
      const row = Math.floor(best / m), col = best % m, r = n - 1 - row, v = z[r][col];
      if (v === null || v === undefined) return null;
      return `x = ${f5(xr[0] + col / Math.max(1, m - 1) * (xr[1] - xr[0]))},  y = ${f5(yr[0] + r / Math.max(1, n - 1) * (yr[1] - yr[0]))},  z = ${f5(v)}`;
    };
    const wire = new T.LineSegments(new T.WireframeGeometry(geo), new T.LineBasicMaterial({ color: 0x12314a, transparent: true, opacity: 0.35 }));
    scene.add(wire);
    scene.add(new T.AxesHelper(10));
    view.dist = 30; view.pitch = 0.6;
    return { spin: 0.15, pick };
  });

  const COLOURS = () => { const c = C(); return [c.cyan, c.amber, c.green]; };
  function plot(box, vis) {
    const curves = vis.curves || [];
    const pts = curves.flatMap(cv => cv.points.filter(q => q[1] !== null));
    const ys = pts.map(q => q[1]).sort((a, b) => a - b);
    let y0 = ys[Math.floor(ys.length * 0.02)] ?? -1, y1 = ys[Math.ceil(ys.length * 0.98) - 1] ?? 1; if (y0 === y1) { y0 -= 1; y1 += 1; }
    const pad = (y1 - y0) * 0.08; y0 -= pad; y1 += pad;
    const x0 = vis.from, x1 = vis.to, legend = el("div", "legend");
    curves.forEach((cv, i) => { const s = el("span"); const sw = el("i"); sw.style.background = COLOURS()[i % 3]; s.append(sw, document.createTextNode(cv.label)); legend.append(s); });
    box.append(legend);
    let mouse = null;
    const api = canvas2d(box, (ctx, w, h) => {
      const c = C(), L = 50, R = 16, T = 16, B = 40, X = x => L + (x - x0) / (x1 - x0) * (w - L - R), Y = y => T + (y1 - y) / (y1 - y0) * (h - T - B);
      const ticks = (a, b) => { const st = Math.pow(10, Math.floor(Math.log10((b - a) / 5 || 1))); const k = [1, 2, 5, 10].find(m => (b - a) / (st * m) <= 8) * st; const o = []; for (let v = Math.ceil(a / k) * k; v <= b + 1e-9; v += k) o.push(+v.toFixed(10)); return o; };
      ctx.strokeStyle = c.line; ctx.lineWidth = 1;
      for (const v of ticks(x0, x1)) { ctx.beginPath(); ctx.moveTo(X(v), T); ctx.lineTo(X(v), h - B); ctx.stroke(); label(ctx, String(v), X(v), h - B + 16, c.muted, 11, "center"); }
      for (const v of ticks(y0, y1)) { ctx.beginPath(); ctx.moveTo(L, Y(v)); ctx.lineTo(w - R, Y(v)); ctx.stroke(); label(ctx, String(v), L - 6, Y(v) + 4, c.muted, 11, "right"); }
      curves.forEach((cv, i) => { ctx.strokeStyle = COLOURS()[i % 3]; ctx.lineWidth = 2.5; ctx.beginPath(); let pen = false;
        for (const [x, y] of cv.points) { if (y === null || y < y0 - (y1 - y0) || y > y1 + (y1 - y0)) { pen = false; continue; } pen ? ctx.lineTo(X(x), Y(y)) : ctx.moveTo(X(x), Y(y)); pen = true; } ctx.stroke(); });
      if (mouse) {                                   // the point nearest the mouse, with its values
        let best = null, bd = 45 * 45;
        curves.forEach(cv => cv.points.forEach(([x, y]) => { if (y === null || y < y0 || y > y1) return;
          const d = (X(x) - mouse[0]) ** 2 + (Y(y) - mouse[1]) ** 2; if (d < bd) { bd = d; best = [x, y, cv.label]; } }));
        if (best) {
          const px = X(best[0]), py = Y(best[1]), f5 = v => String(+Number(v).toPrecision(5));
          const text = (curves.length > 1 ? best[2] + ":  " : "") + `x = ${f5(best[0])},  y = ${f5(best[1])}`;
          ctx.setLineDash([3, 4]); ctx.strokeStyle = c.muted; ctx.beginPath(); ctx.moveTo(px, T); ctx.lineTo(px, h - B); ctx.stroke(); ctx.setLineDash([]);
          ctx.strokeStyle = c.text; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(px, py, 5, 0, 7); ctx.stroke();
          ctx.font = "13px Segoe UI, system-ui, sans-serif"; const tw = ctx.measureText(text).width + 16;
          const bx = px + 12 + tw > w ? px - tw - 12 : px + 12, by = py - 32 < 0 ? py + 12 : py - 32;
          ctx.fillStyle = "#03070dee"; ctx.fillRect(bx, by, tw, 24); ctx.strokeStyle = "#1c4766"; ctx.strokeRect(bx, by, tw, 24);
          label(ctx, text, bx + 8, by + 16, c.text, 13);
        }
      }
    });
    const cv = box.querySelector("canvas");
    cv.addEventListener("mousemove", e => { const r = cv.getBoundingClientRect(); mouse = [e.clientX - r.left, e.clientY - r.top]; });
    cv.addEventListener("mouseleave", () => { mouse = null; });
    return api;
  }

  // ---- diagrams, pictures, formulas, the model's own sketch ----
  let mermaidReady = null, uid = 0;
  async function diagram(box, vis) {
    const holder = el("div", "diagram"); box.append(holder);
    try {
      await load("mermaid");
      if (!mermaidReady) { window.mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: "dark" }); mermaidReady = true; }
      const { svg } = await window.mermaid.render("jarvis-diagram-" + (++uid), vis.mermaid);
      holder.innerHTML = svg;            // Mermaid in strict mode returns sanitised SVG
    } catch (err) { holder.append(el("pre", "raw", vis.mermaid)); }
    return { stop() {} };
  }
  function image(box, vis) {
    const fig = el("figure", "picture");
    if (/^https:\/\/upload\.wikimedia\.org\//.test(vis.url || "")) {
      const img = el("img"); img.src = vis.url; img.alt = vis.title || ""; fig.append(img);
    }
    const cap = el("figcaption"); const a = el("a", "", vis.credit || "Wikipedia");
    if (/^https?:\/\//.test(vis.page || "")) { a.href = vis.page; a.target = "_blank"; a.rel = "noopener"; }
    cap.append(a); fig.append(cap); box.append(fig);
    return { stop() {} };
  }
  function formula(box, latex, big) {
    const f = el("div", big ? "formula big" : "formula");
    if (window.katex) { try { window.katex.render(latex, f, { displayMode: true, throwOnError: false, trust: false }); } catch (e) { f.textContent = latex; } }
    else f.textContent = latex;
    box.append(f); return f;
  }
  const SANDBOX_CSP = "default-src 'none'; script-src 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'unsafe-inline'; img-src data: blob:";
  function sketch(box, vis, onError) {
    const note = el("div", "sketchnote", "A sketch drawn by the model, not a tested scene: it can be wrong.");
    if (!vis.code) { box.append(el("div", "empty", "The model couldn't draw this one.")); return { stop() {} }; }
    const frame = el("iframe"); frame.setAttribute("sandbox", "allow-scripts"); frame.title = "the model's sketch";
    frame.style.cssText = "width:100%;height:calc(100% - 24px);border:0;background:#03070d";
    frame.srcdoc = `<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="${SANDBOX_CSP}">` +
      `<style>html,body{margin:0;height:100%;background:#03070d;color:#eaf5ff;font-family:sans-serif;overflow:hidden}</style>` +
      `<script>window.onerror=function(m){parent.postMessage({sketchError:String(m).slice(0,300)},"*")};<\/script>` +
      `<script src="${LIBS.three}"><\/script></head><body>${vis.code}</body></html>`;
    const listen = e => { if (e.source === frame.contentWindow && e.data && e.data.sketchError) onError(String(e.data.sketchError)); };
    window.addEventListener("message", listen);
    box.append(frame, note);
    return { stop() { window.removeEventListener("message", listen); } };
  }

  // ======================= the lesson player =======================
  let lesson = null, current = null, shownIndex = -1, stage = null, formulaBox = null, onSketchError = () => {};
  function effective(i) { for (let k = i; k >= 0; k--) if (lesson.steps[k].visual) return { visual: lesson.steps[k].visual, from: k }; return { visual: null, from: -1 }; }
  async function show(i) {
    if (!lesson || !stage) return;
    shownIndex = i;
    const { visual, from } = effective(i);
    const step = lesson.steps[i];
    formulaBox.textContent = ""; if (step.formula) formula(formulaBox, step.formula, false);
    if (current && visual && current.visual === visual) return;                   // the same visual: keep it running
    if (current && visual && visual.kind === "scene" && current.visual.kind === "scene" && current.visual.name === visual.name && current.api) {
      current.api.update(visual.params); current.visual = visual; return;          // the same scene, new numbers: change it in place
    }
    if (current && current.api && current.api.stop) current.api.stop();
    stage.textContent = ""; current = null;
    if (!visual) { if (!step.formula) stage.append(el("div", "empty", "")); return; }
    const box = el("div", "scenebox"); stage.append(box);
    let api;
    try {
      if (visual.kind === "scene" && SCENES[visual.name]) api = await SCENES[visual.name](box, visual.params);
      else if (visual.kind === "plot") api = plot(box, visual);
      else if (visual.kind === "surface") api = await surface(box, visual);
      else if (visual.kind === "diagram") api = await diagram(box, visual);
      else if (visual.kind === "image") api = image(box, visual);
      else if (visual.kind === "formula") { formula(box, visual.latex, true); api = { stop() {} }; }
      else if (visual.kind === "sketch") api = sketch(box, visual, msg => onSketchError(from, msg));
      else if (visual.kind === "pview" && window.JarvisProblem) api = window.JarvisProblem.drawView(box, visual.data);
    } catch (err) { box.textContent = ""; box.append(el("div", "empty", "This picture couldn't be drawn (" + err.message + ").")); }
    if (shownIndex !== i) { if (api && api.stop) api.stop(); return; }            // moved on while it loaded
    current = { visual, api };
  }
  const THREE_SCENES = ["waves_3d", "field_3d"];
  function start(data, parts) {
    stop(); lesson = data; stage = parts.stage; formulaBox = parts.formula; onSketchError = parts.onSketchError || (() => {});
    const kinds = lesson.steps.map(s => s.visual).filter(Boolean);           // start the downloads now, not at the step
    if (kinds.some(v => v.kind === "surface" || (v.kind === "scene" && THREE_SCENES.includes(v.name)))) load("three").catch(() => {});
    if (kinds.some(v => v.kind === "diagram")) load("mermaid").catch(() => {});
    stage.textContent = ""; formulaBox.textContent = "";
  }
  function patch(index, code) {                                                     // the model fixed its sketch
    if (!lesson || !lesson.steps[index] || !lesson.steps[index].visual) return;
    lesson.steps[index].visual = Object.assign({}, lesson.steps[index].visual, { code });
    if (current && effective(shownIndex).from === index) { if (current.api && current.api.stop) current.api.stop(); current = null; show(shownIndex); }
  }
  function stop() { if (current && current.api && current.api.stop) current.api.stop(); current = null; lesson = null; shownIndex = -1; }
  // A 3D surface anywhere in the window (the board draws MATLAB's surfaces with it): {z: [[...]]}
  function surfaceIn(el, vis) { return surface(el, vis); }
  // 3D curves (MATLAB's plot3): {curves: [{points: [[x, y, z], ...]}]}, scaled to fit, drag to turn
  function curvesIn(el, vis) {
    return three(el, (T, scene, view) => {
      const all = vis.curves.flatMap(c => c.points.filter(p => p.every(v => v !== null && isFinite(v))));
      if (!all.length) return {};
      const lo = [0, 1, 2].map(i => Math.min(...all.map(p => p[i]))), hi = [0, 1, 2].map(i => Math.max(...all.map(p => p[i])));
      const span = Math.max(1e-9, ...hi.map((h, i) => h - lo[i])), s = 12 / span, mid = hi.map((h, i) => (h + lo[i]) / 2);
      const colours = [0x4de1ff, 0xffb43b, 0xb48cff], lines = [];
      vis.curves.forEach((c, k) => {
        const pts = c.points.filter(p => p.every(v => v !== null && isFinite(v)))
          .map(([x, y, z]) => new T.Vector3((x - mid[0]) * s, (z - mid[2]) * s, -(y - mid[1]) * s));   // z up
        if (pts.length > 1) { const line = new T.Line(new T.BufferGeometry().setFromPoints(pts),
                                                    new T.LineBasicMaterial({ color: colours[k % 3] }));
          line.userData.points = c.points.filter(p => p.every(v => v !== null && isFinite(v))); lines.push(line); scene.add(line); }
      });
      scene.add(new T.AxesHelper(8));
      view.dist = 26; view.pitch = 0.5;
      const f5 = v => String(+Number(v).toPrecision(5));
      const pick = ray => { const hit = ray.intersectObjects(lines)[0]; if (!hit) return null;
        const p = hit.object.userData.points[Math.min(hit.index, hit.object.userData.points.length - 1)];
        return p ? `x = ${f5(p[0])},  y = ${f5(p[1])},  z = ${f5(p[2])}` : null; };
      return { spin: 0.15, pick };
    });
  }
  // One visual on its own, in any box (a worked problem's view, ui/problem.js): never a model-written sketch.
  function draw(box, visual) {
    let api = null, stopped = false;
    (async () => {
      try {
        if (visual.kind === "scene" && SCENES[visual.name]) {
          if (THREE_SCENES.includes(visual.name)) await load("three");
          api = await SCENES[visual.name](box, visual.params);
        }
        else if (visual.kind === "plot") api = plot(box, visual);
        else if (visual.kind === "surface") { await load("three"); api = await surface(box, visual); }
        else if (visual.kind === "diagram") api = await diagram(box, visual);
        else if (visual.kind === "image") api = image(box, visual);
        else if (visual.kind === "formula") { formula(box, visual.latex, true); api = { stop() {} }; }
        else if (visual.kind === "pview" && window.JarvisProblem) api = window.JarvisProblem.drawView(box, visual.data);
      } catch (err) { box.textContent = ""; box.append(el("div", "empty", "This picture couldn't be drawn (" + err.message + ").")); }
      if (stopped && api && api.stop) api.stop();
    })();
    return { stop() { stopped = true; if (api && api.stop) api.stop(); } };
  }
  return { start, show, patch, stop, draw, surfaceIn, curvesIn, scenes: Object.keys(SCENES), get index() { return shownIndex; } };
})();
