import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import plotly.express as px
from datetime import datetime

# =======================================================================
#  KONFIGURASI KONEKSI Google Sheets
# =======================================================================
# Ini adalah "scope" atau izin yang kita perlukan
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]
# Nama file kunci rahasia Anda
NAMA_FILE_KUNCI = "kunci_rahasia.json"
# Nama Google Sheet Anda
NAMA_SHEET = "DataHarmoniFinansial"  # <-- GANTI INI JIKA NAMA SHEET ANDA BEDA

# Fungsi untuk mengautentikasi (menghubungkan) ke Google Sheets
@st.cache_resource
def get_client():
    creds = ServiceAccountCredentials.from_json_keyfile_name(NAMA_FILE_KUNCI, scope)
    client = gspread.authorize(creds)
    return client

# Fungsi untuk membuka lembar (worksheet)
def get_sheet(nama_worksheet):
    client = get_client()
    try:
        sheet = client.open(NAMA_SHEET).worksheet(nama_worksheet)
        return sheet
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"Sheet '{nama_worksheet}' tidak ditemukan di Google Sheet '{NAMA_SHEET}'.")
        return None
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"Google Sheet '{NAMA_SHEET}' tidak ditemukan. Periksa nama sheet Anda.")
        return None

# Fungsi untuk mengambil data dan mengubahnya jadi DataFrame (tabel)
def get_data_as_dataframe(nama_worksheet):
    sheet = get_sheet(nama_worksheet)
    if sheet:
        records = sheet.get_all_records()
        if records:
            return pd.DataFrame(records)
    return pd.DataFrame()

# =======================================================================
#  PENGATURAN HALAMAN WEB
# =======================================================================
st.set_page_config(
    page_title="Dasbor Harmoni Finansial",
    page_icon="💸",
    layout="wide",
)

st.title("💸 Dasbor Harmoni Finansial")
st.markdown("Tempat memantau aset dan arus kas kita bersama.")

# =======================================================================
#  MEMUAT DATA
# =======================================================================
# Kita gunakan st.cache_data agar tidak perlu ambil data terus-menerus
@st.cache_data(ttl=60)  # Cache data selama 60 detik
def load_data():
    df_transaksi = get_data_as_dataframe("Transaksi")
    df_aset = get_data_as_dataframe("Aset")
    
    # Membersihkan data
    if not df_transaksi.empty:
        # Ubah kolom 'Jumlah' menjadi angka
        df_transaksi["Jumlah"] = pd.to_numeric(df_transaksi["Jumlah"], errors="coerce").fillna(0)
    
    if not df_aset.empty:
        # Ubah kolom 'Nilai Sekarang' menjadi angka
        df_aset["Nilai Sekarang"] = pd.to_numeric(df_aset["Nilai Sekarang"], errors="coerce").fillna(0)
        
    return df_transaksi, df_aset

df_transaksi, df_aset = load_data()

# =======================================================================
#  BAGIAN UTAMA: TAMPILAN ANGKA (METRICS)
# =======================================================================
if not df_transaksi.empty and not df_aset.empty:
    # Hitung Pemasukan
    total_pemasukan = df_transaksi[df_transaksi["Jenis"] == "Pemasukan"]["Jumlah"].sum()
    
    # Hitung Pengeluaran
    total_pengeluaran = df_transaksi[df_transaksi["Jenis"] == "Pengeluaran"]["Jumlah"].sum()
    
    # Hitung Aset
    total_tabungan = df_aset[df_aset["Jenis Aset"] == "Tabungan"]["Nilai Sekarang"].sum()
    total_investasi_saham = df_aset[df_aset["Jenis Aset"] == "Saham"]["Nilai Sekarang"].sum()
    total_investasi_emas = df_aset[df_aset["Jenis Aset"] == "Emas"]["Nilai Sekarang"].sum()
    total_investasi = total_investasi_saham + total_investasi_emas
    total_aset = total_tabungan + total_investasi

    # Tampilkan dalam kolom-kolom
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💰 Total Aset", f"Rp {total_aset:,.0f}")
    col2.metric("🏦 Tabungan", f"Rp {total_tabungan:,.0f}")
    col3.metric("📈 Investasi (Saham & Emas)", f"Rp {total_investasi:,.0f}")
    col4.metric("⚖️ Arus Kas (Pemasukan - Pengeluaran)", f"Rp {total_pemasukan - total_pengeluaran:,.0f}")
else:
    st.warning("Data masih kosong. Silakan isi data terlebih dahulu di Google Sheet atau lewat form di bawah.")

st.markdown("---")

# =======================================================================
#  BAGIAN VISUALISASI (GRAFIK)
# =======================================================================
col_grafik1, col_grafik2 = st.columns(2)

with col_grafik1:
    st.subheader("Komposisi Aset")
    if not df_aset.empty:
        # Grafik Pie untuk Aset
        fig_aset = px.pie(
            df_aset, 
            names="Nama Aset", 
            values="Nilai Sekarang", 
            title="Sebaran Aset Saat Ini"
        )
        st.plotly_chart(fig_aset, use_container_width=True)
    else:
        st.info("Data aset kosong.")

with col_grafik2:
    st.subheader("Analisis Pengeluaran")
    if not df_transaksi.empty:
        # Filter hanya pengeluaran
        df_pengeluaran = df_transaksi[df_transaksi["Jenis"] == "Pengeluaran"].copy()
        
        if not df_pengeluaran.empty:
            # Grafik Pie untuk Kategori Pengeluaran
            fig_pengeluaran = px.pie(
                df_pengeluaran, 
                names="Kategori", 
                values="Jumlah", 
                title="Sebaran Pengeluaran per Kategori"
            )
            st.plotly_chart(fig_pengeluaran, use_container_width=True)
        else:
            st.info("Data pengeluaran kosong.")
    else:
        st.info("Data transaksi kosong.")


st.markdown("---")

# =======================================================================
#  BAGIAN INPUT DATA (FORM)
# =======================================================================
st.subheader("Input Data Baru")

# Gunakan 2 kolom untuk form
form_col1, form_col2 = st.columns(2)

# --- Form 1: Input Transaksi (Pemasukan/Pengeluaran) ---
with form_col1:
    st.info("Formulir 1: Catat Transaksi Baru")
    with st.form("form_transaksi", clear_on_submit=True):
        tanggal = st.date_input("Tanggal", value=datetime.now())
        jenis = st.selectbox("Jenis Transaksi", ["Pemasukan", "Pengeluaran"])
        
        # Pilihan kategori berdasarkan jenis
        if jenis == "Pemasukan":
            kategori = st.selectbox("Kategori", ["Gaji", "Bonus", "Hasil Investasi", "Lainnya"])
        else: # Jika Pengeluaran
            kategori = st.selectbox("Kategori", ["Konsumsi", "Transportasi", "Tagihan", "Pengeluaran Tidak Terduga", "Investasi", "Lainnya"])
            
        deskripsi = st.text_input("Deskripsi Singkat")
        jumlah = st.number_input("Jumlah (Rp)", min_value=0, step=1000)
        
        submitted_transaksi = st.form_submit_button("Simpan Transaksi")

        if submitted_transaksi:
            if jumlah > 0 and deskripsi:
                # Buka sheet 'Transaksi'
                sheet_transaksi = get_sheet("Transaksi")
                # Siapkan baris baru
                row_data = [str(tanggal), jenis, kategori, deskripsi, jumlah]
                # Tambahkan baris baru ke Google Sheet
                sheet_transaksi.append_row(row_data)
                st.success("Data transaksi berhasil disimpan!")
                st.cache_data.clear() # Hapus cache agar data langsung update
            else:
                st.error("Harap isi deskripsi dan jumlah lebih dari 0.")

# --- Form 2: Update Nilai Aset ---
with form_col2:
    st.warning("Formulir 2: Update Nilai Aset")
    if not df_aset.empty:
        with st.form("form_update_aset", clear_on_submit=True):
            # Ambil daftar nama aset dari data yang ada
            pilihan_aset = df_aset["Nama Aset"].tolist()
            aset_dipilih = st.selectbox("Pilih Aset yang akan di-update", pilihan_aset)
            
            nilai_baru = st.number_input("Masukkan Nilai Saat Ini (Rp)", min_value=0, step=1000)
            
            submitted_aset = st.form_submit_button("Update Nilai Aset")

            if submitted_aset:
                if nilai_baru > 0:
                    sheet_aset = get_sheet("Aset")
                    # Cari baris mana yang mau di-update
                    cell = sheet_aset.find(aset_dipilih)
                    if cell:
                        # Update sel di kolom C (Nilai Sekarang) di baris yang sama
                        sheet_aset.update_cell(cell.row, 3, nilai_baru) # Kolom 3 adalah 'Nilai Sekarang'
                        st.success(f"Nilai {aset_dipilih} berhasil di-update!")
                        st.cache_data.clear() # Hapus cache
                    else:
                        st.error("Aset tidak ditemukan. Terjadi kesalahan.")
                else:
                    st.error("Nilai baru harus lebih dari 0.")
    else:
        st.info("Anda perlu menambah data Aset di Google Sheet terlebih dahulu untuk bisa meng-update.")


# =======================================================================
#  BAGIAN TAMPILKAN DATA MENTAH (Opsional)
# =======================================================================
st.markdown("---")
st.subheader("Data Mentah dari Google Sheet")

if st.checkbox("Tampilkan data transaksi terakhir?"):
    if not df_transaksi.empty:
        st.dataframe(df_transaksi.tail(10)) # Tampilkan 10 data terakhir
    else:
        st.info("Tidak ada data transaksi.")

if st.checkbox("Tampilkan data aset?"):
    if not df_aset.empty:
        st.dataframe(df_aset)
    else:
        st.info("Tidak ada data aset.")