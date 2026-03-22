import streamlit as st
from supabase import create_client

# Подключение к Supabase
supabase = create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])

def login_form():
    # --- ULTRA PRO DESIGN: DARK GLASSMORPHISM ---
    st.markdown("""
        <style>
            /* 1. Скрываем абсолютно всё лишнее */
            [data-testid="stHeader"], [data-testid="stSidebar"], [data-testid="stFooter"], [data-testid="stDecoration"] {
                display: none !important;
            }

            /* 2. Фон: Глубокий темный градиент (не выжигает глаза) */
            .stApp {
                background: radial-gradient(circle at center, #1e293b 0%, #0f172a 100%) !important;
                height: 100vh !important;
                overflow: hidden !important;
            }

            /* 3. Центрирование контейнера */
            .main {
                display: flex !important;
                align-items: center !important;
                justify-content: center !important;
                height: 100vh !important;
            }

            /* Контейнер для фиксации "квадрата" */
            .stVerticalBlock {
                gap: 0px !important;
                display: flex;
                align-items: center;
                justify-content: center;
            }

            /* 4. Сам квадрат входа (Glass Box) */
            .login-card {
                background: rgba(15, 23, 42, 0.6) !important;
                backdrop-filter: blur(20px);
                -webkit-backdrop-filter: blur(20px);
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 20px;
                padding: 40px;
                width: 380px; /* Фиксированная ширина квадрата */
                box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5);
                text-align: center;
                margin: auto;
            }

            /* 5. Типографика */
            .brand-name {
                color: #f8fafc;
                font-family: 'Inter', sans-serif;
                font-size: 28px;
                font-weight: 800;
                letter-spacing: 2px;
                margin-bottom: 5px;
            }
            .brand-sub {
                color: #64748b;
                font-size: 11px;
                text-transform: uppercase;
                letter-spacing: 3px;
                margin-bottom: 30px;
            }

            /* 6. Инпуты: Темные, плоские, современные */
            .stTextInput input {
                background-color: rgba(255, 255, 255, 0.03) !important;
                border: 1px solid rgba(255, 255, 255, 0.1) !important;
                color: #f8fafc !important;
                border-radius: 10px !important;
                height: 45px !important;
            }
            
            /* Кнопка входа: Акцентный синий */
            .stButton>button {
                background-color: #3b82f6 !important;
                color: white !important;
                border: none !important;
                border-radius: 10px !important;
                height: 45px !important;
                font-weight: 700 !important;
                letter-spacing: 1px !important;
                margin-top: 10px !important;
                transition: 0.3s !important;
            }
            .stButton>button:hover {
                background-color: #2563eb !important;
                box-shadow: 0 0 15px rgba(59, 130, 246, 0.4) !important;
            }
        </style>
    """, unsafe_allow_html=True)

    # HTML Обертка
    st.markdown('<div class="login-card">', unsafe_allow_html=True)
    st.markdown('<div class="brand-name">IMPERIA</div>', unsafe_allow_html=True)
    st.markdown('<div class="brand-sub">WMS Terminal</div>', unsafe_allow_html=True)

    email = st.text_input("Login", placeholder="Email", label_visibility="collapsed")
    password = st.text_input("Password", type="password", placeholder="Password", label_visibility="collapsed")
    
    if st.button("SIGN IN", use_container_width=True):
        try:
            response = supabase.auth.sign_in_with_password({"email": email, "password": password})
            if response.user:
                st.session_state.user = response.user
                user_profile = supabase.table("profiles").select("*, companies(*)").eq("id", response.user.id).single().execute()
                st.session_state.user_data = user_profile.data
                st.rerun()
        except:
            st.error("Invalid Login or Password")

    # Ссылка на помощь
    if st.button("Support", use_container_width=True, help="Contact Administrator"):
        st.toast("Admin: +373 6803 1705")

    st.markdown('</div>', unsafe_allow_html=True)
