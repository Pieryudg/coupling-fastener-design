from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

from bolt_database import (
    DATABASE_PATH,
    connect,
    get_bolt_size,
    get_property_class,
    list_bolt_sizes,
    list_property_classes,
    recommend_bolt_size,
)
from coupling_calculations import CouplingInputs, CouplingResult, calculate
from standards import standard_basis_lines, standard_profile_items
from ctp_calculations import CTPInputs, CTPResult, StatusValue, calculate_ctp
from ctp_database import (
    build_ctp_friction,
    build_ctp_geometry,
    default_ctp_inputs,
    get_ctp_material,
    list_ctp_bolt_types,
    list_ctp_friction_labels,
    list_ctp_materials,
    list_ctp_sizes,
    load_ctp_data,
    standard_tightening_torque_nm,
)


GOVERNING_CASE_DISPLAY = {
    "steady-state selection": "Steady",
    "cyclic torque": "Cyclic",
    "maximum transient torque": "Transient",
}


def smoke_test() -> None:
    conn = connect()
    bolt = get_bolt_size(conn, "M10")
    prop = get_property_class(conn, "10.9")
    inputs = CouplingInputs(
        transmitted_torque_nm=1200,
        service_factor=1.5,
        cyclic_torque_nm=0,
        transient_torque_nm=0,
        bolt_count=8,
        friction_coefficient=0.18,
        inner_radius_mm=45,
        outer_radius_mm=115,
        friction_interfaces=1,
        initial_preload_per_bolt_n=25000,
        preload_loss_percent=15,
        separating_load_per_bolt_n=1000,
        bolt_stiffness_n_per_mm=30000,
        joint_stiffness_n_per_mm=15000,
        max_yield_utilization=0.70,
    )
    result = calculate(inputs, bolt, prop)
    print(f"database={DATABASE_PATH}")
    print(f"bolt={bolt.designation} class={prop.name}")
    print(f"slip_safety_factor={result.slip_safety_factor:.3f}")
    print(f"governing_torque_case={result.governing_torque_case}")
    print(f"design_torque_nm={result.design_torque_nm:.1f}")
    print(f"residual_pretension_n={result.residual_pretension_n:.1f}")
    print(f"service_residual_pretension_n={result.service_residual_pretension_n:.1f}")
    print(f"assembly_yield_utilization={result.assembly_yield_utilization:.3f}")
    ctp_result = calculate_ctp(default_ctp_inputs())
    print(f"ctp_preload_n={ctp_result.preload_n:.3f}")
    print(f"ctp_momentary_bolt_sf={ctp_result.case('momentary').bolt_safety_factor.value:.3f}")
    print(f"ctp_thread_root_sf={ctp_result.thread_root_safety_factor.value:.3f}")
    print(f"ctp_check={ctp_result.check_summary}")


def run_gui() -> int:
    try:
        from PySide6.QtCore import QPointF, QRectF, Qt
        from PySide6.QtGui import QColor, QFont, QPainter, QPen
        from PySide6.QtWidgets import (
            QApplication,
            QComboBox,
            QDoubleSpinBox,
            QFormLayout,
            QFrame,
            QGridLayout,
            QGroupBox,
            QHBoxLayout,
            QLabel,
            QMainWindow,
            QMessageBox,
            QPushButton,
            QScrollArea,
            QSpinBox,
            QVBoxLayout,
            QWidget,
        )
    except ModuleNotFoundError:
        print("PySide6 is required for the native GUI.")
        print("Install it with:")
        print("  ./setup_macos.command")
        return 2

    class DiagramWidget(QWidget):
        def __init__(self) -> None:
            super().__init__()
            self.inputs: CouplingInputs | None = None
            self.result: CouplingResult | None = None
            self.setMinimumSize(620, 520)

        def set_state(self, inputs: CouplingInputs, result: CouplingResult) -> None:
            self.inputs = inputs
            self.result = result
            self.update()

        def paintEvent(self, _event) -> None:  # noqa: N802 - Qt API
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.fillRect(self.rect(), QColor("#ffffff"))
            if self.inputs is None or self.result is None:
                return
            self._draw_annulus(painter, QRectF(28, 28, 300, 250))
            self._draw_triangle(painter, QRectF(370, 28, max(330, self.width() - 400), 300))
            self._draw_bars(painter, QRectF(28, 345, self.width() - 56, 140))

        def _label(self, painter, text: str, x: float, y: float, size: int = 11, color: str = "#142126", bold: bool = False) -> None:
            font = QFont("Arial", size)
            font.setBold(bold)
            painter.setFont(font)
            painter.setPen(QColor(color))
            painter.drawText(QPointF(x, y), text)

        def _draw_annulus(self, painter, rect: QRectF) -> None:
            assert self.inputs is not None and self.result is not None
            inputs = self.inputs
            result = self.result
            self._label(painter, "Friction annulus", rect.left(), rect.top() + 14, 12, bold=True)
            cx = rect.left() + rect.width() / 2
            cy = rect.top() + rect.height() / 2 + 18
            outer = min(rect.width(), rect.height()) * 0.38
            inner = max(24, outer * inputs.inner_radius_mm / inputs.outer_radius_mm)
            pitch = (outer + inner) / 2

            painter.setPen(QPen(QColor("#24454b"), 3))
            painter.setBrush(QColor("#bfe8df"))
            painter.drawEllipse(QPointF(cx, cy), outer, outer)
            painter.setBrush(QColor("#ffffff"))
            painter.drawEllipse(QPointF(cx, cy), inner, inner)
            pen = QPen(QColor("#85aeb2"), 1.5)
            pen.setDashPattern([4, 6])
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(cx, cy), pitch, pitch)

            for index in range(inputs.bolt_count):
                angle = -math.pi / 2 + index * math.tau / inputs.bolt_count
                bx = cx + math.cos(angle) * pitch
                by = cy + math.sin(angle) * pitch
                painter.setPen(QPen(QColor("#26383f"), 2))
                painter.setBrush(QColor("#f7faf9"))
                painter.drawEllipse(QPointF(bx, by), 9, 9)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor("#4f5d67"))
                painter.drawEllipse(QPointF(bx, by), 3, 3)

            painter.setPen(QPen(QColor("#d68b18"), 7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(QRectF(cx + outer * 0.55, cy - outer * 0.56, outer * 0.9, outer * 1.12), 95 * 16, -185 * 16)
            self._label(
                painter,
                f"r_eff {result.effective_radius_mm:.1f} mm | T_slip {result.slip_capacity_nm:,.0f} N*m",
                cx - 118,
                rect.bottom() - 8,
                10,
                "#5d7078",
            )

        def _draw_triangle(self, painter, rect: QRectF) -> None:
            assert self.inputs is not None and self.result is not None
            inputs = self.inputs
            result = self.result
            self._label(painter, "Bolt-joint triangle", rect.left(), rect.top() + 14, 12, bold=True)
            left = rect.left() + 40
            right = rect.right() - 20
            top = rect.top() + 50
            bottom = rect.bottom() - 28
            max_load = max(
                result.bolt_yield_load_n * 1.05,
                inputs.initial_preload_per_bolt_n * 1.15,
                result.bolt_load_under_service_n * 1.15,
                result.required_initial_preload_per_bolt_n * 1.15,
            )

            def yy(load: float) -> float:
                return bottom - max(0.0, load) / max_load * (bottom - top)

            painter.setPen(QPen(QColor("#7c8d94"), 1))
            painter.drawLine(QPointF(left, bottom), QPointF(right, bottom))
            painter.drawLine(QPointF(left, bottom), QPointF(left, top))
            self._hline(painter, left, right, yy(result.bolt_yield_load_n), "#b9322e")
            self._hline(painter, left, right, yy(inputs.initial_preload_per_bolt_n), "#73838a")
            self._hline(painter, left, right, yy(result.residual_pretension_n), "#0c8279")
            self._hline(painter, left, right, yy(result.service_residual_pretension_n), "#d68b18" if result.service_residual_pretension_n > 0 else "#b9322e")
            self._legend(
                painter,
                left + 12,
                top + 18,
                [
                    ("#b9322e", "Yield load"),
                    ("#73838a", "Initial preload"),
                    ("#0c8279", "Residual pretension"),
                    ("#d68b18", "Residual after load"),
                ],
            )

            delta = inputs.separating_load_per_bolt_n / (
                inputs.bolt_stiffness_n_per_mm + inputs.joint_stiffness_n_per_mm
            )
            x0 = left + 42
            x1 = x0 + min(right - x0 - 34, max(56, delta * 2200))
            painter.setPen(QPen(QColor("#0c8279"), 3))
            painter.drawLine(QPointF(x0, yy(result.residual_pretension_n)), QPointF(x1, yy(result.bolt_load_under_service_n)))
            painter.setPen(QPen(QColor("#26383f"), 3))
            painter.drawLine(QPointF(x0, yy(result.residual_pretension_n)), QPointF(x1, yy(result.service_residual_pretension_n)))
            pen = QPen(QColor("#d68b18"), 2)
            pen.setDashPattern([5, 4])
            painter.setPen(pen)
            painter.drawLine(QPointF(x1, yy(result.service_residual_pretension_n)), QPointF(x1, yy(result.bolt_load_under_service_n)))
            self._label(painter, f"Bolt load {result.bolt_load_under_service_n:,.0f} N", x1 + 8, yy(result.bolt_load_under_service_n), 10, "#0b4f49", True)
            self._label(painter, f"F_res {result.service_residual_pretension_n:,.0f} N", x1 + 8, yy(result.service_residual_pretension_n) + 14, 10, "#8a5b0d", True)
            self._label(painter, f"Phi = {result.load_fraction_to_bolt:.2f} | external axial per bolt = {inputs.separating_load_per_bolt_n:,.0f} N", x0, bottom + 22, 10, "#5d7078")
            self._label(painter, f"Slip SF {result.slip_safety_factor:.2f}", right - 88, top - 10, 11, "#0c8279" if result.slip_safety_factor >= 1 else "#b9322e", True)

        def _hline(self, painter, left: float, right: float, y: float, color: str) -> None:
            pen = QPen(QColor(color), 1.5)
            pen.setDashPattern([6, 5])
            painter.setPen(pen)
            painter.drawLine(QPointF(left, y), QPointF(right, y))

        def _legend(self, painter, x: float, y: float, items: list[tuple[str, str]]) -> None:
            painter.fillRect(QRectF(x - 8, y - 16, 160, len(items) * 18 + 8), QColor(255, 255, 255, 225))
            for index, (color, text) in enumerate(items):
                yy = y + index * 18
                painter.setPen(QPen(QColor(color), 2))
                painter.drawLine(QPointF(x, yy - 4), QPointF(x + 22, yy - 4))
                self._label(painter, text, x + 28, yy, 9, color, True)

        def _draw_bars(self, painter, rect: QRectF) -> None:
            assert self.inputs is not None and self.result is not None
            inputs = self.inputs
            result = self.result
            self._label(painter, "Yield and preload utilization", rect.left(), rect.top() + 14, 12, bold=True)
            items = [
                ("Initial preload", inputs.initial_preload_per_bolt_n, result.assembly_yield_utilization),
                ("Service bolt load", result.bolt_load_under_service_n, result.service_yield_utilization),
                ("Required preload", result.required_initial_preload_per_bolt_n, result.required_preload_yield_utilization),
            ]
            bar_x = rect.left() + 170
            bar_w = max(160, rect.width() - 310)
            for index, (name, _load, ratio) in enumerate(items):
                y = rect.top() + 42 + index * 34
                self._label(painter, name, rect.left(), y + 13, 10, "#314248", True)
                painter.setPen(QPen(QColor("#d1dcdf"), 1))
                painter.setBrush(QColor("#edf3f4"))
                painter.drawRect(QRectF(bar_x, y, bar_w, 18))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor("#0c8279" if ratio <= inputs.max_yield_utilization else "#b9322e"))
                painter.drawRect(QRectF(bar_x, y, min(bar_w, bar_w * ratio), 18))
                self._label(painter, f"{ratio * 100:.1f}% yield", bar_x + bar_w + 12, y + 13, 10, "#5d7078")

    class ResultCard(QFrame):
        def __init__(self, title: str) -> None:
            super().__init__()
            self.setObjectName("card")
            layout = QVBoxLayout(self)
            layout.setContentsMargins(12, 10, 12, 10)
            title_label = QLabel(title.upper())
            title_label.setObjectName("metricTitle")
            self.value_label = QLabel("--")
            self.value_label.setObjectName("metricValue")
            layout.addWidget(title_label)
            layout.addWidget(self.value_label)

        def set_value(self, value: str, danger: bool = False) -> None:
            self.value_label.setText(value)
            self.value_label.setProperty("danger", danger)
            self.value_label.style().unpolish(self.value_label)
            self.value_label.style().polish(self.value_label)

    class MainWindow(QMainWindow):
        def __init__(self) -> None:
            super().__init__()
            self.conn = connect()
            self.ctp_data = load_ctp_data()
            self.setWindowTitle("Coupling Fastener Design")
            self.resize(1500, 880)
            self.cards: dict[str, ResultCard] = {}
            self.simple_card_keys: list[str] = []
            self.ctp_card_keys: list[str] = []
            self._build_ui()
            self.update_calculation()

        def _build_ui(self) -> None:
            root = QWidget()
            self.setCentralWidget(root)
            layout = QGridLayout(root)
            layout.setContentsMargins(12, 12, 12, 12)
            layout.setHorizontalSpacing(12)

            inputs = self._build_inputs()
            workbench = self._build_workbench()
            results = self._build_results()
            layout.addWidget(inputs, 0, 0)
            layout.addWidget(workbench, 0, 1)
            layout.addWidget(results, 0, 2)
            layout.setColumnStretch(1, 1)
            self._update_mode_visibility()

        def _build_inputs(self) -> QWidget:
            scroll = QScrollArea()
            scroll.setObjectName("inputScroll")
            scroll.setFixedWidth(500)
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

            frame = QFrame()
            frame.setObjectName("inputRail")
            scroll.setWidget(frame)
            layout = QVBoxLayout(frame)
            title = QLabel("Coupling Fastener Design")
            title.setObjectName("railTitle")
            layout.addWidget(title)

            mode_form = QFormLayout()
            mode_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
            self._configure_form(mode_form)
            self.mode = QComboBox()
            self.mode.addItems(["Simple friction model", "CTP 0007 model"])
            self.mode.setCurrentText("CTP 0007 model")
            self._add_form_row(mode_form, "Calculation mode", self.mode)
            layout.addLayout(mode_form)

            self.simple_group = QGroupBox("Simple friction model")
            form = QFormLayout(self.simple_group)
            form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
            self._configure_form(form)
            self.bolt_size = QComboBox()
            self.bolt_size.addItems(list_bolt_sizes(self.conn))
            self.bolt_size.setCurrentText("M10")
            self.property_class = QComboBox()
            self.property_class.addItems(list_property_classes(self.conn))
            self.property_class.setCurrentText("10.9")
            self.radius_model = QComboBox()
            self.radius_model.addItems(["uniform_pressure", "uniform_wear"])
            self.standard_profile = QComboBox()
            self.profile_keys_by_label = {
                label: key for key, label in standard_profile_items()
            }
            self.standard_profile.addItems(list(self.profile_keys_by_label.keys()))

            self._add_form_row(form, "Bolt size", self.bolt_size)
            self._add_form_row(form, "Material class", self.property_class)
            self._add_form_row(form, "Standard profile", self.standard_profile)
            self._add_form_row(form, "Friction radius model", self.radius_model)

            self.torque = self._double(1200, 0, 1_000_000, 1)
            self.service_factor = self._double(1.5, 0.01, 10, 2)
            self.cyclic_torque = self._double(0, 0, 10_000_000, 1)
            self.transient_torque = self._double(0, 0, 10_000_000, 1)
            self.bolt_count = self._spin(8, 1, 128)
            self.mu = self._double(0.18, 0.01, 1.0, 3)
            self.inner_radius = self._double(45, 0, 10_000, 1)
            self.outer_radius = self._double(115, 0.1, 10_000, 1)
            self.interfaces = self._spin(1, 1, 12)
            self.initial_preload = self._double(25000, 0, 5_000_000, 0)
            self.preload_loss = self._double(15, 0, 99, 1)
            self.separating_load = self._double(1000, 0, 5_000_000, 0)
            self.bolt_stiffness = self._double(30000, 1, 1_000_000, 0)
            self.joint_stiffness = self._double(15000, 1, 1_000_000, 0)
            self.yield_limit = self._double(0.70, 0.01, 1.0, 2)

            for label, widget, unit in [
                ("Transmitted torque", self.torque, "N*m"),
                ("Service factor", self.service_factor, "x"),
                ("Cyclic torque", self.cyclic_torque, "N*m"),
                ("Transient torque", self.transient_torque, "N*m"),
                ("Number of bolts", self.bolt_count, "pcs"),
                ("Friction coefficient", self.mu, "mu"),
                ("Inner friction radius", self.inner_radius, "mm"),
                ("Outer friction radius", self.outer_radius, "mm"),
                ("Friction interfaces", self.interfaces, "faces"),
                ("Initial preload per bolt", self.initial_preload, "N"),
                ("Preload loss", self.preload_loss, "%"),
                ("Separating load per bolt", self.separating_load, "N"),
                ("Bolt stiffness", self.bolt_stiffness, "N/mm"),
                ("Joint stiffness", self.joint_stiffness, "N/mm"),
                ("Max yield utilization", self.yield_limit, "ratio"),
            ]:
                row = QWidget()
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.addWidget(widget, 1)
                unit_label = QLabel(unit)
                unit_label.setObjectName("unitLabel")
                unit_label.setFixedWidth(56)
                row_layout.addWidget(unit_label)
                self._add_form_row(form, label, row)

            layout.addWidget(self.simple_group)

            self.ctp_group = QGroupBox("CTP 0007 model")
            ctp_form = QFormLayout(self.ctp_group)
            ctp_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
            self._configure_form(ctp_form)
            defaults = self.ctp_data["default"]
            self.ctp_type = QComboBox()
            self.ctp_type.addItems(list_ctp_bolt_types(self.ctp_data))
            self.ctp_type.setCurrentText(defaults["bolt_type_code"])
            self.ctp_size = QComboBox()
            self.ctp_size.addItems(list_ctp_sizes(self.ctp_type.currentText(), self.ctp_data))
            self.ctp_size.setCurrentText(defaults["size_code"])
            self.ctp_material = QComboBox()
            self.ctp_material.addItems(list_ctp_materials(self.ctp_data))
            self.ctp_material.setCurrentText(defaults["material_code"])
            self.ctp_shear_plane = QComboBox()
            self.ctp_shear_plane.addItems(["Thread", "Shank"])

            self.ctp_screw_mu_label = QComboBox()
            self.ctp_nut_mu_label = QComboBox()
            self.ctp_part_mu_label = QComboBox()
            friction_labels = list_ctp_friction_labels(self.ctp_data)
            for combo in [self.ctp_screw_mu_label, self.ctp_nut_mu_label, self.ctp_part_mu_label]:
                combo.addItems(friction_labels)
            self.ctp_screw_mu_label.setCurrentText(defaults["screw_nut_friction_label"])
            self.ctp_nut_mu_label.setCurrentText(defaults["nut_part_friction_label"])
            self.ctp_part_mu_label.setCurrentText(defaults["part_part_friction_label"])

            self.ctp_pcd = self._double(447, 0.1, 100_000, 1)
            self.ctp_screw_count = self._spin(10, 1, 512)
            self.ctp_cont_torque = self._double(40100, 0, 10_000_000, 0)
            self.ctp_peak_factor = self._double(2.0, 0, 100, 2)
            self.ctp_momentary_factor = self._double(1.15, 0, 100, 2)
            self.ctp_tightening_torque = self._double(0, 0, 1_000_000, 1)
            self.ctp_percent_tys = self._double(0, 0, 100, 1)
            self.ctp_sleeve_od = self._double(0, 0, 10_000, 2)
            self.ctp_sleeve_yield = self._double(640, 1, 10_000, 0)
            self.ctp_leverarm = self._double(0.05, 0, 10_000, 3)
            self.ctp_groove_diameter = self._double(0, 0, 10_000, 2)
            self.ctp_contact_diameter = self._double(24, 0.1, 10_000, 2)
            self.ctp_thread_engagement = self._double(0, 0, 10_000, 2)
            self.ctp_custom_screw_mu = self._double(0.155, 0.001, 2.0, 3)
            self.ctp_custom_nut_mu = self._double(0.12, 0.001, 2.0, 3)
            self.ctp_custom_part_mu = self._double(0.15, 0.001, 2.0, 3)

            for label, widget in [
                ("Type", self.ctp_type),
                ("Size", self.ctp_size),
                ("Material", self.ctp_material),
                ("Shear plane", self.ctp_shear_plane),
                ("Screw/Nut friction", self.ctp_screw_mu_label),
                ("Nut/Part friction", self.ctp_nut_mu_label),
                ("Part/Part friction", self.ctp_part_mu_label),
            ]:
                self._add_form_row(ctp_form, label, widget)

            for label, widget, unit in [
                ("PCD", self.ctp_pcd, "mm"),
                ("Screw number", self.ctp_screw_count, "pcs"),
                ("Continuous torque", self.ctp_cont_torque, "N*m"),
                ("Peak factor", self.ctp_peak_factor, "x"),
                ("Momentary factor", self.ctp_momentary_factor, "x"),
                ("Tightening torque", self.ctp_tightening_torque, "N*m"),
                ("% tensile yield", self.ctp_percent_tys, "%"),
                ("Sleeve OD", self.ctp_sleeve_od, "mm"),
                ("Sleeve yield", self.ctp_sleeve_yield, "MPa"),
                ("Leverarm", self.ctp_leverarm, "mm"),
                ("Groove diameter", self.ctp_groove_diameter, "mm"),
                ("Contact diameter", self.ctp_contact_diameter, "mm"),
                ("Thread engagement", self.ctp_thread_engagement, "mm"),
                ("Custom screw mu", self.ctp_custom_screw_mu, "mu"),
                ("Custom nut mu", self.ctp_custom_nut_mu, "mu"),
                ("Custom part mu", self.ctp_custom_part_mu, "mu"),
            ]:
                row = QWidget()
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.addWidget(widget, 1)
                unit_label = QLabel(unit)
                unit_label.setObjectName("unitLabel")
                unit_label.setFixedWidth(56)
                row_layout.addWidget(unit_label)
                self._add_form_row(ctp_form, label, row)

            layout.addWidget(self.ctp_group)
            button = QPushButton("Calculate")
            button.clicked.connect(self.update_calculation)
            layout.addWidget(button)
            layout.addStretch(1)

            for widget in [
                self.bolt_size,
                self.property_class,
                self.standard_profile,
                self.radius_model,
                self.torque,
                self.service_factor,
                self.cyclic_torque,
                self.transient_torque,
                self.bolt_count,
                self.mu,
                self.inner_radius,
                self.outer_radius,
                self.interfaces,
                self.initial_preload,
                self.preload_loss,
                self.separating_load,
                self.bolt_stiffness,
                self.joint_stiffness,
                self.yield_limit,
            ]:
                if isinstance(widget, QComboBox):
                    widget.currentTextChanged.connect(self.update_calculation)
                else:
                    widget.valueChanged.connect(self.update_calculation)
            for widget in [
                self.ctp_type,
                self.ctp_size,
                self.ctp_material,
                self.ctp_shear_plane,
                self.ctp_screw_mu_label,
                self.ctp_nut_mu_label,
                self.ctp_part_mu_label,
                self.ctp_pcd,
                self.ctp_screw_count,
                self.ctp_cont_torque,
                self.ctp_peak_factor,
                self.ctp_momentary_factor,
                self.ctp_tightening_torque,
                self.ctp_percent_tys,
                self.ctp_sleeve_od,
                self.ctp_sleeve_yield,
                self.ctp_leverarm,
                self.ctp_groove_diameter,
                self.ctp_contact_diameter,
                self.ctp_thread_engagement,
                self.ctp_custom_screw_mu,
                self.ctp_custom_nut_mu,
                self.ctp_custom_part_mu,
            ]:
                if isinstance(widget, QComboBox):
                    widget.currentTextChanged.connect(self.update_calculation)
                else:
                    widget.valueChanged.connect(self.update_calculation)
            self.ctp_type.currentTextChanged.connect(self._sync_ctp_sizes)
            self.mode.currentTextChanged.connect(self._update_mode_visibility)
            self._update_mode_visibility()
            return scroll

        def _configure_form(self, form: QFormLayout) -> None:
            form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
            form.setHorizontalSpacing(14)
            form.setVerticalSpacing(10)

        def _add_form_row(self, form: QFormLayout, label: str, widget: QWidget) -> None:
            label_widget = QLabel(label)
            label_widget.setObjectName("formLabel")
            label_widget.setMinimumWidth(150)
            if isinstance(widget, (QComboBox, QDoubleSpinBox, QSpinBox)):
                widget.setMinimumWidth(190)
            else:
                widget.setMinimumWidth(240)
            form.addRow(label_widget, widget)

        def _double(self, value: float, minimum: float, maximum: float, decimals: int) -> QDoubleSpinBox:
            box = QDoubleSpinBox()
            box.setRange(minimum, maximum)
            box.setDecimals(decimals)
            box.setSingleStep(10 ** -decimals if decimals else 100)
            box.setValue(value)
            box.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
            return box

        def _spin(self, value: int, minimum: int, maximum: int) -> QSpinBox:
            box = QSpinBox()
            box.setRange(minimum, maximum)
            box.setValue(value)
            box.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
            return box

        def _is_ctp_mode(self) -> bool:
            return self.mode.currentText().startswith("CTP")

        def _sync_ctp_sizes(self) -> None:
            current = self.ctp_size.currentText()
            sizes = list_ctp_sizes(self.ctp_type.currentText(), self.ctp_data)
            self.ctp_size.blockSignals(True)
            self.ctp_size.clear()
            self.ctp_size.addItems(sizes)
            if current in sizes:
                self.ctp_size.setCurrentText(current)
            self.ctp_size.blockSignals(False)
            if sizes:
                self._apply_ctp_variant_defaults()
            if hasattr(self, "status"):
                self.update_calculation()

        def _apply_ctp_variant_defaults(self) -> None:
            try:
                variant = self.ctp_data["bolt_variants"][0]
                for candidate in self.ctp_data["bolt_variants"]:
                    if (
                        candidate["type_code"] == self.ctp_type.currentText()
                        and candidate["size_code"] == self.ctp_size.currentText()
                    ):
                        variant = candidate
                        break
                self.ctp_contact_diameter.setValue(float(variant["contact_diameter_mm"]))
                self.ctp_groove_diameter.setValue(float(variant["groove_diameter_mm"]))
            except Exception:
                return

        def _update_mode_visibility(self) -> None:
            ctp_mode = self._is_ctp_mode()
            self.simple_group.setVisible(not ctp_mode)
            self.ctp_group.setVisible(ctp_mode)
            if hasattr(self, "diagram"):
                self.diagram.setVisible(not ctp_mode)
            if hasattr(self, "ctp_summary"):
                self.ctp_summary.setVisible(ctp_mode)
            for key in self.simple_card_keys:
                self.cards[key].setVisible(not ctp_mode)
            for key in self.ctp_card_keys:
                self.cards[key].setVisible(ctp_mode)
            if hasattr(self, "status"):
                self.update_calculation()

        def _build_workbench(self) -> QWidget:
            frame = QFrame()
            frame.setObjectName("workbench")
            layout = QVBoxLayout(frame)
            top = QHBoxLayout()
            text = QVBoxLayout()
            eyebrow = QLabel("SQLite metric bolt database + flange friction torque model")
            eyebrow.setObjectName("eyebrow")
            title = QLabel("Torque transmission by friction between flanges")
            title.setObjectName("title")
            title.setWordWrap(True)
            self.spec = QLabel("")
            self.spec.setObjectName("spec")
            text.addWidget(eyebrow)
            text.addWidget(title)
            text.addWidget(self.spec)
            self.status = QLabel("OK")
            self.status.setObjectName("status")
            self.status.setFixedSize(116, 52)
            self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
            top.addLayout(text, 1)
            top.addWidget(self.status, 0, Qt.AlignmentFlag.AlignTop)
            layout.addLayout(top)
            self.diagram = DiagramWidget()
            layout.addWidget(self.diagram, 1)
            self.ctp_summary = QLabel("")
            self.ctp_summary.setObjectName("ctpSummary")
            self.ctp_summary.setWordWrap(True)
            self.ctp_summary.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            self.ctp_summary.setVisible(False)
            layout.addWidget(self.ctp_summary, 1)
            return frame

        def _build_results(self) -> QWidget:
            scroll = QScrollArea()
            scroll.setObjectName("results")
            scroll.setFixedWidth(330)
            scroll.setWidgetResizable(True)
            body = QWidget()
            layout = QVBoxLayout(body)
            title = QLabel("Results")
            title.setObjectName("resultsTitle")
            layout.addWidget(title)
            simple_cards = [
                ("Slip safety factor", "slip_sf"),
                ("Slip torque capacity", "slip_capacity"),
                ("Design torque demand", "design_torque"),
                ("Governing torque case", "governing_case"),
                ("Minimum service factor", "minimum_sf"),
                ("Residual pretension", "residual"),
                ("Residual after axial load", "service_residual"),
                ("Required initial preload", "required_initial"),
                ("Bolt yield load", "yield_load"),
                ("Assembly yield utilization", "assembly_util"),
                ("Service yield utilization", "service_util"),
            ]
            ctp_cards = [
                ("Minimum safety factor", "ctp_min_sf"),
                ("Axial pretension", "ctp_preload"),
                ("Tightening torque", "ctp_tightening"),
                ("Flange friction torque", "ctp_friction_torque"),
                ("Continuous torque ratio", "ctp_cont_ratio"),
                ("Peak torque ratio", "ctp_peak_ratio"),
                ("Momentary torque ratio", "ctp_momentary_ratio"),
                ("Momentary residual shear", "ctp_momentary_shear"),
                ("Momentary bolt SF", "ctp_momentary_bolt_sf"),
                ("Thread root SF", "ctp_thread_root_sf"),
                ("First thread stress", "ctp_thread_pullout"),
            ]
            self.simple_card_keys = [key for _title, key in simple_cards]
            self.ctp_card_keys = [key for _title, key in ctp_cards]
            for title_text, key in simple_cards + ctp_cards:
                card = ResultCard(title_text)
                self.cards[key] = card
                layout.addWidget(card)
            checks_group = QGroupBox("Checks")
            checks_layout = QVBoxLayout(checks_group)
            self.checks = QLabel("")
            self.checks.setWordWrap(True)
            checks_layout.addWidget(self.checks)
            layout.addWidget(checks_group)
            layout.addStretch(1)
            scroll.setWidget(body)
            return scroll

        def inputs(self) -> CouplingInputs:
            return CouplingInputs(
                transmitted_torque_nm=self.torque.value(),
                service_factor=self.service_factor.value(),
                cyclic_torque_nm=self.cyclic_torque.value(),
                transient_torque_nm=self.transient_torque.value(),
                bolt_count=self.bolt_count.value(),
                friction_coefficient=self.mu.value(),
                inner_radius_mm=self.inner_radius.value(),
                outer_radius_mm=self.outer_radius.value(),
                friction_interfaces=self.interfaces.value(),
                initial_preload_per_bolt_n=self.initial_preload.value(),
                preload_loss_percent=self.preload_loss.value(),
                separating_load_per_bolt_n=self.separating_load.value(),
                bolt_stiffness_n_per_mm=self.bolt_stiffness.value(),
                joint_stiffness_n_per_mm=self.joint_stiffness.value(),
                max_yield_utilization=self.yield_limit.value(),
                radius_model=self.radius_model.currentText(),
                standard_profile=self.profile_keys_by_label[self.standard_profile.currentText()],
            )

        def ctp_inputs(self) -> CTPInputs:
            type_code = self.ctp_type.currentText()
            size_code = self.ctp_size.currentText()
            material_code = self.ctp_material.currentText()
            geometry = build_ctp_geometry(
                type_code=type_code,
                size_code=size_code,
                pcd_mm=self.ctp_pcd.value(),
                screw_count=self.ctp_screw_count.value(),
                shear_plane=self.ctp_shear_plane.currentText(),
                leverarm_mm=self.ctp_leverarm.value(),
                groove_diameter_mm=self.ctp_groove_diameter.value(),
                contact_diameter_mm=self.ctp_contact_diameter.value(),
                data=self.ctp_data,
            )
            friction = build_ctp_friction(
                screw_nut_label=self.ctp_screw_mu_label.currentText(),
                nut_part_label=self.ctp_nut_mu_label.currentText(),
                part_part_label=self.ctp_part_mu_label.currentText(),
                custom_screw_nut_mu=self.ctp_custom_screw_mu.value(),
                custom_nut_part_mu=self.ctp_custom_nut_mu.value(),
                custom_part_part_mu=self.ctp_custom_part_mu.value(),
                data=self.ctp_data,
            )
            tightening_torque = self.ctp_tightening_torque.value()
            preload_percent = self.ctp_percent_tys.value()
            thread_engagement = self.ctp_thread_engagement.value()
            return CTPInputs(
                reference=self.ctp_data["default"]["reference"],
                geometry=geometry,
                material=get_ctp_material(material_code, self.ctp_data),
                friction=friction,
                continuous_torque_nm=self.ctp_cont_torque.value(),
                peak_factor=self.ctp_peak_factor.value(),
                momentary_factor=self.ctp_momentary_factor.value(),
                tightening_torque_nm=tightening_torque if tightening_torque else None,
                preload_percent_of_yield=preload_percent if preload_percent else None,
                standard_tightening_torque_nm=standard_tightening_torque_nm(
                    type_code,
                    size_code,
                    material_code,
                    self.ctp_data,
                ),
                sleeve_outer_diameter_mm=self.ctp_sleeve_od.value(),
                sleeve_yield_strength_mpa=self.ctp_sleeve_yield.value(),
                thread_engagement_mm=thread_engagement if thread_engagement else None,
            )

        def update_calculation(self) -> None:
            if self._is_ctp_mode():
                self._update_ctp_calculation()
            else:
                self._update_simple_calculation()

        def _update_simple_calculation(self) -> None:
            try:
                bolt = get_bolt_size(self.conn, self.bolt_size.currentText())
                prop = get_property_class(self.conn, self.property_class.currentText())
                inputs = self.inputs()
                result = calculate(inputs, bolt, prop)
            except Exception as exc:
                QMessageBox.warning(self, "Input error", str(exc))
                return

            self.spec.setText(
                f"{bolt.designation} x {bolt.pitch_mm:g} | As {bolt.tensile_area_mm2:g} mm2 | "
                f"class {prop.name}, yield {prop.yield_mpa:g} MPa | "
                f"governing: {GOVERNING_CASE_DISPLAY.get(result.governing_torque_case, result.governing_torque_case)}"
            )
            self.status.setText("OK" if result.warnings[0] == "All current checks pass." else "Check")
            self.status.setProperty("warning", result.warnings[0] != "All current checks pass.")
            self.status.style().unpolish(self.status)
            self.status.style().polish(self.status)
            self.diagram.set_state(inputs, result)

            self.cards["slip_sf"].set_value(f"{result.slip_safety_factor:.2f}", result.slip_safety_factor < 1)
            self.cards["slip_capacity"].set_value(f"{result.slip_capacity_nm:,.0f} N*m")
            self.cards["design_torque"].set_value(f"{result.design_torque_nm:,.0f} N*m")
            self.cards["governing_case"].set_value(
                GOVERNING_CASE_DISPLAY.get(result.governing_torque_case, result.governing_torque_case)
            )
            self.cards["minimum_sf"].set_value(f"{result.minimum_service_factor:g}x", inputs.service_factor < result.minimum_service_factor)
            self.cards["residual"].set_value(f"{result.residual_pretension_n:,.0f} N")
            self.cards["service_residual"].set_value(f"{result.service_residual_pretension_n:,.0f} N", result.service_residual_pretension_n <= 0)
            self.cards["required_initial"].set_value(f"{result.required_initial_preload_per_bolt_n:,.0f} N", result.required_preload_yield_utilization > inputs.max_yield_utilization)
            self.cards["yield_load"].set_value(f"{result.bolt_yield_load_n:,.0f} N")
            self.cards["assembly_util"].set_value(f"{result.assembly_yield_utilization * 100:.1f}%", result.assembly_yield_utilization > inputs.max_yield_utilization)
            self.cards["service_util"].set_value(f"{result.service_yield_utilization * 100:.1f}%", result.service_yield_utilization > inputs.max_yield_utilization)

            rec = recommend_bolt_size(self.conn, prop, result.required_initial_preload_per_bolt_n, inputs.max_yield_utilization)
            rec_text = (
                f"Minimum database size at {inputs.max_yield_utilization * 100:.0f}% yield: "
                f"{rec.designation} (As {rec.tensile_area_mm2:g} mm2)."
                if rec
                else "No database bolt size satisfies the required preload within the selected yield limit."
            )
            standard_text = "\n".join(
                f"- {item}" for item in standard_basis_lines(inputs.standard_profile)
            )
            checks_text = "\n".join(f"- {item}" for item in result.warnings)
            self.checks.setText(
                f"{rec_text}\n\nStandards basis:\n{standard_text}\n\nChecks:\n{checks_text}"
            )

        def _update_ctp_calculation(self) -> None:
            try:
                inputs = self.ctp_inputs()
                result = calculate_ctp(inputs)
            except Exception as exc:
                QMessageBox.warning(self, "Input error", str(exc))
                return

            geometry = inputs.geometry
            self.spec.setText(
                f"CTP {geometry.type_code} {geometry.size_code} | M{result.thread_diameter_mm:g} x "
                f"{result.pitch_mm:g} | {inputs.material.code}, yield {inputs.material.yield_strength_mpa:g} MPa"
            )
            has_warning = result.warnings[0] != "All CTP 0007 checks pass."
            self.status.setText("OK" if not has_warning else "Check")
            self.status.setProperty("warning", has_warning)
            self.status.style().unpolish(self.status)
            self.status.style().polish(self.status)
            self.diagram.setVisible(False)
            self.ctp_summary.setVisible(True)
            self.ctp_summary.setText(self._ctp_summary_text(result))

            continuous = result.case("continuous")
            peak = result.case("peak")
            momentary = result.case("momentary")
            self.cards["ctp_min_sf"].set_value(
                self._format_optional(result.minimum_safety_factor, "", 3),
                (result.minimum_safety_factor or 0) < 1.0,
            )
            self.cards["ctp_preload"].set_value(f"{result.preload_n:,.0f} N")
            self.cards["ctp_tightening"].set_value(f"{result.tightening_torque_nm:,.1f} N*m")
            self.cards["ctp_friction_torque"].set_value(f"{result.friction_torque_nm:,.0f} N*m")
            self.cards["ctp_cont_ratio"].set_value(self._format_status(continuous.torque_ratio, 3), (continuous.torque_ratio.value or 0) < 1)
            self.cards["ctp_peak_ratio"].set_value(self._format_status(peak.torque_ratio, 3), (peak.torque_ratio.value or 0) < 1)
            self.cards["ctp_momentary_ratio"].set_value(self._format_status(momentary.torque_ratio, 3), (momentary.torque_ratio.value or 0) < 1)
            self.cards["ctp_momentary_shear"].set_value(f"{momentary.residual_shear_load_n:,.0f} N")
            self.cards["ctp_momentary_bolt_sf"].set_value(
                self._format_status(momentary.bolt_safety_factor, 3),
                (momentary.bolt_safety_factor.value or 0) < 1.1,
            )
            self.cards["ctp_thread_root_sf"].set_value(
                self._format_status(result.thread_root_safety_factor, 3),
                (result.thread_root_safety_factor.value or 0) < 1.1,
            )
            self.cards["ctp_thread_pullout"].set_value(f"{result.first_thread_pullout_stress_mpa:,.1f} MPa")
            self.checks.setText(result.check_summary + "\n\n" + "\n".join(f"- {item}" for item in result.warnings))

        def _format_optional(self, value: float | None, unit: str = "", decimals: int = 1) -> str:
            if value is None:
                return "--"
            suffix = f" {unit}" if unit else ""
            return f"{value:,.{decimals}f}{suffix}"

        def _format_status(self, value: StatusValue, decimals: int = 3) -> str:
            if value.value is None:
                return value.status or "--"
            return f"{value.value:,.{decimals}f}"

        def _ctp_summary_text(self, result: CTPResult) -> str:
            rows = [
                "CTP 0007 cached-formula replica",
                "",
                f"Reference: {result.inputs.reference}",
                f"Pitch diameter d2: {result.pitch_diameter_mm:.3f} mm",
                f"Thread root d3: {result.thread_root_diameter_mm:.3f} mm",
                f"Tensile stress area: {result.tensile_stress_area_mm2:.3f} mm2",
                f"Average nut radius: {result.average_nut_radius_mm:.3f} mm",
                "",
                "Torque cases:",
            ]
            for case in result.cases:
                rows.append(
                    f"{case.name.title()}: demand {case.torque_nm:,.0f} N*m, "
                    f"ratio {self._format_status(case.torque_ratio, 3)}, "
                    f"residual shear {case.residual_shear_load_n:,.0f} N, "
                    f"bolt SF {self._format_status(case.bolt_safety_factor, 3)}, "
                    f"sleeve SF {self._format_status(case.sleeve_safety_factor, 3)}"
                )
            rows.extend(
                [
                    "",
                    f"Thread root Von Mises: {result.thread_root_von_mises_mpa:,.1f} MPa",
                    f"First thread pull-out stress: {result.first_thread_pullout_stress_mpa:,.1f} MPa",
                    f"Check summary: {result.check_summary}",
                ]
            )
            return "\n".join(rows)

    app = QApplication(sys.argv)
    app.setStyleSheet(
        """
        QWidget { background: #e8eef0; color: #142126; font-family: Arial; }
        #inputScroll { background: #f6fafb; border: 1px solid #cdd8dc; border-radius: 6px; }
        #inputRail { background: #f6fafb; border-radius: 6px; }
        #railTitle { background: #f6fafb; color: #142126; font-size: 20px; font-weight: 850; padding: 8px 4px 10px; }
        #formLabel { background: transparent; color: #314248; font-size: 12px; font-weight: 800; padding: 0; }
        #unitLabel { background: transparent; color: #5d7078; font-size: 12px; font-weight: 700; padding-left: 6px; }
        QComboBox, QDoubleSpinBox, QSpinBox {
            background: #ffffff;
            color: #142126;
            border: 1px solid #aebec3;
            border-radius: 5px;
            min-height: 30px;
            padding: 0 9px;
            selection-background-color: #cce9e7;
            selection-color: #142126;
        }
        QComboBox QAbstractItemView {
            background: #ffffff;
            color: #142126;
            border: 1px solid #8fa2a8;
            selection-background-color: #cce9e7;
            selection-color: #142126;
        }
        QPushButton { background: #0c8279; color: white; border: 0; border-radius: 5px; min-height: 38px; font-weight: 800; }
        #workbench, #results { background: #fbfdfe; border: 1px solid #cdd8dc; border-radius: 6px; }
        #eyebrow { color: #5d7078; font-size: 12px; font-weight: 800; }
        #title { color: #142126; font-size: 23px; font-weight: 850; }
        #spec { color: #5d7078; font-weight: 700; }
        #status { background: #0c8279; color: white; border-radius: 6px; padding: 0; font-weight: 850; min-width: 70px; qproperty-alignment: AlignCenter; }
        #status[warning="true"] { background: #d68b18; }
        #ctpSummary { background: #ffffff; color: #26383f; border: 1px solid #d1dcdf; border-radius: 6px; padding: 14px; font-family: Menlo; font-size: 12px; }
        #resultsTitle { background: white; color: #142126; font-size: 22px; font-weight: 850; padding-bottom: 6px; }
        #card { background: #fbfcfc; border: 1px solid #cdd8dc; border-radius: 6px; }
        #metricTitle { background: #fbfcfc; color: #5d7078; font-size: 11px; font-weight: 850; }
        #metricValue { background: #fbfcfc; color: #0c8279; font-family: Menlo; font-size: 21px; font-weight: 850; }
        #metricValue[danger="true"] { color: #b9322e; }
        QGroupBox { background: #ffffff; color: #142126; border: 1px solid #cdd8dc; border-radius: 6px; margin-top: 16px; padding: 12px 10px 10px; font-weight: 800; }
        QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 6px; background: #f6fafb; color: #314248; }
        """
    )
    window = MainWindow()
    window.show()
    return app.exec()


def main() -> int:
    parser = argparse.ArgumentParser(description="Coupling fastener native desktop GUI")
    parser.add_argument("--smoke-test", action="store_true", help="Run calculations without opening the GUI")
    args = parser.parse_args()
    if args.smoke_test:
        smoke_test()
        return 0
    return run_gui()


if __name__ == "__main__":
    raise SystemExit(main())
