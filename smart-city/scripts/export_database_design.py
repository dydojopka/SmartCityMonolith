"""Generate SQLite DDL, DBML, DOT, PNG and a description from ONE local ORM."""
import argparse
import html
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("service", choices=["identity", "utility", "transport", "billing", "environment", "notification"])
    parser.add_argument("--no-diagram", action="store_true", help="Generate text files; run Graphviz on the host")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "services" / f"{args.service}-service"))
    from app.database import Base
    import app.models  # noqa: F401
    from sqlalchemy.dialects import sqlite
    from sqlalchemy.schema import CreateTable, CreateIndex

    target = root / "database-design" / args.service
    ddl, dbml, description = [], [], [f"# {args.service.title()} Service: база данных", "", "Схема сгенерирована из локальных SQLAlchemy-моделей. UUID - строка; даты/время - UTC. Пользовательский user_id не имеет FK в Identity DB. Defaults и updated_at задаются приложением; SQL отражает реальную DDL.", ""]
    dot = ['digraph schema {', 'graph [rankdir=LR, bgcolor="white"];', 'node [shape=plain fontname="Arial"];']
    for table in Base.metadata.sorted_tables:
        ddl.append(str(CreateTable(table).compile(dialect=sqlite.dialect())).strip() + ";")
        dbml.append(f"Table {table.name} {{")
        description += [f"## `{table.name}`", "", "| Поле | SQL-тип | Ограничения |", "|---|---|---|"]
        labels = [f'<TR><TD BGCOLOR="#2457d6"><FONT COLOR="white"><B>{table.name}</B></FONT></TD></TR>']
        for column in table.columns:
            sqltype = str(column.type.compile(dialect=sqlite.dialect()))
            settings = ["pk"] if column.primary_key else []
            if not column.nullable: settings.append("not null")
            for fk in column.foreign_keys: settings.append(f"ref: > {fk.target_fullname}")
            constraints = ", ".join(settings) or "nullable"
            dbml.append(f"  {column.name} {sqltype.lower()}" + (f" [{', '.join(settings)}]" if settings else ""))
            description.append(f"| `{column.name}` | `{sqltype}` | {constraints} |")
            labels.append(f'<TR><TD ALIGN="LEFT">{html.escape(column.name + ": " + sqltype + " " + constraints)}</TD></TR>')
        indexes = sorted(table.indexes, key=lambda i: i.name)
        if indexes:
            dbml.append("  Indexes {")
            for index in indexes:
                ddl.append(str(CreateIndex(index).compile(dialect=sqlite.dialect())) + ";")
                statement = str(CreateIndex(index).compile(dialect=sqlite.dialect()))
                description += ["", f"Индекс: `{statement}`."]
                if index.dialect_options["sqlite"].get("where") is not None:
                    continue  # DBML cannot faithfully express a partial UNIQUE index.
                cols = ", ".join(c.name for c in index.columns)
                cols = f"({cols})" if len(index.columns) > 1 else cols
                dbml.append(f"    {cols} [name: '{index.name}'" + (", unique" if index.unique else "") + "]")
            dbml.append("  }")
        notes = sorted(str(c.sqltext) for c in table.constraints if c.__class__.__name__ == "CheckConstraint")
        notes += [str(CreateIndex(i).compile(dialect=sqlite.dialect())) for i in indexes if i.dialect_options["sqlite"].get("where") is not None]
        if notes:
            dbml.append("  Note: '''" + "; ".join(notes) + "'''")
            description += ["", "CHECK/частичные индексы: " + "; ".join(f"`{n}`" for n in notes) + "."]
        dbml.append("}\n")
        dot.append(f'{table.name} [label=<<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="7">' + "".join(labels) + "</TABLE>>];")
        for column in table.columns:
            for fk in column.foreign_keys: dot.append(f'{fk.column.table.name} -> {table.name} [label="1:N {column.name}"];')
        description.append("")
    dot.append("}")
    target.mkdir(parents=True, exist_ok=True)
    sql = "PRAGMA foreign_keys=ON;\n\n" + "\n\n".join(ddl) + "\n"
    (target / "schema.sql").write_text("\n".join(line.rstrip() for line in sql.splitlines()) + "\n")
    (target / "schema.dbml").write_text("\n".join(dbml))
    (target / "description.md").write_text("\n".join(description))
    (target / "schema.dot").write_text("\n".join(dot) + "\n")
    image = f"{args.service}-diagram.png" if args.service in {"transport", "billing"} else "schema.png"
    if not args.no_diagram:
        subprocess.run(["dot", "-Tpng", str(target / "schema.dot"), "-o", str(target / image)], check=True)
    print(args.service, "SQL/DBML/DOT/PNG/description updated")


if __name__ == "__main__":
    main()
