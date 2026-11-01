import os
from datetime import datetime, date
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for, session, flash, abort
)
from werkzeug.security import generate_password_hash, check_password_hash

from models import db, Admin, Recipient, Medicine, Schedule

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///medora.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-me")

db.init_app(app)

with app.app_context():
    db.create_all()

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "admin_id" not in session:
            flash("Please log in first.")
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)
    return wrapped


def get_owned_recipient(recipient_id):
    """Return the recipient only if it belongs to the logged-in admin."""
    recipient = Recipient.query.filter_by(
        id=recipient_id, admin_id=session["admin_id"], is_active=True
    ).first()
    if recipient is None:
        abort(404)
    return recipient


def describe_schedule(s):
    """Turn a Schedule row into readable text for the templates."""
    if s.repeat_type == "weekly" and s.days_of_week:
        days = ", ".join(DAY_NAMES[int(d)] for d in s.days_of_week.split(","))
        text = f"Every {days}"
    elif s.repeat_type == "once":
        return f"Only on {s.start_date.strftime('%d %b %Y')}"
    else:
        text = "Every day"
    text += f" from {s.start_date.strftime('%d %b %Y')}"
    if s.end_date:
        text += f" until {s.end_date.strftime('%d %b %Y')}"
    return text


app.add_template_global(describe_schedule)


# ---------- Cover page ----------

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/user/login")
def user_login():
    # Placeholder until we build the OTP login in the next phase
    return "<h1>User login is coming soon.</h1><p><a href='/'>Back</a></p>"


# ---------- Admin account ----------

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


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("home"))


# ---------- Recipients ----------

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


# ---------- Medicines and schedules ----------

@app.route("/admin/recipients/<int:recipient_id>/medicines")
@admin_required
def medicine_list(recipient_id):
    recipient = get_owned_recipient(recipient_id)
    medicines = (
        Medicine.query.filter_by(recipient_id=recipient.id, is_active=True)
        .order_by(Medicine.name)
        .all()
    )
    return render_template("medicine_list.html", recipient=recipient, medicines=medicines)


@app.route("/admin/recipients/<int:recipient_id>/medicines/new", methods=["GET", "POST"])
@admin_required
def medicine_new(recipient_id):
    recipient = get_owned_recipient(recipient_id)
    today = date.today().isoformat()

    def fail(message):
        flash(message)
        return render_template("medicine_form.html", recipient=recipient, today=today)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        strength = request.form.get("strength", "").strip() or None
        description = request.form.get("description", "").strip() or None
        prescription_note = request.form.get("prescription_note", "").strip() or None
        with_food = request.form.get("with_food", "any")
        stock_raw = request.form.get("stock_count", "").strip()
        repeat_type = request.form.get("repeat_type", "daily")

        if not name:
            return fail("Medicine name is required.")
        if with_food not in ("before", "after", "any"):
            with_food = "any"
        if repeat_type not in ("daily", "weekly", "once"):
            repeat_type = "daily"
        stock_count = int(stock_raw) if stock_raw.isdigit() else None

        times = set()
        for raw in request.form.getlist("times"):
            raw = raw.strip()
            if raw:
                try:
                    times.add(datetime.strptime(raw, "%H:%M").time())
                except ValueError:
                    return fail("One of the dose times is invalid.")
        if not times:
            return fail("Add at least one dose time.")

        try:
            start_date = date.fromisoformat(request.form.get("start_date", ""))
        except ValueError:
            start_date = date.today()

        end_date = None
        end_raw = request.form.get("end_date", "").strip()
        if end_raw and repeat_type != "once":
            try:
                end_date = date.fromisoformat(end_raw)
            except ValueError:
                return fail("The end date is invalid.")
            if end_date < start_date:
                return fail("The end date cannot be before the start date.")

        days_of_week = None
        if repeat_type == "weekly":
            valid_days = {str(i) for i in range(7)}
            chosen = sorted({d for d in request.form.getlist("days") if d in valid_days})
            if not chosen:
                return fail("Choose at least one day of the week.")
            days_of_week = ",".join(chosen)

        medicine = Medicine(
            recipient_id=recipient.id,
            name=name,
            strength=strength,
            description=description,
            prescription_note=prescription_note,
            with_food=with_food,
            stock_count=stock_count,
        )
        db.session.add(medicine)
        db.session.flush()

        for t in sorted(times):
            db.session.add(
                Schedule(
                    medicine_id=medicine.id,
                    time_of_day=t,
                    repeat_type=repeat_type,
                    days_of_week=days_of_week,
                    start_date=start_date,
                    end_date=end_date,
                )
            )
        db.session.commit()
        flash(f"{name} was added with {len(times)} dose time(s) per day.")
        return redirect(url_for("medicine_list", recipient_id=recipient.id))

    return render_template("medicine_form.html", recipient=recipient, today=today)


@app.route(
    "/admin/recipients/<int:recipient_id>/medicines/<int:medicine_id>/stop",
    methods=["POST"],
)
@admin_required
def medicine_stop(recipient_id, medicine_id):
    recipient = get_owned_recipient(recipient_id)
    medicine = Medicine.query.filter_by(id=medicine_id, recipient_id=recipient.id).first()
    if medicine is None:
        abort(404)
    medicine.is_active = False
    for s in medicine.schedules:
        s.is_active = False
    db.session.commit()
    flash(f"{medicine.name} was stopped.")
    return redirect(url_for("medicine_list", recipient_id=recipient.id))

if __name__ == "__main__":
    app.run(debug=True, port=5001)