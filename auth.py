import streamlit as st
from supabase import create_client

# Подключение к Supabase
supabase = create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])

@st.dialog("Контактная информация")
def show_support_modal():
    html_code = """
    <div style="text-align: center; margin-bottom: 20px;">
        <div style="font-size: 48px; color: #3b82f6; margin-bottom: 10px;">👤</div>
        <h2 style="margin:0; color: #f8fafc; font-weight: 700;">Денис Маслюк</h2>
        <p style="margin:0; color: #64748b; font-size: 13px; font-weight: 500; letter-spacing: 0.5px;">IT-ДИРЕКТОР / АРХИТЕКТОР СИСТЕМЫ</p>
    </div>

    <div style="background: rgba(128,128,128,0.05); border: 1px solid rgba(128,128,128,0.1); border-radius: 12px; padding: 18px; margin-bottom: 20px; text-align: left;">
        <div style="margin-bottom: 12px;">
            <span style="color: #64748b; font-size: 10px; font-weight: 700; display: block; margin-bottom: 2px;">CONTACT PHONE</span>
            <span style="font-size: 15px; font-weight: 600;">+373 6803 1705</span>
        </div>
        <div>
            <span style="color: #64748b; font-size: 10px; font-weight: 700; display: block; margin-bottom: 2px;">BUSINESS EMAIL</span>
            <span style="font-size: 14px; font-weight: 600;">denis2305den4ik@gmail.com</span>
        </div>
    </div>

    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
        <a href="https://wa.me/37368031705" target="_blank" style="text-decoration:none;">
            <div style="background:#25D366; color:white; padding:12px; border-radius:8px; display:flex; align-items:center; justify-content:center; font-weight:700; font-size:14px;">
                <svg style="width:18px;height:18px;fill:white;margin-right:10px" viewBox="0 0 448 512"><path d="M380.9 97.1C339 55.1 283.2 32 223.9 32c-122.4 0-222 99.6-222 222 0 39.1 10.2 77.3 29.6 111L0 480l117.7-30.9c32.4 17.7 68.9 27 106.1 27h.1c122.3 0 224.1-99.6 224.1-222 0-59.3-25.2-115-67.1-157zm-157 341.6c-33.2 0-65.7-8.9-94-25.7l-6.7-4-69.8 18.3L72 359.2l-4.4-7c-18.5-29.4-28.2-63.3-28.2-98.2 0-101.7 82.8-184.5 184.6-184.5 49.3 0 95.6 19.2 130.4 54.1 34.8 34.9 56.2 81.2 56.1 130.5 0 101.8-84.9 184.6-186.6 184.6zm101.2-138.2c-5.5-2.8-32.8-16.2-37.9-18-5.1-1.9-8.8-2.8-12.5 2.8-3.7 5.6-14.3 18-17.6 21.8-3.2 3.7-6.5 4.2-12 1.4-5.5-2.8-23.1-8.5-44-27.1-16.2-14.5-27.2-32.4-30.3-37.9-3.2-5.5-.3-8.5 2.5-11.2 2.5-2.5 5.5-6.5 8.3-9.7 2.8-3.3 3.7-5.6 5.6-9.3 1.8-3.7.9-6.9-.5-9.7-1.4-2.8-12.5-30.1-17.1-41.2-4.5-10.8-9.1-9.3-12.5-9.5-3.2-.2-6.9-.2-10.6-.2-3.7 0-9.7 1.4-14.8 6.9-5.1 5.6-19.4 19-19.4 46.3 0 27.3 19.9 53.7 22.6 57.4 2.8 3.7 39.1 59.7 94.8 83.8 13.2 5.8 23.5 9.2 31.5 11.8 13.3 4.2 25.4 3.6 35 2.2 10.7-1.5 32.8-13.4 37.4-26.4 4.6-13 4.6-24.1 3.2-26.4-1.3-2.5-5-3.9-10.5-6.6z"/></svg> WhatsApp
            </div>
        </a>
        <a href="viber://chat?number=%2B37368031705" target="_blank" style="text-decoration:none;">
            <div style="background:#7360f2; color:white; padding:12px; border-radius:8px; display:flex; align-items:center; justify-content:center; font-weight:700; font-size:14px;">
                <svg style="width:18px;height:18px;fill:white;margin-right:10px" viewBox="0 0 512 512"><path d="M444 49.9C431.3 38.2 379.9 0 265.3 0 145.3 0 62.6 47.7 44.2 64.2c-35.7 32.1-46.6 73.8-44.1 123.9 2.5 50.1 23.3 133 73 174.9l-4.7 66.3c-1.3 17.6 15 29.9 29.8 23L192 404c27.1 7.2 55.4 11.2 84.7 11.2 144 0 235.3-77.1 235.3-207.2-.1-83.9-34.7-133.2-68-158.1zm-32.3 273.7c-14.7 30.6-67.6 62.6-93.5 62.6-20.3 0-82.3-56.1-137.9-111.7S68.6 172.1 68.6 151.8c0-25.9 32-78.8 62.6-93.5 13.9-6.6 28.9-3.4 36.3 8.3l30.9 49c6.6 10.4 4.6 24.1-4.6 32.1l-24.5 21.3c-6.1 5.3-7.5 14.1-3.3 21 21.5 35.1 50.7 64.3 85.8 85.8 6.9 4.2 15.7 2.8 21-3.3l21.3-24.5c8-9.2 21.7-11.1 32.1-4.6l49 30.9c11.7 7.4 14.9 22.4 8.3 36.3z"/></svg> Viber
            </div>
        </a>
    </div>
    """
    # САМАЯ ВАЖНАЯ СТРОЧКА:
    st.markdown(html_code, unsafe_allow_html=True)
    
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
