package uz.controlps.lock;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.view.KeyEvent;
import android.view.LayoutInflater;
import android.view.View;
import android.widget.ImageView;
import android.widget.TextView;

import java.io.File;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.TimeZone;

/** RAPTOR logo + O'zbekiston soati. Pult tugmalarini yutadi. */
public final class LockScreenBinder {
    private static final TimeZone UZ = TimeZone.getTimeZone("Asia/Tashkent");
    private static final File SD_BG = new File("/sdcard/lock_screen_bg.png");
    private static final File SD_BG2 = new File("/sdcard/raptor_logo.png");

    public final View root;
    private final TextView clock;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final SimpleDateFormat fmt = new SimpleDateFormat("HH:mm:ss", Locale.US);
    private boolean running;

    public LockScreenBinder(Context context) {
        fmt.setTimeZone(UZ);
        root = LayoutInflater.from(context).inflate(R.layout.lock_screen, null);
        clock = root.findViewById(R.id.lock_clock);
        ImageView logo = root.findViewById(R.id.lock_logo);
        Bitmap bmp = loadLogo();
        if (bmp != null) {
            logo.setImageBitmap(bmp);
        }
        root.setFocusable(true);
        root.setFocusableInTouchMode(true);
        root.setOnKeyListener((v, keyCode, event) -> true);
        root.setOnClickListener(v -> { });
    }

    private static Bitmap loadLogo() {
        for (File f : new File[]{SD_BG, SD_BG2}) {
            if (f.isFile()) {
                Bitmap bmp = BitmapFactory.decodeFile(f.getAbsolutePath());
                if (bmp != null) {
                    return bmp;
                }
            }
        }
        return null;
    }

    public void start() {
        running = true;
        tick();
    }

    public void stop() {
        running = false;
        handler.removeCallbacksAndMessages(null);
    }

    public boolean consumeKey(int keyCode, KeyEvent event) {
        return true;
    }

    private void tick() {
        if (!running) {
            return;
        }
        clock.setText(fmt.format(new Date()));
        long delay = 1000L - (SystemClock.uptimeMillis() % 1000L);
        handler.postDelayed(this::tick, delay);
    }
}
