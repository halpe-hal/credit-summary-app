import pandas as pd
import streamlit as st
import csv
from io import StringIO
from datetime import datetime

st.title("📊 クレジットカード明細 自動整形 & 月別集計アプリ")
st.markdown("SAISON / 三井住友 / AMEX / LIFE カードのCSV明細を一括アップロード！")

uploaded_files = st.file_uploader("カード明細CSVファイルを複数選択OKでアップロード", type=["csv"], accept_multiple_files=True)

def parse_file(file):
    content = file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("shift_jis", errors="ignore")

    reader = csv.reader(StringIO(text))
    rows = list(reader)

    parsed_data = []
    card_type = None  # 未判定状態から開始

    # AMEXの検出（最も優先）
    if len(rows) > 1 and 'ご利用日' in rows[0][0] and any('ご利用内容' in col for col in rows[0]):
        card_type = "AMEX"

    # 三井住友のカード番号（完全一致）で検出
    if not card_type and any(cell.strip() == "4980-21**-****-****" for row in rows[:5] for cell in row):
        card_type = "三井住友"

    # LIFEカードの検出（完全一致）
    if not card_type and any(cell.strip() == "ＦＡＳＩＯビジネスカード" for row in rows[:5] for cell in row):
        card_type = "LIFE"

    # SAISONカードの検出（完全一致）
    if not card_type and any(cell.strip() == "セゾンプラチナビジネス・アメリカンエキスプレスカード" for row in rows[:5] for cell in row):
        card_type = "SAISON"

    if not card_type:
        card_type = "不明"  # 最終的に何にも該当しなければ

    # AMEX専用処理（正確な列インデックスで判定）
    if len(rows) > 1 and 'ご利用日' in rows[0][0] and any('ご利用内容' in col for col in rows[0]):
        for row in rows[1:]:
            if len(row) >= 6 and row[0].startswith("2025/") and row[5].replace(',', '').isdigit():
                try:
                    date = pd.to_datetime(row[0])
                    shop = row[2].strip()
                    amount = float(row[5].replace(",", ""))
                    parsed_data.append([date, shop, amount, "AMEX"])
                except:
                    pass
    else:
        for row in rows:
            # 三井住友 (カード番号一致で判別された場合)
            if card_type == "三井住友" and len(row) >= 2 and any(m in row[0] for m in ["2025/"]) and row[1].replace(',', '').replace('.', '').isdigit():
                try:
                    parts = row[0].split(" ", 1)
                    if len(parts) == 2:
                        date = pd.to_datetime(parts[0])
                        shop = parts[1]
                        amount = float(row[1].replace(",", ""))
                        parsed_data.append([date, shop, amount, card_type])
                except:
                    pass

            # SAISON (date + shop + amount)
            elif len(row) >= 6 and row[0].startswith("2025") and row[5].replace(',', '').isdigit():
                try:
                    parsed_data.append([pd.to_datetime(row[0]), row[1], float(row[5].replace(",", "")), card_type])
                except:
                    pass

            # LIFEカード
            elif len(row) >= 6 and row[3].startswith("2025/") and row[5].replace(',', '').isdigit():
                try:
                    date = pd.to_datetime(row[3])
                    shop = row[4].strip()
                    amount = float(row[5].replace(",", ""))
                    parsed_data.append([date, shop, amount, "LIFE"])
                except:
                    pass

    return parsed_data

if uploaded_files:
    all_data = []
    for file in uploaded_files:
        all_data.extend(parse_file(file))

    if not all_data:
        st.error("有効な明細データが見つかりませんでした")
    else:
        df = pd.DataFrame(all_data, columns=["利用日", "ご利用店名", "利用金額", "カード会社"])
        df["年月"] = df["利用日"].dt.to_period("M").astype(str)

        months_sorted = sorted(df["年月"].unique(), reverse=True)
        selected_month = st.selectbox("📅 集計する月を選択", months_sorted)
        df_month = df[df["年月"] == selected_month]

        st.subheader(f"📆 選択中の月: {selected_month}")

        for company in df_month["カード会社"].unique():
            df_company = df_month[df_month["カード会社"] == company]
            grouped = df_company.groupby("ご利用店名")["利用金額"].sum().reset_index()
            grouped.columns = ["ご利用店名", "合計金額"]

            st.markdown(f"### 💳 {company} の集計結果")
            st.dataframe(grouped)

            csv_output = grouped.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                label=f"📥 {company}の{selected_month}集計CSVをダウンロード",
                data=csv_output,
                file_name=f"{company}_summary_{selected_month}.csv",
                mime="text/csv"
            )
