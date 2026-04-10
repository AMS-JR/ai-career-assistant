# =============================================
# utils.llm_payload - keep LLM inputs within context limits
# =============================================

from __future__ import annotations

import copy
import json
import re
from typing import Any


def truncate_chars(text: str | None, max_len: int, suffix: str = "...") -> str:
    if not text or max_len <= 0:
        return ""
    s = text if isinstance(text, str) else str(text)
    if len(s) <= max_len:
        return s
    take = max(0, max_len - len(suffix))
    return s[:take] + suffix if take else suffix


_TAG_RE = re.compile(r"<[^>]+>")


def strip_html_to_text(html: str | None, max_len: int) -> str:
    if not html:
        return ""
    plain = _TAG_RE.sub(" ", str(html))
    plain = re.sub(r"\s+", " ", plain).strip()
    return truncate_chars(plain, max_len)


def trim_api_jobs_for_llm(
    jobs: list[Any],
    *,
    max_items: int,
    description_max_chars: int,
    arbeitnow: bool,
) -> list[dict[str, Any]]:
    """Return shallow job dicts with truncated plain-text descriptions (smaller tool payloads)."""
    out: list[dict[str, Any]] = []
    for raw in jobs[:max_items]:
        if not isinstance(raw, dict):
            continue
        if arbeitnow:
            desc = strip_html_to_text(raw.get("description"), description_max_chars)
            out.append(
                {
                    "slug": raw.get("slug"),
                    "title": raw.get("title"),
                    "company_name": raw.get("company_name"),
                    "location": raw.get("location"),
                    "remote": raw.get("remote"),
                    "tags": raw.get("tags") if isinstance(raw.get("tags"), list) else [],
                    "job_types": raw.get("job_types")
                    if isinstance(raw.get("job_types"), list)
                    else [],
                    "description": desc,
                    "url": raw.get("url"),
                    "created_at": raw.get("created_at"),
                }
            )
        else:
            desc = strip_html_to_text(raw.get("description"), description_max_chars)
            tags = raw.get("tags")
            posted = raw.get("publication_date") or raw.get("created_at")
            out.append(
                {
                    "id": raw.get("id"),
                    "title": raw.get("title"),
                    "company": raw.get("company") or raw.get("company_name"),
                    "candidate_required_location": raw.get("candidate_required_location"),
                    "job_type": raw.get("job_type"),
                    "tags": tags if isinstance(tags, list) else [],
                    "description": desc,
                    "url": raw.get("url"),
                    "posted_at": posted,
                    "publication_date": raw.get("publication_date"),
                    "created_at": raw.get("created_at"),
                }
            )
    return out


def slim_profile_for_llm(
    profile: dict[str, Any],
    *,
    summary_max: int = 2000,
    max_skills: int = 60,
    max_experience: int = 10,
    experience_desc_max: int = 600,
    max_projects: int = 8,
    project_desc_max: int = 400,
    max_education: int = 5,
    max_certs: int = 10,
) -> dict[str, Any]:
    """Drop bulk from parsed profile while keeping structure for matching/tailoring."""
    if not isinstance(profile, dict):
        return {}
    p = copy.deepcopy(profile)
    s = p.get("summary")
    if isinstance(s, str):
        p["summary"] = truncate_chars(s, summary_max)
    title = p.get("title")
    if isinstance(title, str):
        p["title"] = truncate_chars(title, 220)
    sk = p.get("skills")
    if isinstance(sk, list):
        p["skills"] = [str(x) for x in sk[:max_skills]]
    ex = p.get("experience")
    if isinstance(ex, list):
        slim_e: list[Any] = []
        for item in ex[:max_experience]:
            if not isinstance(item, dict):
                continue
            d = dict(item)
            ddesc = d.get("description")
            if isinstance(ddesc, str):
                d["description"] = truncate_chars(ddesc, experience_desc_max)
            slim_e.append(d)
        p["experience"] = slim_e
    pr = p.get("projects")
    if isinstance(pr, list):
        slim_p: list[Any] = []
        for item in pr[:max_projects]:
            if not isinstance(item, dict):
                continue
            d = dict(item)
            ddesc = d.get("description")
            if isinstance(ddesc, str):
                d["description"] = truncate_chars(ddesc, project_desc_max)
            slim_p.append(d)
        p["projects"] = slim_p
    ed = p.get("education")
    if isinstance(ed, list):
        p["education"] = [x for x in ed[:max_education] if isinstance(x, (dict, str))]
    ce = p.get("certifications")
    if isinstance(ce, list):
        slim_c: list[Any] = []
        for item in ce[:max_certs]:
            if isinstance(item, dict):
                d = dict(item)
                nm = d.get("name")
                if isinstance(nm, str):
                    d["name"] = truncate_chars(nm, 200)
                slim_c.append(d)
            else:
                slim_c.append(item)
        p["certifications"] = slim_c
    return p


def profile_json_for_llm(profile: dict[str, Any], max_chars: int) -> str:
    """Compact JSON; if still too large, trim summary/experience further and retry once."""
    slim = slim_profile_for_llm(profile)
    s = json.dumps(slim, ensure_ascii=False, separators=(",", ":"))
    if len(s) <= max_chars:
        return s
    slim2 = slim_profile_for_llm(
        profile,
        summary_max=800,
        max_skills=35,
        max_experience=6,
        experience_desc_max=350,
        max_projects=5,
        project_desc_max=250,
    )
    s2 = json.dumps(slim2, ensure_ascii=False, separators=(",", ":"))
    if len(s2) <= max_chars:
        return s2
    minimal = {
        "name": slim2.get("name"),
        "summary": truncate_chars(str(slim2.get("summary") or ""), 500),
        "skills": (slim2.get("skills") or [])[:30] if isinstance(slim2.get("skills"), list) else [],
    }
    return json.dumps(minimal, ensure_ascii=False, separators=(",", ":"))


def slim_job_for_tailor(job: dict[str, Any], description_max: int) -> dict[str, Any]:
    keys = (
        "title",
        "company",
        "company_name",
        "location",
        "url",
        "source",
        "skill_match_percentage",
        "overall_match_score",
        "why_this_match",
        "matching_skills",
    )
    out: dict[str, Any] = {}
    for k in keys:
        if k in job and job[k] is not None:
            out[k] = job[k]
    desc = job.get("description")
    if isinstance(desc, str):
        out["description"] = truncate_chars(desc, description_max)
    return out
