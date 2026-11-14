"""Read-only controller identification table with responsive row heights.

Rows: the controller drawing with its illustration buttons (both columns merged),
the identification fields, then the custom name, edited in the right-hand column.
"""
from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pawz.i18n import QT_TR_NOOP, tr
from pawz.ui.controller_assets import SvgView
from pawz.ui.rendering import vector_icon

COPIED_FEEDBACK_MS = 2500
ARTWORK_HEIGHT = 75
ARTWORK_MARGIN = 14  # above the drawing and below its buttons
NAME_ROW_HEIGHT = 44


class IdentificationTable(QTableWidget):
    FIELDS = (QT_TR_NOOP("Manufacturer"), QT_TR_NOOP("Model"), QT_TR_NOOP("Family"),
              QT_TR_NOOP("SDL GUID"), QT_TR_NOOP("Status"))
    FIRST_FIELD_ROW = 1  # row 0 holds the drawing
    GUID_FIELD = 3

    def __init__(self, parent=None):
        super().__init__(len(self.FIELDS) + 2, 2, parent)
        self.setObjectName("controllerIdentification")
        self.horizontalHeader().hide()
        self.verticalHeader().hide()
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.verticalHeader().setMinimumSectionSize(28)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWordWrap(True)
        self.setMaximumWidth(600)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.setSpan(0, 0, 1, 2)
        self.artwork = SvgView()
        self.artwork.setObjectName("controllerPreview")
        self.artwork.setFixedHeight(ARTWORK_HEIGHT)
        self._artwork_cell = QWidget()
        holder_layout = self.artwork_layout = QVBoxLayout(self._artwork_cell)
        holder_layout.setContentsMargins(ARTWORK_MARGIN, ARTWORK_MARGIN, ARTWORK_MARGIN, ARTWORK_MARGIN)
        holder_layout.setSpacing(ARTWORK_MARGIN)
        holder_layout.addWidget(self.artwork)
        # Filled by the controllers page: choose, import, restore the illustration.
        self.artwork_actions = QHBoxLayout()
        self.artwork_actions.setSpacing(8)
        holder_layout.addLayout(self.artwork_actions)
        self.setCellWidget(0, 0, self._artwork_cell)

        # A copy button at the right of the GUID value (the item keeps the text).
        self.copy_guid = QPushButton()
        self.copy_guid.setObjectName("copyGuid")
        self.copy_guid.setIcon(vector_icon("copy"))
        self.copy_guid.setIconSize(QSize(14, 14))
        self.copy_guid.setFixedSize(24, 24)
        self.copy_guid.setFlat(True)
        self.copy_guid.setToolTip(tr("Copy"))
        self.copy_guid.setAccessibleName(tr("Copy the SDL GUID"))
        self.copy_guid.setCursor(Qt.CursorShape.PointingHandCursor)
        guid_cell = QWidget()
        guid_cell.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        guid_layout = QHBoxLayout(guid_cell)
        guid_layout.setContentsMargins(0, 0, 6, 0)
        guid_layout.addStretch(1)
        guid_layout.addWidget(self.copy_guid)
        self.setCellWidget(self.FIRST_FIELD_ROW + self.GUID_FIELD, 1, guid_cell)
        self._copied_timer = QTimer(self)
        self._copied_timer.setSingleShot(True)
        self._copied_timer.setInterval(COPIED_FEEDBACK_MS)
        self._copied_timer.timeout.connect(self._restore_copy_icon)

        self.name_row = self.rowCount() - 1
        label = QTableWidgetItem(tr("Custom name"))
        label.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setItem(self.name_row, 0, label)
        self.name = QLineEdit()
        self.name.setObjectName("controllerCustomName")
        name_holder = QWidget()
        name_layout = QVBoxLayout(name_holder)
        name_layout.setContentsMargins(8, 4, 8, 4)
        name_layout.addWidget(self.name)
        self.setCellWidget(self.name_row, 1, name_holder)

    def show_copied(self) -> None:
        """A tick replaces the copy icon for a few seconds."""
        self.copy_guid.setIcon(vector_icon("check"))
        self.copy_guid.setToolTip(tr("Copied"))
        self._copied_timer.start()

    def _restore_copy_icon(self) -> None:
        self.copy_guid.setIcon(vector_icon("copy"))
        self.copy_guid.setToolTip(tr("Copy"))

    def field(self, index: int, column: int = 1) -> QTableWidgetItem | None:
        """The item of identification field ``index`` (0 = manufacturer)."""
        return self.item(self.FIRST_FIELD_ROW + index, column)

    def set_values(self, values: tuple[str, ...]) -> None:
        if len(values) != len(self.FIELDS):
            raise ValueError("Identification requires five values")
        for index, (label, value) in enumerate(zip(self.FIELDS, values)):
            for column, text in enumerate((tr(label), value)):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setToolTip(text)
                self.setItem(self.FIRST_FIELD_ROW + index, column, item)
        self._fit_height()

    def refit(self) -> None:
        """Recompute row heights after the cell contents changed."""
        self._fit_height()

    def _fit_height(self) -> None:
        self.resizeRowsToContents()
        self.setRowHeight(0, max(ARTWORK_HEIGHT + 2 * ARTWORK_MARGIN,
                                 self._artwork_cell.sizeHint().height()))
        self.setRowHeight(self.name_row, NAME_ROW_HEIGHT)
        height = self.verticalHeader().length() + self.frameWidth() * 2
        if height != self.height():
            self.setFixedHeight(height)

    def sizeHint(self) -> QSize:
        return QSize(560, self.verticalHeader().length() + self.frameWidth() * 2)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.horizontalHeader().resizeSection(0, round(self.viewport().width() * 0.3))
        self._fit_height()
