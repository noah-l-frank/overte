// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
package org.overte.snapshot;

import android.content.Context;
import android.content.Intent;
import android.content.ClipData;
import android.content.ComponentName;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.content.pm.ProviderInfo;
import android.content.res.AssetFileDescriptor;
import android.net.Uri;
import android.os.CancellationSignal;
import android.os.Process;
import java.io.IOException;
import java.io.InputStream;
import java.util.Map;
import java.util.LinkedHashMap;
import java.util.concurrent.atomic.AtomicReference;

/** Separate APK/UID. Only normal ACTION_SEND can supply original URI authority. */
final class SnapshotReceiverState {
    static final String PACKAGE="org.overte.e2e.snapshotreceiver";
    static final String AUTHORITY=PACKAGE+".evidence";
    private static SnapshotConsumerEvidence state;
    static synchronized SnapshotConsumerEvidence get(Context context) throws IOException {
        if(!PACKAGE.equals(context.getPackageName()) || (context.getApplicationInfo().flags&ApplicationInfo.FLAG_DEBUGGABLE)==0)
            throw new IOException("Standalone debug fixture required");
        if(state==null)state=new SnapshotConsumerEvidence(context.getFilesDir().toPath());return state;
    }
    static SnapshotConsumerEvidence.Access original(SnapshotConsumer activity,Intent intent) throws IOException {
        if(intent==null || !Intent.ACTION_SEND.equals(intent.getAction()) || intent.getType()==null || !intent.getType().startsWith("image/"))throw new IOException("Original image share required");
        Object stream=intent.getParcelableExtra(Intent.EXTRA_STREAM);ClipData clip=intent.getClipData();
        if(!(stream instanceof Uri) || clip==null || clip.getItemCount()!=1 || !stream.equals(clip.getItemAt(0).getUri())
                || (intent.getFlags()&Intent.FLAG_GRANT_READ_URI_PERMISSION)==0)throw new IOException("Original URI/ClipData/grant mismatch");
        Uri uri=(Uri)stream;
        if(!"content".equals(uri.getScheme()) || !"io.github.noah_be.overte.phone.snapshot.files".equals(uri.getAuthority())
                || uri.getQuery()!=null || uri.getFragment()!=null || uri.getPath()==null || !uri.getPath().matches("/snapshots/[^/]+"))throw new IOException("Foreign snapshot URI");
        final Context context=activity.getApplicationContext();
        ProviderInfo provider=context.getPackageManager().resolveContentProvider(uri.getAuthority(),0);
        if(provider==null || provider.applicationInfo==null || !"io.github.noah_be.overte.phone".equals(provider.packageName)
                || provider.applicationInfo.uid==Process.myUid())throw new IOException("Original Phone provider UID required");
        final int providerUid=provider.applicationInfo.uid;final ComponentName component=activity.getComponentName();
        return new SnapshotConsumerEvidence.Access() {
            final CancellationSignal cancelled=new CancellationSignal();final AtomicReference<InputStream> opened=new AtomicReference<>();
            volatile boolean descriptorOpened,descriptorClosed,streamOpened,streamClosed;
            @Override public Map<String,Object> identity() throws IOException {
                ProviderInfo current=context.getPackageManager().resolveContentProvider(uri.getAuthority(),0);
                if(current==null || current.applicationInfo==null || current.applicationInfo.uid!=providerUid || !provider.packageName.equals(current.packageName))throw new IOException("Phone provider changed");
                Map<String,Object> row=new LinkedHashMap<>();row.put("uri",uri.toString());row.put("providerPackage",current.packageName);
                row.put("providerUid",providerUid);row.put("receiverUid",Process.myUid());row.put("receiverPid",Process.myPid());
                row.put("receiverPackage",context.getPackageName());row.put("component",component.flattenToString());
                row.put("readFlag",true);row.put("clipUri",clip.getItemAt(0).getUri().toString());row.put("permissionAtOpen",granted());return row;
            }
            @Override public boolean granted() { return context.checkUriPermission(uri,Process.myPid(),Process.myUid(),Intent.FLAG_GRANT_READ_URI_PERMISSION)==PackageManager.PERMISSION_GRANTED; }
            @Override public InputStream open() throws IOException {
                if(!granted())throw new IOException("Original read grant missing");
                AssetFileDescriptor descriptor=context.getContentResolver().openAssetFileDescriptor(uri,"r",cancelled);
                if(descriptor==null)throw new IOException("Original shared descriptor missing");descriptorOpened=true;
                final InputStream stream;
                try { stream=descriptor.createInputStream();streamOpened=true; }
                catch(IOException | RuntimeException failure) { descriptor.close();descriptorClosed=true;throw failure; }
                InputStream wrapper=new InputStream() {
                    @Override public int read() throws IOException { return stream.read(); }
                    @Override public int read(byte[] bytes,int offset,int count) throws IOException { return stream.read(bytes,offset,count); }
                    @Override public void close() throws IOException {
                        IOException error=null;
                        try { stream.close();streamClosed=true; }catch(IOException failure) { error=failure; }
                        try { descriptor.close();descriptorClosed=true; }catch(IOException failure) { if(error==null)error=failure;else error.addSuppressed(failure); }
                        if(error!=null)throw error;opened.set(null);
                    }
                };
                opened.set(wrapper);if(cancelled.isCanceled()) { wrapper.close();throw new IOException("Original share cancelled"); }return wrapper;
            }
            @Override public boolean closed() { return (!descriptorOpened || descriptorClosed) && (!streamOpened || streamClosed); }
            @Override public void cancel() {
                cancelled.cancel();InputStream input=opened.get();if(input!=null)try { input.close(); }catch(IOException ignored) { /* Actual close flags retain failure. */ }
            }
            @Override public void finished() { activity.runOnUiThread(activity::finish); }
        };
    }
}
