---
name: server-status
description: Report Bard_Bot server health - host uptime/load, container up/down status and restart counts, CPU/RAM usage, and recent crashes or errors from the bot and lavalink logs. Use when the user asks for server status, a health check, uptime, resource usage, or to check for recent crashes/errors, or at the start of a session on this remote server.
---

# Server status

Run these checks and report a concise summary. Don't just dump raw output — synthesize it into the table/bullets below.

## 1. Host uptime and load

```bash
uptime
```

## 2. Container status and restart counts

```bash
docker compose ps
docker inspect -f '{{.Name}}: started={{.State.StartedAt}} restarts={{.RestartCount}} exitcode={{.State.ExitCode}}' lavalink musicbot
```

## 3. CPU / RAM usage

```bash
docker stats --no-stream
```

## 4. Recent crashes or errors (last 24h by default; widen the window if the user asks for a longer lookback)

```bash
docker compose logs bot --since 24h 2>&1 | grep -iE "error|exception|traceback|crash" | tail -30
docker compose logs lavalink --since 24h 2>&1 | grep -iE "error|exception|crash" | tail -30
```

## Reporting

Summarize as a short table: host uptime/load, each container's up-time and restart count, CPU%/RAM per container, and a "recent errors" line. If restart count is 0 and no matches from step 4, say so plainly rather than padding the report.

When triaging errors found in step 4, check whether they're already-understood/benign cases before flagging them as concerning:
- Occasional Lavalink `AllClientsFailedException` / "Video player configuration error" on specific YouTube video IDs is a known, non-fatal case — `bot/cogs/music.py`'s search-fallback path (`_search_with_fallback`, `_resolve_history_track`, documented in `CLAUDE.md`) is designed to recover from exactly this by retrying as a title search.
- Anything else (repeated container restarts, unhandled Python tracebacks in the bot, Lavalink failing to bind/connect) should be called out clearly, with the relevant log lines quoted.
