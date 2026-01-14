from flask import Flask, request, jsonify
from flask_cors import CORS
from flasgger import Swagger
from firebase_admin import auth
from firebase_admin_init import init_firebase

app = Flask(__name__)
CORS(app)

# --- CONFIGURACIÓN DE SWAGGER ---
# Esto habilita el botón "Authorize" para probar tokens de Firebase
app.config['SWAGGER'] = {
    'title': 'API de Recordatorios',
    'uiversion': 3,
    'securityDefinitions': {
        'Bearer': {
            'type': 'apiKey',
            'name': 'Authorization',
            'in': 'header',
            'description': 'Escribe: "Bearer <tu_token_aqui>"'
        }
    },
    'security': [{'Bearer': []}]
}

swagger = Swagger(app)

db = init_firebase()

def require_firebase_user():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None, ("Falta Authorization Bearer token", 401)
    token = header.split("Bearer ")[1].strip()
    try:
        decoded = auth.verify_id_token(token)
        return decoded, None 
    except Exception:
        return None, ("Token inválido o expirado", 401)

@app.get("/health")
def health():
    """
    Verificar estado del servidor.
    ---
    tags:
      - General
    responses:
      200:
        description: Servidor funcionando
    """
    return {"ok": True}

# ==========================================
# --------       REMINDERS        --------
# ==========================================

@app.get("/reminders")
def list_reminders():
    """
    Listar recordatorios del usuario.
    ---
    tags:
      - Recordatorios
    security:
      - Bearer: []
    parameters:
      - name: tipo
        in: query
        type: string
        required: false
        description: Filtrar por tipo (ej. personal, trabajo)
    responses:
      200:
        description: Lista de recordatorios
      401:
        description: Token inválido o faltante
    """
    user, err = require_firebase_user()
    if err:
        return jsonify({"error": err[0]}), err[1]

    uid = user["uid"]
    tipo = request.args.get("tipo")

    query = db.collection("recordatorios").where("id_usuario", "==", uid)
    if tipo:
        query = query.where("tipo", "==", tipo)

    docs = query.stream()
    out = []
    for d in docs:
        data = d.to_dict()
        data["id"] = d.id
        out.append(data)

    return jsonify(out)

@app.post("/reminders")
def create_reminder():
    """
    Crear un nuevo recordatorio.
    ---
    tags:
      - Recordatorios
    security:
      - Bearer: []
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - nombre
            - fecha
            - hora
          properties:
            nombre:
              type: string
              example: "Comprar leche"
            fecha:
              type: string
              example: "2023-12-31"
            hora:
              type: string
              example: "15:30"
            descripcion:
              type: string
            prioridad:
              type: string
              example: "alta"
            archivos:
              type: array
              items:
                type: string
              description: Lista de URLs o rutas de archivos
            tipo:
              type: string
              example: "personal"
            color:
              type: string
              example: "azul"
    responses:
      201:
        description: Recordatorio creado
      400:
        description: Faltan datos obligatorios
    """
    user, err = require_firebase_user()
    if err:
        return jsonify({"error": err[0]}), err[1]

    uid = user["uid"]
    body = request.get_json(force=True)

    nombre = (body.get("nombre") or "").strip()
    fecha = (body.get("fecha") or "").strip()
    hora = (body.get("hora") or "").strip()

    if not nombre or not fecha or not hora:
        return jsonify({"error": "nombre, fecha, hora son obligatorios"}), 400

    doc = {
        "id_usuario": uid,
        "nombre": nombre,
        "descripcion": body.get("descripcion"),
        "fecha": fecha,
        "hora": hora,
        "estado": bool(body.get("estado", False)),
        "prioridad": body.get("prioridad", "media"),
        "notificacion": bool(body.get("notificacion", True)),
        "repeticion": body.get("repeticion", "ninguna"),
        "dias_repeticion": body.get("dias_repeticion", []),
        "fechas_completadas": body.get("fechas_completadas", []), 
        "estados_fechas": body.get("estados_fechas", {}), 
        "tipo": body.get("tipo", "personal"),
        "color": body.get("color", "azul"),
        "fecha_creacion": body.get("fecha_creacion"),
        # 🔥 AGREGADO: Guardar lista de rutas de archivos
        "archivos": body.get("archivos", []), 
    }

    ref = db.collection("recordatorios").add(doc)
    doc_id = ref[1].id
    doc["id"] = doc_id
    return jsonify(doc), 201

@app.put("/reminders/<rid>")
def update_reminder(rid):
    """
    Actualizar un recordatorio existente.
    ---
    tags:
      - Recordatorios
    security:
      - Bearer: []
    parameters:
      - name: rid
        in: path
        type: string
        required: true
        description: ID del recordatorio
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            nombre:
              type: string
            estado:
              type: boolean
            archivos:
              type: array
              items:
                type: string
    responses:
      200:
        description: Actualizado correctamente
      404:
        description: No encontrado
    """
    user, err = require_firebase_user()
    if err:
        return jsonify({"error": err[0]}), err[1]

    uid = user["uid"]
    body = request.get_json(force=True)

    ref = db.collection("recordatorios").document(rid)
    snap = ref.get()
    if not snap.exists:
        return jsonify({"error": "No encontrado"}), 404

    data = snap.to_dict()
    if data.get("id_usuario") != uid:
        return jsonify({"error": "No autorizado"}), 403

    allowed = {
        "nombre", "descripcion", "fecha", "hora", "estado",
        "prioridad", "notificacion", "repeticion", "tipo", "color", "fecha_creacion",
        "dias_repeticion", 
        "fechas_completadas",
        "estados_fechas",
        # 🔥 AGREGADO: Permitir actualizar archivos
        "archivos"
    }

    patch = {k: body[k] for k in body.keys() if k in allowed}
    ref.update(patch)

    updated = ref.get().to_dict()
    updated["id"] = rid
    return jsonify(updated)

@app.delete("/reminders/<rid>")
def delete_reminder(rid):
    """
    Eliminar un recordatorio.
    ---
    tags:
      - Recordatorios
    security:
      - Bearer: []
    parameters:
      - name: rid
        in: path
        type: string
        required: true
    responses:
      200:
        description: Eliminado
    """
    user, err = require_firebase_user()
    if err:
        return jsonify({"error": err[0]}), err[1]

    uid = user["uid"]
    ref = db.collection("recordatorios").document(rid)
    snap = ref.get()
    if not snap.exists:
        return jsonify({"error": "No encontrado"}), 404

    data = snap.to_dict()
    if data.get("id_usuario") != uid:
        return jsonify({"error": "No autorizado"}), 403

    ref.delete()
    return jsonify({"deleted": True})

# ==========================================
# -------- SECTIONS (CATEGORÍAS) --------
# ==========================================

@app.get("/sections")
def list_sections():
    """
    Listar secciones (categorías).
    ---
    tags:
      - Secciones
    security:
      - Bearer: []
    responses:
      200:
        description: Lista de secciones ordenada alfabéticamente
    """
    user, err = require_firebase_user()
    if err: return jsonify({"error": err[0]}), err[1]
    
    uid = user["uid"]
    
    # 🔥 MANTENIDO: Sin .order_by("nombre") para evitar error de índice en Firebase
    docs = db.collection("secciones").where("id_usuario", "==", uid).stream()
    
    out = []
    for d in docs:
        data = d.to_dict()
        data["id"] = d.id
        out.append(data)

    # 🔥 MANTENIDO: Ordenamos en Python
    out.sort(key=lambda x: x.get('nombre', '').lower())

    return jsonify(out)

@app.post("/sections")
def create_section():
    """
    Crear una nueva sección.
    ---
    tags:
      - Secciones
    security:
      - Bearer: []
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - nombre
          properties:
            nombre:
              type: string
              example: "Trabajo"
            color:
              type: integer
              example: 4280391411
    responses:
      201:
        description: Sección creada
    """
    user, err = require_firebase_user()
    if err: return jsonify({"error": err[0]}), err[1]
    
    uid = user["uid"]
    body = request.get_json(force=True)
    
    nombre = (body.get("nombre") or "").strip()
    color = body.get("color")
    
    if not nombre:
        return jsonify({"error": "Falta nombre"}), 400
        
    doc = {
        "id_usuario": uid,
        "nombre": nombre,
        "color": color if color else 4280391411,
        "fecha_creacion": body.get("fecha_creacion")
    }
    
    ref = db.collection("secciones").add(doc)
    doc["id"] = ref[1].id
    return jsonify(doc), 201

@app.put("/sections/<sid>")
def update_section(sid):
    """
    Actualizar una sección.
    ---
    tags:
      - Secciones
    security:
      - Bearer: []
    parameters:
      - name: sid
        in: path
        required: true
        type: string
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            nombre:
              type: string
            color:
              type: integer
    responses:
      200:
        description: Sección actualizada
    """
    user, err = require_firebase_user()
    if err: return jsonify({"error": err[0]}), err[1]

    uid = user["uid"]
    body = request.get_json(force=True)
    
    ref = db.collection("secciones").document(sid)
    snap = ref.get()
    
    if not snap.exists: return jsonify({"error": "No encontrado"}), 404
    if snap.to_dict().get("id_usuario") != uid: return jsonify({"error": "Ajeno"}), 403
    
    patch = {}
    if "nombre" in body: patch["nombre"] = body["nombre"]
    if "color" in body: patch["color"] = body["color"]
    
    if patch:
        ref.update(patch)
        
    return jsonify({"success": True})

@app.delete("/sections/<sid>")
def delete_section(sid):
    """
    Eliminar una sección.
    ---
    tags:
      - Secciones
    security:
      - Bearer: []
    parameters:
      - name: sid
        in: path
        required: true
        type: string
    responses:
      200:
        description: Sección eliminada
    """
    user, err = require_firebase_user()
    if err: return jsonify({"error": err[0]}), err[1]

    uid = user["uid"]
    ref = db.collection("secciones").document(sid)
    snap = ref.get()
    
    if not snap.exists: return jsonify({"error": "No encontrado"}), 404
    if snap.to_dict().get("id_usuario") != uid: return jsonify({"error": "Ajeno"}), 403
    
    ref.delete()
    return jsonify({"success": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
