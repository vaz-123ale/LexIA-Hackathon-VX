// Globo 3D em canvas (projeção ortográfica), sem bibliotecas externas.
// Geometria: Natural Earth 1:110m (domínio público). Pontos dos ativos são FICTÍCIOS.
const RAD = Math.PI / 180;

function toVec(lon, lat) { const l = lon * RAD, p = lat * RAD; return [Math.cos(p) * Math.cos(l), Math.cos(p) * Math.sin(l), Math.sin(p)]; }
function toLonLat([x, y, z]) { return [Math.atan2(y, x) / RAD, Math.asin(Math.max(-1, Math.min(1, z))) / RAD]; }
function slerp(a, b, t) {
  const d = Math.acos(Math.max(-1, Math.min(1, a[0] * b[0] + a[1] * b[1] + a[2] * b[2])));
  if (d < 1e-6) return a;
  const s = Math.sin(d), k1 = Math.sin((1 - t) * d) / s, k2 = Math.sin(t * d) / s;
  return [a[0] * k1 + b[0] * k2, a[1] * k1 + b[1] * k2, a[2] * k1 + b[2] * k2];
}

export function createGlobe(canvas, opts) {
  const ctx = canvas.getContext('2d');
  let W = 0, H = 0, R = 0, dpr = 1;
  let lam0 = opts.start?.[0] ?? -50, phi0 = opts.start?.[1] ?? -12, zoom = opts.zoom ?? 1;
  let auto = opts.autoRotate ?? true, dragging = false, last = null, hover = null, raf = 0, t0 = performance.now(), alive = true;
  let points = opts.points || [];
  const world = opts.world, hub = opts.hub, highlight = new Set(opts.highlight || ['BRA']);

  function project(lon, lat, elev = 1) {
    const l = (lon - lam0) * RAD, p = lat * RAD, p0 = phi0 * RAD;
    const cosc = Math.sin(p0) * Math.sin(p) + Math.cos(p0) * Math.cos(p) * Math.cos(l);
    const x = Math.cos(p) * Math.sin(l), y = Math.cos(p0) * Math.sin(p) - Math.sin(p0) * Math.cos(p) * Math.cos(l);
    return { x: W / 2 + x * R * elev, y: H / 2 - y * R * elev, vis: cosc, rx: x, ry: y };
  }

  function resize() {
    const r = canvas.getBoundingClientRect();
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    W = r.width; H = r.height; canvas.width = W * dpr; canvas.height = H * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    R = Math.min(W, H) * 0.44 * zoom;
  }

  function ringPath(ring) {
    let started = false;
    for (const [lon, lat] of ring) {
      const pt = project(lon, lat);
      let { x, y } = pt;
      if (pt.vis < 0) { const n = Math.hypot(pt.rx, pt.ry) || 1; x = W / 2 + (pt.rx / n) * R; y = H / 2 - (pt.ry / n) * R; }
      if (!started) { ctx.moveTo(x, y); started = true; } else ctx.lineTo(x, y);
    }
    ctx.closePath();
  }

  function draw(now) {
    if (!alive) return;
    const dt = Math.min(50, now - t0); t0 = now;
    if (auto && !dragging) lam0 += dt * 0.006;
    R = Math.min(W, H) * 0.44 * zoom;
    ctx.clearRect(0, 0, W, H);
    // atmosfera
    const g = ctx.createRadialGradient(W / 2, H / 2, R * 0.9, W / 2, H / 2, R * 1.25);
    const L = opts.theme === 'claro';
    if (L) { g.addColorStop(0, 'rgba(40,81,138,0.18)'); g.addColorStop(1, 'rgba(40,81,138,0)'); }
    else { g.addColorStop(0, 'rgba(77,225,208,0.28)'); g.addColorStop(1, 'rgba(77,225,208,0)'); }
    ctx.fillStyle = g; ctx.beginPath(); ctx.arc(W / 2, H / 2, R * 1.25, 0, Math.PI * 2); ctx.fill();
    // oceano
    const o = ctx.createRadialGradient(W / 2 - R * 0.35, H / 2 - R * 0.35, R * 0.1, W / 2, H / 2, R);
    if (L) { o.addColorStop(0, '#BFD8EC'); o.addColorStop(0.65, '#7FA6CB'); o.addColorStop(1, '#3F6C9A'); }
    else { o.addColorStop(0, '#17325a'); o.addColorStop(1, '#081426'); }
    ctx.fillStyle = o; ctx.beginPath(); ctx.arc(W / 2, H / 2, R, 0, Math.PI * 2); ctx.fill();
    ctx.save(); ctx.beginPath(); ctx.arc(W / 2, H / 2, R, 0, Math.PI * 2); ctx.clip();
    // graticule
    ctx.strokeStyle = L ? 'rgba(255,255,255,0.22)' : 'rgba(120,170,220,0.12)'; ctx.lineWidth = 0.7;
    for (let lon = -180; lon < 180; lon += 20) { ctx.beginPath(); let s = false; for (let lat = -90; lat <= 90; lat += 4) { const p = project(lon, lat); if (p.vis > 0) { s ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y); s = true; } else s = false; } ctx.stroke(); }
    for (let lat = -80; lat <= 80; lat += 20) { ctx.beginPath(); let s = false; for (let lon = -180; lon <= 180; lon += 4) { const p = project(lon, lat); if (p.vis > 0) { s ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y); s = true; } else s = false; } ctx.stroke(); }
    // países
    for (const f of world.f) {
      const hl = highlight.has(f.iso);
      for (const ring of f.r) {
        let any = false; for (let i = 0; i < ring.length; i += 3) { if (project(ring[i][0], ring[i][1]).vis > 0) { any = true; break; } }
        if (!any) continue;
        ctx.beginPath(); ringPath(ring);
        ctx.fillStyle = L ? (hl ? 'rgba(212,161,46,0.55)' : 'rgba(178,179,157,0.85)') : (hl ? 'rgba(77,225,208,0.30)' : 'rgba(98,140,190,0.22)'); ctx.fill();
        ctx.strokeStyle = L ? (hl ? 'rgba(160,106,44,0.9)' : 'rgba(110,112,90,0.5)') : (hl ? 'rgba(120,240,225,0.9)' : 'rgba(150,190,230,0.35)'); ctx.lineWidth = hl ? 1.2 : 0.6; ctx.stroke();
      }
    }
    ctx.restore();
    // arcos hub -> ativos
    const pulse = (now / 1000) % 1;
    if (hub) {
      const hv = toVec(hub.lon, hub.lat);
      for (const pt of points) {
        const pv = toVec(pt.lon, pt.lat);
        ctx.beginPath(); let s = false;
        for (let i = 0; i <= 32; i++) {
          const t = i / 32, v = slerp(hv, pv, t), [lo, la] = toLonLat(v), p = project(lo, la, 1 + 0.12 * Math.sin(Math.PI * t));
          if (p.vis > -0.05) { s ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y); s = true; } else s = false;
        }
        ctx.strokeStyle = pt.color + '99'; ctx.lineWidth = 1.2; ctx.stroke();
        const tt = (pulse + (pt.id.charCodeAt(2) % 10) / 10) % 1, v = slerp(hv, pv, tt), [lo, la] = toLonLat(v), p = project(lo, la, 1 + 0.12 * Math.sin(Math.PI * tt));
        if (p.vis > 0) { ctx.fillStyle = pt.color; ctx.beginPath(); ctx.arc(p.x, p.y, 2.2, 0, Math.PI * 2); ctx.fill(); }
      }
      const hp = project(hub.lon, hub.lat);
      if (hp.vis > 0) { ctx.fillStyle = '#ffffff'; ctx.beginPath(); ctx.arc(hp.x, hp.y, 4, 0, Math.PI * 2); ctx.fill(); ctx.strokeStyle = '#ffffff88'; ctx.beginPath(); ctx.arc(hp.x, hp.y, 8 + 6 * pulse, 0, Math.PI * 2); ctx.stroke(); if (opts.labels !== false) { ctx.fillStyle = '#dfefff'; ctx.font = '600 11px Inter, system-ui'; ctx.fillText(hub.label, hp.x + 10, hp.y - 8); } }
    }
    // pontos
    for (const pt of points) {
      const p = project(pt.lon, pt.lat);
      pt._screen = p.vis > 0 ? p : null;
      if (p.vis <= 0) continue;
      const sel = opts.selected?.() === pt.id, many = points.length > 150, pr = opts.pointSize || (many ? 2.6 : 5);
      if (!many || sel) { ctx.strokeStyle = pt.color; ctx.globalAlpha = 1 - pulse; ctx.beginPath(); ctx.arc(p.x, p.y, pr + 12 * pulse, 0, Math.PI * 2); ctx.stroke(); ctx.globalAlpha = 1; }
      ctx.fillStyle = pt.color; ctx.beginPath(); ctx.arc(p.x, p.y, sel ? pr + 3 : pr, 0, Math.PI * 2); ctx.fill();
      if (!many) { ctx.strokeStyle = '#04101f'; ctx.lineWidth = 1.5; ctx.stroke(); }
      if (opts.labels !== false && (sel || hover === pt.id || zoom > 1.6)) { ctx.fillStyle = '#eef6ff'; ctx.font = '700 11px Inter, system-ui'; ctx.fillText(pt.id, p.x + 9, p.y + 4); }
    }
    // borda
    ctx.strokeStyle = L ? 'rgba(20,49,92,0.35)' : 'rgba(120,240,225,0.45)'; ctx.lineWidth = 1; ctx.beginPath(); ctx.arc(W / 2, H / 2, R, 0, Math.PI * 2); ctx.stroke();
    raf = requestAnimationFrame(draw);
  }

  function pick(ev) {
    const r = canvas.getBoundingClientRect(), x = ev.clientX - r.left, y = ev.clientY - r.top;
    let best = null, bd = 14;
    for (const pt of points) { if (!pt._screen) continue; const d = Math.hypot(pt._screen.x - x, pt._screen.y - y); if (d < bd) { bd = d; best = pt; } }
    return best;
  }
  const onDown = (ev) => { dragging = true; last = [ev.clientX, ev.clientY]; canvas.setPointerCapture?.(ev.pointerId); };
  const onMove = (ev) => {
    if (dragging && last) { const dx = ev.clientX - last[0], dy = ev.clientY - last[1]; lam0 -= dx * 0.35 / zoom; phi0 = Math.max(-85, Math.min(85, phi0 + dy * 0.35 / zoom)); last = [ev.clientX, ev.clientY]; if (Math.abs(dx) + Math.abs(dy) > 2) canvas._moved = true; }
    const p = pick(ev); hover = p?.id || null; canvas.style.cursor = p ? 'pointer' : (dragging ? 'grabbing' : 'grab');
    if (opts.onHover) opts.onHover(p, ev);
  };
  const onUp = (ev) => { if (dragging && !canvas._moved) { const p = pick(ev); if (p && opts.onPick) opts.onPick(p); } dragging = false; canvas._moved = false; };
  const onWheel = (ev) => { ev.preventDefault(); zoom = Math.max(0.7, Math.min(4, zoom * (ev.deltaY < 0 ? 1.1 : 0.9))); };
  canvas.addEventListener('pointerdown', onDown); window.addEventListener('pointermove', onMove); window.addEventListener('pointerup', onUp);
  canvas.addEventListener('wheel', onWheel, { passive: false });
  const ro = new ResizeObserver(resize); ro.observe(canvas);
  resize(); raf = requestAnimationFrame(draw);

  return {
    setPoints(p) { points = p; },
    setAuto(v) { auto = v; }, isAuto: () => auto,
    focus(lon, lat, z) { lam0 = lon; phi0 = lat; if (z) zoom = z; },
    zoomBy(f) { zoom = Math.max(0.7, Math.min(4, zoom * f)); },
    destroy() { alive = false; cancelAnimationFrame(raf); ro.disconnect(); window.removeEventListener('pointermove', onMove); window.removeEventListener('pointerup', onUp); },
  };
}
