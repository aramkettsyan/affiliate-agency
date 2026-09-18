#!/usr/bin/env python3
"""
Auto-poster: publishes one link post per run to the site's Facebook Page.

Picks the newest not-yet-posted guide (falling back to product reviews), builds a
short post from data we already have (no LLM, no cost), and publishes it to the
Page feed via the Graph API. Every post is recorded in social_log.json so the
same page is never posted twice.

Posts link to OUR pages, never to a raw HopLink — Facebook flags/blocks bare
affiliate redirectors, and the on-site page carries the FTC disclosure.

Setup (one time):
  1. Create a Facebook Page for the site.
  2. Create an app at developers.facebook.com -> add "Facebook Login" product.
  3. Graph API Explorer -> select the app + Page -> grant pages_manage_posts and
     pages_read_engagement -> generate a User token -> exchange it for a
     long-lived token -> then GET /me/accounts to read the PAGE token.
  4. Put FB_PAGE_ID and FB_PAGE_ACCESS_TOKEN in .env (git-ignored).
     Verify with: python post_to_facebook.py --check

Run:  python post_to_facebook.py            # posts for real
      python post_to_facebook.py --dry-run  # prints the post, sends nothing
"""

import json
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent
LOG = ROOT / "social_log.json"
GRAPH = "https://graph.facebook.com/v21.0"
CTX = ssl.create_default_context()  # normal TLS verification


def load(name, default):
    p = ROOT / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def read_env():
    """Minimal .env reader — the project has no python-dotenv dependency."""
    env = {}
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def graph(path, params=None, data=None):
    """GET (data=None) or POST against the Graph API. Returns parsed JSON."""
    url = f"{GRAPH}/{path.lstrip('/')}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    body = urllib.parse.urlencode(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        try:
            msg = json.loads(detail)["error"]["message"]
        except Exception:
            msg = detail[:300]
        raise SystemExit(f"Facebook API error {e.code}: {msg}")


def hashtags(keywords, limit=3):
    """Turn keywords into hashtags, skipping ones too long to read well."""
    tags = []
    for kw in keywords:
        words = ["".join(c for c in w if c.isalnum()) for w in str(kw).split()]
        tag = "#" + "".join(w.capitalize() for w in words if w)
        if 4 < len(tag) <= 30 and tag not in tags:
            tags.append(tag)
        if len(tags) == limit:
            break
    return " ".join(tags)


def pick_item(posted_ids):
    """Newest unposted guide first, else the newest unposted product review."""
    guides = load("guides.json", [])
    for g in sorted(guides, key=lambda x: x.get("date", ""), reverse=True):
        if g["id"] not in posted_ids:
            return {"id": g["id"], "title": g["title"],
                    "summary": g.get("summary", ""), "keywords": g.get("keywords", []),
                    "kind": "guide"}
    products = load("products.json", [])
    for p in reversed(products):
        if p["id"] not in posted_ids:
            title = f'{p["name"]} Review: Is It Worth It?'
            return {"id": p["id"], "title": title,
                    "summary": p.get("summary", "") or p.get("best_for", ""),
                    "keywords": p.get("keywords", []), "kind": "product"}
    return None


def build_post(item, config):
    base = config["base_url"].rstrip("/")
    link = f'{base}/{item["id"]}.html'
    summary = item["summary"].strip()
    if len(summary) > 280:
        summary = summary[:277].rsplit(" ", 1)[0] + "..."
    tags = hashtags(item.get("keywords", []))
    parts = [item["title"], "", summary, "", f"Read it here: {link}"]
    if item["kind"] == "product":
        parts += ["", "(Contains affiliate links — full disclosure on the page.)"]
    if tags:
        parts += ["", tags]
    return "\n".join(parts), link


def main():
    dry = "--dry-run" in sys.argv
    env = read_env()
    page_id = env.get("FB_PAGE_ID", "")
    token = env.get("FB_PAGE_ACCESS_TOKEN", "")

    if "--check" in sys.argv:
        if not (page_id and token):
            raise SystemExit("FB_PAGE_ID / FB_PAGE_ACCESS_TOKEN missing from .env")
        me = graph(page_id, {"fields": "name,fan_count", "access_token": token})
        print(f'OK — token posts as: {me.get("name")} ({me.get("fan_count", 0)} followers)')
        return

    config = load("config.json", {})
    log = load("social_log.json", [])
    posted_ids = {e["id"] for e in log if e.get("status") == "posted"}

    item = pick_item(posted_ids)
    if not item:
        print("Nothing new to post — every guide and review has been posted.")
        return

    message, link = build_post(item, config)
    print(f'--- {item["kind"]}: {item["id"]} ---\n{message}\n---')

    if dry:
        print("DRY RUN — nothing sent.")
        return
    if not (page_id and token):
        raise SystemExit("FB_PAGE_ID / FB_PAGE_ACCESS_TOKEN missing from .env — see the "
                         "setup notes at the top of this file.")

    res = graph(f"{page_id}/feed",
                data={"message": message, "link": link, "access_token": token})
    log.append({"id": item["id"], "kind": item["kind"], "post_id": res.get("id"),
                "url": link, "status": "posted",
                "at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    LOG.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f'Posted {item["id"]} -> {res.get("id")}')


if __name__ == "__main__":
    main()
