package com.stagepulse.jarvis;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedInputStream;
import java.io.BufferedReader;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Locale;

/** Checks public signed GitHub releases and verifies downloaded APK bytes before installation. */
public final class UpdateManager {
    private static final String RELEASE_API =
            "https://api.github.com/repos/ibrahimFOH/JARVIS-Android/releases/latest";
    private static final int CONNECT_TIMEOUT_MS = 10000;
    private static final int READ_TIMEOUT_MS = 30000;
    private static final long MAX_APK_BYTES = 300L * 1024L * 1024L;

    public static final class UpdateInfo {
        public final String packageName;
        public final int versionCode;
        public final String versionName;
        public final String apkUrl;
        public final String sha256;
        public final String notes;
        public final String tagName;

        private UpdateInfo(JSONObject json, String tagName) throws Exception {
            packageName = json.getString("packageName");
            versionCode = json.getInt("versionCode");
            versionName = json.getString("versionName");
            apkUrl = json.getString("apkUrl");
            sha256 = json.getString("sha256").toLowerCase(Locale.ROOT);
            notes = json.optString("notes", "Stagepulse JARVIS güncellemesi.");
            this.tagName = tagName;

            if (!tagName.matches("v\\d+\\.\\d+\\.\\d+") || !tagName.equals("v" + versionName)
                    || !tagName.equals(json.optString("tagName", ""))) {
                throw new SecurityException("GitHub Release etiketi ile update.json sürüm bilgileri uyuşmuyor.");
            }
            if (!isTrustedReleaseAsset(apkUrl, tagName)) {
                throw new SecurityException("APK adresi bu sürümün güvenilir GitHub Release adresi değil.");
            }
            if (!sha256.matches("[a-f0-9]{64}")) {
                throw new IllegalArgumentException("Güncelleme SHA-256 değeri geçersiz.");
            }
            if (versionCode < 1 || versionName.trim().isEmpty()) {
                throw new IllegalArgumentException("Güncelleme sürüm bilgisi geçersiz.");
            }
        }
    }

    public UpdateInfo checkLatest(int installedVersionCode) throws Exception {
        JSONObject release = getJson(RELEASE_API);
        String tagName = release.optString("tag_name", "");
        if (!tagName.matches("v\\d+\\.\\d+\\.\\d+")) {
            throw new SecurityException("GitHub Release etiketi vMAJOR.MINOR.PATCH biçiminde değil.");
        }
        JSONArray assets = release.optJSONArray("assets");
        if (assets == null) throw new IllegalStateException("Release dosyaları bulunamadı.");

        String metadataUrl = null;
        for (int i = 0; i < assets.length(); i++) {
            JSONObject asset = assets.optJSONObject(i);
            if (asset != null && "update.json".equals(asset.optString("name"))) {
                metadataUrl = asset.optString("browser_download_url", null);
                break;
            }
        }
        if (metadataUrl == null || metadataUrl.trim().isEmpty()) {
            throw new IllegalStateException("Son yayın update.json içermiyor.");
        }
        if (!isTrustedReleaseAsset(metadataUrl, tagName)) {
            throw new SecurityException("Güncelleme bilgisi bu sürümün beklenen GitHub Release adresinden gelmiyor.");
        }

        UpdateInfo info = new UpdateInfo(getJson(metadataUrl), tagName);
        if (!"com.stagepulse.jarvis".equals(info.packageName)) {
            throw new SecurityException("Güncelleme paketi bu JARVIS uygulamasına ait değil.");
        }
        return info.versionCode > installedVersionCode ? info : null;
    }

    public File downloadAndVerify(UpdateInfo info, File destination) throws Exception {
        if (info == null) throw new IllegalArgumentException("Güncelleme bilgisi boş.");
        HttpURLConnection connection = open(info.apkUrl);
        try {
            int status = connection.getResponseCode();
            if (status < 200 || status >= 300) {
                throw new IllegalStateException("APK indirme isteği HTTP " + status + " döndürdü.");
            }
            validateFinalUrl(connection.getURL());
            long expectedLength = connection.getContentLengthLong();
            if (expectedLength > MAX_APK_BYTES) {
                throw new IllegalStateException("APK beklenenden büyük; indirme durduruldu.");
            }
            File parent = destination.getParentFile();
            if (parent != null && !parent.exists() && !parent.mkdirs()) {
                throw new IllegalStateException("Güncelleme klasörü oluşturulamadı.");
            }

            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            long total = 0;
            try (InputStream input = new BufferedInputStream(connection.getInputStream());
                 OutputStream output = new FileOutputStream(destination)) {
                byte[] buffer = new byte[65536];
                int count;
                while ((count = input.read(buffer)) != -1) {
                    total += count;
                    if (total > MAX_APK_BYTES) {
                        throw new IllegalStateException("APK sınırlandırılmış boyutu aştı.");
                    }
                    digest.update(buffer, 0, count);
                    output.write(buffer, 0, count);
                }
            } catch (Exception e) {
                // Do not leave a partial APK that could later be installed.
                //noinspection ResultOfMethodCallIgnored
                destination.delete();
                throw e;
            }

            String actual = toHex(digest.digest());
            if (!actual.equalsIgnoreCase(info.sha256) || total == 0) {
                //noinspection ResultOfMethodCallIgnored
                destination.delete();
                throw new SecurityException("İndirilen APK bütünlük kontrolünü geçemedi.");
            }
            return destination;
        } finally {
            connection.disconnect();
        }
    }

    private static JSONObject getJson(String address) throws Exception {
        HttpURLConnection connection = open(address);
        try {
            int status = connection.getResponseCode();
            if (status < 200 || status >= 300) {
                throw new IllegalStateException("Güncelleme sunucusu HTTP " + status + " döndürdü.");
            }
            validateFinalUrl(connection.getURL());
            StringBuilder body = new StringBuilder();
            try (BufferedReader reader = new BufferedReader(
                    new InputStreamReader(connection.getInputStream(), StandardCharsets.UTF_8))) {
                String line;
                while ((line = reader.readLine()) != null) body.append(line);
            }
            return new JSONObject(body.toString());
        } finally {
            connection.disconnect();
        }
    }

    private static boolean isTrustedReleaseAsset(String address, String tagName) throws Exception {
        URL url = new URL(address);
        String prefix = "/ibrahimFOH/JARVIS-Android/releases/download/" + tagName + "/";
        String path = url.getPath();
        String assetName = path.startsWith(prefix) ? path.substring(prefix.length()) : "";
        return "https".equalsIgnoreCase(url.getProtocol())
                && "github.com".equalsIgnoreCase(url.getHost())
                && url.getUserInfo() == null
                && (url.getPort() == -1 || url.getPort() == 443)
                && url.getQuery() == null
                && url.getRef() == null
                && !assetName.isEmpty()
                && !assetName.contains("/")
                && !assetName.contains("..")
                && !assetName.contains("%");
    }

    private static void validateFinalUrl(URL url) throws Exception {
        String host = url.getHost().toLowerCase(Locale.ROOT);
        boolean trustedHost = "github.com".equals(host)
                || "api.github.com".equals(host)
                || host.endsWith(".githubusercontent.com");
        if (!"https".equalsIgnoreCase(url.getProtocol())
                || url.getUserInfo() != null
                || (url.getPort() != -1 && url.getPort() != 443)
                || !trustedHost) {
            throw new SecurityException("GitHub güncellemesi güvenilir olmayan bir adrese yönlendirildi.");
        }
    }

    private static HttpURLConnection open(String address) throws Exception {
        URL url = new URL(address);
        if (!"https".equalsIgnoreCase(url.getProtocol())) {
            throw new SecurityException("Güncelleme bağlantısı HTTPS olmalı.");
        }
        HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        connection.setRequestMethod("GET");
        connection.setConnectTimeout(CONNECT_TIMEOUT_MS);
        connection.setReadTimeout(READ_TIMEOUT_MS);
        connection.setInstanceFollowRedirects(true);
        connection.setRequestProperty("Accept", "application/vnd.github+json, application/json");
        connection.setRequestProperty("User-Agent", "Stagepulse-JARVIS-Android-Updater");
        return connection;
    }

    private static String toHex(byte[] bytes) {
        StringBuilder result = new StringBuilder(bytes.length * 2);
        for (byte value : bytes) result.append(String.format(Locale.ROOT, "%02x", value & 0xff));
        return result.toString();
    }
}
