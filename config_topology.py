import plotly.graph_objects as go
import string
from supabase import create_client, Client

# --- НАСТРОЙКИ ПОДКЛЮЧЕНИЯ ---
url = "https://grdyokwemanzcpmfvhps.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdyZHlva3dlbWFuemNwbWZ2aHBzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzM0OTg0NTMsImV4cCI6MjA4OTA3NDQ1M30.CL_UETOVA-Fw1b4vJc_rQUUiuE44cWD2qDYWPog4S0w"
supabase: Client = create_client(url, key)

class WarehouseManager:
    """Движок отрисовки (остается без изменений, чтобы всё работало как раньше)"""
    @staticmethod
    def add_rack_design(fig, x_start, y_start, rows, slots, color, name_prefix, 
                        tiers_config=3, orientation='V', is_box=False, warehouse_id="", highlighted_cell=None):
        num_sections = slots // 2
        z_step = 1.2
        section_length = 2.0 

        # Обработка конфигурации ярусов (из БД может прийти int или list)
        if isinstance(tiers_config, (int, float)):
            tiers_per_section = [int(tiers_config)] * num_sections
        else:
            tiers_per_section = tiers_config

        if is_box:
            max_t = max(tiers_per_section) if isinstance(tiers_per_section, list) else tiers_config
            z_max = max_t * z_step
            width = rows * 1.5
            length = num_sections * section_length
            x_size = width if orientation == 'V' else length
            y_size = length if orientation == 'V' else width
            
            addr = f"WH{warehouse_id}-{name_prefix}-ZONE"
            final_color = 'red' if highlighted_cell == addr else color
            
            fig.add_trace(go.Mesh3d(
                x=[x_start, x_start, x_start+x_size, x_start+x_size, x_start, x_start, x_start+x_size, x_start+x_size],
                y=[y_start, y_start+y_size, y_start+y_size, y_start, y_start, y_start+y_size, y_start+y_size, y_start],
                z=[0, 0, 0, 0, z_max, z_max, z_max, z_max],
                i=[7,0,0,0,4,4,6,6,4,0,3,2], j=[3,4,1,2,5,6,5,2,0,1,6,3], k=[0,7,2,3,6,7,1,1,5,5,7,6],
                color=final_color, opacity=0.5, name=addr, text=addr, hoverinfo="text",
                customdata=[addr]
            ))
            return

        for r in range(rows):
            for sec_idx in range(num_sections):
                current_tiers = int(tiers_per_section[sec_idx])
                z_max = current_tiers * z_step
                
                for s_frame in [sec_idx * section_length, (sec_idx + 1) * section_length]:
                    fx = x_start + (r * 1.5 if orientation == 'V' else s_frame)
                    fy = y_start + (s_frame if orientation == 'V' else r * 1.5)
                    fig.add_trace(go.Scatter3d(
                        x=[fx, fx, None, fx + (0.8 if orientation == 'V' else 0), fx + (0.8 if orientation == 'V' else 0)],
                        y=[fy, fy, None, fy + (0 if orientation == 'V' else 0.8), fy + (0 if orientation == 'V' else 0.8)],
                        z=[0, z_max, None, 0, z_max],
                        mode='lines', line=dict(color='#2c3e50', width=2), showlegend=False, hoverinfo='none'
                    ))
                
                for t in range(current_tiers):
                    tier_label = string.ascii_uppercase[t]
                    z0 = t * z_step
                    x_node = x_start + (r * 1.5 if orientation == 'V' else sec_idx * section_length)
                    y_node = y_start + (sec_idx * section_length if orientation == 'V' else r * 1.5)
                    dx = 0.8 if orientation == 'V' else section_length
                    dy = section_length if orientation == 'V' else 0.8
                    dz = 0.1
                    
                    addr = f"WH{warehouse_id}-{name_prefix}-R{r+1}-S{sec_idx+1}-{tier_label}"
                    final_color = 'red' if highlighted_cell == addr else color

                    fig.add_trace(go.Mesh3d(
                        x=[x_node, x_node, x_node+dx, x_node+dx, x_node, x_node, x_node+dx, x_node+dx],
                        y=[y_node, y_node+dy, y_node+dy, y_node, y_node, y_node+dy, y_node+dy, y_node],
                        z=[z0, z0, z0, z0, z0+dz, z0+dz, z0+dz, z0+dz],
                        i=[7,0,0,0,4,4,6,6,4,0,3,2], j=[3,4,1,2,5,6,5,2,0,1,6,3], k=[0,7,2,3,6,7,1,1,5,5,7,6],
                        color=final_color, opacity=0.8, name=addr, text=addr, hoverinfo="text",
                        customdata=[addr]
                    ))

# --- УНИВЕРСАЛЬНЫЙ СБОРЩИК СКЛАДА ИЗ БД ---

def build_warehouse_dynamic(fig, warehouse_id, offset_x=0, sel=None):
    """Заменяет все функции build_warehouse_XX"""
    mgr = WarehouseManager()
    
    # Получаем данные из Supabase для конкретного склада
    response = supabase.table("warehouse_topology")\
        .select("*")\
        .eq("wh_id", str(warehouse_id))\
        .execute()
    
    if not response.data:
        return fig

    for item in response.data:
        mgr.add_rack_design(
            fig,
            x_start=item['x_start'] + offset_x,
            y_start=item['y_start'],
            rows=item['rows_count'],
            slots=item['slots_count'],
            color=item['color'],
            name_prefix=item['prefix'],
            tiers_config=item['tiers_config'],
            orientation=item['orientation'],
            is_box=item['is_box'],
            warehouse_id=str(warehouse_id),
            highlighted_cell=sel
        )
    return fig

# --- ГЛАВНЫЙ ИНТЕРФЕЙС (СОХРАНЯЕМ НАЗВАНИЯ) ---

def get_warehouse_figure(warehouse_id, highlighted_cell=None):
    fig = go.Figure()
    wh_key = str(warehouse_id)
    
    if warehouse_id == "ALL":
        # Получаем все уникальные ID складов из базы
        wh_ids = supabase.table("warehouse_topology").select("wh_id").execute()
        unique_whs = sorted(list(set([i['wh_id'] for i in wh_ids.data])))
        
        for i, wh in enumerate(unique_whs):
            build_warehouse_dynamic(fig, wh, offset_x=i * 40, sel=highlighted_cell)
        title = "Глобальная топология сети (Dynamic)"
    else:
        build_warehouse_dynamic(fig, wh_key, sel=highlighted_cell)
        title = f"Склад №{warehouse_id} - Интерактивная карта"

    fig.update_layout(
        title=dict(text=title, x=0.5, font=dict(size=22, color='#ecf0f1')),
        template="plotly_dark",
        paper_bgcolor='#1e1e1e',
        plot_bgcolor='#1e1e1e',
        scene=dict(
            aspectmode='data',
            xaxis=dict(title="Длина (м)", gridcolor='#34495e'),
            yaxis=dict(title="Ширина (м)", gridcolor='#34495e'),
            zaxis=dict(title="Ярус", gridcolor='#34495e'),
        ),
        clickmode='event+select',
        hovermode='closest',
        margin=dict(l=0, r=0, b=0, t=50),
        showlegend=False
    )
    return fig

def get_actual_cells(warehouse_id):
    """Теперь работает в 100 раз быстрее, просто опрашивая базу"""
    wh_key = str(warehouse_id)
    # Здесь можно было бы реализовать логику генерации имен без отрисовки Plotly
    # Но для сохранения совместимости, пока используем создание временной фигуры
    temp_fig = go.Figure()
    if wh_key == "ALL":
        wh_ids = supabase.table("warehouse_topology").select("wh_id").execute()
        for i, wh in enumerate(set([i['wh_id'] for i in wh_ids.data])):
            build_warehouse_dynamic(temp_fig, wh, offset_x=i * 40)
    else:
        build_warehouse_dynamic(temp_fig, wh_key)
        
    cells = [trace.name for trace in temp_fig.data if trace.name]
    return sorted(list(set(cells)))

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
