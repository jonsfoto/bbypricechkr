import json, os, urllib.request, datetime

API_KEY = os.environ["BESTBUY_API_KEY"]
SKU = os.environ["BESTBUY_SKU"]      # e.g., "6535721"
OUT_PATH = "price_history.json"

URL = f"https://api.bestbuy.com/v1/products/{SKU}.json?show=sku,name,salePrice,regularPrice,url&apiKey={API_KEY}"

def get_json(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

def load_history(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"sku": SKU, "name": None, "records": []}

def save_history(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def main():
    data = get_json(URL)  # single product object for /products/{sku}.json
    current_price = float(data.get("salePrice"))
    regular_price = float(data.get("regularPrice"))
    name = data.get("name")
    url = data.get("url")

    history = load_history(OUT_PATH)
    history["name"] = name

    last_price = history["records"][-1]["salePrice"] if history["records"] else None
    changed = (last_price is None) or (abs(current_price - last_price) > 1e-9)

    entry = {
        "salePrice": current_price,
        "regularPrice": regular_price,
        "url": url,
        "checkedAt": os.environ.get("CHECKED_AT") or datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    }

    if changed:
        history["records"].append(entry)
        save_history(OUT_PATH, history)
        print("PRICE_CHANGED")
    else:
        # still log a “ping” to the console for debugging
        print("NO_CHANGE")

if __name__ == "__main__":
    main()
