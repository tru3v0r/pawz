"""Read-only controller identification table with responsive row heights."""
from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QHeaderView, QSizePolicy, QTableWidget, QTableWidgetItem


class IdentificationTable(QTableWidget):
    FIELDS = ("Fabricant", "Modèle", "Famille", "GUID SDL", "Statut")

    def __init__(self, parent=None):
        super().__init__(len(self.FIELDS), 2, parent)
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

    def set_values(self, values: tuple[str, ...]) -> None:
        if len(values) != len(self.FIELDS):
            raise ValueError("Identification requires five values")
        for row, (label, value) in enumerate(zip(self.FIELDS, values)):
            for column, text in enumerate((label, value)):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setToolTip(text)
                self.setItem(row, column, item)
        self._fit_height()

    def _fit_height(self) -> None:
        self.resizeRowsToContents()
        height = self.verticalHeader().length() + self.frameWidth() * 2
        if height != self.height():
            self.setFixedHeight(height)

    def sizeHint(self) -> QSize:
        return QSize(560, self.verticalHeader().length() + self.frameWidth() * 2)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.horizontalHeader().resizeSection(0, round(self.viewport().width() * 0.3))
        self._fit_height()
