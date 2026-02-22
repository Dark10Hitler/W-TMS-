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
    # Получаем структуру колонок (предполагается наличие этих констант в вашем коде)
    columns = TABLE_STRUCT.get(table_key, ORDER_COLUMNS) # Заменил дефолт на ORDER_COLUMNS
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
    total_weight = 0.0 

    if uploaded_file:
        try:
            # Чтение файла
            df = pd.read_excel(uploaded_file) if "xls" in uploaded_file.name else pd.read_csv(uploaded_file)
            
            # Ищем нужную колонку с названием товара
            name_col = next((c for c in df.columns if 'назван' in c.lower() or 'товар' in c.lower() or 'наимен' in c.lower()), None)
            
            if not name_col:
                st.error("❌ Не нашел колонку с названием товара! Укажите её вручную:")
                name_col = st.selectbox("Выберите колонку с товаром", df.columns)
            
            # Переименовываем для стабильной работы кода
            df = df.rename(columns={name_col: 'Название товара'})
            
            # Авто-расчет итогов (если колонки есть)
            vol_col = next((c for c in df.columns if 'объем' in c.lower() or 'м3' in c.lower()), None)
            sum_col = next((c for c in df.columns if 'сумма' in c.lower() or 'цена' in c.lower()), None)
            
            if vol_col: total_vol = float(df[vol_col].sum())
            if sum_col: total_sum = float(df[sum_col].sum())
            
            # Добавляем колонку Адрес по умолчанию, если её нет
            if 'Адрес' not in df.columns:
                df['Адрес'] = "НЕ НАЗНАЧЕНО"
            
            parsed_items_df = df
            st.success(f"✅ Файл прочитан. Найдено позиций: {len(df)} | Общий объем: {total_vol:.2f} м3 | Общая сумма: {total_sum:.2f}")
            with st.expander("👀 Предпросмотр загруженных позиций"):
                st.dataframe(df.head(5), use_container_width=True)

        except Exception as e:
            st.error(f"❌ Ошибка парсинга файла: {e}")

    # --- 2. ФОРМА ВВОДА ДАННЫХ ---
    st.markdown("### 2️⃣ Параметры заявки и Логистика")
    with st.form(f"full_create_form_{table_key}", clear_on_submit=False):
        
        # ЛИНИЯ 1: Данные Клиента
        st.markdown("👤 **Информация о клиенте**")
        r1_c1, r1_c2, r1_c3 = st.columns(3)
        
        # Пытаемся взять клиента из файла, если он там есть
        default_client = ""
        if not parsed_items_df.empty and 'Клиент' in parsed_items_df.columns:
            default_client = str(parsed_items_df['Клиент'].iloc[0])
            
        input_client = r1_c1.text_input("Название Клиента*", value=default_client, help="Обязательное поле")
        input_address = r1_c2.text_input("Адрес доставки (Адрес клиента)")
        input_phone = r1_c3.text_input("Телефон")

        st.divider()

        # ЛИНИЯ 2: Основные статусы и транспорт
        st.markdown("🚚 **Транспорт и Статус**")
        r2_c1, r2_c2, r2_c3, r2_c4 = st.columns(4)
        
        status_options = ["ОЖИДАНИЕ", "Стоит на точке загрузки", "Выехал", "Ожидает догруз", "В пути", "Доставлено"]
        selected_status = r2_c1.selectbox("📍 Статус заявки", status_options)

        # Проверка наличия данных в справочниках
        drivers_list = ["Наемный водитель"]
        if 'drivers' in st.session_state and not st.session_state.drivers.empty:
            drivers_list += st.session_state.drivers["Фамилия"].tolist()
            
        vehicles_list = ["Стороннее ТС"]
        if 'vehicles' in st.session_state and not st.session_state.vehicles.empty:
            vehicles_list += st.session_state.vehicles["Госномер"].tolist()
        
        selected_driver = r2_c2.selectbox("👤 Водитель", drivers_list)
        selected_ts = r2_c3.selectbox("🚛 ТС (Госномер)", vehicles_list) # Соответствует колонке "ТС"
        has_certificate = r2_c4.selectbox("📜 Сертификат", ["Нет", "Да"])

        st.divider()

        # ЛИНИЯ 3: Контроль загрузки и Допуск
        st.markdown("⚖️ **Лимиты и Ответственность**")
        r3_c1, r3_c2, r3_c3, r3_c4 = st.columns(4)
        
        v_capacity = r3_c1.number_input("Грузоподъемность ТС (кг)", min_value=0, value=1500)
        v_max_vol = r3_c2.number_input("Объем кузова ТС (м3)", min_value=0.1, value=12.0)
        input_dopusk = r3_c3.text_input("👤 Допуск (Кто разрешил)", placeholder="Введите ФИО")
        input_loading_addr = r3_c4.text_input("Адрес загрузки", value="Центральный склад")

        st.divider()

        # ЛИНИЯ 4: Медиа и Описание
        st.markdown("📝 **Дополнительные сведения и Документы**")
        r4_c1, r4_c2 = st.columns([2, 1])
        
        input_desc = r4_c1.text_area("Описание (детально по товару или особые отметки)", height=100)
        
        # Добавляем загрузку фото для колонки "Фото"
        uploaded_photo = r4_c2.file_uploader("📸 Прикрепить фото (Накладная/Груз)", type=['png', 'jpg', 'jpeg'])
        photo_status = "Прикреплено" if uploaded_photo else "Нет"

        # КНОПКА
        st.markdown("<br>", unsafe_allow_html=True)
        submitted = st.form_submit_button("🚀 СФОРМИРОВАТЬ И СОХРАНИТЬ ЗАЯВКУ", use_container_width=True)

    # --- 3. ОБРАБОТКА СОХРАНЕНИЯ ---
    if submitted:
        # 1. Строгая Валидация
        if not input_client:
            st.error("❌ Ошибка: Поле 'Название Клиента' обязательно для заполнения!")
            return

        # 2. Генерация уникального ID
        import uuid
        order_id = str(uuid.uuid4())[:8].upper()
        
        # Определение текущего времени
        current_date = datetime.now().strftime("%Y-%m-%d")
        current_time = datetime.now().strftime("%H:%M:%S")

        # 3. Сохранение позиций товаров в отдельный реестр (для просмотра деталей)
        if not parsed_items_df.empty:
            if "items_registry" not in st.session_state:
                st.session_state.items_registry = {}
            st.session_state.items_registry[order_id] = parsed_items_df

        # Логика обработки фото (сохранение в Session State или файловую систему)
        # В данном примере просто фиксируем статус для таблицы, но в реальном приложении 
        # вы сохраните uploaded_photo.read() куда-либо
        if uploaded_photo:
            if "photos_registry" not in st.session_state:
                st.session_state.photos_registry = {}
            st.session_state.photos_registry[order_id] = uploaded_photo.name

        # 4. Расчет КПД загрузки ТС
        efficiency = (total_vol / v_max_vol) * 100 if v_max_vol > 0 else 0

        # 5. СБОР ПОЛНЫХ ДАННЫХ СТРОГО ПО ORDER_COLUMNS
        new_data = {
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
            "Водитель": selected_driver,
            "ТС": selected_ts, # Исправлено на 'ТС' согласно ORDER_COLUMNS
            "Дата создания": current_date, 
            "Время создания": current_time,
            "Последнее изменение": f"{operator_name} ({current_time})",
            "Фото": photo_status, # Добавлена колонка Фото
            "Описание": input_desc,
            "Допуск": input_dopusk,
            "🖨️ Печать": False
        }

        # Превращаем в DataFrame для вставки
        new_row_df = pd.DataFrame([new_data])
        
        # 6. СОХРАНЕНИЕ В РЕЕСТР ЗАЯВОК 
        # Используем безопасное извлечение таблицы
        if table_key not in st.session_state:
            st.session_state[table_key] = pd.DataFrame(columns=ORDER_COLUMNS)
            
        # Проверяем, есть ли уже колонки, чтобы избежать сдвигов
        current_df = st.session_state[table_key]
        if current_df.empty:
            st.session_state[table_key] = new_row_df
        else:
            st.session_state[table_key] = pd.concat([current_df, new_row_df], ignore_index=True)

        # 7. ЗЕРКАЛИРОВАНИЕ В ТАБЛИЦУ MAIN
        if "main" not in st.session_state:
            # Инициализация main, если её нет. Предполагается, что MAIN_COLUMNS импортируется.
            try:
                from constants import MAIN_COLUMNS
                st.session_state["main"] = pd.DataFrame(columns=MAIN_COLUMNS)
            except ImportError:
                # Fallback, если не смогли импортировать
                st.session_state["main"] = pd.DataFrame(columns=ORDER_COLUMNS + ["Тип документа"])

        main_row_df = new_row_df.copy()
        main_row_df["Тип документа"] = "ЗАЯВКА"
        
        # Выравниваем колонки
        main_row_df = main_row_df.reindex(columns=st.session_state["main"].columns, fill_value="")
        st.session_state["main"] = pd.concat([st.session_state["main"], main_row_df], ignore_index=True)

        # 8. Завершение работы модалки
        st.session_state.active_modal = None
        st.success(f"✅ Документ {order_id} для клиента {input_client} успешно создан!")
        
        import time
        time.sleep(1.5)
        st.rerun()

@st.dialog("📥 Регистрация нового Прихода (Поставка)", width="large")
def create_arrival_modal():
    st.subheader("🚚 Приемка товаров на склад")
    
    # Имя оператора
    try:
        operator_name = st.session_state.profile_data.iloc[0]['Значение']
    except:
        operator_name = "Системный администратор"

    # --- 1. ПАРСИНГ СПЕЦИФИКАЦИИ ПОСТАВЩИКА ---
    st.markdown("### 1️⃣ Загрузка накладной (Excel/CSV)")
    uploaded_file = st.file_uploader("📥 Загрузите файл от поставщика для авто-разбора позиций", type=["xlsx", "xls", "csv"], key="arrival_uploader")
    
    parsed_items_df = pd.DataFrame()
    total_vol = 0.0
    total_sum = 0.0

    if uploaded_file:
        try:
            df = pd.read_excel(uploaded_file) if "xls" in uploaded_file.name else pd.read_csv(uploaded_file)
            name_col = next((c for c in df.columns if any(k in c.lower() for k in ['товар', 'назван', 'артикул'])), None)
            if name_col:
                df = df.rename(columns={name_col: 'Название товара'})
                if 'Адрес' not in df.columns: df['Адрес'] = "НЕ НАЗНАЧЕНО"
                parsed_items_df = df
                st.success(f"✅ Найдено товаров в накладной: {len(df)}")
                st.dataframe(df.head(3), use_container_width=True)
        except Exception as e:
            st.error(f"Ошибка парсинга файла: {e}")

    # --- 2. ФОРМА ПРИЕМКИ ---
    with st.form("arrival_create_form"):
        st.markdown("### 2️⃣ Данные поставки и Сопроводительные документы")
        
        # ЛИНИЯ 1: Контрагент и Документы
        r1_c1, r1_c2, r1_c3 = st.columns([2, 1, 1])
        vendor_name = r1_c1.text_input("🏢 Поставщик / Отправитель", placeholder="ООО 'Мега-Трейд'")
        doc_number = r1_c2.text_input("📄 № Накладной (УПД/ТТН)")
        arrival_type = r1_c3.selectbox("📦 Тип приемки", ["Полная", "Частичная", "Пересорт", "Возврат"])

        # ЛИНИЯ 2: Транспорт и Ответственные
        st.markdown("🚢 **Логистика**")
        r2_c1, r2_c2, r2_c3, r2_c4 = st.columns(4)
        
        drivers_list = ["Наемный (внешний)"] + (st.session_state.drivers["Фамилия"].tolist() if not st.session_state.drivers.empty else [])
        selected_driver = r2_c1.selectbox("👤 Водитель (Привез)", drivers_list)
        vehicle_num = r2_c2.text_input("🚛 Госномер ТС")
        gate_num = r2_c3.text_input("🚪 Ворота разгрузки", value="Док-1")
        receiver_name = r2_c4.text_input("👷 Приемщик (Кладовщик)", value=operator_name)

        st.divider()

        # ЛИНИЯ 3: Состояние и Качество
        st.markdown("🛡️ **Входной контроль качества**")
        r3_c1, r3_c2, r3_c3 = st.columns(3)
        package_integrity = r3_c1.selectbox("📦 Целостность упаковки", ["Цела", "Повреждена (см. Брак)", "Следы вскрытия"])
        seals_check = r3_c2.selectbox("🔒 Наличие пломб", ["Есть/Совпадают", "Отсутствуют", "Сорваны"])
        temp_mode = r3_c3.text_input("🌡️ Темп. режим (если нужен)", value="Норма")

        # ЛИНИЯ 4: Итоговые данные
        st.divider()
        r4_c1, r4_c2 = st.columns([2, 1])
        comments = r4_c1.text_area("📝 Замечания по приемке", height=70)
        total_sum_input = r4_c2.number_input("💰 Общая сумма по накладной (₽)", min_value=0.0, value=float(total_sum))

        submitted = st.form_submit_button("📥 ПОДТВЕРДИТЬ ПРИЕМКУ И ВНЕСТИ В РЕЕСТР", use_container_width=True)

    if submitted:
            # 1. Валидация
            if not vendor_name or not doc_number:
                st.error("❌ Укажите поставщика и номер документа!")
                return

            # 2. Генерация ID
            import uuid
            arrival_id = f"IN-{str(uuid.uuid4())[:6].upper()}"
            
            # 3. Сохранение позиций в реестр товаров (items_registry)
            if not parsed_items_df.empty:
                if "items_registry" not in st.session_state: 
                    st.session_state.items_registry = {}
                st.session_state.items_registry[arrival_id] = parsed_items_df

            # 4. ПОЛНЫЕ ДАННЫХ ДЛЯ ТАБЛИЦЫ ARRIVALS (Специфический реестр)
            arrival_data = {
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
                "Дата создания": datetime.now().strftime("%Y-%m-%d"),
                "Время": datetime.now().strftime("%H:%M"),
                "🔍 Просмотр": "👀",
                "🖨️ Печать": False
            }

            # Создаем DataFrame для вставки
            arrival_row_df = pd.DataFrame([arrival_data])

            # 5. СОХРАНЕНИЕ В РЕЕСТР ПРИХОДОВ
            if "arrivals" not in st.session_state:
                st.session_state["arrivals"] = pd.DataFrame(columns=arrival_data.keys())
            
            st.session_state["arrivals"] = pd.concat([st.session_state["arrivals"], arrival_row_df], ignore_index=True)

            # 6. ЗЕРКАЛИРОВАНИЕ В ТАБЛИЦУ MAIN (Полное соответствие колонкам)
            # Здесь мы используем MAIN_COLUMNS, чтобы данные легли в свои специфические ячейки
            
            if "main" not in st.session_state:
                from constants import MAIN_COLUMNS
                st.session_state["main"] = pd.DataFrame(columns=MAIN_COLUMNS)

            # Подготавливаем строку для Main
            main_entry = arrival_data.copy()
            main_entry["Тип документа"] = "ПРИХОД"
            
            # Синхронизируем название колонки времени, если в Main она называется "Время создания"
            if "Время" in main_entry:
                main_entry["Время создания"] = main_entry.pop("Время")
            
            # Описание формируем подробно
            main_entry["Описание"] = f"Приход: {arrival_type}. Док: {doc_number}. Целостность: {package_integrity}"
            
            # Создаем DF и выравниваем его по всем колонкам Main (пустые заполнятся "")
            main_row_df = pd.DataFrame([main_entry])
            main_row_df = main_row_df.reindex(columns=st.session_state["main"].columns, fill_value="")
            
            st.session_state["main"] = pd.concat([st.session_state["main"], main_row_df], ignore_index=True)

            # 7. Финал
            st.success(f"✅ Приход {arrival_id} успешно зарегистрирован!")
            st.session_state.active_modal = None
            
            import time
            time.sleep(1)
            st.rerun()
        
    
@st.dialog("➕ Регистрация Дополнительного События/Услуги", width="large")
def create_extras_modal():
    st.subheader("🛠️ Фиксация доп. работ, ресурсов и согласований")
    
    with st.form("extras_detailed_form"):
        # ЛИНИЯ 1: Кто и когда
        st.markdown("### 👤 Ответственность и Время")
        r1_c1, r1_c2, r1_c3 = st.columns(3)
        approved_by = r1_c1.text_input("👤 Кто одобрил (ФИО)", placeholder="Напр: Иванов И.И.")
        executor = r1_c2.text_input("👷 Исполнитель", placeholder="Бригада 2 / Сотрудник")
        
        # ИСПРАВЛЕНИЕ: Используем date_input вместо несуществующего datetime_input
        # Если время критично, можно добавить второй виджет в ту же колонку
        selected_date = r1_c3.date_input("📅 Дата события", datetime.now())
        selected_time = r1_c3.time_input("🕒 Время", datetime.now().time())

        st.divider()

        # ... (ваш код Линии 2 и 3 без изменений) ...
        # Линия 2
        st.markdown("### 📦 Предмет дополнения")
        r2_c1, r2_c2, r2_c3 = st.columns([2, 1, 1])
        subject_type = r2_c1.selectbox("Тип ресурса", [
            "ТОВАР (Переупаковка/Замена)", "ПОМОЩЬ (Погрузка/Разгрузка)", 
            "ТЕХНИКА (Аренда кары/ТС)", "МАТЕРИАЛЫ (Паллеты/Стретч)", "ПРОЧЕЕ"
        ])
        resource_used = r2_c2.text_input("🚜 На чем (Ресурс)", placeholder="Кара №4 / Фура")
        location = r2_c3.text_input("📍 Место (Склад/Зона)", value="Зона догруза")

        st.divider()

        # Линия 3
        st.markdown("### ❓ Причина и Результат")
        r3_c1, r3_c2 = st.columns([2, 1])
        reason = r3_c1.text_area("Почему (Причина возникновения)", height=68, placeholder="Опишите ситуацию детально...")
        status = r3_c2.selectbox("Статус", ["СОГЛАСОВАНО", "В ПРОЦЕССЕ", "ВЫПОЛНЕНО", "ОЖИДАЕТ ОПЛАТЫ"])

        # ЛИНИЯ 4
        r4_c1, r4_c2, r4_c3 = st.columns(3)
        qty = r4_c1.number_input("Сколько (Кол-во)", min_value=0.0, value=1.0)
        cost = r4_c2.number_input("Сумма (если применимо, ₽)", min_value=0.0, value=0.0)
        link_id = r4_c3.text_input("🔗 Связь с ID Заявки (если есть)")

        # Теперь кнопка будет видна и распознана
        submitted = st.form_submit_button("🚀 ЗАФИКСИРОВАТЬ В БАЗЕ И MAIN", use_container_width=True)

    if submitted:
        # 1. Генерация ID и подготовка времени
        import uuid
        extra_id = f"EXT-{str(uuid.uuid4())[:6].upper()}"
        now = datetime.now()
        
        # 2. ПОЛНЫЕ ДАННЫЕ ДЛЯ ТАБЛИЦЫ EXTRAS (Специфический реестр)
        extra_data = {
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
        
        # Создаем DataFrame для вставки
        extra_row_df = pd.DataFrame([extra_data])

        # 3. СОХРАНЕНИЕ В РЕЕСТР ДОПОЛНЕНИЙ
        if "extras" not in st.session_state:
            st.session_state["extras"] = pd.DataFrame(columns=extra_data.keys())
        
        st.session_state["extras"] = pd.concat([st.session_state["extras"], extra_row_df], ignore_index=True)

        # 4. ЗЕРКАЛИРОВАНИЕ В ТАБЛИЦУ MAIN (Глобальный реестр)
        # Мы НЕ "впихиваем" Одобрившего в колонку Клиент. 
        # Мы используем MAIN_COLUMNS, где для этого есть свои поля.

        if "main" not in st.session_state:
            from constants import MAIN_COLUMNS
            st.session_state["main"] = pd.DataFrame(columns=MAIN_COLUMNS)

        # Подготавливаем данные для Main
        main_entry = extra_data.copy()
        main_entry["Тип документа"] = "ДОП.УСЛУГА"
        
        # Синхронизируем колонки времени и описания
        main_entry["Время создания"] = main_entry.pop("Время")
        main_entry["Описание"] = f"Доп.услуга: {subject_type}. Причина: {reason}"
        
        # Если в Main нужна колонка "Статус" с префиксом (опционально)
        main_entry["Статус"] = f"ДОП: {status}"

        # Создаем DF и выравниваем его по всем колонкам Main
        main_row_df = pd.DataFrame([main_entry])
        main_row_df = main_row_df.reindex(columns=st.session_state["main"].columns, fill_value="")
        
        st.session_state["main"] = pd.concat([st.session_state["main"], main_row_df], ignore_index=True)

        # 5. Завершение
        st.success(f"✅ Дополнение {extra_id} успешно добавлено!")
        st.session_state.active_modal = None
        
        import time
        time.sleep(1)
        st.rerun()
        
@st.dialog("⚠️ Регистрация Брака / Повреждений", width="large")
def create_defect_modal():
    st.subheader("🚨 Акт о выявлении дефектов")
    
    # 1. Получаем все товары из всех активных заказов/приходов для выбора
    inventory_df = get_full_inventory_df()
    
    if inventory_df.empty:
        st.warning("В базе данных нет товаров для оформления брака.")
        return

    # Создаем список для выбора: "Товар [ID Документа] - Адрес"
    inventory_df['display_name'] = inventory_df['Название товара'] + " (Док: " + inventory_df['ID Документа'] + ") [" + inventory_df['Адрес'] + "]"
    
    with st.form("defect_form"):
        st.markdown("### 1️⃣ Выбор поврежденного товара")
        
        # Выбор товара из БД
        selected_item_name = st.selectbox("🔍 Выберите товар из базы данных", inventory_df['display_name'].unique())
        
        # Получаем данные выбранного товара для лимитов
        item_info = inventory_df[inventory_df['display_name'] == selected_item_name].iloc[0]
        max_qty = 100 # Если в БД нет колонки количества, ставим лимит. Если есть — берем из item_info['Кол-во']
        
        st.info(f"📍 Текущее местоположение: **{item_info['Адрес']}** | Оригинальный документ: **{item_info['ID Документа']}**")

        st.divider()
        
        st.markdown("### 2️⃣ Детали повреждения")
        col1, col2, col3 = st.columns(3)
        
        defect_qty = col1.number_input("Количество брака (шт/ед)", min_value=1, value=1)
        defect_type = col2.selectbox("Тип брака", ["Механическое", "Залитие", "Заводской брак", "Испорчена упаковка", "Срок годности"])
        responsibility = col3.selectbox("Виновная сторона", ["Поставщик", "Транспортная компания", "Склад", "Клиент (возврат)"])

        st.divider()
        
        st.markdown("### 3️⃣ Обоснование и Решение")
        r3_c1, r3_c2 = st.columns([2, 1])
        defect_desc = r3_c1.text_area("Описание дефекта (детально)", placeholder="Напр: Треснул корпус при разгрузке...")
        action_taken = r3_c2.selectbox("Решение", ["Списание", "Возврат поставщику", "Уценка/Ремонт", "Карантин"])

        # Поля для Main
        st.divider()
        approved_by = st.text_input("👤 Кто зафиксировал брак (ФИО)", value=st.session_state.get('user_name', 'Старший смены'))

        submitted = st.form_submit_button("🚨 ОФОРМИТЬ АКТ БРАКА", use_container_width=True)

    if submitted:
        # 1. Генерация уникального ID акта брака
        import uuid
        defect_id = f"BRK-{str(uuid.uuid4())[:6].upper()}"
        
        # 2. ПОЛНЫЕ ДАННЫЕ ДЛЯ ТАБЛИЦЫ DEFECTS (Специфический реестр)
        # Ничего не сокращаем, записываем все технические детали
        defect_data = {
            "📝 Ред.": "⚙️",
            "id": defect_id,
            "Товар": item_info['Название товара'],
            "Кол-во брака": defect_qty,
            "Адрес хранения": item_info['Адрес'],
            "Тип дефекта": defect_type,
            "Виновник": responsibility,
            "Решение": action_taken,
            "Связь с документом": item_info['ID Документа'],
            "Дата создания": datetime.now().strftime("%Y-%m-%d"),
            "Время": datetime.now().strftime("%H:%M"), # Добавили время для точности
            "Статус": "АКТИВЕН",
            "🔍 Просмотр": "👀",
            "🖨️ Печать": False # Добавили поле печати для единообразия
        }

        # Превращаем в DataFrame для вставки
        defect_row_df = pd.DataFrame([defect_data])

        # 3. СОХРАНЕНИЕ В РЕЕСТР БРАКА
        # Проверяем инициализацию таблицы
        if "defects" not in st.session_state:
            st.session_state["defects"] = pd.DataFrame(columns=defect_data.keys())
        
        st.session_state["defects"] = pd.concat([st.session_state["defects"], defect_row_df], ignore_index=True)

        # 4. ЗЕРКАЛИРОВАНИЕ В MAIN — ИСКЛЮЧЕНО
        # Согласно вашему требованию, брак в общую таблицу (Main) не идет.
        # Это позволяет разделить финансовые потоки и складские потери.

        # 5. Завершение работы
        st.success(f"✅ Акт брака {defect_id} оформлен и сохранен в реестре брака!")
        st.session_state.active_modal = None
        
        import time
        time.sleep(1)
        st.rerun()

@st.dialog("👤 Регистрация водителя", width="medium")
def create_driver_modal():
    st.subheader("📝 Данные нового сотрудника")
    uploaded_photo = st.file_uploader("📸 Фото водителя", type=["jpg", "png", "jpeg"], key="upload_drv_new")
    
    with st.form("driver_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        f_name = col1.text_input("Имя")
        l_name = col2.text_input("Фамилия")
        phone = st.text_input("📱 Номер телефона", value="+7 ")
        license_cat = st.multiselect("🪪 Категории прав", ["B", "C", "CE", "D"], default=["B", "C"])
        
        st.divider()
        experience = st.slider("Стаж вождения (лет)", 0, 40, 5)
        status = st.selectbox("📍 Текущий статус", ["В штате", "На подработке", "Уволен"])
        
        submitted = st.form_submit_button("✅ СОХРАНИТЬ КАРТОЧКУ", use_container_width=True)

    if submitted:
        if not f_name or not l_name:
            st.error("Введите имя и фамилию!")
            return
        
        final_photo = process_image(uploaded_photo) or "https://cdn-icons-png.flaticon.com/512/3135/3135715.png"
        
        new_driver = {
            "id": f"DRV-{str(uuid.uuid4())[:4].upper()}",
            "Имя": f_name, "Фамилия": l_name, "Телефон": phone,
            "Категории": ", ".join(license_cat), "Стаж": experience,
            "Статус": status, "Фото": final_photo,
            "Дата регистрации": datetime.now().strftime("%Y-%m-%d")
        }
        
        st.session_state.drivers = pd.concat([st.session_state.drivers, pd.DataFrame([new_driver])], ignore_index=True)
        st.success(f"Водитель {l_name} добавлен!")
        
        # ОЧИСТКА ВСЕХ ФЛАГОВ ПЕРЕД ВЫХОДОМ
        st.session_state.active_modal = None
        st.session_state.active_edit_modal = None
        time.sleep(1)
        st.rerun()

@st.dialog("⚙️ Редактирование водителя", width="medium")
def edit_driver_modal():
    # Защита от пустого ID
    if not st.session_state.get("editing_id"):
        st.error("Ошибка: ID не найден")
        return

    d_id = st.session_state.editing_id
    df = st.session_state.drivers
    
    # Ищем индекс водителя
    matching_rows = df.index[df['id'] == d_id].tolist()
    if not matching_rows:
        st.error("Водитель не найден в базе")
        return
        
    idx = matching_rows[0]
    curr = df.loc[idx]

    st.subheader(f"Изменение: {curr['Фамилия']}")
    up_photo = st.file_uploader("📸 Обновить фото", type=["jpg", "png", "jpeg"], key=f"up_drv_{d_id}")
    
    with st.form("edit_driver_form"):
        col1, col2 = st.columns(2)
        f_name = col1.text_input("Имя", value=curr['Имя'])
        l_name = col2.text_input("Фамилия", value=curr['Фамилия'])
        phone = st.text_input("Телефон", value=curr['Телефон'])
        
        # Конвертация строки категорий обратно в список
        default_cats = curr['Категории'].split(", ") if isinstance(curr['Категории'], str) else []
        cats = st.multiselect("Категории", ["B", "C", "CE", "D"], default=default_cats)
        
        status_options = ["В штате", "На подработке", "Уволен"]
        current_status_idx = status_options.index(curr['Статус']) if curr['Статус'] in status_options else 0
        status = st.selectbox("Статус", status_options, index=current_status_idx)
        
        if st.form_submit_button("💾 СОХРАНИТЬ ИЗМЕНЕНИЯ", use_container_width=True):
            # Если загружено новое фото — обновляем, иначе оставляем старое
            if up_photo:
                df.at[idx, 'Фото'] = process_image(up_photo)
            
            df.at[idx, 'Имя'] = f_name
            df.at[idx, 'Фамилия'] = l_name
            df.at[idx, 'Телефон'] = phone
            df.at[idx, 'Статус'] = status
            df.at[idx, 'Категории'] = ", ".join(cats)
            
            st.session_state.drivers = df
            
            # ВАЖНО: Сбрасываем именно edit_modal
            st.session_state.active_edit_modal = None
            st.session_state.active_modal = None 
            st.success("Данные успешно обновлены!")
            time.sleep(1)
            st.rerun()
            
@st.dialog("🚛 Регистрация ТС", width="large")
def create_vehicle_modal():
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
            cap = r2_c1.number_input("Вес (кг)", value=1500)
            vol = r2_c2.number_input("Объем (м³)", value=12.0)
            pal = r2_c3.number_input("Паллеты", value=4)
            
            st.divider()
            r3_c1, r3_c2 = st.columns(2)
            l_to = r3_c1.date_input("Дата ТО", value=datetime.now())
            ins = r3_c2.date_input("Страховка до", value=datetime.now())
            
            r4_c1, r4_c2, r4_c3 = st.columns(3)
            curr_odo = r4_c1.number_input("Текущий пробег (км)", value=0)
            oil_limit = r4_c2.number_input("Ресурс масла (км)", value=10000)
            grm_limit = r4_c3.number_input("Ресурс ГРМ (км)", value=60000)

        submitted = st.form_submit_button("✅ ВНЕСТИ ТС В РЕЕСТР", use_container_width=True)

    if submitted:
        if not gov_num or not brand:
            st.error("Заполните госномер и марку!")
            return
        
        # Дефолтные иконки, если фото не загружено
        img_map = {
            "Тент": "https://cdn-icons-png.flaticon.com/512/3564/3564344.png", 
            "Рефрижератор": "https://cdn-icons-png.flaticon.com/512/3564/3564359.png",
            "Изотерм": "https://cdn-icons-png.flaticon.com/512/3564/3564344.png",
            "Бортовой": "https://cdn-icons-png.flaticon.com/512/2554/2554977.png"
        }
        final_v_photo = process_image(uploaded_v_photo) or img_map.get(v_type)

        new_v = {
            "id": f"VEH-{str(uuid.uuid4())[:4].upper()}", 
            "Марка": brand, "Госномер": gov_num, "Тип": v_type, 
            "Грузоподъемность": cap, "Объем": vol, "Паллеты": pal,
            "ТО": l_to.strftime("%Y-%m-%d"), "Страховка": ins.strftime("%Y-%m-%d"),
            "Фото": final_v_photo, "Статус": "На линии"
        }
        
        st.session_state.vehicles = pd.concat([st.session_state.vehicles, pd.DataFrame([new_v])], ignore_index=True)
        st.success(f"ТС {gov_num} добавлено!")
        
        # Чистим все флаги, чтобы диспетчер не запутался
        st.session_state.active_modal = None
        st.session_state.active_edit_modal = None
        time.sleep(1)
        st.rerun()

@st.dialog("⚙️ Редактирование ТС", width="large")
def edit_vehicle_modal():
    if not st.session_state.get("editing_id"):
        st.error("ID автомобиля не найден!")
        return

    v_id = st.session_state.editing_id
    df = st.session_state.vehicles
    
    matching = df.index[df['id'] == v_id].tolist()
    if not matching:
        st.error("Автомобиль не найден в базе!")
        return
        
    idx = matching[0]
    curr = df.loc[idx]

    st.subheader(f"Редактирование: {curr['Госномер']}")
    up_v_photo = st.file_uploader("📸 Обновить фото", type=["jpg", "png"], key=f"up_v_{v_id}")

    with st.form("edit_v_form"):
        c1, c2 = st.columns(2)
        brand = c1.text_input("Марка", value=curr['Марка'])
        v_types = ["Тент", "Рефрижератор", "Изотерм", "Бортовой"]
        v_type = c2.selectbox("Тип", v_types, index=v_types.index(curr['Тип']) if curr['Тип'] in v_types else 0)
        
        st.divider()
        r2_1, r2_2, r2_3 = st.columns(3)
        cap = r2_1.number_input("Грузоподъемность", value=int(curr['Грузоподъемность']))
        vol = r2_2.number_input("Объем", value=float(curr['Объем']))
        pal = r2_3.number_input("Паллеты", value=int(curr['Паллеты']))
        
        st.divider()
        # Поля дат (если они в DataFrame строками, нужно перевести в date)
        try:
            d_to = datetime.strptime(curr['ТО'], "%Y-%m-%d")
            d_ins = datetime.strptime(curr['Страховка'], "%Y-%m-%d")
        except:
            d_to = datetime.now()
            d_ins = datetime.now()

        r3_1, r3_2 = st.columns(2)
        new_to = r3_1.date_input("Дата ТО", value=d_to)
        new_ins = r3_2.date_input("Страховка до", value=d_ins)
        
        if st.form_submit_button("💾 СОХРАНИТЬ ИЗМЕНЕНИЯ", use_container_width=True):
            if up_v_photo:
                df.at[idx, 'Фото'] = process_image(up_v_photo)
            
            df.at[idx, 'Марка'] = brand
            df.at[idx, 'Тип'] = v_type
            df.at[idx, 'Грузоподъемность'] = cap
            df.at[idx, 'Объем'] = vol
            df.at[idx, 'Паллеты'] = pal
            df.at[idx, 'ТО'] = new_to.strftime("%Y-%m-%d")
            df.at[idx, 'Страховка'] = new_ins.strftime("%Y-%m-%d")
            
            st.session_state.vehicles = df
            # СБРАСЫВАЕМ ФЛАГИ
            st.session_state.active_edit_modal = None
            st.session_state.active_modal = None
            
            st.success("Данные ТС обновлены!")
            time.sleep(1)
            st.rerun()