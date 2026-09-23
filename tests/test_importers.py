from app.services.importers import (
    detect_layout,
    parse_payslip_csv,
    parse_statement_csv,
)

NUBANK = (
    "date,title,amount\n"
    '2026-09-20,Restaurante Viva Leve,"224,85"\n'
    '2026-09-18,Bio Mundo Terraco Shop - Parcela 1/2,"184,14"\n'
    '2026-09-04,Pagamento recebido,"- 3.602,90"\n'
    '2026-09-03,Payu *Adidas - Parcela 4/7,"104,28"\n'
)

EXTRATO = (
    "data,descricao,valor,categoria\n"
    "2026-09-05,Mercado,-540.30,Mercado\n"
    "2026-09-04,Salario,13559.58,\n"
)

PAYSLIP = (
    "descricao,tipo,valor\n"
    "001-SALARIO,provento,15701.00\n"
    "007-TRIENIO,provento,1413.09\n"
    "442-AJUDA DE CUSTO,provento,2000.00\n"
    "650-INSS,desconto,988.07\n"
    "683-IRRF SALARIO,desconto,3473.78\n"
)


def test_detect_layout_nubank():
    assert detect_layout(NUBANK) == "cartao"
    assert detect_layout(EXTRATO) == "extrato"


def test_parse_card_statement_ignores_payment_and_extracts_parcela():
    parsed = parse_statement_csv(NUBANK, layout="cartao")
    # 3 gastos (o "Pagamento recebido" negativo é ignorado)
    assert len(parsed) == 3
    adidas = [p for p in parsed if "Adidas" in p.description][0]
    assert adidas.installment_current == 4
    assert adidas.installment_total == 7
    assert "Parcela" not in adidas.description
    assert adidas.amount == 104.28


def test_parse_bank_statement_uses_negatives():
    parsed = parse_statement_csv(EXTRATO, layout="extrato")
    assert len(parsed) == 1
    assert parsed[0].amount == 540.30
    assert parsed[0].category_name == "Mercado"


def test_parse_payslip_gross_and_net():
    p = parse_payslip_csv(PAYSLIP)
    assert p.gross_amount == 19114.09
    assert p.net_amount == round(19114.09 - (988.07 + 3473.78), 2)
