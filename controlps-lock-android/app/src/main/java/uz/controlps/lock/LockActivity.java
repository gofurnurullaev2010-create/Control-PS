package uz.controlps.lock;

import android.app.Activity;
import android.os.Bundle;
import android.view.KeyEvent;
import android.view.WindowManager;

/** To'liq ekran blok: pult ocholmaydi. */
public class LockActivity extends Activity {
    private LockScreenBinder binder;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().addFlags(
                WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON
                        | WindowManager.LayoutParams.FLAG_FULLSCREEN
                        | WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED
                        | WindowManager.LayoutParams.FLAG_DISMISS_KEYGUARD);
        binder = new LockScreenBinder(this);
        setContentView(binder.root);
        binder.start();
        binder.root.requestFocus();
        LockOverlayService.ensureRunning(this, true);
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (binder != null) {
            binder.root.requestFocus();
        }
    }

    @Override
    protected void onDestroy() {
        if (binder != null) {
            binder.stop();
        }
        super.onDestroy();
    }

    @Override
    public void onBackPressed() {
        // bloklangan
    }

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        return true;
    }

    @Override
    public boolean dispatchKeyEvent(KeyEvent event) {
        return true;
    }
}
