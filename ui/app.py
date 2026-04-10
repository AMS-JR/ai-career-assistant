# =============================================
# ui.app - Gradio entrypoint
# =============================================
from __future__ import annotations
import html
import os
import re
import tempfile
import traceback
from pathlib import Path
from typing import Any
import gradio as gr
from gradio.themes import GoogleFont, Base
from gradio.themes import sizes as theme_sizes
from career_agents.resume_tailor import tailor_resume_for_job
from career_agents.orchestrator import parse_resume_from_text, run_matching_for_profile
from utils.profile_storage import sync_resume_to_vector_store
from utils.documents import extract_resume_text
from utils.job_relevance_filter import filter_jobs_by_profile_keywords
from utils.settings import get_relax_profile_keyword_job_filter

from ui.job_ui_utils import sort_jobs_by_match
from ui.render_html import (
    STATUS_IDLE_HTML,
    TAILORED_PLACEHOLDER,
    alert_html,
    draft_preview_label_html,
    empty_profile_html,
    header_html,
    job_choices,
    jobs_html,
    profile_html,
    profile_preview_label_html,
    section_html,
    status_busy_html,
)

# Gradio 6+: theme/css must be passed to launch(); `css=` only accepts CSS *text*, not a path.
_CSS_PATH = Path(__file__).resolve().parent / "app.css"

_THEME = Base(
    primary_hue="orange",
    neutral_hue="zinc",
    radius_size=theme_sizes.radius_sm,
    font=GoogleFont("DM Sans"),
    font_mono=GoogleFont("JetBrains Mono"),
)


# ── PDF generation ────────────────────────────────────────────────────────────
def _md_inline(text: str) -> str:
    """Convert inline markdown to ReportLab XML markup with safe escaping."""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r'\*\*\*(.*?)\*\*\*', r'<b><i>\1</i></b>', text)
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<i>\1</i>', text)
    text = re.sub(r'(?<!_)_(?!_)(.+?)(?<!_)_(?!_)', r'<i>\1</i>', text)
    text = re.sub(r'`(.+?)`', lambda m: f'<font face="Courier" size="8">{m.group(1)}</font>', text)
    text = re.sub(r'~~(.+?)~~', r'\1', text)
    return text


def _write_tailored_pdf(markdown: str, job: dict) -> str | None:
    """Render a tailored resume Markdown string as a clean, professional PDF."""
    if not markdown or not markdown.strip():
        return None
    stripped = markdown.strip()
    if stripped.startswith("_") or stripped.startswith("**No draft yet"):
        return None
    if "Tailoring failed" in stripped[:80]:
        return None

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer,
            HRFlowable, KeepTogether,
        )
        from reportlab.lib.styles import ParagraphStyle

        W, H = A4
        LM, RM, TM, BM = 22 * mm, 22 * mm, 20 * mm, 22 * mm

        INK   = colors.HexColor("#111827")
        INK2  = colors.HexColor("#374151")
        INK3  = colors.HexColor("#6b7280")
        GOLD  = colors.HexColor("#b45309")
        RULE  = colors.HexColor("#e5e7eb")
        RULE2 = colors.HexColor("#d1d5db")

        def S(name: str, parent: ParagraphStyle | None = None, **kw: Any) -> ParagraphStyle:
            if parent is not None:
                return ParagraphStyle(name, parent=parent, **kw)
            defaults: dict[str, Any] = {
                "fontName": "Helvetica",
                "fontSize": 9,
                "leading": 13.5,
                "textColor": INK2,
                "spaceBefore": 0,
                "spaceAfter": 0,
            }
            defaults.update(kw)
            return ParagraphStyle(name, **defaults)

        s_name    = S("name",   fontName="Helvetica-Bold", fontSize=22, leading=26,
                      textColor=INK, alignment=TA_CENTER, spaceAfter=2)
        s_contact = S("contact", fontSize=8.5, leading=12.5, textColor=INK3,
                      alignment=TA_CENTER, spaceAfter=8)
        s_h2      = S("h2",    fontName="Helvetica-Bold", fontSize=10.5, leading=14,
                      textColor=INK, spaceBefore=14, spaceAfter=2)
        s_h3      = S("h3",    fontName="Helvetica-Bold", fontSize=9.5, leading=13,
                      textColor=INK, spaceBefore=8, spaceAfter=1)
        s_body    = S("body",  fontSize=9, leading=13.5, textColor=INK2, spaceAfter=3)
        s_bullet  = S("bullet", fontSize=9, leading=13.5, textColor=INK2,
                      leftIndent=14, bulletIndent=5, spaceAfter=2)
        s_sub     = S("sub",   parent=s_bullet, leftIndent=26, bulletIndent=17, fontSize=8.5)
        s_italic  = S("italic", fontSize=8.5, leading=12.5, textColor=INK3, spaceAfter=3)

        co_label = str(job.get("company", ""))[:50]
        jt_label = str(job.get("title",   ""))[:50]
        footer_left = (
            f"Tailored for {jt_label} at {co_label}" if (jt_label and co_label)
            else jt_label or co_label
        )

        def _on_page(canvas, doc):
            canvas.saveState()
            canvas.setStrokeColor(RULE2)
            canvas.setLineWidth(0.35)
            canvas.line(LM, 14 * mm, W - RM, 14 * mm)
            canvas.setFillColor(INK3)
            canvas.setFont("Helvetica", 7)
            if footer_left:
                canvas.drawString(LM, 10 * mm, footer_left)
            canvas.drawRightString(W - RM, 10 * mm, str(doc.page))
            canvas.restoreState()

        stem = _safe_stem(job)
        tmp  = tempfile.NamedTemporaryFile(suffix=".pdf", prefix=f"{stem}_", delete=False)
        tmp.close()

        doc = SimpleDocTemplate(
            tmp.name, pagesize=A4,
            leftMargin=LM, rightMargin=RM, topMargin=TM, bottomMargin=BM,
            title=jt_label or "Tailored Resume",
            author="Career AI",
        )

        story: list = []
        lines = stripped.split("\n")
        idx   = 0

        while idx < len(lines):
            raw = lines[idx].rstrip()

            if not raw:
                story.append(Spacer(1, 4))
                idx += 1
                continue

            # H1 — candidate name
            if raw.startswith("# "):
                text = _md_inline(raw[2:].strip())
                story.append(Paragraph(text, s_name))
                story.append(HRFlowable(
                    width="36%", thickness=1.5, color=GOLD,
                    hAlign="CENTER", spaceAfter=3,
                ))
                idx += 1
                contact_parts: list[str] = []
                while idx < len(lines) and lines[idx].rstrip() and not lines[idx].startswith("#"):
                    contact_parts.append(_md_inline(lines[idx].rstrip()))
                    idx += 1
                if contact_parts:
                    story.append(Paragraph(" &nbsp;&bull;&nbsp; ".join(contact_parts), s_contact))
                continue

            # H2 — section header
            if raw.startswith("## "):
                text = _md_inline(raw[3:].strip()).upper()
                story.append(KeepTogether([
                    Paragraph(text, s_h2),
                    HRFlowable(width="100%", thickness=0.9, color=GOLD,
                               spaceAfter=5, spaceBefore=1),
                ]))
                idx += 1
                continue

            # H3 — job title / sub-section
            if raw.startswith("### "):
                text = _md_inline(raw[4:].strip())
                story.append(Paragraph(text, s_h3))
                idx += 1
                continue

            # Horizontal rule
            if re.match(r'^[-*_]{3,}\s*$', raw):
                story.append(HRFlowable(
                    width="100%", thickness=0.4, color=RULE,
                    spaceBefore=4, spaceAfter=4,
                ))
                idx += 1
                continue

            # Indented bullet
            if re.match(r'^\s{2,}[-*+] ', raw):
                text = _md_inline(re.sub(r'^\s+[-*+] ', '', raw))
                story.append(Paragraph(f"<bullet>&#8211;</bullet>{text}", s_sub))
                idx += 1
                continue

            # Top-level bullet
            if re.match(r'^[-*+] ', raw):
                text = _md_inline(raw[2:].strip())
                story.append(Paragraph(f"<bullet>&bull;</bullet>{text}", s_bullet))
                idx += 1
                continue

            # Italic-only line  (e.g. *Jan 2020 – Present*)
            if re.match(r'^\*[^*].+[^*]\*$', raw) or re.match(r'^_[^_].+[^_]_$', raw):
                story.append(Paragraph(f"<i>{_md_inline(raw[1:-1])}</i>", s_italic))
                idx += 1
                continue

            # Normal paragraph
            text = _md_inline(raw)
            if text.strip():
                story.append(Paragraph(text, s_body))
            idx += 1

        doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
        return tmp.name

    except Exception as exc:
        print(f"[_write_tailored_pdf] Error: {exc}")
        traceback.print_exc()
        return None


# ── Helpers ───────────────────────────────────────────────────────────────────
def _empty_session() -> dict[str, Any]:
    return {
        "profile": None,
        "jobs": [],
        "job_search_ran": False,
        "keyword_filter_no_results": False,
    }


def _safe_stem(job: dict) -> str:
    base = str(job.get("title") or "tailored_resume")
    base = re.sub(r"[^\w\-.]+", "_", base, flags=re.UNICODE).strip("_")[:48] or "tailored_resume"
    return base


# ── App ───────────────────────────────────────────────────────────────────────
def run_app() -> None:

    def _dl_clear() -> Any:
        return gr.update(value=None, visible=False)

    def _disable_ui(msg: str, pct: float | None = None) -> tuple[Any, ...]:
        d = gr.update(interactive=False)
        return (d, d, d, d, d, gr.update(value=status_busy_html(msg, pct)))

    def _enable_ui() -> tuple[Any, ...]:
        e = gr.update(interactive=True)
        return (e, e, e, e, e, gr.update(value=STATUS_IDLE_HTML))

    def _placeholder(sess: dict) -> str:
        return jobs_html(
            [],
            has_profile=bool(sess.get("profile")),
            job_search_ran=bool(sess.get("job_search_ran")),
            keyword_filter_no_results=bool(sess.get("keyword_filter_no_results")),
        )

    # ── Handlers (generators yield progress + status bar updates) ─────────────
    def parse_upload_gen(file_obj: Any, session: dict):
        session = session or _empty_session()
        sk = gr.skip()

        def _fail(msg: str, err: bool = True):
            return (
                alert_html(msg, err=err),
                session,
                _placeholder(session),
                gr.update(choices=[], value=None),
                TAILORED_PLACEHOLDER,
                _dl_clear(),
                STATUS_IDLE_HTML,
            )

        if file_obj is None:
            yield _fail(
                "Choose a <strong>.pdf</strong>, <strong>.docx</strong>, or "
                "<strong>.doc</strong> file first.",
                err=False,
            )
            return

        path = file_obj if isinstance(file_obj, str) else getattr(file_obj, "name", None)
        if not path:
            yield _fail("Could not read the upload path — please try again.")
            return

        yield (
            sk, sk, sk, sk, sk, sk,
            status_busy_html("Reading document…", 22),
        )

        try:
            text = extract_resume_text(path)
        except Exception as e:
            yield _fail(f"<strong>Extraction failed.</strong> {html.escape(str(e))}")
            return

        yield (
            sk, sk, sk, sk, sk, sk,
            status_busy_html("Parsing resume with AI…", 55),
        )

        try:
            profile = parse_resume_from_text(text)
        except Exception:
            tb = html.escape(traceback.format_exc()[-900:])
            yield _fail(
                f"<strong>Parse failed.</strong>"
                f"<pre style='margin:.4rem 0 0;font-size:.7rem;white-space:pre-wrap'>{tb}</pre>"
            )
            return
        if profile is None:
            yield _fail("<strong>Parser returned invalid data.</strong> Try a different file.")
            return

        yield (
            sk, sk, sk, sk, sk, sk,
            status_busy_html("Syncing profile…", 88),
        )

        session = {
            **session,
            "profile": profile,
            "jobs": [],
            "job_search_ran": False,
            "keyword_filter_no_results": False,
        }
        sync_resume_to_vector_store(profile=profile, raw_text=text, filename=path)

        yield (
            profile_html(profile),
            session,
            jobs_html(
                [],
                has_profile=True,
                job_search_ran=False,
                keyword_filter_no_results=False,
            ),
            gr.update(choices=[], value=None),
            TAILORED_PLACEHOLDER,
            _dl_clear(),
            status_busy_html("Profile ready", 100),
        )

    def find_jobs_gen(session: dict):
        session = session or _empty_session()
        sk = gr.skip()

        if not session.get("profile"):
            yield (
                _placeholder(session),
                session,
                gr.update(choices=[], value=None),
                sk,
                sk,
                STATUS_IDLE_HTML,
            )
            return

        yield (
            sk, sk, sk, sk, sk,
            status_busy_html("Querying Remotive and Arbeitnow…", 28),
        )

        try:
            jobs_raw = run_matching_for_profile(session["profile"])
        except Exception as e:
            err = (
                '<div class="ca-jobs-panel">'
                + alert_html(
                    f"<strong>Job search failed.</strong> {html.escape(str(e))}",
                    err=True,
                )
                + "</div>"
            )
            yield (
                err,
                session,
                gr.update(choices=[], value=None),
                sk,
                sk,
                STATUS_IDLE_HTML,
            )
            return

        yield (
            sk, sk, sk, sk, sk,
            status_busy_html("Ranking and filtering matches…", 72),
        )

        jobs_list = jobs_raw if isinstance(jobs_raw, list) else []
        jobs_sorted = sort_jobs_by_match(jobs_list)
        prof = session.get("profile")
        jobs_kw = (
            filter_jobs_by_profile_keywords(jobs_sorted, prof)
            if isinstance(prof, dict)
            else list(jobs_sorted)
        )

        if jobs_kw:
            final, k_miss = jobs_kw, False
        elif not jobs_sorted:
            final, k_miss = [], False
        elif get_relax_profile_keyword_job_filter():
            final, k_miss = jobs_sorted, False
        else:
            final, k_miss = [], True

        session = {
            **session,
            "jobs": final,
            "job_search_ran": True,
            "keyword_filter_no_results": k_miss,
        }
        choices = job_choices(session["jobs"])

        yield (
            jobs_html(
                final,
                has_profile=True,
                job_search_ran=True,
                keyword_filter_no_results=k_miss,
            ),
            session,
            gr.update(choices=choices, value=None),
            TAILORED_PLACEHOLDER,
            _dl_clear(),
            status_busy_html("Search complete", 100),
        )

    def tailor_gen(job_index: str | None, session: dict):
        session = session or _empty_session()
        empty_dl = _dl_clear()
        sk = gr.skip()

        if not session.get("profile") or not session.get("jobs"):
            yield (
                "**Action required:** extract a profile and run a job search first.",
                empty_dl,
                STATUS_IDLE_HTML,
            )
            return
        if not job_index:
            yield (
                "**Select a posting** from the list above.",
                empty_dl,
                STATUS_IDLE_HTML,
            )
            return
        try:
            idx = int(job_index)
        except (TypeError, ValueError):
            yield (
                "**Invalid selection.** Choose a posting from the dropdown.",
                empty_dl,
                STATUS_IDLE_HTML,
            )
            return
        jobs = session["jobs"]
        if idx < 0 or idx >= len(jobs) or not isinstance(jobs[idx], dict):
            yield (
                "**Selection out of date.** Run job search again, then pick a posting.",
                empty_dl,
                STATUS_IDLE_HTML,
            )
            return
        job = jobs[idx]

        yield (
            sk,
            sk,
            status_busy_html("Writing tailored resume text…", 35),
        )

        try:
            out = tailor_resume_for_job(session["profile"], job)
        except Exception as e:
            yield (f"**Tailoring failed:** {e}", empty_dl, STATUS_IDLE_HTML)
            return

        yield (
            sk,
            sk,
            status_busy_html("Building PDF…", 78),
        )

        path = _write_tailored_pdf(out, job)
        if path:
            yield (
                out,
                gr.update(value=path, visible=True),
                status_busy_html("PDF ready", 100),
            )
        else:
            yield (
                out,
                empty_dl,
                status_busy_html("Draft ready (PDF unavailable)", 100),
            )

    def clear_session() -> tuple:
        s = _empty_session()
        return (
            empty_profile_html(), s,
            jobs_html([], has_profile=False, job_search_ran=False, keyword_filter_no_results=False),
            gr.update(choices=[], value=None),
            TAILORED_PLACEHOLDER, _dl_clear(), STATUS_IDLE_HTML,
        )

    # ── Layout ────────────────────────────────────────────────────────────────
    with gr.Blocks(
        title="Career Assistant",
        elem_classes=["ca-root"],
    ) as demo:

        gr.HTML(header_html())
        status_bar    = gr.HTML(value=STATUS_IDLE_HTML, elem_classes=["ca-status-wrap"])
        session_state = gr.State(_empty_session())

        with gr.Column(elem_classes=["ca-body"]):
            with gr.Row(elem_classes=["ca-row"], equal_height=False):

                # ── Left: Resume ───────────────────────────────────────────
                with gr.Column(scale=4, min_width=270, elem_classes=["ca-panel"]):
                    gr.HTML(section_html(1, "Resume & profile", "Upload PDF or Word, then extract structured data for matching."))
                    with gr.Group(elem_classes=["ca-group"]):
                        upload = gr.File(
                            label="Resume file",
                            file_types=[".pdf", ".docx", ".doc"],
                            type="filepath",
                            elem_classes=["ca-upload"],
                        )
                        parse_btn = gr.Button("Extract profile", variant="primary", size="sm")
                    gr.HTML(profile_preview_label_html())
                    profile_panel = gr.HTML(value=empty_profile_html())

                # ── Right: Opportunities + Tailoring ──────────────────────
                with gr.Column(scale=8, min_width=360, elem_classes=["ca-panel"]):
                    gr.HTML(section_html(2, "Job matches", "Query Remotive and Arbeitnow; listings are scored to your profile."))
                    with gr.Group(elem_classes=["ca-group"]):
                        find_btn = gr.Button("Search jobs", variant="primary", size="sm")
                    jobs_display = gr.HTML(
                        value=jobs_html(
                            [], has_profile=False,
                            job_search_ran=False, keyword_filter_no_results=False,
                        )
                    )

                    gr.HTML(section_html(3, "Tailored application", "Choose a posting, generate a draft, and download a PDF."))
                    with gr.Group(elem_classes=["ca-group"]):
                        job_select = gr.Dropdown(
                            label="Select posting",
                            info="Best match first. Regenerate after each new search.",
                            choices=[], interactive=True,
                            allow_custom_value=False,
                            elem_classes=["ca-drop"],
                        )
                        tailor_btn = gr.Button("Generate tailored PDF", variant="primary", size="sm")

                    with gr.Column(elem_classes=["ca-draft"]):
                        gr.HTML(draft_preview_label_html())
                        tailored_md = gr.Markdown(
                            TAILORED_PLACEHOLDER,
                            elem_classes=["ca-draft-body", "prose"],
                        )
                        tailored_download = gr.DownloadButton(
                            "Download .pdf",
                            variant="secondary",
                            size="sm",
                            visible=False,
                            elem_classes=["ca-dl"],
                        )

            with gr.Row(elem_classes=["ca-footer"]):
                clear_btn = gr.Button("Clear session", variant="secondary", size="sm")

        # ── Event wiring ──────────────────────────────────────────────────
        _work = [parse_btn, find_btn, tailor_btn, clear_btn, job_select, status_bar]

        parse_btn.click(
            lambda: _disable_ui("Starting…", None),
            inputs=[],
            outputs=_work,
            show_progress="hidden",
        ).then(
            parse_upload_gen,
            inputs=[upload, session_state],
            outputs=[
                profile_panel,
                session_state,
                jobs_display,
                job_select,
                tailored_md,
                tailored_download,
                status_bar,
            ],
            show_progress="hidden",
        ).then(
            _enable_ui,
            inputs=[],
            outputs=_work,
            show_progress="hidden",
        )

        find_btn.click(
            lambda: _disable_ui("Starting…", None),
            inputs=[],
            outputs=_work,
            show_progress="hidden",
        ).then(
            find_jobs_gen,
            inputs=[session_state],
            outputs=[
                jobs_display,
                session_state,
                job_select,
                tailored_md,
                tailored_download,
                status_bar,
            ],
            show_progress="hidden",
        ).then(
            _enable_ui,
            inputs=[],
            outputs=_work,
            show_progress="hidden",
        )

        tailor_btn.click(
            lambda: _disable_ui("Starting…", None),
            inputs=[],
            outputs=_work,
            show_progress="hidden",
        ).then(
            tailor_gen,
            inputs=[job_select, session_state],
            outputs=[tailored_md, tailored_download, status_bar],
            show_progress="hidden",
        ).then(
            _enable_ui,
            inputs=[],
            outputs=_work,
            show_progress="hidden",
        )

        clear_btn.click(
            clear_session, inputs=[],
            outputs=[
                profile_panel, session_state, jobs_display, job_select,
                tailored_md, tailored_download, status_bar,
            ],
            show_progress="hidden",
        )

    demo.launch(footer_links=[], theme=_THEME, css_paths=_CSS_PATH)