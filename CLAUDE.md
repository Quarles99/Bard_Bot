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

No test suite, linter, or build step is currently configured in this repo.

## Architecture

- `bot/bot.py` — entrypoint. Builds the `MusicBot` (`commands.Bot` subclass), connects to the Lavalink node via `wavelink.Pool.connect` in `setup_hook`, loads `cogs.music`, then syncs the slash-command tree (globally, plus instantly to any `GUILD_IDS` for dev).
- `bot/cogs/music.py` — all slash commands (`/play`, `/skip`, `/pause`, `/resume`, `/stop`, `/leave`, `/queue`, `/nowplaying`, `/volume`) live in the single `Music` cog. Playback state is held entirely on `wavelink.Player` (attached as the guild's voice client) and its `.queue` — there is no bot-side persistence or database. Auto-advance to the next queued track happens in the `on_wavelink_track_end` listener.
- `lavalink/application.yml` — Lavalink server config. YouTube is deliberately disabled as a built-in source (`sources.youtube: false`) in favor of the `youtube-plugin` jar in `lavalink/plugins/`, which is the currently-supported way to play YouTube audio through Lavalink.
- Adding a new command means adding a method to the `Music` cog in `music.py`; there's no other registration step needed since `bot.py` syncs the whole tree on startup.
