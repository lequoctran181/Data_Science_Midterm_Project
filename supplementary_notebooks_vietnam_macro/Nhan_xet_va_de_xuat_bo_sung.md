# Nhận xét và đề xuất bổ sung cho đề tài

## Kết luận nhanh

Bộ repo hiện tại đã khá đầy đủ cho mức midterm / đồ án giữa kỳ, nhưng để nâng thành một đồ án lớn "chặt" về kinh tế lượng và ít bị phản biện thì nên bổ sung 5 khối:

1. Audit dữ liệu tần suất và xác nhận vai trò của quarterly nội suy.
2. ECM dài hạn - ngắn hạn.
3. Structural breaks / regime dummies.
4. VAR + IRF + FEVD.
5. Forecast theo kịch bản và Prophet benchmark optional.

## Vì sao nên bổ sung

- Khối quarterly hiện tại có dấu hiệu được nội suy từ annual, nên không nên đứng ở vị trí bằng chứng chính.
- Đề cương có cointegration / ECM nhưng repo hiện tại chủ yếu dừng ở kiểm định.
- Báo cáo hiện đã phát hiện break 2021-2022, vì vậy nên mô hình hóa break thay vì chỉ nêu ra.
- Forecast hiện tại cần thêm scenario analysis để phần policy implication mạnh hơn.
- Biến lãi suất trong pipeline hiện tại là lending rate; nên có robustness với real interest rate hoặc policy proxy.

## Thứ tự nên chạy notebook

- 00_data_quality_and_frequency_audit.ipynb
- 01_engle_granger_ecm_longrun_shortrun.ipynb
- 02_structural_breaks_regime_dummies.ipynb
- 03_var_irf_fevd_policy_analysis.ipynb
- 04_forecast_scenarios_and_prophet_benchmark.ipynb
