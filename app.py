import datetime
import io
import re
import urllib3
from bs4 import BeautifulSoup
import numpy as np
import pandas as pd
import plotly.express as px
import requests
import streamlit as st

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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


def create_mops_session():
    """建立具備完整瀏覽器特徵的連線 Session"""
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                " (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://mopsov.twse.com.tw/mops/web/t120sb02_q5",
            "Origin": "https://mopsov.twse.com.tw",
        }
    )
    return s


def parse_mops_html(html_text):
    """精準解析公開資訊觀測站 HTML 表格，完整抓取所有官方真實資料列"""
    soup = BeautifulSoup(html_text, "html.parser")
    tables = soup.find_all("table")
    records = []

    for tbl in tables:
        rows = tbl.find_all("tr")
        for r in rows:
            cells = [c.get_text(strip=True) for c in r.find_all(["td", "th"])]
            if len(cells) < 10:
                continue

            # 排除非資料列、表頭列、無效提示字樣
            first_cell = cells[0]
            if (
                "公司代號" in first_cell
                or "市場別" in first_cell
                or "查無資料" in first_cell
                or "合計" in first_cell
            ):
                continue

            # 只要第一欄為股票代號或統一編號（英數字）且包含公司債或幣別
            if re.match(r"^[0-9A-Za-z]+$", first_cell) and any(
                "公司債" in c or "新台幣" in c or "外幣" in c for c in cells
            ):
                while len(cells) < 13:
                    cells.append("")
                records.append(cells[:13])

    if records:
        return pd.DataFrame(records, columns=HEADERS_13)
    return pd.DataFrame()


def fetch_from_mops(year, market_code, params):
    """直接向觀測站發送精確查詢請求"""
    url = "https://mopsov.twse.com.tw/mops/web/ajax_t120sb02_q5"
    s = create_mops_session()

    m1 = params.get("m1", "1") if str(year) == params.get("y1") else "1"
    d1 = params.get("d1", "1") if str(year) == params.get("y1") else "1"
    m2 = params.get("m2", "12") if str(year) == params.get("y2") else "12"
    d2 = params.get("d2", "31") if str(year) == params.get("y2") else "31"

    payload = {
        "encodeURIComponent": "1",
        "step": "1",
        "firstin": "true",
        "offering_type": "5",  # 普通公司債
        "TYPEK": market_code,
        "code1": params.get("bond_id", ""),
        "code2": params.get("bond_id", ""),
        "co_id1": params.get("co_id", ""),
        "co_id2": params.get("co_id", ""),
        "co_name": params.get("co_name", ""),
        "b_date_y1": str(year),
        "b_date_m1": str(m1),
        "b_date_d1": str(d1),
        "b_date_y2": str(year),
        "b_date_m2": str(m2),
        "b_date_d2": str(d2),
        "is_principal": "1",
        "is_mature": params.get("is_mature", "0"),
    }

    try:
        resp = s.post(url, data=payload, timeout=15, verify=False)
        resp.encoding = "utf-8"
        return parse_mops_html(resp.text)
    except Exception:
        return pd.DataFrame()


def query_multi_year_engine(params):
    """多年度全量即時檢索核心（100% 官方真實數據）"""
    y_start = int(params.get("y1", 113))
    y_end = int(params.get("y2", 113))
    target_market = params.get("typek", "all")

    if target_market == "all":
        markets = ["sii", "otc", "rotc", "pub"]
    else:
        markets = [target_market]

    collected = []

    # 分年、分市場向公開資訊觀測站取得所有真實資料
    for yr in range(y_start, y_end + 1):
        for m in markets:
            df_mops = fetch_from_mops(yr, m, params)
            if not df_mops.empty:
                collected.append(df_mops)

    if not collected:
        return (
            pd.DataFrame(),
            f"公開資訊觀測站於民國 {y_start} ~ {y_end} 年所選條件下查無資料，或連線逾時。",
        )

    combined = pd.concat(collected, ignore_index=True)

    # 依照「債券代碼」與「發行日期」等唯一鍵進行嚴格去重
    combined.drop_duplicates(
        subset=["公司代號", "債券代碼", "發行日期", "債券期別", "券別"],
        inplace=True,
    )

    # 關鍵字篩選
    cid = params.get("co_id", "").strip()
    cname = params.get("co_name", "").strip()
    bid = params.get("bond_id", "").strip()

    if cid:
        combined = combined[
            combined["公司代號"].astype(str).str.contains(cid, case=False, na=False)
        ]
    if cname:
        combined = combined[
            combined["公司名稱"]
            .astype(str)
            .str.contains(cname, case=False, na=False)
        ]
    if bid:
        combined = combined[
            combined["債券代碼"].astype(str).str.contains(bid, case=False, na=False)
        ]

    # 日期精確數值過濾
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

    combined["日期_數值"] = combined["發行日期"].apply(get_date_score)
    start_score = (
        y_start * 10000
        + int(params.get("m1", 1)) * 100
        + int(params.get("d1", 1))
    )
    end_score = (
        y_end * 10000
        + int(params.get("m2", 12)) * 100
        + int(params.get("d2", 31))
    )

    filtered_df = combined[
        (combined["日期_數值"] >= start_score)
        & (combined["日期_數值"] <= end_score)
    ].copy()

    if not filtered_df.empty:
        # 清理並轉換金額欄位
        filtered_df["發行總額_數值"] = (
            filtered_df["發行總額"].astype(str).str.replace(",", "").str.strip()
        )
        filtered_df["發行總額_數值"] = pd.to_numeric(
            filtered_df["發行總額_數值"], errors="coerce"
        ).fillna(0)

        # 清理並轉換利率欄位
        filtered_df["票面利率_數值"] = pd.to_numeric(
            filtered_df["票面利率"].astype(str).str.replace("%", "").str.strip(),
            errors="coerce",
        ).fillna(0)

        # 清理月底餘額
        filtered_df["月底餘額_數值"] = (
            filtered_df["月底餘額"].astype(str).str.replace(",", "").str.strip()
        )
        filtered_df["月底餘額_數值"] = pd.to_numeric(
            filtered_df["月底餘額_數值"], errors="coerce"
        ).fillna(0)

        # 提取發行民國年度（例如 113年）供統計分組
        filtered_df["發行年度"] = filtered_df["發行日期"].apply(
            lambda x: str(x).split("/")[0] + "年" if "/" in str(x) else ""
        )

        return (
            filtered_df,
            f"已成功從公開資訊觀測站取得民國 {y_start} 年 ~ {y_end} 年真實發行紀錄",
        )

    return pd.DataFrame(), "所選條件與區間內查無符合的發行紀錄。"


# --- 前端介面佈局 ---
st.title("🏛️ 台灣上市櫃公司債券發行資訊互動分析儀表板")
st.caption("串接公開資訊觀測站 (MOPS) 普通公司債 ➜ 歷史資料查詢 (t120sb02_q5)")

st.sidebar.header("🔍 1. 查詢參數設定")

with st.sidebar.form(key="mops_search_form"):
    market_choice = st.selectbox(
        "市場別",
        options=["all", "sii", "otc", "rotc", "pub"],
        index=0,
        format_func=lambda x: {
            "all": "全部 (上市+上櫃+興櫃+公開發行)",
            "sii": "上市",
            "otc": "上櫃",
            "rotc": "興櫃",
            "pub": "公開發行",
        }[x],
    )

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
    comp_id = st.text_input(
        "依發行公司代號查詢", placeholder="例：2330、2883 (留空查詢全部)"
    )
    comp_name = st.text_input(
        "依發行公司名稱查詢", placeholder="例：台積電、中油 (留空查詢全部)"
    )
    bond_id = st.text_input("依債券代號查詢", placeholder="例：B88101")
    mature_status = st.radio(
        "債券狀態",
        options=[("0", "未到期債券"), ("1", "已到期債券")],
        format_func=lambda x: x[1],
    )

    submit_btn = st.form_submit_button(
        "🚀 送出查詢觀測站", type="primary", use_container_width=True
    )

if submit_btn:
    params = {
        "typek": market_choice,
        "co_id": comp_id,
        "co_name": comp_name,
        "bond_id": bond_id,
        "y1": str(y1),
        "m1": str(m1),
        "d1": str(d1),
        "y2": str(y2),
        "m2": str(m2),
        "d2": str(d2),
        "is_mature": mature_status[0],
    }
    with st.spinner(f"正在連線公開資訊觀測站檢索民國 {y1} 年 ~ {y2} 年數據..."):
        df_res, msg_res = query_multi_year_engine(params)
    st.session_state["bond_data"] = df_res
    st.session_state["msg"] = msg_res
    st.session_state["curr_y1"] = y1
    st.session_state["curr_y2"] = y2

# 預設初始化 (首次載入 113 全年度)
if "bond_data" not in st.session_state:
    p_init = {
        "typek": "all",
        "y1": "113",
        "m1": "1",
        "d1": "1",
        "y2": "113",
        "m2": "12",
        "d2": "31",
        "is_mature": "0",
    }
    df_init, msg_init = query_multi_year_engine(p_init)
    st.session_state["bond_data"] = df_init
    st.session_state["msg"] = msg_init
    st.session_state["curr_y1"] = 113
    st.session_state["curr_y2"] = 113

raw_df = st.session_state.get("bond_data", pd.DataFrame())

if not raw_df.empty:
    st.success(
        f"🎉 {st.session_state.get('msg', '成功')}！共取得"
        f" **{len(raw_df)}** 筆真實債券發行紀錄。"
    )

    # 1. 核心看板 (單位：億新台幣)
    k1, k2, k3, k4 = st.columns(4)
    tot_amt = raw_df["發行總額_數值"].sum()
    tot_amt_billion = tot_amt / 100_000_000
    k1.metric("總發行規模 (億新台幣)", f"{tot_amt_billion:,.2f} 億元")
    k2.metric("發行總檔數", f"{len(raw_df):,} 檔")
    valid_rates = raw_df[raw_df["票面利率_數值"] > 0]["票面利率_數值"]
    k3.metric(
        "平均票面利率",
        f"{valid_rates.mean():.3f}%" if not valid_rates.empty else "N/A",
    )
    k4.metric("涵蓋發行公司", f"{raw_df['公司名稱'].nunique():,} 家")

    st.markdown("---")

    # 2. 排序控制台
    st.subheader("⚙️ 2. 進一步互動分析與指令排序")
    ctrl1, ctrl2, ctrl3 = st.columns(3)
    with ctrl1:
        sort_by = st.selectbox(
            "選擇分析排序維度",
            options=[
                "發行日期",
                "發行總額 (金額大小)",
                "票面利率",
                "公司名稱",
                "公司代號",
                "到期日期",
            ],
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
            [x for x in raw_df["公司名稱"].unique() if x]
        )
        filter_comp = st.selectbox("依發行公司篩選", options=all_comps)

    display_df = raw_df.copy()
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
    elif sort_by == "到期日期":
        display_df = display_df.sort_values(by="到期日期", ascending=is_asc)

    st.subheader("📋 債券發行詳細清單 (與觀測站欄位完全一致)")
    st.dataframe(display_df[HEADERS_13], use_container_width=True, height=420)

    # 3. 視覺化統計圖表
    st.markdown("---")
    st.subheader("📊 3. 視覺化統計圖表")
    ch1, ch2 = st.columns(2)

    cur_start_y = st.session_state.get("curr_y1", 113)
    cur_end_y = st.session_state.get("curr_y2", 113)

    with ch1:
        top_companies = (
            raw_df[raw_df["公司名稱"] != ""]
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
            title=(
                f"🏢 {cur_start_y} ~ {cur_end_y} 年發行規模 Top 10 公司"
                " (億新台幣)"
            ),
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
        # 單年度獨立統計發行規模
        yearly_summary = (
            raw_df[raw_df["發行年度"] != ""]
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
            title=f"📈 {cur_start_y} ~ {cur_end_y} 年歷年債券發行總額趨勢",
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
        label="📥 匯出當前分析與排序後的表格 (CSV 格式，供 Gemini 分析)",
        data=csv_bytes,
        file_name=f"mops_bonds_{cur_start_y}_{cur_end_y}_analysis.csv",
        mime="text/csv",
        use_container_width=True,
    )
else:
    st.warning("⚠️ 所選條件查無符合的發行紀錄。")
