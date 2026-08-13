# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

Complete, not under active development (2026-08-12) — see `POSTMORTEM.md`. The
bot is stable and stays deployed as-is. The only known gap is playing
age/login-gated YouTube videos, which is a structural limitation of the
`youtube-plugin` client architecture, not something fixable here (full
writeup in the post-mortem). Don't propose new features or start re-chasing
that gap without reading it first — it wasn't for lack of trying.

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
- `YOUTUBE_OAUTH_REFRESH_TOKEN` — optional, needed for reliable YouTube playback from datacenter IPs; see `DEPLOYMENT.md` for the device-login flow that produces it

No test suite, linter, or build step is currently configured in this repo.

For production deployment (Hetzner VPS setup, deploy keys, the YouTube OAuth device-login flow, scaling to multiple Lavalink nodes), see `DEPLOYMENT.md`.

## Architecture

- `bot/bot.py` — entrypoint. Builds the `MusicBot` (`commands.Bot` subclass), connects to the Lavalink node via `wavelink.Pool.connect` in `setup_hook`, opens the `HistoryStore` (`self.history`), loads `cogs.music`, then syncs the slash-command tree (globally, plus instantly to any `GUILD_IDS` for dev).
- `bot/cogs/music.py` — all slash commands (`/play`, `/skip`, `/pause`, `/resume`, `/stop`, `/leave`, `/queue`, `/nowplaying`, `/volume`, `/history list|shuffle|remove`) live in the single `Music` cog. Playback state (current track, queue) is held entirely on `wavelink.Player` (attached as the guild's voice client) and its `.queue`, and is not persisted. Auto-advance to the next queued track happens in the `on_wavelink_track_end` listener.
  - Direct-URL track lookups (a pasted YouTube link, or a stored history URI) can fail even when the video is playable, because Lavalink's unauthenticated load path doesn't use the OAuth token (only the `TV` client does, and it has no metadata/load support at all, so it can't be used there — see `lavalink/application.yml` below and `POSTMORTEM.md` for why this is a dead end, not a config gap). `_search_with_fallback` (used by `/play`) and `_resolve_history_track` (used by `/history shuffle`) both retry as a title search when the direct lookup comes up empty — the title for the `/play` case comes from YouTube's public oEmbed endpoint (`_oembed_title`), since Lavalink itself couldn't load the video. Fallback matches are unconfirmed (could be the wrong video with a matching title), so `/play` skips recording them to history.
- `bot/history_store.py` — `HistoryStore`, an `aiosqlite`-backed store of per-guild play history (one deduped row per unique song per guild, keyed on `(guild_id, source, identifier)`). `/play` records a song the first time it's individually queued (not for bulk playlist adds, and not for fallback-search matches — see above); `/history shuffle` reads a random sample and re-resolves each track's URI through `wavelink.Playable.search` before queueing; `/history remove` deletes a row by id (selected via Discord autocomplete over titles).
- `lavalink/application.yml` — Lavalink server config. YouTube is deliberately disabled as a built-in source (`sources.youtube: false`) in favor of the `youtube-plugin` jar in `lavalink/plugins/`, which is the currently-supported way to play YouTube audio through Lavalink. Also configures the plugin's OAuth (token supplied via the `YOUTUBE_OAUTH_REFRESH_TOKEN` env var, never committed) and a `remoteCipher` service to solve YouTube's signature cipher — both exist to keep YouTube playback working from datacenter IPs, which otherwise get blocked; see `DEPLOYMENT.md` for the full explanation and setup flow.
- `lavalink/compressor-plugin/` — source for a custom Lavalink plugin (Java/Gradle) that adds a `compressor` pluginFilter: a two-stage loudness leveler + limiter that evens out perceived volume across differently-mastered tracks (see `CompressorFilter.java` for the DSP, `CompressorFilterExtension.java` for the Lavalink SPI wiring). It's applied to every player in `bot/cogs/music.py`'s `_ensure_player`. Like `youtube-plugin`, the built jar is placed directly in `lavalink/plugins/` (as `compressor-plugin.jar`) rather than fetched via a `lavalink.plugins:` dependency declaration — `docker-compose.yml` bind-mounts that directory read-write, so a jar baked into a custom image would just get shadowed by the mount. Rebuild after changing the plugin source with:
  ```bash
  cd lavalink/compressor-plugin
  docker run --rm -v "$(pwd)":/src -w /src gradle:8-jdk17 gradle build --no-daemon
  cp build/libs/*.jar ../plugins/compressor-plugin.jar
  ```
  then `docker compose up -d --force-recreate lavalink` to pick it up.
- Adding a new command means adding a method to the `Music` cog in `music.py`; there's no other registration step needed since `bot.py` syncs the whole tree on startup.
- Spotify links don't resolve yet (Spotify's API is metadata-only, so it needs a plugin like LavaSrc to look up the track and play a YouTube match instead) — see `TODO.md` for the planned approach.
