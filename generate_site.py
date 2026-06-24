#!/usr/bin/env python3
"""
Affiliate Agency - static site generator.

Reads products.json + config.json and builds a free, fully static SEO content
site into ./public/. Every page auto-includes an FTC affiliate disclosure.

Content generation:
  - Default (free, no API key): high-quality TEMPLATE articles from product data.
  - Optional (use_llm=true + ANTHROPIC_API_KEY): richer AI-written articles.

Run:  python generate_site.py
Output: ./public/index.html + ./public/<slug>.html
"""

import json
import os
import re
import html
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent
PUBLIC = ROOT / "public"


def slugify(text):
    text = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return text or "article"


def load_json(name):
    with open(ROOT / name, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Content generation
# ---------------------------------------------------------------------------

def ai_article(product, config):
    """Optional richer article via the Claude API. Returns HTML body or None."""
    try:
        import anthropic
    except ImportError:
        print("  ! anthropic package not installed; falling back to template.")
        return None
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("  ! ANTHROPIC_API_KEY not set; falling back to template.")
        return None
    client = anthropic.Anthropic()
    prompt = (
        f"Write a helpful, honest 600-word product review article in clean HTML "
        f"(use <h2>, <p>, <ul>, <li> only — no <html>/<head>/<body>). "
        f"Product: {product['name']}. Category: {product['category']}. "
        f"Best for: {product.get('best_for','')}. "
        f"Pros: {product.get('pros')}. Cons: {product.get('cons')}. "
        f"Summary: {product.get('summary','')}. "
        f"Be balanced and genuinely useful; do not invent fake facts or guarantees. "
        f"Do NOT include the affiliate link — it is added separately."
    )
    msg = client.messages.create(
        model=config.get("llm_model", "claude-opus-4-8"),
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


def custom_article(product):
    """Use a hand-written article from content/<id>.html if it exists."""
    path = ROOT / "content" / f"{product['id']}.html"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


def template_article(product):
    """Free, no-API article body built from structured product data."""
    e = html.escape
    pros = "".join(f"<li>{e(p)}</li>" for p in product.get("pros", []))
    cons = "".join(f"<li>{e(c)}</li>" for c in product.get("cons", []))
    name = e(product["name"])
    return f"""
<h2>What is {name}?</h2>
<p>{e(product.get('summary',''))}</p>
<p>It's especially a good fit for {e(product.get('best_for','people looking for a reliable option'))}.</p>

<h2>The good</h2>
<ul>{pros}</ul>

<h2>Things to keep in mind</h2>
<ul>{cons}</ul>

<h2>Our verdict</h2>
<p>With a rating of {e(str(product.get('rating','N/A')))}/5 and a price of {e(product.get('price','see site'))},
{name} is a solid choice in the {e(product.get('category',''))} space.
If it matches what you need, you can check current availability and pricing below.</p>
"""


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{description}">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="{og_type}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{canonical}">
<meta property="og:site_name" content="{site_name}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{description}">
<meta name="robots" content="index, follow">
{schema}
<style>
  body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;max-width:760px;margin:0 auto;padding:24px;line-height:1.65;color:#1a1a1a}}
  a{{color:#0a66c2}}
  .disclosure{{background:#fff8e1;border:1px solid #ffe082;padding:12px 16px;border-radius:8px;font-size:.9em;margin:16px 0}}
  .cta{{display:inline-block;background:#0a66c2;color:#fff;text-decoration:none;padding:12px 22px;border-radius:8px;font-weight:600;margin:18px 0}}
  header a{{text-decoration:none;color:#1a1a1a;font-weight:700}}
  footer{{margin-top:48px;font-size:.85em;color:#666;border-top:1px solid #eee;padding-top:16px}}
  .card{{border:1px solid #eee;border-radius:10px;padding:16px;margin:14px 0}}
</style>
</head>
<body>
<header><a href="index.html">{site_name}</a> &mdash; <span style="color:#666">{tagline}</span></header>
<div class="disclosure">{disclosure}</div>
{body}
<footer>
  <p>{disclosure}</p>
  <p>&copy; {year} {site_name}. Information is provided for general guidance and may change — verify details on the product page before purchasing.</p>
</footer>
</body>
</html>
"""


def render_article(product, config):
    body_inner = custom_article(product)
    if not body_inner and config.get("use_llm"):
        body_inner = ai_article(product, config)
    if not body_inner:
        body_inner = template_article(product)

    title = f"{product['name']} Review ({date.today().year}) | {config['site_name']}"
    cta = (
        f'<p><a class="cta" href="{html.escape(product["affiliate_url"])}" '
        f'rel="nofollow sponsored" target="_blank">Check {html.escape(product["name"])} →</a></p>'
    )
    body = f"<h1>{html.escape(product['name'])} Review</h1>{cta}{body_inner}{cta}"
    slug = slugify(product["name"])
    canonical = f"{config['base_url']}/{slug}.html"

    # JSON-LD structured data -> eligible for Google rich results
    schema_obj = {
        "@context": "https://schema.org",
        "@type": "Review",
        "itemReviewed": {
            "@type": "Product",
            "name": product["name"],
            "category": product.get("category", ""),
            "description": product.get("summary", ""),
        },
        "author": {"@type": "Organization", "name": config["site_name"]},
        "publisher": {"@type": "Organization", "name": config["site_name"]},
        "url": canonical,
    }
    schema = f'<script type="application/ld+json">{json.dumps(schema_obj)}</script>'

    return slug, PAGE.format(
        title=html.escape(title),
        description=html.escape(product.get("summary", "")[:155]),
        canonical=canonical,
        og_type="article",
        schema=schema,
        site_name=html.escape(config["site_name"]),
        tagline=html.escape(config["site_tagline"]),
        disclosure=html.escape(config["affiliate_disclosure"]),
        body=body,
        year=date.today().year,
    )


def render_index(products, config):
    cards = ""
    for p in products:
        slug = slugify(p["name"])
        cards += (
            f'<div class="card"><h2><a href="{slug}.html">{html.escape(p["name"])}</a></h2>'
            f'<p>{html.escape(p.get("summary",""))}</p>'
            f'<p><small>{html.escape(p.get("category",""))} &middot; {html.escape(str(p.get("rating","")))}/5 &middot; {html.escape(p.get("price",""))}</small></p></div>'
        )
    body = f"<h1>{html.escape(config['site_name'])}</h1><p>{html.escape(config['site_tagline'])}</p>{cards}"
    schema_obj = {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": config["site_name"],
        "url": config["base_url"],
        "description": config["site_tagline"],
    }
    schema = f'<script type="application/ld+json">{json.dumps(schema_obj)}</script>'
    return PAGE.format(
        title=html.escape(f"{config['site_name']} | {config['site_tagline']}"),
        description=html.escape(config["site_tagline"]),
        canonical=config["base_url"],
        og_type="website",
        schema=schema,
        site_name=html.escape(config["site_name"]),
        tagline=html.escape(config["site_tagline"]),
        disclosure=html.escape(config["affiliate_disclosure"]),
        body=body,
        year=date.today().year,
    )


def main():
    config = load_json("config.json")
    products = load_json("products.json")
    PUBLIC.mkdir(exist_ok=True)

    valid = [p for p in products if "REPLACE-WITH-YOUR" not in p.get("affiliate_url", "")]
    if not valid:
        print("WARNING: no products with real affiliate links yet — building demo anyway.")
        valid = products

    limit = config.get("articles_per_run", len(valid))
    published = valid[:limit] if limit else valid
    slugs = []
    for p in published:
        slug, page = render_article(p, config)
        (PUBLIC / f"{slug}.html").write_text(page, encoding="utf-8")
        slugs.append(slug)
        print(f"  + {slug}.html")

    (PUBLIC / "index.html").write_text(render_index(published, config), encoding="utf-8")
    print(f"  + index.html  ({len(published)} products)")

    # --- SEO files ---
    base = config["base_url"].rstrip("/")
    today = date.today().isoformat()
    urls = [f"{base}/"] + [f"{base}/{s}.html" for s in slugs]
    sitemap = ['<?xml version="1.0" encoding="UTF-8"?>',
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        sitemap.append(f"  <url><loc>{u}</loc><lastmod>{today}</lastmod>"
                       f"<changefreq>weekly</changefreq></url>")
    sitemap.append("</urlset>")
    (PUBLIC / "sitemap.xml").write_text("\n".join(sitemap), encoding="utf-8")
    print("  + sitemap.xml")

    (PUBLIC / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {base}/sitemap.xml\n", encoding="utf-8")
    print("  + robots.txt")

    (PUBLIC / ".nojekyll").write_text("", encoding="utf-8")  # let GitHub Pages serve as-is
    print(f"Done. Open {PUBLIC / 'index.html'} in a browser.")


if __name__ == "__main__":
    main()
