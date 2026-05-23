"""
Properties Widget for AetherPDF.

This widget provides the right-hand properties panel for annotation tools and
text editing styles.
"""

from typing import Tuple
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QRadioButton,
    QButtonGroup, QSlider, QColorDialog, QPushButton, QGridLayout,
    QSpinBox, QCheckBox, QToolButton, QSizePolicy
)
from PySide6.QtCore import Signal, Qt, QSize
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap


class PropertiesWidget(QFrame):
    """
    Right properties panel for controlling annotation and text settings.

    Signals:
        tool_changed (str): Emitted when active drawing tool changes.
        color_changed (tuple): Emitted when the selected color changes.
        width_changed (float): Emitted when line/border thickness changes.
        opacity_changed (float): Emitted when transparency changes.
        text_style_changed (dict): Emitted when text style changes.
    """
    tool_changed = Signal(str)
    color_changed = Signal(tuple)
    width_changed = Signal(float)
    opacity_changed = Signal(float)
    text_style_changed = Signal(dict)

    def __init__(self, parent=None) -> None:
        """Initialize properties panel with layout and default values."""
        super().__init__(parent)
        self.setObjectName("propertiesFrame")
        self.setMinimumWidth(200)
        self.setMaximumWidth(360)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        self._active_tool: str = "highlight"
        self._current_color: Tuple[float, float, float] = (1.0, 1.0, 0.0)
        self._current_width: float = 3.0
        self._current_opacity: float = 1.0
        self._text_font_size: float = 12.0
        self._text_bold: bool = False
        self._text_italic: bool = False
        self.preset_buttons = []

        self._init_ui()
        self.set_mode("annotate")
        self._refresh_color_ui()

    def _init_ui(self) -> None:
        """Configure widget layout hierarchy and QSS styling."""
        self.setStyleSheet("""
            QFrame#propertiesFrame {
                background-color: #1B1B1F;
                border-left: 1px solid #2E2E35;
            }
            QLabel, QRadioButton, QCheckBox {
                color: #E1E1E6;
                font-size: 13px;
            }
            QLabel#propertiesTitle {
                color: #00F0FF;
                font-size: 14px;
                font-weight: bold;
                padding: 8px 4px;
            }
            QLabel[sectionLabel="true"] {
                color: #C9B7FF;
                font-weight: bold;
            }
            QSpinBox {
                background-color: #202024;
                color: #E1E1E6;
                border: 1px solid #2E2E35;
                border-radius: 4px;
                padding: 4px 18px 4px 8px;
            }
            QSpinBox:hover, QSpinBox:focus {
                border: 1px solid #00F0FF;
            }
            QSpinBox::up-button {
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 16px;
                border-left: 1px solid #2E2E35;
                background-color: #2A2A30;
            }
            QSpinBox::down-button {
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 16px;
                border-left: 1px solid #2E2E35;
                background-color: #2A2A30;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #383840;
            }
            QSpinBox::up-arrow {
                image: none;
                width: 0px;
                height: 0px;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-bottom: 6px solid #E1E1E6;
            }
            QSpinBox::down-arrow {
                image: none;
                width: 0px;
                height: 0px;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 6px solid #E1E1E6;
            }
            QCheckBox::indicator, QRadioButton::indicator {
                width: 14px;
                height: 14px;
            }
            QLabel#currentColorSwatch {
                border: 2px solid #FFFFFF;
                border-radius: 6px;
                min-width: 42px;
                min-height: 24px;
            }
            QLabel#currentColorValue {
                color: #E1E1E6;
                font-family: Consolas, monospace;
                font-size: 12px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(16)

        self.label_title = QLabel("주석 속성")
        self.label_title.setObjectName("propertiesTitle")
        self.label_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label_title)

        self.tools_section = QFrame()
        tools_layout = QVBoxLayout(self.tools_section)
        tools_layout.setContentsMargins(0, 0, 0, 0)
        tools_layout.setSpacing(6)

        label_tools = QLabel("주석 도구")
        label_tools.setProperty("sectionLabel", True)
        tools_layout.addWidget(label_tools)

        self.btn_group = QButtonGroup(self)

        self.radio_highlight = QRadioButton("형광펜")
        self.radio_highlight.setChecked(True)
        self.btn_group.addButton(self.radio_highlight)
        tools_layout.addWidget(self.radio_highlight)

        self.radio_underline = QRadioButton("밑줄")
        self.btn_group.addButton(self.radio_underline)
        tools_layout.addWidget(self.radio_underline)

        self.radio_strikeout = QRadioButton("취소선")
        self.btn_group.addButton(self.radio_strikeout)
        tools_layout.addWidget(self.radio_strikeout)

        self.radio_ink = QRadioButton("자유 그리기")
        self.btn_group.addButton(self.radio_ink)
        tools_layout.addWidget(self.radio_ink)
        layout.addWidget(self.tools_section)

        self.color_section = QFrame()
        color_layout = QVBoxLayout(self.color_section)
        color_layout.setContentsMargins(0, 0, 0, 0)
        color_layout.setSpacing(8)

        label_color = QLabel("색상")
        label_color.setProperty("sectionLabel", True)
        color_layout.addWidget(label_color)

        current_color_layout = QHBoxLayout()
        current_color_layout.setSpacing(8)

        self.current_color_swatch = QLabel()
        self.current_color_swatch.setObjectName("currentColorSwatch")
        self.current_color_swatch.setFixedSize(46, 28)
        current_color_layout.addWidget(self.current_color_swatch)

        self.current_color_value = QLabel()
        self.current_color_value.setObjectName("currentColorValue")
        current_color_layout.addWidget(self.current_color_value)
        current_color_layout.addStretch()
        color_layout.addLayout(current_color_layout)

        grid_layout = QGridLayout()
        grid_layout.setSpacing(6)

        self.presets = [
            ("#00F0FF", (0.0, 0.94, 1.0)),
            ("#8A2BE2", (0.54, 0.17, 0.89)),
            ("#FFFF00", (1.0, 1.0, 0.0)),
            ("#FF007F", (1.0, 0.0, 0.5)),
            ("#00FF66", (0.0, 1.0, 0.4)),
        ]

        for idx, (hex_val, rgb_val) in enumerate(self.presets):
            btn = QPushButton()
            btn.setFixedSize(28, 28)
            btn.setToolTip(hex_val)
            btn.clicked.connect(lambda checked=False, val=rgb_val: self._on_color_preset_clicked(val))
            grid_layout.addWidget(btn, 0, idx)
            self.preset_buttons.append(btn)

        self.btn_custom_color = QToolButton()
        self.btn_custom_color.setFixedSize(28, 28)
        self.btn_custom_color.setIcon(self._create_palette_icon())
        self.btn_custom_color.setIconSize(QSize(18, 18))
        self.btn_custom_color.setToolTip("색상 직접 선택")
        self.btn_custom_color.setStyleSheet("""
            QToolButton {
                border: 1px solid #2E2E35;
                border-radius: 14px;
                background-color: #202024;
            }
            QToolButton:hover {
                border: 1px solid #8A2BE2;
                background-color: #2A2A30;
            }
        """)
        self.btn_custom_color.clicked.connect(self._on_custom_color_dialog)
        grid_layout.addWidget(self.btn_custom_color, 0, len(self.presets))

        color_layout.addLayout(grid_layout)
        layout.addWidget(self.color_section)

        self.width_section = QFrame()
        width_layout = QVBoxLayout(self.width_section)
        width_layout.setContentsMargins(0, 0, 0, 0)
        width_layout.setSpacing(6)

        self.label_width = QLabel("선 두께: 3.0 px")
        self.label_width.setProperty("sectionLabel", True)
        width_layout.addWidget(self.label_width)

        self.slider_width = QSlider(Qt.Horizontal)
        self.slider_width.setMinimum(1)
        self.slider_width.setMaximum(15)
        self.slider_width.setValue(3)
        self.slider_width.valueChanged.connect(self._on_width_changed)
        width_layout.addWidget(self.slider_width)
        layout.addWidget(self.width_section)

        self.opacity_section = QFrame()
        opacity_layout = QVBoxLayout(self.opacity_section)
        opacity_layout.setContentsMargins(0, 0, 0, 0)
        opacity_layout.setSpacing(6)

        self.label_opacity = QLabel("불투명도: 100%")
        self.label_opacity.setProperty("sectionLabel", True)
        opacity_layout.addWidget(self.label_opacity)

        self.slider_opacity = QSlider(Qt.Horizontal)
        self.slider_opacity.setMinimum(10)
        self.slider_opacity.setMaximum(100)
        self.slider_opacity.setValue(100)
        self.slider_opacity.valueChanged.connect(self._on_opacity_changed)
        opacity_layout.addWidget(self.slider_opacity)
        layout.addWidget(self.opacity_section)

        self.text_section = QFrame()
        text_layout = QVBoxLayout(self.text_section)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(8)

        label_text = QLabel("텍스트 스타일")
        label_text.setProperty("sectionLabel", True)
        text_layout.addWidget(label_text)

        size_layout = QHBoxLayout()
        size_label = QLabel("크기")
        self.spin_text_size = QSpinBox()
        self.spin_text_size.setMinimum(6)
        self.spin_text_size.setMaximum(72)
        self.spin_text_size.setSingleStep(1)
        self.spin_text_size.setButtonSymbols(QSpinBox.UpDownArrows)
        self.spin_text_size.setValue(int(self._text_font_size))
        self.spin_text_size.valueChanged.connect(self._on_text_style_changed)
        size_layout.addWidget(size_label)
        size_layout.addWidget(self.spin_text_size)
        text_layout.addLayout(size_layout)

        style_flags_layout = QHBoxLayout()
        self.chk_text_bold = QCheckBox("굵게")
        self.chk_text_italic = QCheckBox("기울임")
        self.chk_text_bold.stateChanged.connect(self._on_text_style_changed)
        self.chk_text_italic.stateChanged.connect(self._on_text_style_changed)
        style_flags_layout.addWidget(self.chk_text_bold)
        style_flags_layout.addWidget(self.chk_text_italic)
        text_layout.addLayout(style_flags_layout)
        layout.addWidget(self.text_section)

        layout.addStretch()

        self.btn_group.buttonClicked.connect(self._on_tool_selected)

    def set_mode(self, mode: str) -> None:
        """Show only controls relevant to the active editing mode."""
        is_text_mode = mode == "edit_text"
        is_annot_mode = mode == "annotate"

        self.label_title.setText("텍스트 속성" if is_text_mode else "주석 속성")
        self.tools_section.setVisible(is_annot_mode)
        self.width_section.setVisible(is_annot_mode)
        self.opacity_section.setVisible(is_annot_mode)
        self.text_section.setVisible(is_text_mode)
        self.color_section.setVisible(is_text_mode or is_annot_mode)

    def get_settings(self) -> Tuple[str, Tuple[float, float, float], float, float]:
        """
        Get all current annotation properties.

        Returns:
            Tuple[str, Tuple[float, float, float], float, float]:
            (active_tool, rgb_color, line_width, opacity)
        """
        return (self._active_tool, self._current_color, self._current_width, self._current_opacity)

    def get_text_style(self) -> dict:
        """Get current text style controls."""
        return {
            "color": self._current_color,
            "font_size": self._text_font_size,
            "bold": self._text_bold,
            "italic": self._text_italic,
        }

    def set_text_style(self, style: dict) -> None:
        """Update text controls from a selected PDF text span."""
        color = style.get("color")
        if isinstance(color, tuple) and len(color) == 3:
            self._current_color = color
            self._refresh_color_ui()

        font_size = style.get("font_size")
        if isinstance(font_size, (int, float)):
            self._text_font_size = max(6.0, min(72.0, float(font_size)))
            self.spin_text_size.blockSignals(True)
            self.spin_text_size.setValue(int(round(self._text_font_size)))
            self.spin_text_size.blockSignals(False)

    def _on_tool_selected(self) -> None:
        """Process annotation tool changes and emit signals."""
        if self.radio_highlight.isChecked():
            self._active_tool = "highlight"
        elif self.radio_underline.isChecked():
            self._active_tool = "underline"
        elif self.radio_strikeout.isChecked():
            self._active_tool = "strikeout"
        elif self.radio_ink.isChecked():
            self._active_tool = "ink"

        self.tool_changed.emit(self._active_tool)

    def _on_color_preset_clicked(self, rgb_val: Tuple[float, float, float]) -> None:
        """Handle preset color clicks."""
        self._current_color = rgb_val
        self._refresh_color_ui()
        self.color_changed.emit(self._current_color)
        self.text_style_changed.emit(self.get_text_style())

    def _on_custom_color_dialog(self) -> None:
        """Open native color dialog for customized color selection."""
        initial_color = QColor.fromRgbF(
            self._current_color[0],
            self._current_color[1],
            self._current_color[2]
        )
        q_color = QColorDialog.getColor(initial_color, self, "색상 선택")
        if q_color.isValid():
            self._current_color = (q_color.redF(), q_color.greenF(), q_color.blueF())
            self._refresh_color_ui()
            self.color_changed.emit(self._current_color)
            self.text_style_changed.emit(self.get_text_style())

    def _refresh_color_ui(self) -> None:
        """Update selected color preview and preset selection rings."""
        hex_color = self._current_color_hex()
        self.current_color_swatch.setStyleSheet(f"background-color: {hex_color};")
        self.current_color_value.setText(hex_color)

        for btn, (preset_hex, preset_rgb) in zip(self.preset_buttons, self.presets):
            is_selected = self._colors_match(self._current_color, preset_rgb)
            border_color = "#FFFFFF" if is_selected else "#2E2E35"
            border_width = 3 if is_selected else 2
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {preset_hex};
                    border: {border_width}px solid {border_color};
                    border-radius: 14px;
                }}
                QPushButton:hover {{
                    border: 3px solid #00F0FF;
                }}
            """)

    def _current_color_hex(self) -> str:
        """Return the current RGB color as a hex string."""
        return QColor.fromRgbF(
            self._current_color[0],
            self._current_color[1],
            self._current_color[2]
        ).name().upper()

    def _colors_match(
        self,
        first: Tuple[float, float, float],
        second: Tuple[float, float, float]
    ) -> bool:
        """Compare RGB float tuples with tolerance for dialog conversions."""
        return all(abs(a - b) < 0.01 for a, b in zip(first, second))

    def _create_palette_icon(self) -> QIcon:
        """Create a small palette icon for the custom color picker button."""
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor("#E1E1E6"), 1.5))
        painter.setBrush(QColor("#2A2A30"))
        painter.drawEllipse(3, 4, 18, 16)

        painter.setPen(Qt.NoPen)
        for color, x, y in [
            ("#00F0FF", 8, 8),
            ("#8A2BE2", 14, 8),
            ("#FFFF00", 10, 14),
        ]:
            painter.setBrush(QColor(color))
            painter.drawEllipse(x, y, 4, 4)

        painter.setBrush(QColor("#1B1B1F"))
        painter.drawEllipse(16, 15, 4, 4)
        painter.end()
        return QIcon(pixmap)

    def _on_width_changed(self, val: int) -> None:
        """Handle line thickness slider adjustments."""
        self._current_width = float(val)
        self.label_width.setText(f"선 두께: {self._current_width:.1f} px")
        self.width_changed.emit(self._current_width)

    def _on_opacity_changed(self, val: int) -> None:
        """Handle opacity slider adjustments."""
        self._current_opacity = val / 100.0
        self.label_opacity.setText(f"불투명도: {val}%")
        self.opacity_changed.emit(self._current_opacity)

    def _on_text_style_changed(self) -> None:
        """Emit active text style changes."""
        self._text_font_size = float(self.spin_text_size.value())
        self._text_bold = self.chk_text_bold.isChecked()
        self._text_italic = self.chk_text_italic.isChecked()
        self.text_style_changed.emit(self.get_text_style())
