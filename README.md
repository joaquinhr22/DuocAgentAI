# DuocAIAgent · Evaluación Parcial 2

## Contexto

Agente de IA que orienta a estudiantes de DuocUC sobre el reglamento académico, el calendario 2026 y las prácticas profesionales.

El agente está hecho con LangGraph y usa un modelo de Groq (gpt-oss-20b). Busca la información en los documentos oficiales guardados en MongoDB Atlas con búsqueda vectorial. Antes de responder arma un plan, usa herramientas para consultar fechas o calcular plazos y revisa que la respuesta esté respaldada por los documentos. Además recuerda los datos del estudiante entre conversaciones y pide autorización antes de guardar un plan o crear un ticket para coordinación en caso de dudas mas puntuales.

## Requisitos

- Python 3.12

## Instrucciones

### Documentos de Duoc
Los documentos que usaremos para que nuestro modelo tenga el contexto se encuentran en formato markdown `.md` dentro de la carpeta `docs`

### Clonar el proyecto

```
git clone https://github.com/bjoaquin19/DuocAgentAI.git
cd DuocAgentAI\evaluacion2
```

### Crear el entorno e instalar las dependencias

```
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

### Configurar el .env con los respectivos secretos

### Cargar los documentos



```
python ingesta.py --sin-externas
```

Cargas los 3 documentos de data/internos, este crea los embeddings y los dos indices en Atlas.

### Ejecutar el proyecto

```
streamlit run app.py
```

En esta abres el localhost y seguido interactuas con el proyecto.

### Observabilidad (Prometheus + Grafana)

La app expone métricas en `http://localhost:8001/metrics` y la API en `http://localhost:8000/metrics/` (turnos por tipo, latencia, uso de herramientas, errores, aprobaciones, tokens, costo en USD y detecciones de guardrails). Para ver el dashboard necesitas [Docker Desktop](https://www.docker.com/products/docker-desktop/):

```
docker compose -f observabilidad/docker-compose.yml up -d
```

Luego, en la app, usa el botón **Dashboard de observabilidad (Grafana)** de la barra lateral (o abre `http://localhost:3000/d/duoc-agente`). El dashboard es de solo lectura sin login; el usuario admin es `admin` con la clave de `GRAFANA_ADMIN_PASSWORD` (por defecto `admin`).

### Costos, seguridad y trazabilidad

- **Tokens y costo:** un callback (`ContadorTokens`, en `agente/metricas.py`) se engancha a cada llamada al modelo. El costo se calcula con `PRICE_INPUT_PER_1M` y `PRICE_OUTPUT_PER_1M` del `.env` (USD por 1M de tokens).
- **Guardrails de entrada** (`agente/guardrails.py`): los datos personales (RUT, correo, teléfono, tarjeta) se enmascaran antes de llegar al modelo, y los intentos de prompt injection se bloquean. Se evalúan con `python eval/eval_guardrails.py`.
- **Trazabilidad:** cada turno tiene un `trace_id` y usa la conversación como `session_id`. Los eventos se escriben como JSON en `logs/agente.jsonl` (ruta configurable con `ARCHIVO_LOGS`).

### Informe y presentación
Los documentos de los cuales se alimenta nuestro modelo se encuentran en la carpeta `docs`