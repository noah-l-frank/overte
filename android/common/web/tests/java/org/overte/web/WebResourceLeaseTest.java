// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
package org.overte.web;
import java.io.InputStream;
import java.util.Arrays;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.atomic.AtomicBoolean;

public final class WebResourceLeaseTest {
    private static void check(boolean value) { if (!value) throw new AssertionError(); }
    public static void main(String[] arguments) throws Exception {
        AtomicBoolean active = new AtomicBoolean(true);
        byte[] original = {0, (byte) 0x80, (byte) 0xff};
        WebResourceLease.Response response = new WebResourceLease.Response(1, original, "text/html", "windows-1252");
        original[0] = 123;
        CountDownLatch entered = new CountDownLatch(1), proceed = new CountDownLatch(1);
        AtomicBoolean queued = new AtomicBoolean(false);
        WebResourceLease lease = new WebResourceLease(new WebResourceLease.Native() {
            long load;
            public long begin(long creation, long grant, long page, String document) { return ++load; }
            public boolean bind(WebResourceLease.Ticket ticket, long actualPage, String document) { return actualPage == ticket.page + 1; }
            public boolean current(WebResourceLease.Ticket ticket) { return active.get() && ticket.load == load; }
            public WebResourceLease.Response request(WebResourceLease.Ticket ticket, String url, boolean main, String method) {
                if (queued.get()) { entered.countDown(); try { proceed.await(); } catch (InterruptedException e) { throw new AssertionError(e); } }
                return response;
            }
        });
        check(lease.begin(7, 9, 1, "http://token.overte-inline.invalid/index.html"));
        WebResourceLease.Ticket ticket = lease.capture();
        check(lease.request(ticket, "url", true, "GET") == response);
        check(lease.pageStarted(7,9,2,"url") && lease.capture() == ticket);
        InputStream stream = lease.body(ticket, response);
        check(Arrays.equals(stream.readAllBytes(), new byte[]{0, (byte)0x80, (byte)0xff}));
        check("windows-1252".equals(response.charset));
        InputStream revocable = lease.body(ticket, response);
        check(revocable.read() == 0); active.set(false); check(revocable.read() == -1);
        active.set(true); check(lease.begin(7, 9, 2, "url"));
        check(!lease.valid(ticket));
        ticket = lease.capture();
        InputStream empty = lease.body(ticket, new WebResourceLease.Response(1, new byte[0], "text/html", "UTF-8"));
        check(empty.read() == -1); check(response.action == WebResourceLease.Response.LOCAL);
        queued.set(true); final WebResourceLease.Ticket raced = ticket;
        AtomicBoolean denied = new AtomicBoolean(false);
        Thread io = new Thread(() -> denied.set(lease.request(raced, "url", true, "GET") == null));
        io.start(); entered.await(); lease.revoke(); proceed.countDown(); io.join();
        check(denied.get() && !lease.valid(raced));
        WebResourceLease other = new WebResourceLease(new WebResourceLease.Native() {
            public long begin(long c,long g,long p,String d) { return 1; }
            public boolean bind(WebResourceLease.Ticket t,long p,String d) { return false; }
            public boolean current(WebResourceLease.Ticket t) { return true; }
            public WebResourceLease.Response request(WebResourceLease.Ticket t,String u,boolean m,String v) { return response; }
        });
        other.begin(7,9,2,"url"); check(!other.valid(raced));
        System.out.println("PASS: immutable response bytes/charset, empty HTML, queued revoke, stream revoke, page and view isolation");
    }
}
