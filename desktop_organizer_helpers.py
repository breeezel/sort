# -*- coding: utf-8 -*-
from typing import Tuple

def get_screen_resolution() -> Tuple[int, int]:
    """
    Возвращает разрешение экрана в пикселях.

    Returns:
        Tuple[int, int]: Кортеж (ширина, высота) в пикселях.
    """
    # Это заглушка. Реальная имплементация потребует OS-специфичных вызовов.
    # Например, для Windows:
    # import ctypes
    # user32 = ctypes.windll.user32
    # user32.SetProcessDPIAware()
    # return (user32.GetSystemMetrics(0), user32.GetSystemMetrics(1))
    return (1920, 1080)

def get_windows_scaling() -> float:
    """
    Возвращает коэффициент масштабирования Windows.

    Returns:
        float: Коэффициент масштабирования (например, 1.0 для 100%, 1.25 для 125%).
    """
    # Это заглушка. Реальная имплементация OS-специфична.
    # Например, для Windows можно использовать ctypes для вызова GetDpiForWindow или аналогичного API.
    return 1.0

def calculate_grid_dimensions(available_space_pixels: int, scaled_icon_size_pixels: int, scaled_padding_pixels: int) -> int:
    """
    Рассчитывает, сколько иконок может поместиться в доступном пространстве.

    Args:
        available_space_pixels (int): Доступное пространство в пикселях.
        scaled_icon_size_pixels (int): Размер иконки с учетом масштабирования в пикселях.
        scaled_padding_pixels (int): Отступ между иконками с учетом масштабирования в пикселях.

    Returns:
        int: Количество иконок, которое может поместиться.
    """
    # Логика расчета:
    # Мы добавляем один отступ к общему доступному пространству, потому что первая иконка не имеет отступа перед собой,
    # а последняя иконка не имеет отступа после себя, но формула (пространство + отступ) / (размер_иконки + отступ)
    # корректно обрабатывает количество элементов, которые могут поместиться.
    denominator = scaled_icon_size_pixels + scaled_padding_pixels
    if denominator == 0:
        # Предотвращение деления на ноль, если размер иконки и отступ равны нулю.
        return 0
    return (available_space_pixels + scaled_padding_pixels) // denominator
