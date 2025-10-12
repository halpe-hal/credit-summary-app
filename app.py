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

    # --- AMEXの検出と処理（利用者ごと） ---
    if len(rows) > 1 and 'ご利用日' in rows[0][0] and any('ご利用内容' in col for col in rows[0]):
        header = rows[0]
        member_index = header.index("カード会員様名") if "カード会員様名" in header else None

        for row in rows[1:]:
            if len(row) >= 6 and row[0].startswith("2025/") and row[5].replace(',', '').isdigit():
                try:
                    date = pd.to_datetime(row[0])
                    shop = row[2].strip()
                    amount = float(row[5].replace(",", ""))

                    # カード会員様名から日本語名へマッピング
                    if member_index is not None and member_index < len(row):
                        member_name_en = row[member_index].strip().upper()
                        name_map = {"REI": "レイ", "SHINPEI": "シンペイ", "MIU": "ミウ"}
                        member_jp = name_map.get(member_name_en, member_name_en)
                        card_label = f"AMEX（{member_jp}）"
                    else:
                        card_label = "AMEX（不明）"

                    parsed_data.append([date, shop, amount, card_label])
                except:
                    pass
        return parsed_data  # AMEX処理が終わったらここで終了

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
        
    else:
        for row in rows:
            # 三井住友 (カード番号一致で判別された場合)
            if card_type == "三井住友" and len(row) >= 3:
                import re
                date_str = str(row[0]).strip()
                amt_str  = str(row[2]).strip()

                # 行頭が YYYY/M/D 形式のときだけ処理（名前行や集計行を除外）
                if re.match(r'^\d{4}/\d{1,2}/\d{1,2}$', date_str) and amt_str:
                    try:
                        date = pd.to_datetime(date_str)
                        shop = str(row[1]).strip()
                        # 金額はカンマや通貨記号が混ざっていてもOKにする
                        amount = float(re.sub(r'[^\d\.\-]', '', amt_str))
                        parsed_data.append([date, shop, amount, card_type])
                    except:
                        pass

            # --- SAISON明細：ご利用者名（セル内）→ブロック方式 ---
            elif card_type == "SAISON":
                import re

                current_user = "不明"
                in_block = False

                def has_token(row, token):
                    return any(token in (str(c) if c is not None else "") for c in row)

                for row in rows:
                    # 1) 「ご利用者名：...」セルを行内のどこでも検出して抽出
                    user_switched = False
                    for cell in row:
                        s = str(cell) if cell is not None else ""
                        m = re.search(r"ご利用者名\s*[:：]\s*(.+)", s)
                        if m:
                            name = m.group(1).strip()
                            # 末尾の「様」や余分な空白を除去
                            name = re.sub(r"様$", "", name).strip()
                            current_user = name if name else "不明"
                            in_block = True              # ここから明細ブロック開始
                            user_switched = True
                            break
                    if user_switched:
                        continue  # 見出し行自体はスキップ

                    # 2) 小計/合計行は集計対象外。合計でブロックを閉じる
                    if has_token(row, "【小計】"):
                        continue
                    if has_token(row, "【合計】"):
                        in_block = False
                        current_user = "不明"           # 次のご利用者名が出るまで不明に戻す
                        continue

                    # 3) 明細行（ブロック内のみ処理）：日付+金額の行を採用
                    if in_block and len(row) >= 6:
                        date_str = str(row[0]) if row[0] is not None else ""
                        amt_str  = str(row[5]) if row[5] is not None else ""
                        amt_str  = amt_str.replace(",", "")

                        if re.match(r"\d{4}/\d{1,2}/\d{1,2}", date_str) and amt_str.isdigit():
                            try:
                                date = pd.to_datetime(date_str)
                                shop = str(row[1]).strip() if len(row) > 1 else ""
                                amount = float(amt_str)
                                label = f"SAISON（{current_user}）"
                                parsed_data.append([date, shop, amount, label])
                            except Exception:
                                pass

                return parsed_data

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
