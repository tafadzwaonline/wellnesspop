"""Regenerate docs/input-schema.md and docs/input-schema.json from wellnesspop.schema.

Run from the repository root: python -m scripts.generate_schema_doc"""

import json
from pathlib import Path

from wellnesspop.schema import SCHEMA_VERSION, spec_inventory

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    rows = spec_inventory()
    (ROOT / "docs" / "input-schema.json").write_text(
        json.dumps({"schema_version": SCHEMA_VERSION, "fields": rows}, indent=2), encoding="utf-8")
    lines = [f"# Input schema (version {SCHEMA_VERSION})", "",
             "Generated from `wellnesspop/schema.py` by `scripts/generate_schema_doc.py`. "
             "Rates are fractions (0.2 = 20%); money is USD; dates are ISO (YYYY-MM-DD).", ""]
    group = None
    for r in rows:
        if r["group"] != group:
            group = r["group"]
            title = "Scalar fields" if group == "scalar" else f"Records: `{group}`"
            lines += ["", f"## {title}", "",
                      "| Field | Type | Unit | Default rule | Validation | Provenance | Nullable |",
                      "|---|---|---|---|---|---|---|"]
        kind = r["kind"] + (f" ({', '.join(r['choices'])})" if r["choices"] else "")
        lines.append(f"| `{r['path']}` | {kind} | {r['unit']} | {r['default_rule']} | "
                     f"{r['validation']} | {r['provenance']} | {'yes' if r['nullable'] else 'no'} |")
    lines += ["", "Provenance conventions: `illustrative` for invented defaults, `brief` for "
              "Appendix B values, `derived` for calculated or system values, `user` once edited "
              "(the original provenance is kept in `original_source_kind`), `researched` for "
              "values with a documented source and retrieval date.", ""]
    (ROOT / "docs" / "input-schema.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
