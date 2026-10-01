package com.stagepulse.jarvis;

import org.json.JSONObject;
import java.io.*;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

public final class BridgeClient {
    private BridgeClient() {}

    public static JSONObject health(String baseUrl) throws Exception {
        return request(baseUrl, "/health", null, null, "GET");
    }

    public static JSONObject chat(String baseUrl, String token, String command) throws Exception {
        JSONObject body = new JSONObject();
        body.put("command", command);
        return request(baseUrl, "/api/chat", token, body.toString(), "POST");
    }

    private static JSONObject request(String baseUrl, String path, String token, String body, String method) throws Exception {
        String clean = baseUrl.trim();
        if (clean.endsWith("/")) clean = clean.substring(0, clean.length() - 1);
        HttpURLConnection c = (HttpURLConnection) new URL(clean + path).openConnection();
        c.setRequestMethod(method);
        c.setConnectTimeout(4000);
        c.setReadTimeout(25000);
        c.setUseCaches(false);
        c.setRequestProperty("Accept", "application/json");
        if (token != null) c.setRequestProperty("X-JARVIS-TOKEN", token);
        if (body != null) {
            c.setDoOutput(true);
            c.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
            c.setFixedLengthStreamingMode(bytes.length);
            try (OutputStream out = c.getOutputStream()) { out.write(bytes); }
        }
        int status = c.getResponseCode();
        InputStream in = status >= 200 && status < 400 ? c.getInputStream() : c.getErrorStream();
        String response = readAll(in);
        c.disconnect();
        JSONObject json;
        try { json = new JSONObject(response); }
        catch (Exception e) { json = new JSONObject().put("ok", false).put("error", response); }
        json.put("http_status", status);
        return json;
    }

    private static String readAll(InputStream in) throws Exception {
        if (in == null) return "";
        try (InputStream input = in; ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buf = new byte[4096]; int n;
            while ((n = input.read(buf)) != -1) out.write(buf, 0, n);
            return out.toString(StandardCharsets.UTF_8);
        }
    }
}
