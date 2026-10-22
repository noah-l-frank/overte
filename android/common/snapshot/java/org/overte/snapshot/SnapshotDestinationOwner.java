// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
package org.overte.snapshot;

import java.io.IOException;
import java.io.InputStream;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** E2E-only identity and original-byte ownership, with one-send OS deletion.
 * Access is captured at the actual native destination callback. No caller URI,
 * requested digest or expected deletion count is accepted by this owner.
 */
final class SnapshotDestinationOwner {
    interface Access {
        Map<String,Object> identity() throws IOException;
        InputStream open() throws IOException;
        int delete() throws IOException;
        boolean absent() throws IOException;
    }
    private static final class Entry {
        final String request;final Access access;final boolean inserted;
        Map<String,Object> identity,original;String phase="planned",deleteId="";int deleteCount=-1;
        long acquired,checked;boolean absent,deleteIssued;
        Entry(String request,Access access,boolean inserted) { this.request=request;this.access=access;this.inserted=inserted; }
        Map<String,Object> view() {
            Map<String,Object> row=new LinkedHashMap<>();row.put("request",request);row.put("inserted",inserted);
            row.put("phase",phase);row.put("identity",identity==null ? null : new LinkedHashMap<>(identity));
            row.put("original",original==null ? null : new LinkedHashMap<>(original));row.put("acquiredEpochMs",acquired);
            row.put("deleteId",deleteId);row.put("deleteIssued",deleteIssued);row.put("deleteCount",deleteCount);
            row.put("checkedEpochMs",checked);row.put("absent",absent);return row;
        }
    }
    private final Map<String,Entry> entries=new LinkedHashMap<>();
    private static void nonce(String value) throws IOException { if(value==null || !value.matches("[0-9a-f]{32}"))throw new IOException("Invalid destination identity"); }
    synchronized void register(String request,Access access,boolean inserted) throws IOException {
        nonce(request);if(access==null || entries.size()>=64 || entries.containsKey(request))throw new IOException("Destination already owned");
        entries.put(request,new Entry(request,access,inserted));
    }
    void created(String request) throws IOException {
        Entry entry;synchronized(this) { entry=owned(request);if(!"planned".equals(entry.phase))throw new IOException("Destination creation already observed"); }
        Map<String,Object> identity=new LinkedHashMap<>(entry.access.identity());
        synchronized(this) { entry.identity=identity;entry.phase="created"; }
    }
    void published(String request) throws IOException {
        Entry entry;synchronized(this) { entry=owned(request);if(!"created".equals(entry.phase))throw new IOException("Destination creation is unproved"); }
        Map<String,Object> current=entry.access.identity();same(entry.identity,current);
        Map<String,Object> original=read(entry.access);same(current,entry.access.identity());
        synchronized(this) { entry.original=original;entry.acquired=System.currentTimeMillis();entry.phase="qualified"; }
    }
    private Entry owned(String request) throws IOException { nonce(request);Entry entry=entries.get(request);if(entry==null)throw new IOException("Foreign OS destination");return entry; }
    private static void same(Map<String,Object> one,Map<String,Object> two) throws IOException {
        if(one==null || two==null || !one.equals(two))throw new IOException("Original OS destination identity changed");
    }
    void remove(String request,String id) throws IOException {
        nonce(id);Entry entry;boolean replay;
        synchronized(this) {
            entry=owned(request);replay=!entry.deleteId.isEmpty();
            if(replay && !entry.deleteId.equals(id))throw new IOException("Second destination deletion is forbidden");
            if(!replay && (!entry.inserted || !"qualified".equals(entry.phase) || entry.original==null))throw new IOException("New OS destination ownership is unproved");
            if(!replay)entry.phase="checking-delete";
        }
        if(replay) { inspect(entry);return; }
        same(entry.identity,entry.access.identity());same(entry.original,read(entry.access));same(entry.identity,entry.access.identity());
        // Intent precedes the one real resolver deletion. A lost return is
        // resolved solely by a later independent existence query.
        synchronized(this) { entry.deleteId=id;entry.deleteIssued=true;entry.phase="deleting"; }
        try { int count=entry.access.delete();synchronized(this) { entry.deleteCount=count; } }
        catch(IOException | RuntimeException failure) { synchronized(this) { entry.phase="delete-uncertain"; }throw failure; }
        inspect(entry);
    }
    private void inspect(Entry entry) throws IOException {
        boolean absent=entry.access.absent();long now=System.currentTimeMillis();
        synchronized(this) {
            if(now<=0 || now<entry.checked)throw new IOException("OS destination clock regressed");
            if(absent && !entry.deleteIssued)throw new IOException("OS destination disappeared before owned cleanup");
            if(!absent && entry.absent)throw new IOException("Retired OS destination reappeared");
            entry.checked=now;entry.absent=absent;
            if(absent)entry.phase="retired";
        }
    }
    void inspect() throws IOException {
        List<Entry> copy;synchronized(this) { copy=new ArrayList<>(entries.values()); }
        for(Entry entry:copy)inspect(entry);
    }
    synchronized boolean retired() {
        for(Entry entry:entries.values())if(!entry.deleteIssued || !entry.absent || !"retired".equals(entry.phase))return false;
        return true;
    }
    synchronized List<Map<String,Object>> snapshot() {
        List<Map<String,Object>> result=new ArrayList<>();for(Entry entry:entries.values())result.add(entry.view());return result;
    }
    private static Map<String,Object> read(Access access) throws IOException {
        MessageDigest hash;
        try { hash=MessageDigest.getInstance("SHA-256"); }catch(NoSuchAlgorithmException impossible) { throw new IllegalStateException(impossible); }
        long started=System.nanoTime(),total=0;
        try(InputStream input=access.open()) {
            if(input==null)throw new IOException("Original OS stream is unavailable");
            byte[] buffer=new byte[65536];int count;
            while((count=input.read(buffer))!=-1) {
                if(count==0 || (total+=count)>256L*1024*1024 || System.nanoTime()-started>=15000000000L)throw new IOException("Original OS stream exceeded its bound");
                hash.update(buffer,0,count);
            }
            if(total==0 || System.nanoTime()-started>=15000000000L)throw new IOException("Original OS stream is empty or expired");
        }
        StringBuilder hex=new StringBuilder();for(byte value:hash.digest())hex.append(String.format(java.util.Locale.ROOT,"%02x",value&255));
        Map<String,Object> result=new LinkedHashMap<>();result.put("bytes",total);result.put("sha256",hex.toString());return result;
    }
}
