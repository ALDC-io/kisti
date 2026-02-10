# KiSTI — Deployment

## Architecture

```
GitHub (ALDC-io/kisti) → Vercel (auto-deploy on push) → kisti.analyticlabs.io
                                                           ↑
                                              Cloudflare CNAME → cname.vercel-dns.com
```

## Vercel Setup

1. Connect repo `ALDC-io/kisti` to Vercel
2. Framework: Next.js (auto-detected)
3. Build command: `npm run build`
4. Output directory: `.next`
5. Add custom domain: `kisti.analyticlabs.io`

## DNS (Cloudflare)

- **Zone**: `analyticlabs.io` (`549f9a25ac1912f7aecf6fecb22e8fa3`)
- **Record**: CNAME `kisti` → `cname.vercel-dns.com` (proxied)
- **SSL**: Full (strict) — Vercel handles cert via Let's Encrypt

## Verification

```bash
# Check DNS
dig kisti.analyticlabs.io CNAME

# Check HTTPS
curl -sI https://kisti.analyticlabs.io | head -5

# Should return 200 OK
```

## Auto-Deploy

Every push to `main` triggers a Vercel deployment (~9 seconds).
No manual deploy steps needed.
