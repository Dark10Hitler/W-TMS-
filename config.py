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
        
@st.dialog("⚙️ Редактирование данных", width="large")
def edit_order_modal(entry_id, table_key="orders"):
    # --- 1. ИНИЦИАЛИЗАЦИЯ (ПРЯМАЯ ЗАГРУЗКА ИЗ БД КАК В ПРОСМОТРЕ) ---
    if f"temp_row_{entry_id}" not in st.session_state:
        with st.spinner("📥 Получение данных из базы..."):
            try:
                # Тянем данные из БД, чтобы товары (items_data) точно подтянулись
                response = supabase.table(table_key).select("*").eq("id", entry_id).execute()
                
                if not response.data:
                    st.error(f"Запись {entry_id} не найдена в Supabase")
                    return
                
                db_row = response.data[0]
                
                # Мапим данные из БД на русские ключи, которые используются в твоем интерфейсе
                # Это гарантирует, что row['Клиент'] и прочие не будут пустыми
                st.session_state[f"temp_row_{entry_id}"] = {
                    'id': db_row.get('id'),
                    'Клиент': db_row.get('client_name', db_row.get('Клиент', '')),
                    'Телефон': db_row.get('phone', db_row.get('Телефон', '')),
                    'Адрес клиента': db_row.get('delivery_address', db_row.get('Адрес клиента', '')),
                    'Статус': db_row.get('status', db_row.get('Статус', 'ОЖИДАНИЕ')),
                    'Водитель': db_row.get('driver', db_row.get('Водитель', '')),
                    'ТС': db_row.get('vehicle', db_row.get('ТС', '')),
                    'Адрес загрузки': db_row.get('load_address', db_row.get('Адрес загрузки', '')),
                    'Сумма заявки': db_row.get('total_sum', db_row.get('Сумма заявки', 0.0)),
                    'Общий объем (м3)': db_row.get('total_volume', db_row.get('Общий объем (м3)', 0.0)),
                    'Допуск': db_row.get('approval_by', db_row.get('Допуск', '')),
                    'Сертификат': db_row.get('has_certificate', db_row.get('Сертификат', 'Нет')),
                    'Описание': db_row.get('description', db_row.get('Описание', ''))
                }

                # Загружаем товары из JSON-поля items_data (самая важная часть!)
                items_raw = db_row.get('items_data', [])
                if isinstance(items_raw, list) and len(items_raw) > 0:
                    items_df = pd.DataFrame(items_raw)
                else:
                    items_df = pd.DataFrame(columns=['Название товара', 'Кол-во', 'Адрес'])
                
                if 'Адрес' not in items_df.columns:
                    items_df['Адрес'] = "НЕ УКАЗАНО"
                
                st.session_state[f"temp_items_{entry_id}"] = items_df

                # Сохраняем индекс для локального обновления
                if table_key in st.session_state:
                    df_local = st.session_state[table_key]
                    idx_l = df_local.index[df_local['id'] == entry_id].tolist()
                    st.session_state[f"temp_idx_{entry_id}"] = idx_l[0] if idx_l else None

            except Exception as e:
                st.error(f"Ошибка при инициализации: {e}")
                return

    # Ссылки на текущие данные в сессии
    row = st.session_state[f"temp_row_{entry_id}"]
    items_df = st.session_state[f"temp_items_{entry_id}"]
    idx = st.session_state.get(f"temp_idx_{entry_id}")

    st.markdown(f"### 🖋️ Редактор документа `{entry_id}`")
    tab_main, tab_geo = st.tabs(["📝 Информация и Поля", "📍 Склад (3D)"])

    # --- ВКЛАДКА 1: ОСНОВНЫЕ ДАННЫЕ ---
    with tab_main:
        st.markdown("##### 👤 Клиент и Контакты")
        c1, c2, c3 = st.columns(3)
        row['Клиент'] = c1.text_input("Клиент", value=str(row.get('Клиент', '')), key=f"edit_cli_{entry_id}")
        row['Телефон'] = c2.text_input("Телефон", value=str(row.get('Телефон', '')), key=f"edit_ph_{entry_id}")
        row['Адрес клиента'] = c3.text_input("Адрес доставки", value=str(row.get('Адрес клиента', '')), key=f"edit_adr_c_{entry_id}")

        st.markdown("##### 🚚 Логистика и Транспорт")
        r2_1, r2_2, r2_3, r2_4 = st.columns(4)
        status_list = ["ОЖИДАНИЕ", "Стоит на точке загрузки", "Выехал", "Ожидает догруз", "В пути", "Доставлено", "БРАК"]
        curr_st = str(row.get('Статус', 'ОЖИДАНИЕ'))
        st_idx = status_list.index(curr_st) if curr_st in status_list else 0
        row['Статус'] = r2_1.selectbox("Статус", status_list, index=st_idx, key=f"edit_st_{entry_id}")
        row['Водитель'] = r2_2.text_input("Водитель", value=str(row.get('Водитель', '')), key=f"edit_dr_{entry_id}")
        row['ТС'] = r2_3.text_input("ТС (Госномер)", value=str(row.get('ТС', '')), key=f"edit_ts_{entry_id}")
        row['Адрес загрузки'] = r2_4.text_input("Адрес загрузки", value=str(row.get('Адрес загрузки', 'Центральный склад')), key=f"edit_adr_z_{entry_id}")

        st.markdown("##### ⚖️ Параметры и Допуски")
        r3_1, r3_2, r3_3, r3_4 = st.columns(4)
        row['Сумма заявки'] = r3_1.number_input("Сумма заявки", value=float(row.get('Сумма заявки', 0.0)), key=f"edit_sum_{entry_id}")
        row['Общий объем (м3)'] = r3_2.number_input("Общий объем (м3)", value=float(row.get('Общий объем (м3)', 0.0)), key=f"edit_vol_{entry_id}")
        row['Допуск'] = r3_3.text_input("Допуск (Кто разрешил)", value=str(row.get('Допуск', '')), key=f"edit_dop_{entry_id}")
        cert_val = str(row.get('Сертификат', 'Нет'))
        row['Сертификат'] = r3_4.selectbox("Сертификат", ["Да", "Нет"], index=0 if cert_val == "Да" else 1, key=f"edit_cert_{entry_id}")

        st.divider()
        st.markdown("### 📦 Состав товаров")
        # Редактор таблицы товаров (используем width="stretch" для совместимости)
        updated_items = st.data_editor(items_df, width="stretch", num_rows="dynamic", key=f"ed_it_{entry_id}")
        st.session_state[f"temp_items_{entry_id}"] = updated_items

        if st.button("💾 СОХРАНИТЬ ВСЕ ИЗМЕНЕНИЯ", width="stretch", type="primary"):
            # 1. ТВОЙ PAYLOAD БЕЗ СОКРАЩЕНИЙ
            db_payload = {
                "client_name": row['Клиент'],
                "phone": row['Телефон'],
                "delivery_address": row['Адрес клиента'],
                "status": row['Статус'],
                "driver": row['Водитель'],
                "vehicle": row['ТС'],
                "load_address": row['Адрес загрузки'],
                "total_sum": float(row['Сумма заявки']),
                "total_volume": float(row['Общий объем (м3)']),
                "approval_by": row['Допуск'],
                "has_certificate": row['Сертификат'],
                "description": row.get('Описание', ''),
                "items_data": updated_items.replace({np.nan: None}).to_dict(orient='records'),
                "updated_at": datetime.now().isoformat()
            }

            try:
                # 2. СОХРАНЕНИЕ В ОБЛАКО
                supabase.table(table_key).update(db_payload).eq("id", entry_id).execute()

                # 3. СИНХРОНИЗАЦИЯ С ТАБЛИЦЕЙ INVENTORY
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
                if idx is not None:
                    target_df = st.session_state[table_key]
                    for field, val in row.items():
                        if field in target_df.columns:
                            target_df.at[idx, field] = val
                    # Принудительно обновляем товары в локальном кэше
                    if "items_data" in target_df.columns:
                        target_df.at[idx, "items_data"] = db_payload["items_data"]

                st.success("✅ Все данные синхронизированы с базой данных!")
                time.sleep(1)
                st.rerun()

            except Exception as e:
                st.error(f"🚨 Ошибка сохранения в Supabase: {e}")

            except Exception as e:
                st.error(f"🚨 Ошибка сохранения в Supabase: {e}")

    # --- ВКЛАДКА 2: СКЛАД (ПРИВЯЗКА ЯЧЕЕК) ---
    with tab_geo:
        if updated_items.empty:
            st.warning("Сначала добавьте товары!")
        else:
            col_sel, col_viz = st.columns([1, 2])
            with col_sel:
                st.subheader("Выбор ячейки")
                target_item = st.selectbox("📦 Товар:", updated_items['Название товара'].unique(), key=f"t_sel_{entry_id}")
                wh_id = str(st.selectbox("🏪 Склад:", list(WAREHOUSE_MAP.keys()), key=f"wh_sel_{entry_id}"))
                
                # Генератор ячеек
                conf = WAREHOUSE_MAP[wh_id]
                all_cells = []
                for r in conf['rows']:
                    all_cells.append(f"WH{wh_id}-{r}")
                    for s in range(1, conf.get('sections', 1) + 1):
                        for t in conf.get('tiers', ['A']):
                            all_cells.append(f"WH{wh_id}-{r}-S{s}-{t}")
                all_cells = sorted(list(set(all_cells)))
                
                match_cond = updated_items['Название товара'] == target_item
                curr_addr = updated_items.loc[match_cond, 'Адрес'].values[0] if not updated_items.loc[match_cond, 'Адрес'].empty else "НЕ УКАЗАНО"
                
                selected_cell = st.selectbox("📍 Ячейка:", options=all_cells, 
                                             index=all_cells.index(curr_addr) if curr_addr in all_cells else 0, 
                                             key=f"cs_sel_{entry_id}")
                
                if st.button("🔗 ПРИМЕНИТЬ АДРЕС", use_container_width=True, type="secondary", key=f"bind_{entry_id}"):
                    # Обновляем только в локальном буфере редактора
                    st.session_state[f"temp_items_{entry_id}"].loc[
                        st.session_state[f"temp_items_{entry_id}"]['Название товара'] == target_item, 'Адрес'
                    ] = selected_cell
                    st.toast(f"Адрес {selected_cell} зафиксирован в черновике. Нажмите 'Сохранить изменения' для записи в БД.")

            with col_viz:
                st.subheader("Карта склада")
                fig = get_warehouse_figure(wh_id, highlighted_cell=selected_cell)
                st.plotly_chart(fig, use_container_width=True, key=f"p_viz_{entry_id}")

@st.dialog("🔍 Детальный просмотр заявки", width="large")
def show_order_details_modal(order_id):
    from database import supabase
    
    # --- 1. ПРЯМАЯ ИНТЕГРАЦИЯ С БД (Загрузка актуальной версии) ---
    try:
        # Определяем таблицу (если ID начинается на ORD — это заказы, если на IN — приходы)
        table_name = "orders" if order_id.startswith("ORD") else "arrivals"
        
        response = supabase.table(table_name).select("*").eq("id", order_id).execute()
        
        if not response.data:
            st.error(f"Документ {order_id} не найден в базе данных Supabase.")
            return
            
        # Получаем данные напрямую из БД
        db_row = response.data[0]
        
        # Парсим товары из JSONB поля базы данных
        items_list = db_row.get('items_data', [])
        items_df = pd.DataFrame(items_list) if items_list else pd.DataFrame(columns=['Название товара', 'Кол-во', 'Адрес'])
        
    except Exception as e:
        st.warning(f"⚠️ Ошибка прямого подключения к БД. Использую локальный кэш. Ошибка: {e}")
        # Фолбэк на локальный кэш, если база недоступна
        df_main = st.session_state.get('main', pd.DataFrame())
        row_match = df_main[df_main['id'] == order_id]
        if row_match.empty:
            st.error("Запись не найдена.")
            return
        db_row = row_match.iloc[0].to_dict()
        items_df = st.session_state.items_registry.get(order_id, pd.DataFrame())

    # --- 2. ОТОБРАЖЕНИЕ ДАННЫХ ---
    st.subheader(f"📄 Просмотр документа: {order_id}")
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"**👤 Клиент:** {db_row.get('client_name', db_row.get('Клиент', '---'))}")
        st.markdown(f"**📞 Телефон:** {db_row.get('phone', db_row.get('Телефон', '---'))}")
        st.markdown(f"**📍 Адрес:** {db_row.get('delivery_address', db_row.get('Адрес клиента', '---'))}")
    with c2:
        st.markdown(f"**📦 Статус:** `{db_row.get('status', db_row.get('Статус', '---'))}`")
        st.markdown(f"**📜 Сертификат:** {db_row.get('has_certificate', db_row.get('Сертификат', '---'))}")
        st.markdown(f"**🏗️ Адрес загрузки:** {db_row.get('load_address', db_row.get('Адрес загрузки', '---'))}")
    with c3:
        # Учитываем возможные разные названия ключей в БД и в UI
        v_num = db_row.get('vehicle', db_row.get('ТС', '---'))
        st.markdown(f"**🚛 ТС:** {v_num}")
        st.markdown(f"**👤 Водитель:** {db_row.get('driver', db_row.get('Водитель', '---'))}")
        
        with st.expander("🕒 История правок"):
            st.caption(f"Создан: {db_row.get('created_at', '---')}")
            st.caption(f"Изменил: {db_row.get('updated_by', '---')} ({db_row.get('updated_at', '---')})")

    st.divider()

    st.markdown("### 📋 Товарная спецификация и места хранения")
    
    if not items_df.empty:
        # Красивое оформление таблицы: подсвечиваем адреса
        def color_addr(val):
            color = 'lightgreen' if val and val != "НЕ УКАЗАНО" and val != "-" else '#ffcccc'
            return f'background-color: {color}'

        # Отрисовка спецификации
        if 'Адрес' in items_df.columns:
            st.dataframe(items_df.style.applymap(color_addr, subset=['Адрес']), use_container_width=True)
        else:
            st.dataframe(items_df, use_container_width=True)
        
        # Метрики
        m1, m2, m3 = st.columns(3)
        m1.metric("Всего позиций", f"{len(items_df)}")
        m2.metric("Общий объем", f"{db_row.get('total_volume', db_row.get('Общий объем (м3)', 0))} м³")
        m3.metric("Сумма", f"{db_row.get('total_sum', db_row.get('Сумма заявки', 0))} ₽")
    else:
        st.warning("⚠️ Спецификация товаров пуста или не найдена.")

    st.info(f"**📝 Сведения/Допуск:** {db_row.get('description', db_row.get('Описание', 'Нет описания'))}")

    # --- 3. ЗАКРЫТИЕ ---
    if st.button("❌ ЗАКРЫТЬ", use_container_width=True):
        st.session_state.active_view_modal = None
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
        
    
@st.dialog("🚨 Актирование и Редактирование брака", width="large")
def edit_defect_modal(entry_id):
    from database import supabase
    import numpy as np
    import pandas as pd
    from datetime import datetime
    import time
    
    table_key = "defects"
    bucket_name = "defects" # Имя вашего бакета в Supabase Storage

    # --- 1. ИНИЦИАЛИЗАЦИЯ (Загрузка данных из БД) ---
    if f"temp_row_{entry_id}" not in st.session_state:
        try:
            response = supabase.table(table_key).select("*").eq("id", entry_id).execute()
            if not response.data:
                st.error("Запись не найдена")
                return
            
            db_row = response.data[0]
            
            # Мапим данные для интерфейса (из английских колонок в русские ключи)
            st.session_state[f"temp_row_{entry_id}"] = {
                'Товар': db_row.get('main_item', ''),
                'Кол-во брака': db_row.get('total_defective', 0),
                'Связь с документом': db_row.get('related_doc_id', ''),
                'Тип дефекта': db_row.get('defect_type', 'Бой'),
                'Виновник': db_row.get('culprit', 'Не установлен'),
                'Статус': db_row.get('status', 'ОБНАРУЖЕНО'),
                'Решение': db_row.get('decision', ''),
                'Адрес хранения': db_row.get('quarantine_address', 'Z-BRAK-01'),
                'Фото': db_row.get('photo_url', '')
            }
            
            # Загружаем товары из колонки items_data
            items_raw = db_row.get('items_data', [])
            if isinstance(items_raw, list) and len(items_raw) > 0:
                st.session_state[f"temp_items_{entry_id}"] = pd.DataFrame(items_raw)
            else:
                st.session_state[f"temp_items_{entry_id}"] = pd.DataFrame(columns=['Товар', 'Кол-во', 'Описание дефекта'])
            
            # Индекс для локального обновления таблицы
            if table_key in st.session_state:
                df_local = st.session_state[table_key]
                idx_l = df_local.index[df_local['id'] == entry_id].tolist()
                st.session_state[f"temp_idx_{entry_id}"] = idx_l[0] if idx_l else None
                
        except Exception as e:
            st.error(f"Ошибка загрузки: {e}")
            return

    row = st.session_state[f"temp_row_{entry_id}"]
    items_df = st.session_state[f"temp_items_{entry_id}"]
    idx = st.session_state.get(f"temp_idx_{entry_id}")

    st.error(f"### 🚨 Редактирование Акта №{entry_id}")
    tab_main, tab_photo, tab_geo = st.tabs(["📝 Основные данные", "📸 Фотофиксация", "📍 Склад"])

    # --- ВКЛАДКА 1: ОСНОВНЫЕ ДАННЫЕ ---
    with tab_main:
        c1, c2, c3 = st.columns(3)
        row['Товар'] = c1.text_input("Основной товар", value=row['Товар'], key=f"d_f1_{entry_id}")
        row['Кол-во брака'] = c2.number_input("Кол-во (общ)", value=int(row['Кол-во брака']), key=f"d_f2_{entry_id}")
        row['Связь с документом'] = c3.text_input("Связь с ID", value=row['Связь с документом'], key=f"d_f3_{entry_id}")

        r2_1, r2_2, r2_3 = st.columns(3)
        defect_types = ["Бой", "Порча упаковки", "Некомплект", "Производственный брак"]
        culprit_types = ["Перевозчик", "Склад", "Поставщик", "Не установлен"]
        status_types = ["ОБНАРУЖЕНО", "В ЭКСПЕРТИЗЕ", "ПОДТВЕРЖДЕНО", "СПИСАНО"]

        row['Тип дефекта'] = r2_1.selectbox("Тип дефекта", defect_types, index=defect_types.index(row['Тип дефекта']) if row['Тип дефекта'] in defect_types else 0, key=f"d_f4_{entry_id}")
        row['Виновник'] = r2_2.selectbox("Виновник", culprit_types, index=culprit_types.index(row['Виновник']) if row['Виновник'] in culprit_types else 0, key=f"d_f5_{entry_id}")
        row['Статус'] = r2_3.selectbox("Статус", status_types, index=status_types.index(row['Статус']) if row['Статус'] in status_types else 0, key=f"d_f6_{entry_id}")
        row['Решение'] = st.text_area("Принятое решение", value=row['Решение'], height=70, key=f"d_f7_{entry_id}")

        st.divider()
        st.markdown("##### 📦 Спецификация поврежденных позиций")
        updated_items = st.data_editor(items_df, width="stretch", num_rows="dynamic", key=f"d_ed_{entry_id}")
        st.session_state[f"temp_items_{entry_id}"] = updated_items

    # --- ВКЛАДКА 2: ФОТОФИКСАЦИЯ ---
    with tab_photo:
        st.markdown("##### 📷 Доказательства повреждений")
        if row.get('Фото'):
            # Отображаем текущее фото, если это URL
            st.image(row['Фото'], caption="Текущее фото", width=400)
        
        new_photo = st.file_uploader("Загрузить новое фото брака", type=['jpg', 'png', 'jpeg'], key=f"d_up_{entry_id}")
        
        if new_photo:
            if st.button("📤 ЗАГРУЗИТЬ ФОТО В ОБЛАКО", key=f"btn_up_{entry_id}"):
                try:
                    file_path = f"defect_{entry_id}_{int(time.time())}.jpg"
                    # Загрузка файла в Storage
                    supabase.storage.from_(bucket_name).upload(file_path, new_photo.getvalue())
                    # Получение публичной ссылки
                    public_url = supabase.storage.from_(bucket_name).get_public_url(file_path)
                    row['Фото'] = public_url
                    st.success("Фото успешно загружено!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Ошибка загрузки фото: {e}")

    # --- ВКЛАДКА 3: СКЛАД (КАРАНТИН) ---
    with tab_geo:
        row['Адрес хранения'] = st.text_input("Ячейка брака (Зона Карантин)", value=row['Адрес хранения'], key=f"d_adr_{entry_id}")
        from config import render_warehouse_logic
        render_warehouse_logic(entry_id, updated_items)

    st.divider()

    # --- ФИНАЛЬНОЕ СОХРАНЕНИЕ ---
    if st.button("🚨 СОХРАНИТЬ ИЗМЕНЕНИЯ В АКТЕ", width="stretch", type="primary"):
        # ТВОЙ PAYLOAD БЕЗ СОКРАЩЕНИЙ
        db_payload = {
            "main_item": row['Товар'],
            "total_defective": int(row['Кол-во брака']),
            "related_doc_id": row['Связь с документом'],
            "defect_type": row['Тип дефекта'],
            "culprit": row['Виновник'],
            "status": row['Статус'],
            "decision": row['Решение'],
            "photo_url": row.get('Фото'),
            "quarantine_address": row['Адрес хранения'],
            "items_data": updated_items.replace({np.nan: None}).to_dict(orient='records'),
            "updated_at": datetime.now().isoformat()
        }

        try:
            # 1. Сохранение в Supabase
            supabase.table(table_key).update(db_payload).eq("id", entry_id).execute()

            # 2. Если статус "ПОДТВЕРЖДЕНО", записываем в инвентарь
            if row['Статус'] == "ПОДТВЕРЖДЕНО":
                # Сначала чистим старое, чтобы не дублировать
                supabase.table("inventory").delete().eq("doc_id", entry_id).execute()
                
                inv_rows = []
                for _, item in updated_items.iterrows():
                    inv_rows.append({
                        "doc_id": entry_id,
                        "item_name": item.get('Товар', row['Товар']),
                        "cell_address": row['Адрес хранения'],
                        "quantity": float(item.get('Кол-во', 0)),
                        "warehouse_id": "CARANTIN" 
                    })
                if inv_rows:
                    supabase.table("inventory").insert(inv_rows).execute()

            # 3. Обновляем локальный DataFrame (чтобы закрыть окно и увидеть изменения)
            if idx is not None:
                for field_ru, field_en in [('Статус', 'status'), ('Товар', 'main_item')]:
                    if field_ru in st.session_state[table_key].columns:
                        st.session_state[table_key].at[idx, field_ru] = db_payload[field_en]

            st.success(f"✅ Акт №{entry_id} успешно обновлен!")
            time.sleep(1)
            st.rerun()

        except Exception as e:
            st.error(f"🚨 Ошибка сохранения: {e}")
        
@st.dialog("🔍 Просмотр Акта брака", width="large")
def show_defect_details_modal(defect_id):
    from database import supabase
    import pandas as pd

    # --- 1. ЗАГРУЗКА ДАННЫХ НАПРЯМУЮ ИЗ БД ---
    try:
        # Берем все актуальные поля, включая items_data и photo_url
        response = supabase.table("defects").select("*").eq("id", defect_id).execute()
        
        if not response.data:
            st.error(f"Акт №{defect_id} не найден в базе данных.")
            return
            
        db_row = response.data[0]
        
        # Загружаем спецификацию из JSONB колонки (items_data)
        # Это гарантирует, что мы видим именно те товары, которые были сохранены
        items_list = db_row.get('items_data', [])
        if isinstance(items_list, list) and len(items_list) > 0:
            items_df = pd.DataFrame(items_list)
        else:
            items_df = pd.DataFrame(columns=['Товар', 'Кол-во', 'Описание дефекта'])
            
    except Exception as e:
        st.error(f"🚨 Ошибка при получении данных из БД: {e}")
        return

    # --- 2. ЗАГОЛОВОК И СТАТУСНЫЕ МЕТРИКИ ---
    st.error(f"### 📑 АКТ ДЕФЕКТОВКИ №{defect_id}")
    
    # Верхняя панель с метриками (используем ключи БД)
    m1, m2, m3 = st.columns(3)
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
        # Форматируем дату, если она есть
        raw_date = db_row.get('updated_at', '---')
        clean_date = raw_date[:16].replace('T', ' ') if 'T' in raw_date else raw_date
        st.markdown(f"**📅 Последнее обновление:** {clean_date}")
        
    # Блок с решением комиссии
    st.info(f"**⚖️ Принятое решение:**\n\n{db_row.get('decision', 'На стадии рассмотрения')}")

    # --- 4. СПЕЦИФИКАЦИЯ ТОВАРОВ (ТАБЛИЦА) ---
    st.divider()
    st.markdown("#### 📦 Спецификация поврежденных позиций")
    
    if not items_df.empty:
        # Отображаем таблицу (только чтение)
        st.dataframe(
            items_df, 
            use_container_width=True,
            column_config={
                "Кол-во": st.column_config.NumberColumn("Кол-во", format="%d ед."),
                "Товар": "Наименование",
                "Описание дефекта": "Детали повреждения"
            }
        )
        
        # Подвал таблицы с итогами
        footer_c1, footer_c2 = st.columns(2)
        footer_c1.caption(f"Всего позиций в списке: {len(items_df)}")
        if 'Кол-во' in items_df.columns:
            try:
                total_q = pd.to_numeric(items_df['Кол-во']).sum()
                footer_c2.caption(f"Общее количество единиц: {total_q}")
            except:
                pass
    else:
        st.warning("⚠️ Детальная спецификация товаров не заполнена.")

    # --- 5. ФОТОФИКСАЦИЯ (ВИЗУАЛИЗАЦИЯ) ---
    photo_url = db_row.get('photo_url')
    if photo_url:
        st.divider()
        st.markdown("#### 📷 Фотофиксация повреждений")
        # Показываем фото. Если в базе лежит URL, он отобразится корректно.
        st.image(photo_url, use_container_width=True, caption=f"Доказательство к акту №{defect_id}")
    else:
        st.divider()
        st.caption("📷 Фотоматериалы к данному акту не загружены.")

    # Кнопка закрытия
    if st.button("❌ ЗАКРЫТЬ ПРОСМОТР", use_container_width=True):
        st.rerun()
        
@st.dialog("🖨️ Печать Акта о браке", width="large")
def show_defect_print_modal(defect_id):
    from database import supabase
    import pandas as pd

    # --- 1. ЗАГРУЗКА АКТУАЛЬНЫХ ДАННЫХ ИЗ ОБЛАКА ---
    try:
        # Получаем всё, включая photo_url и items_data
        response = supabase.table("defects").select("*").eq("id", defect_id).execute()
        
        if not response.data:
            st.error("Ошибка: Акт не найден в базе данных")
            return
            
        row = response.data[0]
        
        # Загружаем спецификацию товаров строго из JSONB поля
        items_list = row.get('items_data', [])
        items_df = pd.DataFrame(items_list) if items_list else pd.DataFrame()
        
    except Exception as e:
        st.error(f"Ошибка связи с БД: {e}")
        return

    # --- 2. ПОДГОТОВКА ТАБЛИЦЫ ТОВАРОВ ДЛЯ HTML ---
    if not items_df.empty:
        # Убеждаемся, что колонки соответствуют названиям в БД
        # Обычно это 'Товар', 'Кол-во', 'Описание дефекта'
        cols_to_print = [c for c in ['Товар', 'Кол-во', 'Описание дефекта'] if c in items_df.columns]
        items_html = items_df[cols_to_print].to_html(index=False, border=1, classes='data-table')
    else:
        items_html = "<p style='text-align:center; padding: 20px;'>Детальная спецификация товаров не заполнена</p>"

    # Подготовка блока фото (если есть URL)
    photo_html = ""
    if row.get('photo_url'):
        photo_html = f"""
        <div style="margin-top: 20px; text-align: center;">
            <h3>ФОТОФИКСАЦИЯ ПОВРЕЖДЕНИЙ:</h3>
            <img src="{row['photo_url']}" style="max-width: 100%; border: 1px solid #ccc; border-radius: 8px;">
        </div>
        """

    # --- 3. ГЕНЕРАЦИЯ HTML-ШАБЛОНА ---
    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; padding: 20px; color: #333; }}
            .act-border {{ border: 3px double #d32f2f; padding: 30px; background: #fff; }}
            .header {{ text-align: center; border-bottom: 2px solid #d32f2f; margin-bottom: 20px; padding-bottom: 10px; }}
            .header h1 {{ color: #d32f2f; margin: 0; font-size: 24px; text-transform: uppercase; }}
            .header p {{ margin: 5px 0; font-size: 12px; font-weight: bold; color: #666; }}
            
            .info-table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 14px; }}
            .info-table td {{ padding: 10px; border-bottom: 1px solid #eee; }}
            .info-table b {{ color: #555; }}
            
            .data-table {{ width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 13px; }}
            .data-table th {{ background: #f8f8f8; padding: 12px; border: 1px solid #333; text-align: left; }}
            .data-table td {{ padding: 10px; border: 1px solid #333; }}
            
            .decision-box {{ background: #fff4f4; border: 1px solid #d32f2f; padding: 15px; margin-top: 20px; font-style: italic; }}
            
            .footer {{ margin-top: 50px; display: flex; justify-content: space-between; align-items: flex-start; }}
            .signature-block {{ display: flex; flex-direction: column; gap: 30px; }}
            .signature-line {{ border-top: 1px solid #000; width: 250px; text-align: center; font-size: 10px; padding-top: 5px; }}
            
            .stamp {{ border: 4px double #0000FF; color: #0000FF; width: 150px; height: 150px; 
                        text-align: center; border-radius: 50%; opacity: 0.5; font-size: 12px; 
                        display: flex; align-items: center; justify-content: center;
                        transform: rotate(-15deg); font-weight: bold; text-transform: uppercase; }}
            
            @media print {{ 
                .no-print {{ display: none !important; }} 
                .act-border {{ border: 2px solid #d32f2f; }} 
                body {{ padding: 0; }}
            }}
        </style>
    </head>
    <body>
        <button class="no-print" onclick="window.print()" 
                style="width:100%; padding:15px; background:#d32f2f; color:white; border:none; cursor:pointer; font-weight:bold; border-radius:4px; margin-bottom:20px; font-size: 16px;">
            🖨️ ПЕЧАТАТЬ АКТ БРАКА / СОХРАНИТЬ В PDF
        </button>
        
        <div class="act-border">
            <div class="header">
                <h1>АКТ О ВЫЯВЛЕННЫХ ДЕФЕКТАХ №{defect_id}</h1>
                <p>IMPERIA WMS | ОТДЕЛ КОНТРОЛЯ КАЧЕСТВА И ПРЕТЕНЗИОННОЙ РАБОТЫ</p>
            </div>
            
            <table class="info-table">
                <tr>
                    <td><b>Дата формирования:</b> {row.get('updated_at', '---')[:10]}</td>
                    <td><b>Текущий статус:</b> <span style="color:#d32f2f; font-weight:bold;">{row.get('status', '---')}</span></td>
                </tr>
                <tr>
                    <td><b>Ответственная сторона:</b> {row.get('culprit', '---')}</td>
                    <td><b>Характер дефекта:</b> {row.get('defect_type', '---')}</td>
                </tr>
                <tr>
                    <td><b>Основная позиция:</b> {row.get('main_item', '---')}</td>
                    <td><b>Зона размещения:</b> {row.get('quarantine_address', '---')}</td>
                </tr>
                <tr>
                    <td colspan="2"><b>Документ-основание (ID):</b> {row.get('related_doc_id', '---')}</td>
                </tr>
            </table>
            
            <div class="decision-box">
                <b>ЗАКЛЮЧЕНИЕ / РЕШЕНИЕ КОМИССИИ:</b><br>
                {row.get('decision', 'На стадии рассмотрения экспертной группой.')}
            </div>
            
            <h3 style="margin-top: 30px; border-left: 5px solid #d32f2f; padding-left: 10px;">СПЕЦИФИКАЦИЯ ТМЦ:</h3>
            {items_html}

            {photo_html}

            <div class="footer">
                <div class="signature-block">
                    <div class="signature-line">Сдал (Представитель / Перевозчик)</div>
                    <div class="signature-line">Принял (Сотрудник склада)</div>
                    <div class="signature-line">Утвердил (Начальник смены/QC)</div>
                </div>
                
                <div class="stamp">
                    IMPERIA WMS<br>КОНТРОЛЬ<br>ПРОЙДЕН
                </div>
            </div>
            
            <div style="margin-top:30px; font-size:9px; color:#aaa; text-align:center; border-top: 1px solid #eee; padding-top: 10px;">
                Электронный документ ID: {defect_id} | Дата/Время печати: {pd.Timestamp.now().strftime('%d.%m.%Y %H:%M')} | Система IMPERIA WMS
            </div>
        </div>
    </body>
    </html>
    """

    # Отображение HTML в Streamlit
    st.components.v1.html(full_html, height=900, scrolling=True)
    
    if st.button("❌ ЗАКРЫТЬ ОКНО ПЕЧАТИ", use_container_width=True):
        st.rerun()





