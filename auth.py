import streamlit as st
from supabase import create_client

# Подключение к Supabase
supabase = create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])

# --- МОДАЛЬНОЕ ОКНО КОНТАКТОВ (ПОЯВЛЯЕТСЯ ПОВЕРХ САЙТА) ---
@st.dialog("Контактная информация")
def show_support_modal():
    # Профессиональная карточка директора
    st.markdown("""
        <div style="text-align: center; margin-bottom: 25px;">
            <h2 style="margin:0; color: #f8fafc; font-weight: 700; font-family: 'Inter', sans-serif;">Денис Маслюк</h2>
            <p style="margin:0; color: #3b82f6; font-size: 14px; letter-spacing: 1px; text-transform: uppercase;">IT-Директор / Архитектор системы</p>
        </div>
    """, unsafe_allow_html=True)

    # Две колонки для телефона и почты
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("<p style='color:#9ca3af; font-size:12px; margin-bottom:2px;'>Телефон</p>", unsafe_allow_html=True)
        st.markdown("**📞 +373 6803 1705**")
    with col2:
        st.markdown("<p style='color:#9ca3af; font-size:12px; margin-bottom:2px;'>Email</p>", unsafe_allow_html=True)
        st.markdown("**📧 denis2305den4ik@gmail.com**")

    st.markdown("<hr style='border-color: #374151; margin: 25px 0;'>", unsafe_allow_html=True)

    # Кнопки мессенджеров
    st.markdown("""
        <div style="display: flex; justify-content: center; gap: 15px; flex-wrap: wrap;">
            <a href="https://wa.me/37368031705" target="_blank" style="background-color: #25D366; color: white; padding: 10px 20px; border-radius: 8px; text-decoration: none; font-weight: 600; font-family: sans-serif; display: inline-block; width: 140px; text-align: center; transition: 0.2s; box-shadow: 0 4px 6px rgba(37, 211, 102, 0.2);">
                💬 WhatsApp
            </a>
            <a href="viber://chat?number=%2B37368031705" target="_blank" style="background-color: #7360F2; color: white; padding: 10px 20px; border-radius: 8px; text-decoration: none; font-weight: 600; font-family: sans-serif; display: inline-block; width: 140px; text-align: center; transition: 0.2s; box-shadow: 0 4px 6px rgba(115, 96, 242, 0.2);">
                🟣 Viber
            </a>
        </div>
    """, unsafe_allow_html=True)

# --- ОСНОВНАЯ ФОРМА ВХОДА ---
def login_form():
    st.markdown("""
        <style>
            /* 1. Скрываем всё лишнее */
            [data-testid="stHeader"], [data-testid="stSidebar"], [data-testid="stDecoration"] { display: none !important; }

            /* 2. Идеально черный фон (OLED) */
            .stApp {
                background-color: #000000 !important;
                background-image: radial-gradient(circle at 50% 0%, #111827 0%, #000000 70%) !important;
            }

            /* 3. Опускаем весь блок ниже к центру экрана */
            [data-testid="block-container"] {
                padding-top: 15vh !important; 
            }

            /* 4. Квадрат входа (Premium Dark) */
            [data-testid="column"]:nth-of-type(2) {
                background-color: #0f1115 !important;
                border: 1px solid #272e3a !important;
                border-radius: 14px !important;
                padding: 45px 35px !important;
                box-shadow: 0 25px 50px -12px rgba(0,0,0,1) !important;
            }

            /* 5. Инпуты */
            .stTextInput input {
                background-color: #171c24 !important;
                color: #f9fafb !important;
                border: 1px solid #374151 !important;
                border-radius: 8px !important;
                padding: 14px !important;
                font-size: 15px !important;
                transition: all 0.2s ease;
            }
            .stTextInput input:focus {
                border-color: #3b82f6 !important;
                box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2) !important;
            }

            /* 6. Кнопка логина (Синяя) */
            .stButton > button[kind="primary"] {
                background-color: #2563eb !important;
                color: white !important;
                border: none !important;
                border-radius: 8px !important;
                height: 48px !important;
                font-weight: 600 !important;
                letter-spacing: 0.5px !important;
                width: 100% !important;
                margin-top: 20px !important;
                transition: 0.2s !important;
            }
            .stButton > button[kind="primary"]:hover {
                background-color: #1d4ed8 !important;
                box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3) !important;
            }

            /* 7. Кнопка Support (Прозрачная с бордером) */
            .stButton > button[kind="secondary"] {
                background-color: transparent !important;
                color: #9ca3af !important;
                border: 1px solid #374151 !important;
                border-radius: 8px !important;
                height: 44px !important;
                width: 100% !important;
                margin-top: 5px !important;
                transition: 0.2s !important;
            }
            .stButton > button[kind="secondary"]:hover {
                color: #f3f4f6 !important;
                border-color: #6b7280 !important;
                background-color: rgba(255,255,255,0.02) !important;
            }

            /* Типографика */
            .login-title {
                color: #ffffff;
                text-align: center;
                font-size: 28px;
                font-weight: 800;
                font-family: 'Inter', system-ui, sans-serif;
                margin-bottom: -5px;
                letter-spacing: -0.5px;
            }
            .login-subtitle {
                color: #6b7280;
                text-align: center;
                font-size: 12px;
                text-transform: uppercase;
                letter-spacing: 2px;
                margin-bottom: 30px;
            }
        </style>
    """, unsafe_allow_html=True)

    # --- СТРУКТУРА КОЛОНОК ---
    col1, col2, col3 = st.columns([1, 1.2, 1])

    with col2:
        st.markdown('<div class="login-title">IMPERIA</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-subtitle">WMS Terminal</div>', unsafe_allow_html=True)

        email = st.text_input("Email", placeholder="Email address", label_visibility="collapsed")
        password = st.text_input("Password", type="password", placeholder="Password", label_visibility="collapsed")
        
        # Кнопка входа
        if st.button("Sign In", use_container_width=True, type="primary"):
            try:
                response = supabase.auth.sign_in_with_password({"email": email, "password": password})
                if response.user:
                    st.session_state.user = response.user
                    user_profile = supabase.table("profiles").select("*, companies(*)").eq("id", response.user.id).single().execute()
                    st.session_state.user_data = user_profile.data
                    st.rerun()
            except Exception as e:
                st.error("Invalid credentials. Please try again.")

        # Кнопка поддержки открывает модальное окно
        if st.button("Support", use_container_width=True):
            show_support_modal()
