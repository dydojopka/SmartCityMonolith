"""Build a deterministic assignment ZIP with all six database deliverables."""
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED


def main():
    root = Path(__file__).resolve().parents[1]
    for name in ("identity", "utility", "transport", "billing", "environment", "notification"):
        target = root / "database-design" / name
        image = f"{name}-diagram.png" if name in {"transport", "billing"} else "schema.png"
        for file in ("schema.sql", "schema.dbml", "description.md", image):
            if not (target / file).is_file() or not (target / file).stat().st_size:
                raise RuntimeError(f"Missing database deliverable: {target / file}")
    with ZipFile(root / "database-design.zip", "w", compression=ZIP_DEFLATED) as archive:
        for path in sorted((root / "database-design").glob("*/*")):
            if path.suffix not in {".sql", ".dbml", ".md", ".png", ".pdf", ".dot"}: continue
            item = ZipInfo(str(path.relative_to(root)), date_time=(2026, 10, 5, 0, 0, 0))
            item.compress_type = ZIP_DEFLATED
            item.external_attr = 0o644 << 16
            archive.writestr(item, path.read_bytes())
    print(root / "database-design.zip")


if __name__ == "__main__":
    main()
