"""Authentication routes — login + logout only."""
from __future__ import annotations

import logging

from flask import (Blueprint, redirect, render_template, request, session,
                   url_for)

from auth.forms import validate_login
from auth.service import verify_credentials

log = logging.getLogger("sde.auth")

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        valid, message = validate_login(username, password)
        if not valid:
            return render_template("login.html", error=message, username=username)

        ok_, result = verify_credentials(username, password)
        if ok_:
            session["user"] = result
            from database.models import get_user
            u = get_user(result)
            session["role"] = u.role if u else "user"
            return redirect(url_for("main.dashboard"))
        return render_template("login.html", error=result, username=username)

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    session.pop("user", None)
    session.pop("role", None)
    return redirect(url_for("auth.login"))
