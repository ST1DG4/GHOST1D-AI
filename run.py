import streamlit as st
import subprocess
import threading
import time
import pywebview
import sys

# --- Funciones para el lanzador ---

def run_streamlit():
    """
    Ejecuta el comando 'streamlit run app.py' en un subproceso.
    Asegúrate de que 'app.py' esté en el mismo directorio.
    """
    # Esta es la parte crucial para que funcione después de empaquetar con PyInstaller
    if getattr(sys, 'frozen', False):
        # Estamos en modo empaquetado por PyInstaller
        # La ruta al ejecutable de streamlit cambia.
        # sys._MEIPASS es una carpeta temporal que PyInstaller crea al ejecutar el .exe
        streamlit_path = sys._MEIPASS / 'streamlit' 
        subprocess.run([streamlit_path, 'run', 'app.py', '--server.port', '8501'])
    else:
        # Estamos en modo de desarrollo normal (ejecutando con python run.py)
        # Aquí podemos usar una ruta directa y más robusta al python de nuestro venv
        # para evitar confusiones de "gemelos".
        python_executable = sys.executable
        subprocess.run([python_executable, '-m', 'streamlit', 'run', 'app.py', '--server.port', '8501'])


def start_webview():
    """
    Inicia la ventana de pywebview apuntando al servidor de Streamlit.
    """
    # Aumentamos un poco la espera para darle más tiempo al servidor de arrancar
    time.sleep(8) 
    
    # Creamos la ventana de la aplicación
    pywebview.create_window(
        "GhoStid AI",  # Título de la ventana
        "http://localhost:8501",
        width=1024,
        height=768,
        resizable=True
    )
    pywebview.start()

# --- Script Principal ---

if __name__ == '__main__':
    # Usamos un hilo para que el servidor de Streamlit no bloquee la GUI de pywebview
    streamlit_thread = threading.Thread(target=run_streamlit, daemon=True)
    streamlit_thread.start()

    # Iniciamos la interfaz gráfica en el hilo principal
    start_webview()