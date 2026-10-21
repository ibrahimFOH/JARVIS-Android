package com.stagepulse.jarvis;

import org.json.JSONArray;
import org.json.JSONObject;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;

/** Minimal Gemini text API client. The key is supplied by the user at runtime. */
public final class GeminiClient {
    private GeminiClient() {}

    public static String ask(String apiKey, String model, String prompt) throws Exception {
        if (apiKey == null || apiKey.trim().isEmpty()) throw new IOException("Gemini API anahtarı ayarlanmamış.");
        String selected = (model == null || model.trim().isEmpty()) ? "gemini-2.5-flash" : model.trim();
        URL url = new URL("https://generativelanguage.googleapis.com/v1beta/models/"
                + URLEncoder.encode(selected, "UTF-8") + ":generateContent?key="
                + URLEncoder.encode(apiKey.trim(), "UTF-8"));
        HttpURLConnection c = (HttpURLConnection) url.openConnection();
        c.setRequestMethod("POST");
        c.setConnectTimeout(10000);
        c.setReadTimeout(60000);
        c.setDoOutput(true);
        c.setRequestProperty("Content-Type", "application/json; charset=utf-8");
        JSONObject body = new JSONObject();
        JSONObject part = new JSONObject().put("text", prompt);
        JSONArray parts = new JSONArray().put(part);
        body.put("contents", new JSONArray().put(new JSONObject().put("role", "user").put("parts", parts)));
        body.put("systemInstruction", new JSONObject().put("parts",
                new JSONArray().put(new JSONObject().put("text", "Sen JARVIS'sin. Türkçe konuş; kısa, doğru ve işe yarar cevap ver."))));
        byte[] bytes = body.toString().getBytes(StandardCharsets.UTF_8);
        c.setFixedLengthStreamingMode(bytes.length);
        try (OutputStream out = c.getOutputStream()) { out.write(bytes); }
        int code = c.getResponseCode();
        InputStream stream = code >= 200 && code < 300 ? c.getInputStream() : c.getErrorStream();
        StringBuilder response = new StringBuilder();
        if (stream != null) try (BufferedReader reader = new BufferedReader(new InputStreamReader(stream, StandardCharsets.UTF_8))) {
            String line; while ((line = reader.readLine()) != null) response.append(line);
        }
        c.disconnect();
        JSONObject json = new JSONObject(response.toString());
        if (code < 200 || code >= 300) throw new IOException("Gemini API HTTP " + code + ": " + json.optString("error", response.toString()));
        JSONArray candidates = json.optJSONArray("candidates");
        if (candidates == null || candidates.length() == 0) throw new IOException("Gemini boş yanıt döndürdü.");
        return candidates.getJSONObject(0).getJSONObject("content").getJSONArray("parts").getJSONObject(0).optString("text", "Yanıt metni bulunamadı.");
    }
}
