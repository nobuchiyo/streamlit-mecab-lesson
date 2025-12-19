import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
from datetime import datetime

# --- 1. Googleスプレッドシート設定 ---
# credentials.jsonは同じディレクトリに配置、またはst.secretsを利用
SCOPE = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
SHEET_NAME = "勉強効率化システム_データ" # スプレッドシート名

def get_gsheet_client():
    # ★ここを修正：ファイルからではなくSecretsから情報を取得
    creds_info = st.secrets["gcp_service_account"]
    # from_service_account_info を使うのがポイント
    creds = Credentials.from_service_account_info(creds_info, scopes=SCOPE)
    client = gspread.authorize(creds)
    return client

def load_data():
    client = get_gsheet_client()
    sheet = client.open(SHEET_NAME).sheet1
    data = sheet.get_all_records()
    return pd.DataFrame(data)

def save_data(new_row):
    client = get_gsheet_client()
    sheet = client.open(SHEET_NAME).sheet1
    sheet.append_row(new_row)

# --- 2. Streamlit UI設定 ---
st.set_page_config(page_title="授業効率化システム", layout="wide")
st.title("授業効率化システム (Bチーム)")

# サイドメニュー
menu = st.sidebar.selectbox("メニューを選択", ["データ入力 (FR-01)", "分析・比較 (FR-02, FR-03)"])

# --- 3. データ入力画面 (FR-01) ---
if menu == "データ入力 (FR-01)":
    st.header("成績データと授業スタイルの入力")
    
    with st.form("input_form"):
        col1, col2 = st.columns(2)
        with col1:
            date = st.date_input("実施日", datetime.now())
            name = st.text_input("個人の名前")
            dept = st.selectbox("学科選択", ["情報処理科", "Webデザイン科", "電気工学科"])
        
        with col2:
            score = st.number_input("点数", min_value=0, max_value=100, value=0)
            study_time = st.number_input("かかった時間 (分)", min_value=0, value=0)
            
        st.subheader("授業スタイルの項目 (チェックリスト)")
        style_items = ["教科書中心", "スライド利用", "実習あり", "グループワーク", "課題提出あり"]
        selected_styles = []
        
        # チェックボックスによる授業スタイルの具体化
        cols = st.columns(3)
        for i, item in enumerate(style_items):
            if cols[i % 3].checkbox(item):
                selected_styles.append(item)
        
        # カスタム授業スタイルの追加
        new_style = st.text_input("追加する授業スタイルの項目名を入力する場合")
        if new_style:
            selected_styles.append(new_style)

        submitted = st.form_submit_button("新規データを登録する")
        
        if submitted:
            # カンマ区切りの文字列として保存
            style_str = ",".join(selected_styles)
            new_row = [str(date), name, dept, score, study_time, style_str]
            save_data(new_row)
            st.success("スプレッドシートにデータを保存しました！")

# --- 4. 分析・比較画面 (FR-02, FR-03) ---
elif menu == "分析・比較 (FR-02, FR-03)":
    st.header("成績データと授業スタイルの比較・閲覧")
    
    try:
        df = load_data()
        
        if df.empty:
            st.warning("データがありません。入力を先に行ってください。")
        else:
            # フィルタリング
            st.subheader("絞り込み条件")
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                f_dept = st.multiselect("学科で絞り込み", df["学科"].unique(), default=df["学科"].unique())
            with col_f2:
                # 授業スタイルのタグで絞り込み
                all_styles = set()
                for s in df["授業スタイル"].str.split(","):
                    if isinstance(s, list): all_styles.update(s)
                f_style = st.multiselect("授業スタイルで絞り込み", list(all_styles))

            filtered_df = df[df["学科"].isin(f_dept)]
            if f_style:
                filtered_df = filtered_df[filtered_df["授業スタイル"].apply(lambda x: any(s in x for s in f_style))]

            # FR-02: 必要な計算（平均点など）
            st.subheader("集計結果 (FR-02)")
            avg_score = filtered_df["点数"].mean()
            avg_time = filtered_df["勉強時間"].mean()
            
            m_col1, m_col2, m_col3 = st.columns(3)
            m_col1.metric("平均点数", f"{avg_score:.1f} 点")
            m_col2.metric("平均学習時間", f"{avg_time:.1f} 分")
            m_col3.metric("データ件数", f"{len(filtered_df)} 件")

            # FR-03: 授業スタイル別の効果比較
            st.subheader("授業スタイル別の成績比較 (FR-03)")
            
            # 各授業スタイルごとの集計表を作成
            style_analysis = []
            for style in all_styles:
                style_df = df[df["授業スタイル"].str.contains(style, na=False)]
                if not style_df.empty:
                    style_analysis.append({
                        "授業スタイル": style,
                        "平均点数": style_df["点数"].mean(),
                        "平均時間": style_df["勉強時間"].mean(),
                        "効率指標(点/分)": style_df["点数"].mean() / (style_df["勉強時間"].mean() + 1)
                    })
            
            analysis_df = pd.DataFrame(style_analysis)
            
            if not analysis_df.empty:
                # グラフ表示
                fig = px.bar(analysis_df, x="授業スタイル", y="平均点数", color="平均時間",
                             title="授業スタイルごとの平均点数と時間（色の濃さが時間）",
                             labels={"平均点数":"テスト平均点", "平均時間":"学習時間(分)"})
                st.plotly_chart(fig, use_container_width=True)
                
                st.write("詳細データテーブル")
                st.dataframe(analysis_df.sort_values("平均点数", ascending=False))
            
            st.subheader("全履歴データ")
            st.table(filtered_df)

    except Exception as e:
        st.error(f"エラーが発生しました: {e}")
        st.info("credentials.jsonの配置とスプレッドシートの共有設定を確認してください。")

# --- 5. FR-04 効率的な勉強の示唆 ---
st.sidebar.markdown("---")
st.sidebar.info("FR-04: 分析結果に基づき、より短時間で高得点が取れる授業スタイルへの改善を支援します。")