"""
Full pipeline: scrape Fear of God products, compute SigLIP embeddings, upsert to Supabase.
"""
import sys
from scraper import scrape_all_products
from embeddings import (
    load_siglip,
    image_embedding_from_url,
    text_embedding,
    build_info_text,
)
from db import upsert_products
from config import SOURCE, BRAND


def run(dry_run: bool = False, limit: int | None = None):
    """Scrape, embed, and upsert. If dry_run, only scrape and print count."""
    print("Loading SigLIP model...")
    processor, tokenizer, model, device = load_siglip()
    print("Scraping products...")
    products = list(scrape_all_products())
    if limit:
        products = products[:limit]
    print(f"Found {len(products)} products.")
    if dry_run:
        for i, p in enumerate(products[:5]):
            print(f"  {i+1}. {p.get('title')} | {p.get('product_url')}")
        return

    products = [p for p in products if (p.get("image_url") or "").strip()]
    print(f"Processing {len(products)} products with images...")

    rows = []
    for i, row in enumerate(products):
        if (i + 1) % 10 == 0 or i == 0:
            print(f"Processing {i+1}/{len(products)}: {row.get('title', '')[:50]}...")
        image_url = row.get("image_url")
        if image_url:
            emb = image_embedding_from_url(image_url, processor, model, device)
            row["image_embedding"] = emb
        else:
            row["image_embedding"] = None
        info_text = build_info_text(row)
        if info_text:
            row["info_embedding"] = text_embedding(info_text, tokenizer, model, device)
        else:
            row["info_embedding"] = None
        rows.append(row)

    print("Upserting to Supabase...")
    success, errors = upsert_products(rows)
    print(f"Upserted {success}/{len(rows)} products.")
    if errors:
        for e in errors[:20]:
            print(f"  Error: {e}")
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more errors.")
    return success, errors


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    limit = None
    for arg in sys.argv[1:]:
        if arg.startswith("--limit="):
            limit = int(arg.split("=")[1])
    run(dry_run=dry, limit=limit)
