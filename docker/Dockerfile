FROM python:3.11-slim

# Definir variáveis de ambiente
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Criar diretório de trabalho
WORKDIR /app

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements primeiro para cache
COPY requirements.txt .

# Instalar dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código do projeto
COPY . .

# Criar diretórios necessários
RUN mkdir -p logs backups

# Criar usuário não-root
RUN useradd -m -u 1000 botuser && \
    chown -R botuser:botuser /app

USER botuser

# Comando para executar o bot
CMD ["python", "-m", "bot.main"]
