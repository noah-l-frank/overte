// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
package org.overte.web;

/** A rendered frame retains its original document and surface lease across asynchronous work. */
final class WebFrameGate {
    static final class Ticket {
        final Object owner;
        final long serial, grant, page, surface;
        final String document;
        Ticket(Object owner, long serial, long grant, long page, long surface, String document) {
            this.owner = owner; this.serial = serial; this.grant = grant; this.page = page;
            this.surface = surface; this.document = document;
        }
    }
    private final Object owner;
    private Ticket current;
    private long serial, minimumTimestamp, deliveredTimestamp;
    private int retries;
    private boolean visual, closed;
    WebFrameGate(Object owner) { if (owner == null) throw new IllegalArgumentException(); this.owner = owner; }
    synchronized Ticket begin(Object owner, long grant, long page, long surface, String document) {
        invalidate();
        if (closed || serial == Long.MAX_VALUE || this.owner != owner || grant <= 0 || page <= 0 || surface <= 0 || document == null) return null;
        current = new Ticket(owner, ++serial, grant, page, surface, document);
        return current;
    }
    synchronized boolean matches(long grant, long page, long surface, String document) {
        return current != null && current.grant == grant && current.page == page
            && current.surface == surface && current.document.equals(document);
    }
    synchronized boolean visual(Ticket ticket, long baseline) {
        if (closed || ticket == null || current != ticket) return false;
        visual = true; minimumTimestamp = baseline; deliveredTimestamp = baseline; return true;
    }
    synchronized Ticket capture() { return !closed && visual ? current : null; }
    synchronized boolean admits(Ticket ticket) { return ticket != null && capture() == ticket; }
    synchronized boolean fresh(Ticket ticket, long timestamp) {
        return admits(ticket) && timestamp > minimumTimestamp && timestamp > deliveredTimestamp;
    }
    synchronized void frameAvailable() { if (!closed) retries = 2; }
    synchronized boolean retry(Ticket ticket) {
        if (!admits(ticket) || retries == 0) return false;
        --retries; return true;
    }
    synchronized boolean deliver(Ticket ticket, long timestamp) {
        if (!fresh(ticket,timestamp)) return false;
        deliveredTimestamp = timestamp; return true;
    }
    synchronized void invalidate() { current = null; visual = false; retries = 0; }
    synchronized void close() { invalidate(); closed = true; }
}
