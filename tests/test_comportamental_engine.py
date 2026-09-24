"""Testes do motor de diagnóstico (puro, sem banco).

Rode com:  pytest -q  (a partir da raiz do pacote)
Usa dados sintéticos representando um mês do orçamento.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.comportamental import engine
from app.comportamental.engine import (
    ContextoDiagnostico,
    LancamentoIn,
    ResumoMes,
    diagnosticar,
)

D = Decimal


def _desp(dia, desc, valor, cat, **kw):
    return LancamentoIn(date(2026, 9, dia), desc, D(valor), cat, "despesa", **kw)


@pytest.fixture
def contexto():
    return ContextoDiagnostico(
        periodo="2026-09",
        receita_liquida=D("10000.00"),
        meta_investimento_pct=D("0.10"),
        metas_variaveis={"Alimentação": D("0.08"), "Farmácia": D("0.02")},
    )


def test_recorrencias_anualiza_custo(contexto):
    lancs = [
        _desp(5, "Net", "120", "Outros", recorrente=True),
        _desp(5, "Academia", "150", "Outros", recorrente=True),
        _desp(5, "Anthropic/Claude", "100", "Tecnologia", recorrente=True),
    ]
    diag = diagnosticar(lancs, contexto)
    rec = next(p for p in diag.padroes if p.chave == "recorrencias")
    # 370/mês * 12 = 4440/ano
    assert rec.valor_envolvido == D("4440.00")
    assert "ano" in rec.evidencia


def test_parcelamento_conta_faturas_futuras(contexto):
    lancs = [
        _desp(10, "Notebook 10x", "300", "Tecnologia", parcela_atual=2, parcela_total=10),
    ]
    diag = diagnosticar(lancs, contexto)
    parc = next(p for p in diag.padroes if p.chave == "parcelamento")
    # restantes = 8 parcelas * 300 = 2400
    assert parc.valor_envolvido == D("2400.00")


def test_sazonal_detecta_ipva(contexto):
    lancs = [_desp(15, "IPVA 2026", "1200", "Transporte")]
    diag = diagnosticar(lancs, contexto)
    saz = next(p for p in diag.padroes if p.chave == "sazonais")
    assert saz.valor_envolvido == D("1200.00")
    assert "caixinha" in saz.recomendacao.lower()


def test_investimento_abaixo_da_meta(contexto):
    lancs = [_desp(3, "Mercado", "500", "Mercado")]
    diag = diagnosticar(lancs, contexto)
    inv = next(p for p in diag.padroes if p.chave == "investimento")
    # meta = 1000, investido = 0, falta = 1000
    assert inv.valor_envolvido == D("1000.00")


def test_investimento_cumprido_nao_gera_padrao(contexto):
    lancs = [
        LancamentoIn(date(2026, 9, 2), "Aporte Tesouro", D("1000"), "Outros", "investimento"),
    ]
    diag = diagnosticar(lancs, contexto)
    assert all(p.chave != "investimento" for p in diag.padroes)


def test_contabilidade_mental_apos_13o(contexto):
    lancs = [
        LancamentoIn(date(2026, 9, 1), "13o salario", D("5000"), "Outros", "receita"),
        _desp(3, "TV nova", "3000", "Tecnologia"),
        _desp(4, "Roupas", "800", "Vestuário"),
    ]
    ctx = contexto
    diag = diagnosticar(lancs, ctx)
    cm = next(p for p in diag.padroes if p.chave == "contabilidade_mental")
    assert cm.valor_envolvido == D("3800")


def test_dor_de_pagar_microtransacoes(contexto):
    lancs = [_desp(d, f"iFood {d}", "25", "Alimentação") for d in range(1, 11)]
    diag = diagnosticar(lancs, contexto)
    assert any(p.chave == "dor_pagar" for p in diag.padroes)


def test_meta_variavel_estourada(contexto):
    # Alimentação meta = 8% de 10000 = 800; gasto 1000 estoura.
    lancs = [_desp(2, "Restaurante", "1000", "Alimentação")]
    diag = diagnosticar(lancs, contexto)
    assert any(p.chave.startswith("meta_") for p in diag.padroes)


def test_inflacao_estilo_vida_com_historico(contexto):
    historico = [
        ResumoMes("2026-07", {"Alimentação": D("50")}),
        ResumoMes("2026-08", {"Alimentação": D("52")}),
    ]
    lancs = [
        _desp(1, "Almoço", "80", "Alimentação"),
        _desp(2, "Almoço", "80", "Alimentação"),
    ]
    diag = diagnosticar(lancs, contexto, historico)
    assert any(p.chave == "inflacao_estilo_vida" for p in diag.padroes)


def test_prioriza_e_limita_a_cinco(contexto):
    lancs = [
        _desp(5, "Net", "120", "Outros", recorrente=True),
        _desp(10, "Notebook", "300", "Tecnologia", parcela_atual=1, parcela_total=10),
        _desp(15, "IPVA", "1200", "Transporte"),
        _desp(2, "Restaurante", "1000", "Alimentação"),
    ] + [_desp(d, f"App {d}", "20", "Lazer") for d in range(1, 12)]
    diag = diagnosticar(lancs, contexto)
    assert len(diag.padroes) <= engine.C.MAX_PADROES
    # confiança alta deve vir antes de baixa
    confs = [p.confianca for p in diag.padroes]
    assert confs == sorted(confs, key=lambda c: {"alta": 0, "media": 1, "baixa": 2}[c])


def test_ressalva_sem_receita():
    ctx = ContextoDiagnostico(periodo="2026-09", receita_liquida=None)
    lancs = [_desp(3, "Mercado", "500", "Mercado")]
    diag = diagnosticar(lancs, ctx)
    assert any("Receita" in r for r in diag.ressalvas)


def test_brl_formata_milhar():
    assert engine._brl(D("4440")) == "R$ 4.440,00"
    assert engine._brl(D("1200.5")) == "R$ 1.200,50"


def test_sem_acento_casa_palavras():
    assert engine._contem("Matrícula escola", engine.C.PALAVRAS_SAZONAIS)
    assert engine._contem("MATRICULA 2027", engine.C.PALAVRAS_SAZONAIS)
