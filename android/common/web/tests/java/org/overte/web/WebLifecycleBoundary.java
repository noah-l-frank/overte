// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
package org.overte.web;
import java.util.HashMap;
import java.util.Map;

/** Android WebView/Looper are represented; Qt, JVM, JNI and production dispatch remain real. */
public final class WebLifecycleBoundary {
    static native long revision(long handle);
    static native long active(long handle);
    static native void resume(long handle, long birth, long revision, String url);
    static native void created(long handle, long revision, boolean value);
    public static String loadedUrl;
    public static long handle, creationRevision, hiddenRevision, hiddenActive;
    public static int hidden, creates, evaluations;
    public static void evaluate(long handle,long grant,long page,String script) { evaluations++; }
    public static int wheels;
    public static long wheelHandle, wheelGrant, wheelPage;
    public static String wheelDocument;
    public static float wheelX, wheelY, wheelPixelX, wheelPixelY, wheelAngleX, wheelAngleY;
    public static boolean wheelPixelMode;
    public static void wheel(long h,long g,long p,String document,float x,float y,float px,float py,float ax,float ay,boolean pixel) {
        wheels++; wheelHandle=h; wheelGrant=g; wheelPage=p; wheelDocument=document;
        wheelX=x; wheelY=y; wheelPixelX=px; wheelPixelY=py; wheelAngleX=ax; wheelAngleY=ay; wheelPixelMode=pixel;
    }
    public static int edits;
    public static String lastEdit;
    public static void edit(long h,long g,long p,String document,String command) { edits++; lastEdit=command; }
    public static boolean delayCreated;
    static final Object owner = new Object(), activity = new Object();
    static final Map<Long,Object> instances = new HashMap<>();
    public static void create(long h, long grant, String url, String agent, boolean background, boolean overlay,
            int x, int y, int w, int height, int cx, int cy, int cw, int ch, String bootstrap, String editor) {
        handle = h; creationRevision = grant; loadedUrl = url; creates++; instances.put(h, new Object()); if (!delayCreated) created(h, grant, true);
    }
    public static void revoke(long h) { }
    public static void destroyExpected(long h, long revision) { instances.remove(h); }
    public static void destroy(long h) { instances.remove(h); }
    public static void resize(long h, int x, int y, int w, int height, int cx, int cy, int cw, int ch) { }
    public static void visibility(long h, long grant, boolean visible) {
        Object instance = instances.get(h);
        WebLifecycleDispatch.apply(instance, instances.get(h), owner, owner, activity, activity,
            grant, revision(h), () -> {
                if (!visible) { hidden++; hiddenRevision = grant; hiddenActive = active(h); }
            });
    }
    public static void load(long h, long grant, String url) { throw new AssertionError("creation must not reload its already requested URL"); }
    public static void reload(long h) { resume(h, creationRevision, revision(h), "https://wire.test/reloaded"); }
    public static void focus(long h, boolean value) { }
}
