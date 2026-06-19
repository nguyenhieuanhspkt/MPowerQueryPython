import json
from typing import List, Dict, Any


class Recipe:
    def __init__(self, name: str = 'Untitled'):
        self.name = name
        self.steps: List[Dict[str, Any]] = []

    def add_step(self, step: Dict[str, Any]):
        self.steps.append(step)

    def remove_last(self):
        if self.steps:
            self.steps.pop()

    def save(self, path: str):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({'name': self.name, 'steps': self.steps}, f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path: str) -> 'Recipe':
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        r = cls(name=data.get('name', 'Untitled'))
        r.steps = data.get('steps', [])
        return r

    def to_pandas_code(self, source_path: str = '') -> str:
        lines = ['import pandas as pd', '']

        if source_path:
            if source_path.lower().endswith('.csv'):
                lines.append(f"df = pd.read_csv(r'{source_path}', dtype=str)")
            else:
                lines.append(f"df = pd.read_excel(r'{source_path}', dtype=str)")
        else:
            lines.append("df = pd.read_csv('your_file.csv', dtype=str)  # replace path")

        lines.append('')

        for step in self.steps:
            op = step['operation']
            p = step.get('params', {})

            if op == 'filter':
                col, cond, val = p['column'], p['condition'], p.get('value', '')
                if cond == 'equals':
                    lines.append(f"df = df[df['{col}'] == '{val}']")
                elif cond == 'not_equals':
                    lines.append(f"df = df[df['{col}'] != '{val}']")
                elif cond == 'contains':
                    lines.append(f"df = df[df['{col}'].astype(str).str.contains('{val}', case=False, na=False)]")
                elif cond == 'not_contains':
                    lines.append(f"df = df[~df['{col}'].astype(str).str.contains('{val}', case=False, na=False)]")
                elif cond == 'starts_with':
                    lines.append(f"df = df[df['{col}'].astype(str).str.startswith('{val}')]")
                elif cond == 'ends_with':
                    lines.append(f"df = df[df['{col}'].astype(str).str.endswith('{val}')]")
                elif cond == 'greater_than':
                    lines.append(f"df = df[pd.to_numeric(df['{col}'], errors='coerce') > {val}]")
                elif cond == 'less_than':
                    lines.append(f"df = df[pd.to_numeric(df['{col}'], errors='coerce') < {val}]")
                elif cond == 'greater_equal':
                    lines.append(f"df = df[pd.to_numeric(df['{col}'], errors='coerce') >= {val}]")
                elif cond == 'less_equal':
                    lines.append(f"df = df[pd.to_numeric(df['{col}'], errors='coerce') <= {val}]")
                elif cond == 'is_empty':
                    lines.append(f"df = df[df['{col}'].isna() | (df['{col}'].astype(str).str.strip() == '')]")
                elif cond == 'is_not_empty':
                    lines.append(f"df = df[~(df['{col}'].isna() | (df['{col}'].astype(str).str.strip() == ''))]")

            elif op == 'drop_columns':
                cols_str = str(p.get('columns', []))
                lines.append(f"df = df.drop(columns={cols_str}, errors='ignore')")

            elif op == 'drop_duplicates':
                lines.append("df = df.drop_duplicates()")

            elif op == 'rename_column':
                old, new = p.get('old_name'), p.get('new_name')
                lines.append(f"df = df.rename(columns={{'{old}': '{new}'}})")

            elif op == 'sort':
                col = p.get('column')
                asc = p.get('ascending', True)
                lines.append(f"df = df.sort_values('{col}', ascending={asc}).reset_index(drop=True)")

            elif op == 'fillna':
                col = p.get('column')
                val = p.get('value', '')
                if col == '__all__':
                    lines.append(f"df = df.fillna('{val}')")
                else:
                    lines.append(f"df['{col}'] = df['{col}'].fillna('{val}')")

            elif op == 'remove_top_rows':
                n = p.get('n', 1)
                lines.append(f"df = df.iloc[{n}:].reset_index(drop=True)")

            elif op == 'use_first_row_as_header':
                lines.append("df.columns = df.iloc[0].astype(str).tolist()")
                lines.append("df = df.iloc[1:].reset_index(drop=True)")
            elif op == 'cast_column':
                col = p.get('column')
                to_type = p.get('to_type', 'text')
                if to_type == 'numeric':
                    lines.append(f"df['{col}'] = pd.to_numeric(df['{col}'].astype(str), errors='coerce')")
                elif to_type == 'date':
                    lines.append(f"df['{col}'] = pd.to_datetime(df['{col}'].astype(str), dayfirst=True, errors='coerce')")
                else:
                    lines.append(f"df['{col}'] = df['{col}'].astype(str)")

            elif op == 'group_rows':
                by_cols = p.get('by', [])
                agg_dict = p.get('aggregations', {})
                by_str = repr(by_cols)
                agg_str = repr(agg_dict)
                if agg_dict:
                    lines.append(f"df = df.groupby({by_str}, as_index=False, dropna=False).agg({agg_str}).reset_index(drop=True)")
                else:
                    lines.append(f"df = df[{by_str}].drop_duplicates().reset_index(drop=True)")

            elif op == 'add_index_column':
                col = p.get('col_name', 'STT')
                pos = int(p.get('position', 0))
                lines.append(f"df.insert({pos}, '{col}', range(1, len(df) + 1))")

            elif op == 'flatten_hierarchy':
                gcols = repr(p.get('group_cols', []))
                drop  = p.get('drop_parent_rows', True)
                lines.append(f"_group_cols = {gcols}")
                lines.append(f"for _c in _group_cols:")
                lines.append(f"    _s = df[_c]; df[_c] = _s.where(~(_s.isna() | (_s.astype(str).str.strip() == '')), other=None)")
                lines.append(f"df[_group_cols] = df[_group_cols].ffill()")
                if drop:
                    lines.append(f"_leaf = [c for c in df.columns if c not in _group_cols]")
                    lines.append(f"if _leaf:")
                    lines.append(f"    df = df[~df[_leaf].apply(lambda r: all((v is None or (isinstance(v,float) and v!=v) or (isinstance(v,str) and v.strip()=='')) for v in r), axis=1)]")
                lines.append(f"df = df.reset_index(drop=True)")

            elif op == 'expand_hierarchy':
                src    = p.get('source_col', '')
                levels = p.get('levels', [])
                lc     = p.get('leaf_condition', 'not_any_rule')
                drop   = p.get('drop_parent_rows', True)
                lines.append('import re as _re')
                lines.append(f"_src = '{src}'")
                lines.append(f'_levels = {repr(levels)}')
                lines.append(f"_leaf_cond = '{lc}'")
                lines.append('def _cv(v): return "" if (v is None or (isinstance(v,float) and v!=v)) else str(v).strip()')
                lines.append('def _mr(v,c,p):')
                lines.append('    if c=="starts_with": return v.startswith(p)')
                lines.append('    if c=="contains": return p in v')
                lines.append('    if c=="ends_with": return v.endswith(p)')
                lines.append('    if c=="is_numeric":\n        try: float(v.replace(",",".")); return True\n        except: return False')
                lines.append('    if c=="is_date": return bool(_re.match(r"\\d{1,4}[\\-/\\.T ]\\d{1,2}", v))')
                lines.append('    if c=="regex": return bool(_re.search(p, v))')
                lines.append('    return False')
                lines.append('def _lf(v,c):')
                lines.append('    if c=="is_date_or_number":\n        try: float(v.replace(",",".")); return True\n        except: pass\n        return bool(_re.match(r"\\d{1,4}[\\-/\\.T ]\\d{1,2}", v))')
                lines.append('    return bool(v) if c=="is_not_empty" else True')
                lines.append('_rk=[next((l["col_name"] for l in _levels if _mr(_cv(r[_src]),l["condition"],l.get("match_value",""))),None) if not _lf(_cv(r[_src]),_leaf_cond) else None for _,r in df.iterrows()]')
                lines.append('# simplify: reclassify using matched/leaf/skip')
                lines.append('_rk2=[]')
                lines.append('for _i,_r in df.iterrows():')
                lines.append('    _v=_cv(_r[_src]); _m=next((l["col_name"] for l in _levels if _mr(_v,l["condition"],l.get("match_value",""))),None)')
                lines.append('    _rk2.append(_m if _m else (None if _lf(_v,_leaf_cond) else "skip"))')
                for ilvl, lvl in enumerate(reversed(levels)):
                    an = lvl['col_name']; s = lvl.get('strip_prefix','')
                    lines.append(f'_v{ilvl}=[(_cv(r[_src])[{len(s)}:].strip() if _cv(r[_src]).startswith({repr(s)}) else _cv(r[_src])) if k=={repr(an)} else None for k,(_,r) in zip(_rk2,df.iterrows())]')
                    lines.append(f"df.insert(0, {repr(an)}, _v{ilvl})")
                lc_names = repr([lvl['col_name'] for lvl in levels])
                lines.append(f'df[{lc_names}] = df[{lc_names}].ffill()')
                if drop:
                    lines.append('df = df[[k is None for k in _rk2]].reset_index(drop=True)')
                else:
                    lines.append('df = df[[k != "skip" for k in _rk2]].reset_index(drop=True)')

            elif op == 'split_column':
                col = p.get('column', '')
                delimiter = p.get('delimiter', '')
                idx = p.get('part_index', 0)
                new_col = p.get('new_col_name', '')
                extract_expr = (
                    f"df['{col}'].astype(str).str.split({repr(delimiter)})"
                    f".apply(lambda x: x[{idx}].strip() if abs({idx}) < len(x) else x[-1 if {idx} < 0 else 0].strip())"
                )
                if new_col:
                    lines.append(
                        f"df.insert(df.columns.get_loc('{col}') + 1, '{new_col}', {extract_expr})"
                    )
                else:
                    lines.append(f"df['{col}'] = {extract_expr}")

            elif op == 'semantic_filter':
                col = p.get('column')
                query = p.get('query', '')
                threshold = p.get('threshold', 0.7)
                lines.append(f"# AI Semantic Filter: column='{col}', query='{query}', threshold={threshold}")
                lines.append(f"# Requires BGE-M3 — see core/ai/embedder.py for implementation")

            elif op == 'semantic_dedup':
                col = p.get('column')
                threshold = p.get('threshold', 0.85)
                lines.append(f"# AI Fuzzy Dedup: column='{col}', threshold={threshold}")
                lines.append(f"# Requires BGE-M3 + FAISS — see core/ai/ for implementation")

        lines += ['', "# df.to_csv('output.csv', index=False, encoding='utf-8-sig')"]
        return '\n'.join(lines)
