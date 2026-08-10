# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Discord music bot built on `discord.py` + `wavelink`, with a Lavalink audio server (via the `youtube-plugin`) doing the actual track search/streaming. Two containers, orchestrated by `docker-compose.yml`: `lavalink` (audio node) and `bot` (Discord client).

## Running

```bash
cp .env.example .env   # then fill in DISCORD_TOKEN and LAVALINK_PASSWORD
docker compose up --build
```

There is no local (non-Docker) run path documented — the bot connects to the Lavalink node at `LAVALINK_HOST:LAVALINK_PORT` (defaults `lavalink:2333`, matching the Docker service name), so running `bot.py` outside Docker requires a reachable Lavalink instance and `LAVALINK_HOST` pointed at it.

Required env vars (see `.env.example`):
- `DISCORD_TOKEN` — bot token
- `LAVALINK_PASSWORD` — must match `lavalink/application.yml` (overridden there via `LAVALINK_SERVER_PASSWORD`)
- `GUILD_IDS` — optional, comma-separated guild IDs for instant slash-command sync during dev (global sync can take up to an hour to propagate)
- `DB_PATH` — optional, path to the SQLite play-history database (defaults to `data/history.db`; in Docker this is `/app/data/history.db`, backed by the `./data` bind mount in `docker-compose.yml`)

No test suite, linter, or build step is currently configured in this repo.

## Architecture

- `bot/bot.py` — entrypoint. Builds the `MusicBot` (`commands.Bot` subclass), connects to the Lavalink node via `wavelink.Pool.connect` in `setup_hook`, opens the `HistoryStore` (`self.history`), loads `cogs.music`, then syncs the slash-command tree (globally, plus instantly to any `GUILD_IDS` for dev).
- `bot/cogs/music.py` — all slash commands (`/play`, `/skip`, `/pause`, `/resume`, `/stop`, `/leave`, `/queue`, `/nowplaying`, `/volume`, `/history list|shuffle|remove`) live in the single `Music` cog. Playback state (current track, queue) is held entirely on `wavelink.Player` (attached as the guild's voice client) and its `.queue`, and is not persisted. Auto-advance to the next queued track happens in the `on_wavelink_track_end` listener.
- `bot/history_store.py` — `HistoryStore`, an `aiosqlite`-backed store of per-guild play history (one deduped row per unique song per guild, keyed on `(guild_id, source, identifier)`). `/play` records a song the first time it's individually queued (not for bulk playlist adds); `/history shuffle` reads a random sample and re-resolves each track's URI through `wavelink.Playable.search` before queueing; `/history remove` deletes a row by id (selected via Discord autocomplete over titles).
- `lavalink/application.yml` — Lavalink server config. YouTube is deliberately disabled as a built-in source (`sources.youtube: false`) in favor of the `youtube-plugin` jar in `lavalink/plugins/`, which is the currently-supported way to play YouTube audio through Lavalink.
- `lavalink/compressor-plugin/` — source for a custom Lavalink plugin (Java/Gradle) that adds a `compressor` pluginFilter: a two-stage loudness leveler + limiter that evens out perceived volume across differently-mastered tracks (see `CompressorFilter.java` for the DSP, `CompressorFilterExtension.java` for the Lavalink SPI wiring). It's applied to every player in `bot/cogs/music.py`'s `_ensure_player`. Like `youtube-plugin`, the built jar is placed directly in `lavalink/plugins/` (as `compressor-plugin.jar`) rather than fetched via a `lavalink.plugins:` dependency declaration — `docker-compose.yml` bind-mounts that directory read-write, so a jar baked into a custom image would just get shadowed by the mount. Rebuild after changing the plugin source with:
  ```bash
  cd lavalink/compressor-plugin
  docker run --rm -v "$(pwd)":/src -w /src gradle:8-jdk17 gradle build --no-daemon
  cp build/libs/*.jar ../plugins/compressor-plugin.jar
  ```
  then `docker compose up -d --force-recreate lavalink` to pick it up.
- Adding a new command means adding a method to the `Music` cog in `music.py`; there's no other registration step needed since `bot.py` syncs the whole tree on startup.
