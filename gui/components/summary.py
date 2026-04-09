from __future__ import annotations

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from gui.widgets.cards import SurfaceCard


class MetricCard(SurfaceCard):
  """Small card used for quick metrics.

  :param title: Metric title.
  :param value: Initial metric value.
  :param caption: Supporting caption.
  :param parent: Parent widget.
  :return: None
  """

  def __init__(
    self,
    title: str,
    value: str,
    caption: str,
    parent: QWidget | None = None,
  ) -> None:
    """Initialize the metric card.

    :param title: Metric title.
    :param value: Initial metric value.
    :param caption: Supporting caption.
    :param parent: Parent widget.
    :return: None
    """
    super().__init__(class_name="stat-card", parent=parent)
    layout = QVBoxLayout(self)
    layout.setContentsMargins(18, 16, 18, 16)
    layout.setSpacing(4)

    self.title_label = QLabel(title)
    self.title_label.setProperty("class", "muted")
    layout.addWidget(self.title_label)

    self.value_label = QLabel(value)
    self.value_label.setProperty("class", "metric-value")
    layout.addWidget(self.value_label)

    self.caption_label = QLabel(caption)
    self.caption_label.setProperty("class", "stat-caption")
    layout.addWidget(self.caption_label)

  def set_value(self, value: str) -> None:
    """Update the displayed metric value.

    :param value: New metric value.
    :return: None
    """
    self.value_label.setText(value)

  def set_caption(self, caption: str) -> None:
    """Update the supporting caption.

    :param caption: Supporting caption.
    :return: None
    """
    self.caption_label.setText(caption)
