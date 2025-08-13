#!/usr/bin/env python3
import csv, sqlite3, sys, math, argparse
from pathlib import Path

def is_valid_gtin(g):
    return g.isdigit() and len(g) in (8,12,13,14)

def as_float(x):
    try:
        return float(x)
    except:
        return math.nan

def run(csv_path: Path, db_path: Path):
    # Ordner sicherstellen
    db_path.parent.mkdir(parents=True, exist_ok=True)

    if not csv_path.exists():
        print(f"Fehlt: {csv_path}")
        sys.exit(1)

    con = sqlite3.connect(db_path)
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS offers (
        id INTEGER PRIMARY KEY,
        gtin TEXT NOT NULL,
        title TEXT NOT NULL,
        brand TEXT,
        mpn TEXT,
        seller TEXT NOT NULL,
        price REAL NOT NULL,
        currency TEXT NOT NULL,
        shipping_cost REAL DEFAULT 0,
        availability TEXT,
        url TEXT,
        image_url TEXT,
        total_price REAL NOT NULL,
        last_imported TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    # MVP: Full refresh
    cur.execute("DELETE FROM offers")

    REQUIRED = ["gtin","title","seller","price","currency"]
    ACCEPTED_CURRENCIES = {"EUR"}  # MVP: nur EUR

    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = [c for c in REQUIRED if c not in reader.fieldnames]
        if missing:
            print(f"CSV-Header unvollständig, fehlt: {missing}")
            sys.exit(2)

        rows = bad = 0
        for row in reader:
            rows += 1
            gtin = (row.get("gtin") or "").strip()
            if not is_valid_gtin(gtin):
                bad += 1
                continue

            currency = (row.get("currency") or "").strip().upper()
            if currency not in ACCEPTED_CURRENCIES:
                bad += 1
                continue

            price = as_float(row.get("price"))
            shipping = as_float(row.get("shipping_cost") or 0)
            if math.isnan(price) or math.isnan(shipping):
                bad += 1
                continue

            total = round(price + shipping, 2)

            cur.execute("""
            INSERT INTO offers (gtin,title,brand,mpn,seller,price,currency,shipping_cost,availability,url,image_url,total_price)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                gtin,
                (row.get("title") or "").strip(),
                (row.get("brand") or "").strip() or None,
                (row.get("mpn") or "").strip() or None,
                (row.get("seller") or "").strip(),
                price,
                currency,
                shipping,
                (row.get("availability") or "").strip() or None,
                (row.get("url") or "").strip() or None,
                (row.get("image_url") or "").strip() or None,
                total
            ))

    con.commit()

    print("\nGünstigstes Angebot je GTIN:")
    for (gtin, title, seller, price, ship, total) in cur.execute("""
        SELECT o.gtin, o.title, o.seller, o.price, o.shipping_cost, o.total_price
        FROM offers o
        JOIN (
            SELECT gtin, MIN(total_price) AS min_total FROM offers GROUP BY gtin
        ) m ON o.gtin = m.gtin AND o.total_price = m.min_total
        ORDER BY o.gtin
    """):
        print(f"- {gtin} | {title} → {seller}: {price:.2f} + {ship:.2f} = {total:.2f} EUR")

    con.close()
    print(f"\nFertig. DB: {db_path}")

def parse_args():
    here = Path(__file__).resolve().parent
    default_csv = (here / ".." / "data" / "offers.csv").resolve()
    default_db  = (here / ".." / "data" / "price_index.sqlite").resolve()

    p = argparse.ArgumentParser(description="Importiere CSV-Angebote in SQLite (MVP).")
    p.add_argument("--csv", dest="csv_path", type=Path, default=default_csv,
                   help=f"Pfad zur CSV (Default: {default_csv})")
    p.add_argument("--db", dest="db_path", type=Path, default=default_db,
                   help=f"Pfad zur SQLite-DB (Default: {default_db})")
    return p.parse_args()

if __name__ == "__main__":
    args = parse_args()
    run(args.csv_path, args.db_path)
