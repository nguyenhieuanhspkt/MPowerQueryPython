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

        lines += ['', "# df.to_csv('output.csv', index=False, encoding='utf-8-sig')"]
        return '\n'.join(lines)
