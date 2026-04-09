from __future__ import annotations

from gui.theme.palette import build_palette


class StyleSheet:
  """Compatibility shim for legacy theme imports.

  :return: None
  """

  _palette = build_palette("dark", "#1E66FF")
  COLORS = {
    "bg_base": _palette.window_bg,
    "bg_card": _palette.surface,
    "bg_inset": _palette.surface_muted,
    "primary": _palette.accent,
    "primary_hover": _palette.accent_hover,
    "primary_pressed": _palette.accent_pressed,
    "text_primary": _palette.text_primary,
    "text_secondary": _palette.text_secondary,
    "success": _palette.success,
    "warning": _palette.warning,
    "error": _palette.error,
    "border_error": _palette.error,
  }

  @classmethod
  def apply_primary_color(cls, color: str) -> None:
    """Refresh legacy color tokens for compatibility.

    :param color: Accent color.
    :return: None
    """
    cls._palette = build_palette("dark", color)
    cls.COLORS.update({
      "primary": cls._palette.accent,
      "primary_hover": cls._palette.accent_hover,
      "primary_pressed": cls._palette.accent_pressed,
    })

  @classmethod
  def log_color(cls, level: int) -> str:
    """Return a semantic log color.

    :param level: Numeric log level.
    :return: Hex color value.
    """
    if level >= 40:
      return cls._palette.error
    if level >= 30:
      return cls._palette.warning
    if level == 25:
      return cls._palette.success
    if level <= 10:
      return cls._palette.text_secondary
    return cls._palette.text_primary
