# Notebook bổ sung cho đề tài vĩ mô Việt Nam

Thứ tự khuyến nghị chạy:

1. `00_data_quality_and_frequency_audit.ipynb`
2. `01_engle_granger_ecm_longrun_shortrun.ipynb`
3. `02_structural_breaks_regime_dummies.ipynb`
4. `03_var_irf_fevd_policy_analysis.ipynb`
5. `04_forecast_scenarios_and_prophet_benchmark.ipynb`

## Mục tiêu của từng notebook

- `00_...`: audit dữ liệu annual/quaterly, phát hiện quarterly nội suy.
- `01_...`: ECM dài hạn - ngắn hạn + robustness theo định nghĩa lãi suất.
- `02_...`: break regime, Chow test, rolling coefficients.
- `03_...`: VAR + IRF + FEVD + Granger + diagnostics.
- `04_...`: forecast theo kịch bản + fan chart + Prophet benchmark optional.

## File dữ liệu mà notebook kỳ vọng

Bắt buộc:
- `secondary_data_annual.csv`
- `secondary_data_cleaned.csv` (cho notebook 00)
- `secondary_data_processed.csv` (cho notebook 00, nếu có)

Tùy chọn:
- `data_external/gso_real_gdp_quarterly.csv`
- `data_external/nhnn_policy_rate.csv`

## Gợi ý dùng trong báo cáo

- Giữ `01`, `02`, `03`, `04` ở phần chính nếu bạn muốn đẩy đồ án lên mức "đồ án lớn / khóa luận mini".
- Chuyển các kết quả từ quarterly nội suy sang robustness / appendix nếu notebook `00` xác nhận dữ liệu quá mượt.
