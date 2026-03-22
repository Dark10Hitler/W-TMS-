import streamlit as st
from supabase import create_client

# Подключение к Supabase
supabase = create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])

def login_form():
    # --- СТРОГИЙ CSS: OLED DARK & ODOO STYLE ---
    st.markdown("""
        <style>
            /* 1. Скрываем всё лишнее (хедеры, сайдбары) */
            [data-testid="stHeader"], [data-testid="stSidebar"], [data-testid="stDecoration"] {
                display: none !important;
            }

            /* 2. Глубокий OLED-фон приложения */
            .stApp {
                background-color: #000000 !important; /* Идеально черный */
                background-image: radial-gradient(circle at 50% 0%, #111827 0%, #000000 80%) !important;
            }

            /* 3. МАГИЯ: Превращаем центральную колонку в КВАДРАТ ВХОДА */
            /* Находим вторую колонку (col2) и стилизуем её как карточку */
            [data-testid="column"]:nth-of-type(2) {
                background-color: #0f1115 !important; /* Темно-серый квадрат */
                border: 1px solid #1f2937 !important; /* Тонкая строгая рамка */
                border-radius: 12px !important;
                padding: 40px 30px !important;
                box-shadow: 0 20px 40px rgba(0,0,0,0.8) !important;
                margin-top: 15vh !important; /* Сдвигаем вниз к центру экрана */
            }

            /* 4. Инпуты: стиль Odoo (компактные, чистые) */
            .stTextInput input {
                background-color: #1f2937 !important;
                color: #f9fafb !important;
                border: 1px solid #374151 !important;
                border-radius: 6px !important;
                padding: 12px !important;
                font-size: 14px !important;
            }
            .stTextInput input:focus {
                border-color: #3b82f6 !important;
                box-shadow: 0 0 0 1px #3b82f6 !important;
            }

            /* 5. Кнопка "Войти" (Главная) */
            .stButton > button[kind="primary"] {
                background-color: #2563eb !important; /* Классический синий Odoo */
                color: white !important;
                border: none !important;
                border-radius: 6px !important;
                height: 44px !important;
                font-weight: 600 !important;
                width: 100% !important;
                margin-top: 15px !important;
                transition: 0.2s !important;
            }
            .stButton > button[kind="primary"]:hover {
                background-color: #1d4ed8 !important;
            }

            /* 6. Кнопка "Support" (Вторичная) */
            .stButton > button[kind="secondary"] {
                background-color: transparent !important;
                color: #9ca3af !important;
                border: 1px solid #374151 !important;
                border-radius: 6px !important;
                width: 100% !important;
                margin-top: 5px !important;
            }
            .stButton > button[kind="secondary"]:hover {
                color: #f3f4f6 !important;
                border-color: #4b5563 !important;
            }

            /* Типографика карточки */
            .login-title {
                color: #ffffff;
                text-align: center;
                font-size: 26px;
                font-weight: 700;
                font-family: 'Inter', sans-serif;
                margin-bottom: 0px;
            }
            .login-subtitle {
                color: #6b7280;
                text-align: center;
                font-size: 13px;
                text-transform: uppercase;
                letter-spacing: 1.5px;
                margin-bottom: 25px;
            }
        </style>
    """, unsafe_allow_html=True)

    # --- СТРУКТУРА: 3 КОЛОНКИ ДЛЯ ЦЕНТРИРОВАНИЯ ---
    # col1 (пусто) | col2 (наш квадрат) | col3 (пусто)
    col1, col2, col3 = st.columns([1, 1.2, 1])

    # Весь контент кладем строго во вторую колонку!
    with col2:
        st.markdown('<div class="login-title">IMPERIA</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-subtitle">WMS Terminal</div>', unsafe_allow_html=True)

        email = st.text_input("Email", placeholder="Email", label_visibility="collapsed")
        password = st.text_input("Password", type="password", placeholder="Password", label_visibility="collapsed")
        
        # type="primary" связывает кнопку с синим цветом в CSS
        if st.button("Log in", use_container_width=True, type="primary"):
            try:
                response = supabase.auth.sign_in_with_password({"email": email, "password": password})
                if response.user:
                    st.session_state.user = response.user
                    user_profile = supabase.table("profiles").select("*, companies(*)").eq("id", response.user.id).single().execute()
                    st.session_state.user_data = user_profile.data
                    st.rerun()
            except Exception as e:
                st.error("Invalid credentials")

        # Вторая кнопка
        if st.button("Support", use_container_width=True):
            st.toast("Admin: +373 6803 1705")
