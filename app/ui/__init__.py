"""PyQt UI qatlami."""
__all__ = ['MainWindow']
def __getattr__(name: str):
    if name == 'MainWindow':
        from app.ui.main_window import MainWindow
        return MainWindow
    else:
        raise AttributeError(f'module {__name__!r} has no attribute {name!r}')