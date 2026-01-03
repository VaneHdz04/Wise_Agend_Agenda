import os
import json
import firebase_admin
from firebase_admin import credentials, firestore

def init_firebase():
    if not firebase_admin._apps:
        # Intentamos obtener la configuración desde la variable de entorno de Render
        firebase_config_env = os.environ.get("FIREBASE_CONFIG")

        if firebase_config_env:
            # Caso: Producción (Render)
            # Convertimos el string de la variable de entorno a un diccionario de Python
            cred_dict = json.loads(firebase_config_env)
            cred = credentials.Certificate(cred_dict)
        else:
            # Caso: Desarrollo Local
            # Asegúrate de que esta ruta sea correcta en tu carpeta local
            cred = credentials.Certificate("keys/serviceAccountKey.json")
        
        firebase_admin.initialize_app(cred)

    return firestore.client()