// Bolinha flutuante: mini-chat para perguntas rápidas. A página Central de IA tem a versão completa.
import { e, icon, currentUser } from './core.js';
import { chat, send, msgHtml, SUGGEST } from './chat.js';

let el = null, open = false;

function render() {
  if (!el) return;
  el.querySelector('.bub-btn').setAttribute('aria-expanded', String(open));
  el.classList.toggle('open', open);
  if (!open) return;
  const p = el.querySelector('.bub-panel');
  p.innerHTML = `<header class="bub-h"><span class="bub-av">${icon('spark')}</span><div><b>Pergunta rápida</b><small>Filtra barragens e responde o básico</small></div><a class="btn sm ghost" href="#/ia" data-bub-close>Abrir IA completa</a><button class="icon-btn" data-bub-close aria-label="Fechar">×</button></header>
    <div class="bub-msgs" aria-live="polite">${chat.msgs.length ? chat.msgs.slice(-8).map((m) => msgHtml(m, true)).join('') : `<p class="muted sm">Experimente:</p><div class="bub-sug">${SUGGEST.slice(0, 4).map((s) => `<button class="chip-btn" data-s="${e(s)}">${e(s)}</button>`).join('')}</div>`}${chat.busy ? '<div class="cm ia typing"><span></span><span></span><span></span></div>' : ''}</div>
    <form class="bub-f"><input placeholder="Ex.: inativas sem projeto em MG" aria-label="Pergunta" ${chat.busy ? 'disabled' : ''}><button class="btn primary sm" aria-label="Enviar">${icon('arrow')}</button></form>
    <small class="bub-foot">A IA propõe; regras verificam; humano confirma.</small>`;
  const m = p.querySelector('.bub-msgs'); m.scrollTop = m.scrollHeight;
  p.querySelector('form').addEventListener('submit', (ev) => { ev.preventDefault(); send(ev.target.querySelector('input').value); });
  p.querySelectorAll('[data-s]').forEach((b) => b.addEventListener('click', () => send(b.dataset.s)));
  p.querySelectorAll('[data-bub-close]').forEach((b) => b.addEventListener('click', () => { open = false; render(); }));
  p.querySelectorAll('.cm-r').forEach((a) => a.addEventListener('click', () => { open = false; render(); }));
  if (!chat.busy) p.querySelector('input').focus();
}

export function mountBubble(show) {
  if (!show || !currentUser()) { el?.remove(); el = null; return; }
  if (location.hash.startsWith('#/ia')) { el?.remove(); el = null; return; } // a página completa já está aberta
  if (el) return;
  el = document.createElement('div'); el.className = 'bubble';
  el.innerHTML = `<div class="bub-panel" role="dialog" aria-label="Mini-chat da IA"></div><button class="bub-btn" aria-label="Abrir pergunta rápida" aria-expanded="false" title="Pergunta rápida (IA)">${icon('spark')}<span class="bub-pulse"></span></button>`;
  document.body.appendChild(el);
  el.querySelector('.bub-btn').addEventListener('click', () => { open = !open; render(); });
  chat.listeners.add(render);
}
document.addEventListener('keydown', (ev) => { if (ev.key === 'Escape' && open) { open = false; render(); } });
