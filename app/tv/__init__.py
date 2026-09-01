"""TV integratsiya qatlami (handler, platforms, VIDAA)."""
__all__ = ['TVHandler', 'tv_handler', 'tv_platforms', 'vidaa_platform']
def __getattr__(name: str):
    if name == 'TVHandler':
        from app.tv.tv_handler import TVHandler
        return TVHandler
    else:
        if name in ['tv_handler', 'tv_platforms', 'vidaa_platform']:
            import importlib
            return importlib.import_module(f'app.tv.{name}')
        else:
            raise AttributeError(f'module {__name__!r} has no attribute {name!r}')