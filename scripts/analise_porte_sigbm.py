"""Análise reproduzível: porte do empreendedor × situação declarada das barragens (SIGBM/ANM).

Uso:  python scripts/analise_porte_sigbm.py [caminho/Barragens.csv]
Sem argumento, usa o snapshot mais recente em data/snapshots/sigbm/.

Definições (escolhidas pela equipe, não pela ANM):
- "Pequeno": empreendedor com até 5 barragens no SIGBM, cooperativa (nome contém "cooperativa")
  ou pessoa física (documento no formato de CPF, mascarado pela própria ANM).
- "Grande": empreendedor com mais de 5 barragens.
- Empreendedor = mesmo valor na coluna CPF_CNPJ.
Leitura correta: mostra CONCENTRAÇÃO nos dados declarados; não indica causa nem culpa.
Nenhum nome ou documento de pessoa física é impresso.
"""
import collections
import csv
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def latest_csv() -> Path:
    snaps = sorted((ROOT / 'data' / 'snapshots' / 'sigbm').glob('*/Barragens.csv'))
    if not snaps:
        raise SystemExit('Nenhum snapshot do SIGBM encontrado.')
    return snaps[-1]


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else latest_csv()
    raw = path.read_bytes()
    text = raw.decode('utf-8') if raw[:3] == b'\xef\xbb\xbf' else raw.decode('cp1252')
    delim = max([',', ';'], key=text.split('\n', 1)[0].count)
    rows = list(csv.DictReader(text.splitlines(), delimiter=delim))
    norm = lambda s: unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower()
    K = {norm(k): k for k in rows[0]}
    g = lambda r, k: (r.get(K[norm(k)]) or '').strip()
    own = collections.Counter(g(r, 'CPF_CNPJ') for r in rows)
    is_pf = lambda r: '*' in g(r, 'CPF_CNPJ')
    small = lambda r: own[g(r, 'CPF_CNPJ')] <= 5 or is_pf(r) or 'cooperativa' in norm(g(r, 'Empreendedor'))
    emerg = lambda r: g(r, 'Nível de Emergência') not in ('', '-', 'Sem emergência')
    pop = lambda r: g(r, 'Existência de população a jusante').startswith('Existente')
    pct = lambda a, b: f'{a}/{b} ({100 * a / b:.0f}%)' if b else '-'

    S = [r for r in rows if small(r)]
    B = [r for r in rows if not small(r)]
    E = [r for r in rows if emerg(r)]
    owners_small = {g(r, 'CPF_CNPJ') for r in S}
    print(f'Arquivo: {path}')
    print(f'Barragens: {len(rows)} | empreendedores distintos: {len(own)}')
    print(f'Empreendedores pequenos: {pct(len(owners_small), len(own))}')
    print(f'Barragens de pequenos: {pct(len(S), len(rows))}')
    print(f'Barragens com nível de emergência declarado: {len(E)}')
    print(f'  pertencentes a pequenos: {pct(sum(map(small, E)), len(E))}')
    print(f'  taxa entre pequenos: {pct(sum(map(emerg, S)), len(S))} | entre grandes: {pct(sum(map(emerg, B)), len(B))}')
    ep = [r for r in E if pop(r)]
    print(f'Em emergência com população permanente a jusante: {len(ep)} | de pequenos: {sum(map(small, ep))}')
    pf = [r for r in rows if is_pf(r)]
    print(f'Barragens em nome de pessoa física: {len(pf)} | pessoas distintas: {len({g(r, "CPF_CNPJ") for r in pf})}'
          f' | inseridas na PNSB: {sum(1 for r in pf if g(r, "Inserido na PNSB") == "Sim")}')
    for label, grp in (('cooperativas', [r for r in rows if 'cooperativa' in norm(g(r, 'Empreendedor'))]), ('grandes', B)):
        p = [r for r in grp if g(r, 'Inserido na PNSB') == 'Sim']
        bad = sum(1 for r in p if 'Não Atestado' in g(r, 'Status DCE RISR') or 'Não Enviado' in g(r, 'Status DCE RISR'))
        print(f'DCE RISR não atestada/não enviada (PNSB) — {label}: {pct(bad, len(p))}')


if __name__ == '__main__':
    main()
