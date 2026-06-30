from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import replace
from pathlib import Path

from bolt_database import (
    DATABASE_PATH,
    connect,
    get_ctp_screw_record,
    get_friction_factor,
    get_material_yield,
    list_ctp_screw_types,
    list_ctp_sizes,
    list_friction_presets,
    list_material_codes,
)
from coupling_calculations import (
    CTP_CHECKING_STANDARD_NAMES,
    CTP_DEFAULT_CHECKING_STANDARD,
    CTP_DEFAULT_JOINT_TYPE,
    CTP_JOINT_TYPES,
    CtpInputs,
    CtpResult,
    calculate_ctp,
    default_ctp_inputs,
)


SLEEVE_MATERIAL_YIELD_MPA = {
    "N/A": 0.0,
    "GMC 0401 - 245 MPa": 245.0,
    "GMC 0336 - 650 MPa": 650.0,
    "GMC0433 - 800 MPa": 800.0,
}
APP_NAME = "CTP0007 Issue H"


def smoke_test() -> None:
    conn = connect()
    record = get_ctp_screw_record(conn, "1512", "47xx")
    inputs = default_ctp_inputs(record)
    result = calculate_ctp(inputs, record, get_material_yield(conn, inputs.material_code))
    print(f"database={DATABASE_PATH}")
    print(f"reference={inputs.reference}")
    print(f"screw={record.screw_type} {record.size}")
    print(f"preload_n={result.axial_pretension_n:.3f}")
    print(f"flange_friction_torque_nm={result.flange_friction_torque_nm:.3f}")
    print(f"minimum_safety_factor={result.minimum_safety_factor:.3f}")


def run_gui() -> int:
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QAction, QKeySequence
        from PySide6.QtWidgets import (
            QApplication,
            QAbstractItemView,
            QCheckBox,
            QComboBox,
            QDoubleSpinBox,
            QFormLayout,
            QFrame,
            QGridLayout,
            QGroupBox,
            QHeaderView,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QMainWindow,
            QMessageBox,
            QInputDialog,
            QFileDialog,
            QPushButton,
            QScrollArea,
            QSplitter,
            QSpinBox,
            QTableWidget,
            QTableWidgetItem,
            QVBoxLayout,
            QWidget,
        )
    except ModuleNotFoundError:
        print("PySide6 is required for the native GUI.")
        print("Install it with:")
        print("  python -m pip install -r requirements-desktop.txt")
        return 2

    class NoWheelDoubleSpinBox(QDoubleSpinBox):
        def wheelEvent(self, event) -> None:
            event.ignore()

    class NoWheelSpinBox(QSpinBox):
        def wheelEvent(self, event) -> None:
            event.ignore()

    class NoWheelComboBox(QComboBox):
        def wheelEvent(self, event) -> None:
            event.ignore()

    class MainWindow(QMainWindow):
        def __init__(self) -> None:
            super().__init__()
            self.conn = connect()
            self._updating_sizes = False
            self._last_output_table = None
            self._project_path: Path | None = None
            self._applying_state = True
            self._undo_stack: list[dict] = []
            self._redo_stack: list[dict] = []
            self._last_state: dict | None = None
            self.setWindowTitle(APP_NAME)
            self.resize(1280, 820)
            self._build_actions()
            self._build_ui()
            self._sync_size_list()
            self._load_record_defaults()
            self.update_calculation()
            self._applying_state = False
            self._last_state = self._project_state()
            self._update_action_state()

        def _build_actions(self) -> None:
            file_menu = self.menuBar().addMenu("&File")
            self.open_action = QAction("Open", self)
            self.open_action.setShortcut(QKeySequence.StandardKey.Open)
            self.open_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
            self.open_action.triggered.connect(self._open_project)
            file_menu.addAction(self.open_action)

            self.save_action = QAction("Save", self)
            self.save_action.setShortcut(QKeySequence.StandardKey.Save)
            self.save_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
            self.save_action.triggered.connect(self._save_project)
            file_menu.addAction(self.save_action)

            self.save_as_action = QAction("Save As", self)
            self.save_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
            self.save_as_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
            self.save_as_action.triggered.connect(self._save_project_as)
            file_menu.addAction(self.save_as_action)

            edit_menu = self.menuBar().addMenu("&Edit")
            self.undo_action = QAction("Undo", self)
            self.undo_action.setShortcut(QKeySequence.StandardKey.Undo)
            self.undo_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
            self.undo_action.triggered.connect(self._undo)
            edit_menu.addAction(self.undo_action)

            self.redo_action = QAction("Redo", self)
            self.redo_action.setShortcut(QKeySequence.StandardKey.Redo)
            self.redo_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
            self.redo_action.triggered.connect(self._redo)
            edit_menu.addAction(self.redo_action)

        def _update_action_state(self) -> None:
            if hasattr(self, "undo_action"):
                self.undo_action.setEnabled(bool(self._undo_stack))
                self.redo_action.setEnabled(bool(self._redo_stack))

        def _build_ui(self) -> None:
            root = QWidget()
            self.setCentralWidget(root)
            layout = QGridLayout(root)
            layout.setContentsMargins(12, 12, 12, 12)
            layout.setHorizontalSpacing(12)
            layout.addWidget(self._build_inputs(), 0, 0)
            layout.addWidget(self._build_results(), 0, 1)
            layout.setColumnStretch(1, 1)

        def _build_inputs(self) -> QWidget:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFixedWidth(430)
            scroll.setObjectName("inputRail")
            scroll.viewport().setObjectName("inputViewport")
            body = QWidget()
            body.setObjectName("inputBody")
            layout = QVBoxLayout(body)
            title = QLabel(APP_NAME)
            title.setObjectName("railTitle")
            layout.addWidget(title)

            self.reference = QLineEdit("TSKW/0360/KA/GA253480 Hub Bolts")
            self.screw_type = NoWheelComboBox()
            self.screw_type.addItems(list_ctp_screw_types(self.conn))
            self.screw_type.setCurrentText("1512")
            self.size = NoWheelComboBox()
            self.material = NoWheelComboBox()
            self.material.addItems(list_material_codes(self.conn))
            self.material.setCurrentText("0225 (Classe 12-9)")
            self.manual_yield = self._double(get_material_yield(self.conn, self.material.currentText()), 0, 3000, 1)
            self.pcd = self._double(447, 0.1, 100000, 1)
            self.screw_count = self._spin(10, 1, 500)
            self.thread = self._double(14, 0.1, 500, 3)
            self.pitch = self._double(2, 0.01, 50, 3)
            self.shank = self._double(8, 0, 500, 3)
            self.groove = self._optional_diameter_combo(10, 0, 500, 3)
            self.contact = self._double(18, 0.1, 1000, 3)
            self.thread_type = NoWheelComboBox()
            self.thread_type.addItems(["Machined", "Rolled"])
            self.shear_plane = NoWheelComboBox()
            self.shear_plane.addItems(["Thread", "Shank"])
            self.joint_type = NoWheelComboBox()
            self.joint_type.addItems(list(CTP_JOINT_TYPES))
            self.joint_type.setCurrentText(CTP_DEFAULT_JOINT_TYPE)
            self.pack_thickness = self._optional_diameter_combo(0, 0, 1000, 3)
            self.leverarm = self._double(0.05, 0, 1000, 3)
            self.leverarm.setReadOnly(True)
            self.nut_contact_mode = NoWheelComboBox()
            self.nut_contact_mode.addItems(["Standard", "Special"])
            self.custom_contact = self._optional_diameter_combo(0, 0, 1000, 3)
            self.sleeve_od = self._optional_diameter_combo(0, 0, 1000, 3)
            self.sleeve_material = NoWheelComboBox()
            self.sleeve_material.addItems(list(SLEEVE_MATERIAL_YIELD_MPA))
            self.sleeve_material.setCurrentText("N/A")
            self.sleeve_yield = self._double(SLEEVE_MATERIAL_YIELD_MPA[self.sleeve_material.currentText()], 0, 3000, 1)
            self.sleeve_yield.setReadOnly(True)
            self.tapped_hole_yield = self._optional_diameter_combo(0, 0, 3000, 1)

            friction_names = list_friction_presets(self.conn)
            self.screw_nut_preset = self._preset_combo(friction_names, "Emuge+Oil")
            self.nut_part_preset = self._preset_combo(friction_names, "Light Oil")
            self.part_part_preset = self._preset_combo(friction_names, "API 671")
            self.screw_nut_mu = self._double(0.155, 0.001, 2, 3)
            self.nut_part_mu = self._double(0.12, 0.001, 2, 3)
            self.part_part_mu = self._double(0.15, 0.001, 2, 3)
            self.continuous_torque = self._double(40100, 0, 10000000, 1)
            self.peak_torque = self._double(80200, 0, 10000000, 1)
            self.momentary_torque = self._double(92230, 0, 10000000, 1)
            self.tightening_torque = self._blank_zero_double(0, 0, 1000000, 1)
            self.percent_tys = self._blank_zero_double(0, 0, 100, 2)
            self.use_standard_torque = QCheckBox("Use standard tightening torque")
            self.use_standard_torque.setChecked(True)
            self.thread_engagement = self._double(0, 0, 10000, 3)

            self._add_group(
                layout,
                "Reference and Screw",
                [
                    ("Reference", self.reference),
                    ("Type", self.screw_type),
                    ("Size", self.size),
                    ("Material", self.material),
                    ("TYS MPa", self.manual_yield),
                ],
            )
            self._add_group(
                layout,
                "Joint Geometry",
                [
                    ("PCD mm", self.pcd),
                    ("Screw count", self.screw_count),
                    ("Thread mm", self.thread),
                    ("Pitch mm", self.pitch),
                    ("Shank dia mm", self.shank),
                    ("Groove dia mm", self.groove),
                    ("Contact dia mm", self.contact),
                    ("Nut contact", self.nut_contact_mode),
                    ("Special contact dia", self.custom_contact),
                    ("Thread type", self.thread_type),
                    ("Shear plane", self.shear_plane),
                    ("Joint type", self.joint_type),
                    ("Pack thickness mm", self.pack_thickness),
                    ("Sleeve OD mm", self.sleeve_od),
                    ("Sleeve material", self.sleeve_material),
                    ("Sleeve yield MPa", self.sleeve_yield),
                    ("Tapped hole yield MPa", self.tapped_hole_yield),
                    ("Thread engagement mm", self.thread_engagement),
                ],
            )
            self._add_group(
                layout,
                "Friction and Torque",
                [
                    ("Screw/nut preset", self.screw_nut_preset),
                    ("Screw/nut mu", self.screw_nut_mu),
                    ("Nut/part preset", self.nut_part_preset),
                    ("Nut/part mu", self.nut_part_mu),
                    ("Part/part preset", self.part_part_preset),
                    ("Part/part mu", self.part_part_mu),
                    ("Continuous Nm", self.continuous_torque),
                    ("Peak Nm", self.peak_torque),
                    ("Momentary Nm", self.momentary_torque),
                    ("Tightening Nm", self.tightening_torque),
                    ("% TYS", self.percent_tys),
                    ("Standard torque", self.use_standard_torque),
                ],
            )
            layout.addStretch(1)
            scroll.setWidget(body)

            self.screw_type.currentTextChanged.connect(self._sync_size_list)
            self.size.currentTextChanged.connect(self._load_record_defaults)
            self.material.currentTextChanged.connect(self._load_material_yield)
            self.joint_type.currentTextChanged.connect(self._sync_joint_geometry)
            self.pack_thickness.currentTextChanged.connect(self._sync_joint_geometry)
            self.nut_contact_mode.currentTextChanged.connect(self._sync_nut_contact)
            self.sleeve_od.currentTextChanged.connect(self._sync_sleeve_fields)
            self.sleeve_material.currentTextChanged.connect(self._load_sleeve_yield)
            for preset in [self.screw_nut_preset, self.nut_part_preset, self.part_part_preset]:
                preset.currentTextChanged.connect(self._apply_friction_presets)
            for widget in self._all_input_widgets():
                if isinstance(widget, QComboBox):
                    widget.currentTextChanged.connect(self._input_changed)
                elif isinstance(widget, QCheckBox):
                    widget.stateChanged.connect(self._input_changed)
                elif isinstance(widget, QLineEdit):
                    widget.textChanged.connect(self._input_changed)
                else:
                    widget.valueChanged.connect(self._input_changed)
            return scroll

        def _build_results(self) -> QWidget:
            frame = QFrame()
            frame.setObjectName("results")
            layout = QVBoxLayout(frame)
            top = QHBoxLayout()
            headings = QVBoxLayout()
            title = QLabel("Bolted Joint Calculation")
            title.setObjectName("title")
            self.spec = QLabel("")
            self.spec.setObjectName("spec")
            headings.addWidget(title)
            headings.addWidget(self.spec)
            self.criteria_standard = NoWheelComboBox()
            self.criteria_standard.addItems(list(CTP_CHECKING_STANDARD_NAMES))
            self.criteria_standard.setCurrentText(CTP_DEFAULT_CHECKING_STANDARD)
            self.goal_seek_button = QPushButton("Goal Seek")
            self.goal_seek_button.setObjectName("goalSeek")
            self.status = QLabel("OK")
            self.status.setObjectName("status")
            top.addLayout(headings)
            top.addWidget(self.goal_seek_button)
            top.addWidget(self.criteria_standard)
            top.addWidget(self.status)
            layout.addLayout(top)
            tables = QSplitter(Qt.Orientation.Vertical)
            tables.setChildrenCollapsible(False)

            self.summary = QTableWidget(7, 2)
            self.summary.setHorizontalHeaderLabels(["Item", "Value"])
            self._prepare_table(self.summary)
            tables.addWidget(self._wrapped_table("Screw Data Summary", self.summary))

            self.capability = QTableWidget(3, 9)
            self.capability.setHorizontalHeaderLabels(
                [
                    "Case",
                    "Duty Nm",
                    "Friction Nm",
                    "Ratio %",
                    "Residual Nm",
                    "Shear N",
                    "Sleeve SF",
                    "Maxi Stress (VM) MPa",
                    "Bolt SF",
                ]
            )
            self._prepare_table(self.capability)
            tables.addWidget(self._wrapped_table("Bolted Joint Capability", self.capability))

            self.stresses = QTableWidget(4, 3)
            self.stresses.setHorizontalHeaderLabels(["Check", "Value", "Status"])
            self._prepare_table(self.stresses)
            tables.addWidget(self._wrapped_table("Stresses and Checks", self.stresses))
            for table in (self.summary, self.capability, self.stresses):
                table.itemSelectionChanged.connect(
                    lambda table=table: self._remember_output_table(table)
                )

            checks_group = QGroupBox("Warnings")
            checks_layout = QVBoxLayout(checks_group)
            self.checks = QLabel("")
            self.checks.setWordWrap(True)
            checks_layout.addWidget(self.checks)
            tables.addWidget(checks_group)
            tables.setSizes([210, 165, 145, 90])
            layout.addWidget(tables, 1)
            self.goal_seek_button.clicked.connect(self._open_goal_seek)
            self.criteria_standard.currentTextChanged.connect(self._input_changed)
            return frame

        def _add_group(self, parent: QVBoxLayout, title: str, rows: list[tuple[str, QWidget]]) -> None:
            group = QGroupBox(title)
            form = QFormLayout(group)
            form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
            for label, widget in rows:
                form.addRow(QLabel(label), widget)
            parent.addWidget(group)

        def _preset_combo(self, names: list[str], current: str) -> QComboBox:
            combo = NoWheelComboBox()
            combo.addItems(names)
            combo.setCurrentText(current)
            return combo

        def _double(self, value: float, minimum: float, maximum: float, decimals: int) -> QDoubleSpinBox:
            box = NoWheelDoubleSpinBox()
            box.setRange(minimum, maximum)
            box.setDecimals(decimals)
            box.setSingleStep(10 ** -decimals if decimals else 100)
            box.setValue(value)
            box.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
            return box

        def _blank_zero_double(
            self,
            value: float,
            minimum: float,
            maximum: float,
            decimals: int,
        ) -> QDoubleSpinBox:
            box = self._double(value, minimum, maximum, decimals)
            box.setSpecialValueText(" ")
            return box

        def _optional_diameter_combo(
            self,
            value: float,
            minimum: float,
            maximum: float,
            decimals: int,
        ) -> QComboBox:
            combo = NoWheelComboBox()
            combo.setEditable(True)
            combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
            combo.addItem("N/A")
            combo.setProperty("minimum", minimum)
            combo.setProperty("maximum", maximum)
            combo.setProperty("decimals", decimals)
            self._set_optional_diameter(combo, value)
            return combo

        def _set_optional_diameter(self, combo: QComboBox, value: float) -> None:
            decimals = int(combo.property("decimals"))
            combo.setCurrentText("N/A" if value <= 0 else f"{value:.{decimals}f}")

        def _optional_diameter_value(self, combo: QComboBox, label: str) -> float:
            text = combo.currentText().strip()
            if not text or text.lower() in {"n/a", "na", "none"}:
                return 0.0
            try:
                value = float(text)
            except ValueError as exc:
                raise ValueError(f"{label} must be N/A or a valid diameter.") from exc
            minimum = float(combo.property("minimum"))
            maximum = float(combo.property("maximum"))
            if value < minimum or value > maximum:
                raise ValueError(f"{label} must be between {minimum:g} and {maximum:g} mm, or N/A.")
            return value

        def _spin(self, value: int, minimum: int, maximum: int) -> QSpinBox:
            box = NoWheelSpinBox()
            box.setRange(minimum, maximum)
            box.setValue(value)
            box.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
            return box

        def _prepare_table(self, table: QTableWidget) -> None:
            table.verticalHeader().setVisible(False)
            table.horizontalHeader().setStretchLastSection(False)
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            table.setAlternatingRowColors(True)
            table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
            table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        def _wrapped_table(self, title: str, table: QTableWidget) -> QGroupBox:
            group = QGroupBox(title)
            layout = QVBoxLayout(group)
            layout.addWidget(table)
            return group

        def _remember_output_table(self, table: QTableWidget) -> None:
            if table.selectedIndexes():
                self._last_output_table = table
                for other in self._output_tables():
                    if other is table:
                        continue
                    other.blockSignals(True)
                    other.clearSelection()
                    other.blockSignals(False)

        def _output_tables(self) -> tuple[QTableWidget, QTableWidget, QTableWidget]:
            return (self.summary, self.capability, self.stresses)

        def _clear_output_selection(self) -> None:
            self._last_output_table = None
            for table in self._output_tables():
                table.blockSignals(True)
                table.clearSelection()
                table.blockSignals(False)

        def _all_input_widgets(self) -> list[QWidget]:
            return [
                self.reference,
                self.screw_type,
                self.size,
                self.material,
                self.manual_yield,
                self.pcd,
                self.screw_count,
                self.thread,
                self.pitch,
                self.shank,
                self.groove,
                self.contact,
                self.thread_type,
                self.shear_plane,
                self.joint_type,
                self.pack_thickness,
                self.nut_contact_mode,
                self.custom_contact,
                self.sleeve_od,
                self.sleeve_material,
                self.sleeve_yield,
                self.tapped_hole_yield,
                self.screw_nut_mu,
                self.nut_part_mu,
                self.part_part_mu,
                self.continuous_torque,
                self.peak_torque,
                self.momentary_torque,
                self.tightening_torque,
                self.percent_tys,
                self.use_standard_torque,
                self.thread_engagement,
            ]

        def _project_widgets(self) -> list[QWidget]:
            return [*self._all_input_widgets(), self.criteria_standard]

        def _project_state(self) -> dict:
            return {
                "reference": self.reference.text(),
                "screw_type": self.screw_type.currentText(),
                "size": self.size.currentText(),
                "material": self.material.currentText(),
                "manual_yield": self.manual_yield.value(),
                "pcd": self.pcd.value(),
                "screw_count": self.screw_count.value(),
                "thread": self.thread.value(),
                "pitch": self.pitch.value(),
                "shank": self.shank.value(),
                "groove": self.groove.currentText(),
                "contact": self.contact.value(),
                "thread_type": self.thread_type.currentText(),
                "shear_plane": self.shear_plane.currentText(),
                "joint_type": self.joint_type.currentText(),
                "pack_thickness": self.pack_thickness.currentText(),
                "nut_contact_mode": self.nut_contact_mode.currentText(),
                "custom_contact": self.custom_contact.currentText(),
                "sleeve_od": self.sleeve_od.currentText(),
                "sleeve_material": self.sleeve_material.currentText(),
                "sleeve_yield": self.sleeve_yield.value(),
                "tapped_hole_yield": self.tapped_hole_yield.currentText(),
                "screw_nut_preset": self.screw_nut_preset.currentText(),
                "nut_part_preset": self.nut_part_preset.currentText(),
                "part_part_preset": self.part_part_preset.currentText(),
                "screw_nut_mu": self.screw_nut_mu.value(),
                "nut_part_mu": self.nut_part_mu.value(),
                "part_part_mu": self.part_part_mu.value(),
                "continuous_torque": self.continuous_torque.value(),
                "peak_torque": self.peak_torque.value(),
                "momentary_torque": self.momentary_torque.value(),
                "tightening_torque": self.tightening_torque.value(),
                "percent_tys": self.percent_tys.value(),
                "use_standard_torque": self.use_standard_torque.isChecked(),
                "thread_engagement": self.thread_engagement.value(),
                "checking_standard": self.criteria_standard.currentText(),
            }

        def _apply_project_state(self, state: dict) -> None:
            self._applying_state = True
            self._set_project_signals_blocked(True)
            try:
                self.reference.setText(str(state.get("reference", "")))
                self._set_combo_text(self.screw_type, state.get("screw_type", "1512"))
                screw_type = self.screw_type.currentText() or "1512"
                self.size.clear()
                self.size.addItems(list_ctp_sizes(self.conn, screw_type))
                self._set_combo_text(self.size, state.get("size", "47xx"))
                self._set_combo_text(self.material, state.get("material", self.material.currentText()))
                self.manual_yield.setValue(float(state.get("manual_yield", self.manual_yield.value())))
                self.pcd.setValue(float(state.get("pcd", self.pcd.value())))
                self.screw_count.setValue(int(state.get("screw_count", self.screw_count.value())))
                self.thread.setValue(float(state.get("thread", self.thread.value())))
                self.pitch.setValue(float(state.get("pitch", self.pitch.value())))
                self.shank.setValue(float(state.get("shank", self.shank.value())))
                self.groove.setCurrentText(str(state.get("groove", self.groove.currentText())))
                self.contact.setValue(float(state.get("contact", self.contact.value())))
                self._set_combo_text(self.thread_type, state.get("thread_type", self.thread_type.currentText()))
                self._set_combo_text(self.shear_plane, state.get("shear_plane", self.shear_plane.currentText()))
                self._set_combo_text(self.joint_type, state.get("joint_type", self.joint_type.currentText()))
                self.pack_thickness.setCurrentText(str(state.get("pack_thickness", self.pack_thickness.currentText())))
                self._set_combo_text(self.nut_contact_mode, state.get("nut_contact_mode", self.nut_contact_mode.currentText()))
                self.custom_contact.setCurrentText(str(state.get("custom_contact", self.custom_contact.currentText())))
                self.sleeve_od.setCurrentText(str(state.get("sleeve_od", self.sleeve_od.currentText())))
                self._set_combo_text(self.sleeve_material, state.get("sleeve_material", self.sleeve_material.currentText()))
                self.sleeve_yield.setValue(float(state.get("sleeve_yield", self.sleeve_yield.value())))
                self.tapped_hole_yield.setCurrentText(str(state.get("tapped_hole_yield", self.tapped_hole_yield.currentText())))
                self._set_combo_text(self.screw_nut_preset, state.get("screw_nut_preset", self.screw_nut_preset.currentText()))
                self._set_combo_text(self.nut_part_preset, state.get("nut_part_preset", self.nut_part_preset.currentText()))
                self._set_combo_text(self.part_part_preset, state.get("part_part_preset", self.part_part_preset.currentText()))
                self.screw_nut_mu.setValue(float(state.get("screw_nut_mu", self.screw_nut_mu.value())))
                self.nut_part_mu.setValue(float(state.get("nut_part_mu", self.nut_part_mu.value())))
                self.part_part_mu.setValue(float(state.get("part_part_mu", self.part_part_mu.value())))
                self.continuous_torque.setValue(float(state.get("continuous_torque", self.continuous_torque.value())))
                self.peak_torque.setValue(float(state.get("peak_torque", self.peak_torque.value())))
                self.momentary_torque.setValue(float(state.get("momentary_torque", self.momentary_torque.value())))
                self.tightening_torque.setValue(float(state.get("tightening_torque", self.tightening_torque.value())))
                self.percent_tys.setValue(float(state.get("percent_tys", self.percent_tys.value())))
                self.use_standard_torque.setChecked(bool(state.get("use_standard_torque", self.use_standard_torque.isChecked())))
                self.thread_engagement.setValue(float(state.get("thread_engagement", self.thread_engagement.value())))
                self._set_combo_text(self.criteria_standard, state.get("checking_standard", self.criteria_standard.currentText()))
            finally:
                self._set_project_signals_blocked(False)
            try:
                self._sync_joint_geometry()
                self._sync_nut_contact()
                self._sync_sleeve_fields()
            finally:
                self._applying_state = False
            self.update_calculation()
            self._last_state = self._project_state()
            self._update_action_state()

        def _set_combo_text(self, combo: QComboBox, value: object) -> None:
            text = str(value)
            index = combo.findText(text)
            if index >= 0:
                combo.setCurrentIndex(index)
            elif combo.isEditable():
                combo.setCurrentText(text)

        def _set_project_signals_blocked(self, blocked: bool) -> None:
            for widget in self._project_widgets():
                widget.blockSignals(blocked)

        def _input_changed(self, *_args) -> None:
            if self._applying_state:
                return
            current = self._project_state()
            if self._last_state is not None and current != self._last_state:
                self._undo_stack.append(self._last_state)
                self._undo_stack = self._undo_stack[-100:]
                self._redo_stack.clear()
                self._last_state = current
            self._update_action_state()
            self.update_calculation()

        def _push_current_state_for_undo(self) -> None:
            if self._applying_state:
                return
            current = self._project_state()
            if not self._undo_stack or self._undo_stack[-1] != current:
                self._undo_stack.append(current)
                self._undo_stack = self._undo_stack[-100:]
            self._redo_stack.clear()
            self._last_state = current
            self._update_action_state()

        def _undo(self) -> None:
            if not self._undo_stack:
                return
            current = self._project_state()
            previous = self._undo_stack.pop()
            if current != previous:
                self._redo_stack.append(current)
            self._apply_project_state(previous)

        def _redo(self) -> None:
            if not self._redo_stack:
                return
            current = self._project_state()
            next_state = self._redo_stack.pop()
            if current != next_state:
                self._undo_stack.append(current)
            self._apply_project_state(next_state)

        def _open_project(self) -> None:
            filename, _selected_filter = QFileDialog.getOpenFileName(
                self,
                "Open Project",
                str(self._default_project_directory()),
                "CTP 0007 Project (*.ctp0007.json);;JSON Files (*.json);;All Files (*)",
            )
            if not filename:
                return
            path = Path(filename)
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                state = payload.get("inputs") if isinstance(payload, dict) else None
                if not isinstance(state, dict):
                    raise ValueError("Project file does not contain saved inputs.")
            except Exception as exc:
                QMessageBox.warning(self, "Open Project", f"Could not open project file:\n{exc}")
                return
            self._push_current_state_for_undo()
            self._project_path = path
            self._apply_project_state(state)
            self._update_window_title()

        def _save_project(self) -> None:
            if self._project_path is None:
                self._save_project_as()
                return
            self._write_project(self._project_path)

        def _save_project_as(self) -> None:
            filename, _selected_filter = QFileDialog.getSaveFileName(
                self,
                "Save Project As",
                str(self._default_project_path()),
                "CTP 0007 Project (*.ctp0007.json);;JSON Files (*.json);;All Files (*)",
            )
            if not filename:
                return
            path = self._with_project_suffix(Path(filename))
            self._write_project(path)

        def _write_project(self, path: Path) -> None:
            payload = {
                "format": APP_NAME,
                "version": 1,
                "inputs": self._project_state(),
            }
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            except Exception as exc:
                QMessageBox.warning(self, "Save Project", f"Could not save project file:\n{exc}")
                return
            self._project_path = path
            self._update_window_title()

        def _default_project_directory(self) -> Path:
            if self._project_path is not None:
                return self._project_path.parent
            return Path.cwd()

        def _default_project_path(self) -> Path:
            return self._default_project_directory() / self._project_filename_from_reference()

        def _project_filename_from_reference(self) -> str:
            name = self.reference.text().strip() or f"{APP_NAME} project"
            name = re.sub(r'[<>:"/\\|?*]+', "_", name)
            name = re.sub(r"\s+", " ", name).strip(" .")
            if not name:
                name = f"{APP_NAME} project"
            return f"{name[:120]}.ctp0007.json"

        def _with_project_suffix(self, path: Path) -> Path:
            name = path.name.lower()
            if name.endswith(".ctp0007.json") or name.endswith(".json"):
                return path
            return path.with_name(f"{path.name}.ctp0007.json")

        def _update_window_title(self) -> None:
            if self._project_path is None:
                self.setWindowTitle(APP_NAME)
            else:
                self.setWindowTitle(f"{APP_NAME} - {self._project_path.name}")

        def _sync_size_list(self) -> None:
            if self._updating_sizes:
                return
            self._updating_sizes = True
            current_type = self.screw_type.currentText() or "1512"
            self.size.clear()
            self.size.addItems(list_ctp_sizes(self.conn, current_type))
            if current_type == "1512":
                self.size.setCurrentText("47xx")
            elif current_type == "SPECIAL":
                self.size.setCurrentText("M16")
            self._updating_sizes = False
            self._load_record_defaults()

        def _load_record_defaults(self) -> None:
            if self._updating_sizes or not self.size.currentText():
                return
            try:
                record = self._record()
            except Exception:
                return
            self.thread.blockSignals(True)
            self.pitch.blockSignals(True)
            self.shank.blockSignals(True)
            self.groove.blockSignals(True)
            self.contact.blockSignals(True)
            self.thread_engagement.blockSignals(True)
            self.thread.setValue(record.thread_mm)
            self.pitch.setValue(record.pitch_mm)
            self.shank.setValue(record.shank_diameter_mm)
            self._set_optional_diameter(self.groove, record.groove_diameter_mm)
            self.contact.setValue(record.contact_diameter_mm)
            self.thread_engagement.setValue(record.thread_mm * 1.2)
            self.thread.blockSignals(False)
            self.pitch.blockSignals(False)
            self.shank.blockSignals(False)
            self.groove.blockSignals(False)
            self.contact.blockSignals(False)
            self.thread_engagement.blockSignals(False)
            self._sync_joint_geometry()
            self._sync_nut_contact()
            self._sync_sleeve_fields()
            self.update_calculation()

        def _load_material_yield(self) -> None:
            self.manual_yield.blockSignals(True)
            self.manual_yield.setValue(get_material_yield(self.conn, self.material.currentText()))
            self.manual_yield.blockSignals(False)
            self.update_calculation()

        def _load_sleeve_yield(self) -> None:
            if self.sleeve_material.currentText() == "N/A":
                return
            self.sleeve_yield.blockSignals(True)
            self.sleeve_yield.setValue(SLEEVE_MATERIAL_YIELD_MPA[self.sleeve_material.currentText()])
            self.sleeve_yield.blockSignals(False)
            self.update_calculation()

        def _sync_sleeve_fields(self) -> None:
            try:
                sleeve_od = self._optional_diameter_value(self.sleeve_od, "Sleeve OD")
            except ValueError:
                sleeve_od = 0.0
            if sleeve_od <= 0:
                self.sleeve_material.blockSignals(True)
                self.sleeve_yield.blockSignals(True)
                self.sleeve_material.setCurrentText("N/A")
                self.sleeve_yield.setValue(0.0)
                self.sleeve_material.blockSignals(False)
                self.sleeve_yield.blockSignals(False)
                self.sleeve_material.setEnabled(False)
                self.sleeve_yield.setEnabled(False)
            else:
                self.sleeve_material.setEnabled(True)
                self.sleeve_yield.setEnabled(True)
                if self.sleeve_material.currentText() == "N/A":
                    self.sleeve_material.blockSignals(True)
                    self.sleeve_material.setCurrentText("GMC 0336 - 650 MPa")
                    self.sleeve_material.blockSignals(False)
                    self.sleeve_yield.blockSignals(True)
                    self.sleeve_yield.setValue(SLEEVE_MATERIAL_YIELD_MPA[self.sleeve_material.currentText()])
                    self.sleeve_yield.blockSignals(False)

        def _sync_joint_geometry(self) -> None:
            joint_type = self.joint_type.currentText()
            if joint_type == "Stripper bolt":
                self.pack_thickness.blockSignals(True)
                self._set_optional_diameter(self.pack_thickness, 0)
                self.pack_thickness.blockSignals(False)
                self.pack_thickness.setEnabled(False)
                leverarm = 0.05
            else:
                self.pack_thickness.setEnabled(True)
                if self.pack_thickness.currentText().strip().lower() in {"n/a", "na", "none"}:
                    self.pack_thickness.blockSignals(True)
                    self.pack_thickness.setCurrentText("")
                    self.pack_thickness.blockSignals(False)
                try:
                    pack_thickness = self._optional_diameter_value(self.pack_thickness, "Pack thickness")
                except ValueError:
                    pack_thickness = 0.0
                leverarm = 0.15 * pack_thickness
            self.leverarm.blockSignals(True)
            self.leverarm.setValue(leverarm)
            self.leverarm.blockSignals(False)

        def _sync_nut_contact(self) -> None:
            self.custom_contact.blockSignals(True)
            if self.nut_contact_mode.currentText() == "Standard":
                self._set_optional_diameter(self.custom_contact, 0)
            elif self.custom_contact.currentText().strip().lower() in {"n/a", "na", "none"}:
                self.custom_contact.setCurrentText("")
            self.custom_contact.blockSignals(False)

        def _apply_friction_presets(self) -> None:
            mapping = [
                (self.screw_nut_preset, self.screw_nut_mu),
                (self.nut_part_preset, self.nut_part_mu),
                (self.part_part_preset, self.part_part_mu),
            ]
            for combo, spin in mapping:
                if combo.currentText() != "Custom":
                    spin.setValue(get_friction_factor(self.conn, combo.currentText()))

        def _record(self):
            return get_ctp_screw_record(
                self.conn,
                self.screw_type.currentText(),
                self.size.currentText(),
            )

        def inputs(self) -> CtpInputs:
            return CtpInputs(
                reference=self.reference.text(),
                screw_type=self.screw_type.currentText(),
                size=self.size.currentText(),
                pcd_mm=self.pcd.value(),
                screw_count=self.screw_count.value(),
                material_code=self.material.currentText(),
                manual_yield_mpa=self.manual_yield.value() or None,
                thread_mm=self.thread.value(),
                pitch_mm=self.pitch.value(),
                shank_diameter_mm=self.shank.value(),
                groove_diameter_mm=self._optional_diameter_value(self.groove, "Groove diameter"),
                contact_diameter_mm=self.contact.value(),
                thread_type=self.thread_type.currentText(),
                screw_nut_friction=self.screw_nut_mu.value(),
                nut_part_friction=self.nut_part_mu.value(),
                part_part_friction=self.part_part_mu.value(),
                continuous_torque_nm=self.continuous_torque.value(),
                peak_torque_nm=self.peak_torque.value(),
                momentary_torque_nm=self.momentary_torque.value(),
                tightening_torque_nm=self.tightening_torque.value(),
                percent_tys=self.percent_tys.value(),
                use_standard_torque=self.use_standard_torque.isChecked(),
                shear_plane=self.shear_plane.currentText(),
                leverarm_mm=self.leverarm.value(),
                joint_type=self.joint_type.currentText(),
                pack_thickness_mm=(
                    0.0
                    if self.joint_type.currentText() == "Stripper bolt"
                    else self._optional_diameter_value(self.pack_thickness, "Pack thickness")
                ),
                nut_contact_mode=self.nut_contact_mode.currentText(),
                custom_nut_contact_diameter_mm=(
                    0.0
                    if self.nut_contact_mode.currentText() == "Standard"
                    else self._optional_diameter_value(self.custom_contact, "Special contact diameter")
                ),
                sleeve_outer_diameter_mm=self._optional_diameter_value(self.sleeve_od, "Sleeve OD"),
                sleeve_yield_mpa=self.sleeve_yield.value(),
                tapped_hole_yield_mpa=self._optional_diameter_value(self.tapped_hole_yield, "Tapped hole yield"),
                thread_engagement_mode="Thread" if self.thread_engagement.value() == 0 else "Manual",
                thread_engagement_mm=self.thread_engagement.value(),
                checking_standard=self.criteria_standard.currentText(),
                screw_nut_friction_source=self.screw_nut_preset.currentText(),
            )

        def _current_result(self) -> tuple[CtpInputs, object, CtpResult]:
            record = self._record()
            inputs = self.inputs()
            result = calculate_ctp(inputs, record, get_material_yield(self.conn, inputs.material_code))
            return inputs, record, result

        def _open_goal_seek(self) -> None:
            try:
                inputs, record, result = self._current_result()
            except Exception as exc:
                QMessageBox.warning(self, "Goal Seek", str(exc))
                return

            selected_output = self._selected_goal_output(result)
            input_options = self._goal_input_options()
            if selected_output is None:
                QMessageBox.warning(
                    self,
                    "Goal Seek",
                    "Select one numeric output value from the result tables first.",
                )
                return
            if not input_options:
                QMessageBox.warning(self, "Goal Seek", "No input parameters are available to change.")
                return

            output_label, getter, current_value = selected_output
            target, accepted = QInputDialog.getDouble(
                self,
                "Goal Seek",
                f"Set target value for:\n{output_label}",
                current_value,
                -1_000_000_000_000.0,
                1_000_000_000_000.0,
                6,
            )
            if not accepted:
                return

            labels = [option["label"] for option in input_options]
            selected_label, accepted = QInputDialog.getItem(
                self,
                "Goal Seek",
                "Change which input parameter?",
                labels,
                0,
                False,
            )
            if not accepted:
                return
            option = input_options[labels.index(selected_label)]

            try:
                solution, achieved, exact = self._solve_goal(
                    inputs,
                    record,
                    option,
                    getter,
                    target,
                    option["minimum"],
                    option["maximum"],
                )
                self._set_goal_input_value(option, solution)
                self.update_calculation()
                self._clear_output_selection()
            except Exception as exc:
                QMessageBox.warning(self, "Goal Seek", str(exc))
                return

            status = "Solved" if exact else "Closest result"
            QMessageBox.information(
                self,
                "Goal Seek",
                f"{status}\n"
                f"{option['label']} = {self._format_goal_number(solution, option)}\n"
                f"{output_label} = {achieved:.6g}",
            )

        def _selected_goal_output(self, result: CtpResult) -> tuple[str, object, float] | None:
            tables = [self._last_output_table, self.summary, self.capability, self.stresses]
            seen: set[int] = set()
            for table in tables:
                if table is None or id(table) in seen:
                    continue
                seen.add(id(table))
                for index in table.selectedIndexes():
                    output = self._goal_output_from_cell(table, index.row(), index.column(), result)
                    if output is not None:
                        return output
            return None

        def _goal_output_from_cell(
            self,
            table: QTableWidget,
            row: int,
            column: int,
            result: CtpResult,
        ) -> tuple[str, object, float] | None:
            if table is self.summary:
                return self._summary_goal_output(row, result)
            if table is self.capability:
                return self._capability_goal_output(row, column, result)
            if table is self.stresses:
                return self._stresses_goal_output(row, result)
            return None

        def _summary_goal_output(self, row: int, result: CtpResult) -> tuple[str, object, float] | None:
            mappings = {
                2: ("Screw Data Summary - Tensile stress area mm2", lambda item: item.tensile_stress_area_mm2),
                3: ("Screw Data Summary - Shear-bending dia mm", lambda item: item.shear_bending_diameter_mm),
                4: ("Screw Data Summary - Contact dia mm", lambda item: item.contact_diameter_mm),
                5: ("Screw Data Summary - Contact radius mm", lambda item: item.contact_diameter_mm / 2.0),
                6: ("Screw Data Summary - Average nut radius mm", lambda item: item.average_nut_radius_mm),
                7: ("Screw Data Summary - Axial pretension N", lambda item: item.axial_pretension_n),
                8: ("Screw Data Summary - Tightening torque Nm", lambda item: item.tightening_torque_nm),
                9: ("Screw Data Summary - Preload % TYS", lambda item: item.preload_percent_tys),
                10: ("Screw Data Summary - Preload % limit", lambda item: item.preload_percent_tys_limit),
            }
            return self._numeric_goal_output(result, mappings.get(row))

        def _capability_goal_output(
            self,
            row: int,
            column: int,
            result: CtpResult,
        ) -> tuple[str, object, float] | None:
            if row < 0 or row >= len(result.torque_cases):
                return None
            case = result.torque_cases[row]
            prefix = f"Bolted Joint Capability - {case.name}"
            mappings = {
                1: (f"{prefix} Duty Nm", lambda item, row=row: item.torque_cases[row].duty_torque_nm),
                2: (f"{prefix} Friction Nm", lambda item, row=row: item.torque_cases[row].friction_torque_nm),
                3: (
                    f"{prefix} Ratio %",
                    lambda item, row=row: (
                        item.torque_cases[row].friction_ratio * 100
                        if isinstance(item.torque_cases[row].friction_ratio, float)
                        else float("nan")
                    ),
                ),
                4: (f"{prefix} Residual Nm", lambda item, row=row: item.torque_cases[row].residual_torque_nm),
                5: (f"{prefix} Shear N", lambda item, row=row: item.torque_cases[row].shear_load_per_joint_n),
                6: (
                    f"{prefix} Sleeve SF",
                    lambda item, row=row: (
                        item.torque_cases[row].sleeve_safety_factor
                        if isinstance(item.torque_cases[row].sleeve_safety_factor, float)
                        else float("nan")
                    ),
                ),
                7: (f"{prefix} Maxi Stress (VM) MPa", lambda item, row=row: item.torque_cases[row].bolt_von_mises_mpa),
                8: (f"{prefix} Bolt SF", lambda item, row=row: item.torque_cases[row].bolt_safety_factor),
            }
            return self._numeric_goal_output(result, mappings.get(column))

        def _stresses_goal_output(self, row: int, result: CtpResult) -> tuple[str, object, float] | None:
            mappings = {
                0: (
                    "Stresses and Checks - Groove assembly SF",
                    lambda item: item.groove_safety_factor if isinstance(item.groove_safety_factor, float) else float("nan"),
                ),
                1: ("Stresses and Checks - Thread-root assembly SF", lambda item: item.thread_root_safety_factor),
                2: ("Stresses and Checks - Thread pull-out stress MPa", lambda item: item.thread_pullout_stress_mpa),
                3: ("Stresses and Checks - Minimum safety factor", lambda item: item.minimum_safety_factor),
            }
            return self._numeric_goal_output(result, mappings.get(row))

        def _numeric_goal_output(
            self,
            result: CtpResult,
            mapping: tuple[str, object] | None,
        ) -> tuple[str, object, float] | None:
            if mapping is None:
                return None
            label, getter = mapping
            try:
                value = getter(result)
            except Exception:
                return None
            if isinstance(value, (int, float)) and math.isfinite(float(value)):
                return label, getter, float(value)
            return None

        def _goal_input_options(self) -> list[dict]:
            options: list[dict] = []

            def add_widget(label: str, field: str, widget) -> None:
                if not widget.isEnabled():
                    return
                kind = "int" if isinstance(widget, QSpinBox) else "float"
                decimals = 0 if kind == "int" else widget.decimals()
                options.append(
                    {
                        "label": label,
                        "field": field,
                        "widget": widget,
                        "kind": kind,
                        "current": float(widget.value()),
                        "minimum": float(widget.minimum()),
                        "maximum": float(widget.maximum()),
                        "decimals": decimals,
                    }
                )

            def add_optional(label: str, field: str, widget: QComboBox) -> None:
                if not widget.isEnabled():
                    return
                try:
                    current = self._optional_diameter_value(widget, label)
                except ValueError:
                    current = 0.0
                options.append(
                    {
                        "label": label,
                        "field": field,
                        "widget": widget,
                        "kind": "optional",
                        "current": current,
                        "minimum": float(widget.property("minimum")),
                        "maximum": float(widget.property("maximum")),
                        "decimals": int(widget.property("decimals")),
                    }
                )

            add_widget("TYS MPa", "manual_yield_mpa", self.manual_yield)
            add_widget("PCD mm", "pcd_mm", self.pcd)
            add_widget("Screw count", "screw_count", self.screw_count)
            if self.screw_type.currentText() == "SPECIAL":
                add_widget("Thread mm", "thread_mm", self.thread)
                add_widget("Pitch mm", "pitch_mm", self.pitch)
                add_widget("Shank dia mm", "shank_diameter_mm", self.shank)
                add_widget("Contact dia mm", "contact_diameter_mm", self.contact)
            add_optional("Groove dia mm", "groove_diameter_mm", self.groove)
            if self.joint_type.currentText() != "Stripper bolt":
                add_optional("Pack thickness mm", "pack_thickness_mm", self.pack_thickness)
            if self.nut_contact_mode.currentText() == "Special":
                add_optional("Special contact dia", "custom_nut_contact_diameter_mm", self.custom_contact)
            add_optional("Sleeve OD mm", "sleeve_outer_diameter_mm", self.sleeve_od)
            add_widget("Sleeve yield MPa", "sleeve_yield_mpa", self.sleeve_yield)
            add_widget("Thread engagement mm", "thread_engagement_mm", self.thread_engagement)
            add_widget("Screw/nut mu", "screw_nut_friction", self.screw_nut_mu)
            add_widget("Nut/part mu", "nut_part_friction", self.nut_part_mu)
            add_widget("Part/part mu", "part_part_friction", self.part_part_mu)
            add_widget("Continuous Nm", "continuous_torque_nm", self.continuous_torque)
            add_widget("Peak Nm", "peak_torque_nm", self.peak_torque)
            add_widget("Momentary Nm", "momentary_torque_nm", self.momentary_torque)
            add_widget("Tightening Nm", "tightening_torque_nm", self.tightening_torque)
            add_widget("% TYS", "percent_tys", self.percent_tys)
            return options

        def _solve_goal(
            self,
            base_inputs: CtpInputs,
            record,
            option: dict,
            getter,
            target: float,
            lower: float,
            upper: float,
        ) -> tuple[float, float, bool]:
            if lower > upper:
                lower, upper = upper, lower
            if option["kind"] == "int":
                return self._solve_integer_goal(base_inputs, record, option, getter, target, lower, upper)
            return self._solve_float_goal(base_inputs, record, option, getter, target, lower, upper)

        def _solve_integer_goal(
            self,
            base_inputs: CtpInputs,
            record,
            option: dict,
            getter,
            target: float,
            lower: float,
            upper: float,
        ) -> tuple[float, float, bool]:
            lower_int = math.ceil(lower)
            upper_int = math.floor(upper)
            if lower_int > upper_int:
                raise ValueError("Selected range does not contain an integer value.")
            span = upper_int - lower_int
            if span <= 20000:
                candidates = range(lower_int, upper_int + 1)
            else:
                sampled = {
                    int(round(lower_int + span * index / 500))
                    for index in range(501)
                }
                sampled.add(int(round(option["current"])))
                candidates = sorted(value for value in sampled if lower_int <= value <= upper_int)

            tolerance = self._goal_tolerance(target)
            best: tuple[float, float, float] | None = None
            for candidate in candidates:
                try:
                    residual, achieved = self._goal_residual(
                        base_inputs,
                        record,
                        option,
                        getter,
                        float(candidate),
                        target,
                    )
                except Exception:
                    continue
                score = abs(residual)
                if best is None or score < best[0]:
                    best = (score, float(candidate), achieved)
                if score <= tolerance:
                    return float(candidate), achieved, True
            if best is None:
                raise ValueError("No valid calculation in the selected input range.")
            return best[1], best[2], False

        def _solve_float_goal(
            self,
            base_inputs: CtpInputs,
            record,
            option: dict,
            getter,
            target: float,
            lower: float,
            upper: float,
        ) -> tuple[float, float, bool]:
            if math.isclose(lower, upper):
                raise ValueError("Lower and upper bounds must be different.")
            tolerance = self._goal_tolerance(target)
            points = [lower + (upper - lower) * index / 80 for index in range(81)]
            if lower <= option["current"] <= upper:
                points.append(option["current"])
            points = sorted({round(point, 12) for point in points})
            best: tuple[float, float, float] | None = None
            bracket: tuple[float, float, float, float] | None = None
            previous: tuple[float, float] | None = None

            for point in points:
                try:
                    residual, achieved = self._goal_residual(base_inputs, record, option, getter, point, target)
                except Exception:
                    continue
                score = abs(residual)
                if best is None or score < best[0]:
                    best = (score, point, achieved)
                if score <= tolerance:
                    return point, achieved, True
                if previous is not None and previous[1] * residual <= 0:
                    bracket = (previous[0], point, previous[1], residual)
                    break
                previous = (point, residual)

            if bracket is None:
                if best is None:
                    raise ValueError("No valid calculation in the selected input range.")
                return best[1], best[2], False

            low, high, low_residual, _high_residual = bracket
            for _iteration in range(80):
                middle = (low + high) / 2.0
                residual, achieved = self._goal_residual(base_inputs, record, option, getter, middle, target)
                score = abs(residual)
                if best is None or score < best[0]:
                    best = (score, middle, achieved)
                if score <= tolerance:
                    return middle, achieved, True
                if low_residual * residual <= 0:
                    high = middle
                else:
                    low = middle
                    low_residual = residual

            if best is None:
                raise ValueError("No valid calculation in the selected input range.")
            return best[1], best[2], best[0] <= tolerance

        def _goal_residual(
            self,
            base_inputs: CtpInputs,
            record,
            option: dict,
            getter,
            value: float,
            target: float,
        ) -> tuple[float, float]:
            inputs = self._goal_inputs_with_value(base_inputs, option["field"], value)
            result = calculate_ctp(inputs, record, get_material_yield(self.conn, inputs.material_code))
            achieved = getter(result)
            if not isinstance(achieved, (int, float)) or not math.isfinite(float(achieved)):
                raise ValueError("Selected result is not numeric for this input value.")
            achieved = float(achieved)
            return achieved - target, achieved

        def _goal_inputs_with_value(self, base_inputs: CtpInputs, field: str, value: float) -> CtpInputs:
            if field == "screw_count":
                value = int(round(value))
            updates = {field: value}
            if field == "manual_yield_mpa" and value <= 0:
                updates[field] = None
            if field == "tightening_torque_nm":
                updates["percent_tys"] = 0.0
            elif field == "percent_tys":
                updates["tightening_torque_nm"] = 0.0
                updates["use_standard_torque"] = False
            elif field == "thread_engagement_mm":
                updates["thread_engagement_mode"] = "Thread" if value <= 0 else "Manual"
            return replace(base_inputs, **updates)

        def _set_goal_input_value(self, option: dict, value: float) -> None:
            self._push_current_state_for_undo()
            field = option["field"]
            if field == "tightening_torque_nm":
                self.percent_tys.blockSignals(True)
                self.percent_tys.setValue(0.0)
                self.percent_tys.blockSignals(False)
            elif field == "percent_tys":
                self.tightening_torque.blockSignals(True)
                self.tightening_torque.setValue(0.0)
                self.tightening_torque.blockSignals(False)
                self.use_standard_torque.blockSignals(True)
                self.use_standard_torque.setChecked(False)
                self.use_standard_torque.blockSignals(False)

            widget = option["widget"]
            widget.blockSignals(True)
            if option["kind"] == "optional":
                self._set_optional_diameter(widget, value)
            elif option["kind"] == "int":
                widget.setValue(int(round(value)))
            else:
                widget.setValue(value)
            widget.blockSignals(False)

            if field == "pack_thickness_mm":
                self._sync_joint_geometry()
            elif field == "sleeve_outer_diameter_mm":
                self._sync_sleeve_fields()
            elif field == "custom_nut_contact_diameter_mm":
                self._sync_nut_contact()
            self._last_state = self._project_state()
            self._update_action_state()

        def _format_goal_number(self, value: float, option: dict) -> str:
            if option["kind"] == "int":
                return str(int(round(value)))
            decimals = min(max(int(option.get("decimals", 6)), 0), 6)
            text = f"{value:.{decimals}f}"
            return text.rstrip("0").rstrip(".") if "." in text else text

        def _goal_tolerance(self, target: float) -> float:
            return max(1e-6, abs(target) * 1e-7)

        def update_calculation(self) -> None:
            try:
                inputs, record, result = self._current_result()
            except Exception as exc:
                if hasattr(self, "checks"):
                    self.checks.setText(str(exc))
                return
            self._render_result(inputs, record, result)

        def _render_result(self, inputs: CtpInputs, record, result: CtpResult) -> None:
            self.spec.setText(
                f"{inputs.reference} | Type {record.screw_type} size {record.size} | "
                f"yield {result.tensile_yield_mpa:g} MPa"
            )
            ok = result.warnings == ("All current checks pass.",)
            self.status.setText("OK" if ok else "Check")
            self.status.setProperty("warning", not ok)
            self.status.style().unpolish(self.status)
            self.status.style().polish(self.status)
            self._fill_summary(result)
            self._fill_capability(result)
            self._fill_stresses(result)
            self.checks.setText("\n".join(f"- {item}" for item in result.warnings))

        def _set_item(
            self,
            table: QTableWidget,
            row: int,
            column: int,
            text: str,
            selectable: bool = False,
        ) -> None:
            item = QTableWidgetItem(text)
            item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            flags = Qt.ItemFlag.ItemIsEnabled
            if selectable:
                flags |= Qt.ItemFlag.ItemIsSelectable
            item.setFlags(flags)
            table.setItem(row, column, item)

        def _fill_summary(self, result: CtpResult) -> None:
            rows = [
                ("Thread / pitch", f"M{result.thread_major_diameter_mm:g} x {result.pitch_mm:g}"),
                ("Pitch / root dia", f"{result.pitch_diameter_mm:.3f} / {result.thread_root_diameter_mm:.3f} mm"),
                ("Tensile stress area", f"{result.tensile_stress_area_mm2:.3f} mm2"),
                ("Shear-bending dia", f"{result.shear_bending_diameter_mm:.3f} mm"),
                ("Contact dia", f"{result.contact_diameter_mm:.3f} mm"),
                ("Contact radius", f"{result.contact_diameter_mm / 2.0:.3f} mm"),
                ("Average nut radius", f"{result.average_nut_radius_mm:.3f} mm"),
                ("Axial pretension", f"{result.axial_pretension_n:,.0f} N"),
                ("Tightening torque", f"{result.tightening_torque_nm:,.1f} Nm"),
                ("Preload % TYS", f"{result.preload_percent_tys:.2f}%"),
                ("Preload % limit", f"{result.preload_percent_tys_limit:.0f}%"),
                ("Joint type / Leff", f"{result.joint_type} / {result.leverarm_mm:.3f} mm"),
            ]
            selectable_rows = {2, 3, 4, 5, 6, 7, 8, 9, 10}
            self.summary.setRowCount(len(rows))
            for row, (name, value) in enumerate(rows):
                self._set_item(self.summary, row, 0, name)
                self._set_item(self.summary, row, 1, value, row in selectable_rows)
            self.summary.resizeColumnsToContents()
            self.summary.resizeRowsToContents()

        def _fill_capability(self, result: CtpResult) -> None:
            self.capability.setRowCount(len(result.torque_cases))
            for row, case in enumerate(result.torque_cases):
                values = [
                    case.name,
                    f"{case.duty_torque_nm:,.0f}",
                    f"{case.friction_torque_nm:,.0f}",
                    f"{case.friction_ratio * 100:.1f}%" if isinstance(case.friction_ratio, float) else case.friction_ratio,
                    f"{case.residual_torque_nm:,.0f}",
                    f"{case.shear_load_per_joint_n:,.0f}",
                    _format_sf(case.sleeve_safety_factor),
                    f"{case.bolt_von_mises_mpa:.1f}",
                    f"{case.bolt_safety_factor:.3f}",
                ]
                for column, value in enumerate(values):
                    selectable = column != 0
                    if column == 3 and not isinstance(case.friction_ratio, float):
                        selectable = False
                    if column == 6 and not isinstance(case.sleeve_safety_factor, float):
                        selectable = False
                    self._set_item(self.capability, row, column, value, selectable)
            self.capability.resizeColumnsToContents()
            self.capability.resizeRowsToContents()

        def _fill_stresses(self, result: CtpResult) -> None:
            rows = [
                (
                    f"Groove assembly SF (>={result.groove_yield_sf_limit:.2f})",
                    _format_sf(result.groove_safety_factor),
                    _status(result.groove_safety_factor, result.groove_yield_sf_limit),
                ),
                (
                    f"Thread-root assembly SF (>={result.thread_root_required_sf_limit:.2f}, {result.thread_root_preferred_sf_limit:.2f} pref)",
                    f"{result.thread_root_safety_factor:.3f}",
                    _thread_root_status(result),
                ),
                (
                    "Thread pull-out stress",
                    f"{result.thread_pullout_stress_mpa:.1f} MPa",
                    _tapped_hole_status(result),
                ),
                ("Minimum safety factor", f"{result.minimum_safety_factor:.3f}", "Info"),
            ]
            self.stresses.setRowCount(len(rows))
            for row, values in enumerate(rows):
                for column, value in enumerate(values):
                    selectable = column == 1 and self._stresses_goal_output(row, result) is not None
                    self._set_item(self.stresses, row, column, value, selectable)
            self.stresses.resizeColumnsToContents()
            self.stresses.resizeRowsToContents()

    def _format_sf(value: float | str) -> str:
        return f"{value:.3f}" if isinstance(value, float) else value

    def _status(value: float | str, limit: float) -> str:
        if not isinstance(value, float):
            return "N/A"
        return "Pass" if value >= limit else "Check"

    def _thread_root_status(result: CtpResult) -> str:
        if result.thread_root_safety_factor < result.thread_root_required_sf_limit:
            return "Check"
        if result.thread_root_safety_factor < result.thread_root_preferred_sf_limit:
            return "Preferred"
        return "Pass"

    def _tapped_hole_status(result: CtpResult) -> str:
        if result.tapped_hole_yield_mpa <= 0:
            return "Tapped hole yield must exceed this"
        return "Pass" if result.tapped_hole_yield_mpa >= result.thread_pullout_stress_mpa else "Check"

    app = QApplication(sys.argv)
    app.setStyleSheet(
        """
        QWidget { background: #eef2f4; color: #172126; font-family: Arial; }
        QScrollArea#inputRail { background: #20272c; border: 1px solid #344047; border-radius: 6px; }
        QScrollArea#inputRail > QWidget, #inputViewport, #inputBody { background: #20272c; }
        #railTitle { background: #20272c; color: #f7fbfc; font-size: 21px; font-weight: 850; padding: 10px 4px 8px; }
        QGroupBox { background: #f8fafb; border: 1px solid #c7d2d8; border-radius: 6px; margin-top: 12px; font-weight: 800; }
        QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
        #inputRail QGroupBox { background: #263039; border-color: #47545d; color: #f7fbfc; }
        #inputRail QGroupBox::title { background: #20272c; color: #f7fbfc; padding: 0 6px; }
        #inputRail QLabel { background: transparent; color: #f7fbfc; font-weight: 700; }
        QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox {
            background: white; color: #172126; border: 1px solid #9fb0b8; border-radius: 5px; min-height: 26px; padding: 0 7px;
        }
        QCheckBox { background: transparent; color: #172126; font-weight: 700; }
        #inputRail QCheckBox { color: #f7fbfc; }
        #results { background: #fbfcfd; border: 1px solid #c7d2d8; border-radius: 6px; }
        #title { background: transparent; color: #172126; font-size: 24px; font-weight: 850; }
        #spec { background: transparent; color: #52646d; font-weight: 700; }
        #status { background: #0b7f78; color: white; border-radius: 5px; padding: 9px 18px; font-weight: 850; min-width: 72px; qproperty-alignment: AlignCenter; }
        #status[warning="true"] { background: #b96911; }
        QPushButton { background: #315a72; color: white; border: 0; border-radius: 5px; min-height: 34px; padding: 0 16px; font-weight: 850; }
        QTableWidget { background: white; alternate-background-color: #f3f7f8; gridline-color: #d7e0e4; border: 1px solid #c7d2d8; }
        QHeaderView::section { background: #dde7ea; color: #172126; font-weight: 850; border: 0; padding: 5px; }
        """
    )
    window = MainWindow()
    window.show()
    return app.exec()


def main() -> int:
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--smoke-test", action="store_true", help="Run calculations without opening the GUI")
    args = parser.parse_args()
    if args.smoke_test:
        smoke_test()
        return 0
    return run_gui()


if __name__ == "__main__":
    raise SystemExit(main())
