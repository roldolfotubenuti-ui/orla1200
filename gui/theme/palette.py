from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ThemePalette:
  """Color tokens for the application theme.

  :param mode: Active theme identifier.
  :param accent: Primary accent color.
  :param accent_hover: Hover accent color.
  :param accent_pressed: Pressed accent color.
  :param accent_soft: Soft accent background.
  :param window_bg: Main window background.
  :param sidebar_bg: Legacy sidebar background token.
  :param topbar_bg: Top bar background.
  :param surface: Primary surface color.
  :param surface_alt: Secondary surface color.
  :param surface_muted: Muted surface color.
  :param border: Standard border color.
  :param border_strong: Stronger border color.
  :param text_primary: Primary text color.
  :param text_secondary: Secondary text color.
  :param text_muted: Muted text color.
  :param text_on_accent: Text color on accent surfaces.
  :param success: Success semantic color.
  :param warning: Warning semantic color.
  :param error: Error semantic color.
  :param info: Informational semantic color.
  :param shadow: Shadow color.
  :param row_hover: Table row hover color.
  :param row_selected: Table row selected color.
  :param scrollbar_track: Scrollbar track color.
  :param scrollbar_thumb: Scrollbar thumb color.
  :param sidebar_hover: Legacy sidebar hover token.
  :param sidebar_active: Legacy sidebar active token.
  :param chip_pending_bg: Pending badge background.
  :param chip_pending_fg: Pending badge foreground.
  :param chip_scheduled_bg: Scheduled badge background.
  :param chip_scheduled_fg: Scheduled badge foreground.
  :param chip_published_bg: Published badge background.
  :param chip_published_fg: Published badge foreground.
  :param chip_failed_bg: Failed badge background.
  :param chip_failed_fg: Failed badge foreground.
  :param terminal_shell: Terminal shell background.
  :param terminal_header: Terminal header background.
  :param terminal_bg: Terminal log background.
  :param terminal_border: Terminal border color.
  :param terminal_text: Terminal text color.
  :return: None
  """

  mode: str
  accent: str
  accent_hover: str
  accent_pressed: str
  accent_soft: str
  window_bg: str
  sidebar_bg: str
  topbar_bg: str
  surface: str
  surface_alt: str
  surface_muted: str
  border: str
  border_strong: str
  text_primary: str
  text_secondary: str
  text_muted: str
  text_on_accent: str
  success: str
  warning: str
  error: str
  info: str
  shadow: str
  row_hover: str
  row_selected: str
  scrollbar_track: str
  scrollbar_thumb: str
  sidebar_hover: str
  sidebar_active: str
  chip_pending_bg: str
  chip_pending_fg: str
  chip_scheduled_bg: str
  chip_scheduled_fg: str
  chip_published_bg: str
  chip_published_fg: str
  chip_failed_bg: str
  chip_failed_fg: str
  terminal_shell: str
  terminal_header: str
  terminal_bg: str
  terminal_border: str
  terminal_text: str


def _mix(hex_color: str, other_hex: str, factor: float) -> str:
  """Blend two hex colors.

  :param hex_color: Base color.
  :param other_hex: Target color.
  :param factor: Blend amount from 0 to 1.
  :return: Mixed hex color.
  """
  base = hex_color.lstrip("#")
  other = other_hex.lstrip("#")
  red_1, green_1, blue_1 = int(base[:2], 16), int(base[2:4], 16), int(base[4:6], 16)
  red_2, green_2, blue_2 = int(other[:2], 16), int(other[2:4], 16), int(other[4:6], 16)
  red = round(red_1 + (red_2 - red_1) * factor)
  green = round(green_1 + (green_2 - green_1) * factor)
  blue = round(blue_1 + (blue_2 - blue_1) * factor)
  return f"#{red:02x}{green:02x}{blue:02x}"


def _lighten(hex_color: str, factor: float) -> str:
  """Lighten a hex color.

  :param hex_color: Source color.
  :param factor: Blend strength.
  :return: Lightened color.
  """
  return _mix(hex_color, "#ffffff", factor)


def _darken(hex_color: str, factor: float) -> str:
  """Darken a hex color.

  :param hex_color: Source color.
  :param factor: Blend strength.
  :return: Darkened color.
  """
  return _mix(hex_color, "#000000", factor)


def _light_palette(
  theme_name: str,
  accent: str,
  window_bg: str,
  topbar_bg: str,
  surface_alt: str,
  surface_muted: str,
  border: str,
  border_strong: str,
  text_primary: str,
  text_secondary: str,
  text_muted: str,
  terminal_shell: str,
  terminal_header: str,
  terminal_bg: str,
  terminal_border: str,
  terminal_text: str,
) -> ThemePalette:
  """Build a light-oriented palette.

  :param theme_name: Theme identifier.
  :param accent: Accent color.
  :param window_bg: Window background.
  :param topbar_bg: Top bar background.
  :param surface_alt: Alternate surface color.
  :param surface_muted: Muted surface color.
  :param border: Border color.
  :param border_strong: Strong border color.
  :param text_primary: Primary text color.
  :param text_secondary: Secondary text color.
  :param text_muted: Muted text color.
  :param terminal_shell: Terminal shell color.
  :param terminal_header: Terminal header color.
  :param terminal_bg: Terminal body color.
  :param terminal_border: Terminal border color.
  :param terminal_text: Terminal text color.
  :return: Theme palette.
  """
  return ThemePalette(
    mode=theme_name,
    accent=accent,
    accent_hover=_lighten(accent, 0.12),
    accent_pressed=_darken(accent, 0.16),
    accent_soft=_lighten(accent, 0.84),
    window_bg=window_bg,
    sidebar_bg=surface_alt,
    topbar_bg=topbar_bg,
    surface="#ffffff",
    surface_alt=surface_alt,
    surface_muted=surface_muted,
    border=border,
    border_strong=border_strong,
    text_primary=text_primary,
    text_secondary=text_secondary,
    text_muted=text_muted,
    text_on_accent="#ffffff",
    success="#15803d",
    warning="#c67d00",
    error="#d93025",
    info="#2563eb",
    shadow="rgba(15, 23, 42, 0.08)",
    row_hover=_lighten(accent, 0.90),
    row_selected=_lighten(accent, 0.78),
    scrollbar_track=_darken(surface_alt, 0.02),
    scrollbar_thumb=_darken(surface_alt, 0.18),
    sidebar_hover=_lighten(accent, 0.90),
    sidebar_active=_lighten(accent, 0.84),
    chip_pending_bg=_lighten(accent, 0.90),
    chip_pending_fg=text_secondary,
    chip_scheduled_bg="#fff4d6",
    chip_scheduled_fg="#8a5a00",
    chip_published_bg="#dbf7e8",
    chip_published_fg="#136f45",
    chip_failed_bg="#fde5e3",
    chip_failed_fg="#b3261e",
    terminal_shell=terminal_shell,
    terminal_header=terminal_header,
    terminal_bg=terminal_bg,
    terminal_border=terminal_border,
    terminal_text=terminal_text,
  )


def _dark_palette(
  theme_name: str,
  accent: str,
  window_bg: str,
  topbar_bg: str,
  surface: str,
  surface_alt: str,
  surface_muted: str,
  border: str,
  border_strong: str,
  text_primary: str,
  text_secondary: str,
  text_muted: str,
  terminal_shell: str,
  terminal_header: str,
  terminal_bg: str,
  terminal_border: str,
  terminal_text: str,
) -> ThemePalette:
  """Build a dark-oriented palette.

  :param theme_name: Theme identifier.
  :param accent: Accent color.
  :param window_bg: Window background.
  :param topbar_bg: Top bar background.
  :param surface: Primary surface color.
  :param surface_alt: Alternate surface color.
  :param surface_muted: Muted surface color.
  :param border: Border color.
  :param border_strong: Strong border color.
  :param text_primary: Primary text color.
  :param text_secondary: Secondary text color.
  :param text_muted: Muted text color.
  :param terminal_shell: Terminal shell color.
  :param terminal_header: Terminal header color.
  :param terminal_bg: Terminal body color.
  :param terminal_border: Terminal border color.
  :param terminal_text: Terminal text color.
  :return: Theme palette.
  """
  return ThemePalette(
    mode=theme_name,
    accent=accent,
    accent_hover=_lighten(accent, 0.12),
    accent_pressed=_darken(accent, 0.18),
    accent_soft=_darken(_lighten(accent, 0.22), 0.52),
    window_bg=window_bg,
    sidebar_bg=surface,
    topbar_bg=topbar_bg,
    surface=surface,
    surface_alt=surface_alt,
    surface_muted=surface_muted,
    border=border,
    border_strong=border_strong,
    text_primary=text_primary,
    text_secondary=text_secondary,
    text_muted=text_muted,
    text_on_accent="#ffffff",
    success="#22c55e",
    warning="#f59e0b",
    error="#f97373",
    info="#60a5fa",
    shadow="rgba(2, 6, 23, 0.32)",
    row_hover=_lighten(surface_alt, 0.04),
    row_selected=_darken(_lighten(accent, 0.18), 0.58),
    scrollbar_track=_darken(surface_muted, 0.12),
    scrollbar_thumb=_lighten(surface_muted, 0.12),
    sidebar_hover=_lighten(surface_alt, 0.04),
    sidebar_active=_darken(_lighten(accent, 0.12), 0.48),
    chip_pending_bg=_lighten(surface_muted, 0.06),
    chip_pending_fg=text_primary,
    chip_scheduled_bg="#4f3c08",
    chip_scheduled_fg="#ffd670",
    chip_published_bg="#123624",
    chip_published_fg="#86efac",
    chip_failed_bg="#4a1f24",
    chip_failed_fg="#fca5a5",
    terminal_shell=terminal_shell,
    terminal_header=terminal_header,
    terminal_bg=terminal_bg,
    terminal_border=terminal_border,
    terminal_text=terminal_text,
  )


def build_palette(theme_name: str, accent_fallback: str = "#2563eb") -> ThemePalette:
  """Build a resolved theme palette.

  :param theme_name: Theme identifier.
  :param accent_fallback: Fallback accent used by the base light and dark themes.
  :return: Theme palette.
  """
  theme_key = theme_name.strip().lower()

  if theme_key == "light":
    return _light_palette(
      theme_name="light",
      accent=accent_fallback,
      window_bg="#f1f5f9",
      topbar_bg="#f8fafc",
      surface_alt="#f8fafc",
      surface_muted="#edf2f7",
      border="#d6dde8",
      border_strong="#bec8d6",
      text_primary="#0f172a",
      text_secondary="#475569",
      text_muted="#64748b",
      terminal_shell="#dbe7f5",
      terminal_header="#cfdff1",
      terminal_bg="#152235",
      terminal_border="#b7cade",
      terminal_text="#dbe4f0",
    )

  if theme_key == "orange":
    return _light_palette(
      theme_name="orange",
      accent="#ea580c",
      window_bg="#fff7ed",
      topbar_bg="#fff8f1",
      surface_alt="#fff3e6",
      surface_muted="#ffe8cf",
      border="#efcfac",
      border_strong="#e2b785",
      text_primary="#3b2414",
      text_secondary="#8a5a2b",
      text_muted="#a06e3b",
      terminal_shell="#362116",
      terminal_header="#4a2a18",
      terminal_bg="#21130c",
      terminal_border="#6f4627",
      terminal_text="#ffe2c7",
    )

  if theme_key == "ocean":
    return _light_palette(
      theme_name="ocean",
      accent="#0284c7",
      window_bg="#eef8fd",
      topbar_bg="#f5fbff",
      surface_alt="#edf8fd",
      surface_muted="#dff2fa",
      border="#c6e3ef",
      border_strong="#9bcde3",
      text_primary="#0a2233",
      text_secondary="#33566d",
      text_muted="#54758a",
      terminal_shell="#122738",
      terminal_header="#173446",
      terminal_bg="#0b1d2a",
      terminal_border="#25465d",
      terminal_text="#d8edf8",
    )

  if theme_key == "forest":
    return _light_palette(
      theme_name="forest",
      accent="#2f855a",
      window_bg="#f2f8f4",
      topbar_bg="#f7fbf8",
      surface_alt="#eef7f1",
      surface_muted="#e0efe5",
      border="#cfe1d5",
      border_strong="#aac5b3",
      text_primary="#10281a",
      text_secondary="#355845",
      text_muted="#587464",
      terminal_shell="#14261e",
      terminal_header="#1c3429",
      terminal_bg="#0d1713",
      terminal_border="#305143",
      terminal_text="#ddefe4",
    )

  if theme_key == "rose":
    return _light_palette(
      theme_name="rose",
      accent="#db2777",
      window_bg="#fdf2f8",
      topbar_bg="#fff7fb",
      surface_alt="#fdebf4",
      surface_muted="#f9dce9",
      border="#efc6d8",
      border_strong="#dda6c1",
      text_primary="#3a1025",
      text_secondary="#7d3558",
      text_muted="#9b5b79",
      terminal_shell="#311424",
      terminal_header="#431a31",
      terminal_bg="#1b0d15",
      terminal_border="#6a2d4d",
      terminal_text="#f9dce9",
    )

  if theme_key == "slate":
    return _dark_palette(
      theme_name="slate",
      accent="#14b8a6",
      window_bg="#0f1115",
      topbar_bg="#151922",
      surface="#171c26",
      surface_alt="#1d2430",
      surface_muted="#121822",
      border="#2a3341",
      border_strong="#374456",
      text_primary="#edf2f7",
      text_secondary="#aeb9c8",
      text_muted="#8894a7",
      terminal_shell="#151a22",
      terminal_header="#1b2230",
      terminal_bg="#0d121b",
      terminal_border="#2e3949",
      terminal_text="#e2e8f0",
    )

  return _dark_palette(
    theme_name="dark",
    accent=accent_fallback,
    window_bg="#0b0d12",
    topbar_bg="#11141c",
    surface="#151923",
    surface_alt="#1c2230",
    surface_muted="#10131b",
    border="#262e3f",
    border_strong="#364156",
    text_primary="#f1f5f9",
    text_secondary="#94a3b8",
    text_muted="#64748b",
    terminal_shell="#0f131c",
    terminal_header="#161b26",
    terminal_bg="#090c12",
    terminal_border="#222a3a",
    terminal_text="#e2e8f0",
  )
