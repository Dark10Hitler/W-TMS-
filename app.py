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
from config_topology import get_warehouse_figure,get_actual_cells
from specific_doc import create_modal, create_extras_modal, create_arrival_modal, create_defect_modal
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
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

import pytz
from datetime import datetime
from uploader import upload_to_cloudinary
from database import insert_data # Твоя функция Supabase
import qrcode
from io import BytesIO


# --- РЕЖИМ ВИТРИНЫ (Для всех, кто сканирует QR) ---
if "shelf" in st.query_params:
    shelf_id = st.query_params["shelf"]
    st.set_page_config(page_title=f"Ячейка {shelf_id}", layout="wide", initial_sidebar_state="collapsed")
    
    # CSS: Максимально чистый интерфейс
    st.markdown("""
        <style>
            #MainMenu {visibility: hidden;} 
            [data-testid="stSidebar"] {display: none;}
            footer {visibility: hidden;}
            .product-card {
                background: #f9f9f9;
                padding: 15px;
                border-radius: 10px;
                margin-bottom: 10px;
                border: 1px solid #eee;
            }
        </style>
    """, unsafe_allow_html=True)
    
    st.markdown(f"<h1 style='text-align: center;'>📍 Стеллаж: {shelf_id}</h1>", unsafe_allow_html=True)
    st.divider()

    st.write("### 📦 Товары в этой ячейке:")
    
    try:
        # Получаем товары именно для этой полки
        items = supabase.table("global_inventory").select("*").eq("cell", shelf_id).execute().data
    except Exception as e:
        st.error("Ошибка подключения к базе данных")
        items = []

    if not items:
        st.warning("В данной ячейке товаров не обнаружено.")
    else:
        for item in items:
            with st.container():
                c1, c2 = st.columns([1, 2])
                with c1:
                    pic = item['image_url'] if item['image_url'] else "https://via.placeholder.com/150"
                    st.image(pic, use_container_width=True)
                with c2:
                    st.subheader(item['name'])
                    st.info(f"Склад: {item['warehouse']}")
                    st.caption(f"📅 Дата обновления: {item['last_updated'][:10]}")
                st.divider()
    
    st.stop() # Важно: прерываем код, чтобы админка не подгрузилась ниже



def sync_to_inventory(doc_id, items_list, doc_type):
    """
    doc_id: ID документа (например, ORD-101, ARR-202, EXT-303)
    items_list: список товаров из этого документа (из JSONB)
    doc_type: '📦 ПРИХОД', '🚚 ЗАКАЗ' или '🔄 ДОПОЛНЕНИЕ'
    """
    from database import supabase
    
    inventory_records = []
    
    for item in items_list:
        # Унифицируем названия полей (так как в разных формах они могут называться по-разному)
        product_name = item.get('Название товара') or item.get('product') or item.get('Товар')
        quantity = item.get('Кол-во') or item.get('Количество') or item.get('qty', 0)
        
        if product_name:
            record = {
                "doc_id": str(doc_id),           # Связь с родительским документом
                "product_name": str(product_name),
                "quantity": float(quantity),
                "type": doc_type,                # Тип операции для аналитики
                "status": "НА СКЛАДЕ" if doc_type != "🚚 ЗАКАЗ" else "В ПУТИ",
                "last_updated": datetime.now().isoformat()
            }
            inventory_records.append(record)
    
    if inventory_records:
        # Сохраняем/обновляем в общую таблицу
        # on_conflict='doc_id, product_name' гарантирует, что мы не создадим дублей
        supabase.table("inventory").upsert(inventory_records, on_conflict="doc_id,product_name").execute()

def get_moldova_time():
    tz = pytz.timezone('Europe/Chisinau')
    return datetime.now(tz)

# При создании/обновлении:
now = get_moldova_time()
current_date = now.strftime("%Y-%m-%d")
current_time = now.strftime("%H:%M:%S")

# Инициализация геокодера (User_agent обязателен!)
geolocator = Nominatim(user_agent="imperia_logistics_monitor_2026")

@st.cache_data(ttl=3600)  # Кэшируем адрес на 1 час для одних и тех же координат
def get_address_cached(lat, lon):
    """
    Преобразует координаты в читаемый адрес с кэшированием.
    """
    if lat is None or lon is None:
        return "Координаты отсутствуют"
        
    try:
        # Округляем до 4 знаков (точность ~11 метров), чтобы улучшить попадание в кэш
        location = geolocator.reverse((lat, lon), timeout=3, language='ru')
        if location:
            # Извлекаем только важную часть адреса (улица, номер, город)
            address = location.address
            # Можно сократить адрес, если он слишком длинный
            parts = address.split(', ')
            short_address = ", ".join(parts[:3]) 
            return short_address
        return "Адрес не определен"
        
    except (GeocoderTimedOut, GeocoderServiceError):
        # Если сервис недоступен, возвращаем координаты, чтобы приложение не падало
        return f"📍 {lat:.4f}, {lon:.4f} (Ошибка связи)"
    except Exception as e:
        return "Ошибка геокодирования"

def upload_image_to_supabase(file_name, file_data, bucket_name="avatars"):
    try:
        # Очищаем имя файла от лишних символов и добавляем таймштамп
        clean_name = "".join(c for c in file_name if c.isalnum() or c in "._-").rstrip()
        path_on_supa = f"manager/{int(time.time())}_{clean_name}"
        
        # Загрузка через binary stream
        res = supabase.storage.from_(bucket_name).upload(
            path=path_on_supa,
            file=file_data,
            file_options={"content-type": "image/jpeg"} # или определять программно
        )
        
        # Получаем публичную ссылку
        public_url = supabase.storage.from_(bucket_name).get_public_url(path_on_supa)
        return public_url
    except Exception as e:
        st.error(f"Ошибка на стороне Supabase: {e}")
        return None

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


import requests
import streamlit as st

# 1. СЮДА ВСТАВЛЯЕШЬ СВОЙ АКТУАЛЬНЫЙ АДРЕС (NGROK ИЛИ CLOUDFLARE)
TRACCAR_URL = "https://posttarsal-tanisha-nondisastrous.ngrok-free.dev" 
TRACCAR_AUTH = ("denis.masliuc.speak23dev@gmail.com", "qwert12345")

@st.cache_data(ttl=10)
def get_detailed_traccar_data(endpoint="devices", params=None):
    # Чистим URL от лишних слэшей в конце и добавляем /api
    api_base = f"{TRACCAR_URL.strip().rstrip('/')}/api"
    
    # Заголовок, чтобы NGROK не показывал страницу-предупреждение
    headers = {
        'ngrok-skip-browser-warning': 'true',
        'Accept': 'application/json'
    }
    
    # --- СЦЕНАРИЙ 1: ЗАПРОС УСТРОЙСТВ И ПОЗИЦИЙ ---
    if endpoint == "devices":
        try:
            # Делаем два параллельных запроса
            dev_resp = requests.get(f"{api_base}/devices", auth=TRACCAR_AUTH, headers=headers, timeout=10)
            pos_resp = requests.get(f"{api_base}/positions", auth=TRACCAR_AUTH, headers=headers, timeout=10)
            
            if dev_resp.status_code == 200 and pos_resp.status_code == 200:
                devices_list = dev_resp.json()
                positions_list = pos_resp.json()
                
                # Превращаем список в словарь {id: данные}, чтобы удобнее искать
                devices_dict = {d['id']: d for d in devices_list}
                return devices_dict, positions_list
            
            else:
                st.sidebar.warning(f"⚠️ Статус API: Dev({dev_resp.status_code}) Pos({pos_resp.status_code})")
                return {}, []
                
        except Exception as e:
            st.sidebar.error(f"📡 Ошибка связи (devices): {e}")
            return {}, []
    
    # --- СЦЕНАРИЙ 2: ЗАПРОС ОТЧЕТОВ (С ПАРАМЕТРАМИ) ---
    else:
        try:
            resp = requests.get(f"{api_base}/{endpoint}", auth=TRACCAR_AUTH, headers=headers, params=params, timeout=15)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 401:
                st.error("🔒 Ошибка авторизации: проверь логин/пароль Traccar")
                return []
            else:
                st.error(f"❌ Ошибка API ({endpoint}): {resp.status_code}")
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

st.set_page_config(layout="wide", page_title="W&TMS", page_icon="🏛️")

st.markdown("""
<style>
    /* 1. ПОЛНОЕ УДАЛЕНИЕ ВЕРХНЕЙ ПОЛОСЫ И ДЕКОРАЦИЙ */
    header { visibility: hidden; height: 0px; }
    [data-testid="stHeader"] { display: none; }
    [data-testid="stDecoration"] { display: none; } /* Тонкая цветная полоска сверху */
    
    /* 2. ШРИФТЫ И ОСНОВНОЙ ФОН */
    @import url('https://fonts.googleapis.com/css2?family=Segoe+UI:wght@400;600;700&display=swap');
    
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Segoe UI', system-ui, -apple-system, sans-serif !important;
        background-color: #F3F3F3;
        color: #1B1B1B;
    }

    /* Адаптивный контейнер: убираем лишние отступы сверху */
    .block-container { 
        padding-top: 1rem !important; 
        padding-bottom: 1rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
        max-width: 100%; /* Растягиваем на весь экран */
    }

    /* 3. САЙДБАР (Стиль Windows 11) */
    [data-testid="stSidebar"] {
        background-color: #FFFFFF !important;
        border-right: 1px solid #E5E5E5;
    }

    /* 4. АДАПТИВНЫЕ КАРТОЧКИ МЕТРИК */
    div[data-testid="stMetric"] {
        background-color: #FFFFFF;
        border: 1px solid #E5E5E5;
        border-radius: 8px;
        padding: 1.5% 2% !important; /* Процентные отступы для адаптивности */
        box-shadow: 0 2px 4px rgba(0,0,0,0.04);
        transition: all 0.2s ease-in-out;
    }

    div[data-testid="stMetric"]:hover {
        box-shadow: 0 6px 15px rgba(0,0,0,0.1);
        transform: translateY(-2px);
        border-color: #0067C0;
    }

    /* Настройка размеров текста метрик, чтобы не "ломались" на малых экранах */
    div[data-testid="stMetricLabel"] { 
        font-size: clamp(0.8rem, 1vw, 1rem) !important; 
        color: #5F6368 !important; 
    }
    div[data-testid="stMetricValue"] { 
        font-size: clamp(1.2rem, 2vw, 2.2rem) !important; 
        font-weight: 700 !important; 
    }

    /* 5. КНОПКИ (Умный размер) */
    .stButton>button {
        width: 100%; /* На мобильных кнопка будет во всю ширину */
        max-width: fit-content; /* На десктопе - по размеру текста */
        min-width: 120px;
        border-radius: 6px;
        padding: 0.6rem 1.2rem;
        font-weight: 600;
        background-color: #FFFFFF;
        border: 1px solid #D1D1D1;
        transition: all 0.2s;
    }

    .stButton>button[kind="primary"] {
        background-color: #0067C0;
        color: white;
        border: none;
    }

    /* 6. АДАПТИВНОСТЬ ДЛЯ ТАБЛИЦ И ИНПУТОВ */
    .stTextInput input, .stSelectbox div {
        border-radius: 6px !important;
    }

    /* 7. МЕДИА-ЗАПРОСЫ (Для разных экранов) */
    @media (max-width: 768px) {
        .block-container {
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }
        /* Увеличиваем кликабельные зоны на телефонах */
        .stButton>button {
            height: 48px;
        }
    }

    /* 8. ТАБЛИЦЫ AgGrid (Windows Style) */
    .ag-theme-alpine {
        --ag-border-radius: 8px;
        --ag-header-height: 40px;
        --ag-row-height: 45px;
        --ag-font-size: 14px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    }

    /* Скроллбары */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-thumb { background: #C1C1C1; border-radius: 10px; }
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
    with st.spinner("🚀 Загрузка системы..."):
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

import streamlit as st
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode

def render_aggrid_table(table_key, title):
    """
    Универсальный компонент для отображения данных из Supabase с использованием AgGrid.
    Исправлена ошибка передачи аргумента table_key в функции создания.
    """
    # --- 2. ПРОВЕРКА И ЗАГРУЗКА ДАННЫХ ---
    if table_key not in st.session_state or st.session_state[table_key] is None:
        with st.spinner(f"📡 Синхронизация {title}..."):
            st.session_state[table_key] = load_data_from_supabase(table_key)
    
    df = st.session_state[table_key].copy()
    
    if df.empty:
        # Создаем пустую структуру, чтобы AgGrid не выдавал ошибку
        df = pd.DataFrame(columns=['id', 'client_name', 'status', 'created_at']) 

    # --- 3. ИНТЕРФЕЙС ЗАГОЛОВКА И КНОПКА СОЗДАНИЯ ---
    st.markdown("---")
    c_title, c_act1 = st.columns([7, 3])
    
    with c_title:
        count = len(df)
        st.markdown(f"### 🚀 {title} <span style='font-size: 0.5em; color: #888;'>| Всего: {count}</span>", unsafe_allow_html=True)
    
    with c_act1:
        if table_key != "main":
            if st.button(f"➕ ДОБАВИТЬ", key=f"add_btn_{table_key}", use_container_width=True, type="primary"):
                if table_key == "orders": 
                    create_modal(table_key)
                elif table_key == "arrivals": 
                    create_arrival_modal(table_key)
                elif table_key == "extras": 
                    create_extras_modal(table_key)
                elif table_key == "defects": 
                    create_defect_modal(table_key)  # ← БЕЗ ИЗМЕНЕНИЙ (уже правильно!)
                elif table_key == "drivers": 
                    create_driver_modal(table_key)
                elif table_key == "vehicles": 
                    create_vehicle_modal(table_key)

    # --- 4. НАСТРОЙКА ПАРАМЕТРОВ ГРИДА (AG-GRID) ---
    gb = GridOptionsBuilder.from_dataframe(df)
    
    gb.configure_default_column(
        resizable=True, 
        sortable=True, 
        filterable=True, 
        filter='agTextColumnFilter',
        minWidth=100,
        floatingFilter=True, 
        suppressMovable=False
    )

    # Цветовая индикация статусов через JavaScript
    cell_style_jscode = JsCode("""
    function(params) {
        if (params.value === 'ПРИХОД' || params.value === 'Доставлено' || params.value === 'Завершено') {
            return {'color': 'white', 'backgroundColor': '#2E7D32', 'fontWeight': 'bold'};
        } else if (params.value === 'ЗАЯВКА' || params.value === 'В пути' || params.value === 'Активен') {
            return {'color': 'white', 'backgroundColor': '#1565C0', 'fontWeight': 'bold'};
        } else if (params.value === 'БРАК' || params.value === 'ОТМЕНЕНА' || params.value === 'Уволен') {
            return {'color': 'white', 'backgroundColor': '#C62828', 'fontWeight': 'bold'};
        } else if (params.value === 'НОВЫЙ' || params.value === 'Ожидание') {
            return {'color': '#333', 'backgroundColor': '#FFD54F', 'fontWeight': 'bold'};
        }
        return null;
    }
    """)

    if "Секция" in df.columns:
        gb.configure_column("Секция", cellStyle=cell_style_jscode, pinned='left', width=130)
    
    if "Статус" in df.columns or "status" in df.columns:
        col_name = "Статус" if "Статус" in df.columns else "status"
        gb.configure_column(col_name, cellStyle=cell_style_jscode, width=150)

    # Скрываем технические колонки, чтобы не загромождать таблицу
    hidden_cols = ["items_data", "photo_url", "coordinates", "description", "metadata", "updated_at"]
    for col in hidden_cols:
        if col in df.columns:
            gb.configure_column(col, hide=True)

    gb.configure_selection(selection_mode="single", use_checkbox=False)
    gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=15)
    
    gridOptions = gb.build()

    # --- 5. ОТОБРАЖЕНИЕ ТАБЛИЦЫ ---
    grid_response = AgGrid(
        df,
        gridOptions=gridOptions,
        height=500,
        theme='alpine', 
        update_on=['selectionChanged'], 
        allow_unsafe_jscode=True,
        key=f"grid_component_{table_key}"
    )

    # --- 6. ОБРАБОТКА ВЫБОРА И КНОПКИ ДЕЙСТВИЙ ---
    selected_rows = grid_response.selected_rows
    row_data = None

    if selected_rows is not None:
        if isinstance(selected_rows, pd.DataFrame) and not selected_rows.empty:
            row_data = selected_rows.iloc[0].to_dict()
        elif isinstance(selected_rows, list) and len(selected_rows) > 0:
            row_data = selected_rows[0]

    if row_data:
        entry_id = row_data.get("id")
        st.session_state.last_selected_id = entry_id
        
        # Интеллектуальный роутинг для сводной таблицы
        target_table = table_key
        if table_key == "main":
            id_str = str(entry_id).upper()
            if id_str.startswith("ORD"): target_table = "orders"
            elif id_str.startswith("ARR") or id_str.startswith("IN"): target_table = "arrivals"
            elif id_str.startswith("DEF"): target_table = "defects"
            elif id_str.startswith("EXT"): target_table = "extras"
            else:
                secc = row_data.get("Секция", "")
                if secc == "ПРИХОД": target_table = "arrivals"
                elif secc == "ЗАЯВКА": target_table = "orders"

        st.success(f"📂 Выбран документ: **{entry_id}**")
        
        # Ряд кнопок управления (Изменить, Просмотр, Печать)
        btn_col1, btn_col2, btn_col3, btn_spacer = st.columns([1, 1, 1, 2])
        
        with btn_col1:
            if st.button("⚙️ ИЗМЕНИТЬ", key=f"ed_btn_{entry_id}", use_container_width=True):
                if target_table == "orders": 
                    edit_order_modal(entry_id)
                elif target_table == "arrivals": 
                    edit_arrival_modal(entry_id)
                elif target_table == "extras": 
                    edit_extra_modal(entry_id)
                elif target_table == "defects": 
                    edit_defect_modal(entry_id)
                elif target_table == "drivers": 
                    edit_driver_modal(entry_id)
                elif target_table == "vehicles": 
                    edit_vehicle_modal(entry_id)

        with btn_col2:
            if st.button("🔍 ПРОСМОТР", key=f"vw_btn_{entry_id}", use_container_width=True):
                if target_table == "orders": show_order_details_modal(entry_id)
                elif target_table == "arrivals": show_arrival_details_modal(entry_id)
                elif target_table == "defects": show_defect_details_modal(entry_id)
                elif target_table == "extras": show_extra_details_modal(entry_id)

        with btn_col3:
            if st.button("🖨️ ПЕЧАТЬ", key=f"pr_btn_{entry_id}", use_container_width=True):
                if target_table == "orders": show_print_modal(entry_id)
                elif target_table == "arrivals": show_arrival_print_modal(entry_id)
                elif target_table == "defects": show_defect_print_modal(entry_id)
                elif target_table == "extras": show_extra_print_modal(entry_id)

    else:
        st.info("💡 Выберите строку для управления записью.")

    st.markdown("---")
     
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
        popup="🏢 <b>LOGISTICS WAREHOUSE</b>",
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
    st.markdown("<h1 class='section-head'>👤 Цифровой Профиль Управляющего</h1>", unsafe_allow_html=True)

    # --- 1. ПЕРВИЧНАЯ ЗАГРУЗКА В SESSION STATE ---
    # Мы загружаем данные из базы в сессию только если их там еще нет
    if 'mgr_data' not in st.session_state:
        try:
            res = supabase.table("manager_profile").select("*").order("id").limit(1).execute()
            if res.data:
                st.session_state.mgr_data = res.data[0]
            else:
                st.warning("Профиль не найден. Создайте его.")
                if st.button("➕ Создать профиль"):
                    supabase.table("manager_profile").insert({"full_name": "Новый Управляющий"}).execute()
                    del st.session_state.mgr_data # Сброс для перезагрузки
                    st.rerun()
                return
        except Exception as e:
            st.error(f"Ошибка базы: {e}")
            return

    # Локальная ссылка для удобства доступа к данным в текущем стейте
    m_id = st.session_state.mgr_data['id']

    # --- 2. ВИЗУАЛИЗАЦИЯ (ФОТО) ---
    col_face, col_workplace = st.columns([1, 2])
    
    avatar_url = st.session_state.mgr_data.get('avatar_url') or "https://cdn-icons-png.flaticon.com/512/3135/3135715.png"
    work_url = st.session_state.mgr_data.get('workplace_photo_url') or "https://img.freepik.com/premium-photo/modern-warehouse-with-racks-goods-generative-ai_124507-449.jpg"

    with col_face:
        st.image(avatar_url, caption="Фото управляющего", use_container_width=True)
        new_avatar = st.file_uploader("🖼️ Сменить фото", type=['png', 'jpg', 'jpeg'], key="upd_ava")
        if new_avatar and st.button("💾 Загрузить лицо"):
            url = upload_image_to_supabase(new_avatar.name, new_avatar.getvalue())
            if url:
                supabase.table("manager_profile").update({"avatar_url": url}).eq("id", m_id).execute()
                st.session_state.mgr_data['avatar_url'] = url # Сразу обновляем в сессии
                st.rerun()

    with col_workplace:
        st.image(work_url, caption=st.session_state.mgr_data.get('workplace_name') or "Место работы", use_container_width=True)
        new_work = st.file_uploader("🏗️ Сменить фото склада", type=['png', 'jpg', 'jpeg'], key="upd_work")
        if new_work and st.button("💾 Загрузить склад"):
            url = upload_image_to_supabase(new_work.name, new_work.getvalue())
            if url:
                supabase.table("manager_profile").update({"workplace_photo_url": url}).eq("id", m_id).execute()
                st.session_state.mgr_data['workplace_photo_url'] = url # Сразу обновляем в сессии
                st.rerun()

    st.markdown("---")

    # --- 3. ПОДГОТОВКА ДАННЫХ ДЛЯ РЕДАКТОРА ---
    # Список полей, которые мы разрешаем править
    field_labels = {
        'full_name': '1. ФИО Управляющего',
        'position': '2. Должность',
        'phone': '3. Телефон',
        'email': '4. Email',
        'workplace_name': '5. Название Объекта',
        'employees_count': '6. Кол-во сотрудников',
        'workplace_address': '7. Адрес Объекта',
        'home_address': '8. Домашний Адрес',
        'working_hours': '9. График работы'
    }

    # Формируем DF для редактора прямо из Session State
    edit_list = []
    for k, label in field_labels.items():
        v = st.session_state.mgr_data.get(k, "")
        edit_list.append({
            "key": k,
            "Параметр": label,
            "Значение": "" if v is None else str(v)
        })

    df_edit = pd.DataFrame(edit_list).sort_values("Параметр")

    # --- 4. РЕДАКТОР ПРОФИЛЯ ---
    st.write("### ⚙️ Редактирование профиля")
    # Мы присваиваем результат редактора переменной edited_df
    # Важно: он обновляется ПРИ КАЖДОМ ИЗМЕНЕНИИ ячейки
    edited_df = st.data_editor(
        df_edit,
        column_config={
            "key": None, # Скрываем
            "Параметр": st.column_config.TextColumn(disabled=True),
            "Значение": st.column_config.TextColumn(width="large")
        },
        use_container_width=True,
        hide_index=True,
        key="editor_mgr_main"
    )

    # --- 5. СИНХРОНИЗАЦИЯ (МЕТРИКИ ЧИТАЮТ ИЗ РЕДАКТОРА) ---
    # Превращаем DF из редактора в словарь для мгновенного доступа
    current_state = {row["key"]: row["Значение"] for _, row in edited_df.iterrows()}

    st.markdown("---")
    st.subheader("📊 Текущие показатели (в реальном времени)")
    c1, c2, c3 = st.columns(3)
    
    # Теперь метрики берут данные напрямую из виджета редактора через current_state!
    val_emp = current_state.get('employees_count') or "0"
    val_work = current_state.get('workplace_name') or "Не указано"
    val_phone = current_state.get('phone') or "---"

    c1.metric("Персонал", f"{val_emp} чел.")
    c2.metric("Объект", val_work)
    c3.metric("Связь", val_phone)

    with st.expander("📍 Развернутые контакты"):
        st.write(f"🏢 **Офис:** {current_state.get('workplace_address') or '---'}")
        st.write(f"📧 **Email:** {current_state.get('email') or '---'}")
        st.write(f"🏠 **Дом:** {current_state.get('home_address') or '---'}")

    st.markdown("---")

    # --- 6. СОХРАНЕНИЕ В ОБЛАКО ---
    if st.button("💾 ЗАФИКСИРОВАТЬ ИЗМЕНЕНИЯ В БАЗЕ", type="primary", use_container_width=True):
        try:
            with st.spinner("Синхронизация с облаком..."):
                update_payload = {}
                for k, v in current_state.items():
                    # Приведение типов для базы
                    if k == 'employees_count':
                        # Убираем лишние пробелы и проверяем, число ли это
                        clean_val = str(v).strip()
                        update_payload[k] = int(clean_val) if clean_val.isdigit() else 0
                    else:
                        update_payload[k] = v if str(v).strip() != "" else None
                
                # Обновляем в Supabase
                supabase.table("manager_profile").update(update_payload).eq("id", m_id).execute()
                
                # Обновляем Session State, чтобы при следующем прогоне данные были актуальны
                st.session_state.mgr_data.update(update_payload)
                
                st.success("✅ Профиль успешно сохранен в базе данных!")
                time.sleep(1)
                st.rerun()
                
        except Exception as e:
            st.error(f"Ошибка сохранения: {e}")
            
with st.sidebar:
    st.markdown("""
        <div style='padding: 10px 0px;'>
            <h2 style='color: #1E1E1E; font-family: "Segoe UI", Tahoma, Geneva, sans-serif; font-size: 22px; font-weight: 600;'>
                📦 LOGISTICS W&TMS
            </h2>
            <p style='color: #666; font-size: 12px; margin-top: -10px;'>Warehouse Management System</p>
        </div>
    """, unsafe_allow_html=True)

    selected = option_menu(
        menu_title=None, # Убираем заголовок меню для минимализма
        options=[
            "Main", "База Данных", "Заявки", "Приходы", 
            "Дополнения", "Брак", "Карта", "Аналитика", "Настройки"
        ],
        icons=[
            "house", "database-fill", "clipboard2-check", "box-arrow-in-down", 
            "plus-circle", "exclamation-octagon", "map", "graph-up-arrow", "gear"
        ],
        menu_icon="cast",
        default_index=0,
        styles={
            "container": {
                "padding": "0!important", 
                "background-color": "#FFFFFF", # Чистый белый фон
                "border-radius": "0px"
            },
            "icon": {
                "color": "#5F6368", # Спокойный серый для иконок
                "font-size": "18px"
            },
            "nav-link": {
                "font-size": "14px", 
                "text-align": "left", 
                "margin": "0px", 
                "color": "#3C4043", # Цвет текста Windows Light
                "font-family": "Segoe UI",
                "--hover-color": "#F1F3F4" # Светло-серый при наведении
            },
            "nav-link-selected": {
                "background-color": "#E8F0FE", # Нежно-голубой фон (как в Windows/Google)
                "color": "#1A73E8", # Акцентный синий цвет текста
                "font-weight": "600",
                "border-left": "4px solid #1A73E8" # Полоска слева для акцента
            },
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
        
if selected == "Main": render_aggrid_table("main", "Основной Реестр")
elif selected == "Заявки": render_aggrid_table("orders", "Заявки")
elif selected == "Приходы": render_aggrid_table("arrivals", "Приходы")
elif selected == "Брак": render_aggrid_table("defects", "Журнал Брака")
elif selected == "Дополнения": render_aggrid_table("extras", "Дополнения")
elif selected == "Аналитика":
    st.title("Транспортный анализ")
    
    # --- 1. ФУНКЦИЯ СИНХРОНИЗАЦИИ (Автоматический период: последние 24 часа) ---
    def get_traccar_reports_sync(v_id):
        # Автоматический расчет интервала: от (сейчас - 24ч) до (сейчас)
        now = datetime.now()
        yesterday = now - timedelta(days=1)
        
        # Формат ISO 8601 для API Traccar (Z - UTC)
        iso_start = yesterday.strftime('%Y-%m-%dT%H:%M:%SZ')
        iso_end = now.strftime('%Y-%m-%dT%H:%M:%SZ')
        
        api_url = f"{TRACCAR_URL.rstrip('/')}/api/reports/route"
        params = {
            "deviceId": v_id,
            "from": iso_start,
            "to": iso_end
        }
        headers = {
            "Accept": "application/json",
            "ngrok-skip-browser-warning": "true"
        }
        
        try:
            resp = requests.get(api_url, auth=TRACCAR_AUTH, params=params, headers=headers, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                if not data:
                    return None, "Данные за последние 24 часа не найдены на сервере."
                return data, None
            return None, f"Ошибка сервера Traccar: {resp.status_code}"
        except Exception as e:
            return None, f"Ошибка соединения: {str(e)}"

    # --- 2. МАТЕМАТИЧЕСКИЕ ФУНКЦИИ (Гео-калькулятор) ---
    def calculate_haversine_distance(lat1, lon1, lat2, lon2):
        import math
        R = 6371.0  # Радиус Земли в километрах
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    def get_attr(attr, keys, default=0):
        if not isinstance(attr, dict): return default
        for key in keys:
            if key in attr: return attr[key]
        return default

    # --- 3. ПАНЕЛЬ УПРАВЛЕНИЯ ---
    devices_dict, _ = get_detailed_traccar_data()
    
    v_name = st.selectbox("🎯 Выберите ТС для мгновенного аудита", 
                          options=[d['name'] for d in devices_dict.values()])
    v_id = next((id for id, d in devices_dict.items() if d['name'] == v_name), None)

    # Единая кнопка запуска полной синхронизации
    if st.button("🚀 ЗАПУСТИТЬ ПОЛНУЮ СИНХРОНИЗАЦИЮ (24ч)", type="primary", use_container_width=True):
        with st.spinner(f"🔄 Соединение с Traccar Cloud: Анализ систем {v_name}..."):
            raw_data, error = get_traccar_reports_sync(v_id)
            
            if error:
                st.error(f"🛑 {error}")
            else:
                import pandas as pd
                df_raw = pd.DataFrame(raw_data)
                
                # Базовая обработка времени
                df_raw['dt'] = pd.to_datetime(df_raw['deviceTime'])
                df_raw = df_raw.sort_values('dt')

                # РАСЧЕТ ПРОБЕГА ПО КООРДИНАТАМ (Точный метод)
                coords_dist = [0.0]
                for i in range(1, len(df_raw)):
                    d = calculate_haversine_distance(
                        df_raw.iloc[i-1]['latitude'], df_raw.iloc[i-1]['longitude'],
                        df_raw.iloc[i]['latitude'], df_raw.iloc[i]['longitude']
                    )
                    # Фильтрация GPS выбросов (прыжок > 5км между точками игнорируем)
                    coords_dist.append(d if d < 5.0 else 0.0)
                
                df_raw['step_dist_km'] = coords_dist
                df_raw['speed_kmh'] = round(df_raw['speed'] * 1.852, 1)
                
                # Одометр только для отображения общего пробега ТС
                df_raw['total_odo_sensor'] = df_raw['attributes'].apply(
                    lambda x: get_attr(x, ['totalDistance', 'odometer']) / 1000.0
                )

                # Сохраняем результат в сессию
                st.session_state.audit_results = {
                    'df': df_raw,
                    'v_name': v_name,
                    'period': "Последние 24 часа (Автоматически)"
                }
                
                st.success(f"✅ Синхронизация завершена. Обработано {len(df_raw)} точек телеметрии.")
                st.rerun()

    # --- 4. ОТОБРАЖЕНИЕ РЕЗУЛЬТАТОВ (ГЛУБОКИЙ АУДИТ) ---
    audit_data = st.session_state.get('audit_results')

    if audit_data is not None:
        df = audit_data.get('df')

        if df is not None and not df.empty:
            st.header(f"🛠️ Технический аудит систем: {audit_data['v_name']}")
            
            # --- РАСЧЕТЫ ДЛЯ МЕТРИК ---
            actual_period_km = df['step_dist_km'].sum() # СУММА ВСЕХ ШАГОВ ПО ГЕОМЕТРИИ
            total_dist_end = df['total_odo_sensor'].iloc[-1] # ПОСЛЕДНЕЕ ЗНАЧЕНИЕ ОДОМЕТРА

            moving_df = df[df['speed_kmh'] > 2]
            avg_speed = moving_df['speed_kmh'].mean() if not moving_df.empty else 0
            max_speed = df['speed_kmh'].max()
            
            overspeeds_df = df[df['speed_kmh'] > 90]
            overspeeds_count = len(overspeeds_df)
            
            df['accel_ms2'] = df['speed_kmh'].diff().fillna(0) / 3.6
            hard_maneuvers = len(df[df['accel_ms2'].abs() > 3.0]) 

            base_rate = 9.0  
            
            if not overspeeds_df.empty:
                avg_over_speed = overspeeds_df['speed_kmh'].mean() - 90
                speed_factor = 1 + (avg_over_speed / 10) * 0.15
            else:
                speed_factor = 1.0

            positive_accel = df[df['accel_ms2'] > 0.5]['accel_ms2']
            accel_factor = 1 + (max(0, positive_accel.mean() - 0.8) * 0.2) if not positive_accel.empty else 1.0

            load_factor = min(1.4, speed_factor * accel_factor)
            fuel_total = (actual_period_km / 100) * base_rate * load_factor
            cost_mdl = fuel_total * 21.0
            extra_fuel = max(0, fuel_total - (actual_period_km / 100 * base_rate))

            # --- ВИЗУАЛИЗАЦИЯ (МЕТРИКИ ИСПРАВЛЕННЫЕ) ---
            c1, c2, c3 = st.columns(3)
            c1.metric("🏁 Пробег (Период/GPS)", f"{actual_period_km:.2f} км")
            c2.metric("📟 Total Odometer (ТС)", f"{total_dist_end:.2f} км")
            c3.metric("⏱️ Ср. Скорость", f"{avg_speed:.1f} км/ч", delta=f"Max: {max_speed}")

            st.markdown("---")
            
            e1, e2, e3, e4 = st.columns(4)
            e1.metric("⛽ Расход топлива", f"{fuel_total:.1f} л", 
                      delta=f"{((load_factor-1)*100):.1f}% Нагрузка", delta_color="inverse")
            e2.metric("💰 Финансовый итог", f"{int(cost_mdl)} MDL")
            e3.metric("⚠️ Нарушения (>90)", overspeeds_count, 
                      delta="Критично" if overspeeds_count > 10 else "Норма", delta_color="inverse")
            e4.metric("💢 Резкие маневры", hard_maneuvers)

            # Инженерное заключение
            st.info(f"""
            **Инженерное заключение:**
            * На дистанции **{actual_period_km:.2f} км** (расчет по GPS) зафиксировано **{hard_maneuvers}** резких маневров и **{overspeeds_count}** превышений.
            * Это привело к работе двигателя с коэффициентом нагрузки **{load_factor:.2f}x**.
            * Фактический перерасход составил **{extra_fuel:.2f} л** топлива.
            * Ресурс моторного масла снижается на **{min(25, 0.1 * (hard_maneuvers + overspeeds_count/10)):.1f}%** быстрее стандартного цикла.
            """)

            # --- БЛОК КАРТЫ ---
            import folium
            from streamlit_folium import st_folium
            from folium.plugins import MarkerCluster, AntPath, Fullscreen
            from branca.element import Template, MacroElement

            st.markdown("### 🗺️ Детальный гео-аудит маршрута")
            avg_lat, avg_lon = df['latitude'].mean(), df['longitude'].mean()
            m = folium.Map(location=[avg_lat, avg_lon], zoom_start=13, tiles="cartodbpositron", control_scale=True)
            Fullscreen().add_to(m)

            path_points = df[['latitude', 'longitude']].values.tolist()
            AntPath(locations=path_points, color="#1E90FF", pulse_color="#ffffff", weight=4, opacity=0.7, delay=1000).add_to(m)

            marker_cluster = MarkerCluster(name="Группы нарушений", control=True).add_to(m)

            # Превышения скорости
            for _, row in overspeeds_df.iterrows():
                folium.Marker(
                    location=[row['latitude'], row['longitude']],
                    icon=folium.Icon(color='orange', icon='gauge-high', prefix='fa'),
                    popup=f"Скорость: {row['speed_kmh']} км/ч",
                ).add_to(marker_cluster)

            # Резкое торможение
            df['speed_delta'] = df['speed_kmh'].diff().fillna(0)
            brakes = df[df['speed_delta'] < -18]
            for _, row in brakes.iterrows():
                folium.Marker(
                    location=[row['latitude'], row['longitude']],
                    icon=folium.Icon(color='red', icon='triangle-exclamation', prefix='fa'),
                    popup=f"Торможение: {row['speed_delta']:.1f} км/ч",
                ).add_to(marker_cluster)

            # Старт и Финиш
            folium.Marker(path_points[0], icon=folium.Icon(color='green', icon='play', prefix='fa'), tooltip="Старт").add_to(m)
            folium.Marker(path_points[-1], icon=folium.Icon(color='black', icon='flag-checkered', prefix='fa'), tooltip="Финиш").add_to(m)

            st_folium(m, width=1300, height=600, key="audit_premium_map")

            # --- ПРЕДИКТИВНЫЙ ИЗНОС ---
            st.divider()
            st.subheader("🔧 Предиктивный износ систем (Digital Twin)")
            t1, t2, t3 = st.columns(3)
            
            brake_wear = min(100, (len(brakes) * 4) + (actual_period_km / 50))
            t1.write(f"**Износ колодок: {int(brake_wear)}%**")
            t1.progress(brake_wear / 100)

            engine_load_val = min(100, (hard_maneuvers * 5) + (max_speed / 1.5))
            t2.write(f"**Нагрузка ДВС/КПП: {int(engine_load_val)}%**")
            t2.progress(engine_load_val / 100)

            safety_score = max(0, 100 - (len(brakes) * 5) - (overspeeds_count * 2))
            t3.write(f"**Safety Score: {int(safety_score)}%**")
            t3.progress(safety_score / 100)

            # --- ГРАФИК ТЕЛЕМЕТРИИ ---
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
                x=alt.X('dt:T', title='Временная шкала'),
                y=alt.Y('speed_kmh:Q', title='Скорость (км/ч)'),
                tooltip=['dt', 'speed_kmh']
            ).properties(height=400).interactive()
            
            st.altair_chart(chart, use_container_width=True)

            # Управление данными
            st.divider()
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 СКАЧАТЬ ОТЧЕТ В CSV", csv, f"audit_{audit_data['v_name']}.csv", "text/csv", use_container_width=True)
            with col_btn2:
                if st.button("🗑️ ОЧИСТИТЬ АУДИТ", type="secondary", use_container_width=True):
                    st.session_state.audit_results = None
                    st.rerun()
        else:
            st.warning("⚠️ Таблица данных аудита пуста.")
    else:
        st.info("🔍 Данные аудита еще не сформированы. Запустите проверку.")
            
            
# --- 2. АДМИН-ПАНЕЛЬ (БАЗА ДАННЫХ) ---
elif selected == "База Данных":
    BASE_URL = "https://4nrmgw3mde695us2cdnt9q.streamlit.app/"

    st.markdown("## 🛡️ Управление базой и топологией")

    # 1. Сначала рисуем поле поиска
    search_query = st.text_input(
        "🔍 Быстрый поиск по названию", 
        placeholder="Введите название и нажмите Enter...", 
        key="search_input"
    ).strip().lower()

    # 2. Определяем функции-диалоги (они должны быть объявлены до вызова)
    @st.dialog("🖨 Подготовка ячейки")
    def qr_generator():
        st.write("### Выбор адреса")
        wh = st.selectbox("Склад", list(WAREHOUSE_MAP.keys()), key="qr_wh")
        cell = st.selectbox("Полка", get_actual_cells(wh), key="qr_cell")
        
        st.write("---")
        fig_qr = get_warehouse_figure(wh, highlighted_cell=cell)
        fig_qr.add_annotation(
            x=cell, y=0.5, text="ВЫБРАНО",
            showarrow=True, arrowhead=2, arrowcolor="red", ax=0, ay=-40,
            bgcolor="black", font=dict(color="white")
        )
        fig_qr.update_layout(height=300, margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig_qr, use_container_width=True)
        
        qr_link = f"{BASE_URL}?shelf={cell}"
        st.code(qr_link, language="text")
        st.caption("☝️ Скопируйте ссылку для быстрого перехода с компьютера")

        import qrcode
        from io import BytesIO
        qr_img = qrcode.make(qr_link)
        buf = BytesIO()
        qr_img.save(buf, format="PNG")
        st.image(buf.getvalue(), width=200, caption=f"QR-код для {cell}")
        st.download_button("💾 СКАЧАТЬ QR", buf.getvalue(), f"QR_{cell}.png", use_container_width=True, type="primary")

    @st.dialog("📦 Изменение данных товара")
    def product_editor(item=None):
        name = st.text_input("Название", value=item['name'] if item else "")
        wh = st.selectbox("Склад", list(WAREHOUSE_MAP.keys()), 
                          index=list(WAREHOUSE_MAP.keys()).index(item['warehouse']) if item else 0)
        cell = st.selectbox("Ячейка", get_actual_cells(wh), 
                           index=get_actual_cells(wh).index(item['cell']) if item else 0)
        
        new_img = st.file_uploader("📸 Сменить фото", type=['jpg', 'png'])
        
        st.write("Место на карте:")
        fig_edit = get_warehouse_figure(wh, highlighted_cell=cell)
        fig_edit.update_layout(height=200, margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig_edit, use_container_width=True)

        if st.button("💾 СОХРАНИТЬ ИЗМЕНЕНИЯ", use_container_width=True, type="primary"):
            with st.spinner("Синхронизация..."):
                final_url = item['image_url'] if item else None
                if new_img: final_url = upload_to_cloudinary(new_img, "inventory")
                
                payload = {"name": name, "image_url": final_url, "warehouse": wh, "cell": cell, "last_updated": datetime.now().isoformat()}
                
                if item: supabase.table("global_inventory").update(payload).eq("id", item['id']).execute()
                else: supabase.table("global_inventory").insert(payload).execute()
                st.rerun()

    # 3. Кнопки управления
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("➕ ДОБАВИТЬ ТОВАР", use_container_width=True, type="primary"): 
            product_editor()
    with col_btn2:
        if st.button("🖨 QR И ССЫЛКА ПОЛКИ", use_container_width=True): 
            qr_generator()

    # 4. ЛОГИКА ЗАГРУЗКИ И ФИЛЬТРАЦИИ (КРИТИЧЕСКИЙ МОМЕНТ)
    try:
        # Получаем свежие данные
        all_data = supabase.table("global_inventory").select("*").order("name").execute().data
        
        # Фильтруем список на основе ввода в поиске
        if search_query:
            display_items = [i for i in all_data if search_query in i['name'].lower()]
        else:
            display_items = all_data
            
    except Exception as e:
        st.error(f"Ошибка связи с базой: {e}")
        display_items = []

    st.divider()

    # 5. Вывод отфильтрованного списка
    if not display_items:
        st.info("Товары не найдены.")
    else:
        for prod in display_items:
            with st.container():
                c_img, c_txt, c_loc, c_act = st.columns([1, 4, 2, 1.2])
                
                with c_img:
                    st.image(prod['image_url'] if prod['image_url'] else "https://via.placeholder.com/100", width=80)
                with c_txt:
                    st.markdown(f"**{prod['name']}**")
                    st.markdown(f"<span style='color:white; background:red; padding:2px 6px; border-radius:4px;'>{prod['cell']}</span>", unsafe_allow_html=True)
                with c_loc:
                    if st.button("📍 ГДЕ?", key=f"loc_{prod['id']}", use_container_width=True):
                        st.session_state[f"map_{prod['id']}"] = not st.session_state.get(f"map_{prod['id']}", False)
                with c_act:
                    ce, cd = st.columns(2)
                    if ce.button("✏️", key=f"ed_{prod['id']}"): product_editor(prod)
                    if cd.button("🗑️", key=f"dl_{prod['id']}"):
                        supabase.table("global_inventory").delete().eq("id", prod['id']).execute()
                        st.rerun()

                # Карта внутри списка
                if st.session_state.get(f"map_{prod['id']}"):
                    st.info(f"Склад: {prod['warehouse']} | Стеллаж: {prod['cell']}")
                    fig = get_warehouse_figure(prod['warehouse'], highlighted_cell=prod['cell'])
                    fig.add_annotation(
                        x=prod['cell'], y=0.5, text="ТОВАР ТУТ",
                        showarrow=True, arrowhead=2, arrowsize=2, arrowcolor="red",
                        ax=0, ay=-50, bgcolor="red", font=dict(color="white")
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    if st.button("❌ ЗАКРЫТЬ КАРТУ", key=f"close_{prod['id']}", use_container_width=True):
                        st.session_state[f"map_{prod['id']}"] = False
                        st.rerun()
                st.markdown("<hr style='margin:10px 0; opacity:0.1'>", unsafe_allow_html=True)

elif selected == "Карта": show_map()
elif selected == "Настройки":
    st.markdown("<h1 style='text-align:center;'>⚙️ Системные настройки</h1>", unsafe_allow_html=True)
    
    # Создаем табы
    tabs = st.tabs(["🏢 Склад и Топология", "👥 Команда", "💾 Обслуживание"])
    tab_topology = tabs[0]
    tab_team = tabs[1]
    tab_system = tabs[2]

    # ==========================================
    # ТАБ 1: СКЛАД И ТОПОЛОГИЯ (СВЯЗЬ С БД)
    # ==========================================
    with tab_topology:
        st.subheader("📍 Интерактивная карта складов")
        
        col_map, col_stats = st.columns([2, 1])
        
        with col_map:
            wh_list = list(WAREHOUSE_MAP.keys())
            wh_to_show = st.selectbox("Выберите склад для визуализации", wh_list, key="wh_settings_select")
            
            try:
                # 1. Запрос из актуальной базы global_inventory
                raw_inv = supabase.table("global_inventory").select("name, cell").eq("warehouse", wh_to_show).execute()
                
                # 2. Группировка товаров по ячейкам
                cell_content = {}
                for row in raw_inv.data:
                    c_id = str(row['cell']).strip()
                    p_name = row['name']
                    if c_id not in cell_content:
                        cell_content[c_id] = []
                    cell_content[c_id].append(p_name)
                
                # 3. Отрисовка карты
                fig = get_warehouse_figure(wh_to_show)
                
                for trace in fig.data:
                    cell_name = str(trace.name).strip()
                    products = cell_content.get(cell_name, [])
                    
                    if products:
                        display_limit = 10
                        p_list_str = "<br>• ".join(products[:display_limit])
                        if len(products) > display_limit:
                            p_list_str += f"<br>... и еще {len(products) - display_limit}"
                        
                        hover_html = (
                            f"<b>Ячейка: {cell_name}</b><br>"
                            f"📦 Товаров: {len(products)}<br>"
                            f"<span style='font-size:12px;'>• {p_list_str}</span>"
                        )
                    else:
                        hover_html = f"<b>Ячейка: {cell_name}</b><br><i style='color:gray;'>Ячейка пуста</i>"
                    
                    trace.hovertemplate = hover_html + "<extra></extra>"
                
                st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
                
            except Exception as e:
                st.error(f"Ошибка при обновлении карты: {e}")

        with col_stats:
            st.info("📊 **Статистика склада**")
            try:
                # Безопасный расчет статистики (защита от NameError)
                all_possible_cells = get_actual_cells(wh_to_show)
                total_count = len(all_possible_cells)
                occupied_count = len(cell_content.keys())
                free_count = total_count - occupied_count
                
                # Защита от деления на ноль
                percent_occ = (occupied_count / total_count * 100) if total_count > 0 else 0
                
                st.metric("Всего ячеек", total_count)
                st.metric("Занято", occupied_count, delta=f"{percent_occ:.1f}%", delta_color="inverse")
                st.metric("Свободно", free_count)
                
                st.divider()
                st.write("**Статус базы:**")
                st.caption("🟢 Синхронизация с `global_inventory` активна.")
                
            except Exception as e:
                st.warning(f"Невозможно рассчитать статистику: проверьте импорт `get_actual_cells`. Подробности: {e}")

    # ==========================================
    # ТАБ 2: КОМАНДА
    # ==========================================
    with tab_team:
        st.subheader("👤 Управление персоналом")
        with st.expander("➕ Зарегистрировать нового сотрудника", expanded=True):
            with st.form("user_add_form"):
                new_email = st.text_input("Email сотрудника")
                new_name = st.text_input("ФИО")
                new_role = st.selectbox("Уровень доступа", ["Кладовщик", "Администратор", "Водитель"])
                
                if st.form_submit_button("💾 Сохранить в базу", use_container_width=True):
                    if new_email and new_name:
                        try:
                            supabase.table("profiles").insert({"email": new_email, "full_name": new_name, "role": new_role}).execute()
                            st.success(f"Сотрудник {new_name} успешно добавлен!")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Ошибка БД: {e}")
                    else:
                        st.warning("Пожалуйста, заполните Email и ФИО.")

    # ==========================================
    # ТАБ 3: ОБСЛУЖИВАНИЕ (ПРО-ВЕРСИЯ)
    # ==========================================
    with tab_system:
        st.subheader("🛠️ Сервисные инструменты")
        c1, c2, c3 = st.columns(3)
        
        # --- МОДАЛЬНОЕ ОКНО ДЛЯ ЭКСПОРТА ---
        @st.dialog("📊 Экспорт данных в Excel")
        def export_modal():
            st.write("Выберите таблицы для выгрузки:")
            # Добавлена новая таблица global_inventory!
            available_tables = ["global_inventory", "orders", "arrivals", "defects", "inventory", "profiles"]
            selected_tables = st.multiselect("Таблицы", available_tables, default=["global_inventory"])
            
            if st.button("🚀 Сформировать XLSX", type="primary", use_container_width=True):
                import pandas as pd
                import io
                with st.spinner("Сбор данных..."):
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        for t in selected_tables:
                            try:
                                data = supabase.table(t).select("*").execute().data
                                if data:
                                    # Имя листа в Excel не может быть длиннее 31 символа
                                    pd.DataFrame(data).to_excel(writer, sheet_name=t[:31], index=False)
                            except Exception as e:
                                st.error(f"Не удалось выгрузить {t}: {e}")
                    
                    st.download_button(
                        label="⬇️ СКАЧАТЬ ОТЧЕТ", 
                        data=output.getvalue(), 
                        file_name=f"Warehouse_Report_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
        
        # Кнопки управления
        with c1:
            st.markdown("### 📦 Экспорт")
            if st.button("📊 Панель выгрузки (Excel)", use_container_width=True):
                export_modal()

        with c2:
            st.markdown("### ⚠️ Оптимизация")
            if st.button("🔥 Сбросить кеш системы", use_container_width=True):
                st.cache_data.clear()
                st.cache_resource.clear()
                if 'confirm_delete_all' in st.session_state:
                    del st.session_state['confirm_delete_all']
                st.toast("Кеш системы полностью очищен!")
                time.sleep(1)
                st.rerun()
                
        with c3:
            st.markdown("### 🔴 Опасная зона")
            if st.button("🧨 ОЧИСТИТЬ ВСЕ ДАННЫЕ", type="secondary", use_container_width=True):
                st.session_state.confirm_delete_all = True

        # Логика полного удаления (с защитой и прогресс-баром)
        if st.session_state.get('confirm_delete_all'):
            st.error("### ❗ ВНИМАНИЕ: БЕЗВОЗВРАТНОЕ УДАЛЕНИЕ")
            st.write("Это действие удалит данные из **ВСЕХ** таблиц. Отменить это будет невозможно!")
            
            c_yes, c_no = st.columns(2)
            
            if c_yes.button("☠️ ДА, УДАЛИТЬ АБСОЛЮТНО ВСЁ", type="primary", use_container_width=True):
                try:
                    # ПОЛНЫЙ список таблиц (global_inventory ДОБАВЛЕН!)
                    tables_to_clean = [
                        "global_inventory",  # Наша главная база!
                        "inventory",         
                        "defects",           
                        "positions",         
                        "arrivals",          
                        "orders",            
                        "devices",           
                        "drivers",           
                        "vehicles",          
                        "extras",            
                        "product_locations", 
                        "manager_profile",
                        "profiles"
                    ]
                    
                    total_deleted = 0
                    progress_text = "Идет очистка базы данных. Пожалуйста, подождите..."
                    my_bar = st.progress(0, text=progress_text)
                    
                    for idx, table in enumerate(tables_to_clean):
                        my_bar.progress((idx) / len(tables_to_clean), text=f"Очистка: {table}...")
                        try:
                            # 1. Получаем все ID
                            res = supabase.table(table).select("id").execute()
                            if res.data:
                                ids = [row['id'] for row in res.data]
                                # 2. Удаляем пачками по 500
                                for i in range(0, len(ids), 500):
                                    chunk = ids[i:i + 500]
                                    supabase.table(table).delete().in_("id", chunk).execute()
                                total_deleted += len(ids)
                        except Exception:
                            # Если таблицы нет, просто пропускаем
                            pass
                            
                    my_bar.progress(1.0, text="Удаление завершено!")
                    
                    # КРИТИЧЕСКИ ВАЖНО: Очищаем кэш после удаления
                    st.cache_data.clear()
                    st.cache_resource.clear()
                    st.session_state.confirm_delete_all = False
                    
                    st.success(f"💥 БАЗА ПОЛНОСТЬЮ ОЧИЩЕНА! Удалено строк: {total_deleted}")
                    time.sleep(2)
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Ошибка при очистке: {str(e)}")
            
            if c_no.button("ОТМЕНА", use_container_width=True):
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
