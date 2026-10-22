// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
package org.overte.snapshot;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/** Passive, private E2E callback originals. Never an export-success verdict. */
final class SnapshotExportObservation {
    private static final int LIMIT = 256;
    private final String instance = UUID.randomUUID().toString().replace("-", "");
    private final long startedNanos = System.nanoTime();
    private final List<Map<String, Object>> events = new ArrayList<>();
    private final Map<String, Map<String, Object>> requests = new LinkedHashMap<>();
    private boolean complete = true;
    private long previousEpoch, previousElapsed;
    private String active = "";

    synchronized String begin(long handle, long ticket, long generation, String action, String source) {
        if (!complete) return "";
        if (!active.isEmpty() || handle <= 0 || ticket <= 0 || generation <= 0
                || !("save".equals(action) || "share".equals(action)) || !text(source, 2048) || source.isEmpty()) {
            complete = false; return "";
        }
        String token = UUID.randomUUID().toString().replace("-", "");
        Map<String, Object> identity = new LinkedHashMap<>();
        identity.put("request", token); identity.put("handle", Long.toString(handle));
        identity.put("ticket", Long.toString(ticket)); identity.put("generation", Long.toString(generation));
        identity.put("action", action); identity.put("source", source);
        requests.put(token, identity); active = token;
        event(token, "request-active", "", "");
        return token;
    }

    /** Values are actual callback arguments; no desired result is accepted. */
    synchronized void event(String token, String kind, String value, String auxiliary) {
        if (!complete) return;
        Map<String, Object> identity = requests.get(token);
        if (identity == null || !known(kind) || !text(value, 4096) || !text(auxiliary, 1024)
                || events.size() == LIMIT) { complete = false; return; }
        boolean terminal = "delivered".equals(kind) || "cancelled".equals(kind);
        if ((terminal || "result-ready".equals(kind) || "request-active".equals(kind)) && !token.equals(active)) {
            complete = false; return;
        }
        if (("result-ready".equals(kind) || "delivered".equals(kind))
                && !("success".equals(value) || "cancelled".equals(value) || "error".equals(value))) {
            complete = false; return;
        }
        long epoch = System.currentTimeMillis(), elapsed = (System.nanoTime() - startedNanos) / 1000000;
        if (epoch <= 0 || epoch < previousEpoch || elapsed < previousElapsed) { complete = false; return; }
        Map<String, Object> row = new LinkedHashMap<>(identity);
        row.put("sequence", events.size() + 1); row.put("kind", kind); row.put("value", value);
        row.put("auxiliary", auxiliary); row.put("capturedEpochMs", epoch); row.put("elapsedMs", elapsed);
        events.add(row); previousEpoch = epoch; previousElapsed = elapsed;
        if (terminal) active = "";
    }

    synchronized Map<String, Object> snapshot() {
        long epoch = System.currentTimeMillis(), elapsed = (System.nanoTime() - startedNanos) / 1000000;
        if (epoch <= 0 || epoch < previousEpoch || elapsed < previousElapsed) complete = false;
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("snapshotExportObservationVersion", 1); result.put("instance", instance);
        result.put("complete", complete); result.put("capturedEpochMs", epoch); result.put("elapsedMs", elapsed);
        result.put("sequence", events.size()); result.put("activeRequest", active);
        List<Map<String, Object>> rows = new ArrayList<>();
        for (Map<String, Object> row : events) rows.add(new LinkedHashMap<>(row));
        result.put("events", rows);
        return result;
    }

    private static boolean known(String kind) {
        return "request-active".equals(kind) || "share-uri".equals(kind) || "document-launched".equals(kind)
            || "document-result".equals(kind) || "share-chosen".equals(kind) || "destination-created".equals(kind)
            || "destination-copied".equals(kind) || "destination-published".equals(kind)
            || "destination-deleted".equals(kind) || "destination-delete-failed".equals(kind)
            || "result-ready".equals(kind) || "delivered".equals(kind) || "cancelled".equals(kind);
    }
    private static boolean text(String value, int limit) {
        if (value == null || value.length() > limit) return false;
        for (int i = 0; i < value.length(); ++i) if (value.charAt(i) < 32 || value.charAt(i) == 127) return false;
        return true;
    }
}
