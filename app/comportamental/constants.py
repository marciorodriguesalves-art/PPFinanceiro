"""Constantes e parâmetros da camada comportamental.

Todos os limiares (thresholds) ficam aqui para poderem ser calibrados sem
tocar na lógica do motor de diagnóstico. Os valores padrão foram ajustados
ao perfil de gasto do Sistema de Controle Orçamentário (categorias reais,
meta de 10% de investimento, metas de gasto variável).
"""

from __future__ import annotations

from decimal import Decimal

# --- Categorias reais do sistema -------------------------------------------
CATEGORIAS = [
    "Alimentação",
    "Mercado",
    "Feira",
    "Farmácia",
    "Transporte",
    "Vestuário",
    "Amazon",
    "Igreja/Doação",
    "Tecnologia",
    "Lazer",
    "Outros",
]

# Categorias mais associadas a consumo por impulso / recompensa imediata.
CATEGORIAS_IMPULSO = {"Lazer", "Vestuário", "Amazon", "Tecnologia"}

# Categorias tipicamente supérfluas (gatilho de "contabilidade mental" após
# entradas atípicas como 13º, bônus e restituição).
CATEGORIAS_SUPERFLUAS = {"Lazer", "Vestuário", "Amazon", "Tecnologia"}

# --- Meios de pagamento ----------------------------------------------------
MEIO_CARTAO_CREDITO = "cartao_credito"
MEIOS_DILUEM_DOR = {MEIO_CARTAO_CREDITO}  # cartão adia/dilui a "dor de pagar"

# --- Detecção de entradas atípicas (contabilidade mental) ------------------
# Palavras que marcam uma entrada de dinheiro "extra".
PALAVRAS_ENTRADA_ATIPICA = (
    "13",
    "decimo terceiro",
    "décimo terceiro",
    "bonus",
    "bônus",
    "restituicao",
    "restituição",
    "reembolso",
    "premio",
    "prêmio",
    "plr",
    "participacao nos lucros",
    "participação nos lucros",
)
# Janela (dias) após a entrada atípica em que o gasto supérfluo é atribuído a ela.
JANELA_CONTABILIDADE_MENTAL_DIAS = 15

# --- Detecção de gastos sazonais/irregulares -------------------------------
# Despesas grandes e esporádicas que costumam estourar o mês quando chegam.
PALAVRAS_SAZONAIS = (
    "ipva",
    "iptu",
    "seguro",
    "licenciamento",
    "matricula",
    "matrícula",
    "material escolar",
    "presente",
    "manutencao",
    "manutenção",
    "revisao",
    "revisão",
    "conserto",
    "anuidade",
)

# --- Limiares numéricos ----------------------------------------------------
# "Microtransação": lançamento pequeno cujo acúmulo passa despercebido.
LIMITE_MICROTRANSACAO = Decimal("35.00")
# A partir de quantas microtransações no período o padrão vira relevante.
MIN_MICROTRANSACOES = 8
# Fração do total gasto no cartão a partir da qual a "dor de pagar" é sinalizada.
FRACAO_CARTAO_ALERTA = Decimal("0.70")
# Crescimento do ticket médio de uma categoria (mês a mês) para sinalizar
# inflação do estilo de vida.
CRESCIMENTO_INFLACAO_ALERTA = Decimal("0.15")  # +15%
# Fração da meta de gasto variável a partir da qual já se alerta (antes de estourar).
FRACAO_META_ALERTA = Decimal("0.90")
# Valor mínimo (em % da receita) para um gasto sazonal isolado virar padrão.
FRACAO_SAZONAL_RELEVANTE = Decimal("0.05")  # 5% da receita líquida
# Número mínimo de compras repetidas na mesma categoria/curto prazo p/ impulso.
MIN_REPETICOES_IMPULSO = 4

# Meta mínima de investimento padrão do sistema.
META_INVESTIMENTO_PADRAO = Decimal("0.10")  # 10% da receita líquida

# Quantos padrões, no máximo, o diagnóstico devolve (prioriza os de maior impacto).
MAX_PADROES = 5
MIN_PADROES = 3

# Rótulos de confiança.
CONF_ALTA = "alta"
CONF_MEDIA = "media"
CONF_BAIXA = "baixa"
