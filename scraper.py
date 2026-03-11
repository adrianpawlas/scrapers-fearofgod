"""Scrape Fear of God collection and product data via Shopify JSON API."""
import re
import requests
from typing import Iterator
from config import (
    BASE_WITH_LOCALE,
    COLLECTION_URLS,
    LOCALE,
    PRODUCTS_PER_PAGE,
    SOURCE,
    BRAND,
)


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
    })
    return s


def _collection_handle(url: str) -> str:
    return url.rstrip("/").split("/collections/")[-1].split("?")[0]


def fetch_collection_products(
    collection_url: str,
    page: int = 1,
    limit: int = PRODUCTS_PER_PAGE,
) -> list[dict]:
    """Fetch one page of products from a collection (Shopify JSON)."""
    url = f"{collection_url.rstrip('/')}/products.json"
    params = {"limit": limit, "page": page}
    resp = _session().get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("products") or []


def iter_all_collection_products(
    collection_url: str,
    limit: int = PRODUCTS_PER_PAGE,
) -> Iterator[dict]:
    """Yield all products from a collection, page by page."""
    page = 1
    while True:
        products = fetch_collection_products(collection_url, page=page, limit=limit)
        if not products:
            break
        for p in products:
            yield p
        page += 1


def fetch_product_json(collection_handle: str, product_handle: str) -> dict | None:
    """Fetch full product JSON for a single product."""
    url = f"{BASE_WITH_LOCALE}/collections/{collection_handle}/products/{product_handle}.json"
    resp = _session().get(url, timeout=30)
    if resp.status_code != 200:
        return None
    data = resp.json()
    return data.get("product")


def _strip_html(html: str) -> str:
    if not html:
        return ""
    return re.sub(r"<[^>]+>", " ", html).replace("\n", " ").strip()


def _price_string(variants: list[dict]) -> tuple[str, str]:
    """Return (price_str, sale_str). Price = original; sale = current when on sale."""
    seen = set()
    price_parts = []
    sale_parts = []
    for v in variants or []:
        price = v.get("price") or "0"
        compare = (v.get("compare_at_price") or "").strip()
        cur = str(price).strip()
        currency = (v.get("price_currency") or "USD").strip().upper()
        key = (cur, currency)
        if key in seen:
            continue
        seen.add(key)
        if compare and float(compare or 0) > float(price or 0):
            price_parts.append(f"{compare}{currency}")
            sale_parts.append(f"{cur}{currency}")
        else:
            price_parts.append(f"{cur}{currency}")
            sale_parts.append(f"{cur}{currency}")
    return ", ".join(price_parts), ", ".join(sale_parts)


def _category_from_product_type(product_type: str) -> str:
    if not product_type:
        return ""
    return ", ".join(s.strip() for s in product_type.split("&"))


def _gender_from_tags(tags: list[str] | str, collection_handle: str) -> str:
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",")]
    for t in (tags or []):
        t = (t or "").strip().lower()
        if "gender:women" in t or "womens" in t:
            return "woman"
        if "gender:men" in t or "mens" in t:
            return "man"
    if "womens" in collection_handle.lower():
        return "woman"
    return "man"


def build_product_row(
    product: dict,
    collection_handle: str,
    product_url: str,
) -> dict:
    """Build a single product row for DB from full product JSON."""
    pid = product.get("id")
    handle = product.get("handle") or ""
    title = (product.get("title") or "").strip()
    body_html = product.get("body_html") or ""
    description = _strip_html(body_html)
    product_type = product.get("product_type") or ""
    category = _category_from_product_type(product_type)
    vendor = (product.get("vendor") or BRAND).strip()
    tags_list = product.get("tags") or []
    if isinstance(tags_list, str):
        tags_list = [t.strip() for t in tags_list.split(",")]
    tags = [t for t in tags_list if t] if tags_list else None

    variants = product.get("variants") or []
    price_str, sale_str = _price_string(variants)

    images = product.get("images") or []
    image_url = ""
    additional_urls = []
    if images:
        image_url = (images[0].get("src") or "").strip()
        for img in images[1:]:
            src = (img.get("src") or "").strip()
            if src:
                additional_urls.append(src)
    if not image_url and product.get("image"):
        image_url = (product["image"].get("src") or "").strip()

    additional_images = ", ".join(additional_urls) if additional_urls else None
    gender = _gender_from_tags(tags_list, collection_handle)

    size_options = []
    for opt in product.get("options") or []:
        if (opt.get("name") or "").lower() == "size":
            size_options = opt.get("values") or []
            break
    size = ", ".join(str(s) for s in size_options) if size_options else None

    metadata = {
        "vendor": vendor,
        "product_type": product_type,
        "tags": tags_list,
        "handle": handle,
        "shopify_id": pid,
        "variants_count": len(variants),
    }

    import json
    row = {
        "id": f"{SOURCE}-{pid}",
        "source": SOURCE,
        "product_url": product_url,
        "affiliate_url": None,
        "image_url": image_url,
        "brand": BRAND,
        "title": title,
        "description": description or None,
        "category": category or None,
        "gender": gender,
        "metadata": json.dumps(metadata, ensure_ascii=False),
        "size": size,
        "second_hand": False,
        "country": None,
        "other": None,
        "price": price_str or None,
        "sale": sale_str or None,
        "additional_images": additional_images,
        "tags": tags,
    }
    return row


def scrape_all_products() -> Iterator[dict]:
    """
    Scrape all products from configured collections.
    Yields product rows (dict) ready for embedding + DB, deduplicated by Shopify id.
    """
    seen_ids: set[int] = set()
    for collection_url in COLLECTION_URLS:
        collection_handle = _collection_handle(collection_url)
        for product_summary in iter_all_collection_products(collection_url):
            pid = product_summary.get("id")
            if pid in seen_ids:
                continue
            seen_ids.add(pid)
            handle = product_summary.get("handle")
            if not handle:
                continue
            full_product = fetch_product_json(collection_handle, handle)
            if not full_product:
                continue
            product_url = f"{BASE_WITH_LOCALE}/collections/{collection_handle}/products/{handle}"
            yield build_product_row(full_product, collection_handle, product_url)
