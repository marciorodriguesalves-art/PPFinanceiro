# Controle Orçamentário — MVP

Sistema de controle orçamentário pessoal. Consolida **contra cheque** e **extrato/fatura de cartão**
para equilibrar gastos com metas claras de redução e uma **meta mínima de investimento (10% da receita
líquida)**, oferecendo visão da situação atual, dashboards e um **plano de ação inteligente** para corrigir
desvios orçamentários.

## Visão do sistema

- **Problema que resolve:** falta de visibilidade sobre para onde vai o salário e dificuldade de garantir
  investimento consistente. O sistema mostra, mês a mês, quanto entra (líquido do contra cheque), quanto sai
  (despesas fixas, gastos variáveis e parcelas de cartão), onde há estouro de meta e quanto sobra para investir.
- **Quem usa:** o titular do orçamento (perfil **Usuário**) e um **Administrador** que gerencia usuários e
  categorias. Cada usuário só enxerga seus próprios lançamentos.
- **O que define sucesso:** comprometimento da renda sob controle, categorias dentro das metas e investimento
  previsto **≥ 10%** da receita líquida em cada mês.

## Stack

| Camada | Tecnologia |
| --- | --- |
| Linguagem / framework | Python 3.11 + FastAPI |
| Banco de dados | PostgreSQL |
| Acesso a dados | SQLAlchemy 2.0 + Alembic (migrations) |
| Autenticação | JWT (OAuth2 password) + bcrypt |
| Frontend | Jinja2 + JS puro + Chart.js (dashboards) |
| Testes / lint | pytest + ruff |
| Empacotamento | Docker / docker-compose |

## Escopo do MVP

- **Importação de dados:** contra cheque (CSV) e extrato/fatura mensal (CSV). Detecta layout de cartão
  (ex.: Nubank `date,title,amount`) ou extrato de conta, e extrai parcelas de "Parcela X/Y".
- **Dashboards:** desvios orçamentários, gastos por tipo/categoria, visão anual e mensal, indicadores-chave,
  composição dos gastos, saldo disponível por mês e projeções.
- **Extrato mensal:** receitas, despesas fixas (com baixa de pagamento e data), lançamentos diários,
  parcelas ativas do cartão, indicadores, metas de gasto variável, **plano de ação** automático,
  resumo por categoria (gráficos) e projeção de economia.
- **Controle de usuários (CRUD)** — perfis **Administrador** e **Usuário**.
- **Cadastro de gastos diários (CRUD)** e **despesas fixas (CRUD)**, além de receitas, parcelas e metas.

## Como rodar

### Opção A — Docker (recomendado)

```bash
cp .env.example .env         # ajuste SECRET_KEY e credenciais
docker compose up -d db      # sobe o PostgreSQL
docker build -t orcamento .
docker run --env-file .env --network host orcamento
```

### Opção B — Local

```bash
cp .env.example .env
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

docker compose up -d db      # PostgreSQL em localhost:5432
alembic upgrade head         # cria as tabelas
python -m scripts.seed       # dados iniciais + cenário de demonstração
uvicorn app.main:app --reload
```

Acesse **http://localhost:8000** (interface) e **http://localhost:8000/docs** (API / Swagger).

> Também é possível usar SQLite para testar rápido sem Postgres:
> `export DATABASE_URL="sqlite:///./dev.db"` antes de `alembic upgrade head`.

### Credenciais do seed

| Perfil | E-mail | Senha |
| --- | --- | --- |
| Administrador | `admin@orcamento.com.br` | `admin123` |
| Usuário | `user@orcamento.com.br` | `user123` |

O cenário de demonstração usa o contra cheque de Ago/2026 (líquido R$ 13.559,58) e a fatura real de cartão.

## Formatos de importação

Modelos prontos em `app/static/samples/` (baixáveis na tela **Importar**):

**Contra cheque** (`contra_cheque_exemplo.csv`):
```
descricao,tipo,valor
001-SALARIO,provento,15701.00
650-INSS,desconto,988.07
```
Bruto = Σ proventos; Líquido = Bruto − Σ descontos. (Também aceita colunas `bruto,liquido`.)

**Fatura de cartão** (`fatura_nubank_exemplo.csv`):
```
date,title,amount
2026-09-20,Restaurante Viva Leve,"224,85"
2026-09-03,Payu *Adidas - Parcela 4/7,"104,28"
```
Valores positivos = compras; negativos (pagamentos) são ignorados; "Parcela X/Y" vira parcela ativa.

**Extrato de conta** (`extrato_exemplo.csv`): valores negativos = gastos.

## Motor de regras (plano de ação)

Determinístico, sem chamadas externas (`app/services/action_plan.py`). A partir do orçamento do mês:

1. Sinaliza **comprometimento** quando os gastos superam a receita.
2. Lista **desvios de meta** por categoria (gasto acima do teto), com corte sugerido.
3. Garante a **meta de investimento** (10% configurável em `MIN_INVESTMENT_RATE`): calcula o corte adicional
   necessário para atingir os 10%.
4. Aponta **despesas fixas pendentes** de pagamento.

Retorna corte total sugerido, saldo e investimento projetados após o ajuste. O ponto de extensão está pronto
para, no futuro, plugar uma camada de recomendações via LLM sobre o mesmo diagnóstico.

## Estrutura

```
app/
  main.py            # app FastAPI, static e template
  config.py          # settings (.env)
  database.py        # engine/sessão SQLAlchemy
  security.py        # JWT + bcrypt
  deps.py            # dependências de auth/RBAC
  models/            # tabelas (User, Income, FixedExpense, DailyExpense, Installment, Goal...)
  schemas/           # Pydantic (entrada/saída)
  services/          # budget (cálculo), action_plan (regras), importers (CSV), present
  api/routes/        # auth, users, categories, incomes, fixed/daily, installments, goals, imports, reports, dashboard
  templates/ static/ # frontend (SPA leve + Chart.js)
migrations/          # Alembic
scripts/seed.py      # dados iniciais
tests/               # pytest (auth, crud, budget, importers)
```

## Endpoints principais

- `POST /api/auth/login`, `GET /api/auth/me`
- CRUD: `/api/users` (admin), `/api/categories`, `/api/incomes`, `/api/fixed-expenses`
  (+ `/{id}/payments`), `/api/daily-expenses`, `/api/installments`, `/api/goals`
- Importação: `POST /api/imports/payslip`, `POST /api/imports/statement`
- Relatórios: `/api/reports/monthly/{ano}/{mes}`, `/api/reports/action-plan/{ano}/{mes}`,
  `/api/reports/annual/{ano}`
- Dashboard: `/api/dashboard/overview/{ano}/{mes}`, `/api/dashboard/series/{ano}`

## Testes e qualidade

```bash
pytest        # 17 testes (auth, RBAC, CRUD, motor de regras, importadores)
ruff check .  # lint
```

## Próximos passos sugeridos

- Importação direta de contra cheque em **PDF** (hoje o parser é CSV).
- Recorrência automática de receitas e despesas fixas entre meses.
- Exportação de relatórios em PDF e alertas por e-mail.
- Definição de hospedagem (Railway, Render, Fly.io ou VPS com Docker).
