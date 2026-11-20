import io
import os
import platform
import subprocess
import wave
import numpy as np

try:
    import serial
except ImportError:
    serial = None


def enviar_puerto_serie(palabra_32: int, puerto: str | None = None, baudrate: int = 9600) -> dict:
    trama_bytes = palabra_32.to_bytes(4, byteorder="big")
    linea = f"ARINC:{palabra_32:08X}\n".encode("ascii")

    if not puerto or puerto.upper() == "SIMULADO" or serial is None:
        return {
            "ok": True,
            "modo": "SIMULADO",
            "puerto": puerto or "SIMULADO",
            "baudrate": baudrate,
            "enviado_hex": trama_bytes.hex().upper(),
            "detalle": "Simulación exitosa (sin puerto serie físico seleccionado).",
        }

    try:
        with serial.Serial(puerto, baudrate=baudrate, timeout=1) as ser:
            ser.write(linea)
            ser.write(trama_bytes)
            ser.flush()
        return {
            "ok": True,
            "modo": "SERIAL_REAL",
            "puerto": puerto,
            "baudrate": baudrate,
            "enviado_hex": trama_bytes.hex().upper(),
            "detalle": f"Enviado por {puerto} a {baudrate} baudios.",
        }
    except Exception as exc:
        return {
            "ok": False,
            "modo": "ERROR",
            "puerto": puerto,
            "baudrate": baudrate,
            "enviado_hex": trama_bytes.hex().upper(),
            "detalle": f"Error al abrir/escribir puerto serie: {exc}",
        }


def generar_wav_32bits(bin_32: str, sample_rate: int = 44100, bit_dur_s: float = 0.015, amplitud: float = 0.8) -> bytes:
    muestras_por_bit = int(sample_rate * bit_dur_s)
    onda_total = []

    for bit in bin_32:
        freq = 1800.0 if bit == "1" else 900.0
        t = np.arange(muestras_por_bit) / sample_rate
        pulso = amplitud * np.sign(np.sin(2.0 * np.pi * freq * t))
        onda_total.append(pulso)

    senal = np.concatenate(onda_total)
    pcm = (senal * 32767).astype(np.int16)

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())
    return buffer.getvalue()


def reproducir_por_auricular(bin_32: str) -> dict:
    wav_bytes = generar_wav_32bits(bin_32)
    temp_path = os.path.join(os.path.dirname(__file__), "_ultima_trama_auricular.wav")
    with open(temp_path, "wb") as f:
        f.write(wav_bytes)

    sistema = platform.system()
    try:
        if sistema == "Windows":
            os.startfile(temp_path)  # type: ignore[attr-defined]
            return {"ok": True, "detalle": "Reproducción enviada a la salida de audio/auricular (Windows)."}
        elif sistema == "Darwin":
            subprocess.Popen(["afplay", temp_path])
            return {"ok": True, "detalle": "Reproducción enviada a la salida de audio/auricular (macOS)."}
        else:
            for cmd in (["aplay", temp_path], ["paplay", temp_path], ["ffplay", "-nodisp", "-autoexit", temp_path]):
                if subprocess.call(["which", cmd[0]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
                    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return {"ok": True, "detalle": f"Reproducción enviada por auricular usando {cmd[0]}."}
            return {"ok": True, "detalle": f"WAV generado en {temp_path} (reproductor CLI no encontrado)."}
    except Exception as exc:
        return {"ok": False, "detalle": f"No se pudo reproducir en auricular: {exc}"}
