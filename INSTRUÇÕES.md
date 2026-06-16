# 🚀 Guia de Início Rápido

## Passo 1: Clonar ou descompactar o projeto

```bash
# Se em ZIP, descompacte:
unzip portal-disponibilidade.zip
cd portal-disponibilidade
```

## Passo 2: Executar o instalador

### Linux/macOS
```bash
chmod +x install.sh
./install.sh
```

### Windows
```cmd
install.bat
```

O instalador irá:
- ✓ Verificar Python 3
- ✓ Verificar Node.js / npm
- ✓ Criar ambiente virtual
- ✓ Instalar dependências
- ✓ Compilar o frontend
- ✓ Criar arquivo `.env`
- ✓ Criar banco local `portal.db`

## Passo 3: Configurar o Zabbix

### 3.1 Gerar Token no Zabbix (`45.236.8.20`)

1. Abra o navegador: `http://45.236.8.20`
2. Faça login com sua conta
3. Vá para **Usuários** (menu superior)
4. Clique em **Tokens de API**
5. Clique em **Criar token**
6. Preencha:
   - **Nome:** "K3G Portal" (ou seu nome)
   - **Usuário:** Selecione um usuário com permissão de leitura nos hosts PRF
   - **Host groups:** Marque o grupo que contém os hosts PRF/AM
7. Clique em **Criar**
8. **Copie o token** exibido (é uma string longa de letras/números)

### 3.2 Editar `.env`

Abra o arquivo `.env` com seu editor de texto favorito:

```bash
nano .env        # Linux/macOS
notepad .env     # Windows
```

E edite:
```env
ZBX_URL=http://45.236.8.20/zabbix/api_jsonrpc.php
ZBX_TOKEN=COLE_SEU_TOKEN_AQUI
ZBX_USER=
ZBX_PASSWORD=
ZBX_VERIFY_TLS=false
CORS_ORIGINS=*
```

**Exemplo:**
```env
ZBX_URL=http://45.236.8.20/zabbix/api_jsonrpc.php
ZBX_TOKEN=COLE_SEU_TOKEN_AQUI
ZBX_USER=
ZBX_PASSWORD=
ZBX_VERIFY_TLS=false
CORS_ORIGINS=*
```

Salve o arquivo.

## Passo 4: Iniciar o Backend

Abra um terminal/prompt e execute:

### Linux/macOS
```bash
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8080
```

### Windows
```cmd
venv\Scripts\activate.bat
uvicorn main:app --host 0.0.0.0 --port 8080
```

Você verá:
```
INFO:     Uvicorn running on http://0.0.0.0:8080
```

✓ O backend está rodando!

## Passo 5: Abrir o Portal

Abra o navegador em:
```
http://localhost:8080/
```

O FastAPI agora serve a dashboard diretamente. Não precisa abrir `portal-prf-sla.jsx` manualmente nem subir `http.server` separado.

## Passo 6: Configurar a Conexão

No portal, abra a aba **Configurações**:

1. **Endereço do backend:** `http://localhost:8080`
2. **URL da API Zabbix:** `http://45.236.8.20/zabbix/api_jsonrpc.php`
3. **Token de API:** Cole o token gerado no Passo 3
4. Clique em **Testar conexão**

Se OK (verde):
```
✓ Conectado ao Zabbix 6.0
✓ 10 host(s) PRF encontrados
✓ latência: 245 ms
```

Clique em **Salvar configuração**.

## Passo 7: Usar o Portal

Volte à aba **Painel**:

1. Clique em **Sincronizar** para fazer a primeira coleta de clientes/dispositivos
2. Use a lista suspensa e o campo **Buscar cliente...** para escolher **1 ou mais clientes**
3. Escolha o modo **Unificado** ou **Agrupado**
4. Selecione o **mês** e **ano** desejado
5. Os dados carregam automaticamente
6. Exporte em:
   - **PDF:** Relatório profissional (para impressão/email)
   - **DOCX:** Word editável (para customização)
7. Clique em uma unidade para detalhe completo

---

## ❓ Dúvidas Frequentes

**P: O portal diz "Modo demonstração"**  
R: Significa que o backend não está conectado. Verifique se está rodando (`uvicorn main:app...`) e se a URL em Configurações está correta.

**P: Erro "Falha na conexão" ao testar**  
R: Verifique:
- Backend está rodando? `curl http://localhost:8080/healthz`
- Token é válido? Gere novo no Zabbix
- Hosts PRF existem? Verifique em Zabbix > Hosts > Filtro "PRF"

**P: Posso agendar a exportação do relatório?**  
R: Em breve (roadmap). Por enquanto, use a aba Painel para gerar manualmente.

**P: Como uso em produção?**  
R: Veja `README.md` > Deployment (Docker Compose + nginx).

---

## 🎓 Próximas etapas

Após confirmar que tudo funciona:
1. Leia `README.md` para entender a arquitetura completa
2. Explore os dados em diferentes períodos
3. Teste a exportação em PDF e DOCX
4. Compartilhe o portal com outras pessoas da PRF

---

**Sucesso!** 🚀

K3G Solutions · NOC 24×7
