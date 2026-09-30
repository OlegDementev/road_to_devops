#!/usr/bin/env python3
"""
Генератор оглавления репозитория road_to_devops.

Глобальное оглавление:
- Обходит все .md файлы (кроме служебных папок).
- Группирует по папкам верхнего уровня (блоки).
- Подставляет человекочитаемые названия блоков (BLOCK_NAMES).
- Извлекает номер главы из имени файла ('1.0', '2.3', '01', ...).
- Название главы берёт из первого заголовка '# ' (вне код-блоков).
- Формат: #### 3.0 [Название](путь/файл.md)
- Вставляет результат в README.md между <!-- TOC_START --> и <!-- TOC_END -->.

Локальное оглавление внутри файлов:
- Для .md файлов в FOLDERS_FOR_LOCAL_TOC.
- Поддерживает пользовательские якоря <a id="t_7.1.1"></a>:
    * якорь берётся из id и используется как '#t_7.1.1';
    * тег удаляется из текста заголовка;
    * номер ('7.1.1') извлекается из id и ставится перед названием.
- Если якоря нет — fallback на GitHub-подобный slug.
- Иерархия → 2 пробела на уровень, маркер списка '+'.
- Вставляется между <!-- LOCAL_TOC_START --> и <!-- LOCAL_TOC_END -->.
- Если маркеров нет — файл пропускается.

Проверки:
- все ссылки в README.md ведут на существующие файлы;
- все .md файлы репозитория попали в глобальное оглавление.

Выводит цветной отчёт и возвращает код 1 при найденных проблемах.
"""

import os
import re
import sys
from pathlib import Path
from urllib.parse import unquote

# ======================= НАСТРОЙКИ =======================


def find_repo_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / ".git").exists():
            return p
    return start


REPO_ROOT = find_repo_root(Path(__file__).resolve().parent)
README_FILE = REPO_ROOT / "README.md"

# --- глобальное оглавление ---
TOC_START = "<!-- TOC_START -->"
TOC_END = "<!-- TOC_END -->"

# --- локальные оглавления ---
LOCAL_TOC_START = "<!-- LOCAL_TOC_START -->"
LOCAL_TOC_END = "<!-- LOCAL_TOC_END -->"
LOCAL_TOC_HEADER = ""  # например "## Содержание" — если хочешь заголовок над списком

# В каких папках обновлять локальные оглавления (имена папок верхнего уровня).
# Поставь {"*"}, чтобы обрабатывать все папки.
FOLDERS_FOR_LOCAL_TOC = {"00_prepare", "01_git", "02_linux"}

# Заголовки с этими id полностью пропускаются в локальном оглавлении.
# Например 'title' — технический h2 "Оглавление" в начале файла.
SKIP_HEADING_IDS = {"title"}

# --- исключения ---
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
    "resources",
}

EXCLUDE_FILES = {"README.md", "TOC.md"}

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


def col(text: str, color: str) -> str:
    return f"{color}{text}{C.RESET}" if C.on() else text


def ok(msg):
    print(col("  ✓ ", C.GREEN) + msg)


def warn(msg):
    print(col("  ⚠ ", C.YELLOW) + msg)


def err(msg):
    print(col("  ✗ ", C.RED) + msg)


def info(msg):
    print(col("  • ", C.CYAN) + msg)


# ======================= ОБЩИЕ ХЕЛПЕРЫ =======================


def extract_chapter_number(path: Path) -> str:
    stem = path.stem
    m = re.match(r"^(\d+(?:\.\d+)+)(?:[_\-\s]|$)", stem)
    if m:
        return m.group(1)
    m = re.match(r"^(\d+)(?:[_\-\s]|$)", stem)
    if m:
        return m.group(1)
    return ""


def get_first_heading(file_path: Path) -> str:
    in_code = False
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                s = line.rstrip("\n")
                stripped = s.lstrip()
                if stripped.startswith("```") or stripped.startswith("~~~"):
                    in_code = not in_code
                    continue
                if in_code:
                    continue
                st = s.strip()
                if st.startswith("# "):
                    # Убираем пользовательский якорь, если есть
                    st = re.sub(r"\s*<a\s+id=\"[^\"]+\"\s*></a>\s*$", "", st)
                    return st[2:].strip()
    except Exception:
        pass
    return file_path.stem


def strip_number_prefix(title: str) -> str:
    title = re.sub(r"^\d+(?:[\.\-]\d+)*[\.\)\_\-\s]+", "", title).strip()
    return title.replace("_", " ")


def collect_md_files(root: Path):
    md_files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames if d not in EXCLUDE_DIRS and not d.startswith(".")
        ]
        for fname in filenames:
            if fname.lower().endswith(".md") and fname not in EXCLUDE_FILES:
                full = Path(dirpath) / fname
                rel = full.relative_to(root)
                md_files.append((rel, full))
    return md_files


def encode_link(rel: Path) -> str:
    """Минимальное экранирование для markdown-ссылок: ( ) и пробел."""
    path = str(rel).replace("\\", "/")
    return path.replace(" ", "%20").replace("(", "%28").replace(")", "%29")


# ======================= ГЛОБАЛЬНОЕ ОГЛАВЛЕНИЕ =======================


def build_structure(md_files):
    blocks = {}
    for rel, full in md_files:
        parts = rel.parts
        block = parts[0] if len(parts) > 1 else "."

        chapter = extract_chapter_number(rel)
        raw_title = get_first_heading(full)
        title = strip_number_prefix(raw_title) or raw_title.replace("_", " ")

        blocks.setdefault(block, []).append((chapter, title, rel))

    for items in blocks.values():

        def sort_key(item):
            chapter, _title, rel = item
            if chapter:
                nums = tuple(int(p) for p in chapter.split("."))
                return (0, nums, str(rel).lower())
            return (1, (), str(rel).lower())

        items.sort(key=sort_key)

    return blocks


def render_toc(blocks) -> str:
    lines: list[str] = []
    for block in sorted(blocks.keys()):
        if block == ".":
            block_title = "Файлы в корне репозитория"
        else:
            block_title = BLOCK_NAMES.get(block, block)
        lines.append(f"### {block_title}\n")

        for chapter, title, rel in blocks[block]:
            link = encode_link(rel)
            if chapter:
                lines.append(f"#### {chapter} [{title}]({link})")
            else:
                lines.append(f"#### [{title}]({link})")

        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def update_readme(readme_path: Path, toc_content: str) -> None:
    if not readme_path.exists():
        raise FileNotFoundError(
            f"Файл {readme_path} не найден. Создай README.md или укажи другой путь."
        )

    text = readme_path.read_text(encoding="utf-8")

    if TOC_START not in text or TOC_END not in text:
        raise ValueError(
            f"В {readme_path.name} не найдены маркеры.\n"
            f"Добавь их один раз в нужное место файла:\n"
            f"    {TOC_START}\n"
            f"    {TOC_END}"
        )

    start_idx = text.index(TOC_START) + len(TOC_START)
    end_idx = text.index(TOC_END)

    if start_idx > end_idx:
        raise ValueError(f"Неправильный порядок маркеров в {readme_path.name}.")

    new_text = text[:start_idx] + "\n\n" + toc_content + "\n" + text[end_idx:]
    readme_path.write_text(new_text, encoding="utf-8")


# ======================= ЛОКАЛЬНОЕ ОГЛАВЛЕНИЕ =======================

# Пользовательский якорь в конце заголовка: <a id="t_7.1.1"></a>
ANCHOR_RE = re.compile(r'<a\s+id="([^"]+)"\s*></a>\s*$', re.IGNORECASE)
# Число в якоре: 't_7.1.1' → '7.1.1'
NUMBER_IN_ANCHOR_RE = re.compile(r"(\d+(?:\.\d+)*)")


def slugify(text: str) -> str:
    """GitHub-подобный slug (fallback, если нет <a id=...>)."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)

    text = text.lower().strip()
    text = re.sub(r"[^\w\s\-]", "", text, flags=re.UNICODE)
    text = re.sub(r"\s+", "-", text)
    return text


def collect_headings(file_path: Path) -> list[tuple[int, str, str | None]]:
    """
    Все заголовки ## и глубже вне код-блоков и вне блока LOCAL_TOC.
    Возвращает список (level, text_without_anchor, anchor_id_or_None).
    Заголовки, чей id в SKIP_HEADING_IDS, пропускаются.
    """
    headings: list[tuple[int, str, str | None]] = []
    in_code = False
    in_toc = False
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                s = line.rstrip("\n")
                stripped = s.strip()

                if LOCAL_TOC_START in stripped:
                    in_toc = True
                    continue
                if LOCAL_TOC_END in stripped:
                    in_toc = False
                    continue
                if in_toc:
                    continue

                if stripped.startswith("```") or stripped.startswith("~~~"):
                    in_code = not in_code
                    continue
                if in_code:
                    continue

                m = re.match(r"^(#{2,6})\s+(.+?)\s*$", s)
                if not m:
                    continue

                level = len(m.group(1))
                text = m.group(2).strip()

                anchor_id = None
                am = ANCHOR_RE.search(text)
                if am:
                    anchor_id = am.group(1)
                    text = text[: am.start()].strip()

                if anchor_id and anchor_id in SKIP_HEADING_IDS:
                    continue

                headings.append((level, text, anchor_id))
    except Exception:
        pass
    return headings


def render_local_toc(headings: list[tuple[int, str, str | None]]) -> str:
    """
    Формат строки:
        + 7.1.1 [uptime [uptime]](#t_7.1.1)
    Номер берётся из якоря <a id="t_7.1.1"> и ставится ПЕРЕД ссылкой.
    Если якоря нет — используется GitHub-slug (без номера).
    """
    if not headings:
        return ""

    base = min(h[0] for h in headings)
    seen: dict[str, int] = {}
    lines: list[str] = []

    if LOCAL_TOC_HEADER:
        lines.append(LOCAL_TOC_HEADER)
        lines.append("")

    for level, text, anchor_id in headings:
        indent = "  " * (level - base)

        if anchor_id:
            anchor = anchor_id
            nm = NUMBER_IN_ANCHOR_RE.search(anchor_id)
            number = nm.group(1) if nm else ""
        else:
            slug = slugify(text)
            n = seen.get(slug, 0)
            seen[slug] = n + 1
            anchor = slug if n == 0 else f"{slug}-{n}"
            number = ""

        if number:
            lines.append(f"{indent}+ {number} [{text}](#{anchor})")
        else:
            lines.append(f"{indent}+ [{text}](#{anchor})")

    return "\n".join(lines) + "\n"


def update_local_toc_in_file(path: Path) -> str:
    """
    Обновляет локальное оглавление в файле, если в нём есть маркеры.
    Возвращает: 'updated' | 'unchanged' | 'no-markers' | 'error:...'
    """
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as e:
        return f"error:{e}"

    if LOCAL_TOC_START not in text or LOCAL_TOC_END not in text:
        return "no-markers"

    start_idx = text.index(LOCAL_TOC_START) + len(LOCAL_TOC_START)
    end_idx = text.index(LOCAL_TOC_END)

    if start_idx > end_idx:
        return "error:порядок маркеров нарушен"

    headings = collect_headings(path)
    toc = render_local_toc(headings)

    new_text = text[:start_idx] + "\n\n" + toc + "\n" + text[end_idx:]

    if new_text == text:
        return "unchanged"

    path.write_text(new_text, encoding="utf-8")
    return "updated"


# ======================= ПРОВЕРКА ССЫЛОК В README =======================

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def extract_links(md_text: str) -> list[str]:
    links = []
    for m in LINK_RE.finditer(md_text):
        target = m.group(1).strip()
        if "#" in target:
            target = target.split("#", 1)[0]
        if not target:
            continue
        if target.startswith(("http://", "https://", "mailto:", "ftp://", "#")):
            continue
        links.append(unquote(target))
    return links


def check_links_in_readme(readme_path: Path) -> list[str]:
    text = readme_path.read_text(encoding="utf-8")
    broken = []
    for target in extract_links(text):
        normalized = target.replace("\\", "/").lstrip("./")
        full = (readme_path.parent / normalized).resolve()
        if not full.exists():
            broken.append(target)
    return broken


def check_files_in_toc(blocks) -> list[str]:
    real, in_toc = set(), set()
    for items in blocks.values():
        for _chapter, _title, rel in items:
            real.add(str(rel).replace("\\", "/"))
            in_toc.add(str(rel).replace("\\", "/"))
    return sorted(real - in_toc)


# ======================= MAIN =======================


def main() -> int:
    md_files = collect_md_files(REPO_ROOT)
    if not md_files:
        err("Не найдено ни одного .md файла.")
        return 1

    # ------- 1. Локальные оглавления -------
    print(col("Локальные оглавления…", C.BOLD))
    local_updated = local_unchanged = local_skipped = local_errors = 0
    errors: list[tuple[str, str]] = []

    for rel, full in md_files:
        parts = rel.parts
        top = parts[0] if len(parts) > 1 else "."

        if FOLDERS_FOR_LOCAL_TOC != {"*"} and top not in FOLDERS_FOR_LOCAL_TOC:
            continue

        result = update_local_toc_in_file(full)
        if result == "updated":
            local_updated += 1
            info(f"обновлён: {rel}")
        elif result == "unchanged":
            local_unchanged += 1
        elif result == "no-markers":
            local_skipped += 1
        else:
            local_errors += 1
            errors.append((str(rel), result))

    if local_updated:
        ok(f"Обновлено локальных оглавлений: {local_updated}")
    if local_unchanged:
        info(f"Без изменений: {local_unchanged}")
    if local_skipped:
        warn(f"Пропущено (нет маркеров): {local_skipped}")
    for rel, msg in errors:
        err(f"{rel}: {msg}")

    # ------- 2. Глобальное оглавление -------
    print(col("Глобальное оглавление…", C.BOLD))
    blocks = build_structure(md_files)
    toc_md = render_toc(blocks)

    try:
        update_readme(README_FILE, toc_md)
    except (FileNotFoundError, ValueError) as e:
        err(str(e))
        return 1

    ok(f"Оглавление обновлено: {README_FILE.relative_to(REPO_ROOT)}")
    info(f"Файлов: {len(md_files)}, блоков: {len(blocks)}")

    # ------- 3. Проверки -------
    print(col("Проверка ссылок…", C.BOLD))
    broken = check_links_in_readme(README_FILE)
    if broken:
        err(f"Найдено битых ссылок: {len(broken)}")
        for b in broken:
            print(f"      → {b}")
    else:
        ok("Все ссылки в README ведут на существующие файлы.")

    missing = check_files_in_toc(blocks)
    if missing:
        err(f"Файлов вне оглавления: {len(missing)}")
        for m in missing:
            print(f"      → {m}")
    else:
        ok("Все .md файлы репозитория попали в оглавление.")

    # ------- 4. Итог -------
    if broken or missing or local_errors:
        print(col("\nИтог: обнаружены проблемы (см. выше).", C.RED + C.BOLD))
        return 1

    print(col("\nИтог: всё чисто ✓", C.GREEN + C.BOLD))
    return 0


if __name__ == "__main__":
    sys.exit(main())
