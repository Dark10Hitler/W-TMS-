import sqlite3
import pandas as pd

DB_PATH = "imperia_data.db"

def get_connection():
    # check_same_thread=False нужен, чтобы Streamlit не ругался
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def select_all(table_name):
    """Замена для: supabase.table('...').select('*').execute()"""
    conn = get_connection()
    try:
        # Читаем таблицу и превращаем в список словарей (как было в Supabase)
        df = pd.read_sql(f"SELECT * FROM {table_name}", conn)
        result = df.to_dict(orient='records')
    except Exception as e:
        print(f"Ошибка чтения {table_name}: {e}")
        result = []
    conn.close()
    return result

def insert_data(table_name, data):
    """Замена для: supabase.table('...').insert(data).execute()"""
    conn = get_connection()
    # Превращаем словарь/список словарей в таблицу и дописываем в конец (append)
    df = pd.DataFrame([data] if isinstance(data, dict) else data)
    df.to_sql(table_name, conn, if_exists='append', index=False)
    conn.close()

def update_data(table_name, data_to_update, match_column, match_value):
    """Замена для: supabase.table('...').update(data).eq('id', id).execute()"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Формируем запрос UPDATE
    set_clause = ", ".join([f"{key} = ?" for key in data_to_update.keys()])
    values = list(data_to_update.values())
    values.append(match_value)
    
    query = f"UPDATE {table_name} SET {set_clause} WHERE {match_column} = ?"
    cursor.execute(query, values)
    conn.commit()
    conn.close()

def delete_data(table_name, match_column, match_value):
    """Замена для: supabase.table('...').delete().eq('id', id).execute()"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"DELETE FROM {table_name} WHERE {match_column} = ?", (match_value,))
    conn.commit()
    conn.close()
