import uuid
import streamlit as st

from prompts.prompt import PROMPTS
from src import config
from src.generate.generate import RAGGenerator

st.set_page_config(page_title="Orientador Duoc", page_icon="🎓", layout="wide")
st.title("🎓 Orientador Duoc")
st.caption("Asistente para estudiantes nuevos: prácticas, calendario académico y reglamento. "
           f"Modelo: {config.GROQ_MODEL} (Groq) + RAG sobre PostgreSQL/pgvector")

# --- Sidebar ---
with st.sidebar:
    st.header("Configuración")
    versiones = list(PROMPTS)
    prompt_version = st.selectbox("Versión del prompt", versiones, index=versiones.index(config.PROMPT_VERSION))
    mostrar_fuentes = st.checkbox("Mostrar fragmentos recuperados", value=True)

    st.divider()
    if st.button("Nueva conversación"):
        st.session_state.history = []
        st.session_state.session_id = str(uuid.uuid4())
        st.rerun()

    st.divider()
    st.markdown("**Preguntas de ejemplo**")
    st.markdown("- ¿Cuántas horas dura la práctica laboral?\n"
                "- ¿Cuándo empieza el segundo semestre?\n"
                "- ¿Qué pasa si repruebo una asignatura dos veces?\n"
                "- ¿Qué porcentaje de asistencia necesito?")

# --- Session state ---
if "history" not in st.session_state:
    st.session_state.history = []
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "rag" not in st.session_state or st.session_state.rag.prompt_version != prompt_version:
    st.session_state.rag = RAGGenerator(prompt_version=prompt_version)

# --- Chat ---
for message in st.session_state.history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if query := st.chat_input("Escribe tu pregunta..."):
    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        with st.spinner("Buscando en los documentos..."):
            response = st.session_state.rag.generate(
                query=query,
                history=st.session_state.history,
                session_id=st.session_state.session_id,
            )
        st.markdown(response["answer"])

        if mostrar_fuentes:
            with st.expander("Fuentes recuperadas"):
                for s in response["sources"]:
                    st.markdown(f"**{s['fuente']}** ({s['tipo']}) · score {s['score']} · `{s['origen']}`")
                    st.text(s["contenido"][:500] + ("..." if len(s["contenido"]) > 500 else ""))
            with st.expander("Tokens y latencia"):
                st.write(f"Prompt: {response['prompt_tokens']} | Respuesta: {response['completion_tokens']} | "
                         f"Total: {response['total_tokens']} | Latencia: {response['latencia_ms']} ms")
            if prompt_version == "cot":
                with st.expander("Razonamiento (CoT)"):
                    st.text(response["raw_answer"])

    st.session_state.history.append({"role": "user", "content": query})
    st.session_state.history.append({"role": "assistant", "content": response["answer"]})
