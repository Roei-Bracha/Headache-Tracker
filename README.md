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

### 3. Install Portainer CE

```bash
docker volume create portainer_data
docker run -d -p 9000:9000 --name portainer \
  --restart=always \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v portainer_data:/data \
  portainer/portainer-ce:latest
```

Access Portainer at `http://<LXC_IP>:9000`.

## Deployment via Portainer

### Option A: Git repository (recommended)

1. In Portainer: **Stacks → Add stack → Git repository**
2. Repository URL: your fork/clone of this repo
3. Under **Environment variables**, add:
   - `TELEGRAM_BOT_TOKEN` = your token
   - `OWM_API_KEY` = your OWM key
   - `AUTHORIZED_USER_ID` = your Telegram numeric ID
   - `TZ` = `Asia/Jerusalem`
4. Click **Deploy the stack**

### Option B: Web editor

1. In Portainer: **Stacks → Add stack → Web editor**
2. Paste the contents of `docker-compose.yml`
3. Add the same environment variables as Option A
4. Click **Deploy the stack**

## Place the Head Map Image

Upload the labeled head illustration to the data directory on the LXC:

```bash
scp head_map.jpg root@<LXC_IP>:/path/to/project/data/head_map.jpg
```

The bot loads it from `/app/data/head_map.jpg` inside the container (bind-mounted from `./data`). If the file is missing, the bot sends text only and logs a warning — it will not crash.

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

Then in Portainer: open the stack → **Pull and redeploy**.

## Troubleshooting

| Symptom | Check |
|---|---|
| Timezone wrong in logs | Verify `TZ=Asia/Jerusalem` in your `.env` or Portainer env vars |
| Daily check-in not firing at 18:00 | Run `docker logs headache-bot` at 18:05 and look for "Daily check-in" entries |
| Weather always NULL | Test your OWM key: `curl "https://api.openweathermap.org/data/2.5/weather?lat=32.0556&lon=34.8550&units=metric&appid=YOUR_KEY"` |
| Bot not responding | Confirm `AUTHORIZED_USER_ID` matches your actual Telegram ID (get it from @userinfobot) |
| Docker won't start in LXC | Ensure `nesting=1` and `keyctl=1` are set in Proxmox LXC Options → Features |
