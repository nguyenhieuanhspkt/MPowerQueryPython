from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QDialogButtonBox, QListWidget, QListWidgetItem,
    QAbstractItemView, QMessageBox,
)
from PyQt5.QtCore import Qt

from core.project import MergeSource, AppendSource, QueryDef


class NewMergeQueryDialog(QDialog):
    """Create a new query whose source = pd.merge(left, right, on, how)."""

    _HOW_OPTIONS = ['left', 'inner', 'right', 'outer']

    def __init__(self, query_names: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Add Merge Query')
        self.setMinimumWidth(360)
        self._query_names = query_names
        self._setup_ui()

    def _setup_ui(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        lay.addWidget(QLabel('<b>Left Query</b>'))
        self._combo_left = QComboBox()
        self._combo_left.addItems(self._query_names)
        lay.addWidget(self._combo_left)

        lay.addWidget(QLabel('<b>Right Query</b>'))
        self._combo_right = QComboBox()
        self._combo_right.addItems(self._query_names)
        if len(self._query_names) > 1:
            self._combo_right.setCurrentIndex(1)
        lay.addWidget(self._combo_right)

        lay.addWidget(QLabel('<b>Join Column (on)</b>'))
        self._combo_on = QComboBox()
        self._combo_on.setEditable(True)
        lay.addWidget(self._combo_on)

        lay.addWidget(QLabel('<b>Join Type (how)</b>'))
        self._combo_how = QComboBox()
        self._combo_how.addItems(self._HOW_OPTIONS)
        lay.addWidget(self._combo_how)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

        self._combo_left.currentTextChanged.connect(self._on_left_changed)
        self._on_left_changed(self._combo_left.currentText())

    def _on_left_changed(self, name: str):
        pass  # Column list populated after query runs; user types the name

    def _on_accept(self):
        left = self._combo_left.currentText()
        right = self._combo_right.currentText()
        on = self._combo_on.currentText().strip()
        how = self._combo_how.currentText()
        if not on:
            QMessageBox.warning(self, 'Validation', 'Nhập tên cột để join (on).')
            return
        if left == right:
            QMessageBox.warning(self, 'Validation', 'Left và Right không được là cùng một query.')
            return
        self._result_source = MergeSource(left=left, right=right, on=on, how=how)
        self.accept()

    def get_source(self) -> MergeSource:
        return self._result_source

    def set_columns(self, columns: list):
        """Populate the on-column dropdown with columns from the left query."""
        current = self._combo_on.currentText()
        self._combo_on.clear()
        self._combo_on.addItems(columns)
        if current in columns:
            self._combo_on.setCurrentText(current)


class NewAppendQueryDialog(QDialog):
    """Create a new query whose source = pd.concat of selected queries."""

    def __init__(self, query_names: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Add Append Query')
        self.setMinimumWidth(340)
        self._query_names = query_names
        self._setup_ui()

    def _setup_ui(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        lay.addWidget(QLabel('<b>Chọn các Queries để nối (giữ Ctrl để multi-select)</b>'))
        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.MultiSelection)
        for name in self._query_names:
            self._list.addItem(QListWidgetItem(name))
        lay.addWidget(self._list)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _on_accept(self):
        selected = [item.text() for item in self._list.selectedItems()]
        if len(selected) < 2:
            QMessageBox.warning(self, 'Validation', 'Chọn ít nhất 2 queries để nối.')
            return
        self._result_source = AppendSource(queries=selected)
        self.accept()

    def get_source(self) -> AppendSource:
        return self._result_source
