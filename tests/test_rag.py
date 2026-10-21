"""Tests del flujo completo con la BD real (pgvector) y un LLM falso."""
from conftest import FakeLLM

from src.generate.generate import RAGGenerator, formatear_contexto
from src.retrieval.retrieval import Retriever

CHUNKS = [
    ("TIPO: Práctica Laboral. Duración: 180 horas. Se realiza cerca del cuarto semestre.", "practicas"),
    ("Inicio de clases del segundo semestre: 10-08-2026. Calendario académico.", "calendario_academico"),
    ("Artículo N°30. La asistencia mínima para aprobar es la definida en el reglamento.", "reglamento_academico"),
]


def _cargar(db, emb):
    db.insertar_chunks([
        {"contenido": c, "fuente": f, "tipo": "interna", "origen": f + ".pdf", "chunk_id": i,
         "embedding": emb.get_embedding(c)}
        for i, (c, f) in enumerate(CHUNKS)
    ])


def test_insertar_y_contar(db, fake_embedder):
    _cargar(db, fake_embedder)
    assert db.contar_por_fuente() == {"calendario_academico": 1, "practicas": 1, "reglamento_academico": 1}
    assert db.origen_ya_ingestado("practicas.pdf")
    db.borrar_origen("practicas.pdf")
    assert not db.origen_ya_ingestado("practicas.pdf")


def test_busqueda_vectorial_trae_el_chunk_correcto(db, fake_embedder):
    _cargar(db, fake_embedder)
    retriever = Retriever(db=db, embedder=fake_embedder, usar_reranker=False)
    resultados = retriever.retrieve("¿Cuántas horas dura la práctica laboral?", top_k=2)
    assert resultados[0]["fuente"] == "practicas"
    assert resultados[0]["score"] >= resultados[1]["score"]


def test_generate_arma_prompt_con_contexto_y_guarda_interaccion(db, fake_embedder):
    _cargar(db, fake_embedder)
    llm = FakeLLM()
    rag = RAGGenerator(prompt_version="few_shot",
                       retriever=Retriever(db=db, embedder=fake_embedder, usar_reranker=False), llm=llm)
    historial = [{"role": "user", "content": "hola"}, {"role": "assistant", "content": "hola!"}]
    r = rag.generate("¿horas de práctica laboral?", history=historial, top_k=2, session_id="test")

    assert r["answer"] == llm.respuesta
    assert "180 horas" in llm.ultimo_system_prompt          # el contexto llego al prompt
    assert llm.ultimos_mensajes[-1]["content"] == "¿horas de práctica laboral?"
    assert len(llm.ultimos_mensajes) == 3                    # historial + pregunta
    fila = db.conn.execute("SELECT pregunta, prompt_version, modelo FROM interacciones").fetchone()
    assert fila == ("¿horas de práctica laboral?", "few_shot", "fake-llm")


def test_formatear_contexto_indica_fuente_y_tipo():
    ctx = formatear_contexto([{"contenido": "abc", "fuente": "web_wikipedia.org", "tipo": "externa"}])
    assert "Fuente: web_wikipedia.org (externa)" in ctx


def test_ingesta_de_los_pdfs_reales(db, fake_embedder, monkeypatch, tmp_path):
    """Carga los 3 PDFs de data/internos (sin fuentes web) y revisa que queden en la BD."""
    from pathlib import Path
    import pytest
    from src import config
    from src.ingesta.ingest import Ingestor

    if len(list(Path(config.CARPETA_INTERNOS).glob("*.pdf"))) < 3:
        pytest.skip("faltan los PDFs en data/internos")
    sin_urls = tmp_path / "fuentes.txt"
    sin_urls.write_text("# sin urls\n", encoding="utf-8")
    monkeypatch.setattr(config, "ARCHIVO_EXTERNOS", str(sin_urls))

    ingestor = Ingestor(db=db, embedder=fake_embedder)
    ingestor.ingestar_todo()
    conteo = db.contar_por_fuente()
    assert set(conteo) == {"calendario_academico", "practicas", "reglamento_academico"}
    assert conteo["reglamento_academico"] > 50

    # si se corre de nuevo no se duplica nada
    ingestor.ingestar_todo()
    assert db.contar_por_fuente() == conteo
