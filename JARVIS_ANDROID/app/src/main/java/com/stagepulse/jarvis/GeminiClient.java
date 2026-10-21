package com.stagepulse.jarvis;

import android.util.Base64;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;

public final class GeminiClient {
    private GeminiClient() {}
    private static URL endpoint(String key, String model) throws Exception {
        String m = (model == null || model.trim().isEmpty()) ? "gemini-2.5-flash" : model.trim();
        return new URL("https://generativelanguage.googleapis.com/v1beta/models/" + URLEncoder.encode(m, "UTF-8") + ":generateContent?key=" + URLEncoder.encode(key.trim(), "UTF-8"));
    }
    private static String post(URL url, JSONObject body) throws Exception {
        HttpURLConnection c = (HttpURLConnection) url.openConnection();
        c.setRequestMethod("POST"); c.setConnectTimeout(10000); c.setReadTimeout(90000); c.setDoOutput(true);
        c.setRequestProperty("Content-Type", "application/json; charset=utf-8");
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
        JSONObject candidate = candidates.getJSONObject(0);
        JSONArray parts = candidate.getJSONObject("content").optJSONArray("parts");
        StringBuilder text = new StringBuilder();
        if (parts != null) for (int i = 0; i < parts.length(); i++) text.append(parts.getJSONObject(i).optString("text", ""));
        return text.toString().isEmpty() ? json.toString() : text.toString();
    }
    public static String ask(String apiKey, String model, String prompt) throws Exception {
        if (apiKey == null || apiKey.trim().isEmpty()) throw new IOException("Gemini API anahtarı ayarlanmamış.");
        JSONObject body = new JSONObject();
        body.put("systemInstruction", new JSONObject().put("parts", new JSONArray().put(new JSONObject().put("text", "Sen JARVIS'sin. Türkçe konuş; kısa, doğru ve işe yarar cevap ver."))));
        body.put("contents", new JSONArray().put(new JSONObject().put("role", "user").put("parts", new JSONArray().put(new JSONObject().put("text", prompt)))));
        return post(endpoint(apiKey, model), body);
    }
    public static String analyzeImage(String apiKey, String model, String prompt, byte[] image, String mimeType) throws Exception {
        if (apiKey == null || apiKey.trim().isEmpty()) throw new IOException("Gemini API anahtarı ayarlanmamış.");
        JSONObject inline = new JSONObject().put("mime_type", mimeType).put("data", Base64.encodeToString(image, Base64.NO_WRAP));
        JSONArray parts = new JSONArray().put(new JSONObject().put("text", prompt)).put(new JSONObject().put("inline_data", inline));
        return post(endpoint(apiKey, model), new JSONObject().put("contents", new JSONArray().put(new JSONObject().put("role", "user").put("parts", parts))));
    }
    public static byte[] generateImage(String apiKey, String model, String prompt) throws Exception {
        if (apiKey == null || apiKey.trim().isEmpty()) throw new IOException("Gemini API anahtarı ayarlanmamış.");
        URL url = endpoint(apiKey, (model == null || model.trim().isEmpty()) ? "gemini-2.5-flash-image" : model);
        JSONObject body = new JSONObject().put("contents", new JSONArray().put(new JSONObject().put("role", "user").put("parts", new JSONArray().put(new JSONObject().put("text", prompt)))));
        body.put("generationConfig", new JSONObject().put("responseModalities", new JSONArray().put("TEXT").put("IMAGE")));
        JSONObject json = new JSONObject(post(url, body));
        JSONArray candidates = json.optJSONArray("candidates");
        if (candidates != null) for (int i = 0; i < candidates.length(); i++) {
            JSONArray parts = candidates.getJSONObject(i).getJSONObject("content").optJSONArray("parts");
            if (parts != null) for (int j = 0; j < parts.length(); j++) {
                JSONObject part = parts.getJSONObject(j);
                JSONObject data = part.optJSONObject("inlineData");
                if (data == null) data = part.optJSONObject("inline_data");
                if (data != null && data.has("data")) return Base64.decode(data.getString("data"), Base64.DEFAULT);
            }
        }
        throw new IOException("Gemini yanıtında görsel yok. Görsel üretimini destekleyen model seç.");
    }
}