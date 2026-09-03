from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
@dataclass
class LicenseStatus:
    valid: bool
    hwid: str
    message: Optional[str] = None
    show_expiry_warning: bool = False
class AuthService:
    def verify_login(self, password: str) -> bool:
        from app.auth import app_password
        return bool(app_password.verify_password(password))
    def verify_admin(self, password: str) -> bool:
        from app.auth import app_password
        return bool(app_password.verify_admin_password(password))
    def identify_operator(self, password: str) -> Optional[int]:
        from app.auth import app_password
        return app_password.identify_operator(password)
class LicenseService:
    def verify(self) -> LicenseStatus:
        from app.auth import license_manager
        lic = license_manager.verify_license_full()
        show_warning = False
        if lic.valid:
            try:
                show_warning = license_manager.get_license_status().show_expiry_warning
            except Exception:
                show_warning = False
        return LicenseStatus(valid=lic.valid, hwid=lic.hwid, message=lic.message, show_expiry_warning=show_warning)
    def runtime_check(self) -> LicenseStatus:
        """Har daqiqa: internet probe qilmaydi (Win10 qotishi)."""
        from app.auth import license_manager
        lic = license_manager.verify_license_full()
        return LicenseStatus(valid=lic.valid, hwid=lic.hwid, message=lic.message, show_expiry_warning=False)