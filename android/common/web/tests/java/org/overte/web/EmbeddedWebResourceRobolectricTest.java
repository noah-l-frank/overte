// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
package org.overte.web;

import static org.junit.Assert.*;
import android.app.Activity;
import android.graphics.Rect;
import android.net.Uri;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import java.lang.ref.WeakReference;
import java.lang.reflect.Constructor;
import java.lang.reflect.Field;
import java.util.Map;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.Robolectric;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.annotation.Config;
import org.robolectric.annotation.Implementation;
import org.robolectric.annotation.Implements;
import org.robolectric.annotation.LooperMode;

/** Real shared Java/view selection; only JNI policy and navigation output are observed boundaries. */
@RunWith(RobolectricTestRunner.class)
@LooperMode(LooperMode.Mode.PAUSED)
@Config(sdk={26,35},manifest=Config.NONE,instrumentedPackages={"org.overte.web"},
        shadows={EmbeddedWebResourceRobolectricTest.NativeBoundary.class})
public final class EmbeddedWebResourceRobolectricTest {
    @Implements(value=EmbeddedWebView.class,isInAndroidSdk=false)
    public static final class NativeBoundary {
        static boolean allowed;
        static long selected, requestCreation, requestGrant, requestLoad, requestPage;
        static String requestURL, requestMethod;
        static boolean requestMain;
        static int responseAction;
        @Implementation protected static boolean nativeEditorAllowed(long h,long g,long p,String d) { return allowed; }
        @Implementation protected static void goBack(long handle) { selected=handle; }
        @Implementation protected static long nativeBeginResourceLoad(long h,long c,long g,long p,String d) { return 1; }
        @Implementation protected static boolean nativeResourceCurrent(long h,long c,long g,long l,long p) { return allowed; }
        @Implementation protected static WebResourceLease.Response nativeRequest(long h,long c,long g,long l,long p,String u,boolean m,String verb) {
            requestCreation=c; requestGrant=g; requestLoad=l; requestPage=p; requestURL=u; requestMain=m; requestMethod=verb;
            return new WebResourceLease.Response(responseAction,new byte[0],"text/html","windows-1252");
        }
    }
    public static final class OwnerActivity extends Activity {
        boolean focused=true;
        @Override public boolean hasWindowFocus() { return focused; }
    }
    static final class Host implements EmbeddedWebHost {
        OwnerActivity activity;
        boolean foreground=true;
        Host(OwnerActivity activity) { this.activity=activity; }
        public Activity activity() { return activity; }
        public boolean isForeground() { return foreground; }
        public boolean placeTabletView(WebView view,Rect bounds) { return true; }
        public void removeTabletView(WebView view) { }
        public boolean chooseFiles(ValueCallback<Uri[]> result,WebChromeClient.FileChooserParams request) { return false; }
        public boolean openExternal(Uri url) { return false; }
        public void statusChanged(WebView view,int status) { }
        public void diagnostic(int status) { }
    }
    static final class FocusView extends WebView {
        boolean focused=true;
        final Thread ownerThread=Thread.currentThread();
        FocusView(Activity activity) { super(activity); }
        @Override public boolean hasFocus() { return focused; }
        @Override public boolean canGoBack() { return true; }
        @Override public String getUrl() {
            assertSame("Interception must not read WebView UI state",ownerThread,Thread.currentThread());
            return "https://document.test/page";
        }
        @Override public void goBack() { fail("Selection must delegate the common fenced navigation entry"); }
    }
    OwnerActivity activity;
    Host owner;
    Map<Long,Object> views;
    Field hostField;
    Object previousHost;
    @SuppressWarnings("unchecked") @Before public void setup() throws Exception {
        activity=Robolectric.buildActivity(OwnerActivity.class).setup().get(); owner=new Host(activity);
        hostField=EmbeddedWebView.class.getDeclaredField("host"); hostField.setAccessible(true); previousHost=hostField.get(null);
        hostField.set(null,new WeakReference<EmbeddedWebHost>(owner));
        Field f=EmbeddedWebView.class.getDeclaredField("VIEWS"); f.setAccessible(true); views=(Map<Long,Object>)f.get(null); views.clear();
        NativeBoundary.allowed=true; NativeBoundary.selected=0; NativeBoundary.responseAction=WebResourceLease.Response.LOCAL;
    }
    @After public void cleanup() throws Exception {
        for(Object instance:views.values()) {
            WebResourceLease resources=(WebResourceLease)get(instance,"resources"); resources.revoke();
            ((WebView)get(instance,"view")).destroy();
        }
        views.clear(); hostField.set(null,previousHost);
    }
    static Object get(Object target,String name) throws Exception {
        Field f=target.getClass().getDeclaredField(name); f.setAccessible(true); return f.get(target);
    }
    static void set(Object target,String name,Object value) throws Exception {
        Field f=target.getClass().getDeclaredField(name); f.setAccessible(true); f.set(target,value);
    }
    Object instance(long handle) throws Exception {
        Class<?> type=Class.forName("org.overte.web.EmbeddedWebView$Instance");
        Constructor<?> constructor=type.getDeclaredConstructor(long.class,WebView.class,boolean.class,String.class,String.class,
                EmbeddedWebHost.class,Activity.class,WebTextureRenderer.class); constructor.setAccessible(true);
        Object result=constructor.newInstance(handle,new FocusView(activity),true,"","",owner,activity,null);
        set(result,"creationRevision",7L); ((WebDocumentState)get(result,"document")).begin(11L); views.put(handle,result); return result;
    }
    @Test public void externalURLRequiresNonemptyHostAndRejectsReservedNamespace() {
        for(String value:new String[]{"https:///missing-host","http:///missing-host","https://",
                "data:text/html,x","https://token.overte-inline.invalid/index.html","http://token.overte-inline.invalid./",
                "https://overte-embedded.invalid/1/page"}) {
            assertFalse(value,EmbeddedWebView.isExternalWebURL(Uri.parse(value)));
        }
        assertTrue(EmbeddedWebView.isExternalWebURL(Uri.parse("https://ordinary.example/page")));
    }
    @Test public void uniqueFocusedCurrentPageRoutesAndAmbiguousPagesReject() throws Exception {
        Object first=instance(101); assertTrue(EmbeddedWebView.goBack(owner)); assertEquals(101,NativeBoundary.selected);
        NativeBoundary.selected=0; Object second=instance(102);
        assertFalse(EmbeddedWebView.goBack(owner)); assertEquals(0,NativeBoundary.selected);
        ((FocusView)get(second,"view")).focused=false;
        assertTrue(EmbeddedWebView.goBack(owner)); assertEquals(101,NativeBoundary.selected);
        set(first,"visible",false); NativeBoundary.selected=0;
        assertFalse(EmbeddedWebView.goBack(owner)); assertEquals(0,NativeBoundary.selected);
    }
    @Test public void staleOwnerActivitySourceFocusAndDestroyedPageCannotNavigate() throws Exception {
        Object first=instance(101);
        NativeBoundary.allowed=false; assertFalse(EmbeddedWebView.goBack(owner));
        assertFalse(EmbeddedWebView.goBack(owner,(WebView)get(first,"view"))); NativeBoundary.allowed=true;
        activity.focused=false; assertFalse(EmbeddedWebView.goBack(owner)); activity.focused=true;
        owner.foreground=false; assertFalse(EmbeddedWebView.goBack(owner)); owner.foreground=true;
        set(first,"destroyedDocument",true); assertFalse(EmbeddedWebView.goBack(owner)); set(first,"destroyedDocument",false);
        OwnerActivity old=activity; owner.activity=Robolectric.buildActivity(OwnerActivity.class).setup().get();
        assertFalse(EmbeddedWebView.goBack(owner)); owner.activity=old;
        hostField.set(null,new WeakReference<EmbeddedWebHost>(new Host(activity))); assertFalse(EmbeddedWebView.goBack(owner));
        assertEquals(0,NativeBoundary.selected);
    }
    @Test public void realRequestFlagsAndTypedEmptyResponseCrossIOWithoutWebViewReads() throws Exception {
        Object instance=instance(101); FocusView view=(FocusView)get(instance,"view");
        WebResourceLease resources=(WebResourceLease)get(instance,"resources");
        assertTrue(resources.begin(7,11,1,"https://document.test/page"));
        WebViewClient client=(WebViewClient)get(instance,"client");
        WebResourceRequest request=new WebResourceRequest() {
            public Uri getUrl() { return Uri.parse("http://token.overte-inline.invalid/index.html"); }
            public boolean isForMainFrame() { return false; }
            public boolean isRedirect() { return false; }
            public boolean hasGesture() { return false; }
            public String getMethod() { return "HEAD"; }
            public Map<String,String> getRequestHeaders() { return java.util.Collections.emptyMap(); }
        };
        AtomicReference<Throwable> failure=new AtomicReference<>();
        Thread io=new Thread(()->{try {
            WebResourceResponse response=client.shouldInterceptRequest(view,request);
            assertNotNull(response); assertEquals("text/html",response.getMimeType()); assertEquals("windows-1252",response.getEncoding());
            assertEquals(-1,response.getData().read());
        } catch(Throwable error){failure.set(error);}}); io.start();io.join();
        if(failure.get()!=null) throw new AssertionError(failure.get());
        assertEquals(7,NativeBoundary.requestCreation);assertEquals(11,NativeBoundary.requestGrant);
        assertEquals(1,NativeBoundary.requestLoad);assertEquals(1,NativeBoundary.requestPage);
        assertFalse(NativeBoundary.requestMain);assertEquals("HEAD",NativeBoundary.requestMethod);
        assertEquals(request.getUrl().toString(),NativeBoundary.requestURL);
        NativeBoundary.responseAction=WebResourceLease.Response.DENIED;
        assertEquals(403,client.shouldInterceptRequest(view,request).getStatusCode());
        resources.revoke(); assertEquals(403,client.shouldInterceptRequest(view,request).getStatusCode());
    }
}
