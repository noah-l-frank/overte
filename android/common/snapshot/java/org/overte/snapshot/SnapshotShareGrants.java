// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
package org.overte.snapshot;
import android.content.Context;
import android.content.ComponentName;
import android.content.Intent;
import android.content.pm.ActivityInfo;
import android.content.pm.PackageManager;
import android.net.Uri;
import java.io.IOException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Only actual native share/chooser callbacks supply URI/component authority. */
final class SnapshotShareGrants {
    private static final class Entry {
        final String request;final Context context;final Uri uri;final String chooser;final int chooserUid;
        String component="",revokeId="";int uid;boolean revokeIssued,granted,chooserGranted;long checked;
        Entry(String request,Context context,Uri uri,String chooser,int chooserUid) { this.request=request;this.context=context;this.uri=uri;this.chooser=chooser;this.chooserUid=chooserUid; }
        Map<String,Object> view() {
            Map<String,Object> row=new LinkedHashMap<>();row.put("request",request);row.put("uri",uri.toString());row.put("ownerUid",android.os.Process.myUid());
            row.put("component",component);row.put("receiverUid",uid);row.put("chooserComponent",chooser);row.put("chooserUid",chooserUid);
            row.put("revokeId",revokeId);row.put("revokeIssued",revokeIssued);row.put("granted",granted);row.put("chooserGranted",chooserGranted);row.put("checkedEpochMs",checked);return row;
        }
    }
    private final Map<String,Entry> entries=new LinkedHashMap<>();private final SnapshotOsDestinations queue;
    private final java.util.Set<String> inspections=new java.util.HashSet<>();
    private boolean complete=true;private String checkId="";private long checked;
    SnapshotShareGrants(SnapshotOsDestinations queue) { this.queue=queue; }
    void issued(String request,Context context,Uri uri,Intent chooser) {
        try {
            android.content.pm.ResolveInfo resolved=context.getPackageManager().resolveActivity(chooser,0);
            if(resolved==null || resolved.activityInfo==null || resolved.activityInfo.applicationInfo==null || !uri.getAuthority().equals(context.getPackageName()+".snapshot.files"))throw new IOException("Original system chooser is unavailable");
            ActivityInfo info=resolved.activityInfo;String component=new ComponentName(info.packageName,info.name).flattenToString();
            synchronized(this) {
                if(entries.size()>=64 || entries.containsKey(request) || !request.matches("[0-9a-f]{32}"))throw new IOException("Share URI already owned");
                entries.put(request,new Entry(request,context,uri,component,info.applicationInfo.uid));
            }
        } catch(IOException | RuntimeException failure) { synchronized(this) { complete=false; } }
    }
    void selected(String request,ComponentName component) {
        try {
            Entry entry;synchronized(this) { entry=entries.get(request);if(entry==null || !entry.component.isEmpty())throw new IOException("Unknown or replaced share choice"); }
            ActivityInfo actual=entry.context.getPackageManager().getActivityInfo(component,0);
            synchronized(this) { entry.component=component.flattenToString();entry.uid=actual.applicationInfo.uid; }
        } catch(IOException | PackageManager.NameNotFoundException | RuntimeException failure) { synchronized(this) { complete=false; } }
    }
    synchronized boolean revoke(String request,String id) throws IOException {
        Entry entry=entries.get(request);
        if(!complete || entry==null || !id.matches("[0-9a-f]{32}"))return false;
        if(entry.revokeIssued) {
            if(!entry.revokeId.equals(id))return false;queue.external(() -> inspect(entry));return true;
        }
        entry.revokeIssued=true;entry.revokeId=id;
        queue.external(() -> {
            entry.context.revokeUriPermission(entry.uri,Intent.FLAG_GRANT_READ_URI_PERMISSION);
            inspect(entry);
        });return true;
    }
    boolean inspect(String id) throws IOException {
        synchronized(this) { if(!id.matches("[0-9a-f]{32}") || inspections.size()>=4096 || !inspections.add(id))return false; }
        queue.external(() -> {
            List<Entry> copy;synchronized(this) { copy=new ArrayList<>(entries.values()); }
            for(Entry entry:copy)inspect(entry);
            synchronized(this) { checkId=id;checked=System.currentTimeMillis(); }
        });return true;
    }
    private void inspect(Entry entry) throws IOException {
        if(entry.uid>0) {
            final ActivityInfo current;
            try { current=entry.context.getPackageManager().getActivityInfo(ComponentName.unflattenFromString(entry.component),0); }
            catch(PackageManager.NameNotFoundException failure) { throw new IOException("Original share receiver disappeared"); }
            if(current.applicationInfo.uid!=entry.uid)throw new IOException("Original share receiver UID changed");
        }
        boolean granted=entry.uid>0 && entry.context.checkUriPermission(entry.uri,-1,entry.uid,Intent.FLAG_GRANT_READ_URI_PERMISSION)==PackageManager.PERMISSION_GRANTED;
        boolean chooserGranted=entry.context.checkUriPermission(entry.uri,-1,entry.chooserUid,Intent.FLAG_GRANT_READ_URI_PERMISSION)==PackageManager.PERMISSION_GRANTED;
        synchronized(this) { entry.granted=granted;entry.chooserGranted=chooserGranted;entry.checked=System.currentTimeMillis(); }
    }
    synchronized boolean retired() {
        if(!complete)return false;
        for(Entry entry:entries.values())if(!entry.revokeIssued || entry.checked<=0 || entry.granted || entry.chooserGranted)return false;
        return true;
    }
    synchronized Map<String,Object> observation() {
        List<Map<String,Object>> rows=new ArrayList<>();for(Entry entry:entries.values())rows.add(entry.view());
        Map<String,Object> result=new LinkedHashMap<>();result.put("snapshotShareGrantsVersion",1);result.put("complete",complete);result.put("checkId",checkId);result.put("checkedEpochMs",checked);result.put("rows",rows);return result;
    }
}
