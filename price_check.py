# price_check.py  (multi-SKU + CSV log + retry/backoff)

import json, os, sys, time, csv, pathlib, urllib.request, datetime
from urllib.error import HTTPError

API_KEY = os.environ["BESTBUY_API_KEY"]
SKU_LIST_RAW = os.environ["BESTBUY_SKUS"]  # e.g. "6535721,6523167 6416470"

OUT_DIR = "."  # JSON files in repo root
CSV_LOG = "price_history_log.csv"  # appended only when a price changes

def utc_now_iso():
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

def parse_skus(raw: str):
    parts = [p.strip() for p in raw.replace(",", " ").split()]
    return [p for p in parts if p]

def fetch_product(sku: str, retries: int = 3):
    url = f"https://api.bestbuy.com/v1/products/{sku}.json?show=sku,name,salePrice,regularPrice,url&apiKey={API_KEY}"
    delay = 1.0
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except HTTPError as e:
            # 403 Over Quota, 429 Too Many Requests, or transient server errors
            if e.code in (403, 429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(delay)
                delay *= 2  # 1s -> 2s -> 4s
                continue
            raise

def load_history(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"sku": None, "name": None, "records": []}

def save_history(path: str, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def append_csv(sku, name, sale, regular, url, checked_at):
    new_file = not pathlib.Path(CSV_LOG).exists()
    with open(CSV_LOG, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["checkedAt","sku","name","salePrice","regularPrice","url"])
        w.writerow([checked_at, sku, name, sale, regular, url])

def process_sku(sku: str, checked_at: str):
    data = fetch_product(sku)  # single product object
    name = data.get("name")
    sale = float(data.get("salePrice"))
    regular = float(data.get("regularPrice"))
    url = data.get("url")

    history_path = os.path.join(OUT_DIR, f"price_history_{sku}.json")
    history = load_history(history_path)
    history["sku"] = sku
    history["name"] = name

    last = history["records"][-1]["salePrice"] if history["records"] else None
    changed = (last is None) or (abs(sale - last) > 1e-9)

    entry = {
        "salePrice": sale,
        "regularPrice": regular,
        "url": url,
        "checkedAt": checked_at
    }

    if changed:
        history["records"].append(entry)
        save_history(history_path, history)
        append_csv(sku, name, sale, regular, url, checked_at)
        print(f"CHANGED {sku} {sale} {url}")
        return True, (sku, name, sale, url)
    else:
        print(f"NO_CHANGE {sku} {sale}")
        return False, (sku, name, sale, url)

def main():
    checked_at = os.environ.get("CHECKED_AT") or utc_now_iso()
    skus = parse_skus(SKU_LIST_RAW)
    changed_list = []

    for sku in skus:
        try:
            changed, info = process_sku(sku, checked_at)
            if changed:
                changed_list.append(info)
        except Exception as e:
            print(f"ERROR {sku} {e}", file=sys.stderr)
        time.sleep(0.5)  # reduce burstiness

    # summary lines parsed by the workflow
    print(f"CHANGED_COUNT {len(changed_list)}")
    for sku, name, price, url in changed_list:
        print(f"CHANGED_LINE {sku} | {name} | {price} | {url}")

if __name__ == "__main__":
    main()
