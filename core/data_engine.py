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
    'flatten_hierarchy':       'Flatten Hierarchy',
    'expand_hierarchy':        'Expand Hierarchy',
    'semantic_filter':         'AI Semantic Filter',
    'semantic_dedup':          'AI Fuzzy Dedup',
}


class DataEngine:
    def __init__(self):
        self._original: Optional[pd.DataFrame] = None
        self._current: Optional[pd.DataFrame] = None
        self._source_path: str = ''
        self._sheet_name: Optional[str] = None
        self._decimal: str = ','   # default Vietnamese

    def load_df(self, df: pd.DataFrame, decimal: str = None) -> pd.DataFrame:
        """Load an already-computed DataFrame as the source (for derived queries)."""
        if decimal is not None:
            self._decimal = decimal
        self._source_path = ''
        self._sheet_name = None
        self._original = df.copy()
        self._original.columns = [str(c) for c in self._original.columns]
        self._current = self._original.copy()
        return self._current

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
            elif to_type == 'date':
                self._current.iloc[:, col_ix] = pd.to_datetime(
                    self._current.iloc[:, col_ix].astype(str), dayfirst=True, errors='coerce')
            else:  # 'text'
                series = self._current.iloc[:, col_ix]
                if series.dtype.kind == 'M':  # datetime64 → format as dd/mm/yyyy
                    self._current.iloc[:, col_ix] = (
                        series.dt.strftime('%d/%m/%Y').where(series.notna(), other=''))
                else:
                    self._current.iloc[:, col_ix] = series.astype(str)
        elif op == 'add_index_column':
            col_name = params.get('col_name', 'STT')
            position = int(params.get('position', 0))
            actual = self._unique_col_name(col_name)
            params['col_name'] = actual
            self._current.insert(position, actual, range(1, len(self._current) + 1))

        elif op == 'flatten_hierarchy':
            group_cols  = params.get('group_cols', [])
            drop_parent = params.get('drop_parent_rows', True)
            if not group_cols:
                return self._current
            missing = [c for c in group_cols if c not in self._current.columns]
            if missing:
                raise ValueError(f'Cột không tồn tại: {", ".join(missing)}')
            df = self._current.copy()
            # Normalize empty strings → None so ffill works on both NaN and ''
            for col in group_cols:
                s = df[col]
                empty_mask = s.isna() | (s.astype(str).str.strip() == '')
                df[col] = s.where(~empty_mask, other=None)
            df[group_cols] = df[group_cols].ffill()
            if drop_parent:
                leaf_cols = [c for c in df.columns if c not in group_cols]
                if leaf_cols:
                    def _all_empty(row):
                        return all(
                            (v is None or (isinstance(v, float) and v != v)
                             or (isinstance(v, str) and v.strip() == ''))
                            for v in row
                        )
                    is_parent = df[leaf_cols].apply(_all_empty, axis=1)
                    df = df[~is_parent]
            self._current = df.reset_index(drop=True)

        elif op == 'expand_hierarchy':
            import re as _re

            source_col  = params.get('source_col')
            levels      = params.get('levels', [])
            leaf_cond   = params.get('leaf_condition', 'not_any_rule')
            drop_parent = params.get('drop_parent_rows', True)

            if not source_col or source_col not in self._current.columns:
                raise ValueError(f'Cột nguồn "{source_col}" không tồn tại.')
            if not levels:
                raise ValueError('Chưa định nghĩa rule nhận dạng cấp nào.')

            df = self._current.copy()
            n  = len(df)

            def _cv(raw):
                return '' if (raw is None or (isinstance(raw, float) and raw != raw)) else str(raw).strip()

            def _match_rule(val, cond, pat):
                if cond == 'starts_with': return val.startswith(pat)
                if cond == 'contains':    return pat in val
                if cond == 'ends_with':   return val.endswith(pat)
                if cond == 'is_numeric':
                    try: float(val.replace(',', '.')); return True
                    except ValueError: return False
                if cond == 'is_date':     return bool(_re.match(r'\d{1,4}[\-/\.T ]\d{1,2}', val))
                if cond == 'regex':       return bool(_re.search(pat, val))
                return False

            def _is_leaf(val, cond):
                if cond == 'is_date_or_number':
                    try: float(val.replace(',', '.')); return True
                    except ValueError: pass
                    return bool(_re.match(r'\d{1,4}[\-/\.T ]\d{1,2}', val))
                if cond == 'not_any_rule': return True
                if cond == 'is_not_empty': return bool(val)
                return False

            # Resolve unique column names, update params in-place for rebuild consistency
            existing = set(df.columns)
            for lvl in levels:
                orig  = lvl['col_name']
                aname = orig
                idx   = 1
                while aname in existing:
                    aname = f'{orig}_{idx}'; idx += 1
                existing.add(aname)
                lvl['col_name'] = aname

            # Classify each row: None=leaf, col_name=parent, 'skip'=discard
            row_kind = []
            for i in range(n):
                val     = _cv(df.iloc[i][source_col])
                matched = None
                for lvl in levels:
                    if _match_rule(val, lvl['condition'], lvl.get('match_value', '')):
                        matched = lvl['col_name']
                        break
                if matched:
                    row_kind.append(matched)
                elif _is_leaf(val, leaf_cond):
                    row_kind.append(None)
                else:
                    row_kind.append('skip')

            # Insert level columns at front (reversed → rule #1 ends up leftmost)
            for lvl in reversed(levels):
                aname = lvl['col_name']
                strip = lvl.get('strip_prefix', '')
                vals  = []
                for i, kind in enumerate(row_kind):
                    if kind == aname:
                        raw = _cv(df.iloc[i][source_col])
                        vals.append(raw[len(strip):].strip() if strip and raw.startswith(strip) else raw)
                    else:
                        vals.append(None)
                df.insert(0, aname, vals)

            # Forward-fill level columns
            level_cols = [lvl['col_name'] for lvl in levels]
            df[level_cols] = df[level_cols].ffill()

            # Filter rows: skip rows are always dropped; parent rows dropped only if requested
            if drop_parent:
                df = df[[k is None for k in row_kind]]
            else:
                df = df[[k != 'skip' for k in row_kind]]

            self._current = df.reset_index(drop=True)

        elif op == 'semantic_filter':
            col = params.get('column')
            query = params.get('query', '')
            threshold = float(params.get('threshold', 0.7))
            if col not in self._current.columns:
                raise ValueError(f'Cột "{col}" không tồn tại trong dữ liệu hiện tại.')
            if not query.strip():
                raise ValueError('Query không được để trống.')
            import numpy as np
            from core.ai import get_embedder
            embedder = get_embedder()
            values = self._current[col].fillna('').astype(str).tolist()
            doc_vecs = embedder.embed_documents(values)
            query_vec = embedder.embed_query(query)
            doc_norms = np.linalg.norm(doc_vecs, axis=1, keepdims=True)
            doc_vecs_norm = doc_vecs / (doc_norms + 1e-12)
            q_norm = query_vec / (np.linalg.norm(query_vec) + 1e-12)
            scores = doc_vecs_norm @ q_norm
            mask = scores >= threshold
            self._current = self._current[mask].reset_index(drop=True)

        elif op == 'semantic_dedup':
            col       = params.get('column')
            threshold = float(params.get('threshold', 0.85))
            if col not in self._current.columns:
                raise ValueError(f'Cột "{col}" không tồn tại trong dữ liệu hiện tại.')
            import numpy as np
            import faiss
            from collections import defaultdict
            from core.ai import get_embedder
            embedder = get_embedder()
            values   = self._current[col].fillna('').astype(str).tolist()
            n        = len(values)
            if n < 2:
                return self._current
            vecs      = embedder.embed_documents(values)
            norms     = np.linalg.norm(vecs, axis=1, keepdims=True)
            vecs_norm = (vecs / (norms + 1e-12)).astype(np.float32)
            dim   = vecs_norm.shape[1]
            index = faiss.IndexFlatIP(dim)
            index.add(vecs_norm)
            k = min(30, n)
            scores_mat, indices_mat = index.search(vecs_norm, k)
            parent_arr = list(range(n))

            def _find(x):
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
                    if j < 0 or score < threshold:
                        break
                    ri, rj = _find(i), _find(j)
                    if ri != rj:
                        parent_arr[ri] = rj

            seen_roots = set()
            keep_mask  = []
            for i in range(n):
                root = _find(i)
                keep_mask.append(root not in seen_roots)
                seen_roots.add(root)

            self._current = self._current[keep_mask].reset_index(drop=True)

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
