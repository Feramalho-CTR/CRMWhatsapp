
import os
import asyncio
import json
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

load_dotenv()

# Setup Firebase
cred_val = os.environ.get('FIREBASE_CREDENTIALS_JSON')
try:
    if cred_val.strip().startswith('{'):
        cred = credentials.Certificate(json.loads(cred_val))
    else:
        cred = credentials.Certificate(cred_val)
    firebase_admin.initialize_app(cred)
except:
    pass

_firestore_client = firestore.client()

class FirestoreWrapper:
    def __init__(self, col_name):
        self.col = _firestore_client.collection(col_name)

    async def to_list(self, n=1000):
        # Para simplificar o teste, simulamos o comportamento do cursor
        return await self.find({}).to_list(n)

    def find(self, filter: dict = None):
        wrapper = self
        class _Cursor:
            def __init__(self, w, filter):
                self.w = w
                self.filter = filter or {}
                self._sort = None

            def sort(self, field, direction):
                self._sort = (field, direction)
                return self

            async def to_list(self, n=1000):
                return await asyncio.to_thread(self._to_list_sync, n)

            def _to_list_sync(self, n):
                query = wrapper.col
                if self.filter:
                    for key, val in self.filter.items():
                        if isinstance(val, dict):
                            for op_key, op_val in val.items():
                                if op_key == '$ne': query = query.where(key, '!=', op_val)
                                elif op_key == '$gt': query = query.where(key, '>', op_val)
                                elif op_key == '$lt': query = query.where(key, '<', op_val)
                                elif op_key == '$gte': query = query.where(key, '>=', op_val)
                                elif op_key == '$lte': query = query.where(key, '<=', op_val)
                                elif op_key == '$in': query = query.where(key, 'in', op_val)
                        else:
                            query = query.where(key, '==', val)
                
                if self._sort:
                    field, direction = self._sort
                    from firebase_admin.firestore import Query
                    dir_val = Query.DESCENDING if direction == -1 else Query.ASCENDING
                    query = query.order_by(field, direction=dir_val)
                
                docs = list(query.limit(n).stream())
                return [d.to_dict() for d in docs]

        return _Cursor(wrapper, filter)

async def test_wrapper():
    users_col = FirestoreWrapper('users')
    print("Testing db.users.find({'role': 'agent'})...")
    agents = await users_col.find({"role": "agent"}).to_list()
    print(f"Found {len(agents)} agents via wrapper.")
    for a in agents:
        print(f" - {a.get('username')} ({a.get('role')})")

if __name__ == "__main__":
    asyncio.run(test_wrapper())
