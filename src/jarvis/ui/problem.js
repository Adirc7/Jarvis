// Worked problems in Jarvis's window: the problem, its parts as cards (Hint, Next step, Full solution,
// Check my answer), and the tested animations its steps point at (knowledge/problem_views.py).
// Every number shown was worked out by SymPy in Jarvis; this file only draws.
//
//   const api = JarvisProblem.open(box, data, { post })   // post({problem: "step", part: "b"}) to Jarvis
//   api.state({ part: "b", shown: 2, hint: true, check: { ok: true, said: "Right: 20 m/s." } })
//   api.stop()
window.JarvisProblem = (function () {
  "use strict";
  const C = { bg: "#03070d", panel: "#091522", line: "#12314a", text: "#eaf5ff", muted: "#8fa7ba", cyan: "#4de1ff",
    amber: "#ffb43b", teal: "#4ce2c4", green: "#64efb7", red: "#ff766f", violet: "#b48cff", pink: "#ff7eb6" };
  const PHASE = [C.cyan, C.green, C.amber, C.violet, C.pink, C.teal];
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text; return e; };
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const fmt = (v, d = 3) => { if (v == null || !isFinite(v)) return "?"; const a = Math.abs(v);
    if (a < 1e-10) return "0";
    if (a !== 0 && (a < 1e-3 || a >= 1e6)) return v.toExponential(2);
    return String(Number(v.toPrecision(d + (a >= 100 ? 1 : 0)))); };
  function tex(node, latex, display) {
    node.textContent = "";
    if (!latex) return;
    if (window.katex) { try { window.katex.render(latex, node, { displayMode: !!display, throwOnError: false, trust: false }); return; } catch (e) {} }
    node.textContent = latex;
  }
  function niceStep(span, n) { const raw = span / Math.max(1, n), p = Math.pow(10, Math.floor(Math.log10(raw)));
    const f = raw / p; return (f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10) * p; }

  // ---- styles (once) ----
  function styles() {
    if (document.getElementById("problemCss")) return;
    const css = el("style"); css.id = "problemCss";
    css.textContent = `
.pw { position:relative; flex:1; display:flex; min-height:0; overflow:hidden; font:13px "Segoe UI",system-ui,sans-serif; color:${C.text}; }
.pw.full .pside { display:none; }
.pstage { flex:1; min-width:0; display:flex; flex-direction:column; }
.pview { flex:1; position:relative; min-height:220px; margin:10px 12px 0; border:1px solid ${C.line}; border-radius:12px; overflow:hidden; background:#050c14; }
.pview canvas { position:absolute; inset:0; width:100%; height:100%; display:block; }
.pview .pinner { position:absolute; inset:0; }
.pview .ptag { position:absolute; top:8px; left:12px; color:${C.muted}; font-size:12px; pointer-events:none; }
.pctl { display:flex; align-items:center; gap:8px; margin:8px 12px 0; color:${C.muted}; font-size:12px; }
.pctl[hidden] { display:none; }
.pctl input[type=range] { flex:1; accent-color:${C.cyan}; }
.pctl button, .pside button { font:inherit; font-size:12px; color:${C.text}; background:#12314a; border:1px solid #1c4766; border-radius:6px; padding:4px 10px; cursor:pointer; }
.pctl button:hover, .pside button:hover { border-color:${C.cyan}; }
.pctl button.on { border-color:${C.cyan}; color:#fff; }
.pmath { min-height:56px; margin:8px 12px 10px; padding:8px 12px; border:1px solid ${C.line}; border-radius:10px; background:${C.panel}; display:flex; align-items:center; gap:14px; flex-wrap:wrap; }
.pmath .eq { font-size:18px; } .pmath .goal { color:${C.amber}; font-size:12px; letter-spacing:1px; text-transform:uppercase; }
.badge { font-size:12px; border-radius:999px; padding:2px 9px; border:1px solid; white-space:nowrap; }
.badge.ok { color:${C.green}; border-color:#2f6b55; } .badge.no { color:${C.amber}; border-color:#6b5a2f; }
.pside { width:380px; flex:none; overflow:auto; padding:12px 14px 16px; border-left:1px solid ${C.line}; background:#050d16; }
.pside h3 { margin:0 0 4px; font-size:17px; font-weight:500; color:#fff; }
.pside .subj { color:${C.cyan}; font-size:11px; letter-spacing:2px; text-transform:uppercase; }
.pside .stmt { margin:8px 0; line-height:1.5; color:#d6e7f5; }
.pside table { width:100%; border-collapse:collapse; margin:4px 0 10px; font-size:12px; }
.pside td { padding:3px 4px; border-bottom:1px solid #0e2235; } .pside td.v { text-align:right; color:#fff; white-space:nowrap; }
.pside td.s { color:${C.cyan}; width:52px; }
.pcard { border:1px solid ${C.line}; border-radius:10px; margin:8px 0; background:#07121e; }
.pcard .ph { display:flex; gap:8px; padding:8px 10px; cursor:pointer; align-items:baseline; }
.pcard .ph b { color:${C.amber}; } .pcard .ph span { flex:1; line-height:1.4; } .pcard .ph i { color:${C.green}; font-style:normal; font-size:12px; }
.pcard.on { border-color:${C.cyan}; background:#0a1a2a; }
.pcard .pb { display:none; padding:0 10px 10px; } .pcard.on .pb { display:block; }
.pcard .btns { display:flex; gap:6px; flex-wrap:wrap; margin:2px 0 8px; }
.pcard .hint { border-left:3px solid ${C.amber}; padding:6px 9px; margin:6px 0; background:#1a1508; color:#f2e3c4; line-height:1.4; }
.pcard .st { border-left:3px solid #1c4766; padding:6px 9px; margin:6px 0; cursor:pointer; }
.pcard .st.cur { border-left-color:${C.cyan}; background:#0c2236; }
.pcard .st .g { color:${C.amber}; font-size:11px; letter-spacing:1px; text-transform:uppercase; }
.pcard .st .say { color:#cfe3f3; margin:3px 0; line-height:1.4; } .pcard .st .eq { overflow-x:auto; }
.pcard .chk { display:flex; gap:6px; margin-top:6px; } .pcard .chk input { flex:1; min-width:0; background:#06111c; color:${C.text}; border:1px solid #1c4766; border-radius:6px; padding:5px 8px; font:inherit; }
.pcard .said { margin-top:5px; font-size:12px; } .said.ok { color:${C.green}; } .said.no { color:${C.amber}; }
.pfoot { display:flex; gap:6px; flex-wrap:wrap; margin-top:12px; }
.psum { border:1px solid #2f6b55; border-radius:10px; padding:8px 10px; margin-top:10px; background:#08180f; }
.psum h4 { margin:0 0 4px; color:${C.green}; font-size:12px; letter-spacing:1px; text-transform:uppercase; font-weight:500; }
.psum li { margin:3px 0; line-height:1.4; }
.pnote { color:${C.muted}; font-size:11px; margin-top:10px; }
.pinner .readout { position:absolute; left:10px; right:10px; bottom:8px; font-size:13px; line-height:1.4; color:${C.muted};
  background:#03070dcc; padding:5px 9px; border-radius:6px; pointer-events:none; }
.pinner .legend { position:absolute; top:8px; left:58px; } .pinner .legend span { margin-right:14px; font-size:13px; color:${C.muted}; }
.pinner .diagram { position:absolute; inset:0; display:flex; align-items:center; justify-content:center; padding:16px; overflow:auto; }
.pinner .picture { position:absolute; inset:0; margin:0; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:6px; }
.pinner .picture img { max-width:100%; max-height:calc(100% - 30px); object-fit:contain; border-radius:8px; }
.pinner .formula.big { position:absolute; inset:0; display:flex; align-items:center; justify-content:center; font-size:30px; }`;
    document.head.append(css);
  }

  // ---- a canvas that fills its box and redraws every frame ----
  function canvasIn(box, draw) {
    const c = el("canvas"); box.append(c);
    const ctx = c.getContext("2d");
    let alive = true, last = performance.now();
    function frame(now) {
      if (!alive) return;
      const dt = clamp((now - last) / 1000, 0, 0.05); last = now;
      const w = box.clientWidth || 600, h = box.clientHeight || 360, pr = window.devicePixelRatio || 1;
      if (c.width !== Math.round(w * pr) || c.height !== Math.round(h * pr)) { c.width = Math.round(w * pr); c.height = Math.round(h * pr); }
      ctx.setTransform(pr, 0, 0, pr, 0, 0); ctx.clearRect(0, 0, w, h);
      try { draw(ctx, w, h, dt); } catch (err) { console.error(err); }
      requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
    return { canvas: c, stop() { alive = false; } };
  }
  function text(ctx, s, x, y, colour = C.text, size = 12, align = "left", weight = "") {
    ctx.fillStyle = colour; ctx.font = `${weight} ${size}px "Segoe UI",system-ui,sans-serif`; ctx.textAlign = align;
    ctx.textBaseline = "middle"; ctx.fillText(s, x, y);
  }
  function arrow(ctx, x0, y0, x1, y1, colour, width = 2.5, head = 9) {
    const a = Math.atan2(y1 - y0, x1 - x0), len = Math.hypot(x1 - x0, y1 - y0);
    if (len < 2) return;
    ctx.strokeStyle = colour; ctx.fillStyle = colour; ctx.lineWidth = width;
    ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1 - Math.cos(a) * head * 0.7, y1 - Math.sin(a) * head * 0.7); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(x1, y1);
    ctx.lineTo(x1 - head * Math.cos(a - 0.4), y1 - head * Math.sin(a - 0.4));
    ctx.lineTo(x1 - head * Math.cos(a + 0.4), y1 - head * Math.sin(a + 0.4)); ctx.closePath(); ctx.fill();
  }
  // axes in a rectangle: returns {X, Y} mapping data to pixels
  function axes(ctx, r, xr, yr, xl, yl) {
    const X = v => r.x + (v - xr[0]) / (xr[1] - xr[0]) * r.w, Y = v => r.y + r.h - (v - yr[0]) / (yr[1] - yr[0]) * r.h;
    ctx.strokeStyle = C.line; ctx.lineWidth = 1;
    const sx = niceStep(xr[1] - xr[0], 6), sy = niceStep(yr[1] - yr[0], 4);
    for (let v = Math.ceil(xr[0] / sx) * sx; v <= xr[1] + 1e-9; v += sx) {
      ctx.beginPath(); ctx.moveTo(X(v), r.y); ctx.lineTo(X(v), r.y + r.h); ctx.stroke();
      text(ctx, fmt(v), X(v), r.y + r.h + 10, C.muted, 10, "center");
    }
    for (let v = Math.ceil(yr[0] / sy) * sy; v <= yr[1] + 1e-9; v += sy) {
      ctx.beginPath(); ctx.moveTo(r.x, Y(v)); ctx.lineTo(r.x + r.w, Y(v)); ctx.stroke();
      text(ctx, fmt(v), r.x - 5, Y(v), C.muted, 10, "right");
    }
    ctx.strokeStyle = "#2a5878"; ctx.lineWidth = 1.2;
    if (yr[0] <= 0 && yr[1] >= 0) { ctx.beginPath(); ctx.moveTo(r.x, Y(0)); ctx.lineTo(r.x + r.w, Y(0)); ctx.stroke(); }
    if (xr[0] <= 0 && xr[1] >= 0) { ctx.beginPath(); ctx.moveTo(X(0), r.y); ctx.lineTo(X(0), r.y + r.h); ctx.stroke(); }
    if (xl) text(ctx, xl, r.x + r.w, r.y + r.h + 22, C.muted, 11, "right");
    if (yl) text(ctx, yl, r.x + 4, r.y - 8, C.cyan, 11, "left", "600");
    return { X, Y };
  }
  function curve(ctx, pts, X, Y, colour, width = 2.2, upTo) {
    ctx.strokeStyle = colour; ctx.lineWidth = width; ctx.beginPath(); let pen = false;
    for (const [x, y] of pts) {
      if (upTo !== undefined && x > upTo) break;
      if (y == null || !isFinite(y)) { pen = false; continue; }
      if (!pen) { ctx.moveTo(X(x), Y(y)); pen = true; } else ctx.lineTo(X(x), Y(y));
    }
    ctx.stroke();
  }

  // ---- things that move: a car, a ball, a box... (drawn shapes, no brand) ----
  function body(ctx, look, x, y, s, opts = {}) {
    ctx.save(); ctx.translate(x, y);
    if (look === "ball") { ctx.fillStyle = C.amber; ctx.beginPath(); ctx.arc(0, -s * 0.35, s * 0.35, 0, 7); ctx.fill(); ctx.restore(); return; }
    if (look === "box") { ctx.fillStyle = "#c08a3e"; ctx.fillRect(-s * 0.4, -s * 0.8, s * 0.8, s * 0.8); ctx.strokeStyle = "#7a5420"; ctx.strokeRect(-s * 0.4, -s * 0.8, s * 0.8, s * 0.8); ctx.restore(); return; }
    if (look === "person") { ctx.strokeStyle = C.text; ctx.lineWidth = 2.5; ctx.beginPath(); ctx.arc(0, -s * 0.9, s * 0.12, 0, 7); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(0, -s * 0.78); ctx.lineTo(0, -s * 0.4); ctx.lineTo(-s * 0.15, 0); ctx.moveTo(0, -s * 0.4); ctx.lineTo(s * 0.15, 0);
      ctx.moveTo(-s * 0.18, -s * 0.62); ctx.lineTo(s * 0.18, -s * 0.62); ctx.stroke(); ctx.restore(); return; }
    if (look === "rocket") { ctx.rotate(-Math.PI / 2); ctx.fillStyle = "#d8e6f2"; ctx.beginPath(); ctx.moveTo(s * 0.9, 0); ctx.lineTo(0, -s * 0.2); ctx.lineTo(-s * 0.5, -s * 0.2); ctx.lineTo(-s * 0.5, s * 0.2); ctx.lineTo(0, s * 0.2); ctx.closePath(); ctx.fill(); ctx.restore(); return; }
    const L = look === "truck" ? s * 1.6 : look === "train" ? s * 2.2 : look === "bike" ? s * 0.9 : s * 1.3;
    const H = look === "bike" ? s * 0.3 : s * 0.42, wr = s * 0.17;
    const colour = look === "truck" ? "#3a8bff" : look === "train" ? "#64efb7" : look === "bike" ? "#ff7eb6" : "#4de1ff";
    ctx.fillStyle = colour; ctx.strokeStyle = "#0b2234"; ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.roundRect ? ctx.roundRect(-L / 2, -H - wr, L, H, 5) : ctx.rect(-L / 2, -H - wr, L, H); ctx.fill();
    if (look === "car") { ctx.fillStyle = "#a9e9ff"; ctx.beginPath(); ctx.moveTo(-L * 0.28, -H - wr); ctx.lineTo(-L * 0.16, -H - wr - s * 0.26);
      ctx.lineTo(L * 0.18, -H - wr - s * 0.26); ctx.lineTo(L * 0.32, -H - wr); ctx.closePath(); ctx.fill(); }
    if (opts.braking) { ctx.fillStyle = C.red; ctx.fillRect(-L / 2 - 3, -H - wr + 3, 4, H * 0.45); }
    ctx.fillStyle = "#fff59a"; ctx.fillRect(L / 2 - 2, -H - wr + 3, 3, H * 0.35);
    const wheels = look === "train" ? [-0.38, -0.15, 0.15, 0.38] : [-0.3, 0.3];
    for (const k of wheels) { ctx.save(); ctx.translate(k * L, -wr); ctx.rotate(opts.spin || 0); ctx.fillStyle = "#11161c"; ctx.beginPath();
      ctx.arc(0, 0, wr, 0, 7); ctx.fill(); ctx.strokeStyle = "#7b8b99"; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.moveTo(-wr * 0.7, 0); ctx.lineTo(wr * 0.7, 0); ctx.stroke(); ctx.restore(); }
    ctx.restore();
  }

  // ======================= the views =======================
  // Each returns {draw(ctx, w, h, dt), duration, at(t) for highlight, label, timed}
  function motionAt(b, t) {
    if (t <= b.phases[0].t0) return { s: b.phases[0].s0, v: b.phases[0].u, a: 0, i: -1 };
    for (let i = 0; i < b.phases.length; i++) {
      const p = b.phases[i];
      if (t <= p.t1) { const d = t - p.t0; return { s: p.s0 + p.u * d + p.a * d * d / 2, v: p.u + p.a * d, a: p.a, i }; }
    }
    return { s: b.s_end, v: b.v_end, a: 0, i: b.phases.length };
  }
  function motionView(v) {
    const T = v.T, graphs = v.graphs, span = Math.max(1, v.s_range[1] - v.s_range[0]);
    const series = {};
    for (const b of v.bodies) {
      const pts = { s: [], v: [], a: [] };
      for (let k = 0; k <= 400; k++) { const t = T * k / 400, m = motionAt(b, t); pts.s.push([t, m.s]); pts.v.push([t, m.v]); pts.a.push([t, m.a]); }
      series[b.name] = pts;
    }
    const range = { s: [Math.min(0, v.s_range[0]), v.s_range[1] * 1.08 || 1], v: [Math.min(0, -0.05 * v.v_max), v.v_max * 1.15 || 1],
      a: [-v.a_max * 1.25, v.a_max * 1.25] };
    const names = { s: "s (m)", v: "v (m/s)", a: "a (m/s²)" };
    let spin = 0;
    return { timed: true, T, draw(ctx, w, h, dt, t, hl) {
      const roadH = Math.max(120, h * 0.36), x0 = 50, x1 = w - 30, X = s => x0 + (s - v.s_range[0]) / span * (x1 - x0), ry = roadH - 34;
      // the road, distance marks, and where each phase happened
      ctx.fillStyle = "#0b1622"; ctx.fillRect(0, ry, w, 26); ctx.strokeStyle = "#2a3c4c"; ctx.setLineDash([14, 12]); ctx.lineWidth = 2;
      ctx.beginPath(); ctx.moveTo(0, ry + 13); ctx.lineTo(w, ry + 13); ctx.stroke(); ctx.setLineDash([]);
      const step = niceStep(span, 8);
      for (let s = Math.ceil(v.s_range[0] / step) * step; s <= v.s_range[1] + 1e-9; s += step) {
        ctx.strokeStyle = C.line; ctx.beginPath(); ctx.moveTo(X(s), ry + 26); ctx.lineTo(X(s), ry + 32); ctx.stroke();
        text(ctx, fmt(s) + " m", X(s), ry + 40, C.muted, 10, "center");
      }
      const b0 = v.bodies[0];
      b0.phases.forEach((p, i) => { const sa = p.s0, sb = motionAt(b0, p.t1).s, lit = hl.phase === i;
        ctx.fillStyle = PHASE[i % PHASE.length] + (lit ? "66" : "22"); ctx.fillRect(X(sa), ry - 4, Math.max(1, X(sb) - X(sa)), 4);
        if (X(sb) - X(sa) > 60 || lit) text(ctx, p.label, (X(sa) + X(sb)) / 2, ry - 12, PHASE[i % PHASE.length], 11, "center", lit ? "600" : ""); });
      spin += dt * 6;
      // a speedometer for the first body, in km/h
      { const m = motionAt(b0, t), R = Math.min(60, (ry - 60) * 0.55), cx = w - R - 30, cy = 40 + R, top = Math.max(20, Math.ceil(v.v_max * 3.6 / 20) * 20);
        if (R > 24) { ctx.lineWidth = 6; ctx.strokeStyle = "#12314a"; ctx.beginPath(); ctx.arc(cx, cy, R, Math.PI * 0.8, Math.PI * 2.2); ctx.stroke();
          const f = clamp(Math.abs(m.v) * 3.6 / top, 0, 1); ctx.strokeStyle = m.a < 0 ? C.red : C.cyan; ctx.beginPath(); ctx.arc(cx, cy, R, Math.PI * 0.8, Math.PI * (0.8 + 1.4 * f)); ctx.stroke();
          for (let k = 0; k <= 4; k++) { const an = Math.PI * (0.8 + 1.4 * k / 4); text(ctx, String(Math.round(top * k / 4)), cx + Math.cos(an) * (R - 16), cy + Math.sin(an) * (R - 16), C.muted, 9, "center"); }
          text(ctx, `${Math.round(Math.abs(m.v) * 3.6)}`, cx, cy - 4, C.text, 20, "center", "600"); text(ctx, "km/h", cx, cy + 14, C.muted, 10, "center"); } }
      v.bodies.forEach((b, j) => {
        const m = motionAt(b, t), p = b.phases[m.i], lane = ry + 4 - j * 30;
        if (p && p.locked && m.a < 0) { ctx.strokeStyle = "#000"; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(X(p.s0), ry + 21); ctx.lineTo(X(m.s), ry + 21); ctx.stroke(); }
        body(ctx, b.look, X(m.s), lane + 18, 34, { braking: m.a < 0, spin: p && p.locked && m.a < 0 ? 0 : spin * m.v / Math.max(1, v.v_max) * 3 });
        if (p && p.abs && m.a < 0 && Math.floor(t * 8) % 2 === 0) { ctx.fillStyle = C.amber; ctx.font = "bold 11px Segoe UI"; ctx.textAlign = "center"; ctx.fillText("ABS", X(m.s), lane - 38); }
        if (Math.abs(m.v) > 0.01) arrow(ctx, X(m.s), lane - 22, X(m.s) + clamp(m.v / v.v_max * 70, -70, 70), lane - 22, C.cyan, 2, 7);
        text(ctx, `${b.name}: t = ${fmt(t)} s   s = ${fmt(m.s)} m   v = ${fmt(m.v)} m/s (${fmt(m.v * 3.6)} km/h)   a = ${fmt(m.a)} m/s²` +
          (p ? `   · ${p.label}` : ""), 12, 16 + j * 18, j ? C.muted : C.text, 12);
      });
      // the graphs
      const gTop = roadH + 18, n = graphs.length, gh = (h - gTop - 8) / Math.max(1, n);
      graphs.forEach((g, k) => {
        const r = { x: 56, y: gTop + k * gh + 10, w: w - 80, h: gh - 34 };
        if (r.h < 30) return;
        const { X: GX, Y: GY } = axes(ctx, r, [0, T], range[g] || [0, 1], k === n - 1 ? "t (s)" : "", names[g]);
        b0.phases.forEach((p, i) => { ctx.strokeStyle = "#1f4462"; ctx.setLineDash([4, 4]); ctx.beginPath(); ctx.moveTo(GX(p.t1), r.y); ctx.lineTo(GX(p.t1), r.y + r.h); ctx.stroke(); ctx.setLineDash([]);
          if (hl.phase === i) { ctx.fillStyle = PHASE[i % PHASE.length] + "22"; ctx.fillRect(GX(p.t0), r.y, GX(p.t1) - GX(p.t0), r.h); } });
        if (hl.area && (hl.graph || "v") === g) {
          const [ta, tb] = hl.area, inside = series[b0.name][g].filter(([tt]) => tt > ta && tt < tb);
          const pts = [[ta, motionAt(b0, ta)[g]], ...inside, [tb, motionAt(b0, tb)[g]]];
          ctx.fillStyle = C.amber + "44"; ctx.beginPath(); ctx.moveTo(GX(ta), GY(0)); for (const [tt, y] of pts) ctx.lineTo(GX(tt), GY(y)); ctx.lineTo(GX(tb), GY(0)); ctx.closePath(); ctx.fill();
          // the area under v-t is the distance: exactly s(tb) - s(ta)
          const area = g === "v" ? motionAt(b0, tb).s - motionAt(b0, ta).s : null;
          if (area !== null) text(ctx, `area = distance = ${fmt(area)} m`, GX((ta + tb) / 2), r.y + 12, C.amber, 12, "center", "600");
        }
        v.bodies.forEach((b, j) => { curve(ctx, series[b.name][g], GX, GY, j ? C.pink + "88" : "#2a6f8f", 1.5); curve(ctx, series[b.name][g], GX, GY, j ? C.pink : C.cyan, 2.4, t); });
        if (hl.point !== undefined && (hl.graph || "v") === g) { const m = motionAt(b0, hl.point), y = m[g];
          ctx.fillStyle = C.amber; ctx.beginPath(); ctx.arc(GX(hl.point), GY(y), 5, 0, 7); ctx.fill(); text(ctx, fmt(y), GX(hl.point) + 8, GY(y) - 10, C.amber, 12, "left", "600"); }
        ctx.strokeStyle = C.amber; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(GX(t), r.y); ctx.lineTo(GX(t), r.y + r.h); ctx.stroke();
      });
    } };
  }
  function pathView(v) {
    const P = v.points, T = v.T, xs = P.map(p => p[0]), ys = P.map(p => p[1]);
    const xr = [Math.min(0, ...xs), Math.max(...xs)], yr = [Math.min(0, ...ys), Math.max(...ys)];
    const idx = t => clamp(Math.round(t / T * (P.length - 1)), 0, P.length - 1);
    const gs = v.graphs, col = { x: 0, y: 1, vx: 2, vy: 3 }, names = { x: "x (m)", y: "y (m)", vx: "vx (m/s)", vy: "vy (m/s)" };
    return { timed: true, T, draw(ctx, w, h, dt, t) {
      const top = h * (gs.length ? 0.6 : 0.92), pad = 46;
      const sx = (w - 2 * pad) / Math.max(1e-9, xr[1] - xr[0]), sy = (top - 2 * pad) / Math.max(1e-9, yr[1] - yr[0]), s = Math.min(sx, sy);
      const X = x => pad + (x - xr[0]) * s, Y = y => top - pad - (y - yr[0]) * s;
      if (v.ground) { ctx.fillStyle = "#0b1622"; ctx.fillRect(0, Y(0), w, top - Y(0)); }
      axes(ctx, { x: X(xr[0]), y: Y(yr[1]), w: (xr[1] - xr[0]) * s, h: (yr[1] - yr[0]) * s }, xr, yr, "x (m)", "y (m)");
      ctx.strokeStyle = "#2a6f8f"; ctx.lineWidth = 1.5; ctx.setLineDash([5, 5]); ctx.beginPath(); P.forEach((p, i) => i ? ctx.lineTo(X(p[0]), Y(p[1])) : ctx.moveTo(X(p[0]), Y(p[1]))); ctx.stroke(); ctx.setLineDash([]);
      const k = idx(t); ctx.strokeStyle = C.cyan; ctx.lineWidth = 2.5; ctx.beginPath(); for (let i = 0; i <= k; i++) i ? ctx.lineTo(X(P[i][0]), Y(P[i][1])) : ctx.moveTo(X(P[i][0]), Y(P[i][1])); ctx.stroke();
      const p = P[k], sc = 40 / Math.max(1, Math.max(...P.map(q => Math.hypot(q[2], q[3]))));
      body(ctx, v.look, X(p[0]), Y(p[1]) + 12, 30);
      arrow(ctx, X(p[0]), Y(p[1]), X(p[0]) + p[2] * sc * 1.6, Y(p[1]), C.green, 2, 7);
      arrow(ctx, X(p[0]), Y(p[1]), X(p[0]), Y(p[1]) - p[3] * sc * 1.6, C.pink, 2, 7);
      arrow(ctx, X(p[0]), Y(p[1]), X(p[0]) + p[2] * sc * 1.6, Y(p[1]) - p[3] * sc * 1.6, C.amber, 2.4, 8);
      text(ctx, `t = ${fmt(t)} s   x = ${fmt(p[0])} m   y = ${fmt(p[1])} m   vx = ${fmt(p[2])}   vy = ${fmt(p[3])} m/s`, 12, 16, C.text, 12);
      gs.forEach((g, j) => {
        const gw = (w - 40) / gs.length, r = { x: 50 + j * gw, y: top + 16, w: gw - 60, h: h - top - 44 };
        if (r.h < 30) return;
        const vals = P.map((q, i) => [v.times[i], q[col[g]]]), lo = Math.min(0, ...vals.map(q => q[1])), hi = Math.max(...vals.map(q => q[1]));
        const { X: GX, Y: GY } = axes(ctx, r, [0, T], [lo, hi === lo ? lo + 1 : hi], "t (s)", names[g]);
        curve(ctx, vals, GX, GY, "#2a6f8f", 1.5); curve(ctx, vals, GX, GY, C.cyan, 2.4, t);
      });
    } };
  }
  function graphView(v) {
    const xr = v.x, yr = v.y || [-5, 5], A = v.annotations || {}, cols = [C.cyan, C.pink, C.green, C.violet, C.teal];
    let age = 0, lastKey = "";
    return { timed: false, draw(ctx, w, h, dt, t, hl) {
      const key = JSON.stringify(hl); if (key !== lastKey) { lastKey = key; age = 0; } age += dt;
      const grow = clamp(age / 0.8, 0, 1);
      const r = { x: 56, y: 28, w: w - 90, h: h - 70 }, { X, Y } = axes(ctx, r, xr, yr, v.xlabel, v.ylabel);
      ctx.save(); ctx.beginPath(); ctx.rect(r.x, r.y, r.w, r.h); ctx.clip();
      const show = name => !hl.show || hl.show.includes(name);
      if (A.area && show("area")) { const c = v.curves[A.area.curve], pts = c.points.filter(p => p[0] >= A.area.from && p[0] <= A.area.to && p[1] != null);
        ctx.fillStyle = C.amber + "40"; ctx.beginPath(); ctx.moveTo(X(A.area.from), Y(0)); for (const [x, y] of pts) ctx.lineTo(X(x), Y(y)); ctx.lineTo(X(A.area.to), Y(0)); ctx.closePath(); ctx.fill(); }
      if (A.riemann && show("riemann")) for (const [xa, xb, ya, yb] of A.riemann.bars) {
        ctx.fillStyle = C.violet + "30"; ctx.strokeStyle = C.violet; ctx.lineWidth = 1.5; ctx.beginPath();
        ctx.moveTo(X(xa), Y(0)); ctx.lineTo(X(xa), Y(ya * grow)); ctx.lineTo(X(xb), Y(yb * grow)); ctx.lineTo(X(xb), Y(0)); ctx.closePath(); ctx.fill(); ctx.stroke(); }
      v.curves.forEach((c, i) => curve(ctx, c.points, X, Y, cols[i % cols.length], 2.4));
      if (A.tangent && show("tangent")) { const tg = A.tangent, d = (xr[1] - xr[0]) * 0.3 * grow;
        ctx.strokeStyle = C.amber; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(X(tg.at - d), Y(tg.y - tg.slope * d)); ctx.lineTo(X(tg.at + d), Y(tg.y + tg.slope * d)); ctx.stroke();
        ctx.fillStyle = C.amber; ctx.beginPath(); ctx.arc(X(tg.at), Y(tg.y), 4, 0, 7); ctx.fill(); }
      if (A.newton && show("newton")) { const upto = hl.newton_step === undefined ? A.newton.steps.length : hl.newton_step;
        A.newton.steps.slice(0, upto).forEach((s, i) => { const g = i === upto - 1 ? grow : 1, xe = s.x + (s.next - s.x) * g;
          ctx.strokeStyle = C.amber; ctx.lineWidth = 1.6; ctx.setLineDash([5, 4]); ctx.beginPath(); ctx.moveTo(X(s.x), Y(0)); ctx.lineTo(X(s.x), Y(s.y)); ctx.stroke(); ctx.setLineDash([]);
          ctx.beginPath(); ctx.moveTo(X(s.x), Y(s.y)); ctx.lineTo(X(xe), Y(s.y + s.slope * (xe - s.x))); ctx.stroke();
          ctx.fillStyle = C.amber; ctx.beginPath(); ctx.arc(X(s.x), Y(s.y), 3.5, 0, 7); ctx.fill(); });
        const s0 = A.newton.steps[Math.max(0, Math.min(upto, A.newton.steps.length) - 1)];
        if (s0 && upto > 0) { ctx.fillStyle = C.green; ctx.beginPath(); ctx.arc(X(s0.next), Y(0), 4.5, 0, 7); ctx.fill(); } }
      if (A.euler && show("euler")) { const upto = hl.euler_step === undefined ? A.euler.points.length : hl.euler_step + 1;
        ctx.strokeStyle = C.amber; ctx.fillStyle = C.amber; ctx.lineWidth = 2; ctx.beginPath();
        A.euler.points.slice(0, upto).forEach((p, i) => i ? ctx.lineTo(X(p[0]), Y(p[1])) : ctx.moveTo(X(p[0]), Y(p[1]))); ctx.stroke();
        A.euler.points.slice(0, upto).forEach(p => { ctx.beginPath(); ctx.arc(X(p[0]), Y(p[1]), 3.5, 0, 7); ctx.fill(); }); }
      if (A.points && show("points")) for (const [px, py, lab] of A.points) { ctx.fillStyle = C.green; ctx.beginPath(); ctx.arc(X(px), Y(py), 5, 0, 7); ctx.fill();
        text(ctx, `${lab ? lab + " " : ""}(${fmt(px)}, ${fmt(py)})`, X(px) + 8, Y(py) - 12, C.green, 12, "left", "600"); }
      if (hl.x !== undefined) { ctx.strokeStyle = C.amber; ctx.setLineDash([4, 4]); ctx.beginPath(); ctx.moveTo(X(hl.x), r.y); ctx.lineTo(X(hl.x), r.y + r.h); ctx.stroke(); ctx.setLineDash([]); }
      ctx.restore();
      let ly = 14; v.curves.forEach((c, i) => { text(ctx, "— " + c.label, w - 20, ly, cols[i % cols.length], 12, "right"); ly += 16; });
      if (A.area && show("area")) { text(ctx, `area = ${A.area.shown}`, r.x + 8, r.y + 14, C.amber, 13, "left", "600"); }
      if (A.riemann && show("riemann")) text(ctx, `${A.riemann.rule} rule: ${A.riemann.shown}  (exact ${A.riemann.exact_shown})`, r.x + 8, r.y + 32, C.violet, 13, "left", "600");
      if (A.tangent && show("tangent")) text(ctx, `slope at x = ${fmt(A.tangent.at)}: ${A.tangent.shown}`, r.x + 8, r.y + 50, C.amber, 13, "left", "600");
      if (A.newton && show("newton")) { const upto = hl.newton_step === undefined ? A.newton.steps.length : hl.newton_step;
        A.newton.steps.slice(0, upto).forEach((s, i) => text(ctx, `x${i + 1} = ${s.shown}`, r.x + 8, r.y + 14 + i * 16, C.amber, 13, "left", "600")); }
    } };
  }
  function forcesView(v) {
    const max = Math.max(1e-9, ...v.forces.map(f => Math.abs(f.value || 0)));
    let age = 0, lastKey = "";
    return { timed: false, draw(ctx, w, h, dt, t, hl) {
      const key = JSON.stringify(hl); if (key !== lastKey) { lastKey = key; age = 0; } age += dt;
      const grow = clamp(age / 0.7, 0, 1), th = v.angle * Math.PI / 180, cx = w / 2, cy = h * 0.58;
      ctx.save(); ctx.translate(cx, cy); ctx.rotate(-th);
      ctx.fillStyle = "#0b1622"; ctx.fillRect(-w, 0, 2 * w, 12); ctx.strokeStyle = "#2a5878"; ctx.beginPath(); ctx.moveTo(-w, 0); ctx.lineTo(w, 0); ctx.stroke();
      body(ctx, v.body === "car" ? "car" : v.body === "person" ? "person" : "box", 0, 0, 70);
      ctx.restore();
      if (v.incline) { ctx.strokeStyle = C.muted; ctx.beginPath(); ctx.arc(cx - 160 * Math.cos(th), cy + 160 * Math.sin(th), 40, -th, 0); ctx.stroke();
        text(ctx, `θ = ${fmt(v.angle)}°`, cx - 160 * Math.cos(th) + 48, cy + 160 * Math.sin(th) - 8, C.muted, 12); }
      const L = Math.min(w, h) * 0.32, oy = cy - 30;
      v.forces.forEach((f, i) => {
        const lit = !hl.force || hl.force === f.name || hl.force === f.symbol, len = (f.value == null ? 0.6 : 0.25 + 0.75 * Math.abs(f.value) / max) * L * grow;
        const a = f.angle * Math.PI / 180, x1 = cx + Math.cos(a) * len, y1 = oy - Math.sin(a) * len, colour = lit ? PHASE[i % PHASE.length] : "#35506a";
        arrow(ctx, cx, oy, x1, y1, colour, lit && hl.force ? 4 : 2.8, 11);
        text(ctx, `${f.symbol || f.name}${f.shown ? " = " + f.shown + (f.value != null ? " N" : "") : ""}`, x1 + Math.cos(a) * 14, y1 - Math.sin(a) * 14,
          colour, 13, Math.cos(a) < -0.3 ? "right" : Math.cos(a) > 0.3 ? "left" : "center", "600");
      });
      if (v.incline && (v.components || hl.components)) {
        const wf = v.forces.find(f => f.angle === 270); if (wf) { const len = (wf.value == null ? 0.6 : 0.25 + 0.75 * Math.abs(wf.value) / max) * L;
          const along = len * Math.sin(th), perp = len * Math.cos(th);
          ctx.setLineDash([5, 4]);
          arrow(ctx, cx, oy, cx - Math.cos(th) * along, oy + Math.sin(th) * along, C.muted, 1.8, 8);
          arrow(ctx, cx, oy, cx + Math.sin(th) * perp, oy + Math.cos(th) * perp, C.muted, 1.8, 8); ctx.setLineDash([]);
          text(ctx, "mg sin θ", cx - Math.cos(th) * along - 10, oy + Math.sin(th) * along + 14, C.muted, 12, "right");
          text(ctx, "mg cos θ", cx + Math.sin(th) * perp + 10, oy + Math.cos(th) * perp, C.muted, 12); }
      }
    } };
  }
  function circuitView(v) {
    // lay the network out: series left to right, parallel stacked; every element's wire at its top + 30
    function size(n) { if (n.type === "R") return n.sz = { w: 130, h: 70 };
      const ks = n.kids.map(size);
      return n.sz = n.type === "series" ? { w: ks.reduce((a, k) => a + k.w, 0), h: Math.max(...ks.map(k => k.h)) }
        : { w: Math.max(...ks.map(k => k.w)) + 50, h: ks.reduce((a, k) => a + k.h, 0) }; }
    const wires = [], parts = [];
    function place(n, x, y) {
      if (n.type === "R") { wires.push([x, y + 30, x + 35, y + 30, n.I]); parts.push({ n, x: x + 35, y: y + 30 }); wires.push([x + 95, y + 30, x + 130, y + 30, n.I]); return; }
      if (n.type === "series") { let cx = x; for (const k of n.kids) { place(k, cx, y); cx += k.sz.w; } return; }
      let cy = y; const right = x + n.sz.w;
      n.kids.forEach((k, i) => { place(k, x + 25, cy); wires.push([x + 25 + k.sz.w, cy + 30, right - 25, cy + 30, k.I]);
        if (i) { wires.push([x + 25, cy - n.kids[i - 1].sz.h + 30, x + 25, cy + 30, k.I]); wires.push([right - 25, cy - n.kids[i - 1].sz.h + 30, right - 25, cy + 30, k.I]); }
        cy += k.sz.h; });
      wires.push([x, y + 30, x + 25, y + 30, n.I]); wires.push([right - 25, y + 30, right, y + 30, n.I]);
    }
    const S = size(v.tree); place(v.tree, 0, 0);
    let flow = 0;
    return { timed: false, draw(ctx, w, h, dt, t, hl) {
      flow += dt;
      const W = S.w + 160, H = S.h + 120, sc = Math.min((w - 40) / W, (h - 40) / H, 1.6), ox = (w - W * sc) / 2 + 110 * sc, oy = (h - H * sc) / 2 + 20 * sc;
      ctx.save(); ctx.translate(ox, oy); ctx.scale(sc, sc);
      const bottom = S.h + 40, left = -80;
      const loop = [[S.w, 30, S.w + 30, 30], [S.w + 30, 30, S.w + 30, bottom], [S.w + 30, bottom, left, bottom], [left, bottom, left, 30], [left, 30, 0, 30]];
      const all = [...wires, ...loop.map(l => [...l, v.I])], maxI = Math.max(1e-9, ...wires.map(w2 => Math.abs(w2[4] || 0)), Math.abs(v.I));
      for (const [x0, y0, x1, y1, I] of all) {
        ctx.strokeStyle = "#2f6f93"; ctx.lineWidth = 2.5; ctx.setLineDash([]); ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke();
        ctx.strokeStyle = C.amber; ctx.lineWidth = 2.5; ctx.setLineDash([3, 14]); ctx.lineDashOffset = -flow * 40 * Math.abs(I || 0) / maxI; ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke();
      }
      ctx.setLineDash([]);
      // the battery on the left wire, the internal resistance on the bottom one
      const by = (30 + bottom) / 2; ctx.fillStyle = C.bg; ctx.fillRect(left - 20, by - 16, 40, 32);
      ctx.strokeStyle = C.text; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(left - 18, by - 6); ctx.lineTo(left + 18, by - 6); ctx.stroke();
      ctx.lineWidth = 6; ctx.beginPath(); ctx.moveTo(left - 9, by + 6); ctx.lineTo(left + 9, by + 6); ctx.stroke();
      text(ctx, `${fmt(v.V)} V`, left - 26, by, C.text, 13, "right", "600");
      if (v.r > 0) { const rx = (S.w + left) / 2; ctx.fillStyle = C.bg; ctx.fillRect(rx - 30, bottom - 10, 60, 20); ctx.strokeStyle = C.muted; ctx.lineWidth = 2; ctx.strokeRect(rx - 30, bottom - 10, 60, 20);
        text(ctx, `r = ${fmt(v.r)} Ω`, rx, bottom + 22, C.muted, 12, "center"); }
      for (const { n, x, y } of parts) {
        const lit = hl.element === n.name;
        ctx.fillStyle = lit ? "#1a3a2a" : C.bg; ctx.fillRect(x, y - 13, 60, 26); ctx.strokeStyle = lit ? C.green : C.cyan; ctx.lineWidth = lit ? 3 : 2; ctx.strokeRect(x, y - 13, 60, 26);
        text(ctx, n.name, x + 30, y, lit ? C.green : C.text, 12, "center", "600");
        text(ctx, `${fmt(n.R)} Ω`, x + 30, y - 22, C.muted, 11, "center");
        text(ctx, `${fmt(n.I)} A · ${fmt(n.V)} V`, x + 30, y + 24, lit ? C.green : C.amber, 11, "center", lit ? "600" : "");
      }
      ctx.restore();
      text(ctx, v.shown, 14, 16, C.text, 13, "left", "600");
    } };
  }
  function kineticsView(v) {
    const conc = t => v.order === 0 ? Math.max(0, v.A0 - v.k * t) : v.order === 1 ? v.A0 * Math.exp(-v.k * t) : v.A0 / (1 + v.A0 * v.k * t);
    const f = { A: c => c, lnA: c => (c > 0 ? Math.log(c) : null), invA: c => (c > 0 ? 1 / c : null) }[v.plot];
    const pts = []; for (let k = 0; k <= 300; k++) { const t = v.T * k / 300; pts.push([t, f(conc(t))]); }
    const ys = pts.map(p => p[1]).filter(y => y != null), yr = [Math.min(0, ...ys), Math.max(...ys) * 1.1];
    const dots = Array.from({ length: 70 }, (_, i) => ({ x: Math.random(), y: Math.random(), vx: Math.random() - 0.5, vy: Math.random() - 0.5, r: Math.random() }));
    return { timed: true, T: v.T, draw(ctx, w, h, dt, t, hl) {
      const bw = Math.min(w * 0.34, h - 60), box = { x: 20, y: 40, w: bw, h: bw }, c = conc(t);
      ctx.strokeStyle = C.line; ctx.strokeRect(box.x, box.y, box.w, box.h);
      for (const d of dots) { d.x += d.vx * dt * 0.3; d.y += d.vy * dt * 0.3; if (d.x < 0 || d.x > 1) d.vx *= -1; if (d.y < 0 || d.y > 1) d.vy *= -1;
        d.x = clamp(d.x, 0, 1); d.y = clamp(d.y, 0, 1);
        ctx.fillStyle = d.r < c / v.A0 ? C.cyan : C.amber; ctx.beginPath(); ctx.arc(box.x + 6 + d.x * (box.w - 12), box.y + 6 + d.y * (box.h - 12), 4, 0, 7); ctx.fill(); }
      text(ctx, `● ${v.species} ${fmt(c)} mol/L`, box.x, box.y - 22, C.cyan, 12); text(ctx, "● product", box.x + 150, box.y - 22, C.amber, 12);
      const r = { x: box.x + bw + 70, y: 40, w: w - bw - 120, h: h - 90 };
      const label = { A: `[${v.species}] (mol/L)`, lnA: `ln[${v.species}]`, invA: `1/[${v.species}]` }[v.plot];
      const { X, Y } = axes(ctx, r, [0, v.T], yr, "t (s)", label);
      curve(ctx, pts, X, Y, "#2a6f8f", 1.5); curve(ctx, pts, X, Y, C.cyan, 2.4, t);
      if (v.plot === "A") for (let n = 1; n * v.half_life <= v.T && n <= 6; n++) { const th = n * v.half_life;
        ctx.strokeStyle = (hl.half_lives || hl.t !== undefined) ? C.amber : "#3b4f63"; ctx.setLineDash([4, 4]); ctx.beginPath(); ctx.moveTo(X(th), Y(0)); ctx.lineTo(X(th), Y(f(conc(th)))); ctx.lineTo(r.x, Y(f(conc(th)))); ctx.stroke(); ctx.setLineDash([]);
        if (n <= 3) text(ctx, `${n}t½`, X(th), r.y + r.h + 22, C.amber, 11, "center"); }
      ctx.strokeStyle = C.amber; ctx.beginPath(); ctx.moveTo(X(t), r.y); ctx.lineTo(X(t), r.y + r.h); ctx.stroke();
      text(ctx, `order ${v.order} · k = ${fmt(v.k)} · t½ = ${v.half_shown} s · t = ${fmt(t)} s`, 14, 16, C.text, 12);
    } };
  }
  function titrationView(v) {
    const C_ = v.curve, Vm = v.V_max, phAt = V => { const k = clamp(V / Vm * (C_.length - 1), 0, C_.length - 1), i = Math.floor(k), f = k - i;
      return i + 1 < C_.length ? C_[i][1] * (1 - f) + C_[i + 1][1] * f : C_[i][1]; };
    function colour(ph) {
      if (v.indicator === "phenolphthalein") { const s = clamp((ph - 8.2) / 1.8, 0, 1); return `rgba(255,${Math.round(110 - 40 * s)},${Math.round(200 - 20 * s)},${0.12 + 0.6 * s})`; }
      if (v.indicator === "methyl_orange") { const s = clamp((ph - 3.1) / 1.3, 0, 1); return `rgba(${Math.round(240 + 15 * s)},${Math.round(60 + 160 * s)},${Math.round(40 + 20 * s)},0.6)`; }
      return "rgba(160,210,255,0.25)";
    }
    return { timed: true, T: Vm, unit: "mL", draw(ctx, w, h, dt, V, hl) {
      const ph = phAt(V), bx = 70, top = 30, bh = h * 0.5;
      ctx.strokeStyle = C.text; ctx.lineWidth = 1.5; ctx.strokeRect(bx - 8, top, 16, bh);
      const left = 1 - V / Vm; ctx.fillStyle = "rgba(160,210,255,0.35)"; ctx.fillRect(bx - 7, top + bh * (1 - left), 14, bh * left);
      for (let k = 0; k <= 5; k++) { ctx.beginPath(); ctx.moveTo(bx + 8, top + bh * k / 5); ctx.lineTo(bx + 14, top + bh * k / 5); ctx.stroke(); text(ctx, fmt(Vm * k / 5), bx + 18, top + bh * k / 5, C.muted, 10); }
      ctx.beginPath(); ctx.moveTo(bx - 3, top + bh); ctx.lineTo(bx - 3, top + bh + 18); ctx.moveTo(bx + 3, top + bh); ctx.lineTo(bx + 3, top + bh + 18); ctx.stroke();
      if (Math.floor(V * 10) % 3 === 0 && V < Vm) { ctx.fillStyle = "rgba(160,210,255,0.8)"; ctx.beginPath(); ctx.arc(bx, top + bh + 30, 3, 0, 7); ctx.fill(); }
      const fy = top + bh + 50, fw = 110, fh = Math.min(120, h - fy - 30);
      ctx.fillStyle = colour(ph); ctx.beginPath(); ctx.moveTo(bx - 18, fy); ctx.lineTo(bx - fw / 2, fy + fh); ctx.lineTo(bx + fw / 2, fy + fh); ctx.lineTo(bx + 18, fy); ctx.closePath(); ctx.fill();
      ctx.strokeStyle = C.text; ctx.stroke();
      text(ctx, `pH ${fmt(ph, 3)}`, bx, fy + fh + 16, C.text, 13, "center", "600");
      const r = { x: 210, y: 36, w: w - 250, h: h - 84 }, { X, Y } = axes(ctx, r, [0, Vm], [0, 14], "titrant added (mL)", "pH");
      if (v.pH_half !== undefined) { ctx.fillStyle = C.teal + "18"; ctx.fillRect(X(v.V_eq * 0.1), r.y, X(v.V_eq * 0.9) - X(v.V_eq * 0.1), r.h); text(ctx, "buffer region", X(v.V_eq / 2), r.y + 12, C.teal, 11, "center"); }
      curve(ctx, C_, X, Y, "#2a6f8f", 1.5); curve(ctx, C_, X, Y, C.cyan, 2.6, V);
      const eqLit = hl.equivalence || (hl.V !== undefined && Math.abs(hl.V - v.V_eq) < 1e-6);
      ctx.fillStyle = eqLit ? C.amber : "#6b5a2f"; ctx.beginPath(); ctx.arc(X(v.V_eq), Y(v.pH_eq), eqLit ? 6 : 4, 0, 7); ctx.fill();
      text(ctx, `equivalence: ${v.V_eq_shown} mL, pH ${fmt(v.pH_eq, 3)}`, X(v.V_eq) + 10, Y(v.pH_eq) + 14, eqLit ? C.amber : C.muted, 12, "left", eqLit ? "600" : "");
      if (v.pH_half !== undefined) { const lit = hl.half; ctx.fillStyle = lit ? C.green : "#2f6b55"; ctx.beginPath(); ctx.arc(X(v.V_eq / 2), Y(v.pH_half), lit ? 6 : 4, 0, 7); ctx.fill();
        text(ctx, `half-way: pH = pK = ${fmt(v.pH_half, 3)}`, X(v.V_eq / 2) + 10, Y(v.pH_half) - 14, lit ? C.green : C.muted, 12, "left", lit ? "600" : ""); }
      ctx.strokeStyle = C.amber; ctx.beginPath(); ctx.moveTo(X(V), r.y); ctx.lineTo(X(V), r.y + r.h); ctx.stroke();
      text(ctx, `${fmt(V)} mL of ${fmt(v.titrant_C)} mol/L added`, r.x, 14, C.text, 12);
    } };
  }
  function energyView(v) {
    let ball = 0;
    return { timed: false, draw(ctx, w, h, dt, t, hl) {
      ball = (ball + dt * 0.18) % 1;
      const lo = Math.min(0, v.dH), hi = v.Ea * 1.2, r = { x: 70, y: 30, w: w - 120, h: h - 80 };
      const Y = e => r.y + r.h - (e - lo) / (hi - lo) * r.h, X = s => r.x + s * r.w;
      const E = (s, peak) => s < 0.2 ? 0 : s > 0.8 ? v.dH : s < 0.5 ? peak * (1 - Math.cos(Math.PI * (s - 0.2) / 0.3)) / 2
        : v.dH + (peak - v.dH) * (1 + Math.cos(Math.PI * (s - 0.5) / 0.3)) / 2;
      ctx.strokeStyle = C.line; ctx.beginPath(); ctx.moveTo(r.x, r.y); ctx.lineTo(r.x, r.y + r.h); ctx.lineTo(r.x + r.w, r.y + r.h); ctx.stroke();
      text(ctx, `energy (${v.unit})`, r.x, r.y - 12, C.cyan, 11, "left", "600"); text(ctx, "progress of reaction →", r.x + r.w, r.y + r.h + 16, C.muted, 11, "right");
      const show = k => !hl.show || hl.show.includes(k);
      const path = peak => { ctx.beginPath(); for (let k = 0; k <= 200; k++) { const s = k / 200; k ? ctx.lineTo(X(s), Y(E(s, peak))) : ctx.moveTo(X(s), Y(E(s, peak))); } ctx.stroke(); };
      ctx.strokeStyle = C.cyan; ctx.lineWidth = 2.6; path(v.Ea);
      if (v.Ea_cat && show("catalyst")) { ctx.strokeStyle = C.green; ctx.setLineDash([6, 5]); ctx.lineWidth = 2; path(v.Ea_cat); ctx.setLineDash([]);
        text(ctx, `with a catalyst: Ea = ${fmt(v.Ea_cat)} ${v.unit}`, X(0.5), Y(v.Ea_cat) + 18, C.green, 12, "center"); }
      text(ctx, v.reactants, X(0.1), Y(0) - 12, C.text, 13, "center", "600"); text(ctx, v.products, X(0.9), Y(v.dH) - 12, C.text, 13, "center", "600");
      if (show("Ea")) { arrow(ctx, X(0.3), Y(0), X(0.3), Y(v.Ea), C.amber, 2, 8); text(ctx, `Ea = ${fmt(v.Ea)} ${v.unit}`, X(0.3) - 8, (Y(0) + Y(v.Ea)) / 2, C.amber, 13, "right", "600"); }
      if (show("dH")) { ctx.strokeStyle = C.muted; ctx.setLineDash([3, 4]); ctx.beginPath(); ctx.moveTo(X(0.1), Y(0)); ctx.lineTo(X(0.95), Y(0)); ctx.stroke(); ctx.setLineDash([]);
        arrow(ctx, X(0.93), Y(0), X(0.93), Y(v.dH), v.dH < 0 ? C.pink : C.violet, 2, 8);
        text(ctx, `ΔH = ${fmt(v.dH)} ${v.unit} (${v.dH < 0 ? "exothermic" : "endothermic"})`, X(0.91), (Y(0) + Y(v.dH)) / 2, v.dH < 0 ? C.pink : C.violet, 13, "right", "600"); }
      ctx.fillStyle = C.amber; ctx.beginPath(); ctx.arc(X(ball), Y(E(ball, v.Ea)) - 6, 5, 0, 7); ctx.fill();
    } };
  }
  function iceView(v) {
    let age = 0, lastKey = "";
    return { timed: false, draw(ctx, w, h, dt, t, hl) {
      const key = JSON.stringify(hl); if (key !== lastKey) { lastKey = key; age = 0; } age += dt;
      const g = clamp(age / 1.2, 0, 1), rows = v.rows, cw = Math.min(110, (w - 140) / rows.length), x0 = 120, y0 = 40;
      const labels = [["Initial", "initial"], ["Change", "change"], ["Equilibrium", "eq"]];
      rows.forEach((s, i) => text(ctx, `${s.coef !== 1 ? fmt(s.coef) : ""}${s.name}`, x0 + cw * (i + 0.5), y0, s.side === "product" ? C.amber : C.cyan, 14, "center", "600"));
      labels.forEach(([lab, k], j) => { const y = y0 + 28 + j * 26, lit = hl.row === lab.toLowerCase() || (hl.row === "equilibrium" && k === "eq");
        if (lit) { ctx.fillStyle = "#12314a"; ctx.fillRect(10, y - 12, x0 + cw * rows.length - 10, 24); }
        text(ctx, lab, 20, y, lit ? "#fff" : C.muted, 13);
        rows.forEach((s, i) => text(ctx, (k === "change" && s[k] > 0 ? "+" : "") + fmt(s[k]), x0 + cw * (i + 0.5), y, lit ? "#fff" : C.text, 13, "center")); });
      const top = y0 + 120, bh = h - top - 40, max = Math.max(1e-9, ...rows.map(s => Math.max(s.initial, s.eq)));
      rows.forEach((s, i) => { const val = s.initial + (s.eq - s.initial) * g, bx = x0 + cw * i + cw * 0.2, bw2 = cw * 0.6;
        ctx.fillStyle = (s.side === "product" ? C.amber : C.cyan) + "aa"; ctx.fillRect(bx, top + bh - val / max * bh, bw2, val / max * bh);
        ctx.strokeStyle = C.muted; ctx.setLineDash([3, 3]); ctx.strokeRect(bx, top + bh - s.initial / max * bh, bw2, 0.5); ctx.setLineDash([]);
        text(ctx, fmt(val), bx + bw2 / 2, top + bh + 14, C.text, 12, "center"); });
      if (v.K_shown) text(ctx, `K = ${v.K_shown}   (x = ${fmt(v.x)} ${v.unit})`, 20, 14, C.green, 13, "left", "600");
    } };
  }
  // ---- modern physics, quantum computing, linear algebra, statistics, fields, molecules, particles ----
  function changed(hl, state) { const k = JSON.stringify(hl); if (k !== state.key) { state.key = k; state.age = 0; return true; } return false; }
  function quantumView(v) {
    const st = { key: "", age: 0 }; let tau = 0;
    const cols = [C.cyan, C.amber, C.green, C.violet, C.pink, C.teal];
    return { timed: false, draw(ctx, w, h, dt, t, hl) {
      changed(hl, st); st.age += dt; tau += dt;
      if (v.system === "hydrogen") return hydrogen(ctx, w, h, hl);
      const r = { x: 60, y: 30, w: w - 190, h: h - 70 }, prob = hl.show && hl.show.includes("prob");
      const xs = v.x, x0 = xs[0], x1 = xs[xs.length - 1], X = x => r.x + (x - x0) / (x1 - x0) * r.w;
      if (v.system === "barrier") {
        const V0 = v.V0, E = v.E, Y = e => r.y + r.h - e / (V0 * 1.6) * r.h;
        ctx.fillStyle = "#1a2c40"; ctx.fillRect(X(0), Y(V0), X(v.a) - X(0), r.y + r.h - Y(V0));
        text(ctx, `V₀ = ${fmt(V0 / 1.602e-19)} eV`, X(v.a) + 8, Y(V0), C.muted, 12);
        ctx.strokeStyle = C.amber; ctx.setLineDash([5, 4]); ctx.beginPath(); ctx.moveTo(r.x, Y(E)); ctx.lineTo(r.x + r.w, Y(E)); ctx.stroke(); ctx.setLineDash([]);
        text(ctx, `E = ${v.E_shown[0]}`, r.x + 4, Y(E) - 10, C.amber, 12);
        const amp = r.h * 0.18, ph = tau * 2.5, mid = Y(E);
        ctx.strokeStyle = C.cyan; ctx.lineWidth = 2.2; ctx.beginPath();
        xs.forEach((x, i) => { const [re, im] = v.psi[i], val = re * Math.cos(ph) + im * Math.sin(ph); i ? ctx.lineTo(X(x), mid - val * amp) : ctx.moveTo(X(x), mid - val * amp); }); ctx.stroke();
        ctx.strokeStyle = C.pink + "aa"; ctx.lineWidth = 1.6; ctx.beginPath();
        xs.forEach((x, i) => { const [re, im] = v.psi[i], p2 = (re * re + im * im) * 0.5; i ? ctx.lineTo(X(x), mid - p2 * amp) : ctx.moveTo(X(x), mid - p2 * amp); }); ctx.stroke();
        text(ctx, `transmitted T = ${v.T_shown}   reflected R = ${fmt(v.R)}   (T + R = 1)`, 14, 16, C.text, 13, "left", "600");
        text(ctx, "— Re ψ (moving)   — |ψ|²", r.x + r.w, 16, C.muted, 12, "right"); return;
      }
      const Es = v.E, top = Math.max(...Es) * 1.25, Y = e => r.y + r.h - e / top * r.h;
      ctx.strokeStyle = C.text; ctx.lineWidth = 2;
      if (v.system === "box") { ctx.beginPath(); ctx.moveTo(X(x0), r.y); ctx.lineTo(X(x0), r.y + r.h); ctx.lineTo(X(x1), r.y + r.h); ctx.lineTo(X(x1), r.y); ctx.stroke(); }
      else { ctx.strokeStyle = C.muted; ctx.beginPath(); xs.forEach((x, i) => { const y = Y(Math.min(v.V[i], top)); i ? ctx.lineTo(X(x), y) : ctx.moveTo(X(x), y); }); ctx.stroke(); }
      const peak = Math.max(...v.psi.flat().map(Math.abs)), Hpx = r.h / Es.length * 0.42, amp = Hpx / peak;
      const sup = hl.time && v.superpose && v.superpose.length >= 2 ? v.superpose : null;
      v.levels.forEach((n, k) => {
        const lit = hl.level === undefined || hl.level === n, y0 = Y(Es[k]), col = lit ? cols[k % cols.length] : "#2a4258";
        ctx.strokeStyle = col + (sup ? "55" : ""); ctx.setLineDash([4, 4]); ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(r.x, y0); ctx.lineTo(r.x + r.w, y0); ctx.stroke(); ctx.setLineDash([]);
        if (!sup) { ctx.strokeStyle = col; ctx.lineWidth = lit ? 2.4 : 1.4; ctx.beginPath();
          xs.forEach((x, i) => { const p = v.psi[k][i], y = y0 - (prob ? p * p / (peak * peak) * Hpx : p * amp); i ? ctx.lineTo(X(x), y) : ctx.moveTo(X(x), y); }); ctx.stroke(); }
        text(ctx, `n = ${n}: ${v.E_shown[k]}`, r.x + r.w + 4, y0, col, 11);
      });
      if (sup) { // the superposition's |Ψ|² sloshing: phases e^{-iEt/ħ}, one beat of the first two in 3 s
        const E0 = Es[sup[0]], dE = Math.abs(Es[sup[1]] - E0) || 1, c = 1 / Math.sqrt(sup.length), yb = Y((Es[sup[0]] + Es[sup[1]]) / 2);
        ctx.strokeStyle = C.amber; ctx.lineWidth = 2.6; ctx.beginPath();
        xs.forEach((x, i) => { let re = 0, im = 0; for (const k of sup) { const ph = -2 * Math.PI * (Es[k] - E0) / dE * tau / 3; re += c * v.psi[k][i] * Math.cos(ph); im += c * v.psi[k][i] * Math.sin(ph); }
          const y = yb - (re * re + im * im) / (peak * peak) * Hpx * 1.6; i ? ctx.lineTo(X(x), y) : ctx.moveTo(X(x), y); }); ctx.stroke();
        text(ctx, `|Ψ|² of a superposition of n = ${sup.map(k => v.levels[k]).join(" and ")}: it sloshes back and forth`, 14, 16, C.amber, 13, "left", "600");
      } else text(ctx, prob ? "|ψ|²: where the particle is likely to be found" : "ψ for each level, drawn at its energy", 14, 16, C.text, 13, "left", "600");
    } };
    function hydrogen(ctx, w, h, hl) {
      const r = { x: 40, y: 34, w: w * 0.42, h: h - 70 }, Es = v.E_eV, lo = Math.min(...Es) * 1.08, Y = e => r.y + r.h - (e - lo) / (0 - lo) * r.h;
      text(ctx, "energy (eV)", r.x, r.y - 14, C.cyan, 11, "left", "600");
      ctx.strokeStyle = C.muted; ctx.setLineDash([3, 4]); ctx.beginPath(); ctx.moveTo(r.x, Y(0)); ctx.lineTo(r.x + r.w, Y(0)); ctx.stroke(); ctx.setLineDash([]); text(ctx, "0 (free)", r.x + r.w, Y(0) - 8, C.muted, 10, "right");
      v.levels.forEach((n, k) => { const lit = hl.level === undefined || hl.level === n; ctx.strokeStyle = lit ? cols[k % cols.length] : "#2a4258"; ctx.lineWidth = 2;
        ctx.beginPath(); ctx.moveTo(r.x + 40, Y(Es[k])); ctx.lineTo(r.x + r.w, Y(Es[k])); ctx.stroke(); text(ctx, `n = ${n}   ${v.E_shown[k]}`, r.x + 44, Y(Es[k]) - 9, lit ? C.text : C.muted, 11); });
      if (v.transition) { const tr = v.transition, a = v.levels.indexOf(tr.from), b = v.levels.indexOf(tr.to);
        if (a >= 0 && b >= 0) { const xx = r.x + r.w * 0.6, colour = { violet: "#a070ff", blue: "#4d7dff", green: "#56e07a", yellow: "#ffe45c", orange: "#ffa040", red: "#ff4d4d" }[tr.colour] || C.muted;
          arrow(ctx, xx, Y(Es[a]), xx, Y(Es[b]), colour, 3, 10);
          ctx.strokeStyle = colour; ctx.lineWidth = 2; ctx.beginPath(); for (let k = 0; k <= 60; k++) { const px = xx + 10 + k * 1.6, py = (Y(Es[a]) + Y(Es[b])) / 2 + Math.sin(k * 0.6 - st.age * 8) * 6; k ? ctx.lineTo(px, py) : ctx.moveTo(px, py); } ctx.stroke();
          text(ctx, `photon: ${tr.shown} (${tr.colour}), ΔE = ${fmt(tr.dE_eV)} eV`, xx + 10, (Y(Es[a]) + Y(Es[b])) / 2 - 18, colour, 12, "left", "600"); } }
      const g = { x: w * 0.55, y: 34, w: w * 0.4, h: h - 80 }, all = v.radial.flatMap(c => c.P), pm = Math.max(...all) || 1, rmax = 25;
      const { X, Y: GY } = axes(ctx, g, [0, rmax], [0, pm * 1.1], "r / a₀", "P(r) = r²R²");
      v.radial.forEach((c, k) => curve(ctx, c.r.map((rr, i) => [rr / v.a0, c.P[i]]), X, GY, cols[v.levels.indexOf(c.n) % cols.length], 2.2));
      text(ctx, `hydrogen${v.Z > 1 ? " (Z = " + v.Z + ")" : ""}: radial probability, l = ${v.l}`, g.x, 16, C.text, 12, "left", "600");
    }
  }
  function blochAt(ctx, cx, cy, R, b, label) {
    ctx.strokeStyle = "#2a5878"; ctx.lineWidth = 1.2; ctx.beginPath(); ctx.arc(cx, cy, R, 0, 7); ctx.stroke();
    ctx.beginPath(); ctx.ellipse(cx, cy, R, R * 0.3, 0, 0, 7); ctx.stroke();
    const P = (x, y, z) => [cx + (x * 0.94 + y * 0.34) * R, cy + (-z * 0.94 + y * 0.18) * R];
    text(ctx, "|0⟩", cx, cy - R - 10, C.muted, 11, "center"); text(ctx, "|1⟩", cx, cy + R + 11, C.muted, 11, "center");
    const [ex, ey] = P(1, 0, 0); text(ctx, "+x", ex + 12, ey, C.muted, 10);
    const [bx, by] = P(b[0], b[1], b[2]), len = Math.hypot(...b);
    if (len < 0.05) { text(ctx, "entangled: no direction of its own", cx, cy + R + 26, C.pink, 11, "center"); ctx.fillStyle = C.pink; ctx.beginPath(); ctx.arc(cx, cy, 4, 0, 7); ctx.fill(); }
    else arrow(ctx, cx, cy, bx, by, C.amber, 2.6, 9);
    text(ctx, label, cx, cy - R - 26, C.text, 12, "center", "600");
  }
  function qcircuitView(v) {
    let shown = v.states[v.states.length - 1], from = shown, mix = 1, lastStep = -1;
    const lerp = (a, b, f) => a.map((x, i) => x + (b[i] - x) * f);
    return { timed: false, draw(ctx, w, h, dt, t, hl) {
      const step = hl.gate === undefined ? v.gates.length : clamp(Math.round(hl.gate), 0, v.gates.length);
      if (step !== lastStep) { from = lastStep < 0 ? v.states[step] : { probs: shown.probs, bloch: shown.bloch }; lastStep = step; mix = 0; }
      mix = clamp(mix + dt / 0.6, 0, 1); const target = v.states[step];
      shown = { probs: lerp(from.probs, target.probs, mix), bloch: target.bloch.map((b, q) => lerp(from.bloch[q], b, mix)), amps: target.amps };
      const nq = v.qubits, top = 40, gap = Math.min(46, (h * 0.42) / nq), colW = Math.min(80, (w - 160) / Math.max(1, v.gates.length + 1));
      for (let q = 0; q < nq; q++) { const y = top + q * gap; ctx.strokeStyle = "#3a6f93"; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.moveTo(70, y); ctx.lineTo(80 + colW * (v.gates.length + 1), y); ctx.stroke();
        text(ctx, `q${q} |${(v.initial || "")[q] || "0"}⟩`, 20, y, C.muted, 12); }
      v.gates.forEach((g, i) => { const x = 80 + colW * (i + 1), done = i < step, col = done ? C.cyan : "#35506a";
        if (g.qubits.length > 1) { const ys = g.qubits.map(q => top + q * gap); ctx.strokeStyle = col; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(x, Math.min(...ys)); ctx.lineTo(x, Math.max(...ys)); ctx.stroke();
          const ctrl = g.name === "SWAP" ? [] : g.qubits.slice(0, -1), tq = g.qubits[g.qubits.length - 1];
          ctrl.forEach(q => { ctx.fillStyle = col; ctx.beginPath(); ctx.arc(x, top + q * gap, 5, 0, 7); ctx.fill(); });
          if (g.name === "SWAP") g.qubits.forEach(q => text(ctx, "×", x, top + q * gap, col, 18, "center", "600"));
          else if (g.name === "CZ") { ctx.fillStyle = col; ctx.beginPath(); ctx.arc(x, top + tq * gap, 5, 0, 7); ctx.fill(); }
          else { ctx.strokeStyle = col; ctx.beginPath(); ctx.arc(x, top + tq * gap, 10, 0, 7); ctx.moveTo(x - 10, top + tq * gap); ctx.lineTo(x + 10, top + tq * gap); ctx.moveTo(x, top + tq * gap - 10); ctx.lineTo(x, top + tq * gap + 10); ctx.stroke(); } }
        else { const y = top + g.qubits[0] * gap; ctx.fillStyle = done ? "#12405e" : C.bg; ctx.strokeStyle = col; ctx.lineWidth = 2; ctx.fillRect(x - 16, y - 14, 32, 28); ctx.strokeRect(x - 16, y - 14, 32, 28);
          text(ctx, g.name, x, y, done ? "#fff" : C.muted, 12, "center", "600"); if (g.angle !== null) text(ctx, g.angle_shown, x, y + 22, C.muted, 9, "center"); } });
      const cx = 80 + colW * (step + 0.5); ctx.strokeStyle = C.amber; ctx.setLineDash([4, 4]); ctx.beginPath(); ctx.moveTo(cx, top - 20); ctx.lineTo(cx, top + (nq - 1) * gap + 20); ctx.stroke(); ctx.setLineDash([]);
      text(ctx, step === 0 ? "the start" : `after gate ${step} (${v.gates[step - 1].name})`, cx + 6, top - 24, C.amber, 12, "left", "600");
      // probabilities, coloured by each amplitude's phase
      const by = top + nq * gap + 30, bh = h - by - 40, bw = Math.min(60, (w * 0.55) / v.labels.length);
      v.labels.forEach((lab, i) => { const p = shown.probs[i], x = 30 + i * (bw + 6), [re, im] = shown.amps[i], ph = Math.atan2(im, re);
        ctx.fillStyle = `hsl(${Math.round((ph / Math.PI * 180 + 360) % 360)},80%,60%)`; ctx.fillRect(x, by + bh - p * bh, bw, p * bh);
        ctx.strokeStyle = C.line; ctx.strokeRect(x, by, bw, bh); text(ctx, `|${lab}⟩`, x + bw / 2, by + bh + 12, C.text, 11, "center");
        if (p > 0.005) text(ctx, fmt(p), x + bw / 2, by + bh - p * bh - 9, C.text, 11, "center"); });
      text(ctx, "measurement probabilities (colour: the amplitude's phase)", 30, by - 12, C.muted, 11);
      const R = Math.min(70, (w * 0.4) / nq / 2.4, bh / 2.6);
      shown.bloch.forEach((b, q) => blochAt(ctx, w * 0.62 + q * R * 2.6 + R, by + bh / 2, R, b, `qubit ${q}`));
    } };
  }
  function minkowskiView(v) {
    let now = 0;
    return { timed: false, draw(ctx, w, h, dt, t, hl) {
      const S = v.span, side = Math.min(w - 80, h - 60), ox = (w - side) / 2 + 20, oy = 30, half = side / 2;
      const X = x => ox + half + x / S * half, Y = ct => oy + side - (ct + S * 0) / S * side * 0.98 - 6;
      now = (now + dt * S / 8) % S;
      ctx.strokeStyle = C.line; for (let k = -Math.floor(S); k <= S; k += Math.max(1, Math.round(S / 8))) { ctx.beginPath(); ctx.moveTo(X(k), Y(0)); ctx.lineTo(X(k), Y(S)); ctx.stroke(); ctx.beginPath(); ctx.moveTo(X(-S), Y(Math.abs(k))); ctx.lineTo(X(S), Y(Math.abs(k))); ctx.stroke(); }
      ctx.strokeStyle = "#5a7a94"; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.moveTo(X(-S), Y(0)); ctx.lineTo(X(S), Y(0)); ctx.moveTo(X(0), Y(0)); ctx.lineTo(X(0), Y(S)); ctx.stroke();
      text(ctx, `x ${v.unit ? "(" + v.unit + ")" : ""}`, X(S) - 4, Y(0) + 14, C.muted, 12, "right"); text(ctx, `ct ${v.unit ? "(" + v.unit + ")" : ""}`, X(0) + 6, Y(S) + 8, C.muted, 12);
      ctx.fillStyle = C.amber + "14"; ctx.beginPath(); ctx.moveTo(X(0), Y(0)); ctx.lineTo(X(S), Y(S)); ctx.lineTo(X(-S), Y(S)); ctx.closePath(); ctx.fill();
      ctx.strokeStyle = C.amber; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.moveTo(X(0), Y(0)); ctx.lineTo(X(S), Y(S)); ctx.moveTo(X(0), Y(0)); ctx.lineTo(X(-S), Y(S)); ctx.stroke();
      text(ctx, "light (x = ±ct)", X(S * 0.72), Y(S * 0.8), C.amber, 11);
      if (v.beta) { const b = v.beta, g = v.gamma, frame = hl.frame !== false;
        ctx.strokeStyle = C.green; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(X(0), Y(0)); ctx.lineTo(X(b * S), Y(S)); ctx.moveTo(X(-S), Y(Math.max(0, -b * S))); ctx.lineTo(X(S), Y(b * S)); ctx.stroke();
        text(ctx, `ct' (frame at ${fmt(b)}c, γ = ${v.gamma_shown})`, X(b * S) + 6, Y(S) + 14, C.green, 12, "left", "600"); text(ctx, "x'", X(S) - 10, Y(b * S) - 10, C.green, 12, "right", "600");
        if (frame) { ctx.save(); ctx.beginPath(); ctx.rect(X(-S), Y(S), side, side); ctx.clip();
          ctx.strokeStyle = C.green + "33"; ctx.lineWidth = 1; const step = Math.max(1, Math.round(S / 6));
          for (let k = step; k < S * 1.5; k += step) { // lines of constant ct' = k: ct - b x = k / g ; constant x' = k: x - b ct = k / g
            ctx.beginPath(); ctx.moveTo(X(-S), Y(k / g - b * S)); ctx.lineTo(X(S), Y(k / g + b * S)); ctx.stroke();
            for (const sgn of [1, -1]) { ctx.beginPath(); ctx.moveTo(X(sgn * k / g), Y(0)); ctx.lineTo(X(sgn * k / g + b * S), Y(S)); ctx.stroke(); } }
          ctx.restore(); } }
      ctx.save(); ctx.beginPath(); ctx.rect(X(-S), Y(S), side, side); ctx.clip();
      v.worldlines.forEach((wl, i) => { const col = [C.cyan, C.pink, C.violet, C.teal][i % 4]; ctx.strokeStyle = col; ctx.lineWidth = 2.6; ctx.beginPath();
        wl.points.forEach(([x, ct], k) => k ? ctx.lineTo(X(x), Y(ct)) : ctx.moveTo(X(x), Y(ct))); ctx.stroke();
        text(ctx, `${wl.name}: proper time τ = ${wl.tau_shown}${v.unit ? " " + (v.unit === "ly" ? "years" : v.unit) : ""}`, X(-S) + 8, Y(S) + 14 + i * 16, col, 12, "left", "600");
        for (let k = 1; k < wl.points.length; k++) { const [xa, ca] = wl.points[k - 1], [xb, cb] = wl.points[k]; if (now >= ca && now <= cb) { const f = (now - ca) / ((cb - ca) || 1);
          ctx.fillStyle = col; ctx.beginPath(); ctx.arc(X(xa + (xb - xa) * f), Y(now), 5, 0, 7); ctx.fill(); } } });
      ctx.restore();
      v.events.forEach(e => { const lit = !hl.event || hl.event === e.name; ctx.fillStyle = lit ? "#fff" : C.muted; ctx.beginPath(); ctx.arc(X(e.x), Y(e.ct), lit ? 6 : 4, 0, 7); ctx.fill();
        text(ctx, `${e.name} (x ${fmt(e.x)}, ct ${fmt(e.ct)})${v.beta ? `  →  (x' ${fmt(e.x2)}, ct' ${fmt(e.ct2)})` : ""}`, X(e.x) + 9, Y(e.ct) - 10, lit ? C.text : C.muted, 12, "left", lit && hl.event ? "600" : "");
        if (hl.simultaneity && lit && v.beta) { const k = e.ct - v.beta * e.x; ctx.strokeStyle = C.green; ctx.setLineDash([6, 4]); ctx.beginPath(); ctx.moveTo(X(-S), Y(k - v.beta * S)); ctx.lineTo(X(S), Y(k + v.beta * S)); ctx.stroke(); ctx.setLineDash([]);
          text(ctx, "simultaneous with it in the moving frame", X(S * 0.2), Y(k + v.beta * S * 0.2) - 10, C.green, 11); } });
    } };
  }
  function blackHoleView(v) {
    let ang = 0;
    return { timed: false, draw(ctx, w, h, dt, t, hl) {
      ang += dt * 0.9; const cx = w / 2, cy = h * 0.3, R = Math.min(w * 0.42, h * 0.9), rs = 1, rmax = 8;
      const depth = r => 2 * Math.sqrt(rs * (r - rs)), dmax = depth(rmax), sc = R / rmax;
      for (let k = 0; k <= 22; k++) { const r = rs + (rmax - rs) * Math.pow(k / 22, 1.6), z = (dmax - depth(r)) * sc * 0.55;
        ctx.strokeStyle = `rgba(77,225,255,${0.12 + 0.4 * (1 - k / 22)})`; ctx.lineWidth = 1.2; ctx.beginPath(); ctx.ellipse(cx, cy + z, r * sc, r * sc * 0.28, 0, 0, 7); ctx.stroke(); }
      for (let a = 0; a < 16; a++) { const th = a / 16 * Math.PI * 2; ctx.strokeStyle = "rgba(77,225,255,0.18)"; ctx.beginPath();
        for (let k = 0; k <= 30; k++) { const r = rs + (rmax - rs) * Math.pow(k / 30, 1.6), z = (dmax - depth(r)) * sc * 0.55; const px = cx + Math.cos(th) * r * sc, py = cy + z + Math.sin(th) * r * sc * 0.28; k ? ctx.lineTo(px, py) : ctx.moveTo(px, py); } ctx.stroke(); }
      const ring = (r, col, lab, lit) => { const z = (dmax - depth(Math.max(r, rs + 1e-6))) * sc * 0.55; ctx.strokeStyle = col; ctx.lineWidth = lit ? 3 : 2; ctx.beginPath(); ctx.ellipse(cx, cy + z, r * sc, r * sc * 0.28, 0, 0, 7); ctx.stroke();
        text(ctx, lab, cx + r * sc + 8, cy + z, col, 12, "left", "600"); return z; };
      const show = k => !hl.show || hl.show.includes(k);
      ring(rs, C.red, `event horizon r_s = ${v.rs_shown}`, true);
      if (show("photon")) ring(1.5, C.amber, "photon sphere 1.5 r_s", hl.show && hl.show.includes("photon"));
      const zi = show("isco") ? ring(3, C.green, "innermost stable orbit 3 r_s", hl.show && hl.show.includes("isco")) : 0;
      if (show("isco")) { ctx.fillStyle = C.green; ctx.beginPath(); ctx.arc(cx + Math.cos(ang) * 3 * sc, cy + zi + Math.sin(ang) * 3 * sc * 0.28, 5, 0, 7); ctx.fill(); }
      text(ctx, `mass ${fmt(v.M)} kg   ·   Hawking temperature ${v.T_shown}   ·   evaporates in ${fmt(v.lifetime_s / 3.156e7)} years`, 14, 16, C.text, 12, "left", "600");
      text(ctx, "space near the hole, drawn as a funnel (Flamm's paraboloid): steeper means more curved", 14, h - 14, C.muted, 11);
    } };
  }
  function matrixView(v) {
    const st = { key: "", age: 0 }, A = v.A;
    return { timed: false, draw(ctx, w, h, dt, t, hl) {
      changed(hl, st); st.age += dt; const s = hl.t !== undefined ? clamp(hl.t, 0, 1) : (1 - Math.cos(Math.min(st.age / 2.2, 1) * Math.PI)) / 2;
      const M = [[1 + (A[0][0] - 1) * s, A[0][1] * s], [A[1][0] * s, 1 + (A[1][1] - 1) * s]], ap = (p) => [M[0][0] * p[0] + M[0][1] * p[1], M[1][0] * p[0] + M[1][1] * p[1]];
      const ext = Math.max(3, ...A.flat().map(Math.abs).map(x => x * 2)), sc = Math.min(w, h) / (2 * ext + 1), cx = w / 2, cy = h / 2, P = p => [cx + p[0] * sc, cy - p[1] * sc];
      ctx.strokeStyle = "#162a3c"; for (let k = -ext; k <= ext; k++) { ctx.beginPath(); ctx.moveTo(...P([k, -ext])); ctx.lineTo(...P([k, ext])); ctx.moveTo(...P([-ext, k])); ctx.lineTo(...P([ext, k])); ctx.stroke(); }
      ctx.strokeStyle = C.cyan + "55"; ctx.lineWidth = 1; for (let k = -ext; k <= ext; k++) { ctx.beginPath(); ctx.moveTo(...P(ap([k, -ext]))); ctx.lineTo(...P(ap([k, ext]))); ctx.moveTo(...P(ap([-ext, k]))); ctx.lineTo(...P(ap([ext, k]))); ctx.stroke(); }
      const show = k => !hl.show || hl.show.includes(k);
      if (show("det")) { ctx.fillStyle = C.amber + "40"; ctx.beginPath(); [[0, 0], [1, 0], [1, 1], [0, 1]].map(ap).forEach((p, i) => i ? ctx.lineTo(...P(p)) : ctx.moveTo(...P(p))); ctx.closePath(); ctx.fill();
        text(ctx, `area = |det A| = ${fmt(Math.abs(v.det))}${v.det < 0 ? " (flipped)" : ""}`, ...P(ap([1.1, 1.1])), C.amber, 13, "left", "600"); }
      arrow(ctx, ...P([0, 0]), ...P(ap([1, 0])), C.green, 3, 10); arrow(ctx, ...P([0, 0]), ...P(ap([0, 1])), C.pink, 3, 10);
      text(ctx, "A î", ...P(ap([1.08, -0.15])), C.green, 12, "left", "600"); text(ctx, "A ĵ", ...P(ap([-0.3, 1.1])), C.pink, 12, "left", "600");
      if (show("eigen")) v.eigen.forEach((e, i) => { const d = e.vector, L = ext * 1.5; ctx.strokeStyle = C.violet; ctx.setLineDash([6, 5]); ctx.beginPath(); ctx.moveTo(...P([-d[0] * L, -d[1] * L])); ctx.lineTo(...P([d[0] * L, d[1] * L])); ctx.stroke(); ctx.setLineDash([]);
        const lam = 1 + (e.value - 1) * s; arrow(ctx, ...P([0, 0]), ...P([d[0] * lam, d[1] * lam]), C.violet, 3.4, 10); text(ctx, `λ${i + 1} = ${e.shown}`, ...P([d[0] * lam * 1.08, d[1] * lam * 1.08]), C.violet, 13, "left", "600"); });
      v.vectors.forEach((p, i) => { arrow(ctx, ...P([0, 0]), ...P(ap(p)), C.teal, 2.4, 9); });
      text(ctx, `A = [[${A[0].map(x => fmt(x)).join(", ")}], [${A[1].map(x => fmt(x)).join(", ")}]]   det = ${v.det_shown}${v.complex_eigen ? "   (complex eigenvalues: it rotates)" : ""}`, 14, 16, C.text, 13, "left", "600");
    } };
  }
  function distributionView(v) {
    return { timed: false, draw(ctx, w, h, dt, t, hl) {
      const r = { x: 60, y: 40, w: w - 100, h: h - 90 };
      if (v.discrete) { const N = v.pmf.length, top = Math.max(...v.pmf) * 1.15, { X, Y } = axes(ctx, r, [-0.5, N - 0.5], [0, top], "k", "P(X = k)"), bw = Math.max(2, r.w / N * 0.7);
        v.pmf.forEach((p, k) => { const inR = k >= v.from - 1e-9 && k <= v.to + 1e-9; ctx.fillStyle = inR ? C.amber : "#2a6f8f"; ctx.fillRect(X(k) - bw / 2, Y(p), bw, Y(0) - Y(p)); }); }
      else { const top = Math.max(...v.curve.map(p => p[1])) * 1.15, { X, Y } = axes(ctx, r, v.x, [0, top], "x", "f(x)");
        const a = Math.max(v.x[0], v.from), b = Math.min(v.x[1], v.to), pts = v.curve.filter(p => p[0] >= a && p[0] <= b);
        ctx.fillStyle = C.amber + "55"; ctx.beginPath(); ctx.moveTo(X(a), Y(0)); pts.forEach(p => ctx.lineTo(X(p[0]), Y(p[1]))); ctx.lineTo(X(b), Y(0)); ctx.closePath(); ctx.fill();
        curve(ctx, v.curve, X, Y, C.cyan, 2.4);
        for (const e of [v.from, v.to]) if (isFinite(e) && e >= v.x[0] && e <= v.x[1]) { ctx.strokeStyle = C.amber; ctx.beginPath(); ctx.moveTo(X(e), Y(0)); ctx.lineTo(X(e), r.y); ctx.stroke(); text(ctx, fmt(e), X(e), r.y - 6, C.amber, 11, "center"); } }
      const range = `${isFinite(v.from) ? fmt(v.from) + " ≤ " : ""}X${isFinite(v.to) ? " ≤ " + fmt(v.to) : ""}`;
      text(ctx, `${v.dist}: P(${range}) = ${v.shown}`, 14, 16, C.amber, 14, "left", "600");
    } };
  }
  function montecarloView(v) {
    return { timed: true, T: v.n, unit: "points", draw(ctx, w, h, dt, t, hl) {
      const k = clamp(Math.round(t), 0, v.points.length), [x0, x1, y0, y1] = v.box, side = Math.min(w * 0.45, h - 70), bx = 30, by = 40;
      const X = x => bx + (x - x0) / (x1 - x0) * side, Y = y => by + side - (y - y0) / ((y1 - y0) || 1) * side;
      ctx.strokeStyle = C.line; ctx.strokeRect(bx, by, side, side);
      if (v.mc === "pi") { ctx.strokeStyle = C.amber; ctx.beginPath(); ctx.arc(X(0), Y(0), side, -Math.PI / 2, 0); ctx.stroke(); }
      else { curve(ctx, v.curve, X, Y, C.amber, 2.2); }
      for (let i = 0; i < k; i++) { const [px, py, inside] = v.points[i]; ctx.fillStyle = inside ? C.cyan : "#5a3a4a"; ctx.fillRect(X(px) - 1.3, Y(py) - 1.3, 2.6, 2.6); }
      const r = { x: bx + side + 70, y: 40, w: w - side - 130, h: h - 90 }, run = v.running.filter(p => p[0] <= Math.max(k, 1));
      const vals = v.running.map(p => p[1]), lo = Math.min(v.exact, ...vals), hi = Math.max(v.exact, ...vals), pad = (hi - lo) * 0.15 || 0.1;
      const { X: GX, Y: GY } = axes(ctx, r, [0, v.n], [lo - pad, hi + pad], "samples", "estimate");
      ctx.strokeStyle = C.green; ctx.setLineDash([5, 4]); ctx.beginPath(); ctx.moveTo(GX(0), GY(v.exact)); ctx.lineTo(GX(v.n), GY(v.exact)); ctx.stroke(); ctx.setLineDash([]);
      text(ctx, `exact ${v.exact_shown}`, GX(v.n), GY(v.exact) - 10, C.green, 12, "right");
      curve(ctx, run, GX, GY, C.cyan, 2.2);
      const cur = run.length ? run[run.length - 1][1] : 0;
      text(ctx, `${k} random points · estimate ${fmt(cur, 4)}   (all ${v.n}: ${v.shown})`, 14, 16, C.text, 13, "left", "600");
    } };
  }
  function fieldView(v) {
    const parts = Array.from({ length: 260 }, () => ({ x: Math.random(), y: Math.random(), age: Math.random() * 60 }));
    const mags = v.grid.map(g => Math.hypot(g[2], g[3])), mmax = Math.max(1e-9, ...mags);
    return { timed: false, draw(ctx, w, h, dt, t, hl) {
      const r = { x: 50, y: 34, w: w - 90, h: h - 74 }, { X, Y } = axes(ctx, r, v.x, v.y, "x", "y"), cw = r.w / 20;
      v.grid.forEach((g, i) => { const m = mags[i], ux = v.mode === "slope" ? 1 / Math.hypot(1, g[3]) : g[2] / (m || 1), uy = v.mode === "slope" ? g[3] / Math.hypot(1, g[3]) : g[3] / (m || 1);
        const L = cw * 0.4, px = X(g[0]), py = Y(g[1]), sx = (r.w / (v.x[1] - v.x[0])), sy = (r.h / (v.y[1] - v.y[0])), k = Math.hypot(ux * sx, uy * sy) || 1;
        const dx = ux * sx / k * L, dy = -uy * sy / k * L, col = v.mode === "slope" ? "#4a7a9a" : `hsl(${200 - 160 * m / mmax},80%,60%)`;
        if (v.mode === "slope") { ctx.strokeStyle = col; ctx.lineWidth = 1.4; ctx.beginPath(); ctx.moveTo(px - dx, py - dy); ctx.lineTo(px + dx, py + dy); ctx.stroke(); }
        else arrow(ctx, px - dx, py - dy, px + dx, py + dy, col, 1.4, 5); });
      if (v.mode === "slope") v.solutions.forEach((s, i) => curve(ctx, s, X, Y, [C.amber, C.green, C.pink, C.violet, C.teal][i % 5], 2.4));
      else { const near = (x, y) => { let best = null, bd = 1e18; for (const g of v.grid) { const d = (g[0] - x) ** 2 + (g[1] - y) ** 2; if (d < bd) { bd = d; best = g; } } return best; };
        ctx.fillStyle = C.amber; for (const p of parts) { const x = v.x[0] + p.x * (v.x[1] - v.x[0]), y = v.y[0] + p.y * (v.y[1] - v.y[0]), g = near(x, y);
          if (!g || ++p.age > 120) { p.x = Math.random(); p.y = Math.random(); p.age = 0; continue; }
          p.x += g[2] / mmax * dt * 0.12; p.y += g[3] / mmax * dt * 0.12; if (p.x < 0 || p.x > 1 || p.y < 0 || p.y > 1) { p.x = Math.random(); p.y = Math.random(); p.age = 0; }
          ctx.beginPath(); ctx.arc(X(x), Y(y), 2, 0, 7); ctx.fill(); }
        text(ctx, `div F = ${v.div}    curl F = ${v.curl}`, 14, 16, C.text, 13, "left", "600"); }
    } };
  }
  const CPK = { H: ["#f2f2f2", 0.32], C: ["#8a8f96", 0.5], N: ["#3a6bff", 0.48], O: ["#ff4d4d", 0.46], S: ["#ffe45c", 0.6], P: ["#ff9a40", 0.58],
    F: ["#7cf07c", 0.42], Cl: ["#40d040", 0.56], Br: ["#a52a2a", 0.6], I: ["#9a40c0", 0.64], Na: ["#ab5cf2", 0.62], Fe: ["#e06633", 0.6] };
  function moleculeView(v) {
    let ry = 0, rx = 0.35, drag = null;
    const span = Math.max(1, ...v.atoms.map(a => Math.hypot(a.x, a.y, a.z)));
    return { timed: false, attach(canvas) {
      canvas.addEventListener("pointerdown", e => { drag = [e.clientX, e.clientY, ry, rx]; canvas.setPointerCapture(e.pointerId); });
      canvas.addEventListener("pointermove", e => { if (drag) { ry = drag[2] + (e.clientX - drag[0]) * 0.01; rx = clamp(drag[3] + (e.clientY - drag[1]) * 0.01, -1.5, 1.5); } });
      canvas.addEventListener("pointerup", () => { drag = null; }); canvas.style.cursor = "grab"; canvas.style.pointerEvents = "auto"; },
      draw(ctx, w, h, dt) {
        if (!drag) ry += dt * 0.4;
        const sc = Math.min(w, h) * 0.42 / span, cx = w / 2, cy = h / 2 + 10, cyr = Math.cos(ry), syr = Math.sin(ry), cxr = Math.cos(rx), sxr = Math.sin(rx);
        const P = v.atoms.map(a => { const x1 = a.x * cyr + a.z * syr, z1 = -a.x * syr + a.z * cyr, y2 = a.y * cxr - z1 * sxr, z2 = a.y * sxr + z1 * cxr;
          const f = 1 / (1 + z2 / (span * 6)); return [cx + x1 * sc * f, cy - y2 * sc * f, z2, f]; });
        ctx.lineWidth = 3; for (const [a, b, order] of v.bonds) { const pa = P[a], pb = P[b]; if (!pa || !pb) continue; ctx.strokeStyle = "#9fb3c4";
          if (order >= 2) { const dx = pb[1] - pa[1], dy = pa[0] - pb[0], L = Math.hypot(dx, dy) || 1, o = 3.2;
            for (const s of order === 3 ? [-1, 0, 1] : [-0.5, 0.5]) { ctx.beginPath(); ctx.moveTo(pa[0] + dx / L * o * s * 2, pa[1] + dy / L * o * s * 2); ctx.lineTo(pb[0] + dx / L * o * s * 2, pb[1] + dy / L * o * s * 2); ctx.lineWidth = 2; ctx.stroke(); } ctx.lineWidth = 3; }
          else { ctx.beginPath(); ctx.moveTo(pa[0], pa[1]); ctx.lineTo(pb[0], pb[1]); ctx.stroke(); } }
        v.atoms.map((a, i) => i).sort((i, j) => P[i][2] - P[j][2]).forEach(i => { const [x, y, , f] = P[i], [col, rad] = CPK[v.atoms[i].el] || ["#ff7eb6", 0.5], R = rad * sc * 0.55 * f;
          const g = ctx.createRadialGradient(x - R * 0.35, y - R * 0.35, R * 0.1, x, y, R); g.addColorStop(0, "#ffffff"); g.addColorStop(0.25, col); g.addColorStop(1, "#05121e");
          ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, R, 0, 7); ctx.fill(); });
        text(ctx, `${v.name}   ${v.formula}   (${v.atoms.length} atoms; drag to turn)`, 14, 16, C.text, 13, "left", "600"); text(ctx, v.credit, w - 12, h - 12, C.muted, 10, "right");
        const els = [...new Set(v.atoms.map(a => a.el))]; els.forEach((e, k) => { const [col] = CPK[e] || ["#ff7eb6"]; ctx.fillStyle = col; ctx.beginPath(); ctx.arc(20, 40 + k * 18, 6, 0, 7); ctx.fill(); text(ctx, e, 32, 40 + k * 18, C.text, 12); });
      } };
  }
  function feynmanView(v) {
    let flow = 0;
    return { timed: false, draw(ctx, w, h, dt) {
      flow += dt;
      const pad = 60, X = x => pad + x * (w - 2 * pad), Y = y => h - pad - y * (h - 2 * pad);
      const verts = new Map();
      v.lines.forEach((l, i) => { const [x0, y0] = [X(l.from[0]), Y(l.from[1])], [x1, y1] = [X(l.to[0]), Y(l.to[1])], len = Math.hypot(x1 - x0, y1 - y0), ux = (x1 - x0) / len, uy = (y1 - y0) / len, nx = -uy, ny = ux;
        const col = { fermion: C.cyan, antifermion: C.cyan, photon: C.amber, gluon: C.green, boson: C.violet, scalar: C.pink }[l.type];
        ctx.strokeStyle = col; ctx.lineWidth = 2.2; ctx.setLineDash(l.type === "scalar" ? [7, 6] : []); ctx.beginPath();
        if (l.type === "photon" || l.type === "boson") { for (let k = 0; k <= 80; k++) { const s = k / 80, a = Math.sin(s * len / 9 * Math.PI) * 6, px = x0 + ux * s * len + nx * a, py = y0 + uy * s * len + ny * a; k ? ctx.lineTo(px, py) : ctx.moveTo(px, py); } }
        else if (l.type === "gluon") { for (let k = 0; k <= 160; k++) { const s = k / 160, ph = s * len / 12 * Math.PI * 2, px = x0 + ux * (s * len - Math.cos(ph) * 6) + nx * Math.sin(ph) * 7, py = y0 + uy * (s * len - Math.cos(ph) * 6) + ny * Math.sin(ph) * 7; k ? ctx.lineTo(px, py) : ctx.moveTo(px, py); } }
        else { ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); }
        ctx.stroke(); ctx.setLineDash([]);
        if (l.type === "fermion" || l.type === "antifermion") { const d = l.type === "fermion" ? 1 : -1, mx = (x0 + x1) / 2, my = (y0 + y1) / 2; arrow(ctx, mx - ux * 8 * d, my - uy * 8 * d, mx + ux * 8 * d, my + uy * 8 * d, col, 2.2, 10); }
        const f = ((flow * 0.4 + i * 0.13) % 1); ctx.fillStyle = "#fff"; ctx.globalAlpha = 0.8; ctx.beginPath(); ctx.arc(x0 + (x1 - x0) * f, y0 + (y1 - y0) * f, 3, 0, 7); ctx.fill(); ctx.globalAlpha = 1;
        if (l.label) text(ctx, l.label, (x0 + x1) / 2 + nx * 18, (y0 + y1) / 2 + ny * 18, col, 14, "center", "600");
        for (const p of [l.from, l.to]) { const k = p.join(","); verts.set(k, (verts.get(k) || 0) + 1); } });
      for (const [k, cnt] of verts) if (cnt > 1) { const [x, y] = k.split(",").map(Number); ctx.fillStyle = "#fff"; ctx.beginPath(); ctx.arc(X(x), Y(y), 5, 0, 7); ctx.fill(); }
      text(ctx, v.title || "Feynman diagram", 14, 16, C.text, 13, "left", "600"); text(ctx, v.time === "up" ? "time ↑" : "time →", w - 14, h - 14, C.muted, 12, "right");
    } };
  }
  const VIEWS = { motion: motionView, path: pathView, graph: graphView, forces: forcesView, circuit: circuitView,
    kinetics: kineticsView, titration: titrationView, energy_profile: energyView, ice: iceView, quantum: quantumView,
    qcircuit: qcircuitView, minkowski: minkowskiView, black_hole: blackHoleView, matrix: matrixView,
    distribution: distributionView, montecarlo: montecarloView, field: fieldView, molecule: moleculeView, feynman: feynmanView };

  // ======================= the problem =======================
  function open(box, data, opts = {}) {
    styles();
    const post = opts.post || (() => {});
    box.textContent = "";
    const wrap = el("div", "pw"), stage = el("div", "pstage"), side = el("div", "pside");
    const viewBox = el("div", "pview"), ctl = el("div", "pctl"), mathBar = el("div", "pmath");
    stage.append(viewBox, ctl, mathBar); wrap.append(stage, side); box.append(wrap);
    // transport: play, the time slider, the speed
    const play = el("button", "", "❚❚"), slider = el("input"), speed = el("button", "", "1×"), sideBtn = el("button", "", "Hide panel ›"), clock = el("span");
    slider.type = "range"; slider.min = "0"; slider.max = "1000"; slider.value = "0";
    ctl.append(play, slider, clock, speed, sideBtn);
    let state = { part: "", shown: 0, hint: false, check: null }, viewName = "", api = null, current = null, hl = {};
    let t = 0, playing = true, rate = 1, stopAt = null, lesson = null;
    play.addEventListener("click", () => { playing = !playing; stopAt = null; if (current && t >= current.T - 1e-9) t = 0; });
    slider.addEventListener("input", () => { if (current && current.timed) { t = current.T * slider.value / 1000; playing = false; stopAt = null; } });
    speed.addEventListener("click", () => { rate = rate === 1 ? 2 : rate === 2 ? 0.5 : 1; speed.textContent = rate + "×"; });
    const setSide = full => { wrap.classList.toggle("full", full); sideBtn.textContent = full ? "‹ Panel" : "Hide panel ›";
      try { localStorage.setItem("jarvisProblemFull", full ? "1" : ""); } catch (err) {} };
    try { setSide(localStorage.getItem("jarvisProblemFull") === "1"); } catch (err) {}
    sideBtn.addEventListener("click", () => setSide(!wrap.classList.contains("full")));

    function showView(name, highlight) {
      hl = highlight || {};
      const spec = data.views[name];
      if (name !== viewName) {
        viewName = name; if (api) api.stop(); api = null; current = null; if (lesson) { lesson.stop && lesson.stop(); lesson = null; }
        viewBox.textContent = "";
        if (!spec) { viewBox.append(el("div", "ptag", "Choose a part on the right to start.")); ctl.hidden = true; return; }
        if (spec.kind === "lesson") {
          const inner = el("div", "pinner"); viewBox.append(inner); ctl.hidden = true;
          if (window.JarvisLesson && window.JarvisLesson.draw) lesson = window.JarvisLesson.draw(inner, spec.visual);
          return;
        }
        const make = VIEWS[spec.kind]; if (!make) { viewBox.append(el("div", "ptag", "This view can't be drawn.")); return; }
        current = make(spec); t = 0; playing = true;
        api = canvasIn(viewBox, (ctx, w, h, dt) => {
          if (current.timed) {
            if (playing) { t += dt * rate * current.T / 10; if (stopAt !== null && t >= stopAt) { t = stopAt; playing = false; stopAt = null; }
              if (t >= current.T) { t = current.T; playing = false; } }
            slider.value = String(Math.round(t / current.T * 1000));
            clock.textContent = `${fmt(t)} ${current.unit || "s"}`;
            play.textContent = playing ? "❚❚" : "▶";
          }
          current.draw(ctx, w, h, dt, t, hl);
        });
        ctl.hidden = !current.timed;
        if (current.attach) current.attach(api.canvas);
      }
      if (current && current.timed) {                  // a step's moment: play up to it and stop there
        const target = hl.t !== undefined ? hl.t : hl.V !== undefined ? hl.V : hl.equivalence ? spec.V_eq : hl.half ? spec.V_eq / 2
          : hl.phase !== undefined && spec.bodies ? spec.bodies[0].phases[hl.phase] && spec.bodies[0].phases[hl.phase].t1 : hl.area ? hl.area[1] : null;
        if (target !== null && target !== undefined && isFinite(target)) { if (t > target) t = Math.max(0, hl.area ? hl.area[0] : hl.phase !== undefined ? spec.bodies[0].phases[hl.phase].t0 : 0);
          stopAt = clamp(target, 0, current.T); playing = true; }
      }
    }

    // ---- the card ----
    function render() {
      side.textContent = "";
      side.append(el("div", "subj", data.subject + (data.seed ? " · practice" : "")), el("h3", "", data.title));
      const st = el("div", "stmt"); st.textContent = data.statement; side.append(st);
      if (data.given.length) { const tb = el("table");
        for (const g of data.given) { const tr = el("tr"); tr.append(el("td", "s", g.symbol), el("td", "", g.name), el("td", "v", `${g.shown} ${g.unit || ""}`)); tb.append(tr); }
        side.append(tb); }
      for (const p of data.parts) {
        const on = state.part === p.id, card = el("div", "pcard" + (on ? " on" : "")), head = el("div", "ph");
        const done = on && state.shown >= p.steps.length;
        head.append(el("b", "", `(${p.id})`), el("span", "", p.ask), el("i", "", done && p.answer ? `= ${p.answer} ${p.unit || ""}` : ""));
        head.addEventListener("click", () => post({ problem: "part", part: p.id }));
        const bd = el("div", "pb"), btns = el("div", "btns");
        const b = (label, action) => { const x = el("button", "", label); x.addEventListener("click", ev => { ev.stopPropagation(); post({ problem: action, part: p.id }); }); btns.append(x); };
        b("Hint", "hint"); b("Next step", "step"); if (state.shown > 0) b("Back", "back"); b("Full solution", "solution");
        bd.append(btns);
        if (on && state.hint && p.hint) bd.append(el("div", "hint", "Hint: " + p.hint));
        if (on) p.steps.slice(0, state.shown).forEach((s, i) => {
          const row = el("div", "st" + (i === state.shown - 1 ? " cur" : ""));
          if (s.goal) row.append(el("div", "g", `${i + 1}. ${s.goal}`));
          row.append(el("div", "say", s.say));
          if (s.latex) { const eq = el("div", "eq"); tex(eq, s.latex, true); row.append(eq); }
          if (s.result && s.result.ok) { const eq = el("div", "eq"); tex(eq, s.result.latex, false); row.append(eq); }
          else if (s.result && s.result.note) row.append(el("span", "badge no", "not checked: " + s.result.note));
          row.addEventListener("click", () => showStep(p, i));
          bd.append(row);
        });
        const chk = el("div", "chk"), inp = el("input"), go = el("button", "", "Check my answer");
        inp.placeholder = `Your answer${p.unit ? " in " + p.unit : ""}`;
        const send = () => { if (inp.value.trim()) post({ problem: "check", part: p.id, answer: inp.value.trim().slice(0, 200) }); };
        go.addEventListener("click", send); inp.addEventListener("keydown", ev => { if (ev.key === "Enter") send(); });
        chk.append(inp, go); bd.append(chk);
        if (on && state.check) bd.append(el("div", "said " + (state.check.ok ? "ok" : "no"), state.check.said));
        card.append(head, bd); side.append(card);
      }
      const foot = el("div", "pfoot");
      const fb = (label, action) => { const x = el("button", "", label); x.addEventListener("click", () => post({ problem: action })); foot.append(x); };
      fb("Summary", "summary"); fb("Practice: new numbers", "practice");
      side.append(foot);
      if (state.summary && data.summary.length) { const s = el("div", "psum"); s.append(el("h4", "", "The method"));
        const ul = el("ul"); for (const line of data.summary) ul.append(el("li", "", line)); s.append(ul);
        if (data.concepts.length) s.append(el("div", "pnote", "Ideas: " + data.concepts.join(", "))); side.append(s); }
      side.append(el("div", "pnote", "Every number here was worked out by SymPy; the animations are tested drawings."));
    }
    function showStep(p, i) {
      const s = p.steps[i]; mathBar.textContent = "";
      if (!s) { mathBar.append(el("span", "goal", p.ask)); return; }
      if (s.goal) mathBar.append(el("span", "goal", s.goal));
      if (s.latex) { const eq = el("span", "eq"); tex(eq, s.latex, false); mathBar.append(eq); }
      if (s.result && s.result.ok) { const r = el("span", "eq"); tex(r, s.result.latex, false); mathBar.append(r, el("span", "badge ok", "✓ SymPy")); }
      else if (s.result && s.result.note) mathBar.append(el("span", "badge no", "not checked"));
      const view = s.view || (p.steps.slice(0, i).reverse().find(x => x.view) || {}).view || viewName || Object.keys(data.views)[0];
      showView(view, s.highlight);
    }
    function apply(next) {
      state = Object.assign({ part: "", shown: 0, hint: false, check: null, summary: false }, next || {});
      render();
      const p = data.parts.find(x => x.id === state.part);
      if (p) showStep(p, state.shown - 1);
      else { mathBar.textContent = ""; mathBar.append(el("span", "goal", "Choose a part: start with a hint, or the next step")); }
    }
    const first = Object.keys(data.views)[0]; showView(first, {});
    apply(opts.state);
    return { state: apply, stop() { if (api) api.stop(); if (lesson && lesson.stop) lesson.stop(); box.textContent = ""; },
      get t() { return t; }, get view() { return viewName; } };
  }
  // One view on its own, playing (a lesson's step, ui/lesson.js): the same tested drawings.
  function drawView(box, data, hl = {}) {
    const make = VIEWS[data && data.kind];
    if (!make) throw new Error("no such view");
    const view = make(data); let t = 0;
    const api = canvasIn(box, (ctx, w, h, dt) => {
      if (view.timed) { t += dt * view.T / 10; if (t > view.T * 1.15) t = 0; }       // play, rest a moment, again
      view.draw(ctx, w, h, dt, Math.min(t, view.T || 0), hl);
    });
    if (view.attach) view.attach(api.canvas);
    return { stop: api.stop };
  }
  return { open, drawView, views: Object.keys(VIEWS) };
})();
