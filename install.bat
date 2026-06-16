@echo off
REM install.bat — Setup rápido do Portal de Disponibilidade (Windows)

setlocal enabledelayedexpansion

cls
echo.
echo =====================================================================
echo   Portal de Disponibilidade — PRF/AM (K3G Solutions)
echo   Script de Instalacao — Windows
echo =====================================================================
echo.

REM Verificar Python
echo [1/7] Verificando Python 3...
python --version >nul 2>&1
if errorlevel 1 (
  echo.
  echo X Python 3 nao encontrado.
  echo   Baixe em: https://www.python.org/downloads/
  echo   Certifique-se de marcar "Add Python to PATH" na instalacao.
  pause
  exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PY_VER=%%i
echo OK - Python %PY_VER% encontrado

REM Verificar pip
echo.
echo [2/7] Verificando pip...
python -m pip --version >nul 2>&1
if errorlevel 1 (
  echo X pip nao encontrado
  exit /b 1
)
echo OK - pip disponivel

echo.
echo [3/7] Verificando Node.js / npm...
npm --version >nul 2>&1
if errorlevel 1 (
  echo X npm nao encontrado
  echo   Instale Node.js antes de continuar: https://nodejs.org/
  exit /b 1
)
echo OK - npm disponivel

REM Criar venv
echo.
echo [4/7] Criando ambiente virtual...
if not exist "venv" (
  python -m venv venv
  echo OK - Ambiente criado
) else (
  echo OK - Ambiente ja existe
)

REM Ativar venv
call venv\Scripts\activate.bat
if errorlevel 1 (
  echo X Falha ao ativar venv
  exit /b 1
)
echo OK - Ambiente ativado

REM Instalar dependencias
echo.
echo [5/7] Instalando dependencias Python...
python -m pip install --upgrade pip setuptools wheel >nul 2>&1
pip install -r requirements.txt
if errorlevel 1 (
  echo X Falha ao instalar dependencias
  exit /b 1
)
echo OK - Dependencias instaladas

echo.
echo [6/7] Instalando dependencias do frontend...
npm install
if errorlevel 1 (
  echo X Falha ao instalar dependencias do frontend
  exit /b 1
)
if not exist "static" mkdir static
npm run build:frontend
if errorlevel 1 (
  echo X Falha ao compilar frontend
  exit /b 1
)
echo OK - Frontend compilado

REM Configurar .env
echo.
echo [7/7] Configurando arquivo .env...
if not exist ".env" (
  copy .env.example .env >nul
  echo OK - .env criado (from .env.example)
  echo   (!) Edite .env e coloque suas credenciais do Zabbix
) else (
  echo OK - .env ja existe
)

python -c "import localdb; localdb.init_db()"
if errorlevel 1 (
  echo X Falha ao inicializar banco local
  exit /b 1
)
echo OK - Banco local criado: portal.db

REM Resumo
cls
echo.
echo =====================================================================
echo   Instalacao concluida!
echo =====================================================================
echo.
echo Para iniciar o backend:
echo.
echo   1. Abra o .env e edite as credenciais do Zabbix:
echo      notepad .env
echo.
echo   2. Se abrir uma nova janela de terminal, ative o ambiente:
echo      venv\Scripts\activate.bat
echo.
echo   3. Inicie o servidor FastAPI:
echo      uvicorn main:app --host 0.0.0.0 --port 8080
echo.
echo   4. Abra o portal em seu navegador:
echo      http://localhost:8080
echo.
echo =====================================================================
echo.
echo Proximos passos:
echo.
echo   - Na aba "Configuracoes" do portal, insira:
echo     * Endereco do backend: http://localhost:8080
echo     * URL da API do Zabbix
echo     * Token de API
echo.
echo   - Clique em "Testar conexao"
echo   - No Painel, clique em "Sincronizar" para carregar clientes no banco local
echo   - Use busca + lista suspensa para selecionar um ou mais clientes
echo.
echo   - Volte ao Painel e exporte em PDF ou DOCX
echo.
echo =====================================================================
echo.
pause
