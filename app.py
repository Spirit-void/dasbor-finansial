import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import plotly.express as px
from datetime import datetime
import logging

# =======================================================================
# KONFIGURASI KONEKSI GOOGLE SHEETS
# =======================================================================
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]
NAMA_SHEET = "DataHarmoniFinansial"

# ✅ Setup logging
logging.basicConfig(
    filename="app.log",
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def show_error_page(msg="Terjadi kesalahan tak terduga"):
    st.error(msg)
    st.info("Silakan refresh halaman atau hubungi admin jika masalah berlanjut.")
    st.stop()

# =======================================================================
# KONEKSI DAN PEMUATAN DATA
# =======================================================================
@st.cache_resource
def get_client():
    try:
        creds_dict = st.secrets.get("gcp_service_account", None)
        if not creds_dict:
            st.error("❌ Gagal membaca secrets. Pastikan kredensial sudah diatur di Streamlit Cloud.")
            st.stop()
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client
    except Exception:
        logging.exception("Error saat inisialisasi koneksi Google Sheets:")
        show_error_page("❌ Gagal membuat koneksi ke Google Sheets.")

def get_sheet(nama_worksheet):
    try:
        client = get_client()
        return client.open(NAMA_SHEET).worksheet(nama_worksheet)
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"Sheet '{nama_worksheet}' tidak ditemukan.")
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"Spreadsheet '{NAMA_SHEET}' tidak ditemukan.")
    except Exception:
        logging.exception(f"Error saat membuka worksheet {nama_worksheet}:")
        st.error("Terjadi kesalahan saat mengakses worksheet.")
    return None

def get_data_as_dataframe(nama_worksheet, limit_rows=500):
    """Ambil maksimal `limit_rows` baris terakhir agar cepat."""
    try:
        sheet = get_sheet(nama_worksheet)
        if sheet:
            records = sheet.get_all_values()
            if records:
                headers = records.pop(0)
                # Ambil baris terakhir agar loading cepat
                records = records[-limit_rows:]
                return pd.DataFrame(records, columns=headers)
        return pd.DataFrame()
    except Exception:
        logging.exception(f"Error saat mengambil data dari {nama_worksheet}:")
        st.warning(f"Gagal memuat data dari '{nama_worksheet}'.")
        return pd.DataFrame()

# =======================================================================
# KONFIGURASI HALAMAN
# =======================================================================
st.set_page_config(page_title="Dasbor Harmoni Finansial", page_icon="💸", layout="wide")
st.title("💸 Dasbor Harmoni Finansial")
st.markdown("Pantau aset dan arus kas Anda dengan mudah dan cepat.")

# =======================================================================
# MEMUAT DATA
# =======================================================================
@st.cache_data(ttl=300, show_spinner="Memuat data dari Google Sheet...")
def load_data():
    df_transaksi = get_data_as_dataframe("Transaksi")
    df_aset = get_data_as_dataframe("Aset")

    # Optimasi konversi numerik
    for kolom, df in [("Jumlah", df_transaksi), ("Nilai Sekarang", df_aset)]:
        if not df.empty and kolom in df.columns:
            df[kolom] = pd.to_numeric(df[kolom], errors="coerce").fillna(0)

    return df_transaksi, df_aset

df_transaksi, df_aset = load_data()

if df_transaksi.empty and df_aset.empty:
    show_error_page("Data Google Sheet kosong atau tidak bisa diakses.")

# =======================================================================
# FUNGSI PAGINASI UNTUK DATAFRAME BESAR
# =======================================================================
def show_dataframe_paginated(df, page_size=20):
    total_rows = len(df)
    if total_rows == 0:
        st.info("Tidak ada data untuk ditampilkan.")
        return
    total_pages = (total_rows - 1) // page_size + 1
    page = st.number_input("Halaman", 1, total_pages, 1, key=f"page_{df.shape}")
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    st.dataframe(df.iloc[start_idx:end_idx])
    st.caption(f"Menampilkan baris {start_idx + 1}–{min(end_idx, total_rows)} dari {total_rows}")

# =======================================================================
# METRICS (CACHE PERHITUNGAN)
# =======================================================================
@st.cache_data(ttl=300)
def hitung_metrik(df_transaksi, df_aset):
    total_pemasukan = df_transaksi[df_transaksi["Jenis"] == "Pemasukan"]["Jumlah"].sum()
    total_pengeluaran = df_transaksi[df_transaksi["Jenis"] == "Pengeluaran"]["Jumlah"].sum()
    total_tabungan = df_aset[df_aset["Jenis Aset"] == "Tabungan"]["Nilai Sekarang"].sum()
    total_investasi = df_aset[df_aset["Jenis Aset"].isin(["Saham", "Emas"])]["Nilai Sekarang"].sum()
    total_aset = total_tabungan + total_investasi
    return total_pemasukan, total_pengeluaran, total_aset, total_tabungan, total_investasi

if not df_transaksi.empty and not df_aset.empty:
    try:
        total_pemasukan, total_pengeluaran, total_aset, total_tabungan, total_investasi = hitung_metrik(df_transaksi, df_aset)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("💰 Total Aset", f"Rp {total_aset:,.0f}")
        col2.metric("🏦 Tabungan", f"Rp {total_tabungan:,.0f}")
        col3.metric("📈 Investasi", f"Rp {total_investasi:,.0f}")
        col4.metric("⚖️ Arus Kas", f"Rp {total_pemasukan - total_pengeluaran:,.0f}")
    except Exception:
        logging.exception("Error menghitung metrics:")
        st.error("Terjadi kesalahan saat menghitung data keuangan.")
else:
    st.warning("Data masih kosong. Silakan isi data di Google Sheet.")

st.markdown("---")

# =======================================================================
# VISUALISASI
# =======================================================================
col1, col2 = st.columns(2)

with col1:
    st.subheader("📊 Komposisi Aset")
    if not df_aset.empty:
        try:
            df_plot = df_aset.tail(100)
            fig_aset = px.pie(df_plot, names="Nama Aset", values="Nilai Sekarang", title="Sebaran Aset (100 data terakhir)")
            st.plotly_chart(fig_aset, use_container_width=True)
        except Exception:
            logging.exception("Error visualisasi aset:")
            st.warning("Gagal memuat grafik aset.")
    else:
        st.info("Data aset kosong.")

with col2:
    st.subheader("💸 Analisis Pengeluaran")
    if not df_transaksi.empty:
        try:
            df_pengeluaran = df_transaksi[df_transaksi["Jenis"] == "Pengeluaran"].copy().tail(100)
            if not df_pengeluaran.empty:
                fig_pengeluaran = px.pie(df_pengeluaran, names="Kategori", values="Jumlah", title="Pengeluaran per Kategori (100 data terakhir)")
                st.plotly_chart(fig_pengeluaran, use_container_width=True)
            else:
                st.info("Data pengeluaran kosong.")
        except Exception:
            logging.exception("Error visualisasi pengeluaran:")
            st.warning("Gagal memuat grafik pengeluaran.")
    else:
        st.info("Data transaksi kosong.")

st.markdown("---")

# =======================================================================
# FORM INPUT
# =======================================================================
st.subheader("Input Data Baru")
form_col1, form_col2 = st.columns(2)

with form_col1:
    st.info("Formulir 1: Catat Transaksi Baru")
    with st.form("form_transaksi", clear_on_submit=True):
        tanggal = st.date_input("Tanggal", value=datetime.now())
        jenis = st.selectbox("Jenis Transaksi", ["Pemasukan", "Pengeluaran"])
        kategori = st.selectbox(
            "Kategori",
            ["Gaji", "Bonus", "Hasil Investasi", "Lainnya"] if jenis == "Pemasukan" else
            ["Konsumsi", "Transportasi", "Tagihan", "Pengeluaran Tidak Terduga", "Investasi", "Lainnya"]
        )
        deskripsi = st.text_input("Deskripsi Singkat")
        jumlah = st.number_input("Jumlah (Rp)", min_value=0, step=1000)
        submitted = st.form_submit_button("Simpan Transaksi")

        if submitted:
            try:
                if jumlah > 0 and deskripsi:
                    sheet = get_sheet("Transaksi")
                    if sheet:
                        sheet.append_row([str(tanggal), jenis, kategori, deskripsi, jumlah])
                        st.success("✅ Transaksi berhasil disimpan!")
                        st.cache_data.clear()
                    else:
                        st.error("Worksheet 'Transaksi' tidak ditemukan.")
                else:
                    st.error("Harap isi deskripsi dan jumlah lebih dari 0.")
            except Exception:
                logging.exception("Error menyimpan transaksi:")
                st.error("Gagal menyimpan transaksi ke Google Sheets.")

with form_col2:
    st.warning("Formulir 2: Update Nilai Aset")
    if not df_aset.empty:
        with st.form("form_update_aset", clear_on_submit=True):
            aset_list = df_aset["Nama Aset"].tolist()
            aset_dipilih = st.selectbox("Pilih Aset", aset_list)
            nilai_baru = st.number_input("Nilai Saat Ini (Rp)", min_value=0, step=1000)
            submitted_aset = st.form_submit_button("Update Nilai Aset")

            if submitted_aset:
                try:
                    if nilai_baru > 0:
                        sheet = get_sheet("Aset")
                        if sheet:
                            cell = sheet.find(aset_dipilih)
                            if cell:
                                sheet.update_cell(cell.row, 3, nilai_baru)
                                st.success(f"✅ Nilai {aset_dipilih} berhasil diperbarui!")
                                st.cache_data.clear()
                            else:
                                st.error("Aset tidak ditemukan di Google Sheet.")
                        else:
                            st.error("Worksheet 'Aset' tidak ditemukan.")
                    else:
                        st.error("Nilai baru harus lebih dari 0.")
                except Exception:
                    logging.exception("Error update nilai aset:")
                    st.error("Gagal memperbarui nilai aset.")
    else:
        st.info("Tambahkan data aset di Google Sheet terlebih dahulu.")

# =======================================================================
# DATA MENTAH
# =======================================================================
st.markdown("---")
st.subheader("📜 Data Mentah dari Google Sheet")

if st.checkbox("Tampilkan data transaksi?"):
    show_dataframe_paginated(df_transaksi)

if st.checkbox("Tampilkan data aset?"):
    show_dataframe_paginated(df_aset)
