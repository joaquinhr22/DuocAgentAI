from prometheus_client import Counter, Histogram

RESPUESTAS = Counter("agente_respuestas", "Turnos completados por el agente", ["tipo"])
LATENCIA = Histogram("agente_latencia_segundos", "Latencia de un turno completo", ["tipo"],
                     buckets=(0.5, 1, 2, 5, 10, 20, 30, 60, 120))
HERRAMIENTAS = Counter("agente_herramientas", "Veces que se usó cada herramienta", ["herramienta"])
ERRORES = Counter("agente_errores", "Excepciones al invocar el grafo")
APROBACIONES = Counter("agente_aprobaciones", "Respuestas a solicitudes de aprobación", ["resultado"])


def registrar_turno(tipo: str | None, herramientas: list[str], latencia_s: float):
    tipo = tipo or "desconocido"
    RESPUESTAS.labels(tipo).inc()
    LATENCIA.labels(tipo).observe(latencia_s)
    for h in herramientas:
        HERRAMIENTAS.labels(h).inc()
