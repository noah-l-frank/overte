// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
package org.overte.web;

import java.lang.ref.WeakReference;
import java.util.ArrayList;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicInteger;
import org.json.JSONArray;
import org.json.JSONObject;

/** Lazy read-only E2E ownership. Records retain no renderer, thread, View or callback. */
final class WebTextureObservation {
    private WebTextureObservation() { }
    private static final class Inventory {
        static final ArrayList<Record> records = new ArrayList<>();
        static boolean complete = true;
    }
    static final class Record {
        final String id = UUID.randomUUID().toString().replace("-", "");
        final WeakReference<WebTextureRenderer> renderer;
        final WeakReference<Thread> thread;
        final AtomicInteger main = new AtomicInteger(), gl = new AtomicInteger();
        final ArrayList<WeakReference<Object>> callbacks = new ArrayList<>();
        volatile long handle, creation;
        volatile String source;
        volatile boolean closed, released, releaseSucceeded = true;
        boolean complete = true;
        Record(WebTextureRenderer original, Thread worker) {
            renderer = new WeakReference<>(original); thread = new WeakReference<>(worker);
        }
        Runnable wrap(Runnable original, boolean onMain) {
            AtomicInteger pending = onMain ? main : gl;
            pending.incrementAndGet();
            return () -> { try { original.run(); } finally { pending.decrementAndGet(); } };
        }
        synchronized void callback(Object original) {
            callbacks.removeIf(value -> value.get() == null);
            if (callbacks.size() >= 128) { complete = false; return; }
            callbacks.add(new WeakReference<>(original));
        }
        synchronized int retainedCallbacks() {
            callbacks.removeIf(value -> value.get() == null);
            return callbacks.size();
        }
    }
    static Record create(WebTextureRenderer original, Thread worker) {
        if (!EmbeddedWebView.featureObservationEnabled()) return null;
        synchronized (Inventory.records) {
            if (Inventory.records.size() >= 128) { Inventory.complete = false; return null; }
            Record result = new Record(original,worker); Inventory.records.add(result); return result;
        }
    }
    static JSONObject snapshot(String root, Set<Long> known) throws Exception {
        JSONArray rows = new JSONArray(); boolean complete;
        synchronized (Inventory.records) {
            complete = Inventory.complete;
            ArrayList<Record> ordered = new ArrayList<>(Inventory.records);
            ordered.sort((a,b) -> a.id.compareTo(b.id));
            for (Record record : ordered) {
                if (record.handle <= 0 || record.creation <= 0 || record.source == null) { complete = false; continue; }
                boolean owned = EmbeddedWebView.featureOwnedURL(record.source,root);
                if (!owned && !known.contains(record.handle)) continue;
                int callbacks = record.retainedCallbacks();
                complete &= record.complete && record.main.get() >= 0 && record.gl.get() >= 0;
                Thread thread = record.thread.get();
                rows.put(new JSONObject().put("id",record.id).put("handle",Long.toString(record.handle))
                    .put("creation",record.creation).put("sourceOwned",owned)
                    .put("sourceSha256",EmbeddedWebView.featureURLHash(record.source))
                    .put("objectAlive",record.renderer.get() != null).put("threadAlive",thread != null && thread.isAlive())
                    .put("mainCallbacks",record.main.get()).put("glCallbacks",record.gl.get()).put("retainedCallbacks",callbacks)
                    .put("closed",record.closed).put("released",record.released).put("releaseSucceeded",record.releaseSucceeded));
            }
        }
        return new JSONObject().put("complete",complete).put("renderers",rows);
    }
}
