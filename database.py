import streamlit as st
from supabase import create_client
import pandas as pd

@st.cache_resource
def get_supabase():
    # Проверь, чтобы в Secrets было [supabase] с url и key внутри
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

# Создаем объект подключения
supabase = get_supabase()

# --- ДОБАВЛЯЕМ НЕДОСТАЮЩИЕ ФУНКЦИИ ---

def insert_data(table_name, data_dict):
    """Добавление новой записи в любую таблицу Supabase"""
    try:
        res = supabase.table(table_name).insert(data_dict).execute()
        st.cache_data.clear() # Чистим кеш, чтобы данные сразу обновились в таблицах
        return res
    except Exception as e:
        st.error(f"Ошибка при вставке в {table_name}: {e}")
        return None

def load_data(table_name):
    """Загрузка всех данных из таблицы"""
    try:
        res = supabase.table(table_name).select("*").execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except Exception as e:
        st.error(f"Ошибка при загрузке {table_name}: {e}")
        return pd.DataFrame()
