"""
zabbix_client.py — Cliente JSON-RPC do Zabbix para o Portal de Disponibilidade.
Compatível com Zabbix 6.x/7.x. Usa o item icmpping (UP/DOWN), icmppingsec (latência)
e icmppingloss (perda) já presentes nos hosts PRF.
"""
from __future__ import annotations
import time
from dataclasses import dataclass
from datetime import datetime, timezone
import httpx


@dataclass
class ZabbixConfig:
    url: str          # ex: http://45.236.8.20/zabbix/api_jsonrpc.php
    token: str = ""   # API token (Zabbix 5.4+); preferível a user/senha
    user: str = ""
    password: str = ""
    verify_tls: bool = False
    timeout: float = 30.0


class ZabbixClient:
    def __init__(self, cfg: ZabbixConfig):
        self.cfg = cfg
        self._auth = cfg.token or None
        self._client = httpx.Client(timeout=cfg.timeout, verify=cfg.verify_tls)
        self._id = 0

    def _call(self, method: str, params: dict, auth: bool = True) -> dict:
        self._id += 1
        payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": self._id}
        headers = {"Content-Type": "application/json-rpc"}
        # Zabbix 6.4+ aceita Bearer; 6.0.x costuma exigir token no campo "auth".
        attempts = []
        if auth and self._auth:
            attempts.append(("bearer", payload, {**headers, "Authorization": f"Bearer {self._auth}"}))
            attempts.append(("auth_field", {**payload, "auth": self._auth}, headers))
        else:
            attempts.append(("plain", payload, headers))

        last_error = None
        for mode, body, req_headers in attempts:
            r = self._client.post(self.cfg.url, json=body, headers=req_headers)
            r.raise_for_status()
            data = r.json()
            if "error" not in data:
                return data["result"]
            last_error = data["error"]
            unauthorized = str(last_error.get("data", "")).lower().find("not authorized") >= 0
            if mode == "bearer" and unauthorized:
                continue
            raise RuntimeError(f"Zabbix {method}: {last_error}")

        raise RuntimeError(f"Zabbix {method}: {last_error}")

    def login(self) -> None:
        """Autentica via user/senha se nenhum token foi fornecido."""
        if self._auth:
            return
        self._auth = self._call(
            "user.login",
            {"username": self.cfg.user, "password": self.cfg.password},
            auth=False,
        )

    def apiinfo_version(self) -> str:
        """Versão da API — não exige autenticação. Usado no teste de conexão."""
        return self._call("apiinfo.version", {}, auth=False)

    # ---- Descoberta de hosts/itens ----
    def hosts_by_name(self, search: str = "PRF") -> list[dict]:
        return self._call("host.get", {
            "output": ["hostid", "host", "name", "status"],
            "search": {"name": search},
            "selectInterfaces": ["ip"],
            "selectHostGroups": ["groupid", "name"],
            "sortfield": "name",
        })

    def client_groups(self) -> list[dict]:
        groups = self._call("hostgroup.get", {
            "output": ["groupid", "name"],
            "sortfield": "name",
        })
        generic_prefixes = (
            "Templates",
            "Discovered hosts",
            "Linux servers",
            "Virtual machines",
            "Zabbix servers",
            "Hypervisors",
            "CORE",
            "LINK",
            "DmOS",
            "DM - Templates",
        )
        out = []
        for group in groups:
            if group["name"].startswith(generic_prefixes):
                continue
            hosts = self._call("host.get", {
                "output": ["hostid"],
                "groupids": [group["groupid"]],
                "monitored_hosts": True,
                "limit": 500,
            })
            if not hosts:
                continue
            out.append({
                "id": group["groupid"],
                "name": group["name"],
                "hosts": len(hosts),
            })
        return out

    def hosts_by_group_ids(self, group_ids: list[str]) -> list[dict]:
        return self._call("host.get", {
            "output": ["hostid", "host", "name", "status"],
            "groupids": group_ids,
            "selectInterfaces": ["ip"],
            "selectHostGroups": ["groupid", "name"],
            "sortfield": "name",
        })

    def icmp_items(self, hostid: str) -> dict:
        """Retorna {ping, loss, sec} itemids para um host."""
        items = self._call("item.get", {
            "output": ["itemid", "key_", "name"],
            "hostids": hostid,
            "search": {"key_": "icmpping"},
            "searchByAny": True,
        })
        out = {"ping": None, "loss": None, "sec": None}
        for it in items:
            k = it["key_"]
            if k.startswith("icmppingloss"):
                out["loss"] = it["itemid"]
            elif k.startswith("icmppingsec"):
                out["sec"] = it["itemid"]
            elif k.startswith("icmpping"):
                out["ping"] = it["itemid"]
        return out

    # ---- Histórico / trends ----
    def history(self, itemid: str, time_from: int, time_till: int, value_type: int = 3) -> list[dict]:
        """history.get — value_type: 0=float, 3=unsigned int (icmpping é uint)."""
        return self._call("history.get", {
            "output": "extend",
            "itemids": itemid,
            "time_from": time_from,
            "time_till": time_till,
            "history": value_type,
            "sortfield": "clock",
            "sortorder": "ASC",
        })

    def trends(self, itemid: str, time_from: int, time_till: int) -> list[dict]:
        """trends.get — agregados horários (recomendado p/ mês inteiro)."""
        return self._call("trend.get", {
            "output": "extend",
            "itemids": itemid,
            "time_from": time_from,
            "time_till": time_till,
        })

    # ---- Incidentes (o "Histórico de alertas" do relatório) ----
    def events(self, hostid: str, time_from: int, time_till: int) -> list[dict]:
        """
        event.get — problemas do host no período. É a fonte da seção
        'Histórico de alertas de Incidentes' do relatório (substitui o
        screenshot da lista de Problemas do Zabbix por dados estruturados).
        """
        evs = self._call("event.get", {
            "output": ["eventid", "clock", "name", "severity", "r_eventid"],
            "hostids": hostid,
            "source": 0, "object": 0,
            "value": 1,                       # PROBLEM
            "time_from": time_from,
            "time_till": time_till,
            "sortfield": ["clock"],
            "sortorder": "DESC",
        })
        # eventos de recuperação p/ calcular duração
        r_ids = [e["r_eventid"] for e in evs if e.get("r_eventid") and e["r_eventid"] != "0"]
        recovery = {}
        if r_ids:
            for r in self._call("event.get", {"output": ["eventid", "clock"], "eventids": r_ids}):
                recovery[r["eventid"]] = int(r["clock"])
        out = []
        for e in evs:
            start = int(e["clock"])
            end = recovery.get(e.get("r_eventid"))
            dur = (end - start) if end else None
            out.append({
                "inicio": _epoch_fmt(start),
                "fim": _epoch_fmt(end) if end else "Em aberto",
                "problema": e["name"],
                "duracao": _dur_fmt(dur) if dur is not None else "—",
            })
        return out

    def graph_image(self, graphid: str, time_from: int, time_till: int,
                    width: int = 900, height: int = 200) -> bytes:
        """
        Exporta a IMAGEM PNG de um gráfico do Zabbix (chart2.php).
        Atenção: o render de PNG exige SESSÃO de cookie (login web) — o API token
        sozinho devolve JSON, não imagem. Por isso fazemos login web (cookie zbx_session).
        Em geral é mais limpo reconstruir os gráficos a partir de trends().
        """
        if not (self.cfg.user and self.cfg.password):
            raise RuntimeError("graph_image requer user/senha (sessão web), não apenas token.")
        base = self.cfg.url.replace("/api_jsonrpc.php", "")
        self._client.post(f"{base}/index.php", data={
            "name": self.cfg.user, "password": self.cfg.password,
            "autologin": "1", "enter": "Sign in",
        })
        r = self._client.get(f"{base}/chart2.php", params={
            "graphid": graphid, "from": f"@{time_from}", "to": f"@{time_till}",
            "width": width, "height": height,
        })
        r.raise_for_status()
        return r.content


def month_bounds(year: int, month: int) -> tuple[int, int, int]:
    """Retorna (epoch_inicio, epoch_fim, total_minutos) do mês em UTC."""
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    total_min = int((end - start).total_seconds() // 60)
    return int(start.timestamp()), int(end.timestamp()) - 1, total_min


def _epoch_fmt(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%d-%m %H:%M")


def _dur_fmt(seconds: int) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)
    if d:
        return f"{d}d {h}h {m}min"
    if h:
        return f"{h}h {m}min"
    return f"{m}min" if m else f"{s}s"
