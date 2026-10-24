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
    public static void main(String[] arguments)throws Exception {
        Instance current=reset();read();need(current.view.reads==1 && replies.isEmpty());
        need(current.view.script.equals("window.__overteFeatureWebDOM?JSON.stringify(window.__overteFeatureWebDOM.read(\""+id('3')+"\")):null"));
        int weakCaptures=0;
        for(java.lang.reflect.Field field:current.view.callback.getClass().getDeclaredFields()){
            field.setAccessible(true);Object value=field.get(current.view.callback);
            need(!(value instanceof Instance) && !(value instanceof EmbeddedWebHost));
            if(value instanceof WeakReference)weakCaptures++;
        }
        need(weakCaptures==2);
        Thread.sleep(2);current.view.finish("\"original DOM bytes\"");need(replies.size()==1);
        JSONObject raw=new JSONObject(replies.get(0));JSONObject before=raw.getJSONObject("before"),after=raw.getJSONObject("after");
        need(before!=after && after.getLong("capturedElapsedMs")>before.getLong("capturedElapsedMs"));
        need(before.getLong("grant")==6 && after.getLong("grant")==6 && current.document.page()==1 && current.document.grant()==6);
        System.out.println("ORIGINAL_JAVA_BOOKENDS "+raw.toString());
        current=reset();gate=false;read();need(current.view.reads==0 && MAIN.pending.isEmpty() && replies.isEmpty());
        current=reset();current.document.grant(7);read();need(current.view.reads==0 && replies.size()==1);
        current=reset();current.activity.focus=false;read();need(current.view.reads==0 && replies.size()==1);
        current=reset();read();host=new WeakReference<>(new EmbeddedWebHost());current.view.finish("\"late owner\"");
        need(replies.size()==1 && new JSONObject(replies.get(0)).getString("domRaw").isEmpty());
        current=reset();read();current.document.grant(7);current.view.finish("\"old grant\"");
        need(replies.size()==1 && new JSONObject(replies.get(0)).getString("domRaw").isEmpty());
        current=reset();read();VIEWS.remove(1L);current.view.finish("\"unregistered\"");
        need(replies.size()==1 && new JSONObject(replies.get(0)).getString("domRaw").isEmpty());
        current=reset();read();current.destroyedDocument=true;current.view.finish("\"dead\"");
        need(replies.size()==1 && new JSONObject(replies.get(0)).getString("domRaw").isEmpty());
        current=reset();read();SystemClock.offset=2000;current.view.finish("\"late\"");
        need(replies.size()==1 && new JSONObject(replies.get(0)).getString("domRaw").isEmpty());
        current=reset();featurePicoCurrentDocumentRead(1,3,6,1,id('1'),id('3'),current.requestedUrl);SystemClock.offset=2000;MAIN.flush();
        need(current.view.reads==0 && replies.size()==1);
        current=reset();read();current.view.url="http://foreign.invalid/";current.view.finish("\"foreign document\"");
        need(replies.size()==1 && new JSONObject(replies.get(0)).getString("domRaw").isEmpty());
        current=reset();Thread wrong=new Thread(EmbeddedWebView::read);wrong.start();wrong.join();need(current.view.reads==0);
        System.out.println("PASS unchanged Java current-document bodies and actual document state; explicit Android/JNI seams");
    }
}
