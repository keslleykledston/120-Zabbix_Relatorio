from __future__ import annotations

import base64
import calendar
from datetime import datetime, timezone
from io import BytesIO

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def build_unit_graph_series(year: int, month: int, ping_history: list[dict],
                            sec_history: list[dict], loss_history: list[dict]) -> dict:
    days = calendar.monthrange(year, month)[1]
    labels = [f"{day:02d}/{month:02d}" for day in range(1, days + 1)]
    ping_buckets = [[] for _ in range(days)]
    sec_buckets = [[] for _ in range(days)]
    loss_buckets = [[] for _ in range(days)]

    def bucket(entries: list[dict], target: list[list[float]], transform):
        for entry in entries:
            ts = int(entry["clock"])
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            if dt.year != year or dt.month != month:
                continue
            idx = dt.day - 1
            if 0 <= idx < days:
                target[idx].append(transform(float(entry["value"])))

    bucket(ping_history, ping_buckets, lambda v: v)
    bucket(sec_history, sec_buckets, lambda v: v * 1000.0)
    bucket(loss_history, loss_buckets, lambda v: v)

    comm_loss_pct = []
    latency_ms = []
    packet_loss_pct = []
    for idx in range(days):
        day_ping = ping_buckets[idx]
        day_sec = [v for v in sec_buckets[idx] if v > 0]
        day_loss = loss_buckets[idx]
        if day_ping:
            up_ratio = sum(1.0 for value in day_ping if value >= 1.0) / len(day_ping)
            comm_loss_pct.append(round((1.0 - up_ratio) * 100.0, 2))
        else:
            comm_loss_pct.append(None)
        latency_ms.append(round(sum(day_sec) / len(day_sec), 2) if day_sec else None)
        packet_loss_pct.append(round(sum(day_loss) / len(day_loss), 2) if day_loss else None)

    return {
        "labels": labels,
        "packet_loss_pct": packet_loss_pct,
        "latency_ms": latency_ms,
        "comm_loss_pct": comm_loss_pct,
    }


def render_unit_graph_png(series: dict, title: str) -> bytes | None:
    if not series:
        return None
    labels = series.get("labels") or []
    if not labels:
        return None

    x = list(range(len(labels)))
    tick_step = max(1, len(labels) // 8)
    tick_idx = list(range(0, len(labels), tick_step))
    if tick_idx[-1] != len(labels) - 1:
        tick_idx.append(len(labels) - 1)

    fig, axes = plt.subplots(3, 1, figsize=(10.8, 6.8), sharex=True, constrained_layout=True)
    fig.patch.set_facecolor("white")
    plots = [
        ("Perda de pacotes (%)", series.get("packet_loss_pct", []), "#C9384A"),
        ("Latência média (ms)", series.get("latency_ms", []), "#0E7C86"),
        ("Perda de comunicação (%)", series.get("comm_loss_pct", []), "#D98A26"),
    ]

    has_data = False
    for ax, (ylabel, values, color) in zip(axes, plots):
        cleaned = [value if value is not None else float("nan") for value in values]
        if any(value is not None for value in values):
            has_data = True
        ax.plot(x, cleaned, color=color, linewidth=1.8, marker="o", markersize=2.8)
        ax.fill_between(x, cleaned, [0] * len(cleaned), color=color, alpha=0.12)
        ax.set_ylabel(ylabel, fontsize=9)
        ax.grid(True, axis="y", color="#DCE3EA", linewidth=0.8)
        ax.set_facecolor("#FBFCFD")
        for spine in ax.spines.values():
            spine.set_color("#DCE3EA")
        ax.tick_params(axis="y", labelsize=8)

    if not has_data:
        plt.close(fig)
        return None

    axes[-1].set_xticks(tick_idx)
    axes[-1].set_xticklabels([labels[idx] for idx in tick_idx], fontsize=8)
    fig.suptitle(f"Zabbix - {title}", fontsize=12, fontweight="bold", color="#0E2436")

    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    return buffer.getvalue()


def render_unit_graph_base64(series: dict, title: str) -> str | None:
    png = render_unit_graph_png(series, title)
    if not png:
        return None
    return base64.b64encode(png).decode("ascii")
