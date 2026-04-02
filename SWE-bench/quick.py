import os
import json

directory = "/home/rafay/.claude/projects/-home-rafay-Documents-309-assignment-PP2"
fields = [
    "input_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
    "output_tokens",
    "ephemeral_5m_input_tokens",
    "ephemeral_1h_input_tokens",
]


def to_int(value):
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except Exception:
            return 0
    return 0


def sum_tokens_in_file(path):
    totals = {field: 0 for field in fields}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            if obj.get("type") != "assistant":
                continue

            usage = (obj.get("message") or {}).get("usage") or {}

            # top-level usage fields
            for field in fields[:4]:
                totals[field] += to_int(usage.get(field, 0))

            # nested cache_creation fields
            cache_creation = usage.get("cache_creation") or {}
            if isinstance(cache_creation, dict):
                totals["ephemeral_5m_input_tokens"] += to_int(
                    cache_creation.get("ephemeral_5m_input_tokens", 0)
                )
                totals["ephemeral_1h_input_tokens"] += to_int(
                    cache_creation.get("ephemeral_1h_input_tokens", 0)
                )

    return totals


def walk_and_sum(base_dir):
    results = []
    for root, _, files in os.walk(base_dir):
        for filename in files:
            if not filename.endswith(".jsonl"):
                continue
            path = os.path.join(root, filename)
            rel = os.path.relpath(path, base_dir)
            totals = sum_tokens_in_file(path)
            results.append((rel, totals))
    return sorted(results, key=lambda t: t[0])


def aggregate_dir_totals(results):
    dir_totals: dict[str, dict[str, int]] = {}
    global_totals = {field: 0 for field in fields}

    for rel, totals in results:
        # update global
        for f in fields:
            global_totals[f] += totals.get(f, 0)

        # directory path relative to base
        dirpath = os.path.dirname(rel)
        if dirpath == "":
            dirpath = "."

        # build ancestors (include '.' as root)
        ancestors = []
        if dirpath == ".":
            ancestors = ["."]
        else:
            cur = dirpath
            while True:
                ancestors.append(cur)
                parent = os.path.dirname(cur)
                if parent == "":
                    ancestors.append(".")
                    break
                cur = parent

        for a in ancestors:
            if a not in dir_totals:
                dir_totals[a] = {field: 0 for field in fields}
            for f in fields:
                dir_totals[a][f] += totals.get(f, 0)

    return dir_totals, global_totals


def print_csv(results, dir_totals, global_totals):
    # per-file
    print("File, " + ", ".join(fields))
    for rel, totals in results:
        print(f"{rel}, " + ", ".join(str(totals.get(f, 0)) for f in fields))

    # per-directory (cumulative)
    print("\nDirectory totals (cumulative):")
    print("Directory, " + ", ".join(fields))
    for d in sorted(dir_totals.keys()):
        t = dir_totals[d]
        print(f"{d}, " + ", ".join(str(t.get(f, 0)) for f in fields))

    # global totals
    print("\nGlobal totals:")
    print(", ".join(str(global_totals.get(f, 0)) for f in fields))


def main():
    results = walk_and_sum(directory)
    dir_totals, global_totals = aggregate_dir_totals(results)
    print_csv(results, dir_totals, global_totals)


if __name__ == "__main__":
    main()