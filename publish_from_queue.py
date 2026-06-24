#!/usr/bin/env python3
"""
Drip-publisher for the affiliate site automation.

Reads queue.json (a curated list of REAL, verified ClickBank products), publishes
up to config["publish_per_run"] of them each run, and for each one:
  1. verifies the HopLink actually resolves (drops broken/dead products)
  2. downloads the product image (self-hosted) -> images.json
  3. writes a structured review -> content/<id>.html
  4. appends the product to products.json
  5. removes it from queue.json
generate_site.py then rebuilds the whole site (SEO, sitemap, internal links).

The cron in .github/workflows/publish.yml runs this, then generate_site.py,
commits the new state back, and deploys. Discovery (filling queue.json with real
products) is done via the browser during sessions — a cron cannot browse.

Run locally: python publish_from_queue.py
"""

import json
from pathlib import Path

import fetch_images as fi  # reuse fetch + image-extraction helpers

ROOT = Path(__file__).parent


def load(name, default):
    p = ROOT / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def save(name, data):
    (ROOT / name).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def build_review_html(stub):
    """Structured, honest review body (h2/p/ul) from the queued product data."""
    name = esc(stub["name"])
    niche = esc(stub.get("niche", stub.get("category", "this category")))
    summary = esc(stub.get("summary", ""))
    best_for = esc(stub.get("best_for", "the right buyer"))
    pros = stub.get("pros") or [
        f"Focused, practical {stub.get('niche','')} content".strip(),
        "60-day money-back guarantee through ClickBank",
        "Instant access after purchase",
    ]
    cons = stub.get("cons") or [
        "Results depend on consistent effort",
        "It's a digital product, not a physical one",
        "Some upsells are offered after purchase",
    ]
    pros_li = "".join(f"<li>{esc(x)}</li>" for x in pros)
    cons_li = "".join(f"<li>{esc(x)}</li>" for x in cons)
    health = stub.get("category", "").lower() in ("health & fitness",) or "supplement" in niche.lower()
    health_note = ("<p><em>Note: this is a dietary supplement, not a medical treatment. It is not intended "
                   "to diagnose, treat, cure, or prevent any condition, and results vary. Consult a "
                   "healthcare professional before starting.</em></p>") if health else ""
    return f"""<p>Looking into {name}? This review keeps it honest and to the point: what it actually is,
who it's a good fit for, and what to weigh before you buy.</p>
<h2>What is {name}?</h2>
<p>{summary}</p>{health_note}
<h2>Who is it best for?</h2>
<p>{name} is best for {best_for}. If that matches what you're after, it's worth a closer look.</p>
<h2>The good</h2>
<ul>{pros_li}</ul>
<h2>Things to keep in mind</h2>
<ul>{cons_li}</ul>
<h2>The bottom line</h2>
<p>{name} is a solid option in the {niche} space for the right person. Because it's sold through ClickBank,
it's backed by a 60-day money-back guarantee, so trying it is low-risk. Check current pricing and full
details on the official page below.</p>"""


def main():
    config = load("config.json", {})
    products = load("products.json", [])
    queue = load("queue.json", [])
    images = load("images.json", {})

    nickname = config.get("affiliate_nickname", "")
    per_run = int(config.get("publish_per_run", 1))
    existing_ids = {p["id"] for p in products}

    if not queue:
        print("Queue empty — nothing to publish. (Fill queue.json with verified products.)")
        return
    if not nickname:
        print("ERROR: config.affiliate_nickname is not set.")
        return

    batch = queue[:per_run]
    remaining = queue[per_run:]
    published = 0

    for stub in batch:
        pid = stub.get("id")
        vendor = stub.get("vendor")
        if not pid or not vendor:
            print(f"  - skip (missing id/vendor): {stub}")
            continue
        if pid in existing_ids:
            print(f"  - skip {pid}: already published")
            continue

        url = f"https://hop.clickbank.net/?affiliate={nickname}&vendor={vendor}"
        # 1. verify the link resolves (drop dead products) + reuse HTML for the image
        try:
            resp = fi.fetch(url)
            final = resp.geturl()
            html = resp.read(600_000).decode("utf-8", "ignore")
        except Exception as ex:
            print(f"  - drop {pid}: HopLink failed ({type(ex).__name__}) — vendor '{vendor}' may be dead")
            continue

        # 2. image (best-effort; absent -> no image, per project setting)
        try:
            cands = []
            m = fi.OG_RE.search(html) or fi.OG_RE2.search(html)
            if m:
                from urllib.parse import urljoin
                cands.append(urljoin(final, m.group(1).strip()))
            cands += [c for c in fi.candidate_images(html, final) if c not in cands]
            for img_url in cands[:12]:
                try:
                    ir = fi.fetch(img_url, timeout=20)
                    ct = ir.headers.get("Content-Type", "")
                    data = ir.read(5_000_000)
                except Exception:
                    continue
                if ct.lower().startswith("image") and len(data) >= 9000:
                    fn = f"{pid}{fi.ext_for(img_url, ct)}"
                    (fi.IMGDIR / fn).write_bytes(data)
                    images[pid] = f"img/{fn}"
                    break
        except Exception:
            pass

        # 3. review content
        (ROOT / "content" / f"{pid}.html").write_text(build_review_html(stub), encoding="utf-8")

        # 4. product entry
        entry = {
            "id": pid, "name": stub["name"], "category": stub.get("category", "Other"),
            "niche": stub.get("niche", ""), "price": stub.get("price", "low-ticket (official page)"),
            "affiliate_url": url, "rating": "N/A",
            "clickbank_stats": stub.get("clickbank_stats", {"approval_required": False}),
            "summary": stub.get("summary", ""), "best_for": stub.get("best_for", ""),
            "keywords": stub.get("keywords", []),
        }
        products.append(entry)
        existing_ids.add(pid)
        published += 1
        print(f"  + published {pid} ({'image' if pid in images else 'no image'})")

    save("products.json", products)
    save("queue.json", remaining)
    save("images.json", images)
    print(f"Done. Published {published}/{len(batch)} attempted. {len(remaining)} left in queue.")


if __name__ == "__main__":
    main()
