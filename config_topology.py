
import json
from supabase import create_client, Client

url = "https://grdyokwemanzcpmfvhps.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdyZHlva3dlbWFuemNwbWZ2aHBzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzM0OTg0NTMsImV4cCI6MjA4OTA3NDQ1M30.CL_UETOVA-Fw1b4vJc_rQUUiuE44cWD2qDYWPog4S0w"
supabase: Client = create_client(url, key)

def migrate_warehouses():
    # Собираем все данные из твоего кода в один массив
    topology_data = [
        # СКЛАД 28
        {"wh_id": "28", "prefix": "BULK_ENTRANCE", "x_start": 2, "y_start": 2, "rows_count": 2, "slots_count": 2, "color": "lightgrey", "tiers_config": 1, "orientation": "H", "is_box": True},
        {"wh_id": "28", "prefix": "LW", "x_start": 0, "y_start": 8, "rows_count": 1, "slots_count": 10, "color": "lightblue", "tiers_config": [4, 3, 3, 3, 4], "orientation": "V", "is_box": False},
        {"wh_id": "28", "prefix": "CT1", "x_start": 5, "y_start": 10, "rows_count": 1, "slots_count": 4, "color": "royalblue", "tiers_config": 3, "orientation": "V", "is_box": False},
        {"wh_id": "28", "prefix": "BUFFER", "x_start": 5, "y_start": 15, "rows_count": 2, "slots_count": 2, "color": "lightgrey", "tiers_config": 2, "orientation": "H", "is_box": True},
        {"wh_id": "28", "prefix": "CT2", "x_start": 7.5, "y_start": 10, "rows_count": 1, "slots_count": 4, "color": "royalblue", "tiers_config": 4, "orientation": "V", "is_box": False},
        {"wh_id": "28", "prefix": "CT3", "x_start": 10, "y_start": 10, "rows_count": 1, "slots_count": 8, "color": "royalblue", "tiers_config": 3, "orientation": "V", "is_box": False},
        {"wh_id": "28", "prefix": "CT4", "x_start": 12, "y_start": 10, "rows_count": 1, "slots_count": 8, "color": "royalblue", "tiers_config": 3, "orientation": "V", "is_box": False},
        {"wh_id": "28", "prefix": "BC", "x_start": 5, "y_start": 17, "rows_count": 1, "slots_count": 4, "color": "violet", "tiers_config": 4, "orientation": "H", "is_box": False},
        {"wh_id": "28", "prefix": "OC1", "x_start": 15, "y_start": 10, "rows_count": 1, "slots_count": 8, "color": "green", "tiers_config": 3, "orientation": "V", "is_box": False},
        {"wh_id": "28", "prefix": "RW", "x_start": 18, "y_start": 5, "rows_count": 1, "slots_count": 12, "color": "red", "tiers_config": [3, 3, 3, 3, 5, 3], "orientation": "V", "is_box": False},
        {"wh_id": "28", "prefix": "BW", "x_start": 10, "y_start": 22, "rows_count": 1, "slots_count": 8, "color": "orange", "tiers_config": 3, "orientation": "H", "is_box": False},
        {"wh_id": "28", "prefix": "BW_L", "x_start": 2, "y_start": 22, "rows_count": 1, "slots_count": 4, "color": "black", "tiers_config": 3, "orientation": "H", "is_box": False},
        {"wh_id": "28", "prefix": "FH1", "x_start": 10, "y_start": 0, "rows_count": 1, "slots_count": 8, "color": "grey", "tiers_config": 3, "orientation": "H", "is_box": False},
        {"wh_id": "28", "prefix": "FH2", "x_start": 14, "y_start": 2, "rows_count": 1, "slots_count": 4, "color": "darkgrey", "tiers_config": 3, "orientation": "H", "is_box": False},
        {"wh_id": "28", "prefix": "BULK_FIN", "x_start": 10, "y_start": 2, "rows_count": 1, "slots_count": 2, "color": "lightgrey", "tiers_config": 2, "orientation": "H", "is_box": True},

        # СКЛАД 27
        {"wh_id": "27", "prefix": "BACK", "x_start": 0, "y_start": 20, "rows_count": 1, "slots_count": 8, "color": "orange", "tiers_config": 3, "orientation": "H", "is_box": False},
        {"wh_id": "27", "prefix": "LEFT", "x_start": 0, "y_start": 2, "rows_count": 1, "slots_count": 16, "color": "royalblue", "tiers_config": 3, "orientation": "V", "is_box": False},
        {"wh_id": "27", "prefix": "RIGHT", "x_start": 10, "y_start": 2, "rows_count": 1, "slots_count": 16, "color": "royalblue", "tiers_config": 3, "orientation": "V", "is_box": False},
        {"wh_id": "27", "prefix": "CORE_ZONE", "x_start": 3.5, "y_start": 4, "rows_count": 3, "slots_count": 12, "color": "whitesmoke", "tiers_config": 0.05, "orientation": "V", "is_box": True},

        # СКЛАД 19
        {"wh_id": "19", "prefix": "LEFT", "x_start": 0, "y_start": 2, "rows_count": 1, "slots_count": 16, "color": "royalblue", "tiers_config": 3, "orientation": "V", "is_box": False},
        {"wh_id": "19", "prefix": "RIGHT", "x_start": 12, "y_start": 2, "rows_count": 1, "slots_count": 16, "color": "royalblue", "tiers_config": 3, "orientation": "V", "is_box": False},
        {"wh_id": "19", "prefix": "TOP_BOXES", "x_start": 2, "y_start": 20, "rows_count": 1, "slots_count": 8, "color": "peru", "tiers_config": 2, "orientation": "H", "is_box": True},
        {"wh_id": "19", "prefix": "CENTER_BOXES", "x_start": 4.5, "y_start": 6, "rows_count": 3, "slots_count": 10, "color": "burlywood", "tiers_config": 1, "orientation": "V", "is_box": True},

        # СКЛАД 31
        {"wh_id": "31", "prefix": "ЗАДНЯЯ_ЧАСТЬ", "x_start": 0, "y_start": 18, "rows_count": 3, "slots_count": 10, "color": "darkgrey", "tiers_config": 0.8, "orientation": "H", "is_box": True},
        {"wh_id": "31", "prefix": "ЛЕВО", "x_start": 0, "y_start": 2, "rows_count": 3, "slots_count": 14, "color": "steelblue", "tiers_config": 0.8, "orientation": "V", "is_box": True},
        {"wh_id": "31", "prefix": "ПРАВО", "x_start": 10, "y_start": 2, "rows_count": 3, "slots_count": 14, "color": "steelblue", "tiers_config": 0.8, "orientation": "V", "is_box": True},

        # СКЛАД 32
        {"wh_id": "32", "prefix": "UPPER_PIPE", "x_start": 2, "y_start": 15, "rows_count": 1, "slots_count": 10, "color": "teal", "tiers_config": 3, "orientation": "H", "is_box": False},
        {"wh_id": "32", "prefix": "BUFFER", "x_start": -2, "y_start": 15, "rows_count": 1, "slots_count": 2, "color": "darkred", "tiers_config": 1, "orientation": "H", "is_box": True},
        {"wh_id": "32", "prefix": "LOWER_PIPE", "x_start": 0, "y_start": 5, "rows_count": 1, "slots_count": 12, "color": "teal", "tiers_config": 3, "orientation": "H", "is_box": False},
        {"wh_id": "32", "prefix": "MAIN_PIPE_AREA", "x_start": 4, "y_start": 8, "rows_count": 2, "slots_count": 8, "color": "lightslategrey", "tiers_config": 0.1, "orientation": "H", "is_box": True},

        # СКЛАД 33
        {"wh_id": "33", "prefix": "LEFT_LEVEL_ALL", "x_start": 0, "y_start": 2, "rows_count": 1, "slots_count": 16, "color": "#1f77b4", "tiers_config": 3, "orientation": "V", "is_box": True},
        {"wh_id": "33", "prefix": "RIGHT_LEVEL_ALL", "x_start": 10, "y_start": 2, "rows_count": 1, "slots_count": 16, "color": "#1f77b4", "tiers_config": 3, "orientation": "V", "is_box": True},
        {"wh_id": "33", "prefix": "CONTROL_ZONE", "x_start": 2.5, "y_start": 4, "rows_count": 3, "slots_count": 12, "color": "rgba(100,100,100,0.2)", "tiers_config": 0.01, "orientation": "V", "is_box": True},

        # СКЛАД 37
        {"wh_id": "37", "prefix": "LEFT", "x_start": 0, "y_start": 2, "rows_count": 1, "slots_count": 18, "color": "royalblue", "tiers_config": 3, "orientation": "V", "is_box": False},
        {"wh_id": "37", "prefix": "RIGHT", "x_start": 12, "y_start": 2, "rows_count": 1, "slots_count": 18, "color": "royalblue", "tiers_config": 3, "orientation": "V", "is_box": False},
        {"wh_id": "37", "prefix": "BACK_BOX", "x_start": 2, "y_start": 21, "rows_count": 1, "slots_count": 10, "color": "peru", "tiers_config": 1.5, "orientation": "H", "is_box": True},
        {"wh_id": "37", "prefix": "CENTER_BLOCK", "x_start": 4.5, "y_start": 6, "rows_count": 3, "slots_count": 10, "color": "burlywood", "tiers_config": 1, "orientation": "V", "is_box": True},
    ]

    print(f"🚀 Начинаю миграцию {len(topology_data)} объектов...")
    
    try:
        # Очищаем таблицу перед вставкой (опционально, если хочешь перезаписать всё)
        # supabase.table("warehouse_topology").delete().neq("wh_id", "0").execute()
        
        # Вставляем данные
        result = supabase.table("warehouse_topology").insert(topology_data).execute()
        print("✅ Миграция завершена успешно!")
    except Exception as e:
        print(f"❌ Ошибка при миграции: {e}")

if __name__ == "__main__":
    migrate_warehouses()
