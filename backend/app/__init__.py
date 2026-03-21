# App package
from .config import firebase_app, firestore_client
from .db import get_db

db = get_db()

__all__ = ['db', 'firebase_app', 'firestore_client', 'get_db']
