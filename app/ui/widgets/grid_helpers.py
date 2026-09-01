"""Stol grid layout yordamchilari."""
JOYSTICK_FREE_COUNT = 2
TRANSFER_ICON_FILE = 'transfer_icon.png'
def station_col_widths(compact: bool) -> dict[str, int]:
    if compact:
        return {'stol': 112, 'holat': 88, 'started': 86, 'played': 108, 'ps': 112, 'goods': 108, 'total': 116}
    else:
        return {'stol': 132, 'holat': 104, 'started': 100, 'played': 124, 'ps': 130, 'goods': 124, 'total': 134}
def right_cluster_width(compact: bool) -> int:
    return 292 if compact else 348
def grid_layout_for_count(station_count: int) -> tuple[int, bool]:
    compact = station_count >= 10
    return (1, compact)