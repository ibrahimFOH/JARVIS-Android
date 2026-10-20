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

    public static Result command(String baseUrl, String token, String command) throws Exception {
        String base = baseUrl.trim().replaceAll("/+$", "");
        URL url = new URL(base + "/api/command");
        HttpURLConnection c = (HttpURLConnection) url.openConnection();
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
        InputStream stream = status >= 200 && status < 400 ? c.getInputStream() : c.getErrorStream();
        StringBuilder body = new StringBuilder();
        if (stream != null) {
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(stream, StandardCharsets.UTF_8))) {
                String line;
                while ((line = reader.readLine()) != null) body.append(line);
            }
        }
        c.disconnect();
        JSONObject json = new JSONObject(body.toString());
        if (status < 200 || status >= 300) {
            throw new IOException(json.optString("error", "HTTP " + status));
        }
        return new Result(json.optBoolean("success", false),
                json.optString("response", "Windows JARVIS yanıt vermedi."),
                json.optString("error", ""), json.optBoolean("requires_confirmation", false));
    }

    public static boolean health(String baseUrl, String token) throws Exception {
        String base = baseUrl.trim().replaceAll("/+$", "");
        HttpURLConnection c = (HttpURLConnection) new URL(base + "/api/health").openConnection();
        c.setRequestMethod("GET");
        c.setConnectTimeout(2500);
        c.setReadTimeout(2500);
        c.setRequestProperty("Authorization", "Bearer " + token.trim());
        int code = c.getResponseCode();
        c.disconnect();
        return code == 200;
    }
}
