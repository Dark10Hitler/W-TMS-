import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from streamlit_option_menu import option_menu
import uuid
import time
import pytz
import requests
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
from database import supabase
from geopy.distance import geodesic
import json
from geopy.geocoders import Nominatim # Для получения адреса по координатам
import math

def upload_driver_photo(file):
    from database import supabase
    import time
    try:
        file_ext = file.name.split(".")[-1]
        file_name = f"drv_{int(time.time())}.{file_ext}"
        # Загружаем в созданный тобой бакет
        supabase.storage.from_("defects_photos").upload(
            path=file_name,
            file=file.getvalue(),
            file_options={"content-type": f"image/{file_ext}"}
        )
        return supabase.storage.from_("defects_photos").get_public_url(file_name)
    except:
        return "https://cdn-icons-png.flaticon.com/512/3135/3135715.png"

TABLES_CONFIG = {
    "main": MAIN_COLUMNS,
    "orders": ORDER_COLUMNS,
    "arrivals": ARRIVAL_COLUMNS,
    "defects": DEFECT_COLUMNS,
    "extras": EXTRA_COLUMNS,
    "drivers": ["id", "Фамилия", "Имя", "Телефон", "Статус", "Фото", "Категории", "Стаж"],
    "vehicles": ["id", "Марка", "Госномер", "Тип", "Объем", "Грузоподъемность", "Паллеты", "Статус", "Фото", "ТО", "Страховка"]
}

# Добавь это в начало после импортов
def sync_all_from_supabase():
    """Функция первичной синхронизации всех таблиц"""
    # ЗАМЕНЯЕМ "main" на "main_registry"
    tables_to_sync = ["main_registry", "orders", "arrivals", "defects", "extras", "drivers", "vehicles"]
    for table in tables_to_sync:
        data = load_data_from_supabase(table)
        # Если мы загрузили main_registry, в память сохраняем как 'main' для совместимости с кодом
        state_key = "main" if table == "main_registry" else table
        st.session_state[state_key] = data

def load_data_from_supabase(table_name):
    try:
        # 1. Запрос к Supabase
        response = supabase.table(table_name).select("*").order("created_at", desc=True).execute()
        
        # 2. ПРОВЕРКА ДАННЫХ (Исправление ошибки конструктора)
        # Проверяем, что response.data существует и является списком
        raw_data = response.data
        if raw_data is None or not isinstance(raw_data, list):
            st.warning(f"⚠️ Данные для {table_name} не получены или имеют неверный формат.")
            return pd.DataFrame(columns=TABLE_STRUCT.get(table_name, []))
            
        # Теперь безопасно создаем DataFrame
        df = pd.DataFrame(raw_data)
        
        # Если в базе 0 записей, создаем пустой DF с нужными колонками
        if df.empty:
            return pd.DataFrame(columns=TABLE_STRUCT.get(table_name, []))

        # --- КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ ДЛЯ JSON/DICT ---
        # Чтобы не было ошибок хеширования и проблем с AgGrid
        for col in df.columns:
            # Проверяем, есть ли в колонке словари или списки
            if df[col].apply(lambda x: isinstance(x, (dict, list))).any():
                df[col] = df[col].apply(lambda x: str(x) if x is not None else None)

        # 3. Маппинг (как у вас был)
        RENAME_MAP = {
            "id": "id",
            "status": "Статус",
            "client_name": "Клиент",
            "items_count": "Кол-во позиций",
            "total_volume": "Общий объем (м3)",
            "total_sum": "Сумма заявки",
            "client_address": "Адрес клиента",
            "driver_name": "Водитель",
            "vehicle_number": "ТС (Госномер)",
            "loading_efficiency": "КПД загрузки",
            "phone": "Телефон",
            "event_date": "Когда",
            "event_time": "Время",
            "location": "Где",
            "subject": "Что именно",
            "reason": "Почему (Причина)",
            "approved_by": "Кто одобрил",
            "parent_id": "Связь с ID",
            "transport": "На чем",
            "items_data": "items_data" # Системное поле
        }
        
        current_rename = {k: v for k, v in RENAME_MAP.items() if k in df.columns}
        df = df.rename(columns=current_rename)
        
        return df

    except Exception as e:
        st.error(f"🚨 Критическая ошибка загрузки {table_name}: {str(e)}")
        # Возвращаем пустой DF, чтобы приложение не "падало" полностью
        return pd.DataFrame()

# --- ГЛОБАЛЬНАЯ СИНХРОНИЗАЦИЯ ---
def refresh_all_data():
    """Полное обновление данных из облака в Session State"""
    with st.spinner("🔄 Синхронизация с базой данных..."):
        # ОШИБКА БЫЛА ЗДЕСЬ: заменяем "main" на "main_registry"
        st.session_state.main = load_data_from_supabase("main_registry") 
        
        st.session_state.orders = load_data_from_supabase("orders")
        st.session_state.arrivals = load_data_from_supabase("arrivals")
        st.session_state.extras = load_data_from_supabase("extras")
        st.session_state.defects = load_data_from_supabase("defects")
        st.session_state.drivers = load_data_from_supabase("drivers")
        st.session_state.vehicles = load_data_from_supabase("vehicles")

# Инициализация при первом запуске
if "db_initialized" not in st.session_state:
    st.session_state.items_registry = {}
    refresh_all_data()
    st.session_state.db_initialized = True
    

def save_to_supabase(table_name, data_dict, entry_id=None):
    """
    Универсальное сохранение: если есть entry_id — обновляет (UPDATE), 
    если нет — создает новую запись (INSERT).
    """
    try:
        # 1. МАППИНГ ОБРАТНО (UI Русский -> DB English)
        # Этот словарь — зеркало того, что мы использовали при загрузке
        REVERSE_MAP = {
            "Статус": "status",
            "Клиент": "client_name",
            "Кол-во позиций": "items_count",
            "Общий объем (м3)": "total_volume",
            "Сумма заявки": "total_sum",
            "Адрес клиента": "client_address",
            "Водитель": "driver_name",
            "ТС (Госномер)": "vehicle_number",
            "КПД загрузки": "loading_efficiency",
            "Телефон": "phone",
            "Когда": "event_date",
            "Время": "event_time",
            "Где": "location",
            "Что именно": "subject",
            "Почему (Причина)": "reason",
            "Кто одобрил": "approved_by",
            "Связь с ID": "parent_id",
            "На чем": "transport"
        }

        # Создаем чистый словарь для БД
        db_payload = {}
        for k, v in data_dict.items():
            db_key = REVERSE_MAP.get(k, k) # Если нет в маппинге, оставляем как есть
            # Пропускаем технические колонки AgGrid, их не должно быть в БД
            if k not in ["📝 Ред.", "🔍 Просмотр", "🖨️ Печать"]:
                db_payload[db_key] = v

        # 2. АВТОМАТИЧЕСКАЯ УПАКОВКА ТОВАРОВ
        # Если для этого ID в реестре есть товары — кладем их в JSONB поле
        current_id = entry_id or data_dict.get('id')
        if current_id in st.session_state.items_registry:
            items_df = st.session_state.items_registry[current_id]
            # Превращаем DataFrame в список словарей, понятный для PostgreSQL
            db_payload["items_data"] = items_df.to_dict(orient='records')
            # Обновляем счетчик позиций
            db_payload["items_count"] = len(items_df)

        # 3. ВЫБОР ОПЕРАЦИИ (INSERT / UPDATE)
        if entry_id:
            # Обновляем существующую запись
            response = supabase.table(table_name).update(db_payload).eq("id", entry_id).execute()
        else:
            # Создаем новую
            if "id" not in db_payload: db_payload["id"] = generate_id()
            response = supabase.table(table_name).insert(db_payload).execute()

        return True, response

    except Exception as e:
        st.error(f"🚨 Ошибка сохранения в {table_name}: {e}")
        return False, None


# ИСПОЛЬЗУЕМ ВНЕШНИЙ URL ТУННЕЛЯ, чтобы облако видело твой ПК
TRACCAR_URL = "https://bronchiolar-dichromatic-abdul.ngrok-free.dev"
TRACCAR_AUTH = ("denis.masliuc.speak23dev@gmail.com", "qwert12345")

@st.cache_data(ttl=10)
def get_detailed_traccar_data(endpoint="devices", params=None):
    api_base = f"{TRACCAR_URL.rstrip('/')}/api"
    headers = {'ngrok-skip-browser-warning': 'true'}
    
    # Если запрашиваем устройства (стандартный вызов без аргументов)
    if endpoint == "devices":
        try:
            dev_resp = requests.get(f"{api_base}/devices", auth=TRACCAR_AUTH, headers=headers, timeout=10)
            pos_resp = requests.get(f"{api_base}/positions", auth=TRACCAR_AUTH, headers=headers, timeout=10)
            
            if dev_resp.status_code == 200 and pos_resp.status_code == 200:
                devices = {d['id']: d for d in dev_resp.json()}
                return devices, pos_resp.json()
            return {}, []
        except Exception as e:
            st.sidebar.error(f"📡 Ошибка связи (devices): {e}")
            return {}, []
    
    # Если запрашиваем отчеты (вызов с параметрами)
    else:
        try:
            resp = requests.get(f"{api_base}/{endpoint}", auth=TRACCAR_AUTH, headers=headers, params=params, timeout=15)
            if resp.status_code == 200:
                return resp.json()
            else:
                st.error(f"Ошибка API: {resp.status_code}")
                return []
        except Exception as e:
            st.error(f"📡 Ошибка связи (reports): {e}")
            return []

def get_vehicle_status_color(status):
    """Возвращает цвет для маркера на карте в зависимости от статуса ТС"""
    colors = {
        "online": "green",
        "offline": "red",
        "unknown": "gray"
    }
    return colors.get(status, "blue")

def get_full_inventory_df():
    all_items = []
    try:
        # ===== ПРИХОДЫ (ARRIVALS) =====
        try:
            # Прямой запрос без промежуточной функции
            response = supabase.table("arrivals").select("*").execute()
            arrivals_data = pd.DataFrame(response.data) if response.data else pd.DataFrame()
        except Exception as e:
            st.warning(f"⚠️ Ошибка загрузки приходов: {e}")
            arrivals_data = pd.DataFrame()

        if not arrivals_data.empty:
            st.write(f"DEBUG: Загружено приходов: {len(arrivals_data)}")  # ОТЛАДКА
            
            for _, row in arrivals_data.iterrows():
                data = row.get('items_data')
                
                # ===== КРИТИЧНО: Десериализация JSON =====
                if isinstance(data, str):
                    try:
                        import json
                        data = json.loads(data)
                    except json.JSONDecodeError:
                        st.warning(f"⚠️ Ошибка парсинга JSON для arrival {row.get('id')}")
                        continue
                
                # Если это JSONB из Supabase, он может быть уже распарсен
                if not isinstance(data, list):
                    st.warning(f"⚠️ items_data не является списком: {type(data)}")
                    continue
                
                # Обработка каждого товара в накладной
                for item in data:
                    if not isinstance(item, dict):
                        continue
                        
                    name = item.get('Название товара') or item.get('Наименование') or "Без имени"
                    
                    # Пропускаем техническую строку итогов
                    if str(name).upper() in ["TOTAL", "ИТОГО"]:
                        continue
                    
                    qty = item.get('Количесво товаров') or item.get('Количество') or 0
                    
                    all_items.append({
                        "id": row.get('id'),
                        "Название товара": str(name),
                        "Количество": float(qty) if qty else 0,
                        "Адрес": str(item.get('Адрес') or "НЕ НАЗНАЧЕНО"),
                        "Тип": "📦 ПРИХОД",
                        "Контрагент": str(row.get('vendor_name', 'Н/Д')),
                        "ID Документа": str(row.get('doc_number', 'Н/Д')),
                        "Дата": row.get('created_at')
                    })
        
        # ===== ЗАКАЗЫ (ORDERS) =====
        try:
            response = supabase.table("orders").select("*").execute()
            orders_data = pd.DataFrame(response.data) if response.data else pd.DataFrame()
        except Exception as e:
            st.warning(f"⚠️ Ошибка загрузки заказов: {e}")
            orders_data = pd.DataFrame()

        if not orders_data.empty:
            st.write(f"DEBUG: Загружено заказов: {len(orders_data)}")  # ОТЛАДКА
            
            for _, row in orders_data.iterrows():
                data = row.get('items_data')
                
                if isinstance(data, str):
                    try:
                        import json
                        data = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                
                if not isinstance(data, list):
                    continue
                
                for item in data:
                    if not isinstance(item, dict):
                        continue
                        
                    name = item.get('Название товара') or item.get('Наименование') or "Без имени"
                    
                    if str(name).upper() in ["TOTAL", "ИТОГО"]:
                        continue
                    
                    qty = item.get('Количесво товаров') or item.get('Количество') or 0
                    
                    all_items.append({
                        "id": row.get('id'),
                        "Название товара": str(name),
                        "Количество": float(qty) if qty else 0,
                        "Адрес": str(item.get('Адрес') or "НЕ НАЗНАЧЕНО"),
                        "Тип": "🚚 ЗАКАЗ",
                        "Контрагент": str(row.get('client_name', 'Н/Д')),
                        "ID Документа": str(row.get('id', 'Н/Д')),
                        "Дата": row.get('created_at')
                    })
        
        st.write(f"DEBUG: Всего товаров найдено: {len(all_items)}")  # ОТЛАДКА

    except Exception as e:
        st.error(f"❌ Критическая ошибка парсинга: {e}")
        import traceback
        st.error(traceback.format_exc())
        return pd.DataFrame()

    return pd.DataFrame(all_items) if all_items else pd.DataFrame()
        
def get_saved_location(product_name):
    """Ищет рекомендованный адрес товара в БД Supabase"""
    try:
        from database import supabase
        response = supabase.table("product_locations").select("address").eq("product", product_name).execute()
        if response.data:
            return response.data[0]['address']
        return "НЕИЗВЕСТНО"
    except:
        return "НЕИЗВЕСТНО"

def save_new_location(product_name, location):
    """Запоминает ячейку для товара в облаке (UPSERT)"""
    try:
        from database import supabase
        payload = {"product": product_name, "address": location}
        # Используем upsert: если товар есть — обновит адрес, если нет — создаст
        supabase.table("product_locations").upsert(payload, on_conflict="product").execute()
    except Exception as e:
        st.error(f"Ошибка сохранения топологии: {e}")

st.set_page_config(layout="wide", page_title="IMPERIA LOGISTICS", page_icon="🏢")

st.markdown("""
<style>
    /* 1. Общие настройки шрифтов и фона */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&display=swap');
    
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Inter', sans-serif;
        background-color: #0D1117; /* Чуть глубже основной фон */
    }

    .stApp { background-color: #0D1117; color: #E6EDF3; }

    /* 2. Сайдбар: более строгий и тонкий */
    [data-testid="stSidebar"] {
        background-color: #010409 !important;
        border-right: 1px solid #30363D;
        box-shadow: 10px 0 15px rgba(0,0,0,0.1);
    }

    /* 3. Контейнеры и отступы */
    .block-container { padding-top: 2rem; max-width: 95%; }

    /* 4. Карточки метрик: эффект стекла и мягкая граница */
    div[data-testid="stMetric"] {
        background-color: #161B22;
        border: 1px solid #30363D;
        border-radius: 10px;
        padding: 15px 20px;
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    div[data-testid="stMetric"]:hover {
        border-color: #58A6FF; /* Подсветка при наведении */
        transform: translateY(-2px);
    }
    /* Стилизация текста внутри метрик */
    div[data-testid="stMetricLabel"] { font-size: 0.9rem !important; color: #8B949E !important; }
    div[data-testid="stMetricValue"] { font-size: 1.8rem !important; font-weight: 600 !important; color: #F0F6FC !important; }

    /* 5. Кнопки: строгий темно-красный вместо градиента */
    .stButton>button {
        border-radius: 6px;
        font-weight: 500;
        background-color: #21262D; /* Спокойный фон кнопки по умолчанию */
        color: #C9D1D9;
        border: 1px solid #30363D;
        padding: 0.5rem 1rem;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        width: auto;
    }
    
    /* Основная кнопка (Primary) — делаем её акцентной, но строгой */
    .stButton>button[kind="primary"] {
        background: #D32F2F; 
        border: none;
        color: white;
    }
    .stButton>button:hover {
        border-color: #8B949E;
        background-color: #30363D;
        color: #FFFFFF;
    }
    .stButton>button:active {
        transform: scale(0.98);
    }

    /* 6. Таблицы AgGrid: минимализм */
    .ag-theme-alpine-dark {
        --ag-background-color: #0D1117;
        --ag-header-background-color: #161B22;
        --ag-border-color: #30363D;
        --ag-header-foreground-color: #8B949E;
        --ag-odd-row-background-color: #0D1117;
        --ag-row-hover-color: #1F242C;
        --ag-font-family: 'Inter', sans-serif;
        --ag-font-size: 13px;
    }
    .ag-header-cell-label { font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }

    /* 7. Скроллбары (тонкие) */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: #0D1117; }
    ::-webkit-scrollbar-thumb { background: #30363D; border-radius: 10px; }
    ::-webkit-scrollbar-thumb:hover { background: #484F58; }

    /* 8. Инпуты и текстовые поля */
    .stTextInput>div>div>input, .stSelectbox>div>div>div {
        background-color: #0D1117 !important;
        border: 1px solid #30363D !important;
        border-radius: 6px !important;
    }
</style>
""", unsafe_allow_html=True)

# 3. Затем системные переменные
if "items_registry" not in st.session_state:
    st.session_state.items_registry = {}

# 4. И только в конце — загрузка данных из Supabase
if "db_synced" not in st.session_state:
    refresh_all_data() # Наша функция, которую мы обсуждали ранее
    st.session_state.db_synced = True

# 1. КОНСТАНТЫ И КОНФИГ
MIN_LOAD_FACTOR = 0.3 

# 2. ИНИЦИАЛИЗАЦИЯ (Один цикл вместо трех)
if "db_initialized" not in st.session_state:
    with st.spinner("🚀 Загрузка системы IMPERIA..."):
        st.session_state.items_registry = {}
        st.session_state.active_modal = None
        
        # Загрузка всех таблиц из БД
        for table_name, cols in TABLES_CONFIG.items():
            df = load_data_from_supabase(table_name)
            st.session_state[table_name] = df if not df.empty else pd.DataFrame(columns=cols)
        
        # Загрузка профиля
        db_profile = load_data_from_supabase("profiles")
        if not db_profile.empty:
            st.session_state.profile_data = db_profile
        else:
            st.session_state.profile_data = pd.DataFrame([
                {"Поле": "ФИО", "Значение": "Иванов Иван Иванович"},
                {"Поле": "Должность", "Значение": "Главный Логист / CEO"},
                {"Поле": "Телефон", "Значение": "+7 (999) 000-00-00"},
                {"Поле": "Email", "Значение": "admin@logistics-empire.ru"},
                {"Поле": "Опыт", "Значение": "15 лет в управлении"}
            ])
        st.session_state.db_initialized = True

# 3. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
def generate_id(): 
    return str(uuid.uuid4())[:8]

def calculate_load_efficiency(df_items, vehicle_volume):
    try:
        vehicle_vol = float(vehicle_volume)
        if vehicle_vol <= 0: return 0, "⚠️ Не указан объем ТС"
        if df_items.empty: return 0, "📦 ТС пустое"

        vol_col = "Объем (м3)"
        if vol_col not in df_items.columns:
            return 0, "❌ Нет данных об объеме в спецификации"

        total_volume = pd.to_numeric(df_items[vol_col], errors='coerce').sum()
        efficiency = (total_volume / vehicle_vol) * 100
        
        if efficiency < (MIN_LOAD_FACTOR * 100):
            return efficiency, f"🚫 КРИТИЧЕСКИЙ НЕДОГРУЗ! ({efficiency:.1f}%)"
        elif efficiency > 100:
            return efficiency, f"⚠️ ПЕРЕГРУЗ ОБЪЕМА! ({efficiency:.1f}%)"
        return efficiency, f"✅ Загрузка оптимальна: {efficiency:.1f}%"
    except Exception as e:
        return 0, f"⚙️ Ошибка расчета: {str(e)}"

# 1. Добавляем JS-рендеры для иконок (вставить перед render_aggrid_table)
# Рендерер для кнопки просмотра внутри таблицы
render_view_button = JsCode("""
    function(params) {
        return '<button style="background-color: #58A6FF; color: white; border: none; border-radius: 50px;">🔍 Обзор</button>';
    }
""")

# 2. ПОЛНОСТЬЮ ОБНОВЛЕННАЯ ФУНКЦИЯ ТАБЛИЦЫ
def render_aggrid_table(table_key, title):
    # --- 1. ПРОВЕРКА ДАННЫХ ---
    # Если данных нет в session_state, пробуем загрузить из БД
    if table_key not in st.session_state or st.session_state[table_key].empty:
        st.session_state[table_key] = load_data_from_supabase(table_key)
    
    df = st.session_state[table_key].copy()
    
    # Заголовок и кнопка добавления
    c_title, c_act1 = st.columns([8, 2])
    c_title.markdown(f"### 🚀 {title} <span style='font-size: 0.6em; color: gray;'>({len(df)} зап.)</span>", unsafe_allow_html=True)
    
    # Кнопка добавления (скрыта для 'main', так как это сводный журнал)
    if table_key != "main":
        if c_act1.button("➕ ДОБАВИТЬ", key=f"btn_add_{table_key}", use_container_width=True):
            st.session_state.active_modal = table_key
            st.rerun()

    # --- 2. НАСТРОЙКА ГРИДА ---
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_default_column(resizable=True, sortable=True, filterable=True, minWidth=120)
    
    # Подсветка статусов/секций через JsCode
    if "Секция" in df.columns:
        section_style = JsCode("""
        function(params) {
            if (params.value === 'ПРИХОД') return {'color': 'white', 'backgroundColor': '#1B5E20', 'fontWeight': 'bold'};
            if (params.value === 'ЗАЯВКА') return {'color': 'white', 'backgroundColor': '#0D47A1', 'fontWeight': 'bold'};
            if (params.value === 'БРАК') return {'color': 'white', 'backgroundColor': '#B71C1C', 'fontWeight': 'bold'};
            return null;
        }
        """)
        gb.configure_column("Секция", cellStyle=section_style, pinned='left', width=140)

    # Прячем системные колонки (например, JSON с товарами)
    if "items_data" in df.columns:
        gb.configure_column("items_data", hide=True)

    gb.configure_selection(selection_mode="single", use_checkbox=False)
    gridOptions = gb.build()

    # Рендеринг
    # Рендеринг AgGrid без DeprecationWarning
    grid_response = AgGrid(
        df,
        gridOptions=gridOptions,
        height=500,
        theme='alpine',
    # Заменяем update_mode на update_on
        update_on=['selectionChanged'], 
        allow_unsafe_jscode=True,
        key=f"grid_{table_key}"
    )

    # --- 3. ОБРАБОТКА ВЫБОРА ---
    selected_rows = grid_response.selected_rows
    
    # Универсальная проверка выбора (pd.DataFrame или List)
    row_data = None
    if selected_rows is not None:
        if isinstance(selected_rows, pd.DataFrame) and not selected_rows.empty:
            row_data = selected_rows.iloc[0]
        elif isinstance(selected_rows, list) and len(selected_rows) > 0:
            row_data = selected_rows[0]

    if row_data is not None:
        row_id = row_data["id"]
        st.session_state.editing_id = row_id # Фиксируем ID для модалок

        # --- ИНТЕЛЛЕКТУАЛЬНЫЙ РОУТИНГ ДЛЯ 'MAIN' ---
        # Определяем, к какой таблице реально относится документ
        # --- ИНТЕЛЛЕКТУАЛЬНЫЙ РОУТИНГ ДЛЯ 'MAIN' ---
        target_key = table_key
        if table_key == "main":
            # 1. Проверка по префиксам ID
            if str(row_id).startswith("ORD"): target_key = "orders"
            elif str(row_id).startswith("IN") or str(row_id).startswith("ARR"): target_key = "arrivals"
            elif str(row_id).startswith("DEF"): target_key = "defects"
            elif str(row_id).startswith("EXT"): target_key = "extras"  # ДОБАВЛЕНО
            
            # 2. Проверка по колонке "Секция" (как запасной вариант)
            elif row_data.get("Секция") == "ПРИХОД": target_key = "arrivals"
            elif row_data.get("Секция") == "ЗАЯВКА": target_key = "orders"
            elif row_data.get("Секция") == "ДОПОЛНЕНИЕ": target_key = "extras" # ДОБАВЛЕНО
            elif row_data.get("Секция") == "БРАК": target_key = "defects"     # ДОБАВЛЕНО

        st.markdown("---")
        col_actions = st.columns([1, 1, 1, 3])
        
        # Динамический вызов модальных окон на основе target_key
        with col_actions[0]:
            if st.button("⚙️ ИЗМЕНИТЬ", key=f"edit_{table_key}", width="stretch"):
                if target_key == "orders": edit_order_modal(row_id)
                elif target_key == "arrivals": edit_arrival_modal(row_id)
                elif target_key == "extras": edit_extra_modal(row_id)
                elif target_key == "defects": edit_defect_modal(row_id)
                elif target_key == "drivers": edit_driver_modal(row_id)
                elif target_key == "vehicles": edit_vehicle_modal(row_id)

        with col_actions[1]:
            if st.button("🔍 ПРОСМОТР", key=f"view_{table_key}", width="stretch"):
                if target_key == "orders": show_order_details_modal(row_id)
                elif target_key == "arrivals": show_arrival_details_modal(row_id)
                elif target_key == "defects": show_defect_details_modal(row_id)
                elif target_key == "extras": show_extra_details_modal(row_id)

        with col_actions[2]:
            if st.button("🖨️ ПЕЧАТЬ", key=f"print_{table_key}", width="stretch"):
                if target_key == "orders": show_print_modal(row_id)
                elif target_key == "arrivals": show_arrival_print_modal(row_id)
                elif target_key == "extras": show_extra_print_modal(row_id)
                elif target_key == "defects": show_defect_print_modal(row_id)

    else:
        st.info("💡 Выберите запись в таблице для управления")
     
def save_doc(key, name, qty, price, client, tc, driver):
    """
    Универсальное сохранение документа: 
    1. Формирует данные 
    2. Отправляет в Supabase 
    3. Синхронизирует локальный стейт
    """
    new_id = generate_id()
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # 1. ПОДГОТОВКА ДАННЫХ ДЛЯ UI (Русские ключи)
    new_row = {
        "id": new_id, 
        "Статус": "НОВЫЙ",
        "Клиент": client, 
        "Водитель": driver, 
        "ТС (Госномер)": tc, 
        "Кол-во позиций": 1,
        "Общий объем (м3)": 0, # Должно считаться из спецификации товаров
        "Сумма заявки": price * qty,
        "Дата создания": current_time,
        "Описание": f"Товар: {name}, Кол-во: {qty}"
    }

    # 2. ПОДГОТОВКА ДЛЯ БАЗЫ ДАННЫХ (Маппинг на English)
    # Используем нашу ранее созданную логику маппинга
    db_payload = {
        "id": new_id,
        "status": "НОВЫЙ",
        "client_name": client,
        "driver_name": driver,
        "vehicle_number": tc,
        "total_sum": float(price * qty),
        "description": f"Товар: {name}, Кол-во: {qty}",
        "created_at": datetime.now().isoformat() # Стандарт ISO для БД
    }

    # 3. СОХРАНЕНИЕ В ОБЛАКО (Supabase)
    # Сначала сохраняем в специфичную таблицу (orders, arrivals и т.д.)
    success, response = save_to_supabase(key, new_row) # Функция использует REVERSE_MAP внутри
    
    if success:
        # Если это не брак, дублируем в таблицу 'main' (Общий журнал)
        if key != "defects" and key != "main":
            section_names = {"orders": "ЗАЯВКА", "arrivals": "ПРИХОД", "extras": "ДОПОЛНЕНИЕ"}
            main_row = new_row.copy()
            main_row["Секция"] = section_names.get(key, "ПРОЧЕЕ")
            
            # Сохраняем в таблицу main в Supabase
            save_to_supabase("main", main_row)

        # 4. ОБНОВЛЕНИЕ ЛОКАЛЬНОГО КЭША (Чтобы не делать лишний запрос к БД)
        new_df = pd.DataFrame([new_row])
        st.session_state[key] = pd.concat([st.session_state[key], new_df], ignore_index=True)
        
        if key != "defects" and key != "main":
            main_df = pd.DataFrame([{**new_row, "Секция": section_names.get(key, "ПРОЧЕЕ")}])
            st.session_state["main"] = pd.concat([st.session_state["main"], main_df], ignore_index=True)

        st.session_state.active_modal = None
        st.success(f"✅ Документ {new_id} успешно сохранен в облаке!")
        time.sleep(1)
        st.rerun()
    else:
        st.error("❌ Не удалось сохранить данные в базу. Проверьте соединение.")

def show_dashboard():
    st.markdown(f"## 📊 Центр Управления <span style='font-size: 0.5em; color: gray;'>на {datetime.now().strftime('%d.%m %H:%M')}</span>", unsafe_allow_html=True)
    
    # Извлекаем данные из session_state
    df_main = st.session_state.main
    df_defects = st.session_state.get('defects', pd.DataFrame())
    df_extras = st.session_state.get('extras', pd.DataFrame())
    df_drivers = st.session_state.get('drivers', pd.DataFrame())

    # --- 1. ВЕРХНИЕ МЕТРИКИ (KPI) ---
    m1, m2, m3, m4 = st.columns(4)
    
    with m1:
        st.metric("Всего документов", len(df_main))
    
    with m2:
        active_drivers = len(df_drivers)
        st.metric("Водители в базе", active_drivers, help="Количество активных учетных записей ТС")
    
    with m3:
        defect_count = len(df_defects)
        # Рассчитываем дельту относительно общего числа (процент брака)
        defect_rate = (defect_count / len(df_main) * 100) if len(df_main) > 0 else 0
        st.metric("Акты брака", defect_count, delta=f"{defect_rate:.1f}% от общ.", delta_color="inverse")
    
    with m4:
        extra_count = len(df_extras)
        st.metric("Корректировки", extra_count, help="Догрузы, возвраты и правки")

    st.divider()

    # --- 2. АНАЛИЗ РИТМИЧНОСТИ (ГРАФИК) ---
    st.subheader("🕒 Анализ ритмичности: Пики нагрузки")
    
    # Используем 'created_at' или 'Дата создания'
    time_col = "Дата создания" # Или "created_at" в зависимости от маппинга
    
    if not df_main.empty and time_col in df_main.columns:
        df_time = df_main.copy()
        # Преобразование времени (учитываем, что из Supabase может прийти строка ISO или время HH:MM)
        df_time['hour'] = pd.to_datetime(df_time[time_col], errors='coerce').dt.hour
        
        # Если время было в формате HH:MM и dt.hour не сработал
        if df_time['hour'].isnull().all():
             df_time['hour'] = df_time[time_col].str.split(':').str[0].astype(float)

        hourly_activity = df_time.groupby('hour').size().reset_index(name='Количество')
        
        if not hourly_activity.empty:
            fig_time = px.area( # Area chart выглядит более современно
                hourly_activity, 
                x='hour', 
                y='Количество',
                title="Интенсивность формирования заказов (по часам)",
                template="plotly_dark",
                color_discrete_sequence=['#58A6FF']
            )
            fig_time.update_layout(xaxis=dict(tickmode='linear', tick0=0, dtick=1), height=300)
            st.plotly_chart(fig_time, use_container_width=True)
            
            peak_hour = int(hourly_activity.loc[hourly_activity['Количество'].idxmax(), 'hour'])
            st.info(f"💡 **Аналитический инсайт:** Пик нагрузки сегодня в **{peak_hour}:00**. Планируйте ресурсы склада заранее.")
    else:
        st.info("ℹ️ Данные о времени создания появятся после синхронизации первых заказов.")

    # --- 3. СЕКЦИОННЫЙ АНАЛИЗ ---
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
                hole=0.5,
                color_discrete_sequence=px.colors.sequential.Blues_r
            )
            fig_status.update_layout(height=350, margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig_status, use_container_width=True)

    with col_right:
        st.subheader("🏆 Топ Контрагентов")
        client_col = "Клиент"
        if not df_main.empty and client_col in df_main.columns:
            top_clients = df_main[client_col].value_counts().head(5).reset_index()
            top_clients.columns = [client_col, 'Заказов']
            
            fig_clients = px.bar(
                top_clients, 
                x='Заказов', 
                y=client_col, 
                orientation='h',
                color='Заказов',
                color_continuous_scale='Blues'
            )
            fig_clients.update_layout(height=350, showlegend=False)
            st.plotly_chart(fig_clients, use_container_width=True)

    # --- 4. ПУЛЬС СКЛАДА (LIVE KPI) ---
    st.divider()
    st.subheader("🔥 Оперативный пульс")
    
    cp1, cp2, cp3 = st.columns(3)
    
    with cp1:
        # Считаем за последние 24 часа
        st.metric("Документов сегодня", len(df_main))
        
    # /mount/src/w-tms-/app.py:748
    with cp2:
    # Проверяем, есть ли вообще колонка 'Статус'
        if 'Статус' in df_main.columns:
            waiting_count = len(df_main[df_main['Статус'].fillna('').str.contains("ОЖИДАНИЕ")])
            waiting_pct = (waiting_count / len(df_main) * 100) if len(df_main) > 0 else 0
            st.metric("Очередь на обработку", f"{waiting_pct:.1f}%")
        else:
            st.warning("⚠️ Колонка 'Статус' не найдена в данных")
            st.metric("Очередь на обработку", "0%")

    with cp3:
        # КПД загрузки (средний по всем записям main)
        if "КПД загрузки" in df_main.columns:
            # Очищаем от знака % и считаем среднее
            avg_load = pd.to_numeric(df_main["КПД загрузки"].astype(str).str.replace('%', ''), errors='coerce').mean()
            st.metric("Ср. загрузка ТС", f"{avg_load:.1f}%" if not pd.isna(avg_load) else "0%")
            
def show_map():
    st.markdown("## 🛰️ Оперативный штаб: Мониторинг Fleet")
    
    # 1. Автообновление (15 сек)
    st_autorefresh(interval=15000, key="traccar_map_refresh")
    
    # 2. Получение данных из БД и API
    v_reg = st.session_state.get('vehicles', pd.DataFrame())
    d_reg = st.session_state.get('drivers', pd.DataFrame())
    
    with st.spinner("🚀 Запрос данных со спутников..."):
        devices, positions = get_detailed_traccar_data()

    # 3. Базовая конфигурация карты
    BASE_LAT, BASE_LON = 47.776654, 27.913643
    base_coords = [BASE_LAT, BASE_LON]
    
    m = folium.Map(
        location=base_coords, 
        zoom_start=12, 
        tiles="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png", 
        attr='&copy; OpenStreetMap &copy; CARTO'
    )
    
    # Дополнительные слои
    folium.TileLayer('OpenStreetMap', name="Детальный план").add_to(m)
    folium.LayerControl(position='topright').add_to(m)
    
    # Визуализация Центрального Склада
    folium.Circle(
        location=base_coords, radius=500, color='#e74c3c', weight=3,
        fill=True, fill_color='#e74c3c', fill_opacity=0.2, popup="🏢 ЦЕНТРАЛЬНЫЙ СКЛАД"
    ).add_to(m)

    folium.Marker(
        base_coords, 
        popup="🏢 <b>IMPERIA LOGISTICS HQ</b>",
        icon=folium.Icon(color="darkred", icon="home", prefix="fa")
    ).add_to(m)

    # Счетчики статистики
    stats = {"active": 0, "stopped": 0, "low_battery": 0, "at_base": [], "offline_long": 0}

    # 4. ОБРАБОТКА ПОЗИЦИЙ
    for pos in positions:
        dev_id = pos.get('deviceId')
        if dev_id not in devices: continue
            
        dev = devices[dev_id]
        v_name = dev.get('name') 
        
        # --- СВЯЗКА С БД (по model) ---
        v_row = v_reg[v_reg['model'] == v_name] if not v_reg.empty and 'model' in v_reg.columns else pd.DataFrame()
        v_data = v_row.iloc[0].to_dict() if not v_row.empty else {}
        
        d_row = d_reg[d_reg['ТС'] == v_name] if 'ТС' in d_reg.columns and not d_reg.empty else pd.DataFrame()
        d_data = d_row.iloc[0].to_dict() if not d_row.empty else {}

        # --- ТЕХНИЧЕСКИЕ ПАРАМЕТРЫ ---
        attrs = pos.get('attributes', {})
        speed = round(pos.get('speed', 0) * 1.852, 1)
        lat, lon = pos.get('latitude'), pos.get('longitude')
        batt = attrs.get('batteryLevel', 100)
        course = pos.get('course', 0) # Направление движения
        
        # Расчет времени последнего сигнала
        last_update_raw = pos.get('deviceTime') or pos.get('fixTime')
        last_update_dt = datetime.fromisoformat(last_update_raw.replace('Z', '+00:00'))
        time_diff = datetime.now(last_update_dt.tzinfo) - last_update_dt
        time_str = f"{int(time_diff.total_seconds() // 60)} мин. назад" if time_diff.total_seconds() > 60 else "Только что"

        # Определение адреса и дистанции
        current_address = get_address_cached(lat, lon)
        dist_to_base = round(geodesic((lat, lon), base_coords).km, 2)
        is_at_base = dist_to_base <= 0.5
        
        # Сбор статистики
        if is_at_base: stats["at_base"].append(v_name)
        if speed > 3: stats["active"] += 1
        else: stats["stopped"] += 1
        if isinstance(batt, (int, float)) and batt < 20: stats["low_battery"] += 1
        if time_diff.total_seconds() > 600: stats["offline_long"] += 1

        # Расчет ETA
        if speed > 5:
            eta_m = int((dist_to_base / speed) * 60)
            eta_t = (datetime.now() + timedelta(minutes=eta_m)).strftime("%H:%M")
        else:
            eta_t = "На базе" if is_at_base else "Стоянка"

        # --- КАРТОЧКА ОБЪЕКТА (HTML) ---
        status_color = "#2ecc71" if speed > 3 else "#3498db"
        
        popup_html = f"""
        <div style="width: 290px; font-family: 'Segoe UI', sans-serif; font-size: 13px;">
            <div style="background:{status_color}; color:white; padding:10px; border-radius:5px 5px 0 0;">
                <b>🚛 {v_name}</b> | {v_data.get('Госномер', 'Б/Н')}
            </div>
            <div style="padding:10px; border:1px solid #ddd; background: white;">
                👤 <b>Водитель:</b> {d_data.get('Фамилия', 'Не назначен')}<br>
                📞 <b>Тел:</b> {d_data.get('Телефон', '-')}<br>
                <hr style="margin:8px 0; border:0; border-top:1px solid #eee;">
                📍 <b>Место:</b> {current_address}<br>
                🚀 <b>Скорость:</b> <span style="color:red">{speed} км/ч</span><br>
                🏠 <b>До базы:</b> {dist_to_base} км<br>
                ⏱ <b>ETA:</b> <span style="color:blue">{eta_t}</span><br>
                <hr style="margin:8px 0; border:0; border-top:1px solid #eee;">
                <div style="font-size:11px; color:gray; display:flex; justify-content:space-between;">
                    <span>🔋 Заряд: {batt}%</span>
                    <span>📡 {time_str}</span>
                </div>
            </div>
            <div style="font-size:10px; text-align:center; color: #aaa; padding-top:5px;">
                Координаты: {lat:.5f}, {lon:.5f}
            </div>
        </div>
        """

        # Направление движения (стрелка)
        icon_color = "green" if speed > 3 else "blue"
        
        folium.Marker(
            [lat, lon],
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=f"{v_name} ({speed} км/ч)",
            icon=folium.Icon(color=icon_color, icon="play", angle=course, prefix="fa") if speed > 3 
                 else folium.Icon(color=icon_color, icon="truck", prefix="fa")
        ).add_to(m)

    # 5. ВЫВОД МЕТРИК
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🚚 В движении", stats["active"])
    c2.metric("🅿️ На стоянке", stats["stopped"])
    c3.metric("🏠 На базе", len(stats["at_base"]), delta=f"{dist_to_base} км ближ." if positions else None)
    c4.metric("🪫 Низкий заряд", stats["low_battery"], delta_color="inverse")

    # 6. КАРТА
    st_folium(m, width=1300, height=600, returned_objects=[])

    # 7. ДОПОЛНИТЕЛЬНЫЕ ИНСТРУМЕНТЫ ПОД КАРТОЙ
    col_left, col_right = st.columns(2)
    
    with col_left:
        if stats["at_base"]:
            with st.expander("🏢 Машины на территории склада"):
                for car in stats["at_base"]:
                    st.write(f"🟢 **{car}** — ожидание распоряжений")
        else:
            st.info("ℹ️ На территории склада сейчас нет машин")

    with col_right:
        with st.expander("📡 Статус системы"):
            st.write(f"Обновлено: {datetime.now().strftime('%H:%M:%S')}")
            st.write(f"URL Traccar: `{TRACCAR_URL}`")
            if stats["offline_long"] > 0:
                st.warning(f"⚠️ {stats['offline_long']} устр. не на связи > 10 мин!")

    # Краткая сводная таблица (для быстрого поиска)
    if positions:
        with st.expander("📋 Сводный лог текущих позиций"):
            log_df = []
            for p in positions:
                d = devices.get(p['deviceId'], {})
                log_df.append({
                    "Машина": d.get('name'),
                    "Скорость": f"{round(p.get('speed', 0) * 1.852, 1)} км/ч",
                    "К базе": f"{round(geodesic((p['latitude'], p['longitude']), base_coords).km, 2)} км",
                    "Адрес": get_address_cached(p['latitude'], p['longitude'])
                })
            st.dataframe(pd.DataFrame(log_df), use_container_width=True)
            
def show_profile():
    st.header("👤 Карточка сотрудника")

    # 1. ЗАГРУЗКА ИЗ БАЗЫ
    try:
        res = supabase.table("profiles").select("*").order("id").execute()
        df = pd.DataFrame(res.data)
        
        # Простая функция: ищем значение по имени параметра
        def get_v(name):
            try:
                return df[df['parameter'] == name]['value'].values[0]
            except:
                return "---"
    except Exception as e:
        st.error(f"Ошибка базы: {e}")
        return

    # 2. ОТОБРАЖЕНИЕ (БЕЗ ХАРДКОДА И КРАСОТЫ)
    # Здесь нет имен "Иванов", только ссылки на колонки из твоей таблицы
    col1, col2 = st.columns([1, 3])
    
    with col1:
        st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=120)
    
    with col2:
        st.subheader(get_v('ФИО'))
        st.write(f"**Должность:** {get_v('Должность')}")
        st.write(f"**Департамент:** {get_v('Департамент')}")
        st.write(f"**Контракт:** {get_v('Номер Контракта')}")

    st.markdown("---")
    
    # Сетка данных
    c1, c2, c3 = st.columns(3)
    c1.metric("Телефон", get_v('Телефон'))
    c2.metric("Email", get_v('Email'))
    c3.metric("Офис", get_v('Офис'))

    st.markdown("---")

    # 3. РЕДАКТОР (ТО ЧТО ТЫ ПРАВИШЬ)
    st.write("### 📝 Редактировать данные")
    edited_df = st.data_editor(
        df[['id', 'parameter', 'value']], 
        use_container_width=True,
        hide_index=True,
        column_config={"parameter": "Параметр", "value": "Значение"}
    )

    if st.button("💾 СОХРАНИТЬ ВСЁ"):
        for _, row in edited_df.iterrows():
            supabase.table("profiles").update({"value": row["value"]}).eq("id", row["id"]).execute()
        st.success("Данные обновлены!")
        st.rerun()
            
# --- Сайдбар и навигация остаются как у тебя, но добавляем логику вызова ---
with st.sidebar:
    st.markdown("### 📦 IMPERIA WMS")
    selected = option_menu(
        menu_title="Навигация",
        options=[
            "Dashboard", "База Данных", "Main", "Заявки", "Приходы", 
            "Дополнения", "Брак", "Водители", "ТС", "Карта", 
            "Аналитика", "Личный кабинет", "Настройки"
        ],
        icons=[
            "grid-1x2", "database-fill", "table", "cart-check", "box-seam", 
            "plus-square", "shield-slash", "person-vcard", "truck", "map", 
            "bar-chart-line", "person-circle", "gear-wide-managed"
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
    """
    Удаляет запись из Supabase и синхронизирует локальное состояние.
    """
    try:
        # 1. УДАЛЕНИЕ ИЗ ОБЛАКА (Supabase)
        # Мы обращаемся к таблице по ключу и удаляем строку, где id совпадает
        response = supabase.table(table_key).delete().eq("id", entry_id).execute()
        
        # Проверяем, не пустой ли ответ (если данных нет, значит в БД записи не было)
        if hasattr(response, 'data'):
            
            # 2. УДАЛЕНИЕ ИЗ ЛОКАЛЬНОЙ ПАМЯТИ
            # Оставляем в стейте только те строки, id которых НЕ равен удаленному
            st.session_state[table_key] = st.session_state[table_key][
                st.session_state[table_key]['id'] != entry_id
            ]
            
            # Если удаляем из дочерних таблиц (orders/arrivals), 
            # нужно не забыть удалить и из сводной таблицы 'main'
            if table_key != 'main' and 'main' in st.session_state:
                st.session_state['main'] = st.session_state['main'][
                    st.session_state['main']['id'] != entry_id
                ]
                # Опционально: удалить и из БД таблицы main, если они там дублируются
                supabase.table("main").delete().eq("id", entry_id).execute()

            # 3. УВЕДОМЛЕНИЕ
            st.toast(f"🗑️ Запись {entry_id} успешно удалена из системы", icon="🚮")
            time.sleep(0.5)
            st.rerun()
            
    except Exception as e:
        st.error(f"❌ Ошибка при удалении из базы данных: {e}")
        
if selected == "Dashboard": show_dashboard()
elif selected == "Main": render_aggrid_table("main", "Основной Реестр")
elif selected == "Заявки": render_aggrid_table("orders", "Заявки")
elif selected == "Приходы": render_aggrid_table("arrivals", "Приходы")
elif selected == "Брак": render_aggrid_table("defects", "Журнал Брака")
elif selected == "Дополнения": render_aggrid_table("extras", "Дополнения")
# --- РАЗДЕЛ ВОДИТЕЛИ ---     
elif selected == "Водители":
    st.markdown("<h1 class='section-head'>👨‍✈️ Реестр водителей</h1>", unsafe_allow_html=True)
    
    # 1. СИНХРОНИЗАЦИЯ
    if "drivers" not in st.session_state or st.session_state.drivers.empty:
        with st.spinner("Загрузка..."):
            try:
                res = supabase.table("drivers").select("*").execute()
                if res.data:
                    df = pd.DataFrame(res.data)
                    # Маппинг из имен БД в имена для UI
                    df = df.rename(columns={
                        'first_name': 'Имя', 
                        'last_name': 'Фамилия', 
                        'phone': 'Телефон', 
                        'categories': 'Категории',
                        'experience': 'Стаж', 
                        'status': 'Статус', 
                        'photo_url': 'Фото'
                    })
                    st.session_state.drivers = df
                else:
                    st.session_state.drivers = pd.DataFrame(columns=['id', 'Имя', 'Фамилия', 'Телефон', 'Категории', 'Стаж', 'Статус', 'Фото'])
            except Exception as e:
                st.error(f"Ошибка загрузки: {e}")
                st.session_state.drivers = pd.DataFrame()

    col_btn, col_search = st.columns([1, 2])
    
    if col_btn.button("➕ ДОБАВИТЬ ВОДИТЕЛЯ", type="primary", use_container_width=True):
        create_driver_modal() 

    search = col_search.text_input("🔍 Поиск по фамилии...", placeholder="Введите фамилию")

    df_drivers = st.session_state.drivers
    
    # Фильтрация (с защитой от пустых значений в колонке Фамилия)
    if search and not df_drivers.empty:
        df_drivers = df_drivers[df_drivers['Фамилия'].fillna('').str.contains(search, case=False, na=False)]

    st.divider()

    if not df_drivers.empty:
        cols = st.columns(3)
        for idx, (i, row) in enumerate(df_drivers.iterrows()):
            # Безопасное получение данных через .get()
            driver_id = row.get('id')
            f_name = row.get('Имя', '')
            l_name = row.get('Фамилия', '')
            status = row.get('Статус', 'Н/Д')
            phone = row.get('Телефон', 'Нет номера')
            cats = row.get('Категории', '-')
            exp = row.get('Стаж', 0)
            
            # Логика фото: проверяем 'Фото', потом 'photo_url', потом дефолт
            img_url = row.get('Фото') or row.get('photo_url') or "https://cdn-icons-png.flaticon.com/512/3135/3135715.png"
            
            with cols[idx % 3]:
                with st.container(border=True):
                    st.markdown(f"""
                    <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 15px;">
                        <img src="{img_url}" style="width: 50px; height: 50px; border-radius: 50%; object-fit: cover; border: 2px solid #58A6FF;">
                        <div>
                            <h3 style="margin: 0; font-size: 1.1em;">{l_name} {f_name}</h3>
                            <small style="color: #8B949E;">{status}</small>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    st.caption(f"📱 {phone}")
                    st.caption(f"🪪 Кат: {cats} | Стаж: {exp}л.")
                    
                    c1, c2 = st.columns(2)
                    # Кнопка изменения
                    if c1.button("⚙️ Изм.", key=f"ed_btn_{driver_id}", use_container_width=True):
                        edit_driver_modal(driver_id)
                    
                    # Кнопка удаления
                    if c2.button("🗑️", key=f"del_btn_{driver_id}", use_container_width=True):
                        try:
                            supabase.table("drivers").delete().eq("id", driver_id).execute()
                            # Обновляем локальный стейт без перезагрузки всей базы
                            st.session_state.drivers = st.session_state.drivers[st.session_state.drivers.id != driver_id]
                            st.toast(f"Водитель {l_name} удален")
                            time.sleep(0.5)
                            st.rerun()
                        except Exception as e:
                            st.error("Ошибка удаления")
    else:
        st.info("Водители не найдены.")
        
elif selected == "ТС":
    st.markdown("<h1 class='section-head'>🚛 Управление Автопарком</h1>", unsafe_allow_html=True)
    
    if "vehicles" not in st.session_state or st.session_state.vehicles is None:
        with st.spinner("Синхронизация..."):
            st.session_state.vehicles = load_data_from_supabase("vehicles")

    if st.button("➕ ДОБАВИТЬ НОВОЕ ТРАНСПОРТНОЕ СРЕДСТВО", type="primary", use_container_width=True):
        create_vehicle_modal() 

    st.divider()

    df_v = st.session_state.get("vehicles", pd.DataFrame())

    if not df_v.empty:
        cols = st.columns(2) 
        for idx, (i, row) in enumerate(df_v.iterrows()):
            v_id = row.get('id')
            g_num = row.get('Госномер') or row.get('gov_num') or "Н/Д"
            brand = row.get('Марка') or row.get('brand') or ""
            v_type = row.get('Тип') or row.get('body_type') or ""
            status = row.get('Статус') or row.get('status') or "На линии"
            veh_img = row.get('Фото') or row.get('photo_url') or "https://cdn-icons-png.flaticon.com/512/2554/2554977.png"
            
            cap = row.get('Грузоподъемность') or row.get('capacity') or 0
            vol = row.get('Объем') or row.get('volume') or 0
            pal = row.get('Паллеты') or row.get('pallets') or 0

            st_color = "#238636" if status == "На линии" else "#d29922"

            with cols[idx % 2]:
                with st.container(border=True):
                    # Мы упаковываем HTML в одну строку, чтобы Streamlit не путался
                    card_html = f"""
                    <div style="font-family: sans-serif;">
                        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
                            <div style="display: flex; gap: 12px;">
                                <img src="{veh_img}" style="width: 48px; height: 48px; object-fit: contain; background: #161b22; border-radius: 8px; padding: 4px; border: 1px solid #30363d;">
                                <div>
                                    <div style="font-size: 1.1em; font-weight: bold; color: #58a6ff;">{g_num}</div>
                                    <div style="font-size: 0.85em; color: #8b949e;">{brand} • {v_type}</div>
                                </div>
                            </div>
                            <div style="border: 1px solid {st_color}; color: {st_color}; padding: 2px 8px; border-radius: 10px; font-size: 0.7em; font-weight: bold; background: {st_color}11;">
                                {status.upper()}
                            </div>
                        </div>
                        <div style="display: flex; gap: 8px;">
                            <div style="flex: 1; background: #0d1117; padding: 8px; border-radius: 6px; border: 1px solid #30363d; text-align: center;">
                                <div style="font-size: 0.6em; color: #8b949e; text-transform: uppercase;">Вес</div>
                                <div style="font-size: 0.85em; font-weight: bold; color: #c9d1d9;">{cap} кг</div>
                            </div>
                            <div style="flex: 1; background: #0d1117; padding: 8px; border-radius: 6px; border: 1px solid #30363d; text-align: center;">
                                <div style="font-size: 0.6em; color: #8b949e; text-transform: uppercase;">Объем</div>
                                <div style="font-size: 0.85em; font-weight: bold; color: #c9d1d9;">{vol} м&sup3;</div>
                            </div>
                            <div style="flex: 1; background: #0d1117; padding: 8px; border-radius: 6px; border: 1px solid #30363d; text-align: center;">
                                <div style="font-size: 0.6em; color: #8b949e; text-transform: uppercase;">Паллеты</div>
                                <div style="font-size: 0.85em; font-weight: bold; color: #c9d1d9;">{pal} шт</div>
                            </div>
                        </div>
                    </div>
                    """.replace("\n", "") # Убираем переносы, которые ломают рендеринг
                    
                    st.markdown(card_html, unsafe_allow_html=True)
                    st.write("") 
                    
                    c1, c2 = st.columns([4, 1])
                    if c1.button(f"⚙️ ИЗМЕНИТЬ", key=f"ed_{v_id}", use_container_width=True):
                        st.session_state.editing_id = v_id
                        edit_vehicle_modal()
                    
                    if c2.button(f"🗑️", key=f"dl_{v_id}", use_container_width=True):
                        try:
                            supabase.table("vehicles").delete().eq("id", v_id).execute()
                            st.session_state.vehicles = st.session_state.vehicles[st.session_state.vehicles.id != v_id]
                            st.toast("Автомобиль удален")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Ошибка: {e}")
    else:
        st.info("ℹ️ В автопарке пока нет записей.")

elif selected == "Аналитика":
    st.title("🛡️ Logistics Intelligence & Tech Audit")
    # --- 1. ФУНКЦИЯ СИНХРОНИЗАЦИИ (Исправленная) ---
    def get_traccar_reports_sync(v_id, s_date, e_date):
        # Формат ISO 8601 с миллисекундами для точности
        iso_start = s_date.strftime('%Y-%m-%dT00:00:00Z')
        iso_end = e_date.strftime('%Y-%m-%dT23:59:59Z')
        
        api_url = f"{TRACCAR_URL.rstrip('/')}/api/reports/route"
        params = {
            "deviceId": v_id,
            "from": iso_start,
            "to": iso_end
        }
        headers = {
            "Accept": "application/json",
            "ngrok-skip-browser-warning": "true" # Пропуск окна Ngrok
        }
        
        try:
            resp = requests.get(api_url, auth=TRACCAR_AUTH, params=params, headers=headers, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                if not data:
                    return None, "Данные за этот период не найдены на сервере."
                return data, None
            return None, f"Ошибка сервера Traccar: {resp.status_code}"
        except Exception as e:
            return None, f"Ошибка соединения: {str(e)}"

    # --- 2. ПАНЕЛЬ УПРАВЛЕНИЯ ---
    devices_dict, _ = get_detailed_traccar_data()
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        v_name = st.selectbox("🎯 Выберите ТС для аудита", options=[d['name'] for d in devices_dict.values()])
        v_id = next((id for id, d in devices_dict.items() if d['name'] == v_name), None)
    with c2:
        start_d = st.date_input("Дата начала", datetime.now() - timedelta(days=1))
    with c3:
        end_d = st.date_input("Дата конца", datetime.now())

    if st.button("📑 ЗАПУСТИТЬ ПОЛНУЮ СИНХРОНИЗАЦИЮ", type="primary", use_container_width=True):
        with st.spinner("🔄 Соединение с Traccar Cloud..."):
            raw_data, error = get_traccar_reports_sync(v_id, start_d, end_d)
            
            if error:
                st.error(f"🛑 {error}")
            else:
                df = pd.DataFrame(raw_data)
                df['dt'] = pd.to_datetime(df['deviceTime'])
                # Фильтруем данные строго внутри выбранного диапазона (защита от "хвостов")
                mask = (df['dt'].dt.date >= start_d) & (df['dt'].dt.date <= end_d)
                df = df.loc[mask].sort_values('dt')

                # Математика атрибутов
                def get_attr(attr, keys, default=0):
                    for key in keys:
                        if key in attr: return attr[key]
                    return default

                df['speed_kmh'] = round(df['speed'] * 1.852, 1)
                # Берем totalDistance (как на скриншоте 225.05 км)
                df['total_dist_km'] = df['attributes'].apply(lambda x: get_attr(x, ['totalDistance', 'odometer']) / 1000.0)
                # Расстояние шага (для расчета расхода)
                df['step_dist_km'] = df['attributes'].apply(lambda x: get_attr(x, ['distance']) / 1000.0)
                
                st.session_state.audit_results = {
                    'df': df,
                    'v_name': v_name,
                    'period': f"{start_d} — {end_d}"
                }
                st.rerun()

    # --- 3. ИНЖЕНЕРНЫЙ ВЕРДИКТ: ГЛУБОКАЯ СИНХРОНИЗАЦИЯ ---
if st.session_state.audit_results:
    res = st.session_state.audit_results
    df = res['df']
    
    # --- ИНЖЕНЕРНЫЕ ВЫЧИСЛЕНИЯ (БАЗА: СЕРВЕР TRACCAR) ---
    # 1. Total Distance (из атрибута totalDistance: 225.05 км)
    total_dist_end = df['total_dist_km'].iloc[-1] 
    total_dist_start = df['total_dist_km'].iloc[0]
    actual_period_km = max(0, total_dist_end - total_dist_start)
    
    # 2. Физический одометр устройства (из атрибута odometer: 100.98 км)
    device_odo_current = df['attributes'].apply(lambda x: x.get('odometer', 0) / 1000.0).iloc[-1]
    
    # 3. Скоростные показатели
    moving_df = df[df['speed_kmh'] > 2]
    avg_speed = moving_df['speed_kmh'].mean() if not moving_df.empty else 0
    max_speed = df['speed_kmh'].max()
    
    # 4. Расход топлива (Инженерная модель: База + Коэффициент нагрузки)
    # Считаем "Агрессивность" через производную скорости (м/с²)
    df['accel_ms2'] = df['speed_kmh'].diff() / 3.6 
    hard_maneuvers = len(df[df['accel_ms2'].abs() > 3.0]) # Резкие маневры
    
    base_rate = 12.0  # Базовая норма л/100км
    # Поправочный коэффициент: +0.5% за каждое нарушение скорости и +1% за резкий маневр
    overspeeds_count = len(df[df['speed_kmh'] > 90])
    load_factor = 1 + (overspeeds_count * 0.005) + (hard_maneuvers * 0.01)
    
    fuel_total = (actual_period_km / 100) * base_rate * load_factor
    cost_mdl = fuel_total * 24.15 # Актуальный курс MDL за литр
    
    # --- ВИЗУАЛИЗАЦИЯ ДАННЫХ (TOP-LEVEL METRICS) ---
    st.header("🛠️ Технический аудит систем")
    
    # Первая линия: Одометрия и Пробег
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("🗺️ Пробег (Период)", f"{actual_period_km:.2f} км", 
                  help="Разница totalDistance между первой и последней точкой периода")
    with c2:
        st.metric("📟 Total Distance", f"{total_dist_end:.2f} км", 
                  help="Полный системный пробег ТС (серверный накопитель)")
    with c3:
        st.metric("🔌 Датчик Odometer", f"{device_odo_current:.2f} км", 
                  help="Текущее значение внутреннего счетчика устройства")
    with c4:
        st.metric("⏱️ Ср. Скорость", f"{avg_speed:.1f} км/ч", 
                  delta=f"Max: {max_speed}", delta_color="off")

    # Вторая линия: Экономика и Нарушения
    st.markdown("---")
    e1, e2, e3, e4 = st.columns(4)
    with e1:
        st.metric("⛽ Расход топлива", f"{fuel_total:.1f} л", 
                  delta=f"{(load_factor-1)*100:.1f}% Нагрузка", delta_color="inverse")
    with e2:
        st.metric("💰 Финансовый итог", f"{int(cost_mdl)} MDL")
    with e3:
        st.metric("⚠️ Нарушения (>90)", overspeeds_count, 
                  delta="Критично" if overspeeds_count > 10 else "Норма", 
                  delta_color="inverse")
    with e4:
        st.metric("💢 Резкие маневры", hard_maneuvers, 
                  help="Количество экстремальных ускорений и торможений (>3.0 m/s²)")

    # --- ТЕХНИЧЕСКИЙ ВЕРДИКТ ДЛЯ ЛОГИСТА ---
    st.info(f"**Инженерное заключение:** На дистанции **{actual_period_km:.2f} км** зафиксировано **{hard_maneuvers}** "
            f"событий избыточной нагрузки. Это привело к перерасходу **{(fuel_total * (1 - 1/load_factor)):.2f} л** топлива. "
            f"Текущий ресурс масла снижен на **{0.1 * hard_maneuvers:.1f}%** быстрее регламента.")

    # --- ГРАФИК ПУЛЬСА (СИНХРОНИЗАЦИЯ ПО ОСЯМ) ---
    import altair as alt
    st.markdown("### 📈 Динамика систем (Скорость + Нагрузка)")
    
    # Объединенный график: Скорость и зоны перегрузки
    chart_speed = alt.Chart(df).mark_area(
        line={'color':'#29b5e8', 'size':2},
        color=alt.Gradient(
            gradient='linear',
            stops=[alt.GradientStop(color='white', offset=0),
                   alt.GradientStop(color='#29b5e8', offset=1)],
            x1=1, x2=1, y1=1, y2=0
        )
    ).encode(
        x=alt.X('dt:T', title='Время'),
        y=alt.Y('speed_kmh:Q', title='Скорость км/ч'),
        tooltip=['dt', 'speed_kmh', 'total_dist_km']
    ).properties(height=300)

    # Линия порога нарушений
    limit_line = alt.Chart(pd.DataFrame({'y': [90]})).mark_rule(color='red', strokeDash=[5,5]).encode(y='y:Q')

    st.altair_chart(chart_speed + limit_line, use_container_width=True)

        # --- БЛОК УЛУЧШЕННОЙ КАРТЫ (PREMIUM AUDIT) ---
        import folium
        from streamlit_folium import st_folium
        from folium.plugins import MarkerCluster, AntPath, Fullscreen
        from branca.element import Template, MacroElement

        st.markdown("### 🗺️ Детальный гео-аудит маршрута")

        # 1. Центрирование и база
        avg_lat, avg_lon = df['latitude'].mean(), df['longitude'].mean()
        m = folium.Map(location=[avg_lat, avg_lon], zoom_start=13, tiles="cartodbpositron", control_scale=True)
        Fullscreen().add_to(m)

        # 2. Отрисовка траектории (AntPath)
        path_points = df[['latitude', 'longitude']].values.tolist()
        AntPath(
            locations=path_points,
            color="#1E90FF",
            pulse_color="#ffffff",
            weight=4,
            opacity=0.7,
            delay=1000,
            tooltip="Маршрут движения ТС"
        ).add_to(m)

        # 3. Подготовка кластеров для нарушений
        # icon_create_function=None задействует стандартные красивые кластеры (синий/желтый/оранжевый)
        marker_cluster = MarkerCluster(name="Группы нарушений", control=True).add_to(m)

        # --- ЛОГИКА СОБЫТИЙ ---
        
        # А. Превышения скорости (> 90 км/ч)
        overspeeds = df[df['speed_kmh'] > 90]
        for _, row in overspeeds.iterrows():
            folium.Marker(
                location=[row['latitude'], row['longitude']],
                icon=folium.Icon(color='orange', icon='gauge-high', prefix='fa'),
                popup=f"<b>Превышение:</b> {row['speed_kmh']} км/ч<br>Время: {row['dt'].strftime('%H:%M:%S')}",
                tooltip="Скорость"
            ).add_to(marker_cluster)

        # Б. Резкие маневры (Торможение и ускорение)
        # Считаем разницу скоростей между соседними точками
        df['speed_delta'] = df['speed_kmh'].diff().fillna(0)
        
        # Резкое торможение (падение > 18 км/ч за шаг)
        brakes = df[df['speed_delta'] < -18]
        for _, row in brakes.iterrows():
            folium.Marker(
                location=[row['latitude'], row['longitude']],
                icon=folium.Icon(color='red', icon='triangle-exclamation', prefix='fa'),
                popup=f"<b>Резкий тормоз!</b><br>Сброс: {row['speed_delta']:.1f} км/ч",
            ).add_to(marker_cluster)

        # Резкий старт (прирост > 15 км/ч за шаг)
        accels = df[df['speed_delta'] > 15]
        for _, row in accels.iterrows():
            folium.Marker(
                location=[row['latitude'], row['longitude']],
                icon=folium.Icon(color='darkpurple', icon='bolt', prefix='fa'),
                popup=f"<b>Агрессивный старт</b><br>Прирост: +{row['speed_delta']:.1f} км/ч",
            ).add_to(marker_cluster)

        # В. Остановки и Стоянки (> 5 минут)
        # Группируем последовательные точки со скоростью 0
        df['is_stopped'] = df['speed_kmh'] < 2
        df['stop_group'] = (df['is_stopped'] != df['is_stopped'].shift()).cumsum()
        
        stops_summary = df[df['is_stopped']].groupby('stop_group').agg({
            'dt': ['min', 'max'],
            'latitude': 'first',
            'longitude': 'first'
        })

        for _, stop in stops_summary.iterrows():
            duration = (stop[('dt', 'max')] - stop[('dt', 'min')]).total_seconds() / 60
            if duration >= 5: # Только если стояли дольше 5 минут
                folium.Marker(
                    location=[stop[('latitude', 'first')], stop[('longitude', 'first')]],
                    icon=folium.Icon(color='blue', icon='clock', prefix='fa'),
                    popup=f"<b>Длительная стоянка</b><br>Длительность: {int(duration)} мин.<br>Начало: {stop[('dt', 'min')].strftime('%H:%M')}",
                    tooltip="Стоянка"
                ).add_to(m)

        # Г. Старт и Финиш
        folium.Marker(path_points[0], icon=folium.Icon(color='green', icon='play', prefix='fa'), tooltip="Точка выхода на маршрут").add_to(m)
        folium.Marker(path_points[-1], icon=folium.Icon(color='black', icon='flag-checkered', prefix='fa'), tooltip="Последняя позиция").add_to(m)

        # 4. ПРЕМИАЛЬНАЯ ЛЕГЕНДА С ЧЕРНЫМ ТЕКСТОМ
        legend_html = '''
        {% macro html(this, kwargs) %}
        <div style="position: fixed; 
                    bottom: 30px; left: 30px; width: 260px; height: auto; 
                    background-color: white; border: 2px solid #2c3e50; border-radius: 10px; 
                    z-index:9999; font-size:14px; padding: 12px;
                    box-shadow: 2px 2px 15px rgba(0,0,0,0.3);
                    font-family: 'Arial', sans-serif;
                    color: black !important;">
            <p style="margin: 0 0 8px 0; font-weight: bold; border-bottom: 1px solid #ccc; padding-bottom: 5px; color: black;">
                🔍 Легенда аудита
            </p>
            <div style="line-height: 1.8; color: black;">
                <i class="fa fa-minus" style="color: #1E90FF; margin-right: 8px;"></i> <span style="color: black;">Маршрут (AntPath)</span><br>
                <i class="fa fa-circle" style="color: #3498db; margin-right: 8px;"></i> <span style="color: black;">Кластер нарушений (Цифра)</span><br>
                <i class="fa fa-gauge-high" style="color: orange; margin-right: 8px;"></i> <span style="color: black;">Скорость > 90 км/ч</span><br>
                <i class="fa fa-triangle-exclamation" style="color: #e74c3c; margin-right: 8px;"></i> <span style="color: black;">Резкое торможение</span><br>
                <i class="fa fa-bolt" style="color: #9b59b6; margin-right: 8px;"></i> <span style="color: black;">Резкое ускорение</span><br>
                <i class="fa fa-clock" style="color: #2980b9; margin-right: 8px;"></i> <span style="color: black;">Стоянка (> 5 мин)</span>
            </div>
            <p style="margin: 8px 0 0 0; font-size: 11px; color: #666; font-style: italic;">
                * Кликните на цифру для раскрытия группы
            </p>
        </div>
        {% endmacro %}
        '''
        macro = MacroElement()
        macro._template = Template(legend_html)
        m.get_root().add_child(macro)

        # Рендеринг
        st_folium(m, width=1300, height=600, key="audit_premium_map")

        # --- БЛОК 6: СУПЕР-АНАЛИТИКА (БИЗНЕС, ЛОГИСТИКА, ТЕХОБСЛУЖИВАНИЕ) ---
        st.divider()
        st.header("📈 Logistics Intelligence & Financial Audit")
        
        # Предварительные расчеты для карточек
        max_speed = df['speed_kmh'].max()
        avg_speed = df[df['speed_kmh'] > 5]['speed_kmh'].mean()
        
        # Расчет резких маневров
        df['accel_g'] = df['speed_kmh'].diff() / 3.6  # Ускорение в м/с²
        hard_brakes = len(df[df['accel_g'] < -4.5])  # Торможение сильнее 0.45G
        hard_accels = len(df[df['accel_g'] > 3.0])   # Ускорение сильнее 0.3G
        
        # Экономика
        fuel_price = 24.15 # Текущая цена MDL за литр
        base_consumption = 12 # Базовая норма на 100км
        # Коэффициент перерасхода от агрессивной езды (примерная модель)
        aggressive_factor = 1 + (hard_accels * 0.02) + (len(overspeeds) * 0.005)
        real_consumption = (actual_period_km / 100) * base_consumption * aggressive_factor
        loss_mdl = (real_consumption - (actual_period_km / 100) * base_consumption) * fuel_price

        # --- РЯД 1: ФИНАНСОВЫЙ АУДИТ ---
        st.subheader("💰 Экономическая эффективность")
        f1, f2, f3 = st.columns(3)
        
        f1.metric("Прямые затраты (Fuel)", f"{int(real_consumption * fuel_price)} MDL", 
                  help="Расчет стоимости топлива на основе пробега и стиля вождения")
        
        f2.metric("Убыток (Стиль езды)", f"-{int(loss_mdl)} MDL", 
                  delta=f"{((aggressive_factor-1)*100):.1f}% перерасход", delta_color="inverse")
        
        roi_efficiency = max(0, 100 - (aggressive_factor-1)*200)
        f3.metric("КПД Логистики", f"{int(roi_efficiency)}%", 
                  help="Насколько эффективно используется ресурс ТС относительно идеального вождения")

        # --- РЯД 2: ТЕХНИЧЕСКИЙ ПРЕДИКТОЛОГ (Износ систем) ---
        st.subheader("🔧 Предиктивный износ систем (Digital Twin)")
        t1, t2, t3 = st.columns(3)
        
        # Тормозная система
        brake_wear = min(100, (hard_brakes * 4) + (actual_period_km / 50))
        t1.write(f"**Износ колодок/дисков: {int(brake_wear)}%**")
        t1.progress(brake_wear / 100)
        t1.caption(f"Причина: {hard_brakes} экстренных торможений. Риск перегрева дисков: Высокий.")

        # Двигатель и Трансмиссия
        engine_load = min(100, (hard_accels * 5) + (max_speed / 1.5))
        t2.write(f"**Нагрузка на ДВС/КПП: {int(engine_load)}%**")
        t2.progress(engine_load / 100)
        t2.caption(f"Агрессивные старты ({hard_accels}) сокращают ресурс масла на 15%.")

        # Ходовая часть
        suspension_stress = min(100, (actual_period_km / 100) * (1 + (max_speed/100)))
        t3.write(f"**Усталость подвески: {int(suspension_stress)}%**")
        t3.progress(suspension_stress / 100)
        t3.caption("Обоснование: Вибрационные нагрузки на высоких скоростях.")

        # --- РЯД 3: ВЕРДИКТ БЕЗОПАСНОСТИ ---
        st.divider()
        st.subheader("🛡️ Driver Safety Score (Безопасность)")
        
        safety_score = max(0, 100 - (hard_brakes * 5) - (len(overspeeds) * 2))
        
        col_s1, col_s2 = st.columns([1, 2])
        
        with col_s1:
            if safety_score > 85:
                st.success(f"РЕЙТИНГ: {int(safety_score)}/100\n\nБЕЗОПАСНО")
            elif safety_score > 60:
                st.warning(f"РЕЙТИНГ: {int(safety_score)}/100\n\nСРЕДНИЙ РИСК")
            else:
                st.error(f"РЕЙТИНГ: {int(safety_score)}/100\n\nКРИТИЧЕСКИЙ УРОВЕНЬ")
        
        with col_s2:
            st.info(f"""
            **Инженерный комментарий:**
            * **Превышения:** {len(overspeeds)} случаев. Увеличивает риск ДТП в 2.4 раза.
            * **Динамика:** Средняя скорость рейса {avg_speed:.1f} км/ч при пиковой {max_speed} км/ч.
            * **Прогноз:** Рекомендуется внеплановая проверка тормозной системы через 1500 км.
            """)

        # --- ГРАФИК "ПУЛЬС РЕЙСА" ---
        st.markdown("### 📈 Детализированная телеметрия скорости")
        import altair as alt
        
        chart = alt.Chart(df).mark_area(
            line={'color':'#29b5e8'},
            color=alt.Gradient(
                gradient='linear',
                stops=[alt.GradientStop(color='white', offset=0),
                       alt.GradientStop(color='#29b5e8', offset=1)],
                x1=1, x2=1, y1=1, y2=0
            )
        ).encode(
            x=alt.X('dt:T', title='Временная шкала (Синхронизировано)'),
            y=alt.Y('speed_kmh:Q', title='Скорость (км/ч)'),
            tooltip=['dt', 'speed_kmh', 'total_dist_km']
        ).properties(height=400).interactive()
        
        st.altair_chart(chart, use_container_width=True)

        # Кнопки управления данными
        st.divider()
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("📥 СКАЧАТЬ ОТЧЕТ В CSV", use_container_width=True):
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("Нажмите для загрузки", csv, f"audit_{res['v_name']}.csv", "text/csv")
        with col_btn2:
            if st.button("🗑️ ОЧИСТИТЬ АУДИТ", type="secondary", use_container_width=True):
                st.session_state.audit_results = None
                st.rerun()
            
            
elif selected == "База Данных":
    st.markdown("<h1 class='section-head'>📋 Единая База Товаров</h1>", unsafe_allow_html=True)
    
    with st.spinner("Синхронизация товарных позиций..."):
        inventory_df = get_full_inventory_df() 
    
    # Проверка на пустой DataFrame
    if inventory_df is None or (isinstance(inventory_df, pd.DataFrame) and inventory_df.empty):
        st.info("📦 В документах (Приходы/Заказы) пока нет товаров. Сначала создайте приход в разделе 'Приемка'.")
    else:
        # Панель аналитики
        c1, c2, c3 = st.columns(3)
        
        total_in = inventory_df[inventory_df['Тип'] == "📦 ПРИХОД"]['Количество'].sum() if 'Количество' in inventory_df.columns else 0
        unassigned = len(inventory_df[inventory_df['Адрес'] == 'НЕ НАЗНАЧЕНО']) if 'Адрес' in inventory_df.columns else 0
        
        c1.metric("Всего поступило (ед.)", f"{int(total_in)} шт")
        c2.metric("Требуют размещения", unassigned, delta=f"{unassigned} поз.", delta_color="inverse")
        c3.metric("Уникальных строк", len(inventory_df))

        # Настройка таблицы Ag-Grid
        gb = GridOptionsBuilder.from_dataframe(inventory_df)
        gb.configure_default_column(resizable=True, filterable=True, sortable=True, floatingFilter=True)
        gb.configure_selection(selection_mode="single", use_checkbox=True)
        
        # Стилизация ячеек (Адрес)
        cellsytle_jscode = JsCode("""
        function(params) {
            if (params.value === 'НЕ НАЗНАЧЕНО') {
                return {'color': 'white', 'backgroundColor': '#E74C3C', 'fontWeight': 'bold'};
            } else if (params.value === '🚚 В ЗАКАЗЕ') {
                return {'color': 'white', 'backgroundColor': '#3498DB'};
            } else {
                return {'color': '#2ECC71', 'fontWeight': 'bold', 'backgroundColor': '#1e2329'};
            }
        };
        """)
        gb.configure_column("Адрес", cellStyle=cellsytle_jscode, pinned='left', width=180)
        
        # Отображение таблицы
        grid_res = AgGrid(
            inventory_df,
            gridOptions=gb.build(),
            height=500,
            theme='alpine',
            allow_unsafe_jscode=True,
            update_on=['selectionChanged'], 
            key="global_inventory_grid"
        )

        # Обработка выбора строки
        sel_row = grid_res.get('selected_rows')
        
        if sel_row is not None and len(sel_row) > 0:
            item = sel_row.iloc[0] if isinstance(sel_row, pd.DataFrame) else sel_row[0]
            doc_id = item.get('id')
            item_name = item.get('Название товара')
            current_addr = str(item.get('Адрес', 'НЕ НАЗНАЧЕНО'))
            
            st.divider()
            
            # Основная информация - метрики с временем
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Количество", f"{item.get('Количество', 0)} шт")
            
            with col2:
                st.metric("Тип", item.get('Тип', 'Н/Д'))
            
            with col3:
                st.metric("Контрагент", item.get('Контрагент', 'Н/Д')[:15])
            
            with col4:
                # Форматирование времени с секундами
                from datetime import datetime
                try:
                    date_str = str(item.get('Дата', 'Н/Д'))
                    # Если это ISO формат с временем
                    if 'T' in date_str:
                        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                        formatted_time = dt.strftime("%d.%m.%Y %H:%M:%S")
                    else:
                        formatted_time = date_str[:10]
                except:
                    formatted_time = str(item.get('Дата', 'Н/Д'))[:10]
                
                st.metric("Дата и время", formatted_time)
            
            st.divider()
            
            # Детальная информация + Выбор адреса
            col_info, col_location = st.columns([1, 1.2])
            
            with col_info:
                st.markdown("""
                <div style="background: #1d222b; padding: 15px; border-radius: 8px; border-left: 3px solid #58a6ff;">
                    <b>📋 Информация по документу:</b>
                </div>
                """, unsafe_allow_html=True)
                
                # Форматирование полного времени с секундами
                try:
                    date_str = str(item.get('Дата', 'Н/Д'))
                    if 'T' in date_str:
                        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                        full_datetime = dt.strftime("%d.%m.%Y %H:%M:%S")
                    else:
                        full_datetime = date_str
                except:
                    full_datetime = str(item.get('Дата', 'Н/Д'))
                
                st.markdown(f"""
- **ID Товара:** `{item.get('id', 'Н/Д')}`
- **Номер документа:** {item.get('ID Документа', 'Н/Д')}
- **Контрагент:** {item.get('Контрагент', 'Н/Д')}
- **Дата и время:** 🕐 **{full_datetime}**
- **Кол-во:** {item.get('Количество', 0)} шт
                """)
            
            with col_location:
                st.markdown("""
                <div style="background: #1d222b; padding: 15px; border-radius: 8px; border-left: 3px solid #2ecc71;">
                    <b>🏪 Расположение на складе:</b>
                </div>
                """, unsafe_allow_html=True)
                
                # Выбор склада
                wh_id = st.selectbox(
                    "🏪 Склад:",
                    list(WAREHOUSE_MAP.keys()),
                    key=f"wh_{doc_id}"
                )
                
                # Генерация всех ячеек для выбранного склада
                conf = WAREHOUSE_MAP[str(wh_id)]
                all_cells = []
                for r in conf['rows']:
                    all_cells.append(f"WH{wh_id}-{r}")
                    for s in range(1, conf.get('sections', 1) + 1):
                        for t in conf.get('tiers', ['A']):
                            all_cells.append(f"WH{wh_id}-{r}-S{s}-{t}")
                
                all_cells = sorted(list(set(all_cells)))
                
                # Выбор ячейки
                default_idx = 0
                if current_addr != "НЕ НАЗНАЧЕНО" and current_addr in all_cells:
                    default_idx = all_cells.index(current_addr)
                
                selected_cell = st.selectbox(
                    "📍 Ячейка:",
                    options=all_cells,
                    index=default_idx,
                    key=f"cell_{doc_id}"
                )
                
                # Показываем карту
                try:
                    fig = get_warehouse_figure(str(wh_id), highlighted_cell=selected_cell)
                    st.plotly_chart(fig, use_container_width=True, height=300)
                except:
                    st.info("📍 Карта доступна только для некоторых складов")
                
                # Кнопка сохранения
                if st.button("💾 СОХРАНИТЬ АДРЕС", use_container_width=True, type="primary", key=f"save_{doc_id}"):
                    try:
                        from datetime import datetime
                        import time
                        
                        inv_payload = {
                            "doc_id": doc_id,
                            "item_name": item_name,
                            "cell_address": selected_cell,
                            "quantity": float(item.get('Количество', 0)),
                            "warehouse_id": str(wh_id),
                            "updated_at": datetime.now().isoformat()
                        }
                        
                        supabase.table("inventory").upsert(
                            inv_payload, 
                            on_conflict="doc_id,item_name"
                        ).execute()
                        
                        # Форматированное время для сообщения об успехе
                        success_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
                        st.success(f"✅ Адрес обновлен: {selected_cell} | Время: {success_time}")
                        time.sleep(1)
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"❌ Ошибка: {e}")

elif selected == "Карта": show_map()
elif selected == "Личный кабинет": show_profile()
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

    with tab1:
        st.subheader("📍 Конфигурация зон хранения")
        col_map, col_cfg = st.columns([2, 1])
        
        with col_map:
            wh_to_show = st.selectbox("Выберите склад для просмотра", list(WAREHOUSE_MAP.keys()))
            fig = get_warehouse_figure(wh_to_show)
            st.plotly_chart(fig, width="stretch")
        
        with col_cfg:
            st.markdown("**Добавить новую зону**")
            new_zone = st.text_input("Название зоны", placeholder="Напр: Зона C")
            row_count = st.number_input("Кол-во рядов", 1, 50, 5)
            
            if st.button("💾 Сохранить топологию", width="stretch", type="primary"):
                try:
                    supabase.table("warehouse_config").insert({
                        "warehouse": wh_to_show,
                        "zone_name": new_zone,
                        "rows": row_count
                    }).execute()
                    st.success(f"Зона {new_zone} интегрирована в систему")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Ошибка сохранения: {e}")

    with tab2:
        st.subheader("👤 Управление доступом")
        users_data = supabase.table("profiles").select("*").execute()
        df_users = pd.DataFrame(users_data.data)
        
        if not df_users.empty:
            st.dataframe(df_users, width="stretch", hide_index=True)
        
        if st.button("➕ Зарегистрировать нового сотрудника", width="stretch"):
            st.session_state.active_modal = "user_new"
            st.rerun()

    with tab4:
        st.subheader("🛠️ Обслуживание системы")
        c1, c2, c3 = st.columns(3)
        
        with c1:
            st.markdown("📦 **Экспорт данных**")
            if st.button("📊 Сформировать отчет XLSX", width="stretch"):
                st.toast("Сборка данных из БД...")
            
        with c2:
            st.markdown("⚠️ **Оптимизация**")
            if st.button("🔥 Сбросить кеш сессии", width="stretch"):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.success("Кеш очищен")
                st.rerun()
                
        with c3:
            st.markdown("🔴 **Опасная зона**")
            if st.button("🧨 УДАЛИТЬ ВСЕ ДАННЫЕ", width="stretch", type="secondary"):
                st.session_state.confirm_delete_all = True
            
            if st.session_state.get('confirm_delete_all'):
                st.error("ВНИМАНИЕ! Удаление всех записей!")
                col_yes, col_no = st.columns(2)
                if col_yes.button("ДА, УДАЛИТЬ", type="primary", width="stretch"):
                    supabase.table("main").delete().neq("id", 0).execute() 
                    st.success("База данных очищена")
                    st.session_state.confirm_delete_all = False
                    st.rerun()
                if col_no.button("ОТМЕНА", width="stretch"):
                    st.session_state.confirm_delete_all = False
                    st.rerun()

# --- 1. УМНАЯ ИНИЦИАЛИЗАЦИЯ ДАННЫХ ---
TABLES_TO_LOAD = {
    "orders": "orders",
    "main": "main_registry",
    "drivers": "drivers",
    "vehicles": "vehicles",
    "arrivals": "arrivals",
    "defects": "defects",
    "extras": "extras"
}

for state_key, db_table in TABLES_TO_LOAD.items():
    if state_key not in st.session_state or st.session_state[state_key] is None:
        with st.spinner(f'Синхронизация {state_key}...'):
            # Предполагается, что функция load_data_from_supabase определена выше
            data = load_data_from_supabase(db_table)
            st.session_state[state_key] = data if data is not None else pd.DataFrame()

# --- 2. КОНТРОЛЬ ПЕРЕХОДОВ ---
if "current_page" not in st.session_state:
    st.session_state.current_page = selected

if st.session_state.current_page != selected:
    keys_to_reset = ["active_modal", "active_edit_modal", "active_view_modal", "active_print_modal", "editing_id"]
    for key in keys_to_reset: 
        st.session_state[key] = None
    st.session_state.current_page = selected
    st.rerun()

# --- 3. ГЛАВНЫЙ ДИСПЕТЧЕР (БЕЗ ОШИБОК ИМЕНИ) ---

# --- 3. ГЛАВНЫЙ ДИСПЕТЧЕР (ФИНАЛЬНАЯ ВЕРСИЯ) ---

# ПРИОРИТЕТ 1: РЕДАКТИРОВАНИЕ
if st.session_state.get("active_edit_modal"):
    target = st.session_state.active_edit_modal
    eid = st.session_state.get("editing_id")
    if eid:
        if target == "drivers": edit_driver_modal(eid)
        elif target == "vehicles": edit_vehicle_modal(eid)
        else: edit_order_modal(eid, target)
    st.session_state.active_edit_modal = None 

# ПРИОРИТЕТ 2: ПРОСМОТР
elif st.session_state.get("active_view_modal"):
    vid = st.session_state.active_view_modal
    if str(vid).startswith("ORD"): show_order_details_modal(vid)
    elif str(vid).startswith("ARR") or str(vid).startswith("IN"): show_arrival_details_modal(vid)
    elif str(vid).startswith("DEF"): show_defect_details_modal(vid)
    elif str(vid).startswith("EXT"): show_extra_details_modal(vid)
    st.session_state.active_view_modal = None

# ПРИОРИТЕТ 3: СОЗДАНИЕ (ИСПРАВЛЕН TypeError)
elif st.session_state.get("active_modal"):
    m_type = st.session_state.active_modal
    st.session_state.active_modal = None
    
    if m_type in ["orders", "orders_new"]: 
        # ПЕРЕДАЕМ АРГУМЕНТ, который требует функция в specific_doc
        create_modal(table_key="orders")  
    elif m_type == "arrivals": 
        create_arrival_modal() # Проверь, не нужен ли и тут table_key!
    elif m_type == "extras": 
        create_extras_modal()
    elif m_type == "defects": 
        create_defect_modal()
    elif m_type == "drivers_new": 
        create_driver_modal()
    elif m_type == "vehicle_new": 
        create_vehicle_modal()






























































































































