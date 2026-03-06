import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
from streamlit_option_menu import option_menu
import uuid
import time
from streamlit_folium import st_folium
from constants import TABLE_STRUCT
from constants import ORDER_COLUMNS, ARRIVAL_COLUMNS, EXTRA_COLUMNS, DEFECT_COLUMNS, MAIN_COLUMNS
import base64
from database import supabase

import streamlit as st
import pandas as pd
import numpy as np
import uuid
import time
import pytz
from datetime import datetime
import json

def get_full_inventory_df():
    """Собирает все позиции из всех документов в одну таблицу для выбора"""
    all_items = []
    
    # Проверяем, есть ли вообще данные в реестре позиций
    if "items_registry" in st.session_state and st.session_state.items_registry:
        for doc_id, df in st.session_state.items_registry.items():
            if isinstance(df, pd.DataFrame) and not df.empty:
                temp_df = df.copy()
                # Добавляем ID документа к каждой строке, чтобы знать откуда товар
                temp_df['ID Документа'] = doc_id
                
                # Убеждаемся, что есть колонка Адрес
                if 'Адрес' not in temp_df.columns:
                    temp_df['Адрес'] = "НЕ НАЗНАЧЕНО"
                
                # Исключаем системные строки (например, TOTAL)
                if 'Название товара' in temp_df.columns:
                    temp_df = temp_df[temp_df['Название товара'].astype(str).str.upper() != 'TOTAL']
                
                all_items.append(temp_df)
    
    if not all_items:
        return pd.DataFrame(columns=['Название товара', 'ID Документа', 'Адрес'])
        
    return pd.concat(all_items, ignore_index=True)

@st.dialog("📝 Создание новой заявки / документа", width="large")
def create_modal(table_key):
    from database import supabase
    
    # 1. ПОДГОТОВКА КОЛОНОК И ПРОФИЛЯ
    try:
        # Пытаемся взять глобальную структуру, если нет - дефолт
        columns = TABLE_STRUCT.get(table_key, ORDER_COLUMNS) 
    except:
        columns = []

    st.subheader(f"📦 Регистрация нового документа: {table_key.upper()}")
    
    try:
        operator_name = st.session_state.profile_data.iloc[0]['Значение']
    except:
        operator_name = "Системный администратор"
    
    st.info(f"👤 **Оператор:** {operator_name}")

    # --- 1. ПАРСИНГ ФАЙЛА СПЕЦИФИКАЦИИ ---
    st.markdown("### 1️⃣ Загрузка спецификации")
    uploaded_file = st.file_uploader("📥 Выберите Excel или CSV для разбора позиций", type=["xlsx", "xls", "csv"])
    
    parsed_items_df = pd.DataFrame()
    total_vol = 0.0
    total_sum = 0.0

    if uploaded_file:
        try:
            if "xls" in uploaded_file.name:
                df = pd.read_excel(uploaded_file)
            else:
                df = pd.read_csv(uploaded_file)
                
            # Ищем колонку товара автоматически
            name_col = next((c for c in df.columns if any(x in c.lower() for x in ['назван', 'товар', 'наимен', 'item', 'product'])), None)
            
            if not name_col:
                st.warning("⚠️ Не найдена колонка с товаром автоматически.")
                name_col = st.selectbox("Выберите колонку с названием товара", df.columns)
            
            df = df.rename(columns={name_col: 'Название товара'})
            
            # Поиск объема и суммы
            vol_col = next((c for c in df.columns if any(x in c.lower() for x in ['объем', 'м3', 'vol'])), None)
            sum_col = next((c for c in df.columns if any(x in c.lower() for x in ['сумма', 'цена', 'total', 'price'])), None)
            qty_col = next((c for c in df.columns if any(x in c.lower() for x in ['кол', 'qty', 'count'])), None)
            
            if vol_col: total_vol = float(df[vol_col].sum())
            if sum_col: total_sum = float(df[sum_col].sum())
            
            if 'Адрес' not in df.columns:
                df['Адрес'] = "НЕ НАЗНАЧЕНО"
            
            parsed_items_df = df
            st.success(f"✅ Обработано: {len(df)} поз. | Объем: {total_vol:.2f} м3 | Сумма: {total_sum:.2f}")
            
            with st.expander("👀 Предпросмотр позиций"):
                st.dataframe(df.head(10), use_container_width=True)

        except Exception as e:
            st.error(f"❌ Ошибка парсинга: {e}")

    # Блок фото фактуры
    st.markdown("### 📎 Документальное подтверждение")
    uploaded_invoice_photo = st.file_uploader("📸 Фото фактуры / ТТН (скан или фото)", type=['png', 'jpg', 'jpeg'], key="inv_photo")

    # --- 2. ФОРМА ВВОДА ДАННЫХ ---
    st.markdown("### 2️⃣ Параметры логистики")
    with st.form(f"full_create_form_{table_key}", clear_on_submit=False):
        
        col_cl1, col_cl2, col_cl3 = st.columns(3)
        
        default_client = ""
        if not parsed_items_df.empty and 'Клиент' in parsed_items_df.columns:
            default_client = str(parsed_items_df['Клиент'].iloc[0])
            
        input_client = col_cl1.text_input("Название Клиента*", value=default_client)
        input_address = col_cl2.text_input("Адрес доставки")
        input_phone = col_cl3.text_input("Телефон связи")

        st.divider()

        st.markdown("🚚 **Транспортная информация**")
        r2_c1, r2_c2, r2_c3, r2_c4 = st.columns(4)
        
        status_options = ["ОЖИДАНИЕ", "Стоит на точке загрузки", "Выехал", "Ожидает догруз", "В пути", "Доставлено"]
        selected_status = r2_c1.selectbox("📍 Статус", status_options)
        input_driver = r2_c2.text_input("👤 Водитель (ФИО)")
        input_ts = r2_c3.text_input("🚛 ТС (Госномер)")
        has_certificate = r2_c4.selectbox("📜 Сертификат", ["Нет", "Да"])

        st.divider()

        st.markdown("⚖️ **Характеристики загрузки**")
        r3_c1, r3_c2, r3_c3, r3_c4 = st.columns(4)
        
        v_capacity = r3_c1.number_input("Грузоподъемность (кг)", min_value=0, value=1500)
        v_max_vol = r3_c2.number_input("Объем кузова (м3)", min_value=0.1, value=12.0)
        input_dopusk = r3_c3.text_input("👤 Кто разрешил (Допуск)")
        input_loading_addr = r3_c4.text_input("Адрес загрузки", value="Центральный склад")

        st.divider()

        st.markdown("📝 **Дополнительно**")
        r4_c1, r4_c2 = st.columns([2, 1])
        input_desc = r4_c1.text_area("Особые отметки / Комментарии", height=100)
        uploaded_photo = r4_c2.file_uploader("📸 Фото груза", type=['png', 'jpg', 'jpeg'], key="cargo_photo")

        submitted = st.form_submit_button("🚀 СОЗДАТЬ ЗАЯВКУ В СИСТЕМЕ", use_container_width=True)

    # --- 3. ОБРАБОТКА И СОХРАНЕНИЕ ---
    if submitted:
        if not input_client:
            st.error("❌ Укажите клиента!")
            return

        # ВРЕМЯ МОЛДОВЫ
        moldova_tz = pytz.timezone('Europe/Chisinau')
        now_md = datetime.now(moldova_tz)
        iso_time = now_md.isoformat()
        
        order_id = f"ORD-{str(uuid.uuid4())[:6].upper()}"
        efficiency = (total_vol / v_max_vol) * 100 if v_max_vol > 0 else 0

        # Функция загрузки фото
        def upload_to_storage(file_obj, prefix="photo"):
            if not file_obj: return None
            try:
                ext = file_obj.name.split('.')[-1]
                fname = f"{prefix}_{order_id}_{int(time.time())}.{ext}"
                supabase.storage.from_("order-photos").upload(fname, file_obj.getvalue())
                return supabase.storage.from_("order-photos").get_public_url(fname)
            except Exception as e:
                st.warning(f"Ошибка загрузки фото: {e}")
                return None

        # Загружаем медиа
        final_photo_url = upload_to_storage(uploaded_photo, "cargo")
        final_invoice_url = upload_to_storage(uploaded_invoice_photo, "invoice")

        # JSON товаров
        items_json = []
        if not parsed_items_df.empty:
            items_json = parsed_items_df.replace({np.nan: None}).to_dict(orient='records')

        # PAYLOAD ДЛЯ ORDERS
        supabase_payload = {
            "id": order_id,
            "status": selected_status,
            "client_name": input_client,
            "items_count": len(parsed_items_df),
            "total_volume": float(total_vol),
            "total_sum": float(total_sum),
            "loading_efficiency": float(efficiency),
            "delivery_address": input_address,
            "phone": input_phone,
            "load_address": input_loading_addr,
            "has_certificate": has_certificate,
            "driver": input_driver,
            "vehicle": input_ts,
            "description": input_desc,
            "approval_by": input_dopusk,
            "items_data": items_json,
            "photo_url": final_photo_url,
            "invoice_photo_url": final_invoice_url,
            "print_flag": False,
            "created_at": iso_time
        }

        try:
            # 1. Запись в orders
            supabase.table("orders").insert(supabase_payload).execute()

            # 2. Синхронизация с inventory (Распаковка)
            if items_json:
                inventory_payload = []
                for item in items_json:
                    p_name = item.get('Название товара') or item.get('Наименование') or "Неизвестный товар"
                    p_qty = item.get('Количество') or item.get('Кол-во') or item.get('qty') or 0
                    
                    inventory_payload.append({
                        "doc_id": order_id,
                        "item_name": str(p_name),
                        "quantity": float(p_qty),
                        "warehouse_id": input_loading_addr,
                        "cell_address": "НЕ НАЗНАЧЕНО",
                        "status": selected_status,
                        "created_at": iso_time,
                        "updated_at": iso_time
                    })
                
                if inventory_payload:
                    supabase.table("inventory").upsert(inventory_payload, on_conflict="doc_id,item_name").execute()

            # 3. Обновление UI
            ui_row = {
                "📝 Ред.": "⚙️", "id": order_id, "🔍 Просмотр": "👀 Посмотреть",
                "Статус": selected_status, "Клиент": input_client, "Кол-во позиций": len(parsed_items_df),
                "Общий объем (м3)": round(total_vol, 3), "Сумма заявки": float(total_sum),
                "КПД загрузки": f"{efficiency:.1f}%", "Адрес клиента": input_address,
                "Телефон": input_phone, "Адрес загрузки": input_loading_addr,
                "Сертификат": has_certificate, "Водитель": input_driver, "ТС": input_ts,
                "Дата создания": now_md.strftime("%Y-%m-%d"), "Время создания": now_md.strftime("%H:%M:%S"),
                "Последнее изменение": f"{operator_name} ({now_md.strftime('%H:%M')})",
                "Фото": "✅" if final_photo_url else "❌",
                "Фото фактуры": "✅" if final_invoice_url else "❌",
                "Описание": input_desc, "Допуск": input_dopusk, "🖨️ Печать": False
            }

            if table_key not in st.session_state:
                st.session_state[table_key] = pd.DataFrame()
            
            st.session_state[table_key] = pd.concat([st.session_state[table_key], pd.DataFrame([ui_row])], ignore_index=True)

            st.success(f"✅ Документ {order_id} успешно сохранен!")
            st.balloons()
            time.sleep(1)
            st.rerun()

        except Exception as e:
            st.error(f"🚨 Ошибка базы: {e}")
            
import streamlit as st
import pandas as pd
import numpy as np
import uuid
import time
import pytz
import requests  # Для Cloudinary
from datetime import datetime

@st.dialog("📥 Регистрация нового Прихода (Поставка)", width="large")
def create_arrival_modal(table_key="arrivals", *args, **kwargs):
    from database import supabase 
    
    # --- КОНФИГУРАЦИЯ CLOUDINARY ---
    CLOUD_NAME = "ваш_cloud_name"
    UPLOAD_PRESET = "ваш_preset"
    CLOUDINARY_URL = f"https://api.cloudinary.com/v1_1/{CLOUD_NAME}/image/upload"

    if "drivers" not in st.session_state:
        st.session_state.drivers = pd.DataFrame(columns=["Фамилия", "Имя"])

    try:
        operator_name = st.session_state.profile_data.iloc[0]['Значение']
    except Exception:
        operator_name = "Системный администратор"

    st.subheader("🚚 Приемка товаров на склад")

    # --- 1. ПАРСИНГ ЭКСКЕЛЯ ---
    st.markdown("### 1️⃣ Загрузка спецификации")
    uploaded_file = st.file_uploader("📥 Файл поставщика (Excel/CSV)", type=["xlsx", "xls", "csv"])
    
    parsed_items_df = pd.DataFrame()
    total_sum_from_file = 0.0

    if uploaded_file:
        try:
            df = pd.read_excel(uploaded_file) if "xls" in uploaded_file.name else pd.read_csv(uploaded_file)
            name_col = next((c for c in df.columns if any(k in str(c).lower() for k in ['товар', 'назван', 'артикул', 'наимен'])), None)
            if name_col:
                df = df.rename(columns={name_col: 'Название товара'})
                qty_col = next((c for c in df.columns if any(k in str(c).lower() for k in ['кол', 'qty', 'количество'])), None)
                if qty_col:
                    df = df.rename(columns={qty_col: 'Количество'})
                parsed_items_df = df
                st.success(f"✅ Найдено товаров: {len(df)}")
        except Exception as e:
            st.error(f"❌ Ошибка парсинга: {e}")

    # --- 2. ФОРМА ---
    with st.form("arrival_form_cloudinary", clear_on_submit=False):
        col1, col2, col3 = st.columns([2, 1, 1])
        vendor = col1.text_input("🏢 Поставщик*")
        doc_num = col2.text_input("📄 № Накладной*")
        a_type = col3.selectbox("📦 Тип", ["Полная", "Частичная", "Возврат"])

        r2_c1, r2_c2, r2_c3 = st.columns(3)
        selected_driver = r2_c1.selectbox("👤 Водитель", ["Внешний перевозчик"] + (st.session_state.drivers["Фамилия"].tolist() if not st.session_state.drivers.empty else []))
        vehicle_num = r2_c2.text_input("🚛 Госномер ТС")
        gate_num = r2_c3.text_input("🚪 Ворота", value="Док-1")

        st.divider()
        st.markdown("### 📸 Фотофиксация и Подтверждение")
        # Поле для фото (Накладная или Пломба)
        arrival_photo = st.file_uploader("Загрузите фото документов/груза (Cloudinary)*", type=['png', 'jpg', 'jpeg'])
        
        comments = st.text_area("📝 Замечания")
        submitted = st.form_submit_button("📥 ЗАРЕГИСТРИРОВАТЬ ПОСТАВКУ", use_container_width=True)

    # --- 3. СОХРАНЕНИЕ ---
    if submitted:
        if not vendor or not doc_num or not arrival_photo:
            st.error("❌ Заполните Поставщика, № Документа и прикрепите ФОТО!")
            return

        moldova_tz = pytz.timezone('Europe/Chisinau')
        now_md = datetime.now(moldova_tz)
        arrival_id = f"IN-{uuid.uuid4().hex[:6].upper()}"
        
        # Загрузка в Cloudinary
        photo_url = None
        try:
            with st.spinner("☁️ Загрузка фото в Cloudinary..."):
                files = {"file": arrival_photo.getvalue()}
                data = {"upload_preset": UPLOAD_PRESET, "public_id": f"arrivals/{arrival_id}"}
                res = requests.post(CLOUDINARY_URL, files=files, data=data)
                if res.status_code == 200:
                    photo_url = res.json().get("secure_url")
        except Exception as e:
            st.error(f"🚨 Ошибка Cloudinary: {e}")
            return

        # Подготовка данных
        items_json = parsed_items_df.replace({np.nan: None}).to_dict(orient='records') if not parsed_items_df.empty else []

        payload = {
            "id": arrival_id,
            "vendor_name": vendor,
            "doc_number": doc_num,
            "driver_name": selected_driver,
            "vehicle_number": vehicle_num,
            "arrival_type": a_type,
            "photo_url": photo_url,  # Ссылка из Cloudinary
            "items_data": items_json,
            "gate_number": gate_num,
            "receiver_name": operator_name,
            "created_at": now_md.isoformat()
        }

        try:
            supabase.table("arrivals").insert(payload).execute()
            
            # Обновление остатков (Inventory)
            if items_json:
                inv_payload = [{
                    "doc_id": arrival_id,
                    "item_name": str(i.get('Название товара', 'Неизвестно')),
                    "quantity": float(i.get('Количество', 0)),
                    "warehouse_id": "Зона приемки",
                    "cell_address": gate_num,
                    "status": "ПРИНЯТО",
                    "created_at": now_md.isoformat()
                } for i in items_json]
                supabase.table("inventory").upsert(inv_payload, on_conflict="doc_id,item_name").execute()

            st.success(f"✅ Приход {arrival_id} оформлен!")
            st.balloons()
            time.sleep(1.5)
            st.rerun()
        except Exception as e:
            st.error(f"🚨 Ошибка Supabase: {e}")
        
    
import streamlit as st
import pandas as pd
import numpy as np
import uuid
import time
import pytz
import requests  # Для прямой отправки в Cloudinary
from datetime import datetime

@st.dialog("➕ Регистрация Дополнительного События/Услуги", width="large")
def create_extras_modal(*args, **kwargs):
    from database import supabase  # Подключение к Supabase
    
    # --- КОНФИГУРАЦИЯ CLOUDINARY ---
    # Рекомендуется вынести в st.secrets
    CLOUD_NAME = "ваш_cloud_name"
    UPLOAD_PRESET = "ваш_unsigned_preset" 
    CLOUDINARY_URL = f"https://api.cloudinary.com/v1_1/{CLOUD_NAME}/image/upload"

    # 0. ИНИЦИАЛИЗАЦИЯ ИМЕНИ ОПЕРАТОРА
    try:
        operator_name = st.session_state.profile_data.iloc[0]['Значение']
    except Exception:
        operator_name = "Системный администратор"

    st.subheader("🛠️ Фиксация доп. работ и услуг (Cloudinary Sync)")
    st.info(f"👤 **Регистрирует:** {operator_name}")
    
    with st.form("extras_detailed_form", clear_on_submit=False):
        # ЛИНИЯ 1: Кто и когда
        st.markdown("### 👤 Ответственность и Время")
        r1_c1, r1_c2, r1_c3 = st.columns(3)
        
        approved_by = r1_c1.text_input("👤 Кто одобрил (ФИО)*", placeholder="Напр: Иванов И.И.")
        executor = r1_c2.text_input("👷 Исполнитель", placeholder="Бригада / Сотрудник")
        
        moldova_tz = pytz.timezone('Europe/Chisinau')
        now_md = datetime.now(moldova_tz)
        
        selected_date = r1_c3.date_input("📅 Дата события", now_md)
        selected_time = r1_c3.time_input("🕒 Время", now_md.time())

        st.divider()

        # Линия 2: Предмет
        st.markdown("### 📦 Предмет дополнения")
        r2_c1, r2_c2, r2_c3 = st.columns([2, 1, 1])
        subject_type = r2_c1.selectbox("Тип ресурса", [
            "ТОВАР (Переупаковка/Замена)", 
            "ПОМОЩЬ (Погрузка/Разгрузка)", 
            "ТЕХНИКА (Аренда кары/ТС)", 
            "МАТЕРИАЛЫ (Паллеты/Стретч)", 
            "ПРОЧЕЕ"
        ])
        resource_used = r2_c2.text_input("🚜 Ресурс", placeholder="Кара №4 / ТС")
        location = r2_c3.text_input("📍 Зона", value="Зона догруза")

        st.divider()

        # Линия 3: Логика
        st.markdown("### ❓ Причина и Результат")
        r3_c1, r3_c2 = st.columns([2, 1])
        reason = r3_c1.text_area("Почему (Причина)*", height=68, placeholder="Опишите ситуацию...")
        status = r3_c2.selectbox("Статус", ["СОГЛАСОВАНО", "В ПРОЦЕССЕ", "ВЫПОЛНЕНО", "ОЖИДАЕТ ОПЛАТЫ"])

        # ЛИНИЯ 4: Цифры и Фото
        st.divider()
        r4_c1, r4_c2, r4_c3 = st.columns(3)
        qty = r4_c1.number_input("Сколько (Кол-во)", min_value=0.0, value=1.0)
        cost = r4_c2.number_input("Сумма (MDL/₽)", min_value=0.0, value=0.0)
        link_id = r4_c3.text_input("🔗 ID Заявки (если есть)")

        st.markdown("### 📸 Подтверждающее фото (Cloudinary)")
        uploaded_file = st.file_uploader("Загрузите фото работы/материалов", type=['png', 'jpg', 'jpeg'])

        st.markdown("<br>", unsafe_allow_html=True)
        submitted = st.form_submit_button("🚀 ЗАФИКСИРОВАТЬ И ОТПРАВИТЬ", use_container_width=True)

    # --- ОБРАБОТКА РЕЗУЛЬТАТОВ ---
    if submitted:
        if not approved_by or not reason:
            st.error("❌ Заполните обязательные поля: 'Кто одобрил' и 'Причина'!")
            return

        extra_id = f"EXT-{str(uuid.uuid4())[:6].upper()}"
        photo_url = None

        # 1. ЗАГРУЗКА В CLOUDINARY (если файл есть)
        if uploaded_file:
            try:
                with st.spinner("☁️ Отправка фото в Cloudinary..."):
                    files = {"file": uploaded_file.getvalue()}
                    data = {
                        "upload_preset": UPLOAD_PRESET,
                        "public_id": f"extras/{extra_id}", # Красивая структура папок
                        "tags": "wms_extra_service"
                    }
                    res = requests.post(CLOUDINARY_URL, files=files, data=data)
                    if res.status_code == 200:
                        photo_url = res.json().get("secure_url")
                    else:
                        st.warning(f"⚠️ Фото не загружено: {res.json().get('error', {}).get('message')}")
            except Exception as e:
                st.error(f"🚨 Ошибка Cloudinary: {e}")
                return

        # 2. ПОДГОТОВКА PAYLOAD ДЛЯ SUPABASE
        supabase_payload = {
            "id": extra_id,
            "approved_by": approved_by,
            "executor": executor,
            "subject_type": subject_type,
            "resource_used": resource_used,
            "event_date": selected_date.strftime("%Y-%m-%d"),
            "event_time": selected_time.strftime("%H:%M:%S"),
            "location": location,
            "reason": reason,
            "status": status,
            "quantity": float(qty),
            "total_sum": float(cost),
            "linked_order_id": link_id,
            "photo_url": photo_url, # Та самая прямая ссылка
            "created_at": now_md.isoformat()
        }

        # 3. ОТПРАВКА В ОБЛАКО
        try:
            with st.spinner("💾 Сохранение записи..."):
                supabase.table("extras").insert(supabase_payload).execute()
        except Exception as e:
            st.error(f"🚨 Ошибка Supabase: {e}")
            return

        # 4. ОБНОВЛЕНИЕ ЛОКАЛЬНОГО ИНТЕРФЕЙСА
        ui_extra_data = {
            "📝 Ред.": "⚙️", "id": extra_id, "Кто одобрил": approved_by,
            "Что именно": subject_type, "На чем": resource_used,
            "Когда": selected_date.strftime("%Y-%m-%d"), 
            "Время": selected_time.strftime("%H:%M"),
            "Почему (Причина)": reason, "Статус": status, "Кол-во": qty,
            "Сумма заявки": float(cost), "Фото": photo_url,
            "🔍 Просмотр": "👀", "🖨️ Печать": False
        }

        # Обновляем реестр extras
        if "extras" not in st.session_state or st.session_state["extras"] is None:
            st.session_state["extras"] = pd.DataFrame([ui_extra_data])
        else:
            st.session_state["extras"] = pd.concat([st.session_state["extras"], pd.DataFrame([ui_extra_data])], ignore_index=True)

        # 5. ЗЕРКАЛИРОВАНИЕ В MAIN
        if "main" in st.session_state and st.session_state["main"] is not None:
            main_entry = ui_extra_data.copy()
            main_entry["Тип документа"] = "ДОП.УСЛУГА"
            main_entry["Время создания"] = main_entry.pop("Время")
            main_entry["Описание"] = f"Услуга: {subject_type}. Причина: {reason}"
            main_entry["Статус"] = f"🛠️ {status}"
            
            main_row_df = pd.DataFrame([main_entry])
            main_row_df = main_row_df.reindex(columns=st.session_state["main"].columns, fill_value="")
            st.session_state["main"] = pd.concat([st.session_state["main"], main_row_df], ignore_index=True)

        st.success(f"✅ Услуга {extra_id} сохранена со ссылкой на Cloudinary!")
        st.balloons()
        time.sleep(1.2)
        st.rerun()
        
import streamlit as st
import pandas as pd
import numpy as np
import uuid
import time
import pytz
import requests  # Нужен для отправки в Cloudinary
from datetime import datetime

@st.dialog("⚠️ Регистрация Брака / Повреждений", width="large")
def create_defect_modal(table_key="defects", *args, **kwargs):
    from database import supabase
    
    # Конфигурация Cloudinary (лучше держать в st.secrets)
    # Замени на свои данные или добавь в .streamlit/secrets.toml
    CLOUDINARY_URL = "https://api.cloudinary.com/v1_1/ВАШ_CLOUD_NAME/image/upload"
    UPLOAD_PRESET = "ВАШ_PRESET" # Должен быть 'unsigned' в настройках Cloudinary

    try:
        operator_default = st.session_state.profile_data.iloc[0]['Значение']
    except Exception:
        operator_default = ""

    st.subheader("🚨 Акт регистрации дефекта (Cloudinary Sync)")

    with st.form("defect_form_cloudinary", clear_on_submit=False):
        item_name_input = st.text_input("📦 Название товара (Обязательно)*")
        
        st.divider()
        
        col1, col2 = st.columns(2)
        with col1:
            reporter = st.text_input("👤 Кто выявил (ФИО)*", value=operator_default)
            d_type = st.selectbox("📝 Тип дефекта", ["Бой", "Порча", "Брак производителя", "Некомплект", "Утеря"])
        
        with col2:
            q_zone = st.text_input("📍 Зона", value="ZONE-BRAK")
            decision = st.selectbox("⚖️ Решение", ["На проверку", "Списание", "Уценка", "Возврат"])

        col3, col4 = st.columns([1, 2])
        with col3:
            defect_qty = st.number_input("🔢 Кол-во", min_value=1.0, value=1.0)
        with col4:
            description = st.text_input("🗒️ Комментарий")

        linked_doc_input = st.text_input("📄 Связанный документ")

        st.markdown("### 📸 Фотофиксация (Загрузка в Cloudinary)")
        uploaded_photo = st.file_uploader("Прикрепите фото*", type=['png', 'jpg', 'jpeg'])

        submitted = st.form_submit_button("🔥 ЗАРЕГИСТРИРОВАТЬ И ОТПРАВИТЬ", use_container_width=True)

    if submitted:
        if not item_name_input.strip() or not reporter.strip() or not uploaded_photo:
            st.error("❌ Заполните обязательные поля и добавьте фото!")
            return

        moldova_tz = pytz.timezone('Europe/Chisinau')
        now_md = datetime.now(moldova_tz)

        with st.spinner("☁️ Загрузка изображения в Cloudinary..."):
            defect_id = f"DEF-{uuid.uuid4().hex[:6].upper()}"
            photo_url = None
            
            # --- ЛОГИКА CLOUDINARY ---
            try:
                files = {"file": uploaded_photo.getvalue()}
                data = {
                    "upload_preset": UPLOAD_PRESET,
                    "public_id": f"defects/{defect_id}", # Организуем папку в Cloudinary
                    "tags": "wms_defect"
                }
                response = requests.post(CLOUDINARY_URL, files=files, data=data)
                res_json = response.json()
                
                if response.status_code == 200:
                    photo_url = res_json.get("secure_url") # Получаем ту самую прямую ссылку
                else:
                    st.error(f" Ошибка Cloudinary: {res_json.get('error', {}).get('message')}")
                    return
            except Exception as cloud_err:
                st.error(f"🚨 Ошибка связи с Cloudinary: {cloud_err}")
                return

        with st.spinner("💾 Запись в базу данных..."):
            payload = {
                "id": defect_id,
                "created_at": now_md.isoformat(),
                "item_name": item_name_input.strip(),
                "quantity": float(defect_qty),
                "storage_address": q_zone,
                "defect_type": d_type,
                "description": description,
                "responsible_party": reporter.strip(),
                "decision": decision,
                "status": "ОБНАРУЖЕНО",
                "photo_url": photo_url, # Ссылка из Cloudinary
                "linked_doc_id": linked_doc_input.strip() if linked_doc_input else None
            }

            try:
                supabase.table("defects").insert(payload).execute()
                
                # Обновляем UI
                ui_row = {
                    "📝 Ред.": "⚙️", "id": defect_id, "Товар": item_name_input.strip(),
                    "Кол-во": defect_qty, "Тип дефекта": d_type, "Зона": q_zone,
                    "Решение": decision, "Выявил": reporter.strip(),
                    "Дата": now_md.strftime("%Y-%m-%d"), "Время": now_md.strftime("%H:%M"),
                    "Фото": photo_url, # Теперь здесь настоящая ссылка
                    "🔍 Просмотр": "👀", "🖨️ Печать": False
                }

                # Пушим в session_state
                if "defects" not in st.session_state:
                    st.session_state["defects"] = pd.DataFrame([ui_row])
                else:
                    st.session_state["defects"] = pd.concat([st.session_state["defects"], pd.DataFrame([ui_row])], ignore_index=True)

                st.success(f"✅ Акт {defect_id} создан. Ссылка на фото сохранена!")
                time.sleep(1.5)
                st.rerun()
                
            except Exception as e:
                st.error(f"🚨 Ошибка Supabase: {e}")
