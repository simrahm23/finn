"""The only door to an LLM. Structured JSON out, content-hash cache, rate limit, retries, call log.
A rerun with unchanged inputs and prompt versions makes zero API calls."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import time
from pathlib import Path

from .. import config, db, net

PROMPTS = Path(__file__).parent / "prompts"
RPM = float(os.environ.get("FINN_RPM", "10"))     # stay under the free-tier per-minute limit
_last_call = 0.0


class LlmError(RuntimeError):
    pass


def load_prompt(name: str) -> tuple[str, str]:
    """prompts/<name>.md, first line '# version: x' -> (version, body)."""
    text = (PROMPTS / f"{name}.md").read_text(encoding="utf-8")
    m = re.match(r"#\s*version:\s*(\S+)\s*\n", text)
    return (m.group(1) if m else "0"), (text[m.end():] if m else text)


def _key(model: str, version: str, payload: str) -> str:
    return hashlib.sha256(f"{model}|{version}|{payload}".encode()).hexdigest()


def _log(con, model, purpose, cached, tin, tout):
    con.execute("INSERT INTO llm_calls VALUES (?,?,?,?,?,?)",
                (dt.datetime.now().isoformat(timespec="seconds"), model, purpose, int(cached), tin, tout))


def generate_json(prompt_name: str, payload: dict, schema: dict, model: str | None = None,
                  purpose: str | None = None, retries: int = 4) -> dict:
    """Render prompt + JSON payload, call Gemini with a response schema, return parsed JSON."""
    global _last_call
    model = model or config.MODEL_LITE
    version, body = load_prompt(prompt_name)
    payload_s = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    key = _key(model, f"{prompt_name}:{version}", payload_s)
    purpose = purpose or prompt_name

    with db.session() as con:
        hit = con.execute("SELECT response_json FROM llm_cache WHERE key=?", (key,)).fetchone()
        if hit:
            _log(con, model, purpose, True, 0, 0)
            return json.loads(hit["response_json"])

    if not config.GEMINI_API_KEY:
        raise LlmError("GEMINI_API_KEY is not set")
    from google import genai
    from google.genai import types
    try:
        client = genai.Client(api_key=config.GEMINI_API_KEY,
                              http_options=types.HttpOptions(httpx_client=net.llm_client()))
    except (TypeError, AttributeError):          # older SDKs: default transport
        client = genai.Client(api_key=config.GEMINI_API_KEY)
    contents = f"{body}\n\nINPUT (JSON):\n{payload_s}"
    cfg = types.GenerateContentConfig(response_mime_type="application/json", response_schema=schema, temperature=0)

    err, out = None, None
    for attempt in range(retries):
        wait = 60.0 / RPM - (time.time() - _last_call)
        if wait > 0:
            time.sleep(wait)
        try:
            _last_call = time.time()
            resp = client.models.generate_content(model=model, contents=contents, config=cfg)
            out = json.loads(resp.text)
            um = resp.usage_metadata
            break
        except json.JSONDecodeError as e:          # model returned non-JSON: retry once quickly
            err = e
            time.sleep(1)
        except Exception as e:  # noqa: BLE001
            err = e
            code = getattr(e, "code", None) or getattr(e, "status_code", None)
            if code in (400, 401, 403, 404) or "PerDay" in str(e):
                break                                # not retryable (a daily quota won't reset in seconds)
            time.sleep(min(60, 5 * 2 ** attempt))    # 429 / 5xx / network: back off
    if out is not None:
        tin, tout = (um.prompt_token_count or 0), (um.candidates_token_count or 0)
        with db.session() as con:                    # outside the retry loop: a DB error is never "retried"
            con.execute("INSERT OR REPLACE INTO llm_cache VALUES (?,?,?,?,?,?,?)",
                        (key, model, f"{prompt_name}:{version}", json.dumps(out), tin, tout,
                         dt.datetime.now().isoformat(timespec="seconds")))
            _log(con, model, purpose, False, tin, tout)
        return out
    raise LlmError(f"{prompt_name}: {type(err).__name__}: {err}")


def generate_json_with_fallback(prompt_name: str, payload: dict, schema: dict, purpose: str | None = None) -> dict:
    """Reasoning model first; if its (small) free-tier quota is exhausted or it fails, fall back to the bulk model.
    Output is checked the same way either way, so the fallback can't lower the bar."""
    try:
        return generate_json(prompt_name, payload, schema, model=config.MODEL_FLASH, purpose=purpose, retries=2)
    except LlmError:
        return generate_json(prompt_name, payload, schema, model=config.MODEL_LITE, purpose=f"{purpose or prompt_name}:fallback")


def usage() -> dict:
    with db.session() as con:
        r = con.execute("SELECT COUNT(*) n, SUM(cached) c, SUM(tokens_in) ti, SUM(tokens_out) tout FROM llm_calls").fetchone()
    return {"calls": r["n"] or 0, "cached": r["c"] or 0, "tokens_in": r["ti"] or 0, "tokens_out": r["tout"] or 0,
            "cost_inr": 0.0}   # free tier
