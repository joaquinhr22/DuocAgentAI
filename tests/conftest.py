import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class FakeEmbedder:
    """Embedder falso para no cargar sentence-transformers en los tests.
    Cuenta palabras clave, asi textos parecidos quedan con vectores parecidos."""
    PALABRAS = ["practica", "laboral", "profesional", "horas", "calendario", "semestre",
                "clases", "feriado", "reglamento", "articulo", "asistencia", "nota"]

    def get_embedding(self, text):
        t = text.lower().replace("á", "a").replace("í", "i").replace("é", "e")
        v = [float(t.count(p)) for p in self.PALABRAS]
        v += [0.0] * (384 - len(v))
        v[-1] = 0.01  # para que nunca sea el vector cero
        return v

    def get_embeddings(self, texts):
        return [self.get_embedding(t) for t in texts]


class FakeLLM:
    model = "fake-llm"

    def __init__(self, respuesta="Respuesta de prueba [Fuente: practicas]"):
        self.respuesta = respuesta
        self.ultimo_system_prompt = None
        self.ultimos_mensajes = None

    def generate(self, system_prompt, messages):
        self.ultimo_system_prompt = system_prompt
        self.ultimos_mensajes = messages
        return {"answer": self.respuesta, "prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}


@pytest.fixture
def fake_embedder():
    return FakeEmbedder()


@pytest.fixture
def db():
    """BD real de pruebas. Si no hay PostgreSQL disponible el test se salta."""
    from src.utils.postgres import PostgresClient
    url = os.getenv("TEST_DATABASE_URL", os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/duoc_agent"))
    try:
        client = PostgresClient(url)
    except Exception as e:
        pytest.skip(f"PostgreSQL no disponible: {e}")
    client.conn.execute("DROP TABLE IF EXISTS documentos, interacciones")
    client.crear_tablas()
    yield client
    client.conn.execute("DROP TABLE IF EXISTS documentos, interacciones")
