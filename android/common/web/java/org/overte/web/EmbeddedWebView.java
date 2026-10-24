// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
package org.overte.web;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.graphics.Rect;
import android.net.Uri;
import android.net.http.SslError;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.view.MotionEvent;
import android.view.InputDevice;
import android.view.View;
import android.view.ViewConfiguration;
import android.webkit.CookieManager;
import android.webkit.PermissionRequest;
import android.webkit.RenderProcessGoneDetail;
import android.webkit.SslErrorHandler;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import androidx.webkit.ScriptHandler;
import androidx.webkit.WebMessageCompat;
import androidx.webkit.WebViewCompat;
import androidx.webkit.WebViewFeature;
import org.json.JSONObject;
import org.json.JSONArray;

import java.io.ByteArrayInputStream;
import java.lang.ref.WeakReference;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.UUID;
import java.security.MessageDigest;
import java.util.concurrent.ConcurrentHashMap;

/** Shared native HTML runtime; product hosts own presentation and OS prompts. */
public final class EmbeddedWebView {
    public static final int READY = 0, BRIDGE_UNAVAILABLE = 1, LOAD_FAILED = 2,
        RUNTIME_FAILED = 3, OVERLAY_UNAVAILABLE = 4, FILE_CHOOSER_UNAVAILABLE = 5, EXTERNAL_UNAVAILABLE = 8;
    private static final Handler MAIN = new Handler(Looper.getMainLooper());
    private static final ConcurrentHashMap<Long, Instance> VIEWS = new ConcurrentHashMap<>();
    private static final WebInputGate INPUT = new WebInputGate();
    private static WeakReference<EmbeddedWebHost> host = new WeakReference<>(null);
    private static final ConcurrentHashMap<Long, PendingCreation> CREATING = new ConcurrentHashMap<>();
    private static final class PendingCreation {
        final EmbeddedWebHost owner; final Activity activity; final long revision; final String originalSource; WebTextureRenderer renderer;
        PendingCreation(EmbeddedWebHost owner, long revision, String originalSource) {
            this.owner = owner; this.activity = owner.activity(); this.revision = revision; this.originalSource = nativeFeatureEnabled() ? originalSource : null;
        }
    }
    private EmbeddedWebView() { }

    /** Call on the Android UI thread after the product native library is loaded. */
    public static void initialize(EmbeddedWebHost next) {
        requireMain();
        if (host.get() != next) { destroyAll(); }
        host = new WeakReference<>(next);
        nativeInitialize();
        setForeground(next, next != null && next.isForeground());
    }
    public static void setForeground(EmbeddedWebHost owner, boolean foreground) {
        requireMain();
        if (host.get() != owner) return;
        setInputFocused(owner, foreground && owner.activity() != null && owner.activity().hasWindowFocus());
        nativeForeground(foreground);
        for (Instance instance : new ArrayList<>(VIEWS.values())) {
            instance.document.grant(nativeLifecycleRevision(instance.handle));
            if (foreground && !instance.destroyedDocument) instance.prepareResources(instance.view.getUrl());
            else instance.resources.revoke();
            if (!foreground) { instance.suspend(); }
            else if (instance.visible) { if (instance.destroyedDocument) instance.reportSuspended();
                else { instance.view.setVisibility(View.VISIBLE); instance.view.onResume(); instance.authorize(); instance.armTexture(); instance.commitAudio(); instance.publish(); } }
        }
    }
    /** Window/input focus is independent of Activity foreground and media lifetime. */
    public static void setInputFocused(EmbeddedWebHost owner, boolean focused) {
        requireMain();
        if (host.get() != owner || owner == null) return;
        boolean allowed = focused && owner.isForeground() && owner.activity() != null && owner.activity().hasWindowFocus();
        INPUT.update(owner, allowed);
        for (Instance instance : new ArrayList<>(VIEWS.values())) {
            if (instance.owner != owner || instance.activity != owner.activity() || !instance.active) continue;
            nativeInputFocus(instance.handle, instance.creationRevision, nativeLifecycleRevision(instance.handle), allowed);
            if (!allowed && !instance.destroyedDocument) instance.cancelInput();
        }
    }
    public static void detach(EmbeddedWebHost owner) {
        requireMain();
        if (host.get() != owner) return;
        setForeground(owner, false); destroyAll(); host.clear();
    }
    private static void requireMain() {
        if (Looper.myLooper() != Looper.getMainLooper()) throw new IllegalStateException("UI thread required");
    }
    private static native void nativeInitialize();
    private static native boolean nativeFeatureEnabled();
    private static native boolean nativePicoCurrentDocumentEnabled();
    private static native void nativePicoCurrentDocumentResult(long handle,long creation,long grant,long page,
        String run,String request,String raw);
    static boolean featureObservationEnabled() { return nativeFeatureEnabled(); }
    private static native void nativeFeatureDOMResult(long handle,long grant,long page,String document,String requestId,String result);
    private static native void nativeFeatureFinished(long handle,long grant,long page,String document);
    private static native void nativeFeatureHTTPError(long handle,long grant,long page,String document,int status);
    private static native void nativeFeatureRuntimeResult(String requestId,String result);
    private static native void nativeForeground(boolean active);
    private static native long nativeGeneration(long handle);
    private static native long nativeLifecycleRevision(long handle);
    private static native void nativeInputFocus(long handle, long creationRevision, long revision, boolean focused);
    private static native void nativeSuspended(long handle, long creationRevision, long revision, String url, boolean back, boolean forward);
    private static native void nativeResumeRequest(long handle, long creationRevision, long revision, String url);
    private static native boolean nativeBridgeAllowed(long handle, long grant, long page, String document);
    private static native boolean nativeEditorAllowed(long handle, long grant, long page, String document);
    private static native boolean nativeFileChooserAllowed(long handle, long grant, long page, String document);
    private static native boolean nativeNavigation(long handle, long grant, String url, boolean mainFrame, String method);
    private static native boolean nativeMessage(long handle, long grant, long page, String document,
                                               String origin, boolean mainFrame, String type, String payload);
    private static native void nativePage(long handle, long grant, long page, String url);
    private static native void nativeState(long handle, long grant, long page, String url,
                                           boolean loading, boolean canGoBack, boolean canGoForward, boolean bridge, int status);
    private static native void nativeResult(long handle, long grant, long page, long request, String json);
    private static native void nativeCreated(long handle, long revision, boolean created);
    private static native void nativeFrame(long handle, long grant, long page, ByteBuffer pixels, int width, int height);
    private static native long nativeBeginResourceLoad(long handle, long creation, long grant, long page, String document);
    private static native boolean nativeBindResourcePage(long handle, long creation, long grant, long load, long pendingPage, long actualPage, String document);
    private static native boolean nativeResourceCurrent(long handle, long creation, long grant, long load, long page);
    private static native WebResourceLease.Response nativeRequest(long handle, long creation, long grant, long load, long page,
                                                                 String url, boolean mainFrame, String method);

    private interface Command { void run(Instance instance); }
    private static void post(long handle, Command command) { post(handle, command, false); }
    private static void post(long handle, Command command, boolean suspendedAllowed) {
        Instance expected = VIEWS.get(handle);
        if (!MAIN.post(() -> {
            Instance instance = VIEWS.get(handle);
            if (instance == null || instance != expected || !instance.active
                    || host.get() != instance.owner || instance.owner.activity() != instance.activity
                    || instance.destroyedDocument && !suspendedAllowed) return;
            try { command.run(instance); }
            catch (RuntimeException | OutOfMemoryError failure) { instance.fail(RUNTIME_FAILED); }
        })) { nativeCreated(handle, expected == null ? 0 : expected.creationRevision, false); }
    }
    private static void input(long handle, Command command) { input(handle, command, false); }
    private static void navigationInput(long handle, Command command) { input(handle, command, true); }
    private static void input(long handle, Command command, boolean suspendedAllowed) {
        WebInputGate.Ticket ticket = INPUT.capture();
        Instance expected = VIEWS.get(handle);
        if (ticket == null || expected == null) return;
        WeakReference<Instance> target = new WeakReference<>(expected);
        post(handle, instance -> {
            EmbeddedWebHost owner = host.get();
            if (instance != target.get() || !INPUT.permits(ticket, owner) || !instance.visible
                    || !owner.isForeground() || (instance.owner != owner || owner.activity() != instance.activity)
                    || !owner.activity().hasWindowFocus()) return;
            command.run(instance);
        }, suspendedAllowed);
    }
    @SuppressLint("SetJavaScriptEnabled")
    public static void create(long handle, long grant, String url, String userAgent,
            boolean background, boolean overlay, int x, int y, int width, int height,
            int clipX, int clipY, int clipWidth, int clipHeight, String bootstrap, String editorBootstrap) {
        MAIN.post(() -> {
            EmbeddedWebHost owner = host.get();
            if (nativeGeneration(handle) != grant || owner == null || owner.activity() == null || width <= 1 || height <= 1) {
                nativeCreated(handle, grant, false); return;
            }
            Instance suspended = VIEWS.get(handle);
            WebNavigationArchive history = suspended != null && suspended.destroyedDocument ? suspended.archive : null;
            destroyOnMain(handle);
            PendingCreation creation = new PendingCreation(owner, grant, url);
            CREATING.put(handle, creation);
            Runnable finish = () -> {
                if (CREATING.get(handle) != creation) return;
                CREATING.remove(handle, creation);
                if (host.get() != creation.owner || creation.owner.activity() != creation.activity
                        || nativeGeneration(handle) != grant || creation.activity.isDestroyed()) {
                    if (creation.renderer != null) creation.renderer.close();
                    nativeCreated(handle, grant, false); return;
                }
                WebView view = null;
                try {
                    view = new WebView(overlay ? creation.activity : creation.renderer.context());
                    WebSettings settings = view.getSettings();
                    settings.setJavaScriptEnabled(true); settings.setDomStorageEnabled(true);
                    settings.setAllowFileAccess(false); settings.setAllowContentAccess(false);
                    settings.setAllowFileAccessFromFileURLs(false); settings.setAllowUniversalAccessFromFileURLs(false);
                    settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
                    settings.setJavaScriptCanOpenWindowsAutomatically(false); settings.setSupportMultipleWindows(false);
                    settings.setGeolocationEnabled(false); settings.setMediaPlaybackRequiresUserGesture(true);
                    if (android.os.Build.VERSION.SDK_INT >= 26) settings.setSafeBrowsingEnabled(true);
                    settings.setUseWideViewPort(true);
                    if (userAgent != null && !userAgent.isEmpty()) settings.setUserAgentString(userAgent);
                    CookieManager.getInstance().setAcceptThirdPartyCookies(view, false);
                    view.setBackgroundColor(background ? Color.WHITE : Color.TRANSPARENT);
                    Instance instance = new Instance(handle, view, overlay, bootstrap, editorBootstrap, creation.owner, creation.activity, creation.renderer);
                    instance.creationRevision = grant;
                    instance.archive = history;
                    instance.document.begin(grant);
                    instance.bounds = new Rect(x, y, x + width, y + height);
                    instance.clip = new Rect(clipX, clipY, clipX + clipWidth, clipY + clipHeight);
                    instance.resize(width, height);
                    VIEWS.put(handle, instance);
                    if (!instance.prepareResources(url)) throw new IllegalStateException("Resource lease denied");
                    instance.configureBridge(url);
                    view.setWebViewClient(instance.client);
                    view.setWebChromeClient(instance.chrome);
                    if (overlay) {
                        if (!owner.placeTabletView(view, instance.bounds, instance.clip)) instance.status = OVERLAY_UNAVAILABLE;
                    } else { creation.renderer.attach(view); }
                    view.loadUrl(url);
                    nativeCreated(handle, grant, true);
                    instance.publish();
                } catch (RuntimeException | OutOfMemoryError failure) {
                    if (VIEWS.containsKey(handle)) destroyOnMain(handle);
                    else {
                        if (view != null) view.destroy();
                        if (creation.renderer != null) creation.renderer.close();
                    }
                    owner.diagnostic(RUNTIME_FAILED); nativeCreated(handle, grant, false);
                }
            };
            try {
                if (overlay) finish.run();
                else creation.renderer = new WebTextureRenderer(creation.activity,width,height,new WebTextureRenderer.Callback() {
                    @Override public void ready(WebTextureRenderer renderer) { finish.run(); }
                    @Override public void resized() {
                        Instance instance = VIEWS.get(handle);
                        if (instance != null && instance.renderer == creation.renderer) instance.armTexture();
                    }
                    @Override public void frame(WebFrameGate.Ticket ticket, ByteBuffer pixels, int w, int h) {
                        Instance instance = VIEWS.get(handle);
                        if (instance == null || instance.renderer != creation.renderer || !instance.active || !instance.visible
                                || host.get() != creation.owner || creation.owner.activity() != creation.activity
                                || !creation.owner.isForeground() || nativeGeneration(handle) != ticket.grant
                                || !instance.document.admits(ticket.grant,ticket.page,true,1)
                                || !ticket.document.equals(instance.view.getUrl())) return;
                        nativeFrame(handle,ticket.grant,ticket.page,pixels,w,h);
                    }
                    @Override public void failed() {
                        if (CREATING.remove(handle,creation)) { owner.diagnostic(RUNTIME_FAILED); nativeCreated(handle,grant,false); }
                        else {
                            Instance instance = VIEWS.get(handle);
                            if (instance != null && instance.renderer == creation.renderer) instance.fail(RUNTIME_FAILED);
                        }
                    }
                });
                if (creation.renderer != null) creation.renderer.featureOwner(handle,grant,url);
            } catch (RuntimeException | OutOfMemoryError failure) {
                if (CREATING.remove(handle,creation)) {
                    if (creation.renderer != null) creation.renderer.close();
                    owner.diagnostic(RUNTIME_FAILED); nativeCreated(handle,grant,false);
                }
            }
        });
    }
    public static void revoke(long handle) {
        Instance expected = VIEWS.get(handle); if (expected != null) expected.resources.revoke();
        post(handle, instance -> instance.suspend(), true);
    }
    public static void destroyExpected(long handle, long creationRevision) {
        post(handle, instance -> { if (instance.creationRevision == creationRevision) destroyOnMain(handle); }, true);
    }
    public static void destroy(long handle) {
        Instance expected = VIEWS.get(handle); if (expected != null) expected.resources.revoke();
        MAIN.post(() -> destroyOnMain(handle));
    }
    private static void destroyAll() {
        requireMain(); for (long handle : new ArrayList<>(CREATING.keySet())) destroyOnMain(handle);
        for (long handle : new ArrayList<>(VIEWS.keySet())) destroyOnMain(handle);
    }
    private static void destroyOnMain(long handle) {
        PendingCreation pending = CREATING.remove(handle);
        if (pending != null && pending.renderer != null) pending.renderer.close();
        Instance instance = VIEWS.remove(handle);
        if (instance == null) { if (pending != null) nativeCreated(handle,pending.revision,false); return; }
        instance.resources.revoke();
        instance.active = false; instance.closing = true; instance.audio.suspend(); instance.document.close();
        if (!instance.destroyedDocument) instance.cancelInput();
        if (instance.renderer != null) instance.renderer.close();
        EmbeddedWebHost owner = host.get();
        if (owner != null && instance.overlay) owner.removeTabletView(instance.view);
        if (instance.script != null) instance.script.remove();
        if (instance.editorScript != null) instance.editorScript.remove();
        if (!instance.destroyedDocument) { instance.view.stopLoading(); instance.view.loadUrl("about:blank"); instance.view.destroy(); }
        nativeCreated(handle, instance.creationRevision, false);
    }
    public static void load(long handle, long grant, String url) {
        post(handle, instance -> {
            if (nativeGeneration(handle) != grant) return;
            if (instance.destroyedDocument) { instance.fallbackUrl = url; instance.reportSuspended(); return; }
            instance.document.begin(grant); instance.fallbackUrl = url;
            if (!instance.audio.suspend()) return;
            instance.cancelInput();
            if (instance.renderer != null) instance.renderer.invalidate(); instance.configureBridge(url);
            if (instance.prepareResources(url)) instance.view.loadUrl(url);
        }, true);
    }
    public static void visibility(long handle, long grant, boolean visible) {
        post(handle, instance -> {
            WebLifecycleDispatch.apply(instance, VIEWS.get(handle), instance.owner, host.get(),
                instance.activity, instance.owner.activity(), grant, nativeLifecycleRevision(handle), () -> {
            instance.document.grant(grant); instance.document.visible(visible); instance.visible = visible;
            if (visible && !instance.destroyedDocument) instance.prepareResources(instance.view.getUrl());
            else instance.resources.revoke();
            if (instance.destroyedDocument) { instance.reportSuspended(); return; }
            if (!visible) {
                instance.suspend();
                if (!instance.destroyedDocument) instance.view.setVisibility(View.GONE);
                instance.publish();
            }
            else if (instance.owner.isForeground()) { instance.view.setVisibility(View.VISIBLE); instance.view.onResume(); instance.authorize(); instance.armTexture(); instance.commitAudio(); instance.publish(); }
            });
        }, true);
    }
    public static void resize(long handle, int x, int y, int width, int height, int clipX, int clipY, int clipWidth, int clipHeight) {
        post(handle, instance -> {
            instance.bounds = new Rect(x, y, x + width, y + height);
            instance.clip = new Rect(clipX, clipY, clipX + clipWidth, clipY + clipHeight);
            instance.resize(width, height);
            EmbeddedWebHost owner = host.get();
            if (instance.overlay && owner != null && !owner.placeTabletView(instance.view, instance.bounds, instance.clip)) {
                instance.status = OVERLAY_UNAVAILABLE; instance.publish();
            }
        });
    }
    public static void relayout(EmbeddedWebHost expected) {
        MAIN.post(() -> {
            if (host.get() != expected) return;
            for (Instance instance : VIEWS.values()) {
                if (!instance.active || instance.destroyedDocument || !instance.overlay || instance.activity != expected.activity()) continue;
                boolean placed = expected.placeTabletView(instance.view, instance.bounds, instance.clip);
                if (placed && instance.status == OVERLAY_UNAVAILABLE) {
                    instance.status = instance.bridge ? READY : BRIDGE_UNAVAILABLE;
                    instance.publish();
                }
            }
        });
    }
    public static void background(long handle, boolean value) {
        post(handle, instance -> { if (!instance.destroyedDocument) instance.view.setBackgroundColor(value ? Color.WHITE : Color.TRANSPARENT); });
    }
    public static void userAgent(long handle, String value) {
        post(handle, instance -> { if (!instance.destroyedDocument) instance.view.getSettings().setUserAgentString(value.isEmpty() ? null : value); });
    }
    public static void stop(long handle) { post(handle, instance -> { if (!instance.destroyedDocument) { instance.view.stopLoading(); instance.loading = false; instance.publish(); } }); }
    public static void reload(long handle) { navigationInput(handle, instance -> {
        if (instance.destroyedDocument) { instance.resumeArchive(0); return; }
        if (instance.beginAudioNavigation(instance.view.getUrl())) { instance.document.begin(instance.document.grant()); if (instance.prepareResources(instance.view.getUrl())) instance.view.reload(); }
    }); }
    public static void goForward(long handle) { navigationInput(handle, instance -> { if (instance.destroyedDocument) { instance.resumeArchive(1); return; }
        if (instance.archive != null) { instance.navigateArchive(1); return; }
        instance.navigateHistory(1); }); }
    public static void reloadAndBypassCache(long handle) { navigationInput(handle, instance -> {
        if (instance.destroyedDocument) { instance.resumeArchive(0); return; }
        if (instance.beginAudioNavigation(instance.view.getUrl())) { instance.view.clearCache(false); instance.document.begin(instance.document.grant()); if (instance.prepareResources(instance.view.getUrl())) instance.view.reload(); }
    }); }
    /** Product hosts use the same reserved-origin boundary for OS browser actions. */
    public static boolean isExternalWebURL(Uri url) {
        return url != null && ("http".equals(url.getScheme()) || "https".equals(url.getScheme()))
            && url.getHost() != null && !url.getHost().isEmpty() && url.getUserInfo() == null
            && !"overte-embedded.invalid".equalsIgnoreCase(url.getHost())
            && !WebResourceLease.reservedInlineHost(url.getHost());
    }
    public static void openNative(long handle) { navigationInput(handle, instance -> {
        String url = instance.destroyedDocument ? instance.fallbackUrl : instance.view.getUrl();
        if (url != null && nativeNavigation(handle, instance.document.grant(), url, true, "GET")
                && isExternalWebURL(Uri.parse(url))) {
            EmbeddedWebHost owner = host.get();
            if (owner != null && !owner.openExternal(Uri.parse(url))) { instance.status = EXTERNAL_UNAVAILABLE; instance.publish(); }
        }
    }); }
    public static void goBack(long handle) { navigationInput(handle, instance -> { if (instance.destroyedDocument) { instance.resumeArchive(-1); return; }
        if (instance.archive != null) { instance.navigateArchive(-1); return; }
        instance.navigateHistory(-1); }); }
    /** Route physical Back through common audio, input, and resource navigation fences. */
    public static boolean goBack(EmbeddedWebHost expectedOwner, WebView view) {
        requireMain();
        if (expectedOwner == null || host.get() != expectedOwner || !expectedOwner.isForeground()
                || expectedOwner.activity() == null || !expectedOwner.activity().hasWindowFocus()) return false;
        for (Instance instance : VIEWS.values()) {
            if (instance.view == view && instance.owner == expectedOwner && instance.activity == expectedOwner.activity()
                    && instance.active && instance.visible && !instance.destroyedDocument && view.hasFocus() && view.canGoBack()
                    && nativeEditorAllowed(instance.handle, instance.document.grant(), instance.document.page(), view.getUrl())) {
                goBack(instance.handle); return true;
            }
        }
        return false;
    }
    /** Texture hosts may have no Activity-focused child; reject ambiguous offscreen focus. */
    public static boolean goBack(EmbeddedWebHost expectedOwner) {
        requireMain();
        if (expectedOwner == null || host.get() != expectedOwner) return false;
        WebView selected = null;
        for (Instance instance : VIEWS.values()) {
            if (instance.owner != expectedOwner || instance.activity != expectedOwner.activity() || !instance.active
                    || !instance.visible || instance.destroyedDocument || !instance.view.hasFocus()
                    || !nativeEditorAllowed(instance.handle, instance.document.grant(), instance.document.page(), instance.view.getUrl())) continue;
            if (selected != null) return false;
            selected = instance.view;
        }
        return selected != null && goBack(expectedOwner, selected);
    }
    /** Lazy E2E-only observer state. This has no product scheduling decisions. */
    private static final class FeatureRuntime {
        static final String INSTANCE = UUID.randomUUID().toString().replace("-", "");
        static long sequence, epoch;
    }
    static boolean featureOwnedURL(String value,String root) {
        if (value == null) return false;
        Uri original = Uri.parse(value).buildUpon().clearQuery().fragment(null).build();
        String prefix = root + "tickets/", raw = original.toString();
        return original.getUserInfo() == null && raw.startsWith(prefix)
            && raw.substring(prefix.length()).matches("[0-9a-f]{32}/[A-Za-z0-9_.-]{1,80}");
    }
    static String featureURLHash(String value) throws java.security.NoSuchAlgorithmException {
        byte[] digest = MessageDigest.getInstance("SHA-256").digest((value == null ? "" : value).getBytes(StandardCharsets.UTF_8));
        StringBuilder text = new StringBuilder(64);
        for (byte part : digest) text.append(String.format(java.util.Locale.ROOT,"%02x",part & 255));
        return text.toString();
    }
    /** Original UI queue fence and bounded inventories; no JavaScript or input. */
    public static void featureRuntimeSnapshot(String requestId,String root,String knownJSON) {
        if (!nativeFeatureEnabled() || requestId == null || !requestId.matches("[0-9a-f]{32}")
                || root == null || root.length() > 512 || !root.matches("https?://[^/?#@\\s]+/feature-fixture/v1/runs/[0-9a-f]{32}/")
                || knownJSON == null || knownJSON.length() > 65536) return;
        MAIN.post(() -> {
            try {
                requireMain();long now = System.currentTimeMillis();
                boolean complete = now > 0 && now >= FeatureRuntime.epoch && FeatureRuntime.sequence < 1000000000L
                    && VIEWS.size() <= 128 && CREATING.size() <= 128;
                FeatureRuntime.epoch = now;
                JSONArray known = new JSONArray(knownJSON);HashSet<Long> handles = new HashSet<>();
                if (known.length() > 256) throw new IllegalArgumentException("Observer inventory quota");
                for (int index = 0; index < known.length(); ++index) {
                    String raw = known.getJSONObject(index).getString("handle");
                    if (!raw.matches("[1-9][0-9]{0,18}")) throw new IllegalArgumentException("Observer handle");
                    handles.add(Long.parseLong(raw));
                }
                JSONArray views = new JSONArray(), creations = new JSONArray();
                ArrayList<Long> viewHandles = new ArrayList<>(VIEWS.keySet());Collections.sort(viewHandles);
                if (complete) for (long handle : viewHandles) {
                    Instance instance = VIEWS.get(handle);if (instance == null) { complete = false;break; }
                    String current = instance.destroyedDocument ? instance.fallbackUrl : instance.view.getUrl();
                    boolean sourceOwned = featureOwnedURL(instance.requestedUrl,root), documentOwned = featureOwnedURL(current,root);
                    if (!sourceOwned && !documentOwned && !handles.contains(handle)) continue;
                    boolean owner = host.get() == instance.owner && instance.owner.activity() == instance.activity;
                    views.put(new JSONObject().put("handle",Long.toString(handle)).put("creation",instance.creationRevision)
                        .put("grant",instance.document.grant()).put("page",instance.document.page())
                        .put("active",instance.active).put("destroyed",instance.destroyedDocument).put("closing",instance.closing)
                        .put("ownerCurrent",owner).put("foreground",owner && instance.owner.isForeground()).put("loading",instance.loading)
                        .put("sourceOwned",sourceOwned).put("documentOwned",documentOwned)
                        .put("sourceSha256",featureURLHash(instance.requestedUrl)).put("documentSha256",featureURLHash(current)));
                }
                ArrayList<Long> pendingHandles = new ArrayList<>(CREATING.keySet());Collections.sort(pendingHandles);
                if (complete) for (long handle : pendingHandles) {
                    PendingCreation pending = CREATING.get(handle);if (pending == null) { complete = false;break; }
                    boolean owned = featureOwnedURL(pending.originalSource,root);
                    if (!owned && !handles.contains(handle)) continue;
                    creations.put(new JSONObject().put("handle",Long.toString(handle)).put("creation",pending.revision)
                        .put("sourceOwned",owned).put("sourceSha256",featureURLHash(pending.originalSource)));
                }
                JSONObject renderers = WebTextureRenderer.featureSnapshot(root,handles);
                complete = complete && renderers.getBoolean("complete");
                JSONObject result = new JSONObject().put("javaWebRuntimeVersion",2).put("commandId",requestId)
                    .put("instance",FeatureRuntime.INSTANCE).put("sequence",++FeatureRuntime.sequence)
                    .put("processId",android.os.Process.myPid()).put("capturedEpochMs",now).put("complete",complete)
                    .put("views",views).put("creations",creations).put("renderers",renderers.getJSONArray("renderers"));
                nativeFeatureRuntimeResult(requestId,result.toString());
            } catch (Exception | OutOfMemoryError unavailable) {
                // Missing original observations never become successful empty inventories.
                nativeFeatureRuntimeResult(requestId,"{\"commandId\":\""+requestId+"\",\"complete\":false}");
            }
        });
    }

    // Closed E2E read only. No caller-controlled JavaScript, DOM selector or
    // expected result reaches the WebView through this entrypoint.
    /** Separate Pico-only source: current authority does not rewrite original finish. */
    public static void featurePicoCurrentDocumentRead(long handle,long creation,long grant,long page,
            String run,String requestId,String expectedSource) {
        if (!nativePicoCurrentDocumentEnabled() || run==null || !run.matches("[0-9a-f]{32}")
                || requestId==null || !requestId.matches("[0-9a-f]{32}") || expectedSource==null || expectedSource.length()>131072) return;
        final long started=SystemClock.elapsedRealtime();
        MAIN.post(() -> {
            final Instance instance=VIEWS.get(handle);final EmbeddedWebHost owner=host.get();
            if (!featurePicoCurrentOwner(instance,owner,creation,grant,page,expectedSource,started)) {
                featurePicoCurrentReply(handle,creation,grant,page,run,requestId,new JSONObject(),"",new JSONObject());return;
            }
            final String document=instance.view.getUrl();
            final JSONObject before=featurePicoCurrentSnapshot(instance,owner);
            final String script="window.__overteFeatureWebDOM?JSON.stringify(window.__overteFeatureWebDOM.read("
                +JSONObject.quote(requestId)+")):null";
            final WeakReference<Instance> observed=new WeakReference<>(instance);
            final WeakReference<EmbeddedWebHost> observedOwner=new WeakReference<>(owner);
            instance.view.evaluateJavascript(script,result -> {
                final Instance current=observed.get();final EmbeddedWebHost currentOwner=observedOwner.get();
                final JSONObject after=featurePicoCurrentSnapshot(current,host.get());
                if (!nativePicoCurrentDocumentEnabled() || !featurePicoCurrentOwner(current,currentOwner,creation,grant,page,expectedSource,started)
                        || document==null || !document.equals(current.view.getUrl()) || result==null || result.length()>8192) {
                    featurePicoCurrentReply(handle,creation,grant,page,run,requestId,before,"",after);return;
                }
                featurePicoCurrentReply(handle,creation,grant,page,run,requestId,before,result,after);
            });
        });
    }
    private static boolean featurePicoCurrentOwner(Instance instance,EmbeddedWebHost owner,long creation,long grant,long page,
            String expectedSource,long started) {
        final long age=SystemClock.elapsedRealtime()-started;
        return Looper.myLooper()==Looper.getMainLooper() && age>=0 && age<=1500 && instance!=null
            && VIEWS.get(instance.handle)==instance && instance.featureInstrumentation && !instance.overlay
            && instance.creationRevision==creation && instance.active && !instance.destroyedDocument && !instance.closing && !instance.loading
            && owner!=null && host.get()==owner && instance.owner==owner && owner.activity()!=null && owner.activity()==instance.activity
            && owner.isForeground() && instance.activity.hasWindowFocus() && expectedSource.equals(instance.requestedUrl)
            && instance.document.admits(grant,page,true,1) && nativeEditorAllowed(instance.handle,grant,page,instance.view.getUrl());
    }
    private static JSONObject featurePicoCurrentSnapshot(Instance instance,EmbeddedWebHost owner) {
        JSONObject value=new JSONObject();
        if (Looper.myLooper()!=Looper.getMainLooper() || instance==null) return value;
        try {
            value.put("handle",Long.toString(instance.handle)).put("creation",instance.creationRevision)
                .put("grant",instance.document.grant()).put("page",instance.document.page()).put("url",instance.view.getUrl())
                .put("sourceUrl",instance.requestedUrl).put("ownerCurrent",host.get()==owner && owner!=null && instance.owner==owner
                    && owner.activity()!=null && owner.activity()==instance.activity && VIEWS.get(instance.handle)==instance)
                .put("active",instance.active).put("foreground",owner!=null && owner.isForeground())
                .put("windowFocused",instance.activity.hasWindowFocus()).put("destroyed",instance.destroyedDocument)
                .put("closing",instance.closing).put("loading",instance.loading)
                .put("capturedEpochMs",System.currentTimeMillis()).put("capturedElapsedMs",SystemClock.elapsedRealtime());
        } catch (org.json.JSONException unavailable) { return new JSONObject(); }
        return value;
    }
    private static void featurePicoCurrentReply(long handle,long creation,long grant,long page,String run,String request,
            JSONObject before,String domRaw,JSONObject after) {
        try {
            String raw=new JSONObject().put("before",before).put("domRaw",domRaw).put("after",after).toString();
            if (raw.getBytes(StandardCharsets.UTF_8).length<=16384) nativePicoCurrentDocumentResult(handle,creation,grant,page,run,request,raw);
        } catch (org.json.JSONException unavailable) { /* Native original query expires without another read. */ }
    }

    public static void featureRead(long handle, long grant, long page, String requestId) {
        if (!nativeFeatureEnabled() || requestId == null || requestId.length() > 36
                || !requestId.matches("(?:ios-)?[0-9a-f]{32}")) return;
        post(handle, instance -> {
            EmbeddedWebHost owner = host.get();
            String document = instance.view.getUrl();
            if (!instance.featureInstrumentation || instance.destroyedDocument || owner == null || owner != instance.owner
                    || owner.activity() != instance.activity || !owner.isForeground() || !instance.activity.hasWindowFocus()
                    || !instance.document.admits(grant, page, true, 1)
                    || !nativeEditorAllowed(handle, grant, page, document)) return;
            String script = "window.__overteFeatureWebDOM?JSON.stringify(window.__overteFeatureWebDOM.read("
                + JSONObject.quote(requestId) + ")):null";
            instance.view.evaluateJavascript(script, result -> {
                if (VIEWS.get(handle) != instance || instance.destroyedDocument || !instance.active
                        || host.get() != owner || owner.activity() != instance.activity || !owner.isForeground()
                        || !instance.activity.hasWindowFocus() || !instance.document.admits(grant, page, true, 1)
                        || document == null || !document.equals(instance.view.getUrl())
                        || !nativeEditorAllowed(handle, grant, page, document)) return;
                nativeFeatureDOMResult(handle, grant, page, document, requestId, result);
            });
        });
    }
    public static void featurePicoReadOwned(long handle, long grant, long page, String requestId) {
        if (!nativeFeatureEnabled() || requestId == null || requestId.length() > 36
                || !requestId.matches("(?:ios-)?[0-9a-f]{32}")) return;
        post(handle, instance -> {
            EmbeddedWebHost owner = host.get();
            String document = instance.view.getUrl();
            if (!instance.featureInstrumentation || instance.destroyedDocument || owner == null || owner != instance.owner
                    || owner.activity() != instance.activity || !owner.isForeground() || !instance.activity.hasWindowFocus()
                    || !instance.document.admits(grant, page, true, 1)
                    || !nativeEditorAllowed(handle, grant, page, document)) return;
            String script = "window.__overteFeatureWebDOM?JSON.stringify(window.__overteFeatureWebDOM.readOwned("
                + JSONObject.quote(requestId) + ")):null";
            instance.view.evaluateJavascript(script, result -> {
                if (VIEWS.get(handle) != instance || instance.destroyedDocument || !instance.active
                        || host.get() != owner || owner.activity() != instance.activity || !owner.isForeground()
                        || !instance.activity.hasWindowFocus() || !instance.document.admits(grant, page, true, 1)
                        || document == null || !document.equals(instance.view.getUrl())
                        || !nativeEditorAllowed(handle, grant, page, document)) return;
                nativeFeatureDOMResult(handle, grant, page, document, requestId, result);
            });
        });
    }

    private static native void nativeFeaturePicoGeometry(long handle,long grant,long page,String document,String requestId,String result);
    private static native void nativeFeaturePicoFocus(long handle,long grant,long page,String document,String requestId,String result);
    public static void featurePicoGeometry(long handle,long grant,long page,String requestId,String control) {
        featurePicoGeometryRead(handle,grant,page,requestId,control,false,SystemClock.elapsedRealtime());
    }
    public static void featurePicoFocus(long handle,long grant,long page,String requestId,String control) {
        if (!"text".equals(control) && !"foreign".equals(control)) return;
        featurePicoGeometryRead(handle,grant,page,requestId,control,true,SystemClock.elapsedRealtime());
    }
    private static void featurePicoGeometryRead(long handle,long grant,long page,String requestId,String control,boolean focused,long started) {
        if (!nativeFeatureEnabled() || requestId == null || !requestId.matches("[0-9a-f]{32}")
                || control == null || !control.matches("text|bridge|reference|second|recovery|back|reload|foreign|navigate|play|pause|seekStart|seek|scroll-up|scroll-down")) return;
        MAIN.post(() -> {
            Instance instance=VIEWS.get(handle);
            if (instance==null) { featurePicoReadResult(handle,grant,page,"",requestId,"null",focused);return; }
            EmbeddedWebHost owner = host.get();String document = instance.view.getUrl();
            long elapsed=SystemClock.elapsedRealtime()-started;
            if (elapsed<0 || elapsed>=4000 || !instance.featureInstrumentation || instance.destroyedDocument || !instance.active || owner == null || owner != instance.owner
                    || owner.activity() != instance.activity || !owner.isForeground() || !instance.activity.hasWindowFocus()
                    || !instance.document.admits(grant,page,true,1) || !nativeEditorAllowed(handle,grant,page,document)) {
                featurePicoReadResult(handle,grant,page,document,requestId,"null",focused);return;
            }
            String script = "window.__overteFeatureWebDOM?JSON.stringify(window.__overteFeatureWebDOM.readGeometry("
                + JSONObject.quote(requestId) + "," + JSONObject.quote(control) + ")):null";
            instance.view.evaluateJavascript(script,result -> {
                long age=SystemClock.elapsedRealtime()-started;
                if (age<0 || age>=4000 || VIEWS.get(handle) != instance || instance.destroyedDocument || !instance.active || host.get() != owner
                        || owner.activity() != instance.activity || !owner.isForeground() || !instance.activity.hasWindowFocus()
                        || !instance.document.admits(grant,page,true,1) || document == null || !document.equals(instance.view.getUrl())
                        || !nativeEditorAllowed(handle,grant,page,document)) {
                    featurePicoReadResult(handle,grant,page,document,requestId,"null",focused);return;
                }
                if (focused) {
                    try {
                        Object decoded=new JSONArray("["+result+"]").get(0);
                        JSONObject original=new JSONObject((String)decoded);
                        if (!original.getJSONObject("editor").getBoolean("focused")) {
                            // Read-only focus retries stay tied to the original
                            // owner/activity/instance/document and a fixed deadline.
                            MAIN.postDelayed(() -> {
                                if (VIEWS.get(handle)==instance && host.get()==owner && owner.activity()==instance.activity
                                        && document.equals(instance.view.getUrl())) {
                                    featurePicoGeometryRead(handle,grant,page,requestId,control,true,started);
                                } else featurePicoReadResult(handle,grant,page,document,requestId,"null",true);
                            },20);return;
                        }
                    } catch (Exception unavailable) { featurePicoReadResult(handle,grant,page,document,requestId,"null",true);return; }
                    featurePicoReadResult(handle,grant,page,document,requestId,result,true);
                } else featurePicoReadResult(handle,grant,page,document,requestId,result,false);
            });
        });
    }
    private static void featurePicoReadResult(long handle,long grant,long page,String document,String requestId,String result,boolean focused) {
        if (focused) nativeFeaturePicoFocus(handle,grant,page,document==null ? "" : document,requestId,result);
        else nativeFeaturePicoGeometry(handle,grant,page,document==null ? "" : document,requestId,result);
    }
    public static void evaluate(long handle, long grant, long page, String javascript) {
        post(handle, instance -> {
            if (instance.destroyedDocument || !instance.document.admits(grant, page, true, 1)) return;
            instance.view.evaluateJavascript(javascript, null);
        });
    }
    public static void edit(long handle, long grant, long page, String expectedDocument, String command) {
        input(handle, instance -> {
            if (command == null || command.getBytes(StandardCharsets.UTF_8).length > 65536
                    || !instance.document.admits(grant, page, true, 1)
                    || !nativeEditorAllowed(handle, grant, page, expectedDocument)
                    || !nativeEditorAllowed(handle, grant, page, instance.view.getUrl())) return;
            try {
                String encoded = new JSONObject(command).toString();
                instance.view.evaluateJavascript("window.__overteEditor&&window.__overteEditor.edit(" + encoded + ");", null);
            } catch (org.json.JSONException invalid) { /* Only a bounded editor command object is accepted. */ }
        });
    }
    public static void evaluateResult(long handle, long grant, long page, long request, String javascript) {
        post(handle, instance -> {
            if (instance.destroyedDocument || !instance.document.admits(grant, page, true, 1)) return;
            instance.view.evaluateJavascript(javascript, result -> {
                if (result != null && result.length() <= 65536 && instance.document.admits(grant, page, true, result.getBytes(StandardCharsets.UTF_8).length))
                    nativeResult(handle, grant, page, request, result);
            });
        });
    }
    /** Private native input: never grants evaluateJavascript or EventBridge authority. */
    public static void wheel(long handle, long grant, long page, String expectedDocument,
            float x, float y, float pixelX, float pixelY, float angleX, float angleY, boolean pixelMode) {
        input(handle, instance -> {
            if (!instance.document.admits(grant, page, true, 1)
                    || !nativeEditorAllowed(handle, grant, page, expectedDocument)
                    || !nativeEditorAllowed(handle, grant, page, instance.view.getUrl())) return;
            instance.dispatchWheel(x, y, pixelX, pixelY, angleX, angleY, pixelMode);
        });
    }
    public static void pointer(long handle, int action, float x, float y) {
        input(handle, instance -> instance.dispatchPointer(action, x, y));
    }
    public static void focus(long handle, boolean focused) {
        input(handle, instance -> {
            if (focused) { instance.view.requestFocus(); instance.editorPublish(); }
            else { instance.cancelInput(); }
        });
    }
    private static final class Instance {
        final long handle;
        long creationRevision;
        final WebView view;
        final boolean overlay;
        final String bootstrap, editorBootstrap;
        final boolean featureInstrumentation = nativeFeatureEnabled();
        final WebDocumentState document = new WebDocumentState();
        final WebResourceLease resources;
        Rect bounds, clip;
        boolean destroyedDocument, closing;
        String fallbackUrl;
        WebNavigationArchive archive;
        final WebAudioLifecycle audio;
        WebTextureScale textureScale;
        final EmbeddedWebHost owner;
        final Activity activity;
        final WebTextureRenderer renderer;
        ScriptHandler script, editorScript;
        boolean active = true, visible = true, loading, bridge;
        final WebPointerState pointerState = new WebPointerState();
        int status;
        long pickerLease;
        String requestedUrl = "about:blank";
        Instance(long handle, WebView view, boolean overlay, String bootstrap, String editorBootstrap,
                EmbeddedWebHost owner, Activity activity, WebTextureRenderer renderer) {
            this.handle = handle; this.view = view; this.overlay = overlay; this.bootstrap = bootstrap; this.editorBootstrap = editorBootstrap;
            this.owner = owner; this.activity = activity; this.renderer = renderer;
            resources = new WebResourceLease(new WebResourceLease.Native() {
                public long begin(long creation, long grant, long page, String document) {
                    return nativeBeginResourceLoad(handle, creation, grant, page, document);
                }
                public boolean bind(WebResourceLease.Ticket ticket, long actualPage, String document) {
                    return nativeBindResourcePage(handle, ticket.creation, ticket.grant, ticket.load, ticket.page, actualPage, document);
                }
                public boolean current(WebResourceLease.Ticket ticket) {
                    return nativeResourceCurrent(handle, ticket.creation, ticket.grant, ticket.load, ticket.page);
                }
                public WebResourceLease.Response request(WebResourceLease.Ticket ticket, String url, boolean mainFrame, String method) {
                    return nativeRequest(handle, ticket.creation, ticket.grant, ticket.load, ticket.page, url, mainFrame, method);
                }
            });
            boolean available;
            try { available = WebViewFeature.isFeatureSupported(WebViewFeature.MUTE_AUDIO); }
            catch (RuntimeException providerFailure) { available = false; }
            final boolean supported = available;
            audio = new WebAudioLifecycle(new WebAudioLifecycle.Output() {
                @Override public boolean mute(boolean value) {
                    if (!supported || destroyedDocument) return false;
                    WebViewCompat.setAudioMuted(view, value);
                    return WebViewCompat.isAudioMuted(view) == value;
                }
                @Override public void closeDocument() { closeForAudio(); }
            });
        }
        boolean prepareResources(String url) {
            return url != null && resources.begin(creationRevision, document.grant(), document.page(), url);
        }
        boolean beginAudioNavigation(String url) {
            if (destroyedDocument) return false;
            fallbackUrl = url == null ? view.getUrl() : url;
            return audio.suspend();
        }
        void closeForAudio() {
            if (destroyedDocument) return;
            if (fallbackUrl == null) fallbackUrl = view.getUrl();
            if (archive == null) {
                android.webkit.WebBackForwardList saved = view.copyBackForwardList();
                ArrayList<String> urls = new ArrayList<>();
                int start = Math.max(0, saved.getCurrentIndex() - 63);
                for (int i = start; i < Math.min(saved.getSize(), start + 128); ++i) urls.add(saved.getItemAtIndex(i).getUrl());
                archive = new WebNavigationArchive(); archive.remember(urls, saved.getCurrentIndex() - start);
            }
            destroyedDocument = true;
            resources.revoke(); document.close(); cancelInput();
            if (renderer != null) renderer.close();
            if (overlay) owner.removeTabletView(view);
            if (script != null) { script.remove(); script = null; }
            if (editorScript != null) { editorScript.remove(); editorScript = null; }
            view.stopLoading(); view.destroy();
            if (!closing) reportSuspended();
        }
        void reportSuspended() {
            nativeSuspended(handle, creationRevision, nativeLifecycleRevision(handle), fallbackUrl == null ? requestedUrl : fallbackUrl,
                archive != null && archive.back(), archive != null && archive.forward());
        }
        void resumeArchive(int delta) {
            String url = delta == 0 ? fallbackUrl : archive == null ? null : archive.peek(delta);
            long revision = nativeLifecycleRevision(handle);
            if (url == null || nativeGeneration(handle) != revision
                    || !nativeNavigation(handle, revision, url, true, "GET")) return;
            if (delta != 0) archive.select(delta);
            nativeResumeRequest(handle, creationRevision, revision, url);
        }
        void navigateHistory(int delta) {
            android.webkit.WebBackForwardList history = view.copyBackForwardList();
            int index = history.getCurrentIndex() + delta;
            if (index < 0 || index >= history.getSize()) return;
            String target = history.getItemAtIndex(index).getUrl();
            if (!nativeNavigation(handle, document.grant(), target, true, "GET") || !beginAudioNavigation(target)) return;
            document.begin(document.grant());
            if (prepareResources(target)) { if (delta < 0) view.goBack(); else view.goForward(); }
        }
        void navigateArchive(int delta) {
            String url = archive.peek(delta);
            if (url == null || !nativeNavigation(handle, document.grant(), url, true, "GET")) return;
            if (beginAudioNavigation(url)) { document.begin(document.grant()); if (prepareResources(url)) { archive.select(delta); view.loadUrl(url); } }
        }
        void commitAudio() {
            if (destroyedDocument || loading || !visible || !owner.isForeground()) return;
            long revision = document.grant(), page = document.page(); String url = view.getUrl();
            WebAudioLifecycle.Ticket ticket = audio.document(this, owner, revision, page, url);
            WebViewCompat.postVisualStateCallback(view, page, ignored -> {
                if (destroyedDocument || host.get() != owner || owner.activity() != activity) return;
                boolean current = nativeEditorAllowed(handle, revision, page, url);
                audio.audible(ticket, this, host.get(), document.grant(), document.page(), view.getUrl(),
                    visible, owner.isForeground(), nativeGeneration(handle) == revision, current && !loading);
            });
        }
        void configureBridge(String url) {
            requestedUrl = url;
            if (script != null) { script.remove(); script = null; }
            if (editorScript != null) { editorScript.remove(); editorScript = null; }
            if (bridge) WebViewCompat.removeWebMessageListener(view, "__overteNative");
            if (bridge) WebViewCompat.removeWebMessageListener(view, "__overteEditorNative");
            bridge = WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER)
                && WebViewFeature.isFeatureSupported(WebViewFeature.DOCUMENT_START_SCRIPT);
            status = bridge ? READY : BRIDGE_UNAVAILABLE;
            if (!bridge) return;
            String origin = origin(url);
            if (origin == null) { bridge = false; status = BRIDGE_UNAVAILABLE; return; }
            // The private editor listener never exposes a Qt channel or a script grant.
            // Every message is still checked against the actual main-frame origin and document epoch natively.
            WebViewCompat.addWebMessageListener(view, "__overteEditorNative", Collections.singleton("*"),
                (source, message, sourceOrigin, mainFrame, reply) -> receive(source, message, sourceOrigin, mainFrame, true));
            editorScript = WebViewCompat.addDocumentStartJavaScript(view, editorBootstrap, Collections.singleton("*"));
            WebViewCompat.addWebMessageListener(view, "__overteNative", Collections.singleton(origin),
                (source, message, sourceOrigin, mainFrame, reply) -> receive(source, message, sourceOrigin, mainFrame, false));
            script = WebViewCompat.addDocumentStartJavaScript(view, bootstrap, Collections.singleton(origin));
        }
        void receive(WebView source, WebMessageCompat message, Uri sourceOrigin, boolean mainFrame, boolean editor) {
            if (source != view || !active || (editor && (!owner.isForeground() || !activity.hasWindowFocus())) || message.getType() != WebMessageCompat.TYPE_STRING) return;
            String encoded = message.getData();
            if (encoded == null || encoded.length() > 65536) return;
            int bytes = encoded.getBytes(StandardCharsets.UTF_8).length;
            try {
                JSONObject envelope = new JSONObject(encoded);
                long grant = Long.parseLong(envelope.getString("grant"));
                long page = Long.parseLong(envelope.getString("page"));
                if (!document.admits(grant, page, mainFrame, bytes)) return;
                String type = editor ? "editor" : envelope.getString("type");
                if (!editor && !"channel".equals(type)) return;
                String payload = editor ? envelope.getJSONObject("payload").toString() : envelope.getString("payload");
                nativeMessage(handle, grant, page, view.getUrl(), sourceOrigin.toString(), mainFrame, type, payload);
            } catch (Exception invalid) { /* No untrusted payload is logged. */ }
        }
        void authorize() {
            if (!active || !visible || !bridge || loading) return;
            EmbeddedWebHost owner = host.get();
            if (owner == null || !owner.isForeground()) return;
            String arguments = JSONObject.quote(Long.toString(document.grant())) + ","
                + JSONObject.quote(Long.toString(document.page()));
            String javascript = "";
            if (nativeBridgeAllowed(handle, document.grant(), document.page(), view.getUrl())) {
                javascript += "window.__overteTransport&&window.__overteTransport.authorize(" + arguments + ");";
            }
            if (nativeEditorAllowed(handle, document.grant(), document.page(), view.getUrl())) {
                javascript += "window.__overteEditorTransport&&window.__overteEditorTransport.authorize(" + arguments + ");"
                    + "window.__overteEditor&&window.__overteEditor.publish();";
            }
            view.evaluateJavascript(javascript, null);
        }
        void editorPublish() { view.evaluateJavascript("window.__overteEditor&&window.__overteEditor.publish();", null); }
        void suspend() {
            resources.revoke();
            if (destroyedDocument) { reportSuspended(); return; }
            if (!audio.suspend()) return;
            if (renderer != null) renderer.pause();
            cancelInput();
            view.evaluateJavascript("document.querySelectorAll('video,audio').forEach(function(m){m.pause();});", null);
            view.evaluateJavascript("window.__overteTransport&&window.__overteTransport.suspend();window.__overteEditorTransport&&window.__overteEditorTransport.suspend();", null);
            view.onPause();
        }
        void dispatchPointer(int action, float x, float y) {
            if (!Float.isFinite(x) || !Float.isFinite(y)) return;
            if (action == MotionEvent.ACTION_DOWN && pointerState.pressed()) dispatchPointer(MotionEvent.ACTION_CANCEL, 0, 0);
            long now = SystemClock.uptimeMillis(), down = pointerState.downTime();
            if (!pointerState.accept(action, now)) return;
            boolean hover = WebPointerState.hover(action);
            if (action == MotionEvent.ACTION_DOWN) down = pointerState.downTime();
            MotionEvent event = MotionEvent.obtain(hover ? now : down, now, action,
                overlay ? x : textureScale.pointer(x), overlay ? y : textureScale.pointer(y), 0);
            event.setSource(hover ? InputDevice.SOURCE_MOUSE : InputDevice.SOURCE_TOUCHSCREEN);
            try { if (hover) view.dispatchGenericMotionEvent(event); else view.dispatchTouchEvent(event); }
            finally { event.recycle(); }
        }
        void dispatchWheel(float x, float y, float pixelX, float pixelY, float angleX, float angleY, boolean pixelMode) {
            if (!Float.isFinite(x) || !Float.isFinite(y) || !Float.isFinite(pixelX) || !Float.isFinite(pixelY)
                    || !Float.isFinite(angleX) || !Float.isFinite(angleY)) return;
            float px = overlay ? x : textureScale.pointer(x), py = overlay ? y : textureScale.pointer(y);
            int width = overlay ? bounds.width() : textureScale.layoutWidth;
            int height = overlay ? bounds.height() : textureScale.layoutHeight;
            if (px < 0 || py < 0 || px >= width || py >= height) return;
            ViewConfiguration configuration = ViewConfiguration.get(activity);
            float horizontal = angleX / 120f, vertical = angleY / 120f;
            if (pixelMode) {
                float factorX = configuration.getScaledHorizontalScrollFactor(), factorY = configuration.getScaledVerticalScrollFactor();
                if (!Float.isFinite(factorX) || !Float.isFinite(factorY) || factorX <= 0 || factorY <= 0) return;
                horizontal = (overlay ? pixelX : textureScale.pointer(pixelX)) / factorX;
                vertical = (overlay ? pixelY : textureScale.pointer(pixelY)) / factorY;
            }
            if (!Float.isFinite(horizontal) || !Float.isFinite(vertical) || horizontal == 0 && vertical == 0) return;
            MotionEvent.PointerProperties pointer = new MotionEvent.PointerProperties();
            pointer.id = 0; pointer.toolType = MotionEvent.TOOL_TYPE_MOUSE;
            MotionEvent.PointerCoords coordinates = new MotionEvent.PointerCoords();
            coordinates.x = px; coordinates.y = py;
            coordinates.setAxisValue(MotionEvent.AXIS_HSCROLL, horizontal);
            coordinates.setAxisValue(MotionEvent.AXIS_VSCROLL, vertical);
            long now = SystemClock.uptimeMillis();
            MotionEvent event = MotionEvent.obtain(now, now, MotionEvent.ACTION_SCROLL, 1,
                new MotionEvent.PointerProperties[] { pointer }, new MotionEvent.PointerCoords[] { coordinates },
                0, 0, 1, 1, 0, 0, InputDevice.SOURCE_MOUSE, 0);
            try { view.dispatchGenericMotionEvent(event); } finally { event.recycle(); }
        }
        void cancelInput() {
            if (pointerState.pressed()) dispatchPointer(MotionEvent.ACTION_CANCEL, 0, 0);
            if (pointerState.hovering()) dispatchPointer(MotionEvent.ACTION_HOVER_EXIT, 0, 0);
            view.evaluateJavascript("window.__overteEditor&&window.__overteEditor.blur();", null);
            view.clearFocus();
        }
        void resize(int width, int height) {
            if (width <= 1 || height <= 1) return;
            textureScale = overlay ? null : new WebTextureScale(width, height, view.getResources().getDisplayMetrics().density);
            int w = overlay ? width : textureScale.width, h = overlay ? height : textureScale.height;
            int layoutWidth = overlay ? width : textureScale.layoutWidth, layoutHeight = overlay ? height : textureScale.layoutHeight;
            view.forceLayout();
            view.measure(View.MeasureSpec.makeMeasureSpec(layoutWidth, View.MeasureSpec.EXACTLY), View.MeasureSpec.makeMeasureSpec(layoutHeight, View.MeasureSpec.EXACTLY));
            view.layout(0, 0, layoutWidth, layoutHeight);
            if (renderer != null) renderer.resize(w,h);
        }
        void armTexture() {
            if (renderer != null && active && visible && !loading && host.get() == owner
                    && owner.activity() == activity && owner.isForeground()) {
                renderer.resume();
                renderer.arm(view,document.grant(),document.page(),view.getUrl());
            }
        }
        void publish() {
            if (destroyedDocument) { reportSuspended(); return; }
            int presentationStatus = status;
            if (presentationStatus == READY && bridge && !loading
                    && !nativeBridgeAllowed(handle, document.grant(), document.page(), view.getUrl())) presentationStatus = 9;
            nativeState(handle, document.grant(), document.page(), view.getUrl(), loading, archive != null ? archive.back() : view.canGoBack(), archive != null ? archive.forward() : view.canGoForward(), bridge, presentationStatus);
            EmbeddedWebHost owner = host.get(); if (owner != null && active) owner.statusChanged(view, presentationStatus);
        }
        void fail(int failure) {
            status = failure; publish(); EmbeddedWebHost owner = host.get(); if (owner != null) owner.diagnostic(failure);
            destroyOnMain(handle);
        }
        final WebViewClient client = new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView source, WebResourceRequest request) {
                boolean allowed = nativeNavigation(handle, document.grant(), request.getUrl().toString(), request.isForMainFrame(), request.getMethod());
                if (request.isForMainFrame()) {
                    if (!allowed || !beginAudioNavigation(request.getUrl().toString())) return true;
                    document.begin(document.grant());
                    if (!prepareResources(request.getUrl().toString())) return true;
                }
                return !allowed;
            }
            @Override public boolean shouldOverrideUrlLoading(WebView source, String url) {
                boolean allowed = nativeNavigation(handle, document.grant(), url, true, "GET");
                if (!allowed || !beginAudioNavigation(url)) return true;
                document.begin(document.grant());
                return !prepareResources(url);
            }
            @Override public WebResourceResponse shouldInterceptRequest(WebView source, WebResourceRequest request) {
                // The provider calls this on an IO thread. All mutable UI state is excluded.
                WebResourceLease.Ticket ticket = resources.capture();
                WebResourceLease.Response response = resources.request(ticket, request.getUrl().toString(),
                    request.isForMainFrame(), request.getMethod());
                if (response == null || response.action == WebResourceLease.Response.DENIED) return forbidden();
                if (response.action == WebResourceLease.Response.NETWORK) return null;
                return new WebResourceResponse(response.mime, response.charset, resources.body(ticket, response));
            }
            @Override public void onPageStarted(WebView source, String url, Bitmap favicon) {
                if (destroyedDocument || source != view) return;
                if (document.page() > 1 && !beginAudioNavigation(url)) return;
                document.begin(document.grant()); loading = true;
                if (!resources.pageStarted(creationRevision, document.grant(), document.page(), url)) { resources.revoke(); source.stopLoading(); return; }
                if (renderer != null) renderer.invalidate();
                nativePage(handle, document.grant(), document.page(), url); publish();
            }
            @Override public void onPageFinished(WebView source, String url) {
                if (!active || destroyedDocument || source != view || !url.equals(view.getUrl())) return;
                if (featureInstrumentation) nativeFeatureFinished(handle, document.grant(), document.page(), url);
                loading = false; if (archive != null) archive.visit(url);
                authorize(); armTexture(); commitAudio(); publish();
            }
            @Override public void doUpdateVisitedHistory(WebView source, String url, boolean reload) {
                if (renderer != null) { renderer.invalidate(); armTexture(); } publish();
            }
            @Override public void onReceivedHttpError(WebView source, WebResourceRequest request, WebResourceResponse response) {
                if (featureInstrumentation && source == view && active && !destroyedDocument && request.isForMainFrame())
                    nativeFeatureHTTPError(handle, document.grant(), document.page(), request.getUrl().toString(), response.getStatusCode());
            }
            @Override public void onReceivedSslError(WebView source, SslErrorHandler handler, SslError error) {
                handler.cancel(); status = LOAD_FAILED; loading = false; publish();
            }
            @Override public void onReceivedError(WebView source, android.webkit.WebResourceRequest request,
                                                 android.webkit.WebResourceError error) {
                if (request.isForMainFrame()) { status = LOAD_FAILED; loading = false; publish(); }
            }
            @Override public boolean onRenderProcessGone(WebView source, RenderProcessGoneDetail detail) { fail(RUNTIME_FAILED); return true; }
        };
        final WebChromeClient chrome = new WebChromeClient() {
            @Override public void onPermissionRequest(PermissionRequest request) { request.deny(); }
            @Override public void onGeolocationPermissionsShowPrompt(String origin, android.webkit.GeolocationPermissions.Callback callback) { callback.invoke(origin, false, false); }
            @Override public boolean onShowFileChooser(WebView source, ValueCallback<Uri[]> result, FileChooserParams request) {
                EmbeddedWebHost owner = host.get();
                long page = document.page(), lease = ++pickerLease;
                String sourceIdentity = requestedUrl, documentIdentity = view.getUrl();
                if (source != view || VIEWS.get(handle) != Instance.this || !active || destroyedDocument
                        || !visible || owner == null || owner != Instance.this.owner || owner.activity() != activity
                        || !owner.isForeground() || !activity.hasWindowFocus() || !INPUT.permits(INPUT.capture(), owner)
                        || !nativeFileChooserAllowed(handle, document.grant(), page, documentIdentity)) { result.onReceiveValue(null); return true; }
                WebFileChoiceLease selected = new WebFileChoiceLease(Instance.this, owner, page, sourceIdentity, documentIdentity);
                ValueCallback<Uri[]> guarded = values -> {
                    int decision = selected.consume(Instance.this, host.get(), document.page(), requestedUrl, view.getUrl(),
                        lease == pickerLease && VIEWS.get(handle) == Instance.this
                            && owner == Instance.this.owner && owner.activity() == activity,
                        active && !destroyedDocument, visible,
                        owner.isForeground() && activity.hasWindowFocus() && INPUT.permits(INPUT.capture(), owner),
                        nativeFileChooserAllowed(handle, document.grant(), document.page(), view.getUrl()));
                    if (decision == 0) return;
                    if (lease == pickerLease) ++pickerLease;
                    result.onReceiveValue(decision == 2 ? values : null);
                };
                if (!owner.chooseFiles(guarded, request)) { guarded.onReceiveValue(null); status = FILE_CHOOSER_UNAVAILABLE; publish(); }
                return true;
            }
        };
    }
    private static String origin(String url) {
        Uri target = Uri.parse(url);
        if (!"http".equals(target.getScheme()) && !"https".equals(target.getScheme())) return null;
        if (target.getHost() == null || target.getUserInfo() != null) return null;
        return target.getScheme() + "://" + target.getEncodedAuthority();
    }
    private static WebResourceResponse forbidden() {
        return new WebResourceResponse("text/plain", "UTF-8", 403, "Forbidden", Collections.emptyMap(), new ByteArrayInputStream(new byte[0]));
    }
}
