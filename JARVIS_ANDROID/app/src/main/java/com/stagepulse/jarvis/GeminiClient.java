package com.stagepulse.jarvis;

import android.util.Base64;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;

/** Gemini REST client. API keys are sent as headers, not embedded in request URLs. */
public final class GeminiClient {
    private GeminiClient() {}

    private static URL endpoint(String model) throws Exception {
        String selected = (model == null || model.trim().isEmpty()) ? "gemini-2.5-flash" : model.trim();
        return new URL("https://generativelanguage.googleapis.com/v1beta/models/"
                + URLEncoder.encode(selected, "UTF-8") + ":generateContent");
    }

    private static JSONObject post(String apiKey, String model, JSONObject body) throws Exception {
        if (apiKey == null || apiKey.trim().isEmpty()) throw new IOException("Gemini API anahtarı ayarlanmamış.");
        HttpURLConnection c = (HttpURLConnection) endpoint(model).openConnection();
        c.setRequestMethod("POST");
        c.setConnectTimeout(15000);
        c.setReadTimeout(90000);
        c.setDoOutput(true);
        c.setRequestProperty("Content-Type", "application/json; charset=utf-8");
        c.setRequestProperty("x-goog-api-key", apiKey.trim());
        byte[] bytes = body.toString().getBytes(StandardCharsets.UTF_8);
        c.setFixedLengthStreamingMode(bytes.length);
        try (OutputStream out = c.getOutputStream()) { out.write(bytes); }

        int code = c.getResponseCode();
        InputStream stream = code >= 200 && code < 300 ? c.getInputStream() : c.getErrorStream();
        StringBuilder response = new StringBuilder();
        if (stream != null) {
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(stream, StandardCharsets.UTF_8))) {
                String line;
                while ((line = reader.readLine()) != null) response.append(line);
            }
        }
        c.disconnect();

        JSONObject json;
        try { json = new JSONObject(response.toString()); }
        catch (Exception e) { throw new IOException("Gemini yanıtı okunamadı (HTTP " + code + ")."); }
        if (code < 200 || code >= 300) {
            JSONObject error = json.optJSONObject("error");
            throw new IOException("Gemini API HTTP " + code + ": "
                    + (error == null ? response.toString() : error.optString("message", response.toString())));
        }
        if (!json.has("candidates") || json.optJSONArray("candidates") == null
                || json.optJSONArray("candidates").length() == 0) {
            throw new IOException("Gemini boş yanıt döndürdü veya isteği güvenlik nedeniyle engelledi.");
        }
        return json;
    }

    private static String textFrom(JSONObject json) throws Exception {
        JSONArray candidates = json.optJSONArray("candidates");
        StringBuilder answer = new StringBuilder();
        if (candidates != null) for (int i = 0; i < candidates.length(); i++) {
            JSONObject content = candidates.getJSONObject(i).optJSONObject("content");
            if (content == null) continue;
            JSONArray parts = content.optJSONArray("parts");
            if (parts == null) continue;
            for (int j = 0; j < parts.length(); j++) answer.append(parts.getJSONObject(j).optString("text", ""));
        }
        if (answer.length() == 0) throw new IOException("Gemini metin yanıtı döndürmedi.");
        return answer.toString().trim();
    }

    private static JSONObject baseRequest(String prompt) throws Exception {
        JSONObject body = new JSONObject();
        body.put("systemInstruction", new JSONObject().put("parts",
                new JSONArray().put(new JSONObject().put("text",
                        "Sen JARVIS'sin. Türkçe konuş; kısa, doğru ve işe yarar cevap ver."))));
        body.put("contents", new JSONArray().put(new JSONObject().put("role", "user")
                .put("parts", new JSONArray().put(new JSONObject().put("text", prompt)))));
        return body;
    }

    public static String ask(String apiKey, String model, String prompt) throws Exception {
        return textFrom(post(apiKey, model, baseRequest(prompt)));
    }

    public static String analyzeImage(String apiKey, String model, String prompt, byte[] image, String mimeType) throws Exception {
        if (image == null || image.length == 0) throw new IOException("Görsel verisi boş.");
        JSONObject body = baseRequest(prompt);
        JSONArray parts = body.getJSONArray("contents").getJSONObject(0).getJSONArray("parts");
        parts.put(new JSONObject().put("inline_data", new JSONObject()
                .put("mime_type", mimeType == null ? "image/jpeg" : mimeType)
                .put("data", Base64.encodeToString(image, Base64.NO_WRAP))));
        return textFrom(post(apiKey, model, body));
    }

    public static byte[] generateImage(String apiKey, String model, String prompt) throws Exception {
        JSONObject body = baseRequest(prompt);
        body.put("generationConfig", new JSONObject()
                .put("responseModalities", new JSONArray().put("TEXT").put("IMAGE")));
        JSONObject json = post(apiKey,
                (model == null || model.trim().isEmpty()) ? "gemini-3.1-flash-image" : model,
                body);
        JSONArray candidates = json.optJSONArray("candidates");
        if (candidates != null) for (int i = 0; i < candidates.length(); i++) {
            JSONObject content = candidates.getJSONObject(i).optJSONObject("content");
            if (content == null) continue;
            JSONArray parts = content.optJSONArray("parts");
            if (parts == null) continue;
            for (int j = 0; j < parts.length(); j++) {
                JSONObject part = parts.getJSONObject(j);
                JSONObject data = part.optJSONObject("inlineData");
                if (data == null) data = part.optJSONObject("inline_data");
                if (data != null && data.has("data"))
                    return Base64.decode(data.getString("data"), Base64.DEFAULT);
            }
        }
        throw new IOException("Gemini yanıtında görsel yok. Görsel üretimini destekleyen model seç.");
    }
}