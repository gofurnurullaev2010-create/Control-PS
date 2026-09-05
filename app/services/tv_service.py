from __future__ import annotations
import logging
logger = logging.getLogger(__name__)
class TVService:
    """Eski TV modullari ustidan xavfsiz wrapper."""
    def bootstrap_after_login(self) -> None:
        from app.core.runtime import ensure_tv_tools_path
        from app.tv import tv_handler
        from app.tv import tv_platforms
        ensure_tv_tools_path()
        tv_platforms.prepare_webos_cli()
        tv_platforms.sync_webos_device_mappings_from_ares()
        tv_platforms.warmup_webos_devices()
        try:
            import database as db
            db.clear_tv_settings('STOL-05')
        except Exception as e:
            logger.warning('STOL-05 TV olib tashlash: %s', e)
        tv_handler.start_lock_gate_http_server()
        tv_handler.sync_active_tv_sessions_from_db()
        tv_handler.set_main_app_lock_gate(True)
        tv_handler.sync_webos_initial_lock_from_db()
        tv_handler.start_webos_connectivity_monitor()
        tv_handler.provision_all_android_lock_tvs_background()
    def shutdown(self) -> None:
        try:
            from app.tv import tv_handler
            tv_handler.set_main_app_lock_gate(False)
        except Exception as e:
            logger.warning('TV shutdown: %s', e)
    def handler_for_station(self, station_id: str):
        from app.tv.tv_handler import TVHandler
        settings = self._settings(station_id)
        if not settings or not settings.tv_ip:
            return None
        else:
            return TVHandler(settings.tv_ip, settings.tv_mac, settings.brand, settings.hdmi_input)
    def _settings(self, station_id: str):
        import database as db
        return db.get_tv_settings(station_id)
    def register_session_gate(self, station_id: str) -> None:
        from app.tv import tv_handler
        settings = self._settings(station_id)
        if settings and settings.tv_ip:
            try:
                tv_handler.register_tv_session(settings.tv_ip, station_id=station_id)
            except Exception as e:
                logger.warning('Gate register %s: %s', station_id, e)
    def unregister_session_gate(self, station_id: str) -> None:
        from app.tv import tv_handler
        settings = self._settings(station_id)
        if settings and settings.tv_ip:
            try:
                tv_handler.unregister_tv_session(settings.tv_ip, station_id=station_id)
            except Exception as e:
                logger.warning('Gate unregister %s: %s', station_id, e)
    def sync_active_sessions(self) -> None:
        try:
            from app.tv import tv_handler
            tv_handler.sync_active_tv_sessions_from_db()
        except Exception as e:
            logger.warning('TV session sync: %s', e)