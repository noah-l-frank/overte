// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
package org.overte.snapshot;

import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicBoolean;

/** Pure recorder contract. Does not execute Android export or accept a device. */
public final class SnapshotExportObservationHostTest {
    private static void require(boolean value) { if (!value) throw new AssertionError("Snapshot export source contract"); }
    @SuppressWarnings("unchecked")
    private static List<Map<String, Object>> rows(Map<String, Object> value) {
        return (List<Map<String, Object>>) value.get("events");
    }
    private static String begin(SnapshotExportObservation value, long ticket) {
        return value.begin(42, ticket, 7, "save", "/private/Snapshots/original.png");
    }
    public static void main(String[] args) throws Exception {
        String mode = args[0]; SnapshotExportObservation value = new SnapshotExportObservation();
        long before = System.currentTimeMillis(); String token = begin(value, 1);
        require(token.matches("[0-9a-f]{32}"));
        if ("io-late".equals(mode)) {
            String id=value.submit(token);require(value.pending(token));
            value.event(token,"io-started",id,"");value.event(token,"cancelled","cancelled","");
            require(value.snapshot().get("activeRequest").equals("") && value.pending(token));
            value.event(token,"io-finished",id,"");value.event(token,"io-accepted",id,"");
            require(Boolean.TRUE.equals(value.snapshot().get("complete")) && !value.pending(token)
                && ((List<?>)value.snapshot().get("pendingIo")).isEmpty());
        } else if ("io-rejected".equals(mode)) {
            String id=value.submit(token);value.event(token,"io-rejected",id,"");
            require(Boolean.TRUE.equals(value.snapshot().get("complete")) && !value.pending(token));
        } else if ("io-foreign".equals(mode)) {
            value.submit(token);value.event(token,"io-finished","00000000000000000000000000000000","");
            require(Boolean.FALSE.equals(value.snapshot().get("complete")) && value.pending(token));
        } else if ("io-missing-start".equals(mode)) {
            String id=value.submit(token);value.event(token,"io-accepted",id,"");value.event(token,"io-finished",id,"");
            require(Boolean.FALSE.equals(value.snapshot().get("complete")) && value.pending(token));
        } else if ("io-duplicate-finish".equals(mode)) {
            String id=value.submit(token);value.event(token,"io-accepted",id,"");value.event(token,"io-started",id,"");
            value.event(token,"io-finished",id,"");require(!value.pending(token));
            value.event(token,"io-finished",id,"");require(Boolean.FALSE.equals(value.snapshot().get("complete")) && value.pending(token));
        } else if ("originals".equals(mode)) {
            value.event(token, "destination-created", "content://media/external/images/media/418", "");
            value.event(token, "destination-copied", "content://media/external/images/media/418", "");
            value.event(token, "destination-published", "content://media/external/images/media/418", "1");
            value.event(token, "result-ready", "success", "");
            value.event(token, "delivered", "success", "");
            Map<String, Object> result = value.snapshot();
            require(Boolean.TRUE.equals(result.get("complete")) && result.get("activeRequest").equals(""));
            long epoch = before, elapsed = 0; int sequence = 0;
            for (Map<String, Object> row : rows(result)) {
                require(row.get("request").equals(token) && row.get("handle").equals("42")
                    && row.get("ticket").equals("1") && row.get("generation").equals("7")
                    && row.get("source").equals("/private/Snapshots/original.png"));
                require(((Number) row.get("sequence")).intValue() == ++sequence);
                require(((Number) row.get("capturedEpochMs")).longValue() >= epoch
                    && ((Number) row.get("capturedEpochMs")).longValue() <= System.currentTimeMillis()
                    && ((Number) row.get("elapsedMs")).longValue() >= elapsed);
                epoch = ((Number) row.get("capturedEpochMs")).longValue(); elapsed = ((Number) row.get("elapsedMs")).longValue();
            }
            require(sequence == 6); rows(result).get(0).put("source", "foreign"); rows(result).clear();
            require(rows(value.snapshot()).size() == 6
                && rows(value.snapshot()).get(0).get("source").equals("/private/Snapshots/original.png"));
            require(!new SnapshotExportObservation().snapshot().get("instance").equals(result.get("instance")));
        } else if ("foreign".equals(mode)) {
            value.event("00000000000000000000000000000000", "delivered", "success", "");
            require(Boolean.FALSE.equals(value.snapshot().get("complete")) && rows(value.snapshot()).size() == 1);
        } else if ("duplicate-terminal".equals(mode)) {
            value.event(token, "cancelled", "cancelled", ""); value.event(token, "delivered", "success", "");
            require(Boolean.FALSE.equals(value.snapshot().get("complete")) && rows(value.snapshot()).size() == 2);
        } else if ("ack-only".equals(mode)) {
            value.event(token, "share-chosen", "org.example.receiver/.Receive", "");
            require(Boolean.TRUE.equals(value.snapshot().get("complete")) && value.snapshot().get("activeRequest").equals(token));
            require(rows(value.snapshot()).stream().noneMatch(row -> row.get("kind").equals("destination-copied")));
        } else if ("invalid".equals(mode)) {
            value.event(token, "result-ready", "expected-success", "");
            require(Boolean.FALSE.equals(value.snapshot().get("complete")) && rows(value.snapshot()).size() == 1);
            require(begin(value, 2).equals(""));
        } else if ("overlap".equals(mode)) {
            require(begin(value, 2).equals("")); require(Boolean.FALSE.equals(value.snapshot().get("complete")));
        } else if ("overflow".equals(mode)) {
            for (int i = 1; i < 256; ++i) value.event(token, "destination-copied", "content://owned/" + i, "");
            require(Boolean.TRUE.equals(value.snapshot().get("complete")));
            value.event(token, "delivered", "success", "");
            require(Boolean.FALSE.equals(value.snapshot().get("complete")) && rows(value.snapshot()).size() == 256);
            require(begin(value, 2).isEmpty() && rows(value.snapshot()).size() == 256);
        } else if ("concurrent".equals(mode)) {
            AtomicBoolean done = new AtomicBoolean(), failed = new AtomicBoolean();
            Thread[] readers = new Thread[4];
            for (int i = 0; i < readers.length; ++i) {
                readers[i] = new Thread(() -> {
                    while (!done.get()) {
                        Map<String, Object> snapshot = value.snapshot(); int sequence = 0;
                        for (Map<String, Object> row : rows(snapshot)) {
                            if (((Number) row.get("sequence")).intValue() != ++sequence || !row.get("request").equals(token)) failed.set(true);
                        }
                        if (((Number) snapshot.get("sequence")).intValue() != sequence) failed.set(true);
                    }
                }); readers[i].start();
            }
            for (int i = 0; i < 200; ++i) value.event(token, "destination-copied", "content://owned/" + i, "");
            done.set(true); for (Thread reader : readers) reader.join();
            require(!failed.get() && Boolean.TRUE.equals(value.snapshot().get("complete")));
        } else throw new AssertionError("Unknown host case");
    }
}
