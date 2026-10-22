package com.stagepulse.jarvis;

import android.accessibilityservice.AccessibilityService;
import android.view.accessibility.AccessibilityEvent;
import android.view.accessibility.AccessibilityNodeInfo;
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
        // No accessibility-event contents are logged or persisted. Screen text is read only
        // when the user explicitly issues a read-screen command.
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
        String expected = new ComponentName(context, JarvisAccessibilityService.class).flattenToString();
        for (String part : enabled.split(":")) {
            if (expected.equalsIgnoreCase(part)) return true;
        }
        return false;
    }

    public static boolean requestGlobalAction(int action) {
        JarvisAccessibilityService current = instance;
        if (current == null) return false;
        current.main.post(() -> current.performGlobalAction(action));
        return true;
    }


    private static String norm(String value) {
        if (value == null) return "";
        return value.toLowerCase(java.util.Locale.ROOT)
                .replace("ı", "i").replace("ş", "s").replace("ğ", "g")
                .replace("ü", "u").replace("ö", "o").replace("ç", "c")
                .trim();
    }

    private AccessibilityNodeInfo findNode(AccessibilityNodeInfo node, String target) {
        if (node == null || target == null || target.trim().isEmpty()) return null;
        CharSequence text = node.getText();
        CharSequence description = node.getContentDescription();
        String label = (text == null ? "" : text.toString()) + " "
                + (description == null ? "" : description.toString());
        if (!label.trim().isEmpty() && norm(label).contains(norm(target))) return node;
        for (int i = 0; i < node.getChildCount(); i++) {
            AccessibilityNodeInfo found = findNode(node.getChild(i), target);
            if (found != null) return found;
        }
        return null;
    }

    private AccessibilityNodeInfo findEditable(AccessibilityNodeInfo node) {
        if (node == null) return null;
        if (node.isEditable() && node.isEnabled()) return node;
        for (int i = 0; i < node.getChildCount(); i++) {
            AccessibilityNodeInfo found = findEditable(node.getChild(i));
            if (found != null) return found;
        }
        return null;
    }

    private void clickTextOnMain(String target) {
        AccessibilityNodeInfo root = getRootInActiveWindow();
        AccessibilityNodeInfo node = findNode(root, target);
        boolean clicked = false;
        while (node != null) {
            if (node.isClickable() && node.performAction(AccessibilityNodeInfo.ACTION_CLICK)) {
                clicked = true;
                break;
            }
            node = node.getParent();
        }
        // Result is not reported as success to the caller: apps can reject accessibility actions.
    }

    private void setFocusedTextOnMain(String value) {
        AccessibilityNodeInfo root = getRootInActiveWindow();
        AccessibilityNodeInfo focused = root == null ? null : root.findFocus(AccessibilityNodeInfo.FOCUS_INPUT);
        if (focused == null) focused = findEditable(root);
        if (focused != null && focused.isEditable()) {
            android.os.Bundle args = new android.os.Bundle();
            args.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, value);
            focused.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args);
        }
    }

    private String visibleTextOnMain() {
        AccessibilityNodeInfo root = getRootInActiveWindow();
        if (root == null) return "";
        StringBuilder out = new StringBuilder();
        collectText(root, out);
        return out.toString().trim();
    }

    private void collectText(AccessibilityNodeInfo node, StringBuilder out) {
        if (node == null || out.length() >= 6000) return;
        CharSequence text = node.getText();
        CharSequence description = node.getContentDescription();
        String label = text == null ? "" : text.toString().trim();
        if (label.isEmpty() && description != null) label = description.toString().trim();
        if (!label.isEmpty() && !out.toString().contains(label)) {
            if (out.length() > 0) out.append("\n");
            out.append(label);
        }
        for (int i = 0; i < node.getChildCount() && out.length() < 6000; i++) {
            collectText(node.getChild(i), out);
        }
    }

    private boolean scrollOnMain(boolean down) {
        AccessibilityNodeInfo root = getRootInActiveWindow();
        return scrollFirst(root, down);
    }

    private boolean scrollFirst(AccessibilityNodeInfo node, boolean down) {
        if (node == null) return false;
        if (node.isScrollable()) {
            int action = down ? AccessibilityNodeInfo.ACTION_SCROLL_FORWARD
                    : AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD;
            if (node.performAction(action)) return true;
        }
        for (int i = 0; i < node.getChildCount(); i++) {
            if (scrollFirst(node.getChild(i), down)) return true;
        }
        return false;
    }

    public static boolean clickVisibleText(String target) {
        JarvisAccessibilityService current = instance;
        if (current == null || target == null || target.trim().isEmpty()) return false;
        current.main.post(() -> current.clickTextOnMain(target));
        return true;
    }

    public static boolean setFocusedText(String value) {
        JarvisAccessibilityService current = instance;
        if (current == null || value == null) return false;
        current.main.post(() -> current.setFocusedTextOnMain(value));
        return true;
    }

    public static boolean scrollVisibleWindow(boolean down) {
        JarvisAccessibilityService current = instance;
        if (current == null) return false;
        current.main.post(() -> {
            if (!current.scrollOnMain(down) && Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
                android.util.DisplayMetrics dm = current.getResources().getDisplayMetrics();
                float x = dm.widthPixels * 0.5f;
                float y1 = dm.heightPixels * (down ? 0.78f : 0.30f);
                float y2 = dm.heightPixels * (down ? 0.30f : 0.78f);
                android.graphics.Path path = new android.graphics.Path();
                path.moveTo(x, y1);
                path.lineTo(x, y2);
                android.accessibilityservice.GestureDescription gesture =
                        new android.accessibilityservice.GestureDescription.Builder()
                                .addStroke(new android.accessibilityservice.GestureDescription.StrokeDescription(
                                        path, 0, 350)).build();
                current.dispatchGesture(gesture, null, null);
            }
        });
        return true;
    }

    public static String readVisibleWindowText() {
        JarvisAccessibilityService current = instance;
        if (current == null) return "";
        if (Looper.myLooper() == Looper.getMainLooper()) return "Ekran metni ana iş parçacığında eşzamanlı okunamaz.";
        final java.util.concurrent.atomic.AtomicReference<String> result =
                new java.util.concurrent.atomic.AtomicReference<>("");
        final java.util.concurrent.CountDownLatch latch = new java.util.concurrent.CountDownLatch(1);
        current.main.post(() -> {
            try { result.set(current.visibleTextOnMain()); }
            finally { latch.countDown(); }
        });
        try { latch.await(1500, java.util.concurrent.TimeUnit.MILLISECONDS); }
        catch (InterruptedException e) { Thread.currentThread().interrupt(); }
        return result.get();
    }

    public static boolean supportsScreenLock() {
        return Build.VERSION.SDK_INT >= Build.VERSION_CODES.P;
    }
}
