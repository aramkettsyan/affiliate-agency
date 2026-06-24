# Affiliate Agency — automated affiliate content site

A $0-cost, fully automated affiliate marketing system. It generates an SEO
content site from a product catalog, auto-inserts an FTC affiliate disclosure
on every page, and publishes itself daily for free via GitHub Pages + Actions.

## How the money actually works (read this first)

1. You join an affiliate program (we start with **ClickBank** — instant approval,
   no website required, trusted, pays via direct deposit/PayPal).
2. You get a unique **affiliate link (HopLink)** for each product.
3. This tool builds web pages that review those products and include your link.
4. People find the pages on Google, click your link, and buy.
5. The program pays you a commission.

There is **no** part where a bot spams other people's forum questions — that
gets your accounts banned and earns nothing. Owned content + search traffic is
the model that actually pays.

---

## Step 1 — Get approved (today, free)

1. Sign up at **clickbank.com** (free, near-instant approval).
2. Open the **Marketplace**, pick 2–5 products with:
   - **Gravity** between ~20 and 150 (proven to sell, not oversaturated)
   - Good commission (often 30–75%)
   - A category you can write about (productivity, fitness, hobbies, etc.)
3. Click **Promote** on each → copy your **HopLink**.

(Optional, add later: Amazon Associates — needs this site live first + 3 sales
in 180 days.)

## Step 2 — Add your products

Edit `products.json`. Replace each `affiliate_url` with your real HopLink and
fill in honest pros/cons/summary. Add as many products as you like.

## Step 3 — Build the site locally

```bash
python generate_site.py
```

Open `public/index.html` in a browser to preview.

## Step 4 — Publish it for free (automated forever)

1. Create a **free GitHub account** and a new repo named `affiliate-agency`.
2. Push this folder to it:
   ```bash
   git init && git add . && git commit -m "launch affiliate site"
   git branch -M main
   git remote add origin https://github.com/YOUR-USERNAME/affiliate-agency.git
   git push -u origin main
   ```
3. In the repo: **Settings → Pages → Build and deployment → Source: GitHub Actions**.
4. Edit `config.json` → set `base_url` to
   `https://YOUR-USERNAME.github.io/affiliate-agency`.
5. Done. The site rebuilds and republishes **every day at 09:00 UTC** automatically
   (`.github/workflows/publish.yml`). No server, no cost.

## Step 5 — Get traffic (free)

- Add more product pages (more pages = more search entry points).
- Submit your site to **Google Search Console** so Google indexes it.
- Share pages on free channels you own (Pinterest allows affiliate links and
  sends free traffic; your own social accounts are fine too).

---

## Optional: richer AI-written articles

Free mode uses high-quality templates (no API key, $0). To use Claude for
fuller articles:

1. Set `"use_llm": true` in `config.json`.
2. `pip install anthropic`
3. Set an `ANTHROPIC_API_KEY` env var locally, and add it as a GitHub
   **repository secret** named `ANTHROPIC_API_KEY` for the automated builds.

## Compliance (don't skip)

- The FTC disclosure is auto-added to every page — **keep it**. It's legally
  required and protects your ClickBank account.
- Only write honest reviews. Don't invent fake guarantees or results.
- Affiliate links use `rel="nofollow sponsored"` as Google requires.

## Files

| File | Purpose |
|---|---|
| `config.json` | Site name, base URL, disclosure text, settings |
| `products.json` | Your product catalog + affiliate links |
| `generate_site.py` | Builds the static site into `public/` |
| `.github/workflows/publish.yml` | Free daily auto-build + deploy |
