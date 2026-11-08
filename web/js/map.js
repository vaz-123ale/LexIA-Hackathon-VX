// Mapa vetorial 2D (SVG, offline, Natural Earth) com camadas separadas, clusterização por zoom,
// marcadores com forma por origem (● oficial · ◆ hipotético) e seleção por teclado.
import { satView, gmaps } from './geoview.js';
import { data, e, icon } from './core.js';

export function project(lat, lon) {
  const [xmin, ymin, xmax, ymax] = data.map.bounds;
  return [((lon - xmin) / (xmax - xmin)) * data.map.width, ((ymax - lat) / (ymax - ymin)) * data.map.height];
}
const BASE_VB = [25, 92, 690, 433];
let mapSequence=0;
const displayPoint=(lat,lon)=>{const [x,y]=project(lat,lon);return [x*1.2-72,y];};
export function mapScale(viewBox,width,bounds,height) {
  const lat=bounds[3]-(viewBox[1]+viewBox[3]/2)/height*(bounds[3]-bounds[1]);
  const kmPerPixel=viewBox[2]/Math.max(1,width)/(690/(bounds[2]-bounds[0])*1.2)*111.32*Math.cos(lat*Math.PI/180);
  const target=kmPerPixel*170, order=10**Math.floor(Math.log10(Math.max(target,.0001)));
  const distance=[1,2,5,10].map(n=>n*order).filter(n=>n<=target).at(-1) || order;
  return {distance,width:distance/kmPerPixel};
}

export function createMap(frame, { points, selected, onSelect, height = 560, controls = true, legend = true, cluster = true, onlyBrazil = false, pinScale = 1 }) {
  let vb = [...BASE_VB], pts = points, sel = selected, lastGroups = [];
  const uid=`map-${++mapSequence}`;
  frame.style.height = `${height}px`;
  const paths = data.map.features.filter((f) => (!f.brazil || !data.states) && !(onlyBrazil && !f.brazil)).map((f) => `<path class="country ${f.brazil ? 'brazil' : ''}" d="${f.path}"><title>${e(f.name)}</title></path>`).join('')
    + (data.states ? data.states.features.map((f) => `<path class="uf" d="${f.path}"><title>${e(f.uf)}</title></path>`).join('') : '');
  const rivers=(data.rivers?.features || []).flatMap(f=>f.geometry.type==='LineString'?[f.geometry.coordinates]:f.geometry.coordinates).map(line=>`<path class="map-river" d="${line.map(([lon,lat],i)=>{const [x,y]=project(lat,lon);return `${i?'L':'M'}${x.toFixed(2)},${y.toFixed(2)}`;}).join('')}"/>`).join('');
  const land=(data.states?.features || []).map(f=>`<path d="${f.path}"/>`).join('');
  frame.innerHTML = `<svg viewBox="${vb.join(' ')}" preserveAspectRatio="xMidYMid meet" role="application" aria-label="Mapa do Brasil com estruturas. Use Tab para percorrer marcadores e Enter para selecionar.">
    <defs><linearGradient id="${uid}-sea" gradientUnits="userSpaceOnUse" x1="25" y1="92" x2="715" y2="525"><stop stop-color="#eef8ff"/><stop offset="1" stop-color="#a8d7fa"/></linearGradient><linearGradient id="${uid}-land" gradientUnits="userSpaceOnUse" x1="200" y1="100" x2="500" y2="520"><stop stop-color="#a4cbf5"/><stop offset=".52" stop-color="#b6d7fa"/><stop offset="1" stop-color="#cee4fd"/></linearGradient><radialGradient id="${uid}-green"><stop stop-color="#8dccaa" stop-opacity=".75"/><stop offset=".65" stop-color="#a9d9be" stop-opacity=".4"/><stop offset="1" stop-color="#b3dfc8" stop-opacity="0"/></radialGradient><clipPath id="${uid}-clip">${land}</clipPath></defs>
    <rect x="-500" y="-500" width="2000" height="2000" fill="url(#${uid}-sea)"/>
    <g class="map-geography" transform="translate(-72 0) scale(1.2 1)" style="--map-land:url(#${uid}-land)">${paths}<g clip-path="url(#${uid}-clip)" class="map-land-wash" aria-hidden="true"><ellipse cx="355" cy="245" rx="85" ry="125" fill="url(#${uid}-green)"/><ellipse cx="418" cy="400" rx="75" ry="70" fill="url(#${uid}-green)"/><ellipse cx="290" cy="137" rx="120" ry="55" fill="url(#${uid}-green)"/><path d="M226 139Q242 117 255 132T290 140T319 139L321 154Q302 163 289 153T261 159T237 158Z M370 170Q390 148 409 171T429 195L416 210Q400 191 381 204L367 190Z M429 362Q449 345 454 365T474 385L466 410Q447 396 442 418L423 399Z" fill="#a5d8ba" opacity=".45"/></g><g class="map-rivers" aria-hidden="true">${rivers}</g>${data.states ? data.states.features.map((f) => `<text class="uf-label" x="${f.cx}" y="${f.cy}" text-anchor="middle">${e(f.uf)}</text>`).join('') : ''}</g><g class="pins"></g></svg>
    ${controls ? `<div class="map-ctl"><button class="icon-btn" data-zoom="in" aria-label="Aproximar">+</button><button class="icon-btn" data-zoom="out" aria-label="Afastar">−</button><button class="icon-btn" data-zoom="reset" aria-label="Enquadrar Brasil">${icon('crosshair')}</button></div>` : ''}
    ${legend ? '<div class="map-legend"><span><i class="lgi off"></i>Dado oficial</span><span><i class="lgi hyp"></i>Cenário hipotético</span><span><i class="lgi cl"></i>Agrupamento</span></div>' : ''}<div class="map-distance" aria-label="Escala aproximada do mapa"></div>`;
  const svg = frame.querySelector('svg'), g = svg.querySelector('.pins');

  function render() {
    svg.setAttribute('viewBox', vb.map((v) => v.toFixed(1)).join(' '));
    const scale=mapScale(vb,frame.clientWidth || 820,data.map.bounds,data.map.height);
    frame.querySelector('.map-distance').innerHTML=`<div class="scale-labels" style="width:${scale.width}px"><span>0</span><span>${(scale.distance/2).toLocaleString('pt-BR')}</span><span>${scale.distance.toLocaleString('pt-BR')} km</span></div><div class="scale-bar" style="width:${scale.width}px"></div>`;
    const k = vb[2] / BASE_VB[2];               // escala relativa
    svg.querySelectorAll('.uf-label').forEach((t) => { t.style.fontSize = `${(10 * k).toFixed(2)}px`; t.style.strokeWidth = `${(1.5 * k).toFixed(2)}px`; });
    const cell = vb[2] / 24, r = 5 * k * pinScale;
    const buckets = new Map();
    for (const p of pts) {
      if (!Number.isFinite(p.lat) || !Number.isFinite(p.lon) || Math.abs(p.lat)>90 || Math.abs(p.lon)>180) continue;
      const [x, y] = displayPoint(p.lat, p.lon);
      if (x < vb[0] - 20 || x > vb[0] + vb[2] + 20 || y < vb[1] - 20 || y > vb[1] + vb[3] + 20) continue;
      const key = !cluster || p.kind === 'synthetic' || p.id === sel ? `s:${p.id}` : `${Math.floor(x / cell)}:${Math.floor(y / cell)}`;
      const b = buckets.get(key) || { items: [], x: 0, y: 0 };
      b.items.push({ ...p, x, y }); b.x += x; b.y += y; buckets.set(key, b);
    }
    // funde agrupamentos cujos círculos se sobreporiam
    const rad = (n) => (6 + Math.min(12, Math.sqrt(n) * 1.8)) * k;
    let groups = [...buckets.values()].map((b) => ({ ...b, cx: b.x / b.items.length, cy: b.y / b.items.length }));
    let merged = cluster;
    while (merged) {
      merged = false;
      groups.sort((a, b) => b.items.length - a.items.length);
      outer: for (let i = 0; i < groups.length; i++) for (let j = i + 1; j < groups.length; j++) {
        const A = groups[i], B = groups[j];
        if (A.items.some((p) => p.kind === 'synthetic' || p.id === sel) || B.items.some((p) => p.kind === 'synthetic' || p.id === sel)) continue;
        if (Math.hypot(A.cx - B.cx, A.cy - B.cy) < rad(A.items.length) + rad(B.items.length) + 2 * k) {
          const items = [...A.items, ...B.items];
          groups[i] = { items, x: A.x + B.x, y: A.y + B.y, cx: (A.x + B.x) / items.length, cy: (A.y + B.y) / items.length };
          groups.splice(j, 1); merged = true; break outer;
        }
      }
    }
    let out = '';
    lastGroups = groups;
    groups.forEach((b, gi) => { b.gi = gi; });
    for (const b of groups) {
      const n = b.items.length, cx = b.x / n, cy = b.y / n;
      if (n > 1) {
        const rr = rad(n);
        out += `<g class="cluster" tabindex="0" role="button" data-gi="${b.gi}" data-count="${n}" data-cx="${cx}" data-cy="${cy}" aria-label="${n} estruturas agrupadas; Enter para ver a lista"><circle cx="${cx}" cy="${cy}" r="${rr}"/><text x="${cx}" y="${cy + 4.2 * k}" style="font-size:${12 * k}px">${n}</text></g>`;
      } else {
        const p = b.items[0], s = p.id === sel;
        const shape = p.kind === 'synthetic'
          ? `<rect x="${p.x - r}" y="${p.y - r}" width="${2 * r}" height="${2 * r}" transform="rotate(45 ${p.x} ${p.y})" fill="${p.color}"/>`
          : `<circle cx="${p.x}" cy="${p.y}" r="${s ? r * 1.8 : r}" fill="${p.color}"/>`;
        const label=p.short || p.id;
        out += `<g class="pin ${s ? 'sel' : ''} ${p.kind}" tabindex="0" role="button" data-id="${e(p.id)}" aria-label="${e(p.label)}">${s ? `<rect class="pin-label-bg" x="${p.x+r}" y="${p.y-r*1.4}" width="${Math.min(175,label.length*6.5+15)*k}" height="${18*k}" rx="${8*k}"/>` : ''}${shape}<title>${e(p.label)}</title>${(s || p.kind === 'synthetic') ? `<text x="${p.x + r * 2.1}" y="${p.y + r*.8}" style="font-size:${11.5 * k}px">${e(label)}</text>` : ''}</g>`;
      }
    }
    g.innerHTML = out;
  }
  const zoomAt = (f, cx = vb[0] + vb[2] / 2, cy = vb[1] + vb[3] / 2) => {
    const nw = Math.max(18, Math.min(900, vb[2] * f)), nh = nw * vb[3] / vb[2];
    vb = [cx - (cx - vb[0]) * nw / vb[2], cy - (cy - vb[1]) * nh / vb[3], nw, nh]; render();
  };
  frame.querySelectorAll('[data-zoom]').forEach((b) => b.addEventListener('click', () => { const z = b.dataset.zoom; if (z === 'reset') { vb = [...BASE_VB]; render(); } else zoomAt(z === 'in' ? 0.7 : 1.4); }));
  svg.addEventListener('wheel', (ev) => { ev.preventDefault(); const rc = svg.getBoundingClientRect(); const s = Math.max(vb[2] / rc.width, vb[3] / rc.height); const cx = vb[0] + (ev.clientX - rc.left - (rc.width - vb[2] / s) / 2) * s, cy = vb[1] + (ev.clientY - rc.top - (rc.height - vb[3] / s) / 2) * s; zoomAt(ev.deltaY < 0 ? 0.82 : 1.2, cx, cy); }, { passive: false });
  let drag = null, moved = false;
  svg.addEventListener('pointerdown', (ev) => { drag = [ev.clientX, ev.clientY]; moved = false; });
  svg.addEventListener('pointermove', (ev) => { if (!drag) return; const rc = svg.getBoundingClientRect(); const s = Math.max(vb[2] / rc.width, vb[3] / rc.height); const dx = ev.clientX - drag[0], dy = ev.clientY - drag[1]; if (Math.abs(dx) + Math.abs(dy) > 3) { moved = true; svg.setPointerCapture(ev.pointerId); } if (moved) { vb[0] -= dx * s; vb[1] -= dy * s; drag = [ev.clientX, ev.clientY]; render(); } });
  svg.addEventListener('pointerup', (ev) => { const was = moved; drag = null; moved = false; if (was) return; act(ev.target); });
  const pop = document.createElement('div'); pop.className = 'map-pop'; pop.hidden = true; frame.appendChild(pop);
  const closePop = () => { pop.hidden = true; };
  function openCluster(cl) {
    const grp = lastGroups[+cl.dataset.gi]; if (!grp) return;
    const items = grp.items, lat = items.reduce((a, p) => a + p.lat, 0) / items.length, lon = items.reduce((a, p) => a + p.lon, 0) / items.length;
    const span = Math.max(0.02, ...items.map((p) => Math.max(Math.abs(p.lat - lat), Math.abs(p.lon - lon))));
    const z = Math.max(6, Math.min(14, Math.round(Math.log2(360 / (span * 4)))));
    const byColor = new Map(); items.forEach((p) => byColor.set(p.color, (byColor.get(p.color) || 0) + 1));
    const ufs = [...new Set(items.map((p) => p.uf).filter(Boolean))];
    const allSyn = items.every((p) => p.kind === 'synthetic');
    pop.innerHTML = `<header><div><b>${items.length} estruturas nesta área</b><small>${ufs.length ? ufs.join(' · ') : 'Agrupadas por proximidade'}</small></div><button class="icon-btn" data-pop-close aria-label="Fechar">×</button></header>
      ${satView(lat, lon, { zoom: z, height: 130, area: true, synthetic: allSyn, label: `Área com ${items.length} estruturas` })}
      <div class="pop-legend">${[...byColor].map(([c, n]) => `<span><i style="background:${c}"></i>${n}</span>`).join('')}<small class="muted">cores = legenda do mapa</small></div>
      <div class="pop-list">${items.slice(0, 8).map((p) => `<button data-pop-id="${e(p.id)}"><i style="background:${p.color}"></i><span>${e(p.label)}</span>${icon('arrow')}</button>`).join('')}${items.length > 8 ? `<small class="muted">+${items.length - 8} — aproxime para ver todas</small>` : ''}</div>
      <div class="pop-act"><button class="btn sm primary" data-pop-zoom>${icon('search')} Aproximar aqui</button><a class="btn sm" href="${gmaps(lat.toFixed(5), lon.toFixed(5))}" target="_blank" rel="noopener noreferrer">Google Maps ↗</a></div>`;
    pop.hidden = false;
    pop.querySelector('[data-pop-close]').onclick = closePop;
    pop.querySelector('[data-pop-zoom]').onclick = () => { closePop(); zoomAt(0.45, +cl.dataset.cx, +cl.dataset.cy); };
    pop.querySelectorAll('[data-pop-id]').forEach((b) => { b.onclick = () => { closePop(); onSelect(b.dataset.popId); }; });
  }
  const act = (t) => { const pin = t.closest?.('.pin'), cl = t.closest?.('.cluster'); if (pin) { closePop(); onSelect(pin.dataset.id); } else if (cl) openCluster(cl); else closePop(); };
  svg.addEventListener('keydown', (ev) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); act(ev.target); } });
  render();
  return {
    update(p, s) { pts = p; sel = s; render(); },
    fit(list) {
      if (!list.length) return;
      const xy = list.filter(p=>Number.isFinite(p.lat)&&Number.isFinite(p.lon)).map((p) => displayPoint(p.lat, p.lon));
      if(!xy.length)return;
      const xs = xy.map((a) => a[0]), ys = xy.map((a) => a[1]);
      const pad = 18, w = Math.max(60, Math.max(...xs) - Math.min(...xs) + 2 * pad), h = Math.max(48, Math.max(...ys) - Math.min(...ys) + 2 * pad);
      const ratio = BASE_VB[2] / BASE_VB[3], W = Math.max(w, h * ratio);
      vb = [(Math.min(...xs) + Math.max(...xs)) / 2 - W / 2, (Math.min(...ys) + Math.max(...ys)) / 2 - W / ratio / 2, W, W / ratio]; render();
    },
    focus(lat, lon, w = 120) { const [x, y] = displayPoint(lat, lon); vb = [x - w / 2, y - w * 0.4, w, w * 0.8]; render(); },
  };
}
