"""\nControl PS — UI qatlami (orqaga moslik).\n\nAsosiy kod:\n  - Modular shell: app.ui.main_window\n  - Legacy shell:  app.ui.legacy_main_window\n  - Dialoglar:     app.ui.dialogs.*\n  - Stol kartasi:  app.ui.widgets.station_card\n"""
from __future__ import annotations
from app.ui.widgets.station_card import SessionTimer, StationCard, format_seconds
from app.ui.widgets.admin_button import AdminButtonWidget, _AdminButtonWidget
from app.ui.widgets.grid_helpers import JOYSTICK_FREE_COUNT, TRANSFER_ICON_FILE, grid_layout_for_count as _grid_layout_for_count, right_cluster_width as _right_cluster_width, station_col_widths as _station_col_widths
from app.ui.dialogs.station_dialogs import TransferTimeDialog, VolumeDialog, VIPStartDialog, OrderTypeDialog, _OrderTypeDialog
from app.ui.dialogs.finance_dialogs import PriceDialog, ReportDialog, DebtorAddDialog, DebtorAdjustDialog, DebtorsDialog
from app.ui.dialogs.admin_dialogs import PasswordDialog, AdminDialog, PasswordChangeDialog, OperatorReportDialog
from app.ui.dialogs.tv_settings_dialog import TVSettingsDialog
from app.ui.dialogs.customer_display import CustomerDisplayWindow
from app.ui.legacy_main_window import MainWindow
__all__ = ['MainWindow', 'StationCard', 'SessionTimer', 'format_seconds', 'AdminButtonWidget', '_AdminButtonWidget', 'TransferTimeDialog', 'VolumeDialog', 'VIPStartDialog', 'OrderTypeDialog', '_OrderTypeDialog', 'PriceDialog', 'ReportDialog', 'DebtorAddDialog', 'DebtorAdjustDialog', 'DebtorsDialog', 'PasswordDialog', 'AdminDialog', 'PasswordChangeDialog', 'OperatorReportDialog', 'TVSettingsDialog', 'CustomerDisplayWindow', '_grid_layout_for_count', '_station_col_widths', '_right_cluster_width', 'JOYSTICK_FREE_COUNT', 'TRANSFER_ICON_FILE']