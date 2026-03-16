import psycopg
from pgvector.psycopg import register_vector


class VectorStore:
    def __init__(self, database_url: str, dimensions: int = 768):
        self.database_url = database_url
        self.dimensions = dimensions
        self._init_db()

    def _get_conn(self):
        conn = psycopg.connect(self.database_url)
        register_vector(conn)
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS embeddings (
                    id SERIAL PRIMARY KEY,
                    folder_id TEXT NOT NULL,
                    file_id TEXT NOT NULL,
                    embedding vector({self.dimensions}) NOT NULL,
                    name TEXT NOT NULL DEFAULT '',
                    mime_type TEXT NOT NULL DEFAULT '',
                    metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                    file_hash TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    last_modified TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE(folder_id, file_id)
                )
            """)
            # Index for folder-scoped queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_embeddings_folder
                ON embeddings(folder_id)
            """)
            # Composite index for folder+file lookups (has_file checks)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_embeddings_folder_file
                ON embeddings(folder_id, file_id)
            """)
            # HNSW index for fast approximate nearest neighbor search
            # Uses cosine distance operator (<=>) for semantic similarity
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_embeddings_vector_hnsw
                ON embeddings
                USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64)
            """)
            # Index for file_hash lookups (embedding cache)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_embeddings_file_hash
                ON embeddings(file_hash)
                WHERE file_hash IS NOT NULL
            """)
            conn.commit()

    def add_embedding(
        self,
        folder_id: str,
        file_id: str,
        embedding: list[float],
        metadata: dict,
        file_hash: str | None = None,
    ):
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO embeddings (folder_id, file_id, embedding, name, mime_type, metadata, file_hash, last_modified)
                VALUES (%s, %s, %s::vector, %s, %s, %s::jsonb, %s, NOW())
                ON CONFLICT (folder_id, file_id) DO UPDATE SET
                    embedding = EXCLUDED.embedding,
                    name = EXCLUDED.name,
                    mime_type = EXCLUDED.mime_type,
                    metadata = EXCLUDED.metadata,
                    file_hash = EXCLUDED.file_hash,
                    last_modified = NOW()
                """,
                (
                    folder_id,
                    file_id,
                    str(embedding),
                    metadata.get("name", ""),
                    metadata.get("mime_type", ""),
                    psycopg.types.json.Json(metadata),
                    file_hash,
                ),
            )
            conn.commit()

    def search(
        self,
        folder_id: str,
        query_embedding: list[float],
        limit: int = 10,
        offset: int = 0,
        min_similarity: float = 0.0,
    ) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                """
                SELECT file_id, name, mime_type, folder_id,
                       1 - (embedding <=> %s::vector) AS similarity
                FROM embeddings
                WHERE folder_id = %s
                  AND 1 - (embedding <=> %s::vector) >= %s
                ORDER BY embedding <=> %s::vector
                LIMIT %s OFFSET %s
                """,
                (str(query_embedding), folder_id, str(query_embedding), min_similarity, str(query_embedding), limit, offset),
            ).fetchall()

        return [
            {
                "file_id": row[0],
                "name": row[1],
                "mime_type": row[2],
                "folder_id": row[3],
                "similarity": round(float(row[4]), 4),
            }
            for row in rows
        ]

    def search_similar(
        self,
        file_id: str,
        folder_id: str,
        limit: int = 10,
        min_similarity: float = 0.0,
    ) -> list[dict]:
        """Find files similar to a given file (more like this)."""
        with self._get_conn() as conn:
            # Get the embedding for the reference file
            row = conn.execute(
                "SELECT embedding FROM embeddings WHERE folder_id = %s AND file_id = %s",
                (folder_id, file_id),
            ).fetchone()
            if not row:
                return []
            query_embedding = list(row[0])

            # Search for similar files, excluding the reference file itself
            rows = conn.execute(
                """
                SELECT file_id, name, mime_type, folder_id,
                       1 - (embedding <=> %s::vector) AS similarity
                FROM embeddings
                WHERE folder_id = %s
                  AND file_id != %s
                  AND 1 - (embedding <=> %s::vector) >= %s
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (str(query_embedding), folder_id, file_id, str(query_embedding), min_similarity, str(query_embedding), limit),
            ).fetchall()

        return [
            {
                "file_id": row[0],
                "name": row[1],
                "mime_type": row[2],
                "folder_id": row[3],
                "similarity": round(float(row[4]), 4),
            }
            for row in rows
        ]

    def get_embedding_by_hash(self, file_hash: str) -> list[float] | None:
        """Retrieve a cached embedding by file hash."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT embedding FROM embeddings WHERE file_hash = %s LIMIT 1",
                (file_hash,),
            ).fetchone()
            return list(row[0]) if row else None

    def get_file_last_modified(self, folder_id: str, file_id: str) -> str | None:
        """Get the last_modified timestamp for a file."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT last_modified FROM embeddings WHERE folder_id = %s AND file_id = %s",
                (folder_id, file_id),
            ).fetchone()
            return str(row[0]) if row and row[0] else None

    def delete_folder(self, folder_id: str):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM embeddings WHERE folder_id = %s", (folder_id,))
            conn.commit()

    def get_file_count(self, folder_id: str) -> int:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM embeddings WHERE folder_id = %s",
                (folder_id,),
            ).fetchone()
            return row[0] if row else 0

    def has_file(self, folder_id: str, file_id: str) -> bool:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM embeddings WHERE folder_id = %s AND file_id = %s LIMIT 1",
                (folder_id, file_id),
            ).fetchone()
            return row is not None

    def get_all_embeddings(self, folder_id: str) -> list[dict]:
        """Return all file_id, name, mime_type, and embedding for a folder."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT file_id, name, mime_type, embedding FROM embeddings WHERE folder_id = %s",
                (folder_id,),
            ).fetchall()
        return [
            {
                "file_id": row[0],
                "name": row[1],
                "mime_type": row[2],
                "embedding": list(row[3]),
            }
            for row in rows
        ]

    def list_folders(self) -> list[str]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT folder_id FROM embeddings ORDER BY folder_id"
            ).fetchall()
            return [row[0] for row in rows]
