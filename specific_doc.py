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

def upload_driver_photo(file):
    from database import supabase
    try:
        file_ext = file.name.split(".")[-1]
        file_name = f"drv_{int(time.time())}.{file_ext}"
        
        # Загрузка
        supabase.storage.from_("defects_photos").upload(
            path=file_name,
            file=file.getvalue(),
            file_options={"content-type": f"image/{file_ext}"}
        )
        # Получение ссылки
        return supabase.storage.from_("defects_photos").get_public_url(file_name)
    except Exception as e:
        # В случае ошибки возвращаем дефолтную иконку
        return "https://cdn-icons-png.flaticon.com/512/3135/3135715.png"

def process_image(uploaded_file):
    if uploaded_file is not None:
        file_bytes = uploaded_file.getvalue()
        base64_char = base64.b64encode(file_bytes).decode('utf-8')
        return f"data:image/png;base64,{base64_char}"
    return None


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
                temp_df = temp_df[temp_df['Название товара'].str.upper() != 'TOTAL']
                
                all_items.append(temp_df)
    
    if not all_items:
        return pd.DataFrame(columns=['Название товара', 'ID Документа', 'Адрес'])
        
    return pd.concat(all_items, ignore_index=True)

@st.dialog("📝 Создание новой заявки / документа", width="large")
def create_modal(table_key):
    from database import supabase
    import uuid
    import time
    import numpy as np
    import pandas as pd
    from datetime import datetime

    # Получаем структуру колонок (предполагается, что TABLE_STRUCT и ORDER_COLUMNS определены глобально)
    try:
        columns = TABLE_STRUCT.get(table_key, ORDER_COLUMNS) 
    except:
        columns = []

    st.subheader(f"📦 Регистрация нового документа: {table_key.upper()}")
    
    # Пытаемся безопасно получить имя оператора
    try:
        operator_name = st.session_state.profile_data.iloc[0]['Значение']
    except:
        operator_name = "Системный администратор"
    
    st.markdown(f"**Оператор:** {operator_name}")

    # --- 1. ПАРСИНГ ФАЙЛА СПЕЦИФИКАЦИИ ---
    st.markdown("### 1️⃣ Загрузка спецификации")
    uploaded_file = st.file_uploader("📥 Выберите файл Excel или CSV для автоматического разбора позиций", type=["xlsx", "xls", "csv"])
    
    parsed_items_df = pd.DataFrame()
    total_vol = 0.0
    total_sum = 0.0

    if uploaded_file:
        try:
            df = pd.read_excel(uploaded_file) if "xls" in uploaded_file.name else pd.read_csv(uploaded_file)
            name_col = next((c for c in df.columns if 'назван' in c.lower() or 'товар' in c.lower() or 'наимен' in c.lower()), None)
            
            if not name_col:
                st.error("❌ Не нашел колонку с названием товара! Укажите её вручную:")
                name_col = st.selectbox("Выберите колонку с товаром", df.columns)
            
            df = df.rename(columns={name_col: 'Название товара'})
            
            vol_col = next((c for c in df.columns if 'объем' in c.lower() or 'м3' in c.lower()), None)
            sum_col = next((c for c in df.columns if 'сумма' in c.lower() or 'цена' in c.lower()), None)
            
            if vol_col: total_vol = float(df[vol_col].sum())
            if sum_col: total_sum = float(df[sum_col].sum())
            
            if 'Адрес' not in df.columns:
                df['Адрес'] = "НЕ НАЗНАЧЕНО"
            
            parsed_items_df = df
            st.success(f"✅ Файл прочитан. Найдено позиций: {len(df)} | Общий объем: {total_vol:.2f} м3 | Сумма: {total_sum:.2f}")
            with st.expander("👀 Предпросмотр загруженных позиций"):
                st.dataframe(df.head(5), use_container_width=True)

        except Exception as e:
            st.error(f"❌ Ошибка парсинга файла: {e}")

    # --- НОВЫЙ БЛОК ДЛЯ ФОТО ФАКТУРЫ ЗДЕСЬ ---
    st.markdown("### 📎 Фото фактуры / документа")
    uploaded_invoice_photo = st.file_uploader("📸 Прикрепить фото фактуры (если нет Excel или как факт)", type=['png', 'jpg', 'jpeg'])

    # --- 2. ФОРМА ВВОДА ДАННЫХ ---
    st.markdown("### 2️⃣ Параметры заявки и Логистика")
    with st.form(f"full_create_form_{table_key}", clear_on_submit=False):
        
        st.markdown("👤 **Информация о клиенте**")
        r1_c1, r1_c2, r1_c3 = st.columns(3)
        
        default_client = ""
        if not parsed_items_df.empty and 'Клиент' in parsed_items_df.columns:
            default_client = str(parsed_items_df['Клиент'].iloc[0])
            
        input_client = r1_c1.text_input("Название Клиента*", value=default_client, help="Обязательное поле")
        # Изменено: Название переменной для синхронизации с delivery_address
        input_address = r1_c2.text_input("Адрес доставки (Адрес клиента)")
        input_phone = r1_c3.text_input("Телефон")

        st.divider()

        st.markdown("🚚 **Транспорт и Статус**")
        r2_c1, r2_c2, r2_c3, r2_c4 = st.columns(4)
        
        status_options = ["ОЖИДАНИЕ", "Стоит на точке загрузки", "Выехал", "Ожидает догруз", "В пути", "Доставлено"]
        selected_status = r2_c1.selectbox("📍 Статус заявки", status_options)

        # 1. Изменено: Текстовый ввод водителя вместо выпадающего списка
        input_driver = r2_c2.text_input("👤 Водитель (ФИО)", placeholder="Введите ФИО водителя")

        # 2. Изменено: Текстовый ввод ТС (для гибкости синхронизации)
        input_ts = r2_c3.text_input("🚛 ТС (Госномер)", placeholder="Напр: AA 123 B")
        
        has_certificate = r2_c4.selectbox("📜 Сертификат", ["Нет", "Да"])

        st.divider()

        st.markdown("⚖️ **Лимиты и Ответственность**")
        r3_c1, r3_c2, r3_c3, r3_c4 = st.columns(4)
        
        v_capacity = r3_c1.number_input("Грузоподъемность ТС (кг)", min_value=0, value=1500)
        v_max_vol = r3_c2.number_input("Объем кузова ТС (м3)", min_value=0.1, value=12.0)
        input_dopusk = r3_c3.text_input("👤 Допуск (Кто разрешил)", placeholder="Введите ФИО")
        input_loading_addr = r3_c4.text_input("Адрес загрузки", value="Центральный склад")

        st.divider()

        st.markdown("📝 **Дополнительные сведения и Документы**")
        r4_c1, r4_c2 = st.columns([2, 1])
        
        input_desc = r4_c1.text_area("Описание (детально по товару или особые отметки)", height=100)
        # Поле для загрузки фото
        uploaded_photo = r4_c2.file_uploader("📸 Прикрепить фото (Накладная/Груз)", type=['png', 'jpg', 'jpeg'])

        st.markdown("<br>", unsafe_allow_html=True)
        submitted = st.form_submit_button("🚀 СФОРМИРОВАТЬ И СОХРАНИТЬ ЗАЯВКУ", use_container_width=True)

# --- 3. ОБРАБОТКА И СОХРАНЕНИЕ В SUPABASE ---
    if submitted:
        if not input_client:
            st.error("❌ Ошибка: Поле 'Название Клиента' обязательно для заполнения!")
            return

        # --- НАСТРОЙКА ВРЕМЕНИ (МОЛДОВА) ---
        import pytz
        moldova_tz = pytz.timezone('Europe/Chisinau')
        now_moldova = datetime.now(moldova_tz)
        moldova_time_iso = now_moldova.isoformat()
        current_date = now_moldova.strftime("%Y-%m-%d")
        current_time = now_moldova.strftime("%H:%M:%S")

        # 1. Генерация уникального ID
        order_id = f"ORD-{str(uuid.uuid4())[:6].upper()}"
        
        # Расчет КПД
        efficiency = (total_vol / v_max_vol) * 100 if v_max_vol > 0 else 0

        # Загрузка фото в Bucket "order-photos" (СИНХРОНИЗАЦИЯ С STORAGE)
        final_photo_url = None
        if uploaded_photo:
            try:
                file_ext = uploaded_photo.name.split('.')[-1]
                file_name = f"{order_id}_{int(time.time())}.{file_ext}"
                # Загружаем в правильный бакет
                supabase.storage.from_("order-photos").upload(file_name, uploaded_photo.getvalue())
                # Получаем публичную ссылку
                final_photo_url = supabase.storage.from_("order-photos").get_public_url(file_name)
            except Exception as e:
                st.warning(f"⚠️ Фото не загружено в хранилище: {e}")

        # --- НОВОЕ: Загрузка ФОТО ФАКТУРЫ в Bucket "order-photos" ---
        final_invoice_photo_url = None
        if uploaded_invoice_photo:
            try:
                inv_ext = uploaded_invoice_photo.name.split('.')[-1]
                inv_file_name = f"invoice_{order_id}_{int(time.time())}.{inv_ext}"
                supabase.storage.from_("order-photos").upload(inv_file_name, uploaded_invoice_photo.getvalue())
                final_invoice_photo_url = supabase.storage.from_("order-photos").get_public_url(inv_file_name)
            except Exception as e:
                st.warning(f"⚠️ Фото фактуры не загружено в хранилище: {e}")

        # Конвертация таблицы товаров в JSON
        items_json = []
        if not parsed_items_df.empty:
            clean_df = parsed_items_df.replace({np.nan: None})
            items_json = clean_df.to_dict(orient='records')

        # 2. ФОРМИРОВАНИЕ PAYLOAD (СИНХРОНИЗАЦИЯ КЛЮЧЕЙ С EDIT_ORDER_MODAL)
        supabase_data = {
            "id": order_id,
            "status": selected_status,
            "client_name": input_client,
            "items_count": len(parsed_items_df),
            "total_volume": float(total_vol),
            "total_sum": float(total_sum),
            "loading_efficiency": float(efficiency),
            "delivery_address": input_address,  # СИНХРОНИЗИРОВАНО
            "phone": input_phone,
            "load_address": input_loading_addr, # СИНХРОНИЗИРОВАНО (load_address вместо loading_address)
            "has_certificate": has_certificate, # СИНХРОНИЗИРОВАНО (как в temp_row)
            "driver": input_driver,             # СИНХРОНИЗИРОВАНО (driver вместо driver_info)
            "vehicle": input_ts,                # СИНХРОНИЗИРОВАНО (vehicle вместо vehicle_info)
            "description": input_desc,
            "approval_by": input_dopusk,        # СИНХРОНИЗИРОВАНО
            "items_data": items_json,
            "photo_url": final_photo_url,       # ТЕПЕРЬ ССЫЛКА, А НЕ ТЕКСТ
            "invoice_photo_url": final_invoice_photo_url, # --- ДОБАВЛЕНО В БАЗУ ДАННЫХ ---
            "print_flag": False,
            "created_at": moldova_time_iso      # МОЛДАВСКОЕ ВРЕМЯ СОЗДАНИЯ
        }

        # 3. ОТПРАВКА В БАЗУ ДАННЫХ
        try:
            # СОХРАНЕНИЕ ОСНОВНОГО ДОКУМЕНТА (ORDERS)
            response = supabase.table("orders").insert(supabase_data).execute()

            # --- СИНХРОНИЗАЦИЯ С ТАБЛИЦЕЙ INVENTORY (РАСПАКОВКА ТОВАРОВ) ---
            if items_json:
                inventory_payload = []
                for item in items_json:
                    # Определяем название товара (пробуем разные варианты ключей из файла)
                    p_name = item.get('Название товара') or item.get('Наименование') or item.get('product')
                    # Определяем количество
                    p_qty = item.get('Количество') or item.get('Кол-во') or item.get('qty') or 0
                    
                    if p_name:
                        inventory_payload.append({
                            "doc_id": str(order_id),
                            "item_name": str(p_name),
                            "quantity": float(p_qty),
                            "warehouse_id": str(input_loading_addr),
                            "cell_address": "НЕ НАЗНАЧЕНО",
                            "status": str(selected_status),
                            "created_at": moldova_time_iso,
                            "updated_at": moldova_time_iso
                        })
                
                if inventory_payload:
                    # Массовая вставка товаров в inventory через upsert
                    supabase.table("inventory").upsert(
                        inventory_payload, 
                        on_conflict="doc_id,item_name"
                    ).execute()
            # -------------------------------------------------------------

        except Exception as e:
            st.error(f"🚨 Ошибка при сохранении в облако: {e}")
            return 

        # 4. ОБНОВЛЕНИЕ ЛОКАЛЬНОГО ИНТЕРФЕЙСА (Session State)
        ui_data = {
            "📝 Ред.": "⚙️", 
            "id": order_id, 
            "🔍 Просмотр": "👀 Посмотреть", 
            "Статус": selected_status, 
            "Клиент": input_client,
            "Кол-во позиций": len(parsed_items_df), 
            "Общий объем (м3)": round(total_vol, 3), 
            "Сумма заявки": float(total_sum), 
            "КПД загрузки": f"{efficiency:.1f}%", 
            "Адрес клиента": input_address, 
            "Телефон": input_phone, 
            "Адрес загрузки": input_loading_addr, 
            "Сертификат": has_certificate,
            "Водитель": input_driver,
            "ТС": input_ts, 
            "Дата создания": current_date, 
            "Время создания": current_time,
            "Последнее изменение": f"{operator_name} ({current_time})",
            "Фото": "✅ Прикреплено" if final_photo_url else "Нет",
            "Фото фактуры": "✅ Прикреплено" if final_invoice_photo_url else "Нет", # --- ДОБАВЛЕНО ОТОБРАЖЕНИЕ ---
            "Описание": input_desc,
            "Допуск": input_dopusk,
            "🖨️ Печать": False
        }

        new_row_df = pd.DataFrame([ui_data])
        
        if table_key not in st.session_state:
            try:
                st.session_state[table_key] = pd.DataFrame(columns=ORDER_COLUMNS)
            except:
                st.session_state[table_key] = pd.DataFrame()
            
        current_df = st.session_state[table_key]
        if current_df.empty:
            st.session_state[table_key] = new_row_df
        else:
            st.session_state[table_key] = pd.concat([current_df, new_row_df], ignore_index=True)

        # Синхронизация с главной таблицей
        if "main" in st.session_state:
            main_row_df = new_row_df.copy()
            main_row_df["Тип документа"] = "ЗАЯВКА"
            main_row_df = main_row_df.reindex(columns=st.session_state["main"].columns, fill_value="")
            st.session_state["main"] = pd.concat([st.session_state["main"], main_row_df], ignore_index=True)

        st.session_state.active_modal = None
        st.success(f"✅ Документ {order_id} создан, товары добавлены в inventory!")
        st.balloons()
        
        time.sleep(1.5)
        st.rerun()
import streamlit as st
import pandas as pd
import numpy as np
import uuid
import time
from datetime import datetime

@st.dialog("📥 Регистрация нового Прихода (Поставка)", width="large")
def create_arrival_modal(table_key="arrivals"):
    # Импортируем внутри, если они не импортированы глобально, 
    # но лучше делать это в начале функции
    from database import supabase 
    
    st.subheader("🚚 Приемка товаров на склад")
    
    # 0. Проверка инициализации необходимых данных в session_state
    if "drivers" not in st.session_state:
        st.session_state.drivers = pd.DataFrame(columns=["Фамилия", "Имя"])

    # Имя оператора
    try:
        # Пытаемся достать имя из профиля
        operator_name = st.session_state.profile_data.iloc[0]['Значение']
    except Exception:
        operator_name = "Системный администратор"

    # --- 1. ПАРСИНГ СПЕЦИФИКАЦИИ ПОСТАВЩИКА ---
    st.markdown("### 1️⃣ Загрузка накладной (Excel/CSV)")
    uploaded_file = st.file_uploader(
        "📥 Загрузите файл от поставщика", 
        type=["xlsx", "xls", "csv"], 
        key="arrival_uploader"
    )
    
    parsed_items_df = pd.DataFrame()
    total_vol = 0.0
    total_sum = 0.0

    if uploaded_file:
        try:
            # Чтение файла
            if "xls" in uploaded_file.name:
                df = pd.read_excel(uploaded_file)
            else:
                df = pd.read_csv(uploaded_file)
            
            # Поиск колонки с товаром
            name_col = next((c for c in df.columns if any(k in c.lower() for k in ['товар', 'назван', 'артикул', 'наимен'])), None)
            
            if name_col:
                df = df.rename(columns={name_col: 'Название товара'})
                if 'Адрес' not in df.columns: 
                    df['Адрес'] = "НЕ НАЗНАЧЕНО"
                
                # Поиск колонки суммы/цены
                sum_col = next((c for c in df.columns if any(k in c.lower() for k in ['сумма', 'цена', 'итого'])), None)
                if sum_col: 
                    # Очистка данных от лишних символов и перевод в float
                    df[sum_col] = pd.to_numeric(df[sum_col], errors='coerce').fillna(0)
                    total_sum = float(df[sum_col].sum())
                
                parsed_items_df = df
                st.success(f"✅ Найдено товаров в накладной: {len(df)}")
                with st.expander("👀 Предпросмотр позиций"):
                    st.dataframe(df.head(5), use_container_width=True)
            else:
                st.warning("⚠️ Не удалось автоматически определить колонку с названием товара.")
                
        except Exception as e:
            st.error(f"❌ Ошибка парсинга файла: {e}")

    # --- 2. ФОРМА ПРИЕМКИ ---
    # Используем форму, чтобы избежать перезагрузки при каждом вводе символа
    with st.form("arrival_create_form", clear_on_submit=False):
        st.markdown("### 2️⃣ Данные поставки и Сопроводительные документы")
        
        r1_c1, r1_c2, r1_c3 = st.columns([2, 1, 1])
        vendor_name = r1_c1.text_input("🏢 Поставщик / Отправитель", placeholder="ООО 'Мега-Трейд'")
        doc_number = r1_c2.text_input("📄 № Накладной (УПД/ТТН)")
        arrival_type = r1_c3.selectbox("📦 Тип приемки", ["Полная", "Частичная", "Пересорт", "Возврат"])

        st.markdown("🚢 **Логистика**")
        r2_c1, r2_c2, r2_c3, r2_c4 = st.columns(4)
        
        # Безопасное получение списка водителей
        if not st.session_state.drivers.empty and "Фамилия" in st.session_state.drivers.columns:
            drivers_list = ["Наемный (внешний)"] + st.session_state.drivers["Фамилия"].dropna().tolist()
        else:
            drivers_list = ["Наемный (внешний)"]
            
        selected_driver = r2_c1.selectbox("👤 Водитель (Привез)", drivers_list)
        vehicle_num = r2_c2.text_input("🚛 Госномер ТС")
        gate_num = r2_c3.text_input("🚪 Ворота разгрузки", value="Док-1")
        receiver_name = r2_c4.text_input("👷 Приемщик (Кладовщик)", value=operator_name)

        st.divider()
        st.markdown("🛡️ **Входной контроль качества**")
        r3_c1, r3_c2, r3_c3 = st.columns(3)
        package_integrity = r3_c1.selectbox("📦 Целостность упаковки", ["Цела", "Повреждена (см. Брак)", "Следы вскрытия"])
        seals_check = r3_c2.selectbox("🔒 Наличие пломб", ["Есть/Совпадают", "Отсутствуют", "Сорваны"])
        temp_mode = r3_c3.text_input("🌡️ Темп. режим (если нужен)", value="Норма")

        st.divider()
        r4_c1, r4_c2 = st.columns([2, 1])
        comments = r4_c1.text_area("📝 Замечания по приемке", height=70)
        # Сумма подтягивается из файла, но можно изменить вручную
        total_sum_input = r4_c2.number_input("💰 Общая сумма по накладной", min_value=0.0, value=float(total_sum))

        submitted = st.form_submit_button("📥 ПОДТВЕРДИТЬ ПРИЕМКУ И ВНЕСТИ В РЕЕСТР", use_container_width=True)

    # --- 3. ОБРАБОТКА РЕЗУЛЬТАТОВ ---
    if submitted:
        if not vendor_name or not doc_number:
            st.error("❌ Ошибка: Поле 'Поставщик' и '№ Накладной' обязательны!")
            return

        # 1. Генерация уникального ID
        arrival_id = f"IN-{str(uuid.uuid4())[:6].upper()}"
        
        # 2. Очистка состава товаров для JSONB (Supabase не принимает NaN)
        items_json = []
        if not parsed_items_df.empty:
            clean_items_df = parsed_items_df.replace({np.nan: None})
            items_json = clean_items_df.to_dict(orient='records')

        # 3. Формирование Payload для базы
        supabase_payload = {
            "id": arrival_id,
            "status": "На приемке",
            "vendor_name": vendor_name,
            "doc_number": doc_number,
            "driver_name": selected_driver,
            "vehicle_number": vehicle_num,
            "arrival_type": arrival_type,
            "items_count": len(parsed_items_df),
            "total_sum": float(total_sum_input),
            "receiver_name": receiver_name,
            "package_integrity": package_integrity,
            "seals_check": seals_check,
            "temp_mode": temp_mode,
            "comments": comments,
            "gate_number": gate_num,
            "items_data": items_json,
            "print_flag": False
        }

        # 4. Сохранение в Supabase
        try:
            with st.spinner("💾 Сохранение в облако..."):
                supabase.table("arrivals").insert(supabase_payload).execute()
        except Exception as e:
            st.error(f"🚨 Ошибка Supabase: {e}")
            return

        # 5. Обновление локальных Session State для мгновенного отображения
        now_dt = datetime.now()
        
        ui_arrival_data = {
            "📝 Ред.": "⚙️",
            "id": arrival_id,
            "Статус": "На приемке",
            "Поставщик": vendor_name,
            "Документ": doc_number,
            "Водитель": selected_driver,
            "ТС": vehicle_num,
            "Тип": arrival_type,
            "Кол-во позиций": len(parsed_items_df),
            "Сумма заявки": total_sum_input,
            "Приемщик": receiver_name,
            "Целостность": package_integrity,
            "Дата создания": now_dt.strftime("%Y-%m-%d"),
            "Время": now_dt.strftime("%H:%M"),
            "🔍 Просмотр": "👀",
            "🖨️ Печать": False
        }

        # Добавление в реестр Arrivals
        new_row_df = pd.DataFrame([ui_arrival_data])
        if "arrivals" not in st.session_state or st.session_state["arrivals"] is None:
            st.session_state["arrivals"] = new_row_df
        else:
            st.session_state["arrivals"] = pd.concat([st.session_state["arrivals"], new_row_df], ignore_index=True)

        # Добавление в MAIN реестр
        if "main" in st.session_state and st.session_state["main"] is not None:
            main_entry = ui_arrival_data.copy()
            main_entry["Тип документа"] = "ПРИХОД"
            # Синхронизация имен колонок с главной таблицей
            main_entry["Время создания"] = main_entry.pop("Время")
            main_entry["Описание"] = f"Приход: {arrival_type}. Док: {doc_number}. От: {vendor_name}"
            
            main_row_df = pd.DataFrame([main_entry])
            # Приводим структуру к главной таблице (чтобы не было пустых колонок)
            main_row_df = main_row_df.reindex(columns=st.session_state["main"].columns, fill_value="")
            st.session_state["main"] = pd.concat([st.session_state["main"], main_row_df], ignore_index=True)

        st.success(f"✅ Приход {arrival_id} зарегистрирован!")
        time.sleep(1)
        st.rerun()
        
    
@st.dialog("➕ Регистрация Дополнительного События/Услуги", width="large")
def create_extras_modal(*args, **kwargs):
    from database import supabase  # Наше подключение
    import uuid
    from datetime import datetime
    import time
    import pandas as pd

    st.subheader("🛠️ Фиксация доп. работ, ресурсов и согласований")
    
    with st.form("extras_detailed_form"):
        # ЛИНИЯ 1: Кто и когда
        st.markdown("### 👤 Ответственность и Время")
        r1_c1, r1_c2, r1_c3 = st.columns(3)
        approved_by = r1_c1.text_input("👤 Кто одобрил (ФИО)", placeholder="Напр: Иванов И.И.")
        executor = r1_c2.text_input("👷 Исполнитель", placeholder="Бригада 2 / Сотрудник")
        
        # Устанавливаем текущую дату и время
        now_for_input = datetime.now()
        selected_date = r1_c3.date_input("📅 Дата события", now_for_input)
        selected_time = r1_c3.time_input("🕒 Время", now_for_input.time())

        st.divider()

        # Линия 2: Предмет
        st.markdown("### 📦 Предмет дополнения")
        r2_c1, r2_c2, r2_c3 = st.columns([2, 1, 1])
        subject_type = r2_c1.selectbox("Тип ресурса", [
            "ТОВАР (Переупаковка/Замена)", "ПОМОЩЬ (Погрузка/Разгрузка)", 
            "ТЕХНИКА (Аренда кары/ТС)", "МАТЕРИАЛЫ (Паллеты/Стретч)", "ПРОЧЕЕ"
        ])
        resource_used = r2_c2.text_input("🚜 На чем (Ресурс)", placeholder="Кара №4 / Фура")
        location = r2_c3.text_input("📍 Место (Склад/Зона)", value="Зона догруза")

        st.divider()

        # Линия 3: Логика
        st.markdown("### ❓ Причина и Результат")
        r3_c1, r3_c2 = st.columns([2, 1])
        reason = r3_c1.text_area("Почему (Причина возникновения)", height=68, placeholder="Опишите ситуацию детально...")
        status = r3_c2.selectbox("Статус", ["СОГЛАСОВАНО", "В ПРОЦЕССЕ", "ВЫПОЛНЕНО", "ОЖИДАЕТ ОПЛАТЫ"])

        # ЛИНИЯ 4: Цифры
        r4_c1, r4_c2, r4_c3 = st.columns(3)
        qty = r4_c1.number_input("Сколько (Кол-во)", min_value=0.0, value=1.0)
        cost = r4_c2.number_input("Сумма (если применимо, ₽)", min_value=0.0, value=0.0)
        link_id = r4_c3.text_input("🔗 Связь с ID Заявки (если есть)")

        submitted = st.form_submit_button("🚀 ЗАФИКСИРОВАТЬ В БАЗЕ И MAIN", use_container_width=True)

    if submitted:
        # 1. Валидация
        if not approved_by or not reason:
            st.error("❌ Заполните поле 'Кто одобрил' и 'Причина'!")
            return

        # 2. Генерация ID и времени
        extra_id = f"EXT-{str(uuid.uuid4())[:6].upper()}"
        now = datetime.now()
        
        # 3. ПОДГОТОВКА ДАННЫХ ДЛЯ SUPABASE (английские ключи)
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
            "created_at": now.isoformat()
        }

        # 4. ОТПРАВКА В ОБЛАКО
        try:
            supabase.table("extras").insert(supabase_payload).execute()
        except Exception as e:
            st.error(f"🚨 Ошибка сохранения услуги в Supabase: {e}")
            return

        # 5. ОБНОВЛЕНИЕ ЛОКАЛЬНОГО ИНТЕРФЕЙСА (русские ключи для AgGrid)
        ui_extra_data = {
            "📝 Ред.": "⚙️",
            "id": extra_id,
            "Кто одобрил": approved_by,
            "Что именно": subject_type,
            "На чем": resource_used,
            "Когда": selected_date.strftime("%Y-%m-%d"),
            "Время": selected_time.strftime("%H:%M"),
            "Где": location,
            "Почему (Причина)": reason,
            "Статус": status,
            "Кол-во": qty,
            "Сумма заявки": cost,
            "Связь с ID": link_id,
            "Дата создания": now.strftime("%Y-%m-%d"),
            "🔍 Просмотр": "👀",
            "🖨️ Печать": False
        }

        # Обновляем реестр extras в session_state
        new_row_df = pd.DataFrame([ui_extra_data])
        if "extras" not in st.session_state or st.session_state["extras"] is None:
            st.session_state["extras"] = new_row_df
        else:
            st.session_state["extras"] = pd.concat([st.session_state["extras"], new_row_df], ignore_index=True)

        # 6. ЗЕРКАЛИРОВАНИЕ В ТАБЛИЦУ MAIN
        if "main" in st.session_state and st.session_state["main"] is not None:
            main_entry = ui_extra_data.copy()
            main_entry["Тип документа"] = "ДОП.УСЛУГА"
            main_entry["Время создания"] = main_entry.pop("Время")
            main_entry["Описание"] = f"Доп.услуга: {subject_type}. Причина: {reason}"
            main_entry["Статус"] = f"ДОП: {status}"
            
            main_row_df = pd.DataFrame([main_entry])
            main_row_df = main_row_df.reindex(columns=st.session_state["main"].columns, fill_value="")
            st.session_state["main"] = pd.concat([st.session_state["main"], main_row_df], ignore_index=True)

        st.success(f"✅ Услуга {extra_id} сохранена в облаке!")
        time.sleep(1)
        st.rerun()
        
@st.dialog("⚠️ Регистрация Брака / Повреждений", width="large")
def create_defect_modal(table_key="defects", *args, **kwargs):
    from database import supabase
    from datetime import datetime
    import time
    import uuid
    import streamlit as st

    # === 1. ЗАГРУЗКА ДАННЫХ ИЗ БАЗЫ УДАЛЕНА ===
    # Больше никаких проверок. Зависимость от таблицы inventory полностью отключена!

    # === 2. ФОРМА (СВОБОДНЫЙ ВВОД ТОВАРА ВРУЧНУЮ) ===
    with st.form("defect_form_v7_manual_input"):
        st.subheader("🚨 Акт регистрации дефекта") 
        # 1. Свободный ввод названия товара
        item_name_input = st.text_input(
            "📦 Название товара (Обязательно)", 
            placeholder="Впишите точное название поврежденного товара руками..."
        )
        
        st.divider()
        
        col1, col2 = st.columns(2)
        with col1:
            reporter = st.text_input("👤 Кто выявил (ФИО)", placeholder="Имя сотрудника")
            d_type = st.selectbox("📝 Тип дефекта", ["Бой", "Порча", "Брак производителя", "Некомплект", "Утеря"])
        
        with col2:
            # Локация брака
            q_zone = st.text_input("📍 Куда перемещаем (Зона)", value="ZONE-BRAK")
            decision = st.selectbox("⚖️ Решение", ["На проверку", "Списание", "Уценка", "Возврат"])

        col3, col4 = st.columns([1, 2])
        with col3:
            # МИНИМУМ 1, МАКСИМУМ НЕ ОГРАНИЧЕН (так как нет привязки к базе)
            defect_qty = st.number_input(
                "🔢 Количество брака", 
                min_value=1.0, 
                value=1.0,
                step=1.0,
                help="Укажите фактическое количество бракованных единиц."
            )
        
        with col4:
            description = st.text_input("🗒️ Комментарий к дефекту", placeholder="Опишите характер повреждений")

        # Так как мы больше не тянем данные из базы, даем возможность вписать номер документа руками
        linked_doc_input = st.text_input("📄 Связанный документ (Необязательно)", placeholder="Например: номер накладной или партии")

        uploaded_photo = st.file_uploader("📸 Фото повреждения (Обязательно)", type=['png', 'jpg', 'jpeg'])

        submitted = st.form_submit_button("🔥 ЗАРЕГИСТРИРОВАТЬ И СПИСАТЬ", use_container_width=True)

    # === 3. СОХРАНЕНИЕ ===
    if submitted:
        # Проверка обязательных полей (теперь проверяем и ручной ввод товара)
        if not item_name_input.strip():
            st.error("❌ Вы не вписали название товара!")
            return
        if not reporter.strip():
            st.error("❌ Заполните ФИО сотрудника!")
            return
        if not uploaded_photo:
            st.error("❌ Добавьте фото повреждения!")
            return

        with st.spinner("💾 Сохранение в базу данных..."):
            defect_id = f"DEF-{uuid.uuid4().hex[:6].upper()}"
            
            # Загрузка фото в бакет
            photo_url = None
            try:
                f_ext = uploaded_photo.name.split('.')[-1]
                f_name = f"{defect_id}_{int(time.time())}.{f_ext}"
                supabase.storage.from_("defects_photos").upload(f_name, uploaded_photo.getvalue())
                photo_url = supabase.storage.from_("defects_photos").get_public_url(f_name)
            except Exception as img_err:
                st.warning(f"⚠️ Фото не загружено в хранилище: {img_err}")
                pass

            # Формируем payload. Пишем СТРОГО в таблицу defects
            payload = {
                "id": defect_id,
                "created_at": datetime.now().isoformat(),
                "item_name": item_name_input.strip(),  # Берем из текстового поля напрямую
                "quantity": int(defect_qty),
                "storage_address": q_zone,
                "defect_type": d_type,
                "description": description,
                "responsible_party": reporter.strip(),
                "decision": decision,
                "status": "ОБНАРУЖЕНО",
                "photo_url": photo_url,
                "linked_doc_id": linked_doc_input.strip() if linked_doc_input else None  # Сохраняем логику колонки
            }

            try:
                # Физическая вставка в таблицу
                supabase.table("defects").insert(payload).execute()
                
                st.success(f"✅ Акт {defect_id} создан. Товар «{item_name_input}» зарегистрирован как брак.")
                st.balloons()
                
                # Очищаем кэш и перезагружаем страницу
                if hasattr(st, 'cache_data'):
                    st.cache_data.clear()
                
                time.sleep(1.5)
                st.rerun()
            except Exception as e:
                st.error(f"🚨 Ошибка записи в базу: {e}")
                
@st.dialog("👤 Регистрация водителя")
def create_driver_modal():
    from database import supabase
    st.subheader("📝 Данные нового сотрудника")
    
    # Сначала виджет файла
    up_photo = st.file_uploader("📸 Фото водителя", type=["jpg", "png", "jpeg"])
    
    # Потом форма
    with st.form("driver_form_new"):
        col1, col2 = st.columns(2)
        f_name = col1.text_input("Имя")
        l_name = col2.text_input("Фамилия")
        phone = st.text_input("📱 Номер телефона", value="+7")
        license_cat = st.multiselect("🪪 Категории", ["B", "C", "CE", "D"], default=["B", "C"])
        experience = st.slider("Стаж (лет)", 0, 40, 5)
        status = st.selectbox("📍 Статус", ["В штате", "На подработке", "Уволен"])
        
        submitted = st.form_submit_button("✅ СОХРАНИТЬ")

    if submitted:
        if not f_name or not l_name:
            st.error("Заполните ФИО!")
            return

        # ТЕПЕРЬ NameError исчезнет, так как функция определена выше
        final_photo = upload_driver_photo(up_photo) if up_photo else "https://cdn-icons-png.flaticon.com/512/3135/3135715.png"
        
        driver_id = f"DRV-{str(uuid.uuid4())[:4].upper()}"
        
        db_data = {
            "id": driver_id,
            "first_name": f_name,
            "last_name": l_name,
            "phone": phone,
            "categories": ", ".join(license_cat),
            "experience": experience,
            "status": status,
            "photo_url": final_photo,
            "created_at": datetime.now().strftime("%Y-%m-%d")
        }

        try:
            supabase.table("drivers").insert(db_data).execute()
            st.session_state.drivers = pd.DataFrame() # Сброс кэша
            st.success("Водитель добавлен!")
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.error(f"Ошибка базы: {e}")

@st.dialog("⚙️ Редактирование водителя")
def edit_driver_modal(d_id):
    from database import supabase
    # Тянем свежие данные именно по этому ID
    res = supabase.table("drivers").select("*").eq("id", d_id).execute()
    if not res.data: return
    curr = res.data[0]

    f_name = st.text_input("Имя", value=curr['first_name'])
    l_name = st.text_input("Фамилия", value=curr['last_name'])
    phone = st.text_input("Телефон", value=curr['phone'])
    
    # Обработка категорий
    def_cats = curr['categories'].split(", ") if curr['categories'] else []
    cats = st.multiselect("Категории", ["B", "C", "CE", "D"], default=def_cats)
    
    stat = st.selectbox("Статус", ["В штате", "На подработке", "Уволен"], 
                        index=["В штате", "На подработке", "Уволен"].index(curr['status']))
    
    up_photo = st.file_uploader("Обновить фото")

    if st.button("💾 СОХРАНИТЬ"):
        new_photo = upload_driver_photo(up_photo) if up_photo else curr['photo_url']
        
        upd_data = {
            "first_name": f_name, "last_name": l_name, "phone": phone,
            "categories": ", ".join(cats), "status": stat, "photo_url": new_photo
        }
        
        supabase.table("drivers").update(upd_data).eq("id", d_id).execute()
        st.session_state.drivers = pd.DataFrame() # Сброс кэша для обновления списка
        st.success("Изменено!")
        time.sleep(1)
        st.rerun()
        
@st.dialog("🚛 Регистрация ТС", width="large")
def create_vehicle_modal():
    from database import supabase
    import uuid
    from datetime import datetime
    import time
    import pandas as pd # Не забудь импорт pandas

    st.subheader("📋 Технический паспорт автомобиля")
    uploaded_v_photo = st.file_uploader("📸 Фото автомобиля", type=["jpg", "png"], key="upload_v_new")

    with st.form("vehicle_form", clear_on_submit=True):
        col_side, col_main = st.columns([1, 2])
        with col_side:
            brand = st.text_input("Марка / Модель", placeholder="Газель Next")
            v_type = st.selectbox("Тип кузова", ["Тент", "Рефрижератор", "Изотерм", "Бортовой"])
        
        with col_main:
            r1_c1, r1_c2 = st.columns(2)
            gov_num = r1_c1.text_input("🔢 Госномер")
            vin = r1_c2.text_input("🆔 VIN-код")
            
            st.divider()
            r2_c1, r2_c2, r2_c3 = st.columns(3)
            cap = r2_c1.number_input("Грузоподъемность (кг)", value=1500)
            vol = r2_c2.number_input("Объем (м³)", value=12.0)
            pal = r2_c3.number_input("Паллеты", value=4)
            
            st.divider()
            r3_c1, r3_c2 = st.columns(2)
            l_to = r3_c1.date_input("Дата ТО", value=datetime.now())
            ins = r3_c2.date_input("Страховка до", value=datetime.now())

        # КНОПКА ДОЛЖНА БЫТЬ ТУТ (внутри with st.form)
        submitted = st.form_submit_button("✅ ВНЕСТИ ТС В РЕЕСТР", use_container_width=True)

        if submitted:
            if not gov_num or not brand:
                st.error("🚨 Заполните обязательные поля: Госномер и Марка!")
            else:
                clean_gov_num = gov_num.strip().upper()

                try:
                    # Проверка на дубликат
                    existing = supabase.table("vehicles").select("id").eq("gov_num", clean_gov_num).execute()
                    if existing.data:
                        st.warning(f"⚠️ Автомобиль с госномером **{clean_gov_num}** уже существует!")
                    else:
                        vehicle_id = f"VEH-{str(uuid.uuid4())[:4].upper()}"
                        
                        # Обработка фото
                        final_v_photo = None
                        try:
                            final_v_photo = process_image(uploaded_v_photo)
                        except:
                            pass
                        
                        if not final_v_photo:
                            final_v_photo = globals().get('img_map', {}).get(v_type, "https://cdn-icons-png.flaticon.com/512/2554/2554977.png")

                        db_payload = {
                            "id": vehicle_id,
                            "brand": brand,
                            "gov_num": clean_gov_num, 
                            "vin": vin.strip().upper() if vin else None,
                            "body_type": v_type,
                            "capacity": float(cap),
                            "volume": float(vol),
                            "pallets": int(pal),
                            "last_service": l_to.strftime("%Y-%m-%d"),
                            "insurance_expiry": ins.strftime("%Y-%m-%d"),
                            "photo_url": final_v_photo,
                            "status": "На линии"
                        }

                        supabase.table("vehicles").insert(db_payload).execute()
                        
                        # Обновляем локальный список для UI
                        new_v_ui = {
                            "id": vehicle_id, 
                            "Марка": brand, "Госномер": clean_gov_num, "Тип": v_type, 
                            "Грузоподъемность": cap, "Объем": vol, "Паллеты": pal,
                            "ТО": l_to.strftime("%Y-%m-%d"), "Страховка": ins.strftime("%Y-%m-%d"),
                            "Фото": final_v_photo, "Статус": "На линии"
                        }
                        
                        if "vehicles" in st.session_state:
                            st.session_state.vehicles = pd.concat([st.session_state.vehicles, pd.DataFrame([new_v_ui])], ignore_index=True)

                        st.success(f"✅ ТС {clean_gov_num} добавлено!")
                        time.sleep(1)
                        st.rerun()
                        
                except Exception as e:
                    st.error(f"Ошибка: {e}")

@st.dialog("⚙️ Редактирование ТС", width="large")
def edit_vehicle_modal():
    from database import supabase
    from datetime import datetime
    import time

    if not st.session_state.get("editing_id"):
        st.error("ID автомобиля не найден!")
        return

    v_id = st.session_state.editing_id
    df = st.session_state.vehicles
    
    matching = df.index[df['id'] == v_id].tolist()
    if not matching:
        st.error("Автомобиль не найден в локальном списке!")
        return
        
    idx = matching[0]
    curr = df.loc[idx]

    # БЕЗОПАСНОЕ ПОЛУЧЕНИЕ ДАННЫХ (защита от KeyError)
    curr_gov_num = curr.get('Госномер') or curr.get('gov_num') or "Н/Д"
    curr_brand = curr.get('Марка') or curr.get('brand') or ""
    curr_type = curr.get('Тип') or curr.get('body_type') or "Тент"
    curr_cap = curr.get('Грузоподъемность') or curr.get('capacity') or 0
    curr_vol = curr.get('Объем') or curr.get('volume') or 0
    curr_pal = curr.get('Паллеты') or curr.get('pallets') or 0
    curr_photo = curr.get('Фото') or curr.get('photo_url')

    st.subheader(f"⚙️ {curr_gov_num}")
    up_v_photo = st.file_uploader("📸 Обновить фото", type=["jpg", "png"], key=f"up_v_{v_id}")

    with st.form("edit_v_form"):
        c1, c2 = st.columns(2)
        brand = c1.text_input("Марка", value=str(curr_brand))
        v_types = ["Тент", "Рефрижератор", "Изотерм", "Бортовой"]
        v_type = c2.selectbox("Тип", v_types, index=v_types.index(curr_type) if curr_type in v_types else 0)
        
        st.divider()
        r2_1, r2_2, r2_3 = st.columns(3)
        cap = r2_1.number_input("Грузоподъемность", value=float(curr_cap))
        vol = r2_2.number_input("Объем", value=float(curr_vol))
        pal = r2_3.number_input("Паллеты", value=int(curr_pal))
        
        st.divider()
        # Парсим даты безопасно
        try:
            d_to = datetime.strptime(str(curr.get('ТО') or curr.get('last_service')), "%Y-%m-%d")
            d_ins = datetime.strptime(str(curr.get('Страховка') or curr.get('insurance_expiry')), "%Y-%m-%d")
        except:
            d_to, d_ins = datetime.now(), datetime.now()

        r3_1, r3_2 = st.columns(2)
        new_to = r3_1.date_input("Дата ТО", value=d_to)
        new_ins = r3_2.date_input("Страховка до", value=d_ins)
        
        submitted = st.form_submit_button("💾 СОХРАНИТЬ ИЗМЕНЕНИЯ", use_container_width=True)

    if submitted:
        new_photo = curr_photo
        if up_v_photo:
            try: 
                new_photo = process_image(up_v_photo)
            except: 
                pass

        update_payload = {
            "brand": brand,
            "body_type": v_type,
            "capacity": float(cap),
            "volume": float(vol),
            "pallets": int(pal),
            "last_service": new_to.strftime("%Y-%m-%d"),
            "insurance_expiry": new_ins.strftime("%Y-%m-%d"),
            "photo_url": new_photo
        }

        try:
            supabase.table("vehicles").update(update_payload).eq("id", v_id).execute()
            
            # Обновляем локальный DataFrame
            df.at[idx, 'Марка'] = brand
            df.at[idx, 'Тип'] = v_type
            df.at[idx, 'Грузоподъемность'] = cap
            df.at[idx, 'Объем'] = vol
            df.at[idx, 'Паллеты'] = pal
            df.at[idx, 'ТО'] = new_to.strftime("%Y-%m-%d")
            df.at[idx, 'Страховка'] = new_ins.strftime("%Y-%m-%d")
            df.at[idx, 'Фото'] = new_photo
            
            st.session_state.vehicles = df
            st.success("Данные успешно синхронизированы!")
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.error(f"Ошибка БД: {e}")

















































