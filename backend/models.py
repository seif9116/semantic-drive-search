from pydantic import BaseModel


class IndexRequest(BaseModel):
    folder_id: str


class IndexStatus(BaseModel):
    folder_id: str
    total_files: int
    processed: int
    failed: int
    status: str  # "idle" | "indexing" | "complete" | "error"
    current_file: str = ""


class SearchResult(BaseModel):
    file_id: str
    name: str
    mime_type: str
    similarity: float
    thumbnail_url: str


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]


class FolderInfo(BaseModel):
    folder_id: str
    name: str
    file_count: int
    indexed: bool
