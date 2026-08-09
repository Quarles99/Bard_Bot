# Deployment Guide

Deploying Bard Bot to a Hetzner Cloud VPS. No code changes are needed — the
existing `docker-compose.yml` stack (bot + Lavalink) runs as-is on any server
with Docker installed.

## 1. Create the server

1. Sign up / log in at [console.hetzner.cloud](https://console.hetzner.cloud).
2. Create a new project (or use an existing one).
3. **Add Server**:
   - **Location**: pick one close to most of your Discord servers' members.
   - **Image**: Ubuntu 24.04.
   - **Type**: Shared Resources → Cost-Optimized → **CX23** (2 vCPU / 4GB RAM)
     to start. If it shows as unavailable in your region, fall back to
     Regular Performance at a similar price point.
   - **SSH key**: add your public key here (avoids password auth entirely).
   - Leave the rest at defaults, create the server.
4. Note the server's public IPv4 address.

## 2. Initial server setup

SSH in as root:

```bash
ssh root@<server-ip>
```

Update packages and install Docker (includes the Compose plugin):

```bash
apt update && apt upgrade -y
curl -fsSL https://get.docker.com | sh
systemctl enable --now docker
```

(Optional but recommended) create a non-root user for day-to-day use:

```bash
adduser deploy
usermod -aG docker,sudo deploy
```

Then reconnect as `ssh deploy@<server-ip>` for the rest of these steps.

Set up a basic firewall — you only need SSH open; Lavalink's port (2333) is
never exposed publicly since it's only reachable from the `bot` container on
the internal Docker network:

```bash
ufw allow OpenSSH
ufw enable
```

## 3. Deploy the bot

This repo is **private**. Set up a deploy key so the server can clone/pull it
without using your personal GitHub credentials:

```bash
ssh-keygen -t ed25519 -C "bard-bot-deploy" -N "" -f ~/.ssh/id_ed25519
cat ~/.ssh/id_ed25519.pub
```

Copy that output, then on GitHub go to the repo's
**Settings → Deploy keys → Add deploy key**, paste it in, and leave
**"Allow write access" unchecked** (the server only needs to pull).

Clone via SSH (first connection will ask you to confirm GitHub's host key —
type `yes`):

```bash
git clone git@github.com:Quarles99/Bard_Bot.git
cd Bard_Bot
```

Create your `.env` from the example and fill in real values:

```bash
cp .env.example .env
nano .env
```

```
DISCORD_TOKEN=your-real-bot-token
LAVALINK_PASSWORD=some-long-random-password
```

`LAVALINK_PASSWORD` just needs to match between the `bot` and `lavalink`
containers — `docker-compose.yml` already passes it to both, so you don't need
to touch `lavalink/application.yml`.

**YouTube playback**: from a datacenter IP (like this server's), YouTube's
bot detection tends to block anonymous requests with "This video requires
login" regardless of which client the `youtube-plugin` uses. The fix is
OAuth, already enabled in `lavalink/application.yml`
(`plugins.youtube.oauth.enabled: true`):

1. Leave `YOUTUBE_OAUTH_REFRESH_TOKEN` unset in `.env` and start the stack —
   Lavalink will log a Google device-login URL and code.
2. Open that URL in any browser, enter the code, and sign in with a
   **burner Google account, not your primary one** (per the plugin's own
   warning — there's some risk to the linked account, so don't use one you
   care about).
3. Lavalink then logs a refresh token
   (`docker compose logs lavalink | grep "refresh token"`). Paste it into
   `.env` as `YOUTUBE_OAUTH_REFRESH_TOKEN=...` and
   `docker compose restart lavalink` so it's reused instead of repeating
   the login flow on every restart.

Build and start everything in the background:

```bash
docker compose up -d --build
```

Both containers are set to `restart: unless-stopped`, so they'll come back
automatically after a crash or server reboot (Docker itself is already
enabled to start on boot from step 2).

## 4. Verify it's running

```bash
docker compose ps
docker compose logs -f bot
```

You should see the "Logged in as ..." line and the slash-command sync log
from `bot.py`. Ctrl+C to stop following logs (containers keep running).

If commands don't show up in Discord right away: global sync can take up to
an hour to propagate. For instant sync during setup/testing, add your test
server's ID to `GUILD_IDS` in `.env` (comma-separated for multiple), then
restart: `docker compose restart bot`.

## 5. Updating the bot later

```bash
cd Bard_Bot
git pull
docker compose up -d --build
```

This rebuilds only the `bot` image (Lavalink's image is pulled from the
registry, not built locally) and recreates containers with zero manual
cleanup needed.

## 6. Scaling up later

- **More load on the same box**: resize the Hetzner server in the console
  (Server → Rescale) to a bigger type (e.g. CX23 → CX33). Takes a few
  minutes of downtime, same disk/IP/setup — no redeploy needed.
- **Beyond one box**: `bot/bot.py` connects via
  `wavelink.Pool.connect(nodes=[...])`, so adding a second Lavalink node
  (on this box or another) is just adding another `wavelink.Node(...)` entry
  to that list — wavelink load-balances players across whatever nodes are
  registered.
