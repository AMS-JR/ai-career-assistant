# =============================================
# career_assistant.ui.render_html — load templates from ui/html/
# =============================================

from __future__ import annotations

import html as html_module
import re
from pathlib import Path
from typing import Any
from string import Template

from career_assistant.ui.job_ui_utils import fmt_pct, sort_jobs_by_match
from career_assistant.utils.profile_storage import validate_profile_backend
from career_assistant.utils.settings import (
    ProfileBackend,
    get_openai_vector_store_id,
    get_profile_backend,
)

_HTML_DIR = Path(__file__).resolve().parent / "html"

TAILORED_PLACEHOLDER = "**No draft yet.** Select a posting above, then choose **Generate tailored resume** to build a PDF."
STATUS_IDLE_HTML = '<span class="ca-idle-state"></span>'


def _template(name: str) -> Template:
    """Read from disk each call so edits to ``html/*.html`` apply without restarting."""
    path = _HTML_DIR / name
    return Template(path.read_text(encoding="utf-8"))


def static_fragment(name: str) -> str:
    """Load a small HTML file with no substitutions (e.g. labels)."""
    return (_HTML_DIR / name).read_text(encoding="utf-8")


def _summary_body_html(raw: str) -> str:
    """Turn summary text into spaced paragraphs; single newlines become line breaks."""
    text = (raw or "").strip() or "No summary extracted."
    blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
    if not blocks:
        blocks = [text]
    out: list[str] = []
    for block in blocks:
        esc = html_module.escape(block)
        esc = esc.replace("\n", "<br />")
        out.append(f'<p class="ca-psummary-p">{esc}</p>')
    return "\n".join(out)


def status_busy_html(message: str, pct: float | None = None) -> str:
    """Hairline progress bar with CSS shimmer; determinate width updates from yielded pct."""
    esc = html_module.escape(message)
    if pct is not None:
        p = int(round(max(0.0, min(100.0, float(pct)))))
        pct_el = f'<span class="ca-pbar-pct" aria-valuenow="{p}">{p}%</span>'
        fill = (
            f'<div class="ca-pbar-fill ca-pbar-fill--value" '
            f'style="--pbar-pct:{p}%;" role="progressbar" '
            f'aria-valuenow="{p}" aria-valuemin="0" aria-valuemax="100"></div>'
        )
    else:
        pct_el = '<span class="ca-pbar-pct ca-pbar-pct--wait" aria-hidden="true"></span>'
        fill = '<div class="ca-pbar-fill ca-pbar-fill--flow" aria-hidden="true"></div>'
    return (
        f'<div class="ca-pbar ca-pbar--active" role="status" aria-live="polite">'
        f'<div class="ca-pbar-row">'
        f'<span class="ca-pbar-label">{esc}</span>{pct_el}'
        f"</div>"
        f'<div class="ca-pbar-track">{fill}</div>'
        f"</div>"
    )


def alert_html(msg: str, *, err: bool) -> str:
    alert_class = "ca-alert ca-alert-err" if err else "ca-alert ca-alert-info"
    return _template("alert.html").substitute(
        alert_class=alert_class,
        message=msg,
    )


def _initials(name: str) -> str:
    parts = [p for p in re.split(r"\s+", name.strip()) if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _company_ch(company: str) -> str:
    for ch in str(company or ""):
        if ch.isalnum():
            return html_module.escape(ch.upper())
    return "?"


def _fallback_title(profile: dict) -> str:
    for key in ("title", "headline", "current_role"):
        t = profile.get(key)
        if isinstance(t, str) and t.strip():
            return t.strip()
    ex = profile.get("experience")
    if isinstance(ex, list) and ex:
        first = ex[0]
        if isinstance(first, dict):
            role = first.get("role")
            if isinstance(role, str) and role.strip():
                return role.strip()
    return "—"


def _format_years(profile: dict) -> str:
    y = profile.get("years_of_experience")
    if y is None or y == "":
        return "—"
    if isinstance(y, (int, float)):
        n = int(y)
        return f"{n} yr{'s' if n != 1 else ''}"
    return str(y).strip()


def empty_profile_html() -> str:
    return static_fragment("empty_profile.html")


def _normalize_skills(skills: list[Any]) -> list[str]:
    """Split comma/semicolon/pipe blobs into separate chips; dedupe case-insensitively."""
    pieces: list[str] = []
    for s in skills:
        if s is None:
            continue
        t = str(s).strip()
        if not t:
            continue
        if re.search(r"[,;|]", t):
            for part in re.split(r"[,;|]+", t):
                p = part.strip()
                if p:
                    pieces.append(p)
        else:
            pieces.append(t)
    seen: set[str] = set()
    out: list[str] = []
    for x in pieces:
        k = x.casefold()
        if k not in seen:
            seen.add(k)
            out.append(x)
    return out


def profile_html(profile: dict) -> str:
    name = html_module.escape(str(profile.get("name") or "—"))
    role = html_module.escape(_fallback_title(profile))
    years = html_module.escape(_format_years(profile))
    summary = _summary_body_html(str(profile.get("summary") or ""))
    skills_raw = profile.get("skills") or []
    if not isinstance(skills_raw, list):
        skills_raw = [str(skills_raw)]
    skills = _normalize_skills(skills_raw)
    tags = "".join(
        f'<span class="ca-skill">{html_module.escape(s)}</span>' for s in skills
    ) or '<span class="ca-skill" style="opacity:.4;border-style:dashed">none extracted</span>'
    av = html_module.escape(_initials(str(profile.get("name") or "?")))
    return _template("profile_card.html").substitute(
        av=av,
        name=name,
        role=role,
        years=years,
        summary_html=summary,
        skills=tags,
    )


def jobs_html(
    jobs: list,
    *,
    has_profile: bool = False,
    job_search_ran: bool = False,
    keyword_filter_no_results: bool = False,
) -> str:
    if not jobs:
        if job_search_ran and keyword_filter_no_results:
            msg = (
                "<strong>No roles passed the keyword filter.</strong> Add skills to your profile summary, "
                "or set <code>RELAX_PROFILE_KEYWORD_JOB_FILTER=true</code> in your environment."
            )
        elif job_search_ran:
            msg = "<strong>No listings returned.</strong> Try again in a moment, or check logs for API errors."
        elif has_profile:
            msg = "Profile is ready. Choose <strong>Search jobs</strong> to load matches from Remotive and Arbeitnow."
        else:
            msg = "Upload a resume and extract your profile to begin."
        return f'<div class="ca-jobs-panel">{_template("no_jobs.html").substitute(message=msg)}</div>'

    ordered = sort_jobs_by_match([j for j in jobs if isinstance(j, dict)])
    parts: list[str] = ['<div class="ca-jobs-panel"><div class="ca-jobs-scroll"><div class="ca-jobs-list">']
    card = _template("job_card.html")

    for i, job in enumerate(ordered):
        title = html_module.escape(str(job.get("title", "Untitled")))
        company = html_module.escape(str(job.get("company", "—")))
        url_raw = str(job.get("url", "#")).strip() or "#"
        href = html_module.escape(url_raw, quote=True)
        source = html_module.escape(str(job.get("source", "")))
        loc_raw = str(job.get("location") or "").strip()
        loc = html_module.escape(loc_raw) if loc_raw else ""

        fit_pct = fmt_pct(job.get("overall_match_score"))
        skl_pct = fmt_pct(job.get("skill_match_percentage"))

        desc_raw = str(job.get("description", ""))
        desc = html_module.escape(desc_raw[:280]) + ("…" if len(desc_raw) > 280 else "")
        why_raw = str(job.get("why_this_match", "")).strip()
        why_block = (
            f'<p class="jc-why">{html_module.escape(why_raw[:200])}'
            f'{"…" if len(why_raw) > 200 else ""}</p>'
            if why_raw
            else ""
        )

        loc_chip = f'<span class="jc-chip">{loc}</span>' if loc else ""
        src_chip = f'<span class="jc-chip">{source}</span>' if source else ""
        co_ch = _company_ch(str(job.get("company", "")))

        parts.append(
            card.substitute(
                co_ch=co_ch,
                href=href,
                title=title,
                company=company,
                rank=str(i + 1),
                src_chip=src_chip,
                loc_chip=loc_chip,
                desc=desc,
                why_block=why_block,
                fit_pct=fit_pct,
                skl_pct=skl_pct,
            )
        )

    parts.append("</div></div></div>")
    return "\n".join(parts)


def job_choices(jobs: list) -> list[tuple[str, str]]:
    ordered = sort_jobs_by_match([j for j in jobs if isinstance(j, dict)])
    out: list[tuple[str, str]] = []
    for i, job in enumerate(ordered):
        t = str(job.get("title", "Job"))[:52]
        c = str(job.get("company", ""))[:32]
        ov = fmt_pct(job.get("overall_match_score"))
        sk = fmt_pct(job.get("skill_match_percentage"))
        label = f"{i + 1}. {t}"
        if c.strip():
            label += f" — {c}"
        label += f" ({ov} / {sk})"
        out.append((label[:120], str(i)))
    return out


def section_html(n: int, title: str, desc: str) -> str:
    return _template("section.html").substitute(
        n=str(n),
        title=html_module.escape(title),
        desc=html_module.escape(desc),
    )


def header_html() -> str:
    esc = html_module.escape
    mode = get_profile_backend().value
    vid = get_openai_vector_store_id()
    storage = (
        f"{esc(mode)} &middot; {esc(vid[:8])}&hellip;"
        if get_profile_backend() == ProfileBackend.OPENAI_VECTOR_STORE and vid
        else f"{esc(mode)} &middot; session only"
    )
    warns = validate_profile_backend()
    warn_html = ""
    if warns:
        items = " ".join(f"<div>{esc(w)}</div>" for w in warns)
        warn_html = f'<div class="ca-warn">{items}</div>'
    return _template("header.html").substitute(storage=storage, warn_html=warn_html)


def profile_preview_label_html() -> str:
    return static_fragment("profile_preview_label.html")


def draft_preview_label_html() -> str:
    return static_fragment("draft_preview_label.html")
