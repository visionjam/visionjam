#!/usr/bin/env python3
"""重新生成 README 里的代码语言分布图。

数据：GitHub languages API（按代码字节数），覆盖全部公开、非 fork、非归档仓库。
图表：QuickChart（https://quickchart.io）——现成的图表接口，本地不渲染。
由 .github/workflows/update-languages.yml 每周自动运行。
"""
from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request

USER = "visionjam"
README = "README.md"
START = "<!-- languages-chart:start -->"
END = "<!-- languages-chart:end -->"

TOP_N = 5
CHART_W, CHART_H = 700, 380

# GitHub 官方语言色；没有收录的走 FALLBACK
COLORS = {
    "Python": "#3572A5", "Kotlin": "#A97BFF", "HTML": "#E34C26", "CSS": "#563D7C",
    "Shell": "#89E051", "Lua": "#000080", "Batchfile": "#C1F12E",
    "JavaScript": "#F1E05A", "TypeScript": "#3178C6", "C++": "#F34B7D",
    "C": "#555555", "C#": "#178600", "Java": "#B07219", "Go": "#00ADD8",
    "Rust": "#DEA584", "Ruby": "#701516", "PHP": "#4F5D95", "Swift": "#F05138",
    "Dart": "#00B4AB", "Vue": "#41B883", "SCSS": "#C6538C", "TeX": "#3D6117",
    "Jupyter Notebook": "#DA5B0B", "Dockerfile": "#384D54", "Makefile": "#427819",
    "PowerShell": "#012456", "Nix": "#7E7EFF", "Zig": "#EC915C",
    "其他": "#BBBBBB",
}
FALLBACK = ["#8B949E", "#C9A227", "#6E7781", "#AFB8C1", "#57606A"]


def api(url: str):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "visionjam-profile-chart",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def public_repos():
    page = 1
    while True:
        batch = api(
            f"https://api.github.com/users/{USER}/repos"
            f"?per_page=100&type=owner&sort=updated&page={page}"
        )
        yield from batch
        if len(batch) < 100:
            return
        page += 1


def collect() -> dict[str, int]:
    totals: dict[str, int] = {}
    for repo in public_repos():
        if repo.get("fork") or repo.get("archived"):
            continue
        for lang, size in api(repo["languages_url"]).items():
            totals[lang] = totals.get(lang, 0) + int(size)
    return totals


def build_url(totals: dict[str, int]) -> str:
    total = sum(totals.values())
    if not total:
        raise SystemExit("没有拿到任何语言数据")

    ranked = sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))
    items = ranked[:TOP_N]
    rest = ranked[TOP_N:]
    if rest:
        items = items + [("其他", sum(size for _, size in rest))]

    pcts = [round(size / total * 100, 1) for _, size in items]
    pcts[0] = round(pcts[0] + (100.0 - sum(pcts)), 1)  # 抹平四舍五入误差

    labels = [f"{name} {pct:.1f}%" for (name, _), pct in zip(items, pcts)]
    colors = [COLORS.get(name, FALLBACK[i % len(FALLBACK)]) for i, (name, _) in enumerate(items)]

    for label, pct in zip(labels, pcts):
        print(f"{label:>18}")

    config = {
        "type": "doughnut",
        "data": {
            "labels": labels,
            "datasets": [{
                "data": pcts,
                "backgroundColor": colors,
                "borderColor": "#ffffff",
                "borderWidth": 2,
            }],
        },
        "options": {
            "cutout": "50%",
            "legend": {"position": "right", "labels": {"boxWidth": 14, "fontSize": 15, "padding": 12}},
            "plugins": {"datalabels": {"display": False}},
        },
    }
    encoded = urllib.parse.quote(json.dumps(config, ensure_ascii=False, separators=(",", ":")), safe="")
    return (
        f"https://quickchart.io/chart?width={CHART_W}&height={CHART_H}"
        f"&devicePixelRatio=1&bkg=white&c={encoded}"
    )


def update_readme(url: str) -> None:
    with open(README, encoding="utf-8", newline="") as fh:
        text = fh.read()

    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
    if len(pattern.findall(text)) != 1:
        raise SystemExit(f"README 里找不到唯一的 {START} ... {END} 标记")

    nl = "\r\n" if "\r\n" in text else "\n"
    block = nl.join([
        START,
        "代码语言分布（按代码字节统计，覆盖全部公开仓库）：",
        "",
        f"![代码语言分布]({url})",
        END,
    ])
    new = pattern.sub(lambda _m: block, text)

    if new == text:
        print("README 无需更新")
        return
    with open(README, "w", encoding="utf-8", newline="") as fh:
        fh.write(new)
    print("README 已更新")


if __name__ == "__main__":
    update_readme(build_url(collect()))
