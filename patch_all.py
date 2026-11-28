# -*- coding: utf-8 -*-
"""
patch_all.py - applies all fixes to app.py, templates/student.html, templates/admin.html

Usage (from the project folder that contains app.py and templates/):
    python patch_all.py

- A backup copy (*.bak) is made before any file is changed.
- Each file is changed all-or-nothing: if one anchor is not found, that file is left untouched.
- Safe to run twice (already-patched edits are skipped).
"""
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def find_file(*candidates):
    for c in candidates:
        p = os.path.join(HERE, c)
        if os.path.isfile(p):
            return p
    return None


def read_text(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        raw = f.read()
    crlf = "\r\n" in raw
    return raw.replace("\r\n", "\n"), crlf


def write_text(path, text, crlf):
    if crlf:
        text = text.replace("\n", "\r\n")
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


class Patcher:
    def __init__(self, label, text):
        self.label = label
        self.text = text
        self.errors = []
        self.done = []
        self.skipped = []

    def exact(self, name, old, new, marker):
        if marker in self.text:
            self.skipped.append(name)
            return
        n = self.text.count(old)
        if n != 1:
            self.errors.append("%s: anchor found %d times (expected 1)" % (name, n))
            return
        self.text = self.text.replace(old, new, 1)
        self.done.append(name)

    def regex(self, name, pattern, repl_func, marker, flags=re.S):
        if marker in self.text:
            self.skipped.append(name)
            return
        matches = list(re.finditer(pattern, self.text, flags))
        if len(matches) != 1:
            self.errors.append("%s: pattern matched %d times (expected 1)" % (name, len(matches)))
            return
        m = matches[0]
        self.text = self.text[: m.start()] + repl_func(m) + self.text[m.end():]
        self.done.append(name)

    def insert_before_regex(self, name, pattern, block, marker, flags=re.S):
        def f(m):
            return block + m.group(0)
        self.regex(name, pattern, f, marker, flags)


# ----------------------------------------------------------------------------
# app.py
# ----------------------------------------------------------------------------
HELPERS = '''def safe_media_name(original_name, default_base="media"):
    original_name = original_name or ""
    if "." in original_name:
        base_part, ext = original_name.rsplit(".", 1)
        ext = ext.lower()
    else:
        base_part, ext = original_name, ""
    base = secure_filename(base_part) or default_base
    return f"{base}.{ext}" if ext else base


def guess_content_type(filename, fallback=None):
    guessed, _ = mimetypes.guess_type(filename or "")
    return guessed or fallback or "application/octet-stream"


'''

WEEK_DIRECT = '''        for v_url, v_title in zip(
            request.form.getlist("week_video_urls"),
            request.form.getlist("week_video_titles"),
        ):
            if (v_url or "").strip():
                db.session.add(
                    CourseContent(
                        week_id=week.id,
                        lecture_title="المحاضرة الأولى",
                        title=(v_title or "فيديو شرح"),
                        section_key="explanation",
                        content_type="video_upload",
                        source_path=v_url.strip(),
                    )
                )

'''

SUBMIT_OLD = '''    answers = {}
    for q in questions:
        val = request.form.get(f"q_{q.id}")
        if val in ("A", "B", "C", "D"):
            answers[str(q.id)] = val

    attempt.answers_json = json.dumps(answers, ensure_ascii=False)
    action_type = request.form.get("action_type", "submit")
'''

SUBMIT_NEW = '''    duration_sec = int((exam.duration_minutes or 20) * 60)
    elapsed = (datetime.utcnow() - (attempt.started_at or datetime.utcnow())).total_seconds()
    is_late = elapsed > duration_sec + 120

    if is_late:
        answers = parse_answers_json(attempt.answers_json)
        action_type = "submit"
    else:
        answers = {}
        for q in questions:
            val = request.form.get(f"q_{q.id}")
            if val in ("A", "B", "C", "D"):
                answers[str(q.id)] = val
        attempt.answers_json = json.dumps(answers, ensure_ascii=False)
        action_type = request.form.get("action_type", "submit")
'''


def patch_app(path):
    text, crlf = read_text(path)
    p = Patcher("app.py", text)

    p.exact(
        "import mimetypes",
        "from urllib.parse import quote, urlparse, parse_qs\n",
        "from urllib.parse import quote, urlparse, parse_qs\nimport mimetypes\n",
        "import mimetypes",
    )
    p.exact(
        "media helpers",
        'def upload_to_supabase_with_error(file_storage, folder="uploads"):',
        HELPERS + 'def upload_to_supabase_with_error(file_storage, folder="uploads"):',
        "def safe_media_name",
    )
    p.exact(
        "safe file name in upload",
        'safe_name = secure_filename(file_storage.filename) or "media"',
        "safe_name = safe_media_name(file_storage.filename)",
        "safe_name = safe_media_name(file_storage.filename)",
    )
    p.exact(
        "content type in upload",
        'content_type = file_storage.mimetype or "application/octet-stream"',
        "content_type = guess_content_type(safe_name, file_storage.mimetype)",
        "guess_content_type(safe_name",
    )
    p.exact(
        "signed upload filename",
        'filename = secure_filename((payload.get("filename") or "").strip()) or "video.mp4"',
        'filename = safe_media_name((payload.get("filename") or "").strip(), "video")',
        'safe_media_name((payload.get("filename")',
    )
    p.exact(
        "signed upload content_type",
        '"object_path": object_path,',
        '"object_path": object_path,\n                "content_type": guess_content_type(filename),',
        '"content_type": guess_content_type(filename)',
    )
    p.exact(
        "add_week direct video urls",
        '        db.session.commit()\n        flash("تمت إضافة الأسبوع / الباقة بنجاح.", "success")',
        WEEK_DIRECT + '        db.session.commit()\n        flash("تمت إضافة الأسبوع / الباقة بنجاح.", "success")',
        'request.form.getlist("week_video_urls")',
    )
    p.exact(
        "log silent error in compute_student_level",
        '    except Exception:\n        db.session.rollback()\n        return {\n            "watched_count": 0,',
        '    except Exception:\n        app.logger.exception("compute_student_level failed")\n        db.session.rollback()\n        return {\n            "watched_count": 0,',
        'compute_student_level failed',
    )
    p.exact(
        "server-side exam time check",
        SUBMIT_OLD,
        SUBMIT_NEW,
        "is_late = elapsed > duration_sec + 120",
    )
    p.exact(
        "remove public default dev token",
        'os.environ.get("DEV_UNLOCK_TOKEN", "zizo-dev-2026")',
        'os.environ.get("DEV_UNLOCK_TOKEN", "")',
        'os.environ.get("DEV_UNLOCK_TOKEN", "")',
    )
    return path, p, crlf


# ----------------------------------------------------------------------------
# student.html
# ----------------------------------------------------------------------------
STUDENT_VIDEO_LINK = r"""{% elif item.content_type == 'video_link' and item.source_path %}
                                        {% set embed = format_embed_url(item.source_path) %}
                                        {% set is_yt = ('youtu' in embed) %}
                                        <div class="video-frame-box">
                                          {% if is_yt %}
                                            <iframe id="yt_{{ item.id }}" class="yt-tracked"
                                                    data-content-id="{{ item.id }}"
                                                    data-watch-url="{{ url_for('mark_watched', content_id=item.id) }}"
                                                    src="{{ embed }}{{ '&' if '?' in embed else '?' }}enablejsapi=1"
                                                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                                                    allowfullscreen></iframe>
                                          {% else %}
                                            <iframe src="{{ embed }}"
                                                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                                                    allowfullscreen></iframe>
                                          {% endif %}
                                        </div>
                                        {% if not is_yt and not is_watched %}
                                          <button type="button" class="btn btn-sm btn-outline-success mt-2"
                                                  onclick="reportWatched('{{ item.id }}', '{{ url_for('mark_watched', content_id=item.id) }}')">
                                            <i class="bi bi-check2-circle me-1"></i> أنهيت مشاهدة الفيديو
                                          </button>
                                        {% endif %}"""

STUDENT_JS = r"""const reportedIds = new Set();

    function applyWatchResult(contentId, data) {
      const barEl = document.getElementById("watchBar_" + contentId);
      const badgeEl = document.getElementById("watchBadge_" + contentId);
      const statusEl = document.getElementById("watchStatusText_" + contentId);
      if (barEl) barEl.style.width = "100%";
      if (badgeEl) {
        badgeEl.className = "badge bg-success";
        badgeEl.innerHTML = '<i class="bi bi-check-circle me-1"></i> تم رصد المشاهدة تلقائياً';
      }
      if (statusEl) {
        statusEl.textContent = "تم رصد مشاهدتك للفيديو وتحديث تقدمك الدراسي إلى " + data.overall + "% (" + data.label + ").";
      }
      const set = function (id, txt) { const el = document.getElementById(id); if (el) el.textContent = txt; };
      set("overallProgressDisplay", data.overall + "%");
      set("levelLabelDisplay", data.label);
      set("watchedCountDisplay", data.watched_count);
      set("watchedTotalSubtext", "من إجمالي " + data.total_videos + " فيديو");
      set("activeWeekWatchedLabel", data.watched_count + " من " + data.total_videos);
      set("activeWeekOverallLabel", data.overall + "%");
    }

    function reportWatched(contentId, watchUrl, attempt) {
      attempt = attempt || 0;
      contentId = String(contentId);
      if (reportedIds.has(contentId) || !watchUrl) return;
      reportedIds.add(contentId);
      fetch(watchUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: { "X-Requested-With": "XMLHttpRequest", "Accept": "application/json" }
      })
        .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
        .then(function (d) { if (d && d.ok) { applyWatchResult(contentId, d); } else { throw new Error("bad"); } })
        .catch(function () {
          reportedIds.delete(contentId);
          if (attempt < 3) {
            setTimeout(function () { reportWatched(contentId, watchUrl, attempt + 1); }, 3000 * (attempt + 1));
          }
        });
    }

    window.onYouTubeIframeAPIReady = function () {
      document.querySelectorAll("iframe.yt-tracked").forEach(function (fr) {
        const cid = fr.getAttribute("data-content-id");
        const url = fr.getAttribute("data-watch-url");
        let timer = null;
        new YT.Player(fr, {
          events: {
            onStateChange: function (ev) {
              if (ev.data === YT.PlayerState.PLAYING) {
                if (!timer) {
                  timer = setInterval(function () {
                    const d = ev.target.getDuration();
                    const t = ev.target.getCurrentTime();
                    if (d > 0 && t / d >= 0.8) {
                      clearInterval(timer); timer = null;
                      reportWatched(cid, url);
                    }
                  }, 2000);
                }
              } else if (ev.data === YT.PlayerState.ENDED) {
                reportWatched(cid, url);
              } else if (timer && ev.data !== YT.PlayerState.BUFFERING) {
                clearInterval(timer); timer = null;
              }
            }
          }
        });
      });
    };

    document.addEventListener("DOMContentLoaded", function () {
      document.querySelectorAll("[data-initial-width]").forEach(function (el) {
        const w = el.getAttribute("data-initial-width");
        if (w !== null) { el.style.width = w + "%"; }
      });

      if (window.location.hash === "#subscribeSection" && document.getElementById("tabVodafoneBtn")) {
        openVodafoneTab();
      }

      document.querySelectorAll(".auto-tracked-video").forEach(function (vid) {
        const cid = vid.getAttribute("data-content-id");
        const url = vid.getAttribute("data-watch-url");
        const barEl = document.getElementById("watchBar_" + cid);
        const statusEl = document.getElementById("watchStatusText_" + cid);
        let playTimer = null;

        vid.addEventListener("play", function () {
          if (!playTimer && !reportedIds.has(cid)) {
            playTimer = setTimeout(function () {
              if (!vid.paused) reportWatched(cid, url);
            }, 8000);
          }
        });
        vid.addEventListener("pause", function () {
          if (playTimer) { clearTimeout(playTimer); playTimer = null; }
        });
        vid.addEventListener("timeupdate", function () {
          if (!vid.duration || !isFinite(vid.duration) || vid.duration <= 0) return;
          const pct = Math.min(100, Math.round((vid.currentTime / vid.duration) * 100));
          if (barEl && !reportedIds.has(cid)) barEl.style.width = pct + "%";
          if (pct >= 80) reportWatched(cid, url);
        });
        vid.addEventListener("ended", function () { reportWatched(cid, url); });
        vid.addEventListener("error", function () {
          if (statusEl) {
            statusEl.innerHTML = 'تعذّر تشغيل الفيديو. جرّب متصفح Chrome، أو <a href="' +
              vid.getAttribute("src") + '" target="_blank" rel="noopener" class="text-info">افتحه في تبويب جديد</a>.';
          }
        });
      });

      if (document.querySelector("iframe.yt-tracked")) {
        const s = document.createElement("script");
        s.src = "https://www.youtube.com/iframe_api";
        document.head.appendChild(s);
      }
    });

    """


def patch_student(path):
    text, crlf = read_text(path)
    p = Patcher("student.html", text)

    p.regex(
        "youtube/link videos tracking markup",
        r"\{%\s*elif item\.content_type == 'video_link' and item\.source_path\s*%\}.*?</iframe>\s*</div>",
        lambda m: STUDENT_VIDEO_LINK,
        "class=\"yt-tracked\"",
    )

    # replace the whole DOMContentLoaded block with the new tracking script
    if "const reportedIds = new Set();" in p.text:
        p.skipped.append("watch tracking script")
    else:
        start = p.text.find('document.addEventListener("DOMContentLoaded", function () {')
        end_m = re.search(
            r'setTimeout\(function \(\) \{\s*document\.querySelectorAll\("#flashContainer',
            p.text[start:] if start >= 0 else "",
            re.S,
        )
        if start < 0 or not end_m:
            p.errors.append("watch tracking script: anchors not found")
        else:
            end = start + end_m.start()
            p.text = p.text[:start] + STUDENT_JS + p.text[end:]
            p.done.append("watch tracking script")

    p.regex(
        "hide delayed exam result",
        r"\{% if res %\}(\s*<div class=\"badge bg-info text-dark mb-3\">)",
        lambda m: "{% if res and ex.grading_mode != 'delayed' %}" + m.group(1),
        "res and ex.grading_mode != 'delayed'",
    )
    return path, p, crlf


# ----------------------------------------------------------------------------
# admin.html
# ----------------------------------------------------------------------------
ADMIN_JS = r"""function isVideoFile(f) {
      return !!f && (/^video\//.test(f.type) || /\.(mp4|mov|avi|mkv|webm)$/i.test(f.name));
    }

    async function uploadVideoDirect(file) {
      const r = await fetch("/api/supabase/upload-url", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename: file.name, folder: "lectures" })
      });
      const j = await r.json();
      if (!j.ok) throw new Error(j.error || "تعذر إنشاء رابط الرفع");
      const ct = j.content_type || file.type || "video/mp4";
      const fd = new FormData();
      fd.append("cacheControl", "3600");
      fd.append("", new Blob([file], { type: ct }), file.name);
      const up = await fetch(j.signed_url, { method: "PUT", body: fd });
      if (!up.ok) throw new Error("فشل الرفع (" + up.status + "): " + (await up.text()));
      return j.public_url;
    }

    document.querySelectorAll('form[action$="/admin/contents/add"]').forEach(function (form) {
      form.addEventListener("submit", async function (e) {
        const fileInput = form.querySelector('input[name="media_file"]');
        const f = fileInput && fileInput.files[0];
        if (!isVideoFile(f)) return;
        e.preventDefault();
        const btn = form.querySelector('button[type="submit"]');
        const oldText = btn.textContent;
        btn.disabled = true;
        btn.textContent = "جاري رفع الفيديو... لا تغلق الصفحة";
        try {
          const url = await uploadVideoDirect(f);
          form.querySelector('input[name="external_link"]').value = url;
          form.querySelector('select[name="content_type"]').value = "video_upload";
          fileInput.value = "";
          form.submit();
        } catch (err) {
          alert(err.message);
          btn.disabled = false;
          btn.textContent = oldText;
        }
      });
    });

    document.querySelectorAll('form[action$="/admin/weeks/add"]').forEach(function (form) {
      form.addEventListener("submit", async function (e) {
        const inp = form.querySelector('input[name="week_videos"]');
        const files = inp ? Array.from(inp.files).filter(isVideoFile) : [];
        if (!files.length) return;
        e.preventDefault();
        const btn = form.querySelector('button[type="submit"]');
        const oldText = btn.textContent;
        btn.disabled = true;
        btn.textContent = "جاري رفع الفيديوهات... لا تغلق الصفحة";
        form.querySelectorAll("input[data-direct]").forEach(function (h) { h.remove(); });
        try {
          for (const f of files) {
            const url = await uploadVideoDirect(f);
            [["week_video_urls", url], ["week_video_titles", f.name]].forEach(function (pair) {
              const h = document.createElement("input");
              h.type = "hidden"; h.name = pair[0]; h.value = pair[1];
              h.setAttribute("data-direct", "1");
              form.appendChild(h);
            });
          }
          inp.value = "";
          form.submit();
        } catch (err) {
          alert(err.message);
          btn.disabled = false;
          btn.textContent = oldText;
        }
      });
    });

    """


def patch_admin(path):
    text, crlf = read_text(path)
    p = Patcher("admin.html", text)
    p.insert_before_regex(
        "direct video upload to Supabase",
        r'setTimeout\(function \(\) \{\s*document\.querySelectorAll\("#flashContainer',
        ADMIN_JS,
        "uploadVideoDirect",
    )
    return path, p, crlf


# ----------------------------------------------------------------------------
def main():
    targets = [
        ("app.py", find_file("app.py", "api/index.py", "index.py"), patch_app),
        ("student.html", find_file("templates/student.html", "student.html"), patch_student),
        ("admin.html", find_file("templates/admin.html", "admin.html"), patch_admin),
    ]
    failed = False
    for label, path, fn in targets:
        print("== %s" % label)
        if not path:
            print("   NOT FOUND - put this script in the project folder next to app.py")
            failed = True
            continue
        path, p, crlf = fn(path)
        for d in p.done:
            print("   patched : %s" % d)
        for s in p.skipped:
            print("   already : %s" % s)
        if p.errors:
            failed = True
            for e in p.errors:
                print("   ERROR   : %s" % e)
            print("   -> %s left unchanged" % label)
            continue
        if p.done:
            shutil.copyfile(path, path + ".bak")
            write_text(path, p.text, crlf)
            print("   saved (backup: %s.bak)" % os.path.basename(path))
        else:
            print("   nothing to change")
    print()
    print("DONE WITH ERRORS" if failed else "DONE - all files patched")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()