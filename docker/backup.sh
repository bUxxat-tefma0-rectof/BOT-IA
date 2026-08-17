#!/bin/bash

# Script de backup do banco de dados
# Uso: ./backup.sh [diretório_destino]

# Configurações
BACKUP_DIR="${1:-../backups}"
DB_NAME="${POSTGRES_DB:-tech_offers}"
DB_USER="${POSTGRES_USER:-tech_user}"
DB_PASSWORD="${POSTGRES_PASSWORD}"
DB_HOST="${POSTGRES_HOST:-localhost}"
DB_PORT="${POSTGRES_PORT:-5432}"

# Criar diretório de backup se não existir
mkdir -p "$BACKUP_DIR"

# Nome do arquivo com timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/backup_${DB_NAME}_${TIMESTAMP}.sql"

# Executar backup
echo "Iniciando backup do banco $DB_NAME..."
echo "Arquivo: $BACKUP_FILE"

PGPASSWORD="$DB_PASSWORD" pg_dump \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    -F c \
    -f "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    echo "✅ Backup concluído com sucesso!"
    
    # Comprimir backup
    gzip "$BACKUP_FILE"
    echo "✅ Backup comprimido: ${BACKUP_FILE}.gz"
    
    # Remover backups antigos (mais de 30 dias)
    find "$BACKUP_DIR" -name "backup_*.sql.gz" -mtime +30 -delete
    echo "✅ Backups antigos removidos"
    
else
    echo "❌ Erro ao executar backup!"
    exit 1
fi

# Listar backups recentes
echo ""
echo "📁 Backups recentes:"
ls -lh "$BACKUP_DIR" | tail -5
