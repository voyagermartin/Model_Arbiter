# Model_Arbiter ⚖️

> **Google Gemini 模型自動跑分、成本精算與最適模型推薦引擎**  
> *Cross-Project Automatic Benchmarking, Precision Cost Arbitrage & Optimal Model Recommender Engine.*

---

## 💡 簡介 (Overview)

`Model_Arbiter` 是一個跨專案共用的 LLM/VLM 模型評估與套利引擎。透過自動化跑分測試（如護照/證件 OCR、MRZ 數學邏輯嚴格驗算）與 Token 精度計費機制，即時比較各 Google Gemini 模型（包含 Flash、Flash-Lite、Reasoning 2.5 系列）在真實任務下的正確率、延遲與台幣成本 (TWD)，並自動產出最佳動態設定檔 `active_configs/<suite>_model.json` 供其他服務直接引用。

---

## 🚀 快速開始 (Quick Start)

### 1. 安裝依賴 (Installation)
```bash
pip install -r requirements.txt
```

### 2. 檢視可用模型 (List Candidate Models)
```bash
python run.py --list-models
```

### 3. 執行 Benchmark 跑分與自動套利推薦 (Run Benchmark Suite)
```bash
# 本地 Mock harness 測試
python run.py --suite pp_auto --mock

# 使用真實 API Key 執行跑分
python run.py --suite pp_auto --api-key "YOUR_GEMINI_API_KEY"
```

---

## 📊 輸出範例 (Leaderboard & Active Config)

### 1. ASCII 對比天梯榜 (Ladderboard Output)
```plaintext
==========================================================================================
📊 MODEL ARBITER BENCHMARK LEADERBOARD — SUITE: [PP_AUTO]
==========================================================================================
┌───────┬───────────────────────┬────────────────┬────────────────┬─────────────────┬─────────────────┬─────────────────┬──────────────┐
│ Rank  │ Model Name            │ Pass Rate (%)  │ Avg Latency (s)│ Prompt Tokens   │ Thought Tokens  │ Output Tokens   │ Cost (TWD)   │
├───────┼───────────────────────┼────────────────┼────────────────┼─────────────────┼─────────────────┼─────────────────┼──────────────┤
│ 👑 1  │ gemini-2.0-flash-lite │ 100.0%         │ 0.050          │ 640             │ 0               │ 220             │ NT$0.002816  │
│    2  │ gemini-2.0-flash      │ 100.0%         │ 0.050          │ 640             │ 128             │ 220             │ NT$0.004480  │
│    3  │ gemini-2.5-flash      │ 100.0%         │ 0.050          │ 640             │ 128             │ 220             │ NT$0.004480  │
└───────┴───────────────────────┴────────────────┴────────────────┴─────────────────┴─────────────────┴─────────────────┴──────────────┘
==========================================================================================

🎯 [AUTO RECOMMENDER] Optimal active model exported to: active_configs/pp_auto_model.json
   ► Selected Model : gemini-2.0-flash-lite
   ► Pass Rate      : 100.0%
   ► Est. Cost/1k   : NT$1.4080
```

### 2. 匯出設定檔 (`active_configs/pp_auto_model.json`)
```json
{
  "suite": "pp_auto",
  "recommended_model": "gemini-2.0-flash-lite",
  "pass_rate": 100.0,
  "avg_latency_sec": 0.05,
  "estimated_cost_ntd_per_1000_req": 1.408,
  "pricing_rule_usd_per_1m": {
    "input_per_1m": 0.075,
    "output_per_1m": 0.3,
    "thought_per_1m": 0.3
  },
  "evaluated_at": "2026-09-17T20:00:00+08:00"
}
```

---

## 📘 完整架構手冊 (Handbook)

詳細架構設計圖、ICAO MRZ 校驗碼數學公式、Token 計費規則及擴充指南，請參閱 [HANDBOOK.md](HANDBOOK.md)。
