import plotly.graph_objects as go
import string

class WarehouseManager:
    """Движок отрисовки с поддержкой интерактивного выбора"""
    
    @staticmethod
    def add_rack_design(fig, x_start, y_start, rows, slots, color, name_prefix, 
                        tiers_config=3, orientation='V', is_box=False, warehouse_id="", highlighted_cell=None):
        num_sections = slots // 2
        z_step = 1.2
        section_length = 2.0 

        if isinstance(tiers_config, (int, float)):
            tiers_per_section = [tiers_config] * num_sections
        else:
            tiers_per_section = tiers_config

        if is_box:
            # Отрисовка зон (коробки, площадки)
            max_t = max(tiers_per_section) if isinstance(tiers_per_section, list) else tiers_config
            z_max = max_t * z_step
            width = rows * 1.5
            length = num_sections * section_length
            x_size = width if orientation == 'V' else length
            y_size = length if orientation == 'V' else width
            
            addr = f"WH{warehouse_id}-{name_prefix}-ZONE"
            # Проверка на выделение
            final_color = 'red' if highlighted_cell == addr else color
            
            fig.add_trace(go.Mesh3d(
                x=[x_start, x_start, x_start+x_size, x_start+x_size, x_start, x_start, x_start+x_size, x_start+x_size],
                y=[y_start, y_start+y_size, y_start+y_size, y_start, y_start, y_start+y_size, y_start+y_size, y_start],
                z=[0, 0, 0, 0, z_max, z_max, z_max, z_max],
                i=[7,0,0,0,4,4,6,6,4,0,3,2], j=[3,4,1,2,5,6,5,2,0,1,6,3], k=[0,7,2,3,6,7,1,1,5,5,7,6],
                color=final_color, opacity=0.5, name=addr, text=addr, hoverinfo="text",
                customdata=[addr] # Передаем адрес для клика
            ))
            return

        for r in range(rows):
            for sec_idx in range(num_sections):
                current_tiers = int(tiers_per_section[sec_idx]) if isinstance(tiers_per_section, list) else int(tiers_config)
                z_max = current_tiers * z_step
                
                # Стойки стеллажей
                for s_frame in [sec_idx * section_length, (sec_idx + 1) * section_length]:
                    fx = x_start + (r * 1.5 if orientation == 'V' else s_frame)
                    fy = y_start + (s_frame if orientation == 'V' else r * 1.5)
                    fig.add_trace(go.Scatter3d(
                        x=[fx, fx, None, fx + (0.8 if orientation == 'V' else 0), fx + (0.8 if orientation == 'V' else 0)],
                        y=[fy, fy, None, fy + (0 if orientation == 'V' else 0.8), fy + (0 if orientation == 'V' else 0.8)],
                        z=[0, z_max, None, 0, z_max],
                        mode='lines', line=dict(color='#2c3e50', width=2), showlegend=False, hoverinfo='none'
                    ))
                
                # Полки (ячейки)
                for t in range(current_tiers):
                    tier_label = string.ascii_uppercase[t]
                    z0 = t * z_step
                    x_node = x_start + (r * 1.5 if orientation == 'V' else sec_idx * section_length)
                    y_node = y_start + (sec_idx * section_length if orientation == 'V' else r * 1.5)
                    dx = 0.8 if orientation == 'V' else section_length
                    dy = section_length if orientation == 'V' else 0.8
                    dz = 0.1
                    
                    addr = f"WH{warehouse_id}-{name_prefix}-R{r+1}-S{sec_idx+1}-{tier_label}"
                    # Если эта ячейка выбрана — красим в красный
                    final_color = 'red' if highlighted_cell == addr else color

                    fig.add_trace(go.Mesh3d(
                        x=[x_node, x_node, x_node+dx, x_node+dx, x_node, x_node, x_node+dx, x_node+dx],
                        y=[y_node, y_node+dy, y_node+dy, y_node, y_node, y_node+dy, y_node+dy, y_node],
                        z=[z0, z0, z0, z0, z0+dz, z0+dz, z0+dz, z0+dz],
                        i=[7,0,0,0,4,4,6,6,4,0,3,2], j=[3,4,1,2,5,6,5,2,0,1,6,3], k=[0,7,2,3,6,7,1,1,5,5,7,6],
                        color=final_color, opacity=0.8, name=addr, text=addr, hoverinfo="text",
                        customdata=[addr]
                    ))

# --- ФУНКЦИИ СБОРОК (НИЧЕГО НЕ СОКРАЩЕНО) ---

def build_warehouse_28(fig, offset_x=0, sel=None):
    mgr = WarehouseManager(); wh = "28"; x = offset_x
    mgr.add_rack_design(fig, x+2, 2, 2, 2, 'lightgrey', 'BULK_ENTRANCE', 1, 'H', True, wh, sel)
    mgr.add_rack_design(fig, x+0, 8, 1, 10, 'lightblue', 'LW', [4, 3, 3, 3, 4], "V", False, wh, sel)
    mgr.add_rack_design(fig, x+5, 10, 1, 4, 'royalblue', 'CT1', 3, "V", False, wh, sel)
    mgr.add_rack_design(fig, x+5, 15, 2, 2, 'lightgrey', 'BUFFER', 2, "H", True, wh, sel)
    mgr.add_rack_design(fig, x+7.5, 10, 1, 4, 'royalblue', 'CT2', 4, "V", False, wh, sel)
    mgr.add_rack_design(fig, x+10, 10, 1, 8, 'royalblue', 'CT3', 3, "V", False, wh, sel)
    mgr.add_rack_design(fig, x+12, 10, 1, 8, 'royalblue', 'CT4', 3, "V", False, wh, sel)
    mgr.add_rack_design(fig, x+5, 17, 1, 4, 'violet', 'BC', 4, 'H', False, wh, sel)
    mgr.add_rack_design(fig, x+15, 10, 1, 8, 'green', 'OC1', 3, "V", False, wh, sel)
    mgr.add_rack_design(fig, x+18, 5, 1, 12, 'red', 'RW', [3, 3, 3, 3, 5, 3], "V", False, wh, sel)
    mgr.add_rack_design(fig, x+10, 22, 1, 8, 'orange', 'BW', 3, 'H', False, wh, sel)
    mgr.add_rack_design(fig, x+2, 22, 1, 4, 'black', 'BW_L', 3, 'H', False, wh, sel)
    mgr.add_rack_design(fig, x+10, 0, 1, 8, 'grey', 'FH1', 3, 'H', False, wh, sel)
    mgr.add_rack_design(fig, x+14, 2, 1, 4, 'darkgrey', 'FH2', 3, 'H', False, wh, sel)
    mgr.add_rack_design(fig, x+10, 2, 1, 2, 'lightgrey', 'BULK_FIN', 2, 'H', True, wh, sel)
    return fig

def build_warehouse_27(fig, offset_x=0, sel=None):
    mgr = WarehouseManager(); wh = "27"; x = offset_x
    mgr.add_rack_design(fig, x+0, 20, 1, 8, 'orange', 'BACK', 3, 'H', False, wh, sel)
    mgr.add_rack_design(fig, x+0, 2, 1, 16, 'royalblue', 'LEFT', 3, 'V', False, wh, sel)
    mgr.add_rack_design(fig, x+10, 2, 1, 16, 'royalblue', 'RIGHT', 3, 'V', False, wh, sel)
    mgr.add_rack_design(fig, x+3.5, 4, 3, 12, 'whitesmoke', 'CORE_ZONE', 0.05, 'V', True, wh, sel)
    return fig

def build_warehouse_19(fig, offset_x=0, sel=None):
    mgr = WarehouseManager(); wh = "19"; x = offset_x
    mgr.add_rack_design(fig, x+0, 2, 1, 16, 'royalblue', 'LEFT', 3, 'V', False, wh, sel)
    mgr.add_rack_design(fig, x+12, 2, 1, 16, 'royalblue', 'RIGHT', 3, 'V', False, wh, sel)
    mgr.add_rack_design(fig, x+2, 20, 1, 8, 'peru', 'TOP_BOXES', 2, 'H', True, wh, sel)
    mgr.add_rack_design(fig, x+4.5, 6, 3, 10, 'burlywood', 'CENTER_BOXES', 1, 'V', True, wh, sel)
    return fig

def build_warehouse_31(fig, offset_x=0, sel=None):
    mgr = WarehouseManager(); wh = "31"; x = offset_x
    f_h = 0.8
    mgr.add_rack_design(fig, x+0, 18, 3, 10, 'darkgrey', 'ЗАДНЯЯ_ЧАСТЬ', f_h, 'H', True, wh, sel)
    mgr.add_rack_design(fig, x+0, 2, 3, 14, 'steelblue', 'ЛЕВО', f_h, 'V', True, wh, sel)
    mgr.add_rack_design(fig, x+10, 2, 3, 14, 'steelblue', 'ПРАВО', f_h, 'V', True, wh, sel)
    return fig

def build_warehouse_32(fig, offset_x=0, sel=None):
    mgr = WarehouseManager(); wh = "32"; x = offset_x
    mgr.add_rack_design(fig, x+2, 15, 1, 10, 'teal', 'UPPER_PIPE', 3, 'H', False, wh, sel)
    mgr.add_rack_design(fig, x-2, 15, 1, 2, 'darkred', 'BUFFER', 1, 'H', True, wh, sel)
    mgr.add_rack_design(fig, x+0, 5, 1, 12, 'teal', 'LOWER_PIPE', 3, 'H', False, wh, sel)
    mgr.add_rack_design(fig, x+4, 8, 2, 8, 'lightslategrey', 'MAIN_PIPE_AREA', 0.1, 'H', True, wh, sel)
    return fig

def build_warehouse_33(fig, offset_x=0, sel=None):
    mgr = WarehouseManager(); wh = "33"; x = offset_x
    for t, color in enumerate(['#1f77b4', '#4c99d3', '#7fbadd']):
        z0 = t * 1.2
        mgr.add_rack_design(fig, x+0, 2, 1, 16, color, f'LEFT_LEVEL_{t+1}', 0.1, 'V', True, wh, sel)
        fig.data[-1].z = [z0, z0, z0, z0, z0+0.1, z0+0.1, z0+0.1, z0+0.1]
        mgr.add_rack_design(fig, x+10, 2, 1, 16, color, f'RIGHT_LEVEL_{t+1}', 0.1, 'V', True, wh, sel)
        fig.data[-1].z = [z0, z0, z0, z0, z0+0.1, z0+0.1, z0+0.1, z0+0.1]
    mgr.add_rack_design(fig, x+2.5, 4, 3, 12, 'rgba(100,100,100,0.2)', 'CONTROL_ZONE', 0.01, 'V', True, wh, sel)
    return fig

def build_warehouse_37(fig, offset_x=0, sel=None):
    mgr = WarehouseManager(); wh = "37"; x = offset_x
    mgr.add_rack_design(fig, x+0, 2, 1, 18, 'royalblue', 'LEFT', 3, 'V', False, wh, sel)
    mgr.add_rack_design(fig, x+12, 2, 1, 18, 'royalblue', 'RIGHT', 3, 'V', False, wh, sel)
    mgr.add_rack_design(fig, x+2, 21, 1, 10, 'peru', 'BACK_BOX', 1.5, 'H', True, wh, sel)
    mgr.add_rack_design(fig, x+4.5, 6, 3, 10, 'burlywood', 'CENTER_BLOCK', 1, 'V', True, wh, sel)
    return fig

# ==========================================================
# 🗺️ ГЛАВНЫЙ ИНТЕРФЕЙС ВОЗВРАТА ФИГУРЫ
# ==========================================================
REGISTRY = {
    "19": build_warehouse_19, "27": build_warehouse_27, "28": build_warehouse_28,
    "31": build_warehouse_31, "32": build_warehouse_32, "33": build_warehouse_33, "37": build_warehouse_37
}

def get_warehouse_figure(warehouse_id, highlighted_cell=None):
    fig = go.Figure()
    
    # Приводим к строке для поиска в реестре
    wh_key = str(warehouse_id)
    
    if warehouse_id == "ALL":
        for i, (wh_id, func) in enumerate(REGISTRY.items()):
            func(fig, offset_x=i * 40, sel=highlighted_cell)
        title = "Глобальная топология сети"
    elif wh_key in REGISTRY:
        REGISTRY[wh_key](fig, sel=highlighted_cell)
        title = f"Склад №{warehouse_id} - Интерактивная карта"
    else:
        title = "Склад не выбран"

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
        # Важные параметры для захвата клика
        clickmode='event+select',
        hovermode='closest',
        margin=dict(l=0, r=0, b=0, t=50),
        showlegend=False
    )
    return fig

# ПРИМЕР: как должна рисоваться каждая полка внутри build_warehouse_XX
def add_shelf_cube(fig, name, x_pos, y_pos, z_pos, is_highlighted=False):
    # Цвет: красный если выбрана, синий если обычная
    color = 'red' if is_highlighted else 'royalblue'
    opacity = 0.9 if is_highlighted else 0.6

    # Рисуем ячейку (например, через Mesh3d для 3D куба)
    fig.add_trace(go.Mesh3d(
        x=[x_pos, x_pos+1, x_pos+1, x_pos, x_pos, x_pos+1, x_pos+1, x_pos],
        y=[y_pos, y_pos, y_pos+1, y_pos+1, y_pos, y_pos, y_pos+1, y_pos+1],
        z=[z_pos, z_pos, z_pos, z_pos, z_pos+1, z_pos+1, z_pos+1, z_pos+1],
        
        # --- ВОТ ЭТА СТРОЧКА РЕШАЕТ ВСЁ ---
        customdata=[name] * 8, # Передаем ID ячейки (например '19-LEFT-A-1')
        # ---------------------------------
        
        name=name,
        color=color,
        opacity=opacity,
        flatshading=True,
        hovertemplate=f"Ячейка: {name}<extra></extra>"
    ))