"""Turns a pytest JUnit XML file into what a reviewer sees on GitHub.

- an error annotation on the line of every failed test (shown in the PR's Files changed tab and on the run);
- a Markdown summary for the run page and for the pull request comment.

python scripts/ci_report.py junit.xml summary.md
"""

import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def one_line(text: str, limit: int = 300) -> str:
    """GitHub annotations keep one line. Prefer Hypothesis notes on the failing example, then the differing items."""
    lines = [raw.strip()[2:].strip() for raw in text.splitlines() if raw.strip().startswith("E ")]
    lines = [line for line in lines if line]
    for i, line in enumerate(lines):
        if line.startswith(("Failing test case", "Falsifying example")):
            notes = [x for x in lines[i + 1 :] if x != ")" and not re.fullmatch(r"\w+=,?", x)]
            if notes:
                return " · ".join(notes[:3])[:limit]
    diff = [line for line in lines if " != " in line]
    if diff:
        return " · ".join(diff[:2])[:limit]
    return (lines[0] if lines else " ".join(text.split()))[:limit]


def location(case: ET.Element) -> tuple[str, int]:
    """File and line of the test function: pytest writes the class path, the file is found from it."""
    file = case.get("file") or case.get("classname", "").replace(".", "/") + ".py"
    path = ROOT / file
    line = int(case.get("line") or 0) + 1
    name = re.sub(r"\[.*$", "", case.get("name", ""))
    if path.exists():
        for no, text in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if re.match(rf"\s*(async\s+)?def {re.escape(name)}\(", text):
                line = no
                break
    return file, line


def main(junit: str, out: str) -> int:
    root = ET.parse(junit).getroot()  # noqa: S314 - the file is written by our own pytest run
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    total = sum(int(s.get("tests", 0)) for s in suites)
    skipped = sum(int(s.get("skipped", 0)) for s in suites)
    seconds = sum(float(s.get("time", 0)) for s in suites)
    failed = []
    for case in root.iter("testcase"):
        problem = case.find("failure")
        if problem is None:
            problem = case.find("error")
        if problem is None:
            continue
        file, line = location(case)
        message = one_line(problem.get("message", "") + "\n" + (problem.text or ""))
        name = f"{case.get('classname', '').split('.')[-1]}::{case.get('name')}"
        failed.append((name, file, line, message))
        print(f"::error file={file},line={line},title=Test failed: {case.get('name')}::{message}")

    passed = total - skipped - len(failed)
    verdict = "❌ Do not merge" if failed else "✅ Safe to merge"
    lines = [
        f"### {verdict}",
        "",
        "| Passed | Failed | Skipped | Time |",
        "| ---: | ---: | ---: | ---: |",
        f"| {passed} | {len(failed)} | {skipped} | {seconds:.1f} s |",
        "",
    ]
    if failed:
        lines += ["| Failed test | Where | First assertion line |", "| --- | --- | --- |"]
        for name, file, line, message in failed:
            cell = message.replace("|", "\\|")
            lines.append(f"| `{name}` | `{file}:{line}` | {cell} |")
        lines.append("")
    run = os.environ.get("GITHUB_SERVER_URL", "") + "/" + os.environ.get("GITHUB_REPOSITORY", "")
    run_id = os.environ.get("GITHUB_RUN_ID")
    if run_id:
        lines.append(f"Full log and Hypothesis output: [run {run_id}]({run}/actions/runs/{run_id}).")
    Path(out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
