"""Admin routes — list / add / delete users. Restricted to the admin role."""
from __future__ import annotations

import functools
import logging

from flask import (Blueprint, abort, flash, redirect, render_template, request,
                   session, url_for)

from admin import service

log = logging.getLogger("sde.admin")

admin_bp = Blueprint("admin", __name__, url_prefix="/admin",
                     template_folder="templates")


def admin_required(view):
    """Allow only logged-in users whose role is 'admin'."""
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("auth.login"))
        if session.get("role") != "admin":
            abort(403)
        return view(*args, **kwargs)
    return wrapped


@admin_bp.route("/users")
@admin_required
def users():
    return render_template("admin_users.html", users=service.all_users())


@admin_bp.route("/users/add", methods=["POST"])
@admin_required
def add_user():
    username = request.form.get("username", "")
    password = request.form.get("password", "")
    role = request.form.get("role", "user")
    ok, message = service.add_user(username, password, role)
    flash(message, "success" if ok else "error")
    if ok:
        log.info("Admin %s created user %s (%s)", session.get("user"), username, role)
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/delete/<int:user_id>", methods=["POST"])
@admin_required
def delete_user(user_id: int):
    ok, message = service.remove_user(user_id)
    flash(message, "success" if ok else "error")
    if ok:
        log.info("Admin %s deleted user id=%s", session.get("user"), user_id)
    return redirect(url_for("admin.users"))
