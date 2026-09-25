from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import (
    Category,
    CreditCardInstallment,
    DailyExpense,
    Income,
    PaymentMethod,
    User,
)
from app.services.importers import (
    ParsedExpense,
    detect_layout,
    parse_payslip_csv,
    parse_statement_csv,
)

router = APIRouter()


class StatementImportResult(BaseModel):
    layout: str
    total_linhas: int
    lancamentos_criados: int
    parcelas_criadas: int
    ignorados_duplicados: int
    total_importado: float
    competencias: list[str] = []  # meses detectados no arquivo (YYYY-MM)


class PayslipImportResult(BaseModel):
    year: int
    month: int
    gross_amount: float
    net_amount: float
    criado: bool


async def _read_csv(file: UploadFile) -> str:
    raw = await file.read()
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def _get_or_create_category(db: Session, name: str | None) -> Category | None:
    if not name:
        return None
    cat = db.scalar(select(Category).where(Category.name == name))
    if cat is None:
        cat = Category(name=name)
        db.add(cat)
        db.flush()
    return cat


@router.post("/statement", response_model=StatementImportResult)
async def import_statement(
    year: int = Form(...),
    month: int = Form(...),
    layout: str = Form("auto"),
    create_installments: bool = Form(True),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> StatementImportResult:
    """Importa fatura de cartão ou extrato de conta (CSV).

    A competência de cada lançamento vem da DATA da própria linha do arquivo — por
    isso um mesmo arquivo pode conter vários meses (e vários arquivos podem ser
    enviados). Os campos year/month servem apenas de referência para linhas sem data.
    """
    content = await _read_csv(file)
    resolved_layout = detect_layout(content) if layout == "auto" else layout
    parsed: list[ParsedExpense] = parse_statement_csv(content, layout=resolved_layout)

    default_method = (
        PaymentMethod.credito if resolved_layout == "cartao" else PaymentMethod.debito
    )
    created = installments_created = skipped = 0
    total = 0.0
    meses = set()

    for p in parsed:
        meses.add((p.expense_date.year, p.expense_date.month))
        is_installment = create_installments and (p.installment_total or 0) > 1
        if is_installment:
            # Competência da 1ª parcela derivada da DATA da linha (não do form),
            # para suportar arquivos com múltiplos meses.
            ref_year, ref_month = p.expense_date.year, p.expense_date.month
            offset = (p.installment_current or 1) - 1
            start_month0 = (ref_month - 1) - offset
            start_year = ref_year + (start_month0 // 12)
            start_month = (start_month0 % 12) + 1
            exists = db.scalar(
                select(CreditCardInstallment).where(
                    CreditCardInstallment.user_id == current.id,
                    CreditCardInstallment.description == p.description,
                    CreditCardInstallment.installments_total == p.installment_total,
                    CreditCardInstallment.installment_amount == p.amount,
                )
            )
            if exists:
                skipped += 1
                continue
            cat = _get_or_create_category(db, p.category_name)
            db.add(
                CreditCardInstallment(
                    user_id=current.id,
                    category_id=cat.id if cat else None,
                    description=p.description,
                    card=file.filename,
                    installment_amount=p.amount,
                    installments_total=p.installment_total,
                    start_year=start_year,
                    start_month=start_month,
                )
            )
            installments_created += 1
            total += p.amount
            continue

        dup = db.scalar(
            select(DailyExpense).where(
                DailyExpense.user_id == current.id,
                DailyExpense.expense_date == p.expense_date,
                DailyExpense.description == p.description,
                DailyExpense.amount == p.amount,
            )
        )
        if dup:
            skipped += 1
            continue
        cat = _get_or_create_category(db, p.category_name)
        db.add(
            DailyExpense(
                user_id=current.id,
                category_id=cat.id if cat else None,
                expense_date=p.expense_date,
                description=p.description,
                amount=p.amount,
                payment_method=default_method,
            )
        )
        created += 1
        total += p.amount

    db.commit()
    return StatementImportResult(
        layout=resolved_layout,
        total_linhas=len(parsed),
        lancamentos_criados=created,
        parcelas_criadas=installments_created,
        ignorados_duplicados=skipped,
        total_importado=round(total, 2),
        competencias=[f"{a:04d}-{m:02d}" for a, m in sorted(meses)],
    )


@router.post("/payslip", response_model=PayslipImportResult)
async def import_payslip(
    year: int = Form(...),
    month: int = Form(...),
    description: str = Form("Salário"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> PayslipImportResult:
    """Importa contra cheque (CSV) e registra/atualiza a receita da competência."""
    content = await _read_csv(file)
    parsed = parse_payslip_csv(content)
    if parsed.gross_amount <= 0 and parsed.net_amount <= 0:
        raise HTTPException(
            status_code=422,
            detail="Não foi possível extrair valores do contra cheque. Verifique o formato.",
        )
    income = db.scalar(
        select(Income).where(
            Income.user_id == current.id, Income.year == year, Income.month == month
        )
    )
    created = income is None
    if income is None:
        income = Income(user_id=current.id, year=year, month=month)
        db.add(income)
    income.description = description
    income.source = file.filename
    income.gross_amount = parsed.gross_amount
    income.net_amount = parsed.net_amount
    db.commit()
    return PayslipImportResult(
        year=year,
        month=month,
        gross_amount=parsed.gross_amount,
        net_amount=parsed.net_amount,
        criado=created,
    )
