import streamlit as st
from supabase import create_client

# Подключение к Supabase (используем твою структуру секретов)
supabase = create_client(
    st.secrets["supabase"]["url"], 
    st.secrets["supabase"]["key"]
)

def login_form():
    # --- СУПЕР ДИЗАЙН: ГРАДИЕНТ И СТЕКЛО ---
    st.markdown("""
        <style>
            /* Скрываем всё лишнее */
            [data-testid="stHeader"], [data-testid="stSidebar"], [data-testid="stFooter"] { visibility: hidden !important; }
            
            /* Анимированный футуристичный фон */
            .stApp {
                background: linear-gradient(-45deg, #020617, #0f172a, #1e293b, #020617) !important;
                background-size: 400% 400% !important;
                animation: gradient 10s ease infinite !important;
                height: 100vh !important;
            }

            @keyframes gradient {
                0% { background-position: 0% 50%; }
                50% { background-position: 100% 50%; }
                100% { background-position: 0% 50%; }
            }

            /* Контейнер-центрировщик */
            .main-login-wrapper {
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                height: 85vh;
                width: 100%;
            }

            /* Стеклянная карточка (Glassmorphism) */
            .login-card {
                background: rgba(255, 255, 255, 0.03) !important;
                backdrop-filter: blur(25px) !important;
                -webkit-backdrop-filter: blur(25px) !important;
                border: 1px solid rgba(255, 255, 255, 0.1) !important;
                border-radius: 30px !important;
                padding: 50px 40px !important;
                width: 100%;
                max-width: 400px;
                box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7);
                text-align: center;
            }

            /* Заголовок системы */
            .title-text {
                color: white !important;
                font-size: 34px !important;
                font-weight: 800 !important;
                letter-spacing: -1.5px !important;
                margin-bottom: 5px !important;
                font-family: 'Inter', sans-serif;
            }
            .subtitle-text {
                color: #64748b !important;
                font-size: 13px !important;
                text-transform: uppercase;
                letter-spacing: 2px !important;
                margin-bottom: 35px !important;
            }

            /* Кастомизация инпутов под темную тему */
            .stTextInput input {
                background-color: rgba(0, 0, 0, 0.3) !important;
                border: 1px solid rgba(255, 255, 255, 0.1) !important;
                color: white !important;
                border-radius: 12px !important;
                padding: 10px !important;
            }

            /* Убираем белые рамки вокруг инпутов при фокусе */
            .stTextInput input:focus {
                border-color: #3b82f6 !important;
                box-shadow: 0 0 0 1px #3b82f6 !important;
            }
        </style>
    """, unsafe_allow_html=True)

    # Отрисовка структуры
    st.markdown('<div class="main-login-wrapper">', unsafe_allow_html=True)
    st.markdown('<div class="login-card">', unsafe_allow_html=True)
    
    st.markdown('<p class="title-text">IMPERIA</p>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle-text">Management System</p>', unsafe_allow_html=True)

    # Используем label_visibility="collapsed" чтобы убрать лишний текст над полями
    email = st.text_input("Email", placeholder="Login / Email", label_visibility="collapsed")
    password = st.text_input("Password", type="password", placeholder="Password", label_visibility="collapsed")
    
    st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)

    # Кнопка входа (Primary)
    if st.button("SIGN IN", use_container_width=True, type="primary"):
        try:
            response = supabase.auth.sign_in_with_password({"email": email, "password": password})
            if response.user:
                st.session_state.user = response.user
                # Загружаем данные профиля и компании
                user_profile = supabase.table("profiles").select("*, companies(*)").eq("id", response.user.id).single().execute()
                st.session_state.user_data = user_profile.data
                st.rerun()
        except Exception as e:
            st.error("Access Denied: Invalid credentials")

    # Вспомогательная кнопка (Minimal)
    if st.button("Forgot Password?", help="Contact IT Director", use_container_width=True):
        st.toast("📞 +373 6803 1705 \n 📧 denis2305den4ik@gmail.com", icon="ℹ️")

    st.markdown('</div>', unsafe_allow_html=True) # Закрываем card
    st.markdown('</div>', unsafe_allow_html=True) # Закрываем wrapper
