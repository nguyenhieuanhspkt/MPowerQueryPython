---
name: project-mpowerquery
description: "Tổng quan dự án MPowerQueryPython — mục tiêu, stack, trạng thái"
metadata: 
  node_type: memory
  type: project
  originSessionId: f3e9740c-e3e2-445e-99aa-ef4df6fe4bb5
---

MPowerQueryPython là công cụ no-code/low-code xử lý dữ liệu (CSV/Excel) dựa trên PyQt5 + Pandas. Người dùng tạo pipeline transform qua UI, lưu thành Recipe JSON để tái sử dụng.

**Why:** Hỗ trợ nghiệp vụ đấu thầu trong hệ sinh thái TaskApp — thay thế việc viết Pandas thủ công.

**How to apply:** Mọi tính năng mới cần tham chiếu thuật toán từ PandasGUI trước (frozen header → `dataframe_viewer.py`, filter bar → `filter_viewer.py`, stats → `stat_viewer.py`, chart → `grapher.py`).

**Đã xong (commit 739b753 — 2026-06-17):**
- Pipeline/recipe system, Filter/Drop/Sort/Rename/FillNA/RemoveTopRows/Row→Header, cast_column (text↔numeric)
- Xử lý số tiếng Việt, CSV import dialog, multi-sheet Excel picker, code preview
- SelectableHeaderView: Ctrl+click, **Shift+click range select**, Ctrl+Shift extend range
- Filter icon (▼) per column; type badge 123/ABC; context menu Drop/Keep/Filter/Rename/Cast
- **Group Rows** (group_by + agg dict): Sum/Mean/Min/Max/Count/First/Last
- **Pipeline step preview**: click step → xem data tại thời điểm đó (engine._current không đổi)
- **Delete step giữa**: right-click → Delete This Step; rebuild tự revert nếu lỗi
- **Auto rename trùng tên**: _unique_col_name() → "Revenue" → "Revenue_1"
- **Error với step number**: rebuild() wrap lỗi "Lỗi tại Step N — OpName: ..."
- **Status bar**: shape | steps | PREVIEW badge | **Auto Sum/Count khi select cột** | filename
- **VN thousands format**: 185000 → "185.000", 1234.5 → "1.234,5" (numeric cols only)
- Fix _to_typed_df() dùng iloc[:, i] tránh crash khi duplicate column names
- Selected pipeline step background: #1E1E1E (đen) để text màu nổi rõ
- huong_dan.txt: quick-reference guide cho user

**Còn lại:** Table view nâng cao (frozen header, sort by click, double-click resize), statistics panel, chart builder, filter bar text expression.
