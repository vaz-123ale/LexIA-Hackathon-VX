"""Gera docs/CHECKLIST_COMPLETO.md a partir de data/checklist.json (fonte única).
Uso: python scripts/gerar_checklist.py
"""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ck = json.loads((ROOT / 'data' / 'checklist.json').read_text(encoding='utf8'))
items = ck['items']
icon = {'FEITO': '[x]', 'SIMULADO': '[~]', 'PLANEJADO': '[ ]'}
st = Counter(i['status'] for i in items)
ac = Counter(i['actor'] for i in items)

out = ['# Checklist completo — LexIA', '',
       '> Gerado de `data/checklist.json` por `scripts/gerar_checklist.py`. A mesma lista aparece na tela **Checklist & papel da IA**.', '',
       '## Regra de ouro', '',
       '**A IA propõe → regras versionadas verificam → humano competente decide → o sistema registra.**', '',
       '| Ator | O que faz | O que nunca faz |', '|---|---|---|',
       '| ✦ **IA** | Classifica fontes; compara versões; extrai obrigações candidatas com trecho; sugere vínculos com ativos; redige em linguagem simples e técnica; se abstém sem base | Decidir conformidade; inventar prazo, multa ou sanção; inferir obrigação pelo nome da empresa; publicar tarefa |',
       '| ⚙ **Regra** | Calcula vigência por dispositivo; testa condições/exceções; agente crítico; verifica cada citação da IA; bloqueia ingestão interna, protegida ou suspeita | Interpretar texto livre |',
       '| ◉ **Humano** | Confirma/rejeita achados (jurídico, compliance, especialista); registra motivo e versão; anexa evidência; autoriza envios | — |',
       '| ▣ **Sistema** | Gêmeo digital; trilha de auditoria com hash; grafo com proveniência; conectores e exportações | Enviar algo para fora sem aceite humano |', '',
       '## Placar', '',
       f"- Feito: **{st['FEITO']}** · Simulado: **{st['SIMULADO']}** · Planejado: **{st['PLANEJADO']}** (total {len(items)})",
       f"- Por ator: IA {ac['IA']} · Regra {ac['REGRA']} · Humano {ac['HUMANO']} · Sistema {ac['SISTEMA']}", '',
       'Legenda: `[x]` feito e testado · `[~]` funciona com dados/conectores simulados · `[ ]` planejado.', '']
for area in dict.fromkeys(i['area'] for i in items):
    out += [f'## {area}', '', '| | Item | Ator | Onde | Como verificar |', '|---|---|---|---|---|']
    for i in (x for x in items if x['area'] == area):
        out.append(f"| {icon[i['status']]} | {i['item']} | {i['actor']} | {i['where']} | {i['verify']} |")
    out.append('')
(ROOT / 'docs' / 'CHECKLIST_COMPLETO.md').write_text('\n'.join(out), encoding='utf8')
print('OK', len(items), 'itens')
