"""Graph comments API — annotations on nodes/edges (V8)."""

from __future__ import annotations

import time
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/v1/graph")

# In-memory store (upgrade to PostgreSQL in production)
_comments: dict[str, dict] = {}


class CommentCreate(BaseModel):
    target_id: str
    target_type: str = "entity"  # entity | relationship | community
    text: str
    author: str = "user"
    parent_id: str | None = None


@router.post("/comments", tags=["graph-comments"])
async def create_comment(body: CommentCreate):
    comment_id = str(uuid.uuid4())[:8]
    comment = {
        "id": comment_id,
        "target_id": body.target_id,
        "target_type": body.target_type,
        "text": body.text,
        "author": body.author,
        "parent_id": body.parent_id,
        "created_at": time.time(),
    }
    _comments[comment_id] = comment
    return comment


@router.get("/comments", tags=["graph-comments"])
async def list_comments(target_id: str | None = None):
    if target_id:
        return [c for c in _comments.values() if c["target_id"] == target_id]
    return list(_comments.values())


@router.get("/comments/counts", tags=["graph-comments"])
async def comment_counts():
    counts: dict[str, int] = {}
    for c in _comments.values():
        tid = c["target_id"]
        counts[tid] = counts.get(tid, 0) + 1
    return counts


@router.put("/comments/{comment_id}", tags=["graph-comments"])
async def update_comment(comment_id: str, text: str):
    if comment_id not in _comments:
        raise HTTPException(404, "Comment not found")
    _comments[comment_id]["text"] = text
    return _comments[comment_id]


@router.delete("/comments/{comment_id}", tags=["graph-comments"])
async def delete_comment(comment_id: str):
    if comment_id not in _comments:
        raise HTTPException(404, "Comment not found")
    del _comments[comment_id]
    return {"deleted": True}
