"""check_citations.py - STUDENT IMPLEMENTS `check`.   Runs INSIDE the sandbox (standard library only).

research.py uploads this file to the sandbox and the lead agent runs it with the `execute` tool:
    python3 /tmp/work/research/check_citations.py [report.md] [sources.json]
It must exit 0 and print "OK: ..." when the report is consistent, else print each problem and exit 1.
"""
import json
import re
import sys

REPORT = "/tmp/work/report/report.md"
SOURCES = "/tmp/work/research/sources.json"

_GROUP = re.compile(r"\[(\d+(?:\s*[,–-]\s*\d+)*)\](?!\()")   # [3]  [1, 2]  [1-3]  [2-3]; not [3](link)
_CODE = re.compile(r"(```.*?```|`[^`\n]*`)", re.DOTALL)
_REF_HEADING = re.compile(r"(?m)^##[ \t]+References[ \t]*$")
_REF_LINE = re.compile(r"^\[(\d+)\]\s*(.*)$")


def _group_numbers(group_str):
    numbers = []
    for part in re.split(r"\s*,\s*", group_str):
        span = re.fullmatch(r"(\d+)\s*[–-]\s*(\d+)", part)
        if span:
            a, b = int(span.group(1)), int(span.group(2))
            if a <= b and (b - a) <= 200:
                numbers.extend(range(a, b + 1))
            else:
                numbers.extend([a, b])
        else:
            if part.isdigit():
                numbers.append(int(part))
    return numbers


def check(report_text, sources):
    """Return a list of problem strings (empty list = OK)."""
    problems = []
    if not sources or not isinstance(sources, list):
        return ["no sources in sources.json"]

    source_numbers = set()
    source_urls = {}
    sources_by_n = {}

    for entry in sources:
        if not isinstance(entry, dict):
            problems.append(f"source entry is not an object: {entry!r}")
            continue
        n = entry.get("n")
        if not isinstance(n, int):
            problems.append(f"source entry has non-integer n: {n!r}")
        elif n in sources_by_n:
            problems.append(f"duplicate source number n={n} in sources.json")
        else:
            sources_by_n[n] = entry
            source_numbers.add(n)

        url = entry.get("url")
        if not isinstance(url, str) or not (url.startswith("http://") or url.startswith("https://")):
            problems.append(f"source [{n}] has invalid url: {url!r}")
        else:
            if url in source_urls:
                problems.append(f"duplicate url in sources.json: '{url}' (n={source_urls[url]} and n={n})")
            else:
                source_urls[url] = n

    matches = list(_REF_HEADING.finditer(report_text))
    if not matches:
        problems.append("missing '## References' section")
        body = report_text
        ref_text = ""
    else:
        body = report_text[:matches[-1].start()]
        ref_text = report_text[matches[-1].end():]

    body_clean = _CODE.sub("", body)
    cited = set()
    for match in _GROUP.finditer(body_clean):
        for num in _group_numbers(match.group(1)):
            cited.add(num)

    for num in sorted(cited):
        if num not in source_numbers:
            problems.append(f"[{num}] cited in body but missing from sources.json")

    for num in sorted(source_numbers):
        if num not in cited:
            problems.append(f"source [{num}] in sources.json is never cited in body")

    ref_lines_by_n = {}
    for line in ref_text.splitlines():
        line_str = line.strip()
        if not line_str:
            continue
        m = _REF_LINE.match(line_str)
        if m:
            ref_n = int(m.group(1))
            ref_lines_by_n.setdefault(ref_n, []).append(line_str)

    for ref_n in sorted(ref_lines_by_n.keys()):
        if ref_n not in source_numbers:
            problems.append(f"reference [{ref_n}] in References section does not exist in sources.json")
        if len(ref_lines_by_n[ref_n]) > 1:
            problems.append(f"duplicate reference line for [{ref_n}] ({len(ref_lines_by_n[ref_n])} lines found)")

    for n in sorted(source_numbers):
        if n not in ref_lines_by_n:
            problems.append(f"missing reference line for source [{n}] in References section")
        else:
            for line_content in ref_lines_by_n[n]:
                raw_urls = re.findall(r"https?://[^\s<>\"']+", line_content)
                expected_url = sources_by_n[n].get("url")
                cleaned_urls = []
                for u in raw_urls:
                    if u != expected_url:
                        cleaned_urls.append(u.rstrip(".,;)]"))
                    else:
                        cleaned_urls.append(u)

                if len(cleaned_urls) != 1:
                    problems.append(f"reference line [{n}] contains {len(cleaned_urls)} URLs (expected exactly 1)")
                elif expected_url and cleaned_urls[0] != expected_url:
                    problems.append(
                        f"reference line [{n}] URL '{cleaned_urls[0]}' does not match sources.json URL '{expected_url}'"
                    )

    return problems


def main(argv):
    report_path = argv[1] if len(argv) > 1 else REPORT
    sources_path = argv[2] if len(argv) > 2 else SOURCES
    try:
        with open(report_path, encoding="utf-8") as f:
            report = f.read()
        with open(sources_path, encoding="utf-8") as f:
            sources = json.load(f)
    except (OSError, ValueError) as exc:
        print(f"cannot read inputs: {exc}")
        return 1
    problems = check(report, sources)
    if problems:
        print("\n".join(problems))
        return 1
    print(f"OK: {len(sources)} sources, all citations resolve")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
