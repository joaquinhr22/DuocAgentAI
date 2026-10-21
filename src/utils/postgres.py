"""Conexion a PostgreSQL con la extension pgvector.

Tablas:
- documentos: los chunks con su embedding (la "base vectorial")
- interacciones: log de cada pregunta/respuesta para trazabilidad
"""
import json
import psycopg
from pgvector.psycopg import register_vector
from src import config

SCHEMA = f"""
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documentos (
    id          SERIAL PRIMARY KEY,
    contenido   TEXT NOT NULL,
    fuente      TEXT NOT NULL,      -- reglamento_academico, calendario_academico, practicas, web_...
    tipo        TEXT NOT NULL,      -- interna | externa
    origen      TEXT NOT NULL,      -- nombre del archivo o URL
    chunk_id    INT  NOT NULL,
    embedding   vector({config.EMBEDDING_DIM}) NOT NULL,
    creado_en   TIMESTAMP DEFAULT NOW()
);

-- indice HNSW con distancia coseno (lo mismo que el vector_index de Mongo Atlas)
CREATE INDEX IF NOT EXISTS documentos_embedding_idx
    ON documentos USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS interacciones (
    id                SERIAL PRIMARY KEY,
    session_id        TEXT,
    pregunta          TEXT NOT NULL,
    respuesta         TEXT,
    fuentes           JSONB,
    prompt_version    TEXT,
    modelo            TEXT,
    prompt_tokens     INT,
    completion_tokens INT,
    latencia_ms       INT,
    creado_en         TIMESTAMP DEFAULT NOW()
);
"""


class PostgresClient:
    def __init__(self, url: str = config.DATABASE_URL):
        self.conn = psycopg.connect(url, autocommit=True)
        self.conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        register_vector(self.conn)

    def crear_tablas(self):
        self.conn.execute(SCHEMA)

    def origen_ya_ingestado(self, origen: str) -> bool:
        row = self.conn.execute("SELECT COUNT(*) FROM documentos WHERE origen = %s", (origen,)).fetchone()
        return row[0] > 0

    def borrar_origen(self, origen: str):
        self.conn.execute("DELETE FROM documentos WHERE origen = %s", (origen,))

    def insertar_chunks(self, chunks: list[dict]):
        with self.conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO documentos (contenido, fuente, tipo, origen, chunk_id, embedding)
                   VALUES (%(contenido)s, %(fuente)s, %(tipo)s, %(origen)s, %(chunk_id)s, %(embedding)s)""",
                [{**c, "embedding": _vec(c["embedding"])} for c in chunks],
            )

    def buscar_similares(self, query_embedding: list[float], top_k: int = 5) -> list[dict]:
        # <=> es distancia coseno en pgvector, similitud = 1 - distancia
        rows = self.conn.execute(
            """SELECT contenido, fuente, tipo, origen, 1 - (embedding <=> %s) AS score
               FROM documentos
               ORDER BY embedding <=> %s
               LIMIT %s""",
            (_vec(query_embedding), _vec(query_embedding), top_k),
        ).fetchall()
        return [
            {"contenido": r[0], "fuente": r[1], "tipo": r[2], "origen": r[3], "score": float(r[4])}
            for r in rows
        ]

    def contar_por_fuente(self) -> dict:
        rows = self.conn.execute("SELECT fuente, COUNT(*) FROM documentos GROUP BY fuente ORDER BY fuente").fetchall()
        return {r[0]: r[1] for r in rows}

    def guardar_interaccion(self, datos: dict):
        self.conn.execute(
            """INSERT INTO interacciones (session_id, pregunta, respuesta, fuentes, prompt_version,
                                          modelo, prompt_tokens, completion_tokens, latencia_ms)
               VALUES (%(session_id)s, %(pregunta)s, %(respuesta)s, %(fuentes)s, %(prompt_version)s,
                       %(modelo)s, %(prompt_tokens)s, %(completion_tokens)s, %(latencia_ms)s)""",
            {**datos, "fuentes": json.dumps(datos.get("fuentes", []), ensure_ascii=False)},
        )


def _vec(embedding):
    import numpy as np
    return np.array(embedding, dtype="float32")
