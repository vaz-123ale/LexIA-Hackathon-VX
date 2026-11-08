"""Lê uma lista de funcionários (CSV, XLSX, PDF ou texto colado) e devolve linhas {nome, cargo, email} para a gestão REVISAR.

Regra equipe-import-v1 (determinística, sem IA): cada linha precisa de um e-mail válido; o que vier antes/depois, separado por
; , | ou tabulação, vira nome e cargo. Nada é cadastrado aqui: a tela mostra a prévia e a gestão confirma o envio dos convites.
"""
from __future__ import annotations

import base64
import csv
import io
import re

RULE_VERSION = 'equipe-import-v1'
EMAIL = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
LIMITE = 500


def _linhas_texto(txt: str) -> list[list[str]]:
    out = []
    for ln in txt.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        partes = [p.strip() for p in re.split(r'\t|;|\||,(?=\s*\S)', ln) if p.strip()]
        if len(partes) == 1:  # PDF costuma vir separado só por espaços: "Maria Souza  Técnica de segurança  maria@x.com"
            partes = [p.strip() for p in re.split(r'\s{2,}', ln) if p.strip()]
        out.append(partes)
    return out


def _linha(partes: list[str]) -> dict | None:
    em = next((EMAIL.search(p).group(0) for p in partes if EMAIL.search(p)), None)
    if not em:
        return None
    resto = [p for p in partes if em not in p]
    # e-mail colado no fim do nome (linha de PDF sem separador): "Maria Souza maria@x.com"
    if not resto:
        antes = partes[0].replace(em, '').strip(' -–:;,') if partes else ''
        resto = [antes] if antes else []
    nome = resto[0] if resto else ''
    cargo = resto[1] if len(resto) > 1 else ''
    if re.fullmatch(r'(?i)nome|name|funcion[aá]rio', nome):  # cabeçalho
        return None
    return {'nome': nome[:120], 'cargo': cargo[:80], 'email': em.lower()[:160]}


def ler(nome_arquivo: str, conteudo_b64: str | None = None, texto: str | None = None) -> dict:
    ext = (nome_arquivo or '').lower().rsplit('.', 1)[-1] if '.' in (nome_arquivo or '') else ''
    linhas: list[list[str]] = []
    aviso = None
    if texto:
        linhas = _linhas_texto(texto)
    else:
        raw = base64.b64decode(conteudo_b64 or '')
        if ext == 'xlsx':
            from openpyxl import load_workbook
            wb = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
            for ws in wb.worksheets:
                for row in ws.iter_rows(values_only=True):
                    cells = [str(c).strip() for c in row if c is not None and str(c).strip()]
                    if cells:
                        linhas.append(cells)
        elif ext == 'pdf':
            from pypdf import PdfReader
            txt = '\n'.join((p.extract_text() or '') for p in PdfReader(io.BytesIO(raw)).pages[:50])
            linhas = _linhas_texto(txt)
            if not txt.strip():
                aviso = 'O PDF parece ser uma imagem escaneada (sem texto). Envie em CSV/Excel ou cole a lista.'
        elif ext in ('csv', 'txt', ''):
            txt = raw.decode('utf-8-sig', errors='replace')
            try:
                dialect = csv.Sniffer().sniff(txt[:4000], delimiters=';,\t|')
                linhas = [[c.strip() for c in r if c.strip()] for r in csv.reader(io.StringIO(txt), dialect)]
            except csv.Error:
                linhas = _linhas_texto(txt)
        else:
            return {'linhas': [], 'ignoradas': 0, 'aviso': 'Formato não aceito. Use CSV, Excel (.xlsx), PDF ou cole a lista.', 'rule_version': RULE_VERSION}
    rows, vistos, ign = [], set(), 0
    for p in linhas:
        r = _linha(p)
        if not r or r['email'] in vistos:
            ign += 1 if p else 0
            continue
        vistos.add(r['email'])
        rows.append(r)
        if len(rows) >= LIMITE:
            aviso = f'Limite de {LIMITE} pessoas por envio.'
            break
    return {'linhas': rows, 'ignoradas': ign, 'aviso': aviso, 'rule_version': RULE_VERSION}
