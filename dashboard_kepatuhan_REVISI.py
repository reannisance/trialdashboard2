
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from io import BytesIO

# ---------- FUNGSI UTAMA (VERSI SUPER FIX) ----------
def process_data(df_input, tahun_pajak, jenis_pajak):
    df = df_input.copy()
    df.columns = df.columns.str.strip().str.upper()

    # --------- Normalisasi kolom wajib ---------
    alias_map = {
    'NM UNIT': ['NM UNIT', 'NAMA UNIT', 'UPPPD', 'UNIT', 'UNIT PAJAK'],
    'STATUS': ['STATUS'],
    'TMT': ['TMT'],
    'KLASIFIKASI': ['KLASIFIKASI', 'KATEGORI', 'JENIS']
}
def find_column(possible_names):
    for name in possible_names:
        if name in df.columns:
            return name
    return None

    # Cari kolom wajib utama
    kolom_nm_unit = find_column(alias_map['NM UNIT'])
    kolom_status = find_column(alias_map['STATUS'])
    kolom_tmt = find_column(alias_map['TMT'])
    kolom_klasifikasi = find_column(alias_map['KLASIFIKASI'])  # Optional, tergantung jenis_pajak

    # Validasi wajib minimum
    if not all([kolom_nm_unit, kolom_status, kolom_tmt]):
    raise ValueError("❌ Kolom wajib 'NM UNIT/UPPPD', 'STATUS', atau 'TMT' tidak ditemukan.")

    # Validasi kolom KLASIFIKASI hanya untuk jenis pajak HIBURAN
    if jenis_pajak.upper() == "HIBURAN" and not kolom_klasifikasi:
    raise ValueError("❌ Kolom 'KLASIFIKASI' wajib untuk jenis pajak HIBURAN.")

    # Rename kolom supaya konsisten
    df.rename(columns={
    kolom_nm_unit: 'NM UNIT',
    kolom_status: 'STATUS',
    kolom_tmt: 'TMT',
    **({kolom_klasifikasi: 'KLASIFIKASI'} if kolom_klasifikasi else {})  # hanya kalau ada
}, inplace=True)

    # Pastikan format datetime di TMT
    df['TMT'] = pd.to_datetime(df['TMT'], errors='coerce')

    # Validasi kolom pembayaran bulanan
    payment_cols = []
    for col in df.columns:
    try:
        col_date = pd.to_datetime(col, format="%b-%y", errors="coerce")
        if pd.isna(col_date):
            col_date = pd.to_datetime(col, errors="coerce")
        if pd.notna(col_date) and col_date.year == tahun_pajak:
            if pd.to_numeric(df[col], errors='coerce').notna().sum() > 0:
                payment_cols.append(col)
    except:
        continue

if not payment_cols:
    raise ValueError("❌ Tidak ditemukan kolom pembayaran valid untuk tahun pajak yang dipilih.")

    # Hitung total pembayaran
    df['Total Pembayaran'] = df[payment_cols].apply(pd.to_numeric, errors='coerce').sum(axis=1)

    # Hitung Bulan Aktif
    bulan_aktif = []
    for idx, row in df.iterrows():
        tmt = row['TMT']
        if pd.isna(tmt):
            bulan_aktif.append(0)
        else:
            start = max(pd.Timestamp(year=tahun_pajak, month=1, day=1), tmt)
            end = pd.Timestamp(year=tahun_pajak, month=12, day=31)
            active_months = max(0, (end.year - start.year) * 12 + (end.month - start.month) + 1)
            bulan_aktif.append(active_months)
    df['Bulan Aktif'] = bulan_aktif
    df['Jumlah Pembayaran'] = df[payment_cols].apply(lambda x: pd.to_numeric(x, errors='coerce').gt(0).sum(), axis=1)

    # Kepatuhan
    def hitung_kepatuhan(row):
        payments = pd.to_numeric(row[payment_cols], errors='coerce').fillna(0)
        aktif = row['Bulan Aktif']
        bayar = payments.gt(0).astype(int).values
        gap = 0
        max_gap = 0
        for v in bayar:
            if v == 0:
                gap += 1
                max_gap = max(max_gap, gap)
            else:
                gap = 0
        return 100.0 if max_gap < 3 else round((row['Jumlah Pembayaran'] / aktif) * 100, 2) if aktif > 0 else 0.0

    df['Kepatuhan (%)'] = df.apply(hitung_kepatuhan, axis=1)
    df['Total Pembayaran'] = df['Total Pembayaran'].map(lambda x: f"{x:,.2f}")
    df['Kepatuhan (%)'] = df['Kepatuhan (%)'].map(lambda x: f"{x:.2f}")
    return df, payment_cols


# ---------- KONFIG HALAMAN ----------
st.set_page_config(page_title="📊 Dashboard Kepatuhan Pajak Daerah", layout="wide")
st.title("🎯 Dashboard Kepatuhan Pajak Daerah")
jenis_pajak = st.selectbox("📄 Pilih Jenis Pajak", ["MAKAN MINUM", "JASA KESENIAN DAN HIBURAN"])
st.markdown("Upload file Excel, pilih sheet, filter, dan lihat visualisasi ✨")

# ---------- PANDUAN ----------
with st.expander("📘 Panduan Format Excel yang dapat digunakan (Klik untuk lihat)"):
    st.markdown("""
    Berikut adalah aturan format file Excel yang dapat digunakan:

    ✅ **Kolom Wajib:**
    - `NAMA OP`, `STATUS`, `TMT`, `KLASIFIKASI` (Jika PBJT Jasa Kesenian & Hiburan)

    ✅ **Kolom Pembayaran Bulanan:**
    - Nama kolom bisa `2024-01-01`, `Jan-24`, dll — yang penting ada tahun pajaknya.
    - Nilai harus berupa angka (jangan pakai teks atau simbol).

    📁 Gunakan contoh file bernama **CONTOH_FORMAT_SETORAN MASA.xlsx**
    """)

st.markdown(
    """
    <a href="https://raw.githubusercontent.com/reannisance/trialdashboard1/main/CONTOH_FORMAT_SETORAN%20MASA.xlsx" download>
        <button style='padding: 0.5em 1em; font-size: 16px; color: red; border: 1px solid red; border-radius: 6px; background: transparent;'>
            📎 Download Contoh Format Excel
        </button>
    </a>
    """,
    unsafe_allow_html=True
)

# ---------- UPLOAD ----------
st.markdown("### 📄 Silakan upload file Excel berisi data setoran masa pajak.")
tahun_pajak = st.number_input("📅 Pilih Tahun Pajak", min_value=2000, max_value=2100, value=2024)
uploaded_file = st.file_uploader("Upload File Excel", type=["xlsx"], label_visibility="collapsed")

if uploaded_file is None:
    st.warning("⚠️ Silakan upload file terlebih dahulu.")
    st.stop()

# ---------- PILIH SHEET ----------
try:
    xls = pd.ExcelFile(uploaded_file)
    sheet_names = xls.sheet_names
    selected_sheet = st.selectbox("📑 Pilih Sheet", sheet_names)
    df_input = pd.read_excel(uploaded_file, sheet_name=selected_sheet)
except Exception as e:
    st.error(f"❌ Gagal membaca file Excel: {e}")
    st.stop()

# ---------- PROSES DATA ----------
try:
    df_input, payment_cols = process_data(df_input, tahun_pajak, jenis_pajak)
except Exception as e:
    st.error(f"❌ Gagal memproses data: {e}")
    st.stop()

st.success("✅ Data berhasil diproses dan difilter!")
st.dataframe(df_input.style.format({
    "Total Pembayaran": "{:,.2f}",
    "Kepatuhan (%)": "{:.2f}"
}), use_container_width=True)

# ---------- DOWNLOAD ----------
def to_excel(df):
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Output")
    buffer.seek(0)
    return buffer

st.download_button("📥 Download Hasil Excel", data=to_excel(df_input).getvalue(), file_name="hasil_dashboard_kepatuhan.xlsx")

# ---------- VISUALISASI ----------
st.markdown("### 📊 Tren Pembayaran Pajak per Bulan")
bulanan = df_input[payment_cols].apply(pd.to_numeric, errors='coerce').sum().reset_index()
bulanan.columns = ["Bulan", "Total Pembayaran"]
bulanan["Bulan"] = pd.to_datetime(bulanan["Bulan"], errors="coerce")
bulanan = bulanan.sort_values("Bulan")
fig_line = px.line(bulanan, x="Bulan", y="Total Pembayaran", markers=True)
st.plotly_chart(fig_line, use_container_width=True)

st.markdown("### 📋 Jumlah WP per Kategori Tingkat Kepatuhan")
df_input["Kategori"] = pd.cut(df_input["Kepatuhan (%)"].astype(float), bins=[-1, 50, 99.9, 100], labels=["Tidak Patuh", "Kurang Patuh", "Patuh"])
pie_df = df_input["Kategori"].value_counts().reset_index()
pie_df.columns = ["Kategori", "Jumlah"]
fig_bar = px.bar(pie_df, x="Kategori", y="Jumlah", color="Kategori", color_discrete_sequence=px.colors.qualitative.Pastel)
st.plotly_chart(fig_bar, use_container_width=True)

st.markdown("### 🏆 Top 20 Pembayar Tertinggi")
df_input["Total Pembayaran Numeric"] = df_input["Total Pembayaran"].replace({',': ''}, regex=True).astype(float)
top_df = df_input.sort_values("Total Pembayaran Numeric", ascending=False).head(20)
st.dataframe(top_df[["NAMA WP", "STATUS", "Total Pembayaran", "Kepatuhan (%)"]], use_container_width=True)

st.markdown("### 📌 Ringkasan Statistik")
col1, col2, col3 = st.columns(3)
col1.metric("📌 Total WP", df_input.shape[0])
col2.metric("💰 Total Pembayaran", f"Rp {top_df['Total Pembayaran Numeric'].sum():,.0f}")
col3.metric("📈 Rata-rata Pembayaran", f"Rp {top_df['Total Pembayaran Numeric'].mean():,.0f}")
