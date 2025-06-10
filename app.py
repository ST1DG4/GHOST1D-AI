import streamlit as st
import os
from PIL import Image
from dotenv import load_dotenv
import requests
import io
import re

# --- IMPORTACIONES ---
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from langchain.agents import AgentExecutor, create_react_agent
from langchain_experimental.tools import PythonREPLTool
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain import hub
import speech_recognition as sr

# --- CONFIGURACIÓN INICIAL ---
load_dotenv()
st.set_page_config(page_title="GhoStid AI", layout="wide", page_icon="🤖")

# --- OBTENER CLAVE API ---
ELEVENLABS_API_KEY = os.environ.get("ELEVEN_API_KEY")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

if not ELEVENLABS_API_KEY or not GOOGLE_API_KEY:
    st.error("Error crítico: Faltan claves de API. Revisa tus secretos en Streamlit Cloud.")
    st.stop()

# --- FUNCIONES DE CARGA Y HABILIDADES ---
@st.cache_data
def load_assets(asset_dir):
    if not os.path.exists(asset_dir): return []
    return [os.path.join(asset_dir, f) for f in os.listdir(asset_dir)]

@st.cache_data
def get_available_voices():
    headers = {"xi-api-key": ELEVENLABS_API_KEY}; url = "https://api.elevenlabs.io/v1/voices"
    try:
        response = requests.get(url, headers=headers)
        return {voice['name']: voice['voice_id'] for voice in response.json()['voices']} if response.status_code == 200 else {}
    except Exception: return {}

if 'voices_map' not in st.session_state: st.session_state.voices_map = get_available_voices()
if 'static_avatars' not in st.session_state: st.session_state.static_avatars = load_assets("avatars")
if 'animated_avatars' not in st.session_state: st.session_state.animated_avatars = load_assets("animated_avatars")
if "messages" not in st.session_state: st.session_state.messages = []

def listen_to_user():
    r = sr.Recognizer();
    with sr.Microphone() as source: st.info("Escuchando..."); r.adjust_for_ambient_noise(source); audio = r.listen(source)
    try: query = r.recognize_google(audio, language='es-ES'); st.success(f"Has dicho: {query}"); return query
    except Exception: st.error("No te he entendido."); return None

def extract_speakable_text(text):
    text = re.sub(r'```.*?```', '', text, flags=re.DOTALL); text = text.replace('*', '').replace('`', ''); return ' '.join(text.split())

def speak_response_cloud(text_to_speak, voice_id):
    TTS_URL = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {"Accept": "audio/mpeg", "Content-Type": "application/json", "xi-api-key": ELEVENLABS_API_KEY}
    data = {"text": text_to_speak, "model_id": "eleven_multilingual_v2"}
    try:
        response = requests.post(TTS_URL, json=data, headers=headers)
        if response.status_code == 200: return response.content
        else: return None
    except Exception: return None

# --- INTERFAZ DE USUARIO (SIDEBAR) ---
with st.sidebar:
    st.title("🚀 GhoStid AI"); st.caption("Tu tutor de programación personal.")
    st.header("Opciones de Entrada")
    if st.button("🎤 Hablar", use_container_width=True):
        st.session_state.user_input = listen_to_user()
    uploaded_file = st.file_uploader("📄 Adjuntar Archivo", type=["png", "jpg", "jpeg", "txt", "py", "md", "csv"])
    if uploaded_file: st.session_state.uploaded_file = uploaded_file

    st.header("Configuración")
    st.session_state.voice_enabled = st.toggle("Activar voz", value=True)
    if st.session_state.voices_map:
        voice_names = list(st.session_state.voices_map.keys())
        st.session_state.selected_voice_name = st.selectbox("Voz del Asistente:", options=voice_names, index=voice_names.index("Rachel") if "Rachel" in voice_names else 0)
    with st.expander("🎨 Personalización Visual"):
        format_func = lambda x: "Ninguno" if x is None else os.path.basename(x).split('.')[0].replace('_', ' ').title()
        if st.session_state.static_avatars:
            st.session_state.assistant_avatar = st.selectbox("Avatar Estático (Asistente):", options=st.session_state.static_avatars, format_func=format_func)
            st.session_state.user_avatar = st.selectbox("Avatar Estático (Usuario):", options=st.session_state.static_avatars, index=min(1, len(st.session_state.static_avatars) - 1), format_func=format_func)
        if st.session_state.animated_avatars:
            st.session_state.assistant_gif = st.selectbox("Avatar Animado (Asistente):", options=[None] + st.session_state.animated_avatars, format_func=format_func)
            st.session_state.user_gif = st.selectbox("Avatar Animado (Usuario):", options=[None] + st.session_state.animated_avatars, format_func=format_func)
    st.markdown("---"); st.image("GHOSTID_LOGO.png", use_container_width=True); st.markdown("<p style='text-align: center;'>STIDGAR</p>", unsafe_allow_html=True)

# --- ÁREA PRINCIPAL ---

# Muestra la bienvenida solo si el historial está vacío
if not st.session_state.messages:
    with st.chat_message("assistant", avatar=st.session_state.get('assistant_avatar', '🤖')):
        st.markdown("¡Hola! Soy GhoStid AI. Puedes hacerme una pregunta o adjuntar un archivo para analizarlo.")

# Muestra todo el historial de chat existente
for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar=st.session_state.get('assistant_avatar', '🤖') if msg["role"] == "assistant" else st.session_state.get('user_avatar', '🧑‍💻')):
        st.markdown(msg["content"])
        if msg.get("audio"):
            st.audio(msg["audio"], format='audio/mpeg', start_time=0)

# Obtiene la nueva entrada del usuario
prompt = st.chat_input("Escribe tu pregunta o pídemelo...")
if st.session_state.get('user_input'):
    prompt = st.session_state.pop('user_input')

# Si hay una nueva entrada, se inicia el ciclo de procesamiento
if prompt:
    # Añade y muestra el mensaje del usuario inmediatamente
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar=st.session_state.get('user_avatar', '🧑‍💻')):
        st.markdown(prompt)
    
    # Procesa y muestra la respuesta del asistente en su propia burbuja
    with st.chat_message("assistant", avatar=st.session_state.get('assistant_avatar', '🤖')):
        with st.spinner("GhoStid AI está pensando..."):
            llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest", temperature=0, google_api_key=GOOGLE_API_KEY)
            
            if st.session_state.get("uploaded_file"):
                uploaded_file = st.session_state.pop("uploaded_file")
                file_extension = os.path.splitext(uploaded_file.name)[1]
                if file_extension in [".png", ".jpg", ".jpeg"]:
                    image = Image.open(uploaded_file)
                    human_message = HumanMessage(content=[{"type": "text", "text": prompt}, {"type": "image_url", "image_url": image}])
                    response = llm.invoke([human_message]); response_text = response.content
                else:
                    content = uploaded_file.getvalue().decode("utf-8")
                    prompt_with_context = f"{prompt}\n\n**Contexto del archivo '{uploaded_file.name}':**\n```\n{content}\n```"
                    tools = [PythonREPLTool(), TavilySearchResults(k=3)]; prompt_template = hub.pull("hwchase17/react"); agent = create_react_agent(llm, tools, prompt_template); agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, handle_parsing_errors=True, max_iterations=5)
                    response_object = agent_executor.invoke({"input": prompt_with_context}); response_text = response_object['output']
            else:
                tools = [PythonREPLTool(), TavilySearchResults(k=3)]; prompt_template = hub.pull("hwchase17/react"); agent = create_react_agent(llm, tools, prompt_template); agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, handle_parsing_errors=True, max_iterations=5)
                response_object = agent_executor.invoke({"input": f"Responde en español a: {prompt}"}); response_text = response_object['output']
            
            # Muestra el texto de la respuesta
            st.markdown(response_text)
            
            # Genera, MUESTRA y guarda el audio
            audio_bytes = None
            if st.session_state.voice_enabled and st.session_state.voices_map:
                speakable_text = extract_speakable_text(response_text)
                if speakable_text:
                    selected_voice_id = st.session_state.voices_map[st.session_state.selected_voice_name]
                    audio_bytes = speak_response_cloud(speakable_text, selected_voice_id)
                    if audio_bytes:
                        st.audio(audio_bytes, format='audio/mpeg', start_time=0)
            
            # Guarda el mensaje completo en el historial para la próxima vez
            st.session_state.messages.append({"role": "assistant", "content": response_text, "audio": audio_bytes})
