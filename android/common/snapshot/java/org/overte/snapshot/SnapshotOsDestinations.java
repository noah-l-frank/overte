// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
package org.overte.snapshot;

import android.content.ContentResolver;
import android.content.Context;
import android.content.pm.ProviderInfo;
import android.content.res.AssetFileDescriptor;
import android.database.Cursor;
import android.net.Uri;
import android.os.CancellationSignal;
import android.provider.MediaStore;
import android.system.Os;
import android.system.OsConstants;
import android.system.StructStat;
import java.io.FileNotFoundException;
import java.io.IOException;
import java.io.InputStream;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.Map;
import java.util.Set;
import java.util.List;
import java.util.ArrayList;
import java.util.concurrent.Executors;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

/** Original native insert callbacks own all URI access. Caller commands contain
 * only an existing export request ID. Queries and close are real Android APIs.
 */
final class SnapshotOsDestinations {
    private final SnapshotDestinationOwner owner=new SnapshotDestinationOwner();
    private final ExecutorService worker;private final ScheduledExecutorService watchdog;
    private final Map<String,Access> access=new LinkedHashMap<>();
    private final Set<String> used=new LinkedHashSet<>();
    private final Map<String,String> deletions=new LinkedHashMap<>();
    private final List<Thread> inspections=new ArrayList<>();
    private final List<ScheduledExecutorService> inspectionClocks=new ArrayList<>();
    private int pending;private boolean complete=true;private String checkId="";private long checked;
    SnapshotOsDestinations(ExecutorService worker,ScheduledExecutorService watchdog) { this.worker=worker;this.watchdog=watchdog; }
    synchronized void destination(String request,Context context,ContentResolver resolver,Uri uri,boolean inserted,String name) throws IOException {
        if(access.containsKey(request))throw new IOException("OS destination already registered");
        Access value=new Access(context,resolver,uri,name);access.put(request,value);owner.register(request,value,inserted);
        submit(request,() -> owner.created(request),null);
    }
    synchronized void published(String request) throws IOException { submit(request,() -> owner.published(request),null); }
    synchronized boolean remove(String request,String id) throws IOException {
        if(!id.matches("[0-9a-f]{32}") || used.size()>=4096 || used.contains(id) && !request.equals(deletions.get(id)))return false;
        used.add(id);deletions.put(id,request);submit(request,() -> owner.remove(request,id),null);return true;
    }
    synchronized boolean inspect(String id) throws IOException {
        if(!id.matches("[0-9a-f]{32}") || used.contains(id) || used.size()>=4096)return false;
        used.add(id);submit(null,owner::inspect,id);return true;
    }
    synchronized void external(Work operation) throws IOException { submit(null,operation,null); }
    interface Work { void run() throws IOException; }
    private void submit(String request,Work operation,String check) throws IOException {
        if(!complete || pending>=64)throw new IOException("OS destination work unavailable");
        Access selected=request==null ? null : access.get(request);
        if(request!=null && selected==null)throw new IOException("Unknown OS destination");
        ++pending;
        final boolean afterRetirement=worker.isShutdown();
        if(afterRetirement && request!=null) { --pending;throw new IOException("OS destination owner is retired"); }
        final ScheduledExecutorService timer=afterRetirement ? Executors.newSingleThreadScheduledExecutor(task -> {
            Thread thread=new Thread(task,"OverteSnapshotAbsenceDeadline");thread.setDaemon(true);return thread;
        }) : watchdog;
        if(afterRetirement)inspectionClocks.add(timer);
        Runnable operationBody=() -> {
            ScheduledFuture<?> timeout=timer.schedule(() -> {
                if(selected!=null)selected.cancel();else synchronized(SnapshotOsDestinations.this) { for(Access value:access.values())value.cancel(); }
            },15,TimeUnit.SECONDS);
            try {
                operation.run();
                if(check!=null)synchronized(SnapshotOsDestinations.this) { checkId=check;checked=System.currentTimeMillis(); }
            } catch(IOException | RuntimeException failure) { synchronized(SnapshotOsDestinations.this) { complete=false; } }
            finally { timeout.cancel(false);if(afterRetirement)timer.shutdown();synchronized(SnapshotOsDestinations.this) { --pending; } }
        };
        try {
            if(afterRetirement) {
                Thread thread=new Thread(operationBody,"OverteSnapshotAbsence");thread.setDaemon(true);inspections.add(thread);thread.start();
            } else worker.execute(operationBody);
        } catch(RuntimeException failure) { --pending;complete=false;if(afterRetirement)timer.shutdown();throw new IOException("OS destination work rejected"); }
    }
    synchronized Map<String,Object> observation() {
        Map<String,Object> result=new LinkedHashMap<>();result.put("snapshotOsDestinationsVersion",1);result.put("complete",complete);
        result.put("pending",pending);result.put("checkId",checkId);result.put("checkedEpochMs",checked);result.put("rows",owner.snapshot());return result;
    }
    synchronized boolean retired() { return complete && pending==0 && owner.retired(); }
    synchronized boolean inspectionsTerminated() {
        for(Thread thread:inspections)if(thread.isAlive())return false;
        for(ScheduledExecutorService timer:inspectionClocks)if(!timer.isTerminated())return false;
        return true;
    }

    private static final class Access implements SnapshotDestinationOwner.Access {
        final Context context;final ContentResolver resolver;final Uri uri;final String name;
        Integer providerUid;
        final CancellationSignal cancelled=new CancellationSignal();final AtomicReference<InputStream> opened=new AtomicReference<>();
        Access(Context context,ContentResolver resolver,Uri uri,String name) { this.context=context;this.resolver=resolver;this.uri=uri;this.name=name; }
        ProviderInfo provider() throws IOException {
            ProviderInfo value=context.getPackageManager().resolveContentProvider(uri.getAuthority(),0);
            if(value==null || value.applicationInfo==null || providerUid!=null && providerUid!=value.applicationInfo.uid)throw new IOException("Original OS provider changed");
            if(providerUid==null)providerUid=value.applicationInfo.uid;return value;
        }
        void cancel() { cancelled.cancel();InputStream value=opened.get();if(value!=null)try { value.close(); }catch(IOException ignored) { /* Worker retains any failure. */ } }
        @Override public Map<String,Object> identity() throws IOException {
            if(!"content".equals(uri.getScheme()) || !"media".equals(uri.getAuthority()) || uri.getQuery()!=null || uri.getFragment()!=null
                    || !uri.getPath().matches("/external(?:_primary)?/images/media/[1-9][0-9]*"))throw new IOException("New MediaStore ownership is unproved");
            ProviderInfo provider=provider();
            String owner,display,id;
            try(Cursor cursor=resolver.query(uri,new String[]{MediaStore.Images.Media._ID,MediaStore.Images.Media.DISPLAY_NAME,MediaStore.MediaColumns.OWNER_PACKAGE_NAME},null,null,null,cancelled)) {
                if(cursor==null || cursor.getCount()!=1 || !cursor.moveToFirst())throw new IOException("OS destination row is unavailable");
                id=cursor.getString(0);display=cursor.getString(1);owner=cursor.getString(2);
            }
            if(!context.getPackageName().equals(owner) || !name.equals(display) || !uri.getLastPathSegment().equals(id))throw new IOException("Foreign OS destination");
            try(AssetFileDescriptor descriptor=resolver.openAssetFileDescriptor(uri,"r",cancelled)) {
                if(descriptor==null || descriptor.getStartOffset()!=0)throw new IOException("Original OS file descriptor is unavailable");
                StructStat stat=Os.fstat(descriptor.getParcelFileDescriptor().getFileDescriptor());
                if(!OsConstants.S_ISREG(stat.st_mode) || stat.st_nlink!=1)throw new IOException("OS destination is not an original file");
                Map<String,Object> result=new LinkedHashMap<>();result.put("uri",uri.toString());result.put("providerUid",provider.applicationInfo.uid);
                result.put("ownerPackage",owner);result.put("displayName",display);result.put("device",stat.st_dev);result.put("inode",stat.st_ino);return result;
            } catch(android.system.ErrnoException failure) { throw new IOException("Original OS descriptor identity unavailable"); }
        }
        @Override public InputStream open() throws IOException {
            AssetFileDescriptor descriptor=resolver.openAssetFileDescriptor(uri,"r",cancelled);
            if(descriptor==null)throw new IOException("Original OS destination stream unavailable");
            final InputStream input;
            try { input=descriptor.createInputStream(); }catch(IOException | RuntimeException failure) { descriptor.close();throw failure; }
            InputStream result=new InputStream() {
                @Override public int read() throws IOException { return input.read(); }
                @Override public int read(byte[] data,int offset,int count) throws IOException { return input.read(data,offset,count); }
                @Override public void close() throws IOException {
                    IOException error=null;try { input.close(); }catch(IOException failure) { error=failure; }
                    try { descriptor.close(); }catch(IOException failure) { if(error==null)error=failure;else error.addSuppressed(failure); }
                    opened.set(null);if(error!=null)throw error;
                }
            };
            opened.set(result);if(cancelled.isCanceled()) { result.close();throw new IOException("OS destination read expired"); }return result;
        }
        @Override public int delete() { return resolver.delete(uri,null,null); }
        @Override public boolean absent() throws IOException {
            provider();
            try(Cursor cursor=resolver.query(uri,new String[]{MediaStore.Images.Media._ID},null,null,null,cancelled)) {
                if(cursor==null)throw new IOException("OS absence query is unavailable");if(cursor.getCount()!=0)return false;
            }
            try(AssetFileDescriptor descriptor=resolver.openAssetFileDescriptor(uri,"r",cancelled)) {
                if(descriptor==null)throw new IOException("Ambiguous OS descriptor absence");return false;
            } catch(FileNotFoundException absent) { return true; }
        }
    }
}
