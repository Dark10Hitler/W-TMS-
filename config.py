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
        
        if st.button("🔗 ПРИВЯЗАТЬ К ЯЧЕЙКЕ", use_container_width=True, type="primary", key=f"btn_bind_{entry_id}"):
            # Обновляем адрес в буфере сессии
            st.session_state[f"temp_items_{entry_id}"].loc[
                st.session_state[f"temp_items_{entry_id}"]['Название товара'] == target_item, 'Адрес'
            ] = selected_cell
            st.toast(f"Товар {target_item} привязан к {selected_cell}")
            # Мы не делаем rerun, чтобы пользователь мог привязать несколько товаров подряд

    with col_viz:
        # Визуализация
        fig = get_warehouse_figure(wh_id, highlighted_cell=selected_cell)
        st.plotly_chart(fig, use_container_width=True, key=f"map_v_{entry_id}")
        
@st.dialog("⚙️ Редактирование данных", width="large")
def edit_order_modal(entry_id, table_key="orders"):
    # --- 1. ИНИЦИАЛИЗАЦИЯ (Единоразово для конкретного ID) ---
    if f"temp_row_{entry_id}" not in st.session_state:
        if table_key not in st.session_state:
            st.error(f"Таблица {table_key} не найдена в системе")
            return
            
        df = st.session_state[table_key]
        idx_list = df.index[df['id'] == entry_id].tolist()
        
        if not idx_list:
            st.error(f"Запись с ID {entry_id} не найдена в таблице {table_key}")
            return
        
        st.session_state[f"temp_idx_{entry_id}"] = idx_list[0]
        st.session_state[f"temp_row_{entry_id}"] = df.iloc[idx_list[0]].to_dict()
        
        # Загрузка товаров
        items_df = st.session_state.items_registry.get(
            entry_id, 
            pd.DataFrame(columns=['Название товара', 'Кол-во', 'Адрес'])
        ).copy()
        
        if 'Адрес' not in items_df.columns:
            items_df['Адрес'] = "НЕ УКАЗАНО"
            
        st.session_state[f"temp_items_{entry_id}"] = items_df

    # Ссылки на данные
    row = st.session_state[f"temp_row_{entry_id}"]
    items_df = st.session_state[f"temp_items_{entry_id}"]
    idx = st.session_state[f"temp_idx_{entry_id}"]

    st.markdown(f"### 🖋️ Редактор документа `{entry_id}`")
    
    tab_main, tab_geo = st.tabs(["📝 Информация и Поля", "📍 Склад (3D)"])

    # --- ВКЛАДКА 1: РЕДАКТИРОВАНИЕ ВСЕХ ПОЛЕЙ (ORDER_COLUMNS) ---
    with tab_main:
        # Ряд 1: Основные данные
        st.markdown("##### 👤 Клиент и Контакты")
        c1, c2, c3 = st.columns(3)
        row['Клиент'] = c1.text_input("Клиент", value=str(row.get('Клиент', '')), key=f"edit_cli_{entry_id}")
        row['Телефон'] = c2.text_input("Телефон", value=str(row.get('Телефон', '')), key=f"edit_ph_{entry_id}")
        row['Адрес клиента'] = c3.text_input("Адрес доставки", value=str(row.get('Адрес клиента', '')), key=f"edit_adr_c_{entry_id}")

        # Ряд 2: Логистика
        st.markdown("##### 🚚 Логистика и Транспорт")
        r2_1, r2_2, r2_3, r2_4 = st.columns(4)
        
        status_list = ["ОЖИДАНИЕ", "Стоит на точке загрузки", "Выехал", "Ожидает догруз", "В пути", "Доставлено", "БРАК"]
        curr_st = str(row.get('Статус', 'ОЖИДАНИЕ'))
        st_idx = status_list.index(curr_st) if curr_st in status_list else 0
        
        row['Статус'] = r2_1.selectbox("Статус", status_list, index=st_idx, key=f"edit_st_{entry_id}")
        row['Водитель'] = r2_2.text_input("Водитель", value=str(row.get('Водитель', '')), key=f"edit_dr_{entry_id}")
        row['ТС'] = r2_3.text_input("ТС (Госномер)", value=str(row.get('ТС', '')), key=f"edit_ts_{entry_id}")
        row['Адрес загрузки'] = r2_4.text_input("Адрес загрузки", value=str(row.get('Адрес загрузки', 'Центральный склад')), key=f"edit_adr_z_{entry_id}")

        # Ряд 3: Финансы, Сертификаты и Допуски
        st.markdown("##### ⚖️ Параметры и Допуски")
        r3_1, r3_2, r3_3, r3_4 = st.columns(4)
        
        try:
            curr_sum = float(row.get('Сумма заявки', 0.0))
            curr_vol = float(row.get('Общий объем (м3)', 0.0))
        except:
            curr_sum, curr_vol = 0.0, 0.0

        row['Сумма заявки'] = r3_1.number_input("Сумма заявки", value=curr_sum, key=f"edit_sum_{entry_id}")
        row['Общий объем (м3)'] = r3_2.number_input("Общий объем (м3)", value=curr_vol, key=f"edit_vol_{entry_id}")
        row['Допуск'] = r3_3.text_input("Допуск (Кто разрешил)", value=str(row.get('Допуск', '')), key=f"edit_dop_{entry_id}")
        
        cert_val = str(row.get('Сертификат', 'Нет'))
        row['Сертификат'] = r3_4.selectbox("Сертификат", ["Да", "Нет"], index=0 if cert_val == "Да" else 1, key=f"edit_cert_{entry_id}")

        # Ряд 4: Медиа и Описание
        st.markdown("##### 📝 Дополнительно")
        r4_1, r4_2 = st.columns([2, 1])
        row['Описание'] = r4_1.text_area("Описание", value=str(row.get('Описание', '')), height=100, key=f"edit_desc_{entry_id}")
        
        st.write(f"Текущее фото: {row.get('Фото', 'Нет')}")
        new_photo = r4_2.file_uploader("Обновить фото", type=['png', 'jpg', 'jpeg'], key=f"edit_photo_up_{entry_id}")

        st.divider()
        st.markdown("### 📦 Состав товаров")
        updated_items = st.data_editor(items_df, use_container_width=True, num_rows="dynamic", key=f"ed_it_{entry_id}")
        st.session_state[f"temp_items_{entry_id}"] = updated_items

        if st.button("💾 СОХРАНИТЬ ВСЕ ИЗМЕНЕНИЯ", use_container_width=True, type="primary"):
            # Расчет КПД (если есть данные о ТС в системе)
            # Здесь можно добавить логику пересчета КПД загрузки
            
            # Логирование изменений
            try: operator = st.session_state.profile_data.iloc[0]['Значение']
            except: operator = "Admin"
            
            row['Последнее изменение'] = f"{operator} ({datetime.now().strftime('%H:%M')})"
            row['Кол-во позиций'] = len(updated_items)
            if new_photo: row['Фото'] = "Прикреплено (Обновлено)"

            # Сохранение
            target_df = st.session_state[table_key]
            for field, val in row.items():
                if field in target_df.columns:
                    target_df.at[idx, field] = val
            
            st.session_state.items_registry[entry_id] = updated_items
            
            # Зеркалирование в Main
            if "main" in st.session_state:
                m_df = st.session_state["main"]
                m_idx = m_df.index[m_df['id'] == entry_id].tolist()
                if m_idx:
                    for field in row:
                        if field in m_df.columns: m_df.at[m_idx[0], field] = row[field]

            st.success("✅ Данные успешно обновлены!")
            time.sleep(1)
            st.rerun()

    # --- ВКЛАДКА 2: ВЫБОР МЕСТА (Твой оригинальный код с 3D) ---
    with tab_geo:
        if updated_items.empty:
            st.warning("Добавьте товары во вкладке 'Информация'!")
        else:
            col_sel, col_viz = st.columns([1, 2])
            with col_sel:
                st.subheader("Привязка к ячейке")
                target_item = st.selectbox("📦 Товар:", updated_items['Название товара'].unique(), key=f"t_sel_{entry_id}")
                wh_id = str(st.selectbox("🏪 Склад:", list(WAREHOUSE_MAP.keys()), key=f"wh_sel_{entry_id}"))
                
                # Генератор ячеек (Логика сохранена)
                conf = WAREHOUSE_MAP[wh_id]
                all_cells = []
                for r in conf['rows']:
                    all_cells.extend([f"WH{wh_id}-{r}", f"{wh_id}-{r}"])
                    for s in range(1, conf.get('sections', 1) + 1):
                        for t in conf.get('tiers', ['A']):
                            all_cells.extend([f"WH{wh_id}-{r}-R1-S{s}-{t}", f"WH{wh_id}-{r}-S{s}-{t}", f"{wh_id}-{r}-{s}-{t}"])
                all_cells = sorted(list(set(all_cells)))
                
                match_cond = updated_items['Название товара'] == target_item
                curr_addr = updated_items.loc[match_cond, 'Адрес'].values[0] if not updated_items.loc[match_cond, 'Адрес'].empty else "НЕ УКАЗАНО"
                if curr_addr not in all_cells and curr_addr != "НЕ УКАЗАНО": all_cells.insert(0, curr_addr)
                
                selected_cell = st.selectbox("📍 Ячейка:", options=all_cells, index=all_cells.index(curr_addr) if curr_addr in all_cells else 0, key=f"cs_sel_{entry_id}")
                
                if st.button("🔗 ПРИВЯЗАТЬ", use_container_width=True, type="primary", key=f"bind_{entry_id}"):
                    st.session_state[f"temp_items_{entry_id}"].loc[st.session_state[f"temp_items_{entry_id}"]['Название товара'] == target_item, 'Адрес'] = selected_cell
                    st.toast(f"Привязано к {selected_cell}")

            with col_viz:
                st.subheader("3D Визуализация")
                fig = get_warehouse_figure(wh_id, highlighted_cell=selected_cell)
                st.plotly_chart(fig, use_container_width=True, key=f"p_viz_{entry_id}")

@st.dialog("🔍 Детальный просмотр заявки", width="large")
def show_order_details_modal(order_id):
    df_main = st.session_state.main
    row_match = df_main[df_main['id'] == order_id]
    
    if row_match.empty:
        st.error("Документ не найден.")
        return
        
    row = row_match.iloc[0]
    st.subheader(f"📄 Просмотр документа: {order_id}")
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"**👤 Клиент:** {row.get('Клиент', '---')}")
        st.markdown(f"**📞 Телефон:** {row.get('Телефон', '---')}")
        st.markdown(f"**📍 Адрес:** {row.get('Адрес клиента', '---')}")
    with c2:
        st.markdown(f"**📦 Статус:** `{row.get('Статус', '---')}`")
        st.markdown(f"**📜 Сертификат:** {row.get('Сертификат', '---')}")
        st.markdown(f"**🏗️ Адрес загрузки:** {row.get('Адрес загрузки', '---')}")
    with c3:
        st.markdown(f"**🚛 ТС:** {row.get('ТС (Госномер)', row.get('ТС', '---'))}")
        st.markdown(f"**👤 Водитель:** {row.get('Водитель', '---')}")
        with st.expander("🕒 История правок"):
            st.caption(f"Создан: {row.get('Дата создания')} {row.get('Время создания')}")
            st.caption(f"Последнее изменение: {row.get('Последнее изменение', 'Первичная запись')}")

    st.divider()

    st.markdown("### 📋 Товарная спецификация и места хранения")
    if order_id in st.session_state.items_registry:
        items_df = st.session_state.items_registry[order_id]
        
        # Красивое оформление таблицы: подсвечиваем адреса
        def color_addr(val):
            color = 'lightgreen' if val != "НЕ УКАЗАНО" and val != "-" else '#ffcccc'
            return f'background-color: {color}'

        if 'Адрес' in items_df.columns:
            st.dataframe(items_df.style.applymap(color_addr, subset=['Адрес']), use_container_width=True)
        else:
            st.dataframe(items_df, use_container_width=True)
        
        # Метрики
        m1, m2, m3 = st.columns(3)
        m1.metric("Всего позиций", f"{row.get('Кол-во позиций', 0)}")
        m2.metric("Общий объем", f"{row.get('Общий объем (м3)', 0)} м³")
        m3.metric("КПД загрузки", f"{row.get('КПД загрузки', '0%')}")
    else:
        st.warning("⚠️ Спецификация товаров пуста или не найдена.")

    st.info(f"**📝 Сведения/Допуск:** {row.get('Описание', 'Нет описания')}")

    if st.button("❌ ЗАКРЫТЬ", use_container_width=True):
        st.session_state.active_view_modal = None
        st.rerun()

@st.dialog("🖨️ Печать документа", width="large")
def show_print_modal(order_id):
    row_data = st.session_state.main[st.session_state.main['id'] == order_id]
    if row_data.empty:
        st.error("Ошибка данных для печати")
        return
    row = row_data.iloc[0]
    
    # Подготовка таблицы
    if order_id in st.session_state.items_registry:
        raw_items = st.session_state.items_registry[order_id]
        # Очистка от служебных колонок
        display_cols = [c for c in raw_items.columns if "Unnamed" not in str(c)]
        print_df = raw_items[display_cols].dropna(how='all').fillna("-")
    else:
        print_df = pd.DataFrame(columns=["Товар", "Кол-во", "Адрес"])

    # Превращаем DataFrame в HTML
    items_html = print_df.to_html(index=False, border=1, classes='items-table')

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
                    <td><b>👤 Получатель</b><br>{row.get('Клиент', '---')}</td>
                    <td><b>📍 Куда (Адрес)</b><br>{row.get('Адрес клиента', '---')}</td>
                    <td><b>📞 Телефон</b><br>{row.get('Телефон', '---')}</td>
                </tr>
                <tr>
                    <td><b>🚛 Перевозчик</b><br>{row.get('Водитель', '---')} ({row.get('ТС (Госномер)', '---')})</td>
                    <td><b>🏗️ Место отгрузки</b><br>{row.get('Адрес загрузки', '---')}</td>
                    <td><b>📦 Статус заявки</b><br>{row.get('Статус', '---')}</td>
                </tr>
                <tr>
                    <td><b>📏 Общий объем</b><br>{row.get('Общий объем (м3)', '0')} м³</td>
                    <td><b>📜 Сертификация</b><br>{row.get('Сертификат', '---')}</td>
                    <td><b>📅 Дата док-та</b><br>{row.get('Дата создания')}</td>
                </tr>
            </table>

            <div style="padding:10px; border:1px solid #eee; background:#f9f9f9; font-size:12px;">
                <b>📑 Комментарий / Допуск:</b> {row.get('Описание', '---')}
            </div>

            <h3 style="border-left: 5px solid #2c3e50; padding-left: 10px; margin-top:30px;">СПЕЦИФИКАЦИЯ ТМЦ</h3>
            {items_html}

            <div class="footer">
                <div class="signature-grid">
                    <div>
                        <p style="margin-bottom:40px;">Отгрузил (Склад):</p>
                        <div style="border-bottom: 1px solid #000; width: 200px;"></div>
                        <p style="font-size:10px;">(ФИО, Подпись) / {row.get('Допуск', '_______')}</p>
                    </div>
                    <div style="text-align: right;">
                        <p style="margin-bottom:40px;">Принял (Водитель/Клиент):</p>
                        <div style="border-bottom: 1px solid #000; width: 200px; margin-left: auto;"></div>
                        <p style="font-size:10px;">(ФИО, Подпись) / {row.get('Клиент', '_______')}</p>
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
    table_key = "arrivals"
    # --- 1. ИНИЦИАЛИЗАЦИЯ (Загружаем данные из arrivals) ---
    if f"temp_row_{entry_id}" not in st.session_state:
        df = st.session_state[table_key]
        idx_list = df.index[df['id'] == entry_id].tolist()
        if not idx_list:
            st.error("Запись прихода не найдена")
            return
        
        st.session_state[f"temp_idx_{entry_id}"] = idx_list[0]
        st.session_state[f"temp_row_{entry_id}"] = df.iloc[idx_list[0]].to_dict()
        st.session_state[f"temp_items_{entry_id}"] = st.session_state.items_registry.get(
            entry_id, pd.DataFrame(columns=['Название товара', 'Кол-во', 'Объем (м3)', 'Адрес'])
        ).copy()

    row = st.session_state[f"temp_row_{entry_id}"]
    items_df = st.session_state[f"temp_items_{entry_id}"]
    idx = st.session_state[f"temp_idx_{entry_id}"]

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
        row['Сертификат'] = r2_4.selectbox("Документы в порядке", ["Да", "Нет"], index=(0 if row.get('Сертификат')=="Да" else 1), key=f"ar_f7_{entry_id}")

        st.divider()
        st.markdown("### 📦 Состав принимаемого груза")
        updated_items = st.data_editor(items_df, use_container_width=True, num_rows="dynamic", key=f"ar_ed_{entry_id}")
        st.session_state[f"temp_items_{entry_id}"] = updated_items

        if st.button("💾 ЗАФИКСИРОВАТЬ ПРИЕМКУ", use_container_width=True, type="primary"):
            # Сохраняем в Arrivals
            for field, val in row.items():
                st.session_state[table_key].at[idx, field] = val
            
            # Пересчет объемов
            total_vol = pd.to_numeric(updated_items['Объем (м3)'], errors='coerce').sum()
            st.session_state[table_key].at[idx, 'Кол-во позиций'] = len(updated_items)
            st.session_state[table_key].at[idx, 'Общий объем (м3)'] = round(float(total_vol), 3)
            
            # СИНХРОНИЗАЦИЯ С MAIN (Профессиональный уровень)
            if "main" in st.session_state:
                main_df = st.session_state["main"]
                if entry_id in main_df['id'].values:
                    m_idx = main_df.index[main_df['id'] == entry_id].tolist()[0]
                    for field, val in row.items():
                        if field in main_df.columns:
                            main_df.at[m_idx, field] = val
                    main_df.at[m_idx, 'Общий объем (м3)'] = round(float(total_vol), 3)

            st.session_state.items_registry[entry_id] = updated_items
            st.success("✅ Данные приемки обновлены!")
            time.sleep(1)
            st.rerun()

    with tab_wh:
        # Логика 3D-склада (идентична заявкам, но цель — распределить приход по ячейкам)
        render_warehouse_logic(entry_id, updated_items)
        
@st.dialog("🔍 Карточка Прихода", width="large")
def show_arrival_details_modal(arrival_id):
    df = st.session_state.arrivals
    row_match = df[df['id'] == arrival_id]
    
    if row_match.empty:
        st.error("Документ прихода не найден.")
        return
        
    row = row_match.iloc[0]
    st.subheader(f"📥 Детальный обзор прихода: {arrival_id}")
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"**🏢 Поставщик:** {row.get('Клиент', '---')}")
        st.markdown(f"**📞 Контакт:** {row.get('Телефон', '---')}")
    with c2:
        st.markdown(f"**📦 Статус:** `{row.get('Статус', '---')}`")
        st.markdown(f"**🏗️ Склад приемки:** {row.get('Адрес загрузки', '---')}")
    with c3:
        st.markdown(f"**🚛 Транспорт:** {row.get('ТС (Госномер)', '---')}")
        st.markdown(f"**👤 Водитель:** {row.get('Водитель', '---')}")

    st.divider()
    st.markdown("### 📋 Принятые позиции")
    if arrival_id in st.session_state.items_registry:
        items_df = st.session_state.items_registry[arrival_id]
        st.dataframe(items_df, use_container_width=True)
        
        m1, m2 = st.columns(2)
        m1.metric("Принято строк", f"{len(items_df)}")
        m2.metric("Фактический объем", f"{row.get('Общий объем (м3)', 0)} м³")
    
    if st.button("❌ ЗАКРЫТЬ", use_container_width=True):
        st.rerun()
   
@st.dialog("🖨️ Печать приходного ордера", width="large")
def show_arrival_print_modal(arrival_id):
    row_data = st.session_state.arrivals[st.session_state.arrivals['id'] == arrival_id]
    if row_data.empty:
        st.error("Ошибка данных")
        return
    row = row_data.iloc[0]
    
    items_df = st.session_state.items_registry.get(arrival_id, pd.DataFrame(columns=["Товар", "Кол-во"]))
    items_html = items_df.to_html(index=False, border=1, classes='items-table')

    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        @media print {{ .no-print {{ display: none !important; }} }}
        body {{ font-family: sans-serif; padding: 20px; }}
        .print-container {{ background: white; padding: 20px; border: 1px solid #ccc; }}
        .header {{ border-bottom: 2px solid #000; display: flex; justify-content: space-between; }}
        .info-table {{ width: 100%; margin-top: 20px; border-collapse: collapse; }}
        .info-table td {{ border: 1px solid #eee; padding: 5px; }}
        .items-table {{ width: 100%; margin-top: 20px; border-collapse: collapse; }}
        .items-table th {{ background: #eee; padding: 10px; border: 1px solid #000; }}
        .items-table td {{ padding: 10px; border: 1px solid #000; }}
    </style>
    </head>
    <body>
        <button class="no-print" onclick="window.print()" style="width:100%; padding:10px; background: #2E7D32; color:white; border:none; cursor:pointer;">ПЕЧАТАТЬ ПРИХОДНЫЙ ОРДЕР</button>
        <div class="print-container">
            <div class="header">
                <h2>ПРИХОДНЫЙ ОРДЕР №{arrival_id}</h2>
                <p>IMPERIA WMS | ПРИЕМКА</p>
            </div>
            <table class="info-table">
                <tr>
                    <td><b>Отправитель (Поставщик):</b><br>{row.get('Клиент')}</td>
                    <td><b>Склад приемки:</b><br>{row.get('Адрес загрузки')}</td>
                </tr>
                <tr>
                    <td><b>Транспорт:</b> {row.get('ТС (Госномер)')}</td>
                    <td><b>Водитель:</b> {row.get('Водитель')}</td>
                </tr>
            </table>
            <h3>СПЕЦИФИКАЦИЯ ПРИНЯТОГО ТОВАРА</h3>
            {items_html}
            <div style="margin-top:50px; display:flex; justify-content: space-between;">
                <div>Сдал (Водитель): ___________</div>
                <div>Принял (Кладовщик): ___________</div>
            </div>
        </div>
    </body>
    </html>
    """
    components.html(full_html, height=800, scrolling=True)
    
    
@st.dialog("⚙️ Корректировка: Дополнение к документу", width="large")
def edit_extra_modal(entry_id):
    table_key = "extras"
    
    # --- 1. ИНИЦИАЛИЗАЦИЯ (Сверка с EXTRA_COLUMNS) ---
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
        # Линия 1: Ответственные и связь
        st.markdown("##### 👤 Субъекты и Связи")
        c1, c2, c3 = st.columns(3)
        row['Кто одобрил'] = c1.text_input("Кто одобрил (ФИО/Контрагент)", value=row.get('Кто одобрил', ''), key=f"ex_v1_{entry_id}")
        row['Связь с ID'] = c2.text_input("Связь с ID (Родительский док)", value=row.get('Связь с ID', ''), key=f"ex_v2_{entry_id}")
        row['На чем'] = c3.text_input("На чем (Транспорт/Курьер)", value=row.get('На чем', ''), key=f"ex_v3_{entry_id}")

        # Линия 2: Время и Место
        st.markdown("##### 📅 Время и Локация")
        r2_1, r2_2, r2_3 = st.columns(3)
        row['Когда'] = r2_1.date_input("Когда (Дата события)", value=pd.to_datetime(row.get('Когда', datetime.now())).date(), key=f"ex_v4_{entry_id}").strftime("%Y-%m-%d")
        row['Время'] = r2_2.text_input("Время", value=row.get('Время', datetime.now().strftime("%H:%M")), key=f"ex_v5_{entry_id}")
        row['Где'] = r2_3.text_input("Где (Точка/Склад)", value=row.get('Где', ''), key=f"ex_v6_{entry_id}")

        # Линия 3: Суть и Причины
        st.markdown("##### 📄 Суть корректировки")
        r3_1, r3_2, r3_3 = st.columns([2, 1, 1])
        row['Что именно'] = r3_1.text_input("Что именно (Краткая суть)", value=row.get('Что именно', ''), key=f"ex_v7_{entry_id}")
        row['Статус'] = r3_2.selectbox("Статус", ["СОГЛАСОВАНО", "В РАБОТЕ", "ЗАВЕРШЕНО", "ОТМЕНЕНО"], 
                                       index=0 if row.get('Статус')=="СОГЛАСОВАНО" else 1, key=f"ex_v8_{entry_id}")
        
        try: curr_sum = float(row.get('Сумма заявки', 0.0))
        except: curr_sum = 0.0
        row['Сумма заявки'] = r3_3.number_input("Сумма заявки", value=curr_sum, key=f"ex_v9_{entry_id}")

        # Линия 4: Причина (крупно)
        row['Почему (Причина)'] = st.text_area("Почему (Причина корректировки)", value=row.get('Почему (Причина)', ''), height=70, key=f"ex_v10_{entry_id}")

        st.divider()
        st.markdown("### 📦 Изменения в составе товаров")
        updated_items = st.data_editor(items_df, use_container_width=True, num_rows="dynamic", key=f"ex_ed_{entry_id}")
        st.session_state[f"temp_items_{entry_id}"] = updated_items

        if st.button("💾 СОХРАНИТЬ ВСЕ ДАННЫЕ", use_container_width=True, type="primary"):
            # Авто-расчет количества
            row['Кол-во'] = len(updated_items)
            
            # Сохранение в таблицу extras
            for field, val in row.items():
                if field in st.session_state[table_key].columns:
                    st.session_state[table_key].at[idx, field] = val

            # Синхронизация с MAIN (используем только те поля, что есть в Main)
            if "main" in st.session_state:
                m_df = st.session_state["main"]
                m_idx_list = m_df.index[m_df['id'] == entry_id].tolist()
                if m_idx_list:
                    m_idx = m_idx_list[0]
                    for field, val in row.items():
                        if field in m_df.columns:
                            m_df.at[m_idx, field] = val

            st.session_state.items_registry[entry_id] = updated_items
            st.success("✅ Все ячейки дополнения обновлены!")
            time.sleep(1)
            st.rerun()

    with tab_wh:
        # Универсальная логика склада
        render_warehouse_logic(entry_id, updated_items)
        
@st.dialog("🔍 Просмотр дополнения", width="large")
def show_extra_details_modal(extra_id):
    if "extras" not in st.session_state:
        st.error("База данных extras недоступна")
        return
        
    df = st.session_state.extras
    row_match = df[df['id'] == extra_id]
    
    if row_match.empty:
        st.error("Запись не найдена.")
        return
        
    row = row_match.iloc[0]
    st.subheader(f"📑 Детальный просмотр корректировки: {extra_id}")
    
    # Сетка данных строго по EXTRA_COLUMNS
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"**👤 Кто одобрил:**\n{row.get('Кто одобрил', '---')}")
        st.markdown(f"**🔗 Связь с ID:**\n`{row.get('Связь с ID', 'НЕТ')}`")
        st.markdown(f"**📈 Статус:**\n`{row.get('Статус', '---')}`")

    with col2:
        st.markdown(f"**🎯 Что именно:**\n{row.get('Что именно', '---')}")
        st.markdown(f"**📅 Дата события:**\n{row.get('Когда', '---')}")
        st.markdown(f"**🕒 Время:**\n{row.get('Время', '---')}")

    with col3:
        st.markdown(f"**🚚 На чем (Транспорт):**\n{row.get('На чем', '---')}")
        st.markdown(f"**📍 Где (Локация):**\n{row.get('Где', '---')}")
        st.markdown(f"**💰 Сумма заявки:**\n{row.get('Сумма заявки', 0.0):,.2f}")

    st.warning(f"**❓ Причина (Почему):** {row.get('Почему (Причина)', 'Не указана')}")

    st.divider()
    st.markdown(f"### 📦 Состав позиций (Всего: {row.get('Кол-во', 0)})")
    if extra_id in st.session_state.items_registry:
        st.dataframe(st.session_state.items_registry[extra_id], use_container_width=True)
    else:
        st.info("Спецификация товаров пуста.")

    # Дополнительные системные данные
    st.caption(f"Дата создания записи: {row.get('Дата создания', '---')}")
    
    if st.button("❌ ЗАКРЫТЬ", use_container_width=True):
        st.rerun()

@st.dialog("🖨️ Печать приложения", width="large")
def show_extra_print_modal(extra_id):
    row_data = st.session_state.extras[st.session_state.extras['id'] == extra_id]
    if row_data.empty:
        st.error("Ошибка данных")
        return
    row = row_data.iloc[0]
    
    items_df = st.session_state.items_registry.get(extra_id, pd.DataFrame(columns=["Товар", "Кол-во"]))
    items_html = items_df.to_html(index=False, border=1, classes='items-table')

    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        @media print {{ .no-print {{ display: none !important; }} }}
        body {{ font-family: 'Segoe UI', sans-serif; padding: 30px; line-height: 1.6; }}
        .print-card {{ border: 2px solid #333; padding: 20px; border-radius: 10px; }}
        .doc-header {{ text-align: center; border-bottom: 2px solid #333; margin-bottom: 20px; }}
        .info-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; }}
        .items-table {{ width: 100%; border-collapse: collapse; }}
        .items-table th, .items-table td {{ border: 1px solid #333; padding: 8px; text-align: left; }}
        .items-table th {{ background-color: #f2f2f2; }}
        .footer {{ margin-top: 50px; font-style: italic; }}
    </style>
    </head>
    <body>
        <button class="no-print" onclick="window.print()" style="width:100%; padding:15px; background:#fb8c00; color:white; border:none; border-radius:5px; font-weight:bold; cursor:pointer; margin-bottom:20px;">🖨️ ПЕЧАТЬ ПРИЛОЖЕНИЯ К ДОКУМЕНТУ</button>
        <div class="print-card">
            <div class="doc-header">
                <h1>ДОПОЛНЕНИЕ №{extra_id}</h1>
                <p>К основному документу №{row.get('Parent_ID', '_______')}</p>
            </div>
            <div class="info-grid">
                <div>
                    <b>Тип операции:</b> {row.get('Тип')}<br>
                    <b>Контрагент:</b> {row.get('Клиент')}
                </div>
                <div style="text-align: right;">
                    <b>Дата корректировки:</b> {datetime.now().strftime('%d.%m.%Y')}<br>
                    <b>Статус:</b> {row.get('Статус')}
                </div>
            </div>
            <h3>ПЕРЕЧЕНЬ ИЗМЕНЕНИЙ / ДОПОЛНИТЕЛЬНЫХ ПОЗИЦИЙ</h3>
            {items_html}
            <div class="footer">
                <p>Данное дополнение является неотъемлемой частью основного договора/накладной.</p>
                <div style="display: flex; justify-content: space-between; margin-top: 40px;">
                    <div>Менеджер: _________________</div>
                    <div>Контрагент: _________________</div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    components.html(full_html, height=850, scrolling=True)
    
@st.dialog("🚨 Актирование и Редактирование брака", width="large")
def edit_defect_modal(entry_id):
    table_key = "defects"
    
    # --- 1. ИНИЦИАЛИЗАЦИЯ (Синхронизация с DEFECT_COLUMNS) ---
    if f"temp_row_{entry_id}" not in st.session_state:
        df = st.session_state[table_key]
        idx_list = df.index[df['id'] == entry_id].tolist()
        if not idx_list:
            st.error("Акт брака не найден в базе")
            return
        
        st.session_state[f"temp_idx_{entry_id}"] = idx_list[0]
        st.session_state[f"temp_row_{entry_id}"] = df.iloc[idx_list[0]].to_dict()
        
        # Загружаем товары или создаем пустую структуру, если их нет
        items = st.session_state.items_registry.get(entry_id, pd.DataFrame(columns=['Товар', 'Кол-во', 'Описание дефекта']))
        st.session_state[f"temp_items_{entry_id}"] = items.copy()

    row = st.session_state[f"temp_row_{entry_id}"]
    items_df = st.session_state[f"temp_items_{entry_id}"]
    idx = st.session_state[f"temp_idx_{entry_id}"]

    st.error(f"### 🚨 Редактирование Акта №{entry_id}")
    
    tab_main, tab_photo, tab_geo = st.tabs(["📝 Основные данные", "📸 Фотофиксация", "📍 Склад"])

    with tab_main:
        c1, c2, c3 = st.columns(3)
        # Соответствие DEFECT_COLUMNS
        row['Товар'] = c1.text_input("Основной товар", value=row.get('Товар', ''), key=f"d_f1_{entry_id}")
        row['Кол-во брака'] = c2.number_input("Кол-во (общ)", value=int(row.get('Кол-во брака', 0)), key=f"d_f2_{entry_id}")
        row['Связь с документом'] = c3.text_input("Связь с ID (Заявка)", value=row.get('Связь с документом', ''), key=f"d_f3_{entry_id}")

        r2_1, r2_2, r2_3 = st.columns(3)
        row['Тип дефекта'] = r2_1.selectbox("Тип дефекта", ["Бой", "Порча упаковки", "Некомплект", "Производственный брак"], key=f"d_f4_{entry_id}")
        row['Виновник'] = r2_2.selectbox("Виновник", ["Перевозчик", "Склад", "Поставщик", "Не установлен"], key=f"d_f5_{entry_id}")
        row['Статус'] = r2_3.selectbox("Статус", ["ОБНАРУЖЕНО", "В ЭКСПЕРТИЗЕ", "ПОДТВЕРЖДЕНО", "СПИСАНО"], key=f"d_f6_{entry_id}")

        row['Решение'] = st.text_area("Принятое решение", value=row.get('Решение', ''), height=70, key=f"d_f7_{entry_id}")

        st.divider()
        st.markdown("##### 📦 Спецификация поврежденных позиций")
        # Редактор товаров - именно отсюда берется инфо для таблицы просмотра
        updated_items = st.data_editor(items_df, use_container_width=True, num_rows="dynamic", key=f"d_ed_{entry_id}")
        st.session_state[f"temp_items_{entry_id}"] = updated_items

    with tab_photo:
        st.markdown("##### 📷 Доказательства повреждений")
        if row.get('Фото'):
            st.info(f"Текущее фото: {row['Фото']}")
        new_defect_photo = st.file_uploader("Загрузить фото брака", type=['jpg', 'png', 'jpeg'], key=f"d_ph_{entry_id}")
        if new_defect_photo:
            row['Фото'] = f"defect_{entry_id}.jpg" # Имя файла для сохранения

    with tab_geo:
        st.markdown("##### 📍 Место в зоне карантина")
        row['Адрес хранения'] = st.text_input("Ячейка брака (Зона Карантин)", value=row.get('Адрес хранения', 'Z-BRAK-01'), key=f"d_adr_{entry_id}")
        render_warehouse_logic(entry_id, updated_items)

    # КНОПКА СОХРАНЕНИЯ
    if st.button("🚨 СОХРАНИТЬ ИЗМЕНЕНИЯ В АКТЕ", use_container_width=True, type="primary"):
        target_df = st.session_state[table_key]
        
        # Проставляем дату, если её нет
        if not row.get('Дата создания'):
            row['Дата создания'] = datetime.now().strftime("%d.%m.%Y")

        # Записываем всё в DataFrame
        for field, val in row.items():
            if field in target_df.columns:
                target_df.at[idx, field] = val
        
        # ОБЯЗАТЕЛЬНО: Синхронизируем товары, чтобы они не были EMPTY
        st.session_state.items_registry[entry_id] = updated_items
        
        st.success("✅ Акт брака успешно обновлен!")
        time.sleep(1)
        st.rerun()
        
@st.dialog("🔍 Просмотр Акта брака", width="large")
def show_defect_details_modal(defect_id):
    df = st.session_state.defects
    row_match = df[df['id'] == defect_id]
    
    if row_match.empty:
        st.error("Акт не найден")
        return
        
    row = row_match.iloc[0]
    st.error(f"### 📑 АКТ ДЕФЕКТОВКИ №{defect_id}")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Статус", row.get('Статус', 'Н/Д'))
    c2.metric("Виновник", row.get('Виновник', 'Н/Д'))
    c3.metric("Тип", row.get('Тип дефекта', 'Н/Д'))

    st.markdown("---")
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(f"**📦 Основной товар:** {row.get('Товар')}")
        st.markdown(f"**🔢 Кол-во брака:** {row.get('Кол-во брака')}")
        st.markdown(f"**🔗 Основание (ID):** {row.get('Связь с документом')}")
    with col_b:
        st.markdown(f"**📍 Адрес хранения:** `{row.get('Адрес хранения')}`")
        st.markdown(f"**📅 Создан:** {row.get('Дата создания')}")
        st.markdown(f"**⚖️ Решение:** {row.get('Решение', 'Не принято')}")

    st.divider()
    st.markdown("#### 📦 Состав акта")
    
    # ИСПРАВЛЕНИЕ: Проверяем наличие товаров в реестре
    if defect_id in st.session_state.items_registry:
        items = st.session_state.items_registry[defect_id]
        if not items.empty:
            st.dataframe(items, use_container_width=True)
        else:
            st.warning("В спецификации товаров нет данных.")
    else:
        st.info("Реестр товаров для этого акта еще не сформирован.")

    if st.button("❌ ЗАКРЫТЬ", use_container_width=True):
        st.rerun()
        
@st.dialog("🖨️ Печать Акта о браке", width="large")
def show_defect_print_modal(defect_id):
    row = st.session_state.defects[st.session_state.defects['id'] == defect_id].iloc[0]
    items_df = st.session_state.items_registry.get(defect_id, pd.DataFrame())
    
    # Генерируем красивую HTML таблицу
    items_html = items_df.to_html(index=False, border=1) if not items_df.empty else "Нет данных о товарах"

    full_html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Arial; padding: 20px; }}
            .act-border {{ border: 4px double #d32f2f; padding: 20px; }}
            .header {{ text-align: center; color: #d32f2f; text-transform: uppercase; }}
            .info-table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
            .info-table td {{ padding: 8px; border-bottom: 1px solid #eee; }}
            .data-table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
            .data-table th {{ background: #f8f8f8; padding: 10px; border: 1px solid #333; }}
            .data-table td {{ padding: 10px; border: 1px solid #333; }}
            .footer {{ margin-top: 40px; display: flex; justify-content: space-between; }}
            .stamp {{ border: 2px solid #0000FF; color: #0000FF; width: 150px; height: 60px; 
                      text-align: center; border-radius: 50%; opacity: 0.5; font-size: 10px; padding-top: 15px; }}
            @media print {{ .no-print {{ display: none; }} }}
        </style>
    </head>
    <body>
        <button class="no-print" onclick="window.print()" style="width:100%; padding:15px; background:#d32f2f; color:white; border:none; margin-bottom:20px;">ПЕЧАТАТЬ АКТ №{defect_id}</button>
        <div class="act-border">
            <div class="header">
                <h1>Акт о выявленных дефектах №{defect_id}</h1>
                <p>IMPERIA WMS | ОТДЕЛ КОНТРОЛЯ КАЧЕСТВА</p>
            </div>
            <table class="info-table">
                <tr><td><b>Дата составления:</b> {row.get('Дата создания')}</td><td><b>Статус:</b> {row.get('Статус')}</td></tr>
                <tr><td><b>Виновная сторона:</b> {row.get('Виновник')}</td><td><b>Тип дефекта:</b> {row.get('Тип дефекта')}</td></tr>
                <tr><td><b>Товар:</b> {row.get('Товар')}</td><td><b>Адрес хранения:</b> {row.get('Адрес хранения')}</td></tr>
                <tr><td colspan="2"><b>Связь с документом основания:</b> {row.get('Связь с документом')}</td></tr>
                <tr><td colspan="2"><b>Итоговое решение комиссии:</b> {row.get('Решение')}</td></tr>
            </table>
            
            <h3>Спецификация поврежденного имущества:</h3>
            <div class="data-table">
                {items_html}
            </div>

            <div class="footer">
                <div>Сдал (Водитель/Поставщик): ___________</div>
                <div>Принял (Кладовщик): ___________</div>
                <div class="stamp">ОТДЕЛ ПРИЕМКИ<br>БРАК ВЫЯВЛЕН</div>
            </div>
        </div>
    </body>
    </html>
    """
    st.components.v1.html(full_html, height=800, scrolling=True)