"""Pipeline de ingesta: fuentes internas (PDFs) y externas (paginas web) -> chunks -> embeddings -> PostgreSQL.

Uso:
    python ingest.py            # ingesta lo que falte
    python ingest.py --reset    # borra y vuelve a ingestar todo
"""
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src import config
from src.utils.embeddings import EmbeddingClient
from src.utils.postgres import PostgresClient


# Cada documento tiene una estructura distinta, asi que usamos un splitter distinto para cada uno.
# (esto ya lo haciamos en el notebook, aca lo dejamos ordenado en una tabla)
CONFIG_FUENTES = {
    "reglamento": {
        "fuente": "reglamento_academico",
        "chunk_size": 1000,
        "chunk_overlap": 150,
        # cortamos idealmente por articulo para que no queden articulos partidos
        "separators": ["\nArtículo N°", "\n\n", "\n", ". ", " "],
    },
    "calendario": {
        "fuente": "calendario_academico",
        "chunk_size": 600,
        "chunk_overlap": 100,
        "separators": ["\n=====", "\n\n", "\n", " "],
    },
    "practica": {
        "fuente": "practicas",
        "chunk_size": 1200,
        "chunk_overlap": 150,
        "separators": ["\nTIPO:", "\nTEMA:", "\n\n", "\n", " "],
    },
}
CONFIG_DEFAULT = {"fuente": "otros", "chunk_size": 1000, "chunk_overlap": 150, "separators": ["\n\n", "\n", ". ", " "]}
CONFIG_WEB = {"chunk_size": 1000, "chunk_overlap": 150, "separators": ["\n\n", "\n", ". ", " "]}


# ---------------------------------------------------------------------------
# PASO 1 - Extraccion y limpieza de texto
# ---------------------------------------------------------------------------
def limpiar_texto(texto: str) -> str:
    """Arregla el texto que entrega pypdf.

    En el calendario y el doc de practicas pypdf devolvia cada palabra en una linea
    ("FUENTE\\n \\nDE\\n \\nCONOCIMIENTO"), lo que hacia los chunks casi inutiles.
    Un salto "\\n \\n" simple es un espacio, y tres o mas seguidos son un salto de parrafo.
    """
    texto = texto.replace("\r", "")
    texto = re.sub(r"(\n[ \t]*){3,}", "<<PARRAFO>>", texto)  # parrafos
    texto = re.sub(r"\n[ \t]*\n", " ", texto)               # palabra\n \npalabra -> palabra palabra
    texto = texto.replace("<<PARRAFO>>", "\n\n")
    texto = re.sub(r"[ \t]{2,}", " ", texto)
    return texto.strip()


def extraer_texto_pdf(ruta: Path) -> str:
    reader = PdfReader(str(ruta))
    paginas = [pagina.extract_text() or "" for pagina in reader.pages]
    print(f"  {ruta.name}: {len(reader.pages)} paginas")
    return limpiar_texto("\n".join(paginas))


def extraer_texto_web(url: str) -> str:
    resp = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0 (DuocAIAgent - proyecto estudiantil)"})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()
    texto = soup.get_text("\n")
    texto = re.sub(r"\n\s*\n+", "\n\n", texto)
    return texto.strip()


# ---------------------------------------------------------------------------
# PASO 2 - Chunking
# ---------------------------------------------------------------------------
def config_para_archivo(nombre: str) -> dict:
    nombre = nombre.lower()
    for clave, cfg in CONFIG_FUENTES.items():
        if clave in nombre:
            return cfg
    return CONFIG_DEFAULT


def dividir_en_chunks(texto: str, cfg: dict) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=cfg["chunk_size"],
        chunk_overlap=cfg["chunk_overlap"],
        separators=cfg["separators"],
    )
    # descartamos chunks muy chicos (numeros de pagina, titulos sueltos)
    return [c.strip() for c in splitter.split_text(texto) if len(c.strip()) > 40]


def leer_fuentes_externas(ruta: str) -> list[str]:
    path = Path(ruta)
    if not path.exists():
        return []
    lineas = [l.strip() for l in path.read_text(encoding="utf-8").splitlines()]
    return [l for l in lineas if l and not l.startswith("#")]


# ---------------------------------------------------------------------------
# PASO 3 - Embeddings + guardado en PostgreSQL
# ---------------------------------------------------------------------------
class Ingestor:
    def __init__(self):
        self.embedder = EmbeddingClient()
        self.db = PostgresClient()
        self.db.crear_tablas()

    def _guardar(self, chunks: list[str], fuente: str, tipo: str, origen: str):
        embeddings = self.embedder.get_embeddings(chunks)
        filas = [
            {"contenido": c, "fuente": fuente, "tipo": tipo, "origen": origen, "chunk_id": i, "embedding": e}
            for i, (c, e) in enumerate(zip(chunks, embeddings))
        ]
        self.db.insertar_chunks(filas)
        print(f"  -> {len(filas)} chunks guardados ({fuente})")

    def ingestar_pdf(self, ruta: Path, reset: bool = False):
        if reset:
            self.db.borrar_origen(ruta.name)
        elif self.db.origen_ya_ingestado(ruta.name):
            print(f"  (ya estaba) {ruta.name}")
            return
        cfg = config_para_archivo(ruta.name)
        chunks = dividir_en_chunks(extraer_texto_pdf(ruta), cfg)
        self._guardar(chunks, cfg["fuente"], "interna", ruta.name)

    def ingestar_url(self, url: str, reset: bool = False):
        if reset:
            self.db.borrar_origen(url)
        elif self.db.origen_ya_ingestado(url):
            print(f"  (ya estaba) {url}")
            return
        try:
            texto = extraer_texto_web(url)
        except Exception as e:
            # si una pagina se cae no queremos que se caiga toda la ingesta
            print(f"  [WARN] no se pudo descargar {url}: {e}")
            return
        chunks = dividir_en_chunks(texto, CONFIG_WEB)
        dominio = url.split("/")[2].replace("www.", "")
        self._guardar(chunks, f"web_{dominio}", "externa", url)

    def ingestar_todo(self, reset: bool = False):
        pdfs = sorted(Path(config.CARPETA_INTERNOS).glob("*.pdf"))
        print(f"Fuentes internas: {len(pdfs)} PDF(s) en {config.CARPETA_INTERNOS}")
        for ruta in pdfs:
            self.ingestar_pdf(ruta, reset)

        urls = leer_fuentes_externas(config.ARCHIVO_EXTERNOS)
        print(f"Fuentes externas: {len(urls)} URL(s) en {config.ARCHIVO_EXTERNOS}")
        for url in urls:
            self.ingestar_url(url, reset)

        print("\nResumen en la base de datos:")
        for fuente, n in self.db.contar_por_fuente().items():
            print(f"  {fuente}: {n} chunks")
