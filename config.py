"""
config.py — Armazena a configuração de conexão com o Zabbix.

A aba "Configurações" do portal grava aqui (via POST /api/config). Se não houver
config.json, cai para as variáveis de ambiente (.env). O token nunca é devolvido
em texto puro para o front (mascarado em load_public).
"""
from __future__ import annotations
import json
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

CONFIG_PATH = Path(os.getenv("CONFIG_PATH", "config.json"))

_DEFAULT = {
    "url": os.getenv("ZBX_URL", "http://45.236.8.20/zabbix/api_jsonrpc.php"),
    "token": os.getenv("ZBX_TOKEN", ""),
    "user": os.getenv("ZBX_USER", ""),
    "password": os.getenv("ZBX_PASSWORD", ""),
    "verify_tls": os.getenv("ZBX_VERIFY_TLS", "false").lower() == "true",
}


def load_config() -> dict:
    if CONFIG_PATH.exists():
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        # campos ausentes herdam o default/env
        return {**_DEFAULT, **data}
    return dict(_DEFAULT)


def save_config(cfg: dict) -> dict:
    current = load_config()
    # só sobrescreve o que veio preenchido (evita apagar o token ao salvar a URL)
    for k in ("url", "user", "verify_tls"):
        if k in cfg and cfg[k] is not None:
            current[k] = cfg[k]
    for k in ("token", "password"):
        if cfg.get(k):
            current[k] = cfg[k]
    CONFIG_PATH.write_text(json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8")
    return current


def load_public() -> dict:
    """Versão segura para o front: mascara segredos."""
    c = load_config()
    return {
        "url": c["url"],
        "user": c["user"],
        "verify_tls": c["verify_tls"],
        "token_set": bool(c["token"]),
        "token_preview": (c["token"][:6] + "…" + c["token"][-4:]) if c["token"] else "",
    }
