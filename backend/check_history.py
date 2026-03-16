import firebase_admin
from firebase_admin import credentials, firestore
import os
import json
from dotenv import load_dotenv

def main():
    load_dotenv()
    cred_json = os.environ.get('FIREBASE_CREDENTIALS_JSON')
    if not cred_json:
        print("FIREBASE_CREDENTIALS_JSON not found")
        return
        
    cred_dict = json.loads(cred_json)
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    
    print("--- CLIENTS AND SUBCOLLECTION MESSAGES ---")
    clients = db.collection('clients').stream()
    for c in clients:
        submsgs = list(db.collection('clients').document(c.id).collection('messages').stream())
        print(f"Client {c.id}: {len(submsgs)} messages in subcollection")
        for m in submsgs[:2]:
            print(f"  - {m.id}: {m.to_dict().get('content')[:30]}...")

    print("\n--- TOP-LEVEL MESSAGES COLLECTION ---")
    msgs_top = db.collection('messages').stream()
    top_counts = {}
    for m in msgs_top:
        cid = m.to_dict().get('client_id', 'UNKNOWN')
        top_counts[cid] = top_counts.get(cid, 0) + 1
        
    for cid, count in top_counts.items():
        print(f"Client ID {cid}: {count} messages in top-level collection")

if __name__ == "__main__":
    main()
