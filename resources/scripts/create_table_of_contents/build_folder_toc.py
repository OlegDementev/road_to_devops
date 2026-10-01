#!/usr/bin/env python3
"""
Сборщик общего оглавления папки (0.0_Оглавление.md).

Для каждой папки из FOLDERS:
- Собирает все .md файлы, кроме 0.0_Оглавление.md.
- Из каждого берёт локальное оглавление между LOCAL_TOC_START и LOCAL_TOC_END.
- Локальные ссылки #anchor превращает в имя_файла.md#anchor,
  чтобы они работали из общего файла.
- Формирует секцию для каждого файла:
      ## 7.0 [Мониторинг и процессы](7.0_Мониторинг_и_процессы.md)

      + 7.1 [Обзор системы](7.0_...#t_7.1)
        + 7.1.1 [uptime](7.0_...#t_7.1.1)
- Пишет результат в <папка>/0.0_Оглавление.md между AUTO_TOC_START / AUTO_TOC_END.

Если 0.0_Оглавление.md нет — создаёт его с базовой структурой.
Если файл есть, но маркеров нет — сообщает об ошибке.
"""

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

# Папки, для которых строим общее оглавление (имена папок верхнего уровня).
FOLDERS = {"02_linux"}

# Имя файла-оглавления внутри каждой папки.
TOC_FILENAME = "0.0_Оглавление.md"

# Маркеры внутри 0.0_Оглавление.md — между ними вставляется содержимое.
AUTO_TOC_START = "<!-- AUTO_TOC_START -->"
AUTO_TOC_END = "<!-- AUTO_TOC_END -->"

# Маркеры локального оглавления внутри каждого .md-файла.
LOCAL_TOC_START = "<!-- LOCAL_TOC_START -->"
LOCAL_TOC_END = "<!-- LOCAL_TOC_END -->"

# Не использовать эти файлы как источники.
EXCLUDE_FILES = {TOC_FILENAME, "README.md"}

# Убирать первую строку локального оглавления, если она соответствует самому файлу.
# Пример: файл '7.0_Мониторинг_и_процессы.md', а локальное оглавление начинается с
# '+ 7.0 [Мониторинг и процессы](#t_7.0)'. Если True — эта строка отбрасывается,
# потому что то же самое уже стоит в заголовке секции '## 7.0 [...]'.
STRIP_SELF_HEADER = True

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


# ======================= ХЕЛПЕРЫ =======================


def encode_link(path_str: str) -> str:
    """Минимальное экранирование для markdown-ссылок: ( ) и пробел."""
    return (
        path_str.replace("\\", "/")
        .replace(" ", "%20")
        .replace("(", "%28")
        .replace(")", "%29")
    )


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
    """Первый заголовок '# ' (устойчиво к BOM и разным пробелам).
    Убирает <a id=...> и номер, подчёркивания → пробелы."""
    in_code = False
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for raw in f:
                # убираем BOM и \r
                line = raw.lstrip("\ufeff").rstrip("\n").rstrip("\r")
                stripped = line.lstrip()
                if stripped.startswith("```") or stripped.startswith("~~~"):
                    in_code = not in_code
                    continue
                if in_code:
                    continue
                # заголовок h1: '#', '\t' или пробелы после решётки
                m = re.match(r"^#\s+(.+?)\s*$", line.strip())
                if not m:
                    continue
                title = m.group(1)
                # убрать <a id="..."></a> в конце
                title = re.sub(
                    r'\s*<a\s+id="[^"]+"\s*>(?:\s*</a>)?\s*$',
                    "",
                    title,
                    flags=re.IGNORECASE,
                )
                # убрать номер главы в начале
                title = re.sub(r"^\d+(?:[\.\-]\d+)*[\.\)\_\-\s]+", "", title).strip()
                # подчёркивания → пробелы
                title = title.replace("_", " ")
                return title
    except Exception:
        pass

    # fallback: чистим имя файла тем же способом
    fallback = file_path.stem.replace("_", " ")
    fallback = re.sub(r"^\d+(?:[\.\-]\d+)*[\.\)\_\-\s]+", "", fallback).strip()
    return fallback or file_path.stem


def extract_local_toc(file_path: Path) -> str | None:
    """Возвращает содержимое между LOCAL_TOC_START и LOCAL_TOC_END, либо None."""
    try:
        text = file_path.read_text(encoding="utf-8")
    except Exception:
        return None

    if LOCAL_TOC_START not in text or LOCAL_TOC_END not in text:
        return None

    s = text.index(LOCAL_TOC_START) + len(LOCAL_TOC_START)
    e = text.index(LOCAL_TOC_END)
    if s > e:
        return None
    return text[s:e].strip("\n")


def rewrite_anchors(toc_text: str, target_file: str) -> str:
    """Заменяет (#anchor) на (target_file#anchor), сохраняя отступы и '+ '."""
    encoded = encode_link(target_file)
    return re.sub(r"\]\(#([^)]+)\)", rf"]({encoded}#\1)", toc_text)


def strip_self_header(toc_text: str, file_chapter: str) -> str:
    """
    Убирает первую строку, если она соответствует самому файлу (по номеру главы),
    и сдвигает отступы оставшихся строк влево на 2 пробела.
    """
    if not file_chapter:
        return toc_text

    lines = toc_text.split("\n")
    if not lines:
        return toc_text

    first = lines[0].strip()
    pattern = rf"^\+\s*{re.escape(file_chapter)}(?![\d\.])\b"
    if not re.match(pattern, first):
        return toc_text

    rest = lines[1:]
    fixed: list[str] = []
    for ln in rest:
        if ln.startswith("  "):
            fixed.append(ln[2:])
        else:
            fixed.append(ln)

    # убираем возможные пустые строки в начале
    while fixed and not fixed[0].strip():
        fixed.pop(0)
    return "\n".join(fixed).rstrip()


# ======================= СБОРКА =======================


def collect_source_files(folder: Path) -> list[Path]:
    """Все .md в папке (не рекурсивно), кроме EXCLUDE_FILES. Сортировка по номеру главы."""
    files: list[Path] = []
    for entry in folder.iterdir():
        if not entry.is_file():
            continue
        if entry.suffix.lower() != ".md":
            continue
        if entry.name in EXCLUDE_FILES:
            continue
        files.append(entry)

    def sort_key(p: Path):
        n = extract_chapter_number(p.name)
        if n:
            nums = tuple(int(x) for x in n.split("."))
            return (0, nums, p.name.lower())
        return (1, (), p.name.lower())

    files.sort(key=sort_key)
    return files


def build_folder_toc(folder: Path) -> tuple[str, list[str]]:
    """Возвращает (markdown-оглавление_папки, список_предупреждений)."""
    files = collect_source_files(folder)
    if not files:
        return "", [f"нет .md файлов (кроме {TOC_FILENAME})"]

    warnings: list[str] = []
    sections: list[str] = []

    for f in files:
        chapter = extract_chapter_number(f.name)
        title = get_file_title(f)

        if chapter:
            header = f"{chapter} [{title}]({encode_link(f.name)})"
        else:
            header = f"[{title}]({encode_link(f.name)})"
        sections.append(header)
        sections.append("")

        local = extract_local_toc(f)
        if local is None:
            warnings.append(f"{f.name}: нет маркеров локального оглавления")
            continue

        if STRIP_SELF_HEADER:
            local = strip_self_header(local, chapter)

        if not local.strip():
            warnings.append(f"{f.name}: локальное оглавление пустое")
            continue

        sections.append(rewrite_anchors(local, f.name))
        sections.append("")

    return "\n".join(sections).rstrip() + "\n", warnings


def write_folder_toc(folder: Path, toc_md: str) -> str:
    """
    Записывает оглавление в <folder>/0.0_Оглавление.md между AUTO_TOC_START/END.
    Если файла нет — создаёт.
    Возвращает: 'created' | 'updated' | 'unchanged' | 'error:...'
    """
    target = folder / TOC_FILENAME
    created = False

    if not target.exists():
        base = (
            f"# {Path(TOC_FILENAME).stem}\n\n" f"{AUTO_TOC_START}\n" f"{AUTO_TOC_END}\n"
        )
        target.write_text(base, encoding="utf-8")
        created = True

    try:
        text = target.read_text(encoding="utf-8")
    except Exception as e:
        return f"error:{e}"

    if AUTO_TOC_START not in text or AUTO_TOC_END not in text:
        return (
            f"error:в {TOC_FILENAME} нет маркеров " f"{AUTO_TOC_START} / {AUTO_TOC_END}"
        )

    s = text.index(AUTO_TOC_START) + len(AUTO_TOC_START)
    e = text.index(AUTO_TOC_END)
    if s > e:
        return "error:порядок маркеров нарушен"

    new_text = text[:s] + "\n\n" + toc_md + "\n" + text[e:]

    if new_text == text:
        return "unchanged"

    target.write_text(new_text, encoding="utf-8")
    return "created" if created else "updated"


# ======================= MAIN =======================


def main() -> int:
    print(col("Сборка общих оглавлений по папкам…", C.BOLD))

    if not FOLDERS:
        err("Список FOLDERS пуст. Укажи хотя бы одну папку.")
        return 1

    total_updated = total_unchanged = total_errors = 0
    all_warnings: list[tuple[str, str]] = []

    for folder_name in sorted(FOLDERS):
        folder = REPO_ROOT / folder_name
        if not folder.is_dir():
            err(f"Папка не найдена: {folder_name}")
            total_errors += 1
            continue

        print(col(f"→ {folder_name}", C.CYAN + C.BOLD))

        toc_md, warnings = build_folder_toc(folder)
        for w in warnings:
            all_warnings.append((folder_name, w))

        if not toc_md.strip():
            warn("нечего собирать")
            continue

        result = write_folder_toc(folder, toc_md)
        if result == "created":
            ok(f"создан {TOC_FILENAME}")
            total_updated += 1
        elif result == "updated":
            ok(f"обновлён {TOC_FILENAME}")
            total_updated += 1
        elif result == "unchanged":
            info(f"без изменений: {TOC_FILENAME}")
            total_unchanged += 1
        else:
            err(f"{folder_name}: {result}")
            total_errors += 1

    print()
    if total_updated:
        ok(f"Обновлено файлов: {total_updated}")
    if total_unchanged:
        info(f"Без изменений: {total_unchanged}")
    if all_warnings:
        warn(f"Предупреждений: {len(all_warnings)}")
        for folder_name, w in all_warnings:
            print(f"      {folder_name}: {w}")
    if total_errors:
        err(f"Ошибок: {total_errors}")
        print(col("\nИтог: обнаружены проблемы.", C.RED + C.BOLD))
        return 1

    print(col("\nИтог: всё чисто ✓", C.GREEN + C.BOLD))
    return 0


if __name__ == "__main__":
    sys.exit(main())
