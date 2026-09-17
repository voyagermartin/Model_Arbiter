# Model_Arbiter — 專案核心架構與開發者手冊 (HANDBOOK.md)

> **Version**: v1.2.0-diagnostic  
> **Target Engine**: Google Gemini API (Multimodal & Reasoning Models)  
> **Repository**: [Model_Arbiter GitHub](https://github.com/voyagermartin/Model_Arbiter.git)

---

## 1. Project Vision & Architecture

### 1.1 專案願景 (Project Vision)
`Model_Arbiter` 為跨專案共用的 **「Google Gemini 模型自動跑分、成本精算與最適模型推薦引擎」**。
在 LLM/VLM 技術快速迭代與 API 費率頻繁調整的背景下，許多企業應用（如 OCR 護照辨識、單據解析、複雜推理）過度依賴頂規高價模型（如 Pro 系列），造成龐大營運成本。

`Model_Arbiter` 透過自動化跑分測試與 Token 精度計費機制，即時比較各主流模型（如 Flash, Flash-Lite, Hybrid Reasoning 2.5, **Gemini 3.5 Flash-Lite** 等）在真實任務下的 **正確率**、**響應延遲** 與 **台幣成本 (TWD)**，並自動產出最佳動態設定檔 `active_configs/<suite>_model.json`，供其他商業專案直接引用，達成「零破壞性更新、極致套利降本」目標。

### 1.2 系統架構圖 (Architecture Diagram)

```mermaid
flowchart TD
    subgraph UserInterface [User Interfaces]
        CLI[run.py CLI Runner]
        WEB[web_runner.py Streamlit GUI Dashboard]
    end

    subgraph CoreEngine [Model_Arbiter Engine]
        DISC[core/discovery.py\nModel Discovery & gemini-3.5-flash-lite]
        PRICER[core/pricer.py\nTWD Precision Pricer]
        EVAL[core/evaluator.py\nSuite Evaluator & Ladder Board]
    end

    subgraph BenchmarkSuites [Benchmark Suites]
        PP[suites/pp_auto/\nPassport OCR Suite]
        IMG[suites/pp_auto/images/\nLocal Image Scanner & Pillow Fallback Generator]
        GT[(test_cases.json\nGround Truth Dataset)]
        HARNESS[harness.py\nMulti-Stage Diagnostic Harness & MRZ Checksum]
    end

    subgraph OutputConfig [Active Configurations]
        CFG[active_configs/pp_auto_model.json]
    end

    CLI --> DISC
    CLI --> EVAL
    WEB --> DISC
    WEB --> EVAL
    EVAL --> PP
    PP --> IMG
    PP --> GT
    PP --> HARNESS
    EVAL --> PRICER
    EVAL -->|Auto Recommender| CFG
```

---

## 2. Key Modules & Directory Structure

```plaintext
Model_Arbiter/
├── .gitignore          # Git 忽略設定（隱藏 API 密碼與 active_configs 實體 JSON）
├── HANDBOOK.md         # 專案核心架構與開發者手冊
├── README.md           # Quick Start 與簡易使用說明
├── requirements.txt    # 輕量依賴清單 (google-genai, pydantic, pillow, tabulate, streamlit)
├── run.py              # CLI 主入口腳本
├── web_runner.py       # Streamlit 視覺化跑分監控面板 (含圖片上傳、路徑提示與除錯展開區)
├── core/
│   ├── __init__.py
│   ├── discovery.py    # 自動撈取 Google 官方活躍多模態模型 (含 gemini-3.5-flash-lite)
│   ├── pricer.py       # 官方費率對照表與 TWD 精算
│   └── evaluator.py    # 跑分評估與 active_model.json 輸出
├── suites/
│   ├── __init__.py
│   └── pp_auto/        # 護照/證件辨識測試套件
│       ├── __init__.py
│       ├── images/     # 實體測試圖片目錄 (支援 JPG/PNG 掃描)
│       │   └── .gitkeep
│       ├── test_cases.json   # Ground Truth 驗證標準
│       └── harness.py        # 測試執行、三階段除錯診斷與 Pillow 合成備援
└── active_configs/
    └── .gitkeep        # Git 目錄追蹤檔
```

---

## 3. Diagnostic & Verification Architecture

### 3.1 測試圖片載入與備援順序 (Image Loading & Fallback Pipeline)
1. **優先順序 1**：`web_runner.py` 上傳之實體圖片檔 (`st.file_uploader`)。
2. **優先順序 2**：本地專案目錄 `suites/pp_auto/images/` 掃描到的 `.jpg`, `.png` 檔案。
3. **優先順序 3 (備援機制)**：若無任何圖片，系統自動調用 Pillow 產出標準 Mock 護照合成圖片 (`generate_synthetic_passport_image()`)，確保隨時可執行跑分且不因缺圖中斷。

### 3.2 三階段透明除錯診斷 (Multi-Stage Diagnostic Tracing)
系統絕不默默吞掉例外，錯誤發生時自動歸類並呈現在 UI 與日誌中：
- **`[環境階段]`**：缺少 API Key、圖片讀取失敗或路徑無效。
- **`[呼叫階段]`**：Google API 401 Unauthorized、403 Forbidden、404 Not Found 或 429 配額限制。
- **`[校驗階段]`**：JSON 解析失敗、ICAO MRZ 檢查碼不符或關鍵欄位不一致。

---

## 4. Development & Verification Guide

### 4.1 視覺化 Web 面板 (Streamlit Dashboard)
```bash
streamlit run web_runner.py
```

### 4.2 本地編譯與驗證 (Verification Commands)

```bash
python -m py_compile run.py web_runner.py core/*.py suites/pp_auto/*.py
```
