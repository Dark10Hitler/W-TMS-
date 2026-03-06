import cloudinary
import cloudinary.uploader
import streamlit as st

# Автоматическая настройка через секреты
cloudinary.config(
    cloud_name = st.secrets["CLOUDINARY_CLOUD_NAME"],
    api_key = st.secrets["CLOUDINARY_API_KEY"],
    api_secret = st.secrets["CLOUDINARY_API_SECRET"],
    secure = True
)

def upload_to_cloudinary(file, folder_name="warehouse"):
    """
    Загружает файл в Cloudinary и возвращает ссылку.
    folder_name — это папка внутри Cloudinary (например, 'arrivals' или 'defects')
    """
    try:
        upload_result = cloudinary.uploader.upload(
            file, 
            folder=f"logistics/{folder_name}",
            # Оптимизация на лету:
            quality="auto", 
            fetch_format="auto"
        )
        # Возвращаем защищенную ссылку на фото
        return upload_result['secure_url']
    except Exception as e:
        st.error(f"Ошибка Cloudinary: {e}")
        return None
