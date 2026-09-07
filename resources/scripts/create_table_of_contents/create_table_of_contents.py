import os

# Укажите директорию, где лежит этот файл
INP_DIR_NAME = "01_linux"

# Укажите имя файла.md для которого необходимо сделать оглавление
INP_FILE_NAME = (
    "4.0_Работа_с_окружением,_переменные,_потоки_данных,_текстовые_редакторы.md"
)

# Путь до директории со скриптом
SCRIPT_DIR_PATH = os.path.dirname(os.path.abspath(__file__))

# Путь до основной директории
BASE_DIR_PATH = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

# Расшифровка пути для входного файла
INP_FILE_PATH = os.path.join(BASE_DIR_PATH, INP_DIR_NAME, INP_FILE_NAME)

# Исходящий файл
OUT_FILE_PATH = os.path.join(SCRIPT_DIR_PATH, "contents_tmp.md")

MAX_LINE_LEN = 99


def create_contents():
    with open(INP_FILE_PATH, "r", encoding="utf-8") as inp_f, open(
        OUT_FILE_PATH, "w", encoding="utf-8"
    ) as out_f:

        for line_number, line in enumerate(inp_f, start=1):
            if line.startswith(("## ", "### ", "#### ", "##### ")):

                # Определяем уровень, чтобы задать отступ (опционально)
                level = line.count("#")
                intent = ("+ ", "  + ", "    + ", "      + ")[level - 2]
                title = f"{line[line.find("# "):line.find(' <a')]}"[2::]
                number = f"{line[line.find("t_"):line.find('"></a>')]}"[2::]
                if title in ("Оглавление "):
                    continue
                # Формируем Markdown-ссылку без учета номера страницы
                # link_line = f"{intent}{number} [{title}](#t_{number})"

                # Сколько символов необходимо до полной длины строки
                # cnt_symbols = MAX_LINE_LEN - len(link_line)

                # Формируем Markdown-ссылку c номером страницы
                link_line = f"{intent}{number} [{title}](#t_{number})\n"
                out_f.write(link_line)


if __name__ == "__main__":
    print(
        INP_DIR_NAME,
        INP_FILE_NAME,
        SCRIPT_DIR_PATH,
        BASE_DIR_PATH,
        INP_FILE_PATH,
        OUT_FILE_PATH,
        sep="\n",
    )
    create_contents()
