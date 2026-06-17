import re as _re
import pandas as pd
from PyQt5.QtCore import Qt, QAbstractTableModel, QModelIndex, QVariant, pyqtSignal, QPoint, QRect, QRectF
from PyQt5.QtWidgets import QHeaderView, QMenu, QAction, QApplication, QStyledItemDelegate
from PyQt5.QtGui import QColor, QPainter, QFont, QPolygon

from core.utils import to_numeric_vn

MAX_DISPLAY_ROWS = 50_000

# Matches Python float repr strings like "1500.0", "1234.5", "1499.9999999999998"
# EXCLUDES trailing-zero strings like "1.500", "1.50" — those are source text, not FP results.
_PLAIN_FLOAT_RE = _re.compile(r'^-?\d+\.(\d*[1-9]|0)$')


def _fmt_cell(s: str, decimal: str = ',') -> str:
    """Clean up float strings produced by Excel dtype=str loading.

    - '1500.0'              → '1500'       integer float artifact
    - '1234.5', decimal=',' → '1234,5'     decimal separator normalisation
    - '1499.9999999999998'  → '1500'       FP noise killed by :.10g rounding
    Leaves '1.500', '1.500,50', 'ABC' etc. completely untouched.
    """
    if '.' not in s or ',' in s:
        return s
    if not _PLAIN_FLOAT_RE.match(s):
        return s
    try:
        clean = f'{float(s):.10g}'
        return clean.replace('.', ',') if decimal == ',' else clean
    except ValueError:
        return s


def _add_thousands(s: str, decimal: str = ',') -> str:
    """Add thousands separator to an already decimal-formatted number string.

    decimal=',' → VN style (thousands='.', decimal=','):  185000 → "185.000"
    decimal='.' → intl style (thousands=',', decimal='.'):  185000 → "185,000"
    Falls back to the original string on any parse error.
    """
    if not s:
        return s
    dec_sep  = ',' if decimal == ',' else '.'
    thou_sep = '.' if decimal == ',' else ','

    if dec_sep in s:
        int_part, dec_part = s.split(dec_sep, 1)
        neg    = int_part.startswith('-')
        digits = int_part.lstrip('-')
        try:
            formatted = f'{int(digits):,}'.replace(',', thou_sep)
            return ('-' if neg else '') + formatted + dec_sep + dec_part
        except ValueError:
            return s
    else:
        neg    = s.startswith('-')
        digits = s.lstrip('-')
        try:
            formatted = f'{int(digits):,}'.replace(',', thou_sep)
            return ('-' if neg else '') + formatted
        except ValueError:
            return s


# ---------------------------------------------------------------------------
# Table model
# ---------------------------------------------------------------------------

class PandasModel(QAbstractTableModel):
    def __init__(self, df: pd.DataFrame = None, decimal: str = ','):
        super().__init__()
        self._df = df if df is not None else pd.DataFrame()
        self._decimal = decimal
        self._type_hints: dict = {}

    def set_decimal(self, decimal: str):
        self._decimal = decimal

    def setDataFrame(self, df: pd.DataFrame):
        self.beginResetModel()
        self._df = df.reset_index(drop=True) if df is not None else pd.DataFrame()
        self._type_hints = self._compute_type_hints()
        self.endResetModel()

    def column_type_hints(self) -> dict:
        """Returns {col_index: 'numeric' | 'text' | 'empty'} for current DataFrame."""
        return self._type_hints

    def _compute_type_hints(self) -> dict:
        hints = {}
        for i in range(len(self._df.columns)):
            series = self._df.iloc[:, i]
            non_empty = series.dropna()
            non_empty = non_empty[non_empty.astype(str).str.strip() != '']
            if len(non_empty) == 0:
                hints[i] = 'empty'
                continue
            sample = non_empty.head(500).astype(str)
            numeric = to_numeric_vn(sample, decimal=self._decimal)
            ratio = numeric.notna().sum() / len(sample)
            hints[i] = 'numeric' if ratio >= 0.8 else 'text'
        return hints

    def rowCount(self, parent=QModelIndex()) -> int:
        return min(len(self._df), MAX_DISPLAY_ROWS)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self._df.columns)

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return QVariant()
        if role == Qt.DisplayRole:
            val = self._df.iloc[index.row(), index.column()]
            if pd.isna(val):
                return ''
            s = _fmt_cell(str(val), self._decimal)
            if self._type_hints.get(index.column()) == 'numeric':
                s = _add_thousands(s, self._decimal)
            return s
        if role == Qt.TextAlignmentRole:
            if self._type_hints.get(index.column()) == 'numeric':
                return Qt.AlignVCenter | Qt.AlignRight
            return Qt.AlignVCenter | Qt.AlignLeft
        return QVariant()

    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return QVariant()
        if orientation == Qt.Horizontal:
            return str(self._df.columns[section])
        return str(section + 1)

    def dataFrame(self) -> pd.DataFrame:
        return self._df


# ---------------------------------------------------------------------------
# Selectable column header with filter icon and type badge
# ---------------------------------------------------------------------------

class SelectableHeaderView(QHeaderView):
    """Horizontal header with:
    - Ctrl+click multi-column selection
    - ▼ filter icon per column (left-click to open FilterDialog for that column)
    - Data-type badge per column: '123' = numeric (green), 'ABC' = text (blue)
    - Right-click context menu: filter shortcuts, rename, cast type, drop/keep
    """

    sig_drop_columns      = pyqtSignal(list)       # list of col names → drop them
    sig_filter_column     = pyqtSignal(str)        # col name → open FilterDialog
    sig_filter_not_empty  = pyqtSignal(str)        # col name → add is_not_empty filter step
    sig_rename_column     = pyqtSignal(str)        # col name → open RenameColumnDialog
    sig_cast_column       = pyqtSignal(str, str)   # col name, to_type ('numeric'/'text')
    sig_selection_changed = pyqtSignal(list)       # list of selected col indices
    sig_add_index_column  = pyqtSignal()           # insert STT column at position 0

    _ICON_W = 22    # px: filter icon zone (right edge)
    _TYPE_W = 30    # px: type badge zone (just left of filter icon)

    _HEADER_SELECTED_BG = QColor('#F59E0B')
    _HEADER_SELECTED_FG = QColor('#1C1917')
    _HEADER_ACCENT      = QColor('#B45309')
    _HEADER_NORMAL_BG   = QColor('#4A90E2')   # must match stylesheet

    def __init__(self, parent=None):
        super().__init__(Qt.Horizontal, parent)
        self._selected: set = set()
        self._anchor: int = -1          # anchor column for shift-range selection
        self._filtered_col_names: set = set()
        self._type_hints: dict = {}
        self.setSectionsClickable(True)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.sectionClicked.connect(self._on_section_clicked)
        self.customContextMenuRequested.connect(self._show_menu)

    # ---------------------------------------------------------------- public API

    def clear_selection(self):
        self._selected.clear()
        self._anchor = -1
        self._repaint_all()
        self.sig_selection_changed.emit([])

    def set_active_filters(self, col_names: set):
        self._filtered_col_names = col_names
        self._repaint_all()

    def set_type_hints(self, hints: dict):
        self._type_hints = hints
        self._repaint_all()

    # ---------------------------------------------------------------- selection

    def _on_section_clicked(self, logical_index: int):
        mods = QApplication.keyboardModifiers()
        ctrl  = bool(mods & Qt.ControlModifier)
        shift = bool(mods & Qt.ShiftModifier)

        if shift and self._anchor >= 0:
            lo, hi = min(self._anchor, logical_index), max(self._anchor, logical_index)
            rang = set(range(lo, hi + 1))
            if ctrl:
                self._selected |= rang      # Ctrl+Shift: thêm vùng vào selection hiện tại
            else:
                self._selected = rang       # Shift: thay selection bằng vùng mới
            # anchor không đổi khi shift-click
        elif ctrl:
            if logical_index in self._selected:
                self._selected.discard(logical_index)
            else:
                self._selected.add(logical_index)
            self._anchor = logical_index
        else:
            self._selected = {logical_index}
            self._anchor = logical_index

        self._repaint_all()
        self.sig_selection_changed.emit(list(self._selected))

    def _repaint_all(self):
        self.viewport().update()
        table = self.parent()
        if table is not None:
            table.viewport().update()

    # ---------------------------------------------------------------- mouse

    def mousePressEvent(self, event):
        """Route click on ▼ icon zone to filter signal; normal clicks → selection."""
        if event.button() == Qt.LeftButton:
            pos = event.pos()
            logical_index = self.logicalIndexAt(pos)
            if logical_index >= 0:
                sec_x = self.sectionViewportPosition(logical_index)
                sec_w = self.sectionSize(logical_index)
                if pos.x() >= sec_x + sec_w - self._ICON_W:
                    col_name = str(self.model().headerData(logical_index, Qt.Horizontal))
                    self.sig_filter_column.emit(col_name)
                    return
        super().mousePressEvent(event)

    # ---------------------------------------------------------------- painting

    def paintSection(self, painter: QPainter, rect, logical_index: int):
        right_reserved = self._ICON_W + self._TYPE_W  # space for badges on right

        if logical_index not in self._selected:
            super().paintSection(painter, rect, logical_index)
        else:
            # Amber background for selected column
            painter.save()
            painter.fillRect(rect, self._HEADER_SELECTED_BG)
            painter.fillRect(rect.right() - 1, rect.top(), 1, rect.height(),
                             QColor('#D97706'))
            painter.fillRect(rect.x(), rect.bottom() - 3, rect.width(), 4,
                             self._HEADER_ACCENT)
            font = QFont(painter.font())
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(self._HEADER_SELECTED_FG)
            text = str(self.model().headerData(logical_index, Qt.Horizontal))
            painter.drawText(rect.adjusted(8, 0, -(right_reserved + 4), 0),
                             Qt.AlignVCenter | Qt.AlignLeft, text)
            painter.restore()

        self._paint_type_badge(painter, rect, logical_index)
        self._paint_filter_icon(painter, rect, logical_index)

    def _paint_type_badge(self, painter: QPainter, rect, logical_index: int):
        hint = self._type_hints.get(logical_index)
        if hint is None or hint == 'empty':
            return

        is_selected = logical_index in self._selected

        if hint == 'numeric':
            pill_bg   = QColor('#166534')   # dark green
            pill_fg   = QColor('#86EFAC')   # light green text
            label     = '123'
        else:
            pill_bg   = QColor('#1E3A5F')   # dark navy
            pill_fg   = QColor('#93C5FD')   # light blue text
            label     = 'ABC'

        if is_selected:
            # Adjust pill colors for amber background
            pill_bg = QColor('#14532D') if hint == 'numeric' else QColor('#581C87')
            pill_fg = QColor('#86EFAC') if hint == 'numeric' else QColor('#E9D5FF')

        # Zone background: clear any text super() painted here
        zone_bg = self._HEADER_SELECTED_BG if is_selected else self._HEADER_NORMAL_BG
        type_zone_x = rect.right() - self._ICON_W - self._TYPE_W

        painter.save()
        painter.fillRect(type_zone_x, rect.top(), self._TYPE_W, rect.height(), zone_bg)

        # Pill rect — centered vertically
        pill_w = self._TYPE_W - 6
        pill_h = 14
        pill_x = type_zone_x + 3
        pill_y = rect.center().y() - pill_h // 2

        painter.setPen(Qt.NoPen)
        painter.setBrush(pill_bg)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.drawRoundedRect(QRectF(pill_x, pill_y, pill_w, pill_h), 3.0, 3.0)

        font = QFont(painter.font())
        font.setPixelSize(9)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(pill_fg)
        painter.drawText(QRect(int(pill_x), int(pill_y), int(pill_w), int(pill_h)),
                         Qt.AlignCenter, label)
        painter.restore()

    def _paint_filter_icon(self, painter: QPainter, rect, logical_index: int):
        model = self.model()
        if model is None or model.columnCount() == 0:
            return

        col_name    = str(model.headerData(logical_index, Qt.Horizontal))
        is_active   = col_name in self._filtered_col_names
        is_selected = logical_index in self._selected

        iw = self._ICON_W
        ix = rect.right() - iw

        if is_active:
            zone_bg    = QColor('#1E40AF')
            border_clr = QColor('#357ABD')
            icon_clr   = QColor('#86EFAC')
        elif is_selected:
            zone_bg    = self._HEADER_SELECTED_BG
            border_clr = QColor('#D97706')
            icon_clr   = QColor('#78350F')
        else:
            zone_bg    = self._HEADER_NORMAL_BG
            border_clr = QColor('#357ABD')
            icon_clr   = QColor('#BFDBFE')

        painter.save()
        painter.fillRect(ix, rect.top(), iw - 1, rect.height(), zone_bg)
        painter.fillRect(rect.right() - 1, rect.top(), 1, rect.height(), border_clr)

        cx = ix + (iw - 1) // 2
        cy = rect.center().y()
        painter.setPen(Qt.NoPen)
        painter.setBrush(icon_clr)
        pts = [QPoint(ix + 3, cy - 3), QPoint(ix + iw - 4, cy - 3), QPoint(cx, cy + 4)]
        painter.drawPolygon(QPolygon(pts))

        if is_active:
            painter.drawEllipse(cx - 2, cy + 6, 4, 4)

        painter.restore()

    # ---------------------------------------------------------------- context menu

    def _show_menu(self, pos):
        logical_index = self.logicalIndexAt(pos)
        if logical_index < 0:
            return

        if logical_index not in self._selected:
            self._selected = {logical_index}
            self._repaint_all()

        model = self.model()
        total = model.columnCount()
        selected_names = [str(model.headerData(i, Qt.Horizontal))
                          for i in sorted(self._selected)]
        all_names = [str(model.headerData(i, Qt.Horizontal)) for i in range(total)]
        others = [c for c in all_names if c not in selected_names]
        is_single = len(selected_names) == 1
        col_name  = selected_names[0] if is_single else None
        hint      = self._type_hints.get(logical_index)

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background:#3C3F41; color:#CCCCCC; border:1px solid #555; font-size:12px; }
            QMenu::item:selected { background:#4A90E2; color:white; }
            QMenu::item:disabled { color:#777; font-style:italic; }
            QMenu::separator { background:#555; height:1px; margin:4px 8px; }
        """)

        # ── header label ──────────────────────────────────────────────────────
        if is_single:
            type_tag = ''
            if hint == 'numeric':
                type_tag = '  [123 Number]'
            elif hint == 'text':
                type_tag = '  [ABC Text]'
            lbl_text = f'  Column: {col_name}{type_tag}'
        else:
            lbl_text = f'  {len(selected_names)} columns selected'
        lbl = QAction(lbl_text, self)
        lbl.setEnabled(False)
        menu.addAction(lbl)
        menu.addSeparator()

        # ── single-column actions ─────────────────────────────────────────────
        if is_single:
            act_not_empty = QAction('Filter: is not empty', self)
            act_not_empty.triggered.connect(
                lambda: self.sig_filter_not_empty.emit(col_name))
            menu.addAction(act_not_empty)

            act_filter = QAction('Filter this column...', self)
            act_filter.triggered.connect(
                lambda: self.sig_filter_column.emit(col_name))
            menu.addAction(act_filter)

            menu.addSeparator()

            act_rename = QAction('Rename Column...', self)
            act_rename.triggered.connect(
                lambda: self.sig_rename_column.emit(col_name))
            menu.addAction(act_rename)

            menu.addSeparator()

            if hint == 'text' or hint == 'empty':
                act_cast = QAction('Convert to Number  (text → 123)', self)
                act_cast.triggered.connect(
                    lambda: self.sig_cast_column.emit(col_name, 'numeric'))
                menu.addAction(act_cast)
            if hint == 'numeric':
                act_cast = QAction('Convert to Text  (123 → ABC)', self)
                act_cast.triggered.connect(
                    lambda: self.sig_cast_column.emit(col_name, 'text'))
                menu.addAction(act_cast)

            menu.addSeparator()

        # ── drop / keep ───────────────────────────────────────────────────────
        if others:
            act_keep = QAction(
                f'Remove Other Columns  ‒  keep {len(selected_names)}, drop {len(others)}',
                self)
            act_keep.triggered.connect(lambda: self.sig_drop_columns.emit(others))
            menu.addAction(act_keep)

        act_drop = QAction(
            f'Drop Column(s)  ‒  drop {len(selected_names)}',
            self)
        act_drop.triggered.connect(lambda: self.sig_drop_columns.emit(selected_names))
        menu.addAction(act_drop)

        menu.addSeparator()
        act_index = QAction('Add Index Column  (STT: 1, 2, 3…)', self)
        act_index.triggered.connect(self.sig_add_index_column.emit)
        menu.addAction(act_index)

        menu.exec_(self.viewport().mapToGlobal(pos))


# ---------------------------------------------------------------------------
# Column highlight delegate
# ---------------------------------------------------------------------------

class ColumnHighlightDelegate(QStyledItemDelegate):
    """Paints an amber tint on cells that belong to selected columns."""

    _TINT_ODD  = QColor(245, 158, 11, 50)
    _TINT_EVEN = QColor(245, 158, 11, 35)

    def __init__(self, header: SelectableHeaderView, parent=None):
        super().__init__(parent)
        self._header = header

    def paint(self, painter: QPainter, option, index):
        if index.column() in self._header._selected:
            painter.save()
            tint = self._TINT_ODD if index.row() % 2 == 0 else self._TINT_EVEN
            painter.fillRect(option.rect, tint)
            painter.restore()
        super().paint(painter, option, index)
