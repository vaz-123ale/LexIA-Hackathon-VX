"""Prazos regulatórios das barragens (sistema fictício de demonstração)."""
from datetime import date

PRAZO_EIR_DIA = 15                      # dia do mês seguinte ao fim do ciclo de inspeção
VIGENCIA_RES_220 = date(2026, 12, 26)   # vigência da Resolução ANM 220/2025


def prazo_envio_eir(fim_ciclo: date) -> date:
    """Data limite para enviar o Extrato de Inspeção Regular (EIR) pelo SIGBM."""
    mes = fim_ciclo.month % 12 + 1
    ano = fim_ciclo.year + (1 if fim_ciclo.month == 12 else 0)
    return date(ano, mes, PRAZO_EIR_DIA)


def res_220_vigente(hoje: date) -> bool:
    return hoje >= VIGENCIA_RES_220
