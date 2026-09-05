package uz.controlps.lock;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

public class OverlayReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        if (intent == null) {
            return;
        }
        String a = intent.getAction();
        if (LockOverlayService.ACTION_HIDE.equals(a)) {
            LockOverlayService.ensureRunning(context, false);
        } else if (LockOverlayService.ACTION_WATCH.equals(a)) {
            LockOverlayService.ensureWatching(context);
        } else {
            LockOverlayService.ensureRunning(context, true);
        }
    }
}
