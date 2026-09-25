# Deploy no Railway

Caminho recomendado para colocar o app no ar rápido, com **PostgreSQL gerenciado**,
**HTTPS automático** e **deploy a cada push** — sem administrar servidor.

O repositório já vem pronto: o Railway usa o [`Dockerfile`](Dockerfile) para build e o
[`railway.json`](railway.json) para subir. Na inicialização ele roda as migrations,
garante o usuário admin e sobe o servidor na porta que o Railway define (`$PORT`).
O seed de demonstração **não** roda.

---

## Passo a passo

### 1. Criar o projeto a partir do GitHub
1. Acesse [railway.com](https://railway.com) e entre com o GitHub.
2. **New Project → Deploy from GitHub repo → `marciorodriguesalves-art/PPFinanceiro`**.
3. O Railway detecta o `Dockerfile` + `railway.json` e inicia o primeiro build.

### 2. Adicionar o PostgreSQL
1. Dentro do projeto: **New → Database → Add PostgreSQL**.
2. Isso cria um serviço `Postgres` com a variável `DATABASE_URL` pronta.

### 3. Configurar as variáveis do serviço do app
No serviço do app → aba **Variables**, adicione:

| Variável | Valor |
| --- | --- |
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` (referência ao serviço Postgres) |
| `SECRET_KEY` | uma chave forte (gere abaixo) |
| `ADMIN_EMAIL` | seu e-mail de admin |
| `ADMIN_PASSWORD` | senha inicial (troque após o 1º login) |
| `ADMIN_NAME` | seu nome |
| `ENVIRONMENT` | `production` |

Gere a `SECRET_KEY`:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
```

> **Não** defina `PORT` — o Railway injeta sozinho e o app já escuta nela.
> A `DATABASE_URL` vem como `postgresql://…`; o app converte para o driver
> `postgresql+psycopg://` automaticamente (em `app/config.py`), sem ajuste manual.

### 4. Publicar e expor
1. O Railway faz o deploy automaticamente ao salvar as variáveis (ou clique em **Deploy**).
2. No app → **Settings → Networking → Generate Domain** para obter uma URL pública
   `*.up.railway.app` com HTTPS. (Ou **Custom Domain** para usar seu domínio via CNAME.)
3. Acesse a URL, faça login com o `ADMIN_EMAIL`/`ADMIN_PASSWORD` e **troque a senha**.

### 5. Auto-deploy a cada push
Já vem ligado: o Railway republica sozinho a cada push na branch conectada (`main`).
Para publicar só depois que os testes passarem, ative no serviço:
**Settings → (GitHub trigger) → "Wait for CI to pass"** — assim ele espera o workflow
**CI** (ruff + pytest) ficar verde antes de deployar.

---

## Operação

- **Logs:** aba **Deployments → View Logs** (ou **Observability**).
- **Migrations:** rodam sozinhas a cada deploy (`alembic upgrade head` no start command).
- **Admin:** garantido a cada boot por `scripts/create_admin.py` (idempotente; não recria se já existe, e nunca insere dados de demonstração).
- **Rollback:** em **Deployments**, promova um deploy anterior.
- **Backup do banco:** Railway → serviço **Postgres → Backups** (ative o agendamento).
  Para um dump manual, use a `DATABASE_PUBLIC_URL` do Postgres com `pg_dump`.

---

## Custo (estimativa)
Plano de uso do Railway (~US$ 5/mês de crédito no Hobby) costuma cobrir um app pequeno
+ Postgres de MVP. Confira os limites atuais no painel de billing.

> Este guia convive com o setup de VPS (`docker-compose.prod.yml` + `DEPLOY.md`), que
> continua disponível como alternativa. O workflow `deploy.yml` (SSH para VPS) fica
> inofensivo — sem os secrets do VPS ele é ignorado, e o deploy do Railway é feito pela
> integração nativa dele, não por esse workflow.
