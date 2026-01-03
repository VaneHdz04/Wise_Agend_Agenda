import json
from firebase_admin_init import init_firebase

db = init_firebase()

SEED_FILE = "firestore-seed.json"  # ponlo en backend/

def upsert_collection(name, obj):
    col = db.collection(name)
    for doc_id, data in obj.items():
        col.document(doc_id).set(data)

def main():
    with open(SEED_FILE, "r", encoding="utf-8") as f:
        seed = json.load(f)

    for col_name, docs in seed.items():
        if isinstance(docs, dict):
            upsert_collection(col_name, docs)

    print("✅ Seed cargado a Firestore")

if __name__ == "__main__":
    main()
