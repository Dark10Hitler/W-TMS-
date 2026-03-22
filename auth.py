import streamlit as st
from supabase import create_client

supabase = create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])

# --- SVG ИКОНКИ ДЛЯ ПРОФЕССИОНАЛЬНОГО ВИДА ---
WHATSAPP_SVG = '<svg style="width:20px;height:20px;margin-right:8px;" viewBox="0 0 448 512" fill="white"><path d="M380.9 97.1C339 55.1 283.2 32 223.9 32c-122.4 0-222 99.6-222 222 0 39.1 10.2 77.3 29.6 111L0 480l117.7-30.9c32.4 17.7 68.9 27 106.1 27h.1c122.3 0 224.1-99.6 224.1-222 0-59.3-25.2-115-67.1-157zm-157 341.6c-33.2 0-65.7-8.9-94-25.7l-6.7-4-69.8 18.3L72 359.2l-4.4-7c-18.5-29.4-28.2-63.3-28.2-98.2 0-101.7 82.8-184.5 184.6-184.5 49.3 0 95.6 19.2 130.4 54.1 34.8 34.9 56.2 81.2 56.1 130.5 0 101.8-84.9 184.6-186.6 184.6zm101.2-138.2c-5.5-2.8-32.8-16.2-37.9-18-5.1-1.9-8.8-2.8-12.5 2.8-3.7 5.6-14.3 18-17.6 21.8-3.2 3.7-6.5 4.2-12 1.4-5.5-2.8-23.1-8.5-44-27.1-16.2-14.5-27.2-32.4-30.3-37.9-3.2-5.5-.3-8.5 2.5-11.2 2.5-2.5 5.5-6.5 8.3-9.7 2.8-3.3 3.7-5.6 5.6-9.3 1.8-3.7.9-6.9-.5-9.7-1.4-2.8-12.5-30.1-17.1-41.2-4.5-10.8-9.1-9.3-12.5-9.5-3.2-.2-6.9-.2-10.6-.2-3.7 0-9.7 1.4-14.8 6.9-5.1 5.6-19.4 19-19.4 46.3 0 27.3 19.9 53.7 22.6 57.4 2.8 3.7 39.1 59.7 94.8 83.8 13.2 5.8 23.5 9.2 31.5 11.8 13.3 4.2 25.4 3.6 35 2.2 10.7-1.5 32.8-13.4 37.4-26.4 4.6-13 4.6-24.1 3.2-26.4-1.3-2.5-5-3.9-10.5-6.6z"/></svg>'
VIBER_SVG = '<svg style="width:20px;height:20px;margin-right:8px;" viewBox="0 0 512 512" fill="white"><path d="M444 49.9C431.3 38.2 379.9 0 265.3 0 145.3 0 62.6 47.7 44.2 64.2c-35.7 32.1-46.6 73.8-44.1 123.9 2.5 50.1 23.3 133 73 174.9l-4.7 66.3c-1.3 17.6 15 29.9 29.8 23L192 404c27.1 7.2 55.4 11.2 84.7 11.2 144 0 235.3-77.1 235.3-207.2-.1-83.9-34.7-133.2-68-158.1zm-32.3 273.7c-14.7 30.6-67.6 62.6-93.5 62.6-20.3 0-82.3-56.1-137.9-111.7S68.6 172.1 68.6 151.8c0-25.9 32-78.8 62.6-93.5 13.9-6.6 28.9-3.4 36.3 8.3l30.9 49c6.6 10.4 4.6 24.1-4.6 32.1l-24.5 21.3c-6.1 5.3-7.5 14.1-3.3 21 21.5 35.1 50.7 64.3 85.8 85.8 6.9 4.2 15.7 2.8 21-3.3l21.3-24.5c8-9.2 21.7-11.1 32.1-4.6l49 30.9c11.7 7.4 14.9 22.4 8.3 36.3z"/></svg>'

@st.dialog("System Support")
def show_support_modal():
    st.markdown(f"""
        <div style="text-align: center; font-family: 'Inter', sans-serif;">
            <h3 style="margin-bottom: 5px; font-weight: 700;">Denis Masliuc</h3>
            <p style="color: #64748b; font-size: 13px; margin-bottom: 25px;">IT Director • System Architect</p>
            
            <div style="text-align: left; background: rgba(128,128,128,0.05); border-radius: 12px; padding: 15px; margin-bottom: 20px;">
                <div style="margin-bottom: 10px; display: flex; align-items: center; gap: 10px;">
                    <span style="font-size: 18px;">📞</span> <b>+373 6803 1705</b>
                </div>
                <div style="display: flex; align-items: center; gap: 10px;">
                    <span style="font-size: 18px;">✉️</span> <b>denis2305den4ik@gmail.com</b>
                </div>
            </div>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                <a href="https://wa.me/37368031705" target="_blank" style="text-decoration:none;">
                    <div style="background:#25D366; color:white; padding:12px; border-radius:8px; display:flex; align-items:center; justify-content:center; font-weight:600;">
                        {WHATSAPP_SVG} WhatsApp
                    </div>
                </a>
                <a href="viber://chat?number=%2B37368031705" target="_blank" style="text-decoration:none;">
                    <div style="background:#7360F2; color:white; padding:12px; border-radius:8px; display:flex; align-items:center; justify-content:center; font-weight:600;">
                        {VIBER_SVG} Viber
                    </div>
                </a>
            </div>
        </div>
    """, unsafe_allow_html=True)

def login_form():
    # Определение темы для 2-х режимов
    theme_css = """
        :root {
            --bg-color: #f8fafc;
            --card-bg: #ffffff;
            --text-main: #0f172a;
            --input-bg: #ffffff;
            --border: #e2e8f0;
        }
        @media (prefers-color-scheme: dark) {
            :root {
                --bg-color: #020617;
                --card-bg: #0f172a;
                --text-main: #f8fafc;
                --input-bg: #020617;
                --border: #1e293b;
            }
        }
    """

    st.markdown(f"""
        <style>
            {theme_css}
            [data-testid="stHeader"], [data-testid="stSidebar"], [data-testid="stDecoration"] {{ display: none !important; }}
            
            .stApp {{
                background: var(--bg-color) !important;
                background-image: radial-gradient(circle at center, rgba(59,130,246,0.05) 0%, transparent 100%) !important;
            }}

            [data-testid="block-container"] {{
                display: flex !important;
                align-items: center !important;
                justify-content: center !important;
                height: 100vh !important;
                padding-top: 0 !important;
            }}

            [data-testid="column"]:nth-of-type(2) {{
                background: var(--card-bg) !important;
                border: 1px solid var(--border) !important;
                border-radius: 20px !important;
                padding: 45px !important;
                box-shadow: 0 25px 50px -12px rgba(0,0,0,0.2) !important;
                width: 420px !important;
            }}

            .stTextInput input {{
                background: var(--input-bg) !important;
                color: var(--text-main) !important;
                border: 1px solid var(--border) !important;
                border-radius: 10px !important;
                height: 48px !important;
            }}

            button[kind="primary"] {{
                background: #2563eb !important;
                border-radius: 10px !important;
                height: 50px !important;
                font-weight: 700 !important;
                margin-top: 15px !important;
            }}

            .brand-logo {{
                text-align: center;
                font-family: 'Inter', sans-serif;
                margin-bottom: 30px;
            }}
            .brand-logo h1 {{ color: var(--text-main); font-size: 30px; font-weight: 800; margin:0; letter-spacing:-1px; }}
            .brand-logo p {{ color: #64748b; font-size: 12px; text-transform: uppercase; letter-spacing: 2px; }}
        </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown('<div class="brand-logo"><h1>IMPERIA</h1><p>WMS Terminal</p></div>', unsafe_allow_html=True)
        
        email = st.text_input("Login", placeholder="Email", label_visibility="collapsed")
        password = st.text_input("Password", type="password", placeholder="Password", label_visibility="collapsed")
        
        if st.button("Sign In", use_container_width=True, type="primary"):
            try:
                response = supabase.auth.sign_in_with_password({"email": email, "password": password})
                if response.user:
                    st.session_state.user = response.user
                    user_profile = supabase.table("profiles").select("*, companies(*)").eq("id", response.user.id).single().execute()
                    st.session_state.user_data = user_profile.data
                    st.rerun()
            except:
                st.error("Access denied")

        if st.button("Support", use_container_width=True):
            show_support_modal()
