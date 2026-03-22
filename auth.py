import streamlit as st
from supabase import create_client

# Подключение к Supabase (берем из секретов)
supabase = create_client(st.secrets["url"], st.secrets["key"])

def login_form():
    st.title("🔒 IMPERIA WMS")
    st.subheader("Вход в систему управления")

    email = st.text_input("Электронная почта")
    password = st.text_input("Пароль", type="password")

    if st.button("Войти"):
        try:
            # Пытаемся авторизоваться в Supabase
            response = supabase.auth.sign_in_with_password({"email": email, "password": password})
            
            if response.user:
                st.session_state.user = response.user
                # Загружаем профиль и тумблеры компании
                user_profile = supabase.table("profiles").select("*, companies(*)").eq("id", response.user.id).single().execute()
                st.session_state.user_data = user_profile.data
                st.rerun() # Перезагружаем, чтобы войти в систему
        except Exception as e:
            st.error("Ошибка входа: проверьте почту и пароль")

    # Твоя идея с кнопкой "Забыл пароль"
    if st.button("Забыли пароль?", help="Свяжитесь с администратором"):
        st.info(f"Для восстановления доступа свяжитесь с IT-директором: \n\n 📞 +373 6803 1705 \n 📧 denis2305den4ik@gmail.com")
