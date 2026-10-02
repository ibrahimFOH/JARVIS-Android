#include <android/log.h>
#include <espeak-ng/speak_lib.h>
#include <jni.h>
#include <stdlib.h>
#include <string.h>

#define TAG "JARVIS_ESPEAK"
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, TAG, __VA_ARGS__)

JNIEXPORT jint JNICALL
Java_com_stagepulse_jarvis_EspeakNative_nativeInitialize(
        JNIEnv *env, jobject thiz, jstring dataPath) {
    const char *path = (*env)->GetStringUTFChars(env, dataPath, 0);
    int result = espeak_Initialize(AUDIO_OUTPUT_SYNCHRONOUS, 0, path, 0);
    (*env)->ReleaseStringUTFChars(env, dataPath, path);
    return result;
}

JNIEXPORT jstring JNICALL
Java_com_stagepulse_jarvis_EspeakNative_nativeTextToPhonemes(
        JNIEnv *env, jobject thiz, jstring text, jstring language) {
    const char *c_text = (*env)->GetStringUTFChars(env, text, 0);
    const char *c_lang = (*env)->GetStringUTFChars(env, language, 0);

    if (espeak_SetVoiceByName(c_lang) != EE_OK) {
        LOGE("Failed to set eSpeak voice: %s", c_lang);
        (*env)->ReleaseStringUTFChars(env, text, c_text);
        (*env)->ReleaseStringUTFChars(env, language, c_lang);
        return (*env)->NewStringUTF(env, "");
    }

    const void *text_ptr = c_text;
    char *buffer = (char *)malloc(16384);
    if (buffer == NULL) {
        (*env)->ReleaseStringUTFChars(env, text, c_text);
        (*env)->ReleaseStringUTFChars(env, language, c_lang);
        return (*env)->NewStringUTF(env, "");
    }
    buffer[0] = '\0';
    size_t current = 0;

    while (text_ptr != NULL) {
        const char *phonemes =
                espeak_TextToPhonemes(&text_ptr, espeakCHARS_UTF8, espeakPHONEMES_IPA);
        if (phonemes == NULL || phonemes[0] == '\0') break;

        size_t len = strlen(phonemes);
        if (current + len + 2 >= 16384) break;
        if (current > 0) buffer[current++] = ' ';
        memcpy(buffer + current, phonemes, len);
        current += len;
        buffer[current] = '\0';
    }

    jstring result = (*env)->NewStringUTF(env, buffer);
    free(buffer);

    (*env)->ReleaseStringUTFChars(env, text, c_text);
    (*env)->ReleaseStringUTFChars(env, language, c_lang);
    return result;
}
