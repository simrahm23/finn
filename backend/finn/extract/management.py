"""Management-change card. Person and profile must be found in the filing text, or they are not shown."""
from __future__ import annotations

import re

from .. import contracts as c
from ..ingest import documents
from ..llm import client as llm
from . import validate as v

SCHEMA = {"type": "object", "properties": {
    "person": {"type": "string"}, "role": {"type": "string"},
    "direction": {"type": "string", "enum": ["joining", "leaving"]},
    "effective_date": {"type": "string"}, "reason": {"type": "string"}, "profile": {"type": "string"}},
    "required": ["person", "role", "direction", "effective_date", "reason", "profile"]}


def relevant_text(texts: list[str]) -> tuple[str, int]:
    """First two pages + any annexure page with a profile. Returns (text, page number of the profile or 1)."""
    keep, profile_page = list(range(min(2, len(texts)))), 1
    for i, t in enumerate(texts):
        if i > 1 and re.search(r"brief profile|profile of|experience|qualification", t, re.I):
            keep.append(i)
            profile_page = i + 1
            if len(keep) >= 4:
                break
    return "\n".join(texts[i] for i in keep), profile_page


def extract(url: str) -> tuple[c.ManagementCard | None, str]:
    path = documents.fetch_pdf(url)
    if not path:
        return None, "pdf unavailable"
    texts = documents.page_texts(path, 12)
    text, profile_page = relevant_text(texts)
    if len(text.strip()) < 100:
        return None, "no text (scanned?)"
    raw = llm.generate_json("management", {"text": " ".join(text.split())[:9000]}, SCHEMA, purpose="management")
    person = (raw.get("person") or "").strip()
    if not person or not v.fuzzy_in(person, text):
        return None, "person not found in filing"
    profile = (raw.get("profile") or "").strip()
    if profile and (not v.fuzzy_in(profile[:300], text) or re.search(r"not applicable", profile, re.I)):
        profile = ""
    eff = raw.get("effective_date") or None
    if eff and not re.match(r"\d{4}-\d{2}-\d{2}$", eff):
        eff = None
    return c.ManagementCard(
        direction=raw.get("direction", "leaving"), person=person, role=(raw.get("role") or "").strip() or "Not stated",
        effective_date=eff, reason=(raw.get("reason") or "").strip() or None, profile=profile or None,
        source=c.Source(label=f"Filing p.{profile_page if profile else 1}", kind="filing", url=url,
                        page=profile_page if profile else 1),
    ), "ok"
