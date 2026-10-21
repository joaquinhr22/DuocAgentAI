import time
from datetime import date

from prompts.prompt import construir_system_prompt, extraer_respuesta_final
from src import config
from src.retrieval.retrieval import Retriever
from src.utils.llm import GroqLLM

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]

# cuantos mensajes anteriores mandamos al LLM (Llama 3.1 8B en Groq tiene contexto limitado en el tier gratis)
MAX_HISTORIAL = 6


def formatear_contexto(chunks: list[dict]) -> str:
    partes = []
    for i, c in enumerate(chunks, 1):
        partes.append(f"[{i}] Fuente: {c['fuente']} ({c['tipo']})\n{c['contenido']}")
    return "\n\n---\n\n".join(partes)


def fecha_hoy() -> str:
    hoy = date.today()
    return f"{hoy.day} de {MESES[hoy.month - 1]} de {hoy.year}"


class RAGGenerator:
    def __init__(self, prompt_version: str = config.PROMPT_VERSION, retriever: Retriever | None = None,
                 llm: GroqLLM | None = None):
        self.prompt_version = prompt_version
        self.retriever = retriever or Retriever()
        self.llm = llm or GroqLLM()

    def generate(self, query: str, history: list[dict] | None = None, top_k: int = config.TOP_K_FINAL,
                 chunks: list[dict] | None = None, session_id: str | None = None) -> dict:
        inicio = time.perf_counter()
        history = (history or [])[-MAX_HISTORIAL:]

        # chunks permite reutilizar un retrieve ya hecho (lo usa la evaluacion)
        if chunks is None:
            chunks = self.retriever.retrieve(query, top_k=top_k)

        system_prompt = construir_system_prompt(self.prompt_version, formatear_contexto(chunks), fecha_hoy())
        response = self.llm.generate(system_prompt, history + [{"role": "user", "content": query}])

        respuesta_cruda = response["answer"]
        answer = extraer_respuesta_final(respuesta_cruda) if self.prompt_version == "cot" else respuesta_cruda
        latencia_ms = int((time.perf_counter() - inicio) * 1000)

        resultado = {
            "answer": answer,
            "raw_answer": respuesta_cruda,
            "sources": [
                {"fuente": c["fuente"], "tipo": c["tipo"], "origen": c["origen"],
                 "score": round(c.get("rerank_score", c["score"]), 3), "contenido": c["contenido"]}
                for c in chunks
            ],
            "prompt_tokens": response["prompt_tokens"],
            "completion_tokens": response["completion_tokens"],
            "total_tokens": response["total_tokens"],
            "latencia_ms": latencia_ms,
        }

        # trazabilidad: dejamos registro de cada interaccion en la BD
        try:
            self.retriever.db.guardar_interaccion({
                "session_id": session_id,
                "pregunta": query,
                "respuesta": answer,
                "fuentes": [{k: s[k] for k in ("fuente", "origen", "score")} for s in resultado["sources"]],
                "prompt_version": self.prompt_version,
                "modelo": self.llm.model,
                "prompt_tokens": response["prompt_tokens"],
                "completion_tokens": response["completion_tokens"],
                "latencia_ms": latencia_ms,
            })
        except Exception as e:
            print(f"[WARN] no se pudo guardar la interaccion: {e}")

        return resultado
