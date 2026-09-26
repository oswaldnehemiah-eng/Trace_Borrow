"""TraceBorrow - a small physical lending and return-request tracker."""

from datetime import datetime, timedelta

from flask import Flask, flash, redirect, render_template, request, session, url_for

import database
import queries
from auth import hash_password, login_required, validate_registration, verify_password

app = Flask(__name__)
app.secret_key = "traceborrow-dev-secret-key-change-in-production"
app.permanent_session_lifetime = timedelta(days=30)

# Initialize the persistent SQLite database whenever the app starts.
# This is important when running with Uvicorn or another WSGI/ASGI server,
# because the __main__ block is not executed in that case.
database.init_db()


def current_user():
    user_id = session.get("user_id")
    return queries.get_user_by_id(user_id) if user_id else None


@app.context_processor
def inject_current_user():
    return {"current_user": current_user()}


@app.template_filter("datetime_short")
def datetime_short(value):
    if not value:
        return ""
    try:
        dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%Y-%m-%d %I:%M %p")
    except (TypeError, ValueError):
        return value


@app.route("/")
def index():
    if current_user():
        return redirect(url_for("dashboard"))
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    errors = validate_registration(username, password, confirm_password)
    if not errors and queries.get_user_by_username(username):
        errors.append("That username is already taken.")

    if errors:
        for message in errors:
            flash(message, "error")
        return render_template("register.html", username=username)

    user_id = queries.create_user(username, hash_password(password))
    session["user_id"] = user_id
    session.permanent = True
    flash(f"Welcome to TraceBorrow, {username}!", "success")
    return redirect(url_for("dashboard"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    user = queries.get_user_by_username(username)

    if user is None or not verify_password(password, user["password_hash"]):
        flash("Incorrect username or password.", "error")
        return render_template("login.html", username=username)

    session["user_id"] = user["id"]
    session.permanent = True
    flash(f"Welcome back, {user['username']}!", "success")
    return redirect(url_for("dashboard"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    counts = queries.get_dashboard_counts(user["id"])
    lending_history = queries.get_user_lending_history(user["id"])
    borrowing_history = queries.get_user_borrowing_history(user["id"])
    pending_requests = queries.get_pending_return_requests(user["id"])
    return render_template(
        "dashboard.html",
        counts=counts,
        lending_history=lending_history,
        borrowing_history=borrowing_history,
        pending_requests=pending_requests,
    )


@app.route("/transfer/add", methods=["GET", "POST"])
@login_required
def add_transfer():
    user = current_user()
    people = queries.get_other_users(user["id"])

    if request.method == "GET":
        return render_template("add_transfer.html", people=people)

    borrower_username = request.form.get("borrower_username", "").strip()
    item_description = request.form.get("item_description", "").strip()

    borrower = queries.get_user_by_username(borrower_username)
    if borrower is None:
        flash("Borrower username was not found.", "error")
        return render_template(
            "add_transfer.html",
            people=people,
            borrower_username=borrower_username,
            item_description=item_description,
        )

    success, message = queries.create_transfer(
        user["id"], borrower["id"], item_description
    )
    flash(message, "success" if success else "error")

    if not success:
        return render_template(
            "add_transfer.html",
            people=people,
            borrower_username=borrower_username,
            item_description=item_description,
        )

    return redirect(url_for("dashboard"))


@app.route("/request-return", methods=["GET", "POST"])
@login_required
def request_return():
    if request.method == "GET":
        return render_template("request_return.html")

    item_description = request.form.get("item_description", "").strip()
    success, message = queries.create_return_request(
        current_user()["id"], item_description
    )
    flash(message, "success" if success else "error")
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    database.init_db()
    app.run(debug=True, port=5000)
