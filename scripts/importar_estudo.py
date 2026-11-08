"""Importa o estudo de mercado (docs/Novos docs/Torre_Regulatoria_Planilhas.xlsx) para data/estudo_mercado.json.

Uso: python scripts/importar_estudo.py
Só copia números e textos das abas; não recalcula nem altera premissas. Cada bloco guarda a aba de origem.
"""
import json
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'docs' / 'Novos docs' / 'Torre_Regulatoria_Planilhas.xlsx'
OUT = ROOT / 'data' / 'estudo_mercado.json'


def rows(ws, start=5):
    out = []
    for r in ws.iter_rows(min_row=start, values_only=True):
        if any(c not in (None, '') for c in r):
            out.append(list(r))
    return out


def main():
    wb = openpyxl.load_workbook(SRC, data_only=True)
    painel = {r[0]: {'conservador': r[1], 'base': r[2], 'otimista': r[3], 'leitura': r[4]} for r in rows(wb['Painel']) if r[0]}
    precos = [{'natureza': r[0], 'nome': r[1], 'anual': r[2], 'implantacao': r[3], 'ano': r[4], 'escopo': r[5], 'evidencia': r[6]} for r in rows(wb['Precos'])]
    ocorr = [{'evento': r[0], 'obrigatorias': r[1], 'nao_enviadas': r[2], 'sem_atestar': r[3], 'embargos': r[4], 'outros': r[5], 'ref': r[6]} for r in rows(wb['Ocorrencias'])]
    equil = [{'clientes': r[0], 'receita': r[1], 'custos': r[2], 'resultado': r[3]} for r in rows(wb['Equilibrio']) if isinstance(r[0], (int, float))]
    retorno = {r[0]: {'conservador': r[1], 'base': r[2], 'otimista': r[3], 'leitura': r[4]} for r in rows(wb['Retorno']) if r[0]}
    matriz = [{'oferta': r[0], 'monitora': r[1], 'contexto': r[2], 'obrigacoes': r[3], 'prazos': r[4], 'historico': r[5], 'trilha': r[6], 'encaminha': r[7],
               'obs': r[8], 'evidencia': r[9]} for r in rows(wb['Matriz']) if r[0]]
    concorr = [{'nome': r[0], 'pais': r[1], 'categoria': r[2], 'publico': r[3], 'recursos': r[4], 'preco': r[6], 'fonte': r[9]} for r in rows(wb['Concorrentes']) if r[0]]
    segmentos = [{'segmento': r[0], 'nota': r[7], 'obs': r[8]} for r in rows(wb['Segmentos']) if r[0] and isinstance(r[7], (int, float))]
    mercado = [{'etapa': r[0], 'conservador': r[1], 'base': r[2], 'otimista': r[3], 'fonte': r[4]} for r in rows(wb['Mercado']) if r[0]]
    out = {'fonte': 'Relatório de mercado e viabilidade econômica — Desafio 02 (revisão de 07/11/2026) e planilhas anexas',
           'arquivo': str(SRC.relative_to(ROOT)), 'aviso': 'Estimativas com dados públicos e hipóteses explícitas; sem entrevistas, piloto ou cliente confirmado.',
           'painel': painel, 'precos': precos, 'ocorrencias': ocorr, 'equilibrio': equil, 'retorno': retorno, 'matriz': matriz,
           'concorrentes': concorr, 'segmentos': segmentos, 'mercado': mercado}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding='utf8')
    print('ok', OUT, {k: len(v) if isinstance(v, (list, dict)) else 1 for k, v in out.items()})


if __name__ == '__main__':
    main()
