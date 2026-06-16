# Portal de Disponibilidade — PRF/AM

Plataforma web SLA para o cliente acompanhar a disponibilidade em tempo real e gerar
relatórios mensais (PDF/DOCX) sem depender do NOC. Integra-se ao Zabbix existente
(`45.236.8.20`) e reproduz fielmente o modelo do relatório atual. Agora mantém
um banco local SQLite (`portal.db`) com cache de clientes e dispositivos para seleção rápida.

**Status:** MVP funcional · Backend (FastAPI) + Frontend (React) · Docker-ready

---

## ⚡ Instalação Rápida

### Linux/macOS
```bash
chmod +x install.sh
./install.sh
# Depois edite .env e rode: uvicorn main:app --host 0.0.0.0 --port 8080
# Abra http://localhost:8080/
```

### Windows
```cmd
install.bat
REM Depois edite .env e rode: uvicorn main:app --host 0.0.0.0 --port 8080
REM Abra http://localhost:8080/
```

### Manual (todas as plataformas)
```bash
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate.bat
pip install -r requirements.txt
npm install
npm run build:frontend
cp .env.example .env
# Edite .env com suas credenciais Zabbix
uvicorn main:app --host 0.0.0.0 --port 8080
# Abra http://localhost:8080/
```

---

## 🔧 Configuração Inicial

### 1. Gere um Token de API no Zabbix
No seu Zabbix (`45.236.8.20`):
```
Usuários > Tokens de API > Criar token
```
- **Nome:** "K3G Portal" (ou similar)
- **Usuário:** Crie um usuário dedicado com permissão de leitura
- **Host groups:** Selecione o grupo que contém os hosts PRF
- Copie o token gerado

### 2. Configure o Backend
Edite `.env`:
```bash
ZBX_URL=http://45.236.8.20/zabbix/api_jsonrpc.php
ZBX_TOKEN=seu_token_gerado_acima
ZBX_USER=                    # Só se exportar imagens de gráfico
ZBX_PASSWORD=                # Deixe vazio por enquanto
ZBX_VERIFY_TLS=false
CORS_ORIGINS=*
```

### 3. Configure o Frontend
No portal, aberto em `http://localhost:8080/`:
- Abra a aba **Configurações**
- Preencha:
  - **Endereço do backend:** `http://localhost:8080` (ou `http://noc.k3g.local:8080` em produção)
  - **URL da API Zabbix:** (mesmo de `ZBX_URL`)
  - **Token de API:** (token gerado acima)
- Clique em **Testar conexão**
- Se OK, clique em **Salvar configuração**
- No **Painel**, clique em **Sincronizar** para fazer a primeira coleta de clientes/dispositivos no banco local
- Use o campo **Buscar cliente...** na lista suspensa para selecionar um ou mais clientes

---

## 📊 Uso

### No Painel
1. Clique em **Sincronizar** para popular/atualizar o banco local `portal.db`
2. Use a lista suspensa com **busca** para selecionar **1 ou mais clientes**
3. Escolha o modo **Unificado** ou **Agrupado**
4. Selecione **ano** e **mês** de referência
5. Os dados carregam automaticamente do Zabbix para os clientes selecionados
6. Exporte em:
   - **PDF:** Relatório profissional (capa + metodologia + tabela + seção/unidade)
   - **DOCX:** Word editável (mesmo conteúdo, formato flexível)
7. Abra a unidade desejada para detalhe (série diária, resumo, histórico de incidentes)

### Abas
- **Painel:** Dashboard com KPIs, lista suspensa de clientes, busca, tabela de unidades
- **Configurações:** Cadastro do Zabbix + teste de conexão

---

## 🏗️ Arquitetura

```
┌──────────────────────────────────────────────────────────────┐
│ Frontend (React)                                             │
│ portal-prf-sla.jsx — Dashboard + seletor mês/ano            │
│ • Painel: KPIs, corredores BR-174/BR-319, tabela             │
│ • Config: Cadastro + teste de conexão Zabbix                │
└────────────────┬─────────────────────────────────────────────┘
                 │ fetch /api/...
                 ▼
┌──────────────────────────────────────────────────────────────┐
│ Backend (FastAPI)                                            │
├──────────────────────────────────────────────────────────────┤
│ main.py                                                      │
│ • GET /api/config               (carregar config salva)     │
│ • GET /api/clients              (listar clientes do cache)  │
│ • POST /api/clients/sync        (sincronizar do Zabbix)     │
│ • POST /api/config              (salvar URL/token/user)     │
│ • POST /api/zabbix/test         (testar conexão)            │
│ • GET /api/units?year=...       (lista de unidades)         │
│ • GET /api/report/monthly       (JSON com SLA + incidentes) │
│ • GET /api/report/monthly.pdf   (PDF no modelo)             │
│ • GET /api/report/monthly.docx  (DOCX editável)             │
│ • GET /healthz                  (health check)              │
├──────────────────────────────────────────────────────────────┤
│ localdb.py — Cache local SQLite                              │
│ • clients / devices / client_devices em portal.db           │
│ • primeira coleta e seleção local de clientes              │
├──────────────────────────────────────────────────────────────┤
│ zabbix_client.py — Wrapper JSON-RPC Zabbix                  │
│ • history.get (ICMP up/down, latência, perda)               │
│ • event.get (histórico de alertas/incidentes)               │
│ • hosts_by_name (descoberta de hosts PRF)                   │
├──────────────────────────────────────────────────────────────┤
│ sla.py — Motor SLA                                           │
│ • D = (To − Ti) / To (fórmula exata do relatório)            │
│ • Classificação ok/warn/crit                                │
├──────────────────────────────────────────────────────────────┤
│ report_generator.py — PDF (WeasyPrint)                       │
│ • Capa + metodologia + tabela consolidada + seção/unidade   │
├──────────────────────────────────────────────────────────────┤
│ docx_generator.py — DOCX (python-docx)                       │
│ • Mesmo conteúdo, formato Word editável                     │
├──────────────────────────────────────────────────────────────┤
│ config.py — Persistência de config                           │
│ • Load/save de URL/token/user em config.json                │
│ • Fallback para .env se config.json não existir             │
└────────────────┬─────────────────────────────────────────────┘
                 │ JSON-RPC
                 ▼
        ┌────────────────────┐
        │   Zabbix (NOC)     │
        │ 45.236.8.20        │
        │ • ICMP monitoring  │
        │ • Event history    │
        └────────────────────┘
```

---

## 📁 Arquivos

| Arquivo | Descrição |
|---|---|
| `portal-prf-sla.jsx` | Dashboard React · abas painel/config |
| `main.py` | API FastAPI · 8 endpoints |
| `localdb.py` | Banco local SQLite (`portal.db`) |
| `zabbix_client.py` | Cliente JSON-RPC · history/event/hosts |
| `sla.py` | Motor SLA · `D = (To-Ti)/To` |
| `report_generator.py` | PDF via WeasyPrint |
| `docx_generator.py` | DOCX via python-docx |
| `config.py` | Persistência de configuração |
| `requirements.txt` | Dependências Python |
| `.env.example` | Template de variáveis |
| `install.sh` / `install.bat` | Scripts de instalação |
| `Relatorio_...*.pdf` / `.docx` | Exemplos de saída |

---

## 📈 Dados de Exemplo (Março/2026)

**SLA médio consolidado: 87,12%** — apenas 1 das 10 unidades cumpre ≥99%.

| Unidade | SLA | Perda | Status |
|---|---|---|---|
| Hospital Delphina Aziz | 99,03% | 0,03% | ✓ Dentro do SLA |
| Av. Mário Ypiranga | 97,23% | 2,36% | ⚠ Atenção |
| Posto Careiro (BR-319 km 13) | 96,53% | 2,58% | ⚠ Atenção |
| CICC | 96,53% | 0,21% | ⚠ Atenção |
| Ceasa (BR-319 km 0) | 95,56% | 1,14% | ⚠ Atenção |
| UOP3302 (BR-174 km 1010) | 93,48% | 1,80% | ⚠ Atenção |
| Pista Honda (BR-174 km 932) | 88,35% | 2,39% | ⚠ Atenção |
| Escola Agrícola (BR-174 km 905) | 87,38% | 7,14% | ❌ Crítico |
| Manaus I / UOp3301 (km 927) | 81,83% | 11,89% | ❌ Crítico |
| **Fazenda Vieira (BR-174 km 962)** | **35,23%** | **61,81%** | **❌ Crítico** |

**Nota:** Fazenda Vieira está em colapso — 61,8% de perda de pacotes indica enlace quebrado.

---

## 🚀 Roadmap (pós-MVP)

### Curto Prazo
- [ ] **Cache Redis** — evita varrer `history` a cada requisição (queries pesadas)
- [ ] **APScheduler** — agendador que fecha o mês às 00h05 → PostgreSQL (arquivo trava, não muda)
- [ ] **Docker Compose** — stack completo (backend + Redis + Postgres) pronto para EasyPanel
- [ ] **Gráficos dinâmicos** — recharts no painel (SLA ao longo do mês)

### Médio Prazo
- [ ] **Multi-cliente** — RLS por tenant (padrão ACS-SaaS); cada cliente vê só seus hosts
- [ ] **SLA Contratual** — meta por unidade (ex. 99,5%) e cálculo de glosa/multa
- [ ] **Login** — Keycloak ou JWT; perfis cliente (read-only) e NOC (admin)
- [ ] **Alerta Proativo** — webhook Evolution API quando unidade cruza limite no mês

### Longo Prazo
- [ ] **BI / Dashboards históricos** — Grafana ou Superset integrado
- [ ] **Exportação de dados** — CSV, Excel com análise trimestral
- [ ] **Integração NetBox** — pull de localização/contato automático

---

## 🔐 Segurança

- **Token no backend:** O token Zabbix **nunca** é exposto no frontend. Fica em `.env` ou `config.json`.
- **Config.json:** Arquivo ignorado em `.gitignore`. Salva URL/token no disco (apenas backend acessa).
- **CORS:** Configurável em `CORS_ORIGINS=*` (em produção: restringir a domínios).
- **HTTPS:** Recomendado usar reverse proxy (nginx) com certificado em produção.

---

## 🛠️ Troubleshooting

### "Conectando ao Zabbix…" demora muito
- Verifique conectividade: `curl http://45.236.8.20/zabbix/api_jsonrpc.php`
- Token expirou? Gere novo no Zabbix
- Host groups permissão? Usuário tem acesso aos hosts PRF?

### "Modo demonstração" ao abrir o portal
- Se a dashboard abrir, o frontend está OK. Esse modo só indica que o backend ainda não conseguiu consultar o Zabbix.
- Verifique se `.env` tem `ZBX_URL` e `ZBX_TOKEN` válidos, ou salve a configuração na aba **Configurações**.
- Backend não está rodando ou não acessível
- Configure `Endereço do backend` na aba Configurações
- Verifique CORS se o frontend e backend estão em domínios diferentes

### A lista de clientes está vazia
- Clique em **Sincronizar** no Painel para preencher `portal.db`
- Verifique se o usuário/token do Zabbix tem acesso aos `host groups` dos clientes
- Se necessário, apague `portal.db` e reinicie o backend para recriar a base local

### PDF/DOCX não baixa
- Verifique que o endpoint retorna 200: `curl http://localhost:8080/api/report/monthly.pdf?year=2026&month=3`
- Firewall bloqueando? Teste `localhost` first

### Permissão negada ao salvar config.json
- Backend está rodando com privilégios insuficientes
- Ou o diretório não é writable
- Solução: use `.env` em produção (não salve config em disco)

---

## 📞 Suporte

K3G Solutions LTDA · NOC 24×7
- Email: suporte@k3g.com.br
- Telefone: (34) 3314-8894
- Documentação: Veja README.md (este arquivo) e comments no código

---

## 📄 Licença

Proprietary · K3G Solutions LTDA · 2026
