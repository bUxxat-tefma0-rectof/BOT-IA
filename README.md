# 🚀 Deploy no Render

## Passo a Passo Completo

### 1. Preparar o GitHub

1. Crie um repositório no GitHub
2. Suba todos os arquivos do projeto
3. Configure os Secrets (Settings → Secrets → Actions):
   - `RENDER_API_KEY` (opcional)

### 2. Configurar o Render

1. Acesse [render.com](https://render.com)
2. Crie uma conta (ou faça login)
3. Conecte sua conta do GitHub

### 3. Criar o Banco de Dados

1. No Render, vá em **New +** → **PostgreSQL**
2. Configure:
   - **Name:** `tech-offers-db`
   - **Database:** `tech_offers`
   - **User:** `tech_user`
   - **Plan:** Free
3. Aguarde a criação
4. Copie a **Internal Database URL**

### 4. Criar o Redis (Opcional)

1. No Render, vá em **New +** → **Redis**
2. Configure:
   - **Name:** `tech-offers-redis`
   - **Plan:** Free
3. Aguarde a criação
4. Copie a **Internal Redis URL**

### 5. Criar o Bot (Web Service)

1. No Render, vá em **New +** → **Web Service**
2. Conecte seu repositório do GitHub
3. Configure:
   - **Name:** `tech-offers-bot`
   - **Runtime:** Python
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `bash start.sh`
   - **Plan:** Free

### 6. Configurar Variáveis de Ambiente

No serviço do bot, adicione:

```env
BOT_TOKEN=seu_token_do_botfather
ADMIN_ID=seu_telegram_id
CHANNEL_ID=@seu_canal
DATABASE_URL=url_do_postgres_internal
REDIS_URL=url_do_redis_internal
DEBUG=False
LOG_LEVEL=INFO
TIMEZONE=America/Sao_Paulo
