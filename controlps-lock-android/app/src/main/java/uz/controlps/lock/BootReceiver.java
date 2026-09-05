package uz.controlps.lock;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/** TV yonganda / Wi‑Fi: PC dan so'raladi. START bo'lsa blok ochilmaydi. */
public class BootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        LockOverlayService.ensureWatching(context);
    }
}
