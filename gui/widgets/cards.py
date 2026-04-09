from __future__ import annotations

from PyQt6.QtWidgets import QFrame, QWidget


class SurfaceCard(QFrame):
  """Reusable rounded card surface.

  :param class_name: Optional style class.
  :param parent: Parent widget.
  :return: None
  """

  def __init__(
    self,
    class_name: str = "card",
    parent: QWidget | None = None,
  ) -> None:
    """Initialize the card widget.

    :param class_name: Style class name.
    :param parent: Parent widget.
    :return: None
    """
    super().__init__(parent)
    self.setProperty("class", class_name)


class StatusChip(QFrame):
  """Container for status badges inside tables.

  :param parent: Parent widget.
  :return: None
  """

  def __init__(self, parent: QWidget | None = None) -> None:
    """Initialize the chip container.

    :param parent: Parent widget.
    :return: None
    """
    super().__init__(parent)
    self.setFrameShape(QFrame.Shape.NoFrame)
