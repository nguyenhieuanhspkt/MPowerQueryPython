import pandas as pd
from typing import List, Dict, Any, Optional

from core.utils import to_numeric_vn, parse_number, detect_csv_sep

_OP_LABELS = {
    'filter':                  'Filter',
    'drop_columns':            'Drop Columns',
    'drop_duplicates':         'Drop Duplicates',
    'rename_column':           'Rename Column',
    'sort':                    'Sort',
    'fillna':                  'Fill NA',
    'remove_top_rows':         'Remove Top Rows',
    'use_first_row_as_header': 'Use Row as Header',
    'cast_column':             'Cast Type',
    'group_rows':              'Group Rows',
    'add_index_column':        'Add Index (STT)',
}


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
        # Normalize all column names to str — Excel headers can be int/float
        self._original.columns = [str(c) for c in self._original.columns]
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
                if old not in self._current.columns:
                    raise ValueError(f'Cột "{old}" không tồn tại trong dữ liệu hiện tại.')
                actual = self._unique_col_name(new, exclude=old)
                params['new_name'] = actual   # cập nhật recipe step với tên thực tế
                self._current = self._current.rename(columns={old: actual})
        elif op == 'sort':
            col = params.get('column')
            asc = params.get('ascending', True)
            if col not in self._current.columns:
                raise ValueError(f'Cột "{col}" không tồn tại trong dữ liệu hiện tại.')
            self._current = self._current.sort_values(col, ascending=asc, ignore_index=True)
        elif op == 'fillna':
            col = params.get('column')
            value = params.get('value', '')
            if col == '__all__':
                self._current = self._current.fillna(value)
            else:
                if col not in self._current.columns:
                    raise ValueError(f'Cột "{col}" không tồn tại trong dữ liệu hiện tại.')
                self._current[col] = self._current[col].fillna(value)
        elif op == 'remove_top_rows':
            n = int(params.get('n', 1))
            self._current = self._current.iloc[n:].reset_index(drop=True)
        elif op == 'use_first_row_as_header':
            raw = self._current.iloc[0].astype(str).tolist()
            seen: dict = {}
            deduped = []
            for c in raw:
                if c not in seen:
                    seen[c] = 0
                    deduped.append(c)
                else:
                    seen[c] += 1
                    deduped.append(f'{c}_{seen[c]}')
            self._current.columns = deduped
            self._current = self._current.iloc[1:].reset_index(drop=True)
        elif op == 'cast_column':
            col = params.get('column')
            to_type = params.get('to_type', 'text')
            col_positions = [i for i, c in enumerate(self._current.columns) if c == col]
            if not col_positions:
                raise ValueError(f'Cột "{col}" không tồn tại trong dữ liệu hiện tại.')
            col_ix = col_positions[0]
            if to_type == 'numeric':
                self._current.iloc[:, col_ix] = to_numeric_vn(
                    self._current.iloc[:, col_ix].astype(str), decimal=self._decimal)
            else:
                self._current.iloc[:, col_ix] = self._current.iloc[:, col_ix].astype(str)
        elif op == 'add_index_column':
            col_name = params.get('col_name', 'STT')
            position = int(params.get('position', 0))
            actual = self._unique_col_name(col_name)
            params['col_name'] = actual
            self._current.insert(position, actual, range(1, len(self._current) + 1))

        elif op == 'group_rows':
            by_cols = params.get('by', [])
            agg_dict = params.get('aggregations', {})
            if by_cols:
                missing = [c for c in by_cols if c not in self._current.columns]
                if missing:
                    raise ValueError(f'Cột nhóm không tồn tại: {", ".join(missing)}')
                missing_agg = [c for c in agg_dict if c not in self._current.columns]
                if missing_agg:
                    raise ValueError(f'Cột aggregate không tồn tại: {", ".join(missing_agg)}')
                df = self._current.copy()
                _NUMERIC_OPS = {'sum', 'mean', 'min', 'max'}
                for col, func in agg_dict.items():
                    if func in _NUMERIC_OPS and col in df.columns:
                        df[col] = to_numeric_vn(df[col].astype(str), decimal=self._decimal)
                if agg_dict:
                    # Only keep by_cols + agg columns; drop the rest
                    keep = [c for c in by_cols if c in df.columns]
                    agg_valid = {c: f for c, f in agg_dict.items() if c in df.columns}
                    self._current = (
                        df.groupby(keep, as_index=False, dropna=False)
                        .agg(agg_valid)
                        .reset_index(drop=True)
                    )
                else:
                    keep = [c for c in by_cols if c in df.columns]
                    self._current = df[keep].drop_duplicates().reset_index(drop=True)

        return self._current

    def rebuild(self, steps: List[Dict[str, Any]]) -> pd.DataFrame:
        self._current = self._original.copy()
        for i, step in enumerate(steps):
            try:
                self.apply_step(step)
            except Exception as exc:
                label = _OP_LABELS.get(step.get('operation', ''), step.get('operation', '?'))
                raise RuntimeError(
                    f'Lỗi tại Step {i + 1} — {label}:\n{exc}'
                ) from exc
        return self._current

    def rebuild_preview(self, steps: List[Dict[str, Any]]) -> pd.DataFrame:
        """Rebuild through `steps` without touching _current (for pipeline preview)."""
        saved = self._current
        self._current = self._original.copy()
        try:
            for i, step in enumerate(steps):
                try:
                    self.apply_step(step)
                except Exception as exc:
                    label = _OP_LABELS.get(step.get('operation', ''), step.get('operation', '?'))
                    raise RuntimeError(
                        f'Lỗi tại Step {i + 1} — {label}:\n{exc}'
                    ) from exc
            return self._current
        finally:
            self._current = saved

    def reset(self) -> pd.DataFrame:
        self._current = self._original.copy()
        return self._current

    def export(self, path: str):
        if self._current is None:
            return
        df_out = self._to_typed_df()
        if path.lower().endswith('.csv'):
            df_out.to_csv(path, index=False, encoding='utf-8-sig', decimal=self._decimal)
        else:
            df_out.to_excel(path, index=False)

    def _to_typed_df(self) -> 'pd.DataFrame':
        """Infer numeric types for export columns.

        Uses iloc[:, i] (not df[col]) to handle duplicate column names safely —
        df[col] returns a DataFrame when two columns share the same name.
        """
        df = self._current.copy()
        for i in range(len(df.columns)):
            series = df.iloc[:, i]
            if series.dtype != object:
                continue
            non_empty = series.dropna()
            non_empty = non_empty[non_empty.astype(str).str.strip() != '']
            if len(non_empty) == 0:
                continue
            sample = to_numeric_vn(non_empty.astype(str), decimal=self._decimal)
            if sample.notna().sum() / len(non_empty) < 0.9:
                continue
            df.iloc[:, i] = to_numeric_vn(series.astype(str), decimal=self._decimal)
        return df

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

    # --- helpers ---

    def _unique_col_name(self, name: str, exclude: str = None) -> str:
        """Return `name` if unique among current columns (ignoring `exclude`).
        Otherwise append _1, _2, ... until the name is unique."""
        existing = {c for c in self._current.columns if c != exclude}
        if name not in existing:
            return name
        i = 1
        while f'{name}_{i}' in existing:
            i += 1
        return f'{name}_{i}'

    # --- filter helpers ---

    def _apply_filter(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        col = params['column']
        condition = params['condition']
        value = str(params.get('value', ''))
        # Use positional index to avoid duplicate-column-name issue
        col_positions = [i for i, c in enumerate(df.columns) if c == col]
        if not col_positions:
            raise ValueError(f'Cột "{col}" không tồn tại trong dữ liệu hiện tại.')
        col_ix = col_positions[0]
        series = df.iloc[:, col_ix]

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
