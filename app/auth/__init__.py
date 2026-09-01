"""Auth / litsenziya qatlami."""
__all__ = ['app_password', 'license_manager', 'license_online', 'license_registry']
def __getattr__(name: str):
    if name in __all__:
        import importlib
        return importlib.import_module(f'app.auth.{name}')
    else:
        raise AttributeError(f'module {__name__!r} has no attribute {name!r}')