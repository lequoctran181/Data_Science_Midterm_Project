# Macroeconomic Determinants of Vietnam’s Economic Growth  
## Empirical Analysis and Forecasting

This repository contains the data pipeline, modeling workflow, and research outputs for the project:

**“Tác động của các yếu tố kinh tế vĩ mô đến tăng trưởng kinh tế Việt Nam: Phân tích thực nghiệm và dự báo”**  
(**Macroeconomic Determinants of Vietnam’s Economic Growth: Empirical Analysis and Forecasting**)

The project combines **structural econometric analysis** and **short-term forecasting** to study how major macroeconomic variables affect Vietnam’s GDP growth, while also testing whether **public sentiment extracted from YouTube comments** provides additional predictive information.

---

## 1. Project overview

Vietnam’s growth performance is shaped by a broad set of macroeconomic forces, including inflation, interest rates, foreign direct investment (FDI), investment, exports, unemployment, and government spending. At the same time, empirical research in this area faces two major challenges:

- **endogeneity and dynamic feedback**, because growth and macro variables influence each other;
- **structural instability**, because the Vietnamese economy has experienced important regime changes and shocks, especially around **2008–2009**, **2020–2021**, and **2022 onward**.

To address these issues, this repository adopts a **two-layer research design**:

### Model A — Structural inference
A long-run macroeconomic model estimated on **official annual data** using:

- **OLS**
- **HAC / Newey–West standard errors**

This block is used for **economic interpretation and policy inference**.

### Model B — Forecasting / nowcasting
A short-run forecasting block estimated on **quarterly data**, including:

- **ARIMA**
- **SARIMAX**
- **VAR / Johansen cointegration checks**
- **dynamic regressions with macro + sentiment variables**
- experimental **deep learning models** (LSTM / GRU)
- optional **Prophet** baseline when the environment supports it

This block is used for **out-of-sample forecasting evaluation** and for testing whether sentiment signals improve prediction.

---

## 2. Research objectives

The project is built around three main objectives:

1. **Quantify the long-run relationship** between Vietnam’s GDP growth and core macroeconomic variables.
2. **Assess parameter stability** under structural breaks and changing policy regimes.
3. **Evaluate practical forecasting performance**, including whether alternative data such as public sentiment improves short-horizon predictions.

---

## 3. Data sources

The repository uses two main data blocks.

### 3.1 Macroeconomic data
Official macroeconomic variables are collected from the **World Bank / World Development Indicators (WDI)** for Vietnam (`VNM`).

Core variables include:

- `GDP_Raw`
- `GDP_Growth`
- `Inflation`
- `Interest_Rate`
- `FDI_pct_GDP`
- `Investment_pct_GDP`
- `Export_pct_GDP`
- `Unemployment_Rate`
- `Gov_Spending_pct_GDP`

### 3.2 Public sentiment data
Sentiment data are collected from **public YouTube comments** via the **YouTube Data API** using macro-related search queries in both Vietnamese and English, such as:

- economic growth
- inflation
- interest rate
- GDP Việt Nam
- CPI Việt Nam
- State Bank interest rate related queries

The sentiment pipeline:

- indexes videos,
- collects comments and replies,
- anonymizes public text,
- scores sentiment,
- aggregates results by month and quarter,
- merges quarterly sentiment with macro data for forecasting experiments.

---

## 4. Methodological design

## 4.1 Why the project is split into two models

A single unified model would not be methodologically sound for this dataset because:

- official macro data are primarily **annual**;
- quarterly macro series are derived as **quarterly-like interpolated data**;
- sentiment data have meaningful real overlap only from **2019Q3 onward**;
- the merged sentiment-ready dataset shows **pre-2019Q3 backfill leakage** in several sentiment columns.

For this reason:

- **Model A** is the main source of **structural conclusions**;
- **Model B** is the main source of **forecasting evidence**.

This separation is a feature of the design, not a weakness.

---

## 4.2 Macro data processing

The macro pipeline follows these steps:

1. **Collect annual data** from the World Bank API.
2. **Standardize units** (for example, GDP level converted into billions of USD where appropriate).
3. **Create quarterly-like series** by:
   - assigning annual values to calendar anchors,
   - reindexing to quarterly dates,
   - interpolating through time,
   - linearly extrapolating edge periods when needed.
4. **Repair artificial trailing flats** created by interpolation/extrapolation rules.
5. **Generate engineered features**, including:
   - log GDP,
   - quarter-on-quarter and year-on-year GDP growth,
   - lagged inflation and lagged interest-rate variables,
   - first differences and seasonal differences,
   - real interest rate proxies,
   - standardized (`*_scaled`) variables for forecasting and ML layers.

Important note: quarterly macro data in this project are **derived from annual data**, so quarterly forecasting results must be interpreted with caution.

---

## 4.3 Sentiment data processing

The sentiment pipeline follows these steps:

1. **Search YouTube videos** using macro-related queries.
2. **Extract public comments and replies** within the target collection windows.
3. **Normalize and anonymize text**, including masking links, emails, mentions, and phone-like patterns.
4. **Deduplicate comments** by comment identifier.
5. **Score sentiment**, with the main implementation using **VADER**.
6. **Assign sentiment labels** (`positive`, `neutral`, `negative`) using threshold rules.
7. **Aggregate sentiment by month and quarter**, including:
   - number of comments,
   - average sentiment,
   - net sentiment,
   - positive / neutral / negative ratios,
   - quantiles,
   - interaction measures such as likes and unique authors.
8. **Merge quarterly sentiment with macro data** for overlap-period forecasting experiments.

---

## 4.4 Leakage audit and overlap discipline

One of the most important methodological contributions of this repository is the **explicit leakage audit**.

The merged dataset `model_ready_quarterly_with_scaled.csv` contains several sentiment variables that are effectively **backfilled before 2019Q3**, producing a constant-value pattern that would leak future information into the past.

Therefore:

- **do not use the full history of `model_ready_quarterly_with_scaled.csv` for long-run training**;
- sentiment-augmented models should only be estimated and evaluated on the **actual overlap period: 2019Q3–2025Q1**.

This rule is central to the credibility of the forecasting results in this repository.

---

## 5. Repository contents

The report references the following core scripts, notebooks, datasets, and experiment logs.

### 5.1 Data collection and preprocessing
- `collect_secondary_data.py`  
  Collects macroeconomic data from the World Bank API.

- `process_secondary_data.ipynb`  
  Cleans, interpolates, engineers features, and prepares quarterly macro data.

- `collect_*_data_youtube.py`  
  Collects YouTube public comments and metadata for the sentiment block.  
  (The exact filename in your repository may differ slightly from the wording in the report.)

### 5.2 Main datasets and artifacts
- `secondary_data_annual.csv` / `.xlsx`  
  Annual macroeconomic dataset used for structural inference.

- `secondary_data_cleaned.csv` / `.xlsx`  
  Quarterly-like macro dataset created from the annual source.

- `secondary_data_processed.*`  
  Processed macro data with lags, differences, and engineered features.

- `macro_quarterly_prepared.csv`  
  Main prepared quarterly macro dataset used in forecasting blocks.

- quarterly sentiment dataset by topic  
  Cleaned quarterly sentiment indicators used for overlap-period modeling.

- `model_ready_quarterly_with_scaled.csv`  
  Merged and standardized macro + sentiment dataset.  
  **Use with caution because of pre-2019Q3 leakage.**

- `scaler_parameters.csv`  
  Stored standardization parameters for reproducibility.

- `final_summary.json`  
  Pipeline summary and output trace file.

- `collection_summary.json`  
  Metadata summary for the YouTube data collection process.

### 5.3 Experimental logs and outputs
- `data_modeling_report.txt`
- `ordered_modeling_report.txt`

These files act as the repository’s **experimental logbook**, recording model specifications, diagnostics, comparisons, and backtesting decisions.

### 5.4 Figures and output folders
The report also mentions output folders such as:

- `statistical_testing_images`
- `additional_analysis_outputs`
- `branch2_outputs`

These folders store generated figures, diagnostic outputs, and rerun / robustness artifacts.

---

## 6. Main empirical findings

Based on the modeling results documented in the report, the central findings are:

1. **Inflation is the most robust adverse macro variable** in the annual structural model.  
   In the OLS/HAC specification, inflation remains the only variable that consistently preserves a negative and statistically meaningful association with GDP growth.

2. **Interest-rate effects are not stable across specifications.**  
   Their role depends on the measure used, the policy regime, and structural-break treatment.

3. **Exports appear to be a strong long-run pillar** of output performance, reinforcing the importance of trade openness and the tradables sector.

4. **Structural breaks are not optional diagnostics; they are core features of the data.**  
   The repository documents strong break evidence around **2021–2022**.

5. **For quarterly-like short-run forecasting, SARIMAX is the strongest baseline among the tested classical models.**  
   The selected benchmark is reported as **SARIMAX(0,0,3)** on recalculated quarter-on-quarter GDP growth with **inflation** and **interest rate** as exogenous regressors.

6. **Sentiment helps in-sample explanation on the true overlap period, but it does not yet demonstrate stable out-of-sample superiority.**  
   This is one of the most important balanced conclusions of the repository.

---

## 7. Model summary

### 7.1 Structural model (annual)
- Target: `GDP_Growth`
- Frequency: annual
- Method: OLS with HAC standard errors
- Purpose: interpretation, long-run structural evidence

### 7.2 Quarterly robustness model
- Method: GLSAR on interpolated quarterly-like data
- Purpose: sensitivity check only
- Warning: not a substitute for official annual structural inference

### 7.3 Forecasting model
- Targets considered:
  - `log_gdp`
  - `gdp_growth`
  - `gdp_qoq_pct_recalc`
- Classical methods:
  - ARIMA
  - SARIMAX
  - VAR / Johansen procedures
- Preferred baseline:
  - SARIMAX with macro exogenous inputs

### 7.4 Sentiment-augmented model
- Sample restricted to: **2019Q3–2025Q1**
- Purpose:
  - in-sample explanatory comparison,
  - rolling one-step out-of-sample evaluation,
  - nested tests and forecast-comparison tests

### 7.5 Experimental deep learning layer
- LSTM / GRU variants tested on time-ordered train/test splits
- Used as an exploratory forecasting extension
- Interpreted cautiously due to short overlap sample

---

## 8. Reproducibility notes

This repository is designed around **traceable outputs** and **reproducible preprocessing**.

Key reproducibility features include:

- saved processed datasets,
- stored scaler parameters,
- explicit experiment logs,
- rolling-time forecast evaluation,
- leakage audit,
- overlap-period discipline,
- documented structural-break checks.

For credible replication, always preserve:

- original data collection dates,
- API queries,
- preprocessing parameters,
- train/test split definitions,
- cutoff dates for the overlap sample.

---

## 9. How to use this repository

## 9.1 Environment setup

Create a clean Python environment and install the required packages:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Typical packages expected for this project include:

- `pandas`
- `numpy`
- `matplotlib`
- `statsmodels`
- `scikit-learn`
- `jupyter`
- `requests`
- `python-dotenv`
- `textblob` and/or `vaderSentiment`
- optional: `tensorflow` or `keras`
- optional: `prophet`

## 9.2 Data collection
Run the macro collection script and the YouTube sentiment collection script, then review the raw outputs and metadata summaries.

```bash
python scripts/collect_secondary_data.py
python scripts/collect_sentiment_data_youtube.py
```

## 9.3 Preprocessing
Open the macro preprocessing notebook and generate the cleaned and processed datasets.

```bash
jupyter notebook notebooks/process_secondary_data.ipynb
```

## 9.4 Modeling
Use the modeling notebooks or scripts to reproduce:

- annual OLS/HAC estimation,
- quarterly SARIMAX forecasting,
- VAR and cointegration checks,
- sentiment overlap regressions,
- rolling forecast evaluation,
- optional deep learning experiments.

---

## 10. Important limitations

This repository is methodologically careful, but several limitations remain:

1. **Quarterly macro data are derived, not official quarterly GDP data.**  
   This makes quarterly forecasting useful for methodological exploration, but not a full substitute for official quarterly national accounts.

2. **Sentiment overlap is short.**  
   The true macro–sentiment overlap covers only **23 quarterly observations**.

3. **Pre-2019Q3 sentiment values in the merged scaled dataset should not be trusted for forecasting experiments.**

4. **Sentiment from YouTube comments is a noisy public-attention proxy**, not a pure macro-expectations index.

5. **Structural breaks materially affect inference**, especially around 2021–2022.

These limitations do not invalidate the project; they define the correct interpretation boundary.

---

## 11. Recommended reading of the repository

To understand the project in the right order, read it in this sequence:

1. `README.md`
2. data coverage and processed datasets
3. preprocessing notebook(s)
4. `ordered_modeling_report.txt`
5. structural model results
6. forecasting outputs
7. sentiment overlap experiments
8. robustness and break-analysis outputs

---

## 12. What this repository contributes

This repository contributes more than a set of regression outputs. It offers:

- a structured macroeconomic research workflow for Vietnam,
- a clear distinction between **structural inference** and **forecasting performance**,
- a documented treatment of **data leakage**,
- a practical example of combining **official macro data** with **alternative text-derived sentiment data**,
- a balanced and transparent interpretation of both successful and non-dominant model results.
