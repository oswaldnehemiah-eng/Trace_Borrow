"""Small authentication helpers for TraceBorrow."""

from functools import wraps
from flask import flash, redirect, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

MIN_PASSWORD_LENGTH = 6


def hash_password(password):
    return generate_password_hash(password)


def verify_password(password, password_hash):
    return check_password_hash(password_hash, password)


def validate_registration(username, password, confirm_password):
    errors = []
    username = username.strip()
    if not username:
        errors.append("Username is required.")
    elif len(username) < 3:
        errors.append("Username must be at least 3 characters.")
    if not password or len(password) < MIN_PASSWORD_LENGTH:
        errors.append(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if password != confirm_password:
        errors.append("Passwords do not match.")
    return errors


def login_required(view_function):
    @wraps(view_function)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "error")
            return redirect(url_for("login"))
        return view_function(*args, **kwargs)
    return wrapped_view
