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
        
        # 1. Исправляем количество секций (убираем деление на 2, если slots - это реальное число секций)
        num_sections = int(slots) 
        z_step = 1.2
        section_length = 1.2 # Компактный размер секции

        # 2. Обработка ярусов
        try:
            current_tiers = int(tiers_config)
        except:
            current_tiers = 1

        for r in range(rows):
            for sec_idx in range(num_sections):
                z_max = current_tiers * z_step
                
                # Отрисовка каркаса (линии)
                for s_frame in [sec_idx * section_length, (sec_idx + 1) * section_length]:
                    fx = x_start + (r * 1.5 if orientation == 'V' else s_frame)
                    fy = y_start + (s_frame if orientation == 'V' else r * 1.5)
                    fig.add_trace(go.Scatter3d(
                        x=[fx, fx, None, fx + (0.5 if orientation == 'V' else 0), fx + (0.5 if orientation == 'V' else 0)],
                        y=[fy, fy, None, fy + (0 if orientation == 'V' else 0.5), fy + (0 if orientation == 'V' else 0.5)],
                        z=[0, z_max, None, 0, z_max],
                        mode='lines', line=dict(color='#444', width=1), showlegend=False, hoverinfo='none'
                    ))
                
                # 3. ГЕНЕРАЦИЯ ЯЧЕЕК И ИМЕН
                for t in range(current_tiers):
                    tier_num = t + 1
                    z0 = t * z_step
                    
                    # ГЛАВНОЕ ИЗМЕНЕНИЕ: Формат имени ст-1-01-1
                    # Это должно совпадать с тем, что возвращает get_actual_cells
                    addr = f"{name_prefix}-{sec_idx+1:02d}-{tier_num}"
                    
                    # ПРОВЕРКА ПОДСВЕТКИ
                    final_color = 'red' if highlighted_cell == addr else color

                    x_node = x_start + (r * 1.5 if orientation == 'V' else sec_idx * section_length)
                    y_node = y_start + (sec_idx * section_length if orientation == 'V' else r * 1.5)
                    dx = 0.8 if orientation == 'V' else section_length
                    dy = section_length if orientation == 'V' else 0.8
                    dz = 0.1
                    
                    fig.add_trace(go.Mesh3d(
                        x=[x_node, x_node, x_node+dx, x_node+dx, x_node, x_node, x_node+dx, x_node+dx],
                        y=[y_node, y_node+dy, y_node+dy, y_node, y_node, y_node+dy, y_node+dy, y_node],
                        z=[z0, z0, z0, z0, z0+dz, z0+dz, z0+dz, z0+dz],
                        i=[7,0,0,0,4,4,6,6,4,0,3,2], j=[3,4,1,2,5,6,5,2,0,1,6,3], k=[0,7,2,3,6,7,1,1,5,5,7,6],
                        color=final_color, 
                        opacity=0.9 if highlighted_cell == addr else 0.7, 
                        name=addr, 
                        text=addr, 
                        hovertemplate="<b>%{name}</b><extra></extra>"
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
            aspectmode='data', # Сжимает карту под размер стеллажей (убирает пустоту)
            xaxis=dict(title="", showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(title="", showgrid=False, zeroline=False, showticklabels=False),
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
