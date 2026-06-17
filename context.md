# MPowerQueryPython - Context

## Tổng quan
**MPowerQueryPython** là một công cụ xử lý dữ liệu trực quan (No-code/Low-code) được xây dựng trên nền tảng **Python** và **PyQt5**. Dự án nhằm mục đích thay thế việc viết code `pandas` thủ công bằng giao diện người dùng (UI) trực quan, cho phép người dùng thực hiện các thao tác xử lý dữ liệu (load, lọc, bỏ dòng, chuyển đổi) một cách nhanh chóng và chính xác.

## Nguồn tham khảo thuật toán
Ứng dụng này được xây dựng trên cơ sở **học thuật toán từ [PandasGUI](https://github.com/adamerose/PandasGUI.git)** — một open-source GUI cho Pandas của Adam Rose.

Khi cần implement hoặc cải tiến các tính năng dưới đây, **ưu tiên tham khảo source PandasGUI trước** để kế thừa thuật toán đã được kiểm chứng:

| Tính năng | File tham khảo trong PandasGUI |
|---|---|
| Table view nâng cao (frozen header, sync scroll) | `pandasgui/widgets/dataframe_viewer.py` |
| Filter bar (parse text expression → pandas) | `pandasgui/widgets/filter_viewer.py` |
| Statistics panel (describe per column) | `pandasgui/widgets/stat_viewer.py` |
| Chart / visualization builder | `pandasgui/widgets/grapher.py` |
| State management cho DataFrame | `pandasgui/store.py` |

## Mục tiêu
*   **Trực quan hóa:** Chuyển đổi các thao tác Pandas thành các hành động trên UI.
*   **Năng suất:** Tăng tốc quy trình xử lý dữ liệu đấu thầu/kinh doanh.
*   **Tính kế thừa:** Lưu trữ các chuỗi xử lý (pipeline) để tái sử dụng cho các lần làm việc tiếp theo.

## Cấu trúc thư mục (Architecture)
- `/main.py`: Điểm khởi chạy ứng dụng (Main Entry Point).
- `/ui/`: Chứa các thành phần giao diện người dùng.
- `/core/`: Chứa logic xử lý dữ liệu chính (Pandas Engine).
- `/config/`: Chứa các "Recipe" (Công thức) đã lưu (dưới dạng JSON).
- `/data/`: Dữ liệu đầu vào và đầu ra.

## Stack công nghệ
- **Ngôn ngữ:** Python 3.x
- **UI Framework:** PyQt5
- **Data Engine:** Pandas
- **Thuật toán UI tham khảo:** [PandasGUI](https://github.com/adamerose/PandasGUI.git)

## Quy trình xử lý (Workflow)
1. **Input:** Người dùng load file CSV/Excel vào ứng dụng.
2. **Transform:** Sử dụng pipeline UI để làm sạch, lọc và biến đổi dữ liệu.
3. **Save/Export:** Xuất kết quả ra định dạng mong muốn hoặc lưu "Recipe" (quy trình) để tự động hóa cho các file sau này.

## Trạng thái phát triển
- [x] Khởi tạo khung ứng dụng.
- [x] Xây dựng hệ thống Pipeline (Recipes) — lưu/load JSON, undo, reset.
- [x] Toolbar các tác vụ nhanh (Filter, Drop, Sort, Rename, Fill NA, v.v.).
- [x] Xử lý dấu thập phân tiếng Việt (1,5 → 1.5, 1.500 → 1500).
- [x] Chọn sheet khi mở file Excel nhiều sheet.
- [x] CSV Import dialog (auto-detect separator, chọn decimal).
- [ ] Table view nâng cao (học từ `dataframe_viewer.py` của PandasGUI).
- [ ] Statistics panel (học từ `stat_viewer.py` của PandasGUI).
- [ ] Chart builder (học từ `grapher.py` của PandasGUI).
- [ ] Filter bar dạng text expression (học từ `filter_viewer.py` của PandasGUI).

---
*Ghi chú: Dự án này là một phần trong hệ sinh thái "TaskApp" để hỗ trợ nghiệp vụ đấu thầu.*
