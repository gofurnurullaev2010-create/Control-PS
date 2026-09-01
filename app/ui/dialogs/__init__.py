"""UI dialoglari — kechikkan import (aylana bog'lanishni oldini olish)."""
__all__ = [
    "TransferTimeDialog",
    "VolumeDialog",
    "OrderTypeDialog",
    "_OrderTypeDialog",
    "VIPStartDialog",
    "PriceDialog",
    "ReportDialog",
    "DebtorAddDialog",
    "DebtorAdjustDialog",
    "DebtorsDialog",
    "PasswordDialog",
    "AdminDialog",
    "PasswordChangeDialog",
    "OperatorReportDialog",
    "TVSettingsDialog",
    "CustomerDisplayWindow",
    "LoginDialog",
    "DrinkOrderDialog",
    "MarketOrderDialog",
    "ReturnOrderDialog",
]
_LAZY = {
    "TransferTimeDialog": ("app.ui.dialogs.station_dialogs", "TransferTimeDialog"),
    "VolumeDialog": ("app.ui.dialogs.station_dialogs", "VolumeDialog"),
    "OrderTypeDialog": ("app.ui.dialogs.station_dialogs", "OrderTypeDialog"),
    "_OrderTypeDialog": ("app.ui.dialogs.station_dialogs", "_OrderTypeDialog"),
    "VIPStartDialog": ("app.ui.dialogs.station_dialogs", "VIPStartDialog"),
    "PriceDialog": ("app.ui.dialogs.finance_dialogs", "PriceDialog"),
    "ReportDialog": ("app.ui.dialogs.finance_dialogs", "ReportDialog"),
    "DebtorAddDialog": ("app.ui.dialogs.finance_dialogs", "DebtorAddDialog"),
    "DebtorAdjustDialog": ("app.ui.dialogs.finance_dialogs", "DebtorAdjustDialog"),
    "DebtorsDialog": ("app.ui.dialogs.finance_dialogs", "DebtorsDialog"),
    "PasswordDialog": ("app.ui.dialogs.admin_dialogs", "PasswordDialog"),
    "AdminDialog": ("app.ui.dialogs.admin_dialogs", "AdminDialog"),
    "PasswordChangeDialog": ("app.ui.dialogs.admin_dialogs", "PasswordChangeDialog"),
    "OperatorReportDialog": ("app.ui.dialogs.admin_dialogs", "OperatorReportDialog"),
    "TVSettingsDialog": ("app.ui.dialogs.tv_settings_dialog", "TVSettingsDialog"),
    "CustomerDisplayWindow": ("app.ui.dialogs.customer_display", "CustomerDisplayWindow"),
    "LoginDialog": ("app.ui.dialogs.login_dialog", "LoginDialog"),
    "DrinkOrderDialog": ("app.ui.dialogs.drink_dialog", "DrinkOrderDialog"),
    "MarketOrderDialog": ("app.ui.dialogs.drink_dialog", "MarketOrderDialog"),
    "ReturnOrderDialog": ("app.ui.dialogs.drink_dialog", "ReturnOrderDialog"),
}


def __getattr__(name: str):
    if name in _LAZY:
        mod_name, attr = _LAZY[name]
        import importlib

        mod = importlib.import_module(mod_name)
        value = getattr(mod, attr)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
