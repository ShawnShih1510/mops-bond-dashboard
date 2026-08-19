# app.py
import os
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="公開資訊觀測站 - 普通公司債歷年查詢與分析系統",
    page_icon="🏛️",
    layout="wide",
)

HEADERS_13 = [
    "公司代號",
    "債券種類",
    "公司名稱",
    "債券代碼",
    "債券簡稱",
    "發行日期",
    "票面利率",
    "到期日期",
    "債券期別",
    "券別",
    "幣別",
    "發行總額",
    "月底餘額",
]


@st.cache_data
def load_data():
    csv_path = "mops_bonds_data.csv"
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path, dtype=str)
    else:
        return pd.DataFrame()

    # 資料前處理與數值轉換
    df["發行總額_數值"] = (
        df["發行總額"].astype(str).str.replace(",", "").str.strip()
    )
    df["發行總額_數值"] = pd.to_numeric(
        df["發行總額_數值"], errors="coerce"
    ).fillna(0)

    df["票面利率_數值"] = pd.to_numeric(
        df["票面利率"].astype(str).str.replace("%", "").str.strip(),
        errors="coerce",
    ).fillna(0)
    df["月底餘額_數值"] = (
        df["月底餘額"].astype(str).str.replace(",", "").str.strip()
    )
    df["月底餘額_數值"] = pd.to_numeric(
        df["月底餘額_數值"], errors="coerce"
    ).fillna(0)

    def get_date_score(d_str):
        try:
            parts = str(d_str).strip().split("/")
            if len(parts) == 3:
                return (
                    int(parts[0]) * 10000 + int(parts[1]) * 100 + int(parts[2])
                )
        except Exception:
            pass
        return 0

    df["日期_數值"] = df["發行日期"].apply(get_date_score)
    df["發行年度"] = df["發行日期"].apply(
        lambda x: str(x).split("/")[0] + "年" if "/" in str(x) else ""
    )
    return df


df_all = load_data()

st.title("🏛️ 台灣上市櫃公司債券發行資訊互動分析儀表板")
st.caption("串接公開資訊觀測站 (MOPS) 普通公司債 ➜ 歷史資料查詢 (t120sb02_q5)")

st.sidebar.header("🔍 1. 查詢參數設定")

with st.sidebar.form(key="search_form"):
    st.subheader("📅 發行日期區間 (民國年)")
    c1, c2 = st.columns(2)
    with c1:
        y1 = st.number_input("開始年", value=113, min_value=90, max_value=120)
        m1 = st.number_input("開始月", value=1, min_value=1, max_value=12)
        d1 = st.number_input("開始日", value=1, min_value=1, max_value=31)
    with c2:
        y2 = st.number_input("結束年", value=113, min_value=90, max_value=120)
        m2 = st.number_input("結束月", value=12, min_value=1, max_value=12)
        d2 = st.number_input("結束日", value=31, min_value=1, max_value=31)

    st.subheader("🏢 公司與代號條件 (選填)")
    comp_id = st.text_input("依發行公司代號查詢", placeholder="例：2330、2883")
    comp_name = st.text_input("依發行公司名稱查詢", placeholder="例：台積電、中油")
    bond_id = st.text_input("依債券代號查詢", placeholder="例：B88101")

    submit_btn = st.form_submit_button(
        "🚀 送出查詢觀測站", type="primary", use_container_width=True
    )

if df_all.empty:
    st.error(
        "⚠️ 尚未找到 `mops_bonds_data.csv`，請先於本機執行 `python update_data.py` 產出資料檔並上傳至 GitHub。"
    )
    st.stop()

# 執行篩選
start_score = y1 * 10000 + m1 * 100 + d1
end_score = y2 * 10000 + m2 * 100 + d2

filtered = df_all[
    (df_all["日期_數值"] >= start_score) & (df_all["日期_數值"] <= end_score)
].copy()

if comp_id.strip():
    filtered = filtered[
        filtered["公司代號"]
        .astype(str)
        .str.contains(comp_id.strip(), case=False, na=False)
    ]
if comp_name.strip():
    filtered = filtered[
        filtered["公司名稱"]
        .astype(str)
        .str.contains(comp_name.strip(), case=False, na=False)
    ]
if bond_id.strip():
    filtered = filtered[
        filtered["債券代碼"]
        .astype(str)
        .str.contains(bond_id.strip(), case=False, na=False)
    ]

if not filtered.empty:
    st.success(
        f"🎉 成功獲取民國 {y1} 年 ~ {y2} 年之債券發行紀錄！共取得 **{len(filtered)}** 筆真實官方紀錄。"
    )

    # 1. 關鍵指標卡
    k1, k2, k3, k4 = st.columns(4)
    tot_amt = filtered["發行總額_數值"].sum()
    tot_amt_billion = tot_amt / 100_000_000
    k1.metric("總發行規模 (億新台幣)", f"{tot_amt_billion:,.2f} 億元")
    k2.metric("發行總檔數", f"{len(filtered):,} 檔")
    valid_rates = filtered[filtered["票面利率_數值"] > 0]["票面利率_數值"]
    k3.metric(
        "平均票面利率",
        f"{valid_rates.mean():.3f}%" if not valid_rates.empty else "N/A",
    )
    k4.metric("涵蓋發行公司", f"{filtered['公司名稱'].nunique():,} 家")

    st.markdown("---")

    # 2. 排序控制台
    st.subheader("⚙️ 2. 進一步互動分析與指令排序")
    ctrl1, ctrl2, ctrl3 = st.columns(3)
    with ctrl1:
        sort_by = st.selectbox(
            "選擇分析排序維度",
            options=["發行日期", "發行總額 (金額大小)", "票面利率", "公司名稱", "公司代號"],
            index=0,
        )
    with ctrl2:
        sort_direction = st.radio(
            "排序方向",
            options=[
                "由大到小 / 由新到舊 (遞減)",
                "由小到大 / 由舊到新 (遞增)",
            ],
            horizontal=True,
        )
    with ctrl3:
        all_comps = ["全部公司"] + sorted(
            [x for x in filtered["公司名稱"].unique() if pd.notna(x) and x]
        )
        filter_comp = st.selectbox("依發行公司篩選", options=all_comps)

    display_df = filtered.copy()
    if filter_comp != "全部公司":
        display_df = display_df[display_df["公司名稱"] == filter_comp]

    is_asc = sort_direction == "由小到大 / 由舊到新 (遞增)"
    if sort_by == "發行日期":
        display_df = display_df.sort_values(by="日期_數值", ascending=is_asc)
    elif "發行總額" in sort_by:
        display_df = display_df.sort_values(
            by="發行總額_數值", ascending=is_asc
        )
    elif "票面利率" in sort_by:
        display_df = display_df.sort_values(
            by="票面利率_數值", ascending=is_asc
        )
    elif sort_by == "公司名稱":
        display_df = display_df.sort_values(by="公司名稱", ascending=is_asc)
    elif sort_by == "公司代號":
        display_df = display_df.sort_values(by="公司代號", ascending=is_asc)

    st.subheader("📋 債券發行詳細清單 (與觀測站欄位完全一致)")
    st.dataframe(display_df[HEADERS_13], use_container_width=True, height=420)

    # 3. 視覺化統計圖表
    st.markdown("---")
    st.subheader("📊 3. 視覺化統計圖表")
    ch1, ch2 = st.columns(2)

    with ch1:
        top_companies = (
            filtered[filtered["公司名稱"] != ""]
            .groupby("公司名稱")["發行總額_數值"]
            .sum()
            .reset_index()
        )
        top_companies = top_companies.sort_values(
            by="發行總額_數值", ascending=False
        ).head(10)
        top_companies["發行金額(億元)"] = (
            top_companies["發行總額_數值"] / 100_000_000
        )

        fig_bar = px.bar(
            top_companies,
            x="發行金額(億元)",
            y="公司名稱",
            orientation="h",
            title=f"🏢 {y1} ~ {y2} 年發行規模 Top 10 公司 (億新台幣)",
            labels={
                "發行金額(億元)": "發行金額 (億新台幣)",
                "公司名稱": "公司名稱",
            },
            color="發行金額(億元)",
            color_continuous_scale="Blues",
        )
        fig_bar.update_layout(yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig_bar, use_container_width=True)

    with ch2:
        yearly_summary = (
            filtered[filtered["發行年度"] != ""]
            .groupby("發行年度", as_index=False)["發行總額_數值"]
            .sum()
        )
        yearly_summary["發行金額(億元)"] = (
            yearly_summary["發行總額_數值"] / 100_000_000
        )
        yearly_summary = yearly_summary.sort_values(by="發行年度")

        fig_year = px.bar(
            yearly_summary,
            x="發行年度",
            y="發行金額(億元)",
            title=f"📈 {y1} ~ {y2} 年歷年債券發行總額趨勢",
            labels={
                "發行年度": "民國年度",
                "發行金額(億元)": "發行總額 (億新台幣)",
            },
            color="發行年度",
            text_auto=".2f",
        )
        st.plotly_chart(fig_year, use_container_width=True)

    st.markdown("---")
    csv_bytes = display_df[HEADERS_13].to_csv(
        index=False, encoding="utf-8-sig"
    ).encode("utf-8-sig")
    st.download_button(
        label="📥 匯出當前分析與排序後的表格 (CSV 格式)",
        data=csv_bytes,
        file_name=f"mops_bonds_{y1}_{y2}_analysis.csv",
        mime="text/csv",
        use_container_width=True,
    )
else:
    st.warning("⚠️ 所選條件查無符合的發行紀錄。")
