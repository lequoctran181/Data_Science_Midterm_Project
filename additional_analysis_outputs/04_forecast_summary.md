### Kết luận gợi ý cho phần forecast theo kịch bản
- Mô hình chính được chọn theo RMSE expanding-window: `ARIMA(1, 0, 0)`.
- RMSE ngoài mẫu của mô hình chính = 1.9604.
- Prophet benchmark là optional; notebook sẽ bỏ qua nếu máy chưa cài gói `prophet`.
- Bảng kịch bản baseline / hawkish / dovish rất phù hợp để chuyển sang phần policy implication hoặc slide bảo vệ.