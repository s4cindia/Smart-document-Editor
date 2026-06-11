# Smart Document Editor & Validator

A web-based toolkit for **digital accessibility auditing and document remediation**.

It pairs an interactive spreadsheet/PDF editor with a set of tools for processing
accessibility test reports and producing WCAG conformance documentation (VPATs).
Upload a file, clean and validate the data in your browser, and export polished
Excel, CSV, or PDF outputs.

Built with Flask using a modular, blueprint-based architecture. Authentication is
**login-only** — there is no self-registration; accounts are created by an
administrator.

---

## Table of contents

- [Features](#features)
- [Tech stack](#tech-stack)
- [Requirements](#requirements)
- [Quick start with Docker](#quick-start-with-docker)
- [Running locally without Docker](#running-locally-without-docker)
- [Creating user accounts](#creating-user-accounts)
- [Configuration](#configuration)
- [Project structure](#project-structure)
- [Supported file types](#supported-file-types)
- [Notes & limitations](#notes--limitations)

---

## Features

| Tool | What it does |
|------|--------------|
| **Smart Editor** | Open Excel / CSV / TSV / PDF files into an interactive data grid with inline editing, undo/redo, sorting, filtering, search, validation, duplicate detection, transforms, and analytics. |
| **Merge Reports** | Combine multiple accessibility report workbooks into a single consolidated file. |
| **Report → Excel** | Convert raw accessibility scan output into the standard audit spreadsheet format. |
| **Downloadable Audit** | Generate a tracking sheet that lists downloadable documents (PDF / Word / PowerPoint). |
| **VPAT Report** | Validate a WCAG workbook and export delivery outputs. |
| **VPAT Editor** | A browser-based editor for Voluntary Product Accessibility Templates, covering all Level A / AA / AAA success criteria, with PDF export and draft save/load. |
| **Export** | Download your work as Excel, CSV, or PDF reports. |

---

## Tech stack

- **Backend:** Python, Flask (modular blueprints)
- **Data:** Polars and pandas for fast in-memory tables
- **Spreadsheets:** openpyxl, XlsxWriter
- **PDF:** pdfplumber, PyMuPDF (reading), ReportLab (generation)
- **Database:** SQLAlchemy — works with SQLite (default), MySQL, or PostgreSQL
- **Frontend:** Server-rendered Jinja templates with an AG Grid data table
- **Deployment:** Docker + Docker Compose, served by Gunicorn

---

## Requirements

- To run with Docker: **Docker** and the **Docker Compose** plugin.
- To run locally: **Python 3.10+** and `pip`.

---

## Quick start with Docker

This is the recommended way to run the app. It starts the application and a
PostgreSQL database together.

```bash
# 1. Copy the example environment file and fill in your secrets
cp .env.example .env
#    Edit .env and set:
#      SDE_SECRET_KEY    -> a long random string (e.g. `openssl rand -hex 32`)
#      POSTGRES_PASSWORD -> a strong database password

# 2. Build and start everything in the background
docker compose up -d --build

# 3. Create your first login (see "Creating user accounts" below)
docker compose exec app python create_user.py \
    --username admin --password 'StrongPass!' --role admin
```

Then open **http://localhost:5000** in your browser (or
`http://<server-ip>:5000` from another machine on the same network).

Useful commands:

```bash
docker compose ps             # check status
docker compose logs -f app    # view application logs
docker compose restart app    # restart after a change
docker compose down           # stop everything (your data is kept)
```

---

## Running locally without Docker

Good for development. By default this uses a local SQLite database — no separate
database server required.

```bash
# 1. (Recommended) create and activate a virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create your first login
python create_user.py --username admin --password 'StrongPass!' --role admin

# 4. Start the app
python app.py
```

Open **http://127.0.0.1:5000** in your browser.

---

## Creating user accounts

The app has no sign-up page by design. Accounts are provisioned from the command
line using `create_user.py`.

```bash
# Interactive (prompts for username, password, and role)
python create_user.py

# One-shot
python create_user.py --username alice --password 'Secret123' --role user

# Roles: "admin" or "user"
```

When running under Docker, prefix the command with
`docker compose exec app`.

---

## Configuration

All settings have sensible defaults and can be overridden with environment
variables. The most useful ones:

| Variable | Purpose | Default |
|----------|---------|---------|
| `SDE_SECRET_KEY` | Secret key used to sign login sessions. **Always set this in production.** | a local-only placeholder |
| `SDE_DATA_DIR` | Directory for app data / scratch files | `./data` |
| `SDE_DB_BACKEND` | `sqlite` or `mysql` | `sqlite` |
| `SDE_DB_PATH` | Path to the SQLite file (when using SQLite) | `./database/users.db` |
| `SDE_DB_URL` | Full SQLAlchemy connection URL. Takes priority over everything else — use this for PostgreSQL or MySQL. | _unset_ |

**Example database URLs for `SDE_DB_URL`:**

```bash
# PostgreSQL
postgresql+psycopg2://user:password@host:5432/smart_document_editor

# MySQL
mysql+pymysql://user:password@host:3306/smart_document_editor?charset=utf8mb4
```

The user table is created automatically on first launch.

---

## Project structure

```
Document-Editor-/
├── app.py                 # Application entry point (creates the Flask app)
├── config.py              # Central configuration (env-var overridable)
├── create_user.py         # CLI for creating/managing user accounts
├── requirements.txt       # Python dependencies
├── Dockerfile             # Container image definition
├── docker-compose.yml     # App + PostgreSQL services
│
├── auth/                  # Login / logout
├── dashboard/             # Landing page and editor shell
├── admin/                 # User administration
├── smart_editor/          # Core editor: files, grid, validation, export, PDF
├── merge_axe/             # Merge multiple accessibility report workbooks
├── axe_to_excel/          # Convert scan output to the audit format
├── downloadable_audit/    # Downloadable-documents tracking sheet
├── vpat_report/           # WCAG workbook validation + delivery export
├── vpat_editor/           # Browser-based VPAT editor + PDF export
│
├── services/              # Shared business logic (data store, transforms, etc.)
├── database/              # SQLAlchemy engine, schema, and user data access
├── utils/                 # Helper functions
├── templates/             # Jinja HTML templates
└── static/                # CSS, JavaScript, icons, vendor assets
```

---

## Supported file types

Uploads accept the following formats:

`.xlsx` · `.xls` · `.csv` · `.tsv` · `.pdf`

The default maximum upload size is **200 MB**.

---

## Notes & limitations

- **Single active document.** The editor keeps the currently loaded dataset and
  its undo/redo history in memory and is designed for one active document at a
  time. When deploying, run it as a **single process** (the included Docker setup
  is already configured this way) — running multiple worker processes would split
  that in-memory state across them.
- **Set a real secret key.** In any shared or production environment, always
  provide your own `SDE_SECRET_KEY`.
- **Use HTTPS for anything beyond a trusted local network.** Logins are sent as
  form data, so place the app behind a reverse proxy with TLS if it will be
  reachable outside a private network.
