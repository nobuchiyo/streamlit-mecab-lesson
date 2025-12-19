import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# --- 1. Googleスプレッドシート設定 ---
SCOPE = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
SHEET_NAME = "勉強効率化システム_データ"  # スプレッドシートのファイル名

def get_gsheet_client():
    """Secretsから認証情報を取得し、GSheetsクライアントを返す"""
    creds_info = dict(st.secrets["gcp_service_account"])
    # 秘密鍵の改行エスケープを修正
    if "private_key" in creds_info:
        creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
    
    creds = Credentials.from_service_account_info(creds_info, scopes=SCOPE)
    client = gspread.authorize(creds)
    return client

def load_data():
    """スプレッドシートから全データを読み込む"""
    client = get_gsheet_client()
    sheet = client.open(SHEET_NAME).sheet1
    data = sheet.get_all_records()
    return pd.DataFrame(data)

def save_data(new_row):
    """スプレッドシートに新しい行を追加する"""
    client = get_gsheet_client()
    sheet = client.open(SHEET_NAME).sheet1
    sheet.append_row(new_row)

# --- 定数設定 ---
DEPARTMENTS = ["情報工学科", "自動車工学科", "電気エネルギー工学科", "映像音響学科", "家具クラフト学科"]
DEFAULT_STYLES = ["教科書中心", "スライド利用", "実習あり", "グループワーク", "課題提出あり"]

# --- 2. 画面構成 (UI) ---
st.set_page_config(page_title="勉強効率化システム", layout="wide")

# タイトル表示（資料1枚目イメージ）
st.title("勉強を効率的にできるシステム")
st.caption("Bチーム制作：KIST学習最適化プロジェクト")

# タブに分ける（資料11枚目の配置イメージを整理）
tab_input, tab_analysis, tab_history = st.tabs(["📝 データ入力 (FR-01)", "📊 授業スタイル比較 (FR-03)", "📋 全データ履歴"])

# --- 3. データ入力タブ (FR-01) ---
with tab_input:
    st.header("成績と授業スタイルの登録")
    with st.form("input_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            date = st.date_input("実施日", datetime.now())
            name = st.text_input("学生氏名")
            dept = st.selectbox("学科", DEPARTMENTS)
        
        with col2:
            score = st.number_input("テスト点数 (0-100)", 0, 100, 70)
            study_time = st.number_input("勉強時間 (分)", 0, 1000, 60)
            
        st.subheader("今回の授業スタイル（複数選択可）")
        selected_styles = []
        cols = st.columns(3)
        for i, style in enumerate(DEFAULT_STYLES):
            if cols[i % 3].checkbox(style):
                selected_styles.append(style)
        
        custom_style = st.text_input("その他のスタイルがあれば入力")
        if custom_style:
            selected_styles.append(custom_style)

        submitted = st.form_submit_button("データを保存する")
        
        if submitted:
            if not name:
                st.error("氏名を入力してください。")
            else:
                style_str = ",".join(selected_styles)
                new_row = [str(date), name, dept, score, study_time, style_str]
                save_data(new_row)
                st.success(f"{name}さんのデータをスプレッドシートに保存しました！")

# --- 4. 分析・比較タブ (FR-03) ---
with tab_analysis:
    st.header("授業スタイル別の効果分析")
    
    try:
        df = load_data()
        
        if df.empty:
            st.info("データがまだありません。入力を先に完了させてください。")
        else:
            # データのクリーニングと効率計算
            df['点数'] = pd.to_numeric(df['点数'], errors='coerce')
            df['勉強時間'] = pd.to_numeric(df['勉強時間'], errors='coerce')
            # 効率指標 = 点数 ÷ 時間（1分あたりの獲得点数）
            df['学習効率'] = df['点数'] / df['勉強時間'].replace(0, 1)

            # --- スタイル比較セクション ---
            st.subheader("🔍 スタイルの絞り込み比較")
            
            # 全スタイルを抽出
            all_styles_in_data = set()
            for s in df["授業スタイル"].astype(str).str.split(","):
                if isinstance(s, list): all_styles_in_data.update([x.strip() for x in s if x.strip()])
            
            selected_styles_comp = st.multiselect(
                "比較したいスタイルを選んでください",
                options=list(all_styles_in_data),
                default=list(all_styles_in_data)[:3] if len(all_styles_in_data) >= 3 else list(all_styles_in_data)
            )

            if selected_styles_comp:
                # 選択されたスタイルごとの平均を算出
                comparison_list = []
                for style in selected_styles_comp:
                    style_mask = df["授業スタイル"].str.contains(style, na=False)
                    subset = df[style_mask]
                    if not subset.empty:
                        comparison_list.append({
                            "授業スタイル": style,
                            "平均点数": subset["点数"].mean(),
                            "平均勉強時間": subset["勉強時間"].mean(),
                            "平均学習効率": subset["学習効率"].mean()
                        })
                
                comp_df = pd.DataFrame(comparison_list)

                # メトリクスの表示
                m_cols = st.columns(len(comparison_list))
                for i, row in enumerate(comparison_list):
                    with m_cols[i]:
                        st.metric(row["授業スタイル"], f"{row['平均点数']:.1f}点", f"効率 {row['平均学習効率']:.2f}")

                # グラフ表示
                fig = go.Figure()
                fig.add_trace(go.Bar(x=comp_df["授業スタイル"], y=comp_df["平均点数"], name="平均点数", marker_color='indianred'))
                fig.add_trace(go.Bar(x=comp_df["授業スタイル"], y=comp_df["平均勉強時間"], name="平均時間(分)", marker_color='lightsalmon'))
                
                fig.update_layout(title="授業スタイル別：点数と時間の比較", barmode='group')
                st.plotly_chart(fig, use_container_width=True)

                # 効率の散布図
                fig_scatter = px.scatter(
                    df, x="勉強時間", y="点数", color="学科", 
                    hover_data=["名前", "授業スタイル"],
                    title="全体分布：勉強時間 vs テスト点数（右上にいくほど理想的）"
                )
                st.plotly_chart(fig_scatter, use_container_width=True)
            
    except Exception as e:
        st.error(f"分析エラー: {e}")

# --- 5. 履歴データタブ ---
with tab_history:
    st.header("全データ履歴")
    try:
        current_df = load_data()
        st.dataframe(current_df, use_container_width=True)
        st.download_button("CSVとしてダウンロード", current_df.to_csv(index=False), "study_data.csv", "text/csv")
    except:
        st.write("データを読み込めませんでした。")