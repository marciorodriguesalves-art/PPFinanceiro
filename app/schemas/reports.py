from pydantic import BaseModel


class CategorySpend(BaseModel):
    category_id: int | None
    category: str
    amount: float
    target: float | None = None
    deviation: float | None = None  # amount - target (positivo = acima da meta)
    deviation_rate: float | None = None  # deviation / target


class KPIs(BaseModel):
    receita_liquida: float
    receita_bruta: float
    total_gastos: float
    total_fixos: float
    total_variaveis: float
    total_parcelas: float
    saldo_disponivel: float
    investimento_meta: float
    investimento_previsto: float  # saldo após gastos, se positivo
    taxa_comprometimento: float  # total_gastos / receita_liquida
    taxa_investimento_prevista: float  # investimento_previsto / receita_liquida
    atende_meta_investimento: bool


class ActionItem(BaseModel):
    prioridade: int
    categoria: str
    tipo: str  # "desvio_meta" | "investimento" | "comprometimento" | "fixo_pendente"
    mensagem: str
    valor_sugerido_corte: float


class ActionPlan(BaseModel):
    competencia: str
    resumo: str
    itens: list[ActionItem]
    corte_total_sugerido: float
    saldo_projetado_pos_ajuste: float
    investimento_projetado_pos_ajuste: float


class MonthlyStatement(BaseModel):
    competencia: str
    kpis: KPIs
    gastos_por_categoria: list[CategorySpend]
    desvios: list[CategorySpend]
    fixos_pendentes: list[str]
    plano_acao: ActionPlan
    projecao_economia_12m: float


class MonthPoint(BaseModel):
    competencia: str
    receita: float
    gastos: float
    saldo: float
    investimento: float


class AnnualReport(BaseModel):
    year: int
    meses: list[MonthPoint]
    receita_total: float
    gastos_total: float
    saldo_total: float
    investimento_total: float
