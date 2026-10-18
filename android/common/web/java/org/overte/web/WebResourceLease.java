// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
package org.overte.web;

import java.io.InputStream;
import java.util.concurrent.atomic.AtomicReference;

/** IO sees immutable load tickets, never WebView, Activity, or document UI state. */
final class WebResourceLease {
    interface Native {
        long begin(long creation, long grant, long page, String document);
        boolean current(Ticket ticket);
        Response request(Ticket ticket, String url, boolean mainFrame, String method);
    }
    static final class Ticket {
        final long creation, grant, page, load;
        Ticket(long creation, long grant, long page, long load) {
            this.creation = creation; this.grant = grant; this.page = page; this.load = load;
        }
    }
    static final class Response {
        static final int DENIED = 0, LOCAL = 1, NETWORK = 2;
        final int action;
        final String mime, charset;
        private final byte[] bytes;
        // Called by the real JNI implementation: metadata and bytes from one snapshot.
        Response(int action, byte[] bytes, String mime, String charset) {
            this.action = action; this.bytes = bytes == null ? new byte[0] : bytes.clone();
            this.mime = mime; this.charset = charset;
        }
    }
    private final Native source;
    private final AtomicReference<Ticket> current = new AtomicReference<>();
    WebResourceLease(Native source) { this.source = source; }
    boolean begin(long creation, long grant, long page, String document) {
        current.set(null);
        long load = source.begin(creation, grant, page, document);
        if (load <= 0) return false;
        current.set(new Ticket(creation, grant, page, load)); return true;
    }
    void revoke() { current.set(null); }
    Ticket capture() { return current.get(); }
    boolean valid(Ticket ticket) { return ticket != null && current.get() == ticket && source.current(ticket); }
    Response request(Ticket ticket, String url, boolean mainFrame, String method) {
        if (!valid(ticket)) return null;
        Response response = source.request(ticket, url, mainFrame, method);
        return valid(ticket) ? response : null;
    }
    InputStream body(Ticket ticket, Response response) {
        return new InputStream() {
            private int position;
            @Override public int read() {
                if (!valid(ticket) || position >= response.bytes.length) return -1;
                return response.bytes[position++] & 255;
            }
            @Override public int read(byte[] buffer, int offset, int length) {
                if (buffer == null) throw new NullPointerException();
                if (offset < 0 || length < 0 || offset > buffer.length - length) throw new IndexOutOfBoundsException();
                if (length == 0) return 0;
                if (!valid(ticket) || position >= response.bytes.length) return -1;
                int count = Math.min(length, response.bytes.length - position);
                System.arraycopy(response.bytes, position, buffer, offset, count);
                position += count; return count;
            }
            @Override public int available() { return valid(ticket) ? response.bytes.length - position : 0; }
        };
    }
}
