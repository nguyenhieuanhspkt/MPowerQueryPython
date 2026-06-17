import pandas as pd
from PyQt5.QtCore import Qt, QAbstractTableModel, QModelIndex, QVariant

MAX_DISPLAY_ROWS = 50_000


class PandasModel(QAbstractTableModel):
    def __init__(self, df: pd.DataFrame = None):
        super().__init__()
        self._df = df if df is not None else pd.DataFrame()

    def setDataFrame(self, df: pd.DataFrame):
        self.beginResetModel()
        self._df = df.reset_index(drop=True) if df is not None else pd.DataFrame()
        self.endResetModel()

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
            return str(val)
        if role == Qt.TextAlignmentRole:
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
