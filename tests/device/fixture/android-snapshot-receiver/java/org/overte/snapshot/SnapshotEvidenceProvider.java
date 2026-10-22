// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
package org.overte.snapshot;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.net.Uri;
import android.os.Bundle;
import android.os.ParcelFileDescriptor;
import org.json.JSONObject;
import java.io.IOException;
import java.io.FileNotFoundException;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.HashSet;
import java.util.Arrays;
import java.util.List;

/** Shell/DUMP credential boundary. IDs only; never caller URI/path/result data. */
public final class SnapshotEvidenceProvider extends ContentProvider {
    @Override public boolean onCreate() { return true; }
    private SnapshotConsumerEvidence owner() throws IOException {
        getContext().enforceCallingPermission("android.permission.DUMP","Snapshot evidence requires lab observer credential");
        return SnapshotReceiverState.get(getContext());
    }
    @Override public Bundle call(String method,String arg,Bundle extras) {
        try {
            if(method!=null && method.startsWith("documents-")) {
                getContext().enforceCallingPermission("android.permission.DUMP","Documents evidence requires lab observer credential");
                if(arg!=null || extras==null || !(method.equals("documents-arm") || method.equals("documents-retire")))throw new IOException("Closed document command required");
                if(!extras.keySet().equals(new HashSet<>(method.equals("documents-arm") ? Arrays.asList("runId","armId") : Arrays.asList("runId"))))throw new IOException("Closed document IDs required");
                String run=extras.getString("runId");if(run==null || !run.matches("[0-9a-f]{32}"))throw new IOException("Closed document run required");
                if(method.equals("documents-arm")) {
                    String arm=extras.getString("armId");if(arm==null || !arm.matches("[0-9a-f]{32}"))throw new IOException("Closed document arm required");
                    SnapshotDocumentsState.get(getContext(),true).source.arm(run,arm);
                } else { SnapshotDocumentsState state=SnapshotDocumentsState.get(getContext(),false);if(state==null)throw new IOException("Documents not armed");state.retire(run); }
                Bundle result=new Bundle();result.putBoolean("accepted",true);return result;
            }
            SnapshotConsumerEvidence source=owner();
            if(arg!=null || extras==null)throw new IOException("Closed receiver command required");
            java.util.Set<String> keys=extras.keySet();
            if(method.equals("arm")) {
                if(!keys.equals(new HashSet<>(Arrays.asList("runId","armId"))))throw new IOException("Closed arm command required");
                source.arm(extras.getString("runId"),extras.getString("armId"));
            } else {
                if(!keys.equals(new HashSet<>(method.equals("remove-copy") ? Arrays.asList("runId","copyId") : Arrays.asList("runId"))))throw new IOException("Closed cleanup command required");
                source.checkRun(extras.getString("runId"));
                if(method.equals("cancel"))source.cancel();
                else if(method.equals("remove-copy"))source.remove(extras.getString("copyId"));
                else if(method.equals("retire"))source.retire();
                else throw new IOException("Unknown receiver operation");
            }
            Bundle result=new Bundle();result.putBoolean("accepted",true);return result; // Never consumption evidence.
        } catch(IOException | RuntimeException failure) { throw new IllegalArgumentException("Receiver command unavailable"); }
    }
    @Override public ParcelFileDescriptor openFile(Uri uri,String mode) throws FileNotFoundException {
        if(uri.getPathSegments().size()>0 && uri.getPathSegments().get(0).startsWith("documents-"))return openDocuments(uri,mode);
        try {
            SnapshotConsumerEvidence source=owner();List<String> parts=uri.getPathSegments();
            if(!"r".equals(mode) || !SnapshotReceiverState.AUTHORITY.equals(uri.getAuthority()) || uri.getQuery()!=null || uri.getFragment()!=null)throw new IOException("Closed read URI required");
            byte[] bytes;
            if(parts.size()==3 && parts.get(0).equals("observations")){
                java.util.Map<String,Object> row=source.observation(parts.get(1),parts.get(2));
                row.put("processId",android.os.Process.myPid());row.put("receiverUid",android.os.Process.myUid());row.put("receiverPackage",getContext().getPackageName());
                bytes=new JSONObject(row).toString().getBytes(StandardCharsets.UTF_8);
            }
            else if(parts.size()==4 && parts.get(0).equals("originals"))bytes=source.binary(parts.get(1),parts.get(2),parts.get(3));
            else throw new IOException("Unknown receiver source");
            ParcelFileDescriptor[] pipe=ParcelFileDescriptor.createReliablePipe();
            try { source.transfer(() -> {
                try(OutputStream output=new ParcelFileDescriptor.AutoCloseOutputStream(pipe[1])) { output.write(bytes); }
                catch(IOException failure) { source.rejected();try { pipe[1].closeWithError("Original transfer did not close"); }catch(IOException ignored) { /* Reader detects missing bytes. */ } }
            },pipe[1]); }catch(IOException | RuntimeException failure) {
                source.rejected();pipe[0].close();pipe[1].close();throw failure;
            }return pipe[0];
        } catch(IOException | RuntimeException failure) { throw new FileNotFoundException("Original receiver source unavailable"); }
    }
    private ParcelFileDescriptor openDocuments(Uri uri,String mode) throws FileNotFoundException {
        try {
            getContext().enforceCallingPermission("android.permission.DUMP","Documents evidence requires lab observer credential");
            if(!"r".equals(mode) || !SnapshotReceiverState.AUTHORITY.equals(uri.getAuthority()) || uri.getQuery()!=null || uri.getFragment()!=null)throw new IOException("Closed documents read URI required");
            SnapshotDocumentsState state=SnapshotDocumentsState.get(getContext(),false);if(state==null)throw new IOException("Documents are not armed");
            SnapshotDocumentsEvidence source=state.source;List<String> parts=uri.getPathSegments();byte[] bytes;
            if(parts.size()==3 && parts.get(0).equals("documents-observations")) {
                java.util.Map<String,Object> row=source.observation(parts.get(1),parts.get(2),state.callbacksTerminated());
                row.put("processId",android.os.Process.myPid());row.put("providerUid",android.os.Process.myUid());row.put("providerPackage",getContext().getPackageName());
                bytes=new JSONObject(row).toString().getBytes(StandardCharsets.UTF_8);
            } else if(parts.size()==4 && parts.get(0).equals("documents-originals"))bytes=source.original(parts.get(1),parts.get(2),parts.get(3));
            else throw new IOException("Unknown document evidence source");
            ParcelFileDescriptor[] pipe=ParcelFileDescriptor.createReliablePipe();
            try { source.transfer(() -> {
                try(OutputStream output=new ParcelFileDescriptor.AutoCloseOutputStream(pipe[1])) { output.write(bytes); }
                catch(IOException failure) { source.rejected();try { pipe[1].closeWithError("Original document transfer did not close"); }catch(IOException ignored) { /* EOF reader retains incomplete source. */ } }
            },pipe[1]); }catch(IOException | RuntimeException failure) { source.rejected();pipe[0].close();pipe[1].close();throw failure; }
            return pipe[0];
        } catch(IOException | RuntimeException failure) { throw new FileNotFoundException("Original documents evidence unavailable"); }
    }
    @Override public String getType(Uri uri) { return "application/octet-stream"; }
    @Override public Cursor query(Uri uri,String[] projection,String selection,String[] args,String order) { throw new UnsupportedOperationException(); }
    @Override public Uri insert(Uri uri,ContentValues values) { throw new UnsupportedOperationException(); }
    @Override public int update(Uri uri,ContentValues values,String selection,String[] args) { throw new UnsupportedOperationException(); }
    @Override public int delete(Uri uri,String selection,String[] args) { throw new UnsupportedOperationException(); }
}
