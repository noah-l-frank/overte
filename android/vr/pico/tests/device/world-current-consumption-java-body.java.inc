// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// JNI availability/id/emission, Handler and WebView are declared host seams.
    private interface Command { void run(Instance instance); }
    static final WebInputGate INPUT=new WebInputGate();static final int RUNTIME_FAILED=1;
    static final List<JSONObject> trace=new ArrayList<>();static boolean idFault,emitFault;
    static void nativeCreated(long h,long c,boolean created){throw new AssertionError("Unexpected post refusal");}
    static String nativePicoConsumptionId(long h,long g,long p,String document,String command){
        if(idFault)throw new IllegalStateException("Explicit JNI unavailable seam");
        return id('9');
    }
    static void nativePicoConsumptionEvent(String id,String kind,String raw){
        if(emitFault)throw new IllegalStateException("Explicit JNI emission seam");
        try{trace.add(new JSONObject().put("eventId",id).put("kind",kind).put("raw",raw));}
        catch(org.json.JSONException impossible){throw new AssertionError(impossible);}
    }
    static final String command="{\"op\":\"insert\",\"text\":\"Grüße 🌍\"}";
    static void editCurrent(Instance current,String command){edit(1,6,1,current.requestedUrl,command);}
    static void noConsume(Instance current){
        MAIN.flush();need(current.view.reads==0 && trace.size()==1
            && trace.get(0).optString("kind").equals("java-entry"));
    }
    public static void main(String[] arguments)throws Exception {
        Instance current=reset();editCurrent(current,command);
        need(current.view.reads==0 && trace.size()==1 && MAIN.pending.size()==1);
        MAIN.flush();need(current.view.reads==1 && trace.size()==2 && MAIN.pending.isEmpty());
        need(current.view.script.equals("window.__overteEditor&&window.__overteEditor.edit("+new JSONObject(command).toString()+");"));
        JSONObject entry=new JSONObject(trace.get(0).getString("raw"));
        JSONObject consumed=new JSONObject(trace.get(1).getString("raw"));
        need(entry.getBoolean("isMainThread") && entry.getLong("capturedElapsedMs")>0);
        need(consumed.getJSONObject("before").getBoolean("ownerCurrent")
            && consumed.getJSONObject("after").getBoolean("ownerCurrent"));
        need(consumed.getJSONObject("after").getLong("capturedElapsedMs")>=consumed.getJSONObject("before").getLong("capturedElapsedMs"));
        need(!consumed.has("dom") && !consumed.has("text") && current.view.callback==null);
        need(entry.getString("commandUtf16Hex").contains("d83cdf0d")
            && entry.getString("commandUtf8Hex").contains("f09f8c8d"));
        java.nio.file.Files.writeString(java.nio.file.Path.of(arguments[0],"consumption-java-originals.json"),new org.json.JSONArray(trace).toString());
        current=reset();editCurrent(current,command);current.document.grant(7);noConsume(current);
        current=reset();editCurrent(current,command);host=new WeakReference<>(new EmbeddedWebHost());noConsume(current);
        current=reset();editCurrent(current,command);INPUT.update(current.owner,false);noConsume(current);
        current=reset();editCurrent(current,command);current.owner.foreground=false;noConsume(current);
        current=reset();editCurrent(current,command);current.activity.focus=false;noConsume(current);
        current=reset();editCurrent(current,command);current.visible=false;noConsume(current);
        current=reset();editCurrent(current,command);editor=false;noConsume(current);
        current=reset();editCurrent(current,command);VIEWS.remove(1L);noConsume(current);
        current=reset();editCurrent(current,"invalid JSON");noConsume(current);
        // Test-only observer failures never suppress an otherwise admitted
        // product dispatch or manufacture a Java/DOM completion.
        current=reset();idFault=true;editCurrent(current,command);MAIN.flush();need(current.view.reads==1 && trace.isEmpty());
        current=reset();emitFault=true;editCurrent(current,command);MAIN.flush();need(current.view.reads==1 && trace.isEmpty());
        current=reset();gate=false;editCurrent(current,command);MAIN.flush();need(current.view.reads==1 && trace.isEmpty());
        // Actual observer byte cap is preserved. A valid larger product edit
        // can lack trace originals and therefore cannot qualify trace success.
        current=reset();String wide="{\"text\":\""+"中".repeat(3000)+"\"}";editCurrent(current,wide);MAIN.flush();
        need(current.view.reads==1 && trace.isEmpty());
        System.out.println("PASS actual Java edit/queue/input and consumption UTF16/UTF8 originals; no DOM effect or callback success fabricated");
    }
