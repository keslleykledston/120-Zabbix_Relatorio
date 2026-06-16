import React, { useMemo, useState, useEffect } from "react";
import { createRoot } from "react-dom/client";

/* O endereço do backend (FastAPI) é definido na aba "Configurações".
   O token do Zabbix fica NO BACKEND (.env / config.json), nunca no front. */

/* ============================================================
   PORTAL DE DISPONIBILIDADE — PRF/AM  (MVP K3G Solutions)
   Contrato 07/2025 · PE 9001/2025 — Link Dedicado
   Dados reais: Março/2026 (44.640 min). Fonte: Zabbix (ICMP).
   Série diária ilustrativa derivada da média mensal —
   em produção vem de Zabbix trends.get.
   ============================================================ */

const MONTH_MIN = 44640; // 31 dias

// SLA thresholds (decimal)
const T_OK = 0.99;
const T_WARN = 0.9;

const C = {
  bg: "#EEF2F6",
  surface: "#FFFFFF",
  ink: "#0E2436",
  inkSoft: "#5A6B7B",
  inkFaint: "#8A99A8",
  line: "#DCE3EA",
  ok: "#128A5E",
  warn: "#D98A26",
  crit: "#C9384A",
  teal: "#0E7C86",
};

function statusOf(d) {
  if (d >= T_OK) return "ok";
  if (d >= T_WARN) return "warn";
  return "crit";
}
function statusColor(d) {
  const s = statusOf(d);
  return s === "ok" ? C.ok : s === "warn" ? C.warn : C.crit;
}
function statusLabel(d) {
  const s = statusOf(d);
  return s === "ok" ? "Dentro do SLA" : s === "warn" ? "Atenção" : "Crítico";
}
const pct = (d) => (d * 100).toFixed(2).replace(".", ",") + "%";
const minToHuman = (m) => {
  const h = Math.floor(m / 60);
  const mm = m % 60;
  return `${h}h ${mm}min`;
};
const fmtInt = (n) => n.toLocaleString("pt-BR");

// ---- DADOS REAIS (Março/2026) -------------------------------
const UNITS = [
  { id: "delphina", cliente: "MPAM", nome: "Hospital Delphina Aziz", local: "Av. Torquato Tapajós, 9250 — Manaus/AM", corredor: "Manaus", km: null, ip: "167.249.180.74", d: 0.9903, lat: 4.02, loss: 0.03467, down: 433, inc: "Sem registro" },
  { id: "ypiranga", cliente: "MPAM", nome: "Av. Mário Ypiranga (DNIT)", local: "Av. Mário Ypiranga, 2479 — Parque 10, Manaus/AM", corredor: "Manaus", km: null, ip: "100.65.3.201", d: 0.9723, lat: 3.99, loss: 2.355, down: 1237, inc: "—" },
  { id: "careiro", cliente: "MPAM", nome: "Posto Careiro — UOP3304", local: "BR-319, km 13 — Careiro da Várzea/AM", corredor: "BR-319", km: 13, ip: "167.250.203.20", d: 0.9653, lat: 4.31, loss: 2.5798, down: 1549, inc: "—" },
  { id: "cicc", cliente: "MPAM", nome: "CICC — Comando e Controle", local: "Av. André Araújo, 1422 — Petrópolis, Manaus/AM", corredor: "Manaus", km: null, ip: "167.249.180.106", d: 0.9653, lat: 3.1, loss: 0.2073, down: 1549, inc: "—" },
  { id: "ceasa", cliente: "MPAM", nome: "Posto Manaus II — UOP3303 (Ceasa)", local: "BR-319, km 0 — Manaus/AM", corredor: "BR-319", km: 0, ip: "167.250.203.22", d: 0.9556, lat: 4.83, loss: 1.1435, down: 1982, inc: "—" },
  { id: "figueiredo", cliente: "MPAM", nome: "UOP3302", local: "BR-174, km 1010 — Presidente Figueiredo/AM", corredor: "BR-174", km: 1010, ip: "10.123.122.76", d: 0.9348, lat: 4.47, loss: 1.8031, down: 2910, inc: "—" },
  { id: "honda", cliente: "MPAM", nome: "Pista de Teste Moto Honda", local: "BR-174, km 932 — Manaus/AM", corredor: "BR-174", km: 932, ip: "10.123.122.77", d: 0.8835, lat: 5.75, loss: 2.393, down: 5200, inc: "—" },
  { id: "agricola", cliente: "MPAM", nome: "Escola Agrícola", local: "BR-174, km 905 — Manaus/AM", corredor: "BR-174", km: 905, ip: "10.123.122.78", d: 0.8738, lat: 5.81, loss: 7.1359, down: 5634, inc: "—" },
  { id: "uop3301", cliente: "MPAM", nome: "Posto Manaus I — UOp3301", local: "BR-174, km 927 — Manaus/AM", corredor: "BR-174", km: 927, ip: "10.123.122.75", d: 0.8183, lat: 5.25, loss: 11.8912, down: 8110, inc: "—" },
  { id: "vieira", cliente: "MPAM", nome: "Fazenda Vieira", local: "BR-174, km 962 — Manaus/AM", corredor: "BR-174", km: 962, ip: "10.123.122.80", d: 0.3523, lat: 1.81, loss: 61.8131, down: 28913, inc: "Falha recorrente" },
];

// Série diária determinística com média = SLA mensal (ilustrativa)
function dailySeries(unit) {
  const days = 31;
  const target = unit.d;
  const seed = unit.id.split("").reduce((a, c) => a + c.charCodeAt(0), 0);
  const arr = [];
  let acc = 0;
  for (let i = 0; i < days; i++) {
    const noise = Math.sin((i + seed) * 1.7) * (1 - target) * 0.9;
    let v = target + noise;
    v = Math.max(0, Math.min(1, v));
    arr.push(v);
    acc += v;
  }
  // ajuste fino para casar a média
  const adj = target - acc / days;
  return arr.map((v) => Math.max(0, Math.min(1, v + adj)));
}

// Mapeia a resposta do backend (/api/report/monthly) para o formato do portal.
function mapApiUnits(apiUnits) {
  return apiUnits.map((u, i) => {
    const local = u.local || u.nome || "";
    const kmMatch = local.match(/km\s*(\d+)/i);
    const km = kmMatch ? parseInt(kmMatch[1], 10) : null;
    let corredor = "Manaus";
    if (/BR-?174/i.test(local)) corredor = "BR-174";
    else if (/BR-?319/i.test(local)) corredor = "BR-319";
    const incCount = Array.isArray(u.incidentes) ? u.incidentes.length : 0;
    return {
      id: u.hostid || `u${i}`,
      cliente: u.cliente || "Geral",
      nome: u.nome,
      local,
      corredor,
      km,
      ip: u.ip || "",
      d: u.availability,
      lat: u.latency_ms,
      loss: u.packet_loss_pct,
      down: u.downtime_min,
      inc: incCount ? `${incCount} incidente(s)` : "Sem registro",
    };
  });
}

const MONTH_NAMES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"];
const YEARS = [2025, 2026];

function defaultApiBase() {
  if (typeof window === "undefined") return "";
  if (window.location.protocol === "http:" || window.location.protocol === "https:") {
    return window.location.origin;
  }
  return "";
}

function App() {
  const [tab, setTab] = useState("painel");        // painel | config
  const [year, setYear] = useState(2026);
  const [month, setMonth] = useState(3);           // Março
  const [apiBase, setApiBase] = useState(defaultApiBase); // mesmo host/porta por padrão
  const [sel, setSel] = useState(null);
  const [printing, setPrinting] = useState(false);
  const [sortBy, setSortBy] = useState("sla");
  const [units, setUnits] = useState(UNITS);       // seed = Março/2026 (demonstração)
  const [live, setLive] = useState(false);
  const [loading, setLoading] = useState(false);
  const [availableClients, setAvailableClients] = useState([]);
  const [draftSelectedClients, setDraftSelectedClients] = useState([]);
  const [appliedSelectedClients, setAppliedSelectedClients] = useState([]);
  const [reportMode, setReportMode] = useState("unified");
  const [clientPickerOpen, setClientPickerOpen] = useState(false);
  const [clientSearch, setClientSearch] = useState("");
  const [syncingClients, setSyncingClients] = useState(false);

  const periodoLabel = `${MONTH_NAMES[month - 1]}/${year}`;
  const selectedClientNames = availableClients.filter((c) => appliedSelectedClients.includes(c.id)).map((c) => c.name);
  const pendingClientNames = availableClients.filter((c) => draftSelectedClients.includes(c.id)).map((c) => c.name);
  const filteredClients = useMemo(() => {
    const term = clientSearch.trim().toLowerCase();
    if (!term) return availableClients;
    return availableClients.filter((client) =>
      client.name.toLowerCase().includes(term) || String(client.hosts).includes(term)
    );
  }, [availableClients, clientSearch]);

  function buildReportUrl(ext) {
    const params = new URLSearchParams({ year: String(year), month: String(month), group_mode: reportMode });
    if (appliedSelectedClients.length) params.set("client_ids", appliedSelectedClients.join(","));
    return `${apiBase}/api/report/monthly.${ext}?${params.toString()}`;
  }

  function loadClients(refresh = false) {
    if (!apiBase) return;
    const url = refresh ? `${apiBase}/api/clients?refresh=true` : `${apiBase}/api/clients`;
    if (refresh) setSyncingClients(true);
    fetch(url)
      .then((r) => { if (!r.ok) throw new Error("clients"); return r.json(); })
      .then((data) => {
        const clients = data.clients || [];
        setAvailableClients(clients);
        setDraftSelectedClients((prev) => {
          const valid = prev.filter((id) => clients.some((client) => client.id === id));
          if (valid.length) return valid;
          return clients.length ? [clients[0].id] : [];
        });
        setAppliedSelectedClients((prev) => {
          const valid = prev.filter((id) => clients.some((client) => client.id === id));
          if (valid.length) return valid;
          return clients.length ? [clients[0].id] : [];
        });
      })
      .catch(() => setAvailableClients([]))
      .finally(() => setSyncingClients(false));
  }

  function toggleClient(clientId) {
    setDraftSelectedClients((prev) => (
      prev.includes(clientId)
        ? prev.filter((id) => id !== clientId)
        : [...prev, clientId]
    ));
  }

  function applyClientSelection() {
    setAppliedSelectedClients(draftSelectedClients);
    setClientPickerOpen(false);
  }

  useEffect(() => {
    if (!apiBase) return;
    loadClients(false);
  }, [apiBase]);

  useEffect(() => {
    if (!apiBase) { setLive(false); return; }
    if (!appliedSelectedClients.length) { setLive(false); return; }
    setLoading(true);
    const params = new URLSearchParams({ year: String(year), month: String(month), group_mode: reportMode, client_ids: appliedSelectedClients.join(",") });
    fetch(`${apiBase}/api/report/monthly?${params.toString()}`)
      .then((r) => { if (!r.ok) throw new Error("offline"); return r.json(); })
      .then((data) => { setUnits(mapApiUnits(data.unidades)); setLive(true); })
      .catch(() => setLive(false))
      .finally(() => setLoading(false));
  }, [apiBase, year, month, appliedSelectedClients, reportMode]);

  const consolidado = useMemo(() => {
    const n = units.length;
    const avg = units.reduce((s, u) => s + u.d, 0) / n;
    const totalDown = units.reduce((s, u) => s + u.down, 0);
    const ok = units.filter((u) => statusOf(u.d) === "ok").length;
    const crit = units.filter((u) => statusOf(u.d) === "crit").length;
    const warn = units.filter((u) => statusOf(u.d) === "warn").length;
    const worst = [...units].sort((a, b) => a.d - b.d)[0];
    return { n, avg, totalDown, ok, warn, crit, worst };
  }, [units]);

  const sorted = useMemo(() => {
    const arr = [...units];
    if (sortBy === "sla") arr.sort((a, b) => a.d - b.d);
    if (sortBy === "loss") arr.sort((a, b) => b.loss - a.loss);
    if (sortBy === "lat") arr.sort((a, b) => b.lat - a.lat);
    if (sortBy === "nome") arr.sort((a, b) => a.nome.localeCompare(b.nome));
    return arr;
  }, [sortBy, units]);

  const selUnit = sel ? units.find((u) => u.id === sel) : null;

  function gerarRelatorio(fmt) {
    if (apiBase) {
      const ext = fmt === "pdf" ? "pdf" : "docx";
      window.open(buildReportUrl(ext), "_blank");
      return;
    }
    if (fmt === "docx") {
      alert("Modo demonstração: exportação DOCX não disponível. Configure o backend na aba Configurações.");
      return;
    }
    // PDF em demonstração
    setPrinting(true);
    setTimeout(() => { window.print(); setPrinting(false); }, 120);
  }

  return (
    <div style={{ fontFamily: "'IBM Plex Sans', system-ui, sans-serif", background: C.bg, color: C.ink, minHeight: "100vh" }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');
        * { box-sizing: border-box; }
        .mono { font-family: 'IBM Plex Mono', monospace; font-variant-numeric: tabular-nums; }
        .card { background: ${C.surface}; border: 1px solid ${C.line}; border-radius: 12px; }
        .ubtn { cursor: pointer; border: 1px solid ${C.line}; background: ${C.surface}; color: ${C.ink};
                border-radius: 8px; padding: 7px 12px; font-size: 13px; font-weight: 500; transition: all .15s; }
        .ubtn:hover { border-color: ${C.teal}; color: ${C.teal}; }
        .ubtn.active { background: ${C.ink}; color: #fff; border-color: ${C.ink}; }
        .unit-row { cursor: pointer; transition: background .12s; }
        .unit-row:hover { background: #F6F9FB; }
        .loadingbar { position: relative; overflow: hidden; height: 4px; background: #DCE3EA; border-radius: 999px; }
        .loadingbar::after { content: ""; position: absolute; inset: 0 auto 0 0; width: 32%; background: linear-gradient(90deg, ${C.teal}, ${C.ok}); border-radius: 999px; animation: slide 1.1s linear infinite; }
        @media print {
          .no-print { display: none !important; }
          body { background: #fff; }
          .report-only { display: block !important; }
          .card { box-shadow: none; }
        }
        .report-only { display: none; }
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.45} }
        @keyframes slide { 0% { transform: translateX(-120%); } 100% { transform: translateX(340%); } }
      `}</style>

      {/* ===================== APP (tela) ===================== */}
      <div className="no-print" style={{ maxWidth: 1180, margin: "0 auto", padding: "0 20px 60px" }}>
        {(loading || syncingClients) && (
          <div style={{ marginTop: 12, marginBottom: 6 }}>
            <div className="loadingbar" />
            <div style={{ fontSize: 12, color: C.inkSoft, marginTop: 6 }}>
              {syncingClients ? "Sincronizando clientes e dispositivos no banco local..." : "Consultando Zabbix e carregando dispositivos selecionados..."}
            </div>
          </div>
        )}
        {/* Header */}
        <header style={{ paddingTop: 26, paddingBottom: 18, borderBottom: `1px solid ${C.line}`, marginBottom: 22 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 16 }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
                <div style={{ width: 30, height: 30, borderRadius: 7, background: C.ink, display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", fontWeight: 700, fontSize: 13 }} className="mono">K3</div>
                <span style={{ fontSize: 12, letterSpacing: 1.5, color: C.inkSoft, textTransform: "uppercase", fontWeight: 600 }}>Portal de Disponibilidade</span>
              </div>
              <h1 style={{ margin: 0, fontSize: 26, fontWeight: 700, letterSpacing: -0.4 }}>Portal Multi-Cliente de Disponibilidade</h1>
              <p style={{ margin: "6px 0 0", color: C.inkSoft, fontSize: 13 }} className="mono">
                {selectedClientNames.length ? selectedClientNames.join(" · ") : "Selecione um ou mais clientes"} · Monitoramento ICMP (Zabbix, 60s)
              </p>
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6, marginTop: 8, fontSize: 12, fontWeight: 600, padding: "3px 10px", borderRadius: 20, background: (live ? C.ok : C.warn) + "18", color: live ? C.ok : C.warn }}>
                <span style={{ width: 7, height: 7, borderRadius: "50%", background: live ? C.ok : C.warn }} />
                {loading ? "Conectando ao Zabbix…" : live ? `Conectado ao Zabbix — ${periodoLabel}` : "Modo demonstração — dados de Março/2026"}
              </span>
            </div>
            {tab === "painel" && (
              <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 10 }}>
                <div style={{ display: "flex", gap: 8 }}>
                  <select value={month} onChange={(e) => setMonth(Number(e.target.value))} className="ubtn mono" title="Mês de referência">
                    {MONTH_NAMES.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
                  </select>
                  <select value={year} onChange={(e) => setYear(Number(e.target.value))} className="ubtn mono" title="Ano">
                    {YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
                  </select>
                  <select value={reportMode} onChange={(e) => setReportMode(e.target.value)} className="ubtn mono" title="Modo do relatório">
                    <option value="unified">Unificado</option>
                    <option value="grouped">Agrupado</option>
                  </select>
                </div>
                <div style={{ position: "relative", minWidth: 320 }}>
                  <button className="ubtn" style={{ width: "100%", textAlign: "left", padding: "10px 12px" }} onClick={() => setClientPickerOpen((v) => !v)}>
                    {pendingClientNames.length ? `${pendingClientNames.length} cliente(s) marcados` : "Selecionar clientes"}
                  </button>
                  {clientPickerOpen && (
                    <div className="card" style={{ position: "absolute", right: 0, top: "calc(100% + 8px)", width: 360, padding: 14, zIndex: 20, boxShadow: "0 12px 30px rgba(0,0,0,.12)" }}>
                      <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
                        <input
                          value={clientSearch}
                          onChange={(e) => setClientSearch(e.target.value)}
                          placeholder="Buscar cliente..."
                          style={{ flex: 1, padding: "9px 11px", border: `1px solid ${C.line}`, borderRadius: 8, fontSize: 13.5, background: "#fff", color: C.ink }}
                        />
                        <button className="ubtn" onClick={() => loadClients(true)} disabled={syncingClients}>
                          {syncingClients ? "Sync..." : "Sincronizar"}
                        </button>
                      </div>
                      <div style={{ maxHeight: 260, overflowY: "auto", border: `1px solid ${C.line}`, borderRadius: 8, padding: 8 }}>
                        {filteredClients.map((client) => (
                          <label key={client.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, padding: "7px 6px", fontSize: 13, cursor: "pointer" }}>
                            <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                              <input type="checkbox" checked={draftSelectedClients.includes(client.id)} onChange={() => toggleClient(client.id)} />
                              <span>{client.name}</span>
                            </span>
                            <span className="mono" style={{ color: C.inkFaint }}>{client.hosts}</span>
                          </label>
                        ))}
                        {!filteredClients.length && (
                          <div style={{ padding: "8px 6px", fontSize: 12.5, color: C.inkFaint }}>Nenhum cliente encontrado.</div>
                        )}
                      </div>
                      <div style={{ display: "flex", justifyContent: "space-between", gap: 8, marginTop: 10 }}>
                        <button className="ubtn" onClick={() => setClientPickerOpen(false)}>Fechar</button>
                        <button
                          className="ubtn"
                          style={{ background: C.teal, color: "#fff", borderColor: C.teal, fontWeight: 600 }}
                          onClick={applyClientSelection}
                          disabled={!draftSelectedClients.length || loading}
                        >
                          Selecionar
                        </button>
                      </div>
                    </div>
                  )}
                </div>
                <div style={{ display: "flex", gap: 8 }}>
                  <button className="ubtn" style={{ background: C.teal, color: "#fff", borderColor: C.teal, fontWeight: 600, flex: 1 }} onClick={() => gerarRelatorio("pdf")}>
                    ↓ PDF — {periodoLabel}
                  </button>
                  <button className="ubtn" style={{ background: C.teal, color: "#fff", borderColor: C.teal, fontWeight: 600, flex: 1 }} onClick={() => gerarRelatorio("docx")}>
                    ↓ DOCX — {periodoLabel}
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Abas */}
          <div style={{ display: "flex", gap: 6, marginTop: 18 }}>
            <button className={"ubtn" + (tab === "painel" ? " active" : "")} onClick={() => setTab("painel")}>Painel</button>
            <button className={"ubtn" + (tab === "config" ? " active" : "")} onClick={() => setTab("config")}>Configurações</button>
          </div>
        </header>

        {tab === "config" && (
          <ZabbixConfig apiBase={apiBase} setApiBase={setApiBase} live={live} />
        )}

        {tab === "painel" && (
        <>
        {!appliedSelectedClients.length && (
          <div className="card" style={{ borderColor: C.warn, background: "#FEFAF2", padding: "11px 16px", marginBottom: 18, fontSize: 13, color: C.inkSoft }}>
            Selecione <b>um ou mais clientes</b> e clique em <b>Selecionar</b> para consultar os dispositivos e exportar relatório <b>unificado</b> ou <b>agrupado</b>.
          </div>
        )}
        {!live && month !== 3 && (
          <div className="card" style={{ borderColor: C.warn, background: "#FEFAF2", padding: "11px 16px", marginBottom: 18, fontSize: 13, color: C.inkSoft }}>
            Sem backend conectado, o modo demonstração só possui dados de <b>Março/2026</b>. Configure o Zabbix na aba <b>Configurações</b> para consultar {periodoLabel}.
          </div>
        )}

        {/* KPIs consolidados */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 14, marginBottom: 22 }}>
          <Kpi label="SLA médio consolidado" value={pct(consolidado.avg)} sub={`${consolidado.n} unidades monitoradas`} color={statusColor(consolidado.avg)} big />
          <Kpi label="Indisponibilidade total" value={minToHuman(consolidado.totalDown)} sub={`${fmtInt(consolidado.totalDown)} min no mês`} color={C.ink} />
          <Kpi label="Dentro do SLA (≥99%)" value={String(consolidado.ok)} sub={`de ${consolidado.n} unidades`} color={C.ok} />
          <Kpi label="Em atenção / crítico" value={`${consolidado.warn} / ${consolidado.crit}`} sub="atenção · crítico" color={consolidado.crit ? C.crit : C.warn} />
        </div>

        {/* Alerta crítico */}
        {consolidado.worst && statusOf(consolidado.worst.d) === "crit" && (
          <div className="card" style={{ borderColor: C.crit, background: "#FDF2F3", padding: "12px 16px", marginBottom: 22, display: "flex", alignItems: "center", gap: 12 }}>
            <span style={{ width: 9, height: 9, borderRadius: "50%", background: C.crit, animation: "pulse 1.6s infinite", flexShrink: 0 }} />
            <div style={{ fontSize: 13.5 }}>
              <strong>Atenção:</strong> <strong>{consolidado.worst.nome}</strong> operou com SLA de <span className="mono" style={{ color: C.crit, fontWeight: 600 }}>{pct(consolidado.worst.d)}</span> ({minToHuman(consolidado.worst.down)} indisponível). Perda de pacotes de {consolidado.worst.loss.toFixed(1)}% indica falha de enlace — recomenda-se abertura de chamado N3.
            </div>
          </div>
        )}

        {/* Tabela / ranking de unidades */}
        <section className="card" style={{ padding: "20px 22px", marginBottom: 22 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12, marginBottom: 16 }}>
            <SectionTitle eyebrow="Detalhamento" title="Unidades monitoradas" noMargin />
            <div style={{ display: "flex", gap: 6 }}>
              {[["sla", "SLA"], ["loss", "Perda"], ["lat", "Latência"], ["nome", "Nome"]].map(([k, l]) => (
                <button key={k} className={"ubtn" + (sortBy === k ? " active" : "")} onClick={() => setSortBy(k)}>{l}</button>
              ))}
            </div>
          </div>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13.5 }}>
              <thead>
                <tr style={{ textAlign: "left", color: C.inkSoft, fontSize: 11.5, textTransform: "uppercase", letterSpacing: 0.5 }}>
                  <th style={{ padding: "8px 6px" }}>Unidade</th>
                  <th style={{ padding: "8px 6px" }}>Cliente</th>
                  <th style={{ padding: "8px 6px" }}>SLA</th>
                  <th style={{ padding: "8px 6px" }}>Indisp.</th>
                  <th style={{ padding: "8px 6px" }}>Latência</th>
                  <th style={{ padding: "8px 6px" }}>Perda</th>
                  <th style={{ padding: "8px 6px" }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((u) => (
                  <tr key={u.id} className="unit-row" onClick={() => setSel(u.id)} style={{ borderTop: `1px solid ${C.line}` }}>
                    <td style={{ padding: "11px 6px" }}>
                      <div style={{ fontWeight: 600 }}>{u.nome}</div>
                      <div style={{ color: C.inkFaint, fontSize: 12 }}>{u.local}</div>
                    </td>
                    <td style={{ padding: "11px 6px" }}>{u.cliente}</td>
                    <td style={{ padding: "11px 6px" }} className="mono"><span style={{ color: statusColor(u.d), fontWeight: 600 }}>{pct(u.d)}</span></td>
                    <td style={{ padding: "11px 6px" }} className="mono">{minToHuman(u.down)}</td>
                    <td style={{ padding: "11px 6px" }} className="mono">{u.lat.toFixed(2)} ms</td>
                    <td style={{ padding: "11px 6px" }} className="mono">{u.loss.toFixed(3)}%</td>
                    <td style={{ padding: "11px 6px" }}>
                      <span style={{ fontSize: 11.5, fontWeight: 600, color: statusColor(u.d), background: statusColor(u.d) + "18", padding: "3px 9px", borderRadius: 20 }}>{statusLabel(u.d)}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <footer style={{ color: C.inkFaint, fontSize: 12, textAlign: "center", marginTop: 8 }} className="mono">
          K3G Solutions · NOC 24×7 · Fonte: Zabbix (45.236.8.20) · Cálculo SLA: D = (To − Ti) / To
        </footer>
        </>
        )}
      </div>

      {/* Drawer de detalhe */}
      {selUnit && <Detail unit={selUnit} onClose={() => setSel(null)} />}

      {/* Layout de impressão / relatório mensal */}
      <ReportLayout mes={periodoLabel} consolidado={consolidado} />
    </div>
  );
}

const rootEl = document.getElementById("root");
if (rootEl) {
  createRoot(rootEl).render(<App />);
}

function ZabbixConfig({ apiBase, setApiBase, live }) {
  const [backendUrl, setBackendUrl] = useState(apiBase || "");
  const [zbxUrl, setZbxUrl] = useState("http://45.236.8.20/zabbix/api_jsonrpc.php");
  const [token, setToken] = useState("");
  const [user, setUser] = useState("");
  const [password, setPassword] = useState("");
  const [verifyTls, setVerifyTls] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null); // {ok, message, ...}
  const [saved, setSaved] = useState(false);

  const body = () => ({ url: zbxUrl, token: token || undefined, user: user || undefined, password: password || undefined, verify_tls: verifyTls });

  async function testar() {
    if (!backendUrl) { setResult({ ok: false, message: "Informe o endereço do backend primeiro." }); return; }
    setBusy(true); setResult(null);
    try {
      const r = await fetch(`${backendUrl}/api/zabbix/test`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body()),
      });
      setResult(await r.json());
    } catch (e) {
      setResult({ ok: false, message: `Não foi possível falar com o backend (${backendUrl}). Verifique se o serviço está no ar e o CORS liberado.` });
    } finally { setBusy(false); }
  }

  async function salvar() {
    if (!backendUrl) { setResult({ ok: false, message: "Informe o endereço do backend primeiro." }); return; }
    setBusy(true); setSaved(false);
    try {
      const r = await fetch(`${backendUrl}/api/config`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body()),
      });
      if (!r.ok) throw new Error();
      setApiBase(backendUrl);   // o painel passa a consultar este backend
      setSaved(true);
      setResult({ ok: true, message: "Configuração salva. O Painel agora consulta este Zabbix." });
    } catch (e) {
      setResult({ ok: false, message: `Falha ao salvar no backend (${backendUrl}).` });
    } finally { setBusy(false); }
  }

  const field = { width: "100%", padding: "9px 11px", border: `1px solid ${C.line}`, borderRadius: 8, fontSize: 13.5, fontFamily: "'IBM Plex Mono', monospace", color: C.ink, background: "#fff" };
  const lbl = { fontSize: 12, fontWeight: 600, color: C.inkSoft, marginBottom: 5, display: "block" };

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 18, maxWidth: 680 }}>
      <section className="card" style={{ padding: "22px 24px" }}>
        <SectionTitle eyebrow="Cadastro" title="Conexão com o Zabbix" />
        <p style={{ color: C.inkSoft, fontSize: 13, marginTop: -8, marginBottom: 18 }}>
          Informe os dados do seu Zabbix e teste a conexão. O token é guardado no backend (nunca no navegador).
        </p>

        <div style={{ display: "grid", gap: 14 }}>
          <div>
            <label style={lbl}>Endereço do backend (API do portal)</label>
            <input style={field} value={backendUrl} onChange={(e) => setBackendUrl(e.target.value)} placeholder="http://noc.k3g.local:8080" />
          </div>
          <div>
            <label style={lbl}>URL da API do Zabbix</label>
            <input style={field} value={zbxUrl} onChange={(e) => setZbxUrl(e.target.value)} placeholder="http://SEU_ZABBIX/zabbix/api_jsonrpc.php" />
          </div>
          <div>
            <label style={lbl}>Token de API</label>
            <input style={field} value={token} onChange={(e) => setToken(e.target.value)} placeholder="cole_seu_token_aqui" />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
            <div>
              <label style={lbl}>Usuário <span style={{ fontWeight: 400, color: C.inkFaint }}>(só p/ gráficos PNG)</span></label>
              <input style={field} value={user} onChange={(e) => setUser(e.target.value)} placeholder="opcional" />
            </div>
            <div>
              <label style={lbl}>Senha</label>
              <input style={field} type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="opcional" />
            </div>
          </div>
          <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: C.inkSoft }}>
            <input type="checkbox" checked={verifyTls} onChange={(e) => setVerifyTls(e.target.checked)} /> Verificar certificado TLS (HTTPS)
          </label>
        </div>

        <div style={{ display: "flex", gap: 10, marginTop: 18 }}>
          <button className="ubtn" disabled={busy} onClick={testar}>{busy ? "Testando…" : "Testar conexão"}</button>
          <button className="ubtn" disabled={busy} style={{ background: C.teal, color: "#fff", borderColor: C.teal, fontWeight: 600 }} onClick={salvar}>Salvar configuração</button>
        </div>

        {result && (
          <div className="card" style={{ marginTop: 16, padding: "12px 16px", borderColor: result.ok ? C.ok : C.crit, background: result.ok ? "#F1FAF6" : "#FDF2F3" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, fontWeight: 600, color: result.ok ? C.ok : C.crit, fontSize: 13.5 }}>
              <span style={{ width: 8, height: 8, borderRadius: "50%", background: result.ok ? C.ok : C.crit }} />
              {result.ok ? "Conexão bem-sucedida" : "Não conectou"}
            </div>
            <div style={{ fontSize: 13, color: C.inkSoft, marginTop: 6 }}>{result.message}</div>
            {result.ok && (result.version || result.hosts_prf != null) && (
              <div className="mono" style={{ fontSize: 12.5, color: C.ink, marginTop: 8, display: "flex", gap: 18, flexWrap: "wrap" }}>
                {result.version && <span>versão <b>{result.version}</b></span>}
                {result.hosts_prf != null && <span>hosts PRF: <b>{result.hosts_prf}</b></span>}
                {result.latency_ms != null && <span>latência: <b>{result.latency_ms} ms</b></span>}
              </div>
            )}
          </div>
        )}
      </section>

      <section className="card" style={{ padding: "18px 24px", fontSize: 13, color: C.inkSoft }}>
        <div style={{ fontWeight: 600, color: C.ink, marginBottom: 6 }}>Como obter o token</div>
        No Zabbix: <b>Usuários → Tokens de API → Criar token</b>, vincule a um usuário com permissão de leitura
        nos host groups do cliente. Cole o token acima. O endereço do backend é onde você subiu a API do portal
        (FastAPI, porta 8080 por padrão) — veja o <b>README</b>.
        <div style={{ marginTop: 10, color: live ? C.ok : C.inkFaint }}>
          Status atual do painel: <b>{live ? "conectado ao backend" : "modo demonstração"}</b>
        </div>
      </section>
    </div>
  );
}

function Kpi({ label, value, sub, color, big }) {
  return (
    <div className="card" style={{ padding: "16px 18px" }}>
      <div style={{ fontSize: 11.5, color: C.inkSoft, textTransform: "uppercase", letterSpacing: 0.6, fontWeight: 600 }}>{label}</div>
      <div className="mono" style={{ fontSize: big ? 30 : 24, fontWeight: 700, color, marginTop: 6, lineHeight: 1 }}>{value}</div>
      <div style={{ fontSize: 12, color: C.inkFaint, marginTop: 6 }}>{sub}</div>
    </div>
  );
}

function SectionTitle({ eyebrow, title, noMargin }) {
  return (
    <div style={{ marginBottom: noMargin ? 0 : 16 }}>
      <div style={{ fontSize: 11, color: C.teal, textTransform: "uppercase", letterSpacing: 1.2, fontWeight: 600 }}>{eyebrow}</div>
      <h2 style={{ margin: "3px 0 0", fontSize: 18, fontWeight: 700 }}>{title}</h2>
    </div>
  );
}

function Detail({ unit, onClose }) {
  const series = dailySeries(unit);
  const up = MONTH_MIN - unit.down;
  return (
    <div className="no-print" onClick={onClose} style={{ position: "fixed", inset: 0, background: "rgba(14,36,54,.45)", zIndex: 50, display: "flex", justifyContent: "flex-end" }}>
      <div onClick={(e) => e.stopPropagation()} style={{ width: "min(520px, 100%)", background: C.surface, height: "100%", overflowY: "auto", padding: "26px 26px 50px", boxShadow: "-8px 0 30px rgba(0,0,0,.15)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
          <div>
            <span style={{ fontSize: 11.5, fontWeight: 600, color: statusColor(unit.d), background: statusColor(unit.d) + "18", padding: "3px 9px", borderRadius: 20 }}>{statusLabel(unit.d)}</span>
            <h2 style={{ margin: "10px 0 4px", fontSize: 21, fontWeight: 700 }}>{unit.nome}</h2>
            <p style={{ margin: 0, color: C.inkSoft, fontSize: 13 }}>{unit.local}</p>
            <p style={{ margin: "2px 0 0", color: C.inkFaint, fontSize: 12.5 }} className="mono">IP {unit.ip}</p>
          </div>
          <button className="ubtn" onClick={onClose}>✕</button>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, margin: "22px 0" }}>
          <MiniStat label="Disponibilidade (SLA)" value={pct(unit.d)} color={statusColor(unit.d)} />
          <MiniStat label="Latência média" value={`${unit.lat.toFixed(2)} ms`} color={C.ink} />
          <MiniStat label="Perda de pacotes" value={`${unit.loss.toFixed(4)}%`} color={unit.loss > 5 ? C.crit : C.ink} />
          <MiniStat label="Indisponibilidade" value={minToHuman(unit.down)} color={C.ink} />
        </div>

        <div style={{ fontSize: 12, color: C.inkSoft, marginBottom: 8, fontWeight: 600 }}>
          Disponibilidade diária <span style={{ fontWeight: 400, color: C.inkFaint }}>(ilustrativa — produção: Zabbix trends)</span>
        </div>
        <Sparkbars series={series} />

        <div style={{ marginTop: 24 }}>
          <div style={{ fontSize: 12, color: C.inkSoft, marginBottom: 8, fontWeight: 600 }}>Resumo dos dados apurados</div>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13.5 }}>
            <tbody>
              {[
                ["Período total (To)", `${fmtInt(MONTH_MIN)} min`],
                ["Tempo de indisponibilidade (Ti)", `${fmtInt(unit.down)} min`],
                ["Tempo de disponibilidade", `${fmtInt(up)} min`],
                ["Disponibilidade do serviço (SLA)", pct(unit.d)],
                ["Latência média", `${unit.lat.toFixed(2)} ms`],
                ["Perda de pacotes (média)", `${unit.loss.toFixed(4)}%`],
                ["Histórico de incidentes", unit.inc],
              ].map(([k, v]) => (
                <tr key={k} style={{ borderTop: `1px solid ${C.line}` }}>
                  <td style={{ padding: "9px 4px", color: C.inkSoft }}>{k}</td>
                  <td style={{ padding: "9px 4px", textAlign: "right", fontWeight: 600 }} className="mono">{v}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function MiniStat({ label, value, color }) {
  return (
    <div style={{ border: `1px solid ${C.line}`, borderRadius: 10, padding: "13px 14px" }}>
      <div style={{ fontSize: 11, color: C.inkSoft, textTransform: "uppercase", letterSpacing: 0.5, fontWeight: 600 }}>{label}</div>
      <div className="mono" style={{ fontSize: 21, fontWeight: 700, color, marginTop: 5 }}>{value}</div>
    </div>
  );
}

function Sparkbars({ series }) {
  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: 2, height: 90, padding: "8px 0", borderBottom: `1px solid ${C.line}` }}>
      {series.map((v, i) => (
        <div key={i} title={`Dia ${i + 1}: ${(v * 100).toFixed(1)}%`}
          style={{ flex: 1, height: `${Math.max(4, v * 100)}%`, background: statusColor(v), borderRadius: "2px 2px 0 0", opacity: 0.85 }} />
      ))}
    </div>
  );
}

/* ===== Layout de relatório (somente impressão) ===== */
function ReportLayout({ mes, consolidado }) {
  return (
    <div className="report-only" style={{ padding: "40px 48px", fontFamily: "'IBM Plex Sans', sans-serif", color: "#000" }}>
      <h1 style={{ fontSize: 20, marginBottom: 2 }}>RELATÓRIO DE DISPONIBILIDADE — {mes.toUpperCase()}</h1>
      <p style={{ margin: "0 0 4px", fontSize: 13 }}>PRF/AM — Superintendência da Polícia Rodoviária Federal no Amazonas</p>
      <p style={{ margin: "0 0 18px", fontSize: 12, color: "#444" }}>Contrato 07/2025 · PE 9001/2025 — Link Dedicado · Fonte: Zabbix (ICMP, 60s)</p>

      <p style={{ fontSize: 12.5, lineHeight: 1.5 }}>
        A disponibilidade foi apurada com base nas respostas de monitoramento ICMP (estado UP/DOWN) coletadas pelo Zabbix em intervalos de 60 segundos, sobre o período total de {fmtInt(MONTH_MIN)} minutos. Cálculo: <b>D = (To − Ti) / To × 100</b>. SLA médio consolidado do mês: <b>{pct(consolidado.avg)}</b>.
      </p>

      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11.5, marginTop: 14 }}>
        <thead>
          <tr style={{ background: "#f0f0f0" }}>
            {["Unidade", "Localização", "SLA", "Indisp. (min)", "Latência", "Perda"].map((h) => (
              <th key={h} style={{ border: "1px solid #ccc", padding: "6px 8px", textAlign: "left" }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {[...UNITS].sort((a, b) => a.d - b.d).map((u) => (
            <tr key={u.id}>
              <td style={{ border: "1px solid #ccc", padding: "5px 8px" }}>{u.nome}</td>
              <td style={{ border: "1px solid #ccc", padding: "5px 8px" }}>{u.local}</td>
              <td style={{ border: "1px solid #ccc", padding: "5px 8px" }}>{pct(u.d)}</td>
              <td style={{ border: "1px solid #ccc", padding: "5px 8px" }}>{fmtInt(u.down)}</td>
              <td style={{ border: "1px solid #ccc", padding: "5px 8px" }}>{u.lat.toFixed(2)} ms</td>
              <td style={{ border: "1px solid #ccc", padding: "5px 8px" }}>{u.loss.toFixed(4)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p style={{ fontSize: 10.5, color: "#666", marginTop: 16 }}>
        K3G Solutions LTDA · NOC 24×7 · Gerado automaticamente pelo Portal de Disponibilidade.
      </p>
    </div>
  );
}
