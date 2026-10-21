import argparse
from src.ingesta.ingest import Ingestor

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Carga los documentos a PostgreSQL (pgvector)")
    parser.add_argument("--reset", action="store_true", help="borra lo que habia y vuelve a cargar")
    args = parser.parse_args()
    Ingestor().ingestar_todo(reset=args.reset)
