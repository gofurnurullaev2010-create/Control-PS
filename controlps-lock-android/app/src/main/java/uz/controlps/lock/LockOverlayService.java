package uz.controlps.lock;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.graphics.PixelFormat;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.provider.Settings;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.WindowManager;

/** HDMI/PS ustida RAPTOR blok + PC gate so'rovi. */
public class LockOverlayService extends Service {
    public static final String ACTION_SHOW = "uz.controlps.lock.SHOW_OVERLAY";
    public static final String ACTION_HIDE = "uz.controlps.lock.HIDE_OVERLAY";
    public static final String ACTION_WATCH = "uz.controlps.lock.WATCH_GATE";
    private static final String CHANNEL = "cps_lock";

    private WindowManager wm;
    private View overlay;
    private LockScreenBinder binder;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private boolean shown;
    private Boolean lastGateLock;

    public static void ensureRunning(Context ctx, boolean show) {
        Intent i = new Intent(ctx, LockOverlayService.class);
        i.setAction(show ? ACTION_SHOW : ACTION_HIDE);
        if (Build.VERSION.SDK_INT >= 26) {
            ctx.startForegroundService(i);
        } else {
            ctx.startService(i);
        }
    }

    public static void ensureWatching(Context ctx) {
        Intent i = new Intent(ctx, LockOverlayService.class);
        i.setAction(ACTION_WATCH);
        if (Build.VERSION.SDK_INT >= 26) {
            ctx.startForegroundService(i);
        } else {
            ctx.startService(i);
        }
    }

    @Override
    public void onCreate() {
        super.onCreate();
        wm = (WindowManager) getSystemService(WINDOW_SERVICE);
        startAsForeground();
        handler.post(pollRunnable);
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        startAsForeground();
        String action = intent != null ? intent.getAction() : null;
        if (ACTION_HIDE.equals(action)) {
            lastGateLock = Boolean.FALSE;
            hideOverlay();
        } else if (ACTION_SHOW.equals(action)) {
            lastGateLock = Boolean.TRUE;
            showOverlay();
        }
        return START_STICKY;
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public void onDestroy() {
        handler.removeCallbacksAndMessages(null);
        hideOverlay();
        super.onDestroy();
    }

    private final Runnable pollRunnable = new Runnable() {
        @Override
        public void run() {
            try {
                Boolean need = LockGate.pollShouldLock();
                if (need != null) {
                    lastGateLock = need;
                }
                if (need != null) {
                    if (need) {
                        showOverlay();
                    } else {
                        hideOverlay();
                    }
                } else if (lastGateLock == null || lastGateLock) {
                    showOverlay();
                } else {
                    hideOverlay();
                }
            } catch (Exception ignored) {
            }
            handler.postDelayed(this, 2500);
        }
    };

    private void startAsForeground() {
        if (Build.VERSION.SDK_INT >= 26) {
            NotificationChannel ch = new NotificationChannel(CHANNEL, getString(R.string.lock_channel), NotificationManager.IMPORTANCE_MIN);
            ch.setShowBadge(false);
            NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
            nm.createNotificationChannel(ch);
            Notification n = new Notification.Builder(this, CHANNEL)
                    .setContentTitle("ControlPS")
                    .setContentText("TV blok")
                    .setSmallIcon(android.R.drawable.ic_lock_idle_lock)
                    .setOngoing(true)
                    .build();
            startForeground(7, n);
        }
    }

    private boolean canOverlay() {
        return Build.VERSION.SDK_INT < 23 || Settings.canDrawOverlays(this);
    }

    private void showOverlay() {
        if (shown && overlay != null) {
            return;
        }
        if (!canOverlay()) {
            Intent i = new Intent(this, LockActivity.class);
            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
            startActivity(i);
            shown = true;
            return;
        }
        hideOverlay();
        binder = new LockScreenBinder(this);
        overlay = binder.root;
        overlay.setOnKeyListener((v, keyCode, event) -> true);
        overlay.setFocusable(true);
        overlay.setFocusableInTouchMode(true);
        int type = Build.VERSION.SDK_INT >= 26
                ? WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
                : WindowManager.LayoutParams.TYPE_SYSTEM_ERROR;
        WindowManager.LayoutParams lp = new WindowManager.LayoutParams(
                WindowManager.LayoutParams.MATCH_PARENT,
                WindowManager.LayoutParams.MATCH_PARENT,
                type,
                WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN
                        | WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS
                        | WindowManager.LayoutParams.FLAG_FULLSCREEN
                        | WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON
                        | WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED
                        | WindowManager.LayoutParams.FLAG_HARDWARE_ACCELERATED,
                PixelFormat.TRANSLUCENT);
        lp.gravity = Gravity.TOP | Gravity.START;
        lp.buttonBrightness = 0f;
        try {
            wm.addView(overlay, lp);
            binder.start();
            overlay.requestFocus();
            overlay.setOnKeyListener((View v, int keyCode, KeyEvent event) -> true);
            shown = true;
        } catch (Exception e) {
            Intent i = new Intent(this, LockActivity.class);
            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(i);
            shown = true;
        }
    }

    private void hideOverlay() {
        if (overlay != null && wm != null) {
            try {
                wm.removeViewImmediate(overlay);
            } catch (Exception ignored) {
            }
        }
        if (binder != null) {
            binder.stop();
            binder = null;
        }
        overlay = null;
        shown = false;
    }
}
