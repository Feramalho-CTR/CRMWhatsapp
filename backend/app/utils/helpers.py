import re
from typing import Optional


def normalize_phone(phone: Optional[str]):
    """Return only digits from phone (e.g. +55 11 99999-1234 -> 5511999991234).
    This will be used as human-friendly document id for clients."""
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    return digits if digits else None


def clean_firestore_dict(data: dict):
    """Deeply convert Firestore custom types (like Timestamps) to standard Python types."""
    if not data:
        return data
    new_data = dict(data)
    for key, value in new_data.items():
        # Handle Firestore Timestamps and other datetime-like objects
        if hasattr(value, 'to_datetime'):
            new_data[key] = value.to_datetime()
        # Recursively handle nested dicts
        elif isinstance(value, dict):
            new_data[key] = clean_firestore_dict(value)
        # Handle lists of dicts
        elif isinstance(value, list):
            new_data[key] = [clean_firestore_dict(i) if isinstance(i, dict) else i for i in value]
    return new_data
