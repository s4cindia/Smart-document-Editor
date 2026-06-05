"""Authentication module — login only (no self-registration).

Accounts are provisioned by an administrator via ``create_user.py``; the web
app exposes only login and logout.
"""
from auth.routes import auth_bp  # noqa: F401
