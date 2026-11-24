import datetime
import json
import os
import random
import string
from functools import wraps

from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_ROOT = os.path.join(BASE_DIR, "static", "uploads")
UPLOAD_IMAGES = os.path.join(UPLOAD_ROOT, "images")
UPLOAD_VIDEOS = os.path.join(UPLOAD_ROOT, "videos")
UPLOAD_FILES = os.path.join(UPLOAD_ROOT, "files")

for folder in (UPLOAD_ROOT, UPLOAD_IMAGES, UPLOAD_VIDEOS, UPLOAD_FILES):
    os.makedirs(folder, exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "math-platform-secret-key-2026")

database_url = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
if database_url:
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
else:
    default_db_path = os.path.join(BASE_DIR, "math_platform.db")
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{default_db_path}"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = UPLOAD_ROOT

db = SQLAlchemy(app)

GRADES = [
    "الصف الأول الثانوي",
    "الصف الثاني الثانوي",
    "الصف الثالث الثانوي",
    "الصف الأول الإعدادي",
    "الصف الثاني الإعدادي",
    "الصف الثالث الإعدادي",
]

CONTENT_SECTIONS = [
    ("explanation", "الشرح"),
    ("training", "التدريبات والحل"),
    ("notes", "المذكرات والملفات"),
]

DEVELOPER_CREDIT = "تم التصميم والتطوير بواسطة المهندس عبدالعزيز أمير"


class PlatformSettings(db.Model):
    __tablename__ = "platform_settings"
    id = db.Column(db.Integer, primary_key=True)
    platform_name = db.Column(db.String(150), default="منصة الرياضيات")
    teacher_name = db.Column(db.String(150), default="مستر / أحمد جمال")
    teacher_bio = db.Column(
        db.Text,
        default="منصة تعليمية متخصصة في مادة الرياضيات مع مستر / أحمد جمال، تضم باقة كتالوج المنصة المفتوحة للجميع وشرحاً مبسطاً وتدريبات واختبارات إلكترونية.",
    )
    whatsapp_number = db.Column(db.String(50), default="01000000000")
    pass_percentage_required = db.Column(db.Float, default=60.0)
    teacher_image = db.Column(db.String(255), nullable=True)
    facebook_url = db.Column(db.String(255), nullable=True)
    instagram_url = db.Column(db.String(255), nullable=True)
    tiktok_url = db.Column(db.String(255), nullable=True)
    youtube_url = db.Column(db.String(255), nullable=True)
    admin_username = db.Column(db.String(100), default="admin")
    admin_password_hash = db.Column(db.String(255), nullable=False)


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(40), unique=True, nullable=False)
    parent_phone = db.Column(db.String(40), nullable=True)
    governorate = db.Column(db.String(100), nullable=True)
    grade = db.Column(db.String(100), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)


class Week(db.Model):
    __tablename__ = "weeks"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    grade = db.Column(db.String(100), nullable=False)
    order_num = db.Column(db.Integer, default=1)
    price = db.Column(db.Integer, default=0)
    is_free = db.Column(db.Boolean, default=False)
    is_published = db.Column(db.Boolean, default=True)
    cover_image = db.Column(db.String(255), nullable=True)
    prerequisite_exam_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    contents = db.relationship("WeekContent", backref="week", cascade="all, delete-orphan", lazy=True)


class WeekContent(db.Model):
    __tablename__ = "week_contents"
    id = db.Column(db.Integer, primary_key=True)
    week_id = db.Column(db.Integer, db.ForeignKey("weeks.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    section_key = db.Column(db.String(50), default="explanation")
    content_type = db.Column(db.String(50), default="video_link")
    source_path = db.Column(db.String(500), nullable=True)
    duration_or_notes = db.Column(db.String(255), nullable=True)
    order_num = db.Column(db.Integer, default=1)


class Exam(db.Model):
    __tablename__ = "exams"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    grade = db.Column(db.String(100), nullable=False)
    duration_minutes = db.Column(db.Integer, default=20)
    grading_mode = db.Column(db.String(30), default="instant")
    grading_delay_hours = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    questions = db.relationship("Question", backref="exam", cascade="all, delete-orphan", lazy=True)


class Question(db.Model):
    __tablename__ = "questions"
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("exams.id"), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.String(255), nullable=False)
    option_b = db.Column(db.String(255), nullable=False)
    option_c = db.Column(db.String(255), nullable=False)
    option_d = db.Column(db.String(255), nullable=False)
    correct_option = db.Column(db.String(5), default="A")


class ExamAttempt(db.Model):
    __tablename__ = "exam_attempts"
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("exams.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    attempt_number = db.Column(db.Integer, default=1)
    serial_code = db.Column(db.String(40), nullable=False)
    status = db.Column(db.String(30), default="in_progress")
    saved_answers_json = db.Column(db.Text, default="{}")
    started_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    submitted_at = db.Column(db.DateTime, nullable=True)


class ExamResult(db.Model):
    __tablename__ = "exam_results"
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("exams.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    attempt_id = db.Column(db.Integer, nullable=True)
    score = db.Column(db.Integer, default=0)
    total_questions = db.Column(db.Integer, default=0)
    percentage = db.Column(db.Float, default=0.0)
    submitted_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    student = db.relationship("User", lazy=True)


class ActivationCode(db.Model):
    __tablename__ = "activation_codes"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), unique=True, nullable=False)
    grade = db.Column(db.String(100), nullable=False)
    week_id = db.Column(db.Integer, nullable=True)
    is_used = db.Column(db.Boolean, default=False)
    used_by_user_id = db.Column(db.Integer, nullable=True)


class StudentWeekAccess(db.Model):
    __tablename__ = "student_week_access"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    week_id = db.Column(db.Integer, nullable=False)


class VideoProgress(db.Model):
    __tablename__ = "video_progress"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    content_id = db.Column(db.Integer, nullable=False)
    watched = db.Column(db.Boolean, default=True)


class Center(db.Model):
    __tablename__ = "centers"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    address = db.Column(db.String(255), nullable=True)
    schedule_notes = db.Column(db.String(255), nullable=True)


class Announcement(db.Model):
    __tablename__ = "announcements"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)


def ensure_schema_columns():
    engine_name = db.engine.dialect.name
    alter_statements = []
    if engine_name == "sqlite":
        alter_statements = [
            "ALTER TABLE exams ADD COLUMN grading_mode VARCHAR(30) DEFAULT 'instant'",
            "ALTER TABLE exams ADD COLUMN grading_delay_hours FLOAT DEFAULT 0.0",
            "ALTER TABLE weeks ADD COLUMN is_free BOOLEAN DEFAULT 0",
            "ALTER TABLE weeks ADD COLUMN price INTEGER DEFAULT 0",
            "ALTER TABLE weeks ADD COLUMN cover_image VARCHAR(255)",
            "ALTER TABLE weeks ADD COLUMN prerequisite_exam_id INTEGER",
        ]
    elif engine_name == "postgresql":
        alter_statements = [
            "ALTER TABLE exams ADD COLUMN IF NOT EXISTS grading_mode VARCHAR(30) DEFAULT 'instant'",
            "ALTER TABLE exams ADD COLUMN IF NOT EXISTS grading_delay_hours FLOAT DEFAULT 0.0",
            "ALTER TABLE weeks ADD COLUMN IF NOT EXISTS is_free BOOLEAN DEFAULT FALSE",
            "ALTER TABLE weeks ADD COLUMN IF NOT EXISTS price INTEGER DEFAULT 0",
            "ALTER TABLE weeks ADD COLUMN IF NOT EXISTS cover_image VARCHAR(255)",
            "ALTER TABLE weeks ADD COLUMN IF NOT EXISTS prerequisite_exam_id INTEGER",
        ]
    for stmt in alter_statements:
        try:
            with db.engine.begin() as conn:
                conn.execute(text(stmt))
        except Exception:
            pass


def init_db_and_defaults():
    db.create_all()
    ensure_schema_columns()

    settings = PlatformSettings.query.first()
    if not settings:
        settings = PlatformSettings(
            platform_name="منصة الرياضيات",
            teacher_name="مستر / أحمد جمال",
            teacher_bio="منصة تعليمية متخصصة في مادة الرياضيات مع مستر / أحمد جمال، تضم باقة كتالوج المنصة المفتوحة للجميع وشرحاً مبسطاً وتدريبات واختبارات إلكترونية.",
            whatsapp_number="01000000000",
            pass_percentage_required=60.0,
            admin_username="admin",
            admin_password_hash=generate_password_hash("admin123"),
        )
        db.session.add(settings)
        db.session.commit()

    if User.query.count() == 0:
        demo_student = User(
            full_name="طالب تجريبي",
            phone="01012345678",
            parent_phone="01098765432",
            governorate="الدقهلية",
            grade=GRADES[0],
            password_hash=generate_password_hash("123456"),
            is_active=True,
        )
        db.session.add(demo_student)
        db.session.commit()


with app.app_context():
    try:
        init_db_and_defaults()
    except Exception:
        pass


def get_settings():
    s = PlatformSettings.query.first()
    if not s:
        s = PlatformSettings(
            platform_name="منصة الرياضيات",
            teacher_name="مستر / أحمد جمال",
            admin_username="admin",
            admin_password_hash=generate_password_hash("admin123"),
        )
        db.session.add(s)
        db.session.commit()
    return s


def get_current_student():
    uid = session.get("student_id")
    if not uid:
        return None
    return db.session.get(User, uid)


def is_admin_logged_in():
    return bool(session.get("is_admin"))


def student_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        st = get_current_student()
        if not st:
            flash("يرجى تسجيل الدخول بحساب الطالب أولاً.", "warning")
            return redirect(url_for("auth", mode="login"))
        if not st.is_active:
            flash("حسابك قيد المراجعة من الإدارة، يرجى انتظار التفعيل.", "warning")
            return redirect(url_for("auth", mode="login"))
        return fn(*args, **kwargs)

    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not is_admin_logged_in():
            flash("يرجى تسجيل الدخول كأدمن أولاً.", "warning")
            return redirect(url_for("auth", mode="login"))
        return fn(*args, **kwargs)

    return wrapper


def save_uploaded_file(file_storage, target_dir, public_prefix):
    if not file_storage or not file_storage.filename:
        return None
    os.makedirs(target_dir, exist_ok=True)
    clean_name = secure_filename(file_storage.filename)
    if not clean_name:
        clean_name = "file.bin"
    stamp = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    final_name = f"{stamp}_{clean_name}"
    file_storage.save(os.path.join(target_dir, final_name))
    return f"{public_prefix}/{final_name}"


def compute_student_level(student):
    grade_weeks = Week.query.filter_by(grade=student.grade, is_published=True).all() if student.grade else []
    week_ids = [w.id for w in grade_weeks]
    grade_contents = WeekContent.query.filter(WeekContent.week_id.in_(week_ids)).all() if week_ids else []
    video_ids = [c.id for c in grade_contents if c.content_type in ("video_link", "video_upload")]
    total_videos = len(video_ids)
    watched_count = (
        VideoProgress.query.filter(
            VideoProgress.user_id == student.id,
            VideoProgress.content_id.in_(video_ids),
            VideoProgress.watched.is_(True),
        ).count()
        if video_ids
        else 0
    )

    grade_exams = Exam.query.filter_by(grade=student.grade).all() if student.grade else []
    total_exams = len(grade_exams)
    results = ExamResult.query.filter_by(user_id=student.id).all()
    exam_ids_set = {e.id for e in grade_exams}
    relevant_results = [r for r in results if r.exam_id in exam_ids_set]
    solved_exams = len({r.exam_id for r in relevant_results})
    avg_score = round(sum(r.percentage for r in relevant_results) / len(relevant_results), 1) if relevant_results else 0.0

    video_pct = (watched_count / total_videos * 100.0) if total_videos > 0 else 0.0
    exam_pct = (solved_exams / total_exams * 100.0) if total_exams > 0 else 0.0
    if total_videos > 0 and total_exams > 0:
        overall = round((video_pct * 0.4) + (exam_pct * 0.3) + (avg_score * 0.3), 1)
    elif total_videos > 0:
        overall = round((video_pct * 0.6) + (avg_score * 0.4), 1) if relevant_results else round(video_pct, 1)
    elif total_exams > 0:
        overall = round((exam_pct * 0.5) + (avg_score * 0.5), 1) if relevant_results else round(exam_pct, 1)
    else:
        overall = avg_score

    if overall >= 85:
        label, badge_class = "ممتاز", "bg-success"
    elif overall >= 65:
        label, badge_class = "جيد جداً", "bg-info text-dark"
    elif overall >= 50:
        label, badge_class = "جيد", "bg-primary"
    else:
        label, badge_class = "يحتاج متابعة", "bg-warning text-dark"

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


def evaluate_attempt(exam, attempt):
    questions = Question.query.filter_by(exam_id=exam.id).order_by(Question.id.asc()).all()
    total_questions = len(questions)
    try:
        saved = json.loads(attempt.saved_answers_json or "{}")
    except Exception:
        saved = {}

    now = datetime.datetime.utcnow()
    started = attempt.started_at or now
    end_ref = attempt.submitted_at or now
    elapsed_sec = max(0, int((end_ref - started).total_seconds()))
    duration_sec = max(60, int((exam.duration_minutes or 20) * 60))
    remaining_sec = max(0, duration_sec - int((now - started).total_seconds()))

    mins = elapsed_sec // 60
    secs = elapsed_sec % 60
    time_spent_label = f"{mins} دقيقة و {secs} ثانية"

    solved_count = sum(1 for q in questions if saved.get(str(q.id)) in ("A", "B", "C", "D"))
    score = 0
    details = []
    option_labels = lambda q, opt: getattr(q, f"option_{opt.lower()}", "") if opt in ("A", "B", "C", "D") else ""

    for idx, q in enumerate(questions, start=1):
        chosen = saved.get(str(q.id))
        is_ok = chosen == q.correct_option
        if is_ok:
            score += 1
        details.append(
            {
                "number": idx,
                "text": q.question_text,
                "student_option": chosen,
                "student_label": option_labels(q, chosen),
                "correct_option": q.correct_option,
                "correct_label": option_labels(q, q.correct_option),
                "is_correct": is_ok,
            }
        )

    result_ready = True
    available_at_label = ""
    if attempt.status == "submitted" and exam.grading_mode == "delayed" and (exam.grading_delay_hours or 0) > 0:
        sub_at = attempt.submitted_at or now
        avail_at = sub_at + datetime.timedelta(hours=float(exam.grading_delay_hours))
        available_at_label = avail_at.strftime("%Y-%m-%d %H:%M")
        result_ready = now >= avail_at

    return {
        "score": score,
        "total_marks": total_questions,
        "total_questions": total_questions,
        "solved_count": solved_count,
        "time_spent_label": time_spent_label,
        "remaining_seconds": remaining_sec,
        "result_ready": result_ready,
        "available_at_label": available_at_label,
        "details": details,
    }


@app.context_processor
def inject_globals():
    return {
        "developer_credit": DEVELOPER_CREDIT,
        "grades": GRADES,
        "content_sections": CONTENT_SECTIONS,
    }


@app.route("/")
def index():
    settings = get_settings()
    centers = Center.query.all()
    announcements = Announcement.query.order_by(Announcement.id.desc()).limit(5).all()
    return render_template(
        "index.html",
        settings=settings,
        centers=centers,
        announcements=announcements,
        current_student=get_current_student(),
        is_admin=is_admin_logged_in(),
    )


@app.route("/auth", methods=["GET", "POST"])
def auth():
    settings = get_settings()
    mode = request.args.get("mode", "login")
    if request.method == "POST":
        form_mode = request.form.get("mode", mode)
        if form_mode == "register":
            full_name = (request.form.get("full_name") or "").strip()
            phone = (request.form.get("phone") or "").strip()
            parent_phone = (request.form.get("parent_phone") or "").strip()
            governorate = (request.form.get("governorate") or "").strip()
            grade = (request.form.get("grade") or "").strip()
            password = request.form.get("password") or ""

            if not full_name or not phone or not grade or not password:
                flash("يرجى استكمال الاسم ورقم الطالب والصف وكلمة المرور.", "warning")
                return redirect(url_for("auth", mode="register"))

            if User.query.filter_by(phone=phone).first():
                flash("رقم الهاتف مسجل بالفعل.", "danger")
                return redirect(url_for("auth", mode="register"))

            user = User(
                full_name=full_name,
                phone=phone,
                parent_phone=parent_phone,
                governorate=governorate,
                grade=grade,
                password_hash=generate_password_hash(password),
                is_active=False,
            )
            db.session.add(user)
            db.session.commit()
            flash("تم تسجيل حسابك بنجاح، وهو الآن قيد المراجعة من الإدارة.", "info")
            return redirect(url_for("auth", mode="login"))

        identifier = (request.form.get("identifier") or request.form.get("phone") or request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        if identifier == settings.admin_username and check_password_hash(settings.admin_password_hash, password):
            session.clear()
            session["is_admin"] = True
            session["show_login_modal"] = True
            return redirect(url_for("admin_dashboard"))

        student = User.query.filter_by(phone=identifier).first()
        if student and check_password_hash(student.password_hash, password):
            if not student.is_active:
                flash("حسابك قيد المراجعة من الإدارة، يرجى انتظار التفعيل.", "warning")
                return redirect(url_for("auth", mode="login"))
            session.clear()
            session["student_id"] = student.id
            session["show_login_modal"] = True
            return redirect(url_for("student_dashboard"))

        flash("بيانات الدخول غير صحيحة.", "danger")
        return redirect(url_for("auth", mode="login"))

    return render_template("auth.html", settings=settings, mode=mode)


@app.route("/logout")
def logout():
    session.clear()
    flash("تم تسجيل الخروج بنجاح.", "info")
    return redirect(url_for("index"))


@app.route("/student")
@student_required
def student_dashboard():
    settings = get_settings()
    student = get_current_student()
    show_modal = bool(session.pop("show_login_modal", False))

    weeks = Week.query.filter_by(grade=student.grade, is_published=True).order_by(Week.order_num.asc(), Week.id.asc()).all()
    unlocked_ids = {
        row.week_id for row in StudentWeekAccess.query.filter_by(user_id=student.id).all()
    }
    watched_ids = {
        row.content_id for row in VideoProgress.query.filter_by(user_id=student.id, watched=True).all()
    }
    exams = Exam.query.filter_by(grade=student.grade).order_by(Exam.id.desc()).all()
    my_results = ExamResult.query.filter_by(user_id=student.id).order_by(ExamResult.id.desc()).all()
    announcements = Announcement.query.order_by(Announcement.id.desc()).limit(5).all()
    level = compute_student_level(student)

    return render_template(
        "student.html",
        settings=settings,
        student=student,
        weeks=weeks,
        unlocked_ids=unlocked_ids,
        watched_ids=watched_ids,
        exams=exams,
        my_results=my_results,
        announcements=announcements,
        level=level,
        show_login_modal=show_modal,
    )


@app.route("/student/watch/<int:content_id>", methods=["POST"])
@student_required
def mark_watched(content_id):
    student = get_current_student()
    prog = VideoProgress.query.filter_by(user_id=student.id, content_id=content_id).first()
    if not prog:
        prog = VideoProgress(user_id=student.id, content_id=content_id, watched=True)
        db.session.add(prog)
    else:
        prog.watched = True
    db.session.commit()
    flash("تم تسجيل مشاهدة المحتوى بنجاح.", "success")
    return redirect(url_for("student_dashboard"))


@app.route("/student/redeem-code", methods=["POST"])
@student_required
def redeem_code():
    student = get_current_student()
    code_str = (request.form.get("code") or "").strip().upper()
    code_obj = ActivationCode.query.filter_by(code=code_str).first()
    if not code_obj or code_obj.is_used:
        flash("كود التفعيل غير صحيح أو مستخدم من قبل.", "danger")
        return redirect(url_for("student_dashboard"))

    code_obj.is_used = True
    code_obj.used_by_user_id = student.id
    if code_obj.week_id:
        exists = StudentWeekAccess.query.filter_by(user_id=student.id, week_id=code_obj.week_id).first()
        if not exists:
            db.session.add(StudentWeekAccess(user_id=student.id, week_id=code_obj.week_id))
    else:
        for w in Week.query.filter_by(grade=student.grade).all():
            if not StudentWeekAccess.query.filter_by(user_id=student.id, week_id=w.id).first():
                db.session.add(StudentWeekAccess(user_id=student.id, week_id=w.id))

    db.session.commit()
    flash("تم تفعيل الكود بنجاح.", "success")
    return redirect(url_for("student_dashboard"))


@app.route("/exam/<int:exam_id>", methods=["GET"])
def take_exam(exam_id):
    student = get_current_student()
    admin_flag = is_admin_logged_in()
    if not student and not admin_flag:
        flash("يرجى تسجيل الدخول أولاً لفتح الاختبار.", "warning")
        return redirect(url_for("auth", mode="login"))

    settings = get_settings()
    exam = db.get_or_404(Exam, exam_id)
    questions = Question.query.filter_by(exam_id=exam.id).order_by(Question.id.asc()).all()

    attempt = None
    evaluation = None
    saved_answers = {}

    if student:
        attempt = (
            ExamAttempt.query.filter_by(exam_id=exam.id, user_id=student.id)
            .order_by(ExamAttempt.id.desc())
            .first()
        )
        if attempt:
            evaluation = evaluate_attempt(exam, attempt)
            try:
                saved_answers = json.loads(attempt.saved_answers_json or "{}")
            except Exception:
                saved_answers = {}

    return render_template(
        "exam.html",
        settings=settings,
        exam=exam,
        questions=questions,
        total_marks=len(questions),
        attempt=attempt,
        evaluation=evaluation,
        saved_answers=saved_answers,
        is_admin=admin_flag,
        back_url=url_for("admin_dashboard") if admin_flag else url_for("student_dashboard"),
        start_url=url_for("start_exam_attempt", exam_id=exam.id),
        submit_url=url_for("submit_exam_attempt", exam_id=exam.id),
        admin_settings_url=url_for("update_exam_grading_settings", exam_id=exam.id),
    )


@app.route("/exam/<int:exam_id>/start", methods=["POST"])
@student_required
def start_exam_attempt(exam_id):
    student = get_current_student()
    exam = db.get_or_404(Exam, exam_id)
    prev_count = ExamAttempt.query.filter_by(exam_id=exam.id, user_id=student.id).count()
    serial = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
    attempt = ExamAttempt(
        exam_id=exam.id,
        user_id=student.id,
        attempt_number=prev_count + 1,
        serial_code=serial,
        status="in_progress",
        saved_answers_json="{}",
        started_at=datetime.datetime.utcnow(),
    )
    db.session.add(attempt)
    db.session.commit()
    return redirect(url_for("take_exam", exam_id=exam.id))


@app.route("/exam/<int:exam_id>/submit", methods=["POST"])
@student_required
def submit_exam_attempt(exam_id):
    student = get_current_student()
    exam = db.get_or_404(Exam, exam_id)
    attempt = (
        ExamAttempt.query.filter_by(exam_id=exam.id, user_id=student.id, status="in_progress")
        .order_by(ExamAttempt.id.desc())
        .first()
    )
    if not attempt:
        return redirect(url_for("take_exam", exam_id=exam.id))

    questions = Question.query.filter_by(exam_id=exam.id).all()
    answers = {}
    for q in questions:
        val = (request.form.get(f"q_{q.id}") or "").strip().upper()
        if val in ("A", "B", "C", "D"):
            answers[str(q.id)] = val

    attempt.saved_answers_json = json.dumps(answers, ensure_ascii=False)
    action_type = request.form.get("action_type", "submit")

    if action_type == "save_later":
        db.session.commit()
        flash("تم حفظ إجاباتك مؤقتاً، يمكنك استكمال الاختبار لاحقاً.", "info")
        return redirect(url_for("take_exam", exam_id=exam.id))

    attempt.status = "submitted"
    attempt.submitted_at = datetime.datetime.utcnow()

    score = sum(1 for q in questions if answers.get(str(q.id)) == q.correct_option)
    total = len(questions)
    pct = round((score / total) * 100.0, 1) if total > 0 else 0.0

    result = ExamResult(
        exam_id=exam.id,
        user_id=student.id,
        attempt_id=attempt.id,
        score=score,
        total_questions=total,
        percentage=pct,
    )
    db.session.add(result)
    db.session.commit()
    flash("تم تسليم الاختبار بنجاح.", "success")
    return redirect(url_for("take_exam", exam_id=exam.id))


@app.route("/admin")
@admin_required
def admin_dashboard():
    settings = get_settings()
    show_modal = bool(session.pop("show_login_modal", False))
    selected_grade = (request.args.get("grade") or "").strip()

    all_students = User.query.order_by(User.id.desc()).all()
    pending_students = [st for st in all_students if not st.is_active]

    students_data = []
    students_by_grade = {g: [] for g in GRADES}
    for st in all_students:
        lvl = compute_student_level(st)
        row = {"user": st, "level": lvl}
        students_data.append(row)
        if st.grade in students_by_grade:
            students_by_grade[st.grade].append(row)

    all_weeks = Week.query.order_by(Week.order_num.asc(), Week.id.desc()).all()
    weeks = [w for w in all_weeks if (not selected_grade or w.grade == selected_grade)]

    all_exams = Exam.query.order_by(Exam.id.desc()).all()
    exams = [e for e in all_exams if (not selected_grade or e.grade == selected_grade)]
    exams_map = {e.id: e.title for e in all_exams}

    codes_query = ActivationCode.query.order_by(ActivationCode.id.desc())
    if selected_grade:
        codes_query = codes_query.filter_by(grade=selected_grade)
    codes = codes_query.limit(100).all()

    centers = Center.query.order_by(Center.id.desc()).all()
    announcements = Announcement.query.order_by(Announcement.id.desc()).all()
    exam_results = ExamResult.query.order_by(ExamResult.id.desc()).limit(100).all()

    return render_template(
        "admin.html",
        settings=settings,
        show_login_modal=show_modal,
        selected_grade=selected_grade,
        pending_students=pending_students,
        students_data=students_data,
        students_by_grade=students_by_grade,
        all_weeks=all_weeks,
        weeks=weeks,
        all_exams=all_exams,
        exams=exams,
        exams_map=exams_map,
        codes=codes,
        centers=centers,
        announcements=announcements,
        exam_results=exam_results,
    )


@app.route("/admin/student/<int:student_id>/toggle", methods=["POST"])
@admin_required
def toggle_student(student_id):
    st = db.get_or_404(User, student_id)
    st.is_active = not bool(st.is_active)
    db.session.commit()
    flash(f"تم تحديث حالة حساب الطالب ({st.full_name}).", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/settings", methods=["POST"])
@admin_required
def update_settings():
    try:
        s = get_settings()
        s.platform_name = (request.form.get("platform_name") or s.platform_name).strip()
        s.teacher_name = (request.form.get("teacher_name") or s.teacher_name).strip()
        s.teacher_bio = (request.form.get("teacher_bio") or "").strip()
        s.whatsapp_number = (request.form.get("whatsapp_number") or "").strip()
        s.pass_percentage_required = float(request.form.get("pass_percentage_required") or 60.0)
        s.facebook_url = (request.form.get("facebook_url") or "").strip() or None
        s.instagram_url = (request.form.get("instagram_url") or "").strip() or None
        s.tiktok_url = (request.form.get("tiktok_url") or "").strip() or None
        s.youtube_url = (request.form.get("youtube_url") or "").strip() or None

        img_path = save_uploaded_file(request.files.get("teacher_image"), UPLOAD_IMAGES, "/static/uploads/images")
        if img_path:
            s.teacher_image = img_path

        new_user = (request.form.get("new_admin_username") or "").strip()
        new_pass = request.form.get("new_admin_pass") or ""
        if new_user:
            s.admin_username = new_user
        if new_pass:
            s.admin_password_hash = generate_password_hash(new_pass)

        db.session.commit()
        flash("تم حفظ إعدادات المنصة بنجاح.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(f"تعذر حفظ الإعدادات: {exc}", "danger")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/week/add", methods=["POST"])
@admin_required
def add_week():
    try:
        title = (request.form.get("title") or "").strip()
        description = (request.form.get("description") or "").strip()
        grade = (request.form.get("grade") or "").strip()
        order_num = int(request.form.get("order_num") or 1)
        price = int(float(request.form.get("price") or 0))
        is_free = bool(request.form.get("is_free"))

        if not title or not grade:
            flash("يرجى إدخال عنوان الباقة واختيار الصف الدراسي أو كل الصفوف.", "warning")
            return redirect(url_for("admin_dashboard"))

        target_grades = GRADES if grade == "ALL_GRADES" else [grade]
        uploaded_videos = [f for f in request.files.getlist("week_videos") if f and f.filename]
        saved_videos = []
        for idx, vf in enumerate(uploaded_videos, start=1):
            v_path = save_uploaded_file(vf, UPLOAD_VIDEOS, "/static/uploads/videos")
            if v_path:
                saved_videos.append((idx, v_path))

        created_count = 0
        for g_name in target_grades:
            week = Week(
                title=title,
                description=description,
                grade=g_name,
                order_num=order_num,
                price=0 if is_free else price,
                is_free=is_free,
                is_published=True,
            )
            db.session.add(week)
            db.session.flush()
            created_count += 1

            for v_idx, v_path in saved_videos:
                db.session.add(
                    WeekContent(
                        week_id=week.id,
                        title=f"فيديو {v_idx}",
                        section_key="explanation",
                        content_type="video_upload",
                        source_path=v_path,
                        duration_or_notes="مرفوع من الجهاز",
                        order_num=v_idx,
                    )
                )

        db.session.commit()
        if grade == "ALL_GRADES":
            flash(f"تم إضافة ({title}) لجميع الصفوف الدراسية ({created_count} صفوف) بنجاح.", "success")
            return redirect(url_for("admin_dashboard"))

        flash(f"تم إضافة ({title}) لـ ({grade}) بنجاح.", "success")
        return redirect(url_for("admin_dashboard", grade=grade))
    except Exception as exc:
        db.session.rollback()
        flash(f"تعذر إضافة الأسبوع / الباقة: {exc}", "danger")
        return redirect(url_for("admin_dashboard"))


@app.route("/admin/week/<int:week_id>/toggle", methods=["POST"])
@admin_required
def toggle_week(week_id):
    w = db.get_or_404(Week, week_id)
    w.is_published = not bool(w.is_published)
    db.session.commit()
    flash("تم تحديث حالة نشر الأسبوع / الباقة.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/week/<int:week_id>/delete", methods=["POST"])
@admin_required
def delete_week(week_id):
    w = db.get_or_404(Week, week_id)
    db.session.delete(w)
    db.session.commit()
    flash("تم حذف الأسبوع / الباقة.", "info")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/content/add", methods=["POST"])
@admin_required
def add_content():
    try:
        week_id = int(request.form.get("week_id") or 0)
        title = (request.form.get("title") or "").strip()
        section_key = (request.form.get("section_key") or "explanation").strip()
        content_type = (request.form.get("content_type") or "video_link").strip()
        external_link = (request.form.get("external_link") or "").strip()
        duration_or_notes = (request.form.get("duration_or_notes") or "").strip()

        week = db.get_or_404(Week, week_id)
        source_path = external_link or None

        media_file = request.files.get("media_file")
        if media_file and media_file.filename:
            if content_type == "video_upload":
                source_path = save_uploaded_file(media_file, UPLOAD_VIDEOS, "/static/uploads/videos")
            else:
                source_path = save_uploaded_file(media_file, UPLOAD_FILES, "/static/uploads/files")

        item = WeekContent(
            week_id=week.id,
            title=title,
            section_key=section_key,
            content_type=content_type,
            source_path=source_path,
            duration_or_notes=duration_or_notes,
        )
        db.session.add(item)
        db.session.commit()
        flash("تم إضافة المحتوى بنجاح.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(f"تعذر إضافة المحتوى: {exc}", "danger")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/exam/add", methods=["POST"])
@admin_required
def add_exam():
    try:
        title = (request.form.get("title") or "").strip()
        grade = (request.form.get("grade") or "").strip()
        duration_minutes = int(request.form.get("duration_minutes") or 20)
        grading_mode = (request.form.get("grading_mode") or "instant").strip()
        grading_delay_hours = float(request.form.get("grading_delay_hours") or 0.0)

        if not title or not grade:
            flash("يرجى إدخال عنوان الاختبار واختيار الصف.", "warning")
            return redirect(url_for("admin_dashboard"))

        target_grades = GRADES if grade == "ALL_GRADES" else [grade]
        for g_name in target_grades:
            ex = Exam(
                title=title,
                grade=g_name,
                duration_minutes=max(1, duration_minutes),
                grading_mode="delayed" if grading_mode == "delayed" else "instant",
                grading_delay_hours=max(0.0, grading_delay_hours),
            )
            db.session.add(ex)
        db.session.commit()
        flash("تم إنشاء الاختبار بنجاح.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(f"تعذر إنشاء الاختبار: {exc}", "danger")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/exam/<int:exam_id>/grading", methods=["POST"])
@admin_required
def update_exam_grading_settings(exam_id):
    ex = db.get_or_404(Exam, exam_id)
    mode = (request.form.get("grading_mode") or "instant").strip()
    delay_h = float(request.form.get("grading_delay_hours") or 0.0)
    ex.grading_mode = "delayed" if mode == "delayed" else "instant"
    ex.grading_delay_hours = max(0.0, delay_h)
    db.session.commit()
    flash("تم تحديث إعدادات تصحيح الاختبار.", "success")
    return redirect(url_for("take_exam", exam_id=ex.id))


@app.route("/admin/exam/<int:exam_id>/delete", methods=["POST"])
@admin_required
def delete_exam(exam_id):
    ex = db.get_or_404(Exam, exam_id)
    db.session.delete(ex)
    db.session.commit()
    flash("تم حذف الاختبار.", "info")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/question/add", methods=["POST"])
@admin_required
def add_question():
    try:
        exam_id = int(request.form.get("exam_id") or 0)
        db.get_or_404(Exam, exam_id)
        q = Question(
            exam_id=exam_id,
            question_text=(request.form.get("question_text") or "").strip(),
            option_a=(request.form.get("option_a") or "").strip(),
            option_b=(request.form.get("option_b") or "").strip(),
            option_c=(request.form.get("option_c") or "").strip(),
            option_d=(request.form.get("option_d") or "").strip(),
            correct_option=(request.form.get("correct_option") or "A").strip().upper(),
        )
        db.session.add(q)
        db.session.commit()
        flash("تم إضافة السؤال بنجاح.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(f"تعذر إضافة السؤال: {exc}", "danger")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/codes/generate", methods=["POST"])
@admin_required
def generate_codes():
    try:
        grade = (request.form.get("grade") or "").strip()
        week_id_raw = request.form.get("week_id") or ""
        week_id = int(week_id_raw) if week_id_raw.isdigit() else None
        count = min(100, max(1, int(request.form.get("count") or 10)))

        created = 0
        for _ in range(count):
            code_str = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
            if not ActivationCode.query.filter_by(code=code_str).first():
                db.session.add(ActivationCode(code=code_str, grade=grade, week_id=week_id, is_used=False))
                created += 1
        db.session.commit()
        flash(f"تم توليد {created} كود تفعيل بنجاح.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(f"تعذر توليد الأكواد: {exc}", "danger")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/codes/delete-unused", methods=["POST"])
@admin_required
def delete_unused_codes():
    grade = (request.form.get("grade") or "").strip()
    q = ActivationCode.query.filter_by(is_used=False)
    if grade:
        q = q.filter_by(grade=grade)
    q.delete()
    db.session.commit()
    flash("تم حذف الأكواد غير المستخدمة.", "info")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/codes/<int:code_id>/delete", methods=["POST"])
@admin_required
def delete_code(code_id):
    c = db.get_or_404(ActivationCode, code_id)
    db.session.delete(c)
    db.session.commit()
    flash("تم حذف الكود.", "info")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/center/add", methods=["POST"])
@admin_required
def add_center():
    db.session.add(
        Center(
            name=(request.form.get("name") or "").strip(),
            address=(request.form.get("address") or "").strip(),
            schedule_notes=(request.form.get("schedule_notes") or "").strip(),
        )
    )
    db.session.commit()
    flash("تم إضافة المركز بنجاح.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/center/<int:center_id>/delete", methods=["POST"])
@admin_required
def delete_center(center_id):
    c = db.get_or_404(Center, center_id)
    db.session.delete(c)
    db.session.commit()
    flash("تم حذف المركز.", "info")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/announcement/add", methods=["POST"])
@admin_required
def add_announcement():
    db.session.add(
        Announcement(
            title=(request.form.get("title") or "").strip(),
            message=(request.form.get("message") or "").strip(),
        )
    )
    db.session.commit()
    flash("تم نشر التنبيه بنجاح.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/announcement/<int:ann_id>/delete", methods=["POST"])
@admin_required
def delete_announcement(ann_id):
    a = db.get_or_404(Announcement, ann_id)
    db.session.delete(a)
    db.session.commit()
    flash("تم حذف التنبيه.", "info")
    return redirect(url_for("admin_dashboard"))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)