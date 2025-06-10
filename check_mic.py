import pyaudio

# Creamos una instancia de PyAudio. Es como encender el sistema de audio.
p = pyaudio.PyAudio()

print("Buscando dispositivos de grabación (micrófonos)...")
print("-" * 30)

# Obtenemos la cantidad total de dispositivos de audio (micrófonos y altavoces).
info = p.get_host_api_info_by_index(0)
numdevices = info.get('deviceCount')

found_mic = False
# Revisamos cada dispositivo uno por uno.
for i in range(0, numdevices):
    # 'maxInputChannels' > 0 significa que es un dispositivo de ENTRADA (un micrófono).
    if (p.get_device_info_by_host_api_device_index(0, i).get('maxInputChannels')) > 0:
        print(f"✅ Micrófono Encontrado: ID {i} - {p.get_device_info_by_host_api_device_index(0, i).get('name')}")
        found_mic = True

if not found_mic:
    print("\n❌ No se encontró ningún dispositivo de grabación activo.")
    print("Por favor, revisa la configuración de sonido y privacidad de Windows.")

print("-" * 30)

# Es MUY importante terminar la instancia para liberar los recursos.
p.terminate()