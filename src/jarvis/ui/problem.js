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
  const VIEWS = { motion: motionView, path: pathView, graph: graphView, forces: forcesView, circuit: circuitView,
    kinetics: kineticsView, titration: titrationView, energy_profile: energyView, ice: iceView };

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
  return { open, views: Object.keys(VIEWS) };
})();
