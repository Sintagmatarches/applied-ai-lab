from __future__ import annotations

import re
from typing import Any


def _phrases(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip().lower() for item in value if str(item).strip()]
    return [item.strip().lower() for item in re.split(r"[,;/\n]+", str(value)) if item.strip()]


def _words(value: str) -> set[str]:
    return {word for word in re.split(r"[^a-z0-9+#.]+", value.lower()) if len(word) > 1}


def score_job(job: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    roles = _phrases(profile.get("roles", []))
    skills = _phrases(profile.get("skills", []))
    title_words = _words(str(job.get("title", "")))
    role_overlap = 0.0
    for role in roles:
        role_words = _words(role)
        if role_words:
            role_overlap = max(role_overlap, len(role_words & title_words) / len(role_words))
    role_score = round(min(1.0, role_overlap) * 35)

    evidence = " ".join(
        [
            str(job.get("title", "")),
            " ".join(str(item) for item in job.get("requirements", [])),
            str(job.get("description", "")),
        ]
    ).lower()
    matched = [skill for skill in skills if skill in evidence]
    skill_score = round((len(matched) / len(skills) if skills else 0.0) * 45)

    preferred_location = str(profile.get("location", "")).strip().lower()
    location_match = (
        not preferred_location
        or preferred_location in str(job.get("location", "")).lower()
        or bool(job.get("remote"))
    )
    remote_match = not bool(profile.get("remote_only")) or bool(job.get("remote"))
    preference_score = (10 if location_match else 0) + (10 if remote_match else 0)
    advertised = [str(item) for item in job.get("requirements", [])]
    missing = [
        item
        for item in advertised
        if not any(
            item.lower() in skill or skill in item.lower()
            for skill in skills
        )
    ]
    return {
        "job_id": job["id"],
        "score": min(100, role_score + skill_score + preference_score),
        "components": {
            "role": {"score": role_score, "maximum": 35},
            "skills": {"score": skill_score, "maximum": 45},
            "preferences": {"score": preference_score, "maximum": 20},
        },
        "matched_skills": matched,
        "missing_requirements": missing,
    }
