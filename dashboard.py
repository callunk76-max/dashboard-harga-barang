import streamlit as st
import pandas as pd
import os

CSV_PATH = os.path.join(os.path.dirname(__file__), 'harga_barang.csv')

st.set_page_config(
    page_title='Dashboard Harga Satuan Barang',
    page_icon='📊',
    layout='wide',
)

st.title('📊 Dashboard Standar Harga Satuan Biaya Barang')
st.caption('SK Bupati Bulukumba Tahun 2025')

@st.cache_data
def load_data():
    df = pd.read_csv(CSV_PATH)
    df['harga'] = pd.to_numeric(df['harga'], errors='coerce').fillna(0).astype(int)
    df = df.sort_values(['kelompok', 'nama']).reset_index(drop=True)
    return df

df = load_data()

total_items = len(df)
total_kelompok = df['kelompok'].nunique()

col1, col2 = st.columns(2)
col1.metric('Total Item', f'{total_items:,}')
col2.metric('Kelompok Barang', total_kelompok)

st.divider()

# --- Filters ---
col_f1, col_f2, col_f3, col_f4 = st.columns(4)

with col_f1:
    nama_list = df['nama'].dropna().unique().tolist()
    selected_nama = st.selectbox(
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
    price_range = st.slider(
        'Rentang Harga (Rp)',
        min_value=0,
        max_value=int(df['harga'].max()),
        value=(0, int(df['harga'].max())),
        format='Rp %d',
    )

# --- Apply Filters ---
filtered = df.copy()

if selected_nama:
    mask = (
        filtered['nama'].str.contains(selected_nama, case=False, na=False)
        | filtered['kode'].str.contains(selected_nama, case=False, na=False)
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
            '⬇ Download CSV',
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
