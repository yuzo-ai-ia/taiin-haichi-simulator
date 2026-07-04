# calc_core.py
# テント部品製造ツール 共通計算モジュール
# app.py から import して使う。このファイル単体では実行しない。

import pandas as pd

# ── 定数 ──────────────────────────────────────────────────────────────────────
PROCESSES  = ["縫製", "溶着", "糸切り"]   # 工程の順番は表示にも影響するため固定
COL_SUFFIX = "_分"                         # 部品マスタの列名サフィックス


def calc_process_times(master, order):
    """部品マスタと生産指示から工程別の必要時間を計算する。

    返り値:
        merged      : 計算結果が入ったDataFrame（注文別の表示に使う）
        totals      : 工程別合計分数の辞書  {"縫製": ..., "溶着": ..., "糸切り": ...}
        missing_ids : 部品マスタに存在しない部品IDのset（警告表示用）
    """
    master_ids  = set(master["部品ID"])
    order_ids   = set(order["部品ID"])
    missing_ids = order_ids - master_ids

    # マスタにない行を除外してから結合（calc_time.py と同じロジック）
    order_valid = order[order["部品ID"].isin(master_ids)].copy()
    merged = order_valid.merge(master, on="部品ID", how="left")

    # 工程ごとに「個数 × 標準分数」を計算して合計する（3ファイル共通ロジック）
    totals = {}
    for proc in PROCESSES:
        col_result = proc + "_計(分)"
        merged[col_result] = merged["個数"] * merged[proc + COL_SUFFIX]
        totals[proc] = merged[col_result].sum()

    return merged, totals, missing_ids


def count_processes(row):
    """その行の人が担当できる工程数を返す。
    assign_cut の優先ソート（工程数が少ない人を先に糸切りへ割り当て）で使う。"""
    count = 0
    for proc in PROCESSES:
        if pd.notna(row[proc]) and str(row[proc]).strip() != "":
            count += 1
    return count
