# -*- coding: utf-8 -*-
from typing import List, NamedTuple, Tuple
import time # Для использования в modification_date

# Импорт вспомогательных функций
from desktop_organizer_helpers import get_screen_resolution, get_windows_scaling, calculate_grid_dimensions

# 2. Определение Заглушки DesktopElement
class DesktopElement(NamedTuple):
    """
    Структура данных для представления элемента на рабочем столе.
    """
    name: str
    path: str
    type: str  # Предварительная категория, может быть уточнена get_element_category
    modification_date: float
    current_x: int
    current_y: int

# 3. Определение Заглушек Пользовательских Функций
def get_desktop_elements() -> List[DesktopElement]:
    """
    Возвращает список элементов рабочего стола.
    Это заглушка для функции пользователя.
    """
    # Это заглушка. Реальная имплементация будет получать элементы рабочего стола.
    return [
        DesktopElement("Моя папка", "/path/to/my_folder", "folder", time.time() - 3600, 10, 10),
        DesktopElement("Отчет.txt", "/path/to/report.txt", "text_file", time.time() - 7200, 20, 20),
        DesktopElement("SuperGame.exe", "/path/to/SuperGame.exe", "game", time.time() - 1800, 30, 30),
        DesktopElement("Install_Tool.msi", "/path/to/Install_Tool.msi", "program", time.time() - 5400, 40, 40),
        DesktopElement("Старая папка", "/path/to/old_folder", "folder", time.time() - 86400, 50, 50),
        DesktopElement("notes.txt", "/path/to/notes.txt", "text_file", time.time() - 300, 60, 60),
        DesktopElement("AnotherGame", "/path/to/AnotherGame", "game", time.time() - 90000, 70, 70),
        DesktopElement("Utility.exe", "/path/to/Utility.exe", "program", time.time(), 80, 80), # Самый новый
    ]

def get_element_category(element: DesktopElement) -> str:
    """
    Определяет категорию элемента.
    Это заглушка для функции пользователя.
    """
    # Это заглушка. Реальная имплементация может анализировать имя, путь или тип.
    name_lower = element.name.lower()
    if "папка" in name_lower or element.type == "folder":
        return "folder"
    elif "game" in name_lower or ".exe" in name_lower and any(g_word in name_lower for g_word in ["game", "play"]): # Простой эвристический анализ для игр
        return "game"
    elif ".txt" in name_lower or ".doc" in name_lower or element.type == "text_file":
        return "text_file"
    elif ".exe" in name_lower or ".msi" in name_lower or element.type == "program": # .msi часто инсталляторы программ
        return "program"
    return "unknown" # Категория по умолчанию

def move_element_to_position(element: DesktopElement, x: int, y: int) -> None:
    """
    Перемещает элемент на указанную позицию.
    Это заглушка для функции пользователя.
    """
    # Это заглушка. Реальная имплементация будет взаимодействовать с ОС для перемещения иконки.
    print(f"Перемещение {element.name} в ({x}, {y})")

# 4. Определение функции sort_desktop_icons
def sort_desktop_icons() -> None:
    """
    Сортирует иконки на рабочем столе по категориям и дате модификации.
    Сначала получает информацию о разрешении экрана и масштабировании.
    Затем получает все элементы рабочего стола, сортирует их по дате модификации.
    После этого элементы классифицируются по категориям.
    В текущей версии, функция только выводит отсортированные и категоризированные списки.
    """
    # Инициализация
    screen_width, screen_height = get_screen_resolution()
    scale_factor = get_windows_scaling()
    # Базовые размеры и отступы для иконок (можно будет сделать настраиваемыми)
    icon_base_width: int = 75
    icon_base_height: int = 75
    icon_padding: int = 10 # Отступ между иконками

    # Расчет масштабированных размеров и отступов
    scaled_icon_width: int = int(icon_base_width * scale_factor)
    scaled_icon_height: int = int(icon_base_height * scale_factor)
    scaled_padding: int = int(icon_padding * scale_factor)
    # Русские комментарии для секции инициализации
    # screen_width, screen_height: ширина и высота экрана в пикселях
    # scale_factor: коэффициент масштабирования системы
    # icon_base_width, icon_base_height: базовые размеры иконки без масштабирования
    # icon_padding: базовый отступ между иконками без масштабирования
    # scaled_icon_width, scaled_icon_height: размеры иконки с учетом масштабирования
    # scaled_padding: отступ между иконками с учетом масштабирования

    # Получение и сортировка элементов
    all_elements: List[DesktopElement] = get_desktop_elements()
    # Сортировка элементов по дате модификации (сначала новые)
    all_elements.sort(key=lambda el: el.modification_date, reverse=True)

    # Категоризация элементов
    folders: List[DesktopElement] = []
    games: List[DesktopElement] = []
    text_files: List[DesktopElement] = []
    programs_exes: List[DesktopElement] = [] # Исполняемые файлы и программы
    # Цикл по всем элементам для их категоризации
    for element in all_elements:
        category = get_element_category(element)
        if category == "folder":
            folders.append(element)
        elif category == "game":
            games.append(element)
        elif category == "text_file":
            text_files.append(element)
        elif category == "program":
            programs_exes.append(element)
        # Можно добавить категорию 'other' для нераспознанных элементов

    # Удаляем старые отладочные print'ы
    # print(f"Разрешение экрана: {screen_width}x{screen_height}, Масштабирование: {scale_factor*100}%")
    # print(f"Масштабированные размеры иконки: {scaled_icon_width}x{scaled_icon_height}, Отступ: {scaled_padding}")
    # print("-" * 30)

    # --- 1. Папки (Снизу-справа, заполнение вверх) ---
    # Начальные координаты для папок
    start_x_folders: int = screen_width - scaled_icon_width - scaled_padding
    start_y_folders: int = screen_height - scaled_icon_height - scaled_padding

    # Количество иконок в ряду для папок
    # Используем screen_width для определения, сколько иконок поместится по ширине
    items_per_row_folders: int = calculate_grid_dimensions(screen_width, scaled_icon_width, scaled_padding)

    current_x: int = start_x_folders
    current_y: int = start_y_folders
    rows_occupied_by_folders: int = 0
    if folders: # Только если есть папки
        rows_occupied_by_folders = 1

    print(f"\n--- Размещение папок ({len(folders)}) ---")
    if items_per_row_folders > 0:
        for i, folder_item in enumerate(folders):
            move_element_to_position(folder_item, current_x, current_y)
            current_x -= (scaled_icon_width + scaled_padding) # Двигаемся влево

            # Если ряд заполнен и это не последний элемент
            if (i + 1) % items_per_row_folders == 0 and (i + 1) < len(folders):
                current_x = start_x_folders # Возвращаемся к началу ряда (справа)
                current_y -= (scaled_icon_height + scaled_padding) # Переходим на ряд выше
                rows_occupied_by_folders += 1
    elif folders: # Если есть папки, но не помещаются даже в один ряд
        print(f"Недостаточно места для размещения папок в ряд (ширина: {screen_width})")

    # Определение верхней границы папок
    folders_upper_boundary_y: int
    if not folders:
        folders_upper_boundary_y = screen_height # Если папок нет, граница - низ экрана
    else:
        # Y-координата верхнего края самой верхней папки
        # start_y_folders - это Y для нижнего края первого ряда папок.
        # Нам нужен Y для верхнего края самого верхнего ряда.
        folders_upper_boundary_y = start_y_folders - (rows_occupied_by_folders - 1) * (scaled_icon_height + scaled_padding)

    # --- 2. Игры (Сверху-справа, заполнение вниз) ---
    start_x_games: int = screen_width - scaled_icon_width - scaled_padding
    start_y_games: int = scaled_padding # Начинаем сверху с отступом

    items_per_row_games: int = calculate_grid_dimensions(screen_width, scaled_icon_width, scaled_padding)

    current_x = start_x_games
    current_y = start_y_games

    print(f"\n--- Размещение игр ({len(games)}) ---")
    if items_per_row_games > 0:
        for i, game_item in enumerate(games):
            move_element_to_position(game_item, current_x, current_y)
            current_x -= (scaled_icon_width + scaled_padding) # Двигаемся влево

            if (i + 1) % items_per_row_games == 0 and (i + 1) < len(games):
                current_x = start_x_games # Возвращаемся к началу ряда (справа)
                current_y += (scaled_icon_height + scaled_padding) # Переходим на ряд ниже
    elif games:
        print(f"Недостаточно места для размещения игр в ряд (ширина: {screen_width})")

    # --- 3. Текстовые файлы (Над папками, справа, заполнение вверх) ---
    start_x_text_files: int = screen_width - scaled_icon_width - scaled_padding
    # Размещаем над верхней границей папок, с учетом отступа
    start_y_text_files: int = folders_upper_boundary_y - scaled_padding - scaled_icon_height

    items_per_row_text_files: int = calculate_grid_dimensions(screen_width, scaled_icon_width, scaled_padding)

    current_x = start_x_text_files
    current_y = start_y_text_files

    print(f"\n--- Размещение текстовых файлов ({len(text_files)}) ---")
    if items_per_row_text_files > 0:
        for i, text_file_item in enumerate(text_files):
            # Проверка, чтобы текстовые файлы не заезжали слишком высоко (например, на место игр)
            # Это очень простая проверка, можно усложнить, если категории будут пересекаться
            if current_y < scaled_padding: # Не размещать выше самого верха экрана (с учетом отступа)
                print(f"Предупреждение: Текстовый файл '{text_file_item.name}' не может быть размещен, так как выходит за верхнюю границу.")
                break
            move_element_to_position(text_file_item, current_x, current_y)
            current_x -= (scaled_icon_width + scaled_padding) # Влево

            if (i + 1) % items_per_row_text_files == 0 and (i + 1) < len(text_files):
                current_x = start_x_text_files # Направо
                current_y -= (scaled_icon_height + scaled_padding) # Вверх
    elif text_files:
         print(f"Недостаточно места для размещения текстовых файлов в ряд (ширина: {screen_width}) или над папками.")


    # --- 4. Программы и EXE (Слева, сверху-вниз, заполнение вправо) ---
    start_x_programs: int = scaled_padding # Слева с отступом
    start_y_programs: int = scaled_padding # Сверху с отступом

    # Количество иконок в столбце для программ
    # Используем screen_height для определения, сколько иконок поместится по высоте
    items_per_column_programs: int = calculate_grid_dimensions(screen_height, scaled_icon_height, scaled_padding)

    current_x = start_x_programs
    current_y = start_y_programs

    print(f"\n--- Размещение программ и EXE ({len(programs_exes)}) ---")
    if items_per_column_programs > 0:
        for i, program_item in enumerate(programs_exes):
            move_element_to_position(program_item, current_x, current_y)
            current_y += (scaled_icon_height + scaled_padding) # Двигаемся вниз

            # Если столбец заполнен и это не последний элемент
            if (i + 1) % items_per_column_programs == 0 and (i + 1) < len(programs_exes):
                current_y = start_y_programs # Возвращаемся к началу столбца (сверху)
                current_x += (scaled_icon_width + scaled_padding) # Переходим на столбец правее
    elif programs_exes:
        print(f"Недостаточно места для размещения программ в столбец (высота: {screen_height})")


if __name__ == '__main__':
    # Пример вызова функции для тестирования
    sort_desktop_icons()
