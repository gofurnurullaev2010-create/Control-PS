package uz.controlps.lock;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.Charset;

/**
 * PC: /controlps/tv-should-lock
 * 1 = blok; 0 = START (PS). Tarmoq xatosida oxirgi javob saqlanadi.
 */
public final class LockGate {
    private static final File URL_FILE = new File("/sdcard/controlps_lock_gate.url");

    private LockGate() {}

    public static Boolean pollShouldLock() {
        String url = readUrl();
        if (url == null || url.isEmpty()) {
            return Boolean.TRUE;
        }
        HttpURLConnection c = null;
        try {
            c = (HttpURLConnection) new URL(url.trim()).openConnection();
            c.setConnectTimeout(1500);
            c.setReadTimeout(1500);
            c.setUseCaches(false);
            c.setInstanceFollowRedirects(false);
            int code = c.getResponseCode();
            InputStream in = code >= 400 ? c.getErrorStream() : c.getInputStream();
            if (in == null) {
                in = c.getInputStream();
            }
            String body = "";
            if (in != null) {
                BufferedReader br = new BufferedReader(new InputStreamReader(in, Charset.forName("UTF-8")));
                String line = br.readLine();
                br.close();
                body = line == null ? "" : line.trim();
            }
            if (body.startsWith("0")) {
                return Boolean.FALSE;
            }
            if (body.startsWith("1")) {
                return Boolean.TRUE;
            }
            if (code == 200) {
                return Boolean.TRUE;
            }
            return null;
        } catch (Exception e) {
            return null;
        } finally {
            if (c != null) {
                c.disconnect();
            }
        }
    }

    private static String readUrl() {
        if (!URL_FILE.isFile()) {
            return null;
        }
        try {
            FileInputStream in = new FileInputStream(URL_FILE);
            byte[] buf = new byte[512];
            int n = in.read(buf);
            in.close();
            if (n <= 0) {
                return null;
            }
            return new String(buf, 0, n, Charset.forName("UTF-8")).trim();
        } catch (Exception e) {
            return null;
        }
    }
}
