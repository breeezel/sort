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
    Порядок проверки: Папки -> Системные -> Игры -> Программы -> Файлы/Ссылки -> Прочее.

    Args:
        icon_info (dict): Словарь с информацией об иконке.
                          Ожидаемые ключи: 'name', 'type', 'full_path'.
        game_titles (list): Список строк с названиями игр (в нижнем регистре).

    Returns:
        str: Название категории для иконки.
    """
    name_lower = icon_info['name'].lower()
    icon_type = icon_info['type'].lower() if icon_info['type'] else "неизвестный тип"
    full_path_lower = icon_info['full_path'].lower() if icon_info['full_path'] else ""

    is_exe = full_path_lower.endswith(".exe")
    # Проверяем, находится ли файл непосредственно на рабочем столе
    # (путь заканчивается на desktop\имя_файла.exe или desktop/имя_файла.exe)
    # Это упрощенная проверка; более надежно было бы получить путь к рабочему столу системно.
    is_on_desktop = False
    if full_path_lower:
        normalized_path = full_path_lower.replace("/", os.sep)
        desktop_path_suffix = os.sep + "desktop" + os.sep + name_lower
        if normalized_path.endswith(desktop_path_suffix):
             is_on_desktop = True
        # Также проверяем, если имя файла включает расширение, а name_lower нет
        elif name_lower.endswith(".exe") and normalized_path.endswith(os.sep + "desktop" + os.sep + name_lower):
            is_on_desktop = True
        elif not name_lower.endswith(".exe") and normalized_path.endswith(os.sep + "desktop" + os.sep + name_lower + ".exe"):
             is_on_desktop = True


    # 1. Папки (Наивысший приоритет)
    if icon_type == "папка":
        return "Папки"

    # 2. Системные элементы (например, Корзина, Этот компьютер)
    if name_lower == "корзина" and icon_type == "неизвестный тип":
        return "Системные"
    system_names_exact = ["этот компьютер", "мой компьютер", "панель управления", "network", "сеть", "computer", "control panel", "recycle bin"]
    if name_lower in system_names_exact and icon_type == "неизвестный тип":
        return "Системные"

    # 3. Игры (проверяются перед программами)
    # 3.1. Steam-игры через интернет-ярлык (очень точный признак)
    if icon_type == "интернет-ярлык" and full_path_lower.startswith("steam://rungameid/"):
        return "Игры"

    # 3.2. Имя иконки совпадает с названием из файла game_titles.txt (высокий приоритет)
    if any(game_title == name_lower for game_title in game_titles) or \
       any(game_title in name_lower for game_title in game_titles):
        return "Игры"

    # 3.3. Явное указание на известные игры в имени
    known_games_keywords = [
        "battlefield", "minecraft", "ведьмак", "witcher", "counter-strike", "csgo", "cs:go",
        "dota 2", "valorant", "fortnite", "overwatch", "cyberpunk", "gta", "stalker",
        "world of warcraft", "league of legends", "apex legends", "genshin impact",
        "warframe", "terraria", "stardew valley", "doom", "elden ring", "baldurs gate", "baldurs gate 3"
    ]
    if any(game_keyword in name_lower for game_keyword in known_games_keywords):
        return "Игры"

    # 3.4. .exe в специфичных игровых директориях ("steamapps", "games", "игры")
    if is_exe:
        game_path_indicators = [
            os.sep + "steamapps" + os.sep,
            os.sep + "games" + os.sep,
            os.sep + "игры" + os.sep,
            "games" + os.sep, # Корень диска
            "игры" + os.sep   # Корень диска
        ]
        if any(indicator in full_path_lower for indicator in game_path_indicators):
            return "Игры"

    # 3.5. Общие игровые ключевые слова - применяются с осторожностью, НЕ для .exe на рабочем столе без других признаков
    if not (is_exe and is_on_desktop): # Ослабляем для .exe на рабочем столе
        game_keywords_general = ["game", "play", "игра", "играть"] # "launcher" убрано, т.к. игровые лаунчеры есть в known_program_names
        # Исключаем слова, которые могут указывать на программы, а не игры
        program_like_keywords = ["player", "проигрыватель", "editor", "редактор", "sdk", "kit", "engine"]
        if any(keyword in name_lower for keyword in game_keywords_general) and \
           not any(prog_kw in name_lower for prog_kw in program_like_keywords):
            # Дополнительная проверка: для .exe файлов требуем также наличие игрового слова в пути,
            # чтобы избежать ошибочной классификации утилит с "game" в названии.
            if is_exe:
                if any(keyword in full_path_lower for keyword in game_keywords_general):
                    return "Игры"
            else: # Для не .exe файлов (например, ярлыков без полного пути) старая логика
                 if any(keyword in full_path_lower for keyword in game_keywords_general) or icon_type == "интернет-ярлык":
                    # Исключаем игровые лаунчеры, которые должны быть "Программы"
                    if not any(launcher_name in name_lower for launcher_name in ["steam", "epic games launcher", "battle.net", "origin", "uplay", "gog galaxy"]):
                        return "Игры"


    # 4. Программы (проверяются после всех игр)
    known_program_names = [
        # Игровые лаунчеры - это программы
        "steam", "epic games launcher", "gog galaxy", "origin", "uplay", "battle.net", "rockstar games launcher",
        # ПО для общения
        "discord", "telegram", "skype", "zoom", "slack", "whatsapp", "viber",
        # Среды разработки и текстовые редакторы
        "vscode", "visual studio", "pycharm", "intellij idea", "android studio", "sublime text", "notepad++",
        # Графические и 3D редакторы, ПО для стриминга
        "photoshop", "gimp", "blender", "obs studio", "krita", "inkscape", "figma", "autocad", "maya", "3ds max",
        # Медиаплееры
        "vlc", "k-lite", "winamp", "aimp", "foobar2000",
        # Браузеры
        "chrome", "firefox", "edge", "opera", "brave", "yandex browser",
        # Офисные пакеты
        "word", "excel", "powerpoint", "outlook", "libreoffice", "openoffice", "access", "publisher",
        # Утилиты
        "utorrent", "bittorrent", "filezilla", "putty", "total commander", "7-zip", "winrar", "daemon tools",
        "virtualbox", "vmware", "docker", "ccleaner", "teamviewer", "anydesk", "rdp", "mstsc",
        # Другие популярные программы
        "evernote", "onedrive", "dropbox", "google drive", "spotify", "itunes", "obsidian"
    ]
    if any(prog_name in name_lower for prog_name in known_program_names):
        return "Программы"

    # Проверка на Program Files для .exe и ярлыков (если не игра)
    if is_exe or icon_type == "ярлык":
        program_files_paths = ["program files" + os.sep, "program files (x86)" + os.sep]
        if any(pf_path in full_path_lower for pf_path in program_files_paths):
            return "Программы"

    # Если .exe файл дошел до этого момента и не классифицирован как игра, он считается программой
    if is_exe:
        return "Программы"

    # Общая проверка на тип "ярлык" (если еще не программа и не игра)
    if icon_type == "ярлык":
        return "Программы"
    # "файл" (без .exe) здесь уже не должен быть программой, если не попал в known_program_names

    # 5. Текстовые файлы
    text_extensions = ['.txt', '.md', '.log', '.doc', '.docx', '.rtf', '.odt', '.tex', '.json', '.xml', '.yaml', '.ini', '.cfg', '.py', '.js', '.html', '.css']
    if icon_type == "текстовый файл" or any(full_path_lower.endswith(ext) for ext in text_extensions):
        return "Текстовые файлы"

    # 6. Изображения
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico', '.svg', '.tiff', '.webp', '.psd', '.ai', '.raw']
    if icon_type == "изображение" or any(full_path_lower.endswith(ext) for ext in image_extensions):
        return "Изображения"

    # 7. Интернет-ссылки (не игровые и не Steam, не магазины приложений)
    if icon_type == "интернет-ярлык": # Уже проверено, что это не steam://rungameid/ и не игровые магазины
        if full_path_lower.startswith("http://") or full_path_lower.startswith("https://") or full_path_lower.endswith(".url"):
            return "Интернет-ссылки"

    # 8. Прочее (если ничего из вышеперечисленного не подошло)
    return "Прочее"


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

    def _determine_item_type(item_name: str, desktop_search_paths: list, game_titles_list: list) -> tuple[str, str]:
        """
        Определяет тип элемента рабочего стола и его полный путь.
        Для ярлыков (.lnk) возвращает тип "ярлык" и путь к целевому файлу/папке.
        Для интернет-ярлыков (.url) возвращает тип "интернет-ярлык" и URL, на который они ссылаются.
        Возвращает кортеж (тип, полный_путь_или_url_или_пустая_строка).
        """
        # game_titles_list теперь доступен здесь для последующего использования
        # в вызове get_icon_category, когда он будет добавлен.

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


        determined_type = "неизвестный тип"
        determined_path = ""  # Будет хранить полный путь к элементу, его цель, или URL

        # 1. Поиск на рабочих столах (пользовательском и общем)
        for search_path_dir in desktop_search_paths:
            # A. Проверяем как есть (может быть папка или файл с расширением)
            full_path_candidate = os.path.join(search_path_dir, item_name)
            if os.path.exists(full_path_candidate):
                if os.path.isdir(full_path_candidate):
                    determined_type = "папка"
                    determined_path = full_path_candidate
                    return determined_type, determined_path
                elif os.path.isfile(full_path_candidate):
                    _, ext = os.path.splitext(full_path_candidate)
                    ext = ext.lower()
                    if ext == '.lnk':
                        determined_type = "ярлык"
                        target_path = _resolve_lnk_target(full_path_candidate)
                        determined_path = target_path if target_path else full_path_candidate
                        return determined_type, determined_path
                    elif ext == '.url':
                        determined_type = "интернет-ярлык"
                        target_url = _resolve_url_target(full_path_candidate)
                        determined_path = target_url if target_url else full_path_candidate
                        return determined_type, determined_path
                    elif ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.ico']:
                        determined_type = "изображение"
                    elif ext == '.txt':
                        determined_type = "текстовый файл"
                    elif ext == '.pdf':
                        determined_type = "пдф"
                    else:
                        determined_type = "файл"
                    determined_path = full_path_candidate
                    return determined_type, determined_path

            # B. Если точное совпадение не найдено, проверяем, не ярлык ли это (.lnk)
            #    Имя элемента в ListView ("Мой ярлык") может отличаться от имени файла ("Мой ярлык.lnk")
            shortcut_path_candidate_lnk = os.path.join(search_path_dir, item_name + ".lnk")
            if os.path.isfile(shortcut_path_candidate_lnk):
                determined_type = "ярлык"
                target_path = _resolve_lnk_target(shortcut_path_candidate_lnk)
                determined_path = target_path if target_path else shortcut_path_candidate_lnk
                return determined_type, determined_path

            # C. Проверяем, не интернет-ярлык ли это (.url)
            #    Аналогично, имя в ListView может не содержать ".url"
            shortcut_path_candidate_url = os.path.join(search_path_dir, item_name + ".url")
            if os.path.isfile(shortcut_path_candidate_url):
                determined_type = "интернет-ярлык"
                target_url = _resolve_url_target(shortcut_path_candidate_url)
                determined_path = target_url if target_url else shortcut_path_candidate_url
                return determined_type, determined_path

            # D. Проверяем элементы, у которых расширение (.lnk или .url) уже может быть в имени из ListView
            if item_name.lower().endswith(".lnk"):
                full_path_candidate_with_ext = os.path.join(search_path_dir, item_name)
                if os.path.isfile(full_path_candidate_with_ext):
                    determined_type = "ярлык"
                    target_path = _resolve_lnk_target(full_path_candidate_with_ext)
                    determined_path = target_path if target_path else full_path_candidate_with_ext
                    return determined_type, determined_path
            elif item_name.lower().endswith(".url"):
                full_path_candidate_with_ext = os.path.join(search_path_dir, item_name)
                if os.path.isfile(full_path_candidate_with_ext):
                    determined_type = "интернет-ярлык"
                    target_url = _resolve_url_target(full_path_candidate_with_ext)
                    determined_path = target_url if target_url else full_path_candidate_with_ext
                    return determined_type, determined_path


        # 2. Эвристика по самому имени, если путь не найден на рабочих столах (менее надежно)
        name_lower = item_name.lower()
        if name_lower.endswith(".lnk"):
            determined_type = "ярлык"
            # determined_path остается пустым, так как без файла ярлыка его цель не может быть разрешена
        elif name_lower.endswith(".url"):
            determined_type = "интернет-ярлык"
            # determined_path остается пустым, так как без файла .url его URL не может быть разрешен

        _, ext = os.path.splitext(name_lower)
        if ext:  # Если в имени есть расширение
            if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.ico']:
                determined_type = "изображение"
            elif ext == '.txt':
                determined_type = "текстовый файл"
            elif ext == '.pdf':
                determined_type = "пдф"
            # Можно добавить другие расширения по необходимости
            else:
                determined_type = "файл"

        # Для системных объектов, таких как "Корзина", "Этот компьютер" и т.д.,
        # determined_type останется "неизвестный тип", а determined_path — пустой строкой,
        # что уместно, поскольку у них нет прямого файлового пути.

        return determined_type, determined_path

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

            # Определяем тип элемента и его полный путь
            item_type, item_full_path = _determine_item_type(item_name, desktop_paths_list, game_titles_list)

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
                'name': item_name,
                'type': item_type,
                'full_path': item_full_path
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
                'category': item_category  # Добавляем категорию
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
                # Изменено для вывода индекса, типа и полного пути
                # Категория теперь извлекается из данных иконки, где она была сохранена
                print(f"Индекс: {icon['index']}, Имя: \"{icon['name']}\", Тип: {icon['type']}, Координаты: {icon['coords']}, Путь: {icon['full_path'] if icon['full_path'] else 'Не определен'}, Категория: {icon['category']}")

            print(f"\nВсего иконок: {len(icons_info)}")

            # move_desktop_icon(desktop_handle, 3, 1000, 1000)
        else:
            print("Не удалось получить информацию об иконках.")
    else:
        print("Не удалось найти HWND SysListView32 рабочего стола. Убедитесь, что вы работаете на Windows и рабочий стол активен.")
