import os
import ctypes
from ctypes import wintypes

import win32api
import win32gui
import win32con
import ctypes
import struct
import time
from pywinauto import Desktop
from pywinauto.controls.uia_controls import ListViewWrapper # Для более точной подсказки типов
import logging
import configparser # Добавляем импорт для работы с файлами .url
import sys
import os
import re
import json  # Для примера данных

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# --- Определение структур Windows API с помощью ctypes ---

# Константы для VirtualAllocEx
MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
MEM_RELEASE = 0x8000
PAGE_READWRITE = 0x04

# !!! ДОБАВЛЕННЫЕ КОНСТАНТЫ ДЛЯ LISTVIEW !!!
LVM_FIRST = 0x1000
LVM_GETITEMCOUNT = LVM_FIRST + 4
LVM_GETITEMTEXTW = LVM_FIRST + 75
LVM_GETITEMPOSITION = LVM_FIRST + 16
LVM_SETITEMPOSITION = LVM_FIRST + 15

LVIF_TEXT = 0x0001 # Флаг для LVITEM.mask, чтобы указать, что нужен текст

# Загрузка DLL-библиотек
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
user32 = ctypes.WinDLL('user32', use_last_error=True)

# Структура LVITEM (ListView Item) для получения текста
class LVITEM(ctypes.Structure):
    _fields_ = [
        ("mask", wintypes.UINT),
        ("iItem", wintypes.INT),
        ("iSubItem", wintypes.INT),
        ("state", wintypes.UINT),
        ("stateMask", wintypes.UINT),
        ("pszText", wintypes.LPWSTR),  # LPWSTR для Unicode (wide string)
        ("cchTextMax", wintypes.INT),
        ("iImage", wintypes.INT),
        ("lParam", wintypes.LPARAM),
        ("iIndent", wintypes.INT),
        ("iGroupId", wintypes.INT),
        ("cColumns", wintypes.UINT),
        ("puColumns", ctypes.POINTER(wintypes.UINT)),
        ("piColFmt", ctypes.POINTER(wintypes.INT)),
        ("iGroup", wintypes.INT),
    ]

# Структура POINT для получения координат
class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


def load_game_titles(filename="game_titles.txt") -> list:
    """
    Загружает названия игр из файла.

    Args:
        filename (str): Имя файла для загрузки. По умолчанию "game_titles.txt".

    Returns:
        list: Список названий игр в нижнем регистре.
              Возвращает пустой список в случае ошибки.
    """
    game_titles = []
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            for line in f:
                game_titles.append(line.strip().lower())
        logging.info(f"Успешно загружено {len(game_titles)} названий игр из файла '{filename}'.")
    except FileNotFoundError:
        logging.warning(f"Файл с названиями игр '{filename}' не найден. Используется пустой список игр.")
    except Exception as e:
        logging.error(f"Произошла ошибка при чтении файла '{filename}': {e}")
    return game_titles


def get_icon_category(icon_info: dict, game_titles: list) -> str:
    """
    Определяет категорию иконки на основе ее информации и списка названий игр.
    Использует расширенную информацию об иконке, включая оригинальное имя и тип.
    """
    # Инициализация переменных из icon_info
    name_lower = icon_info['name'].lower() # Имя для классификации (например, имя цели ярлыка)
    resolved_icon_type_lower = icon_info['type'].lower() if icon_info['type'] else "неизвестный тип"
    path_lower = icon_info['full_path'].lower() if icon_info['full_path'] else ""
    original_icon_name_lower = icon_info['original_icon_name'].lower()
    original_desktop_type_lower = icon_info['original_desktop_type'].lower()

    file_extension = None
    if path_lower and resolved_icon_type_lower != "папка" and \
       not path_lower.startswith("http") and \
       not path_lower.startswith("steam:") and \
       not path_lower.startswith("epicgames:") and \
       '.' in os.path.basename(path_lower):
        file_extension = os.path.splitext(os.path.basename(path_lower))[1].lower()

    # Определения списков и словарей
    system_names_exact = ["корзина", "этот компьютер", "мой компьютер", "панель управления", "network", "сеть", "computer", "control panel", "recycle bin"]

    doc_extensions = [
        '.txt', '.md', '.log', '.doc', '.docx', '.rtf', '.odt', '.tex', '.json', '.xml',
        '.yaml', '.ini', '.cfg', '.pdf', '.xls', '.xlsx', '.ppt', '.pptx', '.csv',
        '.epub', '.mobi'
    ]
    img_extensions = [
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico', '.svg', '.tiff', '.webp',
        '.psd', '.ai', '.raw', '.heic', '.heif'
    ]
    video_extensions = [
        '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mpeg', '.mpg'
    ]
    audio_extensions = [
        '.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a', '.wma'
    ]
    archive_extensions = [
        '.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.iso'
    ]
    dev_extensions = [
        '.py', '.pyw', '.js', '.html', '.css', '.java', '.class', '.cpp', '.c', '.h',
        '.hpp', '.cs', '.sh', '.bat', '.ps1', '.php', '.rb', '.go', '.swift', '.kt',
        '.kts', '.sql', '.ipynb', '.jar', '.sln', '.csproj', '.vb', '.ts'
    ]

    known_program_exe_strict = {
        "chrome.exe": "Браузеры", "firefox.exe": "Браузеры", "msedge.exe": "Браузеры",
        "opera.exe": "Браузеры", "iexplore.exe": "Браузеры",
        "winword.exe": "Офисные программы", "excel.exe": "Офисные программы",
        "powerpnt.exe": "Офисные программы", "outlook.exe": "Офисные программы",
        "libreoffice.exe": "Офисные программы", "soffice.bin": "Офисные программы",
        "pycharm64.exe": "Разработка", "pycharm.exe": "Разработка",
        "idea64.exe": "Разработка", "idea.exe": "Разработка",
        "code.exe": "Разработка", "devenv.exe": "Разработка", "atom.exe": "Разработка",
        "sublimetext.exe": "Разработка", "notepad++.exe": "Разработка",
        "vlc.exe": "Мультимедиа", "wmplayer.exe": "Мультимедиа", "spotify.exe": "Мультимедиа",
        "itunes.exe": "Мультимедиа", "audacity.exe": "Мультимедиа",
        "photoshop.exe": "Графика и 3D", "gimp-2.10.exe": "Графика и 3D", "gimp.exe": "Графика и 3D",
        "blender.exe": "Графика и 3D",
        "obs64.exe": "Утилиты", "obs32.exe": "Утилиты",
        "utorrent.exe": "Утилиты", "qbittorrent.exe": "Утилиты", "filezilla.exe": "Утилиты",
        "explorer.exe": "Системные", "taskmgr.exe": "Системные", "cmd.exe": "Системные",
        "powershell.exe": "Системные", "regedit.exe": "Системные", "control.exe": "Системные",
        "discord.exe": "Мессенджеры", "telegram.exe": "Мессенджеры", "skype.exe": "Мессенджеры",
        "zoom.exe": "Мессенджеры", "slack.exe": "Мессенджеры",
        "steam.exe": "Игровые платформы", "epicgameslauncher.exe": "Игровые платформы",
        "battle.net.exe": "Игровые платформы", "origin.exe": "Игровые платформы",
        "goggalaxy.exe": "Игровые платформы", "ubisoftconnect.exe": "Игровые платформы",
        "fileweederapp.exe": "Утилиты", "hfs.exe": "Утилиты", "x360ce.exe": "Утилиты",
        "engine.exe": "Программы" # Generic, hopefully caught by game name first
    }
    known_program_keywords_broader = {
        "visual studio", "pycharm", "intellij idea", "android studio",
        "google chrome", "mozilla firefox", "microsoft edge", "opera browser",
        "microsoft office", "libreoffice", "openoffice",
        "adobe photoshop", "adobe illustrator", "adobe premiere", "adobe acrobat",
        "autodesk autocad", "autodesk maya", "autodesk 3ds max",
        "obs studio", "vlc media player", "windows media player",
        "control panel", "панель управления", "диспетчер задач", "task manager",
        "command prompt", "powershell", "terminal",
        "steam", "epic games launcher", "battle.net", "origin client", "gog galaxy", "uplay", "ubisoft connect",
        "utorrent", "bittorrent", "discord", "telegram desktop", "skype", "zoom meetings",
        "audacity", "blender", "gimp", "notepad++", "sublime text", "vs code",
        "fileweeder", "http file server"
    }

    known_games_keywords_strict = [
        "minecraft", "fortnite", "valorant", "league of legends", "dota 2",
        "counter-strike", "csgo", "cs:go", "cyberpunk 2077", "the witcher", "ведьмак",
        "grand theft auto", "gta v", "stray", "elden ring", "baldurs gate", "baldurs gate 3",
        "starcraft", "diablo", "overwatch", "world of warcraft",
        "call of duty", "battlefield", "apex legends", "genshin impact",
        "terraria", "stardew valley", "doom", "fallout", "skyrim",
        "civilization", "sims", "fifa", "nba 2k",
        "lego® звездные войны™ скайуокер сага", "корсары - гпк rev.3" # From logs, will be lowercased by logic
    ]
    # Convert strict game keywords to lowercase once, as they are compared with lowercased names
    known_games_keywords_strict = [kw.lower() for kw in known_games_keywords_strict]

    game_path_indicators = [
        os.path.join("steam", "steamapps", "common"), # Relative to Program Files or library
        os.path.join("steamlibrary", "steamapps", "common"),
        os.path.join("epic games"),
        os.path.join("gog games"),
        os.path.join("origin games"),
        os.path.join("ubisoft", "ubisoft game launcher", "games"),
        os.path.join("blizzard"),
        os.path.join("riot games"),
        os.path.join("my games"),
        "games" + os.sep, # e.g. D:\Games\
        "игры" + os.sep   # e.g. D:\Игры\
    ]
    # Add Program Files paths dynamically
    pf_paths = [os.environ.get("ProgramFiles", "C:\\Program Files"),
                os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")]
    for pf_path in pf_paths:
        if pf_path: # Ensure the env variable exists
            game_path_indicators.append(os.path.join(pf_path.lower(), "steam", "steamapps", "common"))
            # Add other specific game launcher paths under Program Files if needed

    # 1. Папки
    if resolved_icon_type_lower == "папка":
        return "Папки"

    # 2. Системные элементы
    if original_desktop_type_lower == "неизвестный тип" and original_icon_name_lower in system_names_exact:
        return "Системные"

    # 3. Интернет-ярлыки
    if original_desktop_type_lower == "интернет-ярлык":
        if path_lower.startswith("steam://rungameid/"):
            return "Игры" # Steam игры - особый случай
        if path_lower.startswith("epicgames://"): # Hypothetical, for Epic Games Launcher if it uses such links
             return "Игры"
        # Известные сайты/сервисы
        known_sites = {
            "docs.google.com": "Документы (Онлайн)",
            "youtube.com": "Мультимедиа (Онлайн)", "youtu.be": "Мультимедиа (Онлайн)",
            "github.com": "Разработка (Онлайн)",
            "figma.com": "Дизайн (Онлайн)",
            "drive.google.com": "Файлы (Облако)", "onedrive.live.com": "Файлы (Облако)", "dropbox.com": "Файлы (Облако)",
            # Можно добавить игровые магазины или страницы игр, если они не через спец. протоколы
            "store.steampowered.com": "Игры (Магазин)", "epicgames.com/store": "Игры (Магазин)", "gog.com": "Игры (Магазин)",
        }
        for domain, category in known_sites.items():
            if domain in path_lower:
                return category
        return "Интернет-ссылки" # Общая категория для остальных URL

    # 4. Классификация по расширению файла (используем file_extension)
    if file_extension:
        if file_extension in doc_extensions: return "Документы"
        if file_extension in img_extensions: return "Изображения"
        if file_extension in video_extensions: return "Видео"
        if file_extension in audio_extensions: return "Аудио"
        if file_extension in archive_extensions: return "Архивы"
        if file_extension in dev_extensions: return "Файлы разработки"
        # .exe файлы будут обработаны ниже, чтобы сначала проверить на известные программы/игры

    # 5. Идентификация известных неигровых программ
    exe_name = None
    if file_extension == ".exe" and path_lower:
        exe_name = os.path.basename(path_lower) # path_lower здесь это resolved path
        if exe_name in known_program_exe_strict:
            return known_program_exe_strict[exe_name]

    # Проверка по ключевым словам для программ (имя и путь)
    # name_lower - это resolved name, original_icon_name_lower - это имя иконки на раб. столе
    for keyword_set in [name_lower, original_icon_name_lower, path_lower]:
        if any(prog_keyword in keyword_set for prog_keyword in known_program_keywords_broader):
            return "Программы"

    # Проверка на Program Files или System32 для .exe и ярлыков, указывающих на .exe
    if resolved_icon_type_lower == "исполняемый файл" or \
       (original_desktop_type_lower == "ярлык" and file_extension == ".exe"): # Ярлык на .exe
        program_files_paths = [
            os.environ.get("ProgramFiles", "C:\\Program Files").lower() + os.sep,
            os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)").lower() + os.sep,
            os.environ.get("WinDir", "C:\\Windows").lower() + os.sep + "system32" + os.sep,
        ]
        if any(pf_path in path_lower for pf_path in program_files_paths):
            # Исключаем игровые лаунчеры, которые могут быть в Program Files, но уже отнесены к программам
            # или если игра случайно установлена в Program Files, но её имя есть в game_titles
            if name_lower in game_titles or original_icon_name_lower in game_titles:
                 return "Игры" # Если игра по названию, но в Program Files
            if exe_name and exe_name.lower() in ["steam.exe", "epicgameslauncher.exe", "gog galaxy.exe", "battle.net launcher.exe"]: # Уже обработано выше, но для надежности
                return "Программы"
            return "Программы"


    # 6. Идентификация игр (game_titles - основной список из файла)
    # name_lower это resolved name (например, "witcher3.exe" -> "witcher3")
    # original_icon_name_lower это имя иконки на рабочем столе (например, "Ведьмак 3")
    # game_titles are already lowercase
    if name_lower in game_titles or original_icon_name_lower in game_titles:
        return "Игры"
    # Partial matches with game_titles (which is a list of lowercase strings)
    if any(game_title_part in name_lower for game_title_part in game_titles if len(game_title_part) > 3):
        return "Игры"
    if any(game_title_part in original_icon_name_lower for game_title_part in game_titles if len(game_title_part) > 3):
        return "Игры"

    # known_games_keywords_strict are already lowercased during initialization
    for keyword in known_games_keywords_strict:
        if keyword in name_lower or keyword in original_icon_name_lower:
            return "Игры"

    # Проверка пути для игр (если это .exe или ярлык на .exe)
    # path_lower is already lowercase. game_path_indicators should be constructed with lowercase components.
    if resolved_icon_type_lower == "исполняемый файл" or \
       (original_desktop_type_lower == "ярлык" and file_extension == ".exe"):
        # Ensure all indicators are lowercase for comparison with path_lower
        normalized_game_path_indicators = [ind.lower().replace("\\", os.sep).replace("/", os.sep) for ind in game_path_indicators]
        normalized_path_lower = path_lower.replace("\\", os.sep).replace("/", os.sep)
        if any(indicator in normalized_path_lower for indicator in normalized_game_path_indicators):
            return "Игры"

    # 7. Обработка оставшихся .exe файлов
    # Если дошли до сюда, и это .exe, то это, скорее всего, программа (не системная, не известная игра)
    if resolved_icon_type_lower == "исполняемый файл" or file_extension == ".exe":
        return "Программы"

    # 8. Оставшиеся ярлыки (которые не указывают на известные игры/программы или не были разрешены в .exe)
    if original_desktop_type_lower == "ярлык":
        return "Ярлыки (Прочее)" # Общая категория для неопознанных ярлыков

    # 9. Прочие файлы (если есть расширение, но не подошло под предыдущие категории)
    if file_extension: # Любой файл с расширением, не классифицированный выше
        return "Файлы (Прочее)"

    # 10. Категория по умолчанию
    return "Неизвестно" # Если ничего не подошло


# Структура POINT для получения координат
class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

def get_desktop_listview_handle():
    """
    Возвращает HWND (handle) элемента SysListView32, который отображает иконки рабочего стола.
    Ищет по двум основным путям, по которым может быть организован рабочий стол в Windows.
    """

    # --- Путь 1: Progman -> SHELLDLL_DefView -> SysListView32 ---
    # Это классический путь для рабочего стола, где Progman является основным окном,
    # а SHELLDLL_DefView - это его дочернее окно, содержащее список иконок.

    # Находим окно с классом "Progman"
    progman_hwnd = win32gui.FindWindow("Progman", None)

    if progman_hwnd:
        # Ищем дочернее окно с классом "SHELLDLL_DefView"
        # Это окно является контейнером для иконок рабочего стола
        shelldll_defview_hwnd = win32gui.FindWindowEx(progman_hwnd, 0, "SHELLDLL_DefView", None)

        if shelldll_defview_hwnd:
            # Ищем дочернее окно с классом "SysListView32" внутри SHELLDLL_DefView
            # SysListView32 - это сам элемент списка, который фактически отображает иконки
            syslistview_hwnd = win32gui.FindWindowEx(shelldll_defview_hwnd, 0, "SysListView32", None)
            if syslistview_hwnd:
                return syslistview_hwnd

    # --- Путь 2: WorkerW -> SysListView32 ---
    # Этот путь часто встречается, когда используется активный рабочий стол
    # или динамические обои (например, слайд-шоу). В этом случае,
    # окно "WorkerW" может быть создано для отрисовки обоев,
    # и оно может содержать SysListView32.

    desktop_workerw_hwnd = 0

    # Функция обратного вызова для EnumWindows
    def enum_windows_proc(hwnd, lParam):
        nonlocal desktop_workerw_hwnd
        class_name = win32gui.GetClassName(hwnd)

        # Ищем окна класса "WorkerW"
        if class_name == "WorkerW":
            # Проверяем, имеет ли это окно "WorkerW" дочерний элемент "SysListView32"
            # Это отличает его от других WorkerW окон (например, используемых для DWM)
            child_syslistview = win32gui.FindWindowEx(hwnd, 0, "SysListView32", None)
            if child_syslistview:
                desktop_workerw_hwnd = hwnd
                return False  # Нашли нужный WorkerW, прекращаем перечисление
        return True  # Продолжаем перечисление

    # Перечисляем все окна верхнего уровня, чтобы найти нужный WorkerW
    win32gui.EnumWindows(enum_windows_proc, None)

    if desktop_workerw_hwnd:
        # Если WorkerW найден, находим его дочерний SysListView32
        syslistview_hwnd = win32gui.FindWindowEx(desktop_workerw_hwnd, 0, "SysListView32", None)
        if syslistview_hwnd:
            return syslistview_hwnd

    # Если не удалось найти HWND ни одним из способов, возвращаем None
    return None





# --- Основная функция для получения информации об иконках ---
def get_desktop_icon_info(hwnd_listview: int, game_titles_list: list) -> list:
    """
    Принимает HWND окна SysListView32 рабочего стола и извлекает
    имя, текущие координаты, ИНДЕКС, ТИП и ПОЛНЫЙ ПУТЬ каждой иконки.
    Для ярлыков (.lnk) возвращает полный путь к файлу, на который ссылается ярлык.
    Для интернет-ярлыков (.url) возвращает URL, на который они ссылаются.

    Args:
        hwnd_listview (int): HWND окна SysListView32 (список иконок).
        game_titles_list (list): Список названий игр для классификации.

    Returns:
        list: Список словарей, где каждый словарь содержит
              {'index': N, 'name': 'Имя иконки', 'coords': (X, Y), 'type': 'Тип иконки', 'full_path': 'Полный путь'}.
              Возвращает пустой список в случае ошибки.
    """

    # --- Вспомогательные функции, вложенные для соблюдения требования "только одна функция" ---
    def _get_desktop_paths():
        """Возвращает пути к рабочему столу пользователя и общему рабочему столу."""
        # Предполагается, что 'os' модуль импортирован в глобальной области видимости
        paths = []
        try:
            # Рабочий стол текущего пользователя
            user_desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            if os.path.isdir(user_desktop):
                paths.append(user_desktop)
        except Exception as e:
            logging.warning(f"Не удалось определить путь к рабочему столу пользователя: {e}")

        try:
            # Общий рабочий стол (Public Desktop)
            public_var = os.environ.get("PUBLIC", None)
            if public_var:
                public_desktop = os.path.join(public_var, "Desktop")
                if os.path.isdir(public_desktop):
                    paths.append(public_desktop)
            else:  # Попытка найти через стандартный путь, если переменная PUBLIC отсутствует
                # Этот путь может отличаться в зависимости от системы/языка
                alt_public_desktop = os.path.join(os.environ.get("SystemDrive", "C:"), r"Users\Public\Desktop")
                if os.path.isdir(alt_public_desktop):
                    paths.append(alt_public_desktop)
        except Exception as e:
            logging.warning(f"Не удалось определить путь к общему рабочему столу: {e}")

        if not paths:
            logging.warning("Не удалось найти пути к папкам рабочего стола. Определение типов файлов будет ограничено.")
        return paths

    def _determine_item_type(item_name: str, desktop_search_paths: list, game_titles_list: list) -> tuple[str, str, str, str]:
        """
        Определяет тип элемента рабочего стола, его полный путь, имя для классификации и начальный тип.
        Для ярлыков (.lnk) возвращает тип целевого элемента, путь к цели, имя цели и "ярлык" как начальный тип.
        Для интернет-ярлыков (.url) возвращает "интернет-ярлык", URL, имя .url файла и "интернет-ярлык" как начальный тип.
        Возвращает кортеж (имя_для_классификации, тип, полный_путь_или_url_или_пустая_строка, начальный_тип_до_разрешения).
        """
        # game_titles_list не используется напрямую в этой функции

        def _resolve_lnk_target(lnk_path: str) -> str:
            """Внутренняя вспомогательная функция для разрешения цели ярлыка .lnk."""
            try:
                # Импорт win32com.client и pythoncom должен быть здесь,
                # чтобы избежать глобальных зависимостей, если функция используется отдельно.
                # Убедитесь, что у вас установлен пакет 'pywin32' (pip install pywin32).
                import pythoncom
                from win32com.client import Dispatch

                target_path = ""
                com_initialized_here = False
                try:
                    # Попытка инициализировать COM. Если уже инициализирован, это вызовет ошибку.
                    pythoncom.CoInitialize()
                    com_initialized_here = True
                except pythoncom.com_error as e:
                    # Если COM уже инициализирован (например, -2147417850 = CO_E_ALREADYINITIALIZED)
                    # нам не нужно его инициализировать, и мы не должны его деинициализировать позже.
                    if e.args and e.args[0] == -2147417850:  # RPC_E_CHANGED_MODE or CO_E_ALREADYINITIALIZED
                        pass  # COM уже инициализирован, продолжаем
                    else:
                        raise  # Перевыбросить другие ошибки COM

                try:
                    shell = Dispatch("WScript.Shell")
                    shortcut = shell.CreateShortcut(lnk_path)
                    target_path = shortcut.TargetPath
                finally:
                    if com_initialized_here:
                        pythoncom.CoUninitialize()  # Деинициализировать только если мы его инициализировали

                return target_path
            except ImportError:
                logging.warning(
                    "Модули 'pythoncom' или 'win32com.client' не найдены. Установите 'pywin32' для разрешения ярлыков.")
                return ""
            except Exception as e:
                logging.warning(f"Не удалось разрешить ярлык '{lnk_path}': {e}")
                return ""

        def _resolve_url_target(url_path: str) -> str:
            """Внутренняя вспомогательная функция для извлечения URL из файла .url."""
            config = configparser.ConfigParser()
            try:
                # Файлы .url часто используют кодировку UTF-16 LE или системную.
                # Пытаемся сначала UTF-8, потом UTF-16 LE, потом latin-1.
                try:
                    with open(url_path, 'r', encoding='utf-8') as f:
                        config.read_string(f.read())
                except UnicodeDecodeError:
                    try:
                        with open(url_path, 'r', encoding='utf-16-le') as f:
                            config.read_string(f.read())
                    except UnicodeDecodeError:
                        with open(url_path, 'r', encoding='latin-1') as f:
                            config.read_string(f.read())

                if 'InternetShortcut' in config and 'URL' in config['InternetShortcut']:
                    return config['InternetShortcut']['URL']
                else:
                    logging.warning(f"Файл .url '{url_path}' не содержит раздел [InternetShortcut] или ключ URL.")
                    return ""
            except FileNotFoundError:
                logging.warning(f"Файл .url '{url_path}' не найден.")
                return ""
            except configparser.Error as e:
                logging.warning(f"Ошибка при парсинге файла .url '{url_path}': {e}")
                return ""
            except Exception as e:
                logging.warning(f"Неизвестная ошибка при обработке файла .url '{url_path}': {e}")
                return ""


        determined_type = "неизвестный тип" # Это будет тип цели или сам тип файла
        initial_type_before_resolve = "неизвестный тип" # Тип файла как он есть на рабочем столе
        determined_path = ""
        final_item_name_for_classification = item_name # По умолчанию используется исходное имя

        original_item_name_without_ext, original_item_ext = os.path.splitext(item_name)
        original_item_ext = original_item_ext.lower()

        # 1. Поиск на рабочих столах (пользовательском и общем)
        for search_path_dir in desktop_search_paths:
            # A. Проверяем как есть (может быть папка или файл с расширением)
            full_path_candidate = os.path.join(search_path_dir, item_name)
            if os.path.exists(full_path_candidate):
                if os.path.isdir(full_path_candidate):
                    initial_type_before_resolve = "папка"
                    determined_type = "папка"
                    determined_path = full_path_candidate
                    final_item_name_for_classification = os.path.basename(full_path_candidate)
                    return final_item_name_for_classification, determined_type, determined_path, initial_type_before_resolve
                elif os.path.isfile(full_path_candidate):
                    name_part, ext_part = os.path.splitext(full_path_candidate)
                    ext_lower = ext_part.lower()

                    if ext_lower == '.lnk':
                        initial_type_before_resolve = "ярлык"
                        target_path = _resolve_lnk_target(full_path_candidate)
                        if target_path and os.path.exists(target_path):
                            determined_path = target_path
                            if os.path.isdir(target_path):
                                determined_type = "папка"
                                final_item_name_for_classification = os.path.basename(target_path)
                            else:
                                target_name_no_ext, target_ext = os.path.splitext(os.path.basename(target_path))
                                final_item_name_for_classification = target_name_no_ext
                                target_ext_lower = target_ext.lower()
                                if target_ext_lower == '.exe': determined_type = "исполняемый файл"
                                elif target_ext_lower in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico']: determined_type = "изображение"
                                elif target_ext_lower in ['.txt', '.doc', '.docx', '.rtf', '.odt']: determined_type = "текстовый файл"
                                elif target_ext_lower == '.pdf': determined_type = "пдф"
                                else: determined_type = "файл"
                        else:
                            determined_type = "ярлык" # Остается ярлыком, если цель не найдена
                            determined_path = full_path_candidate
                            final_item_name_for_classification = original_item_name_without_ext if original_item_ext == ".lnk" else item_name
                        return final_item_name_for_classification, determined_type, determined_path, initial_type_before_resolve

                    elif ext_lower == '.url':
                        initial_type_before_resolve = "интернет-ярлык"
                        target_url = _resolve_url_target(full_path_candidate)
                        if target_url:
                            determined_type = "интернет-ярлык"
                            determined_path = target_url
                            final_item_name_for_classification = original_item_name_without_ext if original_item_ext == ".url" else item_name
                        else:
                            determined_type = "интернет-ярлык"
                            determined_path = full_path_candidate
                            final_item_name_for_classification = original_item_name_without_ext if original_item_ext == ".url" else item_name
                        return final_item_name_for_classification, determined_type, determined_path, initial_type_before_resolve

                    # Обычные файлы (не ярлыки)
                    initial_type_before_resolve = "файл" # Общий начальный тип для файлов
                    final_item_name_for_classification = os.path.splitext(os.path.basename(full_path_candidate))[0]
                    if ext_lower in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.ico']:
                        determined_type = "изображение"
                        initial_type_before_resolve = "изображение"
                    elif ext_lower == '.txt':
                        determined_type = "текстовый файл"
                        initial_type_before_resolve = "текстовый файл"
                    elif ext_lower == '.pdf':
                        determined_type = "пдф"
                        initial_type_before_resolve = "пдф"
                    elif ext_lower == '.exe':
                        determined_type = "исполняемый файл"
                        initial_type_before_resolve = "исполняемый файл"
                    else:
                        determined_type = "файл" # Остается "файл", если не более специфичный тип
                    determined_path = full_path_candidate
                    return final_item_name_for_classification, determined_type, determined_path, initial_type_before_resolve

            shortcut_path_candidate_lnk = os.path.join(search_path_dir, item_name + ".lnk")
            if os.path.isfile(shortcut_path_candidate_lnk):
                initial_type_before_resolve = "ярлык"
                target_path = _resolve_lnk_target(shortcut_path_candidate_lnk)
                if target_path and os.path.exists(target_path):
                    determined_path = target_path
                    if os.path.isdir(target_path):
                        determined_type = "папка"
                        final_item_name_for_classification = os.path.basename(target_path)
                    else:
                        target_name_no_ext, target_ext = os.path.splitext(os.path.basename(target_path))
                        final_item_name_for_classification = target_name_no_ext
                        target_ext_lower = target_ext.lower()
                        if target_ext_lower == '.exe': determined_type = "исполняемый файл"
                        elif target_ext_lower in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico']: determined_type = "изображение"
                        elif target_ext_lower in ['.txt', '.doc', '.docx', '.rtf', '.odt']: determined_type = "текстовый файл"
                        elif target_ext_lower == '.pdf': determined_type = "пдф"
                        else: determined_type = "файл"
                else:
                    determined_type = "ярлык"
                    determined_path = shortcut_path_candidate_lnk
                    final_item_name_for_classification = item_name
                return final_item_name_for_classification, determined_type, determined_path, initial_type_before_resolve

            shortcut_path_candidate_url = os.path.join(search_path_dir, item_name + ".url")
            if os.path.isfile(shortcut_path_candidate_url):
                initial_type_before_resolve = "интернет-ярлык"
                target_url = _resolve_url_target(shortcut_path_candidate_url)
                if target_url:
                    determined_type = "интернет-ярлык"
                    determined_path = target_url
                    final_item_name_for_classification = item_name
                else:
                    determined_type = "интернет-ярлык"
                    determined_path = shortcut_path_candidate_url
                    final_item_name_for_classification = item_name
                return final_item_name_for_classification, determined_type, determined_path, initial_type_before_resolve

            if original_item_ext == ".lnk": # item_name из ListView уже содержит .lnk
                full_path_candidate_with_ext = os.path.join(search_path_dir, item_name)
                if os.path.isfile(full_path_candidate_with_ext):
                    initial_type_before_resolve = "ярлык"
                    target_path = _resolve_lnk_target(full_path_candidate_with_ext)
                    if target_path and os.path.exists(target_path):
                        determined_path = target_path
                        if os.path.isdir(target_path):
                            determined_type = "папка"
                            final_item_name_for_classification = os.path.basename(target_path)
                        else:
                            target_name_no_ext, target_ext = os.path.splitext(os.path.basename(target_path))
                            final_item_name_for_classification = target_name_no_ext
                            target_ext_lower = target_ext.lower()
                            if target_ext_lower == '.exe': determined_type = "исполняемый файл"
                            elif target_ext_lower in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico']: determined_type = "изображение"
                            elif target_ext_lower in ['.txt', '.doc', '.docx', '.rtf', '.odt']: determined_type = "текстовый файл"
                            elif target_ext_lower == '.pdf': determined_type = "пдф"
                            else: determined_type = "файл"
                    else:
                        determined_type = "ярлык"
                        determined_path = full_path_candidate_with_ext
                        final_item_name_for_classification = original_item_name_without_ext
                    return final_item_name_for_classification, determined_type, determined_path, initial_type_before_resolve

            elif original_item_ext == ".url": # item_name из ListView уже содержит .url
                full_path_candidate_with_ext = os.path.join(search_path_dir, item_name)
                if os.path.isfile(full_path_candidate_with_ext):
                    initial_type_before_resolve = "интернет-ярлык"
                    target_url = _resolve_url_target(full_path_candidate_with_ext)
                    if target_url:
                        determined_type = "интернет-ярлык"
                        determined_path = target_url
                        final_item_name_for_classification = original_item_name_without_ext
                    else:
                        determined_type = "интернет-ярлык"
                        determined_path = full_path_candidate_with_ext
                        final_item_name_for_classification = original_item_name_without_ext
                    return final_item_name_for_classification, determined_type, determined_path, initial_type_before_resolve

        # Эвристика, если файл не найден на рабочих столах
        final_item_name_for_classification = original_item_name_without_ext if original_item_ext else item_name
        if original_item_ext == ".lnk":
            initial_type_before_resolve = "ярлык"
            determined_type = "ярлык"
        elif original_item_ext == ".url":
            initial_type_before_resolve = "интернет-ярлык"
            determined_type = "интернет-ярлык"
        elif original_item_ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.ico']:
            initial_type_before_resolve = "изображение"
            determined_type = "изображение"
        elif original_item_ext == '.txt':
            initial_type_before_resolve = "текстовый файл"
            determined_type = "текстовый файл"
        elif original_item_ext == '.pdf':
            initial_type_before_resolve = "пдф"
            determined_type = "пдф"
        elif original_item_ext == '.exe':
            initial_type_before_resolve = "исполняемый файл"
            determined_type = "исполняемый файл"
        elif original_item_ext: # Любой другой известный расширение
            initial_type_before_resolve = "файл"
            determined_type = "файл"
        # Если нет расширения и файл не найден (например, "Корзина"), initial_type_before_resolve и determined_type остаются "неизвестный тип"

        return final_item_name_for_classification, determined_type, determined_path, initial_type_before_resolve

    # --- Конец вложенных вспомогательных функций ---

    if not hwnd_listview:
        logging.error("Предоставлен недействительный HWND SysListView32.")
        return []

    results = []
    h_process = None
    remote_lvitem = 0
    remote_text_buffer = 0
    remote_point = 0

    # Получаем пути к рабочим столам для определения типов
    desktop_paths_list = _get_desktop_paths()

    # Внимание: для выполнения этого кода необходимы следующие объекты/модули,
    # которые предполагаются импортированными/определенными вне этой функции:
    # ctypes.wintypes as wintypes
    # win32con (из pywin32)
    # kernel32 (ctypes.WinDLL('kernel32'))
    # user32 (ctypes.WinDLL('user32'))
    # LVITEM, POINT (ctypes.Structure definitions)
    # LVM_GETITEMCOUNT, LVM_GETITEMTEXTW, LVM_GETITEMPOSITION, LVIF_TEXT, MEM_COMMIT, MEM_RESERVE, MEM_RELEASE, PAGE_READWRITE
    # В случае отсутствия, их необходимо определить или импортировать.

    try:
        # Проверка наличия объектов, используемых в основном блоке функции:
        # Исправлена ошибка TypeError: all() takes exactly one argument (8 given)
        # путем оборачивания всех условий в один кортеж.
        if not all((
            hasattr(ctypes, 'wintypes') and hasattr(ctypes.wintypes, 'DWORD'),
            hasattr(ctypes, 'wintypes') and hasattr(ctypes.wintypes, 'SIZE'),
            hasattr(ctypes, 'wintypes') and hasattr(ctypes.wintypes, 'WCHAR'),
            hasattr(sys.modules.get('__main__'), 'win32con') or hasattr(sys.modules.get(__name__), 'win32con'), # Check for win32con
            hasattr(sys.modules.get('__main__'), 'kernel32') or hasattr(sys.modules.get(__name__), 'kernel32'), # Check for kernel32
            hasattr(sys.modules.get('__main__'), 'user32') or hasattr(sys.modules.get(__name__), 'user32'),     # Check for user32
            hasattr(sys.modules.get('__main__'), 'LVITEM') or hasattr(sys.modules.get(__name__), 'LVITEM'),     # Check for LVITEM
            hasattr(sys.modules.get('__main__'), 'POINT') or hasattr(sys.modules.get(__name__), 'POINT')       # Check for POINT
        )):
            logging.error("Необходимые ctypes структуры, константы или модули (wintypes, win32con, kernel32, user32, LVITEM, POINT) не определены или недоступны в текущем контексте.")
            return []


        pid = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd_listview, ctypes.byref(pid))
        process_id = pid.value
        if not process_id:
            logging.error(f"Не удалось получить PID для HWND {hwnd_listview}.")
            return []

        h_process = kernel32.OpenProcess(
            win32con.PROCESS_VM_OPERATION |
            win32con.PROCESS_VM_READ |
            win32con.PROCESS_VM_WRITE |
            win32con.PROCESS_QUERY_INFORMATION,
            False,
            process_id
        )
        if not h_process:
            error_code = ctypes.get_last_error()
            logging.error(
                f"Не удалось открыть процесс {process_id}. Ошибка Windows API: {error_code} - {ctypes.FormatError(error_code)}. Попробуйте запустить скрипт с правами администратора.")
            return []

        lvitem_size = ctypes.sizeof(LVITEM)
        remote_lvitem = kernel32.VirtualAllocEx(h_process, 0, lvitem_size, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE)
        if not remote_lvitem:
            logging.error(
                f"Не удалось выделить удаленную память для LVITEM. Ошибка: {ctypes.FormatError(ctypes.get_last_error())}")
            return []  # finally блок выполнит очистку h_process

        text_buffer_max_chars = 256
        text_buffer_size = text_buffer_max_chars * ctypes.sizeof(ctypes.wintypes.WCHAR)
        remote_text_buffer = kernel32.VirtualAllocEx(h_process, 0, text_buffer_size, MEM_COMMIT | MEM_RESERVE,
                                                     PAGE_READWRITE)
        if not remote_text_buffer:
            logging.error(
                f"Не удалось выделить удаленную память для буфера текста. Ошибка: {ctypes.FormatError(ctypes.get_last_error())}")
            return []

        point_size = ctypes.sizeof(POINT)
        remote_point = kernel32.VirtualAllocEx(h_process, 0, point_size, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE)
        if not remote_point:
            logging.error(
                f"Не удалось выделить удаленную память для POINT. Ошибка: {ctypes.FormatError(ctypes.get_last_error())}")
            return []

        count = user32.SendMessageW(hwnd_listview, LVM_GETITEMCOUNT, 0, 0)
        if count == -1:
            error_code = ctypes.get_last_error()
            logging.warning(
                f"LVM_GETITEMCOUNT вернул {count}. Возможно, нет элементов или произошла ошибка. Ошибка Windows API: {ctypes.FormatError(error_code) if error_code else 'N/A'}")
            if count == -1:
                return []
        elif count == 0:
            logging.info("На рабочем столе нет иконок (LVM_GETITEMCOUNT вернул 0).")
            return []

        logging.info(f"Найдено {count} иконок на рабочем столе.")

        for i in range(count):
            item_name = f"Неизвестная иконка {i}"
            item_type = "неизвестный тип"
            item_full_path = ""  # Инициализация для каждой иконки
            x, y = 0, 0

            lvitem_py = LVITEM()
            lvitem_py.mask = LVIF_TEXT
            lvitem_py.iItem = i
            lvitem_py.iSubItem = 0
            lvitem_py.cchTextMax = text_buffer_max_chars
            lvitem_py.pszText = remote_text_buffer

            bytes_written = ctypes.wintypes.SIZE()
            if not kernel32.WriteProcessMemory(h_process, remote_lvitem, ctypes.byref(lvitem_py), lvitem_size,
                                               ctypes.byref(bytes_written)):
                logging.warning(
                    f"Не удалось записать LVITEM в удаленный процесс для элемента {i}. Ошибка: {ctypes.FormatError(ctypes.get_last_error())}. Пропускаем получение имени.")
            else:
                ret_text = user32.SendMessageW(hwnd_listview, LVM_GETITEMTEXTW, i, remote_lvitem)
                if ret_text > 0:
                    buffer = ctypes.create_unicode_buffer(text_buffer_max_chars)
                    bytes_read = ctypes.wintypes.SIZE()
                    if kernel32.ReadProcessMemory(h_process, remote_text_buffer, buffer, text_buffer_size,
                                                  ctypes.byref(bytes_read)):
                        item_name = buffer.value.strip()
                    else:
                        logging.warning(
                            f"Не удалось прочитать текст элемента {i} из удаленного процесса. Ошибка: {ctypes.FormatError(ctypes.get_last_error())}")
                else:
                    error_code = ctypes.get_last_error()
                    logging.warning(
                        f"Не удалось получить текст для элемента {i}. Код возврата SendMessage: {ret_text}. Ошибка Windows API: {ctypes.FormatError(error_code) if error_code else 'N/A'}")

            # Определяем тип элемента, его полный путь, имя для классификации и начальный тип
            item_name_for_classification, item_type, item_full_path, initial_type_before_resolve = \
                _determine_item_type(item_name, desktop_paths_list, game_titles_list)

            item_modification_date = 0.0  # Default value
            if item_full_path and os.path.exists(item_full_path):
                try:
                    item_modification_date = os.path.getmtime(item_full_path)
                except Exception as e_mod_time:
                    logging.warning(f"Could not get modification time for {item_full_path}: {e_mod_time}")

            ret_pos = user32.SendMessageW(hwnd_listview, LVM_GETITEMPOSITION, i, remote_point)
            if ret_pos == 1:
                point_py = POINT()
                bytes_read_pos = ctypes.wintypes.SIZE()
                if kernel32.ReadProcessMemory(h_process, remote_point, ctypes.byref(point_py), point_size,
                                              ctypes.byref(bytes_read_pos)):
                    x, y = point_py.x, point_py.y
                else:
                    logging.warning(
                        f"Не удалось прочитать POINT для элемента {i} ('{item_name}') из удаленного процесса. Ошибка: {ctypes.FormatError(ctypes.get_last_error())}")
            else:
                error_code = ctypes.get_last_error()
                logging.warning(
                    f"Не удалось получить позицию для элемента {i} ('{item_name}'). Код возврата SendMessage: {ret_pos}. Ошибка Windows API: {ctypes.FormatError(error_code) if error_code else 'N/A'}")

            # Создаем словарь данных для классификации
            icon_data_for_classification = {
                'name': item_name_for_classification,
                'type': item_type,
                'full_path': item_full_path,
                'original_icon_name': item_name, # Имя иконки как на рабочем столе
                'original_desktop_type': initial_type_before_resolve # Тип до разрешения ярлыков
            }
            # Получаем категорию иконки
            item_category = get_icon_category(icon_data_for_classification, game_titles_list)

            # Добавляем информацию об иконке, включая категорию, в список результатов
            results.append({
                'index': i,
                'name': item_name,
                'coords': (x, y),
                'type': item_type,
                'full_path': item_full_path,
                'category': item_category,
                'classified_name': item_name_for_classification,
                'original_desktop_type': initial_type_before_resolve, # Для отладки, если нужно
                'modification_date': item_modification_date
            })

    except Exception as e:
        logging.error(f"Произошла общая ошибка при получении данных об иконках: {e}", exc_info=True)
        error_code = ctypes.get_last_error()
        if error_code != 0:
            logging.error(f"Дополнительная ошибка Windows API: {error_code} - {ctypes.FormatError(error_code)}")
        return []
    finally:
        if h_process:
            if remote_lvitem:
                kernel32.VirtualFreeEx(h_process, remote_lvitem, 0, MEM_RELEASE)
            if remote_text_buffer:
                kernel32.VirtualFreeEx(h_process, remote_text_buffer, 0, MEM_RELEASE)
            if remote_point:
                kernel32.VirtualFreeEx(h_process, remote_point, 0, MEM_RELEASE)
            kernel32.CloseHandle(h_process)

    return results





def move_desktop_icon(hwnd_listview: int, item_index: int, x: int, y: int) -> bool:
    """
    Перемещает иконку рабочего стола в заданные клиентские координаты.

    Важно: Эта функция работает корректно только если функция "Автоматическое упорядочивание иконок"
    (Auto Arrange Icons) отключена на рабочем столе. Если автоупорядочивание включено, Windows может
    сразу же вернуть иконку на ее место или переупорядочить все иконки.

    Args:
        hwnd_listview (int): HWND окна рабочего стола (SysListView32).
                             Обычно это дочерний элемент окна SHELLDLL_DefView.
                             Вы можете получить его, используя функции типа win32gui.FindWindowEx.
        item_index (int): Индекс иконки, которую нужно переместить (0-based).
                          Для определения индекса иконки по имени, потребуется
                          дополнительный код (например, используя LVM_GETITEMTEXT
                          и LVM_FINDITEM).
        x (int): Новая X-координата иконки (относительно клиентской области SysListView32).
        y (int): Новая Y-координата иконки (относительно клиентской области SysListView32).

    Returns:
        bool: True, если сообщение о перемещении было отправлено успешно, False в противном случае.
              Успешная отправка сообщения не гарантирует, что иконка останется
              на месте из-за вышеупомянутого автоупорядочивания.
    """
    if not win32gui.IsWindow(hwnd_listview):
        # В случае, если передан недействительный HWND.
        # В реальном приложении можно было бы логировать эту ошибку.
        return False

    # LVM_SETITEMPOSITION - сообщение для установки позиции элемента списка
    # wParam = item_index (индекс элемента, который нужно переместить)
    # lParam = MAKELPARAM(x, y) (упакованные координаты X и Y)

    # Упаковываем X и Y координаты в один LPARAM
    # MAKELPARAM - это макрос, который объединяет два 16-битных значения в одно 32-битное.
    pos = (y << 16) | x

    # Отправляем сообщение окну SysListView32
    # SendMessage возвращает ненулевое значение при успехе, 0 при неудаче.
    # Результат SendMessage может варьироваться в зависимости от контекста.
    # Для LVM_SETITEMPOSITION возвращаемое значение обычно не используется,
    # и успех определяется тем, что функция не сгенерировала исключение.
    try:
        result = win32gui.SendMessage(
            hwnd_listview,
            LVM_SETITEMPOSITION,
            item_index,
            pos
        )
        # После изменения позиции, особенно для системных ListViews,
        # может потребоваться принудительная перерисовка.
        # LVM_REDRAWALL заставляет контрол перерисовать все свои элементы.
        # win32gui.SendMessage(hwnd_listview, win32con.LVM_REDRAWALL, 0, 0)
        # Также можно использовать InvalidateRect для родительского окна, чтобы
        # гарантировать обновление, если SysListView32 не обновится сам.
        # parent_hwnd = win32gui.GetParent(hwnd_listview)
        # if parent_hwnd:
        #     win32gui.InvalidateRect(parent_hwnd, None, True)

        return result != 0 # Возвращаем True, если сообщение было успешно отправлено (не 0)
    except Exception as e:
        # Логирование ошибки, если SendMessage вызывает исключение (например, из-за неверного HWND)
        # print(f"Ошибка при перемещении иконки: {e}")
        return False

def get_windows_screen_info():
    """
    Возвращает словарь с информацией о разрешении экрана и масштабировании
    для основного монитора в Windows.

    Возвращаемые значения:
    - 'logical_resolution': Разрешение экрана после применения масштабирования (например, '1920x1080').
                          Это то, что видят большинство приложений.
    - 'physical_resolution': Предполагаемое физическое разрешение монитора до масштабирования
                           (например, '3840x2160' для 4K монитора с 200% масштабом).
    - 'scaling_percentage': Процент масштабирования (например, '150%').
    - 'dpi_x', 'dpi_y': Фактические значения DPI по осям X и Y.

    Возвращает None в случае ошибки.
    """
    try:
        # --- 1. Определяем HRESULT, если он отсутствует в wintypes ---
        # Это для совместимости с более старыми версиями Python/ctypes,
        # где wintypes.HRESULT может быть недоступен.
        try:
            _HRESULT = wintypes.HRESULT
        except AttributeError:
            # print("Предупреждение: wintypes.HRESULT не найден, используя ctypes.c_long вместо него.")
            _HRESULT = ctypes.c_long

        # --- 2. Загрузка необходимых DLL ---
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32

        # Попытка загрузить shcore.dll для GetDpiForMonitor и SetProcessDpiAwareness
        # (доступно с Windows 8.1 и выше)
        try:
            shcore = ctypes.windll.shcore
            has_shcore = True
            # print("shcore.dll успешно загружена.")
        except AttributeError:
            has_shcore = False
            # print("Предупреждение: shcore.dll не найдена. Некоторые функции DPI могут быть недоступны.")
        except Exception as e:
            has_shcore = False
            # print(f"Неожиданная ошибка при загрузке shcore: {e}.")

        # --- 3. Делаем процесс DPI-осведомленным ---
        # Это критически важно для получения правильных значений DPI,
        # когда системное масштабирование не 100%.
        if has_shcore:
            try:
                # DPI_AWARENESS_PER_MONITOR_AWARE = 2 (лучший вариант для современных систем)
                # Позволяет приложению реагировать на изменения DPI при перемещении между мониторами.
                DPI_AWARENESS_PER_MONITOR_AWARE = 2

                # Определяем сигнатуру SetProcessDpiAwareness
                shcore.SetProcessDpiAwareness.argtypes = [ctypes.c_int]
                shcore.SetProcessDpiAwareness.restype = _HRESULT

                # Вызываем функцию для установки DPI-осведомленности
                result = shcore.SetProcessDpiAwareness(DPI_AWARENESS_PER_MONITOR_AWARE)
                # S_OK (0) означает успех, E_ACCESSDENIED (-2147024891) - если уже установлено
                if result == 0 or result == -2147024891:  # HRESULT_FROM_WIN32(ERROR_ACCESS_DENIED)
                    # print("Процесс успешно установлен в режим Per-Monitor DPI Aware (или уже был).")
                    pass
                else:
                    print(f"Предупреждение: Не удалось установить DPI-осведомленность (код: {result}).")
            except AttributeError:
                # print("Предупреждение: SetProcessDpiAwareness не найдена (версия Windows < 8.1?), DPI-осведомленность не установлена.")
                pass  # Пропускаем, если функция недоступна
            except Exception as e:
                print(f"Ошибка при попытке установить DPI-осведомленность: {e}")

        # --- 4. Получение логического разрешения (после масштабирования) ---
        # SM_CXSCREEN = 0 (ширина), SM_CYSCREEN = 1 (высота)
        logical_width = user32.GetSystemMetrics(0)  # SM_CXSCREEN
        logical_height = user32.GetSystemMetrics(1)  # SM_CYSCREEN

        # --- 5. Получение DPI и вычисление масштабирования ---
        dpi_x = 0
        dpi_y = 0

        if has_shcore:
            # Для GetDpiForMonitor:
            # HMONITOR hmonitor, int dpiType, UINT* dpiX, UINT* dpiY
            # MDT_EFFECTIVE_DPI = 0 (эффективный DPI, который соответствует масштабу)
            MDT_EFFECTIVE_DPI = 0

            # Получаем хэндл основного монитора
            # MONITOR_DEFAULTTOPRIMARY (0x00000001) возвращает основной монитор
            monitor_handle = user32.MonitorFromWindow(user32.GetDesktopWindow(), 0x00000001)

            if monitor_handle:
                # Определяем аргументы и тип возвращаемого значения для GetDpiForMonitor
                shcore.GetDpiForMonitor.argtypes = [
                    wintypes.HMONITOR,
                    wintypes.INT,
                    ctypes.POINTER(wintypes.UINT),
                    ctypes.POINTER(wintypes.UINT)
                ]
                shcore.GetDpiForMonitor.restype = _HRESULT

                x_dpi_ptr = wintypes.UINT()
                y_dpi_ptr = wintypes.UINT()

                result = shcore.GetDpiForMonitor(monitor_handle, MDT_EFFECTIVE_DPI,
                                                 ctypes.byref(x_dpi_ptr), ctypes.byref(y_dpi_ptr))

                if result == 0:  # S_OK означает успех
                    dpi_x = x_dpi_ptr.value
                    dpi_y = y_dpi_ptr.value
                # else:
                # print(f"Предупреждение: GetDpiForMonitor вернул ошибку {result}. Попытка использовать GetDeviceCaps.")

        if dpi_x == 0 or dpi_y == 0:  # Если GetDpiForMonitor не сработал или недоступен
            # Fallback к GetDeviceCaps (более старый метод, может не учитывать per-monitor DPI)
            # LOGPIXELSX = 88 (DPI по X), LOGPIXELSY = 90 (DPI по Y)
            dc = user32.GetDC(0)  # 0 = экранный DC
            if dc:
                dpi_x = gdi32.GetDeviceCaps(dc, 88)  # LOGPIXELSX
                dpi_y = gdi32.GetDeviceCaps(dc, 90)  # LOGPIXELSY
                user32.ReleaseDC(0, dc)  # Освобождаем DC
            else:
                raise Exception("Не удалось получить контекст устройства (DC) для определения DPI.")

        # Базовое DPI для 100% масштабирования в Windows
        DEFAULT_DPI = 96.0

        # Вычисление масштабирования
        # Обычно X и Y DPI одинаковы, но берем среднее для надежности
        scaling_factor_x = (dpi_x / DEFAULT_DPI) * 100
        scaling_factor_y = (dpi_y / DEFAULT_DPI) * 100

        # Округляем до ближайшего стандартного масштабирования (например, 100, 125, 150)
        avg_scaling_percentage = int(round((scaling_factor_x + scaling_factor_y) / 2))

        # Вычисление физического разрешения (приблизительно, до масштабирования)
        # physical_resolution = logical_resolution / (scaling_percentage / 100)
        # Избегаем деления на ноль, если по каким-то причинам avg_scaling_percentage = 0
        if avg_scaling_percentage == 0:
            physical_width = 0
            physical_height = 0
        else:
            physical_width = int(round(logical_width / (avg_scaling_percentage / 100.0)))
            physical_height = int(round(logical_height / (avg_scaling_percentage / 100.0)))

        return {
            "logical_resolution": f"{logical_width}x{logical_height}",
            "physical_resolution": f"{physical_width}x{physical_height}",
            "scaling_percentage": f"{avg_scaling_percentage}%",
            "dpi_x": dpi_x,
            "dpi_y": dpi_y
        }

    except Exception as e:
        print(f"Произошла ошибка при получении информации о экране: {e}")
        return None

def get_desktop_items():
    """
    Возвращает список полных путей ко всем элементам (файлам и папкам)
    на рабочем столе текущего пользователя.

    Включает обработку ошибок, если папка рабочего стола не найдена
    или нет прав доступа.
    """
    desktop_path = None
    try:
        # Получаем домашнюю директорию текущего пользователя
        # os.path.expanduser('~') работает кроссплатформенно
        home_dir = os.path.expanduser('~')

        # Формируем путь к рабочему столу.
        # 'Desktop' - это стандартное название для большинства систем
        # (Windows, macOS, большинство Linux дистрибутивов).
        desktop_path = os.path.join(home_dir, 'Desktop')

        # Проверяем, существует ли папка рабочего стола
        if not os.path.exists(desktop_path):
            # Если не найдено по стандартному пути, попробуем для локализованных систем
            # (например, "Рабочий стол" для русской Windows).
            # Это менее надежно, так как название может быть любым.
            # Для более надежного определения на Windows можно использовать win32com, но
            # это выходит за рамки простой кроссплатформенной функции.
            if os.name == 'nt': # Если это Windows
                try:
                    import winreg
                    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders")
                    desktop_path = winreg.QueryValueEx(key, "Desktop")[0]
                except Exception:
                    # Если winreg не сработал или не импортирован
                    print(f"Предупреждение: Не удалось найти стандартный путь к рабочему столу '{desktop_path}'. "
                          f"Пытаюсь найти по 'Рабочий стол' (актуально для русской Windows).")
                    localized_desktop_name = "Рабочий стол"
                    potential_desktop_path_localized = os.path.join(home_dir, localized_desktop_name)
                    if os.path.exists(potential_desktop_path_localized):
                        desktop_path = potential_desktop_path_localized
                    else:
                        raise FileNotFoundError(f"Папка рабочего стола не найдена по '{desktop_path}' или '{potential_desktop_path_localized}'.")
            else: # Для других ОС, если не найдено
                raise FileNotFoundError(f"Папка рабочего стола не найдена по '{desktop_path}'.")

        # Получаем список имен файлов и папок в директории рабочего стола
        item_names = os.listdir(desktop_path)

        # Создаем список полных путей к каждому элементу
        full_paths = [os.path.join(desktop_path, name) for name in item_names]

        return full_paths

    except FileNotFoundError:
        print(f"Ошибка: Не удалось найти папку рабочего стола. Проверьте, существует ли она по адресу '{desktop_path}'.")
        return []
    except PermissionError:
        print(f"Ошибка: Отказано в доступе к папке рабочего стола '{desktop_path}'. Возможно, у скрипта нет необходимых разрешений.")
        return []
    except Exception as e:
        print(f"Произошла непредвиденная ошибка: {e}")
        return []

# Пример использования функции:
if __name__ == "__main__":
    # desktop_elements = get_desktop_items()
    screen_info = get_windows_screen_info()
    #
    # if desktop_elements:
    #     print(f"Найдено {len(desktop_elements)} элементов на рабочем столе:")
    #     for element_path in desktop_elements:
    #         # os.path.basename() вернет только имя файла/папки без полного пути
    #         print(f"- {os.path.basename(element_path)}")
    # else:
    #     print("Не удалось получить список элементов рабочего стола или рабочий стол пуст.")


    if screen_info:
        print("Информация об экране Windows:")
        print(f"  Логическое разрешение (после масштабирования): {screen_info['logical_resolution']}")
        print(f"  Предполагаемое физическое разрешение: {screen_info['physical_resolution']}")
        print(f"  Масштабирование: {screen_info['scaling_percentage']}")
        print(f"  DPI (X/Y): {screen_info['dpi_x']}/{screen_info['dpi_y']}")
    else:
        print("Не удалось получить информацию об экране.")

    desktop_handle = get_desktop_listview_handle()

    if desktop_handle:
        print(f"Найден HWND окна рабочего стола (SysListView32): {desktop_handle}")
        try:
            # Попытка получить заголовок или класс окна для проверки
            window_text = win32gui.GetWindowText(desktop_handle)
            window_class = win32gui.GetClassName(desktop_handle)
            print(f"  Текст окна: '{window_text}'")
            print(f"  Класс окна: '{window_class}'")

            # Можно попытаться получить родителя, чтобы увидеть Progman или WorkerW
            parent_handle = win32gui.GetParent(desktop_handle)
            if parent_handle:
                parent_class = win32gui.GetClassName(parent_handle)
                print(f"  Родительский HWND: {parent_handle}, Класс родителя: '{parent_class}'")

        except Exception as e:
            print(f"Ошибка при получении информации об окне: {e}")

    else:
        print("Не удалось найти HWND окна рабочего стола.")

    if desktop_handle:
        game_titles_list = load_game_titles() # Загружаем список названий игр
        logging.info("Получение информации об иконках рабочего стола...")
        # Передаем game_titles_list в функцию
        icons_info = get_desktop_icon_info(desktop_handle, game_titles_list)

        if icons_info:
            print("\n--- Информация об иконках рабочего стола ---")
            for icon in icons_info:
                # Изменено для вывода индекса, типа, полного пути и имени для классификации
                # Категория теперь извлекается из данных иконки, где она была сохранена
                print(f"Индекс: {icon['index']}, Имя: \"{icon['name']}\", Тип: {icon['type']}, Коорд: {icon['coords']}, Путь: {icon['full_path'] if icon['full_path'] else 'N/A'}, Категория: {icon['category']}, Класс. имя: \"{icon['classified_name']}\"")

            print(f"\nВсего иконок: {len(icons_info)}")

            # move_desktop_icon(desktop_handle, 3, 1000, 1000)
        else:
            print("Не удалось получить информацию об иконках.")

        # --- Запуск сортировки иконок рабочего стола ---
        # Внимание: это действие изменит расположение иконок на рабочем столе!
        print("\n--- Запуск сортировки иконок рабочего стола ---")
        sort_desktop_icons()
        print("--- Сортировка иконок завершена ---")
        # --- Конец блока вызова сортировки ---

    else:
        print("Не удалось найти HWND SysListView32 рабочего стола. Убедитесь, что вы работаете на Windows и рабочий стол активен.")

# Новая функция, которую ты напишешь:
def sort_desktop_icons():
    # Подробные комментарии на русском языке будут добавлены по ходу реализации
    logging.info("Запуск функции сортировки иконок рабочего стола.")

    # 1. Определить разрешение и масштаб экрана
    screen_info = get_windows_screen_info()
    if not screen_info:
        logging.error("Не удалось получить информацию об экране. Сортировка прервана.")
        return

    try:
        screen_width_str, screen_height_str = screen_info['logical_resolution'].split('x')
        screen_width = int(screen_width_str)
        screen_height = int(screen_height_str)

        scale_percentage_str = screen_info['scaling_percentage'].replace('%', '')
        scale_factor = int(scale_percentage_str) / 100.0
    except (ValueError, KeyError) as e:
        logging.error(f"Ошибка парсинга информации об экране: {screen_info}. Ошибка: {e}. Сортировка прервана.")
        return

    logging.info(f"Разрешение экрана: {screen_width}x{screen_height}, Масштаб: {scale_factor*100}%")

    # Базовые размеры иконки и отступы
    icon_base_width = 75  # Примерный базовый размер иконки до масштабирования
    icon_base_height = 75 # Примерный базовый размер иконки до масштабирования
    icon_padding = 15     # Отступ между иконками

    # Масштабированные размеры иконки и отступы
    # scaled_icon_width = int(icon_base_width * scale_factor) # Фактический размер иконки может отличаться от этого
    # scaled_icon_height = int(icon_base_height * scale_factor) # Windows управляет размером иконки сама.
                                                            # Мы используем базовые размеры для расчета сетки.
    scaled_icon_width = icon_base_width # Используем базовые размеры для сетки, Windows сама масштабирует визуал
    scaled_icon_height = icon_base_height
    scaled_padding = icon_padding # Отступ тоже не будем масштабировать явно, т.к. координаты абсолютные

    # Размеры ячейки для иконки, включая отступы
    # Это пространство, которое занимает одна иконка + ее правый/нижний отступ
    cell_width = scaled_icon_width + scaled_padding
    cell_height = scaled_icon_height + scaled_padding

    # 2. Получить все элементы рабочего стола
    hwnd_listview = get_desktop_listview_handle()
    if not hwnd_listview:
        logging.error("Не удалось получить HWND рабочего стола. Сортировка прервана.")
        return

    game_titles = load_game_titles() # Загружаем список игр для корректной категоризации
    all_elements_raw = get_desktop_icon_info(hwnd_listview, game_titles)

    if not all_elements_raw:
        logging.info("На рабочем столе нет элементов для сортировки.")
        return

    # Преобразование и фильтрация элементов
    desktop_elements = []
    for el_raw in all_elements_raw:
        name_lower = el_raw.get('name', '').lower()
        # Пропускаем системные элементы типа "Корзина", "Этот компьютер"
        # Эти элементы часто не имеют 'full_path' или имеют специфические имена.
        # Также они могут иметь индекс, но их перемещение может быть нежелательным или не работать стандартно.
        if (not el_raw.get('full_path') and \
            name_lower in ["корзина", "recycle bin", "этот компьютер", "мой компьютер", "computer", "this pc", "сеть", "network"]) or \
            el_raw.get('type') == "Системные": # Дополнительно проверяем категорию "Системные"
            logging.info(f"Пропуск системного или специального элемента '{el_raw.get('name')}' (Категория: {el_raw.get('category')}).")
            continue

        desktop_elements.append({
            'name': el_raw.get('name'),
            'path': el_raw.get('full_path'),
            'type': el_raw.get('category', 'Неизвестно'),
            'modification_date': el_raw.get('modification_date', 0.0),
            'current_x': el_raw.get('coords', (0,0))[0],
            'current_y': el_raw.get('coords', (0,0))[1],
            'index': el_raw.get('index')
        })

    # 3. Отсортировать ВСЕ элементы по дате изменения (новые в начале)
    desktop_elements.sort(key=lambda el: el['modification_date'], reverse=True)
    logging.info(f"Всего элементов для сортировки: {len(desktop_elements)}")

    # 4. Разделить элементы по категориям
    folders_list = []
    games_list = []
    text_files_list = [] # Включая документы, изображения и т.д.
    programs_exes_list = [] # Включая ярлыки на программы

    for element in desktop_elements:
        category = element['type']
        if category == "Папки":
            folders_list.append(element)
        elif category == "Игры":
            games_list.append(element)
        elif category in ["Документы", "Текстовые файлы", "пдф", "Изображения", "Видео", "Аудио", "Архивы", "Файлы разработки", "Документы (Онлайн)", "Мультимедиа (Онлайн)", "Файлы (Облако)"]:
            text_files_list.append(element)
        elif category in ["Программы", "Исполняемый файл", "Ярлыки (Прочее)", "Утилиты", "Разработка", "Браузеры", "Офисные программы", "Графика и 3D", "Мессенджеры", "Игровые платформы", "Разработка (Онлайн)"]:
            programs_exes_list.append(element)
        else: # "Неизвестно", "Интернет-ссылки" (общие), "Системные" (если какие-то прошли фильтр)
            logging.info(f"Элемент '{element['name']}' с категорией '{category}' будет отнесен к программам/прочему для размещения.")
            programs_exes_list.append(element) # По умолчанию относим к программам/прочему

    logging.info(f"Папки: {len(folders_list)}, Игры: {len(games_list)}, Текст/Док/Медиа: {len(text_files_list)}, Программы/Exe/Ярлыки: {len(programs_exes_list)}")

    # 5. Расчет позиций и перемещение для каждой категории

    # Вспомогательная функция для расчета количества элементов в ряду/колонке
    def calculate_max_items_in_dimension(available_space, item_cell_dim):
        if item_cell_dim <= 0: return 0
        return max(0, available_space // item_cell_dim)

    # --- Папки: Нижний правый угол, справа налево (<-), снизу вверх (^) ---
    # Сортировка по дате (новые первые) значит, что самые новые будут ближе к началу координат этой зоны.
    # То есть, самая новая папка будет в самом правом нижнем углу.
    folders_area_top_y = screen_height # Изначально вся высота доступна (если нет папок)
    if folders_list:
        logging.info("Размещение папок...")
        # Макс колонок: сколько ячеек помещается по ширине экрана
        max_cols = calculate_max_items_in_dimension(screen_width - scaled_padding, cell_width) # Учитываем отступ слева
        if max_cols == 0: logging.warning("Недостаточно ширины экрана для размещения даже одной колонки папок."); #return # или continue для других категорий

        start_x_base = screen_width - scaled_icon_width - scaled_padding # X для самой правой иконки
        start_y_base = screen_height - scaled_icon_height - scaled_padding # Y для самой нижней иконки

        current_x = start_x_base
        current_y = start_y_base

        col_idx = 0
        for i, item in enumerate(folders_list):
            logging.info(f"Перемещение папки '{item['name']}' в ({current_x}, {current_y}) (индекс {item['index']})")
            move_desktop_icon(hwnd_listview, item['index'], current_x, current_y)
            time.sleep(0.05)

            col_idx += 1
            if col_idx < max_cols:
                current_x -= cell_width # Двигаемся влево
            else: # Новый ряд (выше)
                current_x = start_x_base # Возвращаемся к правому краю
                current_y -= cell_height # Двигаемся вверх
                col_idx = 0
                if current_y < scaled_padding: # Не выходить за верхний край экрана
                    logging.warning("Достигнут верхний край экрана при размещении папок.")
                    break

        # Обновляем верхнюю границу зоны папок
        # current_y после цикла указывает на позицию, где _была бы_ следующая иконка в текущей колонке (если бы она была)
        # или на начало следующего ряда (если последний ряд был полон).
        # Если последний ряд не был полон, current_y корректна.
        # Если мы перешли на новый ряд (col_idx == 0), то current_y это начало этого (пустого) верхнего ряда.
        # Значит, самая верхняя занятая Y - это current_y (если col_idx !=0) или current_y + cell_height (если col_idx==0 и мы не в первом ряду)
        if folders_list:
            if col_idx == 0 and i > 0 : # Перешли на новый пустой ряд, значит последняя иконка была на current_y + cell_height
                 folders_area_top_y = current_y + cell_height
            else: # Либо в середине ряда, либо это первый ряд
                 folders_area_top_y = current_y
            # Убедимся, что folders_area_top_y не отрицательная
            folders_area_top_y = max(scaled_padding, folders_area_top_y)

    else:
        logging.info("Папок для размещения нет.")
        folders_area_top_y = screen_height # Если папок нет, текстовые файлы могут начинаться снизу

    # --- Игры: Верхний правый угол, справа налево (<-), сверху вниз (v) ---
    # Новые игры - ближе к верхнему правому углу.
    games_area_bottom_y = 0 # Изначально нет занятого пространства снизу
    if games_list:
        logging.info("Размещение игр...")
        max_cols = calculate_max_items_in_dimension(screen_width - scaled_padding, cell_width)
        if max_cols == 0: logging.warning("Недостаточно ширины экрана для игр."); #return

        start_x_base = screen_width - scaled_icon_width - scaled_padding
        start_y_base = scaled_padding # Начинаем сверху с отступом

        current_x = start_x_base
        current_y = start_y_base
        col_idx = 0
        for i, item in enumerate(games_list):
            logging.info(f"Перемещение игры '{item['name']}' в ({current_x}, {current_y}) (индекс {item['index']})")
            move_desktop_icon(hwnd_listview, item['index'], current_x, current_y)
            time.sleep(0.05)

            col_idx += 1
            if col_idx < max_cols:
                current_x -= cell_width # Влево
            else: # Новый ряд (ниже)
                current_x = start_x_base
                current_y += cell_height # Вниз
                col_idx = 0
                if current_y + scaled_icon_height > screen_height - scaled_padding: # Не выходить за нижний край
                    logging.warning("Достигнут нижний край экрана при размещении игр.")
                    break

        if games_list: # Обновляем нижнюю границу зоны игр
            if col_idx == 0 and i > 0: # Перешли на новый пустой ряд (ниже)
                games_area_bottom_y = current_y - cell_height + scaled_icon_height # Нижний край последнего размещенного
            else:
                games_area_bottom_y = current_y + scaled_icon_height
            games_area_bottom_y = min(screen_height - scaled_padding, games_area_bottom_y)
    else:
        logging.info("Игр для размещения нет.")
        games_area_bottom_y = scaled_padding # Если игр нет, программы могут начинаться сверху

    # --- Текстовые файлы: Над областью папок, справа налево (<-), снизу вверх (^) ---
    # Новые файлы - ближе к правому краю, сразу над папками.
    if text_files_list:
        logging.info("Размещение текстовых файлов...")
        max_cols = calculate_max_items_in_dimension(screen_width - scaled_padding, cell_width)
        if max_cols == 0: logging.warning("Недостаточно ширины для текстовых файлов."); #return

        # Начальная Y: на одну ячейку (иконка + отступ) выше верхней границы папок
        start_y_base = folders_area_top_y - scaled_icon_height - scaled_padding
        # Если папок не было, folders_area_top_y = screen_height, тогда start_y_base будет как у папок.
        if not folders_list: # Если папок не было, ведем себя как папки
            start_y_base = screen_height - scaled_icon_height - scaled_padding

        start_x_base = screen_width - scaled_icon_width - scaled_padding

        current_x = start_x_base
        current_y = start_y_base
        col_idx = 0

        for i, item in enumerate(text_files_list):
            # Проверка на перекрытие с играми (если игры есть и занимают это место)
            # Игры идут сверху вниз, справа налево.
            # current_y текстового файла не должен быть < games_area_bottom_y
            # И current_x не должен быть в зоне игр. Левая граница игр ~ screen_width - (max_cols_games * cell_width)
            # Это упрощенная проверка, т.к. игры могут не занимать все max_cols.
            if games_list and current_y < games_area_bottom_y and \
               current_x >= (screen_width - calculate_max_items_in_dimension(screen_width - scaled_padding, cell_width) * cell_width - scaled_padding):
                logging.warning(f"Текстовый файл '{item['name']}' ({current_x},{current_y}) может перекрыть зону игр (низ игр на {games_area_bottom_y}). Пропуск этого файла.")
                # Можно сделать сложнее: попытаться сдвинуть левее или ниже (если это первый ряд текста)
                # Или просто пропустить этот элемент и перейти к следующему в списке text_files_list
                continue

            if current_y < scaled_padding: # Не выходить за верхний край экрана
                logging.warning(f"Достигнут верхний край экрана при размещении текстового файла '{item['name']}'. Прерываем текст.")
                break

            logging.info(f"Перемещение текстового файла '{item['name']}' в ({current_x}, {current_y}) (индекс {item['index']})")
            move_desktop_icon(hwnd_listview, item['index'], current_x, current_y)
            time.sleep(0.05)

            col_idx += 1
            if col_idx < max_cols:
                current_x -= cell_width # Влево
            else: # Новый ряд (выше)
                current_x = start_x_base
                current_y -= cell_height # Вверх
                col_idx = 0
                # Проверка на выход за верхний край уже есть в начале цикла
    else:
        logging.info("Текстовых файлов для размещения нет.")

    # --- Ярлыки программ и .exe: Левая часть экрана, сверху вниз (v), слева направо (->) ---
    # Новые программы - ближе к верхнему левому углу.
    if programs_exes_list:
        logging.info("Размещение программ и exe...")
        # Макс строк: сколько ячеек помещается по высоте экрана
        max_rows = calculate_max_items_in_dimension(screen_height - scaled_padding, cell_height)
        if max_rows == 0: logging.warning("Недостаточно высоты экрана для программ."); #return

        start_x_base = scaled_padding # Начинаем слева с отступом
        start_y_base = scaled_padding # Начинаем сверху с отступом

        # Если игры занимают левый верхний угол, программы должны начаться ниже игр.
        # Левая граница игр: screen_width - (max_cols_games * cell_width)
        # Если start_x_base (для программ) >= левой границы игр И start_y_base (для программ) < games_area_bottom_y, то есть конфликт.
        if games_list:
            # Приблизительная левая граница самой левой колонки игр
            # (может быть неточной, если игры не занимают все колонки до конца)
            # Более точно: найти минимальный X среди игр. Но это сложно без чтения их позиций после перемещения.
            # Пока используем games_area_bottom_y как основной индикатор.
            # Если первая колонка программ (start_x_base) может пересечься с играми по Y.
            if start_y_base < games_area_bottom_y and \
               start_x_base + scaled_icon_width > (screen_width - calculate_max_items_in_dimension(screen_width-scaled_padding, cell_width) * cell_width - scaled_padding) : # Если программы могут зайти на территорию игр
                logging.info(f"Игры в верхнем правом углу (до Y={games_area_bottom_y}) могут мешать программам. Программы слева начнутся ниже игр.")
                start_y_base = games_area_bottom_y # Начать программы под играми (Y следующей ячейки)
                if start_y_base + scaled_icon_height > screen_height - scaled_padding :
                    logging.warning("Нет места для программ под играми. Размещение программ прервано.")
                    programs_exes_list = [] # Очищаем список, чтобы не пытаться их разместить

        current_x = start_x_base
        current_y = start_y_base
        row_idx = 0

        for i, item in enumerate(programs_exes_list):
            # Проверка на перекрытие с папками/текстом (если они дошли до левой части)
            # Папки/текст идут справа налево, снизу вверх.
            # Верхняя граница папок: folders_area_top_y
            # current_y программ не должен быть >= folders_area_top_y ЕСЛИ current_x программ попадает в зону папок/текста
            # Это сложная проверка, так как папки/текст могут не занимать всю ширину.
            # Упрощенно: если current_y программ ниже верха папок И current_x программ может быть в зоне папок
            if (folders_list or text_files_list) and \
               current_y + scaled_icon_height > folders_area_top_y and \
               current_x + scaled_icon_width > (screen_width - calculate_max_items_in_dimension(screen_width-scaled_padding, cell_width)*cell_width - scaled_padding):
                logging.warning(f"Программа '{item['name']}' ({current_x},{current_y}) может перекрыть зону папок/текста (верх на {folders_area_top_y}). Пропуск этого файла.")
                # Можно сдвинуть в новую колонку или остановить
                continue

            if current_x + scaled_icon_width > screen_width - scaled_padding: # Не выходить за правый край
                logging.warning("Достигнут правый край экрана при размещении программ.")
                break

            logging.info(f"Перемещение программы '{item['name']}' в ({current_x}, {current_y}) (индекс {item['index']})")
            move_desktop_icon(hwnd_listview, item['index'], current_x, current_y)
            time.sleep(0.05)

            row_idx += 1
            if row_idx < max_rows:
                current_y += cell_height # Вниз
            else: # Новая колонка (правее)
                current_y = start_y_base # Возвращаемся наверх (или под игры)
                current_x += cell_width   # Вправо
                row_idx = 0
                # Проверка на выход за правый край уже есть в начале цикла для current_x
    else:
        logging.info("Программ/exe для размещения нет.")

    logging.info("Сортировка иконок рабочего стола завершена.")
# Конец функции sort_desktop_icons
