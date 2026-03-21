# App package
from app.core.firebase import firebase_app, firestore_client
from app.db.firestore_wrapper import get_db

db = get_db()

__all__ = ['db', 'firebase_app', 'firestore_client', 'get_db']
