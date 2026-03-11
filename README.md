# Fear of God Scraper

Scrapes [Fear of God](https://fearofgod.com) product catalog, generates image and text embeddings with **SigLIP** (`google/siglip-base-patch16-384`, 768-dim), and upserts into a Supabase `products` table.

## Requirements

- Python 3.10+
- Supabase project with `public.products` table (see schema below)
- Optional: GPU for faster embeddings

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your SUPABASE_URL and SUPABASE_ANON_KEY (or use defaults in config.py)
```

## Usage

**Full run (scrape → embed → upsert):**
```bash
python run.py
```

**Dry run (scrape only, no DB):**
```bash
python run.py --dry-run
```

**Test with a few products:**
```bash
python run.py --limit=5
```

## Automation

- **Manual:** Run `python run.py` anytime.
- **Daily at midnight (UTC):** Use the GitHub Action `.github/workflows/daily-scrape.yml`. Add repo secrets:
  - `SUPABASE_URL`
  - `SUPABASE_ANON_KEY`

## Data

- **Source:** `scraper-fearofgod`
- **Brand:** `Fear of God`
- **Collections:** Mens All, Womens All (paginated via Shopify JSON API)
- **Embeddings:** Image and text with `google/siglip-base-patch16-384` (768 dimensions)

## Table

Upserts into `public.products` with unique constraint `(source, product_url)`. Required fields (e.g. `id`, `source`, `product_url`, `image_url`, `title`, `brand`) are always set; `image_embedding` and `info_embedding` are 768-d vectors from SigLIP.
