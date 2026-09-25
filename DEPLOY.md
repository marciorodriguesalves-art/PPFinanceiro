# Deploy no VPS Hostinger (KVM) com auto-deploy pelo GitHub

Este app é **FastAPI + PostgreSQL** — precisa de um servidor que roda continuamente.
Ele **não** funciona na hospedagem compartilhada da Hostinger (o "Git" do hPanel só
serve site estático/PHP). O caminho é um **VPS KVM** rodando Docker.

Arquitetura: **Caddy** (HTTPS automático) → **app** (FastAPI/uvicorn) → **PostgreSQL**,
tudo em containers definidos em [`docker-compose.prod.yml`](docker-compose.prod.yml).

```
Internet ──443/80──▶ Caddy ──▶ app:8000 ──▶ db:5432
                     (TLS)      (FastAPI)     (Postgres, sem porta pública)
```

---

## 1. Provisionar o VPS

1. No hPanel da Hostinger, crie/abra seu **VPS KVM** e escolha um template com **Ubuntu 24.04**
   (ou o template **Docker**, que já vem com Docker instalado — nesse caso pule o passo 2).
2. Anote o **IP** do VPS e acesse por SSH:
   ```bash
   ssh root@SEU_IP_DO_VPS
   ```

## 2. Instalar o Docker (se o template não trouxe)

```bash
curl -fsSL https://get.docker.com | sh
docker compose version   # confirma o plugin compose
```

## 3. Firewall (recomendado)

```bash
ufw allow OpenSSH
ufw allow 80
ufw allow 443
ufw enable
```
Não abra a porta 5432 — o Postgres fica só na rede interna do Docker.

## 4. Clonar o repositório e configurar o `.env`

Use um diretório fixo (ele será o `VPS_APP_DIR` do deploy automático):

```bash
mkdir -p /opt && cd /opt
git clone https://github.com/marciorodriguesalves-art/PPFinanceiro.git
cd PPFinanceiro

cp .env.prod.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(64))"   # gere a SECRET_KEY
nano .env    # cole a SECRET_KEY, troque as senhas, ajuste SITE_ADDRESS e ACME_EMAIL
```

No `.env`, os pontos que **precisam** ser trocados:
- `SECRET_KEY` — a chave gerada acima (sem ela, tokens JWT ficam inseguros).
- `POSTGRES_PASSWORD` **e** a mesma senha dentro de `DATABASE_URL`.
- `ADMIN_EMAIL` / `ADMIN_PASSWORD` — o admin inicial.
- `SITE_ADDRESS` — seu domínio (ex.: `orcamento.seudominio.com`) para HTTPS automático,
  ou `:80` para acessar só pelo IP (sem HTTPS).
- `ACME_EMAIL` — seu e-mail (usado pelo Let's Encrypt).

## 5. Apontar o domínio (para ter HTTPS)

No DNS do seu domínio, crie um registro **A** apontando para o **IP do VPS**
(ex.: `orcamento` → `SEU_IP`). O Caddy emite o certificado sozinho no primeiro acesso.
Sem domínio, deixe `SITE_ADDRESS=:80` e acesse por `http://SEU_IP`.

## 6. Primeira subida

```bash
docker compose -f docker-compose.prod.yml up -d --build
# cria o usuário administrador (sem dados de demonstração):
docker compose -f docker-compose.prod.yml exec app python -m scripts.create_admin
```

As migrations (`alembic upgrade head`) rodam sozinhas quando o container do app sobe.
Acesse `https://SEU_DOMINIO` (ou `http://SEU_IP`) e faça login com o admin do `.env`.
**Troque a senha do admin logo após o primeiro login.**

> Quer carregar o cenário de demonstração (Ago/2026) para testar as telas?
> `docker compose -f docker-compose.prod.yml exec app python -m scripts.seed`
> Em produção "de verdade", prefira o `create_admin` (sem dados fictícios).

---

## 7. Auto-deploy a cada push (GitHub Actions → VPS)

O workflow [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) roda **depois
que o CI passa** na `main`, conecta no VPS por SSH e atualiza os containers.

### 7.1. Gerar uma chave SSH só para o deploy (no seu computador ou no VPS)

```bash
ssh-keygen -t ed25519 -f ~/deploy_ppf -N "" -C "github-deploy"
# autoriza a chave pública no VPS:
ssh-copy-id -i ~/deploy_ppf.pub root@SEU_IP     # ou cole ~/deploy_ppf.pub em ~/.ssh/authorized_keys
```

### 7.2. Cadastrar os *secrets* no GitHub

Em **GitHub → repositório → Settings → Secrets and variables → Actions → New repository secret**,
crie:

| Secret | Valor |
| --- | --- |
| `VPS_HOST` | IP do VPS |
| `VPS_USER` | usuário SSH (ex.: `root`) |
| `VPS_SSH_KEY` | conteúdo **da chave privada** `~/deploy_ppf` (arquivo inteiro) |
| `VPS_PORT` | porta SSH (opcional; padrão `22`) |
| `VPS_APP_DIR` | caminho do repo no VPS (ex.: `/opt/PPFinanceiro`) |

Pronto. A partir daí: **push na `main` → CI (ruff + pytest) → se passar, deploy automático**.
Dá para disparar manualmente também em **Actions → Deploy → Run workflow**.

> Segurança: a chave privada é sua e vai **só** nos secrets do GitHub (nunca no repositório).
> Eu não tenho acesso ao seu VPS nem à sua conta Hostinger — os passos com senha/SSH são seus.

---

## 8. Operação do dia a dia

```bash
cd /opt/PPFinanceiro
docker compose -f docker-compose.prod.yml ps                 # status
docker compose -f docker-compose.prod.yml logs -f app        # logs do app
docker compose -f docker-compose.prod.yml restart app        # reiniciar
docker compose -f docker-compose.prod.yml down               # parar tudo
```

### Backup do banco

```bash
docker compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > backup_$(date +%F).sql
```

O dado do Postgres vive no volume Docker `pgdata` (persiste entre deploys).
Recomendado agendar o `pg_dump` (cron) e guardar os backups fora do VPS.

---

## Checklist de segurança antes de ir ao ar

- [ ] `SECRET_KEY` forte e única no `.env` (nunca a padrão).
- [ ] `POSTGRES_PASSWORD` trocada (e igual dentro do `DATABASE_URL`).
- [ ] Senha do admin trocada após o primeiro login.
- [ ] Firewall liberando só 22, 80 e 443.
- [ ] `.env` existe **apenas** no VPS (está no `.gitignore`, nunca vai para o Git).
- [ ] HTTPS ativo (domínio no `SITE_ADDRESS`) para produção real.
