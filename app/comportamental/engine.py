"""Motor de diagnóstico comportamental.

Camada determinística e SEM dependência de banco/ORM: recebe uma lista neutra
de lançamentos (DTO `LancamentoIn`) e um contexto, e devolve um `Diagnostico`
com os 3 a 5 padrões psicológicos mais relevantes do período, cada um ancorado
em evidência numérica concreta.

É a mesma lógica descrita no "prompt revisor de gastos": aqui ela vira código,
para alimentar a tela "Diagnóstico do mês" do MVP. Como não toca em ORM nem em
FastAPI, roda e é testável isoladamente (ver tests/test_engine.py).

Regra de ouro: NUNCA inventar valores. Se falta informação para um achado, o
detector simplesmente não o emite (ou baixa a confiança).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from unicodedata import combining, normalize

from . import constants as C

ZERO = Decimal("0")


# --------------------------------------------------------------------------- #
# DTOs de entrada/saída (neutros — independem do ORM)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class LancamentoIn:
    """Um lançamento normalizado, como o motor precisa vê-lo.

    O adaptador do MVP (services.py) converte a linha do banco / a fatura
    Nubank importada para este formato antes de chamar o motor.
    """

    data: date
    descricao: str
    valor: Decimal  # sempre positivo; o sinal fica em `tipo`
    categoria: str
    tipo: str = "despesa"  # "despesa" | "receita" | "investimento"
    meio_pagamento: str | None = None  # cartao_credito | debito | pix | dinheiro | boleto
    recorrente: bool = False  # despesa fixa / assinatura
    parcela_atual: int | None = None
    parcela_total: int | None = None

    @property
    def eh_despesa(self) -> bool:
        return self.tipo == "despesa"

    @property
    def eh_parcelado(self) -> bool:
        return bool(self.parcela_total and self.parcela_total > 1)


@dataclass
class ContextoDiagnostico:
    """Contexto do usuário para o período analisado."""

    periodo: str  # ex.: "2026-09"
    receita_liquida: Decimal | None = None
    meta_investimento_pct: Decimal = C.META_INVESTIMENTO_PADRAO
    metas_variaveis: dict[str, Decimal] = field(default_factory=dict)  # categoria -> fração


@dataclass
class ResumoMes:
    """Resumo de um mês anterior, usado para detectar tendência/inflação."""

    periodo: str
    ticket_medio_por_categoria: dict[str, Decimal] = field(default_factory=dict)


@dataclass
class Padrao:
    """Um padrão comportamental detectado."""

    chave: str
    titulo: str
    evidencia: str
    vies: str
    confianca: str
    recomendacao: str
    valor_envolvido: Decimal = ZERO

    def to_dict(self) -> dict:
        return {
            "chave": self.chave,
            "titulo": self.titulo,
            "evidencia": self.evidencia,
            "vies": self.vies,
            "confianca": self.confianca,
            "recomendacao": self.recomendacao,
            "valor_envolvido": str(self.valor_envolvido),
        }


@dataclass
class Diagnostico:
    periodo: str
    total_analisado: Decimal
    qtd_lancamentos: int
    padroes: list[Padrao] = field(default_factory=list)
    ressalvas: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "periodo": self.periodo,
            "total_analisado": str(self.total_analisado),
            "qtd_lancamentos": self.qtd_lancamentos,
            "padroes": [p.to_dict() for p in self.padroes],
            "ressalvas": self.ressalvas,
        }


# --------------------------------------------------------------------------- #
# Utilitários
# --------------------------------------------------------------------------- #
def _sem_acento(texto: str) -> str:
    forma = normalize("NFKD", texto.lower())
    return "".join(ch for ch in forma if not combining(ch))


def _contem(descricao: str, palavras: tuple[str, ...]) -> bool:
    alvo = _sem_acento(descricao)
    return any(_sem_acento(p) in alvo for p in palavras)


def _brl(valor: Decimal) -> str:
    q = valor.quantize(Decimal("0.01"))
    inteiro, _, dec = f"{q:.2f}".partition(".")
    sinal = "-" if inteiro.startswith("-") else ""
    inteiro = inteiro.lstrip("-")
    grupos = []
    while len(inteiro) > 3:
        grupos.insert(0, inteiro[-3:])
        inteiro = inteiro[:-3]
    grupos.insert(0, inteiro)
    return f"R$ {sinal}{'.'.join(grupos)},{dec}"


def _pct(parte: Decimal, todo: Decimal) -> Decimal:
    if todo == ZERO:
        return ZERO
    return (parte / todo * 100).quantize(Decimal("0.1"))


# --------------------------------------------------------------------------- #
# Detectores — cada um retorna Padrao | None
# --------------------------------------------------------------------------- #
def _det_contabilidade_mental(lancs: list[LancamentoIn]) -> Padrao | None:
    entradas = [
        lanc for lanc in lancs
        if lanc.tipo == "receita" and _contem(lanc.descricao, C.PALAVRAS_ENTRADA_ATIPICA)
    ]
    if not entradas:
        return None
    envolvido = ZERO
    itens = 0
    for entrada in entradas:
        janela_fim = entrada.data + timedelta(days=C.JANELA_CONTABILIDADE_MENTAL_DIAS)
        for lanc in lancs:
            if (
                lanc.eh_despesa
                and lanc.categoria in C.CATEGORIAS_SUPERFLUAS
                and entrada.data <= lanc.data <= janela_fim
            ):
                envolvido += lanc.valor
                itens += 1
    if itens == 0:
        return None
    nomes = ", ".join(sorted({e.descricao for e in entradas}))
    return Padrao(
        chave="contabilidade_mental",
        titulo="Gasto extra logo após uma entrada atípica",
        evidencia=(
            f"Após a(s) entrada(s) '{nomes}', {itens} gasto(s) em categorias "
            f"supérfluas somaram {_brl(envolvido)} em até "
            f"{C.JANELA_CONTABILIDADE_MENTAL_DIAS} dias."
        ),
        vies="Contabilidade mental: dinheiro 'extra' é tratado como se valesse menos.",
        confianca=C.CONF_MEDIA,
        recomendacao=(
            "Trate 13º, bônus e restituição como parte do mesmo orçamento: destine "
            "uma fatia à meta de investimento antes de liberar o restante para consumo."
        ),
        valor_envolvido=envolvido,
    )


def _det_recorrencias(lancs: list[LancamentoIn]) -> Padrao | None:
    recorrentes = [lanc for lanc in lancs if lanc.recorrente and lanc.eh_despesa]
    if not recorrentes:
        return None
    mensal = sum((lanc.valor for lanc in recorrentes), ZERO)
    anual = mensal * 12
    top = sorted(recorrentes, key=lambda lanc: lanc.valor, reverse=True)[:5]
    lista = "; ".join(f"{lanc.descricao} ({_brl(lanc.valor * 12)}/ano)" for lanc in top)
    return Padrao(
        chave="recorrencias",
        titulo="Assinaturas e fixos custam mais do que parecem no ano",
        evidencia=(
            f"{len(recorrentes)} recorrências somam {_brl(mensal)}/mês = "
            f"{_brl(anual)}/ano. Maiores: {lista}."
        ),
        vies="Aversão à perda e efeito posse: manter é mais fácil do que cortar.",
        confianca=C.CONF_ALTA,
        recomendacao=(
            "Revise a lista pelo custo ANUAL, não pela mensalidade. Cancele o que "
            "tem uso baixo — cada corte multiplica por 12."
        ),
        valor_envolvido=anual,
    )


def _det_parcelamento(lancs: list[LancamentoIn]) -> Padrao | None:
    parcelados = [lanc for lanc in lancs if lanc.eh_parcelado and lanc.eh_despesa]
    if not parcelados:
        return None
    comprometido_futuro = ZERO
    for lanc in parcelados:
        restantes = (lanc.parcela_total or 0) - (lanc.parcela_atual or 0)
        if restantes > 0:
            comprometido_futuro += lanc.valor * restantes
    if comprometido_futuro == ZERO:
        return None
    return Padrao(
        chave="parcelamento",
        titulo="Parcelas comprometem os próximos meses",
        evidencia=(
            f"{len(parcelados)} compra(s) parcelada(s) deixam {_brl(comprometido_futuro)} "
            f"já comprometidos em faturas futuras."
        ),
        vies="Dor de pagar diluída: 'cabe na parcela' esconde o custo total.",
        confianca=C.CONF_ALTA,
        recomendacao=(
            "Some sempre o valor TOTAL, não a parcela. Antes de parcelar, cheque quanto "
            "das próximas faturas já está preso a compras passadas."
        ),
        valor_envolvido=comprometido_futuro,
    )


def _det_sazonais(lancs: list[LancamentoIn], ctx: ContextoDiagnostico) -> Padrao | None:
    sazonais = [
        lanc for lanc in lancs
        if lanc.eh_despesa and _contem(lanc.descricao, C.PALAVRAS_SAZONAIS)
    ]
    if not sazonais:
        return None
    total = sum((lanc.valor for lanc in sazonais), ZERO)
    if ctx.receita_liquida:
        limite = ctx.receita_liquida * C.FRACAO_SAZONAL_RELEVANTE
        if total < limite:
            return None
        proporcao = f" ({_pct(total, ctx.receita_liquida)}% da receita)"
    else:
        proporcao = ""
    nomes = ", ".join(sorted({lanc.descricao for lanc in sazonais}))
    return Padrao(
        chave="sazonais",
        titulo="Despesa sazonal estourou o mês sem reserva",
        evidencia=(
            f"Gastos irregulares ({nomes}) somaram {_brl(total)}{proporcao} — o tipo de "
            f"despesa que costuma chegar 'de surpresa'."
        ),
        vies="Viés do otimismo: despesas grandes e esporádicas são esquecidas no plano.",
        confianca=C.CONF_ALTA,
        recomendacao=(
            "Crie uma caixinha mensal para gastos sazonais (IPVA, IPTU, matrícula, seguro, "
            "presentes): guarde 1/12 do custo anual estimado todo mês."
        ),
        valor_envolvido=total,
    )


def _det_dor_pagar(lancs: list[LancamentoIn]) -> Padrao | None:
    despesas = [lanc for lanc in lancs if lanc.eh_despesa]
    if not despesas:
        return None
    total = sum((lanc.valor for lanc in despesas), ZERO)
    no_cartao = sum(
        (lanc.valor for lanc in despesas if lanc.meio_pagamento in C.MEIOS_DILUEM_DOR), ZERO
    )
    micro = [lanc for lanc in despesas if lanc.valor <= C.LIMITE_MICROTRANSACAO]
    soma_micro = sum((lanc.valor for lanc in micro), ZERO)

    fracao_cartao = (no_cartao / total) if total else ZERO
    gatilho_cartao = fracao_cartao >= C.FRACAO_CARTAO_ALERTA and no_cartao > ZERO
    gatilho_micro = len(micro) >= C.MIN_MICROTRANSACOES
    if not (gatilho_cartao or gatilho_micro):
        return None

    partes = []
    if gatilho_cartao:
        partes.append(
            f"{_pct(no_cartao, total)}% dos gastos ({_brl(no_cartao)}) passaram no cartão"
        )
    if gatilho_micro:
        partes.append(
            f"{len(micro)} microtransações (≤ {_brl(C.LIMITE_MICROTRANSACAO)}) "
            f"somaram {_brl(soma_micro)}"
        )
    return Padrao(
        chave="dor_pagar",
        titulo="Pagamento invisível facilita o gasto",
        evidencia="; ".join(partes) + ".",
        vies="Dor de pagar diluída: cartão e microcompras somem da percepção.",
        confianca=C.CONF_MEDIA if gatilho_micro and not gatilho_cartao else C.CONF_ALTA,
        recomendacao=(
            "Torne o gasto visível: acompanhe a fatura em tempo real e defina um teto "
            "semanal para as pequenas compras que mais vazam."
        ),
        valor_envolvido=soma_micro if gatilho_micro else no_cartao,
    )


def _det_impulso(lancs: list[LancamentoIn]) -> Padrao | None:
    despesas = [
        lanc for lanc in lancs if lanc.eh_despesa and lanc.categoria in C.CATEGORIAS_IMPULSO
    ]
    if not despesas:
        return None
    fim_de_semana = [lanc for lanc in despesas if lanc.data.weekday() >= 5]
    # Repetição: várias compras na mesma categoria em janela curta.
    por_cat: dict[str, list[LancamentoIn]] = {}
    for lanc in despesas:
        por_cat.setdefault(lanc.categoria, []).append(lanc)
    repetidas = {c: v for c, v in por_cat.items() if len(v) >= C.MIN_REPETICOES_IMPULSO}

    if len(fim_de_semana) < 3 and not repetidas:
        return None
    envolvido = sum((lanc.valor for lanc in fim_de_semana), ZERO)
    for v in repetidas.values():
        envolvido = max(envolvido, sum((lanc.valor for lanc in v), ZERO))
    detalhes = []
    if len(fim_de_semana) >= 3:
        detalhes.append(
            f"{len(fim_de_semana)} compras de fim de semana em categorias de impulso "
            f"({_brl(sum((lanc.valor for lanc in fim_de_semana), ZERO))})"
        )
    for cat, v in repetidas.items():
        detalhes.append(f"{len(v)}x em {cat} ({_brl(sum((lanc.valor for lanc in v), ZERO))})")
    return Padrao(
        chave="impulso",
        titulo="Sinais de compra por impulso",
        evidencia="; ".join(detalhes) + ".",
        vies="Fadiga de autocontrole e imediatismo: o impulso vence no cansaço.",
        confianca=C.CONF_BAIXA,
        recomendacao=(
            "Crie fricção: uma regra de 24h antes de compras não essenciais dessas "
            "categorias costuma derrubar boa parte do impulso."
        ),
        valor_envolvido=envolvido,
    )


def _det_meta_variavel(lancs: list[LancamentoIn], ctx: ContextoDiagnostico) -> list[Padrao]:
    if not (ctx.receita_liquida and ctx.metas_variaveis):
        return []
    gasto_cat: dict[str, Decimal] = {}
    for lanc in lancs:
        if lanc.eh_despesa:
            gasto_cat[lanc.categoria] = gasto_cat.get(lanc.categoria, ZERO) + lanc.valor
    achados: list[Padrao] = []
    for cat, pct in ctx.metas_variaveis.items():
        teto = ctx.receita_liquida * pct
        gasto = gasto_cat.get(cat, ZERO)
        if teto == ZERO:
            continue
        if gasto >= teto * C.FRACAO_META_ALERTA:
            estourou = gasto > teto
            achados.append(
                Padrao(
                    chave=f"meta_{cat.lower()}",
                    titulo=f"Meta de {cat} {'estourada' if estourou else 'quase no limite'}",
                    evidencia=(
                        f"{cat}: {_brl(gasto)} vs meta de {_brl(teto)} "
                        f"({(pct * 100).quantize(Decimal('0.1'))}% da receita) — "
                        f"{_pct(gasto, teto)}% da meta."
                    ),
                    vies="Inflação do estilo de vida: o teto vira piso sem que se perceba.",
                    confianca=C.CONF_ALTA,
                    recomendacao=(
                        f"Reavalie a meta de {cat}: ou ajuste o teto conscientemente, ou "
                        f"identifique o que puxou o gasto acima do planejado."
                    ),
                    valor_envolvido=max(gasto - teto, ZERO),
                )
            )
    return achados


def _det_inflacao(lancs: list[LancamentoIn], historico: list[ResumoMes]) -> Padrao | None:
    if not historico:
        return None
    ticket_atual: dict[str, list[Decimal]] = {}
    for lanc in lancs:
        if lanc.eh_despesa:
            ticket_atual.setdefault(lanc.categoria, []).append(lanc.valor)
    medias_atuais = {
        c: (sum(v, ZERO) / len(v)) for c, v in ticket_atual.items() if v
    }
    # média histórica por categoria
    hist_cat: dict[str, list[Decimal]] = {}
    for m in historico:
        for c, t in m.ticket_medio_por_categoria.items():
            hist_cat.setdefault(c, []).append(t)
    pior_cat = None
    pior_cresc = ZERO
    for c, atual in medias_atuais.items():
        base_lst = hist_cat.get(c)
        if not base_lst:
            continue
        base = sum(base_lst, ZERO) / len(base_lst)
        if base <= ZERO:
            continue
        cresc = (atual - base) / base
        if cresc >= C.CRESCIMENTO_INFLACAO_ALERTA and cresc > pior_cresc:
            pior_cresc, pior_cat = cresc, c
    if not pior_cat:
        return None
    return Padrao(
        chave="inflacao_estilo_vida",
        titulo=f"Ticket médio de {pior_cat} vem subindo",
        evidencia=(
            f"O gasto médio por compra em {pior_cat} está "
            f"{(pior_cresc * 100).quantize(Decimal('0.1'))}% acima da média dos meses "
            f"anteriores."
        ),
        vies="Inflação do estilo de vida: o padrão sobe junto com o hábito, não com a renda.",
        confianca=C.CONF_MEDIA,
        recomendacao=(
            f"Olhe o que mudou em {pior_cat}: novo hábito, novo fornecedor ou 'upgrade' "
            f"silencioso? Decida se é uma escolha ou um deslize."
        ),
        valor_envolvido=ZERO,
    )


def _det_investimento(lancs: list[LancamentoIn], ctx: ContextoDiagnostico) -> Padrao | None:
    if not ctx.receita_liquida:
        return None
    meta = ctx.receita_liquida * ctx.meta_investimento_pct
    if meta <= ZERO:
        return None
    investido = sum(
        (lanc.valor for lanc in lancs if lanc.tipo == "investimento"), ZERO
    )
    if investido >= meta:
        return None
    falta = meta - investido
    return Padrao(
        chave="investimento",
        titulo="Meta de investimento ainda não foi cumprida",
        evidencia=(
            f"Investido {_brl(investido)} de uma meta de {_brl(meta)} "
            f"({(ctx.meta_investimento_pct * 100).quantize(Decimal('0.1'))}% da receita). "
            f"Faltam {_brl(falta)}."
        ),
        vies="Desconto hiperbólico: poupar 'o que sobra' quase nunca sobra.",
        confianca=C.CONF_ALTA,
        recomendacao=(
            "Inverta a ordem: pague-se primeiro. Reserve a meta de investimento no início "
            "do mês, como se fosse a primeira despesa, e viva com o restante."
        ),
        valor_envolvido=falta,
    )


# --------------------------------------------------------------------------- #
# Orquestração
# --------------------------------------------------------------------------- #
def diagnosticar(
    lancamentos: list[LancamentoIn],
    contexto: ContextoDiagnostico,
    historico: list[ResumoMes] | None = None,
) -> Diagnostico:
    """Roda todos os detectores e devolve os padrões priorizados."""
    historico = historico or []
    despesas = [lanc for lanc in lancamentos if lanc.eh_despesa]
    total = sum((lanc.valor for lanc in despesas), ZERO)

    candidatos: list[Padrao] = []
    for det in (
        _det_investimento,
        _det_recorrencias,
        _det_parcelamento,
        _det_sazonais,
        _det_dor_pagar,
        _det_contabilidade_mental,
        _det_impulso,
        _det_inflacao,
    ):
        # detectores têm assinaturas diferentes; despacha conforme necessário
        if det is _det_sazonais or det is _det_investimento:
            res = det(lancamentos, contexto)  # type: ignore[call-arg]
        elif det is _det_inflacao:
            res = det(lancamentos, historico)  # type: ignore[call-arg]
        else:
            res = det(lancamentos)  # type: ignore[call-arg]
        if res:
            candidatos.append(res)
    candidatos.extend(_det_meta_variavel(lancamentos, contexto))

    # Prioriza: confiança alta primeiro, depois maior valor envolvido.
    ordem_conf = {C.CONF_ALTA: 0, C.CONF_MEDIA: 1, C.CONF_BAIXA: 2}
    candidatos.sort(
        key=lambda p: (ordem_conf.get(p.confianca, 3), -p.valor_envolvido)
    )
    padroes = candidatos[: C.MAX_PADROES]

    ressalvas: list[str] = []
    if contexto.receita_liquida is None:
        ressalvas.append(
            "Receita líquida não informada — metas e proporções não puderam ser avaliadas."
        )
    if not historico:
        ressalvas.append(
            "Sem histórico de meses anteriores — tendência/inflação do estilo de vida "
            "não pôde ser medida."
        )
    if len(padroes) < C.MIN_PADROES:
        ressalvas.append(
            "Poucos padrões relevantes neste período: mais meses de dados aumentam a "
            "precisão do diagnóstico."
        )

    return Diagnostico(
        periodo=contexto.periodo,
        total_analisado=total,
        qtd_lancamentos=len(lancamentos),
        padroes=padroes,
        ressalvas=ressalvas,
    )
