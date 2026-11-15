"""Controller settings and calibration; edits stay in the dialog's draft settings."""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pawz.core.controller_catalog import ControllerCatalog, ControllerDefinition
from pawz.core.controller_inputs import LogicalAxis
from pawz.core.controller_services import Calibration, resolve_model, validate_mapping
from pawz.core.models import BUTTONS
from pawz.i18n import QT_TR_NOOP, tr
from pawz.infra.storage import DATA_DIR
from pawz.ui.artwork_editor import InputNamesDialog
from pawz.ui.controller_assets import (
    PROMPT_ROLE,
    PromptDelegate,
    SvgView,
    available_artwork,
    controller_prompt_svg,
    resolve_artwork,
)
from pawz.ui.controller_tables import IdentificationTable

# Built-in model names that are words rather than product names (see catalog.json).
SOURCES_ROLE = PROMPT_ROLE + 1  # mapping items: asset files a prompt is drawn from
TRANSLATED_MODEL_NAMES = (QT_TR_NOOP("Generic SDL controller"),)


def model_name(definition: ControllerDefinition) -> str:
    """The model name to display: built-in generic names are translated."""
    return tr(definition.model) if definition.model in TRANSLATED_MODEL_NAMES else definition.model


def import_illustration(parent) -> str | None:
    """Ask for an SVG, copy it to the settings folder; its ``user:`` reference."""
    filename, _ = QFileDialog.getOpenFileName(
        parent, tr("Import an illustration"), "", tr("SVG (*.svg)"))
    if not filename:
        return None
    path = Path(filename)
    if path.stat().st_size > 4_000_000 or not QSvgRenderer(filename).isValid():
        QMessageBox.warning(parent, tr("Invalid SVG"),
                            tr("The file must be a valid SVG under 4 MB."))
        return None
    target = DATA_DIR / "illustrations" / (uuid4().hex + ".svg")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(path.read_bytes())
    return "user:" + target.name


class IllustrationDialog(QDialog):
    """Pick a controller illustration, previewed in the current style."""

    def __init__(self, catalog: ControllerCatalog, model: ControllerDefinition,
                 current: str | None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Change illustration"))
        self.setObjectName("illustrationDialog")
        self.resize(620, 360)
        self.model = model
        names: dict[str, str] = {}  # a shared silhouette is named after its first model
        for definition in catalog.definitions:
            if definition.svg:
                names.setdefault(definition.svg, model_name(definition))
        root = QVBoxLayout(self)
        body = QHBoxLayout()
        column = QVBoxLayout()
        self.choices = QListWidget()
        self.choices.setObjectName("illustrationChoices")
        column.addWidget(self.choices, 1)
        import_button = QPushButton(tr("Import custom…"))
        import_button.setObjectName("importIllustration")
        import_button.clicked.connect(self._import)
        column.addWidget(import_button)  # as wide as the list
        body.addLayout(column, 2)
        self.preview = SvgView()
        self.preview.setObjectName("illustrationPreview")
        self.preview.setMinimumSize(260, 180)
        self.preview.set_render_scale(0.75)
        body.addWidget(self.preview, 3)
        root.addLayout(body, 1)
        self._add(tr("Default for this model"), None)
        for relative in available_artwork():
            label = names.get(relative) or Path(relative).stem.replace("-", " ").replace(".", " ").title()
            self._add(label, "asset:" + relative)
        folder = DATA_DIR / "illustrations"
        imported = sorted(folder.glob("*.svg"), key=lambda path: path.stat().st_mtime)
        for number, path in enumerate(imported, 1):
            self._add(tr("Imported illustration {number}").format(number=number), "user:" + path.name)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        buttons.addWidget(box)
        root.addLayout(buttons)
        self.choices.currentRowChanged.connect(self._show)
        self._select(current)
        self._show()

    def _add(self, label: str, reference: str | None) -> None:
        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, reference)
        self.choices.addItem(item)

    def _select(self, reference: str | None) -> None:
        for row in range(self.choices.count()):
            if self.choices.item(row).data(Qt.ItemDataRole.UserRole) == reference:
                self.choices.setCurrentRow(row)
                return
        self.choices.setCurrentRow(0)

    def _show(self, *_):
        self.preview.set_path(resolve_artwork(self.model, self.selection))

    @property
    def selection(self) -> str | None:
        item = self.choices.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _import(self):
        reference = import_illustration(self)
        if reference:
            count = sum(1 for row in range(self.choices.count())
                        if str(self.choices.item(row).data(Qt.ItemDataRole.UserRole)).startswith("user:"))
            self._add(tr("Imported illustration {number}").format(number=count + 1), reference)
            self._select(reference)


class CalibrationDialog(QDialog):
    def __init__(self, joystick, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Hardware input calibration"))
        self.calibration = Calibration(joystick)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(tr("Choose a logical input, then use it on the controller.\n"
                                   "Release all controls before each capture.")))
        self.logical = QComboBox()
        self.logical.addItems(list(BUTTONS) + [axis.value for axis in LogicalAxis
                                             if axis.value not in BUTTONS])
        layout.addWidget(self.logical)
        self.status = QLabel()
        layout.addWidget(self.status)
        capture = QPushButton(tr("Capture this input"))
        capture.clicked.connect(self.start_capture)
        layout.addWidget(capture)
        self.timer = QTimer(self)
        self.timer.setInterval(30)
        self.timer.timeout.connect(self.capture)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def start_capture(self):
        self.calibration.baseline = self.calibration.snapshot()
        self.status.setText(tr("Waiting for an input…"))
        self.timer.start()

    def capture(self):
        try:
            source = self.calibration.capture(self.logical.currentText())
            if source:
                self.timer.stop()
                self.status.setText(f"{self.logical.currentText()} → {source}")
        except Exception as exc:
            self.timer.stop()
            self.status.setText(str(exc))


class ControllersPage(QWidget):
    catalog_changed = Signal()

    def __init__(self, settings, catalog: ControllerCatalog, manager=None, parent=None):
        super().__init__(parent)
        self.settings, self.catalog, self.manager = settings, catalog, manager
        self.setObjectName("settingsPage")
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setObjectName("controllersScroll")
        scroll.viewport().setAutoFillBackground(False)
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        host = QWidget()
        host.setObjectName("controllersContent")
        host.setAutoFillBackground(False)
        scroll.setWidget(host)
        layout = QVBoxLayout(host)
        from pawz.ui.windows import (
            CONTROL_ROW_GAP,
            SECTION_CONTENT_GAP,
            ProfileSectionHeading,
            profile_action_button,
        )
        # Same rhythm as the Profiles tab: space before each heading, then a fixed gap.
        layout.setContentsMargins(14, 0, 14, 18)
        layout.setSpacing(CONTROL_ROW_GAP)

        def heading(title: str):
            layout.addSpacing(16)
            layout.addWidget(ProfileSectionHeading(title))
            layout.addSpacing(SECTION_CONTENT_GAP - layout.spacing())

        heading(tr("Models and mappings"))
        actions = QHBoxLayout()
        actions.setSpacing(CONTROL_ROW_GAP)
        for title, name, callback in (
                (tr("Add a mapping…"), "addMapping", self.add_mapping),
                (tr("Identify my controller…"), "identifyController", self.identify)):
            button = QPushButton(title)
            button.setObjectName(name)
            button.clicked.connect(callback)
            actions.addWidget(button)
        layout.addLayout(actions)
        self.device = QComboBox()
        self.device.setObjectName("controllerDevicePicker")
        self.device.setToolTip(tr("A controller pawz has seen: the rest of the page applies to it."))
        for key, name in settings.known_devices.items():
            self.device.addItem(settings.device_preferences.get(key, {}).get("name", name), key)
        self.model = QComboBox()
        self.model.setObjectName("controllerModelPicker")
        self.model.setToolTip(tr("The catalog model describing it: identification, mappings, drawing."))
        pickers = QGridLayout()
        pickers.setHorizontalSpacing(8)
        pickers.setVerticalSpacing(CONTROL_ROW_GAP)
        pickers.setColumnStretch(1, 1)
        for row_index, (label_text, picker) in enumerate(
                ((tr("Known controller"), self.device), (tr("Model used"), self.model))):
            label = QLabel(label_text)
            label.setBuddy(picker)
            label.setMinimumWidth(80)
            pickers.addWidget(label, row_index, 0)
            pickers.addWidget(picker, row_index, 1)
        rename_button = profile_action_button(tr("Rename this controller"), "edit")
        rename_button.setObjectName("renameController")
        rename_button.clicked.connect(self.edit_custom_name)
        pickers.addWidget(rename_button, 0, 2)
        self.edit_model = profile_action_button(tr("Edit"), "edit")
        self.edit_model.setObjectName("editControllerModel")
        self.delete_model = profile_action_button(tr("Delete"), "delete")
        self.delete_model.setObjectName("deleteControllerModel")
        duplicate = profile_action_button(tr("Duplicate"), "duplicate")
        duplicate.setObjectName("duplicateControllerModel")
        duplicate.clicked.connect(self.duplicate)
        self.edit_model.clicked.connect(self.edit)
        self.delete_model.clicked.connect(self.delete)
        for column, button in enumerate((duplicate, self.edit_model, self.delete_model), 2):
            pickers.addWidget(button, 1, column)
        layout.addLayout(pickers)

        heading(tr("Identification"))
        self.metadata = IdentificationTable()
        self.artwork = self.metadata.artwork
        calibrate = QPushButton(tr("Calibrate…"))
        calibrate.setObjectName("calibrateController")
        calibrate.clicked.connect(self.calibrate)
        name_inputs = QPushButton(tr("Name inputs…"))
        name_inputs.setObjectName("nameInputs")
        name_inputs.setToolTip(tr("Name the buttons and sticks of this drawing, so the main window "
                                  "can light them up where they are drawn."))
        name_inputs.clicked.connect(self.name_inputs)
        tools = QHBoxLayout()
        tools.setSpacing(8)
        tools.addWidget(calibrate, 1)
        tools.addWidget(name_inputs, 1)
        self.metadata.artwork_layout.insertLayout(1, tools)
        for title, name, callback in ((tr("Change illustration…"), "changeIllustration", self.choose_svg),
                                      (tr("Import custom…"), "importIllustration", self.import_svg),
                                      (tr("Restore default"), "restoreIllustration", self.restore_svg)):
            button = QPushButton(title)
            button.setObjectName(name)
            button.clicked.connect(callback)
            self.metadata.artwork_actions.addWidget(button, 1)
        self.metadata.refit()
        self.name = self.metadata.name
        self.name.editingFinished.connect(self.rename)
        self.metadata.copy_guid.clicked.connect(self.copy_guid)
        identification = QVBoxLayout()
        identification.setSpacing(CONTROL_ROW_GAP)
        identification.addWidget(self.metadata)
        self.apply_model = QPushButton()
        self.apply_model.setObjectName("useModel")
        self.apply_model.setMaximumWidth(self.metadata.maximumWidth())  # as wide as the table
        self.apply_model.clicked.connect(self.assign_model)
        identification.addWidget(self.apply_model)
        metadata_row = QHBoxLayout()
        metadata_row.addStretch(1)
        metadata_row.addLayout(identification, 12)
        metadata_row.addStretch(1)
        layout.addLayout(metadata_row)

        heading(tr("Mappings"))
        self.table = QTableWidget(0, 3)
        self.table.setObjectName("controllerCorrespondences")
        self.table.setHorizontalHeaderLabels(
            [tr("SDL logical input"), tr("Physical label"), tr("Hardware input")])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.setMinimumHeight(260)
        self.table.setItemDelegateForColumn(1, PromptDelegate(0.72, self.table))
        # The scroll bar runs beside the rows only: a spacer as tall as the header sits
        # above it.
        header_spacer = QWidget()
        header_spacer.setObjectName("scrollHeaderSpacer")
        header_spacer.setFixedHeight(self.table.horizontalHeader().sizeHint().height())
        self.table.addScrollBarWidget(header_spacer, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.table)

        self.device.currentIndexChanged.connect(self.select_device)
        self.model.currentIndexChanged.connect(self.refresh)
        self.reload_models()
        self.select_device()
        if manager is not None:
            manager.devices_changed.connect(self.refresh_devices)

    def refresh_devices(self):
        selected = self.device.currentData()
        live = getattr(self.manager, "settings", None)
        if live is None:
            return
        self.settings.known_devices.update(live.known_devices)
        for key, preferences in live.device_preferences.items():
            draft = self.settings.device_preferences.setdefault(key, {})
            for field in ("guid", "detected_name"):
                if field in preferences:
                    draft[field] = preferences[field]
        self.device.blockSignals(True)
        self.device.clear()
        for key, name in self.settings.known_devices.items():
            self.device.addItem(self.settings.device_preferences.get(key, {}).get("name") or name, key)
        self.device.setCurrentIndex(max(0, self.device.findData(selected)))
        self.device.blockSignals(False)
        self.select_device()

    def reload_models(self, selected=None):
        self.model.blockSignals(True)
        self.model.clear()
        for definition in self.catalog.definitions:
            self.model.addItem(model_name(definition), definition.id)
        self.model.setCurrentIndex(max(0, self.model.findData(selected)))
        self.model.blockSignals(False)
        self.refresh()
        self.catalog_changed.emit()

    def preferences(self):
        key = self.device.currentData()
        return self.settings.device_preferences.setdefault(key, {}) if key else {}

    def select_device(self, *_):
        preferences = self.preferences()
        key = self.device.currentData()
        self.name.setText(preferences.get("name", ""))
        self.name.setPlaceholderText(self.default_name())
        model_id = resolve_model(self.catalog.definitions, preferences.get("guid", ""),
                                 self.settings.known_devices.get(key, ""), preferences.get("model_id"))
        self.model.setCurrentIndex(max(0, self.model.findData(model_id)))
        self.refresh()

    def refresh(self, *_):
        if not self.model.currentData():
            return
        definition = self.catalog.get(self.model.currentData())
        builtin = self.catalog.is_builtin(definition.id)
        self.edit_model.setEnabled(not builtin)
        self.delete_model.setEnabled(not builtin)
        preferences = self.preferences()
        self.metadata.set_values((definition.manufacturer or "—", model_name(definition), definition.family,
                                  preferences.get("guid") or "—",
                                  tr("Verified") if definition.verified else tr("Not verified on hardware")))
        self.metadata.setToolTip(definition.provenance)
        self.update_apply_model()
        self.artwork.set_path(resolve_artwork(definition, preferences.get("svg")))
        inputs = list(dict.fromkeys(list(BUTTONS) + [axis.value for axis in LogicalAxis]))
        mapping = self.settings.controller_mappings.get(self.device.currentData(), {})
        self.table.setRowCount(len(inputs))
        for row, logical in enumerate(inputs):
            for col, value in enumerate((logical, definition.physical_labels.get(logical, logical),
                                          str(mapping.get(logical, definition.hardware_mapping.get(logical, "SDL"))))):
                item = QTableWidgetItem(value if col != 1 else "")
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setToolTip(value)
                item.setData(Qt.ItemDataRole.AccessibleTextRole, value)
                if col == 1:  # drawn by PromptDelegate
                    data, sources = controller_prompt_svg(logical, definition)
                    item.setData(PROMPT_ROLE, data)
                    item.setData(SOURCES_ROLE, sources)
                self.table.setItem(row, col, item)

    def default_name(self) -> str:
        """The name SDL reported for the selected controller."""
        key = self.device.currentData()
        preferences = self.settings.device_preferences.get(key, {}) if key else {}
        return preferences.get("detected_name") or self.settings.known_devices.get(key, "")

    def rename(self):
        if self.device.currentData():
            name = self.name.text().strip()
            if name and name != self.default_name():
                self.preferences()["name"] = name
            else:
                self.preferences().pop("name", None)
                self.name.clear()

    def edit_custom_name(self):
        """Jump to the custom name, filled with the current name and selected."""
        if not self.name.text():
            self.name.setText(self.default_name())
        scroll = self.findChild(QScrollArea, "controllersScroll")
        if scroll is not None:
            scroll.ensureWidgetVisible(self.name, 0, 60)
        self.name.setFocus(Qt.FocusReason.OtherFocusReason)
        self.name.selectAll()

    def used_model(self) -> str | None:
        """The model the selected controller is shown and identified with."""
        key = self.device.currentData()
        if not key:
            return None
        preferences = self.settings.device_preferences.get(key, {})
        return resolve_model(self.catalog.definitions, preferences.get("guid", ""),
                             self.settings.known_devices.get(key, ""), preferences.get("model_id"))

    def update_apply_model(self):
        used = self.model.currentData() == self.used_model()
        self.apply_model.setEnabled(bool(self.device.currentData()) and not used)
        self.apply_model.setText(tr("✓ This model is already used for this controller") if used
                                 else tr("Use this model for this controller"))

    def assign_model(self):
        if self.device.currentData():
            self.preferences()["model_id"] = self.model.currentData()
            self.update_apply_model()

    def copy_guid(self):
        guid = self.preferences().get("guid")
        if guid:
            QApplication.clipboard().setText(guid)
            self.metadata.show_copied()

    def identify(self):
        self.select_device()
        QMessageBox.information(self, tr("Identification"), tr(
            "Detection uses the SDL GUID and name.\n"
            "A name alone is not a hardware verification.\n"
            "Choose the model by hand if in doubt."))

    def duplicate(self):
        definition = self.catalog.get(self.model.currentData())
        name, ok = QInputDialog.getText(self, tr("Duplicate"), tr("Model name"))
        if ok and name.strip():
            definition = replace(definition, id="custom." + uuid4().hex, model=name.strip(),
                                 verified=False, known_guids=(), provenance="User copy of " + definition.id)
            self.catalog.add_custom(definition)
            self.reload_models(definition.id)

    def edit(self):
        definition = self.catalog.get(self.model.currentData())
        text, ok = QInputDialog.getMultiLineText(self, tr("Edit model"), tr("JSON definition"),
                                                json.dumps(definition.dump(), ensure_ascii=False, indent=2))
        if ok:
            try:
                edited = ControllerDefinition.parse(json.loads(text))
                if edited.id != definition.id:
                    raise ValueError(tr("The model identifier must not change"))
                validate_mapping(edited.hardware_mapping)
                self.catalog.replace_custom(definition.id, replace(edited, verified=False))
                self.reload_models(definition.id)
            except (ValueError, KeyError, TypeError) as exc:
                QMessageBox.warning(self, tr("Invalid definition"), str(exc))

    def delete(self):
        model_id = self.model.currentData()
        self.catalog.remove_custom(model_id)
        for preferences in self.settings.device_preferences.values():
            if preferences.get("model_id") == model_id:
                preferences.pop("model_id")
        self.reload_models()

    def add_mapping(self):
        text, ok = QInputDialog.getMultiLineText(
            self, tr("Custom mapping"), tr("JSON: logical input → bN, aN, +/-aN, hN.M"),
                                                json.dumps(self.settings.controller_mappings.get(self.device.currentData(), {}), indent=2))
        if ok and self.device.currentData():
            try:
                self.settings.controller_mappings[self.device.currentData()] = validate_mapping(json.loads(text))
                self.refresh()
            except (ValueError, TypeError, AttributeError) as exc:
                QMessageBox.warning(self, tr("Invalid mapping"), str(exc))

    def calibrate(self):
        key = self.device.currentData()
        if self.manager is None or key not in self.manager.joysticks:
            QMessageBox.warning(self, tr("Calibration"), tr("Connect the controller to calibrate."))
            return
        self.manager.begin_input_capture()
        try:
            dialog = CalibrationDialog(self.manager.joysticks[key], self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.settings.controller_mappings.setdefault(key, {}).update(dialog.calibration.mapping)
                self.refresh()
        finally:
            self.manager.end_input_capture()

    def name_inputs(self):
        definition = self.catalog.get(self.model.currentData())
        path = resolve_artwork(definition, self.preferences().get("svg"))
        if path is not None and InputNamesDialog(path, self, definition.family).exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def choose_svg(self):
        if not self.device.currentData():
            return
        dialog = IllustrationDialog(self.catalog, self.catalog.get(self.model.currentData()),
                                    self.preferences().get("svg"), self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if dialog.selection:
                self.preferences()["svg"] = dialog.selection
            else:
                self.preferences().pop("svg", None)
            self.refresh()

    def import_svg(self):
        if not self.device.currentData():
            return
        reference = import_illustration(self)
        if reference:
            self.preferences()["svg"] = reference
            self.refresh()

    def restore_svg(self):
        self.preferences().pop("svg", None)
        self.refresh()
