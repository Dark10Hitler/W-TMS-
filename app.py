import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from streamlit_option_menu import option_menu
import uuid
import time
import io
import folium
from streamlit_folium import st_folium
import plotly.express as px
import seaborn as sns
import matplotlib.pyplot as plt
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode, JsCode
import streamlit.components.v1 as components
import os
import plotly.graph_objects as go
from constants import WAREHOUSE_MAP, TABLE_STRUCT, DRIVER_COLUMNS, VEHICLE_COLUMNS, NOMENCLATURE_COLUMNS
from constants import ORDER_COLUMNS, ARRIVAL_COLUMNS, EXTRA_COLUMNS, DEFECT_COLUMNS, MAIN_COLUMNS
from config import edit_arrival_modal, edit_defect_modal, edit_extra_modal, edit_order_modal
from config import show_extra_details_modal, show_arrival_details_modal, show_defect_details_modal, show_order_details_modal
from config import show_arrival_print_modal, show_defect_print_modal, show_extra_print_modal, show_print_modal
from config_topology import get_warehouse_figure
from specific_doc import create_modal, create_extras_modal, create_arrival_modal, create_defect_modal, create_driver_modal, create_vehicle_modal
from specific_doc import edit_vehicle_modal, edit_driver_modal
import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
from streamlit_autorefresh import st_autorefresh
from supabase import create_client, Client

@st.cache_resource
def init_connection():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

supabase = init_connection()

def save_to_supabase(table_name, data_dict):
    try:
        # .insert() принимает обычный словарь Python
        response = supabase.table(table_name).insert(data_dict).execute()
        return True, response
    except Exception as e:
        st.error(f"🚨 Ошибка Supabase: {e}")
        return False, None

# --- НАСТРОЙКИ TRACCAR ---
TRACCAR_URL = "http://localhost:8082" 
TRACCAR_AUTH = ("denis.masliuc.speak23dev@gmail.com", "qwert12345")

def get_detailed_traccar_data(endpoint="positions", params=None):
    """
    Универсальная функция для Traccar API.
    Если endpoint='positions', возвращает (devices, positions) для карты.
    Если endpoint='reports/route', возвращает список точек для Аналитики.
    """
    try:
        if endpoint == "positions":
            dev_resp = requests.get(f"{TRACCAR_URL}/api/devices", auth=TRACCAR_AUTH, timeout=5)
            pos_resp = requests.get(f"{TRACCAR_URL}/api/positions", auth=TRACCAR_AUTH, timeout=5)
            
            if dev_resp.status_code == 200 and pos_resp.status_code == 200:
                devices = {d['id']: d for d in dev_resp.json()}
                return devices, pos_resp.json()
            return {}, []
        
        else:
            # Логика для запроса истории (Аналитика)
            resp = requests.get(f"{TRACCAR_URL}/api/{endpoint}", auth=TRACCAR_AUTH, params=params, timeout=10)
            if resp.status_code == 200:
                return resp.json()
            else:
                st.error(f"Ошибка API ({resp.status_code}): {resp.text}")
                return []
                
    except Exception as e:
        st.error(f"⚠️ Ошибка связи с Traccar: {e}")
        return {}, [] if endpoint == "positions" else []

# Путь к "памяти" системы
DB_PATH = "catalog_locations.csv"

def get_full_inventory_df():
    """Собирает актуальные данные: синхронизирует правки из реестра с базой"""
    all_items = []
    
    # Итерируемся по всем заказам (Заявки, Приходы и т.д.)
    for _, order in st.session_state.main.iterrows():
        order_id = order['id']
        
        # Ключевой момент: берем данные напрямую из items_registry, 
        # где они сохраняются после нажатия "ПРИВЯЗАТЬ МЕСТО"
        if order_id in st.session_state.items_registry:
            items_df = st.session_state.items_registry[order_id].copy()
            
            # Убираем строку TOTAL сразу при сборке
            items_df = items_df[items_df['Название товара'].str.upper() != 'TOTAL']
            
            # Привязываем актуальные данные из "родительской" заявки
            items_df['ID Документа'] = order_id
            items_df['Дата операции'] = order.get('Дата создания', '-')
            items_df['Статус заявки'] = order.get('Статус', 'ОЖИДАНИЕ')
            items_df['Клиент/Контрагент'] = order.get('Клиент', '-')
            items_df['Водитель/ТС'] = f"{order.get('Водитель', '-')} / {order.get('ТС (Госномер)', '-')}"
            
            all_items.append(items_df)
    
    if not all_items:
        return pd.DataFrame()
    
    return pd.concat(all_items, ignore_index=True)
 
def get_saved_location(product_name):
    """Ищет, где этот товар лежал раньше (из локальной базы)"""
    if os.path.exists(DB_PATH):
        df = pd.read_csv(DB_PATH)
        match = df[df['product'] == product_name]
        return match.iloc[0]['address'] if not match.empty else "НЕИЗВЕСТНО"
    return "НЕИЗВЕСТНО"

def save_new_location(product_name, location):
    """Запоминает выбор оператора для будущих заявок"""
    new_loc = pd.DataFrame([{"product": product_name, "address": location}])
    if os.path.exists(DB_PATH):
        df_base = pd.read_csv(DB_PATH)
        # Убираем старую запись, если была, и добавляем новую
        df_base = pd.concat([df_base[df_base['product'] != product_name], new_loc])
        df_base.to_csv(DB_PATH, index=False)
    else:
        new_loc.to_csv(DB_PATH, index=False)

st.set_page_config(layout="wide", page_title="IMPERIA LOGISTICS SYSTEM", page_icon="🏢")

st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #FFFFFF; }
    [data-testid="stSidebar"] { background-color: #161B22 !important; border-right: 1px solid #30363D; }
    .block-container { padding-top: 1.5rem; }
    
    /* Карточки метрик */
    div[data-testid="stMetric"] {
        background-color: #161B22;
        border: 1px solid #30363D;
        border-radius: 12px;
        padding: 20px;
    }

    /* Кнопки */
    .stButton>button {
        border-radius: 8px;
        font-weight: 600;
        background: linear-gradient(90deg, #FF4B4B 0%, #FF2B2B 100%);
        color: white;
        border: none;
        transition: 0.3s;
    }
    
    /* Таблицы AgGrid */
    .ag-theme-alpine-dark {
        --ag-background-color: #161B22;
        --ag-header-background-color: #0D1117;
        --ag-border-color: #30363D;
    }
</style>
""", unsafe_allow_html=True)

if "items_registry" not in st.session_state:
    st.session_state.items_registry = {}  # {order_id: pd.DataFrame(товары)}

MIN_LOAD_FACTOR = 0.3  # 30% минимум (если меньше 70% пусто - орем)

for table_name, cols in TABLE_STRUCT.items():
    if table_name not in st.session_state:
        st.session_state[table_name] = pd.DataFrame(columns=cols)

if "profile_data" not in st.session_state:
    st.session_state.profile_data = pd.DataFrame([
        {"Поле": "ФИО", "Значение": "Иванов Иван Иванович"},
        {"Поле": "Должность", "Значение": "Главный Логист / CEO"},
        {"Поле": "Телефон", "Значение": "+7 (999) 000-00-00"},
        {"Поле": "Email", "Значение": "admin@logistics-empire.ru"},
        {"Поле": "Опыт", "Значение": "15 лет в управлении"}
    ])

if "active_modal" not in st.session_state: st.session_state.active_modal = None

def generate_id(): return str(uuid.uuid4())[:8]

def init_table(name, columns):
    if name not in st.session_state:
        st.session_state[name] = pd.DataFrame(columns=columns)

tables = {
    "main": MAIN_COLUMNS,
    "orders": ORDER_COLUMNS,
    "arrivals": ARRIVAL_COLUMNS,
    "defects": DEFECT_COLUMNS,
    "extras": EXTRA_COLUMNS, # Убедись, что EXTRA_COLUMNS импортирован из constants
    "drivers": ["id", "Фамилия", "Имя", "Телефон", "Статус", "Фото", "Категории", "Стаж"],
    "vehicles": ["id", "Марка", "Госномер", "Тип", "Объем", "Грузоподъемность", "Паллеты", "Статус", "Фото", "ТО", "Страховка"]
}

for table, cols in tables.items():
    init_table(table, cols)

# Заполнение профиля по умолчанию
if st.session_state.profile_data.empty:
    st.session_state.profile_data = pd.DataFrame([
        {"Поле": "ФИО", "Значение": "Иванов Иван Иванович"},
        {"Поле": "Должность", "Значение": "Главный Логист / CEO"},
        {"Поле": "Телефон", "Значение": "+7 (999) 000-00-00"},
        {"Поле": "Email", "Значение": "admin@logistics-empire.ru"},
        {"Поле": "Опыт", "Значение": "15 лет в управлении цепями поставок"}
    ])

if "active_modal" not in st.session_state: st.session_state.active_modal = None

def generate_id(): return str(uuid.uuid4())[:8]

def calculate_load_efficiency(df_items, vehicle_volume):
    """
    Математика точности:
    Считает суммарный объем товаров и сравнивает с объемом ТС.
    """
    if vehicle_volume <= 0:
        return 0, "⚠️ Не указан объем ТС"
    
    # Предположим, в df_items есть колонки: Длина, Ширина, Высота, Кол-во
    # Или уже готовый Объем (м3)
    total_volume = df_items["Объем (м3)"].sum()
    efficiency = (total_volume / vehicle_volume) * 100
    
    status_msg = ""
    if efficiency < 30: # Если пустого места > 70%
        status_msg = f"🚫 КРИТИЧЕСКИЙ НЕДОГРУЗ! Занято всего {efficiency:.1f}%. Везете воздух!"
    else:
        status_msg = f"✅ Загрузка в норме: {efficiency:.1f}%"
        
    return efficiency, status_msg

# 1. Добавляем JS-рендеры для иконок (вставить перед render_aggrid_table)
# Рендерер для кнопки просмотра внутри таблицы
render_view_button = JsCode("""
    function(params) {
        return '<button style="background-color: #58A6FF; color: white; border: none; border-radius: 50px;">🔍 Обзор</button>';
    }
""")

# 2. ПОЛНОСТЬЮ ОБНОВЛЕННАЯ ФУНКЦИЯ ТАБЛИЦЫ
def render_aggrid_table(table_key, title):
    # --- 1. СТИЛИЗАЦИЯ ---
    st.markdown("""
        <style>
            .reportview-container .main .block-container { padding-top: 2rem; }
            .stButton>button { 
                width: 100%; 
                border-radius: 55px; 
                height: 3.2em; 
                text-transform: uppercase; 
                font-weight: bold; 
                margin-top: 18px; 
                border: 1px solid rgba(255, 255, 255, 0.2); 
            }
            .ag-header-cell-label { font-weight: bold; text-transform: uppercase; font-size: 12px; }
            .ag-theme-alpine { margin-top: 10px; border: 1px solid #30363d !important; }
        </style>
    """, unsafe_allow_html=True)

    # --- 2. ПОДГОТОВКА ДАННЫХ ---
    if table_key not in st.session_state:
        st.session_state[table_key] = pd.DataFrame(columns=TABLE_STRUCT.get(table_key, []))
    
    df = st.session_state[table_key].copy()
   
    c_title, c_act1 = st.columns([8, 2])
    c_title.markdown(f"### 🚀 {title} <span style='font-size: 0.6em; color: gray;'>({len(df)} зап.)</span>", unsafe_allow_html=True)
    
    if table_key != "main":
        if c_act1.button("➕ ДОБАВИТЬ", key=f"btn_add_{table_key}", use_container_width=True):
            st.session_state.active_modal = table_key
            st.rerun()
    else:
        c_act1.info("🔍 Только просмотр")

    # --- 3. НАСТРОЙКА AGGRID ---
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_default_column(
        resizable=True, sortable=True, filterable=True, 
        floatingFilter=True, filter="agTextColumnFilter", minWidth=120
    )

    if "Секция" in df.columns:
        section_style = JsCode("""
        function(params) {
            if (params.value === 'ПРИХОД') return {'color': 'white', 'backgroundColor': '#2E7D32', 'fontWeight': 'bold'};
            if (params.value === 'ЗАЯВКА') return {'color': 'white', 'backgroundColor': '#1565C0', 'fontWeight': 'bold'};
            if (params.value === 'ДОПОЛНЕНИЕ') return {'color': 'black', 'backgroundColor': '#FFB300', 'fontWeight': 'bold'};
            return null;
        }
        """)
        gb.configure_column("Секция", cellStyle=section_style, pinned='left', width=150)
          
    gb.configure_column("id", header_name="ID", pinned='left', width=100)
    
    numeric_cols = ["Кол-во позиций", "Общий объем (м3)", "Сумма заявки"]
    for col in numeric_cols:
        if col in df.columns:
            gb.configure_column(col, filter="agNumberColumnFilter")

    gb.configure_selection(selection_mode="single", use_checkbox=False)
    gridOptions = gb.build()

    # --- 4. РЕНДЕРИНГ ---
    grid_response = AgGrid(
        df,
        gridOptions=gridOptions,
        height=550,
        theme='alpine',
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        allow_unsafe_jscode=True,
        key=f"grid_stable_{table_key}"
    )

    # --- 5. ЛОГИКА ВЫБОРА И КНОПКИ ---
    # Исправлено: берем данные из grid_response
    selected_rows = grid_response.selected_rows

    # Проверка на наличие выбора (универсально для разных версий AgGrid)
    has_selection = False
    selected_row = None

    if selected_rows is not None:
        if isinstance(selected_rows, pd.DataFrame):
            if not selected_rows.empty:
                has_selection = True
                selected_row = selected_rows.iloc[0]
        elif isinstance(selected_rows, list) and len(selected_rows) > 0:
            has_selection = True
            selected_row = selected_rows[0]

    if has_selection:
        row_id = selected_row["id"]
        st.session_state.editing_id = row_id # Сохраняем в стейт на всякий случай

        with st.container():
            st.markdown("---")
            col_actions = st.columns([1.2, 1.2, 1.2, 4])
            
            # --- КНОПКИ ДЕЙСТВИЙ ---
            if col_actions[0].button("⚙️ ИЗМЕНИТЬ", key=f"edit_btn_{table_key}", use_container_width=True):
                if table_key == "orders": edit_order_modal(row_id)
                elif table_key == "arrivals": edit_arrival_modal(row_id)
                elif table_key == "extras": edit_extra_modal(row_id)
                elif table_key == "defects": edit_defect_modal(row_id)
                else: edit_order_modal(table_key, row_id)
            
            if col_actions[1].button("🔍 ПРОСМОТР", key=f"view_act_{table_key}", use_container_width=True):
                if table_key == "orders": show_order_details_modal(row_id)
                elif table_key == "arrivals": show_arrival_details_modal(row_id)
                elif table_key == "extras": show_extra_details_modal(row_id)
                elif table_key == "defects": show_defect_details_modal(row_id)
                else: st.warning("Детальный просмотр недоступен")

            if col_actions[2].button("🖨️ ПЕЧАТЬ", key=f"print_act_{table_key}", use_container_width=True):
                if table_key == "orders": show_print_modal(row_id)
                elif table_key == "arrivals": show_arrival_print_modal(row_id)
                elif table_key == "extras": show_extra_print_modal(row_id)
                elif table_key == "defects": show_defect_print_modal(row_id)
    else:
        st.info("💡 Выберите строку в таблице выше, чтобы активировать кнопки управления")
     
def save_doc(key, name, qty, price, client, tc, driver):
    new_id = generate_id()
    new_row = {
        "📝 Ред.": False, 
        "id": new_id, 
        "Название товара": name, 
        "Количество": qty, 
        "Цена": price, 
        "Клиент": client, 
        "Адрес клиента": "Из БД...", 
        "Телефон": "Из БД...", 
        "Адрес загрузки": "Склад №1",
        "ТС": tc, 
        "Водитель": driver, 
        "Дата создания": datetime.now().strftime("%Y-%m-%d %H:%M"), 
        "🖨️ Печать": False
    }
    
    new_df = pd.DataFrame([new_row])
    
    # Сохраняем в целевую таблицу (например, "Приходы")
    st.session_state[key] = pd.concat([st.session_state[key], new_df], ignore_index=True)
    
    # Дублируем в Main (если мы не в самом Main)
    if key != "defects" and key != "main":
        # Создаем копию для Main
        section_names = {"orders": "ЗАЯВКА", "arrivals": "ПРИХОД", "extras": "ДОПОЛНЕНИЕ"}
        
        # Сразу собираем словарь так, чтобы "Секция" была первой
        main_data = {
            "Секция": section_names.get(key, "ПРОЧЕЕ"),
            **new_row # Распаковываем остальные поля
        }
        
        main_df = pd.DataFrame([main_data])
        st.session_state["main"] = pd.concat([st.session_state["main"], main_df], ignore_index=True)
    
    st.session_state.active_modal = None
    st.success(f"Запись {new_id} добавлена в {key} и Main!")
    time.sleep(1)
    st.rerun()

def show_dashboard():
    st.title("📊 Центр Управления")
    
    df_main = st.session_state.main
    df_defects = st.session_state.get('defects', pd.DataFrame())
    df_extras = st.session_state.get('extras', pd.DataFrame())

    # --- 1. ВЕРХНИЕ МЕТРИКИ (Оперативная сводка) ---
    m1, m2, m3, m4 = st.columns(4)
    
    m1.metric("Всего документов", len(df_main))
    
    # Активные водители
    active_drivers = len(st.session_state.drivers)
    m2.metric("Драйверы в системе", active_drivers, help="Количество зарегистрированных ТС")
    
    # Считаем брак (вместо оборотов)
    defect_count = len(df_defects)
    m3.metric("Акты брака", defect_count, delta=f"{defect_count} инц.", delta_color="inverse")
    
    # Считаем корректировки/догрузы
    extra_count = len(df_extras)
    m4.metric("Корректировки", extra_count, help="Количество догрузов и возвратов")

    st.divider()

    # --- 2. АНАЛИЗ АКТИВНОСТИ (Когда формируются документы) ---
    st.subheader("🕒 Анализ ритмичности: Пики создания документов")
    
    if not df_main.empty and "Время создания" in df_main.columns:
        # Подготовка данных для графика
        df_time = df_main.copy()
        # Извлекаем час для группировки
        df_time['Час'] = pd.to_datetime(df_time['Время создания'], format='%H:%M', errors='coerce').dt.hour
        
        # Группируем по часам
        hourly_activity = df_time.groupby('Час').size().reset_index(name='Количество')
        
        # Строим график
        fig_time = px.line(
            hourly_activity, 
            x='Час', 
            y='Количество',
            markers=True,
            title="Активность формирования заказов по часам",
            template="plotly_dark",
            color_discrete_sequence=['#00f2ff']
        )
        fig_time.update_layout(xaxis=dict(tickmode='linear', tick0=0, dtick=1))
        st.plotly_chart(fig_time, use_container_width=True)
        
        # Инсайт
        if not hourly_activity.empty:
            peak_hour = hourly_activity.loc[hourly_activity['Количество'].idxmax(), 'Час']
            st.info(f"💡 **Аналитический инсайт:** Пик нагрузки приходится на **{peak_hour}:00**. В это время рекомендуется усилить смену на приемке/отгрузке.")
    else:
        st.warning("Недостаточно данных о времени для анализа активности.")

    st.divider()

    # --- 3. РАСПРЕДЕЛЕНИЕ ПО СТАТУСАМ И ИНТЕРЕСНЫЙ АНАЛИЗ ---
    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.subheader("📈 Состояние процессов")
        if not df_main.empty and "Статус" in df_main.columns:
            status_counts = df_main['Статус'].value_counts().reset_index()
            status_counts.columns = ['Статус', 'Кол-во']
            
            fig_status = px.pie(
                status_counts, 
                values='Кол-во', 
                names='Статус', 
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            st.plotly_chart(fig_status, use_container_width=True)
        else:
            st.write("Нет данных по статусам.")

    with col_right:
        st.subheader("🏆 Топ Контрагентов")
        if not df_main.empty and "Клиент" in df_main.columns:
            top_clients = df_main['Клиент'].value_counts().head(5).reset_index()
            top_clients.columns = ['Клиент', 'Заказов']
            
            fig_clients = px.bar(
                top_clients, 
                x='Заказов', 
                y='Клиент', 
                orientation='h',
                title="ТОП-5 по объему документов",
                color='Заказов',
                color_continuous_scale='Viridis'
            )
            st.plotly_chart(fig_clients, use_container_width=True)
        else:
            st.write("Нет данных о клиентах.")

    # --- 4. "ФИШКА": ПУЛЬС СКЛАДА ---
    st.divider()
    st.subheader("🔥 Пульс склада (Срочность)")
    
    # Считаем документы, созданные сегодня
    today_str = datetime.now().strftime("%d.%m.%Y")
    today_docs = len(df_main[df_main['Дата создания'] == today_str]) if "Дата создания" in df_main.columns else 0
    
    c_pulse1, c_pulse2, c_pulse3 = st.columns(3)
    
    with c_pulse1:
        st.write("Документов сегодня:")
        st.title(f" {today_docs}")
        
    with c_pulse2:
        # Процент "Зависших" (Ожидание более какого-то времени - упрощенно)
        waiting_pct = (len(df_main[df_main['Статус'] == "ОЖИДАНИЕ"]) / len(df_main) * 100) if len(df_main) > 0 else 0
        st.write("Доля в ожидании:")
        st.title(f" {waiting_pct:.1f}%")

    with c_pulse3:
        # "Коэффициент брака"
        defect_rate = (len(df_defects) / len(df_main) * 100) if len(df_main) > 0 else 0
        st.write("Коэффициент рекламаций:")
        st.title(f" {defect_rate:.1f}%")

def show_map():
    st.title("🛰️ Оперативный штаб: Глобальный мониторинг")
    
    # Автообновление раз в 15 секунд
    st_autorefresh(interval=15000, key="detailed_osm_map_refresh")
    
    try:
        devices, positions = get_detailed_traccar_data()
    except:
        st.error("Ошибка получения данных из Traccar")
        return

    # Настройка карты (Цветная OSM)
    base_coords = [47.776654, 27.913643]
    m = folium.Map(location=base_coords, zoom_start=12, tiles="OpenStreetMap")
    
    # --- ВИЗУАЛИЗАЦИЯ ГЕОЗОНЫ (500м) ---
    folium.Circle(
        location=base_coords,
        radius=500,
        color='red',
        weight=2,
        fill=True,
        fill_color='red',
        fill_opacity=0.1,
        popup="ГЕОЗОНА: ЦЕНТРАЛЬНЫЙ СКЛАД"
    ).add_to(m)

    folium.Marker(
        base_coords, 
        popup="<b>🏢 ГЛАВНЫЙ СКЛАД IMPERIA</b>", 
        icon=folium.Icon(color="darkred", icon="warehouse", prefix="fa")
    ).add_to(m)

    active, stopped, low_power = 0, 0, 0
    at_base_list = []

    for pos in positions:
        dev_id = pos.get('deviceId')
        if dev_id not in devices: continue
            
        dev = devices[dev_id]
        v_name = dev.get('name')
        
        # --- БЕЗОПАСНЫЙ ПОИСК ДАННЫХ (Защита от KeyError) ---
        v_reg = st.session_state.vehicles
        d_reg = st.session_state.drivers
        
        # Поиск ТС
        v_row = v_reg[v_reg['Марка'] == v_name] if 'Марка' in v_reg.columns else pd.DataFrame()
        v_data = v_row.iloc[0].to_dict() if not v_row.empty else {}
        
        # Поиск Водителя (Авто-определение колонки связи)
        d_link = next((c for c in ['ТС', 'Транспорт', 'Машина', 'Автомобиль'] if c in d_reg.columns), None)
        d_row = d_reg[d_reg[d_link] == v_name] if d_link and not d_reg.empty else pd.DataFrame()
        d_data = d_row.iloc[0].to_dict() if not d_row.empty else {}

        # Параметры трекера
        attrs = pos.get('attributes', {})
        batt = attrs.get('batteryLevel', 0)
        charging = attrs.get('charge', False)
        if isinstance(batt, (int, float)) and batt < 20: low_power += 1

        # Логистика
        speed = round(pos.get('speed', 0) * 1.852, 1)
        lat, lon = pos.get('latitude'), pos.get('longitude')
        total_km = round(attrs.get('totalDistance', 0) / 1000, 1)
        
        from geopy.distance import geodesic
        dist_to_base = round(geodesic((lat, lon), base_coords).km, 1)

        # Проверка геозоны
        is_at_base = dist_to_base <= 0.5
        if is_at_base: at_base_list.append(v_name)

        # Расчет ETA
        if speed > 5:
            eta_m = int((dist_to_base / speed) * 60)
            eta_t = (datetime.now() + timedelta(minutes=eta_m)).strftime("%H:%M")
        else:
            eta_t = "На базе" if is_at_base else "Стоянка"

        # Визуал маркера
        color, status = ("green", "В ПУТИ") if speed > 3 else ("blue", "СТОЯНКА")
        if speed > 3: active += 1
        else: stopped += 1

        # --- СУПЕР-HTML КАРТОЧКА ---
        popup_html = f"""
        <div style="width: 320px; font-family: 'Segoe UI', Arial; border-radius: 10px; overflow: hidden; border: 1px solid #ccc;">
            <div style="background: {'#2ecc71' if speed > 3 else '#3498db'}; color:white; padding:12px;">
                <b style="font-size:16px;">🚛 {v_name}</b><br>
                <small>{status} | {v_data.get('Госномер', 'Нет номера')}</small>
            </div>
            <div style="padding:12px; font-size:12px; background: #fff; line-height: 1.5;">
                <p style="margin-bottom:8px;"><b>👤 Водитель:</b> {d_data.get('Фамилия', 'Не назначен')} {d_data.get('Имя', '')}<br>
                <b>📞 Тел:</b> {d_data.get('Телефон', 'Нет данных')}</p>
                
                <table style="width:100%; border-collapse: collapse;">
                    <tr style="border-bottom: 1px solid #eee;"><td>📦 Грузопод.:</td><td align="right">{v_data.get('Грузоподъемность', 'Н/Д')} кг</td></tr>
                    <tr style="border-bottom: 1px solid #eee;"><td>🚀 Скорость:</td><td align="right" style="color:red; font-weight:bold;">{speed} км/ч</td></tr>
                    <tr style="border-bottom: 1px solid #eee;"><td>📍 До базы:</td><td align="right">{dist_to_base} км {'🚩' if is_at_base else ''}</td></tr>
                    <tr style="border-bottom: 1px solid #eee;"><td>⏱ Прибудет:</td><td align="right" style="color:blue; font-weight:bold;">{eta_t}</td></tr>
                </table>
                
                <div style="margin-top: 10px; padding: 8px; background: #f9f9f9; border-radius: 5px; font-size: 11px;">
                    <b>📱 Смартфон:</b> {batt}% {'(⚡ Зарядка)' if charging else ''}<br>
                    <b>🛣 Одометр:</b> {total_km} км | <b>🛰 Спутники:</b> {attrs.get('sat', 'н/д')}
                </div>
            </div>
        </div>
        """

        folium.Marker(
            [lat, lon],
            popup=folium.Popup(popup_html, max_width=350),
            tooltip=f"{v_name} ({speed} км/ч)",
            icon=folium.Icon(color=color, icon="truck", prefix="fa")
        ).add_to(m)

    # --- ВЕРХНЯЯ ПАНЕЛЬ МЕТРИК ---
    m1, m2, m3, m4, m5 = st.columns([1, 1, 1, 1, 2])
    m1.metric("В движении", active)
    m2.metric("На паузе", stopped)
    m3.metric("Заряд < 20%", low_power, delta_color="inverse")
    m4.metric("Обновлено", datetime.now().strftime("%H:%M:%S"))
    
    with m5:
        with st.expander(f"🚩 НА ТЕРРИТОРИИ БАЗЫ ({len(at_base_list)})"):
            if at_base_list:
                for car in at_base_list:
                    st.success(f"🚚 {car} — В зоне разгрузки")
            else:
                st.write("Машин на территории нет")

    st_folium(m, width=1300, height=700)
    
def show_profile():
    st.markdown("<h1 class='no-print'>👤 Личный кабинет / Карточка Сотрудника</h1>", unsafe_allow_html=True)
    col1, col2 = st.columns([1, 2])
    with col1:
        st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=200)
        if st.button("🖨️ ПЕЧАТЬ CV / ПРОФИЛЯ"):
            st.markdown('<script>window.print();</script>', unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="cv-card">
            <h1 style="color: #58A6FF;">{st.session_state.profile_data.iloc[0]['Значение']}</h1>
            <h3>{st.session_state.profile_data.iloc[1]['Значение']}</h3>
            <hr>
            <p><b>📞 Телефон:</b> {st.session_state.profile_data.iloc[2]['Значение']}</p>
            <p><b>📧 Email:</b> {st.session_state.profile_data.iloc[3]['Значение']}</p>
            <p><b>💼 Опыт:</b> {st.session_state.profile_data.iloc[4]['Значение']}</p>
        </div>
        """, unsafe_allow_html=True)
        
    st.markdown("### Редактировать данные профиля")
    st.session_state.profile_data = st.data_editor(st.session_state.profile_data, use_container_width=True)
    
with st.sidebar:
    st.markdown("### 📦 IMPERIA WMS")
    selected = option_menu(
        menu_title="Навигация",
        options=[
            "Dashboard", "База Данных", "Main", "Заявки", "Приходы", 
            "Дополнения", "Брак", "Водители", "ТС", "Карта", 
            "Аналитика", "Личный кабинет", "Настройки" # Добавили Аналитику
        ],
        icons=[
            "grid-1x2", "database-fill", "table", "cart-check", "box-seam", 
            "plus-square", "shield-slash", "person-vcard", "truck", "map", 
            "bar-chart-line", "person-circle", "gear-wide-managed" # Иконка графика
        ],
        menu_icon="house-door",
        default_index=0,
        styles={
            "container": {"padding": "5!important", "background-color": "#0e1117"},
            "icon": {"color": "#faaa1d", "font-size": "18px"},
            "nav-link": {"font-size": "14px", "text-align": "left", "margin": "0px", "--hover-color": "#262730"},
            "nav-link-selected": {"background-color": "#ff4b4b"},
        }
    )
    
def delete_entry(table_key, entry_id):
    st.session_state[table_key] = st.session_state[table_key][st.session_state[table_key]['id'] != entry_id]
    st.toast(f"Запись {entry_id} удалена")
    time.sleep(0.5)
    st.rerun()
    
if selected == "Dashboard": show_dashboard()
elif selected == "Main": render_aggrid_table("main", "Основной Реестр")
elif selected == "Заявки": render_aggrid_table("orders", "Заявки")
elif selected == "Приходы": render_aggrid_table("arrivals", "Приходы")
elif selected == "Брак": render_aggrid_table("defects", "Журнал Брака")
elif selected == "Дополнения": render_aggrid_table("extras", "Дополнения")
# --- РАЗДЕЛ ВОДИТЕЛИ ---
elif selected == "Водители":
    st.markdown("<h1 class='section-head'>👨‍✈️ Реестр водителей</h1>", unsafe_allow_html=True)
    
    col_btn, col_search = st.columns([1, 2])
    if col_btn.button("➕ ДОБАВИТЬ ВОДИТЕЛЯ", type="primary", use_container_width=True):
        st.session_state.active_modal = "drivers_new"
        st.rerun()

    search = col_search.text_input("🔍 Поиск по фамилии...", placeholder="Введите фамилию")

    # Фильтрация данных
    df_drivers = st.session_state.drivers
    if search:
        df_drivers = df_drivers[df_drivers['Фамилия'].str.contains(search, case=False)]

    st.divider()

    if not df_drivers.empty:
        # Создаем сетку из 3 колонок
        cols = st.columns(3)
        
        for idx, (i, row) in enumerate(df_drivers.iterrows()):
            # Размещаем карточку в нужную колонку
            with cols[idx % 3]:
                # Используем container с границей, чтобы кнопки были визуально внутри карточки
                with st.container(border=True):
                    # 1. Визуальная часть (HTML)
                    img_url = row['Фото'] if row['Фото'] else "https://cdn-icons-png.flaticon.com/512/3135/3135715.png"
                    
                    st.markdown(f"""
                    <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 15px;">
                        <img src="{img_url}" style="width: 50px; height: 50px; border-radius: 50%; object-fit: cover; border: 2px solid #58A6FF;">
                        <div>
                            <h3 style="margin: 0; color: white; font-size: 1.1em; line-height: 1.2;">{row['Фамилия']}<br>{row['Имя']}</h3>
                            <span style="background-color: #238636; color: white; padding: 2px 8px; border-radius: 10px; font-size: 0.7em;">{row['Статус']}</span>
                        </div>
                    </div>
                    <div style="font-size: 0.85em; color: #8B949E; margin-bottom: 10px;">
                        <div style="margin-bottom: 4px;">📱 {row['Телефон']}</div>
                        <div style="margin-bottom: 4px;">🪪 Кат: <b>{row['Категории']}</b></div>
                        <div>📅 Стаж: {row['Стаж']} лет</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # 2. Кнопки управления (Streamlit)
                    # Размещаем кнопки в один ряд для компактности
                    c1, c2 = st.columns([1, 1])
                    
                    if c1.button("⚙️ Изм.", key=f"edit_dr_{row['id']}", use_container_width=True):
                        st.session_state.editing_id = row['id']
                        st.session_state.active_edit_modal = "drivers"
                        st.session_state.active_modal = None
                        st.rerun()
                        
                    if c2.button("🗑️", key=f"del_dr_{row['id']}", use_container_width=True):
                        st.session_state.drivers = st.session_state.drivers[st.session_state.drivers['id'] != row['id']]
                        st.rerun()
    else:
        st.info("Водители не найдены.")

# --- РАЗДЕЛ ТС ---
elif selected == "ТС":
    st.markdown("<h1 class='section-head'>🚛 Управление Автопарком</h1>", unsafe_allow_html=True)
    
    # Кнопка добавления нового ТС
    if st.button("➕ ДОБАВИТЬ НОВОЕ ТС", type="primary", use_container_width=True):
        st.session_state.active_modal = "vehicle_new"
        st.rerun()

    st.divider()

    df_v = st.session_state.vehicles
    if not df_v.empty:
        # Создаем сетку из 2 колонок (как у тебя в оригинале)
        cols = st.columns(2) 
        
        for idx, (i, row) in enumerate(df_v.iterrows()):
            with cols[idx % 2]:
                # Используем один общий контейнер с рамкой для всей карточки ТС
                with st.container(border=True):
                    # Если фото нет, используем иконку грузовика
                    veh_img = row['Фото'] if row['Фото'] else "https://cdn-icons-png.flaticon.com/512/2554/2554977.png"
                    
                    # 1. ВИЗУАЛЬНАЯ ЧАСТЬ (HTML)
                    st.markdown(f"""
                    <div style="position: relative; margin-bottom: 10px;">
                        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                            <div style="display: flex; gap: 15px;">
                                <img src="{veh_img}" style="width: 50px; height: 50px; object-fit: contain;">
                                <div>
                                    <h2 style="margin:0; color:#58A6FF; font-size: 1.2em;">{row['Госномер']}</h2>
                                    <p style="margin:0; color: gray; font-size: 0.85em;">{row['Марка']} • {row['Тип']}</p>
                                </div>
                            </div>
                            <div style="background: #238636; color: white; padding: 2px 10px; border-radius: 12px; font-size: 0.7em; font-weight: bold;">
                                {row['Статус']}
                            </div>
                        </div>
                        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; margin-top: 15px; text-align: center;">
                            <div style="background: #0D1117; padding: 6px; border-radius: 8px; border: 1px solid #30363D;">
                                <small style="color: gray; font-size: 0.7em;">Вес</small><br><b style="font-size: 0.8em;">{row.get('Грузоподъемность', 0)} кг</b>
                            </div>
                            <div style="background: #0D1117; padding: 6px; border-radius: 8px; border: 1px solid #30363D;">
                                <small style="color: gray; font-size: 0.7em;">Объем</small><br><b style="font-size: 0.8em;">{row.get('Объем', 0)} м³</b>
                            </div>
                            <div style="background: #0D1117; padding: 6px; border-radius: 8px; border: 1px solid #30363D;">
                                <small style="color: gray; font-size: 0.7em;">Паллеты</small><br><b style="font-size: 0.8em;">{row.get('Паллеты', 0)} шт</b>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    st.divider() # Небольшой разделитель перед кнопками

                    # 2. КНОПКИ УПРАВЛЕНИЯ (Streamlit)
                    vc1, vc2, vc3 = st.columns([1.5, 1.5, 0.8])
                    
                    if vc1.button("⚙️ Изменить", key=f"edit_v_btn_{row['id']}", use_container_width=True):
                        st.session_state.editing_id = row['id']
                        st.session_state.active_edit_modal = "vehicles"
                        st.session_state.active_modal = None
                        st.rerun()
                    
                    # Можно добавить кнопку сервиса, если нужно
                    if vc2.button("🛠️ Сервис", key=f"serv_v_{row['id']}", use_container_width=True):
                        st.toast(f"Запись ТС {row['Госномер']} на обслуживание")

                    if vc3.button("🗑️", key=f"del_v_{row['id']}", use_container_width=True):
                        st.session_state.vehicles = st.session_state.vehicles[st.session_state.vehicles['id'] != row['id']]
                        st.rerun()
    else:
        st.info("В автопарке пока нет автомобилей.")

elif selected == "Аналитика":
    st.title("🛡️ Logistics Intelligence & Tech Audit")
    
    # 1. Загрузка данных
    devices, _ = get_detailed_traccar_data()
    v_name = st.selectbox("🔍 Выберите ТС для глубокого анализа", options=[d['name'] for d in devices.values()])
    v_id = [id for id, d in devices.items() if d['name'] == v_name][0]

    col_t1, col_t2 = st.columns(2)
    start_date = col_t1.date_input("Начало анализа", datetime.now() - timedelta(days=1))
    end_date = col_t2.date_input("Конец анализа", datetime.now())

    if 'show_report' not in st.session_state:
        st.session_state.show_report = False

    if st.button("📑 СФОРМИРОВАТЬ ПОЛНЫЙ ИНЖЕНЕРНЫЙ ОТЧЕТ", type="primary"):
        st.session_state.show_report = True

    if st.session_state.show_report:
        params = {
            "deviceId": v_id, 
            "from": f"{start_date}T00:00:00Z", 
            "to": f"{end_date}T23:59:59Z"
        }
        
        with st.spinner('Инженерный отдел выполняет глубокий аудит систем...'):
            history = get_detailed_traccar_data("reports/route", params=params)
        
        if history and len(history) > 0:
            df = pd.DataFrame(history)
            df['dt'] = pd.to_datetime(df['deviceTime'])
            df['speed_kmh'] = df['speed'] * 1.852
            df['speed_diff'] = df['speed_kmh'].diff()
            
            # РАСЧЕТ БАЗОВЫХ ВЕЛИЧИН
            last_point = df.iloc[-1]
            actual_odo = last_point['attributes'].get('totalDistance', 0) / 1000 if 'attributes' in last_point else 0
            dist_start = df.iloc[0]['attributes'].get('totalDistance', 0) / 1000
            actual_dist = max(0, actual_odo - dist_start)
            
            total_time = (df.iloc[-1]['dt'] - df.iloc[0]['dt']).total_seconds() / 3600
            moving_df = df[df['speed_kmh'] > 3]
            work_hours = len(moving_df) / 60
            idle_hours = max(0, total_time - work_hours)

            # --- БЛОК 1: ПЛАНОВОЕ ТО ---
            st.subheader("🔧 Регламент технического обслуживания")
            
            regulations = [
                # --- ДВИГАТЕЛЬ И ТОПЛИВНАЯ СИСТЕМА ---
                {"part": "Масло ДВС и масляный фильтр", "limit": 10000},
                {"part": "Ремень ГРМ / Цепь (проверка)", "limit": 60000},
                {"part": "Ремень приводной (генератора)", "limit": 30000},
                {"part": "Ролики натяжные", "limit": 60000},
                {"part": "Воздушный фильтр", "limit": 15000},
                {"part": "Топливный фильтр (тонкой очистки)", "limit": 20000},
                {"part": "Топливный фильтр (грубой очистки)", "limit": 40000},
                {"part": "Свечи зажигания / Накала", "limit": 30000},
                {"part": "Промывка форсунок", "limit": 50000},
                {"part": "Регулировка клапанов", "limit": 40000},
                {"part": "Проверка герметичности впуска", "limit": 20000},
                {"part": "Чистка дроссельной заслонки", "limit": 30000},
                {"part": "Проверка опор двигателя", "limit": 50000},
                {"part": "Замер компрессии в цилиндрах", "limit": 100000},
                # --- ТРАНСМИССИЯ ---
                {"part": "Масло в КПП (МКПП/АКПП)", "limit": 80000},
                {"part": "Масло в заднем редукторе", "limit": 60000},
                {"part": "Сцепление (комплект)", "limit": 100000},
                {"part": "Крестовины карданного вала", "limit": 30000},
                {"part": "Подвесной подшипник кардана", "limit": 50000},
                {"part": "ШРУСы (проверка пыльников)", "limit": 20000},
                # --- ТОРМОЗНАЯ СИСТЕМА ---
                {"part": "Тормозные колодки передние", "limit": 25000},
                {"part": "Тормозные колодки задние", "limit": 45000},
                {"part": "Тормозные диски передние", "limit": 70000},
                {"part": "Тормозные диски/барабаны задние", "limit": 100000},
                {"part": "Тормозная жидкость", "limit": 40000},
                {"part": "Шланги тормозные (проверка)", "limit": 30000},
                {"part": "Трос стояночного тормоза", "limit": 50000},
                # --- ХОДОВАЯ И РУЛЕВОЕ УПРАВЛЕНИЕ ---
                {"part": "Амортизаторы (проверка)", "limit": 40000},
                {"part": "Сайлентблоки рычагов", "limit": 50000},
                {"part": "Шаровые опоры", "limit": 40000},
                {"part": "Рулевые наконечники", "limit": 40000},
                {"part": "Жидкость ГУР", "limit": 40000},
                {"part": "Ступичные подшипники", "limit": 80000},
                {"part": "Втулки и стойки стабилизатора", "limit": 20000},
                {"part": "Проверка углов (Сход-развал)", "limit": 20000},
                {"part": "Шкворни (если есть)", "limit": 15000},
                # --- ЖИДКОСТИ И ОХЛАЖДЕНИЕ ---
                {"part": "Антифриз (замена)", "limit": 60000},
                {"part": "Радиатор (чистка/мойка)", "limit": 40000},
                {"part": "Помпа охлаждения", "limit": 90000},
                {"part": "Термостат", "limit": 60000},
                # --- ЭЛЕКТРИКА ---
                {"part": "Аккумулятор (проверка емкости)", "limit": 30000},
                {"part": "Генератор (проверка щеток)", "limit": 80000},
                {"part": "Стартер (ревизия)", "limit": 100000},
                {"part": "Лампы головного света", "limit": 20000},
                # --- КУЗОВ И ПРОЧЕЕ ---
                {"part": "Смазка замков и петель", "limit": 10000},
                {"part": "Прочистка дренажных отверстий", "limit": 30000},
                {"part": "Проверка состояния рамы/кузова", "limit": 50000},
                {"part": "Уплотнители дверей (смазка)", "limit": 15000},
                {"part": "Салонный фильтр", "limit": 15000},
                {"part": "Хладагент кондиционера", "limit": 40000},
                {"part": "Щетки стеклоочистителя", "limit": 10000}
            ]
            
            main_cols = st.columns(3)
            main_cols[0].metric("Текущий одометр", f"{int(actual_odo)} км")
            
            maintenance_rows = []
            for item in regulations:
                remain = item['limit'] - (actual_odo % item['limit'])
                status = "🚨 ЗАМЕНА!" if remain < 500 else "⚠️ СКОРО" if remain < 1500 else "✅ ОК"
                maintenance_rows.append({"Узел": item['part'], "Остаток (км)": int(remain), "Статус": status})

            with st.expander("📋 Посмотреть полный инженерный чек-лист"):
                st.table(pd.DataFrame(maintenance_rows))

            # --- БЛОК 2: ЭКОНОМИКА ---
            st.divider()
            st.subheader("📈 Экономический аудит")
            avg_norm = 9.0 
            fuel_consumed = (actual_dist / 100) * avg_norm
            idle_fuel = idle_hours * 1.5 
            money_lost = idle_fuel * 23 # MDL за литр
            
            f1, f2, f3 = st.columns(3)
            f1.metric("Дистанция (период)", f"{actual_dist:.1f} км")
            f2.metric("Топливо (расчет)", f"{fuel_consumed:.1f} л")
            f3.metric("Убыток (простой)", f"{int(money_lost)} MDL", delta=f"{idle_fuel:.1f} л", delta_color="inverse")

            # --- БЛОК 3: УЛУЧШЕННЫЙ ТАЙМЛАЙН ---
            st.subheader("📅 Таймлайн активности (Пульс рейса)")
            # Создаем расширенный график: Скорость + зоны простоя
            timeline_df = df[['dt', 'speed_kmh']].copy().set_index('dt')
            st.area_chart(timeline_df, color="#29b5e8")
            
            t_col1, t_col2, t_col3, t_col4 = st.columns(4)
            t_col1.metric("Смена", f"{total_time:.1f} ч")
            t_col2.metric("В движении", f"{work_hours:.1f} ч")
            t_col3.metric("Холостой ход", f"{idle_hours:.1f} ч", delta_color="inverse")
            t_col4.metric("GPS точек", len(df))

            # --- БЛОК 4: PREDICTIVE MAINTENANCE С ОБОСНОВАНИЕМ ---
            st.divider()
            st.subheader("📉 Предиктивный износ (Обоснованный прогноз)")
            hard_brake_count = len(df[df['speed_diff'] < -18])
            hard_accel_count = len(df[df['speed_diff'] > 18])
            
            p1, p2, p3 = st.columns(3)
            
            # Износ тормозов: Базовый (пробег) + Нагрузочный (резкие торможения)
            brake_wear_score = min(100, (actual_dist / 250) + (hard_brake_count * 5))
            p1.write("**Тормозная система**")
            p1.progress(brake_wear_score / 100)
            p1.caption(f"Обоснование: зафиксировано {hard_brake_count} экстренных торможений. Износ выше нормы на {int(hard_brake_count*1.2)}%.")
            
            # Износ ДВС: Работа под нагрузкой + Нагарообразование при простое
            engine_stress = min(100, (idle_hours * 4) + (hard_accel_count * 3))
            p2.write("**Риск закоксовки ДВС**")
            p2.progress(engine_stress / 100)
            p2.caption(f"Обоснование: {idle_hours:.1f}ч работы без охлаждения потоком воздуха (простой).")
            
            # Ресурс масла: Математический остаток
            oil_remain = 10000 - (actual_odo % 10000)
            oil_pct = max(0, oil_remain / 10000)
            p3.write("**Физический ресурс масла**")
            p3.progress(oil_pct)
            p3.caption(f"Обоснование: остаток {int(oil_remain)} км до критической точки потери вязкости.")

            # --- БЛОК 5: КАРТА С ЛЕГЕНДОЙ ---
            st.subheader("🗺 Карта фактического маршрута")
            
            # Создаем карту
            m = folium.Map(location=[df.iloc[0]['latitude'], df.iloc[0]['longitude']], zoom_start=12)
            
            # Рисуем линию маршрута
            points = [[p['latitude'], p['longitude']] for i, p in df.iterrows()]
            folium.PolyLine(points, color="#1f77b4", weight=4, opacity=0.8).add_to(m)
            
            # Добавляем маркеры нарушений (резкое торможение)
            for _, row in df[df['speed_diff'] < -20].iterrows():
                folium.CircleMarker(
                    [row['latitude'], row['longitude']], 
                    radius=5, 
                    color='red', 
                    fill=True, 
                    fill_opacity=0.7,
                    popup="Резкий тормоз"
                ).add_to(m)

            # --- ДОБАВЛЕНИЕ ЛЕГЕНДЫ (HTML/CSS) ---
            # --- ДОБАВЛЕНИЕ ЛЕГЕНДЫ (Текст принудительно черный) ---
            legend_html = '''
                 <div style="position: fixed; 
                             bottom: 50px; left: 50px; width: 220px; height: 110px; 
                             border:2px solid grey; z-index:9999; font-size:14px;
                             background-color:white; opacity: 0.9;
                             padding: 10px;
                             border-radius: 5px;
                             color: black; 
                             font-family: Arial, sans-serif;
                             line-height: 1.5;
                             ">
                             <b style="color: black;">Легенда отчета:</b><br>
                             <i style="background:#1f77b4; width:10px; height:10px; display:inline-block; border-radius:50%"></i>&nbsp; <span style="color: black;">Маршрут ТС</span><br>
                             <i style="background:red; width:10px; height:10px; display:inline-block; border-radius:50%"></i>&nbsp; <span style="color: black;">Резкое торможение</span><br>
                             <i style="border: 1px solid black; background:white; width:10px; height:10px; display:inline-block; border-radius:2px"></i>&nbsp; <span style="color: black;">Точки GPS: ''' + str(len(df)) + '''</span>
                </div>
            '''
            m.get_root().html.add_child(folium.Element(legend_html))

            # Отображаем карту в Streamlit
            st_folium(m, width=1300, height=500)

            # --- БЛОК 6: БИЗНЕС-ВЕРДИКТ (ИТОГИ) ---
            st.divider()
            st.subheader("💼 Бизнес-вердикт")
            b1, b2, b3 = st.columns(3)

            utilization = (work_hours / total_time) * 100 if total_time > 0 else 0
            b1.metric("Эффективность ТС", f"{utilization:.1f}%", help="Время полезного движения к общему времени")
            
            offences = hard_brake_count + hard_accel_count
            safety_score = max(0, 100 - (offences * 4) - (idle_hours * 2))
            b2.metric("Driver Safety Score", f"{int(safety_score)}/100")
            
            b3.metric("Экономия на простое", f"{int(money_lost)} MDL", delta="Потенциальная прибыль", delta_color="off")

            if utilization < 40:
                st.error("🚨 КРИТИЧЕСКАЯ НЕЭФФЕКТИВНОСТЬ: Машина простаивает более 60% времени. Прямые убытки на содержание.")
            elif safety_score < 65:
                st.warning("⚠️ ВНИМАНИЕ: Агрессивное вождение. Прогнозируется внеплановый ремонт ходовой через 2-3 месяца.")
            else:
                st.success("✅ ОБРАЗЦОВОЕ ИСПОЛЬЗОВАНИЕ: Высокий коэффициент полезного времени и бережная эксплуатация.")

            if st.button("❌ Закрыть и очистить отчет"):
                st.session_state.show_report = False
                st.rerun()

        else:
            st.warning("За указанный период данных не найдено. Попробуйте выбрать другие даты.")
            st.session_state.show_report = False
            
# Замени этот блок в разделе РОУТИНГ:
elif selected == "База Данных":
    st.markdown("<h1 class='section-head'>📋 Единая База Товаров</h1>", unsafe_allow_html=True)
    
    # Получаем свежие данные (после всех правок в модальных окнах)
    inventory_df = get_full_inventory_df()
    
    if inventory_df.empty:
        st.info("📦 В системе пока нет загруженных товаров.")
    else:
        # Информационная панель
        c1, c2 = st.columns(2)
        total_items = len(inventory_df)
        unassigned = len(inventory_df[inventory_df['Адрес'] == 'НЕ НАЗНАЧЕНО'])
        c1.metric("Всего позиций в базе", total_items)
        c2.metric("Ожидают размещения", unassigned, delta_color="inverse", delta=f"{unassigned} без адреса")

        # Таблица на всю ширину
        gb = GridOptionsBuilder.from_dataframe(inventory_df)
        gb.configure_default_column(resizable=True, filterable=True, sortable=True, floatingFilter=True)
        gb.configure_selection(selection_mode="single")
        
        # Подсвечиваем статус адреса
        cellsytle_jscode = JsCode("""
        function(params) {
            if (params.value === 'НЕ НАЗНАЧЕНО') {
                return {'color': 'white', 'backgroundColor': '#E74C3C', 'fontWeight': 'bold'};
            } else {
                return {'color': '#2ECC71', 'fontWeight': 'bold'};
            }
        };
        """)
        gb.configure_column("Адрес", cellStyle=cellsytle_jscode, pinned='left', width=180)
        
        grid_res = AgGrid(
            inventory_df,
            gridOptions=gb.build(),
            height=450,
            theme='alpine',
            allow_unsafe_jscode=True,
            update_mode=GridUpdateMode.SELECTION_CHANGED,
            key="global_inventory_grid"
        )

        # Блок под таблицей
        sel_row = grid_res.selected_rows
        if sel_row is not None and len(sel_row) > 0:
            item = sel_row.iloc[0] if isinstance(sel_row, pd.DataFrame) else sel_row[0]
            
            st.divider()
            col_txt, col_map = st.columns([1, 1])
            
            with col_txt:
                st.subheader(f"🛠️ Управление: {item['Название товара']}")
                st.markdown(f"""
                **Текущие данные в базе:**
                * **Адрес:** `{item['Адрес']}`
                * **Документ-основание:** `{item['ID Документа']}`
                * **Контрагент:** {item['Клиент/Контрагент']}
                """)
                
                # Кнопка, которая открывает ТО САМОЕ окно распределения
                if st.button("🔄 ИЗМЕНИТЬ ДАННЫЕ / НАЗНАЧИТЬ СКЛАД", type="primary", use_container_width=True):
                    st.session_state.editing_id = item['ID Документа']
                    st.session_state.active_edit_modal = "main" # или та таблица, где лежит заказ
                    st.rerun()

            with col_map:
                # 3D визуализация (если адрес есть)
                addr = str(item['Адрес'])
                if "-" in addr and addr != "НЕ НАЗНАЧЕНО":
                    wh_id = addr.split('-')[0].replace("WH", "")
                    fig = get_warehouse_figure(wh_id, highlighted_cell=addr)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning("⚠️ Товар еще не размещен на 3D карте склада.")

elif selected == "Карта": show_map()
elif selected == "Личный кабинет": show_profile()
elif selected == "Настройки":
    st.markdown("<h1 class='section-head'>⚙️ Системные настройки</h1>", unsafe_allow_html=True)
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "🏢 Склад и Топология", 
        "👥 Команда", 
        "📚 Справочники", 
        "💾 База данных"
    ])

    # --- ВКЛАДКА 1: СКЛАД ---
    with tab1:
        st.subheader("📍 Конфигурация зон хранения")
        col_map, col_cfg = st.columns([2, 1])
        
        with col_map:
            # Превью текущего склада
            wh_to_show = st.selectbox("Выберите склад для просмотра", list(WAREHOUSE_MAP.keys()))
            fig = get_warehouse_figure(wh_to_show)
            st.plotly_chart(fig, use_container_width=True)
        
        with col_cfg:
            st.markdown("**Редактор зон**")
            new_zone = st.text_input("Название новой зоны", placeholder="Зона C")
            row_count = st.number_input("Кол-во рядов", 1, 50, 5)
            if st.button("➕ Добавить зону", use_container_width=True):
                st.success(f"Зона {new_zone} добавлена в очередь на сохранение")

    # --- ВКЛАДКА 2: КОМАНДА ---
    with tab2:
        st.subheader("👤 Управление доступом")
        # Выводим профиль текущего пользователя в красивом виде
        if not st.session_state.profile_data.empty:
            st.dataframe(st.session_state.profile_data, use_container_width=True)
        
        if st.button("➕ Добавить нового сотрудника"):
            st.info("Открывается форма регистрации пользователя...")

    # --- ВКЛАДКА 3: СПРАВОЧНИКИ ---
    with tab3:
        st.subheader("📖 Системные классификаторы")
        c1, c2 = st.columns(2)
        
        with c1:
            st.write("**Типы брака**")
            defect_types = ["Механическое", "Залитие", "Заводской", "Срок годности"]
            st.multiselect("Текущие типы", defect_types, default=defect_types)
            if st.button("➕ Добавить тип брака"):
                st.text_input("Новое название")
        
        with c2:
            st.write("**Статусы заявок**")
            st.code("ОЖИДАНИЕ, В ПУТИ, ДОСТАВЛЕНО, БРАК, ОТМЕНА")

    # --- ВКЛАДКА 4: СИСТЕМА ---
    with tab4:
        st.subheader("🛠️ Обслуживание системы")
        
        c1, c2, c3 = st.columns(3)
        
        with c1:
            st.markdown("📦 **Экспорт данных**")
            full_data = io.BytesIO()
            # Логика сборки всех данных в один Excel
            st.download_button(
                "📥 Скачать полный бэкап (XLSX)",
                data=" ", # Здесь будет ваш excel_file
                file_name=f"backup_warehouse_{datetime.now().strftime('%d_%m_%y')}.xlsx",
                use_container_width=True
            )
            
        with c2:
            st.markdown("⚠️ **Очистка**")
            if st.button("🔥 Сбросить кеш таблиц", use_container_width=True):
                st.warning("Это очистит временные фильтры")
                
        with c3:
            st.markdown("🔴 **Опасная зона**")
            if st.button("🧨 УДАЛИТЬ ВСЕ ДАННЫЕ", use_container_width=True):
                st.error("Вы уверены? Это действие необратимо!")

if "current_page" not in st.session_state:
    st.session_state.current_page = selected

if st.session_state.current_page != selected:
    # СБРОС ВСЕХ МОДАЛОК ПРИ ПЕРЕХОДЕ
    st.session_state.active_modal = None
    st.session_state.active_edit_modal = None
    st.session_state.active_view_modal = None
    st.session_state.active_print_modal = None
    st.session_state.current_page = selected
    st.rerun()

# --- ГЛАВНЫЙ ДИСПЕТЧЕР МОДАЛОК ---

# Сначала проверяем РЕДАКТИРОВАНИЕ (Приоритет №1)
if st.session_state.get("active_edit_modal"):
    target = st.session_state.active_edit_modal
    
    if target == "drivers":
        edit_driver_modal()
    elif target == "vehicles":
        edit_vehicle_modal()
    # Если это не водители и не ТС, значит это заявка (order)
    elif target: 
        edit_order_modal(st.session_state.editing_id, target)

# Затем ПЕЧАТЬ / ПРОСМОТР
elif st.session_state.get("active_view_modal"):
    show_print_modal(st.session_state.active_view_modal)

elif st.session_state.get("active_print_modal"):
    show_print_modal(st.session_state.active_print_modal)

# И только в конце СОЗДАНИЕ НОВЫХ
elif st.session_state.get("active_modal"):
    m_type = st.session_state.active_modal
    
    if m_type == "drivers_new":
        create_driver_modal()
    elif m_type == "vehicle_new":
        create_vehicle_modal()
    elif m_type == "extras":
        create_extras_modal()
    elif m_type == "defects":
        create_defect_modal()
    elif m_type == "arrivals":
        create_arrival_modal()
    elif m_type: # Если есть какой-то другой тип для общей функции

        create_modal(m_type)
