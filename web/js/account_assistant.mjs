// Acompanhamento determinístico. Dados pessoais não são enviados ao provedor.
export function accountBriefing(user, reviews, watched, templates, provisions, asOf) {
  const name = (user?.name || 'Olá').split(' ')[0];
  if (!user || user.kind !== 'empresa') return { name, items: [], scope: 'Sem conta empresarial.' };
  const ids = new Set(watched || []);
  const visible = reviews.filter((r) => ids.has(r.asset_id) || (user.is_demo && r.origin === 'CENARIO_HIPOTETICO'));
  const items = [];
  for (const r of visible) {
    if (['CLOSED', 'REJECTED'].includes(r.state)) continue;
    const team = r.assigned_function === user.function;
    const scope = team ? 'Da sua função' : 'Na carteira acompanhada';
    if (['DRAFT', 'REVIEW_PENDING'].includes(r.state)) items.push({ kind: 'review', id: r.id, title: r.asset_name || r.asset_id,
      text: `${scope}: a revisão ainda não tem decisão registrada. ${r.assigned_function ? 'Atribuída à função ' + r.assigned_function + '.' : 'Sem função responsável atribuída.'}`, action: 'Abrir revisão' });
    const have = new Set((r.evidence || []).map((x) => x.item));
    const missing = (templates[r.scenario] || []).filter((x) => !have.has(x));
    if (missing.length) items.push({ kind: 'evidence', id: r.id, title: r.asset_name || r.asset_id,
      text: `${missing.length} item(ns) do checklist sem evidência registrada. Isso não demonstra descumprimento.`, missing, action: 'Conferir evidências' });
  }
  const pids = new Set(visible.flatMap((r) => r.provisions || []));
  const milestones = provisions.filter((p) => pids.has(p.id) && p.valid_from && p.valid_from > asOf)
    .sort((a, b) => a.valid_from.localeCompare(b.valid_from));
  for (const p of milestones) items.push({ kind: 'milestone', id: p.id, title: `${p.document} · ${p.provision}`,
    text: `Início de vigência catalogado: ${p.valid_from.split('-').reverse().join('/')}. É um marco do dispositivo, não um prazo pessoal nem atualização prevista de toda a norma.`,
    sources: p.sources || [], version: p.version, action: 'Ver no laboratório' });
  return { name, items, scope: user.is_demo ? 'Sua carteira acompanhada + cenários hipotéticos da demonstração. Atribuições são por função, não por pessoa.' : 'Somente revisões de ativos que você adicionou à carteira. Não há isolamento multiempresa de produção nesta demo.' };
}

export function accountIntent(question) {
  const q = question.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  if (/\b(minhas? pendencias?|minha agenda|meu resumo|o que (eu )?preciso fazer)\b/.test(q)) return 'all';
  if (/\b(minhas? revisoes?|o que falta confirmar)\b/.test(q)) return 'review';
  if (/\b(minhas? evidencias?|documentos? faltantes?)\b/.test(q)) return 'evidence';
  if (/\b(meus? (prazos?|marcos?)|proximos marcos)\b/.test(q)) return 'milestone';
  return null;
}
