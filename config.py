import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
from streamlit_option_menu import option_menu
import time
from streamlit_folium import st_folium
import plotly.express as px
import seaborn as sns
import matplotlib.pyplot as plt
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode, JsCode
import streamlit.components.v1 as components
import os
import plotly.graph_objects as go
from constants import WAREHOUSE_MAP
from config_topology import get_warehouse_figure

import pandas as pd
import streamlit as st
import time
from database import supabase
import pytz
from datetime import datetime

def get_moldova_time():
    tz = pytz.timezone('Europe/Chisinau')
    return datetime.now(tz)

def sync_to_inventory(doc_id, items_list, warehouse_id="Основной склад"):
    """
    items_list — это список словарей из твоего JSON (Название товара, Кол-во и т.д.)
    """
    inventory_records = []
    for item in items_list:
        # Приводим ключи к формату твоей таблицы inventory
        record = {
            "doc_id": str(doc_id),
            "item_name": str(item.get('Название товара') or item.get('Товар')),
            "quantity": float(item.get('Кол-во') or item.get('Количество') or 0),
            "warehouse_id": warehouse_id,
            "status": "НА СКЛАДЕ",
            "cell_address": "НЕ НАЗНАЧЕНО" # Изначально адреса нет
        }
        inventory_records.append(record)
    
    if inventory_records:
        # Сохраняем в inventory. Если товар с таким doc_id и item_name есть — обновит, если нет — создаст.
        supabase.table("inventory").upsert(inventory_records, on_conflict="doc_id,item_name").execute()

# При создании/обновлении:
now = get_moldova_time()
current_date = now.strftime("%Y-%m-%d")
current_time = now.strftime("%H:%M:%S")


def get_cell_occupancy():
    # Забираем данные из нашего VIEW
    response = supabase.table("warehouse_utilization").select("*").execute()
    # Превращаем в словарь { 'WH1-R1-S1-A': 'Заполнена', ... }
    return {row['cell_address']: row['occupancy_status'] for row in response.data}

# Внутри функции отрисовки карты:
occupancy_map = get_cell_occupancy()
# Теперь ты можешь передать это в get_warehouse_figure, 
# чтобы она красила ячейки на основе occupancy_map


def render_warehouse_logic(entry_id, items_df):
    """Универсальная логика управления ячейками склада для любого типа документа"""
    if items_df.empty:
        st.warning("Сначала добавьте товары в таблицу!")
        return

    col_sel, col_viz = st.columns([1, 2])
    
    with col_sel:
        target_item = st.selectbox("📦 Товар:", items_df['Название товара'].unique(), key=f"t_{entry_id}")
        wh_id = str(st.selectbox("🏪 Склад:", list(WAREHOUSE_MAP.keys()), key=f"wh_{entry_id}"))
        
        # --- ГЕНЕРАТОР ЯЧЕЕК (Оптимизированный) ---
        conf = WAREHOUSE_MAP[wh_id]
        all_cells = []
        for r in conf['rows']:
            all_cells.append(f"WH{wh_id}-{r}")
            for s in range(1, conf.get('sections', 1) + 1):
                for t in conf.get('tiers', ['A']):
                    all_cells.append(f"WH{wh_id}-{r}-S{s}-{t}")
        
        all_cells = sorted(list(set(all_cells)))
        
        # Получаем текущий адрес товара
        curr_addr = items_df.loc[items_df['Название товара'] == target_item, 'Адрес'].values[0] if 'Адрес' in items_df.columns else "НЕ УКАЗАНО"
        
        if curr_addr not in all_cells and curr_addr != "НЕ УКАЗАНО":
            all_cells.insert(0, curr_addr)

        def_idx = all_cells.index(curr_addr) if curr_addr in all_cells else 0

        selected_cell = st.selectbox(
            "📍 Выберите ячейку:", 
            options=all_cells, 
            index=def_idx,
            key=f"cs_{entry_id}"
        )
        
        # --- КНОПКА ПРИВЯЗКИ ---
        if st.button("🔗 ПРИВЯЗАТЬ К ЯЧЕЙКЕ", use_container_width=True, type="primary"):
            # 1. Создаем переменную ВНУТРИ блока кнопки
            inv_data = {
                "doc_id": entry_id,
                "item_name": target_item,
                "warehouse_id": wh_id,
                "cell_address": selected_cell,
                "quantity": float(items_df.loc[items_df['Название товара'] == target_item, 'Кол-во'].values[0] or 0)
            }
            
            # 2. Используем её ТУТ ЖЕ (с тем же отступом!)
            try:
                supabase.table("inventory").upsert(
                    inv_data, 
                    on_conflict="doc_id, item_name"
                ).execute()
                
                # Обновляем адрес в локальной таблице, чтобы изменения сразу отразились в редакторе
                mask = st.session_state[f"temp_items_{entry_id}"]['Название товара'] == target_item
                st.session_state[f"temp_items_{entry_id}"].loc[mask, 'Адрес'] = selected_cell
                
                st.toast(f"✅ {target_item} привязан к {selected_cell}")
                time.sleep(0.5)
                st.rerun()
            except Exception as e:
                st.error(f"Ошибка при сохранении: {e}")
        
import pytz
from datetime import datetime
import time
import pandas as pd
import numpy as np
import streamlit as st
from streamlit_folium import st_folium
import folium

# --- ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ВРЕМЕНИ ---
def get_moldova_time():
    tz = pytz.timezone('Europe/Chisinau')
    return datetime.now(tz)

import streamlit as st
import pandas as pd
import numpy as np
import time
import folium
from streamlit_folium import st_folium
import datetime

@st.dialog("⚙️ Редактирование данных", width="large")
def edit_order_modal(entry_id, table_key="orders"):
    from database import supabase  # Гарантируем импорт клиента Supabase
    import datetime

    # Вспомогательная функция для времени
    def get_moldova_time():
        return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=2)))

    # 1. ИНИЦИАЛИЗАЦИЯ ДАННЫХ (Загрузка из БД при открытии)
    if f"temp_row_{entry_id}" not in st.session_state:
        with st.spinner("📥 Загрузка актуальных данных из облака..."):
            try:
                response = supabase.table(table_key).select("*").eq("id", entry_id).execute()
                if not response.data:
                    st.error(f"Запись {entry_id} не найдена.")
                    return
                
                db_row = response.data[0]
                
                # Проверка photo_url: если там не ссылка, ставим None
                raw_photo = db_row.get('photo_url', '')
                valid_photo = raw_photo if isinstance(raw_photo, str) and raw_photo.startswith('http') else None

                st.session_state[f"temp_row_{entry_id}"] = {
                    'id': db_row.get('id'),
                    'Клиент': db_row.get('client_name', ''),
                    'Телефон': db_row.get('phone', ''),
                    'Адрес клиента': db_row.get('delivery_address', ''), 
                    'Координаты': db_row.get('coordinates', ''),
                    'Статус': db_row.get('status', 'ОЖИДАНИЕ'),
                    'Водитель': db_row.get('driver', ''),               
                    'ТС': db_row.get('vehicle', ''),                  
                    'Адрес загрузки': db_row.get('load_address', 'Центральный склад'),
                    'Сумма заявки': float(db_row.get('total_sum', 0.0) or 0.0),
                    'Общий объем (м3)': float(db_row.get('total_volume', 0.0) or 0.0),
                    'Допуск': db_row.get('approval_by', ''),            # КТО ОДОБРИЛ (approval_by)
                    'Сертификат': db_row.get('has_certificate', 'Нет'), # СЕРТИФИКАЦИЯ (has_certificate)
                    'Описание': db_row.get('description', ''),
                    'photo_url': valid_photo
                }

                # Загрузка состава товаров
                items_raw = db_row.get('items_data', [])
                items_df = pd.DataFrame(items_raw) if items_raw else pd.DataFrame(columns=['Название товара', 'Кол-во', 'Адрес'])
                if 'Адрес' not in items_df.columns: 
                    items_df['Адрес'] = "НЕ УКАЗАНО"
                st.session_state[f"temp_items_{entry_id}"] = items_df

                # Поиск индекса в локальном DataFrame для мгновенного обновления UI
                if table_key in st.session_state and st.session_state[table_key] is not None:
                    df_local = st.session_state[table_key]
                    idx_list = df_local.index[df_local['id'] == entry_id].tolist()
                    st.session_state[f"temp_idx_{entry_id}"] = idx_list[0] if idx_list else None

            except Exception as e:
                st.error(f"Ошибка инициализации данных: {e}")
                return

    # Работа с данными из state
    row = st.session_state[f"temp_row_{entry_id}"]
    items_df = st.session_state[f"temp_items_{entry_id}"]
    idx = st.session_state.get(f"temp_idx_{entry_id}")

    st.markdown(f"### 🖋️ Редактор документа `{entry_id}`")
    
    # ВКЛАДКИ
    tab_main, tab_map = st.tabs(["📝 Основные данные и Товары", "📍 Геолокация и Карта"])

    # --- ВКЛАДКА 1: ОСНОВНЫЕ ДАННЫЕ ---
    with tab_main:
        c1, c2, c3 = st.columns(3)
        row['Клиент'] = c1.text_input("Клиент", value=row['Клиент'], key=f"e_cli_{entry_id}")
        row['Телефон'] = c2.text_input("Телефон", value=row['Телефон'], key=f"e_ph_{entry_id}")
        row['Адрес клиента'] = c3.text_input("Адрес доставки", value=row['Адрес клиента'], key=f"e_adr_c_{entry_id}")

        st.markdown("---")
        r2_1, r2_2, r2_3, r2_4 = st.columns(4)
        
        # СТАТУС
        status_list = ["ОЖИДАНИЕ", "Стоит на точке загрузки", "Выехал", "Ожидает догруз", "В пути", "Доставлено", "БРАК"]
        st_idx = status_list.index(row['Статус']) if row['Статус'] in status_list else 0
        row['Статус'] = r2_1.selectbox("📍 Статус", status_list, index=st_idx, key=f"e_st_{entry_id}")

        # ВОДИТЕЛЬ
        row['Водитель'] = r2_2.text_input("👤 Водитель (ФИО)", value=row['Водитель'], key=f"e_dr_i_{entry_id}")

        # ТС
        row['ТС'] = r2_3.text_input("🚛 ТС (Госномер)", value=row['ТС'], key=f"e_ts_{entry_id}")
        
        # АДРЕС ЗАГРУЗКИ
        row['Адрес загрузки'] = r2_4.text_input("🏗️ Адрес загрузки", value=row['Адрес загрузки'], key=f"e_adr_z_{entry_id}")

        # --- НОВАЯ СТРОКА: ДОПУСК И СЕРТИФИКАТ ---
        st.markdown("---")
        r3_1, r3_2, r3_3 = st.columns([2, 1, 1])
        
        # КТО ОДОБРИЛ
        row['Допуск'] = r3_1.text_input("👤 Допуск (Кто одобрил отправку)", value=row['Допуск'], key=f"e_dop_{entry_id}")
        
        # СЕРТИФИКАЦИЯ
        cert_list = ["Нет", "Да"]
        cert_idx = cert_list.index(row['Сертификат']) if row['Сертификат'] in cert_list else 0
        row['Сертификат'] = r3_2.selectbox("📜 Сертификат", cert_list, index=cert_idx, key=f"e_cert_{entry_id}")
        
        # Описание (Опционально в эту же строку)
        row['Описание'] = r3_3.text_input("📝 Короткая заметка", value=row['Описание'], key=f"e_desc_{entry_id}")

        # РАБОТА С ФОТО
        st.markdown("---")
        f_c1, f_c2 = st.columns([1, 2])
        with f_c1:
            if row.get('photo_url') and str(row['photo_url']).startswith('http'):
                st.image(row['photo_url'], caption="Текущее фото", width=200)
            else:
                st.info("📷 Фото отсутствует или некорректная ссылка")
        with f_c2:
            new_photo = st.file_uploader("Загрузить новое фото", type=['jpg', 'jpeg', 'png'], key=f"e_photo_{entry_id}")

        st.markdown("### 📦 Состав товаров (Редактирование таблицы)")
        updated_items = st.data_editor(items_df, width="stretch", num_rows="dynamic", key=f"ed_it_{entry_id}")
        st.session_state[f"temp_items_{entry_id}"] = updated_items

    import math
    import requests

# --- ВКЛАДКА 2: КАРТА (Геолокация) ---
    with tab_map:
        st.subheader("📍 Быстрая настройка адреса")
    
    # Твоя база
        BASE_LAT, BASE_LON = 47.776654, 27.913643

    # Функция мгновенного расчета (Гаверсинус) - работает без интернета и за 0.001 сек
        def fast_dist(lat1, lon1, lat2, lon2):
            R = 6371.0
            phi1, phi2 = math.radians(lat1), math.radians(lat2)
            dphi = math.radians(lat2 - lat1)
            dlambda = math.radians(lon2 - lon1)
            a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
            return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        col_m1, col_m2 = st.columns([2, 1])
    
        with col_m2:
        # Поле ввода (сразу показывает текущие координаты)
            manual_coords = st.text_input("Lat, Lon", value=row['Координаты'], key=f"inp_{entry_id}")
        
            if manual_coords and ',' in manual_coords:
                try:
                    p = manual_coords.split(',')
                    t_lat, t_lon = float(p[0]), float(p[1])
                
                # МГНОВЕННЫЙ КМ (Прямой)
                    direct_km = fast_dist(BASE_LAT, BASE_LON, t_lat, t_lon)
                # Коэффициент дорожности (обычно +20-30% к прямой линии для примерного понимания)
                    est_road_km = direct_km * 1.25 
                
                    st.metric("Примерное расстояние", f"~{est_road_km:.2f} км", help="Расчет с учетом дорожного коэффициента 1.25")
                    st.caption(f"📏 По прямой: {direct_km:.2f} км")
                except: pass
        
            st.warning("Кликни на карту и нажми кнопку 'Применить' под ней.")

        with col_m1:
        # Настройка фокуса карты
            curr_lat, curr_lon = BASE_LAT, BASE_LON
            if row['Координаты'] and ',' in row['Координаты']:
                try:
                    parts = row['Координаты'].split(',')
                    curr_lat, curr_lon = float(parts[0]), float(parts[1])
                except: pass

            m = folium.Map(location=[curr_lat, curr_lon], zoom_start=13, control_scale=True)
            folium.LatLngPopup().add_to(m)
        
        # Маркер Базы
            folium.Marker([BASE_LAT, BASE_LON], icon=folium.Icon(color='blue', icon='home')).add_to(m)
        
        # Маркер текущей цели
            if row['Координаты'] and ',' in row['Координаты']:
                folium.Marker([curr_lat, curr_lon], icon=folium.Icon(color='red')).add_to(m)
            # Рисуем прямую линию для скорости (не ждем маршрут)
                folium.PolyLine([[BASE_LAT, BASE_LON], [curr_lat, curr_lon]], color="red", weight=2, dash_array='5').add_to(m)

        # Вывод Folium (быстрый режим)
            map_data = st_folium(m, height=400, width=500, key=f"fast_map_{entry_id}")

        # ОБРАБОТКА КЛИКА (Супер-быстро)
            if map_data.get("last_clicked"):
                click_lat = map_data['last_clicked']['lat']
                click_lng = map_data['last_clicked']['lng']
            
            # Считаем км для кнопки мгновенно
                quick_km = fast_dist(BASE_LAT, BASE_LON, click_lat, click_lng) * 1.25
            
                if st.button(f"✅ ПРИМЕНИТЬ: {quick_km:.2f} км", key=f"save_loc_{entry_id}", use_container_width=True, type="primary"):
                    row['Координаты'] = f"{click_lat:.6f}, {click_lng:.6f}"
                    st.rerun()

    st.divider()
    
    # --- КНОПКИ УПРАВЛЕНИЯ ---
    save_col, cancel_col = st.columns(2)
    
    with save_col:
        if st.button("💾 СОХРАНИТЬ ИЗМЕНЕНИЯ", use_container_width=True, type="primary", key=f"btn_save_{entry_id}"):
            with st.spinner("⏳ Сохранение в базу данных..."):
                try:
                    # 1. Загрузка фото в Storage (если есть новое)
                    final_photo_url = row['photo_url']
                    if new_photo:
                        file_ext = new_photo.name.split('.')[-1]
                        file_name = f"{entry_id}_{int(time.time())}.{file_ext}"
                        supabase.storage.from_("order-photos").upload(file_name, new_photo.getvalue())
                        final_photo_url = supabase.storage.from_("order-photos").get_public_url(file_name)

                    # 2. Формируем Payload для БД
                    now_md = get_moldova_time()
                    db_payload = {
                        "client_name": row['Клиент'],
                        "phone": row['Телефон'],
                        "delivery_address": row['Адрес клиента'],
                        "coordinates": row['Координаты'],
                        "status": row['Статус'],
                        "driver": row['Водитель'],
                        "vehicle": row['ТС'],
                        "load_address": row['Адрес загрузки'],
                        "approval_by": row['Допуск'],           # СОХРАНЕНИЕ: Кто одобрил
                        "has_certificate": row['Сертификат'],   # СОХРАНЕНИЕ: Сертификация
                        "description": row['Описание'],         # СОХРАНЕНИЕ: Заметка
                        "items_data": updated_items.replace({np.nan: None}).to_dict(orient='records'),
                        "photo_url": final_photo_url,
                        "updated_at": now_md.isoformat()
                    }

                    # 3. Апдейт в Supabase
                    supabase.table(table_key).update(db_payload).eq("id", entry_id).execute()

                    # 4. Локальное обновление DataFrame (UI)
                    if idx is not None and table_key in st.session_state:
                        st.session_state[table_key].at[idx, 'Клиент'] = row['Клиент']
                        st.session_state[table_key].at[idx, 'Статус'] = row['Статус']
                        st.session_state[table_key].at[idx, 'Водитель'] = row['Водитель']
                        st.session_state[table_key].at[idx, 'ТС'] = row['ТС']
                        if 'Допуск' in st.session_state[table_key].columns:
                            st.session_state[table_key].at[idx, 'Допуск'] = row['Допуск']
                        if 'Сертификат' in st.session_state[table_key].columns:
                            st.session_state[table_key].at[idx, 'Сертификат'] = row['Сертификат']
                        if 'Адрес клиента' in st.session_state[table_key].columns:
                             st.session_state[table_key].at[idx, 'Адрес клиента'] = row['Адрес клиента']

                    st.success("✅ Данные успешно обновлены!")
                    time.sleep(1)
                    st.session_state.pop(f"temp_row_{entry_id}", None)
                    st.rerun()

                except Exception as e:
                    st.error(f"🚨 Ошибка при сохранении: {e}")

    with cancel_col:
        if st.button("❌ ОТМЕНИТЬ", use_container_width=True, key=f"btn_cancel_{entry_id}"):
            st.session_state.pop(f"temp_row_{entry_id}", None)
            st.rerun()
            
import streamlit as st
import pandas as pd
import pytz
from datetime import datetime

# --- ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ ВРЕМЕНИ ---
def format_to_moldova_time(iso_string):
    if not iso_string or iso_string == '---':
        return '---'
    try:
        # Парсим UTC время из базы
        dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        # Переводим в часовой пояс Кишинева
        tz = pytz.timezone('Europe/Chisinau')
        return dt.astimezone(tz).strftime('%d.%m.%Y %H:%M')
    except:
        return iso_string

@st.dialog("🔍 Детальный просмотр заявки", width="large")
def show_order_details_modal(order_id):
    from database import supabase
    
    # --- 1. ЗАГРУЗКА ДАННЫХ ---
    with st.spinner("🚀 Синхронизация с облаком..."):
        try:
            # Логика определения таблицы по префиксу ID
            table_name = "orders" if str(order_id).startswith("ORD") else "arrivals"
            
            response = supabase.table(table_name).select("*").eq("id", order_id).execute()
            
            if not response.data:
                st.error(f"❌ Документ {order_id} не найден в базе данных.")
                return
                
            db_row = response.data[0]
            
            # Парсинг товаров (JSONB -> DataFrame)
            items_list = db_row.get('items_data', [])
            if isinstance(items_list, list) and len(items_list) > 0:
                items_df = pd.DataFrame(items_list)
            else:
                items_df = pd.DataFrame(columns=['Название товара', 'Кол-во', 'Адрес'])
                
        except Exception as e:
            st.error(f"🚨 Ошибка подключения: {e}")
            return

    # --- 2. ШАПКА И СТАТУС ---
    st.markdown(f"## 📄 Документ: {order_id}")
    
    # Цветовая индикация статуса
    status = db_row.get('status', 'НЕ ОПРЕДЕЛЕН')
    st.info(f"**Текущий статус:** {status}")

    # --- 3. ОСНОВНОЙ БЛОК ИНФОРМАЦИИ ---
    col_info, col_photo = st.columns([2, 1])

    with col_info:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("##### 👤 Контрагент")
            st.markdown(f"**Клиент:** {db_row.get('client_name', '---')}")
            st.markdown(f"**Телефон:** {db_row.get('phone', '---')}")
            st.markdown(f"**Адрес доставки:** {db_row.get('delivery_address', '---')}")
            
            # Ссылка на карту, если есть координаты
            coords = db_row.get('coordinates', '')
            if coords and ',' in coords:
                google_maps_url = f"https://www.google.com/maps?q={coords.replace(' ', '')}"
                st.markdown(f"📍 **[Открыть точку на карте]({google_maps_url})**")

        with c2:
            st.markdown("##### 🚚 Логистика")
            st.markdown(f"**Водитель:** {db_row.get('driver', '---')}")
            st.markdown(f"**Транспорт:** {db_row.get('vehicle', '---')}")
            st.markdown(f"**Место загрузки:** {db_row.get('load_address', '---')}")
            st.markdown(f"**Сертификат:** {db_row.get('has_certificate', 'Нет')}")

    with col_photo:
        st.markdown("##### 📸 Фото-фиксация")
        photo_url = db_row.get('photo_url')
        if photo_url:
            st.image(photo_url, use_container_width=True, caption="Скан накладной / Фото груза")
        else:
            st.warning("Фотография не прикреплена")

    st.divider()

    # --- 4. ТОВАРНАЯ СПЕЦИФИКАЦИЯ ---
    st.markdown("### 📋 Товарный состав")
    
    if not items_df.empty:
        # Форматирование таблицы
        def style_cells(row):
            addr = row.get('Адрес', '')
            color = 'background-color: #d4edda' if addr and addr != "НЕ УКАЗАНО" else 'background-color: #fff3cd'
            return [color] * len(row)

        st.dataframe(
            items_df.style.apply(style_cells, axis=1),
            use_container_width=True,
            hide_index=True
        )
        
        # Итоговые показатели
        m1, m2, m3 = st.columns(3)
        m1.metric("Позиций", len(items_df))
        m2.metric("Общий объем", f"{db_row.get('total_volume', 0)} м³")
        m3.metric("Сумма заявки", f"{db_row.get('total_sum', 0)} MDL")
    else:
        st.warning("⚠️ Список товаров пуст.")

    # --- 5. ДОПОЛНИТЕЛЬНО И ИСТОРИЯ ---
    st.divider()
    
    exp_c1, exp_c2 = st.columns(2)
    with exp_c1:
        st.markdown(f"**📝 Сведения / Допуск:**\n\n> {db_row.get('description', 'Нет описания')}")
        st.caption(f"Разрешил: {db_row.get('approval_by', '---')}")

    with exp_c2:
        with st.expander("🕒 Журнал изменений (Moldova Time)"):
            created = format_to_moldova_time(db_row.get('created_at'))
            updated = format_to_moldova_time(db_row.get('updated_at'))
            st.write(f"**Создан:** {created}")
            st.write(f"**Обновлен:** {updated}")
            st.write(f"**Автор правок:** {db_row.get('updated_by', 'Система')}")

   # --- 6. КНОПКИ УПРАВЛЕНИЯ ---
    st.markdown("<br>", unsafe_allow_html=True)
    col_close, col_extra = st.columns(2) # Распаковываем список на две колонки

# Теперь вызываем кнопку ВНУТРИ колонки
    if col_close.button("❌ ЗАКРЫТЬ", use_container_width=True):
        st.rerun()
        

@st.dialog("🖨️ Печать документа", width="large")
def show_print_modal(order_id):
    from database import supabase
    
    # --- 1. ЗАГРУЗКА АКТУАЛЬНЫХ ДАННЫХ ИЗ БД (ОБЯЗАТЕЛЬНО) ---
    try:
        table_name = "orders" if order_id.startswith("ORD") else "arrivals"
        response = supabase.table(table_name).select("*").eq("id", order_id).execute()
        
        if not response.data:
            st.error("Ошибка: Данные в базе не найдены")
            return
            
        row = response.data[0]
        # Извлекаем товары из JSONB поля
        raw_items = pd.DataFrame(row.get('items_data', []))
    except Exception as e:
        st.error(f"Ошибка связи с БД: {e}")
        return

    # --- 2. ПОДГОТОВКА ТАБЛИЦЫ ТОВАРОВ ---
    if not raw_items.empty:
        # Очистка от служебных колонок
        display_cols = [c for c in raw_items.columns if "Unnamed" not in str(c)]
        print_df = raw_items[display_cols].dropna(how='all').fillna("-")
    else:
        print_df = pd.DataFrame(columns=["Товар", "Кол-во", "Адрес"])

    items_html = print_df.to_html(index=False, border=1, classes='items-table')

    # --- 3. ГЕНЕРАЦИЯ HTML (Используем ключи из БД) ---
    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        @media print {{
            @page {{ size: A4; margin: 10mm; }}
            .no-print {{ display: none !important; }}
            body {{ background: white; }}
            .print-container {{ width: 100%; zoom: 85%; }}
        }}
        body {{ font-family: "Segoe UI", Arial, sans-serif; background: #f0f0f0; padding: 20px; }}
        .print-container {{ 
            background: white; padding: 30px; max-width: 900px; margin: 0 auto; 
            box-shadow: 0 0 15px rgba(0,0,0,0.2); border-radius: 8px;
        }}
        .header {{ border-bottom: 3px solid #333; margin-bottom: 20px; padding-bottom: 10px; }}
        .info-table {{ width: 100%; border-collapse: collapse; margin-bottom: 25px; }}
        .info-table td {{ padding: 8px; border: 1px solid #ddd; font-size: 13px; }}
        .info-table b {{ color: #555; text-transform: uppercase; font-size: 10px; }}
        
        .items-table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        .items-table th {{ background: #444; color: white; border: 1px solid #000; padding: 8px; font-size: 12px; }}
        .items-table td {{ border: 1px solid #333; padding: 8px; font-size: 12px; }}
        
        .footer {{ margin-top: 40px; border-top: 1px dashed #ccc; padding-top: 20px; }}
        .signature-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 60px; margin-top: 30px; }}
        .btn-print {{ 
            background: #27ae60; color: white; padding: 15px 30px; border: none; 
            border-radius: 6px; cursor: pointer; font-weight: bold; margin-bottom: 20px; width: 100%;
        }}
    </style>
    </head>
    <body>
        <button class="btn-print no-print" onclick="window.print()">🖨️ ОТПРАВИТЬ НА ПЕЧАТЬ / СОХРАНИТЬ В PDF</button>

        <div class="print-container">
            <div class="header">
                <table style="width:100%">
                    <tr>
                        <td><h1 style="margin:0; color:#2c3e50;">НАКЛАДНАЯ №{order_id}</h1></td>
                        <td style="text-align:right;"><h3 style="margin:0; color:#7f8c8d;">IMPERIA WMS</h3></td>
                    </tr>
                </table>
            </div>

            <table class="info-table">
                <tr>
                    <td><b>👤 Получатель</b><br>{row.get('client_name', '---')}</td>
                    <td><b>📍 Куда (Адрес)</b><br>{row.get('delivery_address', '---')}</td>
                    <td><b>📞 Телефон</b><br>{row.get('phone', '---')}</td>
                </tr>
                <tr>
                    <td><b>🚛 Перевозчик</b><br>{row.get('driver', '---')} ({row.get('vehicle', '---')})</td>
                    <td><b>🏗️ Место отгрузки</b><br>{row.get('load_address', '---')}</td>
                    <td><b>📦 Статус заявки</b><br>{row.get('status', '---')}</td>
                </tr>
                <tr>
                    <td><b>📏 Общий объем</b><br>{row.get('total_volume', '0')} м³</td>
                    <td><b>📜 Сертификация</b><br>{row.get('has_certificate', '---')}</td>
                    <td><b>📅 Дата док-та</b><br>{row.get('created_at', '---')}</td>
                </tr>
            </table>

            <div style="padding:10px; border:1px solid #eee; background:#f9f9f9; font-size:12px;">
                <b>📑 Комментарий / Допуск:</b> {row.get('description', '---')}
            </div>

            <h3 style="border-left: 5px solid #2c3e50; padding-left: 10px; margin-top:30px;">СПЕЦИФИКАЦИЯ ТМЦ</h3>
            {items_html}

            <div class="footer">
                <div class="signature-grid">
                    <div>
                        <p style="margin-bottom:40px;">Отгрузил (Склад):</p>
                        <div style="border-bottom: 1px solid #000; width: 200px;"></div>
                        <p style="font-size:10px;">(ФИО, Подпись) / {row.get('approval_by', '_______')}</p>
                    </div>
                    <div style="text-align: right;">
                        <p style="margin-bottom:40px;">Принял (Водитель/Клиент):</p>
                        <div style="border-bottom: 1px solid #000; width: 200px; margin-left: auto;"></div>
                        <p style="font-size:10px;">(ФИО, Подпись) / {row.get('client_name', '_______')}</p>
                    </div>
                </div>
                <p style="text-align: center; margin-top: 50px; font-size: 9px; color: #aaa;">
                    Система управления складом IMPERIA | Дата печати: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}
                </p>
            </div>
        </div>
    </body>
    </html>
    """

    components.html(full_html, height=850, scrolling=True)
    
    if st.button("❌ ЗАКРЫТЬ ОКНО ПЕЧАТИ", use_container_width=True):
        st.session_state.active_print_modal = None
        st.rerun()
        
        
@st.dialog("⚙️ Приемка: Редактирование прихода", width="large")
def edit_arrival_modal(entry_id):
    from database import supabase
    import numpy as np
    import pandas as pd
    from datetime import datetime
    import time
    
    table_key = "arrivals"
    
    # --- 1. УМНАЯ ИНИЦИАЛИЗАЦИЯ (ПРЯМАЯ ЗАГРУЗКА ИЗ БД) ---
    if f"temp_row_{entry_id}" not in st.session_state:
        with st.spinner("🔄 Синхронизация состава прихода с БД..."):
            try:
                # Запрашиваем свежие данные из базы, чтобы достать поле items_data
                response = supabase.table(table_key).select("*").eq("id", entry_id).execute()
                
                if not response.data:
                    st.error(f"Документ {entry_id} не найден в базе.")
                    return
                
                db_row = response.data[0]
                
                # Мапим данные из БД на русские ключи твоего интерфейса
                st.session_state[f"temp_row_{entry_id}"] = {
                    'Клиент': db_row.get('client_name', db_row.get('Клиент', '')),
                    'Телефон': db_row.get('phone', db_row.get('Телефон', '')),
                    'Адрес загрузки': db_row.get('load_address', db_row.get('Адрес загрузки', 'Склад №1')),
                    'Статус': db_row.get('status', db_row.get('Статус', 'ПРИЕМКА')),
                    'ТС (Госномер)': db_row.get('vehicle', db_row.get('ТС (Госномер)', '')),
                    'Водитель': db_row.get('driver', db_row.get('Водитель', '')),
                    'Сертификат': db_row.get('has_certificate', db_row.get('Сертификат', 'Нет')),
                    'Общий объем (м3)': db_row.get('total_volume', 0.0)
                }
                
                # ДОСТАЕМ ТОВАРЫ ИЗ items_data (Тут решается проблема пустоты)
                items_raw = db_row.get('items_data', [])
                if isinstance(items_raw, list) and len(items_raw) > 0:
                    items_reg = pd.DataFrame(items_raw)
                else:
                    # Фолбэк на реестр, если в базе совсем пусто
                    items_reg = st.session_state.items_registry.get(
                        entry_id, 
                        pd.DataFrame(columns=['Название товара', 'Кол-во', 'Объем (м3)', 'Адрес'])
                    ).copy()

                # Проверка колонок
                for col in ['Название товара', 'Кол-во', 'Объем (м3)', 'Адрес']:
                    if col not in items_reg.columns:
                        items_reg[col] = 0 if 'Объем' in col or 'Кол' in col else "НЕ УКАЗАНО"
                        
                st.session_state[f"temp_items_{entry_id}"] = items_reg

                # Индекс для локального DF
                if table_key in st.session_state:
                    df_local = st.session_state[table_key]
                    idx_list = df_local.index[df_local['id'] == entry_id].tolist()
                    st.session_state[f"temp_idx_{entry_id}"] = idx_list[0] if idx_list else None

            except Exception as e:
                st.error(f"Ошибка инициализации прихода: {e}")
                return

    # Ссылки на данные в текущей сессии
    row = st.session_state[f"temp_row_{entry_id}"]
    items_df = st.session_state[f"temp_items_{entry_id}"]
    idx = st.session_state.get(f"temp_idx_{entry_id}")

    st.markdown(f"### 📥 Приходная накладная `{entry_id}`")
    tab_info, tab_wh = st.tabs(["📋 Данные поставки", "🏗️ Размещение на складе"])

    with tab_info:
        c1, c2, c3 = st.columns(3)
        row['Клиент'] = c1.text_input("Поставщик", value=row.get('Клиент', ''), key=f"ar_f1_{entry_id}")
        row['Телефон'] = c2.text_input("Контакт поставщика", value=row.get('Телефон', ''), key=f"ar_f2_{entry_id}")
        row['Адрес загрузки'] = c3.text_input("Склад приемки", value=row.get('Адрес загрузки', 'Склад №1'), key=f"ar_f3_{entry_id}")

        r2_1, r2_2, r2_3, r2_4 = st.columns(4)
        status_list = ["ПРИЕМКА", "РАЗГРУЗКА", "ПРИНЯТО", "РАСХОЖДЕНИЕ"]
        curr_st = row.get('Статус', 'ПРИЕМКА')
        st_idx = status_list.index(curr_st) if curr_st in status_list else 0
        
        row['Статус'] = r2_1.selectbox("Статус приемки", status_list, index=st_idx, key=f"ar_f4_{entry_id}")
        row['ТС (Госномер)'] = r2_2.text_input("Транспорт (номер)", value=row.get('ТС (Госномер)', ''), key=f"ar_f5_{entry_id}")
        row['Водитель'] = r2_3.text_input("Водитель", value=row.get('Водитель', ''), key=f"ar_f6_{entry_id}")
        row['Сертификат'] = r2_4.selectbox("Документы в порядке", ["Да", "Нет"], 
                                           index=(0 if row.get('Сертификат')=="Да" else 1), key=f"ar_f7_{entry_id}")

        st.divider()
        st.markdown("### 📦 Состав принимаемого груза")
        
        # Редактор (заменил на width="stretch")
        updated_items = st.data_editor(items_df, width="stretch", num_rows="dynamic", key=f"ar_ed_{entry_id}")
        st.session_state[f"temp_items_{entry_id}"] = updated_items

        if st.button("💾 ЗАФИКСИРОВАТЬ ПРИЕМКУ", width="stretch", type="primary"):
            # Расчет итогов
            valid_vol = pd.to_numeric(updated_items['Объем (м3)'], errors='coerce').fillna(0)
            total_vol = round(float(valid_vol.sum()), 3)
            
            # 1. ПОДГОТОВКА ДАННЫХ (БЕЗ СОКРАЩЕНИЙ)
            db_payload = {
                "client_name": row['Клиент'],
                "phone": row['Телефон'],
                "load_address": row['Адрес загрузки'],
                "status": row['Статус'],
                "vehicle": row['ТС (Госномер)'],
                "driver": row['Водитель'],
                "has_certificate": row['Сертификат'],
                "total_volume": total_vol,
                "items_count": len(updated_items),
                "items_data": updated_items.replace({np.nan: None}).to_dict(orient='records'),
                "updated_at": datetime.now().isoformat()
            }

            try:
                # 2. СОХРАНЕНИЕ В ОБЛАКО
                supabase.table(table_key).update(db_payload).eq("id", entry_id).execute()

                # 3. СИНХРОНИЗАЦИЯ С ТАБЛИЦЕЙ INVENTORY
                if row['Статус'] == "ПРИНЯТО":
                    # Сначала очищаем старые записи по этому doc_id, чтобы не было конфликта
                    supabase.table("inventory").delete().eq("doc_id", entry_id).execute()
                    
                    inv_rows = []
                    for _, item in updated_items.iterrows():
                        addr = item.get('Адрес')
                        if addr and addr != "НЕ УКАЗАНО":
                            inv_rows.append({
                                "doc_id": entry_id,
                                "item_name": item['Название товара'],
                                "cell_address": addr,
                                "quantity": float(item.get('Кол-во', 0)),
                                "warehouse_id": addr.split('-')[0].replace('WH', '') if '-' in addr else "1"
                            })
                    if inv_rows:
                        supabase.table("inventory").insert(inv_rows).execute()

                # 4. ОБНОВЛЕНИЕ ЛОКАЛЬНОГО СОСТОЯНИЯ
                if idx is not None:
                    target_df = st.session_state[table_key]
                    for field, val in row.items():
                        if field in target_df.columns:
                            target_df.at[idx, field] = val
                    target_df.at[idx, 'Общий объем (м3)'] = total_vol
                    if "items_data" in target_df.columns:
                        target_df.at[idx, "items_data"] = db_payload["items_data"]
                
                st.session_state.items_registry[entry_id] = updated_items
                st.success(f"✅ Приемка {entry_id} сохранена!")
                time.sleep(1)
                st.rerun()

            except Exception as e:
                st.error(f"🚨 Ошибка: {e}")

    with tab_wh:
        from config import render_warehouse_logic # убедись, что импорт верный
        render_warehouse_logic(entry_id, updated_items)
        
@st.dialog("🔍 Карточка Прихода", width="large")
def show_arrival_details_modal(arrival_id):
    from database import supabase
    import pandas as pd

    # --- 1. ЗАГРУЗКА АКТУАЛЬНЫХ ДАННЫХ ИЗ БД ---
    try:
        response = supabase.table("arrivals").select("*").eq("id", arrival_id).execute()
        if not response.data:
            st.error(f"Документ {arrival_id} не найден.")
            return
            
        db_row = response.data[0]
        items_list = db_row.get('items_data', [])
        items_df = pd.DataFrame(items_list) if items_list else pd.DataFrame(columns=['Название товара', 'Кол-во', 'Адрес'])
        
    except Exception as e:
        st.warning(f"⚠️ Ошибка связи с БД. {e}")
        return

    # --- 2. ОТОБРАЖЕНИЕ ОСНОВНЫХ ДАННЫХ ---
    st.subheader(f"📥 Детальный обзор прихода: {arrival_id}")
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"**🏢 Поставщик:** {db_row.get('client_name', '---')}")
        st.markdown(f"**📞 Контакт:** {db_row.get('phone', '---')}")
    with c2:
        st.markdown(f"**📦 Статус:** `{db_row.get('status', '---')}`")
        st.markdown(f"**🏗️ Склад приемки:** {db_row.get('load_address', '---')}")
    with c3:
        st.markdown(f"**🚛 Транспорт:** {db_row.get('vehicle', '---')}")
        st.markdown(f"**👤 Водитель:** {db_row.get('driver', '---')}")

    st.divider()
    
    # --- 3. ТАБЛИЦА ТОВАРОВ ---
    st.markdown("### 📋 Принятые позиции")
    if not items_df.empty:
        # Стилизация адреса
        if 'Адрес' in items_df.columns:
            st.dataframe(items_df, use_container_width=True)
        else:
            st.dataframe(items_df, use_container_width=True)
            
        m1, m2, m3 = st.columns(3)
        m1.metric("Принято строк", f"{len(items_df)}")
        m2.metric("Общий объем", f"{db_row.get('total_volume', 0)} м³")
        
        if db_row.get('status') == "ПРИНЯТО":
             m3.success("✅ Размещено на складе")
        else:
             m3.warning("⏳ Ожидает размещения")
    else:
        st.warning("⚠️ Спецификация товаров пуста.")

    # --- 4. ДОБАВЛЕНИЕ ЖУРНАЛА ИЗМЕНЕНИЙ (МОЛДОВА) ---
    st.write("") # Отступ
    exp_c1, exp_c2 = st.columns([1, 1]) # Можно сделать в колонке или на всю ширину
    
    with exp_c1:
        # Дополнительная информация (если есть)
        st.caption(f"ID записи: {db_row.get('id')}")

    with exp_c2:
        with st.expander("🕒 Журнал изменений (Moldova Time)"):
            # Берем системные колонки created_at и updated_at из Supabase
            created = format_to_moldova_time(db_row.get('created_at'))
            updated = format_to_moldova_time(db_row.get('updated_at'))
            
            st.write(f"**📅 Создан:** {created}")
            st.write(f"**🔄 Обновлен:** {updated}")
            st.write(f"**👤 Автор правок:** {db_row.get('updated_by', 'Система')}")

    # --- 5. КНОПКА ЗАКРЫТИЯ ---
    if st.button("❌ ЗАКРЫТЬ", use_container_width=True):
        st.rerun()
        
@st.dialog("🖨️ Печать приходного ордера", width="large")
def show_arrival_print_modal(arrival_id):
    from database import supabase
    import pandas as pd

    # --- 1. ЗАГРУЗКА АКТУАЛЬНЫХ ДАННЫХ ИЗ БД ---
    try:
        response = supabase.table("arrivals").select("*").eq("id", arrival_id).execute()
        
        if not response.data:
            st.error("Ошибка: Приход не найден в базе данных")
            return
            
        row = response.data[0]
        # Берем список товаров напрямую из JSONB поля
        items_list = row.get('items_data', [])
        items_df = pd.DataFrame(items_list) if items_list else pd.DataFrame(columns=["Товар", "Кол-во", "Адрес"])
    except Exception as e:
        st.error(f"Ошибка связи с БД: {e}")
        return

    # --- 2. ПОДГОТОВКА ТАБЛИЦЫ ТОВАРОВ ---
    # Очищаем таблицу от лишних колонок для печати
    if not items_df.empty:
        # Оставляем только важные колонки, если они есть
        cols_to_show = [c for c in ['Название товара', 'Кол-во', 'Объем (м3)', 'Адрес'] if c in items_df.columns]
        print_df = items_df[cols_to_show].fillna("-")
    else:
        print_df = pd.DataFrame(columns=["Товар", "Кол-во"])

    items_html = print_df.to_html(index=False, border=1, classes='items-table')

    # --- 3. ГЕНЕРАЦИЯ HTML ---
    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        @media print {{ .no-print {{ display: none !important; }} }}
        body {{ font-family: sans-serif; padding: 20px; color: #333; }}
        .print-container {{ background: white; padding: 20px; border: 1px solid #ccc; max-width: 800px; margin: auto; }}
        .header {{ border-bottom: 2px solid #000; display: flex; justify-content: space-between; align-items: center; padding-bottom: 10px; }}
        .info-table {{ width: 100%; margin-top: 20px; border-collapse: collapse; }}
        .info-table td {{ border: 1px solid #eee; padding: 8px; font-size: 14px; }}
        .items-table {{ width: 100%; margin-top: 20px; border-collapse: collapse; }}
        .items-table th {{ background: #f2f2f2; padding: 10px; border: 1px solid #000; font-size: 13px; text-align: left; }}
        .items-table td {{ padding: 10px; border: 1px solid #000; font-size: 13px; }}
        .footer-sigs {{ margin-top:50px; display:flex; justify-content: space-between; font-weight: bold; }}
    </style>
    </head>
    <body>
        <button class="no-print" onclick="window.print()" style="width:100%; padding:12px; background: #2E7D32; color:white; border:none; cursor:pointer; font-weight:bold; margin-bottom: 10px;">
            🖨️ ПЕЧАТАТЬ ПРИХОДНЫЙ ОРДЕР / СОХРАНИТЬ PDF
        </button>
        <div class="print-container">
            <div class="header">
                <div style="text-align:left;">
                    <h2 style="margin:0;">ПРИХОДНЫЙ ОРДЕР №{arrival_id}</h2>
                    <small>Дата формирования: {datetime.now().strftime('%d.%m.%Y %H:%M')}</small>
                </div>
                <div style="text-align:right;">
                    <p style="margin:0; font-weight:bold;">IMPERIA WMS</p>
                    <p style="margin:0; font-size:12px;">УЧЕТ ПРИЕМКИ</p>
                </div>
            </div>
            <table class="info-table">
                <tr>
                    <td><b>Отправитель (Поставщик):</b><br>{row.get('client_name', row.get('Клиент', '---'))}</td>
                    <td><b>Склад приемки:</b><br>{row.get('load_address', row.get('Адрес загрузки', '---'))}</td>
                </tr>
                <tr>
                    <td><b>Транспорт:</b> {row.get('vehicle', row.get('ТС (Госномер)', '---'))}</td>
                    <td><b>Водитель:</b> {row.get('driver', row.get('Водитель', '---'))}</td>
                </tr>
            </table>
            <h3 style="margin-top:30px; border-bottom: 1px solid #eee;">СПЕЦИФИКАЦИЯ ПРИНЯТОГО ТОВАРА</h3>
            {items_html}
            
            <div class="footer-sigs">
                <div>Сдал (Водитель): _________________</div>
                <div>Принял (Кладовщик): _________________</div>
            </div>
            
            <div style="margin-top:40px; text-align:center; font-size:10px; color:#999;">
                Документ сгенерирован автоматически в системе IMPERIA WMS
            </div>
        </div>
    </body>
    </html>
    """
    components.html(full_html, height=800, scrolling=True)

    if st.button("❌ ЗАКРЫТЬ", use_container_width=True):
        st.session_state.active_print_modal = None
        st.rerun()
        
    
@st.dialog("⚙️ Корректировка: Дополнение к документу", width="large")
def edit_extra_modal(entry_id):
    from database import supabase
    import numpy as np
    import time

    table_key = "extras"
    
    # --- 1. ИНИЦИАЛИЗАЦИЯ ---
    if f"temp_row_{entry_id}" not in st.session_state:
        if table_key not in st.session_state:
            st.error("Таблица дополнений не инициализирована")
            return
            
        df = st.session_state[table_key]
        idx_list = df.index[df['id'] == entry_id].tolist()
        
        if not idx_list:
            st.error("Запись не найдена")
            return
        
        st.session_state[f"temp_idx_{entry_id}"] = idx_list[0]
        st.session_state[f"temp_row_{entry_id}"] = df.iloc[idx_list[0]].to_dict()
        st.session_state[f"temp_items_{entry_id}"] = st.session_state.items_registry.get(
            entry_id, pd.DataFrame(columns=['Название товара', 'Кол-во', 'Объем (м3)', 'Адрес'])
        ).copy()

    row = st.session_state[f"temp_row_{entry_id}"]
    items_df = st.session_state[f"temp_items_{entry_id}"]
    idx = st.session_state[f"temp_idx_{entry_id}"]

    st.markdown(f"### 🖋️ Редактирование дополнения `{entry_id}`")
    tab_info, tab_wh = st.tabs(["📝 Детали (EXTRA_COLUMNS)", "🏗️ Размещение на складе"])

    with tab_info:
        st.markdown("##### 👤 Субъекты и Связи")
        c1, c2, c3 = st.columns(3)
        row['Кто одобрил'] = c1.text_input("Кто одобрил (ФИО/Контрагент)", value=row.get('Кто одобрил', ''), key=f"ex_v1_{entry_id}")
        row['Связь с ID'] = c2.text_input("Связь с ID (Родительский док)", value=row.get('Связь с ID', ''), key=f"ex_v2_{entry_id}")
        row['На чем'] = c3.text_input("На чем (Транспорт/Курьер)", value=row.get('На чем', ''), key=f"ex_v3_{entry_id}")

        st.markdown("##### 📅 Время и Локация")
        r2_1, r2_2, r2_3 = st.columns(3)
        # Обработка даты
        try:
            curr_date = pd.to_datetime(row.get('Когда', datetime.now())).date()
        except:
            curr_date = datetime.now().date()
            
        row['Когда'] = r2_1.date_input("Когда (Дата события)", value=curr_date, key=f"ex_v4_{entry_id}").strftime("%Y-%m-%d")
        row['Время'] = r2_2.text_input("Время", value=row.get('Время', datetime.now().strftime("%H:%M")), key=f"ex_v5_{entry_id}")
        row['Где'] = r2_3.text_input("Где (Точка/Склад)", value=row.get('Где', ''), key=f"ex_v6_{entry_id}")

        st.markdown("##### 📄 Суть корректировки")
        r3_1, r3_2, r3_3 = st.columns([2, 1, 1])
        row['Что именно'] = r3_1.text_input("Что именно (Краткая суть)", value=row.get('Что именно', ''), key=f"ex_v7_{entry_id}")
        
        status_opts = ["СОГЛАСОВАНО", "В РАБОТЕ", "ЗАВЕРШЕНО", "ОТМЕНЕНО"]
        curr_status = row.get('Статус', "СОГЛАСОВАНО")
        st_idx = status_opts.index(curr_status) if curr_status in status_opts else 0
        row['Статус'] = r3_2.selectbox("Статус", status_opts, index=st_idx, key=f"ex_v8_{entry_id}")
        row['Сумма заявки'] = r3_3.number_input("Сумма заявки", value=float(row.get('Сумма заявки', 0.0)), key=f"ex_v9_{entry_id}")

        row['Почему (Причина)'] = st.text_area("Почему (Причина корректировки)", value=row.get('Почему (Причина)', ''), height=70, key=f"ex_v10_{entry_id}")

        st.divider()
        st.markdown("### 📦 Изменения в составе товаров")
        updated_items = st.data_editor(items_df, use_container_width=True, num_rows="dynamic", key=f"ex_ed_{entry_id}")
        st.session_state[f"temp_items_{entry_id}"] = updated_items

        if st.button("💾 СОХРАНИТЬ ВСЕ ДАННЫЕ", use_container_width=True, type="primary"):
            # 1. ПОДГОТОВКА PAYLOAD ДЛЯ SUPABASE
            # Маппинг на колонки вашей таблицы extras в БД
            db_payload = {
                "approved_by": row['Кто одобрил'],
                "parent_id": row['Связь с ID'],
                "transport": row['На чем'],
                "event_date": row['Когда'],
                "event_time": row['Время'],
                "location": row['Где'],
                "subject": row['Что именно'],
                "status": row['Статус'],
                "amount": float(row['Сумма заявки']),
                "reason": row['Почему (Причина)'],
                "items_count": len(updated_items),
                "items_data": updated_items.replace({np.nan: None}).to_dict(orient='records'),
                "updated_at": datetime.now().isoformat()
            }

            try:
                # 2. СОХРАНЕНИЕ В ОБЛАКО (Таблица extras)
                supabase.table(table_key).update(db_payload).eq("id", entry_id).execute()

                # 3. СИНХРОНИЗАЦИЯ СКЛАДСКИХ ОСТАТКОВ (inventory)
                # Если корректировка завершена, обновляем ячейки
                if row['Статус'] == "ЗАВЕРШЕНО":
                    for _, item in updated_items.iterrows():
                        if item.get('Адрес') and item['Адрес'] != "НЕ УКАЗАНО":
                            inv_payload = {
                                "doc_id": entry_id,
                                "item_name": item['Название товара'],
                                "cell_address": item['Адрес'],
                                "quantity": float(item.get('Кол-во', 0)),
                                "warehouse_id": item['Адрес'].split('-')[0].replace('WH', '') if '-' in item['Адрес'] else "1"
                            }
                            supabase.table("inventory").upsert(inv_payload, on_conflict="doc_id, item_name").execute()

                # 4. ОБНОВЛЕНИЕ ЛОКАЛЬНОГО СОСТОЯНИЯ
                target_df = st.session_state[table_key]
                for field, val in row.items():
                    if field in target_df.columns:
                        target_df.at[idx, field] = val
                
                # Синхронизация с MAIN
                if "main" in st.session_state:
                    m_df = st.session_state["main"]
                    m_idx_list = m_df.index[m_df['id'] == entry_id].tolist()
                    if m_idx_list:
                        m_idx = m_idx_list[0]
                        m_df.at[m_idx, 'Статус'] = row['Статус']
                        if 'Сумма заявки' in m_df.columns:
                            m_df.at[m_idx, 'Сумма заявки'] = row['Сумма заявки']

                st.session_state.items_registry[entry_id] = updated_items
                st.success(f"✅ Корректировка {entry_id} синхронизирована с БД!")
                time.sleep(1)
                st.rerun()

            except Exception as e:
                st.error(f"🚨 Ошибка сохранения корректировки: {e}")

    with tab_wh:
        # Универсальная логика визуализации склада
        render_warehouse_logic(entry_id, updated_items)
        
@st.dialog("🔍 Просмотр дополнения", width="large")
def show_extra_details_modal(extra_id):
    from database import supabase
    import pandas as pd

    # --- 1. ЗАГРУЗКА АКТУАЛЬНЫХ ДАННЫХ ИЗ БД (SUPABASE) ---
    try:
        response = supabase.table("extras").select("*").eq("id", extra_id).execute()
        
        if not response.data:
            st.error(f"Запись {extra_id} не найдена в базе данных.")
            return
            
        db_row = response.data[0]
        
        # Извлекаем состав товаров из JSONB поля
        items_list = db_row.get('items_data', [])
        items_df = pd.DataFrame(items_list) if items_list else pd.DataFrame(columns=['Название товара', 'Кол-во', 'Адрес'])
        
    except Exception as e:
        st.warning(f"⚠️ Ошибка подключения к БД. {e}")
        return

    # --- 2. ОТОБРАЖЕНИЕ ДАННЫХ ---
    st.subheader(f"📑 Детальный просмотр корректировки: {extra_id}")
    st.markdown("---")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"**👤 Кто одобрил:**\n{db_row.get('approved_by', '---')}")
        st.markdown(f"**🔗 Связь с ID:**\n`{db_row.get('parent_id', 'НЕТ')}`")
        st.markdown(f"**📈 Статус:**\n`{db_row.get('status', '---')}`")

    with col2:
        st.markdown(f"**🎯 Что именно:**\n{db_row.get('subject', '---')}")
        st.markdown(f"**📅 Дата события:**\n{db_row.get('event_date', '---')}")
        st.markdown(f"**🕒 Время события:**\n{db_row.get('event_time', '---')}")

    with col3:
        st.markdown(f"**🚚 Транспорт:**\n{db_row.get('transport', '---')}")
        st.markdown(f"**📍 Локация:**\n{db_row.get('location', '---')}")
        
        try:
            val_sum = float(db_row.get('amount', 0.0))
        except:
            val_sum = 0.0
        st.markdown(f"**💰 Сумма заявки:**\n{val_sum:,.2f}")

    # Причина
    st.warning(f"**❓ Причина (Почему):** {db_row.get('reason', 'Не указана')}")

    st.divider()
    
    # --- 3. ТАБЛИЦА ТОВАРОВ ---
    count_pos = db_row.get('items_count', len(items_df))
    st.markdown(f"### 📦 Состав позиций (Всего: {count_pos})")
    
    if not items_df.empty:
        st.dataframe(items_df, use_container_width=True)
    else:
        st.info("Спецификация товаров пуста.")

    # --- 4. ЖУРНАЛ ИЗМЕНЕНИЙ (MOLDOVA TIME) ---
    st.write("") # Небольшой отступ
    exp_c1, exp_c2 = st.columns([1, 1])
    
    with exp_c1:
        st.caption(f"Системный ID: {db_row.get('id')}")

    with exp_c2:
        with st.expander("🕒 Журнал изменений (Moldova Time)"):
            # Конвертируем технические даты Supabase
            created = format_to_moldova_time(db_row.get('created_at'))
            updated = format_to_moldova_time(db_row.get('updated_at'))
            
            st.write(f"**📅 Создано:** {created}")
            st.write(f"**🔄 Обновлено:** {updated}")
            st.write(f"**👤 Автор правок:** {db_row.get('updated_by', 'Система')}")

    st.divider()

    # --- 5. КНОПКА ЗАКРЫТИЯ ---
    if st.button("❌ ЗАКРЫТЬ", use_container_width=True):
        st.rerun()
        
@st.dialog("🖨️ Печать приложения", width="large")
def show_extra_print_modal(extra_id):
    from database import supabase
    import pandas as pd

    # --- 1. ПОЛУЧЕНИЕ ДАННЫХ ИЗ ОБЛАКА ---
    try:
        response = supabase.table("extras").select("*").eq("id", extra_id).execute()
        
        if not response.data:
            st.error("Запись не найдена в БД.")
            return
            
        row = response.data[0]
        # Загружаем товары напрямую из JSONB
        items_list = row.get('items_data', [])
        items_df = pd.DataFrame(items_list) if items_list else pd.DataFrame(columns=["Товар", "Кол-во"])
    except Exception as e:
        st.error(f"Ошибка связи с базой данных: {e}")
        return

    # --- 2. ПОДГОТОВКА ТАБЛИЦЫ ТОВАРОВ ---
    if not items_df.empty:
        # Оставляем только нужные для печати колонки
        cols = [c for c in ['Название товара', 'Кол-во', 'Объем (м3)', 'Адрес'] if c in items_df.columns]
        print_df = items_df[cols].fillna("-")
    else:
        print_df = pd.DataFrame(columns=["Товар", "Кол-во"])

    items_html = print_df.to_html(index=False, border=1, classes='items-table')

    # --- 3. ГЕНЕРАЦИЯ HTML ---
    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        @media print {{ .no-print {{ display: none !important; }} }}
        body {{ font-family: 'Segoe UI', sans-serif; padding: 30px; line-height: 1.6; color: #333; }}
        .print-card {{ border: 2px solid #333; padding: 25px; border-radius: 10px; max-width: 850px; margin: auto; }}
        .doc-header {{ text-align: center; border-bottom: 2px solid #333; margin-bottom: 20px; padding-bottom: 10px; }}
        .info-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; }}
        .items-table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        .items-table th, .items-table td {{ border: 1px solid #333; padding: 10px; text-align: left; font-size: 13px; }}
        .items-table th {{ background-color: #f2f2f2; }}
        .footer {{ margin-top: 50px; font-style: italic; font-size: 12px; }}
        .signature-section {{ display: flex; justify-content: space-between; margin-top: 40px; font-weight: bold; }}
    </style>
    </head>
    <body>
        <button class="no-print" onclick="window.print()" style="width:100%; padding:15px; background:#fb8c00; color:white; border:none; border-radius:5px; font-weight:bold; cursor:pointer; margin-bottom:20px;">
            🖨️ ОТПРАВИТЬ НА ПЕЧАТЬ / СОХРАНИТЬ В PDF
        </button>
        <div class="print-card">
            <div class="doc-header">
                <h1 style="margin:0;">ПРИЛОЖЕНИЕ К ДОКУМЕНТУ №{extra_id}</h1>
                <p>К основному документу: <b>{row.get('parent_id', row.get('Связь с ID', '_______'))}</b></p>
            </div>
            <div class="info-grid">
                <div>
                    <b>Суть корректировки:</b> {row.get('subject', row.get('Что именно', '---'))}<br>
                    <b>Контрагент/Одобрил:</b> {row.get('approved_by', row.get('Кто одобрил', '---'))}
                </div>
                <div style="text-align: right;">
                    <b>Дата корректировки:</b> {row.get('event_date', row.get('Когда', '---'))}<br>
                    <b>Статус:</b> {row.get('status', row.get('Статус', '---'))}
                </div>
            </div>
            
            <div style="background: #f9f9f9; padding: 10px; border-left: 4px solid #fb8c00; margin-bottom: 20px;">
                <b>Причина:</b> {row.get('reason', row.get('Почему (Причина)', 'Не указана'))}
            </div>

            <h3>ПЕРЕЧЕНЬ ИЗМЕНЕНИЙ / ДОПОЛНИТЕЛЬНЫХ ПОЗИЦИЙ</h3>
            {items_html}

            <div class="footer">
                <p>Данное дополнение является неотъемлемой частью основного складского документа. Сведения актуальны на момент печати.</p>
                <div class="signature-section">
                    <div>Ответственное лицо: _________________</div>
                    <div>Контрагент: _________________</div>
                </div>
                <p style="text-align:center; margin-top:30px; color:#aaa;">IMPERIA WMS | Система управления складом</p>
            </div>
        </div>
    </body>
    </html>
    """
    components.html(full_html, height=850, scrolling=True)

    if st.button("❌ ЗАКРЫТЬ", use_container_width=True):
        st.session_state.active_print_modal = None
        st.rerun()
        

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import time
import ast

def upload_image(file):
    """Загрузка изображения в Supabase Storage"""
    from database import supabase
    try:
        file_ext = file.name.split(".")[-1]
        file_name = f"defect_{int(time.time())}.{file_ext}"
        # Важно: Бакет 'defects_photos' должен быть создан в Supabase и быть PUBLIC
        supabase.storage.from_("defects_photos").upload(
            path=file_name,
            file=file.getvalue(),
            file_options={"content-type": f"image/{file_ext}"}
        )
        return supabase.storage.from_("defects_photos").get_public_url(file_name)
    except Exception as e:
        st.error(f"Ошибка загрузки фото: {e}")
        return None

@st.dialog("🚨 Актирование и Редактирование брака", width="large")
def edit_defect_modal(entry_id):
    from database import supabase
    import pandas as pd
    import numpy as np
    from datetime import datetime
    import time
    import uuid

    # --- 1. ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ ЗАГРУЗКИ ТОВАРОВ ИЗ INVENTORY ---
    def fetch_inventory_clean():
        try:
            # Берем всё из inventory, исключая TOTAL (как в регистрации)
            response = supabase.table("inventory").select("item_name, quantity, cell_address").execute()
            if not response.data:
                return pd.DataFrame(columns=['Товар', 'Кол-во', 'Ячейка'])
            
            df_inv = pd.DataFrame(response.data)
            # Убираем системные строки TOTAL
            df_inv = df_inv[df_inv['item_name'] != 'TOTAL']
            
            # Переименовываем для редактора спецификации
            df_inv = df_inv.rename(columns={
                'item_name': 'Товар',
                'quantity': 'Кол-во',
                'cell_address': 'Ячейка'
            })
            return df_inv
        except Exception as e:
            st.error(f"Ошибка загрузки инвентаря: {e}")
            return pd.DataFrame(columns=['Товар', 'Кол-во', 'Ячейка'])

    # --- 2. ИНИЦИАЛИЗАЦИЯ ДАННЫХ ИЗ БАЗЫ (DEFECTS) ---
    if f"temp_row_{entry_id}" not in st.session_state:
        try:
            res = supabase.table("defects").select("*").eq("id", entry_id).execute()
            if res.data:
                db_row = res.data[0]
                
                # Синхронизация полей с таблицей в БД
                st.session_state[f"temp_row_{entry_id}"] = {
                    'item_name': db_row.get('item_name', ''),
                    'linked_doc_id': db_row.get('linked_doc_id', ''),
                    'defect_type': db_row.get('defect_type', 'Бой'),
                    'culprit': db_row.get('culprit', 'Не установлен'),
                    'status': db_row.get('status', 'ОБНАРУЖЕНО'),
                    'decision': db_row.get('decision', 'На проверку'),
                    'storage_address': db_row.get('storage_address', 'ZONE-BRAK'),
                    'photo_url': db_row.get('photo_url', ''),
                    'description': db_row.get('description', ''),
                    'responsible_party': db_row.get('responsible_party', '')
                }
                
                # Загрузка спецификации (JSONB)
                items_in_act = db_row.get('items_data', [])
                if isinstance(items_in_act, dict): # Если это один объект
                    items_in_act = [items_in_act]
                
                if isinstance(items_in_act, list) and len(items_in_act) > 0:
                    st.session_state[f"temp_items_{entry_id}"] = pd.DataFrame(items_in_act)
                else:
                    # Если спецификация пуста, создаем строку на основе данных акта
                    st.session_state[f"temp_items_{entry_id}"] = pd.DataFrame([{
                        "Товар": db_row.get('item_name'),
                        "Кол-во": db_row.get('quantity', 1),
                        "Описание": db_row.get('description', '')
                    }])
        except Exception as e:
            st.error(f"Ошибка инициализации акта: {e}")
            return

    # Ссылки на данные в сессии
    row = st.session_state[f"temp_row_{entry_id}"]
    items_df = st.session_state[f"temp_items_{entry_id}"]

    st.subheader(f"📝 Редактирование Акта №{entry_id}")

    # --- 3. ИНТЕРФЕЙС РЕДАКТИРОВАНИЯ ---
    c1, c2, c3 = st.columns(3)
    row['item_name'] = c1.text_input("📦 Товар (основной)", value=row['item_name'])
    row['linked_doc_id'] = c2.text_input("📄 ID Документа-основания", value=row['linked_doc_id'])
    row['storage_address'] = c3.text_input("📍 Зона брака", value=row['storage_address'])

    r2_1, r2_2, r2_3 = st.columns(3)
    defect_opts = ["Бой", "Порча", "Брак производителя", "Некомплект"]
    row['defect_type'] = r2_1.selectbox("Тип дефекта", defect_opts, 
                                        index=defect_opts.index(row['defect_type']) if row['defect_type'] in defect_opts else 0)
    
    culprit_opts = ["Склад", "Перевозчик", "Поставщик", "Не установлен"]
    row['culprit'] = r2_2.selectbox("Ответственная сторона", culprit_opts, 
                                    index=culprit_opts.index(row['culprit']) if row['culprit'] in culprit_opts else 0)
    
    status_opts = ["ОБНАРУЖЕНО", "В ЭКСПЕРТИЗЕ", "ПОДТВЕРЖДЕНО", "СПИСАНО"]
    row['status'] = r2_3.selectbox("Статус акта", status_opts, 
                                    index=status_opts.index(row['status']) if row['status'] in status_opts else 0)

    col_res, col_resp = st.columns([2, 1])
    row['decision'] = col_res.text_area("⚖️ Решение / Заключение комиссии", value=row['decision'], height=80)
    row['responsible_party'] = col_resp.text_input("👤 Кто выявил (ФИО)", value=row['responsible_party'])

    # --- 4. БЛОК ФОТО (С ЗАГРУЗКОЙ В STORAGE) ---
    st.divider()
    st.write("📸 **Фотофиксация повреждений**")
    
    col_img, col_up = st.columns([1, 2])
    
    if row['photo_url']:
        col_img.image(row['photo_url'], width=250, caption="Текущее фото")
    else:
        col_img.info("Фото отсутствует")
    
    uploaded_file = col_up.file_uploader("Заменить или добавить фото", type=['png', 'jpg', 'jpeg'], key=f"edit_up_{entry_id}")
    
    if uploaded_file:
        with st.spinner("Загрузка фото в облако..."):
            try:
                # Твоя логика генерации имени
                file_ext = uploaded_file.name.split('.')[-1]
                file_name = f"EDIT_{entry_id}_{int(time.time())}.{file_ext}"
                
                # Загружаем в бакет defects_photos
                supabase.storage.from_("defects_photos").upload(file_name, uploaded_file.getvalue())
                new_url = supabase.storage.from_("defects_photos").get_public_url(file_name)
                
                row['photo_url'] = new_url
                st.success("✅ Фото обновлено!")
                st.rerun() # Обновляем, чтобы показать новое фото
            except Exception as e:
                st.error(f"Ошибка загрузки фото: {e}")

    # --- 5. СПЕЦИФИКАЦИЯ (РЕДАКТИРУЕМАЯ ТАБЛИЦА) ---
    st.divider()
    st.write(f"📦 **Спецификация позиций в акте:**")
    
    updated_items = st.data_editor(
        items_df,
        use_container_width=True,
        num_rows="dynamic",
        key=f"editor_{entry_id}",
        column_config={
            "Товар": st.column_config.TextColumn("Наименование товара", width="large"),
            "Кол-во": st.column_config.NumberColumn("Кол-во (ед)", min_value=1),
            "Описание": st.column_config.TextColumn("Детали повреждения")
        }
    )

    # --- 6. СОХРАНЕНИЕ ВСЕХ ИЗМЕНЕНИЙ ---
    if st.button("💾 СОХРАНИТЬ ВСЕ ИЗМЕНЕНИЯ", use_container_width=True, type="primary"):
        # Чистим данные перед отправкой
        final_items_df = updated_items.dropna(subset=['Товар'])
        total_q = int(final_items_df['Кол-во'].sum()) if not final_items_df.empty else 0
        
        # Payload полностью синхронизирован с твоими колонками БД
        db_payload = {
            "item_name": row['item_name'],
            "main_item": row['item_name'], # Дублируем для совместимости
            "quantity": total_q,
            "total_defective": total_q, # Дублируем для совместимости
            "linked_doc_id": row['linked_doc_id'],
            "defect_type": row['defect_type'],
            "culprit": row['culprit'],
            "status": row['status'],
            "decision": row['decision'],
            "photo_url": row['photo_url'],
            "storage_address": row['storage_address'],
            "quarantine_address": row['storage_address'], # Дублируем
            "description": row['description'],
            "responsible_party": row['responsible_party'],
            "reported_by": row['responsible_party'], # Дублируем
            "items_data": final_items_df.replace({np.nan: None}).to_dict(orient='records'),
            "updated_at": datetime.now().isoformat()
        }

        with st.spinner("Синхронизация с базой данных..."):
            try:
                # Обновляем таблицу defects
                supabase.table("defects").update(db_payload).eq("id", entry_id).execute()
                
                # Очищаем кэш и сессию
                if f"temp_row_{entry_id}" in st.session_state:
                    del st.session_state[f"temp_row_{entry_id}"]
                st.cache_data.clear()
                
                st.success("🎉 Акт успешно обновлен!")
                time.sleep(1.2)
                st.rerun()
            except Exception as e:
                st.error(f"🚨 Критическая ошибка базы: {e}")
        
@st.dialog("🔍 Просмотр Акта брака", width="large")
def show_defect_details_modal(defect_id):
    from database import supabase
    import pandas as pd
    import streamlit as st

    # --- 1. ЗАГРУЗКА ДАННЫХ ИЗ ТАБЛИЦЫ DEFECTS ---
    try:
        # Тянем все поля по конкретному ID
        response = supabase.table("defects").select("*").eq("id", defect_id).execute()
        
        if not response.data:
            st.error(f"❌ Акт №{defect_id} не найден в базе данных.")
            if st.button("Закрыть"): st.rerun()
            return
            
        # Берем строку данных
        db_row = response.data[0]
        
        # Обработка вложенной спецификации (JSONB)
        items_list = db_row.get('items_data', [])
        # Если данные пришли строкой (хотя в Supabase это JSON), подстрахуемся
        if isinstance(items_list, str):
            import json
            try: items_list = json.loads(items_list)
            except: items_list = []
        
        # Превращаем в DataFrame для красивого отображения
        items_df = pd.DataFrame(items_list) if items_list else pd.DataFrame()

        # Чистим названия колонок в спецификации для пользователя
        if not items_df.empty:
            rename_map = {
                'item': 'Товар', 
                'item_name': 'Товар', 
                'qty': 'Кол-во', 
                'quantity': 'Кол-во',
                'description': 'Детали повреждения',
                'Описание': 'Детали повреждения'
            }
            items_df = items_df.rename(columns={k: v for k, v in rename_map.items() if k in items_df.columns})
    
    except Exception as e:
        st.error(f"🚨 Ошибка при чтении базы данных: {e}")
        return

    # --- 2. ШАПКА АКТА ---
    st.subheader(f"📑 Акт дефектовки №{defect_id}")
    
    # Метрики сверху для быстрого понимания ситуации
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("📊 Статус", db_row.get('status', 'Н/Д'))
    m2.metric("👤 Виновник", db_row.get('culprit', 'Не указан'))
    m3.metric("⚠️ Тип", db_row.get('defect_type', 'Н/Д'))
    m4.metric("🔢 Всего брака", f"{db_row.get('quantity', 0)} ед.")

    st.divider()
    
    # --- 3. ДЕТАЛЬНАЯ ИНФОРМАЦИЯ ---
    col_left, col_right = st.columns(2)
    
    with col_left:
        st.markdown("### 📦 Информация о товаре")
        st.write(f"**Наименование:** {db_row.get('item_name', '---')}")
        st.write(f"**Документ-основание:** `{db_row.get('linked_doc_id', 'Не привязан')}`")
        st.write(f"**Выявил сотрудник:** {db_row.get('responsible_party', 'Не указан')}")
    
    with col_right:
        st.markdown("### 📍 Локация и время")
        st.write(f"**Зона хранения брака:** `{db_row.get('storage_address', 'ZONE-BRAK')}`")
        
        # Красивое форматирование даты
        raw_date = db_row.get('updated_at') or db_row.get('created_at', '---')
        if 'T' in str(raw_date):
            clean_date = raw_date.replace('T', ' ').split('.')[0]
        else:
            clean_date = raw_date
            
        st.write(f"**Последнее обновление:** {clean_date}")
        st.write(f"**ID записи:** `{defect_id}`")

    # --- 4. ЗАКЛЮЧЕНИЕ И РЕШЕНИЕ ---
    st.markdown("---")
    with st.container():
        st.markdown("### ⚖️ Решение комиссии / Описание")
        decision_text = db_row.get('decision') or "Заключение еще не сформировано."
        st.info(decision_text)
        
        if db_row.get('description'):
            with st.expander("📝 Дополнительные комментарии"):
                st.write(db_row.get('description'))

    # --- 5. ФОТОФИКСАЦИЯ (ГЛАВНЫЙ ЭЛЕМЕНТ) ---
    photo_url = db_row.get('photo_url')
    if photo_url:
        st.markdown("---")
        st.markdown("### 📸 Фотография повреждения")
        # Показываем фото на всю ширину для детального осмотра
        st.image(photo_url, use_container_width=True, caption=f"Фотофиксация к акту №{defect_id}")
    else:
        st.warning("⚠️ К данному акту фотография не прикреплена.")

    # --- 6. ТАБЛИЦА СПЕЦИФИКАЦИИ ---
    st.markdown("---")
    st.markdown("### 📋 Детальная спецификация")
    if not items_df.empty:
        # Отображаем таблицу без возможности редактирования (просмотр)
        st.dataframe(
            items_df, 
            use_container_width=True, 
            hide_index=True
        )
    else:
        st.caption("Детальная спецификация позиций отсутствует. Информация указана в заголовке акта.")

    # --- 7. КНОПКИ УПРАВЛЕНИЯ ---
    st.divider()
    c_btn1, c_btn2 = st.columns(2)
    
    with c_btn1:
        if st.button("⬅️ ВЕРНУТЬСЯ К СПИСКУ", use_container_width=True):
            st.rerun()
            
    with c_btn2:
        # Полезная кнопка для перехода в режим редактирования прямо из просмотра
        if st.button("📝 РЕДАКТИРОВАТЬ АКТ", use_container_width=True, type="primary"):
            st.session_state['edit_defect_id'] = defect_id
            st.rerun()
        
@st.dialog("🖨️ Печать Акта о браке", width="large")
def show_defect_print_modal(defect_id):
    from database import supabase
    import pandas as pd
    import streamlit as st
    import json

    # --- 1. ЗАГРУЗКА И СИНХРОНИЗАЦИЯ ДАННЫХ ---
    try:
        response = supabase.table("defects").select("*").eq("id", defect_id).execute()
        if not response.data:
            st.error("❌ Ошибка: Акт не найден в базе данных")
            return
            
        row = response.data[0]
        
        # Синхронизация JSON данных (Спецификация)
        items_list = row.get('items_data', [])
        if isinstance(items_list, str):
            try: items_list = json.loads(items_list)
            except: items_list = []
            
        # Превращаем в DataFrame и унифицируем колонки СТРОГО под твою БД
        if items_list:
            items_df = pd.DataFrame(items_list)
            # Маппинг всех возможных вариантов названий в единый стандарт для печати
            rename_map = {
                'item': 'Товар', 
                'item_name': 'Товар',
                'Наименование': 'Товар', 
                'quantity': 'Кол-во',
                'qty': 'Кол-во',
                'description': 'Описание дефекта',
                'Описание': 'Описание дефекта',
                'Детали': 'Описание дефекта'
            }
            items_df = items_df.rename(columns={k: v for k, v in rename_map.items() if k in items_df.columns})
            
            # Гарантируем наличие нужных колонок для таблицы
            for col in ['Товар', 'Кол-во', 'Описание дефекта']:
                if col not in items_df.columns:
                    items_df[col] = "---"
            
            # Оставляем только нужный набор для печати
            items_df = items_df[['Товар', 'Кол-во', 'Описание дефекта']]
        else:
            items_df = pd.DataFrame(columns=['Товар', 'Кол-во', 'Описание дефекта'])
            
    except Exception as e:
        st.error(f"🚨 Ошибка связи с БД: {e}")
        return

    # --- 2. ПОДГОТОВКА HTML-ТАБЛИЦЫ ---
    if not items_df.empty:
        items_html = items_df.to_html(index=False, border=1, classes='data-table', escape=False)
    else:
        items_html = "<p style='text-align:center; padding: 20px;'>Спецификация товаров пуста</p>"

    # Логика фото (Синхронизировано с полем photo_url)
    photo_html = ""
    current_photo = row.get('photo_url')
    if current_photo:
        photo_html = f"""
        <div style="margin-top: 30px; text-align: center; page-break-inside: avoid;">
            <h3 style="font-size: 14px; text-align: left; border-left: 4px solid #d32f2f; padding-left: 10px; text-transform: uppercase;">
                Фотофиксация повреждений (Приложение к акту №{defect_id}):
            </h3>
            <div style="border: 1px solid #333; padding: 10px; background: #f9f9f9; display: inline-block; width: 95%;">
                <img src="{current_photo}" style="max-width: 100%; max-height: 500px; object-fit: contain;">
                <p style="font-size: 10px; color: #666; margin-top: 5px;">Дата снимка: {str(row.get('created_at'))[:16]}</p>
            </div>
        </div>
        """

    # --- 3. ГЕНЕРАЦИЯ ПОЛНОГО HTML ДОКУМЕНТА ---
    # Синхронизация переменных: main_item, linked_doc_id, storage_address
    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap');
            body {{ font-family: 'Roboto', Arial, sans-serif; padding: 20px; color: #1a1a1a; line-height: 1.5; background: #f0f0f0; }}
            .act-border {{ border: 1px solid #000; padding: 40px; background: #fff; max-width: 850px; margin: auto; box-shadow: 0 0 10px rgba(0,0,0,0.1); }}
            
            .header {{ text-align: center; border-bottom: 3px solid #d32f2f; margin-bottom: 25px; padding-bottom: 15px; position: relative; }}
            .header h1 {{ color: #d32f2f; margin: 0; font-size: 28px; letter-spacing: 2px; }}
            .header p {{ font-size: 12px; margin: 5px 0 0; font-weight: bold; color: #555; }}
            
            .info-table {{ width: 100%; border-collapse: collapse; margin-bottom: 25px; }}
            .info-table td {{ padding: 12px 8px; border-bottom: 1px solid #ddd; font-size: 14px; vertical-align: top; }}
            .label {{ font-weight: bold; color: #444; width: 30%; }}
            
            .data-table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
            .data-table th {{ background: #333; color: #fff; padding: 12px; border: 1px solid #000; text-align: left; font-size: 13px; }}
            .data-table td {{ padding: 10px; border: 1px solid #000; font-size: 13px; }}
            
            .decision-box {{ border: 2px dashed #d32f2f; padding: 20px; margin-top: 25px; background: #fffcfc; }}
            .decision-title {{ color: #d32f2f; font-weight: bold; font-size: 15px; margin-bottom: 10px; display: block; }}
            
            .footer {{ margin-top: 60px; display: flex; justify-content: space-between; }}
            .signature-block {{ width: 60%; }}
            .sig-item {{ margin-bottom: 35px; border-bottom: 1px solid #000; width: 300px; position: relative; }}
            .sig-label {{ font-size: 10px; position: absolute; bottom: -15px; left: 0; text-transform: uppercase; }}
            
            .stamp-area {{ width: 200px; display: flex; flex-direction: column; align-items: center; justify-content: center; }}
            .stamp {{ border: 3px double #1a237e; color: #1a237e; width: 140px; height: 140px; 
                        text-align: center; border-radius: 50%; opacity: 0.8; font-size: 12px; 
                        display: flex; align-items: center; justify-content: center;
                        transform: rotate(-10deg); font-weight: bold; border-style: double; }}
            
            .no-print {{ display: block; width: 100%; max-width: 850px; margin: 0 auto 20px; }}
            .print-btn {{
                width: 100%; padding: 20px; background: #2e7d32; color: white; 
                border: none; cursor: pointer; font-weight: bold; border-radius: 8px; 
                font-size: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.2);
            }}
            
            @media print {{ 
                .no-print {{ display: none !important; }} 
                body {{ background: white; padding: 0; }}
                .act-border {{ border: none; box-shadow: none; width: 100%; max-width: 100%; padding: 20px; }}
                .stamp {{ -webkit-print-color-adjust: exact; }}
            }}
        </style>
    </head>
    <body>
        <div class="no-print">
            <button class="print-btn" onclick="window.print()">
                🖨️ РАСПЕЧАТАТЬ АКТ (PDF / ПРИНТЕР)
            </button>
        </div>
        
        <div class="act-border">
            <div class="header">
                <h1>АКТ ДЕФЕКТОВКИ №{defect_id}</h1>
                <p>IMPERIA WMS | QUALITY CONTROL SYSTEM | ОФИЦИАЛЬНЫЙ ДОКУМЕНТ</p>
            </div>
            
            <table class="info-table">
                <tr>
                    <td class="label">Дата и время:</td>
                    <td>{str(row.get('updated_at', row.get('created_at', '---')))[:16].replace('T', ' ')}</td>
                    <td class="label">Статус:</td>
                    <td style="color: #d32f2f; font-weight: bold;">{row.get('status', 'ЗАРЕГИСТРИРОВАНО')}</td>
                </tr>
                <tr>
                    <td class="label">Виновник:</td>
                    <td>{row.get('culprit', 'Не установлен')}</td>
                    <td class="label">Тип дефекта:</td>
                    <td>{row.get('defect_type', 'Не указан')}</td>
                </tr>
                <tr>
                    <td class="label">Товар (основной):</td>
                    <td><b>{row.get('item_name', row.get('main_item', '---'))}</b></td>
                    <td class="label">Зона хранения:</td>
                    <td>{row.get('storage_address', row.get('quarantine_address', 'ZONE-BRAK'))}</td>
                </tr>
                <tr>
                    <td class="label">Документ-основание:</td>
                    <td>{row.get('linked_doc_id', row.get('related_doc_id', '---'))}</td>
                    <td class="label">Ответственный:</td>
                    <td>{row.get('responsible_party', 'Системный администратор')}</td>
                </tr>
            </table>
            
            <div class="decision-box">
                <span class="decision-title">ЗАКЛЮЧЕНИЕ И ПРИНЯТОЕ РЕШЕНИЕ:</span>
                <p style="margin: 0; font-style: italic;">{row.get('decision', 'Ожидается решение комиссии по качеству.')}</p>
            </div>
            
            <h3 style="margin-top: 30px; font-size: 14px; text-transform: uppercase; letter-spacing: 1px;">Спецификация поврежденных ТМЦ:</h3>
            {items_html}

            {photo_html}

            <div class="footer">
                <div class="signature-block">
                    <div class="sig-item"><span class="sig-label">Сдал (Представитель поставщика/перевозчика)</span></div>
                    <div class="sig-item"><span class="sig-label">Принял (Сотрудник склада WMS)</span></div>
                    <div class="sig-item"><span class="sig-label">Утвердил (Старший смены / Контролер ГК)</span></div>
                </div>
                <div class="stamp-area">
                    <div class="stamp">
                        IMPERIA WMS<br>СЕКТОР КОНТРОЛЯ<br>БРАК ПРИНЯТ<br>ПОДПИСЬ: ____
                    </div>
                    <p style="font-size: 9px; margin-top: 10px;">Для внутренних документов</p>
                </div>
            </div>

            <div style="margin-top: 40px; border-top: 1px solid #eee; padding-top: 10px; font-size: 10px; color: #999; text-align: center;">
                Электронная подпись документа: {hash(defect_id)} | Сформировано в Imperia WMS v.3.0
            </div>
        </div>
    </body>
    </html>
    """

    # Вывод HTML
    st.components.v1.html(full_html, height=1300, scrolling=True)
    
    st.divider()
    if st.button("⬅️ ВЕРНУТЬСЯ В РЕЕСТР", use_container_width=True):
        st.rerun()























