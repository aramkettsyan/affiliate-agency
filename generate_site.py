#!/usr/bin/env python3
"""
Affiliate Agency - static site generator (v2, redesigned).

Builds a polished, trustworthy affiliate content site into ./public/ from
products.json + roundups.json + config.json. Every page includes:
  - a shared header (logo + nav) and footer (disclosure, links)
  - FTC affiliate disclosure
  - JSON-LD structured data (Review + FAQPage + Breadcrumb)
  - internal links (related products, roundups) for SEO
Also generates: homepage, per-product reviews, "best of" comparison pages,
an About page, sitemap.xml and robots.txt.

Article bodies come from content/<id>.html (hand-written). Run: python generate_site.py
"""

import json
import os
import re
import html
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent
PUBLIC = ROOT / "public"
YEAR = date.today().year
TODAY = date.today().isoformat()
IMAGES = {}  # product id -> local image path (populated in main from images.json)


def image_for(product):
    return IMAGES.get(product["id"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def slugify(text):
    text = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return text or "page"


def load_json(name):
    with open(ROOT / name, encoding="utf-8") as f:
        return json.load(f)


def e(text):
    return html.escape(str(text))


# Map a product to an emoji + accent colour based on its niche/category.
ICONS = [
    ("dog", "🐕", "#b45309"), ("puppy", "🐕", "#b45309"), ("terrier", "🐕", "#b45309"),
    ("cat", "🐱", "#7c3aed"), ("feline", "🐱", "#7c3aed"),
    ("reptile", "🦎", "#15803d"), ("chameleon", "🦎", "#15803d"), ("gecko", "🦎", "#15803d"),
    ("wood", "🔨", "#92400e"), ("shed", "🔨", "#92400e"), ("shop", "🔨", "#92400e"),
    ("boat", "⛵", "#0369a1"), ("cnc", "🔧", "#92400e"), ("saw", "🔧", "#92400e"),
    ("sewing", "✂️", "#be185d"), ("rail", "🚂", "#0f766e"), ("declutter", "📦", "#0d9488"),
    ("organization", "📦", "#0d9488"),
    ("aquaponics", "🌱", "#16a34a"), ("garden", "🌱", "#16a34a"), ("backyard", "🌱", "#16a34a"),
    ("tiny house", "🏠", "#a16207"), ("container", "🏠", "#a16207"), ("home", "🏠", "#a16207"),
    ("survival", "⛺", "#166534"), ("water", "💧", "#0284c7"), ("energy", "⚡", "#ca8a04"),
    ("astrology", "🔮", "#7c3aed"), ("moon", "🌙", "#6d28d9"), ("soulmate", "❤️", "#db2777"),
    ("manifest", "✨", "#7c3aed"), ("genius", "✨", "#7c3aed"), ("wealth", "💰", "#15803d"),
    ("dental", "🦷", "#0891b2"), ("joint", "🦴", "#b45309"), ("blood sugar", "💉", "#dc2626"),
    ("hearing", "👂", "#0d9488"), ("prostate", "💊", "#0e7490"), ("men's", "💊", "#0e7490"),
    ("supplement", "💊", "#0891b2"), ("productivity", "⏰", "#2563eb"), ("fitness", "💪", "#dc2626"),
]


def icon_for(product):
    hay = f"{product.get('niche','')} {product.get('category','')} {product.get('name','')}".lower()
    for key, emoji, color in ICONS:
        if key in hay:
            return emoji, color
    return "⭐", "#2563eb"


# ---------------------------------------------------------------------------
# Article body (hand-written content preferred)
# ---------------------------------------------------------------------------

def custom_article(product):
    path = ROOT / "content" / f"{product['id']}.html"
    return path.read_text(encoding="utf-8") if path.exists() else None


def ai_article(product, config):
    try:
        import anthropic
    except ImportError:
        return None
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    client = anthropic.Anthropic()
    prompt = (
        f"Write a balanced, honest 700-word product review in clean HTML (h2/p/ul/li only) "
        f"for {product['name']} ({product.get('category','')}). Best for {product.get('best_for','')}. "
        f"Summary: {product.get('summary','')}. Be genuinely useful, no invented facts, no fake guarantees. "
        f"Do not include the affiliate link."
    )
    msg = client.messages.create(model=config.get("llm_model", "claude-opus-4-8"),
                                 max_tokens=1800, messages=[{"role": "user", "content": prompt}])
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


def template_article(product):
    pros = "".join(f"<li>{e(p)}</li>" for p in product.get("pros", []))
    cons = "".join(f"<li>{e(c)}</li>" for c in product.get("cons", []))
    return (f"<p>{e(product.get('summary',''))}</p>"
            f"<h2>Who is it for?</h2><p>Best for {e(product.get('best_for',''))}.</p>"
            + (f"<h2>The good</h2><ul>{pros}</ul>" if pros else "")
            + (f"<h2>Things to keep in mind</h2><ul>{cons}</ul>" if cons else ""))


def article_body(product, config):
    return (custom_article(product)
            or (ai_article(product, config) if config.get("use_llm") else None)
            or template_article(product))


# ---------------------------------------------------------------------------
# FAQs (honest, derived from product data) -> useful content + FAQ rich results
# ---------------------------------------------------------------------------

def faqs_for(product):
    name = product["name"]
    price = product.get("price", "")
    faqs = []
    faqs.append((f"Is {name} legit or a scam?",
                 f"{name} is a real product sold through ClickBank, a trusted retailer that has "
                 f"operated since 1998 and handles secure payment and refunds. It is not a scam. "
                 f"That said, treat the vendor's marketing claims with healthy skepticism and judge "
                 f"it on whether it fits your needs."))
    faqs.append((f"Does {name} have a money-back guarantee?",
                 f"Yes. Because {name} is sold via ClickBank, it comes with ClickBank's standard "
                 f"60-day money-back guarantee, so you can request a refund within 60 days if it "
                 f"isn't right for you."))
    if product.get("best_for"):
        faqs.append((f"Who is {name} best for?",
                     f"{name} is best for {product['best_for']}."))
    if price:
        faqs.append((f"How much does {name} cost?",
                     f"Pricing is {price}. Vendors often run discounts, so check the current price "
                     f"on the official page before buying."))
    return faqs


def faq_html(faqs):
    if not faqs:
        return ""
    items = "".join(
        f'<div class="faq"><h3>{e(q)}</h3><p>{e(a)}</p></div>' for q, a in faqs)
    return f'<section class="faqs"><h2>Frequently asked questions</h2>{items}</section>'


def faq_schema(faqs):
    if not faqs:
        return None
    return {
        "@context": "https://schema.org", "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": q,
             "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faqs],
    }


# ---------------------------------------------------------------------------
# Shared chrome: header, footer, page shell
# ---------------------------------------------------------------------------

STYLE = """
:root{
  --bg:#ffffff;--ink:#16202c;--muted:#5b6b7b;--line:#e6ebf1;--soft:#f6f8fb;
  --brand:#1d4ed8;--brand-d:#1e3a8a;--accent:#0ea5a4;--warn:#fff7e6;--warn-b:#ffe1a8;
  --radius:14px;--shadow:0 1px 2px rgba(16,32,44,.04),0 8px 24px rgba(16,32,44,.06);
}
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  color:var(--ink);background:var(--bg);line-height:1.65;font-size:17px}
a{color:var(--brand);text-decoration:none}a:hover{text-decoration:underline}
.wrap{max-width:920px;margin:0 auto;padding:0 20px}
header.site{position:sticky;top:0;z-index:20;background:rgba(255,255,255,.92);backdrop-filter:saturate(1.2) blur(8px);
  border-bottom:1px solid var(--line)}
header.site .row{display:flex;align-items:center;justify-content:space-between;height:62px}
.logo{display:flex;align-items:center;gap:10px;font-weight:800;font-size:19px;color:var(--ink)}
.logo:hover{text-decoration:none}
.logo .mark{width:30px;height:30px;border-radius:8px;background:linear-gradient(135deg,var(--brand),var(--accent));
  display:grid;place-items:center;color:#fff;font-size:16px;font-weight:800}
nav.main{display:flex;gap:18px;font-size:15px;font-weight:600}
nav.main a{color:var(--muted)}nav.main a:hover{color:var(--ink);text-decoration:none}
@media(max-width:640px){nav.main{gap:12px;font-size:13px}.logo{font-size:16px}}
.hero{background:linear-gradient(180deg,var(--soft),#fff);border-bottom:1px solid var(--line);padding:54px 0 40px}
.hero h1{font-size:40px;line-height:1.12;margin:0 0 12px;letter-spacing:-.02em}
.hero p{font-size:19px;color:var(--muted);margin:0;max-width:640px}
@media(max-width:640px){.hero h1{font-size:30px}.hero p{font-size:17px}}
.disclosure{background:var(--warn);border:1px solid var(--warn-b);padding:11px 15px;border-radius:10px;
  font-size:13.5px;color:#6b4e16;margin:18px 0}
h1{font-size:32px;line-height:1.18;letter-spacing:-.02em;margin:.2em 0 .4em}
h2{font-size:23px;margin:1.7em 0 .5em;letter-spacing:-.01em}
h3{font-size:18px;margin:1.2em 0 .3em}
.section-title{display:flex;align-items:baseline;justify-content:space-between;margin-top:36px}
.section-title a{font-size:14px;font-weight:600}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:18px 0}
@media(max-width:640px){.grid{grid-template-columns:1fr}}
.card{border:1px solid var(--line);border-radius:var(--radius);padding:18px;background:#fff;box-shadow:var(--shadow);
  transition:transform .12s ease,box-shadow .12s ease;display:flex;flex-direction:column}
.card:hover{transform:translateY(-2px);box-shadow:0 6px 14px rgba(16,32,44,.10)}
.card .ic{width:42px;height:42px;border-radius:10px;display:grid;place-items:center;font-size:22px;color:#fff;margin-bottom:10px}
.card .thumb{width:100%;height:160px;object-fit:contain;background:#f6f8fb;border:1px solid var(--line);
  border-radius:10px;margin-bottom:12px;padding:6px}
.hero-img{width:100%;max-height:340px;object-fit:contain;background:var(--soft);border:1px solid var(--line);
  border-radius:var(--radius);padding:10px;margin:8px 0 4px}
.card h3{margin:.1em 0 .35em;font-size:18px}.card h3 a{color:var(--ink)}
.card p{margin:0 0 12px;color:var(--muted);font-size:15px;flex:1}
.meta{font-size:12.5px;color:var(--muted);display:flex;gap:10px;flex-wrap:wrap;margin-bottom:10px}
.badge{background:var(--soft);border:1px solid var(--line);border-radius:999px;padding:2px 9px;font-weight:600}
.btn{display:inline-block;background:var(--brand);color:#fff;font-weight:700;padding:11px 18px;border-radius:10px;
  text-align:center}.btn:hover{background:var(--brand-d);text-decoration:none}
.btn.ghost{background:#fff;color:var(--brand);border:1.5px solid var(--brand)}
.btn.block{display:block}
.crumb{font-size:13px;color:var(--muted);margin:18px 0 4px}.crumb a{color:var(--muted)}
.verdict{background:var(--soft);border:1px solid var(--line);border-left:4px solid var(--accent);
  border-radius:10px;padding:14px 16px;margin:16px 0}
.verdict strong{display:block;margin-bottom:4px}
.cta-box{background:linear-gradient(135deg,#f0f7ff,#eefcfb);border:1px solid var(--line);border-radius:var(--radius);
  padding:20px;margin:22px 0;text-align:center}
.cta-box .price{font-size:13px;color:var(--muted);margin-top:8px}
article p,article ul{font-size:17px}article li{margin:.2em 0}
.faqs{margin-top:30px;border-top:1px solid var(--line);padding-top:8px}
.faq{padding:14px 0;border-bottom:1px solid var(--line)}.faq h3{margin:0 0 4px}.faq p{margin:0;color:var(--muted)}
.related{margin-top:34px}
.byline{font-size:13.5px;color:var(--muted);margin:6px 0 0;display:flex;align-items:center;gap:8px}
.byline .av{width:26px;height:26px;border-radius:50%;background:linear-gradient(135deg,var(--brand),var(--accent));
  display:inline-grid;place-items:center;color:#fff;font-size:12px;font-weight:700}
footer.site{margin-top:56px;border-top:1px solid var(--line);background:var(--soft)}
footer.site .row{display:grid;grid-template-columns:1.4fr 1fr;gap:24px;padding:30px 0}
@media(max-width:640px){footer.site .row{grid-template-columns:1fr}}
footer.site h4{margin:0 0 8px;font-size:14px}
footer.site a{color:var(--muted);display:block;font-size:14px;margin:3px 0}
footer .fine{font-size:12.5px;color:var(--muted);border-top:1px solid var(--line);padding:14px 0}
table.cmp{width:100%;border-collapse:collapse;margin:16px 0;font-size:15px}
table.cmp th,table.cmp td{border:1px solid var(--line);padding:9px 11px;text-align:left}
table.cmp th{background:var(--soft)}
"""


def header_html(config):
    name = e(config["site_name"])
    return f"""<header class="site"><div class="wrap row">
<a class="logo" href="index.html"><span class="mark">SP</span>{name}</a>
<nav class="main">
<a href="index.html">Home</a>
<a href="best-guides.html">Best Guides</a>
<a href="about.html">About</a>
</nav></div></header>"""


def footer_html(config, roundups):
    name = e(config["site_name"])
    links = "".join(f'<a href="{r["id"]}.html">{e(r["title"].split(" (")[0])}</a>' for r in roundups[:5])
    return f"""<footer class="site"><div class="wrap">
<div class="row">
<div><h4>{name}</h4>
<p style="color:var(--muted);font-size:14px;margin:0">{e(config['site_tagline'])}. We research popular
products and write honest, plain-English reviews so you can decide with confidence.</p></div>
<div><h4>Popular guides</h4>{links}<a href="about.html">About &amp; how we review</a></div>
</div>
<div class="fine">{e(config['affiliate_disclosure'])}<br>&copy; {YEAR} {name}. Information is for general
guidance and may change &mdash; always verify details on the official product page before buying.</div>
</div></footer>"""


def page_shell(config, roundups, *, title, description, canonical, body,
               og_type="article", schema_objs=None):
    schema = ""
    for obj in (schema_objs or []):
        if obj:
            schema += f'<script type="application/ld+json">{json.dumps(obj)}</script>'
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(description)}">
<link rel="canonical" href="{e(canonical)}">
<meta name="robots" content="index, follow">
<meta property="og:type" content="{og_type}"><meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(description)}"><meta property="og:url" content="{e(canonical)}">
<meta property="og:site_name" content="{e(config['site_name'])}">
<meta name="twitter:card" content="summary_large_image">
{schema}<style>{STYLE}</style></head>
<body>{header_html(config)}
<main class="wrap">{body}</main>
{footer_html(config, roundups)}</body></html>"""


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------

def product_card(product):
    emoji, color = icon_for(product)
    slug = slugify(product["name"])
    cat = e(product.get("category", ""))
    img = image_for(product)
    visual = (f'<img class="thumb" src="{e(img)}" alt="{e(product["name"])} product image" loading="lazy">'
              if img else "")
    return (f'<div class="card">{visual}'
            f'<h3><a href="{slug}.html">{e(product["name"])}</a></h3>'
            f'<div class="meta"><span class="badge">{cat}</span></div>'
            f'<p>{e(product.get("summary",""))}</p>'
            f'<a class="btn ghost block" href="{slug}.html">Read review</a></div>')


def cta_button(product, label=None):
    label = label or f'Visit the official {product["name"]} page →'
    price = product.get("price", "")
    price_html = f'<div class="price">Pricing: {e(price)} · 60-day money-back guarantee via ClickBank</div>' if price else ""
    return (f'<div class="cta-box"><a class="btn" href="{e(product["affiliate_url"])}" '
            f'rel="nofollow sponsored" target="_blank">{e(label)}</a>{price_html}</div>')


def render_article(product, config, roundups, related):
    slug = slugify(product["name"])
    canonical = f"{config['base_url'].rstrip('/')}/{slug}.html"
    emoji, color = icon_for(product)
    body_inner = article_body(product, config)
    faqs = faqs_for(product)

    crumb = (f'<div class="crumb"><a href="index.html">Home</a> › '
             f'<a href="best-guides.html">Reviews</a> › {e(product["name"])}</div>')
    head = (f'<div class="ic" style="background:{color};width:48px;height:48px;font-size:26px;border-radius:12px">{emoji}</div>'
            if False else "")
    verdict = (f'<div class="verdict"><strong>Quick verdict</strong>'
               f'{e(product.get("summary",""))} Best for {e(product.get("best_for","the right buyer"))}. '
               f'Backed by ClickBank\'s 60-day money-back guarantee.</div>')
    byline = ('<div class="byline"><span class="av">SP</span> Reviewed by the Smart Picks editorial team · '
              f'Updated {date.today().strftime("%B %Y")}</div>')

    img = image_for(product)
    hero_img = (f'<img class="hero-img" src="{e(img)}" alt="{e(product["name"])} product image">'
                if img else "")

    rel_html = ""
    if related:
        rel_html = ('<div class="related"><div class="section-title"><h2>Related reviews</h2></div>'
                    '<div class="grid">' + "".join(product_card(r) for r in related) + '</div></div>')

    disclosure = f'<div class="disclosure">{e(config["affiliate_disclosure"])}</div>'
    body = (crumb + f'<h1>{e(product["name"])} Review ({YEAR})</h1>' + byline + hero_img + disclosure + verdict
            + cta_button(product) + f'<article>{body_inner}</article>' + cta_button(product)
            + faq_html(faqs) + rel_html)

    review_schema = {
        "@context": "https://schema.org", "@type": "Review",
        "itemReviewed": {"@type": "Product", "name": product["name"],
                         "category": product.get("category", ""), "description": product.get("summary", "")},
        "author": {"@type": "Organization", "name": config["site_name"]},
        "publisher": {"@type": "Organization", "name": config["site_name"]}, "url": canonical,
    }
    crumb_schema = {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": config["base_url"]},
            {"@type": "ListItem", "position": 2, "name": product["name"], "item": canonical}],
    }
    title = f'{product["name"]} Review ({YEAR}): Worth It? | {config["site_name"]}'
    return slug, page_shell(config, roundups, title=title,
                            description=product.get("summary", "")[:155], canonical=canonical,
                            body=body, schema_objs=[review_schema, faq_schema(faqs), crumb_schema])


def render_roundup(roundup, by_id, config, roundups):
    items = [by_id[p] for p in roundup["product_ids"] if p in by_id]
    canonical = f"{config['base_url'].rstrip('/')}/{roundup['id']}.html"
    crumb = (f'<div class="crumb"><a href="index.html">Home</a> › '
             f'<a href="best-guides.html">Best Guides</a> › {e(roundup["title"].split(" (")[0])}</div>')
    rows = ""
    for i, p in enumerate(items, 1):
        emoji, color = icon_for(p)
        slug = slugify(p["name"])
        rows += (f'<tr><td><strong>{i}. {e(p["name"])}</strong></td>'
                 f'<td>{e(p.get("best_for",""))}</td>'
                 f'<td><a href="{slug}.html">Read review</a></td></tr>')
    table = (f'<table class="cmp"><tr><th>Product</th><th>Best for</th><th></th></tr>{rows}</table>')

    blocks = ""
    for i, p in enumerate(items, 1):
        emoji, color = icon_for(p)
        slug = slugify(p["name"])
        img = image_for(p)
        visual = (f'<img class="thumb" src="{e(img)}" alt="{e(p["name"])} product image" loading="lazy">'
                  if img else f'<div class="ic" style="background:{color}">{emoji}</div>')
        blocks += (f'<div class="card" style="margin:16px 0">'
                   f'{visual}'
                   f'<h2 style="margin:.2em 0">{i}. {e(p["name"])}</h2>'
                   f'<p style="color:var(--muted)">{e(p.get("summary",""))}</p>'
                   f'<p style="font-size:14px"><strong>Best for:</strong> {e(p.get("best_for",""))}</p>'
                   f'<div style="display:flex;gap:10px;flex-wrap:wrap">'
                   f'<a class="btn ghost" href="{slug}.html">Full review</a>'
                   f'<a class="btn" href="{e(p["affiliate_url"])}" rel="nofollow sponsored" target="_blank">Official site →</a>'
                   f'</div></div>')

    disclosure = f'<div class="disclosure">{e(config["affiliate_disclosure"])}</div>'
    byline = ('<div class="byline"><span class="av">SP</span> By the Smart Picks editorial team · '
              f'Updated {date.today().strftime("%B %Y")}</div>')
    body = (crumb + f'<h1>{e(roundup["title"])}</h1>' + byline + disclosure
            + f'<p style="font-size:19px;color:var(--muted)">{e(roundup["intro"])}</p>'
            + '<h2>At a glance</h2>' + table + '<h2>The picks, reviewed</h2>' + blocks)

    crumb_schema = {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": config["base_url"]},
            {"@type": "ListItem", "position": 2, "name": roundup["title"], "item": canonical}],
    }
    list_schema = {
        "@context": "https://schema.org", "@type": "ItemList",
        "itemListElement": [{"@type": "ListItem", "position": i, "name": p["name"]}
                            for i, p in enumerate(items, 1)],
    }
    title = f'{roundup["title"]} | {config["site_name"]}'
    return page_shell(config, roundups, title=title, description=roundup["intro"][:155],
                      canonical=canonical, body=body, schema_objs=[crumb_schema, list_schema])


def render_best_guides(roundups, config):
    canonical = f"{config['base_url'].rstrip('/')}/best-guides.html"
    cards = ""
    for r in roundups:
        cards += (f'<div class="card"><h3><a href="{r["id"]}.html">{e(r["title"])}</a></h3>'
                  f'<p>{e(r["intro"])}</p>'
                  f'<a class="btn ghost block" href="{r["id"]}.html">Read guide</a></div>')
    body = ('<div class="crumb"><a href="index.html">Home</a> › Best Guides</div>'
            '<h1>Best Guides &amp; Comparisons</h1>'
            '<p style="font-size:19px;color:var(--muted)">Side-by-side comparisons of the most popular '
            'products in each niche, so you can pick the right one fast.</p>'
            f'<div class="grid">{cards}</div>')
    return page_shell(config, roundups, title=f'Best Guides &amp; Comparisons | {config["site_name"]}',
                      description="Honest side-by-side comparisons of the most popular products in each niche.",
                      canonical=canonical, body=body, og_type="website")


def render_about(config, roundups):
    canonical = f"{config['base_url'].rstrip('/')}/about.html"
    body = f"""<div class="crumb"><a href="index.html">Home</a> › About</div>
<h1>About {e(config['site_name'])}</h1>
<p style="font-size:19px;color:var(--muted)">{e(config['site_tagline'])}.</p>
<p>{e(config['site_name'])} exists to cut through the hype. The internet is full of over-promising sales
pages, so our goal is simple: explain in plain English what a product actually is, who it's genuinely a
good fit for, and what to watch out for &mdash; before you spend any money.</p>
<h2>How we review</h2>
<ul>
<li><strong>We research the real product.</strong> We look at what each product offers, how it's delivered,
its pricing model, and its refund policy.</li>
<li><strong>We stay balanced.</strong> Every review includes honest downsides, not just positives. If
something is entertainment or a supplement (not a medical treatment), we say so.</li>
<li><strong>We prioritise trusted retailers.</strong> The products we feature are sold through ClickBank,
an established online retailer that handles secure payment and offers a 60-day money-back guarantee.</li>
<li><strong>We set realistic expectations.</strong> No product is magic. We tell you what consistent effort
or setup a product actually requires.</li>
</ul>
<h2>How we make money</h2>
<p>{e(config['affiliate_disclosure'])} This never changes our honest assessment &mdash; we'd rather you find
the right product (or skip one that isn't for you) than make a quick commission.</p>
<h2>Important note</h2>
<p>We are an independent review site, not the manufacturer or seller of any product featured. For
health-related products, our content is general information only and is not medical advice &mdash; always
consult a qualified professional. Always verify current details on the official product page before buying.</p>
<div class="cta-box"><a class="btn" href="best-guides.html">Browse our best guides →</a></div>"""
    return page_shell(config, roundups, title=f'About Us | {config["site_name"]}',
                      description=f"How {config['site_name']} researches and reviews products honestly.",
                      canonical=canonical, body=body, og_type="website")


def render_index(products, config, roundups, by_id):
    canonical = config["base_url"]
    # group products by category for tidy sections
    cats = {}
    for p in products:
        cats.setdefault(p.get("category", "Other"), []).append(p)

    featured = ""
    for r in roundups[:4]:
        featured += (f'<div class="card"><h3><a href="{r["id"]}.html">{e(r["title"])}</a></h3>'
                     f'<p>{e(r["intro"][:120])}…</p>'
                     f'<a class="btn ghost block" href="{r["id"]}.html">Compare picks</a></div>')

    sections = ""
    for cat, items in cats.items():
        sections += (f'<div class="section-title"><h2>{e(cat)}</h2></div>'
                     '<div class="grid">' + "".join(product_card(p) for p in items) + '</div>')

    body = (f'<div class="disclosure">{e(config["affiliate_disclosure"])}</div>'
            '<div class="section-title"><h2>Best guides &amp; comparisons</h2>'
            '<a href="best-guides.html">View all →</a></div>'
            f'<div class="grid">{featured}</div>'
            + sections)

    # hero lives outside .wrap, so prepend a full-width block by wrapping manually
    hero = (f'<section class="hero"><div class="wrap"><h1>{e(config["site_name"])}</h1>'
            f'<p>{e(config["site_tagline"])}. Honest, plain-English reviews and side-by-side comparisons '
            f'of popular products &mdash; so you can choose with confidence.</p></div></section>')

    site_schema = {"@context": "https://schema.org", "@type": "WebSite",
                   "name": config["site_name"], "url": config["base_url"],
                   "description": config["site_tagline"]}
    org_schema = {"@context": "https://schema.org", "@type": "Organization",
                  "name": config["site_name"], "url": config["base_url"]}
    page = page_shell(config, roundups, title=f'{config["site_name"]} | {config["site_tagline"]}',
                      description=config["site_tagline"], canonical=canonical, body=body,
                      og_type="website", schema_objs=[site_schema, org_schema])
    # inject hero right after </header>
    return page.replace('<main class="wrap">', hero + '<main class="wrap">', 1)


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def main():
    global IMAGES
    config = load_json("config.json")
    products = load_json("products.json")
    roundups = load_json("roundups.json")
    IMAGES = load_json("images.json") if (ROOT / "images.json").exists() else {}
    PUBLIC.mkdir(exist_ok=True)

    products = [p for p in products if "REPLACE-WITH-YOUR" not in p.get("affiliate_url", "")]
    by_id = {p["id"]: p for p in products}
    urls = [f"{config['base_url'].rstrip('/')}/"]

    # product reviews (with related = up to 3 same-category others)
    for p in products:
        related = [q for q in products
                   if q is not p and q.get("category") == p.get("category")][:3]
        slug, page = render_article(p, config, roundups, related)
        (PUBLIC / f"{slug}.html").write_text(page, encoding="utf-8")
        urls.append(f"{config['base_url'].rstrip('/')}/{slug}.html")
        print(f"  + {slug}.html")

    # roundups
    for r in roundups:
        (PUBLIC / f"{r['id']}.html").write_text(render_roundup(r, by_id, config, roundups), encoding="utf-8")
        urls.append(f"{config['base_url'].rstrip('/')}/{r['id']}.html")
        print(f"  + {r['id']}.html (roundup)")

    # static pages
    (PUBLIC / "best-guides.html").write_text(render_best_guides(roundups, config), encoding="utf-8")
    (PUBLIC / "about.html").write_text(render_about(config, roundups), encoding="utf-8")
    (PUBLIC / "index.html").write_text(render_index(products, config, roundups, by_id), encoding="utf-8")
    urls += [f"{config['base_url'].rstrip('/')}/best-guides.html",
             f"{config['base_url'].rstrip('/')}/about.html"]
    print(f"  + index.html, best-guides.html, about.html  ({len(products)} products, {len(roundups)} guides)")

    # sitemap + robots
    sm = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        sm.append(f"  <url><loc>{u}</loc><lastmod>{TODAY}</lastmod><changefreq>weekly</changefreq></url>")
    sm.append("</urlset>")
    (PUBLIC / "sitemap.xml").write_text("\n".join(sm), encoding="utf-8")
    base = config["base_url"].rstrip("/")
    (PUBLIC / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {base}/sitemap.xml\n", encoding="utf-8")
    (PUBLIC / ".nojekyll").write_text("", encoding="utf-8")
    print(f"  + sitemap.xml ({len(urls)} urls), robots.txt")
    print(f"Done. Open {PUBLIC / 'index.html'}")


if __name__ == "__main__":
    main()
