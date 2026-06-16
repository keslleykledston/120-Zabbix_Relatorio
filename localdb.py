from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable


DB_PATH = Path(os.getenv("PORTAL_DB_PATH", "portal.db"))


@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS clients (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                host_count INTEGER NOT NULL DEFAULT 0,
                synced_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS devices (
                hostid TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                status TEXT,
                ip TEXT,
                raw_groups TEXT,
                synced_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS client_devices (
                client_id TEXT NOT NULL,
                hostid TEXT NOT NULL,
                PRIMARY KEY (client_id, hostid),
                FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
                FOREIGN KEY (hostid) REFERENCES devices(hostid) ON DELETE CASCADE
            );
            """
        )


def replace_inventory(clients: list[dict], devices: list[dict], relations: Iterable[tuple[str, str]], synced_at: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM client_devices")
        conn.execute("DELETE FROM devices")
        conn.execute("DELETE FROM clients")
        conn.executemany(
            "INSERT INTO clients (id, name, host_count, synced_at) VALUES (?, ?, ?, ?)",
            [(client["id"], client["name"], client["hosts"], synced_at) for client in clients],
        )
        conn.executemany(
            "INSERT INTO devices (hostid, name, status, ip, raw_groups, synced_at) VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    device["hostid"],
                    device["name"],
                    str(device.get("status", "")),
                    device.get("ip", ""),
                    json.dumps(device.get("hostgroups", []), ensure_ascii=False),
                    synced_at,
                )
                for device in devices
            ],
        )
        conn.executemany(
            "INSERT INTO client_devices (client_id, hostid) VALUES (?, ?)",
            list(relations),
        )


def get_clients() -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, name, host_count, synced_at
            FROM clients
            ORDER BY name
            """
        ).fetchall()
    return [
        {
            "id": row["id"],
            "name": row["name"],
            "hosts": row["host_count"],
            "synced_at": row["synced_at"],
        }
        for row in rows
    ]


def get_clients_by_ids(client_ids: list[str]) -> list[dict]:
    if not client_ids:
        return []
    placeholders = ",".join("?" for _ in client_ids)
    with connect() as conn:
        rows = conn.execute(
            f"SELECT id, name, host_count, synced_at FROM clients WHERE id IN ({placeholders})",
            client_ids,
        ).fetchall()
    index = {row["id"]: row for row in rows}
    ordered = []
    for client_id in client_ids:
        row = index.get(client_id)
        if row:
            ordered.append(
                {
                    "id": row["id"],
                    "name": row["name"],
                    "hosts": row["host_count"],
                    "synced_at": row["synced_at"],
                }
            )
    return ordered


def get_devices_for_clients(client_ids: list[str]) -> list[dict]:
    if not client_ids:
        return []
    placeholders = ",".join("?" for _ in client_ids)
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT d.hostid, d.name, d.status, d.ip, d.raw_groups, cd.client_id
            FROM devices d
            JOIN client_devices cd ON cd.hostid = d.hostid
            WHERE cd.client_id IN ({placeholders})
            ORDER BY d.name
            """,
            client_ids,
        ).fetchall()
    return [dict(row) for row in rows]
