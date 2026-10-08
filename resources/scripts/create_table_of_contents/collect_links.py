#!/usr/bin/env python3
"""
Сборщик интернет-ссылок из всех .md файлов репозитория.

- Рекурсивно обходит все .md файлы (кроме служебных папок и helpers/).
- Находит только markdown-ссылки вида [текст](http... или https...).
- «Голые» URL, mailto, ftp и относительные ссылки игнорируются.
- Дедуплицирует в пределах файла.
- Группирует по папкам верхнего уровня и по файлам.
- Заголовок раздела выводится обычным текстом (без ссылки на файл).
- Сохраняет результат в helpers/links.md.
"""

import os
import re
import sys
from pathlib import Path

# ======================= НАСТРОЙКИ =======================


def find_repo_root(start: Path) -> Path:
    """Поднимается вверх от start, пока не найдёт папку .git."""
    for p in [start, *start.parents]:
        if (p / ".git").exists():
            return p
    return start


REPO_ROOT = find_repo_root(Path(__file__).resolve().parent)

OUTPUT_DIR = REPO_ROOT / "helpers"
OUTPUT_FILE = OUTPUT_DIR / "links.md"

# Служебные папки. helpers/ исключён, чтобы скрипт не читал свой же отчёт.
EXCLUDE_DIRS = {
    ".git",
    "__pycache__",
    "venv",
    ".venv",
    "env",
    "node_modules",
    ".idea",
    ".vscode",
    ".mypy_cache",
    ".pytest_cache",
    "dist",
    "build",
    "helpers",
}

# Файлы, которые не сканируем.
EXCLUDE_FILES = {"README.md"}

# URL, которые не попадут в отчёт (бейджи, аналитика и т.п.).
EXCLUDE_URL_PATTERNS: list[str] = [
    # r"shields\.io",
    # r"badgen\.net",
]

BLOCK_NAMES = {
    "00_prepare": "⚙️ Подготовительный блок",
    "01_git": "🌳 Блок Git",
    "02_linux": "🐧 Блок Linux",
    "03_networks": "🌐 Блок сети",
    "04_docker": "🐳 Блок Docker",
    "05_ci_cd": "🔁 Блок CI/CD",
    "06_k8s": "☸️ Блок Kubernetes",
}

# ======================= ЦВЕТНОЙ ВЫВОД =======================


class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    CYAN = "\033[36m"

    @staticmethod
    def on() -> bool:
        return sys.stdout.isatty()


def col(t: str, c: str) -> str:
    return f"{c}{t}{C.RESET}" if C.on() else t


def ok(m):
    print(col("  ✓ ", C.GREEN) + m)


def warn(m):
    print(col("  ⚠ ", C.YELLOW) + m)


def err(m):
    print(col("  ✗ ", C.RED) + m)


def info(m):
    print(col("  • ", C.CYAN) + m)


# ======================= ПОИСК ССЫЛОК =======================

# Только markdown-ссылки, где цель начинается с http:// или https://.
# Опциональный title в кавычках — поддерживается.
MD_LINK_RE = re.compile(
    r'\[([^\]]+)\]\(\s*(https?://[^)\s]+?)(?:\s+"[^"]*")?\s*\)',
    re.IGNORECASE,
)

TRAILING = ".,;:!?"


def strip_url(url: str) -> str:
    return url.rstrip(TRAILING)


def is_excluded_url(url: str) -> bool:
    return any(re.search(p, url) for p in EXCLUDE_URL_PATTERNS)


def extract_links_from_text(text: str) -> list[tuple[str, str]]:
    """Возвращает [(url, title)] из markdown-ссылок на http/https."""
    result: list[tuple[str, str]] = []
    seen: set[str] = set()

    for m in MD_LINK_RE.finditer(text):
        title = m.group(1).strip()
        url = strip_url(m.group(2))
        if is_excluded_url(url) or url in seen:
            continue
        seen.add(url)
        result.append((url, title))

    return result


def collect_md_files(root: Path):
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames if d not in EXCLUDE_DIRS and not d.startswith(".")
        ]
        for fname in filenames:
            if fname.lower().endswith(".md") and fname not in EXCLUDE_FILES:
                full = Path(dirpath) / fname
                files.append((full.relative_to(root), full))
    files.sort(key=lambda x: str(x[0]).lower())
    return files


# ======================= ХЕЛПЕРЫ ДЛЯ НАЗВАНИЙ =======================


def extract_chapter_number(filename: str) -> str:
    stem = Path(filename).stem
    m = re.match(r"^(\d+(?:\.\d+)+)(?:[_\-\s]|$)", stem)
    if m:
        return m.group(1)
    m = re.match(r"^(\d+)(?:[_\-\s]|$)", stem)
    if m:
        return m.group(1)
    return ""


def get_file_title(file_path: Path) -> str:
    """Первый заголовок '# ' (устойчиво к BOM). Убирает <a id=...> и номер."""
    in_code = False
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.lstrip("\ufeff").rstrip("\r\n")
                s = line.lstrip()
                if s.startswith("```") or s.startswith("~~~"):
                    in_code = not in_code
                    continue
                if in_code:
                    continue
                m = re.match(r"^#\s+(.+?)\s*$", line.strip())
                if not m:
                    continue
                title = m.group(1)
                title = re.sub(
                    r'\s*<a\s+id="[^"]+"\s*>(?:\s*</a>)?\s*$',
                    "",
                    title,
                    flags=re.IGNORECASE,
                )
                title = re.sub(r"^\d+(?:[\.\-]\d+)*[\.\)\_\-\s]+", "", title).strip()
                return title.replace("_", " ")
    except Exception:
        pass
    fb = file_path.stem.replace("_", " ")
    return re.sub(r"^\d+(?:[\.\-]\d+)*[\.\)\_\-\s]+", "", fb).strip() or file_path.stem


# ======================= СБОРКА ОТЧЁТА =======================


def build_report(md_files):
    """
    Возвращает (structure, total, unique).
    structure: {block: [(rel, chapter, title, [(url, link_title), ...]), ...]}
    """
    structure: dict[str, list] = {}
    all_unique: set[str] = set()
    total = 0

    for rel, full in md_files:
        try:
            text = full.read_text(encoding="utf-8")
        except Exception:
            continue

        links = extract_links_from_text(text)
        if not links:
            continue

        total += len(links)
        for url, _ in links:
            all_unique.add(url)

        parts = rel.parts
        block = parts[0] if len(parts) > 1 else "."
        chapter = extract_chapter_number(rel)
        title = get_file_title(full)
        structure.setdefault(block, []).append((rel, chapter, title, links))

    for items in structure.values():

        def key(item):
            _rel, ch, _t, _l = item
            if ch:
                return (0, tuple(int(x) for x in ch.split(".")), str(_rel).lower())
            return (1, (), str(_rel).lower())

        items.sort(key=key)

    return structure, total, len(all_unique)


def render(structure, total: int, unique: int) -> str:
    files_with_links = sum(len(v) for v in structure.values())
    lines: list[str] = []

    lines.append("# 🌐 Интернет-ссылки\n")
    lines.append("> Автоматически собрано скриптом `collect_links.py`.\n")
    lines.append(
        f"> Файлов с ссылками: **{files_with_links}** · "
        f"Ссылок: **{total}** · Уникальных: **{unique}**\n"
    )
    lines.append("\n---\n")

    for block in sorted(structure.keys()):
        block_title = (
            "Файлы в корне репозитория"
            if block == "."
            else BLOCK_NAMES.get(block, block)
        )
        lines.append(f"## {block_title}\n")

        for _rel, chapter, title, links in structure[block]:
            # Заголовок раздела — обычный текст, без ссылки на файл.
            label = f"{chapter} {title}".strip() if chapter else title
            lines.append(f"### {label}\n")
            for url, link_title in links:
                lines.append(f"- [{link_title}]({url})")
            lines.append("")

        lines.append("---\n")

    return "\n".join(lines).rstrip() + "\n"


# ======================= MAIN =======================


def main() -> int:
    print(col("Сбор интернет-ссылок из .md файлов…", C.BOLD))

    md_files = collect_md_files(REPO_ROOT)
    if not md_files:
        err("Не найдено ни одного .md файла.")
        return 1

    structure, total, unique = build_report(md_files)

    if total == 0:
        warn("Интернет-ссылок не найдено.")
        return 0

    OUTPUT_DIR.mkdir(exist_ok=True)
    report = render(structure, total, unique)
    OUTPUT_FILE.write_text(report, encoding="utf-8")

    files_with_links = sum(len(v) for v in structure.values())
    ok(f"Отчёт сохранён: {OUTPUT_FILE.relative_to(REPO_ROOT)}")
    info(f"Просканировано файлов: {len(md_files)}, с ссылками: {files_with_links}")
    info(f"Ссылок: {total}, уникальных: {unique}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
