# RowSync

Copy rows from a production Microsoft SQL Server database to dev, stage, or any other target defined in your config — using a **SELECT-only** query with preview, upsert, and live progress.

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688)

## Features

- **SQL editor** — CodeMirror with syntax highlighting and schema autocomplete (tables, columns, aliases)
- **SELECT-only** — Blocks INSERT, UPDATE, DELETE, DROP, and other write/DDL statements
- **Preview** — Run your query against production before copying
- **TOP-aware sync** — Respects `TOP (N)` in your query when applying
- **Multi-table JOINs** — Copies rows from every table referenced in the query
- **Auto-create tables** — Creates missing target tables from production schema (no FKs)
- **Upsert** — Skips duplicates by primary key instead of failing
- **Live progress** — Server-Sent Events stream step-by-step status to the UI
- **Offline UI** — CodeMirror, fonts, and all frontend assets are bundled locally (no CDN required)

## Requirements

- Python 3.10+
- [ODBC Driver 17 for SQL Server](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server) (or compatible)
- Network access to your MSSQL instances

## Quick start

```bash
git clone <your-repo-url>
cd RowSync

python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux / macOS

pip install -r requirements.txt
copy config.example.json config.json   # Windows
# cp config.example.json config.json   # Linux / macOS
```

Edit `config.json` with your connection strings, then start the app:

```bash
python run.py
```

Open **http://127.0.0.1:8765**

The web UI works fully offline once installed — all JavaScript, CSS, and fonts are served from `static/vendor/`.

## Offline / air-gapped use

RowSync does not load any frontend assets from the internet at runtime. Database connectivity still requires network access to your SQL Server instances.

To refresh bundled UI assets after upgrading dependencies:

```bash
python scripts/download_vendor_assets.py
```

## Configuration

`config.json` is git-ignored. Use `config.example.json` as a template.

| Key | Description |
|-----|-------------|
| `connections.production` | Source database (read-only queries run here) |
| `connections.*` | Any other key (`dev`, `stage`, `local`, `test`, …) becomes a sync target |
| `preview_row_limit` | Max rows shown in preview when the query has no `TOP` (default: 500) |

Example:

```json
{
  "connections": {
    "production": "DRIVER={...};SERVER=prod;DATABASE=MyDb;UID=...;PWD=...;TrustServerCertificate=yes",
    "dev": "DRIVER={...};SERVER=dev;DATABASE=MyDb_Dev;UID=...;PWD=...;TrustServerCertificate=yes",
    "local": "DRIVER={...};SERVER=localhost;DATABASE=MyDb;UID=...;PWD=...;TrustServerCertificate=yes"
  },
  "preview_row_limit": 500
}
```

Add or remove target environments by editing the `connections` object — refresh the page to update the dropdown.

## Usage

1. Write a **SELECT** query (optionally with `TOP`, `JOIN`, `WHERE`, `ORDER BY`).
2. Choose a **target** database from the dropdown.
3. Click **Preview** to see rows from production.
4. Click **Apply** to upsert matching rows into the target.

### Example query

```sql
SELECT TOP (100) *
FROM dbo.FinancialStatement fs
WHERE fs.CompanyId = 12345
ORDER BY fs.Id DESC
```

Apply will copy at most **100 rows** from each table involved in the query.

## Project structure

```
RowSync/
├── app/
│   ├── main.py          # FastAPI app & routes
│   ├── config.py        # Config loader
│   ├── database.py      # pyodbc helpers
│   ├── sql_parser.py    # Query parsing & validation
│   ├── schema.py        # Schema introspection & DDL
│   └── sync.py          # Preview & copy logic
├── static/              # Frontend (HTML, CSS, JS)
│   └── vendor/          # Bundled CodeMirror + fonts (offline)
├── scripts/
│   └── download_vendor_assets.py
├── config.example.json
├── requirements.txt
└── run.py
```

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Web UI |
| `GET` | `/api/schema` | Production schema for autocomplete |
| `GET` | `/api/targets` | Available sync targets |
| `POST` | `/api/preview` | Preview query results |
| `POST` | `/api/apply` | Sync rows (SSE stream) |

## Security notes

- Never commit `config.json` — it contains database credentials.
- The SQL editor only allows **SELECT** statements; the server validates this on every request.
- Run behind a VPN or internal network; this tool is intended for trusted operator use, not public exposure.

## License

MIT
