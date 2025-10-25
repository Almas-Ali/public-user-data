import json

in_path  = "scraped_data.json"
out_path = "scraped_data_cleaned.json"

with open(in_path, "r", encoding="utf-8") as f:
    data = json.load(f)  # list of dicts

# normalize id to string and keep the LAST item per id
by_id = {}
dups = []
for obj in data:
    key = str(obj.get("id")).strip()
    if key in by_id:
        dups.append(key)
    by_id[key] = obj

deduped = list(by_id.values())

with open(out_path, "w", encoding="utf-8") as f:
    json.dump(deduped, f, ensure_ascii=False, indent=2)

# duplicates ids
print("Duplicate IDs:")
for d in set(dups):
    print(d)

print(f"Original: {len(data)}  |  Deduped: {len(deduped)}  |  Duplicates found: {len(set(dups))}")
