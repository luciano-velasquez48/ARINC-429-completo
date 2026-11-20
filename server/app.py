import json
import os
import shutil
from datetime import datetime
from flask import Flask, jsonify, render_template, request
from arinc429 import codificar_arinc429
from outputs import enviar_puerto_serie, reproducir_por_auricular

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "datos_arinc429.json")
BAK_PATH = os.path.join(BASE_DIR, "datos_arinc429.bak.json")

INSTRUMENTOS_INICIALES = [
    {"id": 1, "nombre": "Altímetro", "minimo": -1000.0, "maximo": 50000.0, "label_octal": 0o204},
    {"id": 2, "nombre": "Velocímetro (IAS)", "minimo": 0.0, "maximo": 450.0, "label_octal": 0o206},
]


def cargar_estado() -> tuple[list[dict], list[dict], int, int]:
    for ruta in (DB_PATH, BAK_PATH):
        if os.path.exists(ruta):
            try:
                with open(ruta, "r", encoding="utf-8") as f:
                    data = json.load(f)
                insts = data.get("instrumentos", list(INSTRUMENTOS_INICIALES))
                envs = data.get("envios", [])
                next_i = int(data.get("next_inst_id", (max([i["id"] for i in insts], default=2) + 1)))
                next_e = int(data.get("next_envio_id", (max([e["id"] for e in envs], default=0) + 1)))
                return insts, envs, next_i, next_e
            except Exception:
                continue

    insts = [dict(i) for i in INSTRUMENTOS_INICIALES]
    return insts, [], 3, 1


def guardar_estado() -> None:
    if os.path.exists(DB_PATH):
        try:
            shutil.copy2(DB_PATH, BAK_PATH)
        except Exception:
            pass
    payload = {
        "instrumentos": instrumentos,
        "envios": envios,
        "next_inst_id": next_inst_id,
        "next_envio_id": next_envio_id,
    }
    tmp_path = DB_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, DB_PATH)


instrumentos, envios, next_inst_id, next_envio_id = cargar_estado()
guardar_estado()


def buscar_instrumento(inst_id: int) -> dict | None:
    return next((i for i in instrumentos if i["id"] == inst_id), None)


@app.route("/")
def index():
    return render_template("index.html")


@app.get("/api/instrumentos")
def listar_instrumentos():
    return jsonify(instrumentos)


@app.post("/api/instrumentos")
def crear_instrumento():
    global next_inst_id
    data = request.get_json(force=True)
    nombre = str(data.get("nombre", "")).strip()
    if not nombre:
        return jsonify({"error": "El nombre es obligatorio."}), 400
    try:
        minimo = float(data["minimo"])
        maximo = float(data["maximo"])
        label_octal = int(str(data.get("label_octal", "203")), 8)
    except (KeyError, ValueError):
        return jsonify({"error": "Datos numéricos o label octal inválidos."}), 400

    if maximo <= minimo:
        return jsonify({"error": "El máximo debe ser mayor que el mínimo."}), 400

    nuevo = {
        "id": next_inst_id,
        "nombre": nombre,
        "minimo": minimo,
        "maximo": maximo,
        "label_octal": label_octal,
    }
    next_inst_id += 1
    instrumentos.append(nuevo)
    guardar_estado()
    return jsonify(nuevo), 201


@app.put("/api/instrumentos/<int:inst_id>")
def actualizar_instrumento(inst_id: int):
    inst = buscar_instrumento(inst_id)
    if not inst:
        return jsonify({"error": "Instrumento no encontrado."}), 404

    data = request.get_json(force=True)
    nombre = str(data.get("nombre", inst["nombre"])).strip()
    if not nombre:
        return jsonify({"error": "El nombre no puede estar vacío."}), 400
    try:
        minimo = float(data.get("minimo", inst["minimo"]))
        maximo = float(data.get("maximo", inst["maximo"]))
        label_octal = int(str(data.get("label_octal", oct(inst["label_octal"])[2:])), 8)
    except ValueError:
        return jsonify({"error": "Valores inválidos."}), 400

    if maximo <= minimo:
        return jsonify({"error": "El máximo debe ser mayor que el mínimo."}), 400

    inst.update({"nombre": nombre, "minimo": minimo, "maximo": maximo, "label_octal": label_octal})
    guardar_estado()
    return jsonify(inst)


@app.delete("/api/instrumentos/<int:inst_id>")
def eliminar_instrumento(inst_id: int):
    global instrumentos
    inst = buscar_instrumento(inst_id)
    if not inst:
        return jsonify({"error": "Instrumento no encontrado."}), 404
    instrumentos = [i for i in instrumentos if i["id"] != inst_id]
    guardar_estado()
    return jsonify({"eliminado": inst_id})


@app.post("/api/reset-iniciales")
def reset_iniciales():
    global instrumentos, envios, next_inst_id, next_envio_id
    instrumentos = [dict(i) for i in INSTRUMENTOS_INICIALES]
    envios = []
    next_inst_id = 3
    next_envio_id = 1
    guardar_estado()
    return jsonify({"ok": True, "instrumentos": instrumentos})


@app.get("/api/envios")
def listar_envios():
    return jsonify(envios)


@app.post("/api/envios")
def crear_envio():
    global next_envio_id
    data = request.get_json(force=True)
    try:
        inst_id = int(data["instrumento_id"])
        valor = float(data["valor"])
    except (KeyError, ValueError):
        return jsonify({"error": "Debe indicar instrumento_id y un valor numérico."}), 400

    inst = buscar_instrumento(inst_id)
    if not inst:
        return jsonify({"error": "Instrumento no encontrado."}), 404

    try:
        arinc = codificar_arinc429(
            valor=valor,
            minimo=inst["minimo"],
            maximo=inst["maximo"],
            label_octal=inst["label_octal"],
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    puerto = str(data.get("puerto_serie", "SIMULADO")).strip()
    baudrate = int(data.get("baudrate", 9600))
    usar_auricular = bool(data.get("auricular", True))

    serial_res = enviar_puerto_serie(arinc["palabra_32_int"], puerto=puerto, baudrate=baudrate)
    audio_res = reproducir_por_auricular(arinc["bin"]) if usar_auricular else {"ok": True, "detalle": "Desactivado"}

    envio = {
        "id": next_envio_id,
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "instrumento_id": inst["id"],
        "instrumento_nombre": inst["nombre"],
        "valor": valor,
        "arinc": arinc,
        "serial": serial_res,
        "auricular": audio_res,
    }
    next_envio_id += 1
    envios.insert(0, envio)
    guardar_estado()
    return jsonify(envio), 201


@app.delete("/api/envios/<int:envio_id>")
def eliminar_envio(envio_id: int):
    global envios
    existe = any(e["id"] == envio_id for e in envios)
    if not existe:
        return jsonify({"error": "Envío no encontrado."}), 404
    envios = [e for e in envios if e["id"] != envio_id]
    guardar_estado()
    return jsonify({"eliminado": envio_id})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
