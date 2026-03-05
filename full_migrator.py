import sqlite3
import pandas as pd
from database import supabase  # Твое подключение

# Список РЕАЛЬНЫХ таблиц из твоего Supabase (судя по скриншотам)
REAL_TABLES = [
    "arrivals", 
    "defects", 
    "devices", 
    "drivers", 
    "extras", 
    "inventory", 
    "manager_profile", 
    "orders", 
    "positions", 
    "product_locations", 
    "profiles", 
    "vehicles"
]

DB_PATH = "imperia_data.db"

def run_total_migration():
    conn = sqlite3.connect(DB_PATH)
    print("🚛 Начинаем глобальную перекидку LOGISTICS W&TMS на локальный диск...")

    for table in REAL_TABLES:
        try:
            print(f"📥 Качаем таблицу: {table}...")
            
            # Берем данные
            res = supabase.table(table).select("*").execute()
            
            if res.data:
                df = pd.DataFrame(res.data)
                
                # SQLite не любит сложные объекты (списки/словари), превращаем их в текст (JSON)
                for col in df.columns:
                    if df[col].apply(lambda x: isinstance(x, (list, dict))).any():
                        df[col] = df[col].apply(lambda x: str(x) if x is not None else None)

                # Сохраняем
                df.to_sql(table, conn, if_exists='replace', index=False)
                print(f"✅ {table}: успешно перенесено {len(df)} строк.")
            else:
                print(f"🔘 {table}: таблица пуста, создаем пустую структуру.")
                # Если данных нет, создаем хоть какую-то структуру, чтобы код не падал
                pd.DataFrame().to_sql(table, conn, if_exists='replace')

        except Exception as e:
            print(f"❌ Ошибка в таблице {table}: {e}")

    conn.close()
    print("\n🏁 ВСЁ! База 'imperia_data.db' готова. Теперь ты независим от облака!")

if __name__ == "__main__":
    run_total_migration()
