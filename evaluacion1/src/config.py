"""Configuracion central del proyecto.

Todo se lee desde variables de entorno (.env) para no dejar claves en el codigo.
Ver .env.example para la lista completa.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# --- LLM (Groq) ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
TEMPERATURA = float(os.getenv("TEMPERATURA", "0.2"))

# --- Base de datos vectorial (PostgreSQL + pgvector) ---
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/duoc_agent")

# --- Embeddings ---
# Modelo multilingue (funciona bien en espanol) y corre local, no necesita API key.
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")
EMBEDDING_DIM = 384

# --- Retrieval ---
TOP_K_CANDIDATOS = int(os.getenv("TOP_K_CANDIDATOS", "20"))  # lo que trae pgvector
TOP_K_FINAL = int(os.getenv("TOP_K_FINAL", "5"))             # lo que pasa al LLM
USAR_RERANKER = os.getenv("USAR_RERANKER", "true").lower() == "true"
# ms-marco (el de la clase 1.3) esta entrenado en ingles, este es la version multilingue
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1")

# --- Prompt ---
# zero_shot | few_shot | cot  (ver prompts/prompt.py)
PROMPT_VERSION = os.getenv("PROMPT_VERSION", "few_shot")

# --- Datos ---
CARPETA_INTERNOS = os.getenv("CARPETA_INTERNOS", "data/internos")
ARCHIVO_EXTERNOS = os.getenv("ARCHIVO_EXTERNOS", "data/externos/fuentes.txt")
