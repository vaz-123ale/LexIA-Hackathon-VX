// Service worker da LexIA: abre offline com a última versão vista.
// Tudo é rede primeiro; o cache só entra quando o servidor está inacessível (modo offline do app).
// POST nunca é armazenado nem repetido: decisões só valem com o servidor disponível.
const VERSION = 'lexia-v81-mapa-categorias';
const SHELL = ['/content-layout.css?v=1', '/js/asset_symbols.js', '/', '/index.html', '/styles.css', '/reference.css', '/precision.css', '/radar_ia.css', '/brand.css', '/js/ws_contas.js', '/js/ws_perfil.js', '/js/ws_equipe.js', '/js/ws_extrator.js', '/js/ws_relatorio.js', '/js/ws_transparencia.js', '/img/brand/logo.png', '/img/brand/logo-claro.png', '/img/brand/paisagem.png', '/img/brand/onda.png', '/js/ws_radar.js', '/js/ws_ia.js', '/js/chat.js', '/js/bubble.js', '/js/geoview.js', '/js/ws_business.js', '/js/ws_compliance.js', '/js/ws_denuncia.js', '/js/ws_hidro.js', '/js/ws_ativos.js', '/js/ws_minas.js', '/js/ws_radar_setor.js', '/img/sidebar-waves.svg', '/rivers.json', '/main.js', '/js/core.js', '/js/map.js', '/js/globe.js', '/js/graph.js',
  '/js/ws_exec_atlas.js', '/js/ws_impact.js', '/js/ws_decision.js', '/js/ws_gov.js', '/js/drawer.js', '/js/project_screen.js', '/js/workbench.js', '/js/account_assistant.mjs', '/js/site.js', '/br_uf.json', '/img/hero-dam.svg',
  '/map.json', '/world.json', '/favicon.svg', '/manifest.webmanifest', '/icons/icon-192.png', '/icons/icon-512.png', '/icons/icon.svg', '/fonts/InterVariable.woff2', '/img/reference-landscape.png', '/img/reference-target.png', '/img/reference-database.png'];

SHELL.push('/img/brand/landscape-identity.jpg', '/img/brand/login-reference.jpeg', '/img/brand/frentes.jpg');
SHELL.push('/img/brand/sector-nuclear.jpg?v=nuclear2', '/img/brand/sector-nuclear.jpg', '/img/brand/sector-mining.jpg', '/img/brand/sector-energy.jpg', '/img/brand/sector-sanitation.jpg');
SHELL.push('/brand.css?v=m79', '/main.js?v=m79', '/js/site.js?v=visual40', '/img/brand/logo-lexia-v6.png');
self.addEventListener('install', (e) => { e.waitUntil(caches.open(VERSION).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting())); });
self.addEventListener('activate', (e) => { e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== VERSION).map((k) => caches.delete(k)))).then(() => self.clients.claim())); });
self.addEventListener('fetch', (e) => {
  const req = e.request, url = new URL(req.url);
  if (req.method !== 'GET' || url.origin !== location.origin) return;
  // Resultados privados por conta nunca vão ao cache compartilhado do navegador.
  if (url.pathname.startsWith('/api/workbench/') || url.pathname.startsWith('/api/audit') || url.pathname==='/api/events' || url.pathname==='/api/radar/drafts') {
    e.respondWith(fetch(req).catch(() => new Response(JSON.stringify({error:'Acompanhamento por conta exige conexão com o servidor.'}),{status:503,headers:{'Content-Type':'application/json'}})));
    return;
  }
  if (url.pathname.startsWith('/api/export/')) return;
  if (url.pathname.startsWith('/api/')) {
    e.respondWith(fetch(req).then((res) => { if (res.ok) { const copy = res.clone(); caches.open(VERSION).then((c) => c.put(req, copy)); } return res; })
      .catch(() => caches.match(req).then((r) => r || new Response(JSON.stringify({ error: 'Sem conexão com o servidor e sem cópia local desta consulta.' }), { status: 503, headers: { 'Content-Type': 'application/json' } }))));
    return;
  }
  // Interface: rede primeiro (sempre a versão mais nova); cache só quando offline.
  e.respondWith(fetch(req).then((res) => { if (res.ok) { const copy = res.clone(); caches.open(VERSION).then((c) => c.put(req, copy)); } return res; })
    .catch(() => caches.match(req).then((r) => r || caches.match('/index.html'))));
});
