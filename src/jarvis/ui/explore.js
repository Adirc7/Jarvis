// Jarvis's 3D explorer: a model you take apart with your hand (knowledge/explore_models.py,
// perception/hand_controls.py). Open your hand: it comes apart. A fist: back together. Move or twist
// your open hand: it turns; raise it: it tilts. Point and pinch: that part comes out and Jarvis explains
// it. Two hands apart or together: zoom. Peace sign: the next model. The mouse works too.
// Our own models, built from shapes; text is always set as text, never as HTML.
"use strict";
window.JarvisExplore = (function () {
  const THREE_URL = "https://cdn.jsdelivr.net/npm/three@0.149.0/build/three.min.js";
  let threeLoading = null;
  function loadThree() {
    if (window.THREE) return Promise.resolve();
    if (!threeLoading) threeLoading = new Promise((ok, fail) => {
      const s = document.createElement("script");
      s.src = THREE_URL; s.onload = ok; s.onerror = () => fail(new Error("couldn't load three.js"));
      document.head.append(s);
    });
    return threeLoading;
  }
  const COLOURS = { body: "#ff5fa2", powertrain: "#ffb43b", running: "#4de1ff", chassis: "#8fa7ba",
                    interior: "#b48cff", electrical: "#64efb7" };
  const BONES = [[0, 1], [1, 2], [2, 3], [3, 4], [0, 5], [5, 6], [6, 7], [7, 8], [5, 9], [9, 10], [10, 11],
                 [11, 12], [9, 13], [13, 14], [14, 15], [15, 16], [13, 17], [0, 17], [17, 18], [18, 19], [19, 20]];
  const GESTURES = [
    ["Open your hand slowly", "take it apart"], ["Make a fist", "put it back together"],
    ["Move or twist your open hand", "turn it; raise it to tilt"], ["Point, then pinch", "pull a part out"],
    ["Two hands apart or together", "zoom"], ["Peace sign", "the next model"]];
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text; return e; };
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const ease = x => x * x * (3 - 2 * x);

  function styles() {
    if (document.getElementById("exploreCss")) return;
    const css = el("style"); css.id = "exploreCss";
    css.textContent = `
.xw { position:relative; flex:1; display:flex; min-height:0; overflow:hidden; }
.xstage { position:relative; flex:1; min-width:0; cursor:grab; }
.xstage canvas { position:absolute; inset:0; width:100%; height:100%; display:block; }
.xstage canvas.xover { pointer-events:none; }
.xlabels { position:absolute; inset:0; pointer-events:none; }
.xlabel { position:absolute; font:12px Segoe UI,system-ui,sans-serif; color:#eaf5ff; white-space:nowrap;
  padding:2px 7px; border-radius:4px; background:#03070dcc; border:1px solid #1c4766; transform:translateY(-50%); }
.xlabel.on { border-color:#ffffff; color:#ffffff; background:#0c2236ee; }
.xside { width:270px; flex:none; overflow:auto; padding:12px 14px; border-left:1px solid var(--line,#12314a);
  font:13px Segoe UI,system-ui,sans-serif; color:var(--text,#eaf5ff); background:#050d16; }
.xside h3 { margin:0 0 2px; font-size:18px; font-weight:500; color:#fff; }
.xside .sz { color:var(--muted,#8fa7ba); font-size:12px; margin-bottom:10px; }
.xside .row { display:flex; justify-content:space-between; margin:4px 0; font-size:12px; color:var(--muted,#8fa7ba); }
.xside .row b { color:var(--cyan,#4de1ff); font-weight:500; }
.xside .bar { height:5px; background:#12314a; border-radius:3px; overflow:hidden; margin:2px 0 8px; }
.xside .bar i { display:block; height:100%; background:var(--cyan,#4de1ff); }
.xside .ges { margin-top:10px; border-top:1px solid #12314a; padding-top:8px; }
.xside .ges div { margin:5px 0; font-size:12px; } .xside .ges b { color:#fff; font-weight:500; }
.xside .ges span { color:var(--muted,#8fa7ba); }
.xcard { margin-top:12px; border:1px solid #1c4766; border-radius:8px; padding:9px 10px; background:#0a1a2a; }
.xcard .g { font-size:11px; letter-spacing:1px; text-transform:uppercase; }
.xcard p { margin:6px 0 0; line-height:1.45; color:#cfe3f3; }
.xbar { position:absolute; left:12px; right:12px; bottom:10px; display:flex; gap:8px; align-items:center;
  font:12px Segoe UI,system-ui,sans-serif; color:var(--muted,#8fa7ba); }
.xbar button { font-size:12px; color:var(--text,#eaf5ff); background:#12314a; border:1px solid #1c4766;
  border-radius:6px; padding:4px 10px; cursor:pointer; }
.xbar button.on { border-color:var(--cyan,#4de1ff); color:#fff; }
.xbar input { flex:1; max-width:220px; accent-color:#4de1ff; }
.xbar select { font-size:12px; color:var(--text,#eaf5ff); background:#12314a; border:1px solid #1c4766;
  border-radius:6px; padding:4px 6px; }
.xnote { position:absolute; top:10px; left:12px; font:12px Segoe UI,system-ui,sans-serif; color:var(--muted,#8fa7ba); }`;
    document.head.append(css);
  }

  // ---- shapes from the model's data ----
  function geometry(T, s) {
    const n = (v, d) => (v === undefined ? d : v);
    if (s.t === "box") return new T.BoxGeometry(s.s[0], s.s[1], s.s[2]);
    if (s.t === "cyl") return new T.CylinderGeometry(s.s[0], s.s[1], s.s[2], 28);
    if (s.t === "torus") return new T.TorusGeometry(s.s[0], s.s[1], 14, 40);
    if (s.t === "sphere") return new T.SphereGeometry(s.s[0], 24, 16);
    if (s.t === "tube") {
      const curve = new T.CatmullRomCurve3(s.pts.map(p => new T.Vector3(p[0], p[1], p[2])));
      return new T.TubeGeometry(curve, Math.max(24, s.pts.length * 16), s.s[0], 10, false);
    }
    if (s.t === "spring") {
      const [r, h, turns, wire] = [s.s[0], s.s[1], n(s.s[2], 6), n(s.s[3], 0.03)];
      const pts = [];
      for (let i = 0; i <= turns * 24; i++) {
        const a = i / 24 * 2 * Math.PI;
        pts.push(new T.Vector3(r * Math.cos(a), -h / 2 + h * i / (turns * 24), r * Math.sin(a)));
      }
      return new T.TubeGeometry(new T.CatmullRomCurve3(pts), turns * 24, wire, 6, false);
    }
    return new T.BoxGeometry(0.2, 0.2, 0.2);
  }

  async function open(box, model, opts = {}) {
    styles();
    await loadThree();
    const T = window.THREE, post = opts.post || (() => {});
    box.textContent = "";
    const wrap = el("div", "xw"), stage = el("div", "xstage"), side = el("div", "xside");
    wrap.append(stage, side); box.append(wrap);
    const renderer = new T.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
    const over = el("canvas", "xover"), labels = el("div", "xlabels"), note = el("div", "xnote"),
          bar = el("div", "xbar");
    stage.append(renderer.domElement, over, labels, note, bar);
    const ctx = over.getContext("2d");

    const scene = new T.Scene(), camera = new T.PerspectiveCamera(38, 1, 0.1, 400);
    scene.add(new T.AmbientLight(0xffffff, 0.6));
    const sun = new T.DirectionalLight(0xffffff, 0.7); sun.position.set(8, 14, 10); scene.add(sun);
    const root = new T.Group(); scene.add(root);
    const scale = model.scale || 1;
    root.scale.setScalar(scale);

    // ---- build the parts ----
    const parts = [], meshes = [];
    for (const p of model.parts) {
      const tone = p.colour || COLOURS[p.group] || "#4de1ff";
      const colour = new T.Color(tone);
      const group = new T.Group(); root.add(group);
      const part = { data: p, group, shapes: [], mats: [], lines: [], centre: new T.Vector3() };
      for (const s of p.shapes) {
        const holder = new T.Group(); group.add(holder);
        const geo = geometry(T, s);
        const mat = new T.MeshStandardMaterial({ color: colour, emissive: colour, emissiveIntensity: 0.28,
          transparent: true, opacity: 0.2, depthWrite: false, side: T.DoubleSide, roughness: 0.5, metalness: 0.2 });
        const mesh = new T.Mesh(geo, mat);
        const lmat = new T.LineBasicMaterial({ color: colour, transparent: true, opacity: 0.8 });
        const lines = new T.LineSegments(new T.EdgesGeometry(geo, 28), lmat);
        for (const o of [mesh, lines]) {
          if (s.p) o.position.set(s.p[0], s.p[1], s.p[2]);
          if (s.r) o.rotation.set(s.r[0], s.r[1], s.r[2]);
          if (s.sc) o.scale.set(s.sc[0], s.sc[1], s.sc[2]);
          holder.add(o);
        }
        mesh.userData.part = part;
        meshes.push(mesh);
        const c = new T.Box3().setFromObject(mesh).getCenter(new T.Vector3());
        part.shapes.push({ holder, out: new T.Vector3(...(s.out || p.out)), centre: c });
        part.mats.push(mat); part.lines.push(lmat);
      }
      part.centre = part.shapes.reduce((a, s) => a.add(s.centre), new T.Vector3()).divideScalar(part.shapes.length);
      const dir = new T.Vector3(...p.out);
      part.pull = (dir.lengthSq() > 0.01 ? dir : part.centre.clone()).normalize().multiplyScalar(1.4);
      part.tone = tone;
      part.label = el("div", "xlabel", p.name); part.label.style.borderLeft = `3px solid ${tone}`;
      part.label.style.display = "none"; labels.append(part.label);
      parts.push(part);
    }
    const bounds = new T.Box3().setFromObject(root);
    const mid = bounds.getCenter(new T.Vector3());
    root.position.sub(mid.multiplyScalar(scale));
    const radius = bounds.getSize(new T.Vector3()).length() * scale / 2;
    const view = { yaw: 0.75, pitch: 0.42, dist: radius * 2.6 };
    const ring = new T.Mesh(new T.RingGeometry(radius * 0.9, radius * 0.92, 96),
      new T.MeshBasicMaterial({ color: 0x4de1ff, transparent: true, opacity: 0.18, side: T.DoubleSide }));
    ring.rotation.x = -Math.PI / 2; ring.position.y = -radius * 0.45; scene.add(ring);

    // ---- the side: the model, your hand, the gestures, the part ----
    side.append(el("h3", "", model.title), el("div", "sz", model.size || ""));
    if (model.like) side.append(el("div", "sz", "Built inside like: " + model.like));
    const handRow = el("div", "row"), handBar = el("div", "bar"), exRow = el("div", "row"), exBar = el("div", "bar");
    handRow.append(el("span", "", "Hand"), el("b", "", "not seen")); handBar.append(el("i"));
    handBar.firstChild.style.width = "0";
    exRow.append(el("span", "", "Taken apart"), el("b", "", "0%")); exBar.append(el("i"));
    const tuneRow = el("div", "row");                        // the raw numbers, to tune [explore] to your hand
    tuneRow.append(el("span", "", "Spread / pinch"), el("b", "", "-"));
    side.append(handRow, handBar, tuneRow, exRow, exBar);
    const ges = el("div", "ges");
    for (const [what, does] of GESTURES) { const d = el("div"); d.append(el("b", "", what), el("span", "", " - " + does)); ges.append(d); }
    const card = el("div", "xcard"); card.hidden = true;
    side.append(card, ges);

    // ---- the bar: buttons and the slider (the mouse way) ----
    const apart = el("button", "", "Take apart"), together = el("button", "", "Put together"),
          slider = el("input"), models = el("select");
    slider.type = "range"; slider.min = "0"; slider.max = "100"; slider.value = "0";
    for (const [id, name] of (opts.models || [])) {
      const o = el("option", "", name); o.value = id; o.selected = id === model.id; models.append(o);
    }
    models.addEventListener("change", () => post({ explore: "model", model: models.value }));
    bar.append(apart, together, slider, models);
    note.textContent = "Show your hand to the camera, or drag to turn and click a part.";

    // ---- state ----
    let e = 0, target = 0, selected = null, hovered = null, alive = true, hands = [], handsAt = 0;
    let handRef = null, twoRef = null, pointer = null, drag = null, last = performance.now(), idleSpin = true;
    apart.addEventListener("click", () => { target = 1; idleSpin = false; });
    together.addEventListener("click", () => { target = 0; });
    slider.addEventListener("input", () => { target = Number(slider.value) / 100; idleSpin = false; });

    function select(part, tell) {
      selected = part;
      card.hidden = !part; card.textContent = "";
      if (part) {
        const g = el("div", "g", (opts.groups || {})[part.data.group] || part.data.group);
        g.style.color = part.tone;
        card.append(el("h3", "", part.data.name), g, el("p", "", part.data.desc));
        if (target < 0.35) target = 0.6;
        if (tell) post({ explore: "pick", part: part.data.id });
      }
    }
    const ray = new T.Raycaster(), ndc = new T.Vector2();
    function partAt(px, py) {
      const r = stage.getBoundingClientRect();
      ndc.set(px / r.width * 2 - 1, -py / r.height * 2 + 1);
      ray.setFromCamera(ndc, camera);
      const hit = ray.intersectObjects(meshes, false)[0];
      return hit ? hit.object.userData.part : null;
    }
    const dom = renderer.domElement;
    dom.addEventListener("pointerdown", ev => { drag = [ev.clientX, ev.clientY, view.yaw, view.pitch, false];
      dom.setPointerCapture(ev.pointerId); idleSpin = false; });
    dom.addEventListener("pointermove", ev => {
      const r = stage.getBoundingClientRect();
      if (drag) {
        if (Math.abs(ev.clientX - drag[0]) + Math.abs(ev.clientY - drag[1]) > 4) drag[4] = true;
        view.yaw = drag[2] - (ev.clientX - drag[0]) * 0.01;
        view.pitch = clamp(drag[3] + (ev.clientY - drag[1]) * 0.01, -1.2, 1.4);
      } else if (performance.now() - handsAt > 600) hovered = partAt(ev.clientX - r.left, ev.clientY - r.top);
    });
    dom.addEventListener("pointerup", ev => {
      const r = stage.getBoundingClientRect();
      if (drag && !drag[4]) { const p = partAt(ev.clientX - r.left, ev.clientY - r.top); if (p) select(p, true); }
      drag = null;
    });
    dom.addEventListener("pointerleave", () => { hovered = null; });
    dom.addEventListener("wheel", ev => { ev.preventDefault();
      view.dist = clamp(view.dist * (ev.deltaY > 0 ? 1.1 : 0.9), radius * 1.2, radius * 6); }, { passive: false });

    // ---- your hands (from Jarvis, about 15 times a second) ----
    function onHands(msg) {
      hands = msg.hands || [];
      if (hands.length) handsAt = performance.now();
      const lead = hands[0];
      const valueEl = handRow.lastChild;
      if (!lead) {
        handRef = twoRef = pointer = null; valueEl.textContent = "not seen"; handBar.firstChild.style.width = "0";
        tuneRow.lastChild.textContent = "-"; return;
      }
      idleSpin = false;
      const pointing = lead.gesture === "Pointing_Up" || lead.pinch;
      valueEl.textContent = pointing ? "pointing" : lead.gesture === "Closed_Fist" ? "fist" :
        lead.gesture === "Victory" ? "peace" : Math.round(lead.open * 100) + "% open";
      handBar.firstChild.style.width = Math.round(lead.open * 100) + "%";
      tuneRow.lastChild.textContent = (lead.spread || 0).toFixed(2) + " / " + (lead.pinch_d || 0).toFixed(2) +
        (lead.pinch ? "  pinch" : "");
      if (hands.length >= 2) {                                      // two hands: zoom
        const d = Math.hypot(hands[0].centre[0] - hands[1].centre[0], hands[0].centre[1] - hands[1].centre[1]);
        if (!twoRef) twoRef = { d: Math.max(0.05, d), dist: view.dist };
        view.dist = clamp(twoRef.dist * twoRef.d / Math.max(0.05, d), radius * 1.2, radius * 6);
        handRef = null;
      } else twoRef = null;
      if (!pointing && hands.length === 1) {                        // one open hand: apart and turn
        target = lead.open;
        if (!handRef) handRef = { x: lead.centre[0], y: lead.centre[1], roll: lead.roll, yaw: view.yaw, pitch: view.pitch };
        view.yaw = handRef.yaw - (lead.centre[0] - handRef.x) * 5 - (lead.roll - handRef.roll) * 1.4;
        view.pitch = clamp(handRef.pitch + (handRef.y - lead.centre[1]) * 3, -1.2, 1.4);
      } else if (pointing) handRef = null;
      pointer = pointing ? (lead.pinch ? lead.pinch_at : lead.tip) : null;
      if (pointer) {
        const r = stage.getBoundingClientRect();
        hovered = partAt(pointer[0] * r.width, pointer[1] * r.height);
      }
      if ((msg.events || []).includes("pinch") && hovered) select(hovered, true);
    }

    function command(cmd) {
      if (cmd.action === "explode") { target = 1; idleSpin = false; }
      else if (cmd.action === "assemble") target = 0;
      else if (cmd.action === "select") select(parts.find(p => p.data.id === cmd.part) || null, false);
      else if (cmd.action === "clear") select(null, false);
    }

    // ---- every frame ----
    const tmp = new T.Vector3();
    function frame(now) {
      if (!alive) return;
      const dt = clamp((now - last) / 1000, 0, 0.05); last = now;   // a frame's time can be before last
      const w = stage.clientWidth || 600, h = stage.clientHeight || 400, pr = renderer.getPixelRatio();
      if (dom.width !== Math.round(w * pr) || dom.height !== Math.round(h * pr)) {
        renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
        over.width = Math.round(w * pr); over.height = Math.round(h * pr);
      }
      if (performance.now() - handsAt > 1500 && hands.length) onHands({ hands: [] });   // the hand went away
      e += (target - e) * (1 - Math.exp(-dt * 5));
      const f = ease(clamp(e, 0, 1));
      const shown = Math.round(clamp(e, 0, 1) * 100) + "%";
      exRow.lastChild.textContent = shown; exBar.firstChild.style.width = shown;
      if (document.activeElement !== slider) slider.value = String(Math.round(target * 100));
      if (idleSpin && !drag) view.yaw += dt * 0.15;
      for (const part of parts) {
        const pulled = part === selected ? 1 : 0;
        for (const s of part.shapes) {
          s.holder.position.copy(s.out).multiplyScalar(f);
          if (pulled) s.holder.position.addScaledVector(part.pull, 1);
        }
        const lit = part === hovered || part === selected;
        part.mats.forEach(m => { m.opacity = lit ? 0.5 : 0.2; m.emissiveIntensity = lit ? 0.6 : 0.28; });
        part.lines.forEach(m => { m.opacity = lit ? 1 : 0.75; });
      }
      const dist = view.dist * (1 + 0.7 * f);                     // apart, it needs more room: step back
      camera.position.set(dist * Math.cos(view.pitch) * Math.sin(view.yaw), dist * Math.sin(view.pitch),
                          dist * Math.cos(view.pitch) * Math.cos(view.yaw));
      camera.lookAt(0, 0, 0);
      renderer.render(scene, camera);
      drawOverlay(w, h, pr, f);
      requestAnimationFrame(frame);
    }

    // labels in two columns, each joined to its part by a line; the hands drawn over it all
    function drawOverlay(w, h, pr, f) {
      ctx.setTransform(pr, 0, 0, pr, 0, 0); ctx.clearRect(0, 0, w, h);
      const shown = [];
      for (const part of parts) {
        const on = f > 0.25 || part === hovered || part === selected;
        if (!on) { part.label.style.display = "none"; continue; }
        tmp.copy(part.centre);
        for (const s of part.shapes) tmp.addScaledVector(s.out, f / part.shapes.length);
        if (part === selected) tmp.add(part.pull);
        root.localToWorld(tmp); tmp.project(camera);
        if (tmp.z > 1) { part.label.style.display = "none"; continue; }
        shown.push({ part, x: (tmp.x + 1) / 2 * w, y: (1 - tmp.y) / 2 * h });
      }
      for (const right of [false, true]) {
        const col = shown.filter(s => (s.x >= w / 2) === right).sort((a, b) => a.y - b.y);
        const gap = Math.min(22, (h - 70) / Math.max(1, col.length));
        const ys = [];
        col.forEach((c, i) => ys.push(Math.max(c.y, 44, i ? ys[i - 1] + gap : 44)));   // in order, never overlapping
        const over = ys.length ? Math.max(0, ys[ys.length - 1] - (h - 50)) : 0;
        col.forEach((c, i) => {
          const y = Math.max(44 + i * gap, ys[i] - over);                                  // too low: all move up
          const lx = right ? w - 16 : 16;
          const label = c.part.label;
          label.style.display = "block"; label.className = "xlabel" + (c.part === hovered || c.part === selected ? " on" : "");
          label.style.top = y + "px";
          if (right) { label.style.right = "16px"; label.style.left = "auto"; }
          else { label.style.left = "16px"; label.style.right = "auto"; }
          const lw = label.offsetWidth || 80;
          ctx.strokeStyle = c.part.tone + (c.part === selected ? "" : "88");
          ctx.lineWidth = c.part === selected ? 1.6 : 1;
          ctx.beginPath(); ctx.moveTo(right ? lx - lw : lx + lw, y); ctx.lineTo(c.x, c.y); ctx.stroke();
          ctx.fillStyle = ctx.strokeStyle; ctx.beginPath(); ctx.arc(c.x, c.y, 2.5, 0, 7); ctx.fill();
        });
      }
      for (const hand of hands) {                               // your hand, mirrored like a mirror
        const pts = hand.points || [];
        if (pts.length < 21) continue;
        ctx.strokeStyle = "#4de1ffaa"; ctx.lineWidth = 2;
        ctx.beginPath();
        for (const [a, b] of BONES) { ctx.moveTo(pts[a][0] * w, pts[a][1] * h); ctx.lineTo(pts[b][0] * w, pts[b][1] * h); }
        ctx.stroke();
        ctx.fillStyle = "#eaf5ffcc";
        for (const p of pts) { ctx.beginPath(); ctx.arc(p[0] * w, p[1] * h, 2.6, 0, 7); ctx.fill(); }
      }
      if (pointer) {
        const lead = hands[0];
        ctx.strokeStyle = lead && lead.pinch ? "#ffb43b" : "#ffffff"; ctx.lineWidth = 2;
        ctx.beginPath(); ctx.arc(pointer[0] * w, pointer[1] * h, lead && lead.pinch ? 7 : 12, 0, 7); ctx.stroke();
      }
    }
    requestAnimationFrame(frame);
    return {
      hands: onHands, command,
      state: () => ({ explode: e, target, selected: selected && selected.data.id, hovered: hovered && hovered.data.id,
                      yaw: view.yaw, pitch: view.pitch, dist: view.dist, parts: parts.length }),
      stop() { alive = false; renderer.dispose(); box.textContent = ""; },
    };
  }

  return { open };
})();
