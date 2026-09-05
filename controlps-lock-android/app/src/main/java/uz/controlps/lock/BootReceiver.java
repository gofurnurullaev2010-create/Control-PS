package uz.controlps.lock;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/** TV yonganda / Wi‑Fi ulananda PC dan holat so'raladi (STOP bo'lsa tez blok). */
public class BootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        LockOverlayService.ensureRunning(context, true);
    }
}
