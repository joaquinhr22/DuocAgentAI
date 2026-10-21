# Instructivo: correr DuocAIAgent en tu computador (con Jupyter)

Tiempo estimado: 20 a 30 minutos la primera vez (la mayoría es descarga de librerías y modelos).

## 0. Qué necesitas instalar

| Programa | Para qué | Link |
|---|---|---|
| **Python 3.11 o 3.12** | Correr el código. En Windows, al instalar marca **"Add Python to PATH"** | https://www.python.org/downloads/ |
| **Git** | Bajar el repo | https://git-scm.com/downloads |
| **Docker Desktop** | Levantar PostgreSQL con pgvector sin instalarlo a mano | https://www.docker.com/products/docker-desktop/ |
| **VS Code** (opcional) | Abrir el notebook con la extensión "Jupyter" | https://code.visualstudio.com/ |

Además necesitas una **API key de Groq** (gratis): entra a https://console.groq.com/keys, crea una key y cópiala (empieza con `gsk_`).

> Si no puedes instalar Docker, ve a la sección "Sin Docker" al final.

## 1. Bajar el repo

Abre una terminal (en Windows: **PowerShell**) y ejecuta:

```bash
git clone https://github.com/bjoaquin19/AgentAI_project.git
cd AgentAI_project
git checkout correccion-ev1     # mientras el PR no esté mergeado; después basta con main
```

## 2. Crear el entorno virtual e instalar dependencias

**Windows (PowerShell):**
```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

> Si PowerShell reclama que "la ejecución de scripts está deshabilitada", corre una vez
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` y vuelve a activar el entorno.

**Mac / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

La línea de `torch` instala la versión solo-CPU (pesa ~200 MB en vez de ~2 GB con CUDA). En Mac basta `pip install torch`.

Cada vez que abras una terminal nueva hay que **activar el entorno** de nuevo (`.venv\Scripts\Activate.ps1` o `source .venv/bin/activate`).

## 3. Configurar el `.env`

```bash
# Windows
copy .env.example .env
# Mac/Linux
cp .env.example .env
```

Abre `.env` con un editor y pega tu key:

```
GROQ_API_KEY=gsk_tu_key_aqui
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/duoc_agent
```

El `.env` **no se sube a GitHub** (está en el `.gitignore`). Nunca pongan la key directo en el código ni en el notebook.

## 4. Levantar PostgreSQL + pgvector

Con Docker Desktop abierto:

```bash
docker compose up -d db
```

Para comprobar que está arriba: `docker compose ps` debe mostrar el servicio `db` como `healthy`.
La primera vez descarga la imagen `pgvector/pgvector:pg16` (~150 MB). Los datos quedan guardados aunque apagues el PC.

## 5. Abrir el notebook

```bash
jupyter notebook DuocAiAgent.ipynb
```

Se abre el navegador. Ejecuta las celdas **en orden** con `Shift + Enter`:

| Sección | Qué hace | Qué deberías ver |
|---|---|---|
| 0. Configuración | Lee el `.env` y se conecta a PostgreSQL | `Groq API key: OK` y `Conexion OK` |
| 1. Extracción | Lee los PDFs y limpia el texto | El calendario antes (palabra por palabra) y después |
| 2. Chunking | Corta cada documento | reglamento ~116, calendario 15, prácticas 2 chunks |
| 3. Ingesta | Calcula embeddings y los guarda en la BD | La primera vez descarga el modelo (~470 MB, unos minutos) |
| 4. Retrieval | Busca los chunks de una pregunta | Comparación con y sin reranker (también descarga el reranker la primera vez) |
| 5. Prompts | Muestra el system prompt armado | |
| 6. Generación | Pregunta al agente con zero-shot, few-shot y CoT | Respuestas de Llama 3.1 8B |
| 7. Trazabilidad | Muestra las interacciones guardadas | |
| 8. Evaluación | Corre las 14 preguntas del dataset y las evalúa | Tabla resumen; guarda archivos en `eval/resultados/` |
| 9. Tests | Corre pytest | `19 passed` |

**Con VS Code:** abre la carpeta del repo, abre `DuocAiAgent.ipynb`, arriba a la derecha elige el kernel
**`.venv`** (Python Environments → `.venv`) y ejecuta las celdas.

## 6. (Opcional) La app de chat

```bash
streamlit run app.py
```

Abre http://localhost:8501. En la barra lateral se puede cambiar la versión del prompt y ver las fuentes recuperadas.
Sirve para la demo de la presentación.

## 7. Guardar la evidencia para el informe

Después de correr la sección 8 del notebook quedan dos archivos en `eval/resultados/` (`.json` y `.md`). Súbanlos al repo:

```bash
git add eval/resultados
git commit -m "Resultados de la evaluación"
git push
```

## Problemas comunes

| Error | Solución |
|---|---|
| `Falta GROQ_API_KEY en el .env` | El `.env` no está en la carpeta raíz o no tiene la key. Reinicia el kernel después de editarlo (Kernel → Restart) |
| `connection refused ... port 5432` | La BD no está arriba: abre Docker Desktop y corre `docker compose up -d db` |
| `port is already allocated` (5432) | Ya tienes otro PostgreSQL usando ese puerto. Apágalo, o en `docker-compose.yml` cambia `"5432:5432"` por `"5433:5432"` y en el `.env` usa `localhost:5433` |
| `ModuleNotFoundError: No module named 'src'` | Abriste Jupyter fuera de la carpeta del repo. Ciérralo y ábrelo desde `AgentAI_project` |
| `ModuleNotFoundError` de otra librería | El kernel no es el del `.venv`. En Jupyter: Kernel → Change kernel; en VS Code: elige `.venv` |
| `RateLimitError` / error 429 de Groq | Límite del plan gratis. Espera un minuto; en la evaluación prueben primero solo `["few_shot"]` |
| La ingesta se queda pegada al inicio | Está descargando el modelo de embeddings; la primera vez se demora |
| Cambié los PDFs y responde lo antiguo | En la sección 3 usa `ingestor.ingestar_todo(reset=True)` |

## Sin Docker

Pueden usar un PostgreSQL gratis en la nube con pgvector, por ejemplo **Supabase** (https://supabase.com) o **Neon** (https://neon.tech):

1. Crear un proyecto y copiar la *connection string* (Supabase: Project Settings → Database → Connection string → URI).
2. Pegarla en el `.env` como `DATABASE_URL=postgresql://...` (en Supabase agregar `?sslmode=require` al final si no lo trae).
3. Saltarse el paso 4. La extensión `vector` la crea el código solo (en Supabase y Neon ya viene disponible).
