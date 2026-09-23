"""Importadores de contra cheque e extrato/fatura (CSV).

Layouts de gastos suportados (delimitador ``,`` ou ``;``, cabeçalho com ou sem acento):

1. Fatura de cartão (ex.: Nubank) — ``layout="cartao"`` ou detecção automática::

       date,title,amount
       2026-09-20,Restaurante Viva Leve,"224,85"
       2026-09-18,Bio Mundo Terraco Shop - Parcela 1/2,"184,14"
       2026-09-04,Pagamento recebido,"- 3.602,90"

   - Valores POSITIVOS são gastos (compras). Valores negativos (pagamentos
     recebidos/estornos) são ignorados.
   - "Parcela X/Y" no título é extraído para os campos de parcela.

2. Extrato de conta — ``layout="extrato"`` ou detecção automática::

       data,descricao,valor,categoria
       2026-09-03,Mercado Extra,-320.50,Mercado

   - Valores NEGATIVOS são gastos; positivos (entradas) são ignorados.

Contra cheque (CSV)::

       descricao,tipo,valor
       Salário base,provento,5000.00
       INSS,desconto,550.00

   - ``tipo`` ∈ {provento, desconto}. Bruto = Σ proventos; Líquido = Bruto − Σ descontos.
   - Alternativamente, uma linha com colunas ``bruto`` e ``liquido``.
"""

from __future__ import annotations

import csv
import io
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime

_PARCELA_RE = re.compile(r"\s*[-–]?\s*parcela\s+(\d+)\s*/\s*(\d+)", re.IGNORECASE)


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.strip().lower()


def _parse_amount(raw: str) -> float:
    raw = (raw or "").strip().replace("R$", "").replace(" ", "")
    if not raw:
        return 0.0
    neg = raw.startswith("-") or (raw.startswith("(") and raw.endswith(")"))
    raw = raw.strip("()").lstrip("-+")
    if "," in raw and "." in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif "," in raw:
        raw = raw.replace(",", ".")
    try:
        value = float(raw)
    except ValueError:
        value = 0.0
    return -value if neg else value


def _parse_date(raw: str) -> date | None:
    raw = (raw or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _sniff_reader(content: str) -> csv.DictReader:
    first_line = content.splitlines()[0] if content.strip() else ""
    delimiter = ";" if first_line.count(";") > first_line.count(",") else ","
    return csv.DictReader(io.StringIO(content), delimiter=delimiter)


@dataclass
class ParsedExpense:
    expense_date: date
    description: str
    amount: float
    category_name: str | None = None
    installment_current: int | None = None
    installment_total: int | None = None


@dataclass
class ParsedPayslip:
    gross_amount: float
    net_amount: float
    lines: int


def _extract_parcela(title: str) -> tuple[str, int | None, int | None]:
    m = _PARCELA_RE.search(title)
    if not m:
        return title.strip(), None, None
    clean = _PARCELA_RE.sub("", title).strip(" -–")
    return clean, int(m.group(1)), int(m.group(2))


def detect_layout(content: str) -> str:
    """Retorna 'cartao' ou 'extrato' a partir do cabeçalho."""
    reader = _sniff_reader(content)
    headers = {_norm(h) for h in (reader.fieldnames or [])}
    if "title" in headers and "amount" in headers:
        return "cartao"  # padrão Nubank
    return "extrato"


def parse_statement_csv(content: str, layout: str = "auto") -> list[ParsedExpense]:
    if layout == "auto":
        layout = detect_layout(content)

    reader = _sniff_reader(content)
    fieldmap = {_norm(k): k for k in (reader.fieldnames or [])}

    def col(*names: str) -> str | None:
        for n in names:
            if n in fieldmap:
                return fieldmap[n]
        return None

    c_date = col("data", "date")
    c_desc = col("title", "descricao", "historico", "description", "lancamento")
    c_value = col("amount", "valor", "value", "montante")
    c_cat = col("categoria", "category")

    result: list[ParsedExpense] = []
    if not (c_value and c_desc):
        return result

    for row in reader:
        amount = _parse_amount(row.get(c_value, ""))
        if layout == "cartao":
            # Fatura: positivo = compra (gasto); negativo = pagamento/estorno → ignora.
            if amount <= 0:
                continue
            expense_amount = amount
        else:
            # Extrato: negativo = gasto.
            if amount >= 0:
                continue
            expense_amount = abs(amount)

        title = (row.get(c_desc) or "").strip() or "Lançamento"
        desc, cur, total = _extract_parcela(title)
        d = _parse_date(row.get(c_date, "")) if c_date else None
        result.append(
            ParsedExpense(
                expense_date=d or date.today(),
                description=desc or title,
                amount=round(expense_amount, 2),
                category_name=(row.get(c_cat) or "").strip() or None if c_cat else None,
                installment_current=cur,
                installment_total=total,
            )
        )
    return result


def parse_payslip_csv(content: str) -> ParsedPayslip:
    reader = _sniff_reader(content)
    fieldmap = {_norm(k): k for k in (reader.fieldnames or [])}

    c_gross = fieldmap.get("bruto") or fieldmap.get("gross")
    c_net = fieldmap.get("liquido") or fieldmap.get("net")
    rows = list(reader)
    if c_gross and c_net and rows:
        r = rows[0]
        return ParsedPayslip(
            gross_amount=round(abs(_parse_amount(r.get(c_gross, ""))), 2),
            net_amount=round(abs(_parse_amount(r.get(c_net, ""))), 2),
            lines=1,
        )

    c_tipo = fieldmap.get("tipo") or fieldmap.get("type")
    c_value = fieldmap.get("valor") or fieldmap.get("value") or fieldmap.get("amount")
    proventos = descontos = 0.0
    count = 0
    if c_tipo and c_value:
        for r in rows:
            tipo = _norm(r.get(c_tipo, ""))
            value = abs(_parse_amount(r.get(c_value, "")))
            if not value:
                continue
            count += 1
            if tipo.startswith("prov") or tipo in ("credito", "vencimento", "rendimento"):
                proventos += value
            else:
                descontos += value
    return ParsedPayslip(
        gross_amount=round(proventos, 2),
        net_amount=round(max(proventos - descontos, 0.0), 2),
        lines=count,
    )
