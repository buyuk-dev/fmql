from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Iterable, Sequence

from fmql import __version__ as fmql_version
from fmql.packet import Packet
from fmql.search.errors import BackendUnavailableError, IndexVersionError
from fmql.search.types import BackendInfo, IndexStats, SearchHit
from fmql.workspace import Workspace
from fmql_semantic import __version__ as semantic_version
from fmql_semantic.config import Config, resolve_config
from fmql_semantic.dense import dense_search
from fmql_semantic.embeddings import _embed_batch
from fmql_semantic.fusion import reciprocal_rank_fusion
from fmql_semantic.progress import progress
from fmql_semantic.reranker import rerank
from fmql_semantic.sparse import sparse_search
from fmql_semantic.storage import meta as meta_mod
from fmql_semantic.storage.connection import open_db
from fmql_semantic.storage.writer import (
    delete_packets,
    fetch_existing_hashes,
    open_for_build,
    upsert_batch,
)
from fmql_semantic.textprep import build_rows


class SemanticBackend:
    """Hybrid (dense + sparse) search backend for fmql."""

    name = "semantic"

    # ------------------------------------------------------------------ IndexedSearch

    def parse_location(self, location: str) -> object:
        if not location:
            raise ValueError("semantic backend: location must be a non-empty path")
        return Path(location)

    def default_location(self, workspace: Workspace) -> str | None:
        return str(Path(workspace.root) / ".fmql" / "semantic.db")

    def build(
        self,
        packets: Iterable[Packet],
        location: str,
        *,
        options: dict | None = None,
    ) -> IndexStats:
        cfg = resolve_config(options, kind="build")
        start = time.monotonic()

        packets_list = list(packets)
        rows = list(build_rows(packets_list, cfg.fields, cfg.embedding_max_tokens))

        dim = _probe_embedding_dim(cfg)

        conn = open_for_build(
            location,
            embedding_model=cfg.embedding_model or "",
            embedding_dim=dim,
            fields=cfg.fields,
            force=cfg.force,
            fmql_version=fmql_version,
        )
        try:
            existing = fetch_existing_hashes(conn)
            to_embed: list[tuple[str, str, str]] = []
            skipped = 0
            for packet_id, chash, doc in rows:
                prev = existing.get(packet_id)
                if prev is not None and prev[1] == chash:
                    skipped += 1
                    continue
                to_embed.append((packet_id, chash, doc))

            current_ids = {pid for pid, _, _ in rows}
            removed_rowids = [rid for pid, (rid, _) in existing.items() if pid not in current_ids]
            removed = delete_packets(conn, removed_rowids)
            conn.commit()

            indexed = 0
            if to_embed:
                indexed = asyncio.run(_embed_and_write(conn, to_embed, cfg))

            conn.commit()
            elapsed = time.monotonic() - start
            return IndexStats(
                packets_indexed=indexed,
                packets_skipped=skipped,
                packets_removed=removed,
                elapsed_seconds=elapsed,
            )
        finally:
            conn.close()

    def query(
        self,
        text: str,
        location: str,
        *,
        k: int = 10,
        options: dict | None = None,
    ) -> list[SearchHit]:
        cfg = resolve_config(options, kind="query")
        if not text or k <= 0:
            return []

        conn = open_db(location, readonly=True, load_vec=not cfg.sparse_only)
        try:
            meta = meta_mod.read_all(conn)
            meta_mod.check_format_version(meta)
            if not cfg.sparse_only and cfg.embedding_model:
                meta_mod.check_model_pin(meta, cfg.embedding_model)

            fetch_k = cfg.fetch_k or max(k * 4, 50)

            if cfg.dense_only:
                qvec = _embed_query(text, cfg)
                hits = dense_search(conn, qvec, fetch_k=fetch_k)
                return [SearchHit(packet_id=pid, score=score) for pid, score in hits[:k]]

            if cfg.sparse_only:
                hits = sparse_search(conn, text, fetch_k=fetch_k)
                return [SearchHit(packet_id=pid, score=score) for pid, score in hits[:k]]

            qvec = _embed_query(text, cfg)
            dense = dense_search(conn, qvec, fetch_k=fetch_k)
            sparse = sparse_search(conn, text, fetch_k=fetch_k)
            fused = reciprocal_rank_fusion(dense, sparse)

            if cfg.reranker_model and not cfg.rerank_disabled and fused:
                reranked = _apply_rerank(conn, text, fused, cfg)
                if reranked is not None:
                    return [SearchHit(packet_id=pid, score=score) for pid, score in reranked[:k]]

            return [SearchHit(packet_id=pid, score=score) for pid, score in fused[:k]]
        finally:
            conn.close()

    def info(self, location: str | None = None) -> BackendInfo:
        meta_out: dict = {}
        if location:
            try:
                conn = open_db(location, readonly=True, load_vec=False)
                try:
                    raw = meta_mod.read_all(conn)
                finally:
                    conn.close()
                try:
                    meta_mod.check_format_version(raw)
                    meta_out = {
                        "format_version": raw.get("format_version"),
                        "embedding_model": raw.get("embedding_model"),
                        "embedding_dim": raw.get("embedding_dim"),
                        "fields": raw.get("fields"),
                        "built_at": raw.get("built_at"),
                        "location": location,
                    }
                except IndexVersionError as e:
                    meta_out = {"location": location, "error": str(e)}
            except FileNotFoundError:
                meta_out = {"location": location, "error": "index not found"}
            except Exception as e:
                meta_out = {"location": location, "error": f"{type(e).__name__}: {e}"}
        return BackendInfo(
            name=self.name,
            version=semantic_version,
            kind="indexed",
            metadata=meta_out,
        )


# ---------------------------------------------------------------------------- helpers


def _probe_embedding_dim(cfg: Config) -> int:
    vecs = asyncio.run(
        _embed_batch(
            ["fmql semantic dimension probe"],
            model=cfg.embedding_model or "",
            api_base=cfg.embedding_api_base,
            api_key=cfg.embedding_api_key,
        )
    )
    if not vecs or not vecs[0]:
        raise BackendUnavailableError("embedding probe returned empty result")
    return len(vecs[0])


async def _embed_and_write(conn, to_embed: list[tuple[str, str, str]], cfg: Config) -> int:
    batch_size = max(1, cfg.embedding_batch_size)
    concurrency = max(1, cfg.embedding_concurrency)
    sem = asyncio.Semaphore(concurrency)

    async def _one_batch(rows_chunk: list[tuple[str, str, str]]):
        async with sem:
            vecs = await _embed_batch(
                [doc for _, _, doc in rows_chunk],
                model=cfg.embedding_model or "",
                api_base=cfg.embedding_api_base,
                api_key=cfg.embedding_api_key,
            )
            return rows_chunk, vecs

    chunks = [to_embed[i : i + batch_size] for i in range(0, len(to_embed), batch_size)]
    tasks = [asyncio.create_task(_one_batch(c)) for c in chunks]

    indexed = 0
    with progress(len(to_embed), desc="embedding") as bar:
        try:
            for coro in asyncio.as_completed(tasks):
                rows_chunk, vecs = await coro
                upsert_batch(conn, rows_chunk, vecs)
                conn.commit()
                indexed += len(rows_chunk)
                bar.update(len(rows_chunk))  # type: ignore[attr-defined]
        except BaseException:
            for t in tasks:
                if not t.done():
                    t.cancel()
            raise
    return indexed


def _embed_query(text: str, cfg: Config) -> list[float]:
    vecs = asyncio.run(
        _embed_batch(
            [text],
            model=cfg.embedding_model or "",
            api_base=cfg.embedding_api_base,
            api_key=cfg.embedding_api_key,
        )
    )
    return vecs[0]


def _apply_rerank(
    conn,
    query: str,
    fused: Sequence[tuple[str, float]],
    cfg: Config,
) -> list[tuple[str, float]] | None:
    top = list(fused[: cfg.reranker_top_n])
    ids = [pid for pid, _ in top]
    placeholders = ",".join("?" * len(ids))
    rows = conn.execute(
        f"SELECT p.packet_id, f.content "
        f"FROM packets p JOIN packets_fts f ON p.id = f.rowid "
        f"WHERE p.packet_id IN ({placeholders})",
        ids,
    ).fetchall()
    doc_map = {pid: content for pid, content in rows}
    documents = [doc_map.get(pid, "") for pid in ids]
    ordering = rerank(query, documents, cfg=cfg)
    if ordering is None:
        return None
    return [(ids[idx], score) for idx, score in ordering]
