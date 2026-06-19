from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QComboBox, QLineEdit, QLabel, QPushButton,
    QCheckBox, QScrollArea, QWidget, QRadioButton,
    QMessageBox, QTextEdit, QSplitter, QSpinBox, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QDialogButtonBox, QSlider, QInputDialog,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor


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


# ---------------------------------------------------------------------------
# Group Rows dialog
# ---------------------------------------------------------------------------

class GroupRowsDialog(QDialog):
    _AGG_FUNCS = [
        ('none',  '— (bỏ qua)'),
        ('count', 'Count  —  đếm số dòng'),
        ('sum',   'Sum  —  tổng'),
        ('mean',  'Mean  —  trung bình'),
        ('min',   'Min  —  giá trị nhỏ nhất'),
        ('max',   'Max  —  giá trị lớn nhất'),
        ('first', 'First  —  giá trị đầu tiên'),
        ('last',  'Last  —  giá trị cuối cùng'),
    ]

    def __init__(self, columns, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Group Rows (Aggregate)')
        self.setMinimumSize(500, 560)
        self.setStyleSheet(DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(14, 14, 14, 14)

        # ── Group By section ────────────────────────────────────────────────
        gb_box = QGroupBox('Group by  (chọn cột(s) để nhóm)')
        gb_box.setStyleSheet(
            'QGroupBox { font-weight: bold; font-size: 12px; '
            'border: 1px solid #CED4DA; border-radius: 4px; margin-top: 6px; padding-top: 6px; }'
            'QGroupBox::title { subcontrol-origin: margin; left: 8px; }'
        )
        gb_inner_layout = QVBoxLayout(gb_box)

        gb_scroll = QScrollArea()
        gb_scroll.setWidgetResizable(True)
        gb_scroll.setFixedHeight(140)
        gb_scroll.setStyleSheet('QScrollArea { border: none; }')
        gb_content = QWidget()
        gb_content_layout = QVBoxLayout(gb_content)
        gb_content_layout.setSpacing(3)
        gb_content_layout.setContentsMargins(4, 4, 4, 4)

        self._by_checks: dict = {}
        for col in columns:
            cb = QCheckBox(col)
            cb.toggled.connect(self._sync_agg_state)
            self._by_checks[col] = cb
            gb_content_layout.addWidget(cb)
        gb_content_layout.addStretch()
        gb_scroll.setWidget(gb_content)
        gb_inner_layout.addWidget(gb_scroll)
        layout.addWidget(gb_box)

        # ── Aggregation section ─────────────────────────────────────────────
        agg_box = QGroupBox('Aggregate  (chọn hàm tổng hợp cho các cột còn lại)')
        agg_box.setStyleSheet(
            'QGroupBox { font-weight: bold; font-size: 12px; '
            'border: 1px solid #CED4DA; border-radius: 4px; margin-top: 6px; padding-top: 6px; }'
            'QGroupBox::title { subcontrol-origin: margin; left: 8px; }'
        )
        agg_inner_layout = QVBoxLayout(agg_box)

        agg_scroll = QScrollArea()
        agg_scroll.setWidgetResizable(True)
        agg_scroll.setStyleSheet('QScrollArea { border: none; }')
        agg_content = QWidget()
        agg_form = QFormLayout(agg_content)
        agg_form.setSpacing(6)
        agg_form.setContentsMargins(4, 4, 4, 4)
        agg_form.setLabelAlignment(Qt.AlignRight)

        self._agg_combos: dict = {}
        for col in columns:
            combo = QComboBox()
            for key, label in self._AGG_FUNCS:
                combo.addItem(label, key)
            self._agg_combos[col] = combo
            agg_form.addRow(col + ':', combo)
        agg_scroll.setWidget(agg_content)
        agg_inner_layout.addWidget(agg_scroll)
        layout.addWidget(agg_box)

        btn_widget, ok_btn, cancel_btn = _button_row('Apply Group')
        ok_btn.clicked.connect(self._on_ok)
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(btn_widget)

    def _sync_agg_state(self):
        for col, cb in self._by_checks.items():
            combo = self._agg_combos[col]
            if cb.isChecked():
                combo.setEnabled(False)
                combo.setCurrentIndex(0)  # reset to 'none'
            else:
                combo.setEnabled(True)

    def _on_ok(self):
        by_cols = [col for col, cb in self._by_checks.items() if cb.isChecked()]
        if not by_cols:
            QMessageBox.warning(self, 'Thiếu cột nhóm', 'Chọn ít nhất 1 cột để nhóm (Group by).')
            return
        agg = {col: combo.currentData()
               for col, combo in self._agg_combos.items()
               if not self._by_checks[col].isChecked() and combo.currentData() != 'none'}
        if not agg:
            QMessageBox.warning(self, 'Thiếu Aggregation', 'Chọn ít nhất 1 cột với hàm tổng hợp (không phải "bỏ qua").')
            return
        self.accept()

    def get_step(self):
        by_cols = [col for col, cb in self._by_checks.items() if cb.isChecked()]
        agg = {col: combo.currentData()
               for col, combo in self._agg_combos.items()
               if not self._by_checks[col].isChecked() and combo.currentData() != 'none'}
        return {
            'operation': 'group_rows',
            'params': {'by': by_cols, 'aggregations': agg},
        }


# ---------------------------------------------------------------------------
# AI Semantic Filter
# ---------------------------------------------------------------------------

class _EmbedWorker(QThread):
    """Background thread: loads BGE-M3 (lazy), embeds column values + query,
    returns list of (row_index, value, score) sorted by score desc."""

    finished = pyqtSignal(list)
    status   = pyqtSignal(str)
    error    = pyqtSignal(str)

    def __init__(self, values, query, parent=None):
        super().__init__(parent)
        self.values = values
        self.query  = query

    def run(self):
        try:
            import numpy as np
            from core.ai import get_embedder

            self.status.emit('Đang nạp model BGE-M3 (lần đầu ~10s)...')
            embedder = get_embedder()

            self.status.emit(f'Đang nhúng {len(self.values)} giá trị...')
            doc_vecs  = embedder.embed_documents(self.values)
            query_vec = embedder.embed_query(self.query)

            doc_norms    = np.linalg.norm(doc_vecs, axis=1, keepdims=True)
            doc_vecs_norm = doc_vecs / (doc_norms + 1e-12)
            q_norm       = query_vec / (np.linalg.norm(query_vec) + 1e-12)
            scores       = (doc_vecs_norm @ q_norm).tolist()

            results = sorted(
                [(i, self.values[i], scores[i]) for i in range(len(self.values))],
                key=lambda x: x[2],
                reverse=True,
            )
            self.finished.emit(results)
        except Exception as exc:
            self.error.emit(str(exc))


class SemanticFilterDialog(QDialog):
    """Dialog: user chọn cột + nhập query → BGE-M3 tìm rows tương đồng.
    Threshold slider cập nhật highlight real-time. Step lưu query + threshold."""

    def __init__(self, df, columns, parent=None):
        super().__init__(parent)
        self.df           = df
        self._all_results = []   # list of (row_index, value, score)
        self._worker      = None
        self._step        = None
        self._setup_ui(columns)

    # ------------------------------------------------------------------ UI

    def _setup_ui(self, columns):
        self.setWindowTitle('AI Semantic Filter')
        self.setMinimumWidth(640)
        self.setMinimumHeight(540)
        self.setStyleSheet(DIALOG_STYLE)

        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        lay.setContentsMargins(16, 16, 16, 16)

        # --- column + query
        form = QFormLayout()
        form.setSpacing(8)

        self._col_combo = QComboBox()
        self._col_combo.addItems(columns)
        form.addRow('Cột:', self._col_combo)

        qrow = QHBoxLayout()
        self._query_edit = QLineEdit()
        self._query_edit.setPlaceholderText('VD: máy bơm nước, thiết bị điện hạ thế...')
        self._query_edit.returnPressed.connect(self._start_search)
        self._btn_search = QPushButton('Tìm kiếm')
        self._btn_search.setFixedWidth(100)
        self._btn_search.clicked.connect(self._start_search)
        qrow.addWidget(self._query_edit)
        qrow.addWidget(self._btn_search)
        form.addRow('Query:', qrow)
        lay.addLayout(form)

        # --- threshold slider
        trow = QHBoxLayout()
        trow.addWidget(QLabel('Ngưỡng:'))
        self._slider = QSlider(Qt.Horizontal)
        self._slider.setRange(0, 100)
        self._slider.setValue(70)
        self._slider.setTickInterval(10)
        self._slider.setTickPosition(QSlider.TicksBelow)
        self._slider.valueChanged.connect(self._on_threshold_changed)
        trow.addWidget(self._slider)
        self._lbl_thresh = QLabel('0.70')
        self._lbl_thresh.setFixedWidth(38)
        trow.addWidget(self._lbl_thresh)
        lay.addLayout(trow)

        # --- status
        self._lbl_status = QLabel('Nhập query và bấm Tìm kiếm.')
        self._lbl_status.setAlignment(Qt.AlignCenter)
        lay.addWidget(self._lbl_status)

        # --- results table
        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(['Giá trị trong cột', 'Score'])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.setColumnWidth(1, 70)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.verticalHeader().setDefaultSectionSize(22)
        lay.addWidget(self._table)

        # --- note
        note = QLabel('Dòng đậm = sẽ giữ lại.  Dòng xám = sẽ bị loại.  Kéo ngưỡng để điều chỉnh.')
        note.setStyleSheet('color: #888; font-size: 11px;')
        lay.addWidget(note)

        # --- buttons
        btn_box = QDialogButtonBox()
        self._btn_apply = btn_box.addButton('Apply', QDialogButtonBox.AcceptRole)
        self._btn_apply.setEnabled(False)
        btn_box.addButton(QDialogButtonBox.Cancel)
        btn_box.accepted.connect(self._on_apply)
        btn_box.rejected.connect(self.reject)
        lay.addWidget(btn_box)

    # ------------------------------------------------------------------ slots

    def _start_search(self):
        col   = self._col_combo.currentText()
        query = self._query_edit.text().strip()
        if not query:
            QMessageBox.warning(self, 'Thiếu query', 'Nhập nội dung tìm kiếm trước.')
            return
        values = self.df[col].fillna('').astype(str).tolist()
        self._btn_search.setEnabled(False)
        self._btn_apply.setEnabled(False)
        self._table.setRowCount(0)
        self._all_results = []

        self._worker = _EmbedWorker(values, query, self)
        self._worker.finished.connect(self._on_finished)
        self._worker.status.connect(self._lbl_status.setText)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_finished(self, results):
        self._all_results = results
        self._btn_search.setEnabled(True)
        self._btn_apply.setEnabled(True)
        self._populate_table()

    def _on_error(self, msg):
        self._lbl_status.setText(f'Lỗi: {msg}')
        self._btn_search.setEnabled(True)

    def _on_threshold_changed(self, val):
        self._lbl_thresh.setText(f'{val / 100:.2f}')
        if self._all_results:
            self._update_row_colors()

    def _populate_table(self):
        self._table.setRowCount(0)
        for row_idx, val, score in self._all_results:
            r = self._table.rowCount()
            self._table.insertRow(r)
            self._table.setItem(r, 0, QTableWidgetItem(str(val)))
            score_item = QTableWidgetItem(f'{score:.3f}')
            score_item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(r, 1, score_item)
        self._update_row_colors()

    def _update_row_colors(self):
        threshold = self._slider.value() / 100.0
        above = 0
        clr_pass = QColor('#1a1a1a')
        clr_fail = QColor('#bbbbbb')
        for r in range(self._table.rowCount()):
            score     = float(self._table.item(r, 1).text())
            is_above  = score >= threshold
            clr       = clr_pass if is_above else clr_fail
            if is_above:
                above += 1
            for c in range(2):
                item = self._table.item(r, c)
                if item:
                    item.setForeground(clr)
        total = len(self._all_results)
        self._lbl_status.setText(f'{above} / {total} rows sẽ được giữ lại')

    def _on_apply(self):
        if not self._all_results:
            self.reject()
            return
        self._step = {
            'operation': 'semantic_filter',
            'params': {
                'column':    self._col_combo.currentText(),
                'query':     self._query_edit.text().strip(),
                'threshold': self._slider.value() / 100.0,
            },
        }
        self.accept()

    def get_step(self):
        return self._step


# ---------------------------------------------------------------------------
# Fuzzy Dedup worker + dialog
# ---------------------------------------------------------------------------

class _FuzzyDedupWorker(QThread):
    finished = pyqtSignal(list)
    status   = pyqtSignal(str)
    error    = pyqtSignal(str)

    def __init__(self, values, threshold, parent=None):
        super().__init__(parent)
        self.values    = values
        self.threshold = threshold

    def run(self):
        try:
            import numpy as np
            import faiss
            from collections import defaultdict
            from core.ai import get_embedder

            n = len(self.values)
            self.status.emit('Đang nạp model BGE-M3 (lần đầu ~10s)...')
            embedder = get_embedder()

            texts = [str(v) if v is not None else '' for v in self.values]
            self.status.emit(f'Đang nhúng {n} giá trị...')
            vecs = embedder.embed_documents(texts, batch_size=32)

            norms     = np.linalg.norm(vecs, axis=1, keepdims=True)
            vecs_norm = (vecs / (norms + 1e-12)).astype(np.float32)

            self.status.emit('Đang tìm cặp tương đồng...')
            dim   = vecs_norm.shape[1]
            index = faiss.IndexFlatIP(dim)
            index.add(vecs_norm)

            k = min(30, n)
            scores_mat, indices_mat = index.search(vecs_norm, k)

            parent_arr = list(range(n))

            def find(x):
                root = x
                while parent_arr[root] != root:
                    root = parent_arr[root]
                while parent_arr[x] != root:
                    nxt = parent_arr[x]
                    parent_arr[x] = root
                    x = nxt
                return root

            for i in range(n):
                for ki in range(1, k):
                    j     = int(indices_mat[i][ki])
                    score = float(scores_mat[i][ki])
                    if j < 0 or score < self.threshold:
                        break
                    ri, rj = find(i), find(j)
                    if ri != rj:
                        parent_arr[ri] = rj

            cluster_map = defaultdict(list)
            for i in range(n):
                cluster_map[find(i)].append(i)

            results = []
            for _root, members in cluster_map.items():
                if len(members) <= 1:
                    continue
                canonical_idx = members[0]
                canonical_val = texts[canonical_idx]
                dupes = []
                for m in members[1:]:
                    score = float(np.dot(vecs_norm[canonical_idx], vecs_norm[m]))
                    dupes.append({'idx': m, 'val': texts[m], 'score': score})
                results.append({
                    'canonical_idx': canonical_idx,
                    'canonical_val': canonical_val,
                    'dupes': dupes,
                })

            results.sort(key=lambda c: len(c['dupes']), reverse=True)
            self.finished.emit(results)

        except Exception as exc:
            self.error.emit(str(exc))


class FuzzyDedupDialog(QDialog):
    """AI Fuzzy Dedup: nhóm các giá trị tương đồng trong một cột, loại bỏ dòng trùng."""

    def __init__(self, df, columns, parent=None):
        super().__init__(parent)
        self.df       = df
        self._clusters = []
        self._worker   = None
        self._step     = None
        self._setup_ui(columns)

    def _setup_ui(self, columns):
        self.setWindowTitle('AI Fuzzy Dedup')
        self.setMinimumWidth(700)
        self.setMinimumHeight(560)
        self.setStyleSheet(DIALOG_STYLE)

        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        lay.setContentsMargins(16, 16, 16, 16)

        form = QFormLayout()
        form.setSpacing(8)
        self._col_combo = QComboBox()
        self._col_combo.addItems(columns)
        form.addRow('Cột:', self._col_combo)
        lay.addLayout(form)

        trow = QHBoxLayout()
        trow.addWidget(QLabel('Ngưỡng tương đồng:'))
        self._slider = QSlider(Qt.Horizontal)
        self._slider.setRange(50, 99)
        self._slider.setValue(85)
        self._slider.setTickInterval(5)
        self._slider.setTickPosition(QSlider.TicksBelow)
        self._slider.valueChanged.connect(lambda v: self._lbl_thresh.setText(f'{v / 100:.2f}'))
        trow.addWidget(self._slider)
        self._lbl_thresh = QLabel('0.85')
        self._lbl_thresh.setFixedWidth(38)
        trow.addWidget(self._lbl_thresh)
        lay.addLayout(trow)

        self._btn_search = QPushButton('Tìm trùng lặp')
        self._btn_search.setObjectName('btn_primary')
        self._btn_search.clicked.connect(self._start_search)
        lay.addWidget(self._btn_search)

        self._lbl_status = QLabel('Chọn cột và bấm Tìm trùng lặp.')
        self._lbl_status.setAlignment(Qt.AlignCenter)
        lay.addWidget(self._lbl_status)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(['Giữ lại (canonical)', 'Trùng với', 'Score', 'Dòng #'])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.setColumnWidth(2, 70)
        self._table.setColumnWidth(3, 60)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.verticalHeader().setDefaultSectionSize(22)
        lay.addWidget(self._table)

        note = QLabel('Chỉ giữ lại dòng đầu tiên của mỗi nhóm — các dòng trùng sẽ bị xóa.')
        note.setStyleSheet('color: #888; font-size: 11px;')
        lay.addWidget(note)

        btn_box = QDialogButtonBox()
        self._btn_apply = btn_box.addButton('Apply', QDialogButtonBox.AcceptRole)
        self._btn_apply.setEnabled(False)
        btn_box.addButton(QDialogButtonBox.Cancel)
        btn_box.accepted.connect(self._on_apply)
        btn_box.rejected.connect(self.reject)
        lay.addWidget(btn_box)

    def _start_search(self):
        col    = self._col_combo.currentText()
        values = self.df[col].fillna('').astype(str).tolist()
        thr    = self._slider.value() / 100.0
        self._btn_search.setEnabled(False)
        self._btn_apply.setEnabled(False)
        self._table.setRowCount(0)
        self._clusters = []

        self._worker = _FuzzyDedupWorker(values, thr, self)
        self._worker.finished.connect(self._on_finished)
        self._worker.status.connect(self._lbl_status.setText)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_finished(self, clusters):
        self._clusters = clusters
        self._btn_search.setEnabled(True)
        if clusters:
            self._btn_apply.setEnabled(True)
        self._populate_table()

    def _on_error(self, msg):
        self._lbl_status.setText(f'Lỗi: {msg}')
        self._btn_search.setEnabled(True)

    def _populate_table(self):
        self._table.setRowCount(0)
        total_dupes = sum(len(c['dupes']) for c in self._clusters)
        if not self._clusters:
            self._lbl_status.setText('Không tìm thấy giá trị tương đồng nào.')
            return

        row_colors = ['#EBF5FB', '#FEF9E7']
        for ci, cluster in enumerate(self._clusters):
            bg       = QColor(row_colors[ci % 2])
            canonical = cluster['canonical_val']
            for dupe in cluster['dupes']:
                r = self._table.rowCount()
                self._table.insertRow(r)
                for c, text in enumerate([canonical, dupe['val'],
                                          f"{dupe['score']:.3f}", str(dupe['idx'])]):
                    item = QTableWidgetItem(text)
                    item.setBackground(bg)
                    if c >= 2:
                        item.setTextAlignment(Qt.AlignCenter)
                    self._table.setItem(r, c, item)

        n_groups = len(self._clusters)
        total_rows = len(self.df)
        self._lbl_status.setText(
            f'{n_groups} nhóm trùng lặp — xóa {total_dupes} dòng, '
            f'giữ lại {total_rows - total_dupes} / {total_rows} dòng'
        )

    def _on_apply(self):
        if not self._clusters:
            self.reject()
            return
        self._step = {
            'operation': 'semantic_dedup',
            'params': {
                'column':    self._col_combo.currentText(),
                'threshold': self._slider.value() / 100.0,
            },
        }
        self.accept()

    def get_step(self):
        return self._step


# ---------------------------------------------------------------------------
# Cross-file Match worker + dialog
# ---------------------------------------------------------------------------

class _CrossMatchWorker(QThread):
    finished = pyqtSignal(object)
    status   = pyqtSignal(str)
    error    = pyqtSignal(str)

    def __init__(self, df_a, col_a, df_b, col_b, parent=None):
        super().__init__(parent)
        self.df_a  = df_a
        self.col_a = col_a
        self.df_b  = df_b
        self.col_b = col_b

    def run(self):
        try:
            import numpy as np
            from core.ai import get_embedder
            from core.ai.vector_store import VectorStore

            embedder = get_embedder()

            vals_b = self.df_b[self.col_b].fillna('').astype(str).tolist()
            self.status.emit(f'Đang nhúng {len(vals_b)} giá trị (Frame B)...')
            vecs_b = embedder.embed_documents(vals_b, batch_size=32)

            store = VectorStore()
            store.build_index(vecs_b, [{'idx': i, 'val': vals_b[i]} for i in range(len(vals_b))])

            vals_a = self.df_a[self.col_a].fillna('').astype(str).tolist()
            self.status.emit(f'Đang nhúng {len(vals_a)} giá trị (Frame A)...')
            vecs_a = embedder.embed_documents(vals_a, batch_size=32)

            self.status.emit('Đang khớp...')
            match_vals   = []
            match_scores = []
            for vec in vecs_a:
                hits = store.search(vec, top_k=1)
                if hits:
                    match_vals.append(hits[0]['metadata']['val'])
                    match_scores.append(round(hits[0]['score'], 4))
                else:
                    match_vals.append('')
                    match_scores.append(0.0)

            def _light(s):
                return '🟢' if s >= 0.80 else ('🟡' if s >= 0.50 else '🔴')

            result = self.df_a.copy()
            result['_best_match']   = match_vals
            result['_match_score']  = match_scores
            result['_match_status'] = [_light(s) for s in match_scores]

            self.finished.emit(result)

        except Exception as exc:
            self.error.emit(str(exc))


class CrossFileMatchDialog(QDialog):
    """Khớp dòng giữa 2 DataFrames bằng cosine similarity (BGE-M3).
    Kết quả là Frame A + 3 cột mới: _best_match, _match_score, _match_status."""

    def __init__(self, current_df, stored_frames, parent=None):
        super().__init__(parent)
        self._current_df     = current_df
        self._stored_frames  = stored_frames
        self._result_df      = None
        self._result_name    = ''
        self._worker         = None
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle('AI Cross-file Match')
        self.setMinimumWidth(820)
        self.setMinimumHeight(640)
        self.setStyleSheet(DIALOG_STYLE)

        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        lay.setContentsMargins(16, 16, 16, 16)

        # --- Frame A
        grp_a   = QGroupBox('Frame A  (danh sách cần khớp)')
        form_a  = QFormLayout(grp_a)
        form_a.setSpacing(6)

        self._combo_a = QComboBox()
        self._combo_a.addItem('Current (đang xử lý)')
        for sf in self._stored_frames:
            r, c = sf['df'].shape
            self._combo_a.addItem(f"{sf['name']}  ({r:,}×{c})")
        self._combo_a.currentIndexChanged.connect(self._on_frame_a_changed)
        form_a.addRow('Frame:', self._combo_a)

        self._combo_col_a = QComboBox()
        form_a.addRow('Cột khóa:', self._combo_col_a)
        lay.addWidget(grp_a)

        # --- Frame B
        grp_b   = QGroupBox('Frame B  (tham chiếu để khớp vào)')
        form_b  = QFormLayout(grp_b)
        form_b.setSpacing(6)

        self._combo_b = QComboBox()
        for sf in self._stored_frames:
            r, c = sf['df'].shape
            self._combo_b.addItem(f"{sf['name']}  ({r:,}×{c})")
        self._combo_b.currentIndexChanged.connect(self._on_frame_b_changed)
        form_b.addRow('Frame:', self._combo_b)

        self._combo_col_b = QComboBox()
        form_b.addRow('Cột khóa:', self._combo_col_b)
        lay.addWidget(grp_b)

        # Populate columns for initial selection
        self._on_frame_a_changed(0)
        if self._stored_frames:
            self._on_frame_b_changed(0)

        # --- Match button
        self._btn_match = QPushButton('▶  Match Now')
        self._btn_match.setObjectName('btn_primary')
        self._btn_match.clicked.connect(self._start_match)
        lay.addWidget(self._btn_match)

        # --- Status
        self._lbl_status = QLabel('Cấu hình Frame A / B rồi bấm Match Now.')
        self._lbl_status.setAlignment(Qt.AlignCenter)
        lay.addWidget(self._lbl_status)

        # --- Preview table
        self._preview_table = QTableWidget(0, 0)
        self._preview_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._preview_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._preview_table.verticalHeader().setDefaultSectionSize(22)
        lay.addWidget(self._preview_table)

        # --- Note
        note = QLabel('🟢 score ≥ 0.80    🟡 0.50 – 0.79    🔴 < 0.50   |   Hiển thị tối đa 50 dòng đầu.')
        note.setStyleSheet('color: #888; font-size: 11px;')
        lay.addWidget(note)

        # --- Buttons
        brow = QHBoxLayout()
        btn_close = QPushButton('Đóng')
        btn_close.setObjectName('btn_cancel')
        btn_close.clicked.connect(self.reject)
        self._btn_save = QPushButton('Lưu vào Stored Frames')
        self._btn_save.setObjectName('btn_primary')
        self._btn_save.setEnabled(False)
        self._btn_save.clicked.connect(self._on_save)
        brow.addStretch()
        brow.addWidget(btn_close)
        brow.addWidget(self._btn_save)
        lay.addLayout(brow)

    # ---------------------------------------------------------------- helpers

    def _frame_a_df(self):
        idx = self._combo_a.currentIndex()
        return self._current_df if idx == 0 else self._stored_frames[idx - 1]['df']

    def _frame_b_df(self):
        idx = self._combo_b.currentIndex()
        if idx < 0 or idx >= len(self._stored_frames):
            return None
        return self._stored_frames[idx]['df']

    def _on_frame_a_changed(self, _idx):
        df = self._frame_a_df()
        self._combo_col_a.clear()
        if df is not None:
            self._combo_col_a.addItems(list(df.columns))

    def _on_frame_b_changed(self, _idx):
        df = self._frame_b_df()
        self._combo_col_b.clear()
        if df is not None:
            self._combo_col_b.addItems(list(df.columns))

    # ---------------------------------------------------------------- match

    def _start_match(self):
        df_a  = self._frame_a_df()
        df_b  = self._frame_b_df()
        col_a = self._combo_col_a.currentText()
        col_b = self._combo_col_b.currentText()

        if df_b is None:
            QMessageBox.warning(self, 'Thiếu Frame B',
                                'Cần ít nhất 1 Stored Frame làm tham chiếu.')
            return
        if not col_a or not col_b:
            QMessageBox.warning(self, 'Thiếu cột', 'Cần chọn cột khóa cho cả A và B.')
            return

        self._btn_match.setEnabled(False)
        self._btn_save.setEnabled(False)
        self._preview_table.setRowCount(0)
        self._preview_table.setColumnCount(0)
        self._result_df = None

        self._worker = _CrossMatchWorker(df_a, col_a, df_b, col_b, self)
        self._worker.finished.connect(self._on_match_done)
        self._worker.status.connect(self._lbl_status.setText)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_match_done(self, result_df):
        self._result_df = result_df
        self._btn_match.setEnabled(True)
        self._btn_save.setEnabled(True)
        self._populate_preview(result_df)

        n      = len(result_df)
        green  = int((result_df['_match_status'] == '🟢').sum())
        yellow = int((result_df['_match_status'] == '🟡').sum())
        red    = int((result_df['_match_status'] == '🔴').sum())
        self._lbl_status.setText(
            f'{n} dòng khớp xong  —  🟢 {green}   🟡 {yellow}   🔴 {red}'
        )

    def _on_error(self, msg):
        self._lbl_status.setText(f'Lỗi: {msg}')
        self._btn_match.setEnabled(True)

    def _populate_preview(self, df, max_rows=50):
        preview = df.head(max_rows)
        cols    = list(preview.columns)
        ai_cols = {'_best_match', '_match_score', '_match_status'}

        self._preview_table.setColumnCount(len(cols))
        self._preview_table.setHorizontalHeaderLabels(cols)
        self._preview_table.setRowCount(0)

        for ri in range(len(preview)):
            self._preview_table.insertRow(ri)
            status_val = str(preview.iloc[ri].get('_match_status', ''))
            for ci, col in enumerate(cols):
                val  = str(preview.iloc[ri, ci])
                item = QTableWidgetItem(val)
                if col in ai_cols:
                    item.setTextAlignment(Qt.AlignCenter)
                    if col == '_match_status':
                        if status_val == '🟢':
                            item.setBackground(QColor('#D1FAE5'))
                        elif status_val == '🟡':
                            item.setBackground(QColor('#FEF3C7'))
                        else:
                            item.setBackground(QColor('#FEE2E2'))
                    else:
                        item.setBackground(QColor('#F0F9FF'))
                self._preview_table.setItem(ri, ci, item)

        for ci, col in enumerate(cols):
            self._preview_table.setColumnWidth(ci, 130 if col in ai_cols else 100)

    # ---------------------------------------------------------------- save

    def _on_save(self):
        if self._result_df is None:
            QMessageBox.warning(self, 'Chưa có kết quả', 'Bấm Match Now trước.')
            return
        idx_a = self._combo_a.currentIndex()
        name_a = 'Current' if idx_a == 0 else self._stored_frames[idx_a - 1]['name']
        idx_b  = self._combo_b.currentIndex()
        name_b = self._stored_frames[idx_b]['name'] if idx_b >= 0 else 'B'
        default = f'Match: {name_a} ← {name_b}'
        name, ok = QInputDialog.getText(
            self, 'Lưu kết quả Match', 'Tên frame:', text=default
        )
        if not ok or not name.strip():
            return
        self._result_name = name.strip()
        self.accept()

    def get_result_df(self):
        return self._result_df

    def get_result_name(self):
        return self._result_name
