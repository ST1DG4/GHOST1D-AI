import streamlit as st
import os
from PIL import Image
from dotenv import load_dotenv
import requests
import io
import re
import cv2  # La librería para "ver" video
import numpy as np # Necesaria para procesar las imágenes del video
import base64

# --- IMPORTACIONES DE LANGCHAIN Y DEMÁS ---
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

# --- FUNCIONES DE CARGA Y HABILIDADES ---
@st.cache_data
def load_assets(asset_dir):
    # ... (sin cambios)
    if not os.path.exists(asset_dir): return []
    return [os.path.join(asset_dir, f) for f in os.listdir(asset_dir)]

@st.cache_data
def get_available_voices():
    # ... (sin cambios)
    headers = {"xi-api-key": ELEVENLABS_API_KEY}; url = "https://api.elevenlabs.io/v1/voices"
    try:
        response = requests.get(url, headers=headers)
        return {voice['name']: voice['voice_id'] for voice in response.json()['voices']} if response.status_code == 200 else {}
    except Exception: return {}

# --- CAMBIO IMPORTANTE: FUNCIÓN PARA PROCESAR VIDEO ---
def process_video_frames(video_bytes, frames_per_second=1):
    """Extrae fotogramas de un video a una tasa específica."""
    video_path = "temp_video.mp4"
    with open(video_path, "wb") as f:
        f.write(video_bytes)
    
    vidcap = cv2.VideoCapture(video_path)
    fps = vidcap.get(cv2.CAP_PROP_FPS)
    frame_interval = int(fps / frames_per_second)
    
    extracted_frames = []
    frame_count = 0
    while vidcap.isOpened():
        success, image = vidcap.read()
        if not success:
            break
        if frame_count % frame_interval == 0:
            # Convertimos el fotograma de OpenCV (BGR) a PIL (RGB)
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(rgb_image)
            extracted_frames.append(pil_image)
        frame_count += 1
        
    vidcap.release()
    os.remove(video_path)
    return extracted_frames

# (Resto de funciones de habilidad sin cambios)
def listen_to_user(): #...
def extract_speakable_text(text): #...
def speak_response_cloud(text_to_speak, voice_id): #...

# --- INICIALIZACIÓN DE ESTADO ---
if 'voices_map' not in st.session_state: st.session_state.voices_map = get_available_voices()
if 'static_avatars' not in st.session_state: st.session_state.static_avatars = load_assets("avatars")
if 'animated_avatars' not in st.session_state: st.session_state.animated_avatars = load_assets("animated_avatars")
if "messages" not in st.session_state: st.session_state.messages = []

# --- INTERFAZ DE USUARIO (SIDEBAR) ---
with st.sidebar:
    # (Hemos movido el file_uploader, la sidebar ahora es más limpia)
    st.title("🚀 GhoStid AI"); st.caption("Tu tutor de programación personal.")
    st.header("Opciones de Entrada")
    if st.button("🎤 Hablar", use_container_width=True):
        st.session_state.user_input = listen_to_user()
    st.header("Configuración")
    st.session_state.voice_enabled = st.toggle("Activar voz", value=True)
    if st.session_state.voices_map:
        voice_names = list(st.session_state.voices_map.keys())
        st.session_state.selected_voice_name = st.selectbox("Voz del Asistente:", options=voice_names, index=voice_names.index("Rachel") if "Rachel" in voice_names else 0)
    with st.expander("🎨 Personalización Visual"):
        # ... (código de personalización sin cambios)
    st.markdown("---"); st.image("GHOSTID_LOGO.png", use_container_width=True); st.markdown("<p style='text-align: center;'>STIDGAR</p>", unsafe_allow_html=True)

# --- ÁREA PRINCIPAL ---
if not st.session_state.messages:
    # ... (Mensaje de bienvenida sin cambios)
for msg in st.session_state.messages:
    # ... (Bucle de historial sin cambios)

# --- ZONA DE INTERACCIÓN PRINCIPAL (LA GRAN MEJORA) ---
# Creamos un contenedor para agrupar el uploader y el chat input
interaction_container = st.container()
with interaction_container:
    # El nuevo file uploader, ahora en el área principal
    uploaded_file = st.file_uploader(
        "Arrastra y suelta un archivo aquí (imagen, texto, video corto)",
        type=["png", "jpg", "jpeg", "txt", "py", "md", "csv", "mp4", "mov"],
        key="main_uploader"
    )
    if uploaded_file: st.session_state.uploaded_file = uploaded_file

    prompt = st.chat_input("Escribe tu pregunta o pídemelo...")
    if st.session_state.get('user_input'):
        prompt = st.session_state.pop('user_input')

# Lógica principal de procesamiento
if prompt:
    # ... (código para añadir el prompt del usuario al historial)
    
    with st.chat_message("assistant", avatar=st.session_state.get('assistant_avatar', '🤖')):
        with st.spinner("GhoStid AI está pensando..."):
            llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest", temperature=0, google_api_key=GOOGLE_API_KEY)
            
            # Lógica para manejar el archivo adjunto
            if st.session_state.get("uploaded_file"):
                uploaded_file = st.session_state.pop("uploaded_file")
                file_extension = os.path.splitext(uploaded_file.name)[1].lower()
                
                # --- NUEVA LÓGICA PARA VIDEO ---
                if file_extension in [".mp4", ".mov", ".avi"]:
                    with st.spinner("Analizando fotogramas del video..."):
                        video_bytes = uploaded_file.getvalue()
                        frames = process_video_frames(video_bytes)
                    
                    if not frames:
                        response_text = "No se pudieron extraer fotogramas del video. ¿Está corrupto?"
                    else:
                        # Creamos el prompt multimodal con los fotogramas
                        prompt_parts = [{"type": "text", "text": f"Analiza este video y responde a la siguiente pregunta: {prompt}"}]
                        for frame in frames:
                            prompt_parts.append({"type": "image_url", "image_url": frame})
                        
                        human_message = HumanMessage(content=prompt_parts)
                        response = llm.invoke([human_message]); response_text = response.content
                
                elif file_extension in [".png", ".jpg", ".jpeg"]:
                    # ... (lógica de imagen sin cambios) ...
                else:
                    # ... (lógica de texto sin cambios) ...
            
            else:
                # ... (lógica de conversación normal sin cambios) ...

            # ... (código para mostrar texto, generar y mostrar audio, y guardar en historial) ...
