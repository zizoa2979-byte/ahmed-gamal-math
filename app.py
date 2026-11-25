import json
import os
import re
import secrets
from datetime import datetime, timedelta
from urllib.parse import quote, urlparse, parse_qs

from flask import (
    Flask,
    render_template,
    render_template_string,
    request,
    redirect,
    url_for,
    flash,
    session,
    send_from_directory,
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "ahmed-gamal-math-platform-secret-2026")

raw_db_url = os.environ.get("DATABASE_URL", "").strip()
if raw_db_url.startswith("postgres://"):
    raw_db_url = raw_db_url.replace("postgres://", "postgresql://", 1)

if raw_db_url:
    app.config["SQLALCHEMY_DATABASE_URI"] = raw_db_url
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }
else:
    os.makedirs(app.instance_path, exist_ok=True)
    sqlite_path = os.path.join(app.instance_path, "math_platform.db")
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{sqlite_path}"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
default_upload_dir = (
    "/tmp/uploads" if os.environ.get("VERCEL") else os.path.join(BASE_DIR, "static", "uploads")
)
app.config["UPLOAD_FOLDER"] = os.environ.get("UPLOAD_FOLDER", default_upload_dir)
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

ALLOWED_EXTENSIONS = {
    "png", "jpg", "jpeg", "webp", "gif",
    "mp4", "mov", "avi", "mkv", "webm",
    "pdf", "doc", "docx", "ppt", "pptx", "zip", "rar",
}

db = SQLAlchemy(app)

GRADES = [
    "الأول الإعدادي",
    "الثاني الإعدادي",
    "الثالث الإعدادي",
    "الأول الثانوي",
    "الثاني الثانوي",
    "الثالث الثانوي",
]

CONTENT_SECTIONS = [
    ("explanation", "الشرح"),
    ("training", "التطبيق التفاعلي"),
    ("homework", "تسليم الواجب"),
    ("exam_section", "الامتحان"),
]

DEVELOPER_CREDIT = "تم التطوير بواسطة م/ عبد العزيز أمير"
DEV_UNLOCK_TOKEN = os.environ.get("DEV_UNLOCK_TOKEN", "zizo-dev-2026")


def normalize_grade_label(raw_grade):
    g = (raw_grade or "").strip()
    if not g:
        return ""
    if g in ("ALL_GRADES", *GRADES):
        return g

    compact = re.sub(r"\s+", " ", g)
    mapping = {
        "أولى إعدادي": "الأول الإعدادي",
        "اولى اعدادي": "الأول الإعدادي",
        "اول اعدادي": "الأول الإعدادي",
        "الأول اعدادي": "الأول الإعدادي",
        "الصف الأول الإعدادي": "الأول الإعدادي",
        "الصف الاول الاعدادي": "الأول الإعدادي",
        "1 إعدادي": "الأول الإعدادي",
        "1 اعدادي": "الأول الإعدادي",
        "ثانية إعدادي": "الثاني الإعدادي",
        "تانية اعدادي": "الثاني الإعدادي",
        "ثاني اعدادي": "الثاني الإعدادي",
        "الثاني اعدادي": "الثاني الإعدادي",
        "الصف الثاني الإعدادي": "الثاني الإعدادي",
        "الصف الثاني الاعدادي": "الثاني الإعدادي",
        "2 إعدادي": "الثاني الإعدادي",
        "2 اعدادي": "الثاني الإعدادي",
        "ثالثة إعدادي": "الثالث الإعدادي",
        "تالتة اعدادي": "الثالث الإعدادي",
        "ثالث اعدادي": "الثالث الإعدادي",
        "الثالث اعدادي": "الثالث الإعدادي",
        "الصف الثالث الإعدادي": "الثالث الإعدادي",
        "الصف الثالث الاعدادي": "الثالث الإعدادي",
        "3 إعدادي": "الثالث الإعدادي",
        "3 اعدادي": "الثالث الإعدادي",
        "أولى ثانوي": "الأول الثانوي",
        "اولى ثانوي": "الأول الثانوي",
        "اول ثانوي": "الأول الثانوي",
        "الأول ثانوي": "الأول الثانوي",
        "الصف الأول الثانوي": "الأول الثانوي",
        "الصف الاول الثانوي": "الأول الثانوي",
        "1 ثانوي": "الأول الثانوي",
        "ثانية ثانوي": "الثاني الثانوي",
        "تانية ثانوي": "الثاني الثانوي",
        "ثاني ثانوي": "الثاني الثانوي",
        "الثاني ثانوي": "الثاني الثانوي",
        "الصف الثاني الثانوي": "الثاني الثانوي",
        "الصف الثاني الثانوي": "الثاني الثانوي",
        "2 ثانوي": "الثاني الثانوي",
        "ثالثة ثانوي": "الثالث الثانوي",
        "تالتة ثانوي": "الثالث الثانوي",
        "ثالث ثانوي": "الثالث الثانوي",
        "الثالث ثانوي": "الثالث الثانوي",
        "الصف الثالث الثانوي": "الثالث الثانوي",
        "الصف الثالث الثانوي": "الثالث الثانوي",
        "3 ثانوي": "الثالث الثانوي",
    }
    return mapping.get(compact, compact)


# ==================== النماذج (Models) ====================
class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=True)
    full_name = db.Column(db.String(160), nullable=False)
    phone = db.Column(db.String(40), unique=True, nullable=True)
    parent_phone = db.Column(db.String(40), nullable=True)
    governorate = db.Column(db.String(80), default="الدقهلية")
    grade = db.Column(db.String(80), nullable=True)
    role = db.Column(db.String(20), default="student")
    is_active = db.Column(db.Boolean, default=False)
    onboarding_done = db.Column(db.Boolean, default=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    exam_results = db.relationship("ExamResult", backref="student", lazy=True, cascade="all, delete-orphan")


class PlatformSettings(db.Model):
    __tablename__ = "platform_settings"
    id = db.Column(db.Integer, primary_key=True)
    platform_name = db.Column(db.String(200), default="الرياضة أسهل وأوضح مع مستر أحمد جمال")
    teacher_name = db.Column(db.String(120), default="مستر / أحمد جمال")
    teacher_bio = db.Column(
        db.Text,
        default="منصة متكاملة للرياضيات والهندسة والجبر وحساب المثلثات — شرح مبسط ومنهجي، تدريب مكثف على أفكار الامتحانات، ومتابعة مستمرة للمستوى.",
    )
    teacher_image = db.Column(db.String(300), nullable=True)
    whatsapp_number = db.Column(db.String(50), default="201000000000")
    vodafone_cash_number = db.Column(db.String(50), default="01000000000")
    facebook_url = db.Column(db.String(300), nullable=True)
    instagram_url = db.Column(db.String(300), nullable=True)
    tiktok_url = db.Column(db.String(300), nullable=True)
    youtube_url = db.Column(db.String(300), nullable=True)
    pass_percentage_required = db.Column(db.Float, default=50.0)
    is_maintenance = db.Column(db.Boolean, default=False)
    maintenance_message = db.Column(
        db.String(300),
        default="جاري تنفيذ تحديثات وتطويرات شاملة على المنصة، سنعود للعمل بعد الانتهاء من التطوير.",
    )


class Center(db.Model):
    __tablename__ = "centers"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    address = db.Column(db.String(250), nullable=True)
    schedule_notes = db.Column(db.String(250), nullable=True)


class Announcement(db.Model):
    __tablename__ = "announcements"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class WeekPackage(db.Model):
    __tablename__ = "week_packages"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    image_path = db.Column(db.String(400), nullable=True)
    grade = db.Column(db.String(80), nullable=False)
    order_num = db.Column(db.Integer, default=1)
    price = db.Column(db.Float, default=0.0)
    is_free = db.Column(db.Boolean, default=False)
    is_published = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    contents = db.relationship("CourseContent", backref="week", lazy=True, cascade="all, delete-orphan")


class CourseContent(db.Model):
    __tablename__ = "course_contents"
    id = db.Column(db.Integer, primary_key=True)
    week_id = db.Column(db.Integer, db.ForeignKey("week_packages.id"), nullable=False)
    lecture_title = db.Column(db.String(200), default="المحاضرة الأولى")
    title = db.Column(db.String(200), nullable=False)
    section_key = db.Column(db.String(50), default="explanation")
    content_type = db.Column(db.String(50), default="video_link")
    source_path = db.Column(db.String(400), nullable=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("exams.id"), nullable=True)
    required_exam_id = db.Column(db.Integer, nullable=True)
    duration_or_notes = db.Column(db.String(300), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class WatchedContent(db.Model):
    __tablename__ = "watched_contents"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    content_id = db.Column(db.Integer, db.ForeignKey("course_contents.id"), nullable=False)
    watched_at = db.Column(db.DateTime, default=datetime.utcnow)


class WeekSubscription(db.Model):
    __tablename__ = "week_subscriptions"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    week_id = db.Column(db.Integer, db.ForeignKey("week_packages.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class SubscriptionRequest(db.Model):
    __tablename__ = "subscription_requests"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    week_id = db.Column(db.Integer, db.ForeignKey("week_packages.id"), nullable=True)
    subscription_type = db.Column(db.String(60), default="package")
    payment_method = db.Column(db.String(60), default="vodafone_cash")
    sender_phone = db.Column(db.String(50), nullable=False)
    receiver_phone = db.Column(db.String(50), nullable=False)
    screenshot_path = db.Column(db.String(400), nullable=True)
    notes = db.Column(db.String(250), nullable=True)
    status = db.Column(db.String(25), default="pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    student = db.relationship("User", foreign_keys=[user_id], lazy=True)
    week = db.relationship("WeekPackage", foreign_keys=[week_id], lazy=True)


class ActivationCode(db.Model):
    __tablename__ = "activation_codes"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(60), unique=True, nullable=False)
    code_type = db.Column(db.String(30), default="package")
    grade = db.Column(db.String(80), nullable=False)
    week_id = db.Column(db.Integer, db.ForeignKey("week_packages.id"), nullable=True)
    is_used = db.Column(db.Boolean, default=False)
    used_by = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Exam(db.Model):
    __tablename__ = "exams"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    grade = db.Column(db.String(80), nullable=False)
    duration_minutes = db.Column(db.Integer, default=20)
    grading_mode = db.Column(db.String(20), default="instant")
    grading_delay_hours = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    questions = db.relationship("ExamQuestion", backref="exam", lazy=True, cascade="all, delete-orphan")


class ExamQuestion(db.Model):
    __tablename__ = "exam_questions"
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("exams.id"), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.String(300), nullable=False)
    option_b = db.Column(db.String(300), nullable=False)
    option_c = db.Column(db.String(300), nullable=False)
    option_d = db.Column(db.String(300), nullable=False)
    correct_option = db.Column(db.String(5), nullable=False)


class ExamAttempt(db.Model):
    __tablename__ = "exam_attempts"
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("exams.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    attempt_number = db.Column(db.Integer, default=1)
    serial_code = db.Column(db.String(40), nullable=False)
    status = db.Column(db.String(20), default="in_progress")
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    submitted_at = db.Column(db.DateTime, nullable=True)
    answers_json = db.Column(db.Text, default="{}")


class ExamResult(db.Model):
    __tablename__ = "exam_results"
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("exams.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    score = db.Column(db.Integer, default=0)
    total_questions = db.Column(db.Integer, default=0)
    percentage = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ==================== تهيئة قاعدة البيانات ودمج البيانات القديمة بأمان ====================
_db_ready = False


def _sync_legacy_user_table(inspector):
    if "user" not in inspector.get_table_names() or "users" not in inspector.get_table_names():
        return
    try:
        legacy_cols = {c["name"] for c in inspector.get_columns("user")}
        rows = db.session.execute(text('SELECT * FROM "user"')).mappings().all()
        for r in rows:
            uname = (str(r.get("username") or "").strip() or None) if "username" in legacy_cols else None
            phone_val = (str(r.get("phone") or "").strip() or None) if "phone" in legacy_cols else None
            full_name = (str(r.get("full_name") or r.get("name") or uname or phone_val or "مستخدم")).strip()
            role_val = (str(r.get("role") or "student").strip().lower()) if "role" in legacy_cols else "student"
            if role_val not in ("admin", "student"):
                role_val = "student"
            pwd_val = (
                str(r.get("password_hash") or r.get("password") or "").strip()
                if ("password_hash" in legacy_cols or "password" in legacy_cols)
                else ""
            )
            if not pwd_val:
                pwd_val = generate_password_hash("admin123" if role_val == "admin" else "123456")

            exists = None
            if uname:
                exists = User.query.filter_by(username=uname).first()
            if not exists and phone_val:
                exists = User.query.filter_by(phone=phone_val).first()

            if not exists:
                db.session.add(
                    User(
                        username=uname,
                        full_name=full_name,
                        phone=phone_val,
                        parent_phone=str(r.get("parent_phone") or "").strip() or None if "parent_phone" in legacy_cols else None,
                        governorate=str(r.get("governorate") or "الدقهلية").strip() if "governorate" in legacy_cols else "الدقهلية",
                        grade=str(r.get("grade") or "").strip() or None if "grade" in legacy_cols else None,
                        role=role_val,
                        is_active=bool(r.get("is_active")) if "is_active" in legacy_cols and r.get("is_active") is not None else True,
                        onboarding_done=True,
                        password_hash=pwd_val,
                    )
                )
        db.session.commit()
    except Exception:
        db.session.rollback()


def init_db():
    global _db_ready
    if _db_ready:
        return
    try:
        db.create_all()
        inspector = inspect(db.engine)
        tables = set(inspector.get_table_names())

        def ensure_columns(table_name, col_defs):
            if table_name not in tables:
                return
            existing = {c["name"] for c in inspector.get_columns(table_name)}
            for col_name, col_sql in col_defs:
                if col_name not in existing:
                    db.session.execute(
                        text(f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {col_name} {col_sql}")
                    )

        ensure_columns("users", [
            ("username", "VARCHAR(100)"),
            ("full_name", "VARCHAR(160)"),
            ("phone", "VARCHAR(40)"),
            ("parent_phone", "VARCHAR(40)"),
            ("governorate", "VARCHAR(80) DEFAULT 'الدقهلية'"),
            ("grade", "VARCHAR(80)"),
            ("role", "VARCHAR(20) DEFAULT 'student'"),
            ("is_active", "BOOLEAN DEFAULT TRUE"),
            ("onboarding_done", "BOOLEAN DEFAULT TRUE"),
            ("password_hash", "VARCHAR(255)"),
            ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ])

        ensure_columns("platform_settings", [
            ("platform_name", "VARCHAR(200) DEFAULT 'الرياضة أسهل وأوضح مع مستر أحمد جمال'"),
            ("teacher_name", "VARCHAR(120) DEFAULT 'مستر / أحمد جمال'"),
            ("teacher_bio", "TEXT"),
            ("teacher_image", "VARCHAR(300)"),
            ("whatsapp_number", "VARCHAR(50) DEFAULT '201000000000'"),
            ("vodafone_cash_number", "VARCHAR(50) DEFAULT '01000000000'"),
            ("facebook_url", "VARCHAR(300)"),
            ("instagram_url", "VARCHAR(300)"),
            ("tiktok_url", "VARCHAR(300)"),
            ("youtube_url", "VARCHAR(300)"),
            ("pass_percentage_required", "FLOAT DEFAULT 50.0"),
            ("is_maintenance", "BOOLEAN DEFAULT FALSE"),
            ("maintenance_message", "VARCHAR(300) DEFAULT 'جاري تنفيذ تحديثات وتطويرات شاملة على المنصة، سنعود للعمل بعد الانتهاء من التطوير.'"),
        ])

        ensure_columns("week_packages", [
            ("description", "TEXT"),
            ("image_path", "VARCHAR(400)"),
            ("grade", "VARCHAR(80)"),
            ("order_num", "INTEGER DEFAULT 1"),
            ("price", "FLOAT DEFAULT 0.0"),
            ("is_free", "BOOLEAN DEFAULT FALSE"),
            ("is_published", "BOOLEAN DEFAULT TRUE"),
            ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ])

        ensure_columns("course_contents", [
            ("lecture_title", "VARCHAR(200) DEFAULT 'المحاضرة الأولى'"),
            ("section_key", "VARCHAR(50) DEFAULT 'explanation'"),
            ("content_type", "VARCHAR(50) DEFAULT 'video_link'"),
            ("source_path", "VARCHAR(400)"),
            ("exam_id", "INTEGER"),
            ("required_exam_id", "INTEGER"),
            ("duration_or_notes", "VARCHAR(300)"),
            ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ])

        ensure_columns("exams", [
            ("grade", "VARCHAR(80)"),
            ("duration_minutes", "INTEGER DEFAULT 20"),
            ("grading_mode", "VARCHAR(20) DEFAULT 'instant'"),
            ("grading_delay_hours", "FLOAT DEFAULT 0.0"),
            ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ])

        ensure_columns("activation_codes", [
            ("code_type", "VARCHAR(30) DEFAULT 'package'"),
            ("grade", "VARCHAR(80)"),
            ("week_id", "INTEGER"),
            ("is_used", "BOOLEAN DEFAULT FALSE"),
            ("used_by", "INTEGER"),
            ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ])

        ensure_columns("subscription_requests", [
            ("user_id", "INTEGER"),
            ("week_id", "INTEGER"),
            ("subscription_type", "VARCHAR(60) DEFAULT 'package'"),
            ("payment_method", "VARCHAR(60) DEFAULT 'vodafone_cash'"),
            ("sender_phone", "VARCHAR(50)"),
            ("receiver_phone", "VARCHAR(50)"),
            ("screenshot_path", "VARCHAR(400)"),
            ("notes", "VARCHAR(250)"),
            ("status", "VARCHAR(25) DEFAULT 'pending'"),
            ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ])

        db.session.commit()
        _sync_legacy_user_table(inspect(db.engine))

        all_u = User.query.all()
        for u in all_u:
            if not u.full_name:
                u.full_name = u.username or u.phone or f"مستخدم {u.id}"
            if not u.password_hash:
                u.password_hash = generate_password_hash("admin123" if u.role == "admin" else "123456")
            if u.onboarding_done is None:
                u.onboarding_done = True
            if u.is_active is None:
                u.is_active = True

        if not PlatformSettings.query.first():
            db.session.add(PlatformSettings())

        if not User.query.filter_by(role="admin").first():
            admin_user = os.environ.get("ADMIN_USERNAME", "admin")
            admin_pass = os.environ.get("ADMIN_PASSWORD", "admin123")
            db.session.add(
                User(
                    username=admin_user,
                    full_name="مستر / أحمد جمال",
                    phone="01000000000",
                    role="admin",
                    is_active=True,
                    onboarding_done=True,
                    password_hash=generate_password_hash(admin_pass),
                )
            )

        db.session.commit()
        _db_ready = True
    except Exception:
        db.session.rollback()


def is_developer_session():
    return bool(session.get("dev_maintenance_owner") is True)


@app.before_request
def ensure_initialized_and_maintenance_guard():
    init_db()

    allowed_always_prefixes = ("/static", "/uploads", "/admin/dev-access/")
    if request.path.startswith(allowed_always_prefixes):
        return None

    try:
        s = PlatformSettings.query.first()
    except Exception:
        db.session.rollback()
        s = None

    if s and bool(getattr(s, "is_maintenance", False)):
        if is_developer_session():
            return None

        if request.path.startswith("/auth"):
            return None

        msg = (
            s.maintenance_message
            or "جاري تنفيذ تحديثات وتطويرات شاملة على المنصة، سنعود للعمل بعد الانتهاء من التطوير."
        )
        teacher_name = (
            s.teacher_name
            if s.teacher_name and s.teacher_name != "None"
            else "مستر / أحمد جمال"
        )
        return (
            render_template_string(
                """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>جاري تحديث المنصة - {{ teacher_name }}</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.rtl.min.css" rel="stylesheet" />
  <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css" rel="stylesheet" />
  <style>
    body {
      background: #06111f;
      background-image:
        linear-gradient(rgba(14, 165, 233, 0.04) 1px, transparent 1px),
        linear-gradient(90deg, rgba(14, 165, 233, 0.04) 1px, transparent 1px);
      background-size: 28px 28px;
      color: #f8fafc;
      font-family: system-ui, -apple-system, "Segoe UI", Tahoma, sans-serif;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px;
    }
    .maint-card {
      background: #0c1f38;
      border: 1px solid rgba(56, 189, 248, 0.28);
      border-radius: 24px;
      padding: 36px 28px;
      max-width: 520px;
      width: 100%;
      text-align: center;
      box-shadow: 0 24px 60px rgba(0, 0, 0, 0.55);
    }
    .gear-badge {
      width: 84px;
      height: 84px;
      border-radius: 50%;
      background: rgba(14, 165, 233, 0.14);
      color: #38bdf8;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      font-size: 2.6rem;
      margin-bottom: 18px;
      border: 1px solid rgba(56, 189, 248, 0.35);
    }
    .dev-badge {
      margin-top: 22px;
      padding: 8px 16px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.04);
      border: 1px solid rgba(159, 179, 200, 0.18);
      color: #9fb3c8;
      font-size: 0.82rem;
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }
  </style>
</head>
<body>
  <div class="maint-card">
    <div class="gear-badge"><i class="bi bi-tools"></i></div>
    <span class="badge bg-warning text-dark rounded-pill px-3 py-2 mb-3 fw-bold">
      <i class="bi bi-arrow-repeat me-1"></i> المنصة في وضع التحديث والصيانة
    </span>
    <h1 class="h4 fw-bold text-white mb-2">منصة {{ teacher_name }}</h1>
    <p class="text-info fw-semibold mb-3">{{ msg }}</p>
    <p class="small text-secondary mb-4">
      نعمل حالياً على تطوير المنصة ورفع تحديثات جديدة، ولن يتاح الدخول أو التسجيل حتى انتهاء المطور من التحديث وإعادة تشغيل المنصة.
    </p>
    <a href="/" class="btn btn-outline-info rounded-pill px-4 fw-bold">
      <i class="bi bi-arrow-clockwise me-1"></i> تحديث الصفحة
    </a>
    <div>
      <div class="dev-badge">
        <i class="bi bi-code-slash text-info"></i>
        <span>{{ developer_credit }}</span>
      </div>
    </div>
  </div>
</body>
</html>
                """,
                msg=msg,
                teacher_name=teacher_name,
                developer_credit=DEVELOPER_CREDIT,
            ),
            503,
        )

    return None


# ==================== دوال مساعدة ====================
def get_current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    try:
        return db.session.get(User, uid)
    except Exception:
        db.session.rollback()
        return None


def get_settings():
    try:
        s = PlatformSettings.query.first()
        if not s:
            s = PlatformSettings()
            db.session.add(s)
            db.session.commit()
        return s
    except Exception:
        db.session.rollback()
        return PlatformSettings()


def clean_wa_phone(phone):
    digits = re.sub(r"\D", "", phone or "")
    if not digits:
        return "201000000000"
    if digits.startswith("00"):
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        digits = "2" + digits
    return digits


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_uploaded_file(file_storage):
    if not file_storage or not file_storage.filename:
        return None
    if not allowed_file(file_storage.filename):
        return None
    try:
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
        safe_name = secure_filename(file_storage.filename) or "file"
        unique_name = f"{secrets.token_hex(6)}_{safe_name}"
        full_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_name)
        file_storage.save(full_path)

        upload_root = os.path.abspath(app.config["UPLOAD_FOLDER"])
        static_root = os.path.abspath(os.path.join(BASE_DIR, "static"))
        if upload_root.startswith(static_root):
            rel = os.path.relpath(full_path, static_root).replace("\\", "/")
            return url_for("static", filename=rel)
        return url_for("uploaded_media", filename=unique_name)
    except Exception:
        return None


def format_embed_url(url):
    if not url:
        return ""
    u = url.strip()
    parsed = urlparse(u)
    host = (parsed.netloc or "").lower()
    if "youtu.be" in host:
        vid = parsed.path.lstrip("/").split("/")[0]
        if vid:
            return f"https://www.youtube.com/embed/{vid}"
    if "youtube.com" in host:
        qs = parse_qs(parsed.query)
        if "v" in qs and qs["v"]:
            return f"https://www.youtube.com/embed/{qs['v'][0]}"
        if "/embed/" in parsed.path:
            return u
    return u


def weeks_for_grade(grade):
    try:
        norm_g = normalize_grade_label(grade)
        all_pub = (
            WeekPackage.query.filter_by(is_published=True)
            .order_by(WeekPackage.order_num.asc(), WeekPackage.id.asc())
            .all()
        )
        if not norm_g:
            return all_pub
        return [
            w for w in all_pub
            if normalize_grade_label(w.grade) in (norm_g, "ALL_GRADES")
        ]
    except Exception:
        db.session.rollback()
        return []


def exams_for_grade(grade):
    try:
        norm_g = normalize_grade_label(grade)
        all_ex = Exam.query.order_by(Exam.id.desc()).all()
        if not norm_g:
            return all_ex
        return [
            ex for ex in all_ex
            if normalize_grade_label(ex.grade) in (norm_g, "ALL_GRADES")
        ]
    except Exception:
        db.session.rollback()
        return []


def compute_student_level(user):
    try:
        grade_weeks = weeks_for_grade(user.grade)
        video_items = []
        for w in grade_weeks:
            for c in getattr(w, "contents", []) or []:
                if c.content_type in ("video_link", "video_upload"):
                    video_items.append(c.id)

        watched_ids = {
            wc.content_id for wc in WatchedContent.query.filter_by(user_id=user.id).all()
        }
        watched_count = sum(1 for cid in video_items if cid in watched_ids)
        total_videos = len(video_items)
        watch_pct = (watched_count / total_videos * 100.0) if total_videos > 0 else 0.0

        grade_exams = exams_for_grade(user.grade)
        total_exams = len(grade_exams)
        results = ExamResult.query.filter_by(user_id=user.id).order_by(ExamResult.id.desc()).all()
        best_by_exam = {}
        for r in results:
            pct_val = float(r.percentage or 0.0)
            if r.exam_id not in best_by_exam or pct_val > best_by_exam[r.exam_id]:
                best_by_exam[r.exam_id] = pct_val

        solved_exams = len(best_by_exam)
        avg_score = round(sum(best_by_exam.values()) / solved_exams, 1) if solved_exams > 0 else 0.0
        exam_pct = (sum(best_by_exam.values()) / total_exams) if total_exams > 0 else 0.0

        if total_videos > 0 and total_exams > 0:
            overall = round((watch_pct * 0.4) + (exam_pct * 0.6), 1)
        elif total_videos > 0:
            overall = round(watch_pct, 1)
        elif total_exams > 0:
            overall = round(exam_pct, 1)
        else:
            overall = 0.0

        if overall >= 85:
            label, badge_class = "ممتاز جداً", "bg-success"
        elif overall >= 65:
            label, badge_class = "جيد جداً", "bg-info text-dark"
        elif overall >= 50:
            label, badge_class = "متوسط", "bg-primary"
        elif watched_count > 0 or solved_exams > 0:
            label, badge_class = "يحتاج متابعة", "bg-warning text-dark"
        else:
            label, badge_class = "بداية جديدة", "bg-secondary"

        return {
            "watched_count": watched_count,
            "total_videos": total_videos,
            "solved_exams": solved_exams,
            "total_exams": total_exams,
            "avg_score": avg_score,
            "overall": overall,
            "label": label,
            "badge_class": badge_class,
        }
    except Exception:
        db.session.rollback()
        return {
            "watched_count": 0,
            "total_videos": 0,
            "solved_exams": 0,
            "total_exams": 0,
            "avg_score": 0.0,
            "overall": 0.0,
            "label": "بداية جديدة",
            "badge_class": "bg-secondary",
        }


def parse_answers_json(raw_json):
    try:
        data = json.loads(raw_json or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def format_duration_label(seconds):
    sec = max(0, int(seconds or 0))
    mins, rem = divmod(sec, 60)
    hrs, mins = divmod(mins, 60)
    if hrs > 0:
        return f"{hrs} س {mins} د"
    return f"{mins} د {rem} ث"


def evaluate_attempt(exam, attempt):
    questions = ExamQuestion.query.filter_by(exam_id=exam.id).order_by(ExamQuestion.id.asc()).all()
    answers = parse_answers_json(attempt.answers_json)
    total_questions = len(questions)
    total_marks = total_questions

    score = 0
    solved_count = 0
    details = []

    for idx, q in enumerate(questions, start=1):
        opts = {
            "A": q.option_a,
            "B": q.option_b,
            "C": q.option_c,
            "D": q.option_d,
        }
        chosen = answers.get(str(q.id))
        if chosen in opts:
            solved_count += 1
        is_correct = chosen == q.correct_option
        if is_correct:
            score += 1
        details.append(
            {
                "number": idx,
                "text": q.question_text,
                "student_option": chosen,
                "student_label": opts.get(chosen, "لم يُجب"),
                "correct_option": q.correct_option,
                "correct_label": opts.get(q.correct_option, ""),
                "is_correct": is_correct,
            }
        )

    now = datetime.utcnow()
    duration_sec = int((exam.duration_minutes or 20) * 60)
    elapsed_in_progress = int((now - (attempt.started_at or now)).total_seconds())
    remaining_seconds = max(0, duration_sec - elapsed_in_progress)

    end_ref = attempt.submitted_at or now
    spent_sec = max(0, int((end_ref - (attempt.started_at or end_ref)).total_seconds()))
    time_spent_label = format_duration_label(spent_sec)

    result_ready = True
    available_at_label = ""
    if exam.grading_mode == "delayed" and (exam.grading_delay_hours or 0) > 0 and attempt.submitted_at:
        ready_at = attempt.submitted_at + timedelta(hours=float(exam.grading_delay_hours))
        available_at_label = ready_at.strftime("%Y-%m-%d %H:%M UTC")
        result_ready = now >= ready_at

    return {
        "score": score,
        "total_marks": total_marks,
        "total_questions": total_questions,
        "solved_count": solved_count,
        "remaining_seconds": remaining_seconds,
        "time_spent_label": time_spent_label,
        "result_ready": result_ready,
        "available_at_label": available_at_label,
        "details": details,
    }


def _build_lecture_groups(week, user_id, pass_pct_required):
    passed_exam_ids = set()
    try:
        for r in ExamResult.query.filter_by(user_id=user_id).all():
            if float(r.percentage or 0.0) >= float(pass_pct_required or 50.0):
                passed_exam_ids.add(r.exam_id)
    except Exception:
        db.session.rollback()

    items = sorted(getattr(week, "contents", []) or [], key=lambda x: x.id)
    lectures_order = []
    lectures_map = {}

    for c in items:
        lec_name = (c.lecture_title or "المحاضرة الأولى").strip() or "المحاضرة الأولى"
        if lec_name not in lectures_map:
            lectures_order.append(lec_name)
            lectures_map[lec_name] = {
                "title": lec_name,
                "sections": {
                    "explanation": [],
                    "training": [],
                    "homework": [],
                    "exam_section": [],
                },
            }
        sec = c.section_key if c.section_key in lectures_map[lec_name]["sections"] else "explanation"
        is_locked = bool(c.required_exam_id and c.required_exam_id not in passed_exam_ids)
        lectures_map[lec_name]["sections"][sec].append({
            "content": c,
            "is_locked": is_locked,
            "lock_msg": "هذا المحتوى مغلق حتى النجاح في الاختبار السابق!",
        })

    return [lectures_map[name] for name in lectures_order]


@app.context_processor
def inject_globals():
    return {
        "settings": get_settings(),
        "current_user": get_current_user(),
        "grades": GRADES,
        "clean_wa_phone": clean_wa_phone,
        "quote": quote,
        "developer_credit": DEVELOPER_CREDIT,
        "is_developer_session": is_developer_session(),
    }


# ==================== المسارات العامة والمصادقة ====================
@app.route("/uploads/<path:filename>")
def uploaded_media(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/")
def index():
    try:
        centers = Center.query.order_by(Center.id.asc()).all()
        announcements = Announcement.query.order_by(Announcement.id.desc()).all()
    except Exception:
        db.session.rollback()
        centers, announcements = [], []
    return render_template("index.html", centers=centers, announcements=announcements)


def _verify_password_safe(stored_hash, plain_password):
    if not stored_hash:
        return False
    try:
        return check_password_hash(stored_hash, plain_password)
    except Exception:
        return stored_hash == plain_password


@app.route("/auth", methods=["GET", "POST"])
def auth():
    mode = request.args.get("mode", "login")
    if request.method == "POST":
        action = request.form.get("action", mode)

        if action == "register":
            mode = "register"
            full_name = (request.form.get("full_name") or "").strip()
            phone = (request.form.get("phone") or "").strip()
            parent_phone = (request.form.get("parent_phone") or "").strip()
            governorate = (request.form.get("governorate") or "الدقهلية").strip()
            grade = normalize_grade_label((request.form.get("grade") or "").strip())
            password = request.form.get("password") or ""

            if not full_name or not phone or not grade or not password:
                flash("يرجى استكمال جميع البيانات المطلوبة.", "warning")
                return render_template("auth.html", mode="register")

            existing = User.query.filter(
                (User.phone == phone) | (User.username == phone)
            ).first()
            if existing:
                flash("رقم الهاتف مسجل بالفعل على المنصة، يمكنك تسجيل الدخول.", "warning")
                return redirect(url_for("auth", mode="login"))

            try:
                new_student = User(
                    username=phone,
                    full_name=full_name,
                    phone=phone,
                    parent_phone=parent_phone,
                    governorate=governorate,
                    grade=grade,
                    role="student",
                    is_active=False,
                    onboarding_done=True,
                    password_hash=generate_password_hash(password),
                )
                db.session.add(new_student)
                db.session.commit()
            except Exception:
                db.session.rollback()
                flash("تعذر إنشاء الحساب حالياً، يرجى المحاولة مرة أخرى.", "danger")
                return render_template("auth.html", mode="register")

            session["user_id"] = new_student.id
            session["show_login_modal"] = True
            flash("تم إنشاء حسابك بنجاح، وهو الآن قيد مراجعة الإدارة.", "info")
            return redirect(url_for("student_dashboard"))

        else:
            mode = "login"
            login_id = (request.form.get("login_id") or "").strip()
            password = request.form.get("password") or ""

            try:
                user = User.query.filter(
                    (User.phone == login_id)
                    | (User.username == login_id)
                    | (User.full_name == login_id)
                ).first()
            except Exception:
                db.session.rollback()
                user = None

            if not user or not _verify_password_safe(user.password_hash, password):
                flash("بيانات الدخول غير صحيحة، تأكد من رقم الهاتف أو اسم المستخدم وكلمة السر.", "danger")
                return render_template("auth.html", mode="login")

            s = get_settings()
            dev_username = os.environ.get("DEVELOPER_USERNAME", "").strip()
            if bool(getattr(s, "is_maintenance", False)) and not is_developer_session():
                is_dev_user = bool(
                    (user.role or "").lower() == "admin"
                    and (not dev_username or user.username == dev_username)
                )
                if not is_dev_user:
                    flash("المنصة حالياً في وضع التحديث والصيانة بواسطة المطور.", "warning")
                    return render_template("auth.html", mode="login")
                session["dev_maintenance_owner"] = True

            session["user_id"] = user.id
            session["show_login_modal"] = True
            if (user.role or "").lower() == "admin":
                return redirect(url_for("admin_dashboard"))
            return redirect(url_for("student_dashboard"))

    return render_template("auth.html", mode=mode)


@app.route("/logout")
def logout():
    keep_dev = is_developer_session()
    session.clear()
    if keep_dev:
        session["dev_maintenance_owner"] = True
    flash("تم تسجيل الخروج بنجاح.", "info")
    return redirect(url_for("index"))


# ==================== لوحة الطالب ====================
@app.route("/student")
def student_dashboard():
    user = get_current_user()
    if not user:
        flash("يرجى تسجيل الدخول أولاً.", "warning")
        return redirect(url_for("auth", mode="login"))

    if (user.role or "").lower() == "admin":
        return redirect(url_for("admin_dashboard"))

    show_login_modal = bool(session.pop("show_login_modal", False))

    try:
        show_onboarding = not bool(user.onboarding_done and user.full_name and user.grade)
    except Exception:
        show_onboarding = False

    try:
        pending_approval = not bool(user.is_active)
    except Exception:
        pending_approval = False

    try:
        announcements = Announcement.query.order_by(Announcement.id.desc()).all()
    except Exception:
        db.session.rollback()
        announcements = []

    if pending_approval:
        return render_template(
            "student.html",
            user=user,
            show_login_modal=show_login_modal,
            show_onboarding=show_onboarding,
            pending_approval=True,
            announcements=announcements,
            tab="overview",
        )

    tab = request.args.get("tab", "overview")
    week_id_raw = request.args.get("week_id")
    selected_subscribe_week_id = int(request.args.get("subscribe_week_id")) if (request.args.get("subscribe_week_id") or "").isdigit() else None

    try:
        user_norm_grade = normalize_grade_label(user.grade)
        weeks = weeks_for_grade(user_norm_grade)
    except Exception:
        db.session.rollback()
        user_norm_grade = ""
        weeks = []

    try:
        sub_ids = {
            s.week_id for s in WeekSubscription.query.filter_by(user_id=user.id).all()
        }
    except Exception:
        db.session.rollback()
        sub_ids = set()

    subscribed_weeks = [w for w in weeks if getattr(w, "is_free", False) or w.id in sub_ids]

    week_access_map = {}
    for w in weeks:
        can_open = bool(getattr(w, "is_free", False) or (w.id in sub_ids))
        lock_reason = "" if can_open else "هذه الباقة تحتاج اشتراكاً أو كود تفعيل أو تحويل فودافون كاش."
        week_access_map[w.id] = {"can_open": can_open, "lock_reason": lock_reason}

    active_week = None
    active_week_info = None
    lecture_groups = []
    grouped_contents = {"explanation": [], "training": [], "homework": [], "exam_section": []}

    try:
        watched_ids = {
            wc.content_id for wc in WatchedContent.query.filter_by(user_id=user.id).all()
        }
    except Exception:
        db.session.rollback()
        watched_ids = set()

    s_cfg = get_settings()
    if week_id_raw and week_id_raw.isdigit():
        try:
            candidate = db.session.get(WeekPackage, int(week_id_raw))
            if candidate and getattr(candidate, "is_published", True) and normalize_grade_label(candidate.grade) in (user_norm_grade, "ALL_GRADES", ""):
                active_week = candidate
                active_week_info = week_access_map.get(
                    candidate.id,
                    {"can_open": bool(getattr(candidate, "is_free", False) or candidate.id in sub_ids), "lock_reason": "مغلق"},
                )
                lecture_groups = _build_lecture_groups(
                    candidate, user.id, getattr(s_cfg, "pass_percentage_required", 50.0)
                )
                for c in sorted(getattr(candidate, "contents", []) or [], key=lambda x: x.id):
                    sec = c.section_key if c.section_key in grouped_contents else "explanation"
                    grouped_contents[sec].append(c)
        except Exception:
            db.session.rollback()
            active_week = None

    try:
        exams = exams_for_grade(user_norm_grade)
    except Exception:
        db.session.rollback()
        exams = []

    results_by_exam = {}
    try:
        for r in ExamResult.query.filter_by(user_id=user.id).order_by(ExamResult.id.desc()).all():
            if r.exam_id not in results_by_exam:
                results_by_exam[r.exam_id] = r
    except Exception:
        db.session.rollback()
        results_by_exam = {}

    my_requests = []
    try:
        my_requests = (
            SubscriptionRequest.query.filter_by(user_id=user.id)
            .order_by(SubscriptionRequest.id.desc())
            .all()
        )
    except Exception:
        db.session.rollback()
        my_requests = []

    level_info = compute_student_level(user)

    return render_template(
        "student.html",
        user=user,
        show_login_modal=show_login_modal,
        show_onboarding=show_onboarding,
        pending_approval=False,
        tab=tab,
        weeks=weeks,
        subscribed_weeks=subscribed_weeks,
        week_access_map=week_access_map,
        active_week=active_week,
        active_week_info=active_week_info,
        lecture_groups=lecture_groups,
        grouped_contents=grouped_contents,
        watched_ids=watched_ids,
        format_embed_url=format_embed_url,
        exams=exams,
        results_by_exam=results_by_exam,
        my_requests=my_requests,
        selected_subscribe_week_id=selected_subscribe_week_id,
        level_info=level_info,
        announcements=announcements,
    )


@app.route("/student/onboarding", methods=["POST"])
def complete_onboarding():
    user = get_current_user()
    if not user:
        return redirect(url_for("auth", mode="login"))

    user.full_name = (request.form.get("full_name") or user.full_name).strip()
    user.parent_phone = (request.form.get("parent_phone") or "").strip()
    user.governorate = (request.form.get("governorate") or "الدقهلية").strip()
    grade = normalize_grade_label((request.form.get("grade") or "").strip())
    if grade:
        user.grade = grade
    user.onboarding_done = True
    db.session.commit()
    flash("تم حفظ بيانات ملفك الشخصي بنجاح.", "success")
    return redirect(url_for("student_dashboard"))


@app.route("/student/redeem-code", methods=["POST"])
def redeem_code():
    user = get_current_user()
    if not user:
        return redirect(url_for("auth", mode="login"))

    code_str = (request.form.get("code") or "").strip().upper()
    code_type = (request.form.get("code_type") or "").strip()
    week_id_raw = (request.form.get("week_id") or "").strip()
    selected_week_id = int(week_id_raw) if week_id_raw.isdigit() else None

    code_obj = ActivationCode.query.filter_by(code=code_str).first()
    if not code_obj:
        flash("كود التفعيل غير صحيح.", "danger")
        return redirect(url_for("student_dashboard", tab="courses"))

    if code_obj.is_used:
        flash("هذا الكود تم استخدامه مسبقاً.", "warning")
        return redirect(url_for("student_dashboard", tab="courses"))

    code_obj.is_used = True
    code_obj.used_by = user.id
    user.is_active = True

    target_week_id = code_obj.week_id or selected_week_id
    if target_week_id:
        exists_sub = WeekSubscription.query.filter_by(user_id=user.id, week_id=target_week_id).first()
        if not exists_sub:
            db.session.add(WeekSubscription(user_id=user.id, week_id=target_week_id))
        db.session.commit()
        type_label = "كود المحاضرة" if code_type == "lecture" else ("كود السنتر" if code_type == "center" else "كود الباقة")
        flash(f"تم تفعيل الباقة بنجاح ({type_label})!", "success")
        return redirect(url_for("student_dashboard", week_id=target_week_id))

    db.session.commit()
    flash("تم تفعيل حسابك بنجاح!", "success")
    return redirect(url_for("student_dashboard", tab="courses"))


@app.route("/student/subscribe-vodafone", methods=["POST"])
def subscribe_vodafone():
    user = get_current_user()
    if not user:
        return redirect(url_for("auth", mode="login"))

    s = get_settings()
    week_id_raw = (request.form.get("week_id") or "").strip()
    week_id = int(week_id_raw) if week_id_raw.isdigit() else None
    subscription_type = (request.form.get("subscription_type") or "package").strip()
    sender_phone = (request.form.get("sender_phone") or "").strip()
    receiver_phone = (request.form.get("receiver_phone") or getattr(s, "vodafone_cash_number", "") or "").strip()
    notes = (request.form.get("notes") or "").strip()
    screenshot_file = request.files.get("screenshot")

    if not sender_phone or not receiver_phone:
        flash("يرجى إدخال الرقم المحوّل منه والرقم المحوّل إليه.", "warning")
        return redirect(url_for("student_dashboard", tab="courses", subscribe_week_id=week_id))

    screenshot_url = save_uploaded_file(screenshot_file)
    if not screenshot_url:
        flash("يرجى إرفاق صورة سكرين شوت صحيحة للتحويل (PNG, JPG, JPEG, WEBP).", "warning")
        return redirect(url_for("student_dashboard", tab="courses", subscribe_week_id=week_id))

    try:
        req_obj = SubscriptionRequest(
            user_id=user.id,
            week_id=week_id,
            subscription_type=subscription_type,
            payment_method="vodafone_cash",
            sender_phone=sender_phone,
            receiver_phone=receiver_phone,
            screenshot_path=screenshot_url,
            notes=notes,
            status="pending",
        )
        db.session.add(req_obj)
        db.session.commit()
        flash("تم إرسال طلب الاشتراك عبر فودافون كاش بنجاح، وسيتم مراجعته من الإدارة.", "success")
    except Exception:
        db.session.rollback()
        flash("تعذر إرسال طلب الاشتراك حالياً، يرجى المحاولة مرة أخرى.", "danger")

    return redirect(url_for("student_dashboard", tab="courses"))


@app.route("/student/watch/<int:content_id>", methods=["POST"])
def mark_watched(content_id):
    user = get_current_user()
    if not user:
        return redirect(url_for("auth", mode="login"))

    content = db.session.get(CourseContent, content_id)
    if not content:
        flash("المحتوى غير موجود.", "danger")
        return redirect(url_for("student_dashboard"))

    if not WatchedContent.query.filter_by(user_id=user.id, content_id=content.id).first():
        db.session.add(WatchedContent(user_id=user.id, content_id=content.id))
        db.session.commit()
        flash("تم تسجيل إتمام مشاهدة الدرس.", "success")

    return redirect(url_for("student_dashboard", week_id=content.week_id))


# ==================== الاختبارات ====================
@app.route("/exam/<int:exam_id>")
def take_exam(exam_id):
    user = get_current_user()
    if not user:
        flash("يرجى تسجيل الدخول أولاً.", "warning")
        return redirect(url_for("auth", mode="login"))

    exam = db.session.get(Exam, exam_id)
    if not exam:
        flash("الاختبار غير موجود.", "danger")
        return redirect(url_for("student_dashboard", tab="exams"))

    is_admin = (user.role or "").lower() == "admin"
    back_url = url_for("admin_dashboard") if is_admin else url_for("student_dashboard", tab="exams")

    attempt = (
        ExamAttempt.query.filter_by(exam_id=exam.id, user_id=user.id)
        .order_by(ExamAttempt.id.desc())
        .first()
    )
    questions = ExamQuestion.query.filter_by(exam_id=exam.id).order_by(ExamQuestion.id.asc()).all()
    saved_answers = parse_answers_json(attempt.answers_json) if attempt else {}
    evaluation = evaluate_attempt(exam, attempt) if attempt else None

    return render_template(
        "exam.html",
        exam=exam,
        questions=questions,
        total_marks=len(questions),
        attempt=attempt,
        saved_answers=saved_answers,
        evaluation=evaluation,
        is_admin=is_admin,
        back_url=back_url,
        start_url=url_for("start_exam_attempt", exam_id=exam.id),
        submit_url=url_for("submit_exam_attempt", exam_id=exam.id),
        admin_settings_url=url_for("update_exam_grading_settings", exam_id=exam.id),
    )


@app.route("/exam/<int:exam_id>/start", methods=["POST"])
def start_exam_attempt(exam_id):
    user = get_current_user()
    if not user:
        return redirect(url_for("auth", mode="login"))

    exam = db.session.get(Exam, exam_id)
    if not exam:
        return redirect(url_for("student_dashboard", tab="exams"))

    prev_count = ExamAttempt.query.filter_by(exam_id=exam.id, user_id=user.id).count()
    attempt = ExamAttempt(
        exam_id=exam.id,
        user_id=user.id,
        attempt_number=prev_count + 1,
        serial_code=f"EX{exam.id}-U{user.id}-{secrets.token_hex(3).upper()}",
        status="in_progress",
        started_at=datetime.utcnow(),
        answers_json="{}",
    )
    db.session.add(attempt)
    db.session.commit()
    return redirect(url_for("take_exam", exam_id=exam.id))


@app.route("/exam/<int:exam_id>/submit", methods=["POST"])
def submit_exam_attempt(exam_id):
    user = get_current_user()
    if not user:
        return redirect(url_for("auth", mode="login"))

    exam = db.session.get(Exam, exam_id)
    if not exam:
        return redirect(url_for("student_dashboard", tab="exams"))

    attempt = (
        ExamAttempt.query.filter_by(exam_id=exam.id, user_id=user.id, status="in_progress")
        .order_by(ExamAttempt.id.desc())
        .first()
    )
    if not attempt:
        return redirect(url_for("take_exam", exam_id=exam.id))

    questions = ExamQuestion.query.filter_by(exam_id=exam.id).order_by(ExamQuestion.id.asc()).all()
    answers = {}
    for q in questions:
        val = request.form.get(f"q_{q.id}")
        if val in ("A", "B", "C", "D"):
            answers[str(q.id)] = val

    attempt.answers_json = json.dumps(answers, ensure_ascii=False)
    action_type = request.form.get("action_type", "submit")

    if action_type == "save_later":
        db.session.commit()
        flash("تم حفظ إجاباتك مؤقتاً، يمكنك استكمال الاختبار قبل انتهاء الوقت.", "info")
        return redirect(url_for("take_exam", exam_id=exam.id))

    attempt.status = "submitted"
    attempt.submitted_at = datetime.utcnow()

    score = sum(1 for q in questions if answers.get(str(q.id)) == q.correct_option)
    total_q = len(questions)
    pct = round((score / total_q * 100.0), 1) if total_q > 0 else 0.0

    db.session.add(
        ExamResult(
            exam_id=exam.id,
            user_id=user.id,
            score=score,
            total_questions=total_q,
            percentage=pct,
        )
    )
    db.session.commit()
    flash("تم تسليم الاختبار بنجاح!", "success")
    return redirect(url_for("take_exam", exam_id=exam.id))


# ==================== لوحة الإدارة ووضع المطور ====================
def require_admin():
    user = get_current_user()
    if not user:
        flash("يرجى تسجيل الدخول أولاً.", "warning")
        return None, redirect(url_for("auth", mode="login"))
    if (user.role or "").lower() != "admin":
        flash("هذه الصفحة مخصصة للإدارة فقط.", "danger")
        return None, redirect(url_for("student_dashboard"))
    return user, None


@app.route("/admin/dev-access/<token>")
def dev_access_unlock(token):
    if DEV_UNLOCK_TOKEN and secrets.compare_digest(token or "", DEV_UNLOCK_TOKEN):
        session["dev_maintenance_owner"] = True
        admin_user = User.query.filter_by(role="admin").first()
        if admin_user:
            session["user_id"] = admin_user.id
        flash("تم تفعيل جلسة المطور الخاصة بك بنجاح.", "success")
        return redirect(url_for("admin_dashboard"))
    return "غير مصرح", 403


@app.route("/admin/toggle-maintenance", methods=["POST"])
def toggle_maintenance():
    admin_user, err_resp = require_admin()
    if err_resp:
        return err_resp

    s = get_settings()
    currently_maint = bool(getattr(s, "is_maintenance", False))

    if not currently_maint:
        s.is_maintenance = True
        custom_msg = (request.form.get("maintenance_message") or "").strip()
        if custom_msg:
            s.maintenance_message = custom_msg
        session["dev_maintenance_owner"] = True
        db.session.commit()
        flash(
            "تم إيقاف المنصة وتفعيل وضع التحديث؛ الزر وصلاحية التحكم لك أنت فقط ولن يظهر الزر للمستر في لوحة الإدارة.",
            "warning",
        )
    else:
        if not is_developer_session():
            flash("المنصة في وضع التحديث حالياً ولا يمكن إعادة تشغيلها إلا من جلسة المطور.", "danger")
            return redirect(url_for("admin_dashboard"))

        s.is_maintenance = False
        session.pop("dev_maintenance_owner", None)
        db.session.commit()
        flash("تم إنهاء التحديث وإعادة تشغيل المنصة للطلاب والجميع بنجاح!", "success")

    return redirect(url_for("admin_dashboard"))


@app.route("/admin")
def admin_dashboard():
    admin_user, err_resp = require_admin()
    if err_resp:
        return err_resp

    show_login_modal = bool(session.pop("show_login_modal", False))
    selected_grade = normalize_grade_label((request.args.get("grade") or "").strip())

    try:
        all_users = User.query.order_by(User.id.desc()).all()
        all_students = [u for u in all_users if (u.role or "").lower() != "admin"]
    except Exception:
        db.session.rollback()
        all_students = []

    pending_students = [st for st in all_students if not bool(st.is_active)]

    students_data = []
    students_by_grade = {g: [] for g in GRADES}
    for st in all_students:
        lvl = compute_student_level(st)
        norm_g = normalize_grade_label(st.grade)
        row = {"user": st, "level": lvl, "grade_label": norm_g or (st.grade or "غير محدد")}
        students_data.append(row)
        if norm_g in students_by_grade:
            students_by_grade[norm_g].append(row)

    try:
        all_weeks = WeekPackage.query.order_by(WeekPackage.order_num.asc(), WeekPackage.id.desc()).all()
    except Exception:
        db.session.rollback()
        all_weeks = []
    weeks = (
        [w for w in all_weeks if normalize_grade_label(w.grade) in (selected_grade, "ALL_GRADES")]
        if selected_grade
        else all_weeks
    )

    try:
        all_exams = Exam.query.order_by(Exam.id.desc()).all()
    except Exception:
        db.session.rollback()
        all_exams = []
    exams = (
        [ex for ex in all_exams if normalize_grade_label(ex.grade) in (selected_grade, "ALL_GRADES")]
        if selected_grade
        else all_exams
    )

    try:
        all_codes = ActivationCode.query.order_by(ActivationCode.id.desc()).all()
        codes = (
            [c for c in all_codes if normalize_grade_label(c.grade) == selected_grade]
            if selected_grade
            else all_codes
        )
    except Exception:
        db.session.rollback()
        codes = []

    try:
        subscription_requests = SubscriptionRequest.query.order_by(SubscriptionRequest.id.desc()).all()
    except Exception:
        db.session.rollback()
        subscription_requests = []

    pending_subscriptions = [sr for sr in subscription_requests if sr.status == "pending"]

    try:
        exam_results = ExamResult.query.order_by(ExamResult.id.desc()).all()
    except Exception:
        db.session.rollback()
        exam_results = []

    try:
        centers = Center.query.order_by(Center.id.asc()).all()
    except Exception:
        db.session.rollback()
        centers = []

    try:
        announcements = Announcement.query.order_by(Announcement.id.desc()).all()
    except Exception:
        db.session.rollback()
        announcements = []

    exams_map = {ex.id: ex.title for ex in all_exams}

    return render_template(
        "admin.html",
        admin_user=admin_user,
        show_login_modal=show_login_modal,
        selected_grade=selected_grade,
        pending_students=pending_students,
        students_data=students_data,
        students_by_grade=students_by_grade,
        all_weeks=all_weeks,
        weeks=weeks,
        all_exams=all_exams,
        exams=exams,
        content_sections=CONTENT_SECTIONS,
        codes=codes,
        subscription_requests=subscription_requests,
        pending_subscriptions=pending_subscriptions,
        centers=centers,
        announcements=announcements,
        exam_results=exam_results,
        exams_map=exams_map,
    )


@app.route("/admin/subscriptions/<int:req_id>/<action>", methods=["POST"])
def handle_subscription_request(req_id, action):
    _, err_resp = require_admin()
    if err_resp:
        return err_resp

    sr = db.session.get(SubscriptionRequest, req_id)
    if not sr:
        flash("طلب الاشتراك غير موجود.", "danger")
        return redirect(url_for("admin_dashboard"))

    if action == "approve":
        sr.status = "approved"
        st = db.session.get(User, sr.user_id)
        if st:
            st.is_active = True
        if sr.week_id:
            exists_sub = WeekSubscription.query.filter_by(user_id=sr.user_id, week_id=sr.week_id).first()
            if not exists_sub:
                db.session.add(WeekSubscription(user_id=sr.user_id, week_id=sr.week_id))
        db.session.commit()
        flash("تم قبول الاشتراك وتفعيل الباقة للطالب بنجاح!", "success")
    elif action == "reject":
        sr.status = "rejected"
        db.session.commit()
        flash("تم رفض طلب الاشتراك.", "info")

    return redirect(url_for("admin_dashboard"))


@app.route("/admin/student/<int:student_id>/toggle", methods=["POST"])
def toggle_student(student_id):
    _, err_resp = require_admin()
    if err_resp:
        return err_resp

    st = db.session.get(User, student_id)
    if st and (st.role or "").lower() != "admin":
        st.is_active = not bool(st.is_active)
        db.session.commit()
        flash("تم تحديث حالة حساب الطالب بنجاح.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/settings", methods=["POST"])
def update_settings():
    admin_user, err_resp = require_admin()
    if err_resp:
        return err_resp

    s = get_settings()
    s.platform_name = (request.form.get("platform_name") or s.platform_name).strip()
    s.teacher_name = (request.form.get("teacher_name") or s.teacher_name).strip()
    s.teacher_bio = (request.form.get("teacher_bio") or "").strip()
    s.whatsapp_number = (request.form.get("whatsapp_number") or "").strip()
    s.vodafone_cash_number = (request.form.get("vodafone_cash_number") or s.vodafone_cash_number or "").strip()
    s.facebook_url = (request.form.get("facebook_url") or "").strip() or None
    s.instagram_url = (request.form.get("instagram_url") or "").strip() or None
    s.tiktok_url = (request.form.get("tiktok_url") or "").strip() or None
    s.youtube_url = (request.form.get("youtube_url") or "").strip() or None

    try:
        s.pass_percentage_required = float(request.form.get("pass_percentage_required") or 50.0)
    except ValueError:
        s.pass_percentage_required = 50.0

    img_file = request.files.get("teacher_image")
    saved_img = save_uploaded_file(img_file)
    if saved_img:
        s.teacher_image = saved_img

    new_admin_user = (request.form.get("new_admin_username") or "").strip()
    new_admin_pass = request.form.get("new_admin_pass") or ""
    if new_admin_user:
        admin_user.username = new_admin_user
    if new_admin_pass:
        admin_user.password_hash = generate_password_hash(new_admin_pass)

    db.session.commit()
    flash("تم حفظ إعدادات المنصة بنجاح.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/weeks/add", methods=["POST"])
def add_week():
    _, err_resp = require_admin()
    if err_resp:
        return err_resp

    title = (request.form.get("title") or "").strip()
    description = (request.form.get("description") or "").strip()
    grade = normalize_grade_label((request.form.get("grade") or "").strip())
    is_free = bool(request.form.get("is_free"))

    try:
        order_num = int(request.form.get("order_num") or 1)
    except ValueError:
        order_num = 1

    try:
        price = float(request.form.get("price") or 0.0)
    except ValueError:
        price = 0.0

    if not title or not grade:
        flash("يرجى إدخال عنوان الأسبوع/الباقة واختيار الصف الدراسي.", "warning")
        return redirect(url_for("admin_dashboard"))

    try:
        img_file = request.files.get("week_image") or request.files.get("image")
        saved_week_img = save_uploaded_file(img_file)

        week = WeekPackage(
            title=title,
            description=description,
            image_path=saved_week_img,
            grade=grade,
            order_num=order_num,
            price=price,
            is_free=is_free,
            is_published=True,
        )
        db.session.add(week)
        db.session.flush()

        for vf in request.files.getlist("week_videos"):
            v_url = save_uploaded_file(vf)
            if v_url:
                db.session.add(
                    CourseContent(
                        week_id=week.id,
                        lecture_title="المحاضرة الأولى",
                        title=vf.filename or "فيديو شرح",
                        section_key="explanation",
                        content_type="video_upload",
                        source_path=v_url,
                    )
                )

        db.session.commit()
        flash("تمت إضافة الأسبوع / الباقة بنجاح.", "success")
    except Exception:
        db.session.rollback()
        flash("تعذر حفظ الأسبوع/الباقة، يرجى التحقق من البيانات أو حجم الملف المرفوع.", "danger")

    return redirect(url_for("admin_dashboard", grade="" if grade == "ALL_GRADES" else grade))


@app.route("/admin/contents/add", methods=["POST"])
def add_content():
    _, err_resp = require_admin()
    if err_resp:
        return err_resp

    week_id = request.form.get("week_id")
    lecture_title = (request.form.get("lecture_title") or "المحاضرة الأولى").strip() or "المحاضرة الأولى"
    title = (request.form.get("title") or "").strip()
    section_key = (request.form.get("section_key") or "explanation").strip()
    content_type = (request.form.get("content_type") or "video_link").strip()
    external_link = (request.form.get("external_link") or "").strip()
    duration_or_notes = (request.form.get("duration_or_notes") or "").strip()
    exam_id_raw = (request.form.get("exam_id") or "").strip()
    req_exam_raw = (request.form.get("required_exam_id") or "").strip()

    week = db.session.get(WeekPackage, int(week_id)) if week_id and week_id.isdigit() else None
    if not week or not title:
        flash("يرجى اختيار الباقة وإدخال عنوان العنصر.", "warning")
        return redirect(url_for("admin_dashboard"))

    try:
        source_path = external_link or None
        media_file = request.files.get("media_file")
        uploaded_url = save_uploaded_file(media_file)
        if uploaded_url:
            source_path = uploaded_url
            if content_type == "video_link":
                content_type = "video_upload"
            elif content_type == "file_link":
                content_type = "file_upload"

        linked_exam_id = int(exam_id_raw) if exam_id_raw.isdigit() else None
        req_exam_id = int(req_exam_raw) if req_exam_raw.isdigit() else None
        if section_key == "exam_section" and linked_exam_id and content_type == "video_link" and not source_path:
            content_type = "exam_link"

        db.session.add(
            CourseContent(
                week_id=week.id,
                lecture_title=lecture_title,
                title=title,
                section_key=section_key,
                content_type=content_type,
                source_path=source_path,
                exam_id=linked_exam_id,
                required_exam_id=req_exam_id,
                duration_or_notes=duration_or_notes,
            )
        )
        db.session.commit()
        flash("تمت إضافة المحتوى داخل المحاضرة والباقة بنجاح.", "success")
    except Exception:
        db.session.rollback()
        flash("تعذر إضافة المحتوى حالياً، يرجى المحاولة مرة أخرى.", "danger")

    return redirect(url_for("admin_dashboard"))


@app.route("/admin/weeks/<int:week_id>/toggle", methods=["POST"])
def toggle_week(week_id):
    _, err_resp = require_admin()
    if err_resp:
        return err_resp
    w = db.session.get(WeekPackage, week_id)
    if w:
        w.is_published = not bool(w.is_published)
        db.session.commit()
        flash("تم تحديث حالة نشر الأسبوع.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/weeks/<int:week_id>/delete", methods=["POST"])
def delete_week(week_id):
    _, err_resp = require_admin()
    if err_resp:
        return err_resp

    w = db.session.get(WeekPackage, week_id)
    if not w:
        flash("الأسبوع / الباقة غير موجودة.", "warning")
        return redirect(url_for("admin_dashboard"))

    try:
        content_ids = [c.id for c in (w.contents or [])]
        if content_ids:
            WatchedContent.query.filter(WatchedContent.content_id.in_(content_ids)).delete(
                synchronize_session=False
            )

        WeekSubscription.query.filter_by(week_id=w.id).delete(synchronize_session=False)
        ActivationCode.query.filter_by(week_id=w.id).update(
            {"week_id": None}, synchronize_session=False
        )
        SubscriptionRequest.query.filter_by(week_id=w.id).update(
            {"week_id": None}, synchronize_session=False
        )

        db.session.delete(w)
        db.session.commit()
        flash("تم حذف الأسبوع / الباقة بنجاح.", "info")
    except Exception:
        db.session.rollback()
        flash("تعذر حذف الباقة بسبب ارتباطها ببيانات أخرى، تم إلغاء العملية بأمان.", "danger")

    return redirect(url_for("admin_dashboard"))


@app.route("/admin/exams/add", methods=["POST"])
def add_exam():
    _, err_resp = require_admin()
    if err_resp:
        return err_resp

    title = (request.form.get("title") or "").strip()
    grade = normalize_grade_label((request.form.get("grade") or "").strip())
    grading_mode = (request.form.get("grading_mode") or "instant").strip()

    try:
        duration_minutes = int(request.form.get("duration_minutes") or 20)
    except ValueError:
        duration_minutes = 20

    try:
        grading_delay_hours = float(request.form.get("grading_delay_hours") or 0.0)
    except ValueError:
        grading_delay_hours = 0.0

    if not title or not grade:
        flash("يرجى إدخال عنوان الاختبار واختيار الصف.", "warning")
        return redirect(url_for("admin_dashboard"))

    db.session.add(
        Exam(
            title=title,
            grade=grade,
            duration_minutes=max(1, duration_minutes),
            grading_mode="delayed" if grading_mode == "delayed" else "instant",
            grading_delay_hours=max(0.0, grading_delay_hours),
        )
    )
    db.session.commit()
    flash("تم إنشاء الاختبار الإلكتروني بنجاح.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/exams/questions/add", methods=["POST"])
def add_question():
    _, err_resp = require_admin()
    if err_resp:
        return err_resp

    exam_id = request.form.get("exam_id")
    exam = db.session.get(Exam, int(exam_id)) if exam_id and exam_id.isdigit() else None
    question_text = (request.form.get("question_text") or "").strip()
    opt_a = (request.form.get("option_a") or "").strip()
    opt_b = (request.form.get("option_b") or "").strip()
    opt_c = (request.form.get("option_c") or "").strip()
    opt_d = (request.form.get("option_d") or "").strip()
    correct_option = (request.form.get("correct_option") or "A").strip().upper()

    if not exam or not question_text or not all([opt_a, opt_b, opt_c, opt_d]):
        flash("يرجى استكمال بيانات السؤال والاختيارات الأربعة.", "warning")
        return redirect(url_for("admin_dashboard"))

    if correct_option not in ("A", "B", "C", "D"):
        correct_option = "A"

    db.session.add(
        ExamQuestion(
            exam_id=exam.id,
            question_text=question_text,
            option_a=opt_a,
            option_b=opt_b,
            option_c=opt_c,
            option_d=opt_d,
            correct_option=correct_option,
        )
    )
    db.session.commit()
    flash("تمت إضافة السؤال بنجاح.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/exams/<int:exam_id>/delete", methods=["POST"])
def delete_exam(exam_id):
    _, err_resp = require_admin()
    if err_resp:
        return err_resp
    ex = db.session.get(Exam, exam_id)
    if ex:
        db.session.delete(ex)
        db.session.commit()
        flash("تم حذف الاختبار.", "info")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/exams/<int:exam_id>/grading", methods=["POST"])
def update_exam_grading_settings(exam_id):
    _, err_resp = require_admin()
    if err_resp:
        return err_resp

    ex = db.session.get(Exam, exam_id)
    if ex:
        mode = (request.form.get("grading_mode") or "instant").strip()
        try:
            delay_hrs = float(request.form.get("grading_delay_hours") or 0.0)
        except ValueError:
            delay_hrs = 0.0
        ex.grading_mode = "delayed" if mode == "delayed" else "instant"
        ex.grading_delay_hours = max(0.0, delay_hrs)
        db.session.commit()
        flash("تم تحديث إعدادات التصحيح للاختبار.", "success")

    if request.referrer and f"/exam/{exam_id}" in request.referrer:
        return redirect(url_for("take_exam", exam_id=exam_id))
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/codes/generate", methods=["POST"])
def generate_codes():
    _, err_resp = require_admin()
    if err_resp:
        return err_resp

    grade = normalize_grade_label((request.form.get("grade") or "").strip())
    code_type = (request.form.get("code_type") or "package").strip()
    week_id_raw = request.form.get("week_id")
    week_id = int(week_id_raw) if week_id_raw and week_id_raw.isdigit() else None

    try:
        count = max(1, min(100, int(request.form.get("count") or 10)))
    except ValueError:
        count = 10

    if not grade:
        flash("يرجى اختيار الصف الدراسي لتوليد الأكواد.", "warning")
        return redirect(url_for("admin_dashboard"))

    prefix = "LEC" if code_type == "lecture" else ("CTR" if code_type == "center" else "AHMED")
    created = 0
    while created < count:
        code_val = f"{prefix}-{secrets.token_hex(3).upper()}"
        if not ActivationCode.query.filter_by(code=code_val).first():
            db.session.add(ActivationCode(code=code_val, code_type=code_type, grade=grade, week_id=week_id))
            created += 1

    db.session.commit()
    flash(f"تم توليد {created} كود تفعيل بنجاح.", "success")
    return redirect(url_for("admin_dashboard", grade=grade))


@app.route("/admin/codes/delete-unused", methods=["POST"])
def delete_unused_codes():
    _, err_resp = require_admin()
    if err_resp:
        return err_resp

    grade = normalize_grade_label((request.form.get("grade") or "").strip())
    unused = ActivationCode.query.filter_by(is_used=False).all()
    for c in unused:
        if not grade or normalize_grade_label(c.grade) == grade:
            db.session.delete(c)
    db.session.commit()
    flash("تم حذف الأكواد غير المستخدمة.", "info")
    return redirect(url_for("admin_dashboard", grade=grade))


@app.route("/admin/codes/<int:code_id>/delete", methods=["POST"])
def delete_code(code_id):
    _, err_resp = require_admin()
    if err_resp:
        return err_resp
    c = db.session.get(ActivationCode, code_id)
    if c:
        db.session.delete(c)
        db.session.commit()
        flash("تم حذف الكود.", "info")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/centers/add", methods=["POST"])
def add_center():
    _, err_resp = require_admin()
    if err_resp:
        return err_resp
    name = (request.form.get("name") or "").strip()
    address = (request.form.get("address") or "").strip()
    schedule_notes = (request.form.get("schedule_notes") or "").strip()
    if name:
        db.session.add(Center(name=name, address=address, schedule_notes=schedule_notes))
        db.session.commit()
        flash("تمت إضافة المركز / الفرع بنجاح.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/centers/<int:center_id>/delete", methods=["POST"])
def delete_center(center_id):
    _, err_resp = require_admin()
    if err_resp:
        return err_resp
    c = db.session.get(Center, center_id)
    if c:
        db.session.delete(c)
        db.session.commit()
        flash("تم حذف المركز.", "info")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/announcements/add", methods=["POST"])
def add_announcement():
    _, err_resp = require_admin()
    if err_resp:
        return err_resp
    title = (request.form.get("title") or "").strip()
    message = (request.form.get("message") or "").strip()
    if title and message:
        db.session.add(Announcement(title=title, message=message))
        db.session.commit()
        flash("تم نشر التنبيه بنجاح.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/announcements/<int:ann_id>/delete", methods=["POST"])
def delete_announcement(ann_id):
    _, err_resp = require_admin()
    if err_resp:
        return err_resp
    ann = db.session.get(Announcement, ann_id)
    if ann:
        db.session.delete(ann)
        db.session.commit()
        flash("تم حذف التنبيه.", "info")
    return redirect(url_for("admin_dashboard"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="127.0.0.1", port=5000)