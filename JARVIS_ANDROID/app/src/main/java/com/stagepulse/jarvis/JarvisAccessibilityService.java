package com.stagepulse.jarvis;

import android.accessibilityservice.AccessibilityService;
import android.view.accessibility.AccessibilityEvent;
import android.provider.Settings;
import android.content.ComponentName;
import android.content.Context;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;

public final class JarvisAccessibilityService extends AccessibilityService {
    private static volatile JarvisAccessibilityService instance;
    private final Handler main = new Handler(Looper.getMainLooper());

    @Override public void onServiceConnected() {
        super.onServiceConnected();
        instance = this;
    }

    @Override public void onAccessibilityEvent(AccessibilityEvent event) {
        // JARVIS uses this service only for explicitly requested Android global actions.
        // It does not read text, inspect screens, or collect events from other apps.
    }

    @Override public void onInterrupt() { }

    @Override public void onDestroy() {
        if (instance == this) instance = null;
        super.onDestroy();
    }

    public static boolean isEnabled(Context context) {
        String enabled = Settings.Secure.getString(
                context.getContentResolver(), Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES);
        if (enabled == null || enabled.isEmpty()) return false;
        String expected = ComponentName.flattenToString(
                new ComponentName(context, JarvisAccessibilityService.class));
        for (String part : enabled.split(":")) {
            if (expected.equalsIgnoreCase(part)) return true;
        }
        return false;
    }

    public static boolean performGlobalAction(int action) {
        JarvisAccessibilityService current = instance;
        if (current == null) return false;
        current.main.post(() -> current.performGlobalAction(action));
        return true;
    }

    public static boolean supportsScreenLock() {
        return Build.VERSION.SDK_INT >= Build.VERSION_CODES.P;
    }
}
