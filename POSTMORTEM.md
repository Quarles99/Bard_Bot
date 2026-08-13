# Post-mortem

**Status: development ended 2026-08-12.** The bot is stable and stays deployed
as-is — every command works except playing age/login-gated YouTube videos,
which fail with a clear in-Discord explanation instead of breaking silently.
This document is for anyone (including a future version of ourselves) who
picks this back up and is tempted to re-investigate YouTube age-gate support.
Short version: we did, thoroughly, and hit a wall in the upstream plugin's
architecture, not a bug that's likely to get fixed.

## What this project was

A Discord music bot (`discord.py` + `wavelink`) backed by a self-hosted
Lavalink node, using `youtube-plugin` (`lavalink-devs/youtube-source`) since
Lavalink dropped its own built-in YouTube source. See `CLAUDE.md` for the
architecture and `DEPLOYMENT.md` for how it's actually run.

## The chain of YouTube problems, in the order we hit them

Each of these was a real, separate failure mode, fixed in order:

1. **Datacenter IP blocking** — YouTube's bot detection flags anonymous
   requests from a VPS with "This video requires login," regardless of
   client. Fix: OAuth (`cd360fc`, `7b09dc6`).
2. **OAuth only works on one client** — of `youtube-plugin`'s clients, only
   `TV` attaches the OAuth token to its requests at all. Added it to the
   client list (`8e11cfc`).
3. **Signature cipher breakage** — once TV cleared the login check, it hit a
   *different* failure: "Must find sig function from script." YouTube's
   player script had changed in a way the plugin's bundled cipher-solver
   couldn't parse. Worked around by offloading cipher-solving to a remote
   service (`9c46f5f`), per the plugin maintainers' own recommendation.
4. **Age/login-gated videos** — the wall this document is about. See below.

Each of 1–3 was fixable from our side (config or infra). #4 was not, and
that's the qualitative difference that ended the project here.

## Why age-gated videos can't be fixed from our side

`youtube-source`'s own README documents a capability table for its clients.
As of **2026-08-12**, on plugin version **1.18.2** (also the latest released
version at the time), it looks like this (columns relevant here only):

| Client | OAuth | Age-restriction | Metadata/Search/Load |
|---|---|---|---|
| `TV` | **Yes** | With OAuth | **None** |
| `WEB`, `MWEB`, `ANDROID`, `ANDROID_MUSIC`, `ANDROID_VR`, `IOS`, `TVHTML5_SIMPLY`, `MUSIC` | No | No | Yes |
| `WEBEMBEDDED` | No | Limited | Video only |

The load step (metadata lookup, search, resolving a URL to a playable track)
and the playback step (actually streaming audio) are handled by different
clients, and **no single client does both with OAuth**:

- **Load step: structurally impossible to authenticate.** `TV` is the only
  OAuth-capable client, and it has *no* metadata/search support at all — it
  can't be used for loading, full stop. Every client that *can* load has
  OAuth = No. This is why `/play`ing a login-gated URL directly always fails
  the initial lookup (`_search_with_fallback` in `bot/cogs/music.py`), and
  why the oEmbed-title fallback search can't help either — a plain search
  still resolves to unauthenticated clients, so it only succeeds for videos
  that don't actually require sign-in (the softer "inappropriate for some
  users" content-check case, not the hard login-required case — see below).
- **Playback step: OAuth-capable in principle, broken in practice.** `TV` can
  stream once given a track, and is the documented OAuth-capable client for
  that step. But production logs confirmed it fails on actual age/login-gated
  videos regardless, with `"The page needs to be reloaded"` — an
  unrelated failure inside the plugin's InnerTube playability check, tracked
  upstream as
  [lavalink-devs/youtube-source#226](https://github.com/lavalink-devs/youtube-source/issues/226).
  As of 2026-08-12 that issue is **open with zero comments or linked fixes**,
  and there is no unreleased patch or open PR addressing it (the only
  tangentially related open PR, #202, is about reverting the removal of a
  different client used for metadata loading, not this failure).

Put together: even if the playback bug in #226 got fixed tomorrow, the load
step still couldn't produce an authenticated result to hand to it. Both
halves would need fixing, in a client architecture that currently has no
client that does both. That's a structural limitation of the plugin, not a
bug list item — hence "wall," not "blocker."

## What we checked and ruled out, so it isn't re-litigated

- **`poToken`** — upstream docs are explicit that it only applies to `WEB`
  and `WEBEMBEDDED`, and doesn't substitute for OAuth. It wouldn't touch the
  login-required (`LOGIN_REQUIRED`) case at all.
- **Newer plugin version** — 1.18.2 was the latest release as of 2026-08-12;
  there's nothing to upgrade to.
- **`WEBEMBEDDED`'s "Limited" age-restriction support** — likely explains why
  the softer content-check-required case (YouTube's own "inappropriate for
  some users" wording) already plays fine via search, while the harder
  login-required case doesn't. This is a plausible read of the capability
  table, **not confirmed** against production logs — worth checking first if
  picked back up, before assuming it's settled.
- **A different OAuth token, or re-running the device-login flow** — #226 is
  a client-side parsing/protocol failure (see its stack trace: it dies in
  `getPlayabilityStatus`, not in token validation), so it reproduces
  regardless of which account or token is used.

## What's shipped instead

Both places this failure can surface give the user a clear explanation
instead of a silent failure or a crash:

- `bot/cogs/music.py`, `/play` command — the direct-load path detects the
  age-restriction error message and says so instead of a generic "no
  results."
- `bot/cogs/music.py`, `on_wavelink_track_exception` — catches the case where
  a *search* result looked fine when queued (search results aren't
  playability-checked up front) and only fails once Lavalink tries to stream
  it.

Both point at this document for anyone who wants the full story.

## If you pick this back up

Start by re-pulling `youtube-source`'s README client table and issue tracker
— don't trust the table above once time has passed. Look specifically for:
a client added *after* 1.18.2 that combines OAuth with metadata/load support,
or a resolution on #226. Short of that, the only paths we didn't fully
exhaust: confirming the `WEBEMBEDDED` hypothesis above against real logs, and
whether Lavalink's `AudioFilterExtension`/plugin API would let a from-scratch
client implementation do both — a much larger undertaking than anything
config-level, and out of scope for what this project was trying to be.
