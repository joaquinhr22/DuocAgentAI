"""Logs estructurados (una línea JSON por evento) con session_id y trace_id."""
import json
import logging
import os
import sys
from datetime import datetime, timezone

from agente import config

_logger = logging.getLogger("agente")


class _JsonFormatter(logging.Formatter):
    def format(self, record):
        datos = {"ts": datetime.now(timezone.utc).isoformat(), "nivel": record.levelname,
                 "evento": record.getMessage()}
        datos.update(getattr(record, "campos", {}))
        return json.dumps(datos, ensure_ascii=False, default=str)


def _configurar():
    if _logger.handlers:
        return
    _logger.setLevel(logging.INFO)
    _logger.propagate = False
    formato = _JsonFormatter()
    consola = logging.StreamHandler(sys.stderr)
    consola.setFormatter(formato)
    _logger.addHandler(consola)
    if config.ARCHIVO_LOGS:
        os.makedirs(os.path.dirname(config.ARCHIVO_LOGS) or ".", exist_ok=True)
        archivo = logging.FileHandler(config.ARCHIVO_LOGS, encoding="utf-8")
        archivo.setFormatter(formato)
        _logger.addHandler(archivo)


def evento(nombre: str, nivel: int = logging.INFO, **campos):
    _configurar()
    _logger.log(nivel, nombre, extra={"campos": campos})
