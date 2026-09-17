# Model_Arbiter ⚖️

> **Google Gemini 模型自動跑分、成本精算與最適模型推薦引擎**  
> *Cross-Project Automatic Benchmarking, Precision Cost Arbitrage & Optimal Model Recommender Engine.*

[![Deploy to Streamlit Cloud](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://share.streamlit.io/deploy?repository=voyagermartin/Model_Arbiter&branch=main&mainModule=web_runner.py)

---

## ☁️ 免本地安裝 — 一鍵線上雲端部署 (Streamlit Cloud)

您可以點擊上方 **[Deploy to Streamlit Cloud]** 按鈕，或是點擊下方連結，直接將本專案免費部署至 Streamlit 社群雲端網頁：

🔗 **[點此一鍵線上啟動 Streamlit 雲端 Web 面板](https://share.streamlit.io/deploy?repository=voyagermartin/Model_Arbiter&branch=main&mainModule=web_runner.py)**

*(說明：Streamlit App 需要 Python 後端服務，因此由官方 Streamlit Community Cloud 免費託管運作。只要點擊上方連結即可自動完成雲端部署並取得專屬網址！)*

---

## 💡 簡介 (Overview)

`Model_Arbiter` 是一個跨專案共用的 LLM/VLM 模型評估與套利引擎。透過自動化跑分測試（如護照/證件 OCR、MRZ 數學邏輯嚴格驗算）與 Token 精度計費機制，即時比較各 Google Gemini 模型（包含 Flash、Flash-Lite、Reasoning 2.5 系列）在真實任務下的正確率、延遲與台幣成本 (TWD)，並自動產出最佳動態設定檔 `active_configs/<suite>_model.json` 供其他服務直接引用。

提供 **Streamlit 視覺化跑分監控面板 `web_runner.py`**，包含一鍵執行跑分、性價比天梯榜與即時模型導出功能。

---

## 🚀 快速開始 (Quick Start)

### 1. 線上雲端面板 (Streamlit Cloud)
直接開啟 [https://share.streamlit.io/deploy?repository=voyagermartin/Model_Arbiter&branch=main&mainModule=web_runner.py](https://share.streamlit.io/deploy?repository=voyagermartin/Model_Arbiter&branch=main&mainModule=web_runner.py) 即可全網頁操作。

### 2. 本地開發與 CLI 指令 (CLI Usage)
```bash
# 1. 安裝依賴
pip install -r requirements.txt

# 2. 檢視可用模型
python run.py --list-models

# 3. 本地 Mock harness 跑分測試
python run.py --suite pp_auto --mock

# 4. 使用真實 API Key 執行跑分
python run.py --suite pp_auto --api-key "YOUR_GEMINI_API_KEY"

# 5. 本地啟動 Web 面板
streamlit run web_runner.py
```

---

## 📘 完整架構手冊 (Handbook)

詳細架構設計圖、ICAO MRZ 校驗碼數學公式、Token 計費規則及擴充指南，請參閱 [HANDBOOK.md](HANDBOOK.md)。
