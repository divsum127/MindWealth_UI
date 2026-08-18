# MindWealth Hosting — Troubleshooting Reference

## Symptom → diagnosis → fix

### Domain shows old WordPress site

**Cause:** DNS still points to Hostinger shared hosting (`191.101.79.86`).

**Check:**
```bash
dig +short www.mindwealth.co A
```

**Fix:** Update Hostinger DNS A record to `51.20.53.218`. Wait for propagation.

---

### Domain returns nginx default / wrong site

**Cause:** `server_name` mismatch or site not enabled.

**Check:**
```bash
ls -la /etc/nginx/sites-enabled/mindwealth.co
sudo nginx -T | grep -A2 "server_name mindwealth"
curl -sI -H "Host: www.mindwealth.co" http://127.0.0.1/
```

**Fix:** Reinstall site from `scripts/mindwealth.co.nginx`, `nginx -t`, reload.

---

### 502 Bad Gateway on domain

**Cause:** Nuxt process not running or wrong port.

**Check:**
```bash
systemctl status mindwealth-ui
ss -tlnp | grep 8512
sudo journalctl -u mindwealth-ui -n 50 --no-pager
```

**Fix:**
```bash
cd /home/ubuntu/MindwealthUI_Vue_prod && npm run build   # if .output missing
sudo systemctl restart mindwealth-ui
```

Build in `MindwealthUI_Vue_prod`, **not** the dev checkout `MindwealthUI_Vue`. The two units ran from
one directory until 2026-08-18; building in the dev tree used to overwrite the bundle prod loads.

---

### UI loads but no data / empty charts

**Cause:** Backend API down or auth failure.

**Check:**
```bash
systemctl status mindwealth-api
curl -s http://127.0.0.1:8506/api/v1/health | jq
curl -s http://127.0.0.1:8512/api/meta | jq
```

**Fix:** Restart API; set `NUXT_API_KEY` in systemd if backend returns 401.

---

### certbot fails (connection / validation error)

**Cause:** DNS not pointing to EC2 yet, or port 80 blocked.

**Check:**
```bash
dig +short mindwealth.co A
curl -sI http://mindwealth.co/.well-known/acme-challenge/test  # after DNS live
```

**Fix:** Confirm DNS → `51.20.53.218`, security group allows 80/443, `/var/www/mindwealth` exists.

---

### Service fails immediately after deploy

**Common errors:**

| Log message | Fix |
|-------------|-----|
| `ENOENT` `.output/server/index.mjs` | Run `npm run build` **in `/home/ubuntu/MindwealthUI_Vue_prod`** (the path in the unit's `ExecStart`) |
| `EADDRINUSE` 8512 | `ss -tlnp \| grep 8512` — stop the conflicting process **by PID**. Never `pkill -f ".output/server/index.mjs"`: it matches both Nuxt units and `Restart=on-failure` will not restart them after a clean SIGTERM (14m50s outage, 2026-08-17) |
| Node version error | `nvm use 20` before build; service uses v20.20.2 path |

---

### Hostinger login blocked

**Cause:** "Suspicious Login Detected" email 2FA.

**Options:**
1. User provides 6-digit code from email (one-time).
2. User changes DNS manually in hPanel.
3. User creates API token at `https://hpanel.hostinger.com/profile/api` and provides token (not password).

---

## Log locations

```bash
# Nuxt app
sudo journalctl -u mindwealth-ui -f

# nginx domain traffic
sudo tail -f /var/log/nginx/mindwealth-access.log
sudo tail -f /var/log/nginx/mindwealth-error.log

# API
sudo journalctl -u mindwealth-api -f
```

---

## Manual test without systemd

Use a **scratch port** and bind to loopback — never `PORT=8512`, which collides with the live service.

```bash
cd /home/ubuntu/MindwealthUI_Vue_prod
HOST=127.0.0.1 PORT=8599 NUXT_API_BASE_URL=http://127.0.0.1:8506 \
  /home/ubuntu/.nvm/versions/node/v20.20.2/bin/node .output/server/index.mjs &
SMOKE_PID=$!
curl -s -o /dev/null -w "root %{http_code}\n" http://127.0.0.1:8599/
curl -s -o /dev/null -w "meta %{http_code}\n" http://127.0.0.1:8599/api/meta   # 401 = auth gate up
kill "$SMOKE_PID"
```

Stop it **by PID** (or Ctrl+C in the foreground). Never `pkill -f` the Nitro entrypoint — it matches
the live systemd units too.

---

## nginx SSL server block (after certbot)

Certbot modifies the live nginx file to add a `listen 443 ssl` block. If you overwrite from repo template, re-run:

```bash
sudo certbot --nginx -d mindwealth.co -d www.mindwealth.co
```

Or manually add SSL directives referencing:
- `/etc/letsencrypt/live/mindwealth.co/fullchain.pem`
- `/etc/letsencrypt/live/mindwealth.co/privkey.pem`

---

## DNS record reference (target state)

| Name | Type | Value |
|------|------|-------|
| `@` | A | `51.20.53.218` |
| `www` | CNAME | `mindwealth.co` |

Previous WordPress hosting IP: `191.101.79.86` (Hostinger LiteSpeed).

---

## Full health check script

```bash
echo "=== DNS ==="
dig +short mindwealth.co A www.mindwealth.co A

echo "=== Services ==="
systemctl is-active mindwealth-ui mindwealth-api nginx

echo "=== HTTP ==="
curl -s -o /dev/null -w "UI: %{http_code}\n" http://127.0.0.1:8512/
curl -s -o /dev/null -w "Proxy: %{http_code}\n" -H "Host: www.mindwealth.co" http://127.0.0.1/
curl -s -o /dev/null -w "HTTPS: %{http_code}\n" https://www.mindwealth.co/ 2>/dev/null || echo "HTTPS: not ready"

echo "=== API ==="
curl -s http://127.0.0.1:8506/api/v1/health | jq -r '.status // .'
```
