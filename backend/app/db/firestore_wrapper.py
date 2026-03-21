import logging
from typing import Any, Dict
import asyncio

from app.core.firebase import firestore_client
from app.utils.helpers import clean_firestore_dict


class _CollectionWrapper:
    def __init__(self, collection_name: str):
        if firestore_client is None:
            raise RuntimeError('Firestore client not initialized. Configure Firebase credentials.')
        self.col = firestore_client.collection(collection_name)

    async def find_one(self, filter: dict):
        return await asyncio.to_thread(self._find_one_sync, filter or {})

    def _find_one_sync(self, filter: dict):
        if not filter:
            docs = list(self.col.limit(1).stream())
            return clean_firestore_dict(docs[0].to_dict()) if docs else None

        # Atalho para busca direta por ID de documento (apenas se for string e o único filtro)
        if 'id' in filter and isinstance(filter['id'], str) and len(filter) == 1:
            doc = self.col.document(filter['id']).get()
            return clean_firestore_dict(doc.to_dict()) if doc.exists else None

        # Constrói query com múltiplos filtros
        query = self.col
        for key, val in filter.items():
            if isinstance(val, dict):
                # Suporta operadores simples do MongoDB (ex: $ne, $gt, $lt)
                for op_key, op_val in val.items():
                    if op_key == '$ne':
                        query = query.where(key, '!=', op_val)
                    elif op_key == '$gt':
                        query = query.where(key, '>', op_val)
                    elif op_key == '$lt':
                        query = query.where(key, '<', op_val)
                    elif op_key == '$gte':
                        query = query.where(key, '>=', op_val)
                    elif op_key == '$lte':
                        query = query.where(key, '<=', op_val)
                    elif op_key == '$in':
                        query = query.where(key, 'in', op_val)
            else:
                query = query.where(key, '==', val)

        docs = list(query.limit(1).stream())
        return clean_firestore_dict(docs[0].to_dict()) if docs else None

    async def insert_one(self, doc: dict):
        return await asyncio.to_thread(self._insert_one_sync, doc)

    def _insert_one_sync(self, doc: dict):
        # Garante que não estamos inserindo objetos complexos não serializáveis
        doc_copy = clean_firestore_dict(dict(doc))
        doc_id = doc_copy.get('id')
        if doc_id:
            self.col.document(doc_id).set(doc_copy)
            return {'inserted_id': doc_id}
        else:
            doc_ref = self.col.document()
            doc_copy['id'] = doc_ref.id
            doc_ref.set(doc_copy)
            return {'inserted_id': doc_copy['id']}

    async def update_one(self, filter: dict, update: dict):
        return await asyncio.to_thread(self._update_one_sync, filter, update)

    def _update_one_sync(self, filter: dict, update: dict):
        if not filter:
            return {'matched_count': 0}

        # Atalho para busca direta por ID de documento (apenas se for string e o único filtro)
        if 'id' in filter and isinstance(filter['id'], str) and len(filter) == 1:
            doc_ref = self.col.document(filter['id'])
            doc = doc_ref.get()
            if not doc.exists:
                return {'matched_count': 0}
            if '$set' in update:
                doc_ref.update(update['$set'])
            else:
                doc_ref.update(update)
            return {'matched_count': 1}
        else:
            # Fallback para query (pega o primeiro que encontrar)
            query = self.col
            for key, val in filter.items():
                if isinstance(val, dict):
                    for op_key, op_val in val.items():
                        if op_key == '$ne':
                            query = query.where(key, '!=', op_val)
                        elif op_key == '$in':
                            query = query.where(key, 'in', op_val)
                else:
                    query = query.where(key, '==', val)

            docs = list(query.limit(1).stream())
            if not docs:
                return {'matched_count': 0}
            doc_ref = self.col.document(docs[0].id)
            if '$set' in update:
                doc_ref.update(update['$set'])
            else:
                doc_ref.update(update)
            return {'matched_count': 1}

    async def delete_one(self, filter: dict):
        return await asyncio.to_thread(self._delete_one_sync, filter)

    def _delete_one_sync(self, filter: dict):
        if not filter:
            return {'deleted_count': 0}

        # Atalho para busca direta por ID de documento
        if 'id' in filter and isinstance(filter['id'], str) and len(filter) == 1:
            doc_ref = self.col.document(filter['id'])
            doc = doc_ref.get()
            if not doc.exists:
                return {'deleted_count': 0}
            doc_ref.delete()
            return {'deleted_count': 1}
        else:
            query = self.col
            for key, val in filter.items():
                if isinstance(val, dict):
                    # Simplificado: deletar por query básica
                    pass
                else:
                    query = query.where(key, '==', val)

            docs = list(query.limit(1).stream())
            if not docs:
                return {'deleted_count': 0}
            self.col.document(docs[0].id).delete()
            return {'deleted_count': 1}

    async def count_documents(self, filter: dict):
        return await asyncio.to_thread(self._count_documents_sync, filter)

    def _count_documents_sync(self, filter: dict):
        if not filter:
            # Uso de agregação para contagem eficiente (se disponível)
            try:
                return self.col.count().get()[0][0].value
            except Exception:
                docs = list(self.col.stream())
                return len(docs)

        query = self.col
        for key, val in filter.items():
            if isinstance(val, dict):
                for op_key, op_val in val.items():
                    if op_key == '$ne':
                        query = query.where(key, '!=', op_val)
                    elif op_key == '$gt':
                        query = query.where(key, '>', op_val)
                    elif op_key == '$lt':
                        query = query.where(key, '<', op_val)
                    elif op_key == '$gte':
                        query = query.where(key, '>=', op_val)
                    elif op_key == '$lte':
                        query = query.where(key, '<=', op_val)
                    elif op_key == '$in':
                        query = query.where(key, 'in', op_val)
                    elif op_key == '$exists':
                        # Firestore não tem $exists direto, mas podemos aproximar
                        pass
            else:
                query = query.where(key, '==', val)

        try:
            # Tenta contagem otimizada
            return query.count().get()[0][0].value
        except Exception:
            docs = list(query.stream())
            return len(docs)

    def find(self, filter: dict = None):
        wrapper = self

        class _Cursor:
            def __init__(self, w, filter):
                self.w = w
                self.filter = filter or {}
                self._sort = None
                self._limit = None

            def sort(self, key, direction):
                self._sort = (key, direction)
                return self

            def limit(self, n):
                self._limit = n
                return self

            async def to_list(self, n=1000):
                return await asyncio.to_thread(self._to_list_sync, n)

            def _to_list_sync(self, n):
                query = wrapper.col
                if self.filter:
                    for key, val in self.filter.items():
                        if isinstance(val, dict):
                            for op_key, op_val in val.items():
                                if op_key == '$ne':
                                    query = query.where(key, '!=', op_val)
                                elif op_key == '$gt':
                                    query = query.where(key, '>', op_val)
                                elif op_key == '$lt':
                                    query = query.where(key, '<', op_val)
                                elif op_key == '$gte':
                                    query = query.where(key, '>=', op_val)
                                elif op_key == '$lte':
                                    query = query.where(key, '<=', op_val)
                                elif op_key == '$in':
                                    query = query.where(key, 'in', op_val)
                        else:
                            query = query.where(key, '==', val)

                docs = list(query.stream())
                results = []
                for d in docs:
                    data = clean_firestore_dict(d.to_dict()) or {}
                    # Garante que o ID do documento esteja presente no dicionário
                    if 'id' not in data:
                        data['id'] = d.id
                    results.append(data)
                if self._sort:
                    key, direction = self._sort
                    reverse = True if direction < 0 else False

                    # Ordenação segura contra tipos mistos ou None
                    def safe_sort_key(x):
                        val = x.get(key)
                        if val is None:
                            return 0 if not reverse else float('inf')
                        return val

                    results.sort(key=safe_sort_key, reverse=reverse)
                if self._limit:
                    results = results[:self._limit]
                if n:
                    return results[:n]
                return results

        return _Cursor(wrapper, filter)


def get_db():
    """Retorna o objeto db com as coleções inicializadas."""
    if firestore_client is None:
        return None

    db = type('DB', (), {})()
    db.users = _CollectionWrapper('users')
    db.clients = _CollectionWrapper('clients')
    db.messages = _CollectionWrapper('messages')
    db.whatsapp_config = _CollectionWrapper('whatsapp_config')
    return db
