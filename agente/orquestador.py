import logging
import time
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command

from agente import config, guardrails, logs, metricas
from agente.grafo import construir_grafo, crear_checkpointer


class Orquestador:
    def __init__(self, llm=None, servicios=None, checkpointer=None, llm_validador=None):
        if servicios is None:
            from agente.servicios import crear_servicios
            servicios = crear_servicios()
        if llm is None:
            from agente.llm import crear_llm
            llm = crear_llm()
        if checkpointer is None:
            checkpointer = crear_checkpointer(getattr(servicios.db, "client", None))
        self.servicios = servicios
        self.grafo = construir_grafo(llm, servicios, checkpointer, llm_validador)

    def _config(self, thread_id: str) -> dict:
        return {"configurable": {"thread_id": thread_id}, "recursion_limit": config.RECURSION_LIMIT}

    def _resultado(self, salida: dict, thread_id: str) -> dict:
        estado = self.grafo.get_state(self._config(thread_id))
        valores = estado.values
        pendiente = None
        interrupciones = salida.get("__interrupt__") if isinstance(salida, dict) else None
        if interrupciones:
            pendiente = interrupciones[0].value
        mensajes = valores.get("messages", [])
        respuesta = mensajes[-1].content if mensajes and isinstance(mensajes[-1], AIMessage) and not pendiente else ""
        return {
            "respuesta": respuesta,
            "pendiente_aprobacion": pendiente,
            "tipo": valores.get("tipo"),
            "motivo": valores.get("motivo"),
            "consulta": valores.get("consulta"),
            "plan": valores.get("plan", []),
            "decisiones": valores.get("decisiones", []),
            "herramientas": valores.get("herramientas_usadas", []),
            "documentos": valores.get("documentos", []),
            "perfil": valores.get("perfil", {}),
            "memorias": valores.get("memorias", []),
            "resumen": valores.get("resumen", ""),
        }

    def _invocar(self, entrada, thread_id: str) -> dict:
        try:
            salida = self.grafo.invoke(entrada, self._config(thread_id))
        except Exception:
            metricas.ERRORES.inc()
            raise
        return self._resultado(salida, thread_id)

    def _bloqueado(self, mensaje: str, trace_id: str) -> dict:
        return {"respuesta": mensaje, "pendiente_aprobacion": None, "tipo": "bloqueado_guardrail",
                "motivo": "Bloqueado por guardrail de entrada", "consulta": None, "plan": [], "decisiones": [],
                "herramientas": [], "documentos": [], "perfil": {}, "memorias": [], "resumen": "",
                "trace_id": trace_id}

    def preguntar(self, user_id: str, thread_id: str, texto: str) -> dict:
        trace_id = uuid4().hex[:16]
        rev = guardrails.revisar_entrada(texto)
        for d in rev.detecciones:
            metricas.GUARDRAILS.labels(d).inc()
        logs.evento("turno_inicio", trace_id=trace_id, session_id=thread_id, user_id=user_id,
                    guardrails=rev.detecciones, bloqueado=rev.bloqueado)
        if rev.bloqueado:
            logs.evento("turno_bloqueado", logging.WARNING, trace_id=trace_id, session_id=thread_id,
                        motivo=rev.detecciones)
            return self._bloqueado(rev.mensaje, trace_id)
        inicio = time.time()
        try:
            r = self._invocar({"messages": [HumanMessage(rev.texto_limpio)], "user_id": user_id}, thread_id)
        except Exception as e:
            logs.evento("turno_error", logging.ERROR, trace_id=trace_id, session_id=thread_id, error=type(e).__name__)
            raise
        logs.evento("turno_fin", trace_id=trace_id, session_id=thread_id, tipo=r["tipo"],
                    herramientas=r["herramientas"], latencia_ms=int((time.time() - inicio) * 1000))
        r["trace_id"] = trace_id
        return r

    def responder_aprobacion(self, thread_id: str, aprobado: bool) -> dict:
        metricas.APROBACIONES.labels("aprobado" if aprobado else "rechazado").inc()
        return self._invocar(Command(resume=aprobado), thread_id)

    def historial(self, thread_id: str) -> list[dict]:
        valores = self.grafo.get_state(self._config(thread_id)).values
        filas = []
        for m in valores.get("messages", []):
            if isinstance(m, HumanMessage):
                filas.append({"rol": "user", "contenido": m.content})
            elif isinstance(m, AIMessage) and m.content and not m.tool_calls:
                filas.append({"rol": "assistant", "contenido": m.content})
        return filas
