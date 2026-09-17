# Model_Arbiter ⚖️

> **Google Gemini 模型自動跑分、成本精算與最適模型推薦引擎**  
> *Cross-Project Automatic Benchmarking, Precision Cost Arbitrage & Optimal Model Recommender Engine.*

---

## 💡 簡介 (Overview)

`Model_Arbiter` 是一個跨專案共用的 LLM/VLM 模型評估與套利引擎。透過自動化跑分測試（如護照/證件 OCR、MRZ 數學邏輯嚴格驗算）與 Token 精度計費機制，即時比較各 Google Gemini 模型（包含 Flash、Flash-Lite、Reasoning 2.5 系列）在真實任務下的正確率、延遲與台幣成本 (TWD)，並自動產出最佳動態設定檔 `active_configs/<suite>_model.json` 供其他服務直接引用。

新增 **Streamlit 視覺化跑分監控面板 `web_runner.py`**，提供一鍵執行跑分、性價比天梯榜與即時模型導出功能！

---

## 🚀 快速開始 (Quick Start)

### 1. 安裝依賴 (Installation)
```bash
pip install -r requirements.txt
```

### 2. 啟動視覺化 Web 監控面板 (Streamlit Web Dashboard)
```bash
streamlit run web_runner.py
```

### 3. 檢視可用模型與 CLI 跑分 (CLI Commands)
```bash
# 檢視可用模型
python run.py --list-models

# 本地 Mock harness 測試
python run.py --suite pp_auto --mock

# 使用真實 API Key 執行跑分
python run.py --suite pp_auto --api-key "YOUR_GEMINI_API_KEY"
```

---

## 📘 完整架構手冊 (Handbook)

詳細架構設計圖、ICAO MRZ 校驗碼數學公式、Token 計費規則及擴充指南，請參閱 [HANDBOOK.md](HANDBOOK.md)。
