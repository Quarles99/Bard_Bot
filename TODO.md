# TODO

**Not being pursued** — development on this project ended (see
`POSTMORTEM.md`). Kept below as reference for anyone forking this to add the
feature themselves.

## Add Spotify support

Currently `/play` supports YouTube and SoundCloud (SoundCloud is native to
Lavalink; YouTube goes through `youtube-plugin`, now working with OAuth +
remote cipher — see `DEPLOYMENT.md`). Spotify links don't resolve at all:
Spotify's API is metadata-only and doesn't allow third-party audio
streaming, so Lavalink needs a plugin that looks up Spotify metadata and
plays the match from a real audio source (YouTube, in our case).

### Plan

1. **Get Spotify API credentials** — create an app at
   [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard)
   (free). Note the Client ID and Client Secret.

2. **Add the [LavaSrc](https://github.com/topi314/LavaSrc) plugin** —
   download the latest `lavasrc-plugin-*.jar` release and drop it in
   `lavalink/plugins/`, alongside `youtube-plugin-1.18.2.jar`.

3. **Configure `lavalink/application.yml`** — add a `plugins.lavasrc` block:
   ```yaml
   plugins:
     lavasrc:
       providers:
         - "ytsearch:\"%ISRC%\""
         - "ytsearch:%QUERY%"
       sources:
         spotify: true
       spotify:
         clientId: "${SPOTIFY_CLIENT_ID}"     # verify LavaSrc's actual env-var substitution syntax
         clientSecret: "${SPOTIFY_CLIENT_SECRET}"
         countryCode: "US"
   ```
   Double-check LavaSrc's README for the current config schema and whether
   it supports the same Spring env-var substitution pattern already used
   for `LAVALINK_SERVER_PASSWORD` and
   `PLUGINS_YOUTUBE_OAUTH_REFRESHTOKEN` in `docker-compose.yml` — if not,
   figure out the equivalent so credentials still don't get committed to
   git (same reasoning as the OAuth refresh token).

4. **Wire credentials through `docker-compose.yml` and `.env.example`** —
   same pattern as `YOUTUBE_OAUTH_REFRESH_TOKEN`: add
   `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` to `.env.example` as
   placeholders, real values only in the server's `.env` (gitignored).

5. **Test**: a track link, a playlist link, and an album link via `/play`.
   No changes should be needed in `bot/cogs/music.py` — Lavalink resolves
   the source from the URL automatically, same as it already does for
   YouTube/SoundCloud.

6. **Update `DEPLOYMENT.md`** with the Spotify credential setup step,
   matching how the YouTube OAuth flow is already documented there.

7. Commit and push, then `git pull` + `docker compose up -d --build lavalink`
   on the server (new plugin jar needs Lavalink to pick it up — restart is
   enough since plugins aren't baked into the image, but double check).
