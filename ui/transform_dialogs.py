from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QComboBox, QLineEdit, QLabel, QPushButton,
    QCheckBox, QScrollArea, QWidget, QRadioButton,
    QMessageBox, QTextEdit, QSplitter, QSpinBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont


DIALOG_STYLE = """
    QDialog {
        background-color: #F8F9FA;
    }
    QLabel {
        color: #333333;
        font-size: 12px;
    }
    QComboBox, QLineEdit {
        background-color: #FFFFFF;
        border: 1px solid #CED4DA;
        border-radius: 4px;
        padding: 5px 8px;
        font-size: 12px;
        min-height: 28px;
    }
    QComboBox:focus, QLineEdit:focus {
        border-color: #4A90E2;
    }
    QPushButton {
        border-radius: 4px;
        padding: 6px 16px;
        font-size: 12px;
        min-width: 80px;
    }
    QPushButton#btn_primary {
        background-color: #4A90E2;
        color: white;
        border: none;
    }
    QPushButton#btn_primary:hover {
        background-color: #357ABD;
    }
    QPushButton#btn_cancel {
        background-color: #E9ECEF;
        color: #495057;
        border: 1px solid #CED4DA;
    }
    QPushButton#btn_cancel:hover {
        background-color: #DEE2E6;
    }
    QCheckBox {
        font-size: 12px;
        spacing: 6px;
    }
    QRadioButton {
        font-size: 12px;
        spacing: 6px;
    }
"""


def _button_row(ok_label: str) -> tuple:
    """Returns (widget, ok_btn, cancel_btn)."""
    widget = QWidget()
    layout = QHBoxLayout(widget)
    layout.setContentsMargins(0, 10, 0, 0)
    cancel_btn = QPushButton('Cancel')
    cancel_btn.setObjectName('btn_cancel')
    ok_btn = QPushButton(ok_label)
    ok_btn.setObjectName('btn_primary')
    layout.addStretch()
    layout.addWidget(cancel_btn)
    layout.addWidget(ok_btn)
    return widget, ok_btn, cancel_btn


# ---------------------------------------------------------------------------
# Filter dialog
# ---------------------------------------------------------------------------

class FilterDialog(QDialog):
    _CONDITIONS = [
        ('equals',       '== equals'),
        ('not_equals',   '!= not equals'),
        ('contains',     '∋ contains'),
        ('not_contains', '∌ not contains'),
        ('starts_with',  'starts with'),
        ('ends_with',    'ends with'),
        ('greater_than', '> greater than'),
        ('less_than',    '< less than'),
        ('greater_equal','≥ greater or equal'),
        ('less_equal',   '≤ less or equal'),
        ('is_empty',     'is empty (NA/blank)'),
        ('is_not_empty', 'is not empty'),
    ]
    _NO_VALUE = {'is_empty', 'is_not_empty'}

    def __init__(self, columns, parent=None, preselect: str = None):
        super().__init__(parent)
        self.setWindowTitle('Filter Rows')
        self.setMinimumWidth(420)
        self.setStyleSheet(DIALOG_STYLE)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setSpacing(8)

        self.col_combo = QComboBox()
        self.col_combo.addItems(columns)
        if preselect and preselect in columns:
            self.col_combo.setCurrentIndex(columns.index(preselect))
        form.addRow('Column:', self.col_combo)

        self.cond_combo = QComboBox()
        for key, label in self._CONDITIONS:
            self.cond_combo.addItem(label, key)
        form.addRow('Condition:', self.cond_combo)

        self.value_edit = QLineEdit()
        self.value_edit.setPlaceholderText('Filter value...')
        form.addRow('Value:', self.value_edit)

        layout.addLayout(form)

        btn_widget, ok_btn, cancel_btn = _button_row('Apply Filter')
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(btn_widget)

        self.cond_combo.currentIndexChanged.connect(self._on_cond_changed)

    def _on_cond_changed(self, _):
        key = self.cond_combo.currentData()
        self.value_edit.setEnabled(key not in self._NO_VALUE)

    def get_step(self):
        return {
            'operation': 'filter',
            'params': {
                'column': self.col_combo.currentText(),
                'condition': self.cond_combo.currentData(),
                'value': self.value_edit.text(),
            }
        }


# ---------------------------------------------------------------------------
# Drop Columns dialog
# ---------------------------------------------------------------------------

class DropColumnsDialog(QDialog):
    def __init__(self, columns, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Drop Columns')
        self.setMinimumSize(320, 420)
        self.setStyleSheet(DIALOG_STYLE)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        layout.addWidget(QLabel('Select columns to remove:'))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet('QScrollArea { border: 1px solid #CED4DA; border-radius: 4px; }')
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setSpacing(4)
        inner_layout.setContentsMargins(8, 8, 8, 8)

        self.checkboxes: dict = {}
        for col in columns:
            cb = QCheckBox(col)
            self.checkboxes[col] = cb
            inner_layout.addWidget(cb)
        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)

        # select all / none shortcuts
        toggle_widget = QWidget()
        toggle_layout = QHBoxLayout(toggle_widget)
        toggle_layout.setContentsMargins(0, 0, 0, 0)
        btn_all = QPushButton('Select All')
        btn_all.setObjectName('btn_cancel')
        btn_all.clicked.connect(lambda: [cb.setChecked(True) for cb in self.checkboxes.values()])
        btn_none = QPushButton('Clear All')
        btn_none.setObjectName('btn_cancel')
        btn_none.clicked.connect(lambda: [cb.setChecked(False) for cb in self.checkboxes.values()])
        toggle_layout.addWidget(btn_all)
        toggle_layout.addWidget(btn_none)
        toggle_layout.addStretch()
        layout.addWidget(toggle_widget)

        btn_widget, ok_btn, cancel_btn = _button_row('Drop Selected')
        ok_btn.clicked.connect(self._on_ok)
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(btn_widget)

    def _on_ok(self):
        if not any(cb.isChecked() for cb in self.checkboxes.values()):
            QMessageBox.warning(self, 'No Selection', 'Please select at least one column.')
            return
        self.accept()

    def get_step(self):
        cols = [col for col, cb in self.checkboxes.items() if cb.isChecked()]
        return {'operation': 'drop_columns', 'params': {'columns': cols}}


# ---------------------------------------------------------------------------
# Rename Column dialog
# ---------------------------------------------------------------------------

class RenameColumnDialog(QDialog):
    def __init__(self, columns, parent=None, preselect: str = None):
        super().__init__(parent)
        self.setWindowTitle('Rename Column')
        self.setMinimumWidth(380)
        self.setStyleSheet(DIALOG_STYLE)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setSpacing(8)

        self.col_combo = QComboBox()
        self.col_combo.addItems(columns)
        if preselect and preselect in columns:
            self.col_combo.setCurrentIndex(columns.index(preselect))
        form.addRow('Column:', self.col_combo)

        self.new_name_edit = QLineEdit()
        self.new_name_edit.setPlaceholderText('New column name...')
        form.addRow('New Name:', self.new_name_edit)

        layout.addLayout(form)

        btn_widget, ok_btn, cancel_btn = _button_row('Rename')
        ok_btn.clicked.connect(self._on_ok)
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(btn_widget)

    def _on_ok(self):
        if not self.new_name_edit.text().strip():
            QMessageBox.warning(self, 'Empty Name', 'Please enter a new column name.')
            return
        self.accept()

    def get_step(self):
        return {
            'operation': 'rename_column',
            'params': {
                'old_name': self.col_combo.currentText(),
                'new_name': self.new_name_edit.text().strip(),
            }
        }


# ---------------------------------------------------------------------------
# Sort dialog
# ---------------------------------------------------------------------------

class SortDialog(QDialog):
    def __init__(self, columns, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Sort Rows')
        self.setMinimumWidth(340)
        self.setStyleSheet(DIALOG_STYLE)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setSpacing(8)

        self.col_combo = QComboBox()
        self.col_combo.addItems(columns)
        form.addRow('Sort by:', self.col_combo)
        layout.addLayout(form)

        dir_widget = QWidget()
        dir_layout = QHBoxLayout(dir_widget)
        dir_layout.setContentsMargins(0, 0, 0, 0)
        self.asc_radio = QRadioButton('Ascending  A→Z / 0→9')
        self.desc_radio = QRadioButton('Descending  Z→A / 9→0')
        self.asc_radio.setChecked(True)
        dir_layout.addWidget(self.asc_radio)
        dir_layout.addWidget(self.desc_radio)
        layout.addWidget(dir_widget)

        btn_widget, ok_btn, cancel_btn = _button_row('Sort')
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(btn_widget)

    def get_step(self):
        return {
            'operation': 'sort',
            'params': {
                'column': self.col_combo.currentText(),
                'ascending': self.asc_radio.isChecked(),
            }
        }


# ---------------------------------------------------------------------------
# Fill NA dialog
# ---------------------------------------------------------------------------

class FillNADialog(QDialog):
    def __init__(self, columns, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Fill Missing Values (NA)')
        self.setMinimumWidth(380)
        self.setStyleSheet(DIALOG_STYLE)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setSpacing(8)

        self.col_combo = QComboBox()
        self.col_combo.addItem('(all columns)', '__all__')
        for col in columns:
            self.col_combo.addItem(col, col)
        form.addRow('Column:', self.col_combo)

        self.value_edit = QLineEdit()
        self.value_edit.setPlaceholderText('e.g.  0  |  N/A  |  Unknown')
        form.addRow('Fill value:', self.value_edit)

        layout.addLayout(form)

        btn_widget, ok_btn, cancel_btn = _button_row('Apply')
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(btn_widget)

    def get_step(self):
        return {
            'operation': 'fillna',
            'params': {
                'column': self.col_combo.currentData(),
                'value': self.value_edit.text(),
            }
        }


# ---------------------------------------------------------------------------
# CSV Import options dialog
# ---------------------------------------------------------------------------

class CsvImportDialog(QDialog):
    _SEPS = [
        ('auto', 'Auto-detect'),
        (',',    'Dau phay  ,   (CSV chuan)'),
        (';',    'Dau cham phay  ;   (Excel Viet Nam / chau Au)'),
        ('\t',   'Tab'),
        ('|',    'Pipe  |'),
    ]
    _DECIMALS = [
        (',', 'Dau phay  ,   vi du: 1,5   (Viet Nam)'),
        ('.', 'Dau cham  .   vi du: 1.5   (quoc te)'),
    ]

    def __init__(self, path: str, detected_sep: str, parent=None):
        super().__init__(parent)
        import os
        self.setWindowTitle('Tuy chon Import CSV')
        self.setMinimumWidth(480)
        self.setStyleSheet(DIALOG_STYLE)
        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        layout.addWidget(QLabel(f'File: <b>{os.path.basename(path)}</b>'))

        # ── separator ──────────────────────────────────────────────────────
        sep_box = QWidget()
        sep_layout = QVBoxLayout(sep_box)
        sep_layout.setContentsMargins(0, 0, 0, 0)
        sep_layout.setSpacing(4)
        sep_layout.addWidget(QLabel('<b>Ky tu phan cach cot (separator):</b>'))

        self._sep_radios = {}
        for val, label in self._SEPS:
            rb = QRadioButton(label)
            self._sep_radios[val] = rb
            sep_layout.addWidget(rb)

        default_sep = detected_sep if detected_sep in self._sep_radios else 'auto'
        self._sep_radios[default_sep].setChecked(True)
        layout.addWidget(sep_box)

        # ── decimal separator ──────────────────────────────────────────────
        dec_box = QWidget()
        dec_layout = QVBoxLayout(dec_box)
        dec_layout.setContentsMargins(0, 0, 0, 0)
        dec_layout.setSpacing(4)
        dec_layout.addWidget(QLabel('<b>Dau thap phan (decimal):</b>'))

        self._dec_radios = {}
        for val, label in self._DECIMALS:
            rb = QRadioButton(label)
            self._dec_radios[val] = rb
            dec_layout.addWidget(rb)

        # default: nếu sep là ';' → nhiều khả năng file VN → decimal ','
        default_dec = ',' if default_sep in (';', 'auto') else '.'
        self._dec_radios[default_dec].setChecked(True)
        layout.addWidget(dec_box)

        # ── ambiguous note ─────────────────────────────────────────────────
        note = QLabel(
            '<i>Lua chon nay chi anh huong den truong hop mo ho:<br>'
            '&nbsp;"1,000" co the la 1.0 (VN) hoac 1000 (quoc te)<br>'
            '&nbsp;"1.500" co the la 1500 (VN) hoac 1.5 (quoc te)</i>'
        )
        note.setStyleSheet(
            'color: #6C757D; background: #F8F9FA; '
            'border: 1px solid #DEE2E6; border-radius: 4px; padding: 8px; font-size: 11px;'
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        btn_widget, ok_btn, cancel_btn = _button_row('Import')
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(btn_widget)

    def get_sep(self) -> str:
        for val, rb in self._sep_radios.items():
            if rb.isChecked():
                return val
        return 'auto'

    def get_decimal(self) -> str:
        for val, rb in self._dec_radios.items():
            if rb.isChecked():
                return val
        return ','


# ---------------------------------------------------------------------------
# Remove Top Rows dialog
# ---------------------------------------------------------------------------

class RemoveTopRowsDialog(QDialog):
    def __init__(self, total_rows: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Remove Top Rows')
        self.setMinimumWidth(340)
        self.setStyleSheet(DIALOG_STYLE)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        layout.addWidget(QLabel(f'Data hiện tại có <b>{total_rows:,}</b> dòng.<br>Bỏ bao nhiêu dòng từ đầu?'))

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)

        self.spin = QSpinBox()
        self.spin.setMinimum(1)
        self.spin.setMaximum(max(1, total_rows - 1))
        self.spin.setValue(1)
        self.spin.setStyleSheet(
            'QSpinBox { background: white; border: 1px solid #CED4DA; '
            'border-radius: 4px; padding: 4px 8px; font-size: 12px; min-height: 28px; }'
        )
        form.addRow('Số dòng cần bỏ:', self.spin)
        layout.addLayout(form)

        btn_widget, ok_btn, cancel_btn = _button_row('Remove')
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(btn_widget)

    def get_step(self):
        return {
            'operation': 'remove_top_rows',
            'params': {'n': self.spin.value()},
        }


# ---------------------------------------------------------------------------
# Sheet Picker dialog
# ---------------------------------------------------------------------------

class SheetPickerDialog(QDialog):
    def __init__(self, sheet_names: list, file_name: str = '', parent=None):
        super().__init__(parent)
        self.setWindowTitle('Select Sheet')
        self.setMinimumWidth(360)
        self.setStyleSheet(DIALOG_STYLE)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        label = QLabel(f'File <b>{file_name}</b> có <b>{len(sheet_names)}</b> sheet.\nChọn sheet cần load:')
        label.setWordWrap(True)
        layout.addWidget(label)

        self.combo = QComboBox()
        self.combo.addItems(sheet_names)
        layout.addWidget(self.combo)

        btn_widget, ok_btn, cancel_btn = _button_row('Load Sheet')
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(btn_widget)

    def selected_sheet(self) -> str:
        return self.combo.currentText()


# ---------------------------------------------------------------------------
# Code Preview dialog
# ---------------------------------------------------------------------------

class CodePreviewDialog(QDialog):
    def __init__(self, code: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Generated Pandas Code')
        self.setMinimumSize(620, 480)
        self.setStyleSheet(DIALOG_STYLE)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        label = QLabel('Equivalent pandas code for your pipeline:')
        layout.addWidget(label)

        self.code_edit = QTextEdit()
        self.code_edit.setReadOnly(True)
        self.code_edit.setFont(QFont('Consolas', 10))
        self.code_edit.setStyleSheet(
            'QTextEdit { background-color: #1E1E1E; color: #D4D4D4; '
            'border: 1px solid #555; border-radius: 4px; padding: 8px; }'
        )
        self.code_edit.setPlainText(code)
        layout.addWidget(self.code_edit)

        btn_widget, ok_btn, cancel_btn = _button_row('Copy to Clipboard')
        ok_btn.clicked.connect(self._copy)
        cancel_btn.setText('Close')
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(btn_widget)

    def _copy(self):
        from PyQt5.QtWidgets import QApplication
        QApplication.clipboard().setText(self.code_edit.toPlainText())
        from PyQt5.QtWidgets import QToolTip
        from PyQt5.QtGui import QCursor
        QToolTip.showText(QCursor.pos(), 'Copied!')
