from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QMenu, QAction,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont

from core.project import FileSource, MergeSource, AppendSource


class QuerySidebar(QWidget):
    sig_query_selected  = pyqtSignal(str)
    sig_query_refresh   = pyqtSignal(str)
    sig_query_export    = pyqtSignal(str)
    sig_query_rename    = pyqtSignal(str)
    sig_query_delete    = pyqtSignal(str)
    sig_add_file_query  = pyqtSignal()
    sig_add_merge_query = pyqtSignal()
    sig_add_append_query = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active_query = None
        self._blocking = False
        self._setup_ui()

    def _setup_ui(self):
        self.setObjectName('query_sidebar')
        self.setFixedWidth(190)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 10, 6, 8)
        lay.setSpacing(6)

        hdr = QHBoxLayout()
        title = QLabel('Queries')
        title.setObjectName('sidebar_title')
        hdr.addWidget(title)
        hdr.addStretch()
        self._lbl_count = QLabel('')
        self._lbl_count.setObjectName('sidebar_count')
        hdr.addWidget(self._lbl_count)
        lay.addLayout(hdr)

        self._list = QListWidget()
        self._list.setObjectName('query_list')
        self._list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._show_context_menu)
        self._list.currentRowChanged.connect(self._on_row_changed)
        lay.addWidget(self._list)

        self._btn_add = QPushButton('＋  Add Query')
        self._btn_add.setObjectName('btn_add_query')
        self._btn_add.clicked.connect(self._on_add_clicked)
        lay.addWidget(self._btn_add)

    def refresh(self, project, active_query):
        self._active_query = active_query
        self._blocking = True
        self._list.clear()
        for q in project._queries:
            src = q.source
            if isinstance(src, FileSource):
                icon = '📄'
            elif isinstance(src, MergeSource):
                icon = '⇌'
            elif isinstance(src, AppendSource):
                icon = '⊕'
            else:
                icon = '⚙'
            item = QListWidgetItem(f'{icon}  {q.name}')
            item.setData(Qt.UserRole, q.name)
            is_active = q.name == active_query
            f = QFont(item.font())
            f.setBold(is_active)
            item.setFont(f)
            item.setForeground(QColor('#7DD3FC' if is_active else '#94A3B8'))
            self._list.addItem(item)
        # Select active row
        for i in range(self._list.count()):
            if self._list.item(i).data(Qt.UserRole) == active_query:
                self._list.setCurrentRow(i)
                break
        self._blocking = False
        count = self._list.count()
        self._lbl_count.setText(str(count) if count else '')

    def _on_row_changed(self, row: int):
        if self._blocking or row < 0:
            return
        item = self._list.item(row)
        if item:
            name = item.data(Qt.UserRole)
            if name and name != self._active_query:
                self._active_query = name
                self.sig_query_selected.emit(name)

    def _show_context_menu(self, pos):
        item = self._list.itemAt(pos)
        if item is None:
            return
        name = item.data(Qt.UserRole)
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background:#3C3F41; color:#CCCCCC; border:1px solid #555; font-size:12px; }
            QMenu::item:selected { background:#4A90E2; color:white; }
            QMenu::item:disabled { color:#666; }
        """)
        hdr = QAction(f'  {name}', self)
        hdr.setEnabled(False)
        menu.addAction(hdr)
        menu.addSeparator()
        menu.addAction('↻  Refresh this Query').triggered.connect(
            lambda: self.sig_query_refresh.emit(name))
        menu.addAction('Export...').triggered.connect(
            lambda: self.sig_query_export.emit(name))
        menu.addSeparator()
        menu.addAction('Rename...').triggered.connect(
            lambda: self.sig_query_rename.emit(name))
        act_del = menu.addAction('Delete Query')
        act_del.triggered.connect(lambda: self.sig_query_delete.emit(name))
        act_del.setEnabled(self._list.count() > 1)
        menu.exec_(self._list.viewport().mapToGlobal(pos))

    def _on_add_clicked(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background:#3C3F41; color:#CCCCCC; border:1px solid #555; font-size:12px; }
            QMenu::item:selected { background:#4A90E2; color:white; }
        """)
        menu.addAction('📄  From File...').triggered.connect(self.sig_add_file_query.emit)
        menu.addAction('⇌  Merge Queries...').triggered.connect(self.sig_add_merge_query.emit)
        menu.addAction('⊕  Append Queries...').triggered.connect(self.sig_add_append_query.emit)
        menu.exec_(self._btn_add.mapToGlobal(self._btn_add.rect().bottomLeft()))
