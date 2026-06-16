"""
sla.py — Motor de cálculo de SLA a partir do histórico ICMP do Zabbix.

Reproduz exatamente a metodologia do relatório PRF/AM:
    D  = (To - Ti) / To          (disponibilidade, decimal)
    Ti = To * (1 - D)            (indisponibilidade, minutos)
onde D é inferido pela proporção de coletas ICMP com estado UP.

icmpping       -> 1 (UP) / 0 (DOWN)
icmppingsec    -> latência em segundos (x1000 = ms)
icmppingloss   -> perda de pacotes (%)
"""
from __future__ import annotations
from dataclasses import dataclass, asdict


@dataclass
class UnitSLA:
    hostid: str
    nome: str
    ip: str
    availability: float      # decimal (0..1)
    sla_pct: float           # %
    downtime_min: int
    uptime_min: int
    total_min: int
    latency_ms: float
    packet_loss_pct: float
    samples: int
    status: str              # ok | warn | crit

    def to_dict(self) -> dict:
        return asdict(self)


def classify(d: float, t_ok: float = 0.99, t_warn: float = 0.90) -> str:
    if d >= t_ok:
        return "ok"
    if d >= t_warn:
        return "warn"
    return "crit"


def compute_sla(ping_history: list[dict],
                sec_history: list[dict],
                loss_history: list[dict],
                total_min: int,
                hostid: str,
                nome: str,
                ip: str) -> UnitSLA:
    """
    Recebe as listas de history.get (cada item: {clock, value}) e devolve o SLA.
    A disponibilidade = média das amostras icmpping (proporção de estados UP).
    """
    ping_vals = [float(h["value"]) for h in ping_history]
    samples = len(ping_vals)

    if samples == 0:
        availability = 0.0
    else:
        availability = sum(1.0 for v in ping_vals if v >= 1.0) / samples

    downtime_min = round(total_min * (1.0 - availability))
    uptime_min = total_min - downtime_min

    # latência: icmppingsec vem em segundos -> ms
    sec_vals = [float(h["value"]) for h in sec_history if float(h["value"]) > 0]
    latency_ms = round((sum(sec_vals) / len(sec_vals)) * 1000, 2) if sec_vals else 0.0

    loss_vals = [float(h["value"]) for h in loss_history]
    packet_loss = round(sum(loss_vals) / len(loss_vals), 4) if loss_vals else 0.0

    return UnitSLA(
        hostid=hostid,
        nome=nome,
        ip=ip,
        availability=round(availability, 4),
        sla_pct=round(availability * 100, 2),
        downtime_min=downtime_min,
        uptime_min=uptime_min,
        total_min=total_min,
        latency_ms=latency_ms,
        packet_loss_pct=packet_loss,
        samples=samples,
        status=classify(availability),
    )


def consolidate(units: list[UnitSLA]) -> dict:
    if not units:
        return {"sla_medio": 0, "indisp_total_min": 0, "ok": 0, "warn": 0, "crit": 0}
    avg = sum(u.availability for u in units) / len(units)
    return {
        "sla_medio_pct": round(avg * 100, 2),
        "indisp_total_min": sum(u.downtime_min for u in units),
        "ok": sum(1 for u in units if u.status == "ok"),
        "warn": sum(1 for u in units if u.status == "warn"),
        "crit": sum(1 for u in units if u.status == "crit"),
        "unidades": len(units),
    }
