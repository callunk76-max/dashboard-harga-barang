import streamlit as st
import pandas as pd
import os
import re
from pathlib import Path

st.set_page_config(
    page_title='Dashboard Harga Satuan Barang',
    page_icon='📊',
    layout='wide',
)

CSV_PATH = os.path.join(os.path.dirname(__file__), 'harga_barang.csv')
UPLOAD_PASSWORD = '13Kholil'

# --- Session state init ---
if 'data_source' not in st.session_state:
    st.session_state.data_source = 'default'
if 'uploaded_df' not in st.session_state:
    st.session_state.uploaded_df = None
if 'upload_auth' not in st.session_state:
    st.session_state.upload_auth = False

# --- CSS ---
st.markdown("""
<style>
td:first-child, th:first-child {
    max-width: 50px !important;
    min-width: 40px !important;
    width: 50px !important;
    text-align: center !important;
}
</style>
""", unsafe_allow_html=True)

# --- Helpers ---
@st.cache_data
def load_default_data():
    df = pd.read_csv(CSV_PATH)
    df['harga'] = pd.to_numeric(df['harga'], errors='coerce').fillna(0).astype(int)
    df = df.sort_values(['kelompok', 'nama']).reset_index(drop=True)
    return df

def parse_csv(file):
    df = pd.read_csv(file)
    expected = {'kode', 'kelompok', 'nama', 'satuan', 'harga'}
    cols = set(df.columns.str.lower().str.strip())
    if not expected.intersection(cols):
        st.error('Format CSV tidak sesuai. Minimal harus ada kolom: kode, kelompok, nama, satuan, harga')
        return None
    df.columns = df.columns.str.lower().str.strip()
    if 'harga' in df.columns:
        df['harga'] = pd.to_numeric(df['harga'], errors='coerce').fillna(0).astype(int)
    return df

def parse_excel(file):
    df = pd.read_excel(file, engine='openpyxl')
    df.columns = df.columns.str.lower().str.strip()
    expected = {'kode', 'kelompok', 'nama', 'satuan', 'harga'}
    cols = set(df.columns)
    if not expected.intersection(cols):
        st.error('Format Excel tidak sesuai. Minimal harus ada kolom: kode, kelompok, nama, satuan, harga')
        return None
    if 'harga' in df.columns:
        df['harga'] = pd.to_numeric(df['harga'], errors='coerce').fillna(0).astype(int)
    return df

def parse_pdf(file):
    try:
        import pdfplumber
        import pytesseract
        from PIL import Image
        import io
    except ImportError:
        st.error('Library OCR tidak tersedia. Install: pip install pdfplumber pytesseract Pillow')
        return None

    rows = []
    kode_re = re.compile(r'(\d{1,2}[,.]\d{1,2}[,.]\d{1,2}[,.]\d{1,2}[,.]\d{1,2}[,.]\d{4})')
    price_re = re.compile(r'(\d{1,3}(?:[.,]\d{3})+)')

    with pdfplumber.open(file) as pdf:
        progress = st.progress(0, 'Memproses PDF...')
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text:
                img = page.to_image(resolution=200)
                pil_img = img.original
                text = pytesseract.image_to_string(pil_img, lang='eng+ind', config='--psm 3')
            for line in text.split('\n'):
                line = line.strip()
                if not line or len(line) < 15:
                    continue
                km = kode_re.search(line)
                pm = price_re.search(line)
                if km and pm:
                    kode = km.group(1).replace(',', '.')
                    harga = pm.group(1).replace(',', '').replace('.', '')
                    try:
                        harga = int(harga)
                    except:
                        continue
                    rest = line[km.end():pm.start()].strip()
                    kelompok = ''
                    nama = rest
                    if '|' in rest:
                        parts = [p.strip().strip('_| ') for p in rest.split('|') if p.strip()]
                        kelompok = parts[0] if parts else ''
                        nama = ' '.join(parts[1:]) if len(parts) > 1 else (parts[0] if parts else rest)
                    rows.append({
                        'kode': kode,
                        'kelompok': kelompok,
                        'nama': nama,
                        'satuan': '',
                        'harga': harga,
                    })
            progress.progress((i + 1) / len(pdf.pages), f'Memproses PDF... {i+1}/{len(pdf.pages)}')

    if not rows:
        st.error('Tidak ada data yang bisa diekstrak dari PDF')
        return None
    df = pd.DataFrame(rows)
    df = df.sort_values(['kelompok', 'nama']).reset_index(drop=True)
    return df

# --- Sidebar: Upload ---
with st.sidebar:
    st.header('📤 Upload Data')
    with st.expander('Upload file harga satuan', expanded=False):
        pw = st.text_input('Password', type='password', placeholder='Masukkan password')
        if pw == UPLOAD_PASSWORD:
            st.session_state.upload_auth = True
            st.success('✅ Akses diberikan')

            uploaded_file = st.file_uploader(
                'Pilih file (CSV, Excel, PDF)',
                type=['csv', 'xlsx', 'xls', 'pdf'],
            )

            if uploaded_file and st.button('Proses Upload'):
                ext = Path(uploaded_file.name).suffix.lower()
                with st.spinner(f'Memproses {uploaded_file.name}...'):
                    if ext == '.csv':
                        new_df = parse_csv(uploaded_file)
                    elif ext in ('.xlsx', '.xls'):
                        new_df = parse_excel(uploaded_file)
                    elif ext == '.pdf':
                        new_df = parse_pdf(uploaded_file)
                    else:
                        new_df = None
                        st.error('Format file tidak didukung')

                if new_df is not None and len(new_df) > 0:
                    st.session_state.uploaded_df = new_df
                    st.session_state.data_source = 'upload'
                    st.success(f'✅ {len(new_df)} item berhasil diupload!')
                    st.rerun()

            if st.session_state.uploaded_df is not None:
                if st.button('🔄 Kembali ke data default'):
                    st.session_state.uploaded_df = None
                    st.session_state.data_source = 'default'
                    st.rerun()
        elif pw:
            st.error('❌ Password salah')

    st.divider()
    st.caption('**callunk76-max/dashboard-harga-barang**')

# --- Main ---
st.title('📊 Dashboard Standar Harga Satuan Biaya Barang')
st.caption('SK Bupati Bulukumba Tahun 2025')

# Load data
if st.session_state.data_source == 'upload' and st.session_state.uploaded_df is not None:
    df = st.session_state.uploaded_df.copy()
    st.info(f'📁 Menggunakan data upload: {len(df)} item')
else:
    df = load_default_data()
    st.session_state.data_source = 'default'

total_items = len(df)
total_kelompok = df['kelompok'].nunique()

col1, col2 = st.columns(2)
col1.metric('Total Item', f'{total_items:,}')
col2.metric('Kelompok Barang', total_kelompok)

st.divider()

# --- Filters ---
col_f1, col_f2, col_f3, col_f4 = st.columns([3, 2, 1.5, 2.5])

with col_f1:
    nama_list = df['nama'].dropna().unique().tolist()
    search = st.selectbox(
        '🔍 Cari barang',
        [''] + sorted(nama_list),
        placeholder='Ketik nama barang...',
    )

with col_f2:
    kelompok_list = ['Semua'] + sorted(df['kelompok'].unique().tolist())
    selected_kelompok = st.selectbox('Kelompok Barang', kelompok_list)

with col_f3:
    satuan_values = df['satuan'].dropna().unique().tolist()
    satuan_list = ['Semua'] + sorted(s for s in satuan_values if str(s).strip())
    selected_satuan = st.selectbox('Satuan', satuan_list)

with col_f4:
    max_price = int(df['harga'].max())
    price_range = st.slider(
        'Rentang Harga (Rp)',
        min_value=0,
        max_value=max_price,
        value=(0, max_price),
        format='Rp %d',
    )

# --- Apply Filters ---
filtered = df.copy()

if search:
    mask = (
        filtered['nama'].str.contains(search, case=False, na=False)
        | filtered['kode'].str.contains(search, case=False, na=False)
    )
    filtered = filtered[mask]

if selected_kelompok != 'Semua':
    filtered = filtered[filtered['kelompok'] == selected_kelompok]

if selected_satuan != 'Semua':
    filtered = filtered[filtered['satuan'] == selected_satuan]

filtered = filtered[
    (filtered['harga'] >= price_range[0]) & (filtered['harga'] <= price_range[1])
]

# --- Table with row number ---
st.subheader(f'📋 Hasil: {len(filtered)} item ditemukan')

if not filtered.empty:
    display_df = filtered[['kode', 'kelompok', 'nama', 'satuan', 'harga']].copy()
    display_df.insert(0, 'No', range(1, len(display_df) + 1))
    display_df['harga'] = display_df['harga'].apply(lambda x: f'Rp {x:,}')

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            'No': st.column_config.NumberColumn('No', width='small'),
            'kode': 'Kode',
            'kelompok': 'Kelompok',
            'nama': 'Nama Barang',
            'satuan': 'Satuan',
            'harga': 'Harga',
        },
        height=500,
    )

    # --- Export ---
    col_ex1, col_ex2, _ = st.columns([1, 1, 3])
    with col_ex1:
        csv = filtered.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            '⬇ Download Filtered CSV',
            csv,
            'harga_barang_filtered.csv',
            'text/csv',
        )
    with col_ex2:
        all_csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            '⬇ Download All CSV',
            all_csv,
            'harga_barang_all.csv',
            'text/csv',
        )
else:
    st.info('Tidak ada item yang cocok dengan filter.')

st.divider()
st.caption(
    'Sumber: SK Standar Harga Satuan Biaya Barang 2025 (Final).pdf | '
    f'Total {total_items:,} item dari {total_kelompok} kelompok | '
    'Dibuat dengan Streamlit'
)
