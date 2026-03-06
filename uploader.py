import streamlit as st
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from streamlit_gsheets import GSheetsConnection
import io

# 1. Настройка подключения
# В Streamlit Cloud данные из JSON ключа кладутся в st.secrets
def get_gdrive_service():
    info = st.secrets["gcp_service_account"]
    creds = service_account.Credentials.from_service_account_info(info)
    return build('drive', 'v3', credentials=creds)

# 2. РАБОТА С ТЕКСТОМ (Google Sheets)
def load_data(worksheet_name):
    conn = st.connection("gsheets", type=GSheetsConnection)
    return conn.read(worksheet=worksheet_name)

def insert_row(worksheet_name, data_dict):
    conn = st.connection("gsheets", type=GSheetsConnection)
    existing_df = conn.read(worksheet=worksheet_name)
    new_df = pd.concat([existing_df, pd.DataFrame([data_dict])], ignore_index=True)
    conn.update(worksheet=worksheet_name, data=new_df)
    st.cache_data.clear()

# 3. РАБОТА С ФОТО (Google Drive)
def upload_to_drive(file_buffer, file_name, folder_id):
    service = get_gdrive_service()
    
    file_metadata = {'name': file_name, 'parents': [folder_id]}
    media = MediaIoBaseUpload(io.BytesIO(file_buffer.getvalue()), 
                              mimetype='image/jpeg', resumable=True)
    
    # Загрузка
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    file_id = file.get('id')
    
    # Разрешаем просмотр всем, у кого есть ссылка
    service.permissions().create(fileId=file_id, body={'type': 'anyone', 'role': 'viewer'}).execute()
    
    # Формируем прямую ссылку для Streamlit
    return f"https://drive.google.com/uc?id={file_id}"
