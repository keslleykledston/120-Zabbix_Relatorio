"""
main.py — API do Portal de Disponibilidade (FastAPI).

Painel / relatórios:
    GET  /api/units?year=2026&month=3&search=PRF
    GET  /api/report/monthly?year=2026&month=3&search=PRF       -> JSON
    GET  /api/report/monthly.pdf?year=2026&month=3&search=PRF   -> PDF no modelo

Cadastro / conexão Zabbix (aba Configurações):
    GET  /api/config            -> config atual (token mascarado)
    POST /api/config            -> salva URL/token/user/senha
    POST /api/zabbix/test       -> testa conexão (apiinfo.version + host.get)

    GET  /healthz
"""
from __future__ import annotations
import os
import time
import tempfile
from datetime import datetime, timezone
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from zabbix_client import ZabbixClient, ZabbixConfig, month_bounds
from sla import compute_sla, consolidate, UnitSLA
from report_generator import build_pdf
from docx_generator import build_docx
from charts import build_unit_graph_series
import config as cfgstore
import localdb

app = FastAPI(title="Portal Disponibilidade — K3G", version="0.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory="static"), name="static")

_client: ZabbixClient | None = None


@app.on_event("startup")
def startup():
    localdb.init_db()


@app.get("/")
def index():
    return FileResponse("index.html")


def get_client() -> ZabbixClient:
    """Cliente Zabbix a partir da config salva (ou .env). Cacheado até troca de config."""
    global _client
    if _client is None:
        c = cfgstore.load_config()
        zc = ZabbixClient(ZabbixConfig(
            url=c["url"], token=c["token"], user=c["user"],
            password=c["password"], verify_tls=c["verify_tls"],
        ))
        zc.login()
        _client = zc
    return _client


def reset_client():
    global _client
    _client = None


def _parse_client_ids(client_ids: str | None) -> list[str]:
    if not client_ids:
        return []
    return [part.strip() for part in client_ids.split(",") if part.strip()]


# ---------------- Cadastro / teste ----------------
class ZbxConfigIn(BaseModel):
    url: str | None = None
    token: str | None = None
    user: str | None = None
    password: str | None = None
    verify_tls: bool | None = None


@app.get("/api/config")
def get_config():
    return cfgstore.load_public()


def _sync_clients_inventory() -> dict:
    client = get_client()
    synced_at = datetime.now(timezone.utc).isoformat()
    clients = client.client_groups()
    devices_by_hostid = {}
    relations = []
    for group in clients:
        hosts = client.hosts_by_group_ids([group["id"]])
        for host in hosts:
            hostid = host["hostid"]
            devices_by_hostid[hostid] = host
            relations.append((group["id"], hostid))
    localdb.replace_inventory(clients, list(devices_by_hostid.values()), relations, synced_at)
    return {
        "clients": localdb.get_clients(),
        "devices": len(devices_by_hostid),
        "synced_at": synced_at,
    }


@app.get("/api/clients")
def get_clients(refresh: bool = False):
    clients = localdb.get_clients()
    if refresh or not clients:
        return _sync_clients_inventory()
    return {"clients": clients, "cached": True}


@app.post("/api/clients/sync")
def sync_clients():
    return _sync_clients_inventory()


@app.post("/api/config")
def post_config(body: ZbxConfigIn):
    saved = cfgstore.save_config(body.model_dump(exclude_none=True))
    reset_client()
    return {"ok": True, "config": cfgstore.load_public()}


@app.post("/api/zabbix/test")
def test_connection(body: ZbxConfigIn):
    """Testa as credenciais informadas SEM salvá-las."""
    c = cfgstore.load_config()
    url = body.url or c["url"]
    token = body.token or c["token"]
    user = body.user if body.user is not None else c["user"]
    password = body.password if body.password else c["password"]
    verify = body.verify_tls if body.verify_tls is not None else c["verify_tls"]

    zc = ZabbixClient(ZabbixConfig(url=url, token=token, user=user,
                                   password=password, verify_tls=verify))
    t0 = time.time()
    try:
        version = zc.apiinfo_version()           # não exige auth
        zc.login()                               # valida user/senha (se for o caso)
        hosts = zc.hosts_by_name("CLIENTE")      # valida token + conta hosts
        ms = round((time.time() - t0) * 1000)
        return {
            "ok": True,
            "version": version,
            "hosts_prf": len(hosts),
            "latency_ms": ms,
            "message": f"Conectado ao Zabbix {version} — {len(hosts)} host(s) encontrados.",
        }
    except Exception as e:
        return {"ok": False, "message": f"Falha na conexão: {e}"}


# ---------------- Relatórios ----------------
def _build_report(year: int, month: int, search: str | None = None,
                  client_ids: list[str] | None = None,
                  group_mode: str = "unified",
                  with_incidents: bool = True) -> dict:
    c = get_client()
    t_from, t_till, total_min = month_bounds(year, month)
    client_ids = client_ids or []
    selected_clients = localdb.get_clients_by_ids(client_ids) if client_ids else []
    if client_ids and len(selected_clients) != len(client_ids):
        _sync_clients_inventory()
        selected_clients = localdb.get_clients_by_ids(client_ids)
    hosts = c.hosts_by_group_ids(client_ids) if client_ids else c.hosts_by_name(search or "PRF")
    dedup_hosts = {}
    for host in hosts:
        dedup_hosts[host["hostid"]] = host
    units = []
    for h in dedup_hosts.values():
        items = c.icmp_items(h["hostid"])
        if not items["ping"]:
            continue
        ping = c.history(items["ping"], t_from, t_till, value_type=3)
        sec = c.history(items["sec"], t_from, t_till, value_type=0) if items["sec"] else []
        loss = c.history(items["loss"], t_from, t_till, value_type=0) if items["loss"] else []
        ip = h.get("interfaces", [{}])[0].get("ip", "")
        u = compute_sla(ping, sec, loss, total_min, h["hostid"], h["name"], ip).to_dict()
        u["local"] = h["name"]
        u["graphs"] = build_unit_graph_series(year, month, ping, sec, loss)
        matched_groups = [g for g in h.get("hostgroups", []) if not client_ids or g["groupid"] in client_ids]
        ordered_matches = sorted(
            matched_groups,
            key=lambda g: client_ids.index(g["groupid"]) if g["groupid"] in client_ids else 9999,
        )
        u["cliente"] = ordered_matches[0]["name"] if ordered_matches else (search or "Geral")
        u["clientes"] = [g["name"] for g in ordered_matches]
        if with_incidents:
            u["incidentes"] = c.events(h["hostid"], t_from, t_till)
        units.append(u)
    units.sort(key=lambda x: x["availability"])
    objs = [UnitSLA(**{k: u[k] for k in UnitSLA.__annotations__}) for u in units]
    report = {
        "periodo": {"ano": year, "mes": month, "total_min": total_min},
        "consolidado": consolidate(objs),
        "unidades": units,
        "metodologia": "D = (To - Ti)/To · ICMP UP/DOWN · amostragem 60s",
        "agrupamento": group_mode,
        "clientes_selecionados": selected_clients,
    }
    if client_ids and group_mode == "grouped":
        groups = []
        for client in selected_clients:
            client_units = [u for u in units if u.get("cliente") == client["name"]]
            client_objs = [UnitSLA(**{k: u[k] for k in UnitSLA.__annotations__}) for u in client_units]
            groups.append({
                "cliente": client,
                "consolidado": consolidate(client_objs) if client_units else {
                    "sla_medio_pct": 0,
                    "indisp_total_min": 0,
                    "ok": 0,
                    "warn": 0,
                    "crit": 0,
                    "unidades": 0,
                },
                "unidades": client_units,
            })
        report["grupos"] = groups
    return report


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/api/units")
def units(year: int = Query(...), month: int = Query(..., ge=1, le=12),
          search: str | None = None,
          client_ids: str | None = Query(None),
          group_mode: str = Query("unified", pattern="^(unified|grouped)$")):
    return {"units": _build_report(year, month, search, _parse_client_ids(client_ids), group_mode, with_incidents=False)["unidades"]}


@app.get("/api/report/monthly")
def monthly(year: int = Query(...), month: int = Query(..., ge=1, le=12),
            search: str | None = None,
            client_ids: str | None = Query(None),
            group_mode: str = Query("unified", pattern="^(unified|grouped)$")):
    return _build_report(year, month, search, _parse_client_ids(client_ids), group_mode)


@app.get("/api/report/monthly.pdf")
def monthly_pdf(year: int = Query(...), month: int = Query(..., ge=1, le=12),
                search: str | None = None,
                client_ids: str | None = Query(None),
                group_mode: str = Query("unified", pattern="^(unified|grouped)$")):
    parsed_client_ids = _parse_client_ids(client_ids)
    report = _build_report(year, month, search, parsed_client_ids, group_mode)
    report_name = search or ("clientes" if parsed_client_ids else "geral")
    out = os.path.join(tempfile.gettempdir(), f"relatorio_{report_name}_{year}-{month:02d}.pdf")
    build_pdf(report, out)
    return FileResponse(out, media_type="application/pdf",
                        filename=f"Relatorio_Disponibilidade_{report_name}_{year}-{month:02d}.pdf")


@app.get("/api/report/monthly.docx")
def monthly_docx(year: int = Query(...), month: int = Query(..., ge=1, le=12),
                 search: str | None = None,
                 client_ids: str | None = Query(None),
                 group_mode: str = Query("unified", pattern="^(unified|grouped)$")):
    parsed_client_ids = _parse_client_ids(client_ids)
    report = _build_report(year, month, search, parsed_client_ids, group_mode)
    report_name = search or ("clientes" if parsed_client_ids else "geral")
    out = os.path.join(tempfile.gettempdir(), f"relatorio_{report_name}_{year}-{month:02d}.docx")
    build_docx(report, out)
    return FileResponse(out, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        filename=f"Relatorio_Disponibilidade_{report_name}_{year}-{month:02d}.docx")
