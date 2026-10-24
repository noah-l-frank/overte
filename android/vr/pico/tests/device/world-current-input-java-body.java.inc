// Explicit Android/JNI scheduler and WebView boundaries around unchanged
// production method bodies. JSONObject and WebDocumentState are actual classes.
package org.overte.web;
import org.json.JSONObject;
import java.util.*;
import java.lang.ref.WeakReference;
import java.nio.charset.StandardCharsets;
import java.util.function.Consumer;
public class EmbeddedWebView {
    static final Thread main=Thread.currentThread();
    static final class Looper {
        static final Object MAIN=new Object();static Object getMainLooper(){return MAIN;}
        static Object myLooper(){return Thread.currentThread()==main?MAIN:null;}
    }
    static final class SystemClock {
        static long offset;static long elapsedRealtime(){return System.nanoTime()/1000000+offset;}
    }
    static final class Queue {
        final List<Runnable> pending=new ArrayList<>();
        void post(Runnable job){pending.add(job);}
        void flush(){while(!pending.isEmpty())pending.remove(0).run();}
    }
    static final Queue MAIN=new Queue();
    static final class Activity {boolean focus=true;boolean hasWindowFocus(){return focus;}}
    static final class EmbeddedWebHost {
        final Activity activity=new Activity();boolean foreground=true;
        Activity activity(){return activity;}boolean isForeground(){return foreground;}
    }
    static final class View {
        String url;int reads;String script;Consumer<String> callback;
        String getUrl(){return url;}
        void evaluateJavascript(String value,Consumer<String> result){reads++;script=value;callback=result;}
        void finish(String raw){Consumer<String> result=callback;callback=null;result.accept(raw);}
    }
    static final class Instance {
        final long handle=1,creationRevision=3;boolean featureInstrumentation=true,overlay=false,active=true,destroyedDocument=false,closing=false,loading=false;
        final View view=new View();final WebDocumentState document=new WebDocumentState();
        String requestedUrl;EmbeddedWebHost owner;Activity activity;
    }
    static WeakReference<EmbeddedWebHost> host=new WeakReference<>(null);
    static final Map<Long,Instance> VIEWS=new HashMap<>();
    static boolean gate=true,editor=true;
    static boolean nativePicoCurrentDocumentEnabled(){return gate;}
    static boolean nativeEditorAllowed(long h,long g,long p,String d){return editor;}
    static final List<String> replies=new ArrayList<>();
    static void nativePicoCurrentDocumentResult(long h,long c,long g,long p,String run,String request,String raw){replies.add(raw);}
    static final List<String> currentInputReplies=new ArrayList<>();
    static void nativePicoCurrentInputResult(long h,long c,long g,long p,String run,String request,String raw){currentInputReplies.add(raw);}
    // ORIGINAL_METHODS
    static void need(boolean value){if(!value)throw new AssertionError();}
    static String id(char c){char[] value=new char[32];Arrays.fill(value,c);return new String(value);}
    static Instance reset(){
        MAIN.pending.clear();replies.clear();gate=editor=true;SystemClock.offset=0;
        EmbeddedWebHost owner=new EmbeddedWebHost();host=new WeakReference<>(owner);
        Instance value=new Instance();value.owner=owner;value.activity=owner.activity;
        value.requestedUrl="http://127.0.0.1/feature-fixture/v1/runs/"+id('1')+"/tickets/"+id('2')+"/index.html";
        value.view.url=value.requestedUrl;value.document.begin(4);value.document.grant(6);VIEWS.clear();VIEWS.put(1L,value);return value;
    }
    static void read(){featurePicoCurrentDocumentRead(1,3,6,1,id('1'),id('3'),VIEWS.get(1L).requestedUrl);MAIN.flush();}
    static void readGeometry(){
        featurePicoCurrentInputRead(1,3,6,1,id('1'),id('3'),VIEWS.get(1L).requestedUrl,"text");MAIN.flush();
    }
    public static void main(String[] arguments)throws Exception {
        Instance current=reset();currentInputReplies.clear();readGeometry();need(current.view.reads==1 && currentInputReplies.isEmpty());
        need(current.view.script.equals("window.__overteFeatureWebDOM?JSON.stringify(window.__overteFeatureWebDOM.readGeometry(\""+id('3')+"\",\"text\")):null"));
        Thread.sleep(2);current.view.finish("\"readonly geometry with focused=false\"");need(currentInputReplies.size()==1 && replies.isEmpty());
        JSONObject original=new JSONObject(currentInputReplies.get(0));need(original.has("geometryRaw") && !original.has("domRaw"));
        need(original.getJSONObject("after").getLong("capturedElapsedMs")>original.getJSONObject("before").getLong("capturedElapsedMs"));
        need(current.document.grant()==6 && current.document.page()==1 && MAIN.pending.isEmpty());
        current=reset();currentInputReplies.clear();featurePicoCurrentInputRead(1,3,6,1,id('1'),id('3'),current.requestedUrl,"arbitrary-selector");MAIN.flush();need(current.view.reads==0 && currentInputReplies.isEmpty());
        current=reset();currentInputReplies.clear();gate=false;readGeometry();need(current.view.reads==0 && currentInputReplies.isEmpty());
        current=reset();currentInputReplies.clear();readGeometry();current.document.grant(7);current.view.finish("\"stale\"");need(current.view.reads==1 && new JSONObject(currentInputReplies.get(0)).getString("geometryRaw").isEmpty());
        current=reset();currentInputReplies.clear();readGeometry();host=new WeakReference<>(new EmbeddedWebHost());current.view.finish("\"foreign\"");need(new JSONObject(currentInputReplies.get(0)).getString("geometryRaw").isEmpty());
        current=reset();currentInputReplies.clear();readGeometry();VIEWS.remove(1L);current.view.finish("\"dead\"");need(new JSONObject(currentInputReplies.get(0)).getString("geometryRaw").isEmpty());
        current=reset();currentInputReplies.clear();readGeometry();SystemClock.offset=2000;current.view.finish("\"late\"");need(new JSONObject(currentInputReplies.get(0)).getString("geometryRaw").isEmpty());
        current=reset();currentInputReplies.clear();featurePicoCurrentInputRead(1,3,6,1,id('1'),id('3'),current.requestedUrl,"text");SystemClock.offset=2000;MAIN.flush();need(current.view.reads==0 && currentInputReplies.size()==1);
        current=reset();currentInputReplies.clear();readGeometry();String wide="\""+"中".repeat(3000)+"\"";need(wide.length()<8192 && wide.getBytes(StandardCharsets.UTF_8).length>8192);
        current.view.finish(wide);need(current.view.reads==1 && new JSONObject(currentInputReplies.get(0)).getString("geometryRaw").isEmpty());
        System.out.println("PASS actual current-input Java readonly geometry bodies, two bookends, no focus/retry, weak/grant/UTF8/queue/callback guards");
    }
}
