# Bard_Bot

A self-hosted Discord music bot built on `discord.py` + `wavelink`, backed
by a [Lavalink](https://github.com/lavalink-devs/Lavalink) audio node that
handles the actual track search and streaming.

**Status: complete, not under active development** (2026-08-12). The bot is
stable and stays deployed as-is — everything works except playing
age/login-gated YouTube videos, which fail with an explanation instead of
breaking. See [`POSTMORTEM.md`](POSTMORTEM.md) for why that gap exists and
why it isn't being chased further, and [`CLAUDE.md`](CLAUDE.md) for the
architecture if you're picking this up.

## Features

- Play from YouTube or SoundCloud — search terms, direct links, or
  playlists (Spotify links aren't supported yet; see [`TODO.md`](TODO.md)
  for the planned approach)
- Standard playback controls: skip, pause, resume, stop, leave, queue,
  now-playing, volume
- Per-guild play history, backed by SQLite — list, shuffle a random sample
  back into the queue, or remove a song
- A custom Lavalink filter plugin that evens out perceived loudness across
  differently-mastered tracks, applied automatically to every player
- OAuth + remote-cipher support for the YouTube plugin so playback keeps
  working from datacenter IPs, which YouTube otherwise blocks

## Commands

| Command | Description |
| --- | --- |
| `/play <query>` | Play a search term, URL, or playlist; queues if already playing |
| `/skip` | Skip the current song |
| `/pause` / `/resume` | Pause or resume playback |
| `/stop` | Stop playback and clear the queue |
| `/leave` | Disconnect the bot from voice |
| `/queue` | Show the current queue |
| `/nowplaying` | Show the currently playing song |
| `/volume <0-100>` | Set playback volume |
| `/history list` | Show songs tracked from this server's play history |
| `/history shuffle <count>` | Queue a random sample from play history |
| `/history remove <song>` | Remove a song from play history |

## Running it

Two containers, orchestrated by `docker-compose.yml`: `lavalink` (audio
node) and `bot` (Discord client).

```bash
cp .env.example .env   # then fill in DISCORD_TOKEN and LAVALINK_PASSWORD
docker compose up --build
```

Required env vars (see `.env.example`):

- `DISCORD_TOKEN` — bot token
- `LAVALINK_PASSWORD` — must match `lavalink/application.yml`
- `GUILD_IDS` — optional, comma-separated guild IDs for instant slash-command
  sync during dev (global sync can take up to an hour to propagate)
- `DB_PATH` — optional, path to the SQLite play-history database
- `YOUTUBE_OAUTH_REFRESH_TOKEN` — optional, needed for reliable YouTube
  playback from datacenter IPs; see `DEPLOYMENT.md` for the device-login
  flow that produces it

There is no local (non-Docker) run path — the bot connects to the Lavalink
node at `LAVALINK_HOST:LAVALINK_PORT`, so running `bot.py` outside Docker
requires a reachable Lavalink instance.

For production deployment (VPS setup, deploy keys, the YouTube OAuth
device-login flow, scaling to multiple Lavalink nodes), see
[`DEPLOYMENT.md`](DEPLOYMENT.md).

## Architecture

- `bot/bot.py` — entrypoint; builds the bot, connects to Lavalink, opens the
  history store, loads the `Music` cog, syncs slash commands.
- `bot/cogs/music.py` — all slash commands live in a single `Music` cog.
  Playback state lives entirely on the `wavelink.Player`, not persisted.
- `bot/history_store.py` — `aiosqlite`-backed per-guild play history.
- `lavalink/application.yml` — Lavalink config; YouTube goes through the
  `youtube-plugin` jar (not Lavalink's built-in source) with OAuth and a
  remote cipher service to stay working from datacenter IPs.
- `lavalink/compressor-plugin/` — a custom Lavalink Java plugin adding a
  loudness-leveling audio filter, applied to every player.

See [`CLAUDE.md`](CLAUDE.md) for the full architecture writeup.

## Known limitation

Age/login-gated YouTube videos can't be played — Lavalink's unauthenticated
load path doesn't use the OAuth token, and the one client that does support
OAuth has no metadata/load support at all. This is a structural limitation
of the `youtube-plugin` client architecture, not a config gap. Full
explanation in [`POSTMORTEM.md`](POSTMORTEM.md).
