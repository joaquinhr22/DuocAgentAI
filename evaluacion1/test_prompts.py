import pytest

from prompts.prompt import (MENSAJE_FUERA_DE_DOMINIO, PROMPTS, construir_system_prompt,
                            extraer_respuesta_final)


@pytest.mark.parametrize("version", list(PROMPTS))
def test_prompt_incluye_contexto_fecha_y_reglas(version):
    p = construir_system_prompt(version, "CONTEXTO_DE_PRUEBA", "21 de octubre de 2026")
    assert "CONTEXTO_DE_PRUEBA" in p
    assert "21 de octubre de 2026" in p
    assert MENSAJE_FUERA_DE_DOMINIO in p
    assert "{" not in p  # no quedaron placeholders sin reemplazar


def test_few_shot_tiene_ejemplos_y_zero_shot_no():
    assert "EJEMPLOS" in construir_system_prompt("few_shot", "", "hoy")
    assert "EJEMPLOS" not in construir_system_prompt("zero_shot", "", "hoy")


def test_version_invalida():
    with pytest.raises(ValueError):
        construir_system_prompt("no_existe", "", "hoy")


def test_extraer_respuesta_final_cot():
    texto = "Razonamiento: el contexto dice 180.\nRespuesta final: Son 180 horas."
    assert extraer_respuesta_final(texto) == "Son 180 horas."
    assert extraer_respuesta_final("sin marcador") == "sin marcador"
