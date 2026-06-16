#!/bin/bash
# install.sh — Setup rápido do Portal de Disponibilidade (Linux/macOS)

set -e

echo "═══════════════════════════════════════════════════════════════"
echo "  Portal de Disponibilidade — PRF/AM (K3G Solutions)"
echo "  Script de Instalação — Linux/macOS"
echo "═══════════════════════════════════════════════════════════════"
echo

# Verificar dependências do sistema
echo "[1/7] Verificando dependências do sistema…"
if ! command -v python3 &> /dev/null; then
  echo "❌ Python 3 não encontrado. Instale via apt/brew/yum antes de continuar."
  exit 1
fi

PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "✓ Python $PY_VER encontrado"

# Verificar pip
if ! python3 -m pip &> /dev/null; then
  echo "❌ pip não encontrado. Instale via apt/yum/brew."
  exit 1
fi
echo "✓ pip disponível"

if ! command -v npm &> /dev/null; then
  echo "❌ npm não encontrado. Instale Node.js antes de continuar."
  exit 1
fi
echo "✓ npm disponível"

# Criar ambiente virtual (opcional mas recomendado)
echo
echo "[2/6] Criando ambiente virtual…"
if [ ! -d "venv" ]; then
  python3 -m venv venv
  echo "✓ Ambiente virtual criado"
else
  echo "✓ Ambiente virtual já existe"
fi

# Ativar ambiente
source venv/bin/activate
echo "✓ Ambiente ativado: $(which python)"

# Instalar dependências
echo
echo "[3/6] Instalando dependências Python…"
pip install --upgrade pip setuptools wheel > /dev/null 2>&1
pip install -r requirements.txt
echo "✓ Dependências instaladas"

# Configurar .env
echo
echo
echo "[4/6] Instalando dependências do frontend…"
npm install
mkdir -p static
npm run build:frontend
echo "✓ Frontend compilado em static/app.js"

echo
echo "[5/7] Configurando arquivo .env…"
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "✓ .env criado (from .env.example)"
  echo "  ⚠ Edite .env e coloque suas credenciais do Zabbix:"
  echo "    ZBX_URL=http://SEU_ZABBIX/zabbix/api_jsonrpc.php"
  echo "    ZBX_TOKEN=seu_token_aqui"
else
  echo "✓ .env já existe"
fi

echo
echo "[6/7] Inicializando banco local…"
python -c "import localdb; localdb.init_db()"
echo "✓ Banco local criado: portal.db"

# Informações de uso
echo
echo "[7/7] Instalação concluída!"
echo
echo "═══════════════════════════════════════════════════════════════"
echo "  Para iniciar o backend:"
echo "═══════════════════════════════════════════════════════════════"
echo
echo "  1. Edite .env com suas credenciais do Zabbix:"
echo "     nano .env"
echo
echo "  2. Ative o ambiente (se sair desta sessão):"
echo "     source venv/bin/activate"
echo
echo "  3. Inicie o servidor:"
echo "     uvicorn main:app --host 0.0.0.0 --port 8080"
echo
echo "  4. Portal disponível em:"
echo "     http://localhost:8080"
echo "     (dashboard + API no mesmo endereço)"
echo
echo "═══════════════════════════════════════════════════════════════"
echo "  Próximos passos:"
echo "═══════════════════════════════════════════════════════════════"
echo
echo "  • Na aba 'Configurações' do portal, insira:"
echo "    - Endereço do backend: http://localhost:8080"
echo "    - URL da API do Zabbix (mesmo que ZBX_URL)"
echo "    - Token de API"
echo
echo "  • Clique em 'Testar conexão' para validar"
echo "  • No Painel, use 'Sincronizar' para popular banco local de clientes/dispositivos"
echo "  • Use busca + lista suspensa para selecionar um ou mais clientes"
echo
echo "  • Voltando ao Painel, selecione ano/mês e exporte em PDF/DOCX"
echo
echo "═══════════════════════════════════════════════════════════════"
