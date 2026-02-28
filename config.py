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

@st.dialog("⚙️ Редактирование данных", width="large")
def edit_order_modal(entry_id, table_key="orders"):
    from database import supabase  # Гарантируем импорт клиента Supabase
    import datetime

    # Вспомогательная функция для времени (если нет внешней)
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
                
                # Маппинг: БД (английский) -> Интерфейс (русский)
                # Добавлена проверка photo_url: если там не ссылка, ставим None
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
                    'Допуск': db_row.get('approval_by', ''),
                    'Сертификат': db_row.get('has_certificate', 'Нет'),
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
    
    # ОСТАВЛЯЕМ ТОЛЬКО 2 ВКЛАДКИ (Склад удален)
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
        drivers_list = ["Наемный водитель"]
        if 'drivers' in st.session_state and st.session_state.drivers is not None:
            d_col = "Фамилия" if "Фамилия" in st.session_state.drivers.columns else "last_name"
            if d_col in st.session_state.drivers.columns:
                drivers_list += st.session_state.drivers[d_col].dropna().tolist()
        
        current_dr = row['Водитель']
        dr_index = drivers_list.index(current_dr) if current_dr in drivers_list else 0
        selected_dr_base = r2_2.selectbox("👤 Водитель (Выбор)", drivers_list, index=dr_index, key=f"e_dr_s_{entry_id}")
        
        if selected_dr_base == "Наемный водитель":
            row['Водитель'] = r2_2.text_input("Укажите ФИО вручную", value="" if current_dr == "Наемный водитель" else current_dr, key=f"e_dr_i_{entry_id}")
        else:
            row['Водитель'] = selected_dr_base

        row['ТС'] = r2_3.text_input("🚛 ТС (Госномер)", value=row['ТС'], key=f"e_ts_{entry_id}")
        row['Адрес загрузки'] = r2_4.text_input("🏗️ Адрес загрузки", value=row['Адрес загрузки'], key=f"e_adr_z_{entry_id}")

        # РАБОТА С ФОТО (Исправлено)
        st.markdown("---")
        f_c1, f_c2 = st.columns([1, 2])
        with f_c1:
            # Проверяем, что в photo_url реально ссылка, а не текст "Прикреплено"
            if row.get('photo_url') and str(row['photo_url']).startswith('http'):
                st.image(row['photo_url'], caption="Текущее фото", width=200)
            else:
                st.info("📷 Фото отсутствует или некорректная ссылка")
        with f_c2:
            new_photo = st.file_uploader("Загрузить новое фото", type=['jpg', 'jpeg', 'png'], key=f"e_photo_{entry_id}")

        st.markdown("### 📦 Состав товаров (Редактирование таблицы)")
        updated_items = st.data_editor(items_df, width="stretch", num_rows="dynamic", key=f"ed_it_{entry_id}")
        st.session_state[f"temp_items_{entry_id}"] = updated_items

    # --- ВКЛАДКА 2: КАРТА (Геолокация) ---
    with tab_map:
        st.subheader("📍 Координаты доставки")
        col_m1, col_m2 = st.columns([2, 1])
        
        with col_m2:
            manual_coords = st.text_input("Координаты (Lat, Lon)", value=row['Координаты'], placeholder="Напр: 47.0123, 28.8642")
            row['Координаты'] = manual_coords
            st.info("Кликните на карту слева, чтобы получить точные координаты точки.")

        with col_m1:
            # Центрируем на Кишинев, если координат нет
            start_lat, start_lon = 47.01, 28.86
            if row['Координаты'] and ',' in row['Координаты']:
                try:
                    start_lat, start_lon = map(float, row['Координаты'].split(','))
                except: pass

            m = folium.Map(location=[start_lat, start_lon], zoom_start=12)
            folium.LatLngPopup().add_to(m)
            
            if row['Координаты'] and ',' in row['Координаты']:
                try:
                    folium.Marker([start_lat, start_lon], popup="Точка доставки", icon=folium.Icon(color='red')).add_to(m)
                except: pass
            
            map_data = st_folium(m, height=400, width=550, key=f"map_{entry_id}")
            
            if map_data.get("last_clicked"):
                new_lat = map_data['last_clicked']['lat']
                new_lng = map_data['last_clicked']['lng']
                new_coords_str = f"{new_lat:.6f}, {new_lng:.6f}"
                if st.button(f"📍 Использовать: {new_coords_str}"):
                    row['Координаты'] = new_coords_str
                    st.rerun()

    st.divider()
    
    # --- КНОПКИ УПРАВЛЕНИЯ ---
    save_col, cancel_col = st.columns(2)
    
    with save_col:
        if st.button("💾 СОХРАНИТЬ ИЗМЕНЕНИЯ", use_container_width=True, type="primary"):
            with st.spinner("⏳ Сохранение в базу данных..."):
                try:
                    # 1. Загрузка фото в Storage (если есть новое)
                    final_photo_url = row['photo_url']
                    if new_photo:
                        file_ext = new_photo.name.split('.')[-1]
                        file_name = f"{entry_id}_{int(time.time())}.{file_ext}"
                        supabase.storage.from_("order-photos").upload(file_name, new_photo.getvalue())
                        final_photo_url = supabase.storage.from_("orders").get_public_url(file_name)

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
                        "items_data": updated_items.replace({np.nan: None}).to_dict(orient='records'),
                        "photo_url": final_photo_url,
                        "updated_at": now_md.isoformat()
                    }

                    # 3. Апдейт в Supabase
                    supabase.table(table_key).update(db_payload).eq("id", entry_id).execute()

                    # 4. Локальное обновление DataFrame (UI)
                    if idx is not None and table_key in st.session_state:
                        # Обновляем те поля, которые отображаются в главной таблице
                        st.session_state[table_key].at[idx, 'Клиент'] = row['Клиент']
                        st.session_state[table_key].at[idx, 'Статус'] = row['Статус']
                        st.session_state[table_key].at[idx, 'Водитель'] = row['Водитель']
                        st.session_state[table_key].at[idx, 'ТС'] = row['ТС']
                        if 'photo_url' in st.session_state[table_key].columns:
                            st.session_state[table_key].at[idx, 'photo_url'] = final_photo_url

                    st.success("✅ Данные успешно обновлены!")
                    time.sleep(1)
                    st.rerun()

                except Exception as e:
                    st.error(f"🚨 Ошибка при сохранении: {e}")

    with cancel_col:
        if st.button("❌ ОТМЕНИТЬ", use_container_width=True):
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
    b1 = st.columns(2)
    
    if b1.button("❌ ЗАКРЫТЬ", use_container_width=True):
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
        # Тянем данные напрямую из таблицы arrivals
        response = supabase.table("arrivals").select("*").eq("id", arrival_id).execute()
        
        if not response.data:
            st.error(f"Документ {arrival_id} не найден в базе данных.")
            return
            
        db_row = response.data[0]
        
        # Извлекаем список товаров из JSONB колонки
        items_list = db_row.get('items_data', [])
        items_df = pd.DataFrame(items_list) if items_list else pd.DataFrame(columns=['Название товара', 'Кол-во', 'Адрес'])
        
    except Exception as e:
        st.warning(f"⚠️ Ошибка связи с БД. Показываю данные из локального кэша. {e}")
        # Фолбэк на локальный стейт, если база недоступна
        df = st.session_state.arrivals
        row_match = df[df['id'] == arrival_id]
        if row_match.empty:
            st.error("Документ не найден.")
            return
        db_row = row_match.iloc[0].to_dict()
        items_df = st.session_state.items_registry.get(arrival_id, pd.DataFrame())

    # --- 2. ОТОБРАЖЕНИЕ ДАННЫХ ---
    st.subheader(f"📥 Детальный обзор прихода: {arrival_id}")
    
    c1, c2, c3 = st.columns(3)
    with c1:
        # Используем .get() с проверкой на английские и русские ключи (для надежности)
        st.markdown(f"**🏢 Поставщик:** {db_row.get('client_name', db_row.get('Клиент', '---'))}")
        st.markdown(f"**📞 Контакт:** {db_row.get('phone', db_row.get('Телефон', '---'))}")
    with c2:
        st.markdown(f"**📦 Статус:** `{db_row.get('status', db_row.get('Статус', '---'))}`")
        st.markdown(f"**🏗️ Склад приемки:** {db_row.get('load_address', db_row.get('Адрес загрузки', '---'))}")
    with c3:
        st.markdown(f"**🚛 Транспорт:** {db_row.get('vehicle', db_row.get('ТС (Госномер)', '---'))}")
        st.markdown(f"**👤 Водитель:** {db_row.get('driver', db_row.get('Водитель', '---'))}")

    st.divider()
    
    # --- 3. ТАБЛИЦА ТОВАРОВ ---
    st.markdown("### 📋 Принятые позиции")
    if not items_df.empty:
        # Стилизация: подсвечиваем наличие адреса хранения
        def color_stock(val):
            return 'background-color: #e6ffed' if val and val != "НЕ УКАЗАНО" else ''

        if 'Адрес' in items_df.columns:
            st.dataframe(items_df.style.applymap(color_stock, subset=['Адрес']), use_container_width=True)
        else:
            st.dataframe(items_df, use_container_width=True)
            
        m1, m2, m3 = st.columns(3)
        m1.metric("Принято строк", f"{len(items_df)}")
        m2.metric("Общий объем", f"{db_row.get('total_volume', db_row.get('Общий объем (м3)', 0))} м³")
        
        # Добавляем индикатор инвентаризации
        if db_row.get('status') == "ПРИНЯТО":
             m3.success("✅ Размещено на складе")
        else:
             m3.warning("⏳ Ожидает размещения")
    else:
        st.warning("⚠️ Спецификация товаров пуста.")

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
        # Прямой запрос к таблице extras
        response = supabase.table("extras").select("*").eq("id", extra_id).execute()
        
        if not response.data:
            st.error(f"Запись {extra_id} не найдена в базе данных.")
            return
            
        db_row = response.data[0]
        
        # Извлекаем состав товаров из JSONB поля
        items_list = db_row.get('items_data', [])
        items_df = pd.DataFrame(items_list) if items_list else pd.DataFrame(columns=['Название товара', 'Кол-во', 'Адрес'])
        
    except Exception as e:
        st.warning(f"⚠️ Ошибка подключения к БД. Использую локальный кэш. {e}")
        # Фолбэк на session_state
        if "extras" not in st.session_state:
            st.error("Данные недоступны.")
            return
        df = st.session_state.extras
        row_match = df[df['id'] == extra_id]
        if row_match.empty:
            st.error("Запись не найдена.")
            return
        db_row = row_match.iloc[0].to_dict()
        items_df = st.session_state.items_registry.get(extra_id, pd.DataFrame())

    # --- 2. ОТОБРАЖЕНИЕ ДАННЫХ ---
    st.subheader(f"📑 Детальный просмотр корректировки: {extra_id}")
    st.markdown("---")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Используем .get() с поддержкой имен колонок из БД (snake_case) и UI (Кириллица)
        st.markdown(f"**👤 Кто одобрил:**\n{db_row.get('approved_by', db_row.get('Кто одобрил', '---'))}")
        st.markdown(f"**🔗 Связь с ID:**\n`{db_row.get('parent_id', db_row.get('Связь с ID', 'НЕТ'))}`")
        st.markdown(f"**📈 Статус:**\n`{db_row.get('status', db_row.get('Статус', '---'))}`")

    with col2:
        st.markdown(f"**🎯 Что именно:**\n{db_row.get('subject', db_row.get('Что именно', '---'))}")
        st.markdown(f"**📅 Дата события:**\n{db_row.get('event_date', db_row.get('Когда', '---'))}")
        st.markdown(f"**🕒 Время:**\n{db_row.get('event_time', db_row.get('Время', '---'))}")

    with col3:
        st.markdown(f"**🚚 На чем (Транспорт):**\n{db_row.get('transport', db_row.get('На чем', '---'))}")
        st.markdown(f"**📍 Где (Локация):**\n{db_row.get('location', db_row.get('Где', '---'))}")
        
        try:
            val_sum = float(db_row.get('amount', db_row.get('Сумма заявки', 0.0)))
        except:
            val_sum = 0.0
        st.markdown(f"**💰 Сумма заявки:**\n{val_sum:,.2f}")

    # Причина выделена цветом
    st.warning(f"**❓ Причина (Почему):** {db_row.get('reason', db_row.get('Почему (Причина)', 'Не указана'))}")

    st.divider()
    
    # --- 3. ТАБЛИЦА ТОВАРОВ ---
    count_pos = db_row.get('items_count', len(items_df))
    st.markdown(f"### 📦 Состав позиций (Всего: {count_pos})")
    
    if not items_df.empty:
        st.dataframe(items_df, use_container_width=True)
    else:
        st.info("Спецификация товаров пуста.")

    # Системные данные (даты из БД)
    st.caption(f"Создано в системе: {db_row.get('created_at', '---')} | Последнее обновление: {db_row.get('updated_at', '---')}")
    
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
    
    # --- 1. ФУНКЦИЯ СБОРА ТОВАРОВ (Если акт пуст) ---
    def fetch_inventory_for_defect():
        all_items = []
        if "arrivals" in st.session_state and not st.session_state.arrivals.empty:
            for _, row_arr in st.session_state.arrivals.iterrows():
                raw_data = row_arr.get('items_data', [])
                if isinstance(raw_data, str):
                    try: raw_data = ast.literal_eval(raw_data)
                    except: raw_data = []
                if isinstance(raw_data, list):
                    all_items.extend(raw_data)
        
        if not all_items:
            return pd.DataFrame(columns=['Товар', 'Кол-во', 'Описание'])
            
        df_res = pd.DataFrame(all_items)
        # Маппинг колонок под единый стандарт
        rename_map = {'item': 'Товар', 'Наименование': 'Товар', 'Название': 'Товар'}
        df_res = df_res.rename(columns={k: v for k, v in rename_map.items() if k in df_res.columns})
        
        if 'Товар' in df_res.columns:
            df_res['Кол-во'] = pd.to_numeric(df_res.get('Кол-во', 0), errors='coerce').fillna(0)
            summary = df_res.groupby('Товар', as_index=False)['Кол-во'].sum()
            summary['Описание'] = "" # Стандартный ключ
            return summary
        return pd.DataFrame(columns=['Товар', 'Кол-во', 'Описание'])

    # --- 2. ИНИЦИАЛИЗАЦИЯ ДАННЫХ ИЗ БД ---
    if f"temp_row_{entry_id}" not in st.session_state:
        res = supabase.table("defects").select("*").eq("id", entry_id).execute()
        if res.data:
            db_row = res.data[0]
            st.session_state[f"temp_row_{entry_id}"] = {
                'Товар': db_row.get('main_item', ''),
                'Связь с документом': db_row.get('related_doc_id', ''),
                'Тип дефекта': db_row.get('defect_type', 'Бой'),
                'Виновник': db_row.get('culprit', 'Не установлен'),
                'Статус': db_row.get('status', 'ОБНАРУЖЕНО'),
                'Решение': db_row.get('decision', ''),
                'Адрес хранения': db_row.get('quarantine_address', 'ZONE-BRAK'),
                'Фото': db_row.get('photo_url', '')
            }
            
            items_in_act = db_row.get('items_data', [])
            if isinstance(items_in_act, str):
                try: items_in_act = ast.literal_eval(items_in_act)
                except: items_in_act = []
            
            if isinstance(items_in_act, list) and len(items_in_act) > 0:
                df_init = pd.DataFrame(items_in_act)
                # Исправляем старые ключи "Описание дефекта" -> "Описание"
                if 'Описание дефекта' in df_init.columns:
                    df_init = df_init.rename(columns={'Описание дефекта': 'Описание'})
                st.session_state[f"temp_items_{entry_id}"] = df_init
            else:
                st.session_state[f"temp_items_{entry_id}"] = fetch_inventory_for_defect()

    row = st.session_state[f"temp_row_{entry_id}"]
    items_df = st.session_state[f"temp_items_{entry_id}"]

    st.subheader(f"📝 Редактирование Акта №{entry_id}")

    # --- 3. ИНТЕРФЕЙС ---
    c1, c2, c3 = st.columns(3)
    row['Товар'] = c1.text_input("Товар (Заголовок)", value=row['Товар'])
    row['Связь с документом'] = c2.text_input("ID Документа", value=row['Связь с документом'])
    row['Адрес хранения'] = c3.text_input("Зона брака", value=row['Адрес хранения'])

    r2_1, r2_2, r2_3 = st.columns(3)
    defect_opts = ["Бой", "Порча", "Брак производителя", "Некомплект"]
    row['Тип дефекта'] = r2_1.selectbox("Тип", defect_opts, index=defect_opts.index(row['Тип дефекта']) if row['Тип дефекта'] in defect_opts else 0)
    
    culprit_opts = ["Склад", "Перевозчик", "Поставщик", "Не установлен"]
    row['Виновник'] = r2_2.selectbox("Кто виноват", culprit_opts, index=culprit_opts.index(row['Виновник']) if row['Виновник'] in culprit_opts else 0)
    
    status_opts = ["ОБНАРУЖЕНО", "В ЭКСПЕРТИЗЕ", "ПОДТВЕРЖДЕНО", "СПИСАНО"]
    row['Статус'] = r2_3.selectbox("Статус", status_opts, index=status_opts.index(row['Статус']) if row['Статус'] in status_opts else 0)

    row['Решение'] = st.text_area("Заключение комиссии", value=row['Решение'])

    # БЛОК ФОТО
    st.divider()
    st.write("📸 **Фотофиксация**")
    if row['Фото']:
        st.image(row['Фото'], width=150, caption="Текущее фото")
    
    uploaded_file = st.file_uploader("Заменить или загрузить фото", type=['png', 'jpg', 'jpeg'])
    if uploaded_file:
        with st.spinner("Загрузка на сервер..."):
            new_url = upload_image(uploaded_file)
            if new_url:
                row['Фото'] = new_url
                st.success("Фото обновлено!")
                st.image(new_url, width=150)

    # СПЕЦИФИКАЦИЯ
    st.divider()
    st.write(f"📦 **Спецификация позиций ({len(items_df)}):**")
    
    updated_items = st.data_editor(
        items_df,
        use_container_width=True,
        num_rows="dynamic",
        key=f"editor_{entry_id}",
        column_config={
            "Товар": st.column_config.TextColumn("Наименование", width="large"),
            "Кол-во": st.column_config.NumberColumn("Кол-во брака", min_value=0),
            "Описание": st.column_config.TextColumn("Детали повреждения")
        }
    )

    # --- 4. СОХРАНЕНИЕ ---
    if st.button("🚨 СОХРАНИТЬ ИЗМЕНЕНИЯ", use_container_width=True, type="primary"):
        # Оставляем только те строки, где есть брак
        final_items = updated_items[updated_items['Кол-во'] > 0].copy()
        
        db_payload = {
            "main_item": row['Товар'],
            "total_defective": int(final_items['Кол-во'].sum()) if not final_items.empty else 0,
            "related_doc_id": row['Связь с документом'],
            "defect_type": row['Тип дефекта'],
            "culprit": row['Виновник'],
            "status": row['Статус'],
            "decision": row['Решение'],
            "photo_url": row['Фото'],
            "quarantine_address": row['Адрес хранения'],
            "items_data": final_items.replace({np.nan: None}).to_dict(orient='records'),
            "updated_at": datetime.now().isoformat()
        }

        try:
            supabase.table("defects").update(db_payload).eq("id", entry_id).execute()
            st.success("✅ Данные в базе обновлены!")
            time.sleep(1.5)
            st.rerun()
        except Exception as e:
            st.error(f"🚨 Ошибка Supabase: {e}")
        
@st.dialog("🔍 Просмотр Акта брака", width="large")
def show_defect_details_modal(defect_id):
    from database import supabase
    import pandas as pd
    import streamlit as st

    # --- 1. ЗАГРУЗКА ДАННЫХ НАПРЯМУЮ ИЗ БД ---
    try:
        response = supabase.table("defects").select("*").eq("id", defect_id).execute()
        
        if not response.data:
            st.error(f"Акт №{defect_id} не найден в базе данных.")
            return
            
        db_row = response.data[0]
        
        # Безопасная загрузка спецификации
        items_list = db_row.get('items_data', [])
        items_df = pd.DataFrame(items_list) if items_list else pd.DataFrame()

        # Принудительная унификация названий колонок для отображения
        if not items_df.empty:
            # Если в базе ключ "Описание", меняем его на "Описание дефекта" для красоты в UI
            if 'Описание' in items_df.columns:
                items_df = items_df.rename(columns={'Описание': 'Описание дефекта'})
            elif 'item' in items_df.columns:
                items_df = items_df.rename(columns={'item': 'Товар'})
    
    except Exception as e:
        st.error(f"Ошибка при получении данных: {e}")
        return

    # --- 2. ЗАГОЛОВОК И СТАТУСНЫЕ МЕТРИКИ ---
    st.subheader(f"📑 Акт дефектовки №{defect_id}")
    
    m1, m2, m3 = st.columns(3)
    # Используем .get() с дефолтными значениями, чтобы избежать ошибок
    m1.metric("Статус", db_row.get('status', 'Н/Д'))
    m2.metric("Виновник", db_row.get('culprit', 'Н/Д'))
    m3.metric("Тип дефекта", db_row.get('defect_type', 'Н/Д'))

    st.markdown("---")
    
    # --- 3. ДЕТАЛЬНАЯ КАРТОЧКА ---
    col_left, col_right = st.columns(2)
    
    with col_left:
        st.markdown(f"**📦 Основной товар:**\n{db_row.get('main_item', '---')}")
        st.markdown(f"**🔢 Кол-во брака (ед.):** `{db_row.get('total_defective', 0)}`")
        st.markdown(f"**🔗 Документ-основание:** `{db_row.get('related_doc_id', 'Не указан')}`")
    
    with col_right:
        st.markdown(f"**📍 Зона хранения:** `{db_row.get('quarantine_address', 'Зона Карантин')}`")
        raw_date = db_row.get('updated_at', '---')
        clean_date = raw_date[:16].replace('T', ' ') if 'T' in str(raw_date) else raw_date
        st.markdown(f"**📅 Последнее обновление:** {clean_date}")
        
    st.info(f"**⚖️ Принятое решение:**\n\n{db_row.get('decision', 'На стадии рассмотрения')}")

    # --- 4. СПЕЦИФИКАЦИЯ ТОВАРОВ (ТАБЛИЦА) ---
    st.divider()
    st.markdown("#### 📦 Спецификация поврежденных позиций")
    
    if not items_df.empty:
        st.dataframe(
            items_df, 
            use_container_width=True,
            column_config={
                "Кол-во": st.column_config.NumberColumn("Кол-во", format="%d ед."),
                "Товар": "Наименование",
                "Описание дефекта": "Детали повреждения"
            }
        )
        
        f1, f2 = st.columns(2)
        f1.caption(f"Всего позиций: {len(items_df)}")
        if 'Кол-во' in items_df.columns:
            total_q = pd.to_numeric(items_df['Кол-во'], errors='coerce').sum()
            f2.caption(f"Общее кол-во единиц: {int(total_q)}")
    else:
        st.warning("⚠️ Детальная спецификация товаров не заполнена.")

    # --- 5. ФОТОФИКСАЦИЯ ---
    photo_url = db_row.get('photo_url')
    if photo_url:
        st.divider()
        st.markdown("#### 📷 Фотофиксация повреждений")
        st.image(photo_url, use_container_width=True, caption=f"Фото к акту №{defect_id}")
    else:
        st.divider()
        st.caption("📷 Фотоматериалы не загружены.")

    # Кнопка закрытия
    st.write("") # Отступ
    if st.button("❌ ЗАКРЫТЬ ПРОСМОТР", use_container_width=True, type="secondary"):
        st.rerun()
        
@st.dialog("🖨️ Печать Акта о браке", width="large")
def show_defect_print_modal(defect_id):
    from database import supabase
    import pandas as pd
    import streamlit as st

    # --- 1. ЗАГРУЗКА ДАННЫХ ---
    try:
        response = supabase.table("defects").select("*").eq("id", defect_id).execute()
        if not response.data:
            st.error("Ошибка: Акт не найден в базе данных")
            return
            
        row = response.data[0]
        items_list = row.get('items_data', [])
        
        # Превращаем в DataFrame и проверяем ключи (унификация)
        if items_list:
            items_df = pd.DataFrame(items_list)
            # Если в базе старый ключ, переименовываем для печати
            if 'Описание дефекта' in items_df.columns:
                items_df = items_df.rename(columns={'Описание дефекта': 'Описание'})
        else:
            items_df = pd.DataFrame()
            
    except Exception as e:
        st.error(f"Ошибка связи с БД: {e}")
        return

    # --- 2. ПОДГОТОВКА ТАБЛИЦЫ ---
    if not items_df.empty:
        # Берем только нужные колонки для печати
        cols = [c for c in ['Товар', 'Кол-во', 'Описание'] if c in items_df.columns]
        items_html = items_df[cols].to_html(index=False, border=1, classes='data-table')
    else:
        items_html = "<p style='text-align:center; padding: 20px;'>Спецификация товаров пуста</p>"

    # Подготовка фото
    photo_html = ""
    if row.get('photo_url'):
        photo_html = f"""
        <div style="margin-top: 20px; text-align: center;">
            <h3 style="font-size: 14px;">ФОТОФИКСАЦИЯ ПОВРЕЖДЕНИЙ:</h3>
            <img src="{row['photo_url']}" style="max-width: 100%; max-height: 400px; border: 1px solid #ccc; border-radius: 8px;">
        </div>
        """

    # --- 3. ГЕНЕРАЦИЯ HTML + JS ---
    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; padding: 10px; color: #333; }}
            .act-border {{ border: 2px solid #d32f2f; padding: 25px; background: #fff; }}
            .header {{ text-align: center; border-bottom: 2px solid #d32f2f; margin-bottom: 20px; padding-bottom: 10px; }}
            .header h1 {{ color: #d32f2f; margin: 0; font-size: 22px; text-transform: uppercase; }}
            
            .info-table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 13px; }}
            .info-table td {{ padding: 8px; border-bottom: 1px solid #eee; }}
            
            .data-table {{ width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 12px; }}
            .data-table th {{ background: #f4f4f4; padding: 10px; border: 1px solid #333; text-align: left; }}
            .data-table td {{ padding: 8px; border: 1px solid #333; }}
            
            .decision-box {{ background: #fff4f4; border: 1px solid #d32f2f; padding: 12px; margin-top: 15px; font-style: italic; font-size: 13px; }}
            
            .footer {{ margin-top: 40px; display: flex; justify-content: space-between; }}
            .signature-line {{ border-top: 1px solid #000; width: 200px; text-align: center; font-size: 10px; margin-top: 35px; }}
            
            .stamp {{ border: 3px double #0000FF; color: #0000FF; width: 120px; height: 120px; 
                        text-align: center; border-radius: 50%; opacity: 0.6; font-size: 10px; 
                        display: flex; align-items: center; justify-content: center;
                        transform: rotate(-15deg); font-weight: bold; }}
            
            @media print {{ 
                .no-print {{ display: none !important; }} 
                body {{ padding: 0; }}
                .act-border {{ border: 1px solid #000; }}
            }}
            
            .print-btn {{
                width: 100%; padding: 15px; background: #d32f2f; color: white; 
                border: none; cursor: pointer; font-weight: bold; border-radius: 4px; 
                margin-bottom: 20px; font-size: 16px;
            }}
        </style>
        
        <script>
            function doPrint() {{
                window.focus();
                window.print();
            }}
        </script>
    </head>
    <body>
        <button class="no-print print-btn" onclick="doPrint()">
            🖨️ ПЕЧАТАТЬ АКТ БРАКА / СОХРАНИТЬ В PDF
        </button>
        
        <div class="act-border">
            <div class="header">
                <h1>АКТ ДЕФЕКТОВКИ №{defect_id}</h1>
                <p style="font-size: 10px;">IMPERIA WMS | ОТДЕЛ КОНТРОЛЯ КАЧЕСТВА</p>
            </div>
            
            <table class="info-table">
                <tr>
                    <td><b>Дата:</b> {str(row.get('updated_at', '---'))[:10]}</td>
                    <td><b>Статус:</b> <span style="color:#d32f2f;">{row.get('status', '---')}</span></td>
                </tr>
                <tr>
                    <td><b>Виновник:</b> {row.get('culprit', '---')}</td>
                    <td><b>Тип дефекта:</b> {row.get('defect_type', '---')}</td>
                </tr>
                <tr>
                    <td><b>Основной товар:</b> {row.get('main_item', '---')}</td>
                    <td><b>Локация:</b> {row.get('quarantine_address', '---')}</td>
                </tr>
                <tr>
                    <td colspan="2"><b>Основание:</b> {row.get('related_doc_id', '---')}</td>
                </tr>
            </table>
            
            <div class="decision-box">
                <b>РЕШЕНИЕ:</b> {row.get('decision', 'На рассмотрении.')}
            </div>
            
            <h3 style="margin-top: 20px; font-size: 14px; border-left: 4px solid #d32f2f; padding-left: 8px;">СПЕЦИФИКАЦИЯ:</h3>
            {items_html}

            {photo_html}

            <div class="footer">
                <div class="signatures">
                    <div class="signature-line">Сдал (Перевозчик/Поставщик)</div>
                    <div class="signature-line">Принял (Склад)</div>
                    <div class="signature-line">Утвердил (QC)</div>
                </div>
                <div class="stamp">IMPERIA WMS<br>КОНТРОЛЬ<br>ПРОЙДЕН</div>
            </div>
        </div>
    </body>
    </html>
    """

    # Важно: height должен быть достаточным, чтобы не появлялось двойной прокрутки
    st.components.v1.html(full_html, height=1000, scrolling=True)
    
    if st.button("❌ ЗАКРЫТЬ", use_container_width=True):
        st.rerun()












