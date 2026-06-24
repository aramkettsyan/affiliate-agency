#!/usr/bin/env python3
"""
Download each product's official og:image (the vendor-designated share image)
and self-host it under public/img/. Writes images.json mapping id -> local path.
Skips any product whose image can't be fetched (per requirements).
Run: python fetch_images.py
"""

import json
import re
import ssl
import urllib.request
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs

ROOT = Path(__file__).parent
IMGDIR = ROOT / "public" / "img"
IMGDIR.mkdir(parents=True, exist_ok=True)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
CTX = ssl.create_default_context()  # normal TLS verification

OG_RE = re.compile(
    r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)(?::secure_url)?["\']'
    r'[^>]+content=["\']([^"\']+)["\']', re.I)
OG_RE2 = re.compile(
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']'
    r'(?:og:image|twitter:image)["\']', re.I)

IMG_RE = re.compile(r'<img[^>]+src=["\']([^"\']+\.(?:png|jpe?g|webp))["\']', re.I)
POS = re.compile(r'(product|bottle|jar|tube|dropper|pack|mockup|cover|book|hero|supplement|jug|box|'
                 r'\d-?bottle|\d-?month|spline|render)', re.I)
NEG = re.compile(r'(logo|icon|badge|seal|guarant|visa|master|paypal|amex|discover|secure|card|'
                 r'star|arrow|btn|button|spacer|pixel|ssl|norton|mcafee|clickbank|money-?back|'
                 r'header|footer|banner-?ad|checkout|payment|review-?\d|avatar|testimonial)', re.I)


def candidate_images(html, base):
    """Return product-image URLs in priority order (keyword matches first)."""
    seen, pos, other = set(), [], []
    for src in IMG_RE.findall(html):
        url = urljoin(base, src.strip())
        if url in seen or NEG.search(url):
            continue
        seen.add(url)
        (pos if POS.search(url) else other).append(url)
    return pos + other


def fetch(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    return urllib.request.urlopen(req, timeout=timeout, context=CTX)


def vendor_of(p):
    q = parse_qs(urlparse(p["affiliate_url"]).query)
    return (q.get("vendor") or [""])[0]


def ext_for(url, ctype):
    ct = (ctype or "").lower()
    if "png" in ct:
        return ".png"
    if "webp" in ct:
        return ".webp"
    if "gif" in ct:
        return ".gif"
    if "jpeg" in ct or "jpg" in ct:
        return ".jpg"
    m = re.search(r"\.(png|jpe?g|webp|gif)(?:\?|$)", url, re.I)
    return ("." + m.group(1).lower().replace("jpeg", "jpg")) if m else ".jpg"


def main():
    products = json.loads((ROOT / "products.json").read_text(encoding="utf-8"))
    images = {}
    ok = skip = 0
    for p in products:
        pid, vendor = p["id"], vendor_of(p)
        hop = f"https://hop.clickbank.net/?affiliate=aram094&vendor={vendor}"
        try:
            resp = fetch(hop)
            final = resp.geturl()
            html = resp.read(600_000).decode("utf-8", "ignore")
            # priority: og:image first, then keyword-matched product images
            candidates = []
            m = OG_RE.search(html) or OG_RE2.search(html)
            if m:
                candidates.append(urljoin(final, m.group(1).strip()))
            candidates += [c for c in candidate_images(html, final) if c not in candidates]

            saved = False
            for img_url in candidates[:12]:
                try:
                    ir = fetch(img_url, timeout=20)
                    ctype = ir.headers.get("Content-Type", "")
                    data = ir.read(5_000_000)
                except Exception:
                    continue
                if not ctype.lower().startswith("image") or len(data) < 9000:
                    continue
                fn = f"{pid}{ext_for(img_url, ctype)}"
                (IMGDIR / fn).write_bytes(data)
                images[pid] = f"img/{fn}"
                ok += 1
                saved = True
                print(f"  + {pid}: {fn}  ({len(data)//1024} KB)  <- {img_url[:68]}")
                break
            if not saved:
                print(f"  - {pid}: no usable product image  (skip)")
                skip += 1
        except Exception as ex:
            print(f"  - {pid}: {type(ex).__name__} {ex}  (skip)")
            skip += 1
    (ROOT / "images.json").write_text(json.dumps(images, indent=2), encoding="utf-8")
    print(f"\nDone. {ok} images downloaded, {skip} skipped. -> images.json")


if __name__ == "__main__":
    main()
