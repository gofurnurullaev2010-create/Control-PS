"""Kompyuterda mijozlar ro\'yxatini ko\'rish: python -m app.auth.tools.mijozlar_korish"""
from app.auth.license_registry import format_roster
__all__ = ['format_roster']
if __name__ == '__main__':
    print(format_roster())