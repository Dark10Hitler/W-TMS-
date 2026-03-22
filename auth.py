import streamlit as st
from supabase import create_client

# Подключение к Supabase
supabase = create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])

# Подключаем шрифты и иконки Google
st.markdown("""
    <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap">
    <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,0,0" />
""", unsafe_allow_html=True)

@st.dialog("Контактная информация")
def show_support_modal():
    # Профессиональная карточка директора
    st.markdown("""
        <div style="text-align: center; margin-bottom: 20px;">
            <div style="font-size: 48px; color: #3b82f6; margin-bottom: 10px;">
                <span class="material-symbols-rounded" style="font-size: 64px;">account_circle</span>
            </div>
            <h2 style="margin:0; color: #f8fafc; font-weight: 700; font-family: 'Inter';">Денис Маслюк</h2>
            <p style="margin:0; color: #64748b; font-size: 13px; font-weight: 500; letter-spacing: 0.5px;">IT-ДИРЕКТОР / АРХИТЕКТОР СИСТЕМЫ</p>
        </div>
        
        <div style="background: #111827; border: 1px solid #1f2937; border-radius: 12px; padding: 20px; margin-bottom: 20px;">
            <div style="display: flex; align-items: center; margin-bottom: 15px;">
                <span class="material-symbols-rounded" style="color: #3b82f6; margin-right: 12px;">call</span>
                <div>
                    <div style="color: #64748b; font-size: 11px;">Телефон</div>
                    <div style="color: #f8fafc; font-weight: 600;">+373 6803 1705</div>
                </div>
            </div>
            <div style="display: flex; align-items: center;">
                <span class="material-symbols-rounded" style="color: #3b82f6; margin-right: 12px;">mail</span>
                <div>
                    <div style="color: #64748b; font-size: 11px;">Email</div>
                    <div style="color: #f8fafc; font-weight: 600;">denis2305den4ik@gmail.com</div>
                </div>
            </div>
        </div>
        
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
            <a href="https://wa.me/37368031705" target="_blank" style="text-decoration: none;">
                <div style="background: #075e54; color: white; padding: 12px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-weight: 600; font-size: 14px;">
                    <span class="material-symbols-rounded" style="margin-right: 8px; font-size: 20px;">chat</span> WhatsApp
                </div>
            </a>
            <a href="viber://chat?number=%2B37368031705" target="_blank" style="text-decoration: none;">
                <div style="background: #7360f2; color: white; padding: 12px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-weight: 600; font-size: 14px;">
                    <span class="material-symbols-rounded" style="margin-right: 8px; font-size: 20px;">forum</span> Viber
                </div>
            </a>
        </div>
    """, unsafe_allow_html=True)

def login_form():
    st.markdown("""
        <style>
            [data-testid="stHeader"], [data-testid="stSidebar"], [data-testid="stDecoration"] { display: none !important; }

            /* Строгий OLED-градиент */
            .stApp {
                background-color: #000000 !important;
                background-image: radial-gradient(circle at center, #111827 0%, #030712 100%) !important;
            }

            /* Идеальное центрирование */
            [data-testid="block-container"] {
                display: flex !important;
                align-items: center !important;
                justify-content: center !important;
                height: 100vh !important;
                padding: 0 !important;
            }

            /* Квадрат Odoo Enterprise */
            [data-testid="column"]:nth-of-type(2) {
                background: #0a0f18 !important;
                border: 1px solid #1e293b !important;
                border-radius: 16px !important;
                padding: 40px 40px !important;
                box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7) !important;
                max-width: 420px !important;
            }

            /* Инпуты с иконками */
            .stTextInput input {
                background-color: #030712 !important;
                color: #f8fafc !important;
                border: 1px solid #1e293b !important;
                border-radius: 8px !important;
                padding: 12px 16px !important;
                font-family: 'Inter', sans-serif;
            }
            .stTextInput input:focus {
                border-color: #3b82f6 !important;
                box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15) !important;
            }

            /* Кнопка Sign In */
            button[kind="primary"] {
                background-color: #2563eb !important;
                border-radius: 8px !important;
                font-weight: 600 !important;
                height: 46px !important;
                transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
            }
            button[kind="primary"]:hover {
                background-color: #1d4ed8 !important;
                transform: translateY(-1px);
            }

            /* Заголовок */
            .brand-h {
                color: #ffffff;
                font-size: 32px;
                font-weight: 800;
                font-family: 'Inter';
                text-align: center;
                letter-spacing: -1px;
                margin-bottom: 4px;
            }
            .brand-s {
                color: #475569;
                font-size: 11px;
                font-weight: 600;
                text-align: center;
                text-transform: uppercase;
                letter-spacing: 3px;
                margin-bottom: 32px;
            }
        </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.8, 1])

    with col2:
        st.markdown('<div class="brand-h">IMPERIA</div>', unsafe_allow_html=True)
        st.markdown('<div class="brand-s">WMS Terminal</div>', unsafe_allow_html=True)

        email = st.text_input("Login", placeholder="example@domain.com", label_visibility="collapsed")
        password = st.text_input("Password", type="password", placeholder="••••••••", label_visibility="collapsed")
        
        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)

        if st.button("Access System", use_container_width=True, type="primary"):
            try:
                response = supabase.auth.sign_in_with_password({"email": email, "password": password})
                if response.user:
                    st.session_state.user = response.user
                    user_profile = supabase.table("profiles").select("*, companies(*)").eq("id", response.user.id).single().execute()
                    st.session_state.user_data = user_profile.data
                    st.rerun()
            except:
                st.error("Authentication failed")

        if st.button("System Support", use_container_width=True):
            show_support_modal()
