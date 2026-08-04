from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class FitAssessment:
    score: float | None
    verdict: str
    matched_dimensions: tuple[str, ...]
    strengths: tuple[str, ...]
    gaps: tuple[str, ...]


WEIGHTS = {
    "role": 40.0,
    "location": 25.0,
    "must_have": 20.0,
    "preferred": 10.0,
    "work_mode": 5.0,
}


ROLE_ALIAS_FAMILIES = (
    (
        "solutions architecture",
        (
            "解决方案架构师",
            "solution architect",
            "solutions architect",
            "cloud solution architect",
            "ai solution architect",
        ),
    ),
    (
        "solutions consulting",
        ("解决方案顾问", "solutions consultant", "solution consultant"),
    ),
    (
        "presales",
        ("售前", "presales", "pre-sales", "sales engineer", "technical sales"),
    ),
    (
        "customer success",
        ("客户成功", "customer success", "customer success manager"),
    ),
    (
        "commercial product",
        ("产品商业化", "product commercialization", "commercial product"),
    ),
    (
        "forward deployed engineering",
        ("fde", "forward deployed engineer", "forward-deployed engineer"),
    ),
)


def evaluate_fit(job: Any, profile: Mapping[str, Any]) -> FitAssessment:
    company = _text(getattr(job, "company", ""))
    title = _text(getattr(job, "title", ""))
    location = _text(getattr(job, "location", ""))
    description = _text(getattr(job, "description", ""))
    work_mode = _text(getattr(job, "work_mode", ""))
    full_text = " ".join((company, title, location, description, work_mode)).lower()

    exclude_companies = _values(profile, "exclude_companies", "excluded_companies")
    for excluded in exclude_companies:
        if _contains(company, excluded):
            return FitAssessment(
                score=0,
                verdict="excluded",
                matched_dimensions=(),
                strengths=(),
                gaps=(f"company: matches excluded company '{excluded}'",),
            )

    exclude_keywords = _values(profile, "exclude_keywords", "excluded_keywords")
    for excluded in exclude_keywords:
        if _contains(full_text, excluded):
            return FitAssessment(
                score=0,
                verdict="excluded",
                matched_dimensions=(),
                strengths=(),
                gaps=(f"keyword: contains excluded keyword '{excluded}'",),
            )

    targets = _values(profile, "target_roles", "roles")
    locations = _values(profile, "locations", "preferred_locations")
    must_have = _values(profile, "must_have_keywords", "must_have")
    preferred = _values(profile, "preferred_keywords", "nice_to_have_keywords")
    work_modes = _values(profile, "work_modes", "preferred_work_modes")
    configured = bool(targets or locations or must_have or preferred or work_modes)
    if not configured:
        return FitAssessment(None, "unconfigured", (), (), ("profile: no screening preferences configured",))

    total_weight = 0.0
    points = 0.0
    matched: list[str] = []
    strengths: list[str] = []
    gaps: list[str] = []

    if targets:
        total_weight += WEIGHTS["role"]
        role_match = next(
            (
                (target, alias_match)
                for target in targets
                for matched, alias_match in [_role_matches(title, target)]
                if matched
            ),
            None,
        )
        if role_match is not None:
            target, alias_match = role_match
            points += WEIGHTS["role"]
            matched.append("role")
            if alias_match:
                strengths.append(
                    f"role: title '{title}' matches configured target '{target}' through a known alias family"
                )
            else:
                strengths.append(f"role: title matches one of {', '.join(targets)}")
        else:
            gaps.append(f"role: title does not directly match {', '.join(targets)}")

    if locations:
        total_weight += WEIGHTS["location"]
        if any(_contains(location, wanted) or _contains(wanted, location) for wanted in locations):
            points += WEIGHTS["location"]
            matched.append("location")
            strengths.append(f"location: {location} matches preferred location")
        else:
            gaps.append(f"location: {location} is outside preferred locations {', '.join(locations)}")

    if must_have:
        total_weight += WEIGHTS["must_have"]
        found = [keyword for keyword in must_have if _contains(full_text, keyword)]
        if found:
            points += WEIGHTS["must_have"] * len(found) / len(must_have)
            matched.append("must_have")
            strengths.append(f"must-have: found {', '.join(found)}")
        missing = [keyword for keyword in must_have if keyword not in found]
        if missing:
            gaps.append(f"must-have: not found {', '.join(missing)}")

    if preferred:
        total_weight += WEIGHTS["preferred"]
        found = [keyword for keyword in preferred if _contains(full_text, keyword)]
        if found:
            points += WEIGHTS["preferred"] * len(found) / len(preferred)
            matched.append("preferred")
            strengths.append(f"preferred: found {', '.join(found)}")
        missing = [keyword for keyword in preferred if keyword not in found]
        if missing:
            gaps.append(f"preferred: not found {', '.join(missing)}")

    if work_modes:
        total_weight += WEIGHTS["work_mode"]
        if work_mode and any(_contains(work_mode, wanted) or _contains(wanted, work_mode) for wanted in work_modes):
            points += WEIGHTS["work_mode"]
            matched.append("work_mode")
            strengths.append(f"work-mode: {work_mode} matches preferred mode")
        else:
            gaps.append(f"work-mode: {work_mode or 'unspecified'} is outside preferred modes {', '.join(work_modes)}")

    score = round(points / total_weight * 100, 1) if total_weight else None
    verdict = "strong_match" if score is not None and score >= 80 else "possible_match" if score is not None and score >= 55 else "weak_match"
    return FitAssessment(score, verdict, tuple(matched), tuple(strengths), tuple(gaps))


def rank_jobs(jobs: Sequence[Any], profile: Mapping[str, Any]) -> list[tuple[Any, FitAssessment]]:
    ranked = [(job, evaluate_fit(job, profile)) for job in jobs]
    return sorted(
        ranked,
        key=lambda pair: (
            pair[1].verdict != "excluded",
            pair[1].score if pair[1].score is not None else -1,
        ),
        reverse=True,
    )


def _values(profile: Mapping[str, Any], *keys: str) -> list[str]:
    for key in keys:
        raw = profile.get(key)
        if isinstance(raw, str) and raw.strip():
            return [raw.strip()]
        if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes, bytearray)):
            values = [str(item).strip() for item in raw if str(item).strip()]
            if values:
                return values
    return []


def _contains(haystack: str, needle: str) -> bool:
    return _text(needle).lower() in _text(haystack).lower()


def _role_matches(title: str, target: str) -> tuple[bool, bool]:
    normalized_title = _text(title).casefold()
    normalized_target = _text(target).casefold()
    if not normalized_title or not normalized_target:
        return False, False
    if normalized_target in normalized_title or normalized_title in normalized_target:
        return True, False

    for _, aliases in ROLE_ALIAS_FAMILIES:
        normalized_aliases = tuple(alias.casefold() for alias in aliases)
        target_aliases = tuple(
            alias for alias in normalized_aliases if _role_alias_in_text(normalized_target, alias)
        )
        title_aliases = tuple(
            alias for alias in normalized_aliases if _role_alias_in_text(normalized_title, alias)
        )
        if target_aliases and title_aliases:
            return True, True
    return False, False


def _role_alias_in_text(text: str, alias: str) -> bool:
    if alias == "fde":
        return re.search(r"(?<![a-z0-9])fde(?![a-z0-9])", text) is not None
    return alias in text


def _text(value: Any) -> str:
    return " ".join(str(value or "").split())
