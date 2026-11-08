"""Integração AWS com utilidade real (opcional; o sistema funciona sem ela).

1. Cofre de provas (Amazon S3 + Object Lock, modo COMPLIANCE):
   Pela Lei 12.334/2010 o empreendedor responde independentemente de culpa (art. 4º, III). Provar O QUE SE SABIA E QUANDO
   vale dinheiro: cada snapshot oficial, versão de modelo, decisão humana e cabeça da trilha de auditoria vira um objeto
   imutável, com SHA-256 e retenção que nem o administrador da conta consegue apagar antes do prazo.
   Sem bucket configurado, grava em var/vault/ no mesmo formato (mesma chave, mesmo manifesto) — a demonstração não depende de nuvem.

2. Claude via Amazon Bedrock (TORRE_LLM_PROVIDER=bedrock):
   a empresa usa a IA dentro da própria conta AWS (dados não saem do ambiente dela; cobrança no contrato AWS que já existe).

Configuração (variáveis de ambiente ou .env):
  TORRE_S3_BUCKET=nome-do-bucket            # bucket criado com Object Lock (infra/aws/template.yaml)
  TORRE_S3_PREFIX=torre360/                 # opcional
  TORRE_S3_RETENTION_DAYS=1825              # opcional (5 anos)
  AWS_REGION=sa-east-1                      # credenciais pelo mecanismo padrão da AWS (perfil, papel IAM, SSO)
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LOCAL_VAULT = ROOT / 'var' / 'vault'


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


class EvidenceVault:
    def __init__(self, client=None, bucket: str | None = None, prefix: str | None = None, retention_days: int | None = None, local_root: Path = LOCAL_VAULT):
        self.bucket = bucket if bucket is not None else os.environ.get('TORRE_S3_BUCKET') or None
        self.prefix = prefix if prefix is not None else os.environ.get('TORRE_S3_PREFIX', 'torre360/')
        self.retention_days = retention_days or int(os.environ.get('TORRE_S3_RETENTION_DAYS', '1825'))
        self.local_root = local_root
        self._client = client
        self.last_error: str | None = None

    @property
    def mode(self) -> str:
        return 's3' if self.bucket else 'local'

    def client(self):
        if self._client is None:
            import boto3  # só exige boto3 se o S3 estiver configurado
            self._client = boto3.client('s3', region_name=os.environ.get('AWS_REGION') or os.environ.get('AWS_DEFAULT_REGION'))
        return self._client

    def put(self, kind: str, name: str, body: bytes, meta: dict[str, Any] | None = None) -> dict:
        """Grava um objeto de prova. A chave inclui o SHA-256: o mesmo conteúdo nunca é duplicado nem sobrescrito."""
        digest = hashlib.sha256(body).hexdigest()
        key = f"{self.prefix}{kind}/{_now().strftime('%Y/%m/%d')}/{name}.{digest[:16]}"
        record = {'kind': kind, 'name': name, 'key': key, 'sha256': digest, 'bytes': len(body), 'stored_at': _now().isoformat(),
                  'mode': self.mode, 'meta': meta or {}}
        if self.mode == 's3':
            until = _now() + timedelta(days=self.retention_days)
            try:
                self.client().put_object(Bucket=self.bucket, Key=key, Body=body, ChecksumAlgorithm='SHA256',
                                         ObjectLockMode='COMPLIANCE', ObjectLockRetainUntilDate=until,
                                         Metadata={'sha256': digest, 'kind': kind}, ServerSideEncryption='aws:kms')
                record['retain_until'] = until.isoformat()
                self.last_error = None
            except Exception as exc:  # falha de rede/permissão: guarda localmente e avisa (nunca perde a prova)
                self.last_error = f'{type(exc).__name__}: {str(exc)[:200]}'
                record['mode'] = 'local (S3 indisponível)'
                self._local(key, body)
        else:
            self._local(key, body)
        self._index(record)
        return record

    def put_json(self, kind: str, name: str, obj: Any, meta: dict | None = None) -> dict:
        return self.put(kind, name, json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str).encode('utf8'), meta)

    def _local(self, key: str, body: bytes) -> None:
        p = self.local_root / key
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists():  # imutável também no modo local: nunca sobrescreve
            p.write_bytes(body)

    def _index(self, record: dict) -> None:
        self.local_root.mkdir(parents=True, exist_ok=True)
        with (self.local_root / 'index.jsonl').open('a', encoding='utf8') as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + '\n')

    def get(self, key: str) -> bytes:
        """Lê um objeto do cofre (S3 ou cópia local)."""
        p = self.local_root / key
        if p.exists():
            return p.read_bytes()
        if self.mode == 's3':
            return self.client().get_object(Bucket=self.bucket, Key=key)['Body'].read()
        raise FileNotFoundError(key)

    def has(self, kind: str, name: str) -> bool:
        return any(r['kind'] == kind and r['name'] == name for r in self.records(100000))

    def records(self, limit: int = 50) -> list[dict]:
        idx = self.local_root / 'index.jsonl'
        if not idx.exists():
            return []
        lines = idx.read_text(encoding='utf8').splitlines()[-limit:]
        return [json.loads(x) for x in reversed(lines)]

    def verify_local(self, record: dict) -> bool:
        p = self.local_root / record['key']
        return p.exists() and hashlib.sha256(p.read_bytes()).hexdigest() == record['sha256']

    def status(self) -> dict:
        recs = self.records(500)
        return {'mode': self.mode, 'bucket': self.bucket, 'prefix': self.prefix, 'retention_days': self.retention_days,
                'object_lock': 'COMPLIANCE' if self.mode == 's3' else 'local (somente leitura lógica)', 'stored': len(recs),
                'by_kind': {k: sum(1 for r in recs if r['kind'] == k) for k in sorted({r['kind'] for r in recs})},
                'last_error': self.last_error, 'recent': recs[:12],
                'why': 'A lei responsabiliza o empreendedor independentemente de culpa. O cofre prova, com data e hash, o que a empresa sabia e decidiu — e não pode ser apagado antes do prazo.'}


# ---------------------------------------------------------------- Claude: Anthropic direto ou Amazon Bedrock

def llm_provider() -> str:
    """Ordem: escolha explícita (TORRE_LLM_PROVIDER) → Anthropic (se houver chave) → Gemini (se houver chave) → Anthropic (desligado)."""
    explicit = os.environ.get('TORRE_LLM_PROVIDER', '').lower()
    if explicit in ('bedrock', 'gemini', 'anthropic'):
        return explicit
    if os.environ.get('ANTHROPIC_API_KEY'):
        return 'anthropic'
    if os.environ.get('GEMINI_API_KEY'):
        return 'gemini'
    return 'anthropic'


# ---------------------------------------------------------------- Google Gemini (REST, sem SDK)
GEMINI_URL = 'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'


def _gemini_schema(s):
    """Converte o JSON Schema usado com a Claude para o subconjunto OpenAPI aceito pelo Gemini."""
    if isinstance(s, dict):
        out = {}
        for k, v in s.items():
            if k == 'additionalProperties':
                continue
            if k == 'type':
                out['type'] = str(v).upper()
            elif k in ('properties',):
                out[k] = {pk: _gemini_schema(pv) for pk, pv in v.items()}
            else:
                out[k] = _gemini_schema(v)
        return out
    if isinstance(s, list):
        return [_gemini_schema(x) for x in s]
    return s


GEMINI_FALLBACKS = ['gemini-3.5-flash', 'gemini-3.5-flash-lite', 'gemini-flash-latest']


def gemini_request(body: dict, timeout: int = 30, model: str | None = None) -> dict:
    """Tenta o modelo configurado e, se estiver sobrecarregado/indisponível/lento, os modelos de reserva."""
    import json as _json
    import urllib.error
    import urllib.request
    models = list(dict.fromkeys([model or model_name(), *GEMINI_FALLBACKS]))
    last = None
    for m in models:
        req = urllib.request.Request(GEMINI_URL.format(model=m), data=_json.dumps(body).encode('utf8'),
                                     headers={'Content-Type': 'application/json', 'x-goog-api-key': os.environ['GEMINI_API_KEY']})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                out = _json.loads(r.read())
                out['_model'] = m
                return out
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code not in (404, 429, 500, 503):
                raise
        except (TimeoutError, OSError) as exc:
            last = exc
    raise last if last else RuntimeError('Gemini indisponível')


def gemini_structured(system: str, user: str, schema: dict, max_tokens: int = 2000, model: str | None = None) -> str:
    d = gemini_request({'systemInstruction': {'parts': [{'text': system}]}, 'contents': [{'role': 'user', 'parts': [{'text': user}]}],
                        'generationConfig': {'responseMimeType': 'application/json', 'responseSchema': _gemini_schema(schema), 'maxOutputTokens': max(max_tokens, 2048)}}, model=model)
    cand = (d.get('candidates') or [{}])[0]
    if cand.get('finishReason') in ('SAFETY', 'PROHIBITED_CONTENT', 'BLOCKLIST'):
        raise RuntimeError('refusal')
    return ''.join(p.get('text', '') for p in cand.get('content', {}).get('parts', []))


def make_client():
    import anthropic
    if llm_provider() == 'bedrock':
        return anthropic.AnthropicBedrock(aws_region=os.environ.get('AWS_REGION') or os.environ.get('AWS_DEFAULT_REGION') or 'us-east-1')
    return anthropic.Anthropic()


def model_name() -> str:
    if llm_provider() == 'gemini':
        return os.environ.get('TORRE_GEMINI_MODEL', 'gemini-3.5-flash')
    if llm_provider() == 'bedrock':
        # o ID do modelo no Bedrock depende da conta/região: configure explicitamente
        return os.environ.get('TORRE_BEDROCK_MODEL') or os.environ.get('TORRE_LLM_MODEL', 'claude-opus-5-5')
    return os.environ.get('TORRE_LLM_MODEL', 'claude-opus-5-5')


def structured_call(system: str, user: str, schema: dict, max_tokens: int = 2000, effort: str = 'medium', model: str | None = None) -> str:
    """Uma chamada com saída em JSON (schema fechado). No Bedrock, sem o fallback de servidor (não disponível lá)."""
    if llm_provider() == 'gemini':
        return gemini_structured(system, user, schema, max_tokens, model=model)
    client = make_client()
    kw = dict(model=model or model_name(), max_tokens=max_tokens, system=system,
              output_config={'effort': effort, 'format': {'type': 'json_schema', 'schema': schema}},
              messages=[{'role': 'user', 'content': user}])
    if llm_provider() == 'bedrock':
        r = client.messages.create(**kw)
    else:
        r = client.beta.messages.create(betas=['server-side-fallback-2026-07-01'], fallbacks='default', **kw)
    if r.stop_reason == 'refusal':
        raise RuntimeError('refusal')
    return next(b.text for b in r.content if b.type == 'text')


# ---------------------------------------------------------------- custo: determinístico primeiro, IA só quando precisa
# Política (TORRE_LLM_POLICY): "economica" (padrão) = regras e respostas controladas primeiro; IA generativa só quando
# elas não resolvem. Cada chamada usa o modelo mais barato que dá conta da tarefa, passa por cache e por um teto diário.
TIERS = {
    'leve': {'gemini': 'gemini-3.5-flash-lite', 'anthropic': 'claude-haiku-5-5', 'bedrock_env': 'TORRE_BEDROCK_MODEL_LEVE'},
    'padrao': {'gemini': 'gemini-3.5-flash', 'anthropic': 'claude-opus-5-5', 'bedrock_env': 'TORRE_BEDROCK_MODEL'},
}
TASK_TIER = {'filtros': 'leve', 'resumo': 'leve', 'perguntas': 'padrao', 'denuncia': 'padrao', 'planejador': 'padrao', 'extracao': 'padrao', 'redacao': 'leve'}
USAGE: dict = {'dia': None, 'chamadas': 0, 'cache': 0, 'deterministico': 0, 'teto_atingido': 0, 'por_modelo': {}, 'por_tarefa': {},
               'por_cliente': {}, 'por_funcionalidade': {}, 'requisicoes': 0}
_CACHE: dict = {}
import contextvars as _cv
_CLIENT = _cv.ContextVar('lexia_client', default='anonimo')
_FEATURE = _cv.ContextVar('lexia_feature', default='outros')


def _bucket(kind: str, key: str) -> dict:
    return USAGE[kind].setdefault(key, {'requisicoes': 0, 'ia': 0, 'cache': 0, 'deterministico': 0, 'tokens_est': 0})


def _count(field: str, n: int = 1) -> None:
    _bucket('por_cliente', _CLIENT.get())[field] += n
    _bucket('por_funcionalidade', _FEATURE.get())[field] += n


def meter_request(client: str | None, feature: str) -> None:
    """Marca a requisição atual (cliente = Customer/org, funcionalidade = grupo da rota) para medir custo por cliente e por funcionalidade."""
    _roll()
    _CLIENT.set(client or 'anonimo')
    _FEATURE.set(feature or 'outros')
    USAGE['requisicoes'] += 1
    _count('requisicoes')


def economy() -> bool:
    return os.environ.get('TORRE_LLM_POLICY', 'economica').lower() != 'qualidade'


def _today():
    return datetime.now(timezone.utc).date().isoformat()


def _roll():
    if USAGE['dia'] != _today():
        USAGE.update(dia=_today(), chamadas=0, cache=0, deterministico=0, teto_atingido=0, por_modelo={}, por_tarefa={},
                     por_cliente={}, por_funcionalidade={}, requisicoes=0)


def daily_cap() -> int:
    try:
        return int(os.environ.get('TORRE_LLM_MAX_CALLS_DIA', '300'))
    except ValueError:
        return 300


def budget_ok() -> bool:
    _roll()
    return USAGE['chamadas'] < daily_cap()


def note_deterministic(task: str) -> None:
    _roll()
    USAGE['deterministico'] += 1
    _count('deterministico')


def tier_model(task: str) -> str:
    tier = TIERS[TASK_TIER.get(task, 'padrao')]
    prov = llm_provider()
    if prov == 'gemini':
        return os.environ.get('TORRE_GEMINI_MODEL_LEVE' if TASK_TIER.get(task) == 'leve' else 'TORRE_GEMINI_MODEL', tier['gemini'])
    if prov == 'bedrock':
        return os.environ.get(tier['bedrock_env']) or model_name()
    return os.environ.get('TORRE_LLM_MODEL_LEVE' if TASK_TIER.get(task) == 'leve' else 'TORRE_LLM_MODEL', tier['anthropic'])


def usage() -> dict:
    _roll()
    total = USAGE['chamadas'] + USAGE['cache'] + USAGE['deterministico']
    price = os.environ.get('TORRE_LLM_USD_POR_MTOK')  # sem preço configurado, não exibimos custo em dinheiro (não inventamos)
    def _cost(b):
        return round(b['tokens_est'] / 1e6 * float(price), 4) if price else None
    for kind in ('por_cliente', 'por_funcionalidade'):
        for b in USAGE[kind].values():
            b['custo_usd_est'] = _cost(b)
            b['ia_por_requisicao'] = round(b['ia'] / b['requisicoes'], 3) if b['requisicoes'] else None
    return {**USAGE, 'preco_configurado': bool(price), 'teto_diario': daily_cap(), 'politica': 'econômica' if economy() else 'qualidade',
            'resolvido_sem_ia_pct': round(100 * (USAGE['cache'] + USAGE['deterministico']) / total) if total else None,
            'tiers': {k: TASK_TIER[k] for k in TASK_TIER}}


def llm_call(task: str, system: str, user: str, schema: dict, max_tokens: int = 2000, effort: str = 'medium') -> str:
    """Ponto único de chamada generativa: cache → teto diário → modelo do nível da tarefa."""
    import hashlib as _h
    _roll()
    key = _h.sha256('|'.join([llm_provider(), task, system, user, json.dumps(schema, sort_keys=True)]).encode('utf8')).hexdigest()
    if key in _CACHE:
        USAGE['cache'] += 1
        _count('cache')
        return _CACHE[key]
    if not budget_ok():
        USAGE['teto_atingido'] += 1
        raise RuntimeError('teto diário de chamadas de IA atingido')
    model = tier_model(task)
    out = structured_call(system, user, schema, max_tokens=max_tokens, effort=effort, model=model)
    USAGE['chamadas'] += 1
    USAGE['por_modelo'][model] = USAGE['por_modelo'].get(model, 0) + 1
    USAGE['por_tarefa'][task] = USAGE['por_tarefa'].get(task, 0) + 1
    _count('ia')
    _count('tokens_est', (len(system) + len(user) + len(out or '')) // 4)   # estimativa ~4 caracteres por token
    if len(_CACHE) > 2000:
        _CACHE.clear()
    _CACHE[key] = out
    return out
