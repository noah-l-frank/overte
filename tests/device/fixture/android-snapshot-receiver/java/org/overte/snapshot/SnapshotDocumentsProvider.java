// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
package org.overte.snapshot;

import android.database.Cursor;
import android.database.MatrixCursor;
import android.os.Binder;
import android.os.CancellationSignal;
import android.os.ParcelFileDescriptor;
import android.provider.DocumentsContract.Document;
import android.provider.DocumentsContract.Root;
import android.provider.DocumentsProvider;
import java.io.FileNotFoundException;
import java.io.IOException;
import java.util.Arrays;
import java.util.List;
import java.util.Map;

/** Normal DocumentsUI creates/writes the actual separately owned PNG.
 * The manifest requires MANAGE_DOCUMENTS; grants cover normal returned URIs.
 */
public final class SnapshotDocumentsProvider extends DocumentsProvider {
    private static final String[] ROOT_COLUMNS={Root.COLUMN_ROOT_ID,Root.COLUMN_DOCUMENT_ID,Root.COLUMN_TITLE,Root.COLUMN_SUMMARY,Root.COLUMN_FLAGS,Root.COLUMN_MIME_TYPES,Root.COLUMN_AVAILABLE_BYTES};
    private static final String[] DOC_COLUMNS={Document.COLUMN_DOCUMENT_ID,Document.COLUMN_DISPLAY_NAME,Document.COLUMN_MIME_TYPE,Document.COLUMN_SIZE,Document.COLUMN_LAST_MODIFIED,Document.COLUMN_FLAGS,
        "overte_run_id","overte_arm_id","overte_provider_instance","overte_create_uid","overte_created_epoch_ms","overte_writer_uid","overte_write_opened_epoch_ms","overte_write_closed_epoch_ms",
        "overte_device","overte_inode","overte_sha256","overte_delete_calls","overte_open_descriptors"};
    @Override public boolean onCreate() { return true; }
    private SnapshotDocumentsState state() throws IOException { SnapshotDocumentsState actual=SnapshotDocumentsState.get(getContext(),false);if(actual==null)throw new IOException("Documents are not armed");return actual; }
    private static MatrixCursor cursor(String[] projection,String[] allowed) throws FileNotFoundException {
        String[] columns=projection==null ? allowed : projection;List<String> inventory=Arrays.asList(allowed);
        if(columns.length==0 || columns.length>allowed.length)throw new FileNotFoundException("Closed columns required");
        java.util.Set<String> unique=new java.util.HashSet<>();for(String column:columns)if(!inventory.contains(column) || !unique.add(column))throw new FileNotFoundException("Unknown or repeated document column");
        return new MatrixCursor(columns);
    }
    private static FileNotFoundException unavailable() { return new FileNotFoundException("Original controlled document unavailable"); }
    @Override public Cursor queryRoots(String[] projection) throws FileNotFoundException {
        MatrixCursor result=cursor(projection,ROOT_COLUMNS);
        try {
            SnapshotDocumentsState state=SnapshotDocumentsState.get(getContext(),false);if(state==null || state.source.retired())return result;
            String root=state.source.rootId();MatrixCursor.RowBuilder row=result.newRow();
            for(String column:result.getColumnNames()) {
                Object value=column.equals(Root.COLUMN_ROOT_ID) || column.equals(Root.COLUMN_DOCUMENT_ID) ? root
                    : column.equals(Root.COLUMN_TITLE) ? "Overte Snapshot Evidence" : column.equals(Root.COLUMN_SUMMARY) ? "Controlled original PNG destination"
                    : column.equals(Root.COLUMN_FLAGS) ? Root.FLAG_SUPPORTS_CREATE | Root.FLAG_LOCAL_ONLY
                    : column.equals(Root.COLUMN_MIME_TYPES) ? "image/png" : 32L*1024*1024;row.add(value);
            }return result;
        } catch(IOException | RuntimeException failure) { throw unavailable(); }
    }
    private void add(MatrixCursor cursor,String id,Map<String,Object> actual,boolean root) throws IOException {
        MatrixCursor.RowBuilder row=cursor.newRow();
        for(String column:cursor.getColumnNames()) {
            Object value;
            if(column.equals(Document.COLUMN_DOCUMENT_ID))value=id;
            else if(column.equals(Document.COLUMN_DISPLAY_NAME))value=root ? "Overte Snapshot Evidence" : actual.get("displayName");
            else if(column.equals(Document.COLUMN_MIME_TYPE))value=root ? Document.MIME_TYPE_DIR : actual.get("mimeType");
            else if(column.equals(Document.COLUMN_FLAGS))value=root ? Document.FLAG_DIR_SUPPORTS_CREATE : Document.FLAG_SUPPORTS_WRITE | Document.FLAG_SUPPORTS_DELETE;
            else if(column.equals(Document.COLUMN_SIZE))value=root ? 0L : actual.get("bytes");
            else if(column.equals(Document.COLUMN_LAST_MODIFIED))value=root ? 0L : actual.get("createdEpochMs");
            else {
                String key;
                switch(column) {
                case "overte_run_id":key="runId";break;case "overte_arm_id":key="armId";break;case "overte_provider_instance":key="providerInstance";break;
                case "overte_create_uid":key="createUid";break;case "overte_created_epoch_ms":key="createdEpochMs";break;case "overte_writer_uid":key="writerUid";break;
                case "overte_write_opened_epoch_ms":key="writeOpenedEpochMs";break;case "overte_write_closed_epoch_ms":key="writeClosedEpochMs";break;
                case "overte_device":key="device";break;case "overte_inode":key="inode";break;case "overte_sha256":key="sha256";break;case "overte_delete_calls":key="deleteCalls";break;case "overte_open_descriptors":key="activeDescriptors";break;
                default:throw new IOException("Unknown document column");
                }value=root ? null : actual.get(key);
            }row.add(value);
        }
    }
    @Override public Cursor queryDocument(String id,String[] projection) throws FileNotFoundException {
        MatrixCursor result=cursor(projection,DOC_COLUMNS);
        try { SnapshotDocumentsEvidence source=state().source;if(source.rootId().equals(id)) { if(!source.retired())add(result,id,null,true); }
            else { Map<String,Object> row=source.metadata(id);if(row!=null)add(result,id,row,false); }return result;
        } catch(IOException | RuntimeException failure) { throw unavailable(); }
    }
    @Override public Cursor queryChildDocuments(String parent,String[] projection,String order) throws FileNotFoundException {
        MatrixCursor result=cursor(projection,DOC_COLUMNS);
        try { if(order!=null && !order.isEmpty() && !order.matches("(?:"+Document.COLUMN_DISPLAY_NAME+"|"+Document.COLUMN_LAST_MODIFIED+") (?:ASC|DESC)"))throw new IOException("Unconfigured sort input");for(Map<String,Object> row:state().source.children(parent))add(result,(String)row.get("documentId"),row,false);return result; }
        catch(IOException | RuntimeException failure) { throw unavailable(); }
    }
    @Override public String createDocument(String parent,String mime,String name) throws FileNotFoundException {
        final int actual=Binder.getCallingUid();
        try { return state().source.create(parent,mime,name,actual); }catch(IOException | RuntimeException failure) { throw unavailable(); }
    }
    @Override public ParcelFileDescriptor openDocument(String id,String mode,CancellationSignal signal) throws FileNotFoundException {
        final int caller=Binder.getCallingUid();SnapshotDocumentsEvidence source=null;String descriptor=null;ParcelFileDescriptor opened=null;
        try {
            if(signal!=null)signal.throwIfCanceled();SnapshotDocumentsState state=state();source=state.source;
            descriptor=source.reserve(id,mode,caller);final String token=descriptor;final SnapshotDocumentsEvidence original=source;
            opened=ParcelFileDescriptor.open(source.path(token).toFile(),mode.equals("w") ? ParcelFileDescriptor.MODE_WRITE_ONLY | ParcelFileDescriptor.MODE_TRUNCATE : ParcelFileDescriptor.MODE_READ_ONLY,state.handler,
                error -> { try { original.close(token,error!=null); }catch(IOException | RuntimeException failure) { original.rejected(); } });
            android.system.StructStat actual=android.system.Os.fstat(opened.getFileDescriptor());
            source.opened(token,actual.st_dev,actual.st_ino,actual.st_uid,actual.st_nlink,android.system.OsConstants.S_ISREG(actual.st_mode));
            if(signal!=null)signal.throwIfCanceled();return opened;
        } catch(IOException | RuntimeException | android.system.ErrnoException failure) {
            // Normal post-delete open must throw FileNotFoundException without
            // poisoning the independent absence source. Only an allocated
            // descriptor belongs to this attempted open's failure lifetime.
            if(source!=null && descriptor!=null) { source.rejected();if(opened==null)try { source.close(descriptor,true); }catch(IOException ignored) { source.rejected(); } }
            if(opened!=null)try { opened.close(); }catch(IOException ignored) { /* Original callback retains error. */ }throw unavailable();
        }
    }
    @Override public void deleteDocument(String id) throws FileNotFoundException {
        try { state().source.delete(id); }catch(IOException | RuntimeException failure) { throw unavailable(); }
    }
}
