import os
import uuid
import random
import string
from datetime import datetime
from functools import wraps
from urllib.parse import quote
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = (os.environ.get("SECRET_KEY") or "ahmed_gamal_math_platform_2026_zizo").strip()

# قاعدة بيانات تدعم Supabase PostgreSQL في الإنتاج و SQLite محلياً
raw_db_url = (os.environ.get("DATABASE_URL") or "sqlite:///ahmed_gamal_math_v1.db").strip()
if raw_db_url.startswith("postgres://"):
    raw_db_url = raw_db_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = raw_db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
    "pool_size": 5,
    "max_overflow": 5,
}
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024

if os.environ.get("VERCEL"):
    BASE_UPLOAD_DIR = "/tmp/uploads"
else:
    BASE_UPLOAD_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), "static", "uploads")

UPLOAD_VIDEOS = os.path.join(BASE_UPLOAD_DIR, "videos")
UPLOAD_FILES = os.path.join(BASE_UPLOAD_DIR, "files")
UPLOAD_IMAGES = os.path.join(BASE_UPLOAD_DIR, "images")

for folder in [UPLOAD_VIDEOS, UPLOAD_FILES, UPLOAD_IMAGES]:
    os.makedirs(folder, exist_ok=True)

db = SQLAlchemy(app)

GRADES = [
    "الصف الأول الإعدادي",
    "الصف الثاني الإعدادي",
    "الصف الثالث الإعدادي",
    "الصف الأول الثانوي",
    "الصف الثاني الثانوي",
    "الصف الثالث الثانوي",
]


# ===================== نماذج قاعدة البيانات =====================

class PlatformSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    platform_name = db.Column(db.String(150), default="منصة مستر أحمد جمال للرياضيات")
    teacher_name = db.Column(db.String(150), default="مستر / أحمد جمال")
    teacher_bio = db.Column(
        db.Text,
        default="شرح مبسط ومنهجي للرياضيات للمرحلتين الإعدادية والثانوية، تدريب مكثف على أفكار الامتحانات، وتقييم تلقائي لمستوى الطالب ومتابعة مستمرة مع ولي الأمر."
    )
    whatsapp_number = db.Column(db.String(30), default="01000000000")
    teacher_image = db.Column(db.String(300), default="")
    auto_activate_students = db.Column(db.Boolean, default=False)


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
    role = db.Column(db.String(20), default="student")  # admin أو student
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
    is_published = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    contents = db.relationship("WeekContent", backref="week", cascade="all, delete-orphan", order_by="WeekContent.order_num")
    exams = db.relationship("Exam", backref="week", cascade="all, delete-orphan")


class WeekContent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    week_id = db.Column(db.Integer, db.ForeignKey("week.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content_type = db.Column(db.String(30), nullable=False)  # video_upload, video_link, file_upload, file_link
    source_path = db.Column(db.String(500), nullable=False)
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
    correct_option = db.Column(db.String(5), nullable=False)  # A, B, C, D


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


# ===================== دوال مساعدة ومحرك المستوى التلقائي =====================

def get_settings():
    try:
        settings = PlatformSettings.query.first()
        if not settings:
            settings = PlatformSettings()
            db.session.add(settings)
            db.session.commit()
        return settings
    except Exception:
        db.session.rollback()
        return PlatformSettings()


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


def evaluate_student_level(student):
    """حساب مستوى الطالب تلقائياً من مشاهدة الفيديوهات وحل الامتحانات ودرجاته"""
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
    student_results = ExamResult.query.filter_by(user_id=student.id).all()

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
        badge_class = "bg-warning text-dark"
    elif overall >= 70:
        label = "جيد جداً"
        badge_class = "bg-info text-dark"
    elif overall >= 50:
        label = "جيد"
        badge_class = "bg-success"
    else:
        label = "يحتاج متابعة"
        badge_class = "bg-danger"

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
        "all_videos_done": (total_videos == 0) or (watched_count >= total_videos),
        "all_exams_done": (total_exams == 0) or (solved_count >= total_exams),
    }


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("يرجى تسجيل الدخول أولاً.", "warning")
            return redirect(url_for("auth"))
        user = User.query.get(session["user_id"])
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
            flash("سجل دخولك بحساب المدرس أولاً.", "warning")
            return redirect(url_for("auth"))
        user = User.query.get(session["user_id"])
        if not user or user.role != "admin":
            flash("هذا القسم مخصص للمدرس فقط.", "danger")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated


@app.context_processor
def inject_globals():
    current_user = None
    if "user_id" in session:
        try:
            current_user = User.query.get(session["user_id"])
        except Exception:
            db.session.rollback()
            current_user = None
    return dict(
        settings=get_settings(),
        current_user=current_user,
        grades=GRADES,
        clean_wa_phone=clean_wa_phone,
        quote=quote
    )


# ===================== المسارات العامة والمصادقة =====================

@app.route("/")
def index():
    selected_grade = request.args.get("grade", "").strip()
    weeks_query = Week.query.filter_by(is_published=True)
    if selected_grade:
        weeks_query = weeks_query.filter_by(grade=selected_grade)
    weeks = weeks_query.order_by(Week.order_num.asc()).all()

    grade_counts = {g: User.query.filter_by(role="student", grade=g).count() for g in GRADES}
    students_count = User.query.filter_by(role="student").count()
    videos_count = WeekContent.query.filter(WeekContent.content_type.like("video%")).count()
    exams_count = Exam.query.count()

    return render_template(
        "index.html",
        weeks=weeks,
        selected_grade=selected_grade,
        grade_counts=grade_counts,
        students_count=students_count,
        videos_count=videos_count,
        exams_count=exams_count
    )


@app.route("/auth", methods=["GET", "POST"])
def auth():
    if request.method == "POST":
        action = request.form.get("action")

        if action == "login":
            login_id = (request.form.get("login_id") or request.form.get("phone") or "").strip()
            password = request.form.get("password", "")
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
                return redirect(url_for("admin_dashboard" if user.role == "admin" else "student_dashboard"))
            else:
                flash("بيانات الدخول غير صحيحة.", "danger")

        elif action == "register":
            full_name = request.form.get("full_name", "").strip()
            phone = request.form.get("phone", "").strip()
            parent_name = request.form.get("parent_name", "").strip()
            parent_phone = request.form.get("parent_phone", "").strip()
            governorate = request.form.get("governorate", "الدقهلية").strip()
            grade = request.form.get("grade", "")
            password = request.form.get("password", "")

            if not all([full_name, phone, parent_name, parent_phone, grade, password]):
                flash("يرجى إدخال الاسم الكامل، رقم الطالب، اسم ولي الأمر، رقم ولي الأمر، الصف الدراسي، وكلمة المرور.", "danger")
                return redirect(url_for("auth"))

            if phone == parent_phone:
                flash("رقم هاتف ولي الأمر يجب أن يكون مختلفاً عن رقم هاتف الطالب.", "warning")
                return redirect(url_for("auth"))

            if User.query.filter_by(phone=phone).first():
                flash("رقم هاتف الطالب مسجل بالفعل، يمكنك تسجيل الدخول مباشرة.", "warning")
                return redirect(url_for("auth"))

            settings = get_settings()
            token = uuid.uuid4().hex
            new_user = User(
                full_name=full_name,
                phone=phone,
                parent_name=parent_name,
                parent_phone=parent_phone,
                governorate=governorate,
                grade=grade,
                password_hash=generate_password_hash(password),
                role="student",
                is_active=settings.auto_activate_students,
                session_token=token
            )
            db.session.add(new_user)
            db.session.commit()

            session["user_id"] = new_user.id
            session["session_token"] = token
            flash("تم إنشاء حسابك بنجاح! مرحباً بك في منصة مستر أحمد جمال.", "success")
            return redirect(url_for("student_dashboard"))

    return render_template("auth.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("تم تسجيل الخروج بنجاح.", "info")
    return redirect(url_for("index"))


# ===================== لوحة الطالب وتحديد المستوى التلقائي =====================

@app.route("/student")
@login_required
def student_dashboard():
    user = User.query.get(session["user_id"])
    if user.role == "admin":
        return redirect(url_for("admin_dashboard"))

    weeks = Week.query.filter_by(grade=user.grade, is_published=True).order_by(Week.order_num.asc()).all()
    unlocked_ids = {e.week_id for e in Enrollment.query.filter_by(user_id=user.id).all()}
    watched_ids = {p.content_id for p in VideoProgress.query.filter_by(user_id=user.id).all()}

    selected_week_id = request.args.get("week_id", type=int)
    active_week = None
    can_access = False

    if selected_week_id:
        active_week = Week.query.get_or_404(selected_week_id)
        if active_week.is_free or user.is_active or (active_week.id in unlocked_ids):
            can_access = True

    exams = Exam.query.filter_by(grade=user.grade).order_by(Exam.created_at.desc()).all()
    results = ExamResult.query.filter_by(user_id=user.id).order_by(ExamResult.submitted_at.desc()).all()
    results_by_exam = {r.exam_id: r for r in results}
    level_info = evaluate_student_level(user)

    return render_template(
        "student.html",
        user=user,
        weeks=weeks,
        unlocked_ids=unlocked_ids,
        watched_ids=watched_ids,
        active_week=active_week,
        can_access=can_access,
        exams=exams,
        results=results,
        results_by_exam=results_by_exam,
        level_info=level_info,
        format_embed_url=format_embed_url
    )


@app.route("/student/watch/<int:content_id>", methods=["POST"])
@login_required
def mark_watched(content_id):
    user = User.query.get(session["user_id"])
    content = WeekContent.query.get_or_404(content_id)
    existing = VideoProgress.query.filter_by(user_id=user.id, content_id=content.id).first()
    if not existing:
        db.session.add(VideoProgress(user_id=user.id, content_id=content.id))
        db.session.commit()
    flash(f"تم تسجيل مشاهدة ({content.title}) وتحديث مستواك تلقائياً.", "success")
    return redirect(url_for("student_dashboard", week_id=content.week_id))


@app.route("/student/redeem", methods=["POST"])
@login_required
def redeem_code():
    user = User.query.get(session["user_id"])
    code_str = request.form.get("code", "").strip().upper()
    code_obj = AccessCode.query.filter_by(code=code_str, is_used=False).first()

    if not code_obj:
        flash("الكود غير صحيح أو تم استخدامه من قبل.", "danger")
        return redirect(url_for("student_dashboard"))

    if code_obj.grade != user.grade:
        flash(f"هذا الكود خاص بـ ({code_obj.grade}) وليس بصفك الدراسي.", "warning")
        return redirect(url_for("student_dashboard"))

    code_obj.is_used = True
    code_obj.used_by_id = user.id
    code_obj.used_at = datetime.utcnow()

    if code_obj.week_id:
        exists = Enrollment.query.filter_by(user_id=user.id, week_id=code_obj.week_id).first()
        if not exists:
            db.session.add(Enrollment(user_id=user.id, week_id=code_obj.week_id))
        flash("تم فتح الأسبوع بنجاح!", "success")
    else:
        user.is_active = True
        flash("تم تفعيل اشتراكك الكامل بنجاح!", "success")

    db.session.commit()
    return redirect(url_for("student_dashboard"))


@app.route("/exam/<int:exam_id>", methods=["GET", "POST"])
@login_required
def take_exam(exam_id):
    user = User.query.get(session["user_id"])
    exam = Exam.query.get_or_404(exam_id)

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


# ===================== لوحة تحكم المدرس المتقسمة بالصفوف =====================

@app.route("/admin")
@admin_required
def admin_dashboard():
    selected_grade = request.args.get("grade", "").strip()

    grade_summary = []
    for g in GRADES:
        g_students = User.query.filter_by(role="student", grade=g).all()
        g_weeks_count = Week.query.filter_by(grade=g).count()
        g_exams_count = Exam.query.filter_by(grade=g).count()
        avg_lvl = round(sum(evaluate_student_level(s)["overall"] for s in g_students) / len(g_students), 1) if g_students else 0.0
        grade_summary.append({
            "grade": g,
            "students_count": len(g_students),
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

    weeks = weeks_query.order_by(Week.grade.asc(), Week.order_num.asc()).all()
    exams = exams_query.order_by(Exam.created_at.desc()).all()
    codes = AccessCode.query.order_by(AccessCode.created_at.desc()).limit(50).all()

    results_query = ExamResult.query.join(User)
    if selected_grade:
        results_query = results_query.filter(User.grade == selected_grade)
    exam_results = results_query.order_by(ExamResult.submitted_at.desc()).all()

    return render_template(
        "admin.html",
        selected_grade=selected_grade,
        grade_summary=grade_summary,
        students_data=students_data,
        weeks=weeks,
        exams=exams,
        codes=codes,
        exam_results=exam_results
    )


@app.route("/admin/settings", methods=["POST"])
@admin_required
def update_settings():
    settings = get_settings()
    settings.platform_name = request.form.get("platform_name", settings.platform_name)
    settings.teacher_name = request.form.get("teacher_name", settings.teacher_name)
    settings.teacher_bio = request.form.get("teacher_bio", settings.teacher_bio)
    settings.whatsapp_number = request.form.get("whatsapp_number", settings.whatsapp_number)
    settings.auto_activate_students = True if request.form.get("auto_activate_students") else False

    img = request.files.get("teacher_image")
    if img and img.filename:
        settings.teacher_image = save_uploaded_file(img, UPLOAD_IMAGES, "/static/uploads/images")

    new_admin_pass = request.form.get("new_admin_pass", "").strip()
    if new_admin_pass:
        admin_user = User.query.get(session["user_id"])
        admin_user.password_hash = generate_password_hash(new_admin_pass)

    db.session.commit()
    flash("تم حفظ إعدادات المنصة بنجاح.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/week/add", methods=["POST"])
@admin_required
def add_week():
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    grade = request.form.get("grade", "")
    order_num = request.form.get("order_num", 1, type=int)
    price = request.form.get("price", 50, type=int)
    is_free = True if request.form.get("is_free") else False

    cover_path = save_uploaded_file(request.files.get("cover_image"), UPLOAD_IMAGES, "/static/uploads/images")

    week = Week(
        title=title,
        description=description,
        grade=grade,
        order_num=order_num,
        price=price,
        is_free=is_free,
        cover_image=cover_path
    )
    db.session.add(week)
    db.session.commit()
    flash(f"تم إضافة ({title}) لـ ({grade}) بنجاح.", "success")
    return redirect(url_for("admin_dashboard", grade=grade))


@app.route("/admin/week/toggle/<int:week_id>", methods=["POST"])
@admin_required
def toggle_week(week_id):
    week = Week.query.get_or_404(week_id)
    week.is_published = not week.is_published
    db.session.commit()
    flash("تم تحديث حالة نشر الدرس/الأسبوع.", "success")
    return redirect(url_for("admin_dashboard", grade=week.grade))


@app.route("/admin/week/delete/<int:week_id>", methods=["POST"])
@admin_required
def delete_week(week_id):
    week = Week.query.get_or_404(week_id)
    g = week.grade
    db.session.delete(week)
    db.session.commit()
    flash("تم حذف الدرس/الأسبوع ومحتوياته.", "info")
    return redirect(url_for("admin_dashboard", grade=g))


@app.route("/admin/content/add", methods=["POST"])
@admin_required
def add_content():
    week_id = request.form.get("week_id", type=int)
    week = Week.query.get_or_404(week_id)
    title = request.form.get("title", "").strip()
    content_type = request.form.get("content_type", "")
    duration_or_notes = request.form.get("duration_or_notes", "").strip()
    order_num = request.form.get("order_num", 1, type=int)

    source_path = ""
    if content_type == "video_upload":
        source_path = save_uploaded_file(request.files.get("media_file"), UPLOAD_VIDEOS, "/static/uploads/videos")
    elif content_type == "file_upload":
        source_path = save_uploaded_file(request.files.get("media_file"), UPLOAD_FILES, "/static/uploads/files")
    else:
        source_path = request.form.get("external_link", "").strip()

    if not source_path:
        flash("يرجى رفع الملف أو إدخال الرابط بشكل صحيح.", "danger")
        return redirect(url_for("admin_dashboard", grade=week.grade))

    content = WeekContent(
        week_id=week_id,
        title=title,
        content_type=content_type,
        source_path=source_path,
        duration_or_notes=duration_or_notes,
        order_num=order_num
    )
    db.session.add(content)
    db.session.commit()
    flash("تم إضافة المحتوى بنجاح.", "success")
    return redirect(url_for("admin_dashboard", grade=week.grade))


@app.route("/admin/content/delete/<int:content_id>", methods=["POST"])
@admin_required
def delete_content(content_id):
    content = WeekContent.query.get_or_404(content_id)
    g = content.week.grade if content.week else ""
    db.session.delete(content)
    db.session.commit()
    flash("تم حذف المحتوى.", "info")
    return redirect(url_for("admin_dashboard", grade=g))


@app.route("/admin/exam/add", methods=["POST"])
@admin_required
def add_exam():
    title = request.form.get("title", "").strip()
    grade = request.form.get("grade", "")
    week_id = request.form.get("week_id", type=int)
    duration_minutes = request.form.get("duration_minutes", 20, type=int)

    exam = Exam(
        title=title,
        grade=grade,
        week_id=week_id if week_id and week_id > 0 else None,
        duration_minutes=duration_minutes
    )
    db.session.add(exam)
    db.session.commit()
    flash(f"تم إنشاء الامتحان ({title}) لـ ({grade}). أضف أسئلته الآن.", "success")
    return redirect(url_for("admin_dashboard", grade=grade))


@app.route("/admin/exam/question/add", methods=["POST"])
@admin_required
def add_question():
    exam_id = request.form.get("exam_id", type=int)
    exam = Exam.query.get_or_404(exam_id)
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
        flash("تم إضافة السؤال للامتحان.", "success")
    return redirect(url_for("admin_dashboard", grade=exam.grade))


@app.route("/admin/exam/delete/<int:exam_id>", methods=["POST"])
@admin_required
def delete_exam(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    g = exam.grade
    db.session.delete(exam)
    db.session.commit()
    flash("تم حذف الامتحان.", "info")
    return redirect(url_for("admin_dashboard", grade=g))


@app.route("/admin/student/toggle/<int:student_id>", methods=["POST"])
@admin_required
def toggle_student(student_id):
    student = User.query.get_or_404(student_id)
    student.is_active = not student.is_active
    db.session.commit()
    flash(f"تم تحديث حالة الطالب {student.full_name}.", "success")
    return redirect(url_for("admin_dashboard", grade=student.grade))


@app.route("/admin/codes/generate", methods=["POST"])
@admin_required
def generate_codes():
    grade = request.form.get("grade", "")
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


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template("index.html", weeks=[], selected_grade="", grade_counts={g: 0 for g in GRADES}, students_count=0, videos_count=0, exams_count=0), 500


# ===================== تهيئة قاعدة البيانات وحساب المدرس لـ Vercel و Supabase =====================

_db_initialized = False


def init_db():
    global _db_initialized
    if _db_initialized:
        return
    try:
        db.create_all()
        settings = PlatformSettings.query.first()
        if not settings:
            db.session.add(PlatformSettings())
            db.session.commit()
        if not User.query.filter_by(role="admin").first():
            admin = User(
                username="Mr_Ahmed_Gamal_Math2026",
                full_name="مستر / أحمد جمال",
                phone="01099887766",
                password_hash=generate_password_hash("M@th#Gamal$2026!Zizo"),
                role="admin",
                is_active=True
            )
            db.session.add(admin)
            db.session.commit()
        _db_initialized = True
    except Exception as exc:
        db.session.rollback()
        print("Database initialization error:", exc)


@app.before_request
def ensure_db_ready():
    init_db()


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
