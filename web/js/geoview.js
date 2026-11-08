// Vista de satélite de um ponto + atalhos para o Google Maps.
// Imagem: mosaico de blocos do Esri World Imagery (atribuição obrigatória exibida).
// Pontos de CENÁRIO HIPOTÉTICO não recebem imagem: as coordenadas não representam instalações reais.
import { e, icon } from './core.js';

const TILE = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile';

function tileXY(lat, lon, z) {
  const n = 2 ** z, rad = (lat * Math.PI) / 180;
  return [((lon + 180) / 360) * n, ((1 - Math.log(Math.tan(rad) + 1 / Math.cos(rad)) / Math.PI) / 2) * n];
}

export const gmaps = (lat, lon) => `https://www.google.com/maps/search/?api=1&query=${lat},${lon}`;
export const gsat = (lat, lon, z = 17) => `https://www.google.com/maps/@?api=1&map_action=map&center=${lat},${lon}&zoom=${z}&basemap=satellite`;

/** Mosaico 3×3 centrado no ponto. opts: {zoom, height, label, synthetic, area} */
export function satView(lat, lon, opts = {}) {
  if (!Number.isFinite(+lat) || !Number.isFinite(+lon)) return '';
  if (opts.synthetic) {
    return `<div class="sat sat-off"><div>${icon('pin')}<b>Ponto de cenário hipotético</b><small>Coordenada ilustrativa, não é uma instalação real; por isso não mostramos imagem de satélite.</small></div></div>`;
  }
  const z = opts.zoom || 16, h = opts.height || 200;
  const [fx, fy] = tileXY(+lat, +lon, z), tx = Math.floor(fx), ty = Math.floor(fy);
  const ox = (fx - tx) * 256 + 256, oy = (fy - ty) * 256 + 256; // posição do ponto dentro do mosaico 768×768
  let tiles = '';
  for (let j = -1; j <= 1; j++) for (let i = -1; i <= 1; i++) tiles += `<img alt="" loading="lazy" decoding="async" src="${TILE}/${z}/${ty + j}/${tx + i}" style="left:${(i + 1) * 256}px;top:${(j + 1) * 256}px">`;
  return `<figure class="sat" style="height:${h}px">
    <div class="sat-mosaic" style="left:calc(50% - ${ox.toFixed(0)}px);top:calc(50% - ${oy.toFixed(0)}px)">${tiles}</div>
    ${opts.area ? '<span class="sat-area" aria-hidden="true"></span>' : `<span class="sat-pin" aria-hidden="true">${icon('pin')}</span>`}
    <figcaption><span>${e(opts.label || 'Imagem de satélite')}</span><small>Imagem: Esri, Maxar, Earthstar Geographics · pode não ser recente</small></figcaption>
  </figure>
  <div class="sat-links"><a class="btn sm" href="${gsat(lat, lon, z + 1)}" target="_blank" rel="noopener noreferrer">${icon('pin')} Google Maps (satélite) ↗</a><a class="btn sm ghost" href="${gmaps(lat, lon)}" target="_blank" rel="noopener noreferrer">Abrir local ↗</a><small class="muted">${(+lat).toFixed(5)}, ${(+lon).toFixed(5)}</small></div>`;
}
