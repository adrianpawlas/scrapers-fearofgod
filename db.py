"""Supabase upsert for products table."""
from datetime import datetime
from supabase import create_client, Client

from config import SUPABASE_URL, SUPABASE_ANON_KEY


def get_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


def _row_to_payload(row: dict) -> dict:
    return {
        "id": row["id"],
        "source": row["source"],
        "product_url": row["product_url"],
        "affiliate_url": row.get("affiliate_url"),
        "image_url": row["image_url"],
        "brand": row["brand"],
        "title": row["title"],
        "description": row.get("description"),
        "category": row.get("category"),
        "gender": row.get("gender"),
        "metadata": row.get("metadata"),
        "size": row.get("size"),
        "second_hand": row.get("second_hand", False),
        "image_embedding": row.get("image_embedding"),
        "country": row.get("country"),
        "compressed_image_url": row.get("compressed_image_url"),
        "tags": row.get("tags"),
        "other": row.get("other"),
        "price": row.get("price"),
        "sale": row.get("sale"),
        "additional_images": row.get("additional_images"),
        "info_embedding": row.get("info_embedding"),
        "created_at": datetime.utcnow().isoformat() + "Z",
    }


def upsert_products(rows: list[dict]) -> tuple[int, list[str]]:
    """
    Upsert product rows into public.products.
    Returns (success_count, list of error messages).
    """
    if not rows:
        return 0, []
    client = get_client()
    errors = []
    success = 0
    for row in rows:
        try:
            payload = _row_to_payload(row)
            client.table("products").upsert(
                payload,
                on_conflict="source,product_url",
            ).execute()
            success += 1
        except Exception as e:
            errors.append(f"{row.get('id', '?')}: {e}")
    return success, errors
