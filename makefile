# Makefile para comandos úteis do projeto

.PHONY: help install run init-db reset-db backup test clean logs

# Variáveis
PYTHON = python3
PIP = pip3
DOCKER = docker
DOCKER_COMPOSE = docker-compose

# Cores
GREEN = \033[0;32m
RED = \033[0;31m
YELLOW = \033[1;33m
NC = \033[0m

help: ## Mostra esta ajuda
	@echo "$(GREEN)Comandos disponíveis:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-15s$(NC) %s\n", $$1, $$2}'

install: ## Instala dependências
	@echo "$(GREEN)Instalando dependências...$(NC)"
	$(PIP) install -r requirements.txt

run: ## Executa o bot
	@echo "$(GREEN)Iniciando bot...$(NC)"
	$(PYTHON) -m bot.main

init-db: ## Inicializa banco de dados
	@echo "$(GREEN)Inicializando banco de dados...$(NC)"
	$(PYTHON) scripts/init_db.py

reset-db: ## Reseta banco de dados
	@echo "$(RED)Resetando banco de dados...$(NC)"
	$(PYTHON) scripts/init_db.py --reset

backup: ## Executa backup do banco
	@echo "$(GREEN)Executando backup...$(NC)"
	$(PYTHON) scripts/backup_db.py

docker-build: ## Constrói imagem Docker
	@echo "$(GREEN)Construindo imagem Docker...$(NC)"
	$(DOCKER_COMPOSE) -f docker/docker-compose.yml build

docker-up: ## Inicia containers Docker
	@echo "$(GREEN)Iniciando containers...$(NC)"
	$(DOCKER_COMPOSE) -f docker/docker-compose.yml up -d

docker-down: ## Para containers Docker
	@echo "$(RED)Parando containers...$(NC)"
	$(DOCKER_COMPOSE) -f docker/docker-compose.yml down

docker-logs: ## Mostra logs dos containers
	@echo "$(GREEN)Mostrando logs...$(NC)"
	$(DOCKER_COMPOSE) -f docker/docker-compose.yml logs -f

test: ## Executa testes
	@echo "$(GREEN)Executando testes...$(NC)"
	$(PYTHON) -m pytest tests/ -v

clean: ## Limpa arquivos temporários
	@echo "$(YELLOW)Limpando arquivos temporários...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	@echo "$(GREEN)Limpeza concluída!$(NC)"

logs: ## Mostra logs do bot
	@echo "$(GREEN)Mostrando logs...$(NC)"
	tail -f logs/tech_offers_*.log
