import io
from datetime import datetime
import pandas as pd
import plotly.express as px
import requests
import streamlit as st

st.set_page_config(
    page_title="台灣上市櫃公司債券發行資訊互動分析儀表板",
    layout="wide",
)


# 爬取 MOPS 公司債發行資料
def fetch_bond_data(
    y1: int,
    m1: int,
    d1: int,
    y2: int,
    m2: int,
    d2: int,
    co_id: str = "",
    co_name: str = "",
    market_type: str = "all",
):
    url = "https://mopsov.twse.com.tw/mops/web/ajax_t120sb02_q5"
    target_co_id = co_id.strip()

    # 參數補零與格式化
    payload = {
        "encodeURIComponent": "1",
        "step": "1",
        "firstin": "1",
        "off": "1",
        "TYPEK": market_type,
        "year1": str(y1),
        "month1": f"{int(m1):02d}",
        "day1": f"{int(d1):02d}",
        "year2": str(y2),
        "month2": f"{int(m2):02d}",
        "day2": f"{int(d2):02d}",
        "co_id1": target_co_id,
        "co_id2": target_co_id,
        "co_name": co_name.strip(),
        "is_pay": "Y",
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": "https://mopsov.twse.com.tw/mops/web/t120sb02_q5",
        "Origin": "https://mopsov.twse.com.tw",
        "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    try:
        resp = requests.post(url, data=payload, headers=headers, timeout=25)
        resp.encoding = "utf-8"

        # 若 MOPS 回傳查無資料或內容中無表格
        if (
            "查無" in resp.text
            or "無符合" in resp.text
            or "<table" not in resp.text.lower()
        ):
            return pd.DataFrame()

        # 解析 HTML 表格
        try:
            tables = pd.read_html(io.StringIO(resp.text))
        except ValueError:
            return pd.DataFrame()

        target_df = None
        for df in tables:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [
                    "_".join([str(c) for c in col if str(c) != "nan"]).strip()
                    for col in df.columns
                ]

            cols_str = " ".join([str(c) for c in df.columns])
            row0_str = (
                " ".join([str(v) for v in df.iloc[0].values])
                if len(df) > 0
                else ""
            )

            if (
                "公司代號" in cols_str
                or "債券簡稱" in cols_str
                or "公司代號" in row0_str
            ):
                if "公司代號" in row0_str and "公司代號" not in cols_str:
                    df.columns = df.iloc[0]
                    df = df.iloc[1:].reset_index(drop=True)
                target_df = df
                break

        if target_df is None or target_df.empty:
            return pd.DataFrame()

        target_df.columns = [
            str(c).replace(" ", "").strip() for c in target_df.columns
        ]

        if "公司代號" in target_df.columns:
            target_df = target_df[
                target_df["公司代號"].astype(str).str.strip() != "公司代號"
            ]

        if "發行總額" in target_df.columns:
            target_df["發行總額_數值"] = (
                target_df["發行總額"]
                .astype(str)
                .str.replace(",", "")
                .str.replace("--", "0")
                .str.strip()
            )
            target_df["發行總額_數值"] = pd.to_numeric(
                target_df["發行總額_數值"], errors="coerce"
            ).fillna(0)

        if "票面利率" in target_df.columns:
            target_df["票面利率_數值"] = (
                target_df["票面利率"]
                .astype(str)
                .str.replace("%", "")
                .str.strip()
            )
            target_df["票面利率_數值"] = pd.to_numeric(
                target_df["票面利率_數值"], errors="coerce"
            ).fillna(0.0)

        return target_df.reset_index(drop=True)

    except Exception as e:
        st.error(f"連線異常：{e}")
        return pd.DataFrame()


# 側邊欄設定
st.sidebar.header("🔍 查詢條件設定")
market_opt = {"全部": "all", "上市": "sii", "上櫃": "otc", "興櫃": "rotc"}
selected_market = st.sidebar.selectbox("市場別", list(market_opt.keys()))

st.sidebar.markdown("**發行起日 (民國)**")
col_y1, col_m1, col_d1 = st.sidebar.columns(3)
with col_y1:
    y1 = st.number_input("年", min_value=80, max_value=150, value=113, step=1)
with col_m1:
    m1 = st.number_input("月", min_value=1, max_value=12, value=1, step=1)
with col_d1:
    d1 = st.number_input("日", min_value=1, max_value=31, value=1, step=1)

st.sidebar.markdown("**發行迄日 (民國)**")
col_y2, col_m2, col_d2 = st.sidebar.columns(3)
with col_y2:
    y2 = st.number_input(
        "年 ", min_value=80, max_value=150, value=113, step=1
    )
with col_m2:
    m2 = st.number_input("月 ", min_value=1, max_value=12, value=12, step=1)
with col_d2:
    d2 = st.number_input("日 ", min_value=1, max_value=31, value=31, step=1)

input_co_id = st.sidebar.text_input("公司代號（選填，如：1328）", "")
input_co_name = st.sidebar.text_input("公司名稱（選填，如：中油）", "")

query_btn = st.sidebar.button("🚀 開始查詢", type="primary", use_container_width=True)

# 主頁面
st.title("🏛️ 台灣上市櫃公司債券發行資訊互動分析儀表板")
st.caption(
    "串接公開資訊觀測站 (MOPS) 普通公司債 ➜ 歷史資料查詢 (t120sb02_q5)"
)

if query_btn:
    with st.spinner("正在向公開資訊觀測站請求資料..."):
        df = fetch_bond_data(
            y1,
            m1,
            d1,
            y2,
            m2,
            d2,
            input_co_id,
            input_co_name,
            market_opt[selected_market],
        )
        st.session_state["bond_data"] = df

if "bond_data" in st.session_state:
    raw_df = st.session_state["bond_data"]

    if not raw_df.empty:
        total_bonds = len(raw_df)
        total_amount = (
            raw_df["發行總額_數值"].sum()
            if "發行總額_數值" in raw_df.columns
            else 0
        )
        avg_rate = (
            raw_df["票面利率_數值"].mean()
            if "票面利率_數值" in raw_df.columns
            else 0
        )

        m1_card, m2_card, m3_card = st.columns(3)
        m1_card.metric("發行總筆數", f"{total_bonds:,} 筆")
        m2_card.metric("發行總金額合計", f"{total_amount / 1e8:,.2f} 億元")
        m3_card.metric("平均票面利率", f"{avg_rate:.3f} %")

        st.markdown("---")

        st.subheader("⚙️ 資料排序與篩選")
        c1, c2, c3 = st.columns([2, 2, 2])

        sort_options = [
            c
            for c in ["發行日期", "發行總額_數值", "票面利率_數值", "公司代號"]
            if c in raw_df.columns
        ]
        with c1:
            sort_by = st.selectbox(
                "排序欄位", options=sort_options, index=0 if sort_options else 0
            )
        with c2:
            sort_order = st.radio(
                "排序方向",
                ["降冪 (大到小 / 新到舊)", "升冪 (小到大 / 舊到新)"],
                horizontal=True,
            )
        with c3:
            filter_co = st.multiselect(
                "依公司名稱過濾",
                options=raw_df["公司名稱"].unique()
                if "公司名稱" in raw_df.columns
                else [],
                default=[],
            )

        display_df = raw_df.copy()
        if filter_co and "公司名稱" in display_df.columns:
            display_df = display_df[display_df["公司名稱"].isin(filter_co)]

        ascending = True if "升冪" in sort_order else False
        if sort_by in display_df.columns:
            display_df = display_df.sort_values(by=sort_by, ascending=ascending)

        tab1, tab2 = st.tabs(["📋 資料清單", "📈 統計圖表分析"])

        with tab1:
            view_cols = [c for c in display_df.columns if not c.endswith("_數值")]
            st.dataframe(
                display_df[view_cols], use_container_width=True, hide_index=True
            )

            csv_data = display_df[view_cols].to_csv(index=False).encode(
                "utf_8_sig"
            )
            st.download_button(
                label="💾 匯出查詢結果 (CSV)",
                data=csv_data,
                file_name=f"bond_data_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
            )

        with tab2:
            col_chart1, col_chart2 = st.columns(2)
            if (
                "公司名稱" in display_df.columns
                and "發行總額_數值" in display_df.columns
            ):
                top_emitters = (
                    display_df.groupby("公司名稱")["發行總額_數值"]
                    .sum()
                    .reset_index()
                    .sort_values(by="發行總額_數值", ascending=False)
                    .head(10)
                )
                top_emitters["發行金額(億)"] = (
                    top_emitters["發行總額_數值"] / 1e8
                )

                fig1 = px.bar(
                    top_emitters,
                    x="公司名稱",
                    y="發行金額(億)",
                    title="發行金額前 10 大公司 (億元)",
                    text_auto=".2f",
                    color="發行金額(億)",
                    color_continuous_scale="Blues",
                )
                col_chart1.plotly_chart(fig1, use_container_width=True)

            if (
                "發行日期" in display_df.columns
                and "票面利率_數值" in display_df.columns
            ):
                fig2 = px.scatter(
                    display_df,
                    x="發行日期",
                    y="票面利率_數值",
                    size="發行總額_數值",
                    hover_data=[
                        c
                        for c in ["公司名稱", "債券簡稱"]
                        if c in display_df.columns
                    ],
                    title="票面利率分佈 (氣泡大小代表發行金額)",
                    labels={"票面利率_數值": "票面利率 (%)"},
                )
                col_chart2.plotly_chart(fig2, use_container_width=True)
    else:
        st.warning("查無符合條件的債券發行資料，請調整日期或條件後重新查詢。")
