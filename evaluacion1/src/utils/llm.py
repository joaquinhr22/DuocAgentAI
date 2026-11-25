from groq import Groq
from src import config


class GroqLLM:
    """Cliente del LLM. Usamos Llama 3.1 8B servido por Groq (gratis y rapido)."""

    def __init__(self, model: str = config.GROQ_MODEL, temperature: float = config.TEMPERATURA):
        if not config.GROQ_API_KEY:
            raise ValueError("Falta GROQ_API_KEY en el .env")
        self.model = model
        self.temperature = temperature
        self.client = Groq(api_key=config.GROQ_API_KEY)

    def generate(self, system_prompt: str, messages: list[dict]) -> dict:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system_prompt}] + messages,
            temperature=self.temperature,
        )
        return {
            "answer": response.choices[0].message.content,
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
        }
