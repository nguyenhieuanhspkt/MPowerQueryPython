---
name: project-architecture
description: "Kiến trúc code MPowerQueryPython — các module, luồng dữ liệu chính"
metadata: 
  node_type: memory
  type: project
  originSessionId: f3e9740c-e3e2-445e-99aa-ef4df6fe4bb5
---

**Entry point:** `main.py` → `MainWindow`

**Core modules:**
- `core/data_engine.py` — `DataEngine`: `_original`/`_current` DataFrame; `load()`, `apply_step()`, `rebuild()`, `rebuild_preview()`, `export()`.
  - `rebuild(steps)`: wrap từng step với try/except → "Lỗi tại Step N — OpName: ..." nếu fail.
  - `rebuild_preview(steps)`: swap `_current` tạm thời, restore sau → dùng cho pipeline preview mà không thay đổi state.
  - `_to_typed_df()`: dùng `iloc[:, i]` (không phải `df[col]`) để tránh crash khi duplicate column names.
  - `_unique_col_name(name, exclude)`: trả về tên duy nhất (thêm _1, _2...) trong current columns.
  - Mọi operation đều validate column existence trước khi thực thi — raise ValueError rõ tên cột.
- `core/recipe.py` — `Recipe`: danh sách steps dict, save/load JSON, `to_pandas_code()`.
- `core/utils.py` — `parse_number()` xử lý số VN/chuẩn, `to_numeric_vn()`, `detect_csv_sep()`.

**UI modules:**
- `ui/main_window.py` — `MainWindow`: toolbar + menu + pipeline panel + QTableView.
  - `_STEP_META`: dict op → (label, color). Thêm operation mới cần entry ở đây.
  - `_refreshing_pipeline`: bool flag — block `currentRowChanged` signal khi rebuild list.
  - `_on_step_selected(row)`: preview data tại step row; last step = full view; update status bar.
  - `_on_pipeline_context_menu(pos)`: right-click → Delete This Step.
  - `_delete_step(idx)`: pop + rebuild; revert nếu rebuild fail.
  - `_on_col_selection_changed(col_indices)`: tính Sum (numeric) hoặc Count (text) → `_lbl_aggregate`.
  - `_fmt_agg(value, decimal)`: module-level helper format số aggregate kiểu VN.
  - Status bar labels: `_lbl_shape`, `_lbl_steps`, `_lbl_preview` (widget), `_lbl_aggregate` (permanent), `_lbl_source` (permanent).
- `ui/pandas_model.py` — `PandasModel` + `SelectableHeaderView` + `ColumnHighlightDelegate`.
  - `_fmt_cell(s, decimal)`: fix float artifact ("1500.0"→"1500", "1234.5"→"1234,5").
  - `_add_thousands(s, decimal)`: thêm dấu ngàn VN ("185000"→"185.000", "1.234,5" đúng xử lý).
  - `PandasModel.data()`: gọi `_fmt_cell` rồi `_add_thousands` nếu col hint == 'numeric'.
  - `SelectableHeaderView`: Ctrl+click toggle, **Shift+click range**, Ctrl+Shift extend.
    - `_anchor: int`: anchor column cho shift-select.
    - Signals: `sig_drop_columns`, `sig_filter_column`, `sig_filter_not_empty`, `sig_rename_column`, `sig_cast_column`, **`sig_selection_changed(list)`**.
- `ui/transform_dialogs.py` — tất cả dialog; `GroupRowsDialog` mới: 2 scroll section (Group By checkboxes + Aggregate comboboxes liên động).

**Step schema:** `{"operation": "...", "params": {...}}`

**Operations hiện có:**
`filter`, `drop_columns`, `drop_duplicates`, `rename_column`, `sort`, `fillna`, `remove_top_rows`, `use_first_row_as_header`, `cast_column`, **`group_rows`** (params: `by: list`, `aggregations: dict{col: func}`).

**How to apply:** Thêm operation mới = case trong `DataEngine.apply_step()` + `Recipe.to_pandas_code()` + dialog trong `transform_dialogs.py` + entry trong `_STEP_META` + import dialog trong `main_window.py`.

**Key patterns:**
- Truy cập cột bằng `iloc[:, col_ix]` (không dùng `df[col_name]`) — tránh duplicate column name issue.
- `_fmt_cell` regex `_PLAIN_FLOAT_RE` — chỉ fix Python float repr, KHÔNG đụng text như `"1.500"`.
- Type hints: `ratio = to_numeric_vn(sample).notna().sum() / len(sample)` ≥ 0.8 → numeric.
- `params` dict được mutate in-place trong `apply_step` (e.g., `params['new_name'] = actual`) → recipe tự cập nhật với giá trị thực tế.
- `_refreshing_pipeline = True` + `blockSignals(True)` khi rebuild pipeline list để tránh spurious `_on_step_selected` fires.
