from langchain_core.callbacks import BaseCallbackHandler
from prometheus_client import Counter, Histogram

from agente import config

RESPUESTAS = Counter("agente_respuestas", "Turnos completados por el agente", ["tipo"])
LATENCIA = Histogram("agente_latencia_segundos", "Latencia de un turno completo", ["tipo"],
                     buckets=(0.5, 1, 2, 5, 10, 20, 30, 60, 120))
HERRAMIENTAS = Counter("agente_herramientas", "Veces que se usó cada herramienta", ["herramienta"])
ERRORES = Counter("agente_errores", "Excepciones al invocar el grafo")
APROBACIONES = Counter("agente_aprobaciones", "Respuestas a solicitudes de aprobación", ["resultado"])
GUARDRAILS = Counter("agente_guardrails", "Detecciones de los guardrails de entrada", ["tipo"])
TOKENS = Counter("agente_tokens", "Tokens consumidos por el LLM", ["tipo"])
COSTO_USD = Counter("agente_costo_usd", "Costo estimado en USD de las llamadas al LLM")


def registrar_turno(tipo: str | None, herramientas: list[str], latencia_s: float):
    tipo = tipo or "desconocido"
    RESPUESTAS.labels(tipo).inc()
    LATENCIA.labels(tipo).observe(latencia_s)
    for h in herramientas:
        HERRAMIENTAS.labels(h).inc()


def calcular_costo(tokens_in: int, tokens_out: int) -> float:
    """Costo en USD según los precios por 1M de tokens definidos en el .env."""
    return (tokens_in * config.PRICE_INPUT_PER_1M + tokens_out * config.PRICE_OUTPUT_PER_1M) / 1_000_000


def registrar_uso(tokens_in: int, tokens_out: int):
    TOKENS.labels("entrada").inc(tokens_in)
    TOKENS.labels("salida").inc(tokens_out)
    COSTO_USD.inc(calcular_costo(tokens_in, tokens_out))


class ContadorTokens(BaseCallbackHandler):
    """Se engancha a cada llamada al LLM y suma sus tokens a las métricas."""

    def on_llm_end(self, response, **kwargs):
        entrada = salida = 0
        for generaciones in response.generations:
            for g in generaciones:
                uso = getattr(getattr(g, "message", None), "usage_metadata", None) or {}
                entrada += uso.get("input_tokens", 0)
                salida += uso.get("output_tokens", 0)
        if not (entrada or salida):
            uso = (response.llm_output or {}).get("token_usage", {})
            entrada, salida = uso.get("prompt_tokens", 0), uso.get("completion_tokens", 0)
        registrar_uso(entrada, salida)
