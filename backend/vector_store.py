import chromadb


class VectorStore:
    def __init__(self, persist_dir: str, dimensions: int = 768):
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.dimensions = dimensions

    def _get_or_create_collection(self, folder_id: str):
        name = f"folder_{folder_id.replace('-', '_')}"
        # ChromaDB collection names: 3-63 chars, alphanumeric + underscores
        name = name[:63]
        return self.client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )

    def add_embedding(
        self,
        folder_id: str,
        file_id: str,
        embedding: list[float],
        metadata: dict,
    ):
        collection = self._get_or_create_collection(folder_id)
        collection.upsert(
            ids=[file_id],
            embeddings=[embedding],
            metadatas=[metadata],
        )

    def search(
        self,
        folder_id: str,
        query_embedding: list[float],
        limit: int = 10,
    ) -> list[dict]:
        try:
            collection = self._get_or_create_collection(folder_id)
            if collection.count() == 0:
                return []
        except Exception:
            return []

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(limit, collection.count()),
            include=["metadatas", "distances"],
        )

        items = []
        for i, file_id in enumerate(results["ids"][0]):
            distance = results["distances"][0][i]
            similarity = 1 - distance  # cosine distance to similarity
            meta = results["metadatas"][0][i]
            items.append({
                "file_id": file_id,
                "name": meta.get("name", ""),
                "mime_type": meta.get("mime_type", ""),
                "similarity": round(similarity, 4),
                "folder_id": meta.get("folder_id", ""),
            })

        return items

    def delete_folder(self, folder_id: str):
        name = f"folder_{folder_id.replace('-', '_')}"[:63]
        try:
            self.client.delete_collection(name=name)
        except ValueError:
            pass

    def get_file_count(self, folder_id: str) -> int:
        try:
            collection = self._get_or_create_collection(folder_id)
            return collection.count()
        except Exception:
            return 0

    def has_file(self, folder_id: str, file_id: str) -> bool:
        try:
            collection = self._get_or_create_collection(folder_id)
            result = collection.get(ids=[file_id])
            return len(result["ids"]) > 0
        except Exception:
            return False

    def list_folders(self) -> list[str]:
        collections = self.client.list_collections()
        return [c.replace("folder_", "", 1) for c in collections]
