# app.py
# テント部品製造ツール Streamlit版

import streamlit as st
import pandas as pd
from calc_core import calc_process_times, count_processes, PROCESSES

st.set_page_config(page_title="テント部品製造ツール", layout="wide")
st.title("テント部品製造ツール")

SAMPLE_MASTER = "sample_部品マスタ.csv"
SAMPLE_ORDER  = "sample_生産指示.csv"
SAMPLE_STAFF  = "sample_人員.csv"

REQUIRED_COLS = {
    "部品マスタ.csv": ["部品ID", "部品名", "縫製_分", "溶着_分", "糸切り_分"],
    "生産指示.csv":   ["部品ID", "個数", "納期"],
    "人員.csv":       ["名前", "稼働時間", "縫製", "溶着", "糸切り"],
}


def load_csv_safe(source, label, dtype=None):
    """CSVを読み込み、列名が想定通りか確認する。
    問題があれば日本語エラーを表示してアプリを止める（生のトレースバックを出さないため）。"""
    try:
        df = pd.read_csv(source, encoding="utf-8-sig", dtype=dtype)
    except Exception:
        st.error(f"❌ 「{label}」を読み込めませんでした。CSV形式のファイルか確認してください。")
        st.stop()

    missing = [c for c in REQUIRED_COLS[label] if c not in df.columns]
    if missing:
        st.error(
            f"❌ 「{label}」に必要な列が見つかりません → {', '.join(missing)}\n\n"
            f"想定している列名：{', '.join(REQUIRED_COLS[label])}"
        )
        st.stop()
    return df


# ── サンプルCSVダウンロード ────────────────────────────────────────
st.subheader("サンプルCSVをダウンロード")
st.caption("列名や形式を確認したいときは、こちらのサンプルをダウンロードして参考にしてください。")

dl_cols = st.columns(3)
sample_downloads = [
    ("部品マスタ.csv", SAMPLE_MASTER),
    ("生産指示.csv",   SAMPLE_ORDER),
    ("人員.csv",       SAMPLE_STAFF),
]
for col, (label, path) in zip(dl_cols, sample_downloads):
    with open(path, "rb") as f:
        col.download_button(f"⬇ {label}", f, file_name=label, mime="text/csv")

# ── CSVアップロード ────────────────────────────────────────────────
st.header("CSVファイルをアップロード")
st.caption("アップロードが無い項目は、動作確認用のサンプルデータで表示されます。")

master_file = st.file_uploader("部品マスタ.csv", type="csv")
order_file  = st.file_uploader("生産指示.csv", type="csv")
staff_file  = st.file_uploader("人員.csv", type="csv")

using_sample = not (master_file and order_file and staff_file)
if using_sample:
    st.info("📌 現在はサンプルデータを表示しています。3つのCSVをすべてアップロードすると、実データの結果に切り替わります。")

# ── データ読み込み ─────────────────────────────────────────────────
master = load_csv_safe(master_file or SAMPLE_MASTER, "部品マスタ.csv", dtype={"部品ID": str})
order  = load_csv_safe(order_file  or SAMPLE_ORDER,  "生産指示.csv",   dtype={"部品ID": str})
staff  = load_csv_safe(staff_file  or SAMPLE_STAFF,  "人員.csv")

merged, totals, missing_ids = calc_process_times(master, order)

if missing_ids:
    st.warning(f"部品マスタに存在しない部品ID → {sorted(missing_ids)}（スキップします）")

# ════════════════════════════════════════════════════════════════════
# フェーズ1：注文別 作業時間 ＋ 工程別合計
# ════════════════════════════════════════════════════════════════════
st.header("📋 フェーズ1：注文別 作業時間")

display_cols = ["部品ID", "部品名", "個数", "納期"] + [p + "_計(分)" for p in PROCESSES]
st.dataframe(merged[display_cols], use_container_width=True, hide_index=True)

st.subheader("工程別合計")
metric_cols = st.columns(len(PROCESSES) + 1)
for i, proc in enumerate(PROCESSES):
    mins = totals[proc]
    hrs  = mins / 60
    metric_cols[i].metric(proc, f"{mins:.0f} 分", f"{hrs:.2f} 時間")

grand_total_min = sum(totals.values())
grand_total_hr  = grand_total_min / 60
metric_cols[-1].metric("全体合計", f"{grand_total_min:.0f} 分", f"{grand_total_hr:.2f} 時間")

# ════════════════════════════════════════════════════════════════════
# フェーズ2：人手チェック
# ════════════════════════════════════════════════════════════════════
st.header("👥 フェーズ2：今日の人手チェック")

st.markdown(
    """
    <style>
    .phase2-text { font-size: 19px; line-height: 1.7; margin: 0.2em 0; }
    </style>
    """,
    unsafe_allow_html=True,
)

total_staff = len(staff)
total_hours = staff["稼働時間"].sum()

staff_count = {}
for proc in PROCESSES:
    can_do = staff[proc].notna() & (staff[proc].astype(str).str.strip() != "")
    staff_count[proc] = int(can_do.sum())

col_a, col_b = st.columns(2)

with col_a:
    st.subheader("① 工程別の必要時間")
    for proc in PROCESSES:
        mins = totals[proc]
        hrs  = mins / 60
        st.markdown(f'<p class="phase2-text"><b>{proc}</b>： {mins:.0f}分（{hrs:.2f}h）</p>', unsafe_allow_html=True)

with col_b:
    st.subheader("② 今日の人手")
    st.markdown(f'<p class="phase2-text">出勤：<b>{total_staff}人</b> / 合計 <b>{total_hours:.1f}時間</b></p>', unsafe_allow_html=True)
    for proc in PROCESSES:
        note = "　← 糸切りを当てる候補" if proc == "糸切り" else ""
        st.markdown(f'<p class="phase2-text">┗ {proc}できる：<b>{staff_count[proc]}人</b>{note}</p>', unsafe_allow_html=True)

total_need_hr  = sum(totals.values()) / 60
total_avail_hr = total_hours

st.subheader("③ 全体は足りる？")
if total_need_hr <= total_avail_hr:
    st.success(f"必要 {total_need_hr:.2f}h ＜ 稼働 {total_avail_hr:.1f}h → ◎ 余裕あり")
else:
    st.warning(f"必要 {total_need_hr:.2f}h ＞ 稼働 {total_avail_hr:.1f}h → △ 不足の可能性あり")

bottleneck = max(totals, key=totals.get)
st.subheader("④ ボトルネック候補")
st.info(f"一番重い工程 → **{bottleneck}**")

# ════════════════════════════════════════════════════════════════════
# フェーズ3：糸切り担当の提案
# ════════════════════════════════════════════════════════════════════
TARGET   = "糸切り"
need_min = totals[TARGET]
hrs      = need_min / 60

can_cut_mask = (
    staff[TARGET].notna() &
    (staff[TARGET].astype(str).str.strip() != "")
)
candidates = staff[can_cut_mask].copy()
candidates["できる工程数"] = candidates.apply(count_processes, axis=1)
candidates = candidates.sort_values(
    by=["できる工程数", "稼働時間"],
    ascending=[True, False]
).reset_index(drop=True)

assignments = []
remaining   = need_min

for _, person in candidates.iterrows():
    if remaining <= 0:
        break
    avail_min = person["稼働時間"] * 60
    assigned  = min(avail_min, remaining)
    assignments.append({
        "名前":       person["名前"],
        "割り当て分": assigned,
    })
    remaining -= assigned

rows = []
for a in assignments:
    person_row = staff[staff["名前"] == a["名前"]].iloc[0]
    proc_names = [
        p for p in PROCESSES
        if pd.notna(person_row[p]) and str(person_row[p]).strip() != ""
    ]
    rows.append({
        "名前":           a["名前"],
        "割り当て（分）": f"{a['割り当て分']:.0f}",
        "できる工程":     "・".join(proc_names) if proc_names else "なし",
    })

total_assigned = sum(a["割り当て分"] for a in assignments)

table_rows_html = "".join(
    f'<tr><td style="padding:10px; border-top:1px solid #f0c896;">{r["名前"]}</td>'
    f'<td style="padding:10px; border-top:1px solid #f0c896;">{r["割り当て（分）"]}</td>'
    f'<td style="padding:10px; border-top:1px solid #f0c896;">{r["できる工程"]}</td></tr>'
    for r in rows
)

if remaining <= 0:
    banner_bg, banner_fg, banner_text = "#d4edda", "#155724", f"合計 {total_assigned:.0f}分 ✓ 充足"
else:
    banner_bg, banner_fg, banner_text = "#f8d7da", "#721c24", f"合計 {total_assigned:.0f}分 ✗ {remaining:.0f}分不足"

st.markdown(
    f"""
    <div style="margin-top:10px;">
      <h2 style="font-size:30px; margin-top:0;">
        ✂️ フェーズ3：糸切り担当の提案（たたき台）
      </h2>
      <p style="font-size:22px; margin:14px 0;">
        糸切り必要時間：<b style="font-size:28px;">{need_min:.0f}分</b>（{hrs:.1f}h）
      </p>
      <table style="width:100%; font-size:20px; border-collapse:collapse; margin:16px 0;">
        <tr style="background-color:#ffe4c4;">
          <th style="padding:10px; text-align:left;">名前</th>
          <th style="padding:10px; text-align:left;">割り当て（分）</th>
          <th style="padding:10px; text-align:left;">できる工程</th>
        </tr>
        {table_rows_html}
      </table>
      <div style="font-size:24px; font-weight:bold; padding:14px; border-radius:8px;
                  background-color:{banner_bg}; color:{banner_fg};">
        {banner_text}
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.caption("※これはたたき台です。現場の感覚で調整してください。")
st.caption("※多工程できる人は、縫製などのボトルネックに温存しています。")
