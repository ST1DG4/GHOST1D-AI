import streamlit as st
import os
from PIL import Image
from dotenv import load_dotenv
import requests
import io
import re

# --- IMPORTACIONES ---
# Hemos eliminado pydub y simpleaudio, ya no son necesarios para la reproducción
from langchain_google_genai import ChatGoogleGenerativeAI
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
if not ELEVENLABS_API_KEY:
    st.error("Error crítico: La clave de API de ElevenLabs no se encontró.")
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

# --- FUNCIÓN DE VOZ SIMPLIFICADA PARA LA NUBE ---
def speak_response_cloud(text_to_speak, voice_id):
    """
    Genera audio y lo muestra en un reproductor de Streamlit.
    """
    TTS_URL = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {"Accept": "audio/mpeg", "Content-Type": "application/json", "xi-api-key": ELEVENLABS_API_KEY}
    data = {"text": text_to_speak, "model_id": "eleven_multilingual_v2"}

    try:
        response = requests.post(TTS_URL, json=data, headers=headers)
        if response.status_code == 200:
            # La función nativa de Streamlit para mostrar audio.
            st.audio(response.content, format='audio/mpeg', start_time=0)
        else:
            st.error(f"Error de API de ElevenLabs: {response.text}")
    except Exception as e:
        st.error(f"Error al procesar el audio: {e}")

# --- ELIMINADO: La función stop_speaking() ya no es necesaria ---

# --- INTERFAZ DE USUARIO (SIDEBAR) ---
with st.sidebar:
    st.title("🚀 GhoStid AI"); st.caption("Tu tutor de programación personal.")
    st.header("Opciones de Entrada")
    if st.button("🎤 Hablar", use_container_width=True):
        try: st.session_state.user_input_from_voice = listen_to_user(); st.rerun()
        except OSError: st.session_state.mic_error = True; st.rerun()

    st.header("Configuración de Voz")
    st.session_state.voice_enabled = st.toggle("Activar voz", value=True)
    if st.session_state.voices_map:
        voice_names = list(st.session_state.voices_map.keys())
        st.session_state.selected_voice_name = st.selectbox("Voz del Asistente:", options=voice_names, index=voice_names.index("Rachel") if "Rachel" in voice_names else 0)

    with st.expander("🎨 Personalización Visual"):
        format_func = lambda x: "Ninguno" if x is None else os.path.basename(x).split('.')[0].replace('_', ' ').title()
        if st.session_state.static_avatars:
            st.session_state.assistant_avatar = st.selectbox("Avatar Estático (Asistente):", options=st.session_state.static_avatars, format_func=format_func)
            st.session_state.user_avatar = st.selectbox("Avatar Estático (Usuario):", options=st.session_state.static_avatars, index=min(1, len(st.session_state.static_avatars) - 1), format_func=format_func)
        else: st.session_state.assistant_avatar = '🤖'; st.session_state.user_avatar = '🧑‍💻'
        if st.session_state.animated_avatars:
            st.session_state.assistant_gif = st.selectbox("Avatar Animado (Asistente):", options=[None] + st.session_state.animated_avatars, format_func=format_func)
            st.session_state.user_gif = st.selectbox("Avatar Animado (Usuario):", options=[None] + st.session_state.animated_avatars, format_func=format_func)
        else: st.session_state.assistant_gif = None; st.session_state.user_gif = None

    # --- ELIMINADO: El botón "Detener Voz" ya no es necesario ---
    
    st.markdown("---")
    st.image("GHOSTID_LOGO.png", use_container_width=True)
    st.markdown("<p style='text-align: center;'>STIDGAR</p>", unsafe_allow_html=True)

# --- ÁREA PRINCIPAL Y LÓGICA DEL AGENTE ---
if st.session_state.get("mic_error"):
    st.error("❌ Error de Micrófono."); st.warning("Revisa la configuración de sonido y privacidad de Windows.");
    if st.button("🔄 Volver"): st.session_state.mic_error = False; st.rerun()
else:
    if "messages" not in st.session_state: st.session_state.messages = [{"role": "assistant", "content": "¡Hola! Soy GhoStid AI. ¿En qué te ayudo?"}]
    # --- Modificación: lógica de visualización de mensajes para el audio ---
    for message in st.session_state.messages:
        static_avatar = st.session_state.get('assistant_avatar', '🤖') if message["role"] == "assistant" else st.session_state.get('user_avatar', '🧑‍💻')
        with st.chat_message(message["role"], avatar=static_avatar):
            gif_to_show = st.session_state.get('assistant_gif') if message["role"] == "assistant" else st.session_state.get('user_gif')
            if gif_to_show: st.image(gif_to_show, width=120)
            st.markdown(message["content"])
            # Si el mensaje tiene audio guardado, lo mostramos
            if message.get("audio"):
                st.audio(message["audio"], format='audio/mpeg', start_time=0)

    if prompt := st.chat_input("Escribe tu pregunta o pídemelo..."):
        st.session_state.user_input_from_voice = None; st.session_state.user_input_from_text = prompt
    user_input = st.session_state.get('user_input_from_text') or st.session_state.get('user_input_from_voice')
    if user_input:
        st.session_state.user_input_from_text = None; st.session_state.user_input_from_voice = None; st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user", avatar=st.session_state.get('user_avatar', '🧑‍💻')):
            if st.session_state.get('user_gif'): st.image(st.session_state.get('user_gif'), width=120)
            st.markdown(user_input)
        
        llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest", temperature=0); tools = [PythonREPLTool(), TavilySearchResults(k=3)]; prompt_template = hub.pull("hwchase17/react"); agent = create_react_agent(llm, tools, prompt_template); agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, handle_parsing_errors=True, max_iterations=5)
        
        with st.chat_message("assistant", avatar=st.session_state.get('assistant_avatar', '🤖')):
            with st.spinner("GhoStid AI está pensando..."):
                response_object = agent_executor.invoke({"input": f"Responde en español a: {user_input}"}); response_text = response_object['output']
                if st.session_state.get('assistant_gif'): st.image(st.session_state.get('assistant_gif'), width=120)
                st.markdown(response_text)

                assistant_message = {"role": "assistant", "content": response_text}
                
                if st.session_state.voice_enabled and st.session_state.voices_map:
                    speakable_text = extract_speakable_text(response_text)
                    if speakable_text:
                        with st.spinner("Generando voz para la nube..."):
                            selected_voice_id = st.session_state.voices_map[st.session_state.selected_voice_name]
                            
                            # Generamos el audio directamente aquí para poder guardarlo y mostrarlo
                            TTS_URL = f"https://api.elevenlabs.io/v1/text-to-speech/{selected_voice_id}"
                            headers = {"Accept": "audio/mpeg", "Content-Type": "application/json", "xi-api-key": ELEVENLABS_API_KEY}
                            data = {"text": speakable_text, "model_id": "eleven_multilingual_v2"}
                            response = requests.post(TTS_URL, json=data, headers=headers)
                            if response.status_code == 200:
                                audio_bytes = response.content
                                st.audio(audio_bytes, format='audio/mpeg', start_time=0)
                                assistant_message["audio"] = audio_bytes
                            else:
                                st.error("Error al generar audio.")

                st.session_state.messages.append(assistant_message)
                st.rerun()
