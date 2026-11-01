import os
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

from models import db, Admin, Recipient

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///medora.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-me")

db.init_app(app)

with app.app_context():
    db.create_all()


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "admin_id" not in session:
            flash("Please log in first.")
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)
    return wrapped


@app.route("/")
def home():
    return "Medora is running!"


@app.route("/admin/register", methods=["GET", "POST"])
def admin_register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")

        if not name or not email or len(password) < 8:
            flash("Name, email and a password of at least 8 characters are required.")
            return render_template("admin_register.html")

        if Admin.query.filter_by(email=email).first():
            flash("An account with this email already exists.")
            return render_template("admin_register.html")

        admin = Admin(
            name=name,
            email=email,
            phone=phone,
            password_hash=generate_password_hash(password),
        )
        db.session.add(admin)
        db.session.commit()
        flash("Account created. Please log in.")
        return redirect(url_for("admin_login"))

    return render_template("admin_register.html")


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        admin = Admin.query.filter_by(email=email).first()
        if admin and check_password_hash(admin.password_hash, password):
            session.clear()
            session["admin_id"] = admin.id
            return redirect(url_for("admin_dashboard"))

        flash("Invalid email or password.")
    return render_template("admin_login.html")


@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    admin = db.session.get(Admin, session["admin_id"])
    return render_template("admin_dashboard.html", admin=admin)


@app.route("/admin/recipients")
@admin_required
def recipient_list():
    recipients = (
        Recipient.query.filter_by(admin_id=session["admin_id"], is_active=True)
        .order_by(Recipient.name)
        .all()
    )
    return render_template("recipient_list.html", recipients=recipients)


@app.route("/admin/recipients/new", methods=["GET", "POST"])
@admin_required
def recipient_new():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip().lower() or None
        age_raw = request.form.get("age", "").strip()
        language = request.form.get("preferred_language", "en")
        emergency = request.form.get("emergency_contact_phone", "").strip() or None

        if not name or not phone:
            flash("Name and phone number are required.")
            return render_template("recipient_form.html")

        if not phone.isdigit() or len(phone) != 10:
            flash("Enter a valid 10-digit phone number.")
            return render_template("recipient_form.html")

        if language not in ("en", "hi", "mr"):
            language = "en"

        age = int(age_raw) if age_raw.isdigit() else None

        if Recipient.query.filter_by(phone=phone).first():
            flash("A recipient with this phone number already exists.")
            return render_template("recipient_form.html")

        recipient = Recipient(
            admin_id=session["admin_id"],
            name=name,
            phone=phone,
            email=email,
            age=age,
            preferred_language=language,
            emergency_contact_phone=emergency,
        )
        db.session.add(recipient)
        db.session.commit()
        flash(f"{name} was added.")
        return redirect(url_for("recipient_list"))

    return render_template("recipient_form.html")


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)