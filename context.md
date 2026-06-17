# MPowerQueryPython - Context

## Tổng quan
**MPowerQueryPython** là một công cụ xử lý dữ liệu trực quan (No-code/Low-code) được xây dựng trên nền tảng **Python** và **PyQt5**. Dự án nhằm mục đích thay thế việc viết code `pandas` thủ công bằng giao diện người dùng (UI) trực quan, cho phép người dùng thực hiện các thao tác xử lý dữ liệu (load, lọc, bỏ dòng, chuyển đổi) một cách nhanh chóng và chính xác.

## Nguồn tham khảo thuật toán
Ứng dụng này được xây dựng trên cơ sở **học thuật toán từ [PandasGUI](https://github.com/adamerose/PandasGUI.git)** — một open-source GUI cho Pandas của Adam Rose.

Khi cần implement hoặc cải tiến các tính năng dưới đây, **ưu tiên tham khảo source PandasGUI trước** để kế thừa thuật toán đã được kiểm chứng:

| Tính năng | File tham khảo trong PandasGUI |
|---|---|
| Table view nâng cao (frozen header, sync scroll) | `venv/Lib/site-packages/pandasgui/widgets/dataframe_viewer.py` |
| Filter bar (parse text expression → pandas) | `venv/Lib/site-packages/pandasgui/widgets/filter_viewer.py` |
| Statistics panel (describe per column) | `venv/Lib/site-packages/pandasgui/widgets/stats_viewer.py` |
| Chart / visualization builder | `venv/Lib/site-packages/pandasgui/widgets/grapher.py` |
| Column right-click menu | `venv/Lib/site-packages/pandasgui/widgets/column_menu.py` |
| State management cho DataFrame | `venv/Lib/site-packages/pandasgui/store.py` |

## Mục tiêu
*   **Trực quan hóa:** Chuyển đổi các thao tác Pandas thành các hành động trên UI.
*   **Năng suất:** Tăng tốc quy trình xử lý dữ liệu đấu thầu/kinh doanh.
*   **Tính kế thừa:** Lưu trữ các chuỗi xử lý (pipeline) để tái sử dụng cho các lần làm việc tiếp theo.

## Cấu trúc thư mục

```
main.py                  # Entry point — tạo QApplication, khởi MainWindow
core/
  data_engine.py         # DataEngine: load/apply_step/rebuild/export/_to_typed_df
  recipe.py              # Recipe: lưu pipeline steps, sinh pandas code
  utils.py               # parse_number, to_numeric_vn, detect_csv_sep
ui/
  main_window.py         # MainWindow: toolbar, menu, pipeline panel, table view
  pandas_model.py        # PandasModel + SelectableHeaderView + ColumnHighlightDelegate
  transform_dialogs.py   # Tất cả dialog: Filter, DropColumns, Rename, Sort, FillNA, ...
config/                  # Recipe JSON files (tạo khi save)
data/                    # Input/output data files
```

## Stack công nghệ
- **Ngôn ngữ:** Python 3.x
- **UI Framework:** PyQt5 >= 5.15
- **Data Engine:** Pandas >= 1.5
- **Excel:** openpyxl >= 3.0
- **Thuật toán UI & Engine tham khảo:** [PandasGUI](https://github.com/adamerose/PandasGUI.git)

## Chạy ứng dụng

```powershell
.\venv\Scripts\activate
python main.py
```

## Kiến trúc cốt lõi

### DataEngine (`core/data_engine.py`)
- Giữ `_original` (DataFrame gốc) và `_current` (sau transform).
- `load()` đọc CSV/Excel, lưu `decimal` setting (mặc định `','` tiếng Việt).
- `apply_step(step)` áp 1 bước transform lên `_current`.
- `rebuild(steps)` reset về `_original` rồi apply lại toàn bộ steps — dùng cho Undo.
- `export(path)` gọi `_to_typed_df()` trước khi ghi — tự động convert string column sang numeric nếu ≥ 90% giá trị parse được, tránh lỗi "Number Stored as Text" trong Excel. CSV dùng `decimal=self._decimal`.
- **Truy cập cột bằng positional index (`iloc`)** — tránh lỗi khi file Excel có cột trùng tên. Pattern học từ PandasGUI: tìm index trước, dùng `df.iloc[:, col_ix]`.

### Recipe (`core/recipe.py`)
- Danh sách steps: `[{"operation": "filter", "params": {...}}, ...]`
- `save(path)` / `load(path)` → JSON.
- `to_pandas_code()` sinh code pandas thuần từ steps.

### Step schema — cách thêm operation mới
Thêm case trong `DataEngine.apply_step()` + `Recipe.to_pandas_code()` + dialog (nếu cần) trong `transform_dialogs.py` + entry trong `_STEP_META` của `MainWindow`.

| operation | params |
|---|---|
| `filter` | `column`, `condition`, `value` |
| `drop_columns` | `columns: list` |
| `drop_duplicates` | _(none)_ |
| `rename_column` | `old_name`, `new_name` |
| `sort` | `column`, `ascending: bool` |
| `fillna` | `column` (`__all__` = tất cả cột), `value` |
| `remove_top_rows` | `n: int` |
| `use_first_row_as_header` | _(none)_ |
| `cast_column` | `column`, `to_type` (`'numeric'` hoặc `'text'`) |

Filter conditions: `equals`, `not_equals`, `contains`, `not_contains`, `starts_with`, `ends_with`, `greater_than`, `less_than`, `greater_equal`, `less_equal`, `is_empty`, `is_not_empty`

### PandasModel (`ui/pandas_model.py`)
- `PandasModel(QAbstractTableModel)`: feed DataFrame vào QTableView.
  - `set_decimal(decimal)` — gọi sau khi load file để model biết định dạng số VN/quốc tế.
  - `column_type_hints()` → dict `{col_idx: 'numeric'|'text'|'empty'}` — tính khi `setDataFrame`, dùng `to_numeric_vn` với decimal setting. Sample tối đa 500 rows mỗi cột.
  - `data()` dùng `_fmt_cell(s, decimal)` để sửa float artifact từ Excel (`"1500.0"` → `"1500"`, `"1234.5"` → `"1234,5"` khi decimal=`,`). Regex `_PLAIN_FLOAT_RE` loại trừ text string có trailing zero (`"1.500"` không bị đụng vào).
- `SelectableHeaderView(QHeaderView)`: header nâng cao.
  - **Signals:** `sig_drop_columns(list)`, `sig_filter_column(str)`, `sig_filter_not_empty(str)`, `sig_rename_column(str)`, `sig_cast_column(str, str)`.
  - **Click trái vào icon ▼** (22px phải) → `sig_filter_column` mở FilterDialog cho cột đó.
  - **Ctrl+click** vào tên cột → multi-select (amber highlight + ColumnHighlightDelegate tô cell).
  - **Type badge** `123`/`ABC` (30px, ngay trái icon ▼): xanh lá = numeric, xanh navy = text. Cập nhật qua `set_type_hints(hints)`.
  - **Active filter dot**: icon ▼ chuyển xanh lá + chấm tròn khi cột đang có filter step. Cập nhật qua `set_active_filters(col_names)`.
  - **Right-click menu (single column):**
    - Filter: is not empty (nhanh, không mở dialog)
    - Filter this column... (mở FilterDialog)
    - Rename Column...
    - Convert to Number / Convert to Text
    - Remove Other Columns / Drop Column(s)
  - **Right-click menu (multi-column):** Remove Other Columns / Drop Column(s).
- `ColumnHighlightDelegate`: tô amber tint lên cells của cột đang được select.

### Dialogs (`ui/transform_dialogs.py`)
Tất cả dialog transform hỗ trợ `preselect: str = None` để pre-select cột từ header click:
- `FilterDialog(columns, parent, preselect=None)`
- `RenameColumnDialog(columns, parent, preselect=None)`

### MainWindow (`ui/main_window.py`)
- `_refresh_table(df)` gọi `self._col_header.set_type_hints(self._model.column_type_hints())` sau mỗi lần refresh.
- `_update_filter_highlights()` — sync icon ▼ xanh/xám với recipe steps; gọi sau apply/undo/reset/load.
- `_col_header.setFixedHeight(40)` — header cao 40px để chứa type badge.
- Handlers từ header: `_on_header_filter_not_empty`, `_on_header_rename_column`, `_on_header_cast_column`.

## Quy trình xử lý (Workflow)
1. **Input:** Người dùng load file CSV/Excel vào ứng dụng.
2. **Transform:** Sử dụng pipeline UI để làm sạch, lọc và biến đổi dữ liệu.
3. **Save/Export:** Xuất kết quả ra định dạng mong muốn hoặc lưu "Recipe" (quy trình) để tự động hóa cho các file sau này.

## Trạng thái phát triển

### Đã hoàn thành
- [x] Khởi tạo khung ứng dụng.
- [x] Hệ thống Pipeline (Recipes) — lưu/load JSON, undo, reset, sinh pandas code.
- [x] Toolbar các tác vụ nhanh (Filter, Drop, Sort, Rename, Fill NA, v.v.).
- [x] Xử lý dấu thập phân tiếng Việt (`parse_number`, `to_numeric_vn`).
- [x] Chọn sheet khi mở file Excel nhiều sheet.
- [x] CSV Import dialog (auto-detect separator, chọn decimal).
- [x] **SelectableHeaderView** — Ctrl+click multi-select cột, amber highlight, context menu Drop/Keep.
- [x] **ColumnHighlightDelegate** — tô màu amber toàn cột khi select.
- [x] **Filter icon (▼)** trên mỗi cột header — click mở FilterDialog pre-select đúng cột; icon xanh lá khi cột có filter step.
- [x] **Type badge (123/ABC)** trên header — hiển thị loại dữ liệu của cột, cập nhật tự động sau mỗi bước.
- [x] **Context menu cột** — Filter: is not empty (nhanh), Filter this column..., Rename Column..., Convert to Number/Text.
- [x] **cast_column operation** — đổi kiểu cột text↔numeric, ghi vào Recipe, sinh pandas code.
- [x] **Sửa float artifact** — `"1500.0"` → `"1500"`, `"1234.5"` → `"1234,5"` (decimal=`,`), FP noise → round :.10g.
- [x] **Export chuẩn** — `_to_typed_df()` convert numeric string cols trước khi export; CSV dùng `decimal=self._decimal`; Excel hết cảnh báo "Number Stored as Text".

### Còn lại (roadmap)
- [ ] Table view nâng cao — frozen header khi scroll, double-click resize cột, sort khi click header (học từ `dataframe_viewer.py` PandasGUI).
- [ ] Statistics panel — `describe()` per column (học từ `stats_viewer.py` PandasGUI).
- [ ] Chart builder (học từ `grapher.py` PandasGUI).
- [ ] Filter bar dạng text expression — gõ `col_a > 100 & col_b != ""` (học từ `filter_viewer.py` PandasGUI).

---
*Ghi chú: Dự án này là một phần trong hệ sinh thái "TaskApp" để hỗ trợ nghiệp vụ đấu thầu.*
