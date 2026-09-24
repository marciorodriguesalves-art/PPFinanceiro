# CLAUDE.md

Orientações para o Claude Code (e demais agentes) ao trabalhar neste repositório.
Escreva código e comentários em **português**, no mesmo estilo do que já existe.

## Visão geral

**Controle Orçamentário (PPFinanceiro)** — sistema web de controle orçamentário pessoal.
Consolida **contra cheque** (receita) e **extrato/fatura de cartão** (gastos) por competência
(ano/mês) para equilibrar despesas com metas de redução e garantir uma **meta mínima de
investimento (10% da receita líquida)**. Entrega dashboards, extrato mensal e um **plano de
ação determinístico** que aponta cortes para corrigir desvios.

## Stack

- **Python 3.11 + FastAPI** (API + página única servida via Jinja2 + JS puro + Chart.js).
- **PostgreSQL** como banco; **SQLAlchemy 2.0** (ORM tipado com `Mapped[...]`) + **Alembic** (migrations).
- **JWT** (OAuth2 password flow) + **bcrypt** para autenticação.
- **pytest** (testes) + **ruff** (lint/format). **Docker / docker-compose** para empacotar.

## Comandos essenciais

```bash
# Ambiente
cp .env.example .env            # ajuste SECRET_KEY e credenciais (o .env NÃO é versionado)
pip install -e ".[dev]"         # instala app + ferramentas de dev
docker compose up -d db         # sobe o PostgreSQL local (localhost:5432)

# Banco
alembic upgrade head            # aplica as migrations
alembic revision --autogenerate -m "mensagem"   # cria migration a partir dos modelos
python -m scripts.seed          # dados iniciais + cenário de demonstração

# Rodar
uvicorn app.main:app --reload   # http://localhost:8000  (Swagger em /docs)

# Qualidade
ruff check .                    # lint
ruff check --fix . && ruff format .   # corrige e formata
pytest                          # suíte de testes (17 testes)
pytest tests/test_budget.py -q  # um arquivo
pytest -k action_plan           # por nome
```

Os alvos do `Makefile` (`make db-up`, `make migrate`, `make seed`, `make run`, `make test`, `make lint`, `make fmt`) encapsulam os comandos acima.

## Arquitetura

Fluxo: **rota** (`app/api/routes/`) → valida com **schema** Pydantic (`app/schemas/`) →
chama **service** (`app/services/`) → persiste via **model** SQLAlchemy (`app/models/`).

```
app/
  main.py            # cria o app FastAPI, monta /static e template, /health e /
  config.py          # Settings (pydantic-settings) lidas do .env — instância única `settings`
  database.py        # engine/Session + Base declarativa; dependência get_db
  security.py        # hash/verify de senha (bcrypt) e emissão/decodificação de JWT
  deps.py            # get_current_user e require_admin (RBAC)
  models/            # tabelas: User, Category, Income, FixedExpense(+Payment),
                     #          DailyExpense, CreditCardInstallment, VariableGoal, AppSetting
  schemas/           # entrada/saída Pydantic por domínio
  services/
    budget.py        # compute_month_budget → MonthBudget (indicadores + linhas por categoria)
    action_plan.py   # build_action_plan → ActionPlan (regras determinísticas)
    importers.py     # parse de CSV (contra cheque, fatura de cartão, extrato)
    present.py       # formatação para apresentação
  api/routes/        # auth, users, categories, incomes, fixed_expenses, daily_expenses,
                     # installments, goals, imports, reports, dashboard
  templates/ static/ # frontend leve (SPA + Chart.js)
migrations/          # Alembic (env.py lê settings.database_url; versions/ = migrations)
scripts/seed.py      # popula dados iniciais e cenário demo
tests/               # pytest (conftest.py monta o banco e as fixtures de auth)
```

Pontos importantes:
- `app/config.py` expõe uma instância única `settings`; importe-a (`from app.config import settings`) em vez de reler o ambiente.
- `migrations/env.py` obtém a URL do banco de `settings.database_url` (variável `DATABASE_URL`), **não** de `alembic.ini`.
- `budget.py` e `action_plan.py` são **puros/determinísticos** (sem I/O externo). Toda mudança de regra de cálculo entra aqui e precisa de teste.

## Regras de negócio

Estas regras são o coração do produto. Ao alterá-las, ajuste os testes em `tests/test_budget.py`
e `tests/test_importers.py` e confirme que o `README.md` continua coerente.

1. **Competência = (ano, mês).** Todo lançamento e cálculo é sempre referente a uma competência. Não misture meses.
2. **Receita.** `receita_bruta = Σ proventos`; `receita_liquida = Σ (bruto − descontos)`. Cálculos de meta e comprometimento usam sempre a **receita líquida**.
3. **Total de gastos** = `despesas fixas (planejadas, ativas) + gastos variáveis (lançamentos diários) + parcelas de cartão ativas na competência`.
4. **Saldo disponível** = `receita_liquida − total_gastos`.
5. **Meta mínima de investimento** = `receita_liquida × MIN_INVESTMENT_RATE` (padrão **10%**, configurável no `.env`). O orçamento só "atende a meta" quando `investimento_previsto ≥ meta` **e** `saldo_disponivel ≥ 0`.
6. **Comprometimento** = `total_gastos / receita_liquida`. Acima de `1.0` significa que os gastos superam a renda — item mais crítico do plano de ação.
7. **Metas por categoria (gasto variável).** Podem ser valor absoluto (`target_amount`) e/ou fração da receita líquida (`target_rate`); havendo os dois, vale o **menor** limite. Meta com `year=0, month=0` é a **meta padrão** válida para qualquer mês; meta específica da competência tem prioridade sobre a padrão.
8. **Desvio de meta** = categoria cujo gasto excede o teto (`deviation > 0`). O plano de ação lista os desvios do maior para o menor e sugere o corte.
9. **Parcelas de cartão.** Uma parcela está ativa na competência quando `0 ≤ (ano−start_year)·12 + (mês−start_month) < installments_total`. "Parcela X/Y" no título da fatura é extraída na importação.
10. **Despesas fixas.** Valor planejado das despesas **ativas** entra no total. O pagamento é registrado por competência (`FixedExpensePayment`); fixas sem baixa aparecem como "pendentes" no plano de ação.
11. **Plano de ação (`action_plan.py`)** — prioridade: (1) comprometimento acima da renda, (2) desvios de meta por categoria, (3) fechar a meta de investimento, (4) despesas fixas pendentes. É **determinístico e offline**; o gancho para uma futura camada de LLM opera sobre o mesmo diagnóstico, sem substituir as regras.
12. **Importação de gastos.** Fatura de cartão: valores **positivos** são gastos, negativos (pagamentos/estornos) são ignorados. Extrato de conta: valores **negativos** são gastos, positivos ignorados. Aceita delimitador `,` ou `;` e cabeçalho com/sem acento.
13. **Autorização (RBAC).** Perfis `admin` e `user`. Gestão de usuários é restrita a `admin` (`require_admin`). **Cada usuário só enxerga e altera os próprios lançamentos** — filtre sempre por `user_id`.
14. **Dinheiro.** Persistido como `Numeric(12,2)`; nos serviços trabalha-se em `float` **sempre arredondando para 2 casas** (`round(x, 2)`). Nunca exiba/salve mais casas.

## Glossário

| Termo | Significado |
| --- | --- |
| **Competência** | Par (ano, mês) ao qual um lançamento/cálculo pertence. |
| **Contra cheque** | Fonte da receita; linhas de `provento` e `desconto` (ou colunas `bruto,liquido`). |
| **Receita bruta / líquida** | Soma dos proventos / bruto menos descontos. |
| **Despesa fixa** | Gasto recorrente (aluguel, escola, assinatura). Tem valor planejado e baixa de pagamento por mês. |
| **Gasto variável / lançamento diário** | Despesa avulsa do dia a dia (`DailyExpense`), classificada por categoria. |
| **Parcela** | Compra parcelada no cartão (`CreditCardInstallment`), ativa em N competências a partir da 1ª. |
| **Categoria** | Rótulo de gasto; natureza `fixa`, `variavel` ou `ambos` (`CategoryKind`). |
| **Meta (variável)** | Teto de gasto por categoria (`VariableGoal`): valor e/ou fração da renda. |
| **Desvio** | Quanto o gasto de uma categoria excede sua meta. |
| **Saldo disponível** | Receita líquida menos o total de gastos da competência. |
| **Meta de investimento** | Percentual mínimo da receita líquida a investir (`MIN_INVESTMENT_RATE`, 10%). |
| **Comprometimento** | Fração da renda consumida pelos gastos. |
| **Plano de ação** | Lista priorizada de cortes gerada por `action_plan.py`. |
| **Seed** | Carga inicial (`scripts/seed.py`): admin/usuário demo + cenário de exemplo. |
| **RBAC** | Controle de acesso por perfil (`admin` / `user`). |

## Nunca fazer

- **Nunca** commitar segredos: `.env`, chaves, senhas ou dumps de banco. Só `.env.example` (com placeholders) vai para o Git. O `.env` está no `.gitignore` — mantenha assim.
- **Nunca** editar migrations já aplicadas/versionadas. Gere uma nova migration para mudar o schema; ao alterar `app/models/`, crie a migration correspondente na mesma mudança.
- **Nunca** ler `os.environ` diretamente para configuração — use `from app.config import settings`.
- **Nunca** consultar/alterar dados sem filtrar por `user_id` (vaza dados entre usuários). Endpoints de gestão de usuários exigem `require_admin`.
- **Nunca** introduzir chamadas externas/rede em `budget.py` ou `action_plan.py`: eles devem permanecer determinísticos e testáveis offline.
- **Nunca** usar `float` para arredondamento monetário sem `round(x, 2)`, nem gravar dinheiro fora de `Numeric(12,2)`.
- **Nunca** guardar senha em texto puro: use `hash_password`/`verify_password` (bcrypt) de `app/security.py`.
- **Nunca** mudar o significado das convenções de importação (sinal dos valores, "Parcela X/Y", `year=0/month=0` como meta padrão) sem atualizar testes e este documento.
- **Nunca** commitar `.venv/`, caches (`.ruff_cache`, `.pytest_cache`, `__pycache__`) ou bancos locais (`*.db`, `*.sqlite3`).
- **Nunca** dar merge com CI vermelho: `ruff check .` e `pytest` precisam passar (o CI roda os testes contra PostgreSQL).

## Camada comportamental (`app/comportamental/`)

Camada **aditiva** de economia comportamental sobre o MVP: lê os lançamentos já
existentes (receita, gastos variáveis, despesas fixas, parcelas) e produz um
**diagnóstico** psicológico do mês — "por que se fura o orçamento" — além das
caixinhas sazonais e do raio-x de recorrências.

```
app/comportamental/
  engine.py      # MOTOR determinístico e PURO (sem ORM/FastAPI) — um detector por viés
  constants.py   # todos os limiares calibráveis (thresholds)
  services.py    # carregadores (banco -> DTO do motor) + regras de ambiente + persistência
  models.py      # tabelas novas: ReservaSazonal, Recorrencia, Diagnostico(+Padrao/Ressalva)
  schemas.py     # Pydantic v2
  router.py      # rotas, montadas em /api/comportamental
```

Regras/convenções específicas:
- O **motor (`engine.py`) é puro e determinístico**: recebe `list[LancamentoIn]` + contexto e devolve os 3–5 padrões mais relevantes (confiança alta primeiro, depois maior valor). Mesma regra do `budget.py`/`action_plan.py`: **sem I/O externo, sem inventar valor** — se falta dado, o detector não emite o achado (registra uma *ressalva*).
- O acoplamento ao schema real fica **só em `services.py`** (`_carregar_lancamentos`, `_carregar_contexto`, `_carregar_historico`). Ao mudar modelos do MVP, ajuste ali.
- Toda a camada opera em **`Decimal`** (não `float`) — o motor cuida de dinheiro; use o helper `_dec()` ao trazer valores do ORM.
- Filtre sempre por `usuario_id` (mesma regra 13 do MVP). As tabelas são novas e não removem/alteram nada do schema existente.
- Meios de pagamento do MVP são mapeados para o vocabulário do motor em `services._MEIO_PAGAMENTO` (`credito` → `cartao_credito`, que é o que "dilui a dor de pagar").
- Detectores atuais (viés → gatilho): investimento (desconto hiperbólico), recorrencias (efeito posse), parcelamento (dor diluída), sazonais (otimismo), dor_pagar (cartão/microtransações), contabilidade_mental (entrada atípica → supérfluo), meta_variavel + inflacao_estilo_vida (lifestyle creep), impulso (autocontrole). Limiares em `constants.py`.

Endpoints: `POST/GET /api/comportamental/diagnosticos[/{periodo}]`, `GET /api/comportamental/recorrencias/anualizado`, `POST /api/comportamental/recorrencias`, `POST/GET /api/comportamental/reservas`.

## Testes & CI

- `tests/conftest.py` usa **SQLite in-memory** por padrão (rápido). Se `TEST_DATABASE_URL` estiver definido, os testes rodam nesse banco.
- O CI (`.github/workflows/ci.yml`) sobe um **PostgreSQL de teste**, roda `ruff check`, valida as migrations (`alembic upgrade head` + `downgrade base`) e executa `pytest` apontando `TEST_DATABASE_URL` para esse Postgres.
- Ao adicionar regra de negócio, adicione teste. Prefira testar os serviços (`budget`, `action_plan`, `importers`) diretamente, além do teste de rota.
