from types import SimpleNamespace

from agente import config, metricas


def test_calcular_costo(monkeypatch):
    monkeypatch.setattr(config, "PRICE_INPUT_PER_1M", 0.10)
    monkeypatch.setattr(config, "PRICE_OUTPUT_PER_1M", 0.50)
    assert metricas.calcular_costo(1_000_000, 1_000_000) == 0.60


def test_contador_tokens_suma_uso(monkeypatch):
    monkeypatch.setattr(config, "PRICE_INPUT_PER_1M", 1.0)
    monkeypatch.setattr(config, "PRICE_OUTPUT_PER_1M", 2.0)
    antes = metricas.COSTO_USD._value.get()
    msg = SimpleNamespace(usage_metadata={"input_tokens": 100, "output_tokens": 50})
    resp = SimpleNamespace(generations=[[SimpleNamespace(message=msg)]], llm_output=None)
    metricas.ContadorTokens().on_llm_end(resp)
    assert round(metricas.COSTO_USD._value.get() - antes, 9) == round((100 * 1 + 50 * 2) / 1_000_000, 9)
