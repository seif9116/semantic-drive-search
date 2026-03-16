"""
Image organization logic.

Two strategies:
  - date:     group files into "YYYY - Month" subfolders using Drive createdTime
  - semantic: k-means cluster the embedding space, name each cluster with Gemini
              vision, then move files into the named subfolders
"""

import re
import time
from datetime import datetime

NAMING_MODEL = "gemini-2.0-flash"
SAMPLE_SIZE = 3   # representative images sent to Gemini per cluster


# ── Helpers ────────────────────────────────────────────────────────────────────

def _sanitize_folder_name(raw: str) -> str:
    name = raw.strip().lower()
    name = re.sub(r"[^a-z0-9_ ]", "", name)
    name = re.sub(r"\s+", "_", name).strip("_")
    return name[:60] or "cluster"


def _deduplicate_names(named: list[dict]) -> list[dict]:
    """Append _2, _3 etc. to any duplicate cluster names."""
    seen: dict[str, int] = {}
    for item in named:
        base = item["name"]
        if base in seen:
            seen[base] += 1
            item["name"] = f"{base}_{seen[base]}"
        else:
            seen[base] = 1
    return named


def _name_cluster(client, sample_images: list[tuple[bytes, str]], index: int) -> str:
    """Ask Gemini to pick a folder name from sample images."""
    from google.genai import types

    if not sample_images:
        return f"cluster_{index + 1}"

    parts = [
        types.Part.from_bytes(data=img_bytes, mime_type=mime)
        for img_bytes, mime in sample_images
    ]
    parts.append(
        "These images belong to the same visual/semantic cluster. "
        "What theme or concept connects them? "
        "Reply with ONLY a short folder name (2-5 words, lowercase, underscores). "
        "Examples: beach_sunsets, family_gatherings, product_screenshots"
    )

    try:
        response = client.models.generate_content(model=NAMING_MODEL, contents=parts)
        return _sanitize_folder_name(response.text) or f"cluster_{index + 1}"
    except Exception:
        return f"cluster_{index + 1}"


# ── Date organizer ─────────────────────────────────────────────────────────────

def organize_by_date(creds, folder_id: str, dry_run: bool = False) -> dict:
    """Group all indexed media in folder_id into YYYY - Month subfolders."""
    from backend import drive

    files = drive.list_media_files(creds, folder_id)
    if not files:
        return {"folder_id": folder_id, "mode": "date", "groups": [], "total_files": 0, "dry_run": dry_run}

    # Group by year-month
    groups: dict[str, dict] = {}
    for f in files:
        try:
            dt = datetime.fromisoformat(f.get("createdTime", "").replace("Z", "+00:00"))
            sort_key = dt.strftime("%Y-%m")
            label = dt.strftime("%Y - %B")   # "2023 - March"
        except (ValueError, AttributeError):
            sort_key = "0000-00"
            label = "Unknown Date"

        if sort_key not in groups:
            groups[sort_key] = {"label": label, "files": []}
        groups[sort_key]["files"].append(f)

    ordered = sorted(groups.items())

    result: dict = {
        "folder_id": folder_id,
        "mode": "date",
        "dry_run": dry_run,
        "total_files": len(files),
        "groups": [
            {
                "folder_name": info["label"],
                "file_count": len(info["files"]),
                **({"files": [f["name"] for f in info["files"]]} if dry_run else {}),
            }
            for _, info in ordered
        ],
    }

    if not dry_run:
        for _, info in ordered:
            new_folder_id = drive.create_folder(creds, info["label"], folder_id)
            for f in info["files"]:
                parents = drive.get_file_parents(creds, f["id"])
                old_parent = parents[0] if parents else folder_id
                drive.move_file(creds, f["id"], new_folder_id, old_parent)

    return result


# ── Semantic organizer ─────────────────────────────────────────────────────────

def organize_semantic(creds, folder_id: str, k: int = 10, dry_run: bool = False) -> dict:
    """
    Cluster the embedding space with k-means, name each cluster with Gemini
    vision (using the most representative images), then move files in Drive.
    """
    import numpy as np
    from sklearn.cluster import KMeans
    from sklearn.metrics.pairwise import cosine_similarity
    from backend.config import settings
    from backend.vector_store import VectorStore
    from backend import drive
    from backend.embeddings import get_client

    store = VectorStore(database_url=settings.database_url, dimensions=settings.embedding_dimensions)
    rows = store.get_all_embeddings(folder_id)

    if not rows:
        return {"error": "No indexed files found. Run `sds index <folder_id>` first."}

    n = len(rows)
    k = min(k, n)

    matrix = np.array([r["embedding"] for r in rows], dtype=np.float32)

    kmeans = KMeans(n_clusters=k, random_state=42, n_init="auto")
    labels = kmeans.fit_predict(matrix)

    # Build per-cluster file lists + find most representative files
    clusters = []
    for cid in range(k):
        indices = [i for i, lbl in enumerate(labels) if lbl == cid]
        if not indices:
            continue

        idx_arr = np.array(indices)
        centroid = kmeans.cluster_centers_[cid].reshape(1, -1)
        sims = cosine_similarity(centroid, matrix[idx_arr])[0]
        top = idx_arr[sims.argsort()[::-1][:SAMPLE_SIZE]]

        clusters.append({
            "cid": cid,
            "files": [rows[i] for i in indices],
            "representative": [rows[i] for i in top],
        })

    # Name each cluster with Gemini vision
    client = get_client()
    named: list[dict] = []

    for cluster in clusters:
        sample_images: list[tuple[bytes, str]] = []
        for rep in cluster["representative"]:
            # skip videos — too large for naming; images only
            if not rep["mime_type"].startswith("image/"):
                continue
            try:
                img_bytes = drive.download_file(creds, rep["file_id"])
                sample_images.append((img_bytes, rep["mime_type"]))
            except Exception:
                pass
            time.sleep(0.2)

        name = _name_cluster(client, sample_images, cluster["cid"])
        named.append({"name": name, "files": cluster["files"]})

    named = _deduplicate_names(named)

    result: dict = {
        "folder_id": folder_id,
        "mode": "semantic",
        "dry_run": dry_run,
        "k": k,
        "total_files": n,
        "clusters": [
            {
                "name": c["name"],
                "file_count": len(c["files"]),
                **({"files": [f["name"] for f in c["files"]]} if dry_run else {}),
            }
            for c in named
        ],
    }

    if not dry_run:
        for c in named:
            new_folder_id = drive.create_folder(creds, c["name"], folder_id)
            for f in c["files"]:
                parents = drive.get_file_parents(creds, f["file_id"])
                old_parent = parents[0] if parents else folder_id
                drive.move_file(creds, f["file_id"], new_folder_id, old_parent)

    return result
