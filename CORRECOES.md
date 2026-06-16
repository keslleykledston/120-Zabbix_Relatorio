# Correções Aplicadas

## 2026-06-16

### 1. `install.sh` falhava no macOS
- Problema: o script usava `grep -P` para extrair a versão do Python.
- Causa: o `grep` padrão do macOS não suporta a opção `-P`.
- Correção: substituí a extração por `python3 -c ...`, que funciona em macOS e Linux.

### 2. O backend não carregava o `.env`
- Problema: `config.py` lia `os.getenv(...)`, mas o arquivo `.env` nunca era carregado automaticamente.
- Impacto: `ZBX_URL`, `ZBX_TOKEN` e demais variáveis só funcionavam se fossem exportadas manualmente no shell ou passadas com `uvicorn --env-file`.
- Correção: adicionei `load_dotenv()` no início de `config.py`.

### 3. Dependência implícita virou explícita
- Problema: `python-dotenv` era usado apenas de forma transitiva por `uvicorn[standard]`.
- Risco: a leitura do `.env` quebraria se a resolução de dependências mudasse.
- Correção: adicionei `python-dotenv` em `requirements.txt`.

### 4. Mensagem de uso do instalador ajustada
- Problema: o script dizia para acessar o portal em `http://localhost:8080`, mas essa porta expõe apenas o backend FastAPI.
- Correção: diferenciei backend (`:8080`) de frontend estático (`python -m http.server 3000`).

## Validação Executada

- `python3 -m venv venv`
- `source venv/bin/activate && pip install -r requirements.txt`
- `source venv/bin/activate && python -c "import main; print(main.app.title)"`
- `source venv/bin/activate && uvicorn main:app --host 127.0.0.1 --port 8080`
- `curl http://127.0.0.1:8080/healthz`
- Geração offline de PDF e DOCX com `report_generator` e `docx_generator`

## Resultado

- Instalação concluída em `venv/`
- Backend iniciando corretamente
- `GET /healthz` respondendo `{"status":"ok"}`
- Geração de PDF e DOCX funcionando no ambiente local
