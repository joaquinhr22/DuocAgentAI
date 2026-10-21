# Decisiones de diseño

Este documento resume por qué elegimos cada cosa. Complementa el informe.

## 1. Cambios respecto a la primera versión (notebook en Colab)

| Problema en la v1 | Qué hicimos |
|---|---|
| Todo estaba en un notebook de Colab, no se podía ejecutar fuera de Colab (`google.colab.files`, `userdata`) | Separamos en módulos (ingesta, retrieval, generate, prompts) como en la clase 1.4, con `.env` y Docker |
| El README estaba vacío | README con instrucciones de ejecución, pruebas y arquitectura |
| Solo había fuentes internas | Agregamos fuentes externas (páginas web) marcadas con `tipo = externa` |
| pypdf sacaba el calendario palabra por palabra (`FUENTE\n \nDE\n \n...`) y los chunks quedaban malos | Función `limpiar_texto()` antes del chunking |
| El separador `"\n==========\n"` del calendario nunca calzaba con el texto | Separadores revisados por tipo de documento (`CONFIG_FUENTES`) |
| Se insertaba varias veces lo mismo en Mongo (había 279 chunks del reglamento en vez de 93) | La ingesta revisa si el archivo ya fue cargado; `--reset` para recargar |
| Los ejemplos few-shot se mandaban dentro del mensaje del usuario | Van en el system prompt; el usuario solo manda su pregunta |
| No había historial de conversación | Se mandan los últimos 6 mensajes |
| No había evaluación ni tests | `eval/evaluate.py` (3 versiones de prompt) y `tests/` con pytest |
| El diagrama solo mostraba la ingesta | Diagrama completo: ingesta + consulta + evaluación |
| Modelo `openai/gpt-oss-20b` | `llama-3.1-8b-instant` (Groq), según lo definido para el proyecto |
| MongoDB Atlas | PostgreSQL + pgvector |

## 2. Modelo de lenguaje: Llama 3.1 8B en Groq

- Es open source y Groq lo sirve gratis con muy baja latencia (respuestas en ~1 segundo).
- Para este caso no necesitamos un modelo grande: la respuesta ya viene en el contexto, el modelo solo
  tiene que leerla y redactar. Lo importante es que **no invente**, y eso lo controlamos con el prompt y la
  temperatura baja (0.2).
- Limitación: con 8B el modelo sigue peor las instrucciones largas, por eso el prompt es corto y tiene ejemplos.

## 3. Embeddings locales

`paraphrase-multilingual-MiniLM-L12-v2` (384 dimensiones). Está entrenado en español, no cuesta nada y no
manda los documentos a un tercero. Es el mismo modelo que ya usábamos en la v1.
Importante: el mismo modelo se usa para indexar y para la pregunta; si se cambia hay que re-ingestar todo.

## 4. PostgreSQL + pgvector

- Una sola base de datos para los vectores **y** para los logs de interacciones (trazabilidad).
- Es SQL normal, se puede consultar y filtrar por fuente o tipo sin aprender otra API.
- Se puede levantar local con Docker (`pgvector/pgvector:pg16`) o usar un servicio gratis en la nube.
- Índice HNSW con distancia coseno: para unos cientos de chunks es más que suficiente.

## 5. Chunking por tipo de documento

Cada documento tiene una estructura distinta, así que no usamos un solo tamaño:

| Documento | chunk_size / overlap | Separador principal | Razón |
|---|---|---|---|
| Reglamento | 1000 / 150 | `Artículo N°` | Un artículo es la unidad de sentido; no queremos artículos partidos |
| Calendario | 600 / 100 | bloques `=====` | Son eventos cortos (fecha + actividad); chunks chicos = búsqueda más precisa |
| Prácticas | 1200 / 150 | `TIPO:` / `TEMA:` | Separa práctica laboral de profesional |
| Web | 1000 / 150 | párrafos | Genérico |

## 6. Reranking

pgvector trae 20 candidatos por similitud coseno y un cross-encoder los reordena y deja 5. El cross-encoder lee
pregunta y chunk juntos, por eso es más preciso, pero más lento; por eso solo se aplica sobre 20.
En la clase 1.3 se usó `ms-marco-MiniLM-L-6-v2`, pero está entrenado solo en inglés, así que usamos su versión
multilingüe. Se puede desactivar con `USAR_RERANKER=false` para comparar.

## 7. Prompts

Estructura de la clase 1.2: **rol → tarea → contexto → formato → restricciones**. Tres versiones:

- **zero_shot**: solo las instrucciones.
- **few_shot** (por defecto): + 4 ejemplos que cubren los casos difíciles: dato presente, dato que falta,
  pregunta fuera de dominio y saludo. Con un modelo de 8B los ejemplos ayudan a que respete el formato y
  las frases de rechazo.
- **cot**: + razonamiento paso a paso; útil para preguntas de fechas ("¿cuánto falta para...?"). Al estudiante
  solo se le muestra lo que va después de "Respuesta final:".

Otras decisiones del prompt:
- Se le pasa la **fecha de hoy**, porque muchas preguntas de calendario son relativas.
- Si una fuente externa contradice a una interna, **manda la interna** (documento oficial).
- Debe citar la fuente `[Fuente: ...]` para que el estudiante pueda verificar.
- Si no está la información, deriva a Punto Estudiantil / Director de Carrera en vez de inventar.

## 8. Fuentes internas vs externas

- **Internas**: PDFs oficiales de Duoc (reglamento, calendario, prácticas). Son la fuente de verdad.
- **Externas**: páginas web listadas en `data/externos/fuentes.txt` (sitio de Duoc, feriados legales de Chile).
  Complementan, por ejemplo, para saber si un día es feriado.
- Cada chunk guarda `fuente`, `tipo` (interna/externa) y `origen` (archivo o URL), y el contexto que ve el LLM
  incluye esa etiqueta.

## 9. Trazabilidad y restricciones

- Tabla `interacciones`: qué se preguntó, qué chunks se usaron (con score), qué respondió, con qué prompt y
  cuántos tokens. Sirve para auditar respuestas malas y para calcular costos.
- No se guardan datos personales del estudiante (solo un `session_id` aleatorio).
- Las API keys solo van en `.env` (no se suben al repo).
