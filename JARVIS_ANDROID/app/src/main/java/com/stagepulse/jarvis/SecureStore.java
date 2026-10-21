package com.stagepulse.jarvis;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/** Small Android Keystore-backed encrypted storage for API keys and LAN tokens. */
public final class SecureStore {
    private static final String STORE = "AndroidKeyStore";
    private static final String ALIAS = "StagepulseJARVIS.SecretStore.v1";
    private static final String PREFIX = "enc:v1:";
    private SecureStore() {}

    private static SecretKey getKey() throws Exception {
        KeyStore store = KeyStore.getInstance(STORE);
        store.load(null);
        if (store.containsAlias(ALIAS)) {
            KeyStore.Entry entry = store.getEntry(ALIAS, null);
            if (entry instanceof KeyStore.SecretKeyEntry) return ((KeyStore.SecretKeyEntry) entry).getSecretKey();
        }
        KeyGenerator generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, STORE);
        generator.init(new KeyGenParameterSpec.Builder(ALIAS,
                KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setRandomizedEncryptionRequired(true)
                .build());
        return generator.generateKey();
    }

    public static void put(SharedPreferences prefs, String name, String value) {
        if (value == null || value.isEmpty()) {
            prefs.edit().remove(name).apply();
            return;
        }
        try {
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.ENCRYPT_MODE, getKey());
            byte[] encrypted = cipher.doFinal(value.getBytes(StandardCharsets.UTF_8));
            byte[] iv = cipher.getIV();
            ByteBuffer buffer = ByteBuffer.allocate(4 + iv.length + encrypted.length);
            buffer.putInt(iv.length).put(iv).put(encrypted);
            prefs.edit().putString(name, PREFIX + Base64.encodeToString(buffer.array(), Base64.NO_WRAP)).apply();
        } catch (Exception e) {
            throw new IllegalStateException("Gizli bilgi Android Keystore ile şifrelenemedi.", e);
        }
    }

    public static String get(SharedPreferences prefs, String name) {
        String value = prefs.getString(name, "");
        if (value == null || value.isEmpty()) return "";
        if (!value.startsWith(PREFIX)) return value; // Migrate legacy plain-text values on next save.
        try {
            byte[] raw = Base64.decode(value.substring(PREFIX.length()), Base64.NO_WRAP);
            ByteBuffer buffer = ByteBuffer.wrap(raw);
            int ivLength = buffer.getInt();
            if (ivLength < 12 || ivLength > 16 || raw.length <= 4 + ivLength) return "";
            byte[] iv = new byte[ivLength];
            buffer.get(iv);
            byte[] ciphertext = new byte[buffer.remaining()];
            buffer.get(ciphertext);
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.DECRYPT_MODE, getKey(), new GCMParameterSpec(128, iv));
            return new String(cipher.doFinal(ciphertext), StandardCharsets.UTF_8);
        } catch (Exception e) {
            return "";
        }
    }

    public static void migrate(SharedPreferences prefs, String name) {
        String existing = prefs.getString(name, "");
        if (existing != null && !existing.isEmpty() && !existing.startsWith(PREFIX)) {
            put(prefs, name, existing);
        }
    }
}
