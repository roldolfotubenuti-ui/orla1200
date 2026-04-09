from __future__ import annotations

import qtawesome as qta
from PyQt6.QtGui import QIcon


def build_icon(name: str, color: str) -> QIcon:
  """Build a themed icon from the qtawesome icon set.

  :param name: Icon identifier.
  :param color: Icon color.
  :return: Built icon.
  """
  return qta.icon(name, color=color)
