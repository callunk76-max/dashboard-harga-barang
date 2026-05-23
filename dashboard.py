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
UPLOAD_PASSWORD = os.environ.get('UPLOAD_PASSWORD', '')

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
    .stTextInput > div > div > input {
        font-size: 0.95rem;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.8rem !important;
    }
</style>
""", unsafe_allow_html=True)

# --- Helpers ---
@st.cache_data(ttl=300)  # auto refresh setiap 5 menit
def load_default_data(_csv_mtime):
    df = pd.read_csv(CSV_PATH)
    df['harga'] = pd.to_numeric(df['harga'], errors='coerce').fillna(0).astype(int)
    df = df.sort_values(['kelompok', 'nama']).reset_index(drop=True)
    return df

def get_default_data():
    """Load data with cache buster based on file timestamp."""
    mtime = os.path.getmtime(CSV_PATH) if os.path.exists(CSV_PATH) else 0
    return load_default_data(mtime)

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
    """Parse PDF harga satuan (scanned/image PDF with OCR)."""
    try:
        import pdfplumber
        import pytesseract
        from PIL import Image
    except ImportError:
        st.error('Library OCR tidak tersedia. Install: pip install pdfplumber pytesseract Pillow')
        return None

    # Regex: kode 6-group, price at END of line only!
    kode_re = re.compile(r'(\d{1,2}[,.]\d{1,2}[,.]\d{1,2}[,.]\d{1,2}[,.]\d{1,2}[,.]\d{4})')
    price_end_re = re.compile(r'(\d{1,3}(?:[.,]\d{3})+(?:,\d+)?)\s*$')

    # Known kelompok names from the SK for auto-detection
    KELOMPOK_KNOWN = [
        'Bahan Bangunan dan Konstruksi', 'Bahan Baku / Obat-obatan', 'Bahan Kimia',
        'Bahan Bakar dan Pelumas', 'Alat Listrik', 'Alat Pendingin', 'Alat Studio',
        'Alat Laboratorium', 'Alat Kedokteran', 'Alat Komunikasi', 'Alat Keamanan',
        'Alat Olahraga', 'Alat Pemadam Kebakaran', 'Alat Penangkap Ikan',
        'Alat Besar Darat', 'Pompa', 'Perabot Kantor', 'Komputer',
        'Peralatan Komputer', 'Bahan/Bibit Hewan', 'Lainnya',
    ]

    SATUAN_KEYWORDS = {
        'buah': 'Buah', 'unit': 'Unit', 'batang': 'Batang', 'lembar': 'Lembar',
        'botol': 'Botol', 'bungkus': 'Bungkus', 'dus': 'Dus', 'dos': 'Dos',
        'kg': 'Kg', 'tube': 'Tube', 'box': 'Box', 'pcs': 'Pcs', 'ampul': 'Ampul',
        'meter': 'Meter', 'pack': 'Pack', 'set': 'Set', 'gram': 'Gram',
        'liter': 'Liter', 'lusin': 'Lusin', 'ekor': 'Ekor', 'zak': 'Zak',
        'drum': 'Drum', 'ton': 'Ton', 'pasang': 'Pasang', 'kapsul': 'Kapsul',
        'tablet': 'Tablet', 'strip': 'Strip', 'karton': 'Karton',
        'sak': 'Sak', 'karung': 'Karung', 'rol': 'Rol', 'pasang': 'Pasang',
        'pair': 'Pair', 'inch': 'Inch', 'kodi': 'Kodi', 'rim': 'Rim',
        'butir': 'Butir', 'biji': 'Biji', 'kantong': 'Kantong',
    }

    def clean_ocr_rest(rest_text):
        """Clean the text between kode and price."""
        t = rest_text.strip()
        # Remove leading/trailing punctuation and separators
        t = re.sub(r'^[\s_|>\-\[\]()"\'#@*]+|[\s_|>\-\[\]()"\'#@*]+$', '', t)
        # Collapse multiple spaces
        t = re.sub(r'\s+', ' ', t)
        return t

    def extract_kelompok_nama(text):
        """Extract kelompok and nama from the middle text."""
        text = clean_ocr_rest(text)
        
        # Method 1: Has explicit | separator
        if '|' in text:
            parts = [p.strip().strip('_| ') for p in text.split('|') if p.strip()]
            if parts:
                kelompok = parts[0] if len(parts) >= 1 else ''
                nama = ' '.join(parts[1:]) if len(parts) > 1 else (parts[0] if parts else text)
                return kelompok, nama
        
        # Method 2: Try to detect kelompok from known list at start of text
        for k in sorted(KELOMPOK_KNOWN, key=len, reverse=True):
            if text.lower().startswith(k.lower()):
                rest = text[len(k):].strip()
                rest = re.sub(r'^[\s_|>\-]+|[\s_|>\-]+$', '', rest)
                if rest and len(rest) > 3:
                    return k, rest
        
        # Method 3: No kelompok detected, put everything in nama
        return '', text

    def detect_satuan(nama_text):
        """Try to infer satuan from nama text."""
        if not nama_text:
            return ''
        words = nama_text.lower().split()
        if not words:
            return ''
        # Check last word
        last = words[-1].strip('.,;:()[]')
        if last in SATUAN_KEYWORDS:
            return SATUAN_KEYWORDS[last]
        # Check second-to-last for patterns like "50 Kg"
        if len(words) >= 2:
            second_last = words[-2].strip('.,;:()[]')
            if second_last in SATUAN_KEYWORDS:
                return SATUAN_KEYWORDS[second_last]
        return ''

    def clean_item_name(nama):
        """Clean up OCR artifacts in item names."""
        if not nama:
            return nama
        n = nama.strip()
        # Remove consecutive duplicate words (Aspal Aspal -> Aspal)
        words = n.split()
        cleaned = []
        i = 0
        while i < len(words):
            w = words[i]
            # Single word duplicate: "Aspal Aspal"
            if i + 1 < len(words) and words[i+1].lower() == w.lower() and len(w) > 2:
                cleaned.append(w)
                i += 2
            else:
                cleaned.append(w)
                i += 1
        n = ' '.join(cleaned)
        # Fix trailing "Ke" leftover
        n = re.sub(r'\s+Ke$', '', n).strip()
        return n

    # ---- Main parsing ----
    rows = []
    with pdfplumber.open(file) as pdf:
        total_pages = len(pdf.pages)
        progress = st.progress(0, f'Memproses {total_pages} halaman...')
        
        for i, page in enumerate(pdf.pages):
            # 1) Try text extraction
            text = page.extract_text()
            if not text or len(text.strip()) < 50:
                # 2) Fallback: OCR
                img = page.to_image(resolution=200)
                text = pytesseract.image_to_string(
                    img.original,
                    lang='eng+ind',
                    config='--psm 3 --oem 3'
                )

            for line in text.split('\n'):
                line = line.strip()
                if not line or len(line) < 15:
                    continue
                
                km = kode_re.search(line)
                pm = price_end_re.search(line)
                
                if not (km and pm):
                    continue
                
                # Ensure price is AFTER kode (not overlapping)
                if pm.start() <= km.end():
                    continue
                
                kode = km.group(1).replace(',', '.')
                
                # Parse price: remove dots, keep decimals
                price_str = pm.group(1).replace('.', '').replace(',', '.')
                try:
                    # Check if it has decimal
                    if '.' in price_str:
                        harga = int(float(price_str))
                    else:
                        harga = int(price_str)
                except (ValueError, OverflowError):
                    continue
                
                # Extract middle text (kelompok + nama)
                rest = line[km.end():pm.start()].strip()
                if not rest or len(rest) < 3:
                    continue
                
                kelompok, nama = extract_kelompok_nama(rest)
                nama = clean_item_name(nama)
                satuan = detect_satuan(nama)
                
                if not nama or len(nama) < 3:
                    continue
                
                rows.append({
                    'kode': kode,
                    'kelompok': kelompok,
                    'nama': nama,
                    'satuan': satuan,
                    'harga': harga,
                })
            
            pct = (i + 1) / total_pages
            progress.progress(pct, f'Halaman {i+1}/{total_pages} ({len(rows)} item ditemukan)')

    if not rows:
        st.error('Tidak ada data yang bisa diekstrak dari PDF. Periksa format PDF atau kualitas scan.')
        return None
    
    df = pd.DataFrame(rows)
    df = df.sort_values(['kelompok', 'nama']).reset_index(drop=True)
    
    return df

# --- Sidebar ---
with st.sidebar:
    st.header('📤 Upload Data')
    with st.expander('Upload file harga satuan', expanded=False):
        pw = st.text_input('Password', type='password', placeholder='Masukkan password')
        if pw == UPLOAD_PASSWORD:
            st.session_state.upload_auth = True
            st.success('✅ Akses diberikan')
        elif pw:
            st.error('❌ Password salah')

        if st.session_state.upload_auth:
            uploaded_file = st.file_uploader(
                'Pilih file (CSV, Excel, PDF)',
                type=['csv', 'xlsx', 'xls', 'pdf'],
                key='file_uploader'
            )

            if uploaded_file and st.button('Proses Upload', key='btn_upload'):
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
                if st.button('🔄 Kembali ke data default', key='btn_reset'):
                    st.session_state.uploaded_df = None
                    st.session_state.data_source = 'default'
                    st.rerun()

    # --- Quick Stats in Sidebar ---
    if st.session_state.data_source == 'upload' and st.session_state.uploaded_df is not None:
        current_df = st.session_state.uploaded_df.copy()
    else:
        current_df = get_default_data()
    
    st.divider()
    st.subheader('📊 Ringkasan')
    st.caption(f'**Total Item:** {len(current_df):,}')
    st.caption(f'**Kelompok:** {current_df["kelompok"].nunique()}')
    st.caption(f'**Rata-rata Harga:** Rp {int(current_df["harga"].mean()):,}')
    st.caption(f'**Harga Tertinggi:** Rp {int(current_df["harga"].max()):,}')
    st.caption(f'**Harga Terendah:** Rp {int(current_df["harga"].min()):,}')
    
    # Manual refresh button (clears cache)
    col_r1, col_r2 = st.columns([1, 2])
    with col_r1:
        if st.button('🔄 Refresh', help='Muatin ulang data dari CSV'):
            st.cache_data.clear()
            st.rerun()
    with col_r2:
        st.caption(f'{len(current_df):,} item')

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
    df = get_default_data()
    st.session_state.data_source = 'default'

total_items = len(df)
total_kelompok = df['kelompok'].nunique()

col1, col2 = st.columns(2)
col1.metric('Total Item', f'{total_items:,}')
col2.metric('Kelompok Barang', total_kelompok)

st.divider()

# --- Filters ---
fcol1, fcol2, fcol3, fcol4 = st.columns([3, 1.5, 1.5, 2.5])

with fcol1:
    # Multi-select with max 1 item = autocomplete + built-in X to remove
    nama_options = sorted(df['nama'].dropna().unique().tolist())
    selected = st.multiselect(
        '🔍 Cari barang (nama atau kode)',
        nama_options,
        placeholder='Ketik nama barang...',
        max_selections=1,
        key='search_input',
    )
    search = selected[0] if selected else ''

with fcol2:
    kelompok_list = ['Semua'] + sorted(df['kelompok'].unique().tolist())
    selected_kelompok = st.selectbox('Kelompok Barang', kelompok_list, key='filter_kelompok')

with fcol3:
    satuan_values = df['satuan'].dropna().unique().tolist()
    satuan_list = ['Semua'] + sorted(s for s in satuan_values if str(s).strip())
    selected_satuan = st.selectbox('Satuan', satuan_list, key='filter_satuan')

with fcol4:
    max_price = int(df['harga'].max())
    if max_price > 0:
        price_range = st.slider(
            'Rentang Harga (Rp)',
            min_value=0,
            max_value=max_price,
            value=(0, max_price),
            format='Rp %d',
            key='price_slider',
        )
        # Show active range indicator
        if price_range[0] > 0 or price_range[1] < max_price:
            st.caption(f'✅ Filter aktif: Rp {price_range[0]:,} - Rp {price_range[1]:,}')
        else:
            st.caption(f'Rp 0 - Rp {max_price:,}')
    else:
        price_range = (0, 1)
        st.caption('Data harga belum tersedia')

# --- Apply Filters ---
filtered = df.copy()

if search:
    # Filter by partial name or kode match
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

# --- Summary cards ---
st.subheader(f'📋 Hasil: {len(filtered)} item ditemukan')

if not filtered.empty:
    col_s1, col_s2, col_s3, col_s4 = st.columns(4)
    col_s1.metric('Total Item', f'{len(filtered):,}')
    col_s2.metric('Kelompok', filtered['kelompok'].nunique())
    col_s3.metric('Rata-rata', f'Rp {int(filtered["harga"].mean()):,}')
    col_s4.metric('Range', f'Rp {int(filtered["harga"].min()):,} - Rp {int(filtered["harga"].max()):,}')

    st.divider()

    # --- Table with row number ---
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
    col_ex1, col_ex2, _ = st.columns([1.5, 1.5, 4])
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
