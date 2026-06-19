import os
import pandas as pd
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTableView, QListWidget, QListWidgetItem, QLabel, QPushButton,
    QToolBar, QAction, QFileDialog, QStatusBar, QMessageBox,
    QFrame, QAbstractItemView, QSizePolicy, QInputDialog,
    QStyledItemDelegate, QStyle,
)
from PyQt5.QtCore import Qt, QSize, QRect, QEvent
from PyQt5.QtGui import QColor, QFont, QPainter

from core.data_engine import DataEngine
from core.recipe import Recipe
from core.project import (Project, QueryDef, FileSource, QuerySource,
                           MergeSource, AppendSource, recent_projects, push_recent)
from ui.pandas_model import PandasModel, SelectableHeaderView, ColumnHighlightDelegate
from ui.query_sidebar import QuerySidebar
from ui.project_dialogs import NewMergeQueryDialog, NewAppendQueryDialog
from core.utils import detect_csv_sep, to_numeric_vn
from ui.transform_dialogs import (
    FilterDialog, DropColumnsDialog, RenameColumnDialog,
    SortDialog, FillNADialog, CodePreviewDialog,
    SheetPickerDialog, RemoveTopRowsDialog, CsvImportDialog,
    GroupRowsDialog, SemanticFilterDialog,
    FuzzyDedupDialog, CrossFileMatchDialog,
    FlattenHierarchyDialog,
    ExpandHierarchyDialog,
)

def _fmt_agg(value: float, decimal: str = ',') -> str:
    """Format an aggregate number (sum) with thousands separators."""
    try:
        f = float(value)
        if f != f:          # NaN
            return '—'
        if f == int(f):
            s = f'{int(f):,}'
        else:
            s = f'{f:,.2f}'
        if decimal == ',':
            s = s.replace(',', '\x00').replace('.', ',').replace('\x00', '.')
        return s
    except (TypeError, ValueError, OverflowError):
        return '—'


_STEP_META = {
    'filter':                ('Filter',                '#4A90E2'),
    'drop_columns':          ('Drop Columns',          '#E25757'),
    'drop_duplicates':       ('Drop Duplicates',       '#E2A000'),
    'rename_column':         ('Rename Column',         '#27AE60'),
    'sort':                  ('Sort',                  '#9B59B6'),
    'fillna':                ('Fill NA',               '#16A085'),
    'remove_top_rows':       ('Remove Top Rows',       '#C0392B'),
    'use_first_row_as_header': ('Use Row 1 as Header', '#8E44AD'),
    'cast_column':           ('Cast Type',             '#6366F1'),
    'group_rows':            ('Group Rows',            '#F39C12'),
    'add_index_column':      ('Add Index (STT)',        '#10B981'),
    'flatten_hierarchy':     ('Flatten Hierarchy',     '#0F766E'),
    'expand_hierarchy':      ('Expand Hierarchy',      '#0D9488'),
    'semantic_filter':       ('AI Semantic Filter',    '#7C3AED'),
    'semantic_dedup':        ('AI Fuzzy Dedup',        '#9333EA'),
}


class _PipelineDeleteDelegate(QStyledItemDelegate):
    """Paints a × delete button on the right side of each pipeline step item."""
    _BTN_W  = 18
    _BTN_H  = 18
    _MARGIN = 8   # distance from right edge of item

    def paint(self, painter: QPainter, option, index):
        super().paint(painter, option, index)
        btn = self._btn_rect(option.rect)
        selected = bool(option.state & QStyle.State_Selected)
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor('#666666' if selected else '#DDDDDD'))
        painter.drawRoundedRect(btn, 4, 4)
        f = QFont(painter.font())
        f.setPixelSize(12)
        f.setBold(True)
        painter.setFont(f)
        painter.setPen(QColor('#EEEEEE' if selected else '#888888'))
        painter.drawText(btn, Qt.AlignCenter, '×')
        painter.restore()

    def _btn_rect(self, item_rect) -> QRect:
        x = item_rect.right() - self._BTN_W - self._MARGIN
        y = item_rect.center().y() - self._BTN_H // 2
        return QRect(x, y, self._BTN_W, self._BTN_H)

    def hit_delete(self, pos, item_rect) -> bool:
        return self._btn_rect(item_rect).contains(pos)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # Multi-query project state
        self.project: Project = Project('Untitled')
        self._query_engines: dict = {}   # query_name → DataEngine
        self._query_recipes: dict = {}   # query_name → Recipe
        self._active_query: str = None
        self._project_modified: bool = False
        self._refreshing_pipeline = False
        self._stored_frames: list = []   # list of {'name', 'df', 'source', 'steps'}
        self._init_ui()
        self._apply_style()

    # ---- project-aware engine / recipe proxy properties -------------------

    @property
    def engine(self) -> DataEngine:
        if self._active_query:
            return self._query_engines.get(self._active_query)
        return None

    @property
    def recipe(self) -> Recipe:
        if self._active_query:
            return self._query_recipes.get(self._active_query)
        return None

    @recipe.setter
    def recipe(self, value: Recipe):
        if self._active_query:
            self._query_recipes[self._active_query] = value

    # ------------------------------------------------------------------ setup

    def eventFilter(self, obj, event):
        if (obj is self.pipeline_list.viewport()
                and event.type() == QEvent.MouseButtonPress
                and event.button() == Qt.LeftButton):
            item = self.pipeline_list.itemAt(event.pos())
            if item is not None:
                row = self.pipeline_list.row(item)
                rect = self.pipeline_list.visualItemRect(item)
                if self._pipeline_delegate.hit_delete(event.pos(), rect):
                    self._delete_step(row)
                    return True
        return super().eventFilter(obj, event)

    def _init_ui(self):
        self.setWindowTitle('MPowerQueryPython')
        self.setMinimumSize(1100, 680)
        self.resize(1320, 820)
        self._create_menu()
        self._create_toolbar()
        self._create_central_widget()
        self._create_status_bar()
        self._set_data_actions_enabled(False)

    def _create_menu(self):
        mb = self.menuBar()

        fm = mb.addMenu('&File')
        fm.addAction('New Project', self._new_project, 'Ctrl+N')
        fm.addAction('Open Project...', self._open_project, 'Ctrl+O')
        fm.addAction('Save Project', self._save_project, 'Ctrl+S')
        fm.addAction('Save Project As...', self._save_project_as, 'Ctrl+Shift+S')
        self._recent_menu = fm.addMenu('Recent Projects')
        self._update_recent_menu()
        fm.addSeparator()
        fm.addAction('Add Query from File...', self._add_file_query, 'Ctrl+Shift+O')
        fm.addSeparator()
        fm.addAction('Export...', self._export_file, 'Ctrl+E')
        fm.addSeparator()
        fm.addAction('Exit', self.close, 'Alt+F4')

        em = mb.addMenu('&Edit')
        em.addAction('Undo Last Step', self._undo_step, 'Ctrl+Z')
        em.addAction('Reset to Original', self._reset_data)
        em.addSeparator()
        em.addAction('Save Recipe...', self._save_recipe)
        em.addAction('Load Recipe...', self._load_recipe)

        tm = mb.addMenu('&Transform')
        tm.addAction('Filter Rows...', self._add_filter)
        tm.addAction('Drop Columns...', self._add_drop_columns)
        tm.addAction('Drop Duplicates', self._add_drop_duplicates)
        tm.addAction('Rename Column...', self._add_rename)
        tm.addAction('Sort Rows...', self._add_sort)
        tm.addAction('Fill NA...', self._add_fillna)
        tm.addSeparator()
        tm.addAction('Remove Top Rows...', self._add_remove_top_rows)
        tm.addAction('Use First Row as Header', self._add_use_first_row_as_header)
        tm.addSeparator()
        tm.addAction('Group Rows...', self._add_group_rows)
        tm.addAction('Flatten Hierarchy...', self._add_flatten_hierarchy)
        tm.addAction('Expand Hierarchy...', self._add_expand_hierarchy)
        tm.addSeparator()
        tm.addAction('AI Semantic Filter...', self._add_semantic_filter)
        tm.addAction('AI Fuzzy Dedup...', self._add_fuzzy_dedup)
        tm.addSeparator()
        tm.addAction('AI Cross-file Match...', self._add_cross_match)

        vm = mb.addMenu('&View')
        vm.addAction('View Pandas Code', self._show_code)

    def _create_toolbar(self):
        tb = self.addToolBar('Main')
        tb.setIconSize(QSize(18, 18))
        tb.setMovable(False)
        tb.setObjectName('main_toolbar')
        tb.setToolButtonStyle(Qt.ToolButtonTextOnly)

        def act(label, tip, slot):
            a = QAction(label, self)
            a.setToolTip(tip)
            a.triggered.connect(slot)
            tb.addAction(a)
            return a

        act('Add Query', 'Add Query from File  (Ctrl+Shift+O)', self._add_file_query)
        self._act_export      = act('Export',      'Export active query  (Ctrl+E)',      self._export_file)
        self._act_refresh     = act('Refresh',     'Refresh source & rebuild  (Ctrl+R)', self._on_toolbar_refresh)
        self._act_refresh.setShortcut('Ctrl+R')
        tb.addSeparator()
        self._act_save_recipe = act('Save Recipe', 'Save pipeline as recipe',            self._save_recipe)
        self._act_load_recipe = act('Load Recipe', 'Load & apply recipe',                self._load_recipe)
        tb.addSeparator()
        self._act_filter      = act('Filter',      'Add filter step',                    self._add_filter)
        self._act_drop_cols   = act('Drop Cols',   'Drop columns',                       self._add_drop_columns)
        self._act_dedup       = act('Dedup',       'Drop duplicate rows',                self._add_drop_duplicates)
        self._act_sort        = act('Sort',        'Sort rows',                          self._add_sort)
        self._act_rename      = act('Rename',      'Rename a column',                    self._add_rename)
        self._act_fillna      = act('Fill NA',     'Fill missing values',                self._add_fillna)
        self._act_rm_top      = act('Rm Top',     'Remove top rows',                    self._add_remove_top_rows)
        self._act_header      = act('Row→Header', 'Use first row as column headers',    self._add_use_first_row_as_header)
        self._act_group       = act('Group',      'Group rows / aggregate',             self._add_group_rows)
        self._act_flatten     = act('Flatten',    'Flatten hierarchy / denormalize',    self._add_flatten_hierarchy)
        self._act_expand      = act('Expand',     'Expand narrow → wide hierarchy',     self._add_expand_hierarchy)
        tb.addSeparator()
        self._act_semantic    = act('AI Filter',  'Semantic filter bằng BGE-M3',        self._add_semantic_filter)
        self._act_fuzzy_dedup = act('AI Dedup',   'Fuzzy dedup bằng BGE-M3',            self._add_fuzzy_dedup)
        self._act_cross_match = act('AI Match',   'Cross-file match giữa 2 frames',     self._add_cross_match)
        tb.addSeparator()
        self._act_undo        = act('Undo',        'Undo last step  (Ctrl+Z)',           self._undo_step)
        self._act_reset       = act('Reset',       'Reset to original data',             self._reset_data)
        tb.addSeparator()
        self._act_code        = act('View Code',   'Show generated pandas code',         self._show_code)

        self._data_actions = [
            self._act_export, self._act_refresh, self._act_save_recipe,
            self._act_filter, self._act_drop_cols, self._act_dedup,
            self._act_sort, self._act_rename, self._act_fillna,
            self._act_rm_top, self._act_header, self._act_group,
            self._act_flatten, self._act_expand,
            self._act_fuzzy_dedup, self._act_cross_match,
            self._act_semantic,
            self._act_undo, self._act_reset, self._act_code,
        ]

    def _create_central_widget(self):
        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        self.setCentralWidget(central)

        # Query sidebar (leftmost)
        self._query_sidebar = QuerySidebar(self)
        self._query_sidebar.sig_query_selected.connect(self._switch_query)
        self._query_sidebar.sig_query_refresh.connect(self._on_sidebar_refresh)
        self._query_sidebar.sig_query_export.connect(self._on_sidebar_export)
        self._query_sidebar.sig_query_rename.connect(self._on_sidebar_rename)
        self._query_sidebar.sig_query_delete.connect(self._on_sidebar_delete)
        self._query_sidebar.sig_add_file_query.connect(self._add_file_query)
        self._query_sidebar.sig_add_merge_query.connect(self._add_merge_query)
        self._query_sidebar.sig_add_append_query.connect(self._add_append_query)
        layout.addWidget(self._query_sidebar)

        h_splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(h_splitter)

        # Left column: pipeline + store panels stacked vertically
        left_splitter = QSplitter(Qt.Vertical)
        left_splitter.setObjectName('left_splitter')
        left_splitter.setFixedWidth(270)
        left_splitter.setChildrenCollapsible(False)
        left_splitter.addWidget(self._build_pipeline_panel())
        left_splitter.addWidget(self._build_store_panel())
        left_splitter.setSizes([510, 210])

        h_splitter.addWidget(left_splitter)
        h_splitter.addWidget(self._build_table_panel())
        h_splitter.setSizes([270, 1050])
        h_splitter.setStretchFactor(0, 0)
        h_splitter.setStretchFactor(1, 1)

    def _build_pipeline_panel(self):
        panel = QFrame()
        panel.setObjectName('pipeline_panel')
        panel.setFrameShape(QFrame.StyledPanel)
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        title = QLabel('Pipeline Steps')
        title.setObjectName('panel_title')
        lay.addWidget(title)

        self.pipeline_list = QListWidget()
        self.pipeline_list.setObjectName('pipeline_list')
        self.pipeline_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.pipeline_list.currentRowChanged.connect(self._on_step_selected)
        self._pipeline_delegate = _PipelineDeleteDelegate(self.pipeline_list)
        self.pipeline_list.setItemDelegate(self._pipeline_delegate)
        self.pipeline_list.viewport().installEventFilter(self)
        lay.addWidget(self.pipeline_list)

        btn_row = QHBoxLayout()
        self._btn_undo = QPushButton('Undo')
        self._btn_undo.setObjectName('btn_secondary')
        self._btn_undo.clicked.connect(self._undo_step)
        self._btn_reset = QPushButton('Reset')
        self._btn_reset.setObjectName('btn_danger')
        self._btn_reset.clicked.connect(self._reset_data)
        btn_row.addWidget(self._btn_undo)
        btn_row.addWidget(self._btn_reset)
        lay.addLayout(btn_row)

        self._btn_code = QPushButton('View Pandas Code')
        self._btn_code.setObjectName('btn_code')
        self._btn_code.clicked.connect(self._show_code)
        lay.addWidget(self._btn_code)

        return panel

    def _build_table_panel(self):
        panel = QFrame()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._empty_label = QLabel('Open a CSV or Excel file to get started\n(File > Open   or   Ctrl+O)')
        self._empty_label.setObjectName('empty_label')
        self._empty_label.setAlignment(Qt.AlignCenter)
        lay.addWidget(self._empty_label)

        self._table_view = QTableView()
        self._table_view.setObjectName('data_table')
        self._table_view.setAlternatingRowColors(True)
        self._table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table_view.verticalHeader().setDefaultSectionSize(24)
        self._table_view.setShowGrid(True)

        self._col_header = SelectableHeaderView(self._table_view)
        self._col_header.setMinimumSectionSize(80)
        self._col_header.setFixedHeight(40)
        self._col_header.sig_drop_columns.connect(self._on_header_drop_columns)
        self._col_header.sig_filter_column.connect(self._on_header_filter_column)
        self._col_header.sig_filter_not_empty.connect(self._on_header_filter_not_empty)
        self._col_header.sig_rename_column.connect(self._on_header_rename_column)
        self._col_header.sig_cast_column.connect(self._on_header_cast_column)
        self._col_header.sig_selection_changed.connect(self._on_col_selection_changed)
        self._col_header.sig_add_index_column.connect(self._on_header_add_index)
        self._table_view.setHorizontalHeader(self._col_header)

        self._col_delegate = ColumnHighlightDelegate(self._col_header, self._table_view)
        self._table_view.setItemDelegate(self._col_delegate)

        self._model = PandasModel()
        self._table_view.setModel(self._model)
        self._table_view.hide()
        lay.addWidget(self._table_view)

        return panel

    def _build_store_panel(self):
        panel = QFrame()
        panel.setObjectName('store_panel')
        panel.setFrameShape(QFrame.StyledPanel)
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(10, 8, 10, 10)
        lay.setSpacing(6)

        # Header row: title + frame count badge
        hdr = QHBoxLayout()
        title = QLabel('Stored Frames')
        title.setObjectName('panel_title')
        hdr.addWidget(title)
        hdr.addStretch()
        self._lbl_store_count = QLabel('')
        self._lbl_store_count.setObjectName('store_count_badge')
        hdr.addWidget(self._lbl_store_count)
        lay.addLayout(hdr)

        # Frame list
        self._store_list = QListWidget()
        self._store_list.setObjectName('store_list')
        self._store_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._store_list.currentRowChanged.connect(self._on_stored_selected)
        lay.addWidget(self._store_list)

        # Action buttons: ← Back | Duplicate | Delete
        btn_row = QHBoxLayout()
        self._btn_store_back = QPushButton('← Back')
        self._btn_store_back.setObjectName('btn_store_back')
        self._btn_store_back.setToolTip('Exit stored frame preview, return to pipeline view')
        self._btn_store_back.clicked.connect(self._exit_stored_view)
        self._btn_store_dup = QPushButton('Duplicate')
        self._btn_store_dup.setObjectName('btn_secondary')
        self._btn_store_dup.setToolTip('Clone selected frame')
        self._btn_store_dup.clicked.connect(self._duplicate_stored)
        self._btn_store_del = QPushButton('Delete')
        self._btn_store_del.setObjectName('btn_danger')
        self._btn_store_del.setToolTip('Remove selected frame from store')
        self._btn_store_del.clicked.connect(self._delete_stored)
        btn_row.addWidget(self._btn_store_back)
        btn_row.addWidget(self._btn_store_dup)
        btn_row.addWidget(self._btn_store_del)
        lay.addLayout(btn_row)

        # Save button
        self._btn_store_save = QPushButton('+ Save Current Frame')
        self._btn_store_save.setObjectName('btn_store_save')
        self._btn_store_save.setToolTip('Snapshot the current DataFrame into the store')
        self._btn_store_save.clicked.connect(self._save_current_to_store)
        self._btn_store_save.setEnabled(False)
        lay.addWidget(self._btn_store_save)

        self._update_store_buttons()
        return panel

    def _create_status_bar(self):
        sb = QStatusBar()
        self.setStatusBar(sb)

        self._lbl_shape = QLabel('—')
        self._lbl_shape.setStyleSheet('color: #DDDDDD; font-size: 11px; padding: 0 12px 0 8px;')
        sb.addWidget(self._lbl_shape)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.VLine)
        sep1.setStyleSheet('color: #555555;')
        sb.addWidget(sep1)

        self._lbl_steps = QLabel('0 step(s)')
        self._lbl_steps.setStyleSheet('color: #AAAAAA; font-size: 11px; padding: 0 12px;')
        sb.addWidget(self._lbl_steps)

        self._lbl_preview = QLabel('')
        self._lbl_preview.setStyleSheet(
            'color: #1C1917; background: #F59E0B; font-size: 10px; font-weight: bold;'
            'padding: 2px 8px; border-radius: 3px; margin: 0 6px;'
        )
        self._lbl_preview.hide()
        sb.addWidget(self._lbl_preview)

        self._lbl_aggregate = QLabel('')
        self._lbl_aggregate.setStyleSheet('color: #86EFAC; font-size: 11px; font-weight: bold; padding: 0 14px;')
        sb.addPermanentWidget(self._lbl_aggregate)

        self._lbl_source = QLabel('')
        self._lbl_source.setStyleSheet('color: #777777; font-size: 11px; padding: 0 8px;')
        sb.addPermanentWidget(self._lbl_source)

    # ---------------------------------------------------------------- actions

    def _update_recent_menu(self):
        self._recent_menu.clear()
        paths = recent_projects()
        if not paths:
            a = QAction('(no recent projects)', self)
            a.setEnabled(False)
            self._recent_menu.addAction(a)
        else:
            for path in paths:
                name = os.path.basename(path)
                a = QAction(name, self)
                a.setStatusTip(path)
                a.triggered.connect(lambda checked, p=path: self._load_project(p))
                self._recent_menu.addAction(a)

    def _set_data_actions_enabled(self, enabled: bool):
        for a in self._data_actions:
            a.setEnabled(enabled)
        self._btn_undo.setEnabled(enabled)
        self._btn_reset.setEnabled(enabled)
        self._btn_code.setEnabled(enabled)
        self._btn_store_save.setEnabled(enabled)

    def _add_file_query(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 'Add Query — Open Data File', '',
            'Data Files (*.csv *.xlsx *.xls);;CSV (*.csv);;Excel (*.xlsx *.xls)'
        )
        if not path:
            return
        try:
            sheet_name = None
            csv_sep = 'auto'
            decimal = ','

            if path.lower().endswith('.csv'):
                detected = detect_csv_sep(path)
                dlg = CsvImportDialog(path, detected, self)
                if dlg.exec_():
                    csv_sep = dlg.get_sep()
                    decimal = dlg.get_decimal()
                else:
                    return
            else:
                sheets = DataEngine.get_sheet_names(path)
                if len(sheets) > 1:
                    dlg = SheetPickerDialog(sheets, os.path.basename(path), self)
                    if dlg.exec_():
                        sheet_name = dlg.selected_sheet()
                    else:
                        return

            base = os.path.splitext(os.path.basename(path))[0]
            if sheet_name:
                base += f'_{sheet_name}'
            query_name = self.project.unique_query_name(base)

            source = FileSource(path=path, sheet_name=sheet_name,
                                decimal=decimal, csv_sep=csv_sep)
            q = QueryDef(name=query_name, source=source)
            self.project.add_query(q)

            eng = DataEngine()
            rec = Recipe(query_name)
            self._query_engines[query_name] = eng
            self._query_recipes[query_name] = rec

            eng.load(path, sheet_name=sheet_name, csv_sep=csv_sep, decimal=decimal)

            self._project_modified = True
            self._switch_query(query_name)
            self._mark_modified_and_autosave()

        except Exception as exc:
            QMessageBox.critical(self, 'Load Error', f'Could not load file:\n{exc}')

    def _export_file(self):
        if self.engine.current is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, 'Export Data', '',
            'CSV (*.csv);;Excel (*.xlsx)'
        )
        if not path:
            return
        try:
            self.engine.export(path)
            QMessageBox.information(self, 'Exported', f'File saved:\n{path}')
        except Exception as exc:
            QMessageBox.critical(self, 'Export Error', str(exc))

    def _save_recipe(self):
        if not self.recipe.steps:
            QMessageBox.information(self, 'Empty Pipeline', 'No steps to save yet.')
            return
        os.makedirs('config', exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(
            self, 'Save Recipe', 'config', 'Recipe (*.json)'
        )
        if not path:
            return
        try:
            self.recipe.save(path)
            QMessageBox.information(self, 'Saved', f'Recipe saved:\n{path}')
        except Exception as exc:
            QMessageBox.critical(self, 'Save Error', str(exc))

    def _load_recipe(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 'Load Recipe', 'config', 'Recipe (*.json)'
        )
        if not path:
            return
        try:
            self.recipe = Recipe.load(path)
            if self.engine.original is not None:
                df = self.engine.rebuild(self.recipe.steps)
                self._refresh_table(df)
                self._refresh_pipeline()
                self._update_status()
                self._update_filter_highlights()
            QMessageBox.information(self, 'Loaded', f'Recipe loaded:\n{path}')
        except Exception as exc:
            QMessageBox.critical(self, 'Load Error', str(exc))

    # ---- transform triggers ------------------------------------------------

    def _add_filter(self):
        self._run_dialog(FilterDialog, list(self.engine.current.columns))

    def _add_drop_columns(self):
        self._run_dialog(DropColumnsDialog, list(self.engine.current.columns))

    def _add_drop_duplicates(self):
        self._apply_step({'operation': 'drop_duplicates', 'params': {}})

    def _add_sort(self):
        self._run_dialog(SortDialog, list(self.engine.current.columns))

    def _add_rename(self):
        self._run_dialog(RenameColumnDialog, list(self.engine.current.columns))

    def _add_fillna(self):
        self._run_dialog(FillNADialog, list(self.engine.current.columns))

    def _add_remove_top_rows(self):
        if self.engine.current is None:
            return
        dlg = RemoveTopRowsDialog(len(self.engine.current), self)
        if dlg.exec_():
            self._apply_step(dlg.get_step())

    def _add_use_first_row_as_header(self):
        if self.engine.current is None:
            return
        if len(self.engine.current) == 0:
            QMessageBox.warning(self, 'Empty Data', 'Không có dòng nào để dùng làm header.')
            return
        self._apply_step({'operation': 'use_first_row_as_header', 'params': {}})

    def _add_group_rows(self):
        self._run_dialog(GroupRowsDialog, list(self.engine.current.columns))

    def _add_flatten_hierarchy(self):
        if self.engine is None or self.engine.current is None:
            return
        dlg = FlattenHierarchyDialog(self.engine.current, self)
        if dlg.exec_():
            step = dlg.get_step()
            if step:
                self._apply_step(step)

    def _add_expand_hierarchy(self):
        if self.engine is None or self.engine.current is None:
            return
        dlg = ExpandHierarchyDialog(self.engine.current, self)
        if dlg.exec_():
            step = dlg.get_step()
            if step:
                self._apply_step(step)

    def _add_semantic_filter(self):
        if self.engine.current is None:
            return
        dlg = SemanticFilterDialog(self.engine.current, list(self.engine.current.columns), self)
        if dlg.exec_():
            step = dlg.get_step()
            if step:
                self._apply_step(step)

    def _add_fuzzy_dedup(self):
        if self.engine.current is None:
            return
        dlg = FuzzyDedupDialog(self.engine.current, list(self.engine.current.columns), self)
        if dlg.exec_():
            step = dlg.get_step()
            if step:
                self._apply_step(step)

    def _add_cross_match(self):
        if self.engine.current is None:
            return
        if not self._stored_frames:
            QMessageBox.information(
                self, 'AI Cross-file Match',
                'Cần ít nhất 1 Stored Frame làm tham chiếu.\n'
                'Lưu một DataFrame vào Store trước.'
            )
            return
        dlg = CrossFileMatchDialog(self.engine.current, self._stored_frames, self)
        if dlg.exec_():
            result_df   = dlg.get_result_df()
            result_name = dlg.get_result_name()
            if result_df is not None:
                source = os.path.basename(self.engine.source_path) if self.engine.source_path else '—'
                self._stored_frames.append({
                    'name':   result_name,
                    'df':     result_df,
                    'source': f'AI Match ← {source}',
                    'steps':  len(self.recipe.steps),
                })
                self._refresh_store()
                QMessageBox.information(
                    self, 'AI Cross-file Match',
                    f'Kết quả "{result_name}" đã được lưu vào Stored Frames.'
                )

    def _run_dialog(self, DialogClass, columns):
        if self.engine.current is None:
            return
        dlg = DialogClass(columns, self)
        if dlg.exec_():
            self._apply_step(dlg.get_step())

    def _apply_step(self, step):
        try:
            df = self.engine.apply_step(step)
            self.recipe.add_step(step)
            self._mark_modified_and_autosave()
            self._refresh_table(df)
            self._refresh_pipeline()
            self._update_status()
            self._update_filter_highlights()
        except Exception as exc:
            QMessageBox.critical(self, 'Transform Error', str(exc))

    def _on_header_drop_columns(self, cols: list):
        self._apply_step({'operation': 'drop_columns', 'params': {'columns': cols}})
        self._col_header.clear_selection()

    def _on_header_filter_column(self, col_name: str):
        if self.engine.current is None:
            return
        cols = list(self.engine.current.columns)
        dlg = FilterDialog(cols, self, preselect=col_name)
        if dlg.exec_():
            self._apply_step(dlg.get_step())

    def _on_header_filter_not_empty(self, col_name: str):
        self._apply_step({
            'operation': 'filter',
            'params': {'column': col_name, 'condition': 'is_not_empty', 'value': ''},
        })

    def _on_header_rename_column(self, col_name: str):
        if self.engine.current is None:
            return
        cols = list(self.engine.current.columns)
        dlg = RenameColumnDialog(cols, self, preselect=col_name)
        if dlg.exec_():
            self._apply_step(dlg.get_step())

    def _on_header_cast_column(self, col_name: str, to_type: str):
        self._apply_step({
            'operation': 'cast_column',
            'params': {'column': col_name, 'to_type': to_type},
        })

    def _on_header_add_index(self):
        self._apply_step({'operation': 'add_index_column', 'params': {}})

    def _on_col_selection_changed(self, col_indices: list):
        if not col_indices:
            self._lbl_aggregate.setText('')
            return
        df = self._model.dataFrame()
        if df is None or df.empty:
            self._lbl_aggregate.setText('')
            return
        hints = self._model.column_type_hints()
        dec = self.engine.decimal if self.engine.current is not None else ','

        numeric_idx = [i for i in col_indices if hints.get(i) == 'numeric' and i < len(df.columns)]
        text_idx    = [i for i in col_indices if hints.get(i) != 'numeric' and i < len(df.columns)]

        parts = []
        if numeric_idx:
            total = 0.0
            for ci in numeric_idx:
                nums = to_numeric_vn(df.iloc[:, ci].astype(str), decimal=dec)
                total += float(nums.sum(skipna=True))
            parts.append(f'Sum: {_fmt_agg(total, dec)}')
        if text_idx:
            count = sum(
                int(df.iloc[:, ci].dropna().astype(str).str.strip().ne('').sum())
                for ci in text_idx
            )
            parts.append(f'Count: {count:,}')
        self._lbl_aggregate.setText('   '.join(parts))

    def _update_filter_highlights(self):
        filtered = {s['params']['column'] for s in self.recipe.steps
                    if s['operation'] == 'filter'}
        self._col_header.set_active_filters(filtered)

    def _on_step_selected(self, row: int):
        """Preview data state at a clicked pipeline step (no engine state change)."""
        if self._refreshing_pipeline or self.engine.original is None:
            return
        n = len(self.recipe.steps)
        if row < 0 or row >= n:
            return
        # Deselect stored frame view when user returns to pipeline
        self._store_list.blockSignals(True)
        self._store_list.setCurrentRow(-1)
        self._store_list.blockSignals(False)
        self._update_store_buttons()
        if row == n - 1:
            # Last step = full pipeline = no preview needed
            self._model.setDataFrame(self.engine.current)
            self._col_header.set_type_hints(self._model.column_type_hints())
            self._update_status()
            return
        try:
            preview_df = self.engine.rebuild_preview(self.recipe.steps[:row + 1])
        except Exception as exc:
            QMessageBox.warning(self, 'Preview Error',
                                f'Không thể xem trước step {row + 1}:\n{exc}')
            return
        self._model.setDataFrame(preview_df)
        self._col_header.set_type_hints(self._model.column_type_hints())
        self._update_status(preview_idx=row, df=preview_df)

    # --------------------------------------------------------- stored frames

    def _on_stored_selected(self, row: int):
        """Preview a stored frame in the table (no engine state change)."""
        self._update_store_buttons()
        if row < 0 or row >= len(self._stored_frames):
            return
        entry = self._stored_frames[row]
        self._model.setDataFrame(entry['df'])
        self._col_header.set_type_hints(self._model.column_type_hints())
        r, c = entry['df'].shape
        self._lbl_shape.setText(f'{r:,} rows  ×  {c} cols')
        self._lbl_steps.setText(f"{entry['steps']} step(s) at save")
        self._lbl_preview.setText(f"  STORED: {entry['name']}  ")
        self._lbl_preview.show()
        # Deselect pipeline list
        self._refreshing_pipeline = True
        self.pipeline_list.blockSignals(True)
        self.pipeline_list.setCurrentRow(-1)
        self.pipeline_list.blockSignals(False)
        self._refreshing_pipeline = False

    def _save_current_to_store(self):
        if self.engine.current is None:
            return
        n = len(self._stored_frames) + 1
        source = os.path.basename(self.engine.source_path) if self.engine.source_path else '—'
        default_name = f'Frame {n}'
        name, ok = QInputDialog.getText(
            self, 'Save Frame to Store', 'Tên frame:', text=default_name
        )
        if not ok or not name.strip():
            return
        self._stored_frames.append({
            'name': name.strip(),
            'df': self.engine.current.copy(),
            'source': source,
            'steps': len(self.recipe.steps),
        })
        self._refresh_store()

    def _duplicate_stored(self):
        row = self._store_list.currentRow()
        if row < 0 or row >= len(self._stored_frames):
            return
        entry = self._stored_frames[row]
        new_entry = {**entry, 'name': entry['name'] + ' (copy)', 'df': entry['df'].copy()}
        self._stored_frames.insert(row + 1, new_entry)
        self._refresh_store()
        self._store_list.setCurrentRow(row + 1)

    def _delete_stored(self):
        row = self._store_list.currentRow()
        if row < 0 or row >= len(self._stored_frames):
            return
        name = self._stored_frames[row]['name']
        reply = QMessageBox.question(
            self, 'Delete Stored Frame', f'Xóa frame "{name}"?',
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        self._stored_frames.pop(row)
        self._refresh_store()
        self._restore_current_view()

    def _exit_stored_view(self):
        self._store_list.blockSignals(True)
        self._store_list.setCurrentRow(-1)
        self._store_list.blockSignals(False)
        self._update_store_buttons()
        self._restore_current_view()

    def _restore_current_view(self):
        if self.engine.current is not None:
            self._model.setDataFrame(self.engine.current)
            self._col_header.set_type_hints(self._model.column_type_hints())
            self._update_status()

    def _refresh_store(self):
        self._store_list.blockSignals(True)
        self._store_list.clear()
        for entry in self._stored_frames:
            r, c = entry['df'].shape
            item = QListWidgetItem(
                f"{entry['name']}\n  {r:,} × {c}  |  {entry['source']}"
            )
            self._store_list.addItem(item)
        self._store_list.blockSignals(False)
        count = len(self._stored_frames)
        self._lbl_store_count.setText(str(count) if count else '')
        self._update_store_buttons()

    def _update_store_buttons(self):
        has = self._store_list.currentRow() >= 0
        self._btn_store_back.setEnabled(has)
        self._btn_store_dup.setEnabled(has)
        self._btn_store_del.setEnabled(has)

    # ---------------------------------------------------------

    def _delete_step(self, idx: int):
        n = len(self.recipe.steps)
        if idx < 0 or idx >= n:
            return
        removed = self.recipe.steps.pop(idx)
        try:
            df = self.engine.rebuild(self.recipe.steps)
        except Exception as exc:
            self.recipe.steps.insert(idx, removed)
            QMessageBox.critical(
                self, 'Delete Failed',
                f'Không thể xóa step {idx + 1} — các step sau phụ thuộc vào nó:\n{exc}\n\nStep đã được khôi phục.'
            )
            return
        new_select = min(idx, len(self.recipe.steps) - 1)
        self._mark_modified_and_autosave()
        self._refresh_table(df)
        self._refresh_pipeline(select_idx=new_select)
        self._update_status()
        self._update_filter_highlights()

    def _undo_step(self):
        if not self.recipe.steps:
            return
        removed = self.recipe.steps.pop()
        try:
            df = self.engine.rebuild(self.recipe.steps)
        except Exception as exc:
            self.recipe.steps.append(removed)
            QMessageBox.critical(self, 'Undo Error', str(exc))
            return
        self._mark_modified_and_autosave()
        self._refresh_table(df)
        self._refresh_pipeline()
        self._update_status()
        self._update_filter_highlights()

    def _reset_data(self):
        if self.engine.original is None:
            return
        reply = QMessageBox.question(
            self, 'Reset',
            'Reset to original data? All pipeline steps will be cleared.',
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            df = self.engine.reset()
            self.recipe.steps.clear()
            self._col_header.clear_selection()
            self._mark_modified_and_autosave()
            self._refresh_table(df)
            self._refresh_pipeline()
            self._update_status()
            self._update_filter_highlights()

    def _show_code(self):
        code = self.recipe.to_pandas_code(self.engine.source_path)
        dlg = CodePreviewDialog(code, self)
        dlg.exec_()

    # ---------------------------------------------------------------- refresh

    def _refresh_table(self, df):
        # If a stored frame is being previewed, deselect it — pipeline wins
        if self._store_list.currentRow() >= 0:
            self._store_list.blockSignals(True)
            self._store_list.setCurrentRow(-1)
            self._store_list.blockSignals(False)
            self._update_store_buttons()
        self._model.setDataFrame(df)
        self._col_header.set_type_hints(self._model.column_type_hints())
        for col in range(self._model.columnCount()):
            self._table_view.setColumnWidth(col, max(100, min(220, 20 * len(str(df.columns[col])))))

    def _refresh_pipeline(self, select_idx: int = -1):
        self._refreshing_pipeline = True
        self.pipeline_list.blockSignals(True)
        self.pipeline_list.clear()
        for i, step in enumerate(self.recipe.steps):
            op = step['operation']
            label, color = _STEP_META.get(op, (op, '#888888'))
            detail = self._step_detail(op, step.get('params', {}))
            item = QListWidgetItem(f'{i + 1}.  {label}\n      {detail}')
            item.setForeground(QColor(color))
            self.pipeline_list.addItem(item)
        if self.recipe.steps:
            target = select_idx if 0 <= select_idx < len(self.recipe.steps) else len(self.recipe.steps) - 1
            self.pipeline_list.setCurrentRow(target)
        self.pipeline_list.blockSignals(False)
        self._refreshing_pipeline = False

    @staticmethod
    def _step_detail(op, p):
        if op == 'filter':
            return f"{p.get('column')}  {p.get('condition')}  '{p.get('value', '')}'"
        if op == 'drop_columns':
            cols = p.get('columns', [])
            return ', '.join(cols[:4]) + ('…' if len(cols) > 4 else '')
        if op == 'drop_duplicates':
            return 'all columns'
        if op == 'rename_column':
            return f"{p.get('old_name')}  →  {p.get('new_name')}"
        if op == 'sort':
            direction = 'ASC ↑' if p.get('ascending', True) else 'DESC ↓'
            return f"{p.get('column')}  {direction}"
        if op == 'fillna':
            col = p.get('column')
            col_label = '(all)' if col == '__all__' else col
            return f"{col_label}  ←  '{p.get('value', '')}'"
        if op == 'remove_top_rows':
            n = p.get('n', 1)
            return f"bỏ {n} dòng đầu"
        if op == 'use_first_row_as_header':
            return 'dòng 1 → tên cột'
        if op == 'cast_column':
            col = p.get('column', '')
            _type_labels = {'numeric': 'Number (123)', 'date': 'Date (DT)', 'text': 'Text (ABC)'}
            to_type = _type_labels.get(p.get('to_type'), 'Text (ABC)')
            return f"{col}  →  {to_type}"
        if op == 'group_rows':
            by_cols = p.get('by', [])
            agg = p.get('aggregations', {})
            by_str = ', '.join(by_cols) if by_cols else '—'
            agg_parts = [f"{c}→{f}" for c, f in list(agg.items())[:3]]
            agg_str = ', '.join(agg_parts) + ('…' if len(agg) > 3 else '')
            return f"by: {by_str}  |  {agg_str}"
        if op == 'add_index_column':
            col = p.get('col_name', 'STT')
            return f'cột "{col}" = 1, 2, 3…'
        if op == 'semantic_filter':
            col   = p.get('column', '')
            query = p.get('query', '')
            thr   = p.get('threshold', 0.7)
            short = query[:30] + '…' if len(query) > 30 else query
            return f'{col}  |  "{short}"  ≥{thr}'
        if op == 'semantic_dedup':
            col = p.get('column', '')
            thr = p.get('threshold', 0.85)
            return f'{col}  |  threshold ≥{thr}'
        return ''

    def _update_status(self, preview_idx: int = None, df=None):
        if self.engine is None or self.engine.current is None:
            self._lbl_shape.setText('—')
            self._lbl_steps.setText('0 step(s)')
            self._lbl_preview.hide()
            self._lbl_source.setText('')
            return
        display = df if df is not None else self.engine.current
        rows, cols = display.shape
        self._lbl_shape.setText(f'{rows:,} rows  ×  {cols} cols')
        self._lbl_steps.setText(f'{len(self.recipe.steps)} step(s)')
        if preview_idx is not None:
            n = len(self.recipe.steps)
            self._lbl_preview.setText(f'  PREVIEW  Step {preview_idx + 1} / {n}  ')
            self._lbl_preview.show()
        else:
            self._lbl_preview.hide()
        src = self.engine.source_path
        self._lbl_source.setText(os.path.basename(src) if src else self._active_query or '')

    # ----------------------------------------------------------------- project

    def _update_title(self):
        if self.project.path:
            proj_name = os.path.splitext(os.path.basename(self.project.path))[0]
        else:
            proj_name = self.project.name
        mod = ' *' if self._project_modified else ''
        if self._active_query:
            self.setWindowTitle(f'{proj_name}{mod}  —  {self._active_query}  —  MPowerQueryPython')
        else:
            self.setWindowTitle(f'{proj_name}{mod}  —  MPowerQueryPython')

    def _switch_query(self, name: str):
        if name not in self._query_engines:
            return
        self._active_query = name
        self.project.active_query = name
        eng = self.engine
        if eng is not None and eng.current is not None:
            self._col_header.clear_selection()
            self._model.set_decimal(eng.decimal)
            self._refresh_table(eng.current)
            self._refresh_pipeline()
            self._update_filter_highlights()
            self._set_data_actions_enabled(True)
            self._empty_label.hide()
            self._table_view.show()
        else:
            self._set_data_actions_enabled(False)
            self._empty_label.show()
            self._table_view.hide()
        self._update_status()
        self._update_title()
        self._query_sidebar.refresh(self.project, name)

    def _run_query(self, name: str):
        q = self.project.get_query(name)
        eng = self._query_engines.get(name)
        if eng is None:
            return
        rec = self._query_recipes.get(name)
        src = q.source

        if isinstance(src, FileSource):
            eng.load(src.path, sheet_name=src.sheet_name,
                     csv_sep=src.csv_sep, decimal=src.decimal)
        elif isinstance(src, QuerySource):
            dep = self._query_engines.get(src.query_name)
            if dep and dep.current is not None:
                eng.load_df(dep.current)
        elif isinstance(src, MergeSource):
            le = self._query_engines.get(src.left)
            re = self._query_engines.get(src.right)
            if le and re and le.current is not None and re.current is not None:
                merged = pd.merge(le.current, re.current, on=src.on, how=src.how)
                eng.load_df(merged, decimal=le.decimal)
        elif isinstance(src, AppendSource):
            dfs = [self._query_engines[n].current for n in src.queries
                   if n in self._query_engines and self._query_engines[n].current is not None]
            if dfs:
                eng.load_df(pd.concat(dfs, ignore_index=True))

        if eng.original is not None and rec:
            eng.rebuild(rec.steps)

    def _refresh_cascade(self, from_query: str):
        order = self.project.topo_order()
        try:
            start = order.index(from_query)
        except ValueError:
            return
        for name in order[start:]:
            try:
                self._run_query(name)
            except Exception as exc:
                QMessageBox.critical(self, 'Refresh Error',
                                     f'Lỗi khi chạy query "{name}":\n{exc}')
                break
        if self._active_query:
            eng = self.engine
            if eng and eng.current is not None:
                self._refresh_table(eng.current)
                self._refresh_pipeline()
                self._update_status()

    def _mark_modified_and_autosave(self):
        if self._active_query and self.recipe:
            try:
                q = self.project.get_query(self._active_query)
                q.recipe_steps = list(self.recipe.steps)
            except KeyError:
                pass
        self._project_modified = True
        self._update_title()
        if self.project.path:
            try:
                self.project.save(self.project.path)
                self._project_modified = False
                self._update_title()
            except Exception:
                pass

    def _sync_recipe_to_project(self):
        for name, rec in self._query_recipes.items():
            try:
                self.project.get_query(name).recipe_steps = list(rec.steps)
            except KeyError:
                pass

    # ---- project CRUD ------

    def _new_project(self):
        if self._project_modified:
            reply = QMessageBox.question(
                self, 'Unsaved Changes',
                'Project chưa lưu. Tiếp tục sẽ mất thay đổi. Tiếp tục?',
                QMessageBox.Yes | QMessageBox.No)
            if reply != QMessageBox.Yes:
                return
        self.project = Project('Untitled')
        self._query_engines.clear()
        self._query_recipes.clear()
        self._active_query = None
        self._project_modified = False
        self._stored_frames.clear()
        self._set_data_actions_enabled(False)
        self._empty_label.show()
        self._table_view.hide()
        self._model.setDataFrame(None)
        self._refresh_pipeline()
        self._refresh_store()
        self._query_sidebar.refresh(self.project, None)
        self._update_title()
        self._lbl_shape.setText('—')
        self._lbl_steps.setText('0 step(s)')
        self._lbl_source.setText('')

    def _open_project(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 'Open Project', 'config',
            'MPowerQuery Project (*.mpq);;All Files (*)')
        if path:
            self._load_project(path)

    def _load_project(self, path: str):
        try:
            proj = Project.load(path)
        except Exception as exc:
            QMessageBox.critical(self, 'Open Error', f'Could not open project:\n{exc}')
            return
        self.project = proj
        self._query_engines.clear()
        self._query_recipes.clear()
        for q in proj._queries:
            self._query_engines[q.name] = DataEngine()
            r = Recipe(q.name)
            r.steps = list(q.recipe_steps)
            self._query_recipes[q.name] = r
        try:
            for name in proj.topo_order():
                self._run_query(name)
        except Exception as exc:
            QMessageBox.critical(self, 'Build Error',
                                 f'Lỗi khi rebuild project:\n{exc}')
        self._active_query = proj.active_query
        self._project_modified = False
        self._stored_frames.clear()
        self._refresh_store()
        push_recent(path)
        self._update_recent_menu()
        if self._active_query:
            self._switch_query(self._active_query)
        self._update_title()

    def _save_project(self):
        if not self.project.path:
            self._save_project_as()
            return
        self._sync_recipe_to_project()
        try:
            self.project.save(self.project.path)
            self._project_modified = False
            push_recent(self.project.path)
            self._update_recent_menu()
            self._update_title()
        except Exception as exc:
            QMessageBox.critical(self, 'Save Error', str(exc))

    def _save_project_as(self):
        os.makedirs('config', exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(
            self, 'Save Project As', 'config',
            'MPowerQuery Project (*.mpq)')
        if not path:
            return
        if not path.endswith('.mpq'):
            path += '.mpq'
        self._sync_recipe_to_project()
        try:
            self.project.save(path)
            self._project_modified = False
            push_recent(path)
            self._update_recent_menu()
            self._update_title()
        except Exception as exc:
            QMessageBox.critical(self, 'Save Error', str(exc))

    # ---- toolbar / sidebar handlers ------

    def _on_toolbar_refresh(self):
        if self._active_query:
            self._refresh_cascade(self._active_query)

    def _on_sidebar_refresh(self, name: str):
        self._refresh_cascade(name)

    def _on_sidebar_export(self, name: str):
        eng = self._query_engines.get(name)
        if eng is None or eng.current is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, f'Export "{name}"', '',
            'CSV (*.csv);;Excel (*.xlsx)')
        if not path:
            return
        try:
            eng.export(path)
            QMessageBox.information(self, 'Exported', f'File saved:\n{path}')
        except Exception as exc:
            QMessageBox.critical(self, 'Export Error', str(exc))

    def _on_sidebar_rename(self, name: str):
        new_name, ok = QInputDialog.getText(
            self, 'Rename Query', 'Tên mới:', text=name)
        if not ok or not new_name.strip() or new_name.strip() == name:
            return
        new_name = new_name.strip()
        try:
            self.project.rename_query(name, new_name)
            self._query_engines[new_name] = self._query_engines.pop(name)
            self._query_recipes[new_name] = self._query_recipes.pop(name)
            if self._active_query == name:
                self._active_query = new_name
            self._mark_modified_and_autosave()
            self._query_sidebar.refresh(self.project, self._active_query)
            self._update_title()
        except ValueError as exc:
            QMessageBox.warning(self, 'Rename Error', str(exc))

    def _on_sidebar_delete(self, name: str):
        reply = QMessageBox.question(
            self, 'Delete Query', f'Xóa query "{name}"?',
            QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        try:
            self.project.remove_query(name)
            self._query_engines.pop(name, None)
            self._query_recipes.pop(name, None)
            self._mark_modified_and_autosave()
            if self._active_query == name:
                nxt = self.project.active_query
                if nxt:
                    self._switch_query(nxt)
                else:
                    self._active_query = None
                    self._set_data_actions_enabled(False)
                    self._empty_label.show()
                    self._table_view.hide()
            self._query_sidebar.refresh(self.project, self._active_query)
        except ValueError as exc:
            QMessageBox.warning(self, 'Delete Error', str(exc))

    def _add_merge_query(self):
        names = self.project.query_names()
        if len(names) < 2:
            QMessageBox.information(self, 'Merge Query',
                                    'Cần ít nhất 2 queries để merge.')
            return
        dlg = NewMergeQueryDialog(names, self)
        # Pre-populate on-column from left query's current columns
        left_eng = self._query_engines.get(names[0])
        if left_eng and left_eng.current is not None:
            dlg.set_columns(list(left_eng.current.columns))
        if not dlg.exec_():
            return
        source = dlg.get_source()
        query_name = self.project.unique_query_name(
            f'Merge_{source.left}_{source.right}')
        try:
            q = QueryDef(name=query_name, source=source)
            self.project.add_query(q)
            eng = DataEngine()
            rec = Recipe(query_name)
            self._query_engines[query_name] = eng
            self._query_recipes[query_name] = rec
            self._run_query(query_name)
            self._project_modified = True
            self._switch_query(query_name)
            self._mark_modified_and_autosave()
        except Exception as exc:
            QMessageBox.critical(self, 'Merge Error', str(exc))

    def _add_append_query(self):
        names = self.project.query_names()
        if len(names) < 2:
            QMessageBox.information(self, 'Append Query',
                                    'Cần ít nhất 2 queries để append.')
            return
        dlg = NewAppendQueryDialog(names, self)
        if not dlg.exec_():
            return
        source = dlg.get_source()
        query_name = self.project.unique_query_name('Append_Query')
        try:
            q = QueryDef(name=query_name, source=source)
            self.project.add_query(q)
            eng = DataEngine()
            rec = Recipe(query_name)
            self._query_engines[query_name] = eng
            self._query_recipes[query_name] = rec
            self._run_query(query_name)
            self._project_modified = True
            self._switch_query(query_name)
            self._mark_modified_and_autosave()
        except Exception as exc:
            QMessageBox.critical(self, 'Append Error', str(exc))

    # ----------------------------------------------------------------- style

    def _apply_style(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #F0F2F5; }

            QMenuBar {
                background-color: #2B2D30;
                color: #CCCCCC;
                font-size: 12px;
                padding: 2px 4px;
            }
            QMenuBar::item:selected { background-color: #4A90E2; color: white; }
            QMenu {
                background-color: #3C3F41;
                color: #BBBBBB;
                border: 1px solid #555;
            }
            QMenu::item:selected { background-color: #4A90E2; color: white; }

            QToolBar {
                background-color: #3C3F41;
                border-bottom: 1px solid #2B2D30;
                padding: 3px 6px;
                spacing: 2px;
            }
            QToolBar QToolButton {
                color: #DDDDDD;
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 12px;
            }
            QToolBar QToolButton:hover {
                background-color: #4A90E2;
                color: white;
                border-color: #357ABD;
            }
            QToolBar QToolButton:disabled { color: #666666; }
            QToolBar::separator {
                background-color: #555555;
                width: 1px;
                margin: 4px 4px;
            }

            #pipeline_panel {
                background-color: #FFFFFF;
                border: 1px solid #DEE2E6;
                border-radius: 6px;
            }
            #panel_title {
                font-size: 13px;
                font-weight: bold;
                color: #343A40;
                padding-bottom: 2px;
            }
            #pipeline_list {
                background-color: #FAFBFC;
                border: 1px solid #E9ECEF;
                border-radius: 4px;
                font-size: 11px;
                padding: 4px;
            }
            #pipeline_list::item {
                padding: 6px 6px;
                border-bottom: 1px solid #F0F0F0;
                border-radius: 3px;
            }
            #pipeline_list::item:selected { background-color: #1E1E1E; border-radius: 3px; }
            #pipeline_list::item:selected:!active { background-color: transparent; border-radius: 3px; }

            QPushButton#btn_secondary {
                background-color: #6C757D; color: white;
                border: none; border-radius: 4px;
                padding: 5px 12px; font-size: 11px;
            }
            QPushButton#btn_secondary:hover { background-color: #5A6268; }
            QPushButton#btn_danger {
                background-color: #DC3545; color: white;
                border: none; border-radius: 4px;
                padding: 5px 12px; font-size: 11px;
            }
            QPushButton#btn_danger:hover { background-color: #C82333; }
            QPushButton#btn_code {
                background-color: #343A40; color: #CCCCCC;
                border: none; border-radius: 4px;
                padding: 5px 12px; font-size: 11px;
            }
            QPushButton#btn_code:hover { background-color: #23272B; color: white; }

            #data_table {
                background-color: #FFFFFF;
                alternate-background-color: #F7F9FC;
                gridline-color: #E8EAED;
                font-size: 12px;
                selection-background-color: #D2E3FC;
                selection-color: #202124;
            }
            QHeaderView::section {
                background-color: #4A90E2;
                color: white;
                padding: 5px 8px;
                border: none;
                border-right: 1px solid #357ABD;
                font-weight: bold;
                font-size: 11px;
            }
            QHeaderView::section:vertical {
                background-color: #F1F3F4;
                color: #5F6368;
                border: none;
                border-bottom: 1px solid #E8EAED;
                font-weight: normal;
            }

            #empty_label {
                color: #9AA0A6;
                font-size: 15px;
                background-color: #FFFFFF;
                border: 2px dashed #DEE2E6;
                border-radius: 8px;
                margin: 24px;
            }

            QStatusBar {
                background-color: #2B2D30;
                color: #AAAAAA;
                font-size: 11px;
            }

            #store_panel {
                background-color: #FFFFFF;
                border: 1px solid #DEE2E6;
                border-radius: 6px;
            }
            #store_list {
                background-color: #FAFBFC;
                border: 1px solid #E9ECEF;
                border-radius: 4px;
                font-size: 11px;
                padding: 4px;
            }
            #store_list::item {
                padding: 5px 6px;
                border-bottom: 1px solid #F0F0F0;
                border-radius: 3px;
                color: #495057;
            }
            #store_list::item:selected {
                background-color: #E3F2FD;
                color: #1565C0;
                border-radius: 3px;
            }
            #store_list::item:selected:!active {
                background-color: transparent;
                border-radius: 3px;
            }

            QPushButton#btn_store_save {
                background-color: #2196F3; color: white;
                border: none; border-radius: 4px;
                padding: 5px 12px; font-size: 11px; font-weight: bold;
            }
            QPushButton#btn_store_save:hover { background-color: #1976D2; }
            QPushButton#btn_store_save:disabled { background-color: #BBDEFB; color: #90CAF9; }

            QPushButton#btn_store_back {
                background-color: #78909C; color: white;
                border: none; border-radius: 4px;
                padding: 5px 8px; font-size: 11px;
            }
            QPushButton#btn_store_back:hover { background-color: #607D8B; }
            QPushButton#btn_store_back:disabled { background-color: #CFD8DC; color: #B0BEC5; }

            #store_count_badge {
                background-color: #4A90E2; color: white;
                border-radius: 8px; padding: 1px 6px;
                font-size: 10px; font-weight: bold;
            }

            QSplitter#left_splitter::handle {
                background-color: #DEE2E6;
                height: 5px;
            }

            #query_sidebar {
                background-color: #1E293B;
                border-right: 1px solid #334155;
            }
            #sidebar_title {
                font-size: 11px;
                font-weight: bold;
                color: #64748B;
                text-transform: uppercase;
                letter-spacing: 1px;
                padding: 0 2px 4px 2px;
            }
            #sidebar_count {
                background-color: #334155; color: #94A3B8;
                border-radius: 8px; padding: 1px 6px;
                font-size: 10px; font-weight: bold;
            }
            #query_list {
                background-color: #1E293B;
                border: none;
                font-size: 12px;
                padding: 2px;
                outline: none;
            }
            #query_list::item {
                padding: 7px 8px;
                border-radius: 4px;
                color: #94A3B8;
            }
            #query_list::item:selected {
                background-color: #1D4ED8;
                color: #BFDBFE;
                border-radius: 4px;
            }
            #query_list::item:hover:!selected {
                background-color: #334155;
                border-radius: 4px;
            }
            QPushButton#btn_add_query {
                background-color: #334155; color: #94A3B8;
                border: 1px solid #475569; border-radius: 4px;
                padding: 6px 8px; font-size: 12px; text-align: left;
            }
            QPushButton#btn_add_query:hover {
                background-color: #1D4ED8; color: white;
                border-color: #3B82F6;
            }
        """)
