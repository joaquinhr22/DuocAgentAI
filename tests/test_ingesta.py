from src.ingesta.ingest import (CONFIG_DEFAULT, config_para_archivo, dividir_en_chunks,
                                leer_fuentes_externas, limpiar_texto)


def test_limpiar_texto_une_palabras_sueltas_de_pypdf():
    # asi salia el calendario en el notebook
    crudo = "FUENTE\n \nDE\n \nCONOCIMIENTO:\n \nCALENDARIO\n \n \nINSTITUCIÓN:\n \nDuoc\n \nUC"
    limpio = limpiar_texto(crudo)
    assert "FUENTE DE CONOCIMIENTO: CALENDARIO" in limpio
    assert "\n\nINSTITUCIÓN: Duoc UC" in limpio


def test_limpiar_texto_no_rompe_texto_normal():
    texto = "Artículo N°1. El presente reglamento\nregula la vida académica."
    assert limpiar_texto(texto) == texto


def test_config_por_nombre_de_archivo():
    assert config_para_archivo("NUEVO-REGLAMENTO-ACADEMICO_20260525.pdf")["fuente"] == "reglamento_academico"
    assert config_para_archivo("calendario DuocUC.pdf")["fuente"] == "calendario_academico"
    assert config_para_archivo("Horas de practica duocUc.pdf")["fuente"] == "practicas"
    assert config_para_archivo("otro.pdf") == CONFIG_DEFAULT


def test_chunks_respetan_tamano_y_cortan_por_articulo():
    cfg = config_para_archivo("reglamento.pdf")
    texto = "\n".join(f"Artículo N°{i}. " + "texto del artículo " * 30 for i in range(1, 10))
    chunks = dividir_en_chunks(texto, cfg)
    assert len(chunks) > 1
    assert all(len(c) <= cfg["chunk_size"] for c in chunks)
    assert sum(c.startswith("Artículo N°") for c in chunks) >= len(chunks) - 1


def test_chunks_descarta_fragmentos_muy_cortos():
    assert dividir_en_chunks("12", CONFIG_DEFAULT) == []


def test_leer_fuentes_externas_ignora_comentarios(tmp_path):
    f = tmp_path / "fuentes.txt"
    f.write_text("# comentario\n\nhttps://a.cl\n  https://b.cl  \n", encoding="utf-8")
    assert leer_fuentes_externas(str(f)) == ["https://a.cl", "https://b.cl"]
    assert leer_fuentes_externas(str(tmp_path / "no_existe.txt")) == []


def test_calendario_cada_chunk_lleva_su_seccion_y_se_ignoran_reglas():
    from src.ingesta.ingest import CONFIG_FUENTES
    texto = ("FUENTE DE CONOCIMIENTO: CALENDARIO ACADÉMICO DUOC UC 2026 - documento de prueba para tests\n\n"
             "===================== PRIMER SEMESTRE 2026 (2026-1) =====================\n\n"
             "Período Ordinario de Inscripción de Asignaturas: Inicio: 13-01-2026. Término: 15-01-2026.\n\n"
             "===================== SEGUNDO SEMESTRE 2026 (2026-2) =====================\n\n"
             "Período Ordinario de Inscripción de Asignaturas: Inicio: 27-07-2026. Término: 30-07-2026.\n\n"
             "===================== REGLAS DE INTERPRETACIÓN PARA EL AGENTE =====================\n\n"
             "1. Todas las fechas corresponden al Calendario Académico Duoc UC 2026 y no se deben inventar.")
    chunks = dividir_en_chunks(texto, CONFIG_FUENTES["calendario"])
    assert len(chunks) == 3
    assert chunks[1].startswith("[PRIMER SEMESTRE 2026 (2026-1)]") and "13-01-2026" in chunks[1]
    assert chunks[2].startswith("[SEGUNDO SEMESTRE 2026 (2026-2)]") and "27-07-2026" in chunks[2]
    assert not any("REGLAS DE INTERPRETACIÓN" in c for c in chunks)


def test_preparar_reglamento_separa_articulos_pegados():
    from src.ingesta.ingest import preparar_reglamento
    texto = "para tales efectos. Artículo N°30. La asistencia... según el artículo N°29. Artículo N°45 . Un estudiante"
    r = preparar_reglamento(texto)
    assert "\n\nArtículo N°30." in r
    assert "\n\nArtículo N°45 ." in r
    assert "el artículo N°29." in r  # referencias en minuscula no se cortan
