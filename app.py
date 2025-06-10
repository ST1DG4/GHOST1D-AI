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
        if response.status_code == 200:
            return response.content
        else: return None
    except Exception: return None

# --- INTERFAZ DE USUARIO (SIDEBAR) ---
with st.sidebar:
    st.title("🚀 GhoStid AI"); st.caption("Tu tutor de programación personal.")
    st.header("Opciones de Entrada")
    if st.button("🎤 Hablar", use_container_width=True):
        try: st.session_state.user_input_from_voice = listen_to_user()
        except Exception: st.session_state.mic_error = True
    uploaded_file = st.file_uploader("📄 Adjuntar un Archivo", type=["png", "jpg", "jpeg", "txt", "py", "md", "csv"])
    if uploaded_file is not None:
        file_extension = os.path.splitext(uploaded_file.name)[1]
        if file_extension in [".png", ".jpg", ".jpeg"]:
            st.session_state.file_context = {"type": "image", "content": Image.open(uploaded_file), "name": uploaded_file.name}
        else:
            try: content = uploaded_file.getvalue().decode("utf-8"); st.session_state.file_context = {"type": "text", "content": content, "name": uploaded_file.name}
            except Exception: st.sidebar.error("No se pudo leer el archivo.")
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

# --- ÁREA PRINCIPAL Y LÓGICA DEL AGENTE ---
if "messages" not in st.session_state: st.session_state.messages = []
if st.session_state.get("mic_error"):
    st.error("❌ Error de Micrófono."); st.warning("Revisa los permisos del micrófono en tu navegador y sistema.");
    if st.button("🔄 Volver"): st.session_state.mic_error = False; st.rerun()

# Mostramos la bienvenida solo si no hay mensajes
if not st.session_state.messages:
    st.chat_message("assistant", avatar=st.session_state.get('assistant_avatar', '🤖')).markdown("¡Hola! Soy GhoStid AI. Puedes hacerme una pregunta o adjuntar un archivo para analizarlo.")

# Mostramos el historial de chat
for msg in st.session_state.messages:
    static_avatar = st.session_state.get('assistant_avatar', '🤖') if msg["role"] == "assistant" else st.session_state.get('user_avatar', '🧑‍💻')
    with st.chat_message(msg["role"], avatar=static_avatar):
        gif_to_show = st.session_state.get('assistant_gif') if msg["role"] == "assistant" else st.session_state.get('user_gif')
        if gif_to_show: st.image(gif_to_show, width=120)
        st.markdown(msg["content"])
        if msg.get("audio"): st.audio(msg["audio"], format='audio/mpeg', start_time=0)

# Obtenemos la nueva entrada del usuario
user_input_text = st.chat_input("Escribe tu pregunta o pídemelo...")
user_input_voice = st.session_state.pop('user_input_from_voice', None)
user_input = user_input_text or user_input_voice

if user_input:
    # Guardamos y mostramos la entrada del usuario
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user", avatar=st.session_state.get('user_avatar', '🧑‍💻')):
        if st.session_state.get('user_gif'): st.image(st.session_state.get('user_gif'), width=120)
        st.markdown(user_input)
    
    # Procesamos la respuesta del asistente
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest", temperature=0, google_api_key=GOOGLE_API_KEY)
    
    with st.spinner("GhoStid AI está pensando..."):
        if st.session_state.get("file_context"):
            file_context = st.session_state.pop("file_context")
            if file_context["type"] == "image":
                human_message = HumanMessage(content=[{"type": "text", "text": user_input}, {"type": "image_url", "image_url": file_context["content"]}])
                response = llm.invoke([human_message]); response_text = response.content
            else:
                prompt_with_context = f"{user_input}\n\n**Contexto del archivo '{file_context['name']}':**\n```\n{file_context['content']}\n```"
                tools = [PythonREPLTool(), TavilySearchResults(k=3)]; prompt_template = hub.pull("hwchase17/react"); agent = create_react_agent(llm, tools, prompt_template); agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, handle_parsing_errors=True, max_iterations=5)
                response_object = agent_executor.invoke({"input": prompt_with_context}); response_text = response_object['output']
        else:
            tools = [PythonREPLTool(), TavilySearchResults(k=3)]; prompt_template = hub.pull("hwchase17/react"); agent = create_react_agent(llm, tools, prompt_template); agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, handle_parsing_errors=True, max_iterations=5)
            response_object = agent_executor.invoke({"input": f"Responde en español a: {user_input}"}); response_text = response_object['output']

        assistant_message = {"role": "assistant", "content": response_text}
        
        # Generamos y guardamos el audio
        if st.session_state.voice_enabled and st.session_state.voices_map:
            speakable_text = extract_speakable_text(response_text)
            if speakable_text:
                selected_voice_id = st.session_state.voices_map[st.session_state.selected_voice_name]
                audio_bytes = speak_response_cloud(speakable_text, selected_voice_id)
                if audio_bytes:
                    assistant_message["audio"] = audio_bytes
        
        # Guardamos el mensaje completo del asistente
        st.session_state.messages.append(assistant_message)
        
        # --- ¡¡LA CORRECCIÓN FINAL!! ---
        # En lugar de recargar, simplemente forzamos a Streamlit a
        # volver a dibujar la pantalla con la nueva información.
        st.experimental_rerun()
