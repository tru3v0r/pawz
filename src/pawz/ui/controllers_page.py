"""Controller settings and calibration; edits stay in the dialog's draft settings."""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
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
from pawz.infra.storage import DATA_DIR
from pawz.ui.controller_assets import ASSET_DIR, SvgView, resolve_artwork
from pawz.ui.controller_tables import IdentificationTable


class CalibrationDialog(QDialog):
    def __init__(self, joystick, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Calibration des entrées matérielles")
        self.calibration = Calibration(joystick)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Choisissez une entrée logique, puis actionnez-la sur la manette.\n"
                                "Relâchez les contrôles avant chaque capture."))
        self.logical = QComboBox()
        self.logical.addItems(list(BUTTONS) + [axis.value for axis in LogicalAxis
                                             if axis.value not in BUTTONS])
        layout.addWidget(self.logical)
        self.status = QLabel()
        layout.addWidget(self.status)
        capture = QPushButton("Capturer cette entrée")
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
        self.status.setText("En attente d’une entrée…")
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
        from pawz.ui.windows import ProfileSectionHeading, profile_action_button
        layout.addWidget(ProfileSectionHeading("Modèles et mappings"))
        actions = QHBoxLayout()
        for title, name, callback in (
                ("Ajouter un mapping…", "addMapping", self.add_mapping),
                ("Identifier ma manette…", "identifyController", self.identify)):
            button = QPushButton(title)
            button.setObjectName(name)
            button.clicked.connect(callback)
            actions.addWidget(button)
        layout.addLayout(actions)
        self.device = QComboBox()
        self.device.setObjectName("controllerDevicePicker")
        for key, name in settings.known_devices.items():
            self.device.addItem(settings.device_preferences.get(key, {}).get("name", name), key)
        layout.addWidget(self.device)
        self.model = QComboBox()
        self.model.setObjectName("controllerModelPicker")
        row = QHBoxLayout()
        row.addWidget(self.model, 1)
        self.edit_model = profile_action_button("Modifier", "edit")
        self.edit_model.setObjectName("editControllerModel")
        self.delete_model = profile_action_button("Supprimer", "delete")
        self.delete_model.setObjectName("deleteControllerModel")
        duplicate = profile_action_button("Dupliquer", "duplicate")
        duplicate.setObjectName("duplicateControllerModel")
        duplicate.clicked.connect(self.duplicate)
        self.edit_model.clicked.connect(self.edit)
        self.delete_model.clicked.connect(self.delete)
        for button in (duplicate, self.edit_model, self.delete_model):
            row.addWidget(button)
        layout.addLayout(row)
        self.artwork = SvgView()
        layout.addWidget(ProfileSectionHeading("Identification"))
        self.artwork.setObjectName("controllerPreview")
        self.artwork.setFixedHeight(150)
        layout.addWidget(self.artwork)
        self.metadata = IdentificationTable()
        metadata_row = QHBoxLayout()
        metadata_row.addStretch(1)
        metadata_row.addWidget(self.metadata, 12)
        metadata_row.addStretch(1)
        layout.addLayout(metadata_row)
        form = QFormLayout()
        self.name = QLineEdit()
        self.name.setObjectName("controllerCustomName")
        self.name.editingFinished.connect(self.rename)
        form.addRow("Nom personnalisé", self.name)
        layout.addLayout(form)
        apply_model = QPushButton("Utiliser ce modèle pour cette manette")
        apply_model.clicked.connect(self.assign_model)
        layout.addWidget(apply_model)
        self.table = QTableWidget(0, 3)
        layout.addWidget(ProfileSectionHeading("Correspondances"))
        self.table.setObjectName("controllerCorrespondences")
        self.table.setHorizontalHeaderLabels(["Entrée logique SDL", "Libellé physique", "Entrée matérielle"])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.setMinimumHeight(260)
        layout.addWidget(self.table)
        layout.addWidget(ProfileSectionHeading("Personnalisation"))
        for title, callback in (("Calibrer…", self.calibrate),
                                ("Choisir une illustration…", self.choose_svg),
                                ("Importer un SVG personnalisé…", self.import_svg),
                                ("Restaurer l’illustration", self.restore_svg)):
            button = QPushButton(title)
            button.clicked.connect(callback)
            layout.addWidget(button)
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
            self.model.addItem(definition.model, definition.id)
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
        self.metadata.set_values((definition.manufacturer or "—", definition.model, definition.family,
                                  preferences.get("guid") or "—",
                                  "Vérifié" if definition.verified else "Non vérifié sur matériel"))
        self.metadata.setToolTip(definition.provenance)
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
                self.table.setItem(row, col, item)
            prompt = SvgView()
            prompt.setObjectName("physicalInputIcon")
            prompt.setAccessibleName(definition.physical_labels.get(logical, logical))
            prompt.setToolTip(definition.physical_labels.get(logical, logical))
            prompt.set_controller_prompt(logical, definition)
            prompt.set_render_scale(0.72)
            self.table.setCellWidget(row, 1, prompt)

    def rename(self):
        if self.device.currentData():
            self.preferences()["name"] = self.name.text().strip()

    def assign_model(self):
        if self.device.currentData():
            self.preferences()["model_id"] = self.model.currentData()

    def identify(self):
        self.select_device()
        QMessageBox.information(self, "Identification", "La détection utilise le GUID et le nom SDL.\n"
                                "Un nom seul ne constitue pas une vérification matérielle.\n"
                                "Choisissez manuellement le modèle en cas d’ambiguïté.")

    def duplicate(self):
        definition = self.catalog.get(self.model.currentData())
        name, ok = QInputDialog.getText(self, "Dupliquer", "Nom du modèle")
        if ok and name.strip():
            definition = replace(definition, id="custom." + uuid4().hex, model=name.strip(),
                                 verified=False, known_guids=(), provenance="Copie utilisateur de " + definition.id)
            self.catalog.add_custom(definition)
            self.reload_models(definition.id)

    def edit(self):
        definition = self.catalog.get(self.model.currentData())
        text, ok = QInputDialog.getMultiLineText(self, "Modifier le modèle", "Définition JSON",
                                                json.dumps(definition.dump(), ensure_ascii=False, indent=2))
        if ok:
            try:
                edited = ControllerDefinition.parse(json.loads(text))
                if edited.id != definition.id:
                    raise ValueError("L’identifiant du modèle doit rester stable")
                validate_mapping(edited.hardware_mapping)
                self.catalog.replace_custom(definition.id, replace(edited, verified=False))
                self.reload_models(definition.id)
            except (ValueError, KeyError, TypeError) as exc:
                QMessageBox.warning(self, "Définition invalide", str(exc))

    def delete(self):
        model_id = self.model.currentData()
        self.catalog.remove_custom(model_id)
        for preferences in self.settings.device_preferences.values():
            if preferences.get("model_id") == model_id:
                preferences.pop("model_id")
        self.reload_models()

    def add_mapping(self):
        text, ok = QInputDialog.getMultiLineText(self, "Mapping personnalisé", "JSON : entrée logique → bN, aN, +/-aN, hN.M",
                                                json.dumps(self.settings.controller_mappings.get(self.device.currentData(), {}), indent=2))
        if ok and self.device.currentData():
            try:
                self.settings.controller_mappings[self.device.currentData()] = validate_mapping(json.loads(text))
                self.refresh()
            except (ValueError, TypeError, AttributeError) as exc:
                QMessageBox.warning(self, "Mapping invalide", str(exc))

    def calibrate(self):
        key = self.device.currentData()
        if self.manager is None or key not in self.manager.joysticks:
            QMessageBox.warning(self, "Calibration", "Connectez la manette à calibrer.")
            return
        self.manager.begin_input_capture()
        try:
            dialog = CalibrationDialog(self.manager.joysticks[key], self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.settings.controller_mappings.setdefault(key, {}).update(dialog.calibration.mapping)
                self.refresh()
        finally:
            self.manager.end_input_capture()

    def choose_svg(self):
        names = sorted(path.name for path in ASSET_DIR.glob("*.svg"))
        selected, ok = QInputDialog.getItem(self, "Illustration", "SVG disponible", names, 0, False)
        if ok and self.device.currentData():
            self.preferences()["svg"] = "asset:" + selected
            self.refresh()

    def import_svg(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Importer une illustration", "", "SVG (*.svg)")
        if filename and self.device.currentData():
            path = Path(filename)
            if path.stat().st_size > 4_000_000 or not QSvgRenderer(filename).isValid():
                QMessageBox.warning(self, "SVG invalide", "Le fichier doit être un SVG valide de moins de 4 Mo.")
                return
            target = DATA_DIR / "illustrations" / (uuid4().hex + ".svg")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())
            self.preferences()["svg"] = "user:" + target.name
            self.refresh()

    def restore_svg(self):
        self.preferences().pop("svg", None)
        self.refresh()
