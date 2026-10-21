"""Evaluacion del RAG.

Para cada pregunta de eval/dataset.json y para cada version de prompt:
1. Recupera los chunks (una sola vez por pregunta, se comparten entre versiones)
2. Genera la respuesta
3. Calcula metricas:
   - hit_fuente: la fuente esperada aparece en los chunks recuperados (mide el retrieval)
   - correctitud: LLM-as-judge compara la respuesta con la respuesta esperada (0 a 1)
   - fundamentacion: LLM-as-judge revisa si la respuesta se apoya en el contexto (0 a 1)

Usamos como juez un modelo mas grande que el del agente (llama-3.3-70b en Groq) porque
un modelo evaluandose a si mismo tiende a ponerse buena nota.

Uso:
    python -m eval.evaluate                      # las 3 versiones de prompt
    python -m eval.evaluate --versiones few_shot
"""
import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path

from groq import Groq

from prompts.prompt import PROMPTS
from src import config
from src.generate.generate import RAGGenerator, formatear_contexto
from src.retrieval.retrieval import Retriever
from src.utils.llm import GroqLLM

DATASET_PATH = Path(__file__).parent / "dataset.json"
RESULTADOS_DIR = Path(__file__).parent / "resultados"
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "llama-3.3-70b-versatile")
PAUSA_SEG = 2  # el tier gratis de Groq tiene limite de requests por minuto

JUDGE_PROMPT = """Eres un evaluador de un asistente para estudiantes de Duoc UC.
Te doy una pregunta, la respuesta esperada (correcta), la respuesta del asistente y el contexto que tenia.

Evalua:
- correctitud (0.0 a 1.0): ¿la respuesta del asistente dice lo mismo que la esperada? 1 = mismo dato, 0.5 = parcial, 0 = incorrecta o inventada.
  Si la esperada es que el asistente se niegue o diga que no tiene la informacion, y lo hace, es 1.
- fundamentacion (0.0 a 1.0): ¿todo lo que afirma el asistente esta respaldado por el contexto? Penaliza datos inventados.

Responde SOLO con un JSON: {"correctitud": <float>, "fundamentacion": <float>, "comentario": "<una frase>"}"""


def juzgar(client: Groq, pregunta: str, esperada: str, respuesta: str, contexto: str) -> dict:
    contenido = (f"PREGUNTA: {pregunta}\n\nRESPUESTA ESPERADA: {esperada}\n\n"
                 f"RESPUESTA DEL ASISTENTE: {respuesta}\n\nCONTEXTO:\n{contexto}")
    try:
        r = client.chat.completions.create(
            model=JUDGE_MODEL,
            messages=[{"role": "system", "content": JUDGE_PROMPT}, {"role": "user", "content": contenido}],
            temperature=0,
            response_format={"type": "json_object"},
        )
        return json.loads(r.choices[0].message.content)
    except Exception as e:
        return {"correctitud": None, "fundamentacion": None, "comentario": f"error juez: {e}"}


def promedio(valores):
    valores = [v for v in valores if isinstance(v, (int, float))]
    return round(sum(valores) / len(valores), 3) if valores else None


def run_evaluation(versiones: list[str]) -> dict:
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    retriever = Retriever()
    llm = GroqLLM()
    juez = Groq(api_key=config.GROQ_API_KEY)
    generadores = {v: RAGGenerator(prompt_version=v, retriever=retriever, llm=llm) for v in versiones}

    resultados = []
    for item in dataset:
        print(f"\n[{item['id']}] {item['pregunta']}")
        chunks = retriever.retrieve(item["pregunta"])
        fuentes_recuperadas = [c["fuente"] for c in chunks]
        esperada = item.get("fuente_esperada")
        hit = None if esperada is None else esperada in fuentes_recuperadas
        contexto = formatear_contexto(chunks)

        for version, rag in generadores.items():
            r = rag.generate(item["pregunta"], chunks=chunks, session_id="evaluacion")
            nota = juzgar(juez, item["pregunta"], item["respuesta_esperada"], r["answer"], contexto)
            print(f"  {version:10s} correctitud={nota.get('correctitud')} fund={nota.get('fundamentacion')} hit={hit}")
            resultados.append({
                "id": item["id"],
                "categoria": item["categoria"],
                "pregunta": item["pregunta"],
                "respuesta_esperada": item["respuesta_esperada"],
                "prompt_version": version,
                "respuesta": r["answer"],
                "fuentes_recuperadas": fuentes_recuperadas,
                "hit_fuente": hit,
                "correctitud": nota.get("correctitud"),
                "fundamentacion": nota.get("fundamentacion"),
                "comentario_juez": nota.get("comentario"),
                "total_tokens": r["total_tokens"],
                "latencia_ms": r["latencia_ms"],
            })
            time.sleep(PAUSA_SEG)

    resumen = {}
    for v in versiones:
        filas = [x for x in resultados if x["prompt_version"] == v]
        resumen[v] = {
            "correctitud": promedio([x["correctitud"] for x in filas]),
            "fundamentacion": promedio([x["fundamentacion"] for x in filas]),
            "hit_fuente": promedio([1 if x["hit_fuente"] else 0 for x in filas if x["hit_fuente"] is not None]),
            "tokens_promedio": promedio([x["total_tokens"] for x in filas]),
            "latencia_ms_promedio": promedio([x["latencia_ms"] for x in filas]),
        }

    salida = {
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "modelo": config.GROQ_MODEL,
        "juez": JUDGE_MODEL,
        "reranker": config.USAR_RERANKER,
        "resumen": resumen,
        "detalle": resultados,
    }
    guardar(salida)
    return salida


def guardar(salida: dict):
    RESULTADOS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    (RESULTADOS_DIR / f"resultados_{stamp}.json").write_text(
        json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")

    lineas = [f"# Resultados evaluación ({salida['fecha']})", "",
              f"Modelo: `{salida['modelo']}` · Juez: `{salida['juez']}` · Reranker: {salida['reranker']}", "",
              "| Prompt | Correctitud | Fundamentación | Hit fuente | Tokens prom. | Latencia prom. (ms) |",
              "|---|---|---|---|---|---|"]
    for v, m in salida["resumen"].items():
        lineas.append(f"| {v} | {m['correctitud']} | {m['fundamentacion']} | {m['hit_fuente']} | "
                      f"{m['tokens_promedio']} | {m['latencia_ms_promedio']} |")
    lineas += ["", "## Detalle", "", "| # | Categoría | Prompt | Correctitud | Hit | Comentario juez |", "|---|---|---|---|---|---|"]
    for x in salida["detalle"]:
        comentario = (x["comentario_juez"] or "").replace("|", "/")
        lineas.append(f"| {x['id']} | {x['categoria']} | {x['prompt_version']} | {x['correctitud']} | "
                      f"{x['hit_fuente']} | {comentario} |")
    (RESULTADOS_DIR / f"resultados_{stamp}.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print(f"\nResultados guardados en {RESULTADOS_DIR}/resultados_{stamp}.(json|md)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--versiones", nargs="+", default=list(PROMPTS), choices=list(PROMPTS))
    args = parser.parse_args()
    salida = run_evaluation(args.versiones)
    print("\n=== Resumen ===")
    for v, m in salida["resumen"].items():
        print(v, m)
