package com.shq.mediadownloader;

import android.content.ContentValues;
import android.content.Context;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.provider.MediaStore;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;

@CapacitorPlugin(name = "Downloader")
public class DownloaderPlugin extends Plugin {

    @PluginMethod
    public void save(PluginCall call) {
        String url = call.getString("url");
        String filename = call.getString("filename", "media");
        Boolean isVideoObj = call.getBoolean("isVideo", false);
        String referer = call.getString("referer");

        if (url == null) {
            call.reject("url is required");
            return;
        }
        boolean isVideo = isVideoObj != null && isVideoObj;

        final String fUrl = url;
        final String fFilename = filename;
        final boolean fIsVideo = isVideo;
        final String fReferer = referer;

        // Run on background thread; resolve/reject on main via getActivity().runOnUiThread
        new Thread(() -> {
            try {
                doSave(fUrl, fFilename, fIsVideo, fReferer);
                getActivity().runOnUiThread(() -> call.resolve(new JSObject()));
            } catch (final Exception e) {
                getActivity().runOnUiThread(() -> call.reject("Download failed: " + e.getMessage()));
            }
        }).start();
    }

    private void doSave(String url, String filename, boolean isVideo, String referer) throws Exception {
        Context ctx = getContext();

        // Download bytes via HttpURLConnection (supports Referer header for bilibili etc.)
        URL u = new URL(url);
        HttpURLConnection conn = (HttpURLConnection) u.openConnection();
        conn.setInstanceFollowRedirects(true);
        conn.setConnectTimeout(15000);
        conn.setReadTimeout(30000);
        conn.setRequestProperty("User-Agent",
                "Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36");
        if (referer != null && !referer.isEmpty()) {
            conn.setRequestProperty("Referer", referer);
        }
        conn.connect();
        int code = conn.getResponseCode();
        if (code < 200 || code >= 300) {
            throw new Exception("HTTP " + code);
        }
        InputStream body = conn.getInputStream();

        String mime = isVideo ? "video/mp4" : "image/jpeg";
        String ext = isVideo ? "mp4" : "jpg";

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            // Android 10+: MediaStore, no permission needed
            ContentValues vals = new ContentValues();
            vals.put(MediaStore.MediaColumns.DISPLAY_NAME, filename);
            vals.put(MediaStore.MediaColumns.MIME_TYPE, mime);
            if (isVideo) {
                vals.put(MediaStore.Video.Media.RELATIVE_PATH, Environment.DIRECTORY_MOVIES + "/MediaDownloader");
            } else {
                vals.put(MediaStore.Images.Media.RELATIVE_PATH, Environment.DIRECTORY_PICTURES + "/MediaDownloader");
            }
            Uri collection = isVideo
                    ? MediaStore.Video.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY)
                    : MediaStore.Images.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY);
            Uri item = ctx.getContentResolver().insert(collection, vals);
            if (item == null) throw new Exception("MediaStore insert failed");
            OutputStream os = ctx.getContentResolver().openOutputStream(item);
            if (os == null) throw new Exception("Cannot open output stream");
            try (InputStream is = body; OutputStream out = os) {
                pipe(is, out);
            }
        } else {
            // Android 9 and below: write to public dir (manifest declares WRITE_EXTERNAL_STORAGE)
            File baseDir = Environment.getExternalStoragePublicDirectory(
                    isVideo ? Environment.DIRECTORY_MOVIES : Environment.DIRECTORY_PICTURES);
            File dir = new File(baseDir, "MediaDownloader");
            if (!dir.exists() && !dir.mkdirs()) throw new Exception("Cannot create dir");
            File out = new File(dir, filename + "." + ext);
            try (InputStream is = body; FileOutputStream fos = new FileOutputStream(out)) {
                pipe(is, fos);
            }
            // Trigger media scan so it shows in gallery
            android.media.MediaScannerConnection.scanFile(ctx,
                    new String[]{out.getAbsolutePath()}, new String[]{mime}, null);
        }
    }

    private void pipe(InputStream is, OutputStream os) throws Exception {
        byte[] buf = new byte[8192];
        int n;
        while ((n = is.read(buf)) > 0) {
            os.write(buf, 0, n);
        }
        os.flush();
    }
}
