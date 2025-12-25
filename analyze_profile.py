"""Profile analysis utility for extracting performance metrics from profiling data."""

import json
import sys
from pathlib import Path


def analyze(filename):
    """Analyze a Chrome profile and extract performance metrics."""
    try:
        text = Path(filename).read_text(encoding="utf-8")
    except Exception:
        return

    # Extract JSON
    json_str = None
    for line in text.splitlines():
        if "const sessionData =" in line:
            start = line.find("{")
            end = line.rfind("};")
            end = line.rfind("}") + 1 if end == -1 else end + 1
            if start != -1 and end != -1:
                json_str = line[start:end]
                break

    if not json_str:
        return

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        return

    root = data.get("frame_tree")
    if not root:
        return

    metrics = {}  # name -> self_time

    def get_name(identifier):
        if "\u0000" in identifier:
            parts = identifier.split("\u0000")
            func_name = parts[0]
            file_path = parts[1]
            line_no = parts[2] if len(parts) > 2 else "?"

            if "/site-packages/" in file_path:
                file_short = file_path.split("/site-packages/")[-1]
            elif "/cdisplayagain/" in file_path:
                file_short = file_path.split("/cdisplayagain/")[-1]
            elif "/lib/python" in file_path:
                file_short = "stdlib/" + Path(file_path).name
            else:
                file_short = Path(file_path).name
            return f"{func_name} ({file_short}:{line_no})"
        return identifier

    def walk(node, parent_name="root"):
        identifier = node.get("identifier", "unknown")

        # Determine effectively who owns this self-time
        name = parent_name if identifier == "[self]" else get_name(identifier)

        total_time = node.get("time", 0.0)
        children = node.get("children", [])
        children_time = sum(child.get("time", 0.0) for child in children)
        self_time = total_time - children_time

        if self_time > 0:
            metrics[name] = metrics.get(name, 0.0) + self_time

        # Recurse
        # If this node was [self], we don't pass [self] as parent name down (it has no children usually).
        # But if it did, we'd use parent_name.
        # If it's a normal node, we use its name.
        next_parent = parent_name if identifier == "[self]" else name

        for child in children:
            walk(child, next_parent)

    walk(root)

    # Sort
    sorted_metrics = sorted(metrics.items(), key=lambda x: x[1], reverse=True)

    for _name, _st in sorted_metrics[:20]:
        pass


if __name__ == "__main__":
    for f in sys.argv[1:]:
        analyze(f)
