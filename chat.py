"""Chat por consola (igual que los scripts de la clase 1.3). Uso: python chat.py"""
from src.generate.generate import RAGGenerator

if __name__ == "__main__":
    rag = RAGGenerator()
    history = []
    print(f"Orientador Duoc (prompt: {rag.prompt_version}). Escribe 'salir' para terminar.\n")
    while True:
        query = input("Tú: ").strip()
        if not query or query.lower() in ("salir", "exit", "quit"):
            break
        r = rag.generate(query, history)
        print(f"\nAgente: {r['answer']}")
        print(f"  (fuentes: {', '.join(sorted({s['fuente'] for s in r['sources']}))} | "
              f"{r['total_tokens']} tokens | {r['latencia_ms']} ms)\n")
        history += [{"role": "user", "content": query}, {"role": "assistant", "content": r["answer"]}]
