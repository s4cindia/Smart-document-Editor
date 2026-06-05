# Smart Document Editor & Validator

Local Flask app for accessibility/WCAG audit tooling: a Smart Editor plus four
feature tools (Merge Axe Excels, Generate Axe 2 Excel, Generate Excel for
Downloadable, Validate/Generate Delivery Outputs).

## Architecture (modular blueprints)

```
smart-document-editor/
├── app.py                 # app factory; registers blueprints, login guard
├── config.py              # env-driven config (SDE_SECRET_KEY/SDE_DB_PATH/SDE_DATA_DIR)
├── app_helpers.py         # shared web helpers (JSON envelope, uploads, loaders)
├── create_user.py         # ADMIN CLI to add users (no self-registration)
│
├── database/              # SQLite users store
│   ├── db.py              #   connection + schema (init_db)
│   └── models.py          #   user data-access + werkzeug password hashing
│
├── auth/                  # login-only auth
│   ├── routes.py  service.py  forms.py
├── dashboard/             # landing page, editor shell, status, downloads
│   ├── routes.py  services.py
├── smart_editor/          # editor backend (files/data/check/transform/analytics/export/pdf)
│   ├── routes.py  services.py  excel_processor.py  validators.py
├── merge_axe/             # Merge Axe Tool Excels
├── axe_to_excel/          # Generate Axe 2 Excel (+ shared /api/feature/sheets)
├── downloadable_audit/    # Generate Excel for Downloadable
├── vpat_report/           # Validate / Generate Delivery Outputs
│
├── services/              # shared business logic (single source of truth)
├── utils/                 # helpers, file utils
├── templates/             # base.html, dashboard.html, login.html, index.html, ...
└── static/                # css / js / vendored libraries
```

Each feature module has a thin `routes.py` (blueprint) and a `services.py`
facade over the shared `services/` layer, so logic is never duplicated.

## Setup

```bash
pip install -r requirements.txt
python create_user.py --username admin --password "Admin@123" --role admin
python app.py
```

Open http://127.0.0.1:5000 and log in.

### Users (admin only)

There is no signup. Provision accounts from the shell:

```bash
python create_user.py                      # interactive prompts
python create_user.py -u alice -p "Pass12" # one-shot
python create_user.py --list               # list existing users
```

### Configuration (optional environment overrides)

| Variable         | Purpose                          | Default                     |
|------------------|----------------------------------|-----------------------------|
| `SDE_SECRET_KEY` | Flask session signing key        | local dev key               |
| `SDE_DB_PATH`    | SQLite users database file        | `database/users.db`         |
| `SDE_DATA_DIR`   | Data/templates directory          | `data/`                     |

### Optional templates

Drop `Template_WCAG_Audit.xlsx` and `wcag_tags.txt` into `data/templates/` to
make Generate Axe 2 Excel fill the real audit template; without them a
fully-formatted standalone workbook is produced instead.

## Smart Editor export note

On every Excel export, any cell in a **Summary** column longer than 215
characters or containing a line break is highlighted yellow (text is never
altered or truncated; no other column is affected).

## Database backend (SQLite or MySQL)

The user/login store is backend-agnostic (SQLAlchemy). It defaults to a local
SQLite file and requires no setup. To use **MySQL**, set environment variables
before launching `python app.py`:

```
SDE_DB_BACKEND=mysql
SDE_MYSQL_HOST=127.0.0.1
SDE_MYSQL_PORT=3306
SDE_MYSQL_USER=your_user
SDE_MYSQL_PASSWORD=your_password
SDE_MYSQL_DB=smart_document_editor      # create this database first
```

(or set a full `SDE_DB_URL`, e.g. `mysql+pymysql://user:pass@host:3306/db`).

Create the MySQL database once: `CREATE DATABASE smart_document_editor CHARACTER SET utf8mb4;`
The `users` table is created automatically on first run. Provision users with
`python create_user.py` (same env vars in effect). Requires `pip install -r requirements.txt`
(now includes SQLAlchemy and PyMySQL).
