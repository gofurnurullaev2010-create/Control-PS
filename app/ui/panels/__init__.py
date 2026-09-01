"""Admin va market panellari."""
__all__ = ['AdminLoginDialog', 'AdminPanelDialog', 'MarketPanelDialog']
def __getattr__(name: str):
    if name in ['AdminLoginDialog', 'AdminPanelDialog', 'ChangePasswordDialog']:
        from app.ui.panels import admin_panel_new as mod
        return getattr(mod, name)
    else:
        if name == 'MarketPanelDialog':
            from app.ui.panels.market_panel import MarketPanelDialog
            return MarketPanelDialog
        else:
            raise AttributeError(f'module {__name__!r} has no attribute {name!r}')