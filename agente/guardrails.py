"""Guardrails de entrada: detectan PII y prompt injection antes de llamar al modelo.

Son reglas determinísticas (regex): no gastan tokens, son rápidas y fáciles de probar.
- PII (RUT, correo, teléfono, tarjeta): se enmascara y el turno continúa.
- Prompt injection: se bloquea el turno y no se llama al modelo.
"""
import re
import unicodedata
from dataclasses import dataclass, field

PII = {
    "rut": re.compile(r"\b\d{1,2}\.?\d{3}\.?\d{3}-[\dkK]\b"),
    "correo": re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b"),
    "tarjeta": re.compile(r"\b(?:\d[ -]?){13,16}\b"),
    "telefono": re.compile(r"(?<!\d)(?:\+?56[\s-]?)?9[\s-]?\d{4}[\s-]?\d{4}(?!\d)"),
}

INJECTION = [
    r"ignora (todas |todo |cualquier )?(las |tus |los )?(instrucciones|reglas|indicaciones)",
    r"olvida (todas |todo )?(las |tus |lo )?(instrucciones|reglas|anterior)",
    r"ignore (all |any )?(the )?(previous|prior|above) (instructions|rules)",
    r"disregard (all |the )?(previous|prior|above)",
    r"(muestra|revela|dime|imprime|repite)(me)? (tu |tus |el )?(prompt|instrucciones) (del sistema|de sistema|inicial|oculto)?",
    r"(system prompt|prompt del sistema|prompt de sistema)",
    r"(you are|eres|actua como|actúa como) (now |ahora )?(dan|un modelo sin|sin (reglas|restricciones|filtros))",
    r"(modo|mode) (desarrollador|developer|dios|god|dan)",
    r"jailbreak",
]
_INJECTION = [re.compile(p) for p in INJECTION]

MENSAJE_BLOQUEO = ("No puedo ayudar con esa solicitud porque intenta cambiar mis instrucciones. "
                   "Puedo ayudarte con el reglamento, el calendario académico y las prácticas de DuocUC.")


@dataclass
class Revision:
    texto_limpio: str
    detecciones: list[str] = field(default_factory=list)
    bloqueado: bool = False
    mensaje: str = ""


def _normalizar(texto: str) -> str:
    sin_tildes = "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
    return sin_tildes.lower()


def revisar_entrada(texto: str) -> Revision:
    detecciones = []
    limpio = texto
    if any(p.search(_normalizar(texto)) for p in _INJECTION):
        return Revision(texto_limpio=texto, detecciones=["prompt_injection"], bloqueado=True,
                        mensaje=MENSAJE_BLOQUEO)
    for tipo, patron in PII.items():
        if patron.search(limpio):
            detecciones.append(f"pii_{tipo}")
            limpio = patron.sub(f"[{tipo.upper()}]", limpio)
    return Revision(texto_limpio=limpio, detecciones=detecciones)
