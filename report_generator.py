"""
report_generator.py — Gera o relatório mensal de disponibilidade em PDF,
reproduzindo o modelo do documento original (PRF/AM):

  Capa  ->  Metodologia  ->  Tabela consolidada  ->  Seção por unidade
            (médias + Histórico de Incidentes + Resultados + Resumo apurado)

Os "gráficos" do modelo original são a lista de Problemas do Zabbix por unidade;
aqui são reconstruídos via API (event.get) — ver zabbix_client.problems().

Uso:
    from report_generator import build_pdf
    build_pdf(report_dict, "/caminho/relatorio.pdf")

Onde report_dict tem o formato devolvido por main.py:/api/report/monthly,
acrescido de "incidentes" por unidade (lista de {inicio, fim, duracao, problema}).
"""
from __future__ import annotations
from datetime import datetime
from weasyprint import HTML
from charts import render_unit_graph_base64

MESES_PT = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
            "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]


def _fmt(n):
    return f"{int(n):,}".replace(",", ".")


def _pct(x):
    return f"{x:.2f}".replace(".", ",") + "%"


def _status_color(sla_pct):
    if sla_pct >= 99:
        return "#128A5E"
    if sla_pct >= 90:
        return "#D98A26"
    return "#C9384A"


def _incident_rows(incidentes):
    if not incidentes:
        return '<tr><td colspan="4" class="empty">Sem registro de incidentes no período.</td></tr>'
    rows = []
    for it in incidentes:
        rows.append(
            f"<tr><td>{it.get('inicio','')}</td><td>{it.get('fim','')}</td>"
            f"<td>{it.get('problema','')}</td><td class='r'>{it.get('duracao','')}</td></tr>"
        )
    return "".join(rows)


def _unit_section(u):
    sla = u["sla_pct"]
    color = _status_color(sla)
    graph_b64 = render_unit_graph_base64(u.get("graphs"), u["nome"])
    graph_html = (
        f"""
      <h3>Gráficos do Zabbix</h3>
      <div class="graphbox">
        <img src="data:image/png;base64,{graph_b64}" alt="Gráficos Zabbix {u['nome']}">
      </div>
        """
        if graph_b64 else ""
    )
    return f"""
    <section class="unit">
      <h2>{u['nome']}</h2>
      <p class="addr">{u.get('local','')} &nbsp;·&nbsp; <span class="mono">{u.get('ip','')}</span></p>

      <div class="means">
        <div><span>Disponibilidade</span><b style="color:{color}">{_pct(sla)}</b></div>
        <div><span>Latência média</span><b>{u['latency_ms']:.2f} ms</b></div>
        <div><span>Perda de pacotes</span><b>{u['packet_loss_pct']:.4f}%</b></div>
      </div>

      {graph_html}

      <h3>Histórico de alertas de Incidentes</h3>
      <table class="inc">
        <thead><tr><th>Início</th><th>Resolvido</th><th>Problema</th><th class="r">Duração</th></tr></thead>
        <tbody>{_incident_rows(u.get('incidentes'))}</tbody>
      </table>

      <h3>Resultados</h3>
      <ul class="res">
        <li>Média observada: <b>{u['availability']:.4f}</b></li>
        <li>Tempo do mês (To): <b>{_fmt(u['total_min'])} min</b></li>
        <li>Tempo estimado de indisponibilidade (Ti): <b>{_fmt(u['downtime_min'])} min</b></li>
        <li>Tempo de disponibilidade: <b>{_fmt(u['uptime_min'])} min</b></li>
        <li>Disponibilidade SLA: <b style="color:{color}">&#8776; {_pct(sla)}</b></li>
      </ul>

      <h3>Resumo dos dados apurados</h3>
      <table class="sum">
        <tr><th>Indicador</th><th class="r">Valor</th></tr>
        <tr><td>Tempo de indisponibilidade</td><td class="r">{_fmt(u['downtime_min'])} minutos</td></tr>
        <tr><td>Tempo de disponibilidade</td><td class="r">{_fmt(u['uptime_min'])} minutos</td></tr>
        <tr><td>Disponibilidade do serviço (SLA)</td><td class="r">{_pct(sla)}</td></tr>
        <tr><td>Latência média</td><td class="r">{u['latency_ms']:.2f} ms</td></tr>
        <tr><td>Perda de pacotes (média)</td><td class="r">{u['packet_loss_pct']:.4f}%</td></tr>
      </table>
    </section>
    """


def _consolidated_table(units):
    rows = []
    for u in sorted(units, key=lambda x: x["sla_pct"]):
        rows.append(
            f"<tr><td>{u['nome']}</td><td class='r' style='color:{_status_color(u['sla_pct'])};font-weight:600'>"
            f"{_pct(u['sla_pct'])}</td><td class='r'>{_fmt(u['downtime_min'])}</td>"
            f"<td class='r'>{u['latency_ms']:.2f} ms</td><td class='r'>{u['packet_loss_pct']:.4f}%</td></tr>"
        )
    return "".join(rows)


def _client_group_block(group):
    client = group["cliente"]
    cons = group["consolidado"]
    units = group["unidades"]
    if not units:
        return f"""
        <section class="client-group">
          <h2>Cliente: {client['name']}</h2>
          <p class="sub">Nenhuma unidade com itens ICMP válidos no período.</p>
        </section>
        """
    return f"""
    <section class="client-group">
      <h2>Cliente: {client['name']}</h2>
      <div class="kpi mini">
        <div><span>SLA médio</span><b style="color:{_status_color(cons['sla_medio_pct'])}">{_pct(cons['sla_medio_pct'])}</b></div>
        <div><span>Indisponibilidade</span><b>{_fmt(cons['indisp_total_min'])} min</b></div>
        <div><span>Unidades</span><b>{cons['unidades']}</b></div>
        <div><span>Crítico</span><b style="color:#C9384A">{cons['crit']}</b></div>
      </div>
      <table>
        <thead><tr><th>Unidade</th><th class="r">SLA</th><th class="r">Indisp. (min)</th><th class="r">Latência</th><th class="r">Perda</th></tr></thead>
        <tbody>{_consolidated_table(units)}</tbody>
      </table>
    </section>
    """


def build_html(report: dict) -> str:
    p = report["periodo"]
    cons = report["consolidado"]
    units = report["unidades"]
    groups = report.get("grupos", [])
    mes_nome = MESES_PT[p["mes"]]
    total = p["total_min"]
    selected_clients = report.get("clientes_selecionados", [])
    selected_names = ", ".join(client["name"] for client in selected_clients) if selected_clients else "Filtro geral"
    grouped_html = "".join(_client_group_block(group) for group in groups)
    detail_units = []
    if groups:
        for group in groups:
            detail_units.extend(group["unidades"])
    else:
        detail_units = units

    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<style>
  @page {{ size: A4; margin: 22mm 18mm 18mm; @bottom-center {{
    content: "K3G Solutions LTDA · NOC 24×7 · Página " counter(page) " de " counter(pages);
    font-size: 8pt; color: #8A99A8; }} }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: 'Helvetica Neue', Arial, sans-serif; color: #0E2436; font-size: 10.5pt; line-height: 1.5; }}
  .mono {{ font-family: 'Courier New', monospace; }}
  .r {{ text-align: right; }}
  .cover {{ page-break-after: always; }}
  .brand {{ display:inline-block; background:#0E2436; color:#fff; font-weight:700; padding:4px 9px; border-radius:6px; font-size:11pt; letter-spacing:1px; }}
  .eyebrow {{ font-size:9pt; letter-spacing:2px; text-transform:uppercase; color:#0E7C86; font-weight:600; margin-top:20px; }}
  h1 {{ font-size:20pt; margin:6px 0 2px; }}
  .sub {{ color:#5A6B7B; font-size:10pt; }}
  .meth {{ background:#F2F6F8; border:1px solid #DCE3EA; border-radius:8px; padding:12px 18px; margin-top:16px; }}
  .meth h3 {{ margin:0 0 6px; font-size:11pt; }}
  .kpi {{ display:flex; gap:14px; margin-top:16px; }}
  .kpi div {{ flex:1; border:1px solid #DCE3EA; border-radius:8px; padding:12px 14px; }}
  .kpi span {{ font-size:8.5pt; text-transform:uppercase; letter-spacing:.5px; color:#5A6B7B; }}
  .kpi b {{ display:block; font-size:18pt; margin-top:4px; }}
  table {{ width:100%; border-collapse:collapse; margin:6px 0 4px; font-size:9.5pt; }}
  th, td {{ border:1px solid #DCE3EA; padding:5px 8px; text-align:left; }}
  th {{ background:#F2F6F8; font-size:8.5pt; text-transform:uppercase; letter-spacing:.4px; }}
  .unit {{ page-break-inside: avoid; margin-top:18px; padding-top:14px; border-top:2px solid #0E2436; }}
  .unit h2 {{ font-size:14pt; margin:0; }}
  .addr {{ color:#5A6B7B; font-size:9pt; margin:2px 0 10px; }}
  .means {{ display:flex; gap:12px; margin-bottom:8px; }}
  .means div {{ flex:1; background:#F7FAFB; border:1px solid #DCE3EA; border-radius:6px; padding:8px 10px; }}
  .means span {{ font-size:8pt; text-transform:uppercase; color:#5A6B7B; letter-spacing:.4px; }}
  .means b {{ display:block; font-size:13pt; margin-top:2px; }}
  .graphbox {{ border:1px solid #DCE3EA; border-radius:8px; background:#FBFCFD; padding:8px; margin:8px 0 10px; }}
  .graphbox img {{ width:100%; display:block; }}
  h3 {{ font-size:10pt; margin:12px 0 4px; color:#0E2436; }}
  .client-group {{ page-break-inside: avoid; margin-top:16px; }}
  .client-group h2 {{ font-size:13pt; margin:0 0 8px; }}
  .kpi.mini b {{ font-size:14pt; }}
  ul.res {{ margin:2px 0 4px; padding-left:18px; }}
  ul.res li {{ margin:1px 0; }}
  .inc td, .inc th {{ font-size:8.5pt; padding:3px 7px; }}
  .empty {{ color:#8A99A8; font-style:italic; text-align:center; }}
  .sum td:first-child {{ width:60%; }}
</style></head><body>

  <div class="cover">
  <span class="brand">K3G</span>
  <div class="eyebrow">Relatório de Disponibilidade</div>
  <h1>Clientes Selecionados — {mes_nome} de {p['ano']}</h1>
  <p class="sub">Relatório multi-cliente de disponibilidade e SLA<br>
  Fonte: monitoramento ICMP do Zabbix</p>
  <p class="sub"><b>Clientes selecionados:</b> {selected_names}<br>
  <b>Modo do relatório:</b> {"Agrupado por cliente" if groups else "Unificado"}</p>

  <div class="kpi">
    <div><span>SLA médio consolidado</span><b style="color:{_status_color(cons['sla_medio_pct'])}">{_pct(cons['sla_medio_pct'])}</b></div>
    <div><span>Indisponibilidade total</span><b>{_fmt(cons['indisp_total_min'])} min</b></div>
    <div><span>Dentro do SLA</span><b style="color:#128A5E">{cons['ok']}/{cons['unidades']}</b></div>
    <div><span>Crítico</span><b style="color:#C9384A">{cons['crit']}</b></div>
  </div>

  <div class="meth">
    <h3>Metodologia</h3>
    <p style="margin:0">A disponibilidade foi apurada com base na média das respostas de monitoramento
    ICMP (estado UP/DOWN) coletadas pelo Zabbix em intervalos regulares de 60 segundos, ao longo de
    {_fmt(total)} minutos ({total // 1440} dias). O cálculo segue:</p>
    <p class="mono" style="margin:8px 0 0; font-size:11pt"><b>D = (To &minus; Ti) / To &times; 100</b>
    &nbsp;&nbsp; Ti = To &times; (1 &minus; D)</p>
    <p style="margin:6px 0 0; font-size:9pt; color:#5A6B7B">To: período total de operação (min) ·
    Ti: somatório das interrupções e intervalos com taxa de erro elevada · D: disponibilidade (decimal).</p>
  </div>

  <h3 style="margin-top:16px">Quadro consolidado das unidades</h3>
  <table>
    <thead><tr><th>Unidade</th><th class="r">SLA</th><th class="r">Indisp. (min)</th><th class="r">Latência</th><th class="r">Perda</th></tr></thead>
    <tbody>{_consolidated_table(units)}</tbody>
  </table>
  {grouped_html}
  <p class="sub" style="margin-top:8px; font-size:8.5pt">Emitido em {datetime.now().strftime('%d/%m/%Y %H:%M')} ·
  Fonte: Zabbix · Gerado automaticamente pelo Portal de Disponibilidade K3G.</p>
</div>

{''.join(_unit_section(u) for u in detail_units)}

</body></html>"""


def build_pdf(report: dict, out_path: str) -> str:
    html = build_html(report)
    HTML(string=html).write_pdf(out_path)
    return out_path


# ----- dados fictícios de exemplo (Março/2026) p/ demonstração offline -----
def sample_report() -> dict:
    base = [
        ("Unidade Alfa", "Av. Exemplo, 100 — Cidade Exemplo/UF", "192.0.2.10", 0.9982, 4.02, 0.02, 80, "Sem registro"),
        ("Unidade Beta", "Rua Modelo, 245 — Cidade Exemplo/UF", "192.0.2.11", 0.9941, 3.99, 0.08, 263, None),
        ("Unidade Gama", "Setor Central, 55 — Cidade Exemplo/UF", "192.0.2.12", 0.9907, 4.31, 0.15, 415, None),
        ("Unidade Delta", "Rod. Exemplo, km 12 — Cidade Exemplo/UF", "192.0.2.13", 0.9786, 4.83, 1.12, 955, None),
        ("Unidade Épsilon", "Rod. Exemplo, km 48 — Cidade Exemplo/UF", "192.0.2.14", 0.9234, 5.25, 3.48, 3419, None),
        ("Unidade Zeta", "Polo Remoto, km 96 — Cidade Exemplo/UF", "192.0.2.15", 0.9001, 5.81, 5.77, 4459, None),
    ]
    total = 44640
    units = []
    # incidentes fictícios só p/ ilustrar o layout (produção: event.get)
    demo_inc = {
        "Unidade Zeta": [
            {"inicio": "27-03 13:36", "fim": "27-03 13:37", "problema": "Sem resposta de ICMP", "duracao": "1min"},
            {"inicio": "06-03 08:12", "fim": "09-03 10:56", "problema": "Perda de comunicação intermitente", "duracao": "3d 2h 44min"},
        ],
    }
    for nome, local, ip, d, lat, loss, down, inc in base:
        units.append({
            "nome": nome, "local": local, "ip": ip,
            "availability": d, "sla_pct": round(d * 100, 2),
            "downtime_min": down, "uptime_min": total - down, "total_min": total,
            "latency_ms": lat, "packet_loss_pct": loss,
            "status": "ok" if d >= 0.99 else "warn" if d >= 0.90 else "crit",
            "incidentes": demo_inc.get(nome),
        })
    avg = sum(u["availability"] for u in units) / len(units)
    cons = {
        "sla_medio_pct": round(avg * 100, 2),
        "indisp_total_min": sum(u["downtime_min"] for u in units),
        "ok": sum(1 for u in units if u["status"] == "ok"),
        "warn": sum(1 for u in units if u["status"] == "warn"),
        "crit": sum(1 for u in units if u["status"] == "crit"),
        "unidades": len(units),
    }
    return {"periodo": {"ano": 2026, "mes": 3, "total_min": total},
            "consolidado": cons, "unidades": units,
            "metodologia": "D = (To - Ti)/To · ICMP UP/DOWN · 60s"}


if __name__ == "__main__":
    build_pdf(sample_report(), "Relatorio_Disponibilidade_PRF-AM_Marco-2026.pdf")
    print("PDF gerado.")
