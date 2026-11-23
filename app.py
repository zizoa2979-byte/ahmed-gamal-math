import os
import uuid
import random
import string
from datetime import datetime
from functools import wraps
from urllib.parse import quote, urlparse, parse_qsl, urlencode, urlunparse
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = (os.environ.get("SECRET_KEY") or "ahmed_gamal_math_platform_2026_zizo").strip()

DEFAULT_TEACHER_NAME = "مستر / أحمد جمال"
DEFAULT_PLATFORM_NAME = "الرياضة أسهل وأوضح مع مستر أحمد جمال"
DEFAULT_TEACHER_BIO = "الرياضة أسهل وأوضح مع مستر أحمد جمال — شرح مبسط ومنهجي، تدريب مكثف على أفكار الامتحانات، وتقييم مستمر للمستوى."
DEFAULT_WHATSAPP = "01070626007"
DEVELOPER_CREDIT = "تم التصميم والتطوير بواسطة المهندس عبد العزيز أمير"


def normalize_db_url(raw_url: str) -> str:
    url = (raw_url or "").strip()
    if not url:
        return "sqlite:///ahmed_gamal_math_v1.db"
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if url.startswith("postgresql://"):
        parsed = urlparse(url)
        query_params = dict(parse_qsl(parsed.query))
        if "sslmode" not in query_params:
            query_params["sslmode"] = "require"
        new_query = urlencode(query_params)
        url = urlunparse(parsed._replace(query=new_query))
    return url


db_uri = normalize_db_url(os.environ.get("DATABASE_URL") or "")
app.config["SQLALCHEMY_DATABASE_URI"] = db_uri
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

if not db_uri.startswith("sqlite"):
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": 3,
        "max_overflow": 2,
    }

app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024

is_vercel = bool(os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV"))
if is_vercel:
    BASE_UPLOAD_DIR = "/tmp/uploads"
else:
    BASE_UPLOAD_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), "static", "uploads")

UPLOAD_VIDEOS = os.path.join(BASE_UPLOAD_DIR, "videos")
UPLOAD_FILES = os.path.join(BASE_UPLOAD_DIR, "files")
UPLOAD_IMAGES = os.path.join(BASE_UPLOAD_DIR, "images")

for folder in [UPLOAD_VIDEOS, UPLOAD_FILES, UPLOAD_IMAGES]:
    try:
        os.makedirs(folder, exist_ok=True)
    except Exception:
        pass

db = SQLAlchemy(app)

GRADES = [
    "الصف الأول الإعدادي",
    "الصف الثاني الإعدادي",
    "الصف الثالث الإعدادي",
    "الصف الأول الثانوي",
    "الصف الثاني الثانوي",
    "الصف الثالث الثانوي",
]

CONTENT_SECTIONS = [
    ("explanation", "تقسيم الشرح"),
    ("training", "تقسيم التدريبات"),
    ("exam_section", "تقسيم الاختبار"),
]


class PlatformSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    platform_name = db.Column(db.String(150), default=DEFAULT_PLATFORM_NAME)
    teacher_name = db.Column(db.String(150), default=DEFAULT_TEACHER_NAME)
    teacher_bio = db.Column(db.Text, default=DEFAULT_TEACHER_BIO)
    whatsapp_number = db.Column(db.String(30), default=DEFAULT_WHATSAPP)
    teacher_image = db.Column(db.String(300), default="")
    facebook_url = db.Column(db.String(300), default="")
    instagram_url = db.Column(db.String(300), default="")
    tiktok_url = db.Column(db.String(300), default="")
    youtube_url = db.Column(db.String(300), default="")
    auto_activate_students = db.Column(db.Boolean, default=False)
    pass_percentage_required = db.Column(db.Float, default=50.0)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=True)
    full_name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    parent_name = db.Column(db.String(150), nullable=True)
    parent_phone = db.Column(db.String(20), nullable=True)
    governorate = db.Column(db.String(80), default="الدقهلية")
    grade = db.Column(db.String(80), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="student")
    is_active = db.Column(db.Boolean, default=False)
    session_token = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Week(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    grade = db.Column(db.String(80), nullable=False)
    order_num = db.Column(db.Integer, default=1)
    is_free = db.Column(db.Boolean, default=False)
    price = db.Column(db.Integer, default=50)
    cover_image = db.Column(db.String(300), default="")
    prerequisite_exam_id = db.Column(db.Integer, nullable=True)
    is_published = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    contents = db.relationship("WeekContent", backref="week", cascade="all, delete-orphan", order_by="WeekContent.order_num")
    exams = db.relationship("Exam", backref="week", cascade="all, delete-orphan")


class WeekContent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    week_id = db.Column(db.Integer, db.ForeignKey("week.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    section_key = db.Column(db.String(30), default="explanation")
    content_type = db.Column(db.String(30), nullable=False)
    source_path = db.Column(db.String(500), default="")
    duration_or_notes = db.Column(db.String(150), default="")
    order_num = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class VideoProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    content_id = db.Column(db.Integer, db.ForeignKey("week_content.id"), nullable=False)
    watched_at = db.Column(db.DateTime, default=datetime.utcnow)


class Exam(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    grade = db.Column(db.String(80), nullable=False)
    week_id = db.Column(db.Integer, db.ForeignKey("week.id"), nullable=True)
    duration_minutes = db.Column(db.Integer, default=20)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    questions = db.relationship("ExamQuestion", backref="exam", cascade="all, delete-orphan")
    results = db.relationship("ExamResult", backref="exam", cascade="all, delete-orphan")


class ExamQuestion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("exam.id"), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.String(250), nullable=False)
    option_b = db.Column(db.String(250), nullable=False)
    option_c = db.Column(db.String(250), nullable=False)
    option_d = db.Column(db.String(250), nullable=False)
    correct_option = db.Column(db.String(5), nullable=False)


class ExamResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("exam.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    total_questions = db.Column(db.Integer, nullable=False)
    percentage = db.Column(db.Float, nullable=False)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    student = db.relationship("User", backref="exam_results")


class Enrollment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    week_id = db.Column(db.Integer, db.ForeignKey("week.id"), nullable=False)
    unlocked_at = db.Column(db.DateTime, default=datetime.utcnow)


class AccessCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True, nullable=False)
    week_id = db.Column(db.Integer, db.ForeignKey("week.id"), nullable=True)
    grade = db.Column(db.String(80), nullable=False)
    is_used = db.Column(db.Boolean, default=False)
    used_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class CenterBranch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    address = db.Column(db.String(250), default="")
    schedule_notes = db.Column(db.String(250), default="")
    grade = db.Column(db.String(80), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Announcement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    grade = db.Column(db.String(80), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


def ensure_schema_columns():
    alter_statements = [
        "ALTER TABLE platform_settings ADD COLUMN IF NOT EXISTS facebook_url VARCHAR(300) DEFAULT ''",
        "ALTER TABLE platform_settings ADD COLUMN IF NOT EXISTS instagram_url VARCHAR(300) DEFAULT ''",
        "ALTER TABLE platform_settings ADD COLUMN IF NOT EXISTS tiktok_url VARCHAR(300) DEFAULT ''",
        "ALTER TABLE platform_settings ADD COLUMN IF NOT EXISTS youtube_url VARCHAR(300) DEFAULT ''",
        "ALTER TABLE platform_settings ADD COLUMN IF NOT EXISTS auto_activate_students BOOLEAN DEFAULT FALSE",
        "ALTER TABLE platform_settings ADD COLUMN IF NOT EXISTS pass_percentage_required FLOAT DEFAULT 50.0",
    ]
    for stmt in alter_statements:
        try:
            with db.engine.begin() as conn:
                conn.execute(text(stmt))
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass


def _sanitize_settings_obj(settings):
    if not settings:
        settings = PlatformSettings()
    if not (settings.teacher_name or "").strip() or (settings.teacher_name or "").strip().lower() == "none":
        settings.teacher_name = DEFAULT_TEACHER_NAME
    if not (settings.platform_name or "").strip() or (settings.platform_name or "").strip().lower() == "none":
        settings.platform_name = DEFAULT_PLATFORM_NAME
    if not (settings.teacher_bio or "").strip() or (settings.teacher_bio or "").strip().lower() == "none":
        settings.teacher_bio = DEFAULT_TEACHER_BIO
    if not (settings.whatsapp_number or "").strip() or (settings.whatsapp_number or "").strip().lower() == "none":
        settings.whatsapp_number = DEFAULT_WHATSAPP
    if (settings.teacher_image or "").strip().lower() == "none":
        settings.teacher_image = ""
    if settings.pass_percentage_required is None:
        settings.pass_percentage_required = 50.0
    return settings


def get_settings():
    try:
        settings = PlatformSettings.query.first()
        if not settings:
            settings = PlatformSettings()
            db.session.add(settings)
            db.session.commit()
        return _sanitize_settings_obj(settings)
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        return _sanitize_settings_obj(PlatformSettings())


def save_uploaded_file(file_obj, target_folder, url_prefix):
    if not file_obj or file_obj.filename == "":
        return ""
    ext = os.path.splitext(secure_filename(file_obj.filename))[1]
    unique_name = f"{uuid.uuid4().hex}{ext}"
    file_obj.save(os.path.join(target_folder, unique_name))
    return f"{url_prefix}/{unique_name}"


def format_embed_url(url):
    if not url:
        return ""
    if "youtube.com/watch?v=" in url:
        video_id = url.split("v=")[1].split("&")[0]
        return f"https://www.youtube.com/embed/{video_id}?rel=0&modestbranding=1"
    if "youtu.be/" in url:
        video_id = url.split("youtu.be/")[1].split("?")[0]
        return f"https://www.youtube.com/embed/{video_id}?rel=0&modestbranding=1"
    if "drive.google.com" in url and "/view" in url:
        return url.replace("/view", "/preview")
    return url


def clean_wa_phone(phone):
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    if digits.startswith("0"):
        digits = "2" + digits
    elif digits and not digits.startswith("2"):
        digits = "20" + digits
    return digits


def is_week_unlocked_by_exam(user_id, week):
    if not week.prerequisite_exam_id:
        return True, ""
    settings = get_settings()
    req_pct = settings.pass_percentage_required if settings.pass_percentage_required is not None else 50.0
    best_res = ExamResult.query.filter_by(user_id=user_id, exam_id=week.prerequisite_exam_id).order_by(ExamResult.percentage.desc()).first()
    if best_res and best_res.percentage >= req_pct:
        return True, ""
    prereq_exam = db.session.get(Exam, week.prerequisite_exam_id)
    exam_name = prereq_exam.title if prereq_exam else "الاختبار السابق"
    return False, f"هذا المحتوى مغلق حتى النجاح في ({exam_name}) بنسبة {req_pct}% على الأقل."


def evaluate_student_level(student):
    grade_weeks = Week.query.filter_by(grade=student.grade, is_published=True).all()
    week_ids = [w.id for w in grade_weeks]

    total_videos = 0
    video_ids = []
    if week_ids:
        videos = WeekContent.query.filter(
            WeekContent.week_id.in_(week_ids),
            WeekContent.content_type.like("video%")
        ).all()
        total_videos = len(videos)
        video_ids = [v.id for v in videos]

    watched_count = 0
    if video_ids:
        watched_count = VideoProgress.query.filter(
            VideoProgress.user_id == student.id,
            VideoProgress.content_id.in_(video_ids)
        ).count()

    video_ratio = (watched_count / total_videos * 100.0) if total_videos > 0 else 100.0

    grade_exams = Exam.query.filter_by(grade=student.grade).all()
    total_exams = len(grade_exams)
    exams_title_map = {e.id: e.title for e in grade_exams}
    student_results = ExamResult.query.filter_by(user_id=student.id).order_by(ExamResult.submitted_at.desc()).all()

    solved_exam_ids = {r.exam_id for r in student_results}
    solved_count = len(solved_exam_ids)
    exam_completion_ratio = (solved_count / total_exams * 100.0) if total_exams > 0 else 100.0

    if student_results:
        avg_score = sum(r.percentage for r in student_results) / len(student_results)
    elif total_exams == 0:
        avg_score = 100.0
    else:
        avg_score = 0.0

    if total_videos == 0 and total_exams == 0:
        overall = 0.0
    else:
        overall = round((video_ratio * 0.30) + (exam_completion_ratio * 0.30) + (avg_score * 0.40), 1)

    if overall >= 85 and (total_videos == 0 or watched_count == total_videos) and (total_exams == 0 or solved_count == total_exams):
        label = "متفوق وممتاز"
        badge_class = "bg-info text-dark"
    elif overall >= 70:
        label = "جيد جداً"
        badge_class = "bg-info text-dark"
    elif overall >= 50:
        label = "جيد"
        badge_class = "bg-success"
    else:
        label = "يحتاج متابعة"
        badge_class = "bg-secondary"

    exam_details = []
    for r in student_results:
        ex_obj = db.session.get(Exam, r.exam_id)
        ex_title = exams_title_map.get(r.exam_id) or (ex_obj.title if ex_obj else f"امتحان #{r.exam_id}")
        exam_details.append({
            "exam_title": ex_title,
            "score": r.score,
            "total": r.total_questions,
            "percentage": r.percentage,
            "submitted_at": r.submitted_at.strftime("%Y-%m-%d %H:%M") if r.submitted_at else "-"
        })

    return {
        "overall": overall,
        "label": label,
        "badge_class": badge_class,
        "watched_count": watched_count,
        "total_videos": total_videos,
        "video_pct": round(video_ratio, 1),
        "solved_exams": solved_count,
        "total_exams": total_exams,
        "exam_pct": round(exam_completion_ratio, 1),
        "avg_score": round(avg_score, 1),
        "exam_details": exam_details
    }


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("يرجى تسجيل الدخول أولاً.", "warning")
            return redirect(url_for("auth"))
        user = db.session.get(User, session["user_id"])
        if not user or user.session_token != session.get("session_token"):
            session.clear()
            flash("تم فتح الحساب من جهاز آخر، يرجى تسجيل الدخول مرة أخرى.", "danger")
            return redirect(url_for("auth"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("سجل دخولك بحساب الإدارة أولاً.", "warning")
            return redirect(url_for("auth"))
        user = db.session.get(User, session["user_id"])
        if not user or user.session_token != session.get("session_token"):
            session.clear()
            flash("يرجى تسجيل الدخول مرة أخرى.", "warning")
            return redirect(url_for("auth"))
        if user.role != "admin":
            flash("هذا القسم مخصص للإدارة فقط.", "danger")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated


@app.context_processor
def inject_globals():
    current_user = None
    recent_students = []
    if "user_id" in session:
        try:
            current_user = db.session.get(User, session["user_id"])
            if current_user and current_user.role == "admin":
                recent_students = User.query.filter_by(role="student").order_by(User.created_at.desc()).limit(6).all()
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass
            current_user = None
    return dict(
        settings=get_settings(),
        current_user=current_user,
        recent_students=recent_students,
        grades=GRADES,
        content_sections=CONTENT_SECTIONS,
        clean_wa_phone=clean_wa_phone,
        quote=quote,
        developer_credit=DEVELOPER_CREDIT
    )


@app.route("/")
def index():
    students_by_grade = {g: [] for g in GRADES}
    try:
        for g in GRADES:
            g_students_raw = User.query.filter_by(role="student", grade=g).order_by(User.created_at.desc()).all()
            students_by_grade[g] = [{"user": s, "level": evaluate_student_level(s)} for s in g_students_raw]
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
    return render_template("index.html", students_by_grade=students_by_grade)


@app.route("/auth", methods=["GET", "POST"])
def auth():
    mode = request.args.get("mode", "login")
    if request.method == "POST":
        action = request.form.get("action")

        if action == "login":
            login_id = (request.form.get("login_id") or request.form.get("phone") or "").strip()
            password = (request.form.get("password") or "").strip()
            if not login_id or not password:
                flash("يرجى عدم ترك أي خانة فارغة عند تسجيل الدخول.", "danger")
                return render_template("auth.html", mode="login")

            user = User.query.filter(
                (User.phone == login_id) | (User.username == login_id)
            ).first()

            if user and check_password_hash(user.password_hash, password):
                token = uuid.uuid4().hex
                user.session_token = token
                db.session.commit()
                session["user_id"] = user.id
                session["session_token"] = token
                flash(f"أهلاً بك يا {user.full_name}!", "success")
                if user.role == "admin":
                    return redirect(url_for("admin_dashboard"))
                return redirect(url_for("student_dashboard"))
            else:
                flash("بيانات الدخول غير صحيحة.", "danger")
                return render_template("auth.html", mode="login")

        elif action == "register":
            full_name = (request.form.get("full_name") or "").strip()
            phone = (request.form.get("phone") or "").strip()
            parent_phone = (request.form.get("parent_phone") or "").strip()
            governorate = (request.form.get("governorate") or "").strip()
            grade = (request.form.get("grade") or "").strip()
            password = (request.form.get("password") or "").strip()

            if not all([full_name, phone, parent_phone, governorate, grade, password]):
                flash("لا يُسمح بترك أي خانة فارغة! يرجى إدخال جميع البيانات المطلوبة.", "danger")
                return render_template("auth.html", mode="register")

            if phone == parent_phone:
                flash("رقم هاتف الطالب ورقم هاتف ولي الأمر لا يجوز أن يكونا متطابقين.", "warning")
                return render_template("auth.html", mode="register")

            if User.query.filter_by(phone=phone).first():
                flash("رقم هاتف الطالب مسجل بالفعل، يمكنك تسجيل الدخول مباشرة.", "warning")
                return render_template("auth.html", mode="login")

            token = uuid.uuid4().hex
            new_user = User(
                full_name=full_name,
                phone=phone,
                parent_name="",
                parent_phone=parent_phone,
                governorate=governorate,
                grade=grade,
                password_hash=generate_password_hash(password),
                role="student",
                is_active=False,
                session_token=token
            )
            db.session.add(new_user)
            db.session.commit()

            session["user_id"] = new_user.id
            session["session_token"] = token
            flash("سوف يتم مراجعة حساباتكم ولن يظهر المحتوى إلا بعد قبول وموافقة الإدارة على الحساب.", "info")
            return redirect(url_for("student_dashboard"))

    return render_template("auth.html", mode=mode)


@app.route("/logout")
def logout():
    session.clear()
    flash("تم تسجيل الخروج بنجاح.", "info")
    return redirect(url_for("index"))


@app.route("/student")
@login_required
def student_dashboard():
    user = db.session.get(User, session["user_id"])
    if user.role == "admin":
        return redirect(url_for("admin_dashboard"))

    if not user.is_active:
        announcements = Announcement.query.filter(
            (Announcement.grade == "") | (Announcement.grade == None) | (Announcement.grade == user.grade)
        ).order_by(Announcement.created_at.desc()).limit(10).all()
        return render_template("student.html", user=user, pending_approval=True, announcements=announcements)

    tab = request.args.get("tab", "overview")
    weeks = Week.query.filter_by(grade=user.grade, is_published=True).order_by(Week.order_num.asc()).all()
    unlocked_ids = {e.week_id for e in Enrollment.query.filter_by(user_id=user.id).all()}
    watched_ids = {p.content_id for p in VideoProgress.query.filter_by(user_id=user.id).all()}

    week_access_map = {}
    for w in weeks:
        has_sub = bool(w.is_free or user.is_active or (w.id in unlocked_ids))
        exam_ok, lock_reason = is_week_unlocked_by_exam(user.id, w)
        week_access_map[w.id] = {
            "has_sub": has_sub,
            "exam_ok": exam_ok,
            "can_open": has_sub and exam_ok,
            "lock_reason": lock_reason
        }

    selected_week_id = request.args.get("week_id", type=int)
    active_week = None
    active_week_info = None
    grouped_contents = {k: [] for k, _ in CONTENT_SECTIONS}

    if selected_week_id:
        active_week = db.session.get(Week, selected_week_id)
        if not active_week:
            return redirect(url_for("student_dashboard"))
        has_sub = bool(active_week.is_free or user.is_active or (active_week.id in unlocked_ids))
        exam_ok, lock_reason = is_week_unlocked_by_exam(user.id, active_week)
        active_week_info = {
            "has_sub": has_sub,
            "exam_ok": exam_ok,
            "can_open": has_sub and exam_ok,
            "lock_reason": lock_reason
        }
        if active_week_info["can_open"]:
            for item in active_week.contents:
                sec = item.section_key if item.section_key in grouped_contents else "explanation"
                grouped_contents[sec].append(item)

    exams = Exam.query.filter_by(grade=user.grade).order_by(Exam.created_at.desc()).all()
    results = ExamResult.query.filter_by(user_id=user.id).order_by(ExamResult.submitted_at.desc()).all()
    results_by_exam = {r.exam_id: r for r in results}
    level_info = evaluate_student_level(user)

    centers = CenterBranch.query.filter(
        (CenterBranch.grade == "") | (CenterBranch.grade == None) | (CenterBranch.grade == user.grade)
    ).order_by(CenterBranch.created_at.desc()).all()

    announcements = Announcement.query.filter(
        (Announcement.grade == "") | (Announcement.grade == None) | (Announcement.grade == user.grade)
    ).order_by(Announcement.created_at.desc()).limit(15).all()

    subscribed_weeks = [w for w in weeks if w.is_free or user.is_active or (w.id in unlocked_ids)]

    return render_template(
        "student.html",
        user=user,
        pending_approval=False,
        tab=tab,
        weeks=weeks,
        subscribed_weeks=subscribed_weeks,
        unlocked_ids=unlocked_ids,
        watched_ids=watched_ids,
        week_access_map=week_access_map,
        active_week=active_week,
        active_week_info=active_week_info,
        grouped_contents=grouped_contents,
        exams=exams,
        results=results,
        results_by_exam=results_by_exam,
        level_info=level_info,
        centers=centers,
        announcements=announcements,
        format_embed_url=format_embed_url
    )


@app.route("/student/watch/<int:content_id>", methods=["POST"])
@login_required
def mark_watched(content_id):
    user = db.session.get(User, session["user_id"])
    if not user.is_active:
        flash("سوف يتم مراجعة حساباتكم ولن يظهر المحتوى إلا بعد قبول الحساب.", "warning")
        return redirect(url_for("student_dashboard"))
    content = db.session.get(WeekContent, content_id)
    if not content:
        return redirect(url_for("student_dashboard"))
    existing = VideoProgress.query.filter_by(user_id=user.id, content_id=content.id).first()
    if not existing:
        db.session.add(VideoProgress(user_id=user.id, content_id=content.id))
        db.session.commit()
    flash(f"تم تسجيل مشاهدة ({content.title}) وتحديث مستواك.", "success")
    return redirect(url_for("student_dashboard", week_id=content.week_id))


@app.route("/student/redeem", methods=["POST"])
@login_required
def redeem_code():
    user = db.session.get(User, session["user_id"])
    code_str = request.form.get("code", "").strip().upper()
    code_obj = AccessCode.query.filter_by(code=code_str, is_used=False).first()

    if not code_obj:
        flash("الكود غير صحيح أو تم استخدامه من قبل.", "danger")
        return redirect(url_for("student_dashboard"))

    if code_obj.grade != user.grade:
        flash(f"هذا الكود خاص بـ ({code_obj.grade}) وليس بصفك الدراسي ({user.grade}).", "warning")
        return redirect(url_for("student_dashboard"))

    code_obj.is_used = True
    code_obj.used_by_id = user.id
    code_obj.used_at = datetime.utcnow()

    if code_obj.week_id:
        exists = Enrollment.query.filter_by(user_id=user.id, week_id=code_obj.week_id).first()
        if not exists:
            db.session.add(Enrollment(user_id=user.id, week_id=code_obj.week_id))
        flash("تم تفعيل الباقة/الأسبوع بنجاح!", "success")
    else:
        user.is_active = True
        flash("تم تفعيل حسابك واشتراكك بنجاح!", "success")

    db.session.commit()
    return redirect(url_for("student_dashboard"))


@app.route("/exam/<int:exam_id>", methods=["GET", "POST"])
@login_required
def take_exam(exam_id):
    user = db.session.get(User, session["user_id"])
    if user.role != "admin" and not user.is_active:
        flash("سوف يتم مراجعة حساباتكم ولن يظهر المحتوى إلا بعد قبول الحساب.", "warning")
        return redirect(url_for("student_dashboard"))
    exam = db.session.get(Exam, exam_id)
    if not exam:
        return redirect(url_for("student_dashboard"))

    if request.method == "POST":
        questions = exam.questions
        total = len(questions)
        correct = 0

        for q in questions:
            chosen = (request.form.get(f"q_{q.id}") or "").strip().upper()
            if chosen == q.correct_option:
                correct += 1

        pct = round((correct / total) * 100.0, 1) if total > 0 else 0.0

        existing_res = ExamResult.query.filter_by(exam_id=exam.id, user_id=user.id).first()
        if existing_res:
            existing_res.score = correct
            existing_res.total_questions = total
            existing_res.percentage = pct
            existing_res.submitted_at = datetime.utcnow()
        else:
            db.session.add(ExamResult(
                exam_id=exam.id,
                user_id=user.id,
                score=correct,
                total_questions=total,
                percentage=pct
            ))
        db.session.commit()
        flash(f"تم تسليم الامتحان! درجتك: {correct} من {total} ({pct}%).", "success")
        return redirect(url_for("student_dashboard"))

    return render_template("exam.html", exam=exam, user=user)


@app.route("/admin")
@admin_required
def admin_dashboard():
    selected_grade = request.args.get("grade", "").strip()

    try:
        students_by_grade = {}
        grade_summary = []

        for g in GRADES:
            g_students_raw = User.query.filter_by(role="student", grade=g).order_by(User.created_at.desc()).all()
            g_students_enriched = [{"user": s, "level": evaluate_student_level(s)} for s in g_students_raw]
            students_by_grade[g] = g_students_enriched

            g_weeks_count = Week.query.filter_by(grade=g).count()
            g_exams_count = Exam.query.filter_by(grade=g).count()
            avg_lvl = round(sum(item["level"]["overall"] for item in g_students_enriched) / len(g_students_enriched), 1) if g_students_enriched else 0.0
            grade_summary.append({
                "grade": g,
                "students_count": len(g_students_enriched),
                "weeks_count": g_weeks_count,
                "exams_count": g_exams_count,
                "avg_level": avg_lvl
            })

        students_query = User.query.filter_by(role="student")
        weeks_query = Week.query
        exams_query = Exam.query

        if selected_grade:
            students_query = students_query.filter_by(grade=selected_grade)
            weeks_query = weeks_query.filter_by(grade=selected_grade)
            exams_query = exams_query.filter_by(grade=selected_grade)

        students_raw = students_query.order_by(User.created_at.desc()).all()
        students_data = [{"user": s, "level": evaluate_student_level(s)} for s in students_raw]

        weeks = weeks_query.order_by(Week.order_num.asc()).all()
        all_weeks = Week.query.order_by(Week.order_num.asc()).all()
        exams = exams_query.order_by(Exam.created_at.desc()).all()
        all_exams = Exam.query.order_by(Exam.created_at.desc()).all()
        exams_map = {e.id: e.title for e in all_exams}
        codes = AccessCode.query.order_by(AccessCode.created_at.desc()).limit(100).all()
        centers = CenterBranch.query.order_by(CenterBranch.created_at.desc()).all()
        announcements = Announcement.query.order_by(Announcement.created_at.desc()).limit(30).all()

        results_query = ExamResult.query.join(User)
        if selected_grade:
            results_query = results_query.filter(User.grade == selected_grade)
        exam_results = results_query.order_by(ExamResult.submitted_at.desc()).all()
    except Exception as exc:
        try:
            db.session.rollback()
        except Exception:
            pass
        flash(f"حدث تنبيه أثناء تحميل بعض بيانات الإدارة: {exc}", "warning")
        students_by_grade = {g: [] for g in GRADES}
        grade_summary = []
        students_data = []
        weeks = []
        all_weeks = []
        exams = []
        all_exams = []
        exams_map = {}
        codes = []
        centers = []
        announcements = []
        exam_results = []

    return render_template(
        "admin.html",
        selected_grade=selected_grade,
        students_by_grade=students_by_grade,
        grade_summary=grade_summary,
        students_data=students_data,
        weeks=weeks,
        all_weeks=all_weeks,
        exams=exams,
        all_exams=all_exams,
        exams_map=exams_map,
        codes=codes,
        centers=centers,
        announcements=announcements,
        exam_results=exam_results
    )


@app.route("/admin/settings", methods=["POST"])
@admin_required
def update_settings():
    settings = get_settings()
    settings.platform_name = (request.form.get("platform_name") or DEFAULT_PLATFORM_NAME).strip()
    settings.teacher_name = (request.form.get("teacher_name") or DEFAULT_TEACHER_NAME).strip()
    settings.teacher_bio = (request.form.get("teacher_bio") or DEFAULT_TEACHER_BIO).strip()
    settings.whatsapp_number = (request.form.get("whatsapp_number") or DEFAULT_WHATSAPP).strip()
    settings.facebook_url = request.form.get("facebook_url", settings.facebook_url or "").strip()
    settings.instagram_url = request.form.get("instagram_url", settings.instagram_url or "").strip()
    settings.tiktok_url = request.form.get("tiktok_url", settings.tiktok_url or "").strip()
    settings.youtube_url = request.form.get("youtube_url", settings.youtube_url or "").strip()
    settings.auto_activate_students = True if request.form.get("auto_activate_students") else False

    req_pct = request.form.get("pass_percentage_required", type=float)
    if req_pct is not None and 0 <= req_pct <= 100:
        settings.pass_percentage_required = req_pct

    img = request.files.get("teacher_image")
    if img and img.filename:
        settings.teacher_image = save_uploaded_file(img, UPLOAD_IMAGES, "/static/uploads/images")

    admin_user = db.session.get(User, session["user_id"])
    new_admin_username = request.form.get("new_admin_username", "").strip()
    if new_admin_username and admin_user:
        admin_user.username = new_admin_username

    new_admin_pass = request.form.get("new_admin_pass", "").strip()
    if new_admin_pass and admin_user:
        admin_user.password_hash = generate_password_hash(new_admin_pass)

    db.session.commit()
    flash("تم حفظ إعدادات المنصة بنجاح.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/week/add", methods=["POST"])
@admin_required
def add_week():
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    grade = request.form.get("grade", "").strip()
    order_num = request.form.get("order_num", 1, type=int)
    price = request.form.get("price", 0, type=int)
    is_free = True if request.form.get("is_free") else False
    prereq_exam_id = request.form.get("prerequisite_exam_id", type=int)

    cover_path = save_uploaded_file(request.files.get("cover_image"), UPLOAD_IMAGES, "/static/uploads/images")

    week = Week(
        title=title,
        description=description,
        grade=grade,
        order_num=order_num,
        price=price,
        is_free=is_free,
        cover_image=cover_path,
        prerequisite_exam_id=prereq_exam_id if prereq_exam_id and prereq_exam_id > 0 else None
    )
    db.session.add(week)
    db.session.commit()

    uploaded_videos = request.files.getlist("week_videos")
    video_idx = 1
    for vf in uploaded_videos:
        if vf and vf.filename:
            v_path = save_uploaded_file(vf, UPLOAD_VIDEOS, "/static/uploads/videos")
            if v_path:
                db.session.add(WeekContent(
                    week_id=week.id,
                    title=f"فيديو {video_idx}",
                    section_key="explanation",
                    content_type="video_upload",
                    source_path=v_path,
                    duration_or_notes="مرفوع من الجهاز",
                    order_num=video_idx
                ))
                video_idx += 1

    db.session.commit()
    flash(f"تم إضافة ({title}) لـ ({grade}) بنجاح.", "success")
    return redirect(url_for("admin_dashboard", grade=grade))


@app.route("/admin/week/toggle/<int:week_id>", methods=["POST"])
@admin_required
def toggle_week(week_id):
    week = db.session.get(Week, week_id)
    if week:
        week.is_published = not week.is_published
        db.session.commit()
        flash("تم تحديث حالة نشر الباقة/الأسبوع.", "success")
        return redirect(url_for("admin_dashboard", grade=week.grade))
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/week/delete/<int:week_id>", methods=["POST"])
@admin_required
def delete_week(week_id):
    week = db.session.get(Week, week_id)
    g = week.grade if week else ""
    if week:
        db.session.delete(week)
        db.session.commit()
        flash("تم حذف الباقة/الأسبوع ومحتوياته.", "info")
    return redirect(url_for("admin_dashboard", grade=g))


@app.route("/admin/content/add", methods=["POST"])
@admin_required
def add_content():
    week_id = request.form.get("week_id", type=int)
    week = db.session.get(Week, week_id)
    if not week:
        return redirect(url_for("admin_dashboard"))

    title = request.form.get("title", "").strip()
    section_key = request.form.get("section_key", "explanation").strip()
    if section_key not in dict(CONTENT_SECTIONS):
        section_key = "explanation"
    content_type = (request.form.get("content_type") or "video_upload").strip()
    duration_or_notes = request.form.get("duration_or_notes", "").strip()
    order_num = request.form.get("order_num", 1, type=int)

    existing_count = WeekContent.query.filter_by(week_id=week_id).count()
    if not title:
        title = f"فيديو {existing_count + 1}"

    source_path = ""
    if content_type == "video_upload":
        source_path = save_uploaded_file(request.files.get("media_file"), UPLOAD_VIDEOS, "/static/uploads/videos")
    elif content_type == "file_upload":
        source_path = save_uploaded_file(request.files.get("media_file"), UPLOAD_FILES, "/static/uploads/files")
    elif content_type in ("video_link", "file_link"):
        source_path = request.form.get("external_link", "").strip()

    content = WeekContent(
        week_id=week_id,
        title=title,
        section_key=section_key,
        content_type=content_type,
        source_path=source_path,
        duration_or_notes=duration_or_notes,
        order_num=order_num
    )
    db.session.add(content)
    db.session.commit()
    flash(f"تم إضافة ({title}) داخل القسم المحدد بنجاح.", "success")
    return redirect(url_for("admin_dashboard", grade=week.grade))


@app.route("/admin/content/delete/<int:content_id>", methods=["POST"])
@admin_required
def delete_content(content_id):
    content = db.session.get(WeekContent, content_id)
    g = content.week.grade if content and content.week else ""
    if content:
        db.session.delete(content)
        db.session.commit()
        flash("تم حذف المحتوى.", "info")
    return redirect(url_for("admin_dashboard", grade=g))


@app.route("/admin/exam/add", methods=["POST"])
@admin_required
def add_exam():
    title = request.form.get("title", "").strip()
    grade = request.form.get("grade", "").strip()
    week_id = request.form.get("week_id", type=int)
    duration_minutes = request.form.get("duration_minutes", 20, type=int)

    if not title or not grade:
        flash("يرجى إدخال عنوان الاختبار واختيار الصف الدراسي.", "warning")
        return redirect(url_for("admin_dashboard"))

    exam = Exam(
        title=title,
        grade=grade,
        week_id=week_id if week_id and week_id > 0 else None,
        duration_minutes=duration_minutes
    )
    db.session.add(exam)
    db.session.commit()
    flash(f"تم إنشاء الاختبار ({title}) لـ ({grade}). أضف أسئلته الآن.", "success")
    return redirect(url_for("admin_dashboard", grade=grade))


@app.route("/admin/exam/question/add", methods=["POST"])
@admin_required
def add_question():
    exam_id = request.form.get("exam_id", type=int)
    exam = db.session.get(Exam, exam_id)
    if not exam:
        return redirect(url_for("admin_dashboard"))
    question_text = request.form.get("question_text", "").strip()
    option_a = request.form.get("option_a", "").strip()
    option_b = request.form.get("option_b", "").strip()
    option_c = request.form.get("option_c", "").strip()
    option_d = request.form.get("option_d", "").strip()
    correct_option = (request.form.get("correct_option", "A")).strip().upper()

    if all([question_text, option_a, option_b, option_c, option_d]):
        db.session.add(ExamQuestion(
            exam_id=exam.id,
            question_text=question_text,
            option_a=option_a,
            option_b=option_b,
            option_c=option_c,
            option_d=option_d,
            correct_option=correct_option
        ))
        db.session.commit()
        flash("تم إضافة السؤال للاختبار.", "success")
    return redirect(url_for("admin_dashboard", grade=exam.grade))


@app.route("/admin/exam/delete/<int:exam_id>", methods=["POST"])
@admin_required
def delete_exam(exam_id):
    exam = db.session.get(Exam, exam_id)
    g = exam.grade if exam else ""
    if exam:
        db.session.delete(exam)
        db.session.commit()
        flash("تم حذف الاختبار.", "info")
    return redirect(url_for("admin_dashboard", grade=g))


@app.route("/admin/student/toggle/<int:student_id>", methods=["POST"])
@admin_required
def toggle_student(student_id):
    student = db.session.get(User, student_id)
    if student:
        student.is_active = not student.is_active
        db.session.commit()
        flash(f"تم تحديث حالة الحساب ({student.full_name}).", "success")
        return redirect(url_for("admin_dashboard", grade=student.grade))
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/codes/generate", methods=["POST"])
@admin_required
def generate_codes():
    grade = request.form.get("grade", "").strip()
    week_id = request.form.get("week_id", type=int)
    count = min(request.form.get("count", 10, type=int), 100)

    for _ in range(count):
        rand_part = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
        code_str = f"AHMED-{rand_part}"
        db.session.add(AccessCode(
            code=code_str,
            grade=grade,
            week_id=week_id if week_id and week_id > 0 else None
        ))
    db.session.commit()
    flash(f"تم توليد {count} كود تفعيل بنجاح.", "success")
    return redirect(url_for("admin_dashboard", grade=grade))


@app.route("/admin/codes/delete/<int:code_id>", methods=["POST"])
@admin_required
def delete_code(code_id):
    code_obj = db.session.get(AccessCode, code_id)
    g = code_obj.grade if code_obj else ""
    if code_obj:
        db.session.delete(code_obj)
        db.session.commit()
        flash("تم حذف الكود.", "info")
    return redirect(url_for("admin_dashboard", grade=g))


@app.route("/admin/codes/delete-unused", methods=["POST"])
@admin_required
def delete_unused_codes():
    grade = request.form.get("grade", "").strip()
    q = AccessCode.query.filter_by(is_used=False)
    if grade:
        q = q.filter_by(grade=grade)
    deleted_count = q.delete(synchronize_session=False)
    db.session.commit()
    flash(f"تم حذف {deleted_count} كود غير مستخدم.", "info")
    return redirect(url_for("admin_dashboard", grade=grade))


@app.route("/admin/center/add", methods=["POST"])
@admin_required
def add_center():
    name = request.form.get("name", "").strip()
    address = request.form.get("address", "").strip()
    schedule_notes = request.form.get("schedule_notes", "").strip()
    grade = request.form.get("grade", "").strip()
    if name:
        db.session.add(CenterBranch(name=name, address=address, schedule_notes=schedule_notes, grade=grade))
        db.session.commit()
        flash("تم إضافة المركز/الفرع بنجاح.", "success")
    return redirect(url_for("admin_dashboard", grade=grade))


@app.route("/admin/center/delete/<int:center_id>", methods=["POST"])
@admin_required
def delete_center(center_id):
    center = db.session.get(CenterBranch, center_id)
    if center:
        db.session.delete(center)
        db.session.commit()
        flash("تم حذف المركز/الفرع.", "info")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/announcement/add", methods=["POST"])
@admin_required
def add_announcement():
    title = request.form.get("title", "").strip()
    message = request.form.get("message", "").strip()
    grade = request.form.get("grade", "").strip()
    if title and message:
        db.session.add(Announcement(title=title, message=message, grade=grade))
        db.session.commit()
        flash("تم نشر الإشعار للمتدربين بنجاح.", "success")
    return redirect(url_for("admin_dashboard", grade=grade))


@app.route("/admin/announcement/delete/<int:ann_id>", methods=["POST"])
@admin_required
def delete_announcement(ann_id):
    ann = db.session.get(Announcement, ann_id)
    if ann:
        db.session.delete(ann)
        db.session.commit()
        flash("تم حذف الإشعار.", "info")
    return redirect(url_for("admin_dashboard"))


@app.errorhandler(500)
def internal_error(error):
    try:
        db.session.rollback()
    except Exception:
        pass
    return (
        "<html lang='ar' dir='rtl'><body style='background:#071324;color:#fff;font-family:sans-serif;text-align:center;padding:50px;'>"
        "<h3>حدث خطأ مؤقت في الخادم</h3><p><a href='/' style='color:#38bdf8;'>العودة للرئيسية</a></p></body></html>",
        500,
    )


_db_initialized = False


def init_db():
    global _db_initialized
    if _db_initialized:
        return
    try:
        db.create_all()
        ensure_schema_columns()
        settings = PlatformSettings.query.first()
        if not settings:
            settings = PlatformSettings()
            db.session.add(settings)
        else:
            _sanitize_settings_obj(settings)

        if not User.query.filter_by(role="admin").first():
            admin = User(
                username="Mr_Ahmed_Gamal_Math2026",
                full_name=DEFAULT_TEACHER_NAME,
                phone="01099887766",
                password_hash=generate_password_hash("M@th#Gamal$2026!Zizo"),
                role="admin",
                is_active=True
            )
            db.session.add(admin)
        db.session.commit()
        _db_initialized = True
    except Exception as exc:
        try:
            db.session.rollback()
        except Exception:
            pass
        print("Database initialization error:", exc)


@app.before_request
def ensure_db_ready():
    init_db()


if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(debug=True, port=5000)