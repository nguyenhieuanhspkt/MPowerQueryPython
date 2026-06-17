import pandas as pd
from typing import List, Dict, Any, Optional

from core.utils import to_numeric_vn, parse_number, detect_csv_sep


class DataEngine:
    def __init__(self):
        self._original: Optional[pd.DataFrame] = None
        self._current: Optional[pd.DataFrame] = None
        self._source_path: str = ''
        self._sheet_name: Optional[str] = None
        self._decimal: str = ','   # default Vietnamese

    def load(self, path: str, sheet_name: str = None, csv_sep: str = 'auto', decimal: str = ',') -> pd.DataFrame:
        self._source_path = path
        self._sheet_name = sheet_name
        self._decimal = decimal
        if path.lower().endswith('.csv'):
            sep = detect_csv_sep(path) if csv_sep == 'auto' else csv_sep
            self._original = pd.read_csv(path, dtype=str, sep=sep, encoding_errors='replace')
        else:
            kw = {'sheet_name': sheet_name} if sheet_name is not None else {}
            self._original = pd.read_excel(path, dtype=str, **kw)
        self._current = self._original.copy()
        return self._current

    @staticmethod
    def get_sheet_names(path: str) -> list:
        if path.lower().endswith('.csv'):
            return []
        xl = pd.ExcelFile(path)
        return xl.sheet_names

    def apply_step(self, step: Dict[str, Any]) -> pd.DataFrame:
        op = step['operation']
        params = step.get('params', {})

        if op == 'filter':
            self._current = self._apply_filter(self._current, params)
        elif op == 'drop_columns':
            cols = params.get('columns', [])
            self._current = self._current.drop(columns=cols, errors='ignore')
        elif op == 'drop_duplicates':
            self._current = self._current.drop_duplicates()
        elif op == 'rename_column':
            old, new = params.get('old_name'), params.get('new_name')
            if old and new:
                self._current = self._current.rename(columns={old: new})
        elif op == 'sort':
            col = params.get('column')
            asc = params.get('ascending', True)
            self._current = self._current.sort_values(col, ascending=asc, ignore_index=True)
        elif op == 'fillna':
            col = params.get('column')
            value = params.get('value', '')
            if col == '__all__':
                self._current = self._current.fillna(value)
            else:
                self._current[col] = self._current[col].fillna(value)
        elif op == 'remove_top_rows':
            n = int(params.get('n', 1))
            self._current = self._current.iloc[n:].reset_index(drop=True)
        elif op == 'use_first_row_as_header':
            self._current.columns = self._current.iloc[0].astype(str).tolist()
            self._current = self._current.iloc[1:].reset_index(drop=True)

        return self._current

    def rebuild(self, steps: List[Dict[str, Any]]) -> pd.DataFrame:
        self._current = self._original.copy()
        for step in steps:
            self.apply_step(step)
        return self._current

    def reset(self) -> pd.DataFrame:
        self._current = self._original.copy()
        return self._current

    def export(self, path: str):
        if self._current is None:
            return
        if path.lower().endswith('.csv'):
            self._current.to_csv(path, index=False, encoding='utf-8-sig')
        else:
            self._current.to_excel(path, index=False)

    @property
    def current(self) -> Optional[pd.DataFrame]:
        return self._current

    @property
    def original(self) -> Optional[pd.DataFrame]:
        return self._original

    @property
    def source_path(self) -> str:
        return self._source_path

    @property
    def decimal(self) -> str:
        return self._decimal

    # --- filter helpers ---

    def _apply_filter(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        col = params['column']
        condition = params['condition']
        value = str(params.get('value', ''))
        series = df[col]

        _NUMERIC = {'greater_than', 'less_than', 'greater_equal', 'less_equal'}

        if condition == 'equals':
            mask = series == value
        elif condition == 'not_equals':
            mask = series != value
        elif condition == 'contains':
            mask = series.astype(str).str.contains(value, case=False, na=False, regex=False)
        elif condition == 'not_contains':
            mask = ~series.astype(str).str.contains(value, case=False, na=False, regex=False)
        elif condition == 'starts_with':
            mask = series.astype(str).str.startswith(value, na=False)
        elif condition == 'ends_with':
            mask = series.astype(str).str.endswith(value, na=False)
        elif condition in _NUMERIC:
            num_series = to_numeric_vn(series, decimal=self._decimal)
            try:
                num_value = parse_number(value, decimal=self._decimal)
            except ValueError:
                raise ValueError(
                    f'Không thể đọc giá trị số "{value}".\n'
                    f'Nhập theo dạng: 1.5  hoặc  1,5  (một phẩy năm).'
                )
            if condition == 'greater_than':
                mask = num_series > num_value
            elif condition == 'less_than':
                mask = num_series < num_value
            elif condition == 'greater_equal':
                mask = num_series >= num_value
            else:
                mask = num_series <= num_value
        elif condition == 'is_empty':
            mask = series.isna() | (series.astype(str).str.strip() == '')
        elif condition == 'is_not_empty':
            mask = ~(series.isna() | (series.astype(str).str.strip() == ''))
        else:
            mask = pd.Series([True] * len(df), index=df.index)

        return df[mask].reset_index(drop=True)
