"""Read supplied exports from a directory or ZIPs without choosing conflicting copies."""
from dataclasses import dataclass
from functools import cached_property
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import re
from zipfile import ZipFile

import openpyxl


def text(value):
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


@dataclass(frozen=True)
class SourceFile:
    group: str
    name: str
    relative_path: str
    content: bytes
    locations: tuple[str, ...]

    @cached_property
    def sha256(self):
        return sha256(self.content).hexdigest()

    def read_bytes(self):
        return self.content


DEFAULT_SHEETS = {
    "C": "Order  Transaction-Level", "E": "Full Discounts Report", "F": "Redemptions",
    "G": "Person map", "I": "Clearance SKUs", "J": "Subscribers",
    "12": "Search keyword report All time ",
}


class SourceCatalog:
    """Deduplicate byte-identical copies and fail on ambiguous input versions.

    Logical source paths do not depend on the user's directory or ZIP layout.
    Every workbook read closes its file handle. Raw files are never extracted or written.
    """

    def __init__(self, data_dir):
        self.path = Path(data_dir).expanduser().resolve()
        if not self.path.is_dir():
            raise FileNotFoundError(f"Raw data directory does not exist: {self.path}")
        found = {}

        def add(name, content, location):
            normalized = name.replace("\\", "/")
            parts = normalized.split("/")
            base = parts[-1]
            if any(p == "__MACOSX" or p.startswith("._") for p in parts) or base.startswith("~$"):
                return
            group = self._group(normalized)
            if group is None:
                return
            key = f"{group}/{base}"
            digest = sha256(content).hexdigest()
            if key in found:
                old = found[key]
                if old["hash"] != digest:
                    raise ValueError(f"Conflicting copies of {key}; keep one source version in WEAVVE_DATA.")
                old["locations"].append(location)
            else:
                found[key] = dict(group=group, name=base, content=content, hash=digest, locations=[location])

        for path in sorted(self.path.rglob("*")):
            if not path.is_file() or any(p in {"__MACOSX", ".git", "venv", ".venv"} for p in path.parts):
                continue
            relative = path.relative_to(self.path).as_posix()
            if path.suffix.lower() == ".zip":
                with ZipFile(path) as archive:
                    for info in sorted(archive.infolist(), key=lambda x: x.filename):
                        if not info.is_dir() and self._group(info.filename):
                            add(info.filename, archive.read(info), f"{relative} > {info.filename}")
            elif self._group(relative):
                add(relative, path.read_bytes(), relative)
        self._files = [SourceFile(v["group"], v["name"], key, v["content"], tuple(sorted(v["locations"])))
                       for key, v in sorted(found.items())]
        self._matrices = {}
        self._sheets = {}
        self._rows = {}
        for group in "CDEFGIJKL" + "":
            self._check_unique(group)
        self._check_unique("12")

    @staticmethod
    def _group(name):
        name = name.replace("\\", "/")
        base = name.rsplit("/", 1)[-1]
        if base.startswith(("~$", "._")) or "__MACOSX" in name.split("/"):
            return None
        if base.lower().endswith(".xlsx"):
            if "A.SEO" in name or base.startswith("SEO (GSC)"):
                return "A"
            match = re.match(r"(12|[C-L])\.", base)
            return match.group(1) if match else None
        if base.lower().endswith(".csv") and ("B.SEO" in name or base.startswith("Organic KWs")):
            return "B"
        if base.lower().endswith(".eml"):
            return "H"
        return None

    def _check_unique(self, group):
        entries = self.files(group)
        if len(entries) > 1:
            raise ValueError(f"Multiple files for source {group}: {[f.name for f in entries]}. Select one version.")

    def files(self, group=None):
        return [f for f in self._files if group is None or f.group == str(group)]

    def require(self, groups):
        missing = [g for g in groups if not self.files(g)]
        if missing:
            raise FileNotFoundError(f"Missing raw sources: {', '.join(missing)}. Supply the original exports/ZIPs.")

    def sheets(self, code):
        code = str(code)
        if code not in self._sheets:
            self.require([code])
            with BytesIO(self.files(code)[0].read_bytes()) as stream:
                wb = openpyxl.load_workbook(stream, read_only=True, data_only=True)
                self._sheets[code] = tuple(wb.sheetnames)
                wb.close()
        return self._sheets[code]

    def matrix(self, code, sheet=None):
        code = str(code)
        names = self.sheets(code)
        sheet = sheet or DEFAULT_SHEETS.get(code) or next(
            (s for s in names if s.strip().lower() not in {"read me", "readme", "definitions", "legends"}), names[0])
        key = (code, sheet)
        if key not in self._matrices:
            if sheet not in names:
                raise ValueError(f"Source {code} has no sheet {sheet!r}; available sheets: {names}")
            wb = openpyxl.load_workbook(BytesIO(self.files(code)[0].read_bytes()), read_only=True, data_only=True)
            self._matrices[key] = [tuple(row) for row in wb[sheet].values]
            wb.close()
        return self._matrices[key]

    def rows(self, code, sheet=None):
        key = (str(code), sheet)
        if key not in self._rows:
            matrix = self.matrix(code, sheet)
            header_index = next((i for i, row in enumerate(matrix) if any(text(v) for v in row)), None)
            if header_index is None:
                return []
            headers = [text(v) for v in matrix[header_index]]
            named = [h for h in headers if h]
            if len(named) != len(set(named)) or "source_row" in named:
                raise ValueError(f"Ambiguous/reserved column names in source {code}, sheet {sheet}")
            self._rows[key] = [
                {**{h: row[j] if j < len(row) else None for j, h in enumerate(headers) if h}, "source_row": i + 1}
                for i, row in enumerate(matrix) if i > header_index and any(text(v) for v in row)
            ]
        return self._rows[key]

    def inventory(self):
        return [{"source": f.group, "file": f.relative_path, "sha256": f.sha256, "bytes": len(f.content)}
                for f in self._files]
