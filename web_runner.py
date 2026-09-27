"""
Model_Arbiter - Streamlit Visual Benchmark & Cost Arbitrage Dashboard (`web_runner.py`)
"""

import os
import sys
import json
import time
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional
import streamlit as st

# Ensure UTF-8 output encoding on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from core.discovery import list_candidate_models, get_model_status_badge, probe_model_status
from core.pricer import calculate_cost_ntd, get_model_pricing
from core.evaluator import run_suite_evaluation, recommend_and_export_active_model

# Streamlit Page Config
st.set_page_config(
    page_title="Model_Arbiter 跑分與成本仲裁面板",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
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
</style>
""", unsafe_allow_html=True)


def get_suite_status(suite_name: str) -> Dict[str, Any]:
    """Dynamically retrieves manifest configuration and dataset sample count for the given suite."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    suite_dir = os.path.join(current_dir, "suites", suite_name)
    
    manifest_path = os.path.join(suite_dir, "manifest.json")
    manifest = {}
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except Exception:
            manifest = {}

    inf_cfg = manifest.get("inference_config", {})
    temp = inf_cfg.get("temperature", 0.1)
    thinking_cfg = inf_cfg.get("thinking_config", {})
    thinking_budget = thinking_cfg.get("thinking_budget", 1024)

    test_cases_path = os.path.join(suite_dir, "test_cases.json")
    test_cases = []
    if os.path.exists(test_cases_path):
        try:
            with open(test_cases_path, "r", encoding="utf-8") as f:
                test_cases = json.load(f)
        except Exception:
            test_cases = []

    return {
        "suite_name": suite_name,
        "temperature": temp,
        "thinking_budget": thinking_budget,
        "sample_count": len(test_cases),
        "test_cases": test_cases
    }


def check_active_config_eol(suite_name: str, candidate_models: List[Dict[str, Any]]) -> Tuple[Optional[str], bool, Optional[str]]:
    """Checks if currently active recommended model in active_configs is DEPRECATED/offline."""
    config_file = os.path.join("active_configs", f"{suite_name}_model.json")
    if not os.path.exists(config_file):
        return None, False, None

    try:
        with open(config_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            rec_model = data.get("recommended_model")
            if not rec_model:
                return None, False, None

            matching = next((m for m in candidate_models if m["name"] == rec_model), None)
            if matching and (matching.get("status") == "DEPRECATED" or matching.get("deprecated")):
                rep = matching.get("suggested_replacement") or "gemini-3.8-flash"
                return rec_model, True, rep
            
            if "2.5-flash" in rec_model or "1.0" in rec_model:
                return rec_model, True, "gemini-3.8-flash"

            return rec_model, False, None
    except Exception:
        return None, False, None


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

    # Execution Mode (UI strictly defaults to Live API runner)
    is_mock = False

    # Benchmark Suite Selector
    suite_option = st.sidebar.selectbox(
        "🎯 測試套件 (Benchmark Suite)",
        ["pp_auto"],
        format_func=lambda x: "護照/證件辨識套件 (pp_auto)" if x == "pp_auto" else x
    )

    # Discovered Models & Status Radar
    api_key = api_key_input.strip() if api_key_input else None
    discovered_models = list_candidate_models(api_key=api_key, probe=False)
    active_radar_models = [m for m in discovered_models if not m.get("deprecated") and m.get("status") != "DEPRECATED"]
    deprecated_radar_models = [m for m in discovered_models if m.get("deprecated") or m.get("status") == "DEPRECATED"]

    with st.sidebar.expander(f"📡 市場模型雷達 ({len(active_radar_models)} 個現役可跑分模型)", expanded=False):
        st.markdown("**🟢 現役與新登場模型 (Active Candidate Models)**")
        for m in active_radar_models:
            badge = get_model_status_badge(m)
            st.markdown(f"- {badge}")

        if deprecated_radar_models:
            st.markdown("---")
            st.caption("🔴 已淘汰/除役模型 (Deprecated - 測試自動過濾排除):")
            for m in deprecated_radar_models:
                rep = m.get("suggested_replacement") or "gemini-3.8-flash"
                st.caption(f"• ~{m['name']}~ (已除役 - 建議改用 {rep})")

        st.markdown("---")
        refresh_radar = st.button("🔄 重新整理市場模型雷達", use_container_width=True)
        if refresh_radar:
            with st.spinner("📡 正在向 Google API 探測最新可用模型..."):
                list_candidate_models(api_key=api_key, force_refresh=True, probe=True)
            st.toast("📡 已探測並更新市場模型雷達！", icon="🚀")
            st.rerun()

    # ---------------------------------------------------------
    # 題庫狀態與同步控制卡片 (Benchmark Suite Status & Sync Control)
    # ---------------------------------------------------------
    st.sidebar.markdown("---")
    st.sidebar.subheader("📁 基準題庫與環境規格")

    status_info = get_suite_status(suite_option)
    tb_val = status_info["thinking_budget"]
    if tb_val == -1:
        tb_str = "Dynamic (-1)"
    elif tb_val > 0:
        tb_str = f"{tb_val} Tokens"
    else:
        tb_str = "Disabled (0)"

    temp_str = str(status_info["temperature"])
    sample_count = status_info["sample_count"]

    with st.sidebar.container(border=True):
        st.markdown(f"**🎯 目標套件 (Suite)**：`{suite_option}`")
        st.markdown(f"**🧠 Thinking Budget**：`{tb_str}`")
        st.markdown(f"**🌡️ Temperature**：`{temp_str}`")
        
        if sample_count > 0:
            st.success(f"📦 已載入 **{sample_count}** 筆黃金驗收樣本")
        else:
            st.warning("⚠️ 尚無本地驗收樣本，請點擊下方同步")

    sync_clicked = st.sidebar.button(
        "🔄 自 Registry 同步最新考卷",
        use_container_width=True,
        help="自中央 Google Sheet Web App 拉取最新 Prompt、推論參數與真實題庫"
    )

    if sync_clicked:
        try:
            with st.spinner("☁️ 正在連線至中央 Registry (GAS Web App) 拉取最新環境指紋與真實題庫..."):
                from suites.pp_auto.sync_specs import sync_registry_specs
                res_summary = sync_registry_specs()
            st.toast(f"🎉 考卷與題庫同步完成 (載入 {res_summary.get('synced_cases', 0)} 筆樣本)", icon="☁️")
            time.sleep(0.5)
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"❌ 同步中央 Registry 失敗: {e}")

    st.sidebar.info("💡 **自動化套利機制**：\n當候選模型達成 100% 通過率時，系統自動推薦單本 TWD 成本最低者。")

    # ---------------------------------------------------------
    # 2. 主畫面標題與簡介 (Main Header & EOL Alert Banner)
    # ---------------------------------------------------------
    st.markdown('<div class="main-title">Model_Arbiter 模型自動跑分與成本精算面板</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Google Gemini 多模態模型自動化跑分、思考 Token 精算與最適模型推薦引擎</div>', unsafe_allow_html=True)

    # Production Config EOL Alert Banner
    active_model_name, is_eol, replacement_model = check_active_config_eol(suite_option, discovered_models)
    if is_eol:
        st.error(
            f"🚨 **[EOL 生命週期警示]** 現役生產環境模型 `{active_model_name}` 已被官方下線/停用！\n\n"
            f"💡 **官方建議替代模型**: `{replacement_model}`\n\n"
            f"請立即點擊下方「🚀 開始全自動跑分與成本仲裁」重新評測，並將最適模型覆寫至生產設定檔！",
            icon="⚠️"
        )
    elif active_model_name:
        st.info(f"✅ **[生產環境模型狀態]** 現役設定檔模型 `{active_model_name}` 運作良好，符合極致套利規範。")

    # Action Button
    start_benchmark = st.button("🚀 開始全自動跑分與成本仲裁", type="primary", use_container_width=True)

    # ---------------------------------------------------------
    # 3. 跑分邏輯執行 (Benchmark Execution)
    # ---------------------------------------------------------
    if start_benchmark:
        if not api_key:
            st.error("⚠️ [環境階段] 請在側邊欄輸入有效的 Gemini API Key！")
            return

        with st.spinner("🔍 正在執行市場模型雷達探針，過濾已除役模型並檢索 Gemini 現役多模態模型 (包含 gemini-3.8-flash, 3.5-flash-lite 等主力模型)..."):
            discovered = list_candidate_models(api_key=api_key, force_refresh=True, probe=True)
            active_models = [m for m in discovered if not m.get("deprecated") and m.get("status") != "DEPRECATED"]
            candidate_models = [m["name"] for m in active_models]

        st.markdown(f"**發現 `{len(candidate_models)}` 個活躍現役多模態模型**: `{', '.join(candidate_models)}`")

        progress_bar = st.progress(0)
        status_text = st.empty()

        suite_results = []
        total_models = len(candidate_models)

        for idx, model_name in enumerate(candidate_models):
            status_text.markdown(f"⏳ **正在跑分測試模型 [{idx + 1}/{total_models}]**: `{model_name}`...")
            
            res_list = run_suite_evaluation(
                suite_name=suite_option,
                api_key=api_key,
                candidate_models=[model_name],
                mock=is_mock
            )
            if res_list:
                suite_results.append(res_list[0])

            progress_bar.progress(int(((idx + 1) / total_models) * 100))
            time.sleep(0.05)

        status_text.success("✅ 跑分測試全數完成！")
        progress_bar.progress(100)

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

        sorted_results = sorted(results, key=lambda x: (-x["pass_rate"], x["cost_ntd"], x["avg_latency_sec"]))

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
        # 5. 例外與錯誤日誌排查區 (Detailed Diagnostic Error Section)
        # ---------------------------------------------------------
        failed_models = [r for r in results if r["pass_rate"] < 100.0 or any(c.get("error_details") for c in r.get("case_details", []))]

        if failed_models:
            st.markdown("### ⚠️ 詳細錯誤日誌與階段排查 (Diagnostic Tracing)")
            for fm in failed_models:
                for c in fm.get("case_details", []):
                    if c.get("error_details"):
                        stage = c.get("error_stage", "[未知階段]")
                        with st.expander(f"🔴 檢視模型 `{fm['model_name']}` 錯誤紀錄 ({stage})"):
                            st.markdown(f"**失敗階段**: `{stage}`")
                            st.markdown(f"**圖片來源**: `{c.get('image_source', '未知')}`")
                            st.error(f"**錯誤訊息**: {c.get('error_details')}")
                            if c.get("traceback"):
                                st.code(c["traceback"], language="python")

        # ---------------------------------------------------------
        # 6. 最佳套利推薦卡片 (Champion Recommendation Card)
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

            st.markdown("### 💾 設定檔動態覆寫與同步")
            if st.button("📥 將最佳推薦覆寫至 active_configs/pp_auto_model.json", type="secondary"):
                exported = recommend_and_export_active_model(suite_name=suite_name, results=results)
                if exported:
                    st.toast(f"✅ 成功將最佳模型 [{model_name}] 匯出至 active_configs/pp_auto_model.json！", icon="🎉")
        else:
            st.warning("⚠️ 沒有任何模型達成 100% 通過率門檻，請檢查上方【詳細錯誤日誌與階段排查】區塊進行除錯。")


if __name__ == "__main__":
    main()
