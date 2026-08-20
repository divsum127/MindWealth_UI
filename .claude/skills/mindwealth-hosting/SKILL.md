---
name: mindwealth-hosting
description: >-
  Host and operate MindWealth Alpha Terminal (Nuxt SSR) at www.mindwealth.co.
  Covers EC2 systemd deploy, nginx reverse proxy, Hostinger DNS, Let's Encrypt SSL,
  redeploys, and troubleshooting. Use when the user asks about mindwealth.co hosting,
  domain DNS, nginx, certbot, SSL, redeploying the frontend, or changing production URL/config.
---

# MindWealth Hosting (www.mindwealth.co)

## Architecture (read first)

```
Browser → www.mindwealth.co (Hostinger DNS)
       → EC2 51.20.53.218:443/80 (nginx)
       → 127.0.0.1:8512 (Nuxt SSR, mindwealth-ui.service)
       → 127.0.0.1:8506 (FastAPI, mindwealth-api.service)
```

| Layer | Detail |
|-------|--------|
| App | Nuxt 3 SSR — **not** static files; 40+ `server/api/*` routes proxy to backend |
| Domain registrar / DNS | Hostinger hPanel |
| Compute | AWS EC2 `51.20.53.218` (same box as API) |
| Public entry | nginx reverse proxy (not direct port 8512 for production domain) |
| Process manager | `mindwealth-ui.service` (systemd) |
| Prod repo | `/home/ubuntu/MindwealthUI_Vue_prod` — branch `presentation-prod`, **pull-only** |
| Dev repo | `/home/ubuntu/MindwealthUI_Vue` — branch `ui-dev`, serves `:8514` only |
| Node | v20.20.2 via nvm |

**Do not** deploy this app to Hostinger shared WordPress/PHP hosting. It requires Node.js SSR.

### Production isolation (read before any build)

| | Dev | Production |
|---|---|---|
| Tree | `/home/ubuntu/MindwealthUI_Vue` | `/home/ubuntu/MindwealthUI_Vue_prod` |
| Branch | `ui-dev` | `presentation-prod` (pinned, pull-only) |
| Unit | `mindwealth-ui-dev.service` | `mindwealth-ui.service` |
| Port | `8514` | `8512` (nginx → `www.mindwealth.co`) |

Until 2026-08-18 both units shared `WorkingDirectory=/home/ubuntu/MindwealthUI_Vue` and a **relative**
`ExecStart=node .output/server/index.mjs`, so they resolved to one build. A dev `npm run build`
overwrote the bundle prod would load at its next start, and `Restart=on-failure` could promote it with
no operator present. `ExecStart` is now absolute in both units so a `WorkingDirectory` edit cannot
silently repoint a service again.

Rules that follow from this:

- Build for prod **only** in `MindwealthUI_Vue_prod`. Never build in the dev tree and restart `mindwealth-ui`.
- The prod clone is pull-only. Do not use it as a workspace — the deploy script refuses to run on a dirty tree.
- Invoke the prod deploy script from the **dev** tree (`/home/ubuntu/MindwealthUI_Vue/scripts/fetch-and-reload.sh`); the tracked copy inside the prod clone is stale until `scripts/` is merged to `presentation-prod`.
- `sudo systemctl restart mindwealth-ui` is a deploy. Confirm with the user before running it.

---

## Key paths and files

| File | Purpose |
|------|---------|
| `scripts/mindwealth.co.nginx` | nginx site template (repo source of truth) |
| `/etc/nginx/sites-available/mindwealth.co` | Installed nginx config |
| `scripts/mindwealth-ui.service` | systemd unit template (prod) |
| `/etc/systemd/system/mindwealth-ui.service` | Installed systemd unit |
| `/etc/systemd/system/mindwealth-ui.service.d/secrets.conf` | `NUXT_API_KEY` drop-in, root `0600`, **not** in git |
| `nuxt.config.ts` | `NUXT_*` runtime config defaults |
| `started.md` | EC2/systemd deploy guide (no domain-specific steps) |

---

## Current state checklist

Run these before any hosting change to see what is already done:

```bash
# DNS — should be 51.20.53.218 when live
dig +short mindwealth.co A
dig +short www.mindwealth.co A

# App + proxy
systemctl is-active mindwealth-ui nginx

# Confirm prod is running from the PROD tree, not the dev checkout
systemctl show mindwealth-ui -p WorkingDirectory -p ExecStart
curl -s -o /dev/null -w "UI direct: %{http_code}\n" http://127.0.0.1:8512/
curl -s -o /dev/null -w "nginx proxy: %{http_code}\n" -H "Host: www.mindwealth.co" http://127.0.0.1/

# API dependency
curl -s http://127.0.0.1:8506/api/v1/health | jq

# SSL
sudo certbot certificates | grep -A3 mindwealth || echo "no cert yet"
```

**Known pending (as of initial setup):** DNS may still point to Hostinger WordPress (`191.101.79.86`). HTTPS cert not issued until DNS points to EC2.

---

## Workflows

### 1. First-time domain go-live

1. **EC2 app running** — follow `started.md` or redeploy workflow below.
2. **Install nginx site** (if missing):
   ```bash
   sudo mkdir -p /var/www/mindwealth
   sudo chown www-data:www-data /var/www/mindwealth
   sudo cp /home/ubuntu/MindwealthUI_Vue/scripts/mindwealth.co.nginx /etc/nginx/sites-available/mindwealth.co
   sudo ln -sf /etc/nginx/sites-available/mindwealth.co /etc/nginx/sites-enabled/
   sudo nginx -t && sudo systemctl reload nginx
   ```
3. **Hostinger DNS** — hPanel → Domains → `mindwealth.co` → DNS Zone:
   - `@` A record → `51.20.53.218`
   - `www` CNAME → `mindwealth.co` (or A → `51.20.53.218`)
   - TTL: default (14400) is fine
4. **Wait for DNS** (5–30 min). Verify: `dig +short www.mindwealth.co A` → `51.20.53.218`
5. **Issue SSL** (after DNS propagates):
   ```bash
   sudo certbot --nginx -d mindwealth.co -d www.mindwealth.co
   ```
6. **Verify**: `curl -sI https://www.mindwealth.co | head -5`

**WordPress note:** Changing root DNS replaces the old WordPress site on `www.mindwealth.co`. Keep WordPress on a subdomain (e.g. `blog.mindwealth.co`) if still needed.

### 2. Redeploy after code changes

**Production builds from its own clone.** Prod (`:8512`) and dev (`:8514`) had one shared
`WorkingDirectory` and one `.output` until 2026-08-18, so a dev `npm run build` overwrote the
bundle prod loaded at its next start — including an unattended `Restart=on-failure`. Never build
in `/home/ubuntu/MindwealthUI_Vue` and restart `mindwealth-ui`.

Preferred — the deploy script, invoked from the dev tree (it targets the prod tree by absolute
path; the copy inside the prod clone is stale until `scripts/` is merged to `presentation-prod`):

```bash
bash /home/ubuntu/MindwealthUI_Vue/scripts/fetch-and-reload.sh
```

Manual equivalent:

```bash
cd /home/ubuntu/MindwealthUI_Vue_prod
export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh" && nvm use 20
git fetch origin presentation-prod && git merge --ff-only origin/presentation-prod
npm ci               # lockfile-exact; only needed if package-lock.json changed
npm run build
sudo systemctl restart mindwealth-ui
sudo systemctl status mindwealth-ui
curl -s -o /dev/null -w "root HTTP %{http_code}\n" http://127.0.0.1:8512/
curl -s -o /dev/null -w "meta HTTP %{http_code}\n" http://127.0.0.1:8512/api/meta
```

`/` must be 200. `/api/meta` returns **401** unauthenticated — that is healthy (BFF up, auth gate
rejecting the probe). Do not health-check it with `curl -sf`; `-f` treats 401 as an error and aborts
the deploy under `set -e`.

Restarting `mindwealth-ui` changes what the public site serves — confirm with the user first.

No nginx reload needed unless `scripts/mindwealth.co.nginx` changed.

### 3. Change nginx config

1. Edit `scripts/mindwealth.co.nginx` in repo (keep as source of truth).
2. Install and reload:
   ```bash
   sudo cp /home/ubuntu/MindwealthUI_Vue/scripts/mindwealth.co.nginx /etc/nginx/sites-available/mindwealth.co
   sudo nginx -t && sudo systemctl reload nginx
   ```
3. If certbot already ran, it may have added SSL blocks to the live file — merge SSL server block from `/etc/nginx/sites-available/mindwealth.co` back into repo template or re-run certbot after overwrite.

### 4. Change runtime env (API URL, admin mode, API key)

Edit `scripts/mindwealth-ui.service`, then:

```bash
sudo cp /home/ubuntu/MindwealthUI_Vue/scripts/mindwealth-ui.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl restart mindwealth-ui
```

| Variable | Default | Notes |
|----------|---------|-------|
| `NUXT_API_BASE_URL` | `http://127.0.0.1:8506` | No `/api/v1` suffix |
| `NUXT_API_KEY` | drop-in | Lives in `/etc/systemd/system/mindwealth-ui.service.d/secrets.conf` (root `0600`), **not** the unit template — so reinstalling the template cannot drop it. Verify: `systemctl show mindwealth-ui -p Environment` |
| `NUXT_PUBLIC_ADMIN_MODE` | `false` | `true` enables admin UI |
| `PORT` | `8512` | Must match nginx `proxy_pass` |

Rebuild **not** required for env-only changes.

### 5. Hostinger DNS via API (optional)

Hostinger web login may trigger email 2FA. Prefer API token from hPanel → Profile → API.

```bash
# GET current records
curl -s -H "Authorization: Bearer $HOSTINGER_API_TOKEN" \
  "https://developers.hostinger.com/api/dns/v1/zones/mindwealth.co"

# UPDATE @ A record (merge mode — does not delete other records)
curl -s -X PUT -H "Authorization: Bearer $HOSTINGER_API_TOKEN" \
  -H "Content-Type: application/json" \
  "https://developers.hostinger.com/api/dns/v1/zones/mindwealth.co" \
  -d '{"zone":[{"name":"@","type":"A","ttl":14400,"records":[{"content":"51.20.53.218"}]}],"overwrite":false}'
```

Never store API tokens or passwords in repo files or skills.

### 6. SSL renewal

Certbot auto-renews via systemd timer. Manual check:

```bash
sudo certbot renew --dry-run
```

---

## Decision guide

| User request | Action |
|--------------|--------|
| "Site down" | Check `mindwealth-ui`, `mindwealth-api`, nginx; see [reference.md](reference.md) |
| "Deploy new frontend version" | Redeploy workflow — build in `MindwealthUI_Vue_prod`, never the dev tree |
| "Deploy to dev / staging" | `scripts/fetch-and-reload-dev.sh` — dev tree, `:8514`, does not touch prod |
| "Point domain to server" | Hostinger DNS A → `51.20.53.218`, then certbot |
| "Add HTTPS" | DNS must point to EC2 first, then certbot |
| "Change API backend URL" | Edit systemd env, daemon-reload, restart |
| "Upload to Hostinger file manager" | **Wrong approach** — explain SSR requirement |
| "Change port" | Update systemd `PORT`, nginx `proxy_pass`, rebuild not required |

---

## Co-located services (same EC2)

| Service | Port | systemd unit |
|---------|------|--------------|
| MindWealth API | 8506 | `mindwealth-api` |
| MindWealth UI (this app, prod) | 8512 | `mindwealth-ui` |
| MindWealth UI (dev) | 8514 | `mindwealth-ui-dev` |
| Streamlit | 8504 / 8509 | `mindwealth-streamlit` |
| Dash | 8080 | `mindwealth-app` |
| PeaceToggle | 8508 | nginx `peacetoggle.app` |

Avoid port conflicts. Production domain traffic should hit nginx 80/443 only.

---

## Security rules

- Never commit or paste Hostinger passwords, API tokens, or `NUXT_API_KEY` into chat, skills, or git.
- Ask user to rotate password if exposed in chat.
- Hostinger login automation often blocked by 2FA — ask user for code or manual DNS change.
- EC2 security group: ensure inbound 80 and 443 open for public domain access.

---

## Additional resources

- Detailed troubleshooting: [reference.md](reference.md)
- EC2/systemd setup (no domain): `started.md` in repo root
