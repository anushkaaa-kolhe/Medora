from datetime import datetime, timezone, date
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def utcnow():
    return datetime.now(timezone.utc)


class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(15))
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)

    recipients = db.relationship("Recipient", backref="admin", lazy=True)


class Recipient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey("admin.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(15), unique=True, nullable=False)
    email = db.Column(db.String(120))  # optional
    age = db.Column(db.Integer)
    preferred_language = db.Column(db.String(2), default="en")  # en / hi / mr
    emergency_contact_phone = db.Column(db.String(15))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utcnow)


class OTP(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(15), nullable=False, index=True)
    code_hash = db.Column(db.String(255), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    attempts = db.Column(db.Integer, default=0)
    used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utcnow)

    from datetime import date  # you can also put this at the top with other imports


class Medicine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey("recipient.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    strength = db.Column(db.String(50))            # e.g. "500 mg"
    description = db.Column(db.String(255))        # what it is for
    prescription_note = db.Column(db.String(255))  # doctor's instruction
    with_food = db.Column(db.String(20))           # "before", "after", "any"
    stock_count = db.Column(db.Integer)            # tablets left, for refill alerts
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    recipient = db.relationship("Recipient", backref="medicines")
    schedules = db.relationship("Schedule", backref="medicine", lazy=True)


class Schedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    medicine_id = db.Column(db.Integer, db.ForeignKey("medicine.id"), nullable=False)
    time_of_day = db.Column(db.Time, nullable=False)           # e.g. 08:00
    repeat_type = db.Column(db.String(10), default="daily")    # daily / weekly / once
    days_of_week = db.Column(db.String(20))                    # "0,2,4" (Mon=0), only for weekly
    start_date = db.Column(db.Date, nullable=False, default=date.today)
    end_date = db.Column(db.Date)                              # empty = no end
    is_active = db.Column(db.Boolean, default=True)

    dose_logs = db.relationship("DoseLog", backref="schedule", lazy=True)


class DoseLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey("schedule.id"), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey("recipient.id"), nullable=False, index=True)
    scheduled_for = db.Column(db.DateTime, nullable=False, index=True)
    status = db.Column(db.String(10), default="due")   # due / taken / missed / skipped
    responded_at = db.Column(db.DateTime)
    snooze_count = db.Column(db.Integer, default=0)
    snoozed_until = db.Column(db.DateTime)
    skip_reason = db.Column(db.String(255))
    source = db.Column(db.String(10))                  # button / voice / alexa / system
    created_at = db.Column(db.DateTime, default=utcnow)

    __table_args__ = (
        db.UniqueConstraint("schedule_id", "scheduled_for", name="uq_dose_once"),
    )