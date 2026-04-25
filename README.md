# Headache Tracker Telegram Bot

Personal Telegram bot for daily headache tracking. Produces structured SQLite data for neurologist review.

## Prerequisites

1. **Telegram Bot Token** — Message [@BotFather](https://t.me/BotFather) on Telegram. Send `/newbot`, follow the prompts. Copy the token (looks like `123456789:ABCdef...`).
2. **OpenWeatherMap API Key** — Register at [openweathermap.org](https://openweathermap.org/api). Subscribe to the free "Current Weather Data" plan. Your API key appears in your account dashboard.
3. **Your Telegram User ID** — Message [@userinfobot](https://t.me/userinfobot). It replies with your numeric user ID. This is what goes in `AUTHORIZED_USER_ID`.

## Proxmox LXC Setup

### 1. Create the LXC container

In Proxmox, go to **Create CT**:
- Template: Debian 12 (bookworm)
- CPU: 1 core
- Memory: 512 MB
- Disk: 4 GB
- Network: DHCP or static IP

After creation, go to **Options → Features** and enable:
- `nesting=1`
- `keyctl=1`

These are required for Docker to run inside an LXC container.

### 2. Install Docker inside the LXC

Start the container and open a console:

```bash
curl -fsSL https://get.docker.com | sh
usermod -aG docker $USER
newgrp docker
docker run hello-world
```

### 3. Install Komodo

Komodo is a Docker/Compose management UI. Install the Komodo Periphery agent on the LXC (it connects to a central Komodo Core instance):

```bash
curl -sSL https://raw.githubusercontent.com/mbecker20/komodo/main/scripts/setup-periphery.py | python3
```

Follow the prompts to connect the agent to your Komodo Core URL and generate an API key. Once connected, the LXC will appear as a server in your Komodo dashboard.

If you don't have a Komodo Core instance yet, deploy one first — see the [Komodo docs](https://komo.do/docs/introduction).

## Deployment via Komodo

### Option A: Stack from Git repository (recommended)

1. In Komodo: **Stacks → New Stack**
2. Set **Server** to your LXC
3. Set **Source** to Git and enter your repository URL
4. Under **Environment**, add:
   ```
   TELEGRAM_BOT_TOKEN=your_token
   OWM_API_KEY=your_owm_key
   AUTHORIZED_USER_ID=your_telegram_id
   TZ=Asia/Jerusalem
   ```
5. Click **Deploy**

Komodo will clone the repo, run `docker compose up -d`, and track the stack.

### Option B: Stack from compose file

1. In Komodo: **Stacks → New Stack**
2. Set **Server** to your LXC
3. Set **Source** to UI and paste the contents of `docker-compose.yml`
4. Add the same environment variables as Option A
5. Click **Deploy**

## Place the Head Map Image

Upload the labeled head illustration to the data directory on the LXC:

```bash
scp head_map.png root@<LXC_IP>:/path/to/project/data/head_map.png
```

The bot loads it from `/app/data/head_map.png` inside the container (bind-mounted from `./data`). If the file is missing, the bot sends text only and logs a warning — it will not crash.

## Verify Deployment

```bash
docker logs headache-bot --tail 50
```

Expected output:
```
... INFO database: Database initialized at /app/data/headaches.db
... INFO bot: Daily check-in scheduled at 18:00 (Asia/Jerusalem)
... INFO bot: Bot starting (polling)...
```

Send `/start` to your bot in Telegram. You should receive the Hebrew welcome message.

## Backups

**Export DB manually:**
```bash
docker cp headache-bot:/app/data/headaches.db ./headaches_backup_$(date +%Y%m%d).db
```

**LXC snapshots in Proxmox** cover the entire container filesystem including the bind-mounted `./data` directory. Take a snapshot before updates.

## Updating

```bash
git pull
```

Then in Komodo: open the stack → **Reclone & Redeploy** (or just **Redeploy** if using a branch that auto-pulls).

## Troubleshooting

| Symptom | Check |
|---|---|
| Timezone wrong in logs | Verify `TZ=Asia/Jerusalem` in your Komodo stack environment vars |
| Daily check-in not firing at 18:00 | Run `docker logs headache-bot` at 18:05 and look for "Daily check-in" entries |
| Weather always NULL | Test your OWM key: `curl "https://api.openweathermap.org/data/2.5/weather?lat=32.0556&lon=34.8550&units=metric&appid=YOUR_KEY"` |
| Bot not responding | Confirm `AUTHORIZED_USER_ID` matches your actual Telegram ID (get it from @userinfobot) |
| Docker won't start in LXC | Ensure `nesting=1` and `keyctl=1` are set in Proxmox LXC Options → Features |
