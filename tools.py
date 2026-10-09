"""tools.py - STUDENT IMPLEMENTS.  Source tools for the research agents.   Guide: GUIDE.md, part 1.

Rules for every tool:
  * runs on the HOST (not in the sandbox): API keys must never enter the sandbox;
  * returns a STRING (JSON text of compact records) and NEVER raises:
        "NO RESULTS"  when the source answers with nothing,
        "ERROR: ..."  when the source keeps failing after the retries (the agent then tries another source);
  * the docstring is the tool description the LLM reads: keep it precise (what it does, what it returns, when to use it).
Try your tools without any agent:   python tools.py
"""
import json
import os
import random
import re
import time
import xml.etree.ElementTree

import httpx
from langchain_core.tools import tool

# ---- constants (given) ----
ARXIV_URL = "https://export.arxiv.org/api/query"  # https only: http answers 301
HF_DAILY_URL = "https://huggingface.co/api/daily_papers"
HF_SEARCH_URL = "https://huggingface.co/api/papers/search"
EXA_URL = "https://mcp.exa.ai/mcp"

_LAST_ARXIV_CALL = 0.0


def _arxiv_wait():
    global _LAST_ARXIV_CALL
    now = time.time()
    elapsed = now - _LAST_ARXIV_CALL
    if elapsed < 3.0:
        time.sleep(3.0 - elapsed)
    _LAST_ARXIV_CALL = time.time()


class RetryableError(Exception):
    """Given. Raise it inside a call to ask with_retry to wait and try again (retry_after in seconds, optional)."""

    def __init__(self, message, retry_after=None):
        super().__init__(message)
        self.retry_after = retry_after


# ---- TODO 1: retry helper ----
def with_retry(fn, *, attempts=5, base=1.0, cap=30.0):
    """Call fn(); when it raises RetryableError, wait and call it again."""
    for attempt in range(attempts):
        try:
            return fn()
        except (RetryableError, httpx.TransportError, httpx.HTTPStatusError) as exc:
            retry_after = None
            if isinstance(exc, httpx.HTTPStatusError):
                if exc.response.status_code not in (429, 500, 502, 503, 504):
                    raise
                ra_header = exc.response.headers.get("Retry-After")
                if ra_header:
                    try:
                        retry_after = float(ra_header)
                    except ValueError:
                        pass
            elif isinstance(exc, RetryableError):
                retry_after = exc.retry_after

            if attempt == attempts - 1:
                raise

            if retry_after is not None:
                delay = min(cap, max(0.0, float(retry_after)))
            else:
                exp_delay = base * (2 ** attempt)
                jitter = random.uniform(0.0, 0.5 * exp_delay)
                delay = min(cap, exp_delay + jitter)

            time.sleep(delay)


# ---- TODO 2: arXiv ----
@tool
def arxiv_search(query: str, max_results: int = 10) -> str:
    """Search arXiv papers by keywords, newest first. Returns a JSON list of {id, url, published, title, summary}."""
    try:
        raw_terms = re.findall(r"[A-Za-z0-9\-]+", query)
        terms = [t for t in raw_terms if t.lower() not in ("and", "or", "not")]
        if not terms:
            terms = raw_terms
        if not terms:
            return "NO RESULTS"

        search_query = " AND ".join(f"all:{t}" for t in terms)
        clamped_max = max(1, min(30, max_results))

        def _fetch():
            _arxiv_wait()
            resp = httpx.get(
                ARXIV_URL,
                params={
                    "search_query": search_query,
                    "sortBy": "submittedDate",
                    "sortOrder": "descending",
                    "max_results": clamped_max,
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            return resp

        resp = with_retry(_fetch, attempts=6, base=2.0, cap=60.0)
        root = xml.etree.ElementTree.fromstring(resp.text)
        entries = root.findall("{http://www.w3.org/2005/Atom}entry")
        if not entries:
            return "NO RESULTS"

        records = []
        for entry in entries:
            id_val = entry.findtext("{http://www.w3.org/2005/Atom}id", "").strip()
            raw_id = id_val.split("/abs/")[-1] if "/abs/" in id_val else id_val.rsplit("/", 1)[-1]
            clean_id = re.sub(r"v\d+$", "", raw_id)
            url = f"https://arxiv.org/abs/{clean_id}"
            published = entry.findtext("{http://www.w3.org/2005/Atom}published", "")[:10]
            title = " ".join(entry.findtext("{http://www.w3.org/2005/Atom}title", "").split())
            summary = " ".join(entry.findtext("{http://www.w3.org/2005/Atom}summary", "").split())
            if len(summary) > 600:
                summary = summary[:600] + "..."
            records.append({
                "id": clean_id,
                "url": url,
                "published": published,
                "title": title,
                "summary": summary,
            })

        return json.dumps(records, ensure_ascii=False) if records else "NO RESULTS"
    except Exception as exc:
        return f"ERROR: {type(exc).__name__}: {exc}"


# ---- TODO 3: Hugging Face ----
@tool
def hf_daily_papers(limit: int = 30, date: str = "", keyword: str = "") -> str:
    """Hugging Face Daily Papers = what is trending in AI research. Returns a JSON list of
    {id, url, published, title, summary, upvotes, github, stars} sorted by upvotes. `date` is YYYY-MM-DD (empty = latest).
    `keyword` filters title/summary; there is no topic search on this endpoint (use hf_search_papers for a topic)."""
    try:
        params = {"limit": max(1, min(100, limit))}
        if date.strip():
            params["date"] = date.strip()

        def _fetch():
            resp = httpx.get(HF_DAILY_URL, params=params, timeout=30.0)
            resp.raise_for_status()
            return resp

        resp = with_retry(_fetch, attempts=5, base=1.0, cap=30.0)
        data = resp.json()
        if not isinstance(data, list):
            return "NO RESULTS"

        records = []
        for item in data:
            if not isinstance(item, dict):
                continue
            p = item.get("paper", {}) if isinstance(item.get("paper"), dict) else item
            paper_id = p.get("id") or item.get("id")
            if not paper_id:
                continue
            title = " ".join(str(p.get("title") or item.get("title") or "").split())
            summary_raw = p.get("ai_summary") or item.get("ai_summary") or p.get("summary") or item.get("summary") or ""
            summary = " ".join(str(summary_raw).split())
            if len(summary) > 600:
                summary = summary[:600] + "..."
            upvotes = p.get("upvotes") if p.get("upvotes") is not None else item.get("upvotes", 0)
            github = p.get("githubRepo") or item.get("githubRepo") or ""
            stars = p.get("githubStars") if p.get("githubStars") is not None else item.get("githubStars", 0)
            published = str(p.get("publishedAt") or item.get("publishedAt") or "")[:10]
            url = f"https://huggingface.co/papers/{paper_id}"

            if keyword.strip():
                kw = keyword.strip().lower()
                if kw not in (title + " " + summary).lower():
                    continue

            records.append({
                "id": str(paper_id),
                "url": url,
                "published": published,
                "title": title,
                "summary": summary,
                "upvotes": int(upvotes or 0),
                "github": str(github),
                "stars": int(stars or 0),
            })

        records.sort(key=lambda r: r.get("upvotes", 0), reverse=True)
        return json.dumps(records, ensure_ascii=False) if records else "NO RESULTS"
    except Exception as exc:
        return f"ERROR: {type(exc).__name__}: {exc}"


@tool
def hf_search_papers(query: str, limit: int = 10) -> str:
    """Search Hugging Face papers by topic. Returns a JSON list of
    {id, url, published, title, summary, upvotes, github, stars}."""
    try:
        if not query.strip():
            return "NO RESULTS"
        params = {"q": query.strip(), "limit": max(1, min(50, limit))}

        def _fetch():
            resp = httpx.get(HF_SEARCH_URL, params=params, timeout=30.0)
            resp.raise_for_status()
            return resp

        resp = with_retry(_fetch, attempts=5, base=1.0, cap=30.0)
        data = resp.json()
        if not isinstance(data, list):
            return "NO RESULTS"

        records = []
        for item in data:
            if not isinstance(item, dict):
                continue
            p = item.get("paper", {}) if isinstance(item.get("paper"), dict) else item
            paper_id = p.get("id") or item.get("id")
            if not paper_id:
                continue
            title = " ".join(str(p.get("title") or item.get("title") or "").split())
            summary_raw = p.get("ai_summary") or item.get("ai_summary") or p.get("summary") or item.get("summary") or ""
            summary = " ".join(str(summary_raw).split())
            if len(summary) > 600:
                summary = summary[:600] + "..."
            upvotes = p.get("upvotes") if p.get("upvotes") is not None else item.get("upvotes", 0)
            github = p.get("githubRepo") or item.get("githubRepo") or ""
            stars = p.get("githubStars") if p.get("githubStars") is not None else item.get("githubStars", 0)
            published = str(p.get("publishedAt") or item.get("publishedAt") or "")[:10]
            url = f"https://huggingface.co/papers/{paper_id}"

            records.append({
                "id": str(paper_id),
                "url": url,
                "published": published,
                "title": title,
                "summary": summary,
                "upvotes": int(upvotes or 0),
                "github": str(github),
                "stars": int(stars or 0),
            })

        return json.dumps(records, ensure_ascii=False) if records else "NO RESULTS"
    except Exception as exc:
        return f"ERROR: {type(exc).__name__}: {exc}"


# ---- TODO 4: web search / fetch through the Exa MCP endpoint ----
def _redact_key(text: str) -> str:
    exa_key = os.getenv("EXA_API_KEY", "").strip()
    if exa_key and exa_key in text:
        text = text.replace(exa_key, "[REDACTED]")
    return text


def _call_exa_mcp(tool_name: str, arguments: dict) -> str:
    exa_key = os.getenv("EXA_API_KEY", "").strip()
    url = f"{EXA_URL}?exaApiKey={exa_key}" if exa_key else EXA_URL
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments,
        },
    }

    def _fetch():
        resp = httpx.post(url, headers=headers, json=payload, timeout=45.0)
        resp.raise_for_status()

        resp_obj = None
        for line in resp.text.splitlines():
            if line.startswith("data:"):
                line_json = line[len("data:"):].strip()
                if line_json:
                    try:
                        resp_obj = json.loads(line_json)
                    except json.JSONDecodeError:
                        pass
        if resp_obj is None:
            resp_obj = resp.json()

        if "error" in resp_obj:
            raise RuntimeError(f"Exa error: {resp_obj['error']}")

        result = resp_obj.get("result", {})
        meta = result.get("_meta", {})
        if meta.get("rate_limited") or meta.get("is_rate_limited") or "rate_limit" in str(meta).lower():
            raise RetryableError(f"Exa rate limited (meta): {meta}")

        contents = result.get("content", [])
        texts = [c.get("text", "") for c in contents if isinstance(c, dict) and c.get("type") == "text"]
        full_text = "\n\n".join(texts).strip()

        lower_text = full_text.lower()
        if "rate limit" in lower_text and ("exceeded" in lower_text or "tier" in lower_text or "exa" in lower_text or "requests" in lower_text):
            raise RetryableError(f"Exa rate limited in content: {full_text[:200]}")

        return full_text

    return with_retry(_fetch, attempts=6, base=2.0, cap=60.0)


@tool
def web_search(query: str, objective: str = "", num_results: int = 5) -> str:
    """Search the web (Exa). Describe the ideal page in natural language. Returns clean text of the top results with URLs."""
    try:
        if not query.strip():
            return "NO RESULTS"
        obj = objective.strip() or f"find academic research and survey papers about {query.strip()}"
        num = max(1, min(20, num_results))
        res = _call_exa_mcp("web_search_exa", {"query": query.strip(), "objective": obj, "numResults": num})
        return res if res.strip() else "NO RESULTS"
    except Exception as exc:
        return _redact_key(f"ERROR: {type(exc).__name__}: {exc}")


@tool
def web_fetch(url: str) -> str:
    """Read the full content of one web page (e.g. an arXiv abstract page) as markdown. Long pages are truncated."""
    try:
        if not url.strip():
            return "NO RESULTS"
        res = _call_exa_mcp("web_fetch_exa", {"urls": [url.strip()]})
        if not res.strip():
            return "NO RESULTS"
        if len(res) > 12000:
            res = res[:12000] + "\n...[truncated]"
        return res
    except Exception as exc:
        return _redact_key(f"ERROR: {type(exc).__name__}: {exc}")


# ---- TODO 5: registry (the researcher subagent gets exactly these) ----
SOURCE_TOOLS = [arxiv_search, hf_daily_papers, hf_search_papers, web_search, web_fetch]


if __name__ == "__main__":
    for name, fn, args in [
        ("arxiv_search", arxiv_search, {"query": "world model", "max_results": 3}),
        ("hf_daily_papers", hf_daily_papers, {"limit": 20}),
        ("hf_search_papers", hf_search_papers, {"query": "world model", "limit": 3}),
        ("web_search", web_search, {"query": "survey paper on world models", "num_results": 2}),
        ("web_fetch", web_fetch, {"url": "https://arxiv.org/abs/1803.10122"}),
    ]:
        try:
            print(f"== {name}\n{fn.invoke(args)[:400]}\n")
        except NotImplementedError as exc:
            print(f"== {name}: not implemented yet ({exc})\n")
