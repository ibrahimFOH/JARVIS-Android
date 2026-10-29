package com.stagepulse.jarvis;

import org.json.JSONObject;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;

public final class BridgeClient {
    public static final class Result {
        public final boolean success;
        public final String response;
        public final String error;
        public final boolean requiresConfirmation;
        Result(boolean ok, String text, String err, boolean confirm) {
            success = ok; response = text; error = err; requiresConfirmation = confirm;
        }
    }

    private BridgeClient() {}

    private static String validateBaseUrl(String raw) throws IOException {
        try {
            URL url = new URL(raw.trim());
            if (url.getUserInfo() != null || url.getQuery() != null || url.getRef() != null) {
                throw new IOException("Windows host adresinde kullanıcı bilgisi, sorgu veya fragment kullanılamaz.");
            }
            String path = url.getPath();
            if (path != null && !path.isEmpty() && !"/".equals(path)) {
                throw new IOException("Yalnızca host kök adresini gir; /api yolu otomatik eklenir.");
            }
            String protocol = url.getProtocol().toLowerCase(java.util.Locale.ROOT);
            if ("https".equals(protocol)) {
                if (url.getPort() == 0 || url.getPort() > 65535) {
                    throw new IOException("Windows host portu geçersiz.");
                }
                return raw.trim().replaceAll("/+$", "");
            }
            if (!"http".equals(protocol) || !isPrivateIpv4(url.getHost())) {
                throw new IOException("Düz HTTP yalnızca özel IPv4 LAN adresleriyle kullanılabilir. Uzak host için HTTPS kullan.");
            }
            if (url.getPort() < 1 || url.getPort() > 65535) {
                throw new IOException("LAN bağlantısı için geçerli port belirt; varsayılan port 8765.");
            }
            return raw.trim().replaceAll("/+$", "");
        } catch (MalformedURLException e) {
            throw new IOException("Windows host adresi geçersiz.", e);
        }
    }

    private static boolean isPrivateIpv4(String host) {
        String[] parts = host.split("\\.", -1);
        if (parts.length != 4) return false;
        int[] octets = new int[4];
        try {
            for (int i = 0; i < 4; i++) {
                if (parts[i].isEmpty() || (parts[i].length() > 1 && parts[i].startsWith("0"))) return false;
                octets[i] = Integer.parseInt(parts[i]);
                if (octets[i] < 0 || octets[i] > 255) return false;
            }
        } catch (NumberFormatException e) {
            return false;
        }
        return octets[0] == 10
                || (octets[0] == 172 && octets[1] >= 16 && octets[1] <= 31)
                || (octets[0] == 192 && octets[1] == 168)
                || (octets[0] == 127 && octets[1] == 0 && octets[2] == 0 && octets[3] == 1);
    }

    public static Result command(String baseUrl, String token, String command) throws Exception {
        String base = validateBaseUrl(baseUrl);
        URL url = new URL(base + "/api/command");
        HttpURLConnection c = (HttpURLConnection) url.openConnection();
        try {
            c.setInstanceFollowRedirects(false);
            c.setRequestMethod("POST");
            c.setConnectTimeout(4000);
            c.setReadTimeout(120000);
            c.setDoOutput(true);
            c.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            c.setRequestProperty("Accept", "application/json");
            c.setRequestProperty("Authorization", "Bearer " + token.trim());

            JSONObject payload = new JSONObject();
            payload.put("command", command);
            byte[] bytes = payload.toString().getBytes(StandardCharsets.UTF_8);
            c.setFixedLengthStreamingMode(bytes.length);
            try (OutputStream out = c.getOutputStream()) { out.write(bytes); }

            int status = c.getResponseCode();
            if (status >= 300 && status < 400) {
                throw new IOException("Windows bridge yönlendirme yanıtı reddedildi; kimlik doğrulama token'ı başka adrese aktarılmadı.");
            }
            InputStream stream = status >= 200 && status < 300
                    ? c.getInputStream() : c.getErrorStream();
            StringBuilder body = new StringBuilder();
            if (stream != null) {
                try (BufferedReader reader = new BufferedReader(
                        new InputStreamReader(stream, StandardCharsets.UTF_8))) {
                    String line;
                    while ((line = reader.readLine()) != null) body.append(line);
                }
            }
            if (status < 200 || status >= 300) {
                String error = "HTTP " + status;
                try {
                    if (body.length() > 0) error = new JSONObject(body.toString()).optString("error", error);
                } catch (Exception ignored) { }
                throw new IOException(error);
            }
            try {
                JSONObject json = new JSONObject(body.toString());
                return new Result(json.optBoolean("success", false),
                        json.optString("response", "Windows JARVIS yanıt vermedi."),
                        json.optString("error", ""), json.optBoolean("requires_confirmation", false));
            } catch (Exception e) {
                throw new IOException("Windows bridge geçerli JSON yanıtı döndürmedi.", e);
            }
        } finally {
            c.disconnect();
        }
    }

    public static boolean health(String baseUrl, String token) throws Exception {
        String base = validateBaseUrl(baseUrl);
        HttpURLConnection c = (HttpURLConnection) new URL(base + "/api/health").openConnection();
        try {
            c.setInstanceFollowRedirects(false);
            c.setRequestMethod("GET");
            c.setConnectTimeout(2500);
            c.setReadTimeout(2500);
            c.setRequestProperty("Authorization", "Bearer " + token.trim());
            return c.getResponseCode() == 200;
        } finally {
            c.disconnect();
        }
    }
}
