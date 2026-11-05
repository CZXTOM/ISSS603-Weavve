"""One local, versioned dataset used by every current analysis notebook.

The manifest is an executable contract: source hashes, cleaning-code hashes, rule
parameters, table schemas and output hashes. Sensitive outputs stay outside this repo.
"""
import argparse
import csv
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from hashlib import sha256
import json
import os
import platform
from importlib.metadata import version
from pathlib import Path
import shutil
import tempfile
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

from .paths import DATA, OUT, ROOT
from .sources import SourceCatalog


RULES = {
    "version": "1",
    "gst_from": "2025-08-26",
    "gst_divisor": "1.09",
    "special_person_ids": ["P000034", "P013881"],
    "money": "Signed net including refunds; per-line GST gate; positive discount amounts.",
    "purchase": "Noncancelled order with corrected signed net strictly above zero.",
    "customer_scope": "Website or Shopee purchases, excluding configured special accounts.",
    "other_platforms": "Keep sales, but do not infer reliable person-level repeat behavior.",
    "clearance": "Listed SKU flag with source timing; never remove its lifetime history.",
    "date_codes": "Preserve date-typed values as unresolved; do not guess original coupon strings.",
}
REQUIRED = ["A", "B", "C", "D", "E", "F", "G", "I", "J", "K", "L", "12"]


def _json(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Path):
        return str(value)
    raise TypeError(type(value).__name__)


def _canonical(value):
    return json.dumps(value, default=_json, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _code_inventory():
    folder = Path(__file__).resolve().parent
    names = ["clean.py", "sources.py", "clean_transactions.py", "clean_support.py", "clean_search.py"]
    return [{"file": n, "sha256": sha256((folder / n).read_bytes()).hexdigest()} for n in names]


def _kind(value):
    if isinstance(value, bool): return "bool"
    if isinstance(value, datetime): return "datetime"
    if isinstance(value, date): return "date"
    if isinstance(value, Decimal): return "decimal"
    if isinstance(value, int): return "int"
    if isinstance(value, float): return "float"
    if isinstance(value, (list, dict, tuple)): return "json"
    return "str"


def _column_kind(values):
    kinds = {_kind(v) for v in values if v is not None and v != ""}
    if not kinds: return "str"
    if len(kinds) == 1: return next(iter(kinds))
    if kinds <= {"int", "float"}: return "float"
    if kinds <= {"int", "float", "decimal"}: return "decimal"
    if kinds <= {"date", "datetime"}: return "datetime"
    return "str"


def _encode(value, kind):
    if value is None: return ""
    if kind == "bool": return "true" if value else "false"
    if kind == "json": return json.dumps(value, default=_json, sort_keys=True, ensure_ascii=False)
    if isinstance(value, (datetime, date)): return value.isoformat()
    return str(value)


def _decode(value, kind):
    if kind == "str": return value
    if value == "": return None
    if kind == "bool":
        if value not in {"true", "false"}: raise ValueError(f"Invalid boolean {value!r}")
        return value == "true"
    if kind == "int": return int(value)
    if kind == "float": return float(value)
    if kind == "decimal": return Decimal(value)
    if kind == "date": return date.fromisoformat(value)
    if kind == "datetime": return datetime.fromisoformat(value)
    if kind == "json": return json.loads(value)
    raise ValueError(f"Unknown column type: {kind}")


def _write_table(path, records):
    records = list(records)
    columns = list(dict.fromkeys(k for row in records for k in row))
    # Empty tables still get an explicit schema and are valid outputs.
    schema = {c: _column_kind(row.get(c) for row in records) for c in columns}
    with Path(path).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for row in records:
            writer.writerow({c: _encode(row.get(c), schema[c]) for c in columns})
    return {"file": Path(path).name, "rows": len(records), "columns": schema,
            "sha256": sha256(Path(path).read_bytes()).hexdigest()}


def _validate_output_root(out_dir, data_dir):
    output = Path(out_dir).expanduser().resolve()
    raw = Path(data_dir).expanduser().resolve()
    repo = ROOT.resolve()
    if output == repo or output.is_relative_to(repo):
        raise ValueError("Cleaned outputs must be outside the Git repository. Set WEAVVE_OUT to a private folder.")
    if output == raw or output.is_relative_to(raw) or raw.is_relative_to(output):
        raise ValueError("Raw input and cleaned-output directories must be separate, nonoverlapping folders.")
    clean = (output / "clean").resolve()
    if clean.parent != output:
        raise ValueError("The clean directory must not redirect outside the output directory.")
    return output


def _remove_staging(path, parent):
    target = Path(path).resolve()
    parent = Path(parent).resolve()
    if target == parent or not target.is_relative_to(parent) or not target.name.startswith(".building-"):
        raise ValueError("Refusing to remove a path outside the cleaning staging directory.")
    shutil.rmtree(target)


@dataclass
class Dataset:
    path: Path
    manifest: dict

    def verify(self):
        for name in self.manifest["tables"]:
            self.table(name)
        return self

    def table(self, name):
        if name not in self.manifest["tables"]:
            raise KeyError(f"Unknown cleaned table {name!r}; available: {', '.join(self.manifest['tables'])}")
        entry = self.manifest["tables"][name]
        path = (self.path / entry["file"]).resolve()
        if not path.is_relative_to(self.path.resolve()) or path.suffix != ".csv":
            raise ValueError(f"Invalid table path for {name}")
        if not path.is_file() or sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError(f"Cleaned table {name} was modified after build.")
        with path.open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            expected = list(entry["columns"])
            # JSON uses sort_keys for stable metadata; CSV column order is checked by set.
            if (set(reader.fieldnames or []) != set(expected)
                    or len(reader.fieldnames or []) != len(expected)):
                raise ValueError(f"Schema mismatch for {name}")
            records = []
            for row in reader:
                if None in row or any(v is None for v in row.values()):
                    raise ValueError(f"Malformed CSV row in {name}")
                records.append({c: _decode(row[c], kind) for c, kind in entry["columns"].items()})
        if len(records) != entry["rows"]:
            raise ValueError(f"Row count mismatch for {name}")
        return records

    def frame(self, name):
        import pandas as pd
        return pd.DataFrame(self.table(name), columns=list(self.manifest["tables"][name]["columns"]))


def _fingerprint(catalog):
    contract = {"rules": RULES, "sources": catalog.inventory(), "code": _code_inventory(),
                "runtime": {"python": platform.python_version(), "openpyxl": version("openpyxl")}}
    return sha256(_canonical(contract)).hexdigest(), contract


def load_dataset(path=None, data_dir=None, out_dir=None, verify=True):
    data_dir = Path(data_dir or DATA).expanduser().resolve()
    out_dir = Path(out_dir or OUT).expanduser().resolve()
    selected = path or os.environ.get("WEAVVE_CLEAN")
    if selected is None:
        pointer = out_dir / "clean" / "latest.json"
        if not pointer.is_file():
            raise FileNotFoundError("No cleaned dataset. Run python scripts/build_clean_data.py first.")
        selected = out_dir / "clean" / json.loads(pointer.read_text(encoding="utf-8"))["dataset_id"]
    selected = Path(selected).expanduser().resolve()
    manifest = json.loads((selected / "manifest.json").read_text(encoding="utf-8"))
    dataset = Dataset(selected, manifest)
    if verify:
        fingerprint, contract = _fingerprint(SourceCatalog(data_dir))
        if manifest.get("dataset_id") != fingerprint or manifest.get("contract") != contract:
            raise ValueError("Cleaned dataset is stale for these raw files or cleaning code. Run build_clean_data.py.")
        dataset.verify()
    return dataset


def _zip_dataset(dataset):
    dataset.verify()
    destination = dataset.path.parent / f"weavve_clean_{dataset.manifest['dataset_id'][:16]}.zip"
    names = {entry["file"] for entry in dataset.manifest["tables"].values()}
    names.update({"manifest.json", "DATA_DICTIONARY.md"})
    with ZipFile(destination, "w", compression=ZIP_DEFLATED) as archive:
        for name in sorted(names):
            path = (dataset.path / name).resolve()
            if not path.is_relative_to(dataset.path.resolve()) or not path.is_file():
                raise ValueError(f"Invalid bundle member: {name}")
            info = ZipInfo(path.name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())
    return destination


def build_dataset(data_dir=None, out_dir=None, make_zip=False):
    from .clean_transactions import clean_transactions
    from .clean_support import build_support_tables
    from .clean_search import build_search_tables

    data_dir = Path(data_dir or DATA).expanduser().resolve()
    output = _validate_output_root(out_dir or OUT, data_dir)
    catalog = SourceCatalog(data_dir)
    catalog.require(REQUIRED)
    fingerprint, contract = _fingerprint(catalog)
    parent = output / "clean"
    parent.mkdir(parents=True, exist_ok=True)
    destination = parent / fingerprint
    if destination.exists():
        dataset = load_dataset(destination, data_dir=data_dir)
    else:
        result = clean_transactions(catalog.rows("C"), catalog.rows("G", "Person map"),
                                    catalog.rows("G", "Order channel"), catalog.rows("D"), catalog.rows("I"),
                                    special_person_ids=RULES["special_person_ids"],
                                    gst_from=date.fromisoformat(RULES["gst_from"]),
                                    gst_divisor=Decimal(RULES["gst_divisor"]))
        order_dates = [r["order_date"] for r in result["tables"]["orders"]]
        if not order_dates:
            raise ValueError("No noncancelled orders remain; inspect the raw source and cleaning rules.")
        cutoff = max(order_dates)
        combined = [result, build_support_tables(catalog, cutoff), build_search_tables(catalog, cutoff)]
        tables, warnings, checks = {}, [], {}
        for i, component in enumerate(combined):
            overlap = tables.keys() & component["tables"].keys()
            if overlap: raise ValueError(f"Duplicate output tables: {overlap}")
            tables.update(component["tables"])
            warnings.extend(component.get("warnings", []))
            checks[["transactions", "support", "search"][i]] = component.get("checks", {})
        staging = Path(tempfile.mkdtemp(prefix=".building-", dir=parent))
        try:
            entries = {name: _write_table(staging / f"{name}.csv", records) for name, records in sorted(tables.items())}
            manifest = {"dataset_id": fingerprint, "contract": contract, "transaction_cutoff": cutoff.isoformat(),
                        "tables": entries, "checks": checks, "warnings": warnings}
            (staging / "manifest.json").write_text(json.dumps(manifest, default=_json, sort_keys=True, indent=2), encoding="utf-8")
            dictionary = ["# Local cleaned dataset", "", f"Dataset ID: `{fingerprint}`", "",
                          "Use this manifest and these tables together. Do not commit or upload this directory to GitHub.",
                          "Amounts are in the supplied currency. Raw source columns and explicit normalized fields are distinct.",
                          "Dates, monetary types and table grains are documented in docs/cleaning_contract.md in the code repository.", ""]
            for name, entry in entries.items():
                dictionary += [f"## {name}", "", f"Rows: {entry['rows']}", "", "| Column | Type |", "|---|---|"]
                dictionary += [f"| {c} | {kind} |" for c, kind in entry["columns"].items()]
                dictionary.append("")
            dictionary += ["## Review flags", ""] + [f"- {w}" for w in warnings]
            (staging / "DATA_DICTIONARY.md").write_text("\n".join(dictionary), encoding="utf-8")
            Dataset(staging, manifest).verify()
            try:
                staging.rename(destination)
            except FileExistsError:
                load_dataset(destination, data_dir=data_dir)
                _remove_staging(staging, parent)
            dataset = Dataset(destination, manifest)
        except Exception:
            if staging.exists(): _remove_staging(staging, parent)
            raise
    pointer = parent / "latest.json"
    temp_pointer = parent / f".latest-{os.getpid()}.tmp"
    temp_pointer.write_text(json.dumps({"dataset_id": fingerprint}, indent=2), encoding="utf-8")
    temp_pointer.replace(pointer)
    if make_zip: _zip_dataset(dataset)
    return dataset


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build one shared set of private, local cleaned tables.")
    parser.add_argument("--data", type=Path, help="Original files or supplied ZIPs (default WEAVVE_DATA).")
    parser.add_argument("--out", type=Path, help="Private output directory outside the repository (default WEAVVE_OUT).")
    parser.add_argument("--zip", action="store_true", help="Also create a local ZIP; never publish it to GitHub.")
    args = parser.parse_args(argv)
    dataset = build_dataset(args.data, args.out, args.zip)
    print(f"Dataset ID: {dataset.manifest['dataset_id']}")
    print(f"Local tables: {dataset.path}")
    print(f"Tables: {len(dataset.manifest['tables'])}; review flags: {len(dataset.manifest['warnings'])}")
    if args.zip: print(f"Local ZIP: {dataset.path.parent / ('weavve_clean_' + dataset.manifest['dataset_id'][:16] + '.zip')}")


if __name__ == "__main__":
    main()
