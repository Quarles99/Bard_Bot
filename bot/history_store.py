import os
from dataclasses import dataclass
from datetime import datetime, timezone

import aiosqlite
import wavelink

SCHEMA = """
CREATE TABLE IF NOT EXISTS track_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    source TEXT NOT NULL,
    identifier TEXT NOT NULL,
    uri TEXT NOT NULL,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    length_ms INTEGER NOT NULL,
    request_count INTEGER NOT NULL DEFAULT 1,
    first_requested_at TEXT NOT NULL,
    last_requested_at TEXT NOT NULL,
    UNIQUE (guild_id, source, identifier)
);
"""


@dataclass
class TrackRecord:
    id: int
    uri: str
    title: str
    author: str
    length_ms: int
    request_count: int
    last_requested_at: str


class HistoryStore:
    def __init__(self, path: str):
        self._path = path
        self._conn: aiosqlite.Connection | None = None

    async def init(self) -> None:
        parent = os.path.dirname(self._path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._conn = await aiosqlite.connect(self._path)
        await self._conn.execute(SCHEMA)
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()

    async def record_play(self, guild_id: int, track: wavelink.Playable) -> None:
        now = datetime.now(timezone.utc).isoformat()
        await self._conn.execute(
            """
            INSERT INTO track_history
                (guild_id, source, identifier, uri, title, author, length_ms,
                 request_count, first_requested_at, last_requested_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            ON CONFLICT (guild_id, source, identifier) DO UPDATE SET
                request_count = request_count + 1,
                last_requested_at = excluded.last_requested_at,
                uri = excluded.uri,
                title = excluded.title
            """,
            (
                guild_id,
                track.source,
                track.identifier,
                track.uri,
                track.title,
                track.author,
                track.length,
                now,
                now,
            ),
        )
        await self._conn.commit()

    async def list_tracks(self, guild_id: int, limit: int | None = None) -> list[TrackRecord]:
        query = (
            "SELECT id, uri, title, author, length_ms, request_count, last_requested_at "
            "FROM track_history WHERE guild_id = ? ORDER BY last_requested_at DESC"
        )
        params: tuple = (guild_id,)
        if limit is not None:
            query += " LIMIT ?"
            params += (limit,)
        async with self._conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()
        return [TrackRecord(*row) for row in rows]

    async def sample_tracks(self, guild_id: int, count: int) -> list[TrackRecord]:
        async with self._conn.execute(
            "SELECT id, uri, title, author, length_ms, request_count, last_requested_at "
            "FROM track_history WHERE guild_id = ? ORDER BY RANDOM() LIMIT ?",
            (guild_id, count),
        ) as cursor:
            rows = await cursor.fetchall()
        return [TrackRecord(*row) for row in rows]

    async def search_titles(self, guild_id: int, query: str, limit: int = 25) -> list[TrackRecord]:
        async with self._conn.execute(
            "SELECT id, uri, title, author, length_ms, request_count, last_requested_at "
            "FROM track_history WHERE guild_id = ? AND title LIKE ? "
            "ORDER BY last_requested_at DESC LIMIT ?",
            (guild_id, f"%{query}%", limit),
        ) as cursor:
            rows = await cursor.fetchall()
        return [TrackRecord(*row) for row in rows]

    async def remove_track(self, guild_id: int, record_id: int) -> TrackRecord | None:
        async with self._conn.execute(
            "SELECT id, uri, title, author, length_ms, request_count, last_requested_at "
            "FROM track_history WHERE guild_id = ? AND id = ?",
            (guild_id, record_id),
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        await self._conn.execute(
            "DELETE FROM track_history WHERE guild_id = ? AND id = ?", (guild_id, record_id)
        )
        await self._conn.commit()
        return TrackRecord(*row)
