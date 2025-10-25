#!/usr/bin/env python3
import argparse, json, subprocess, hashlib, re, sys
from typing import List, Tuple, Any

def run(cmd: List[str]) -> str:
    return subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT).strip()

def commits_touching(path: str, follow: bool=True) -> List[str]:
    args = ["git", "log", "--format=%H"]
    if follow: args.append("--follow")
    args += ["--", path]
    out = run(args)
    return [l for l in out.splitlines() if l]

def get_file_at(commit: str, path: str) -> str | None:
    try:
        return run(["git", "show", f"{commit}:{path}"])
    except subprocess.CalledProcessError:
        return None

# --- tolerant JSON parsing helpers ---

_COMMENTS = re.compile(r"(^|\s)//.*?$|/\*.*?\*/", re.DOTALL | re.MULTILINE)
_TRAILING_COMMAS = re.compile(r",(\s*[}\]])")

def clean_json(text: str) -> str:
    # drop // and /* */ comments and trailing commas (JSON5-ish)
    t = _COMMENTS.sub(" ", text)
    t = _TRAILING_COMMAS.sub(r"\1", t)
    return t

def parse_json_maybe(text: str, ndjson: bool) -> Any | List[Any] | None:
    if ndjson:
        items = []
        for ln in text.splitlines():
            s = ln.strip()
            if not s: continue
            try:
                items.append(json.loads(clean_json(s)))
            except Exception:
                return None
        return items
    try:
        return json.loads(clean_json(text))
    except Exception:
        return None

# --- merge strategies ---

def item_key(item: Any):
    if isinstance(item, dict) and "id" in item:
        return ("id", str(item["id"]))
    dump = json.dumps(item, sort_keys=True, separators=(",", ":"))
    return ("hash", hashlib.sha1(dump.encode()).hexdigest())

def merge_history(history: List[Tuple[str, Any]], assume: str) -> Any:
    # history is oldest -> newest
    if not history: return None
    first = history[0][1]

    if assume == "list" or isinstance(first, list):
        seen = {}
        out = []
        for _, arr in history:
            if not isinstance(arr, list): continue
            for it in arr:
                k = item_key(it)
                if k not in seen:
                    seen[k] = True
                    out.append(it)
        return out

    if assume == "dict" or isinstance(first, dict):
        merged = {}
        for _, d in history:
            if not isinstance(d, dict): continue
            merged.update(d)  # last write wins
        return merged

    # fallback: latest snapshot
    return history[-1][1]

def main():
    p = argparse.ArgumentParser(description="Recover cumulative JSON from git history")
    p.add_argument("--path", required=True, help="Path to JSON file relative to repo root")
    p.add_argument("--output", default="combined.json")
    p.add_argument("--assume", choices=["auto","list","dict"], default="auto",
                   help="Force top-level type (default: auto-detect)")
    p.add_argument("--ndjson", action="store_true", help="Treat file as JSON Lines")
    p.add_argument("--no-follow", action="store_true", help="Do not follow renames")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    # sanity: show repo root vs cwd
    try:
        root = run(["git", "rev-parse", "--show-toplevel"])
        if args.verbose:
            print(f"Repo root: {root}")
    except subprocess.CalledProcessError as e:
        print("Error: not inside a git repo.")
        sys.exit(2)

    commits = commits_touching(args.path, follow=not args.no_follow)
    commits.reverse()  # oldest -> newest
    if args.verbose:
        print(f"Commits touching {args.path}: {len(commits)}")

    parsed = []
    failed = 0
    for c in commits:
        s = get_file_at(c, args.path)
        if not s: 
            failed += 1
            continue
        obj = parse_json_maybe(s, args.ndjson)
        if obj is None:
            failed += 1
        else:
            parsed.append((c, obj))

    if args.verbose:
        print(f"Parsed snapshots: {len(parsed)}; failed/empty: {failed}")

    if not parsed:
        print("No JSON data found (nothing parsable from history).")
        print("Tips: check --path, try --ndjson, or run with --verbose.")
        sys.exit(1)

    assume = args.assume
    if assume == "auto":
        assume = "list" if isinstance(parsed[0][1], list) else ("dict" if isinstance(parsed[0][1], dict) else "auto")

    combined = merge_history(parsed, assume)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(combined, f, ensure_ascii=False, indent=2)
    print(f"Wrote {args.output} from {len(parsed)} snapshots "
          f"(total commits seen: {len(commits)}).")

if __name__ == "__main__":
    main()
