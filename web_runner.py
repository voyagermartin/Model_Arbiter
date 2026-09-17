"""
Model_Arbiter - Streamlit Visual Benchmark & Cost Arbitrage Dashboard (`web_runner.py`)
"""

import os
import sys
import json
import time
from datetime import datetime
import streamlit as st

# Ensure UTF-8 output encoding on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from core.discovery import list_candidate_models
from core.pricer import calculate_cost_ntd, get_model_pricing
from core.evaluator import run_suite_evaluation, recommend_and_export_active_model

# Streamlit Page Config
st.set_page_config(
    page_title="Model_Arbiter 跑分與成本仲裁面板",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling (Glassmorphism & Metric Cards)
st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        background: linear-gradient(135deg, #4F46E5 0%, #06B6D4 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    .subtitle {
        color: #6B7280;
        font-size: 1.05rem;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(229, 231, 235, 0.2);
        border-radius: 12px;
        padding: 1.25rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        text-align: center;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #10B981;
    }
    .metric-label {
        font-size: 0.875rem;
        color: #9CA3AF;
        margin-top: 0.25rem;
    }
    .champion-banner {
        background: linear-gradient(135deg, #059669 0%, #10B981 100%);
        color: white;
        padding: 1.25rem;
        border-radius: 12px;
        margin-top: 1rem;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)


def main():
    # ---------------------------------------------------------
    # 1. 側邊欄設定 (Sidebar Settings)
    # ---------------------------------------------------------
    st.sidebar.title("⚖️ Model_Arbiter 控制台")
    st.sidebar.markdown("---")

    # API Key Input
    env_api_key = os.environ.get("GEMINI_API_KEY", "")
    api_key_input = st.sidebar.text_input(
        "🔑 Gemini API Key",
        value=env_api_key,
        type="password",
        help="輸入 Google Gemini API Key (若已設定 GEMINI_API_KEY 環境變數則自動帶入)"
    )

    # Execution Mode Switch
    mode_option = st.sidebar.radio(
        "⚙️ 執行模式 (Execution Mode)",
        ["🔘 離線快速模擬 (Mock)", "🔴 真實 API 跑分"],
        index=0
    )
    is_mock = "Mock" in mode_option

    # Benchmark Suite Selector
    suite_option = st.sidebar.selectbox(
        "🎯 測試套件 (Benchmark Suite)",
        ["pp_auto"],
        format_func=lambda x: "護照/證件辨識套件 (pp_auto)" if x == "pp_auto" else x
    )

    st.sidebar.markdown("---")
    st.sidebar.info("💡 **自動化套利機制**：\n當候選模型達成 100% 通過率時，系統自動推薦單本 TWD 成本最低者。")

    # ---------------------------------------------------------
    # 2. 主畫面標題與簡介 (Main Header)
    # ---------------------------------------------------------
    st.markdown('<div class="main-title">Model_Arbiter 模型自動跑分與成本精算面板</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Google Gemini 多模態模型自動化跑分、思考 Token 精算與最適模型推薦引擎</div>', unsafe_allow_html=True)

    # Action Button
    start_benchmark = st.button("🚀 開始全自動跑分與成本仲裁", type="primary", use_container_width=True)

    # ---------------------------------------------------------
    # 3. 跑分邏輯執行 (Benchmark Execution)
    # ---------------------------------------------------------
    if start_benchmark:
        api_key = api_key_input.strip() if api_key_input else None

        if not is_mock and not api_key:
            st.error("⚠️ 請在側邊欄輸入有效的 Gemini API Key 或切換為「離線快速模擬 (Mock)」模式！")
            return

        # Fetch active candidate models
        with st.spinner("🔍 正在檢索 Gemini 活躍多模態模型清單..."):
            discovered = list_candidate_models(api_key=api_key)
            candidate_models = [m["name"] for m in discovered if not m.get("deprecated")]

        st.markdown(f"**發現 `{len(candidate_models)}` 個活躍多模態模型**: `{', '.join(candidate_models)}`")

        progress_bar = st.progress(0)
        status_text = st.empty()

        suite_results = []
        total_models = len(candidate_models)

        for idx, model_name in enumerate(candidate_models):
            status_text.markdown(f"⏳ **正在跑分測試模型 [{idx + 1}/{total_models}]**: `{model_name}`...")
            
            # Execute benchmark for this specific model
            res_list = run_suite_evaluation(
                suite_name=suite_option,
                api_key=api_key,
                candidate_models=[model_name],
                mock=is_mock
            )
            if res_list:
                suite_results.append(res_list[0])

            progress_bar.progress(int(((idx + 1) / total_models) * 100))
            time.sleep(0.1)

        status_text.success("✅ 跑分測試全數完成！")
        progress_bar.progress(100)

        # Store in session state
        st.session_state["benchmark_results"] = suite_results
        st.session_state["suite_name"] = suite_option

    # ---------------------------------------------------------
    # 4. 視覺化結果展示 (Visual Output & Leaderboard)
    # ---------------------------------------------------------
    if "benchmark_results" in st.session_state and st.session_state["benchmark_results"]:
        results = st.session_state["benchmark_results"]
        suite_name = st.session_state.get("suite_name", "pp_auto")

        st.markdown("---")
        st.subheader("📊 性價比天梯榜 (Benchmark Leaderboard)")

        # Sort results: Pass Rate DESC, Cost ASC, Latency ASC
        sorted_results = sorted(results, key=lambda x: (-x["pass_rate"], x["cost_ntd"], x["avg_latency_sec"]))

        # Build Dataframe table rows
        table_rows = []
        for rank, r in enumerate(sorted_results, 1):
            is_champion = (rank == 1 and r["pass_rate"] == 100.0)
            status_badge = "👑 Champion" if is_champion else ("✅ Pass" if r["pass_rate"] == 100.0 else "❌ Failed")
            
            table_rows.append({
                "排名 (Rank)": f"#{rank}",
                "模型代碼 (Model ID)": r["model_name"],
                "狀態 (Status)": status_badge,
                "通過率 (Pass Rate)": f"{r['pass_rate']:.1f}%",
                "平均延遲 (Latency)": f"{r['avg_latency_sec']:.3f} s",
                "Prompt Tokens": r["prompt_tokens"],
                "Thought Tokens": r["thought_tokens"],
                "Output Tokens": r["candidate_tokens"],
                "單本台幣成本 (TWD)": f"NT${r['cost_ntd']:.6f}"
            })

        st.dataframe(table_rows, use_container_width=True)

        # ---------------------------------------------------------
        # 5. 最佳套利推薦卡片 (Champion Recommendation Card)
        # ---------------------------------------------------------
        eligible = [r for r in results if r["pass_rate"] == 100.0]

        if eligible:
            best_model = min(eligible, key=lambda x: (x["cost_ntd"], x["avg_latency_sec"]))
            model_name = best_model["model_name"]
            pricing = get_model_pricing(model_name)

            avg_prompt = best_model["prompt_tokens"] / best_model["total_cases"]
            avg_candidate = best_model["candidate_tokens"] / best_model["total_cases"]
            avg_thought = best_model["thought_tokens"] / best_model["total_cases"]

            cost_per_1k_ntd = calculate_cost_ntd(
                model_name=model_name,
                prompt_tokens=int(avg_prompt * 1000),
                candidate_tokens=int(avg_candidate * 1000),
                thought_tokens=int(avg_thought * 1000)
            )

            st.markdown("### 🏆 最佳套利模型推薦 (Optimal Model Recommendation)")

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("👑 推薦模型", model_name)
            with col2:
                st.metric("🎯 通過率", f"{best_model['pass_rate']}%")
            with col3:
                st.metric("⚡ 平均延遲", f"{best_model['avg_latency_sec']} s")
            with col4:
                st.metric("💰 每千次預估成本", f"NT${cost_per_1k_ntd:.4f}")

            st.success(
                f"**[仲裁結論]** 模型 `{model_name}` 達成 100% 驗收通過率，且每千次辨識成本僅新台幣 **NT${cost_per_1k_ntd:.4f}**，為最佳極致降本選擇！"
            )

            # ---------------------------------------------------------
            # 6. 一鍵匯出 Active Config 按鈕 (Export Button)
            # ---------------------------------------------------------
            st.markdown("### 💾 設定檔動態覆寫與同步")
            if st.button("📥 將最佳推薦覆寫至 active_configs/pp_auto_model.json", type="secondary"):
                exported = recommend_and_export_active_model(suite_name=suite_name, results=results)
                if exported:
                    st.toast(f"✅ 成功將最佳模型 [{model_name}] 匯出至 active_configs/pp_auto_model.json！", icon="🎉")
        else:
            st.warning("⚠️ 沒有任何模型達成 100% 通過率門檻，無法進行自動套利覆寫。")


if __name__ == "__main__":
    main()
