"""Decision Pack: relatório HTML imprimível (o navegador salva em PDF) de UMA análise.
Sempre rotulado como AVALIAÇÃO PRELIMINAR. Não é parecer jurídico, laudo nem declaração de conformidade."""
from __future__ import annotations

import html
from datetime import date
from typing import Any

LABEL = {
    'proposed': 'Proposto / em consulta', 'published_not_effective': 'Publicado, ainda sem efeito', 'effective': 'Vigente',
    'historical': 'Histórico', 'revoked': 'Revogado', 'unknown': 'Data de efeito a conferir',
    'candidate_review': 'Candidato à revisão', 'missing_attributes': 'Faltam atributos', 'excluded_by_scope': 'Excluído pelo escopo',
    'no_supported_link': 'Sem vínculo suportado', 'confirmed_applicable_by_human': 'Aplicável — confirmado por humano',
    'rejected_by_human': 'Rejeitado por humano', 'not_assigned': 'Sem responsável', 'pending_review': 'Aguardando revisão',
    'reviewing': 'Em revisão', 'approved_for_action': 'Aprovado para ação', 'action_in_progress': 'Ação em andamento', 'closed': 'Encerrado',
    'urgent': 'Urgente', 'high': 'Alta', 'medium': 'Média', 'low': 'Baixa', 'not_assessed': 'Não avaliada',
}
h = lambda v: html.escape('' if v is None else str(v))


def prov_rows(prov, ax, sources):
    out = []
    for p in prov:
        links = ['<a href="%s">%s · %s</a>' % (h(s['url']), h(s['id']), h(s['title'])) for s in sources if s['id'] in p['sources']]
        if p.get('official_text_url'):
            links.append('<a href="%s">texto oficial</a>' % h(p['official_text_url']))
        vig = '%s → %s' % (h(p.get('valid_from') or p.get('consultation_from') or '—'), h(p.get('valid_to') or p.get('consultation_to') or '—'))
        out.append('<tr><td>%s<br><code>%s</code></td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
            h(p['provision']), h(p['id']), h(p['version']), vig, h(LABEL[ax['normative_lifecycle'].get(p['id'], 'unknown')]), '<br>'.join(links)))
    return ''.join(out)


def render(ctx: dict[str, Any]) -> str:
    f, ax, asset, review = ctx['finding'], ctx['axes'], ctx['asset'], ctx.get('review')
    origin = 'DADO OFICIAL (SIGBM/ANM)' if asset.get('origin') == 'DADO_OFICIAL' else 'CENÁRIO HIPOTÉTICO (dados sintéticos)'
    rows = lambda items: ''.join(f'<tr>{"".join(f"<td>{h(c)}</td>" for c in it)}</tr>' for it in items)
    prov = ctx['provisions']
    snap = ctx.get('snapshot')
    fin = ctx.get('finance') or []
    out = f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Decision Pack — {h(f['scenario'])}:{h(asset['id'])}</title>
<style>body{{font:13px/1.5 Inter,Segoe UI,Arial,sans-serif;color:#111;max-width:900px;margin:24px auto;padding:0 20px}}
h1{{font-size:20px;margin:0}}h2{{font-size:14px;margin:22px 0 6px;border-bottom:1px solid #ccc;padding-bottom:4px}}
.banner{{border:2px solid #b07a1f;background:#fff7e6;padding:10px 12px;margin:12px 0;font-weight:600}}
table{{width:100%;border-collapse:collapse;margin:6px 0}}td,th{{border:1px solid #ddd;padding:5px 7px;text-align:left;vertical-align:top}}th{{background:#f3f3f3}}
.muted{{color:#555}}code{{font-size:11px}}@media print{{.noprint{{display:none}}}}</style></head><body>
<p class="noprint"><button onclick="window.print()">Imprimir / salvar em PDF</button></p>
<h1>LexIA · Decision Pack</h1><div class="muted">Gerado em {h(ctx['generated_at'])} · data-base da análise {h(ctx['as_of'])}</div>
<div class="banner">AVALIAÇÃO PRELIMINAR. Não é parecer jurídico, licença, laudo de engenharia, certificação de segurança nem declaração de conformidade.
A decisão final é de profissional competente.</div>
<h2>1. Objeto</h2><table>{rows([('Ativo', f"{asset['id']} · {asset.get('name')}"), ('Origem do dado', origin),
    ('Responsável na fonte', asset.get('owner_name') or '—'), ('Local', asset.get('region') or f"{asset.get('municipio', '')}/{asset.get('uf', '')}"),
    ('Snapshot', f"{snap['snapshot_id']} · coletado em {snap['fetched_at']} · SHA-256 {snap['sha256'][:16]}…" if snap else 'não se aplica (cenário sintético)'),
    ('Cenário normativo', ctx['scenario']['name'] + ' — ' + ctx['scenario']['subtitle'])])}</table>
<h2>2. Quatro eixos (independentes)</h2><table>{rows([('Ciclo normativo (por dispositivo)', '; '.join(f"{k}: {LABEL[v]}" for k, v in ax['normative_lifecycle'].items()) or '—'),
    ('Avaliação de aplicabilidade', LABEL[ax['applicability_assessment']]), ('Fluxo de trabalho', LABEL[ax['workflow_state']]),
    ('Prioridade LexIA', f"{LABEL[ax['priority']['level']]} (pontuação {ax['priority']['score']}, {ax['priority']['formula_version']}) — " + '; '.join(ax['priority']['justification'])),
    ('Próxima ação', ax['next_action'])])}</table>
<p class="muted">A prioridade é da fila de trabalho da LexIA e não usa a Categoria de Risco (CRI) nem o DPA oficiais.</p>
<h2>3. Por que foi selecionado (regra {h(f['rule_id'])})</h2><table><tr><th>Atributo</th><th>Operador</th><th>Valor</th><th>Resultado</th><th>Dispositivo · versão</th><th>Data</th></tr>
{rows([(e['attribute'], e['operator'], e['value'] if e['value'] is not None else '— (ausente)', e['result'], f"{e['provision'] or '—'} · {e['version'] or '—'}", e['as_of']) for e in ctx['explanation']])}</table>
<p>{h(f['rationale'])}</p>{f"<p class='muted'>{h(f.get('temporal_note'))}</p>" if f.get('temporal_note') else ''}
<h2>4. Dispositivos e fontes</h2><table><tr><th>Dispositivo</th><th>Versão</th><th>Vigência</th><th>Status na data</th><th>Fonte oficial</th></tr>
{prov_rows(prov, ax, ctx['sources'])}</table>
<p class="muted">Textos de dispositivos: resumo curado do dossiê de 05/11/2026; texto integral não armazenado.</p>
<h2>5. O que está faltando</h2><ul>{''.join(f'<li>{h(m)}</li>' for m in f['missing'])}</ul>
<h2>6. Ações candidatas (exigem aceite humano)</h2><ul>{''.join(f'<li>{h(a)}</li>' for a in f['actions'])}</ul><p>Prazo legal: <b>{h(f['legal_deadline'] or 'não expresso na fonte (null)')}</b></p>
<h2>7. Revisão humana</h2>{('<p>Função atribuída: <b>' + h(review.get('assigned_function') or 'não atribuída') + '</b></p><table><tr><th>De → para</th><th>Quem (papel)</th><th>Quando</th><th>Motivo</th><th>Versão da fonte</th></tr>' + rows([(f"{t['from_state']} → {t['to_state']}", f"{t['actor']} ({t['role']})", t['at'], t['reason'], t['source_version']) for t in review['transitions']]) + '</table>') if review else '<p>Nenhuma revisão aberta para esta análise.</p>'}
<h2>8. Evidências registradas</h2>{('<table><tr><th>Item</th><th>Descrição</th><th>Responsável</th><th>SHA-256</th></tr>' + rows([(e['item'], e['description'], e['actor'], e['sha256']) for e in review['evidence']]) + '</table>') if review and review['evidence'] else '<p>Nenhuma.</p>'}
<p class="muted">O hash comprova integridade pontual do registro; não é certificação de inviolabilidade.</p>
<h2>9. Cenário financeiro (premissas do usuário)</h2>{''.join(f"<p><b>{h(o['name'])}</b>: mínimo R$ {o['total']['low']:,.2f} · base R$ {o['total']['base']:,.2f} · máximo R$ {o['total']['high']:,.2f} ({h(fs['estimator_version'])}, salvo por {h(fs['actor'])})</p>" for fs in fin[:1] for o in fs['result']['options']) or '<p>Nenhum cenário salvo.</p>'}
<h2>10. Trilha de auditoria</h2><p>Cadeia {'íntegra' if ctx['chain']['ok'] else 'QUEBRADA'} · {ctx['chain']['checked']} registros verificados.</p>
</body></html>'''
    return out
