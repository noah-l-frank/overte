"""Actual native SAF Java Access over explicit synthetic Android API seams.

File bytes/identity, fixture owner, native asynchronous ownership and deletion
execute on host files. Binder/ContentResolver/Os API producers are synthetic.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[4]
STUBS={
'android/content/pm/ApplicationInfo.java':'package android.content.pm; public class ApplicationInfo { public int uid; }',
'android/content/pm/ProviderInfo.java':'package android.content.pm; public class ProviderInfo { public ApplicationInfo applicationInfo; public String packageName; }',
'android/content/pm/PackageManager.java':'package android.content.pm; public abstract class PackageManager { public abstract ProviderInfo resolveContentProvider(String authority,int flags); }',
'android/content/Context.java':'''package android.content; public abstract class Context {
 public abstract android.content.pm.PackageManager getPackageManager();public abstract android.content.pm.ApplicationInfo getApplicationInfo();public abstract String getPackageName(); }''',
'android/database/Cursor.java':'''package android.database; public interface Cursor extends java.io.Closeable {
 int getCount();boolean moveToFirst();String getString(int index);int getInt(int index);long getLong(int index);void close(); }''',
'android/net/Uri.java':'''package android.net; public final class Uri {
 private final java.net.URI value;private Uri(String raw){value=java.net.URI.create(raw);}public static Uri parse(String raw){return new Uri(raw);}
 public String getScheme(){return value.getScheme();}public String getAuthority(){return value.getAuthority();}public String getQuery(){return value.getQuery();}
 public String getFragment(){return value.getFragment();}public String getPath(){return value.getPath();}public String toString(){return value.toString();}
 public java.util.List<String> getPathSegments(){return java.util.Arrays.asList(getPath().substring(1).split("/"));}public String getLastPathSegment(){java.util.List<String> p=getPathSegments();return p.get(p.size()-1);} }''',
'android/os/CancellationSignal.java':'package android.os; public class CancellationSignal { private boolean cancelled;public void cancel(){cancelled=true;}public boolean isCanceled(){return cancelled;}public void throwIfCanceled(){if(cancelled)throw new IllegalStateException("Synthetic cancellation");} }',
'android/os/ParcelFileDescriptor.java':'package android.os; public class ParcelFileDescriptor { private final java.io.FileDescriptor fd;public ParcelFileDescriptor(java.io.FileDescriptor fd){this.fd=fd;}public java.io.FileDescriptor getFileDescriptor(){return fd;} }',
'android/content/res/AssetFileDescriptor.java':'''package android.content.res; public abstract class AssetFileDescriptor implements java.io.Closeable {
 public abstract long getStartOffset();public abstract android.os.ParcelFileDescriptor getParcelFileDescriptor();public abstract java.io.InputStream createInputStream()throws java.io.IOException; }''',
'android/content/ContentResolver.java':'''package android.content; public abstract class ContentResolver {
 public abstract android.database.Cursor query(android.net.Uri uri,String[] fields,String selection,String[] args,String order,android.os.CancellationSignal signal);
 public abstract android.content.res.AssetFileDescriptor openAssetFileDescriptor(android.net.Uri uri,String mode,android.os.CancellationSignal signal)throws java.io.FileNotFoundException;
 public abstract int delete(android.net.Uri uri,String selection,String[] args);public abstract boolean documentDelete(android.net.Uri uri)throws java.io.FileNotFoundException; }''',
'android/provider/MediaStore.java':'''package android.provider;public class MediaStore {
 public static class MediaColumns { public static final String OWNER_PACKAGE_NAME="owner_package_name"; }
 public static class Images { public static class Media { public static final String _ID="_id",DISPLAY_NAME="_display_name"; } } }''',
'android/provider/DocumentsContract.java':'''package android.provider;public class DocumentsContract {
 public static class Document { public static final String COLUMN_DOCUMENT_ID="document_id",COLUMN_DISPLAY_NAME="_display_name",COLUMN_MIME_TYPE="mime_type",COLUMN_SIZE="_size"; }
 public static String getDocumentId(android.net.Uri uri){return uri.getPathSegments().get(1);}
 public static boolean deleteDocument(android.content.ContentResolver resolver,android.net.Uri uri)throws java.io.FileNotFoundException{return resolver.documentDelete(uri);} }''',
'android/system/ErrnoException.java':'package android.system;public class ErrnoException extends Exception {}',
'android/system/StructStat.java':'package android.system;public class StructStat { public long st_dev,st_ino,st_uid,st_nlink;public int st_mode; }',
'android/system/OsConstants.java':'package android.system;public class OsConstants { public static boolean S_ISREG(int mode){return (mode&0170000)==0100000;} }',
'android/system/Os.java':'''package android.system;public class Os {
 static final java.util.Map<java.io.FileDescriptor,StructStat> originals=new java.util.IdentityHashMap<>();
 public static void register(java.io.FileDescriptor fd,java.nio.file.Path path)throws java.io.IOException {
  StructStat actual=new StructStat();actual.st_dev=((Number)java.nio.file.Files.getAttribute(path,"unix:dev")).longValue();actual.st_ino=((Number)java.nio.file.Files.getAttribute(path,"unix:ino")).longValue();
  actual.st_uid=((Number)java.nio.file.Files.getAttribute(path,"unix:uid")).longValue();actual.st_nlink=((Number)java.nio.file.Files.getAttribute(path,"unix:nlink")).longValue();actual.st_mode=((Number)java.nio.file.Files.getAttribute(path,"unix:mode")).intValue();originals.put(fd,actual); }
 public static StructStat fstat(java.io.FileDescriptor fd)throws ErrnoException { StructStat actual=originals.get(fd);if(actual==null)throw new ErrnoException();return actual;} }''',
}
# The original Provider executes too; only Android Handler/Binder/PFD glue and
# its State's Context delivery are synthetic. Files and evidence stay original.
STUBS.update({
'android/os/Handler.java':'package android.os;public class Handler {}',
'android/os/Binder.java':'package android.os;public class Binder { public static int caller=1001;public static int getCallingUid(){return caller;} }',
'android/os/ParcelFileDescriptor.java':'''package android.os;public class ParcelFileDescriptor implements java.io.Closeable {
 public static final int MODE_WRITE_ONLY=1,MODE_TRUNCATE=2,MODE_READ_ONLY=4;public interface OnCloseListener { void onClose(java.io.IOException error); }
 private final java.io.FileDescriptor fd;private java.io.RandomAccessFile file;private OnCloseListener callback;private boolean closed;
 public ParcelFileDescriptor(java.io.FileDescriptor fd){this.fd=fd;}private ParcelFileDescriptor(java.io.RandomAccessFile file,OnCloseListener cb)throws java.io.IOException{this.file=file;fd=file.getFD();callback=cb;}
 public static ParcelFileDescriptor open(java.io.File path,int mode,Handler handler,OnCloseListener cb)throws java.io.IOException {
  java.io.RandomAccessFile file=new java.io.RandomAccessFile(path,mode==MODE_READ_ONLY ? "r" : "rw");if(mode!=MODE_READ_ONLY)file.setLength(0);
  android.system.Os.register(file.getFD(),path.toPath());return new ParcelFileDescriptor(file,cb);
 }
 public java.io.FileDescriptor getFileDescriptor(){return fd;}public void close()throws java.io.IOException{if(closed)return;closed=true;if(file!=null)file.close();if(callback!=null)callback.onClose(null);}
}''',
'android/provider/DocumentsProvider.java':'''package android.provider;public abstract class DocumentsProvider {
 private android.content.Context context;public void attach(android.content.Context context){this.context=context;}public android.content.Context getContext(){return context;}
 public abstract boolean onCreate();public abstract android.database.Cursor queryRoots(String[] projection)throws java.io.FileNotFoundException;
 public abstract android.database.Cursor queryDocument(String id,String[] projection)throws java.io.FileNotFoundException;
 public abstract android.database.Cursor queryChildDocuments(String parent,String[] projection,String order)throws java.io.FileNotFoundException;
 public abstract String createDocument(String parent,String mime,String name)throws java.io.FileNotFoundException;
 public abstract android.os.ParcelFileDescriptor openDocument(String id,String mode,android.os.CancellationSignal cancel)throws java.io.FileNotFoundException;
 public abstract void deleteDocument(String id)throws java.io.FileNotFoundException;
}''',
'android/database/MatrixCursor.java':'''package android.database;public class MatrixCursor implements Cursor {
 final String[] columns;final java.util.List<Object[]> rows=new java.util.ArrayList<>();int selected=-1;
 public MatrixCursor(String[] columns){this.columns=columns;}public String[] getColumnNames(){return columns;}public RowBuilder newRow(){Object[] values=new Object[columns.length];rows.add(values);return new RowBuilder(values);}
 public static class RowBuilder{final Object[] values;int index;RowBuilder(Object[] values){this.values=values;}public RowBuilder add(Object value){values[index++]=value;return this;}}
 public int getCount(){return rows.size();}public boolean moveToFirst(){selected=0;return !rows.isEmpty();}public String getString(int i){return String.valueOf(rows.get(selected)[i]);}
 public int getInt(int i){return ((Number)rows.get(selected)[i]).intValue();}public long getLong(int i){return ((Number)rows.get(selected)[i]).longValue();}public void close(){}
}''',
'org/overte/snapshot/SnapshotDocumentsState.java':'''package org.overte.snapshot;final class SnapshotDocumentsState {
 static SnapshotDocumentsState assigned;final SnapshotDocumentsEvidence source;final android.os.Handler handler=new android.os.Handler();SnapshotDocumentsState(SnapshotDocumentsEvidence source){this.source=source;}
 static SnapshotDocumentsState get(android.content.Context context,boolean create){if(create)throw new AssertionError("Provider initialized state without DUMP arm");return assigned;}
}''',
})
STUBS['android/provider/DocumentsContract.java']=STUBS['android/provider/DocumentsContract.java'].replace('public static class Document {','''public static class Root {public static final String COLUMN_ROOT_ID="root_id",COLUMN_DOCUMENT_ID="document_id",COLUMN_TITLE="title",COLUMN_SUMMARY="summary",COLUMN_FLAGS="flags",COLUMN_MIME_TYPES="mime_types",COLUMN_AVAILABLE_BYTES="available_bytes";public static final int FLAG_SUPPORTS_CREATE=1,FLAG_LOCAL_ONLY=2;}
 public static class Document { public static final String MIME_TYPE_DIR="vnd.android.document/directory",COLUMN_LAST_MODIFIED="last_modified",COLUMN_FLAGS="flags";public static final int FLAG_DIR_SUPPORTS_CREATE=1,FLAG_SUPPORTS_WRITE=2,FLAG_SUPPORTS_DELETE=4;''')
PROVIDER_SOURCE=r'''package org.overte.snapshot;
import java.io.*;import java.nio.file.*;import java.util.*;import android.database.Cursor;import android.os.*;
public final class SnapshotDocumentsProviderHostTest {
 interface Work{void run()throws Exception;}static void need(boolean value){if(!value)throw new AssertionError("Original DocumentsProvider callback contract");}
 static void absent(Work action)throws Exception{try{action.run();throw new AssertionError("Absent or foreign document opened");}catch(FileNotFoundException expected){}}
 @SuppressWarnings("unchecked")public static void main(String[] args)throws Exception {
  Path root=Paths.get(args[0]);String run=SnapshotDocumentsAccessHostTest.RUN,arm=SnapshotDocumentsAccessHostTest.ARM;SnapshotDocumentsEvidence source=new SnapshotDocumentsEvidence(root);source.arm(run,arm);
  SnapshotDocumentsState.assigned=new SnapshotDocumentsState(source);SnapshotDocumentsProvider provider=new SnapshotDocumentsProvider();provider.attach(new SnapshotDocumentsAccessHostTest.Device(1002,"original"));
  need(provider.onCreate());try(Cursor roots=provider.queryRoots(null)){need(roots.getCount()==1);}
  Binder.caller=1000;String id=provider.createDocument(source.rootId(),"image/png","e2e-"+run+"-provider.png");try(Cursor children=provider.queryChildDocuments(source.rootId(),null,"_display_name ASC")){need(children.getCount()==1);}
  Binder.caller=1001;ParcelFileDescriptor writer=provider.openDocument(id,"w",new CancellationSignal());
  try(FileOutputStream output=new FileOutputStream(writer.getFileDescriptor())){output.write(new byte[]{1,2,3,4,5});}writer.close();
  Map<String,Object> row=source.observation(run,UUID.randomUUID().toString().replace("-",""),false);need((Boolean)row.get("complete"));need(((List<Map<String,Object>>)row.get("documents")).get(0).get("writerUid").equals(1001));
  ParcelFileDescriptor reader=provider.openDocument(id,"r",new CancellationSignal());try(FileInputStream input=new FileInputStream(reader.getFileDescriptor())){need(input.read()==1);}reader.close();
  absent(() -> provider.openDocument(id,"w",new CancellationSignal()));provider.deleteDocument(id);
  try(Cursor actual=provider.queryDocument(id,null)){need(actual.getCount()==0);}absent(() -> provider.openDocument(id,"r",new CancellationSignal()));
  row=source.observation(run,UUID.randomUUID().toString().replace("-",""),false);need((Boolean)row.get("complete"));need(((List<Map<String,Object>>)row.get("documents")).get(0).get("deleteCalls").equals(1));
  absent(() -> provider.deleteDocument(id));source.retire(run);need((Boolean)source.observation(run,UUID.randomUUID().toString().replace("-",""),true).get("workersTerminated"));
 }
}'''

SOURCE=r'''package org.overte.snapshot;
import java.io.*;import java.nio.file.*;import java.util.*;import java.util.concurrent.*;
import android.net.Uri;import android.content.*;import android.content.pm.*;import android.content.res.*;import android.database.Cursor;import android.os.*;import android.system.*;
public final class SnapshotDocumentsAccessHostTest {
 static final String RUN="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",ARM="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",REQUEST="cccccccccccccccccccccccccccccccc",DELETE="dddddddddddddddddddddddddddddddd";
 static void need(boolean value){if(!value)throw new AssertionError("Actual native SAF Access contract");}
 static long unix(Path path,String field)throws IOException{return ((Number)Files.getAttribute(path,"unix:"+field)).longValue();}
 static class Rows implements Cursor { final Object[] values;Rows(Object[] values){this.values=values;}public int getCount(){return values==null ? 0 : 1;}public boolean moveToFirst(){return values!=null;}
  public String getString(int index){return String.valueOf(values[index]);}public int getInt(int index){return ((Number)values[index]).intValue();}public long getLong(int index){return ((Number)values[index]).longValue();}public void close(){} }
 static class Device extends Context {
  final ProviderInfo provider=new ProviderInfo();final ApplicationInfo phone=new ApplicationInfo();final String mode;Device(int uid,String mode){this.mode=mode;provider.applicationInfo=new ApplicationInfo();provider.applicationInfo.uid=uid;phone.uid=uid+1;provider.packageName="org.overte.e2e.snapshotreceiver";
   if(mode.equals("wrong-package"))provider.packageName="org.foreign";if(mode.equals("same-uid"))provider.applicationInfo.uid=phone.uid;}
  public PackageManager getPackageManager(){return new PackageManager(){public ProviderInfo resolveContentProvider(String authority,int flags){return provider;}};}
  public ApplicationInfo getApplicationInfo(){return phone;}public String getPackageName(){return "io.github.noah_be.overte.phone";}
 }
 static class Resolver extends ContentResolver {
  final SnapshotDocumentsEvidence source;final Device device;final String id,mode;int calls;final List<String> delayed=new ArrayList<>();
  Resolver(SnapshotDocumentsEvidence source,Device device,String id,String mode){this.source=source;this.device=device;this.id=id;this.mode=mode;}
  public Cursor query(Uri uri,String[] fields,String a,String[] b,String c,CancellationSignal signal) {
   signal.throwIfCanceled();if(mode.equals("permission"))throw new SecurityException("Synthetic denied query");
   try { Map<String,Object> original=source.metadata(id);if(original==null)return new Rows(null);Object[] values=new Object[fields.length];
    for(int i=0;i<fields.length;i++) { String key;switch(fields[i]) {
     case "document_id":key="documentId";break;case "_display_name":key="displayName";break;case "mime_type":key="mimeType";break;case "_size":key="bytes";break;
     case "overte_run_id":key="runId";break;case "overte_arm_id":key="armId";break;case "overte_provider_instance":key="providerInstance";break;case "overte_create_uid":key="createUid";break;
     case "overte_created_epoch_ms":key="createdEpochMs";break;case "overte_writer_uid":key="writerUid";break;case "overte_write_opened_epoch_ms":key="writeOpenedEpochMs";break;case "overte_write_closed_epoch_ms":key="writeClosedEpochMs";break;
     case "overte_device":key="device";break;case "overte_inode":key="inode";break;case "overte_sha256":key="sha256";break;case "overte_delete_calls":key="deleteCalls";break;case "overte_open_descriptors":key="activeDescriptors";break;
     default:throw new AssertionError("Unspecified query column "+fields[i]); }
     values[i]=original.get(key);if(mode.equals("old-creation") && key.equals("createdEpochMs"))values[i]=1L;
    }return new Rows(values);
   }catch(IOException failure){throw new IllegalStateException(failure);}
  }
  public AssetFileDescriptor openAssetFileDescriptor(Uri uri,String mode,CancellationSignal signal)throws FileNotFoundException {
   try { String descriptor=source.reserve(id,"r",device.phone.uid);Path path=source.path(descriptor);FileInputStream input=new FileInputStream(path.toFile());Os.register(input.getFD(),path);StructStat stat=Os.fstat(input.getFD());source.opened(descriptor,stat.st_dev,stat.st_ino,stat.st_uid,stat.st_nlink,true);
    return new AssetFileDescriptor(){boolean closed;public long getStartOffset(){return 0;}public ParcelFileDescriptor getParcelFileDescriptor(){try{return new ParcelFileDescriptor(input.getFD());}catch(IOException failure){throw new IllegalStateException(failure);}}
     public InputStream createInputStream(){return input;}public void close()throws IOException{if(closed)return;closed=true;input.close();if(Resolver.this.mode.equals("delayed-callback")){synchronized(delayed){delayed.add(descriptor);}}else source.close(descriptor,false);} };
   }catch(IOException|ErrnoException failure){throw new FileNotFoundException("Original synthetic FD unavailable");}
  }
  public int delete(Uri uri,String selection,String[] args){throw new AssertionError("Generic resolver delete entered fixed Documents branch");}
  public boolean documentDelete(Uri uri)throws FileNotFoundException { ++calls;try { source.delete(id);if(mode.equals("lost-return"))throw new IOException("Actual deletion return lost");return true; }catch(IOException failure){throw new FileNotFoundException("Synthetic deletion return unavailable");} }
  void release()throws IOException{synchronized(delayed){for(String descriptor:delayed)source.close(descriptor,false);delayed.clear();}}
 }
 static void settled(SnapshotOsDestinations owner)throws Exception{for(int attempt=0;attempt<300;attempt++){if(((Number)owner.observation().get("pending")).intValue()==0)return;Thread.sleep(10);}throw new AssertionError("Native worker never settled");}
 @SuppressWarnings("unchecked") public static void main(String[] args)throws Exception {
  String mode=args[0];Path root=Paths.get(args[1]);SnapshotDocumentsEvidence source=new SnapshotDocumentsEvidence(root);source.arm(RUN,ARM);String name="e2e-"+RUN+"-native.png",id=source.create(source.rootId(),"image/png",name,1000);
  Path directory;try(java.util.stream.Stream<Path> paths=Files.list(root)){directory=paths.findFirst().get();}int uid=(int)unix(directory,"uid");Device device=new Device(uid,mode);Resolver resolver=new Resolver(source,device,id,mode);
  ExecutorService worker=Executors.newSingleThreadExecutor();ScheduledExecutorService clock=Executors.newSingleThreadScheduledExecutor();SnapshotOsDestinations owner=new SnapshotOsDestinations(worker,clock);
  try {
   Uri uri=Uri.parse("content://"+(mode.equals("foreign-authority") ? "org.foreign.documents" : SnapshotDocumentsEvidence.AUTHORITY)+"/document/"+id);
   owner.destination(REQUEST,device,resolver,uri,false,name);settled(owner);Map<String,Object> initial=owner.observation();need(((Number)initial.get("snapshotOsDestinationsVersion")).intValue()==(mode.equals("foreign-authority") ? 1 : 2));
   if(Arrays.asList("wrong-package","same-uid","old-creation","foreign-authority","permission").contains(mode)){need(!((Boolean)initial.get("complete")) && resolver.calls==0);return;}
   need((Boolean)initial.get("complete"));String writer=source.reserve(id,"w",mode.equals("wrong-writer") ? device.phone.uid+1 : device.phone.uid);Path file=source.path(writer);
   try(OutputStream output=Files.newOutputStream(file)){source.opened(writer,unix(file,"dev"),unix(file,"ino"),unix(file,"uid"),unix(file,"nlink"),true);output.write(new byte[]{1,2,3,4,5});}source.close(writer,false);
   owner.published(REQUEST);settled(owner);if(mode.equals("wrong-writer")){need(!((Boolean)owner.observation().get("complete")) && resolver.calls==0);return;}
   need((Boolean)owner.observation().get("complete"));Map<String,Object> row=((List<Map<String,Object>>)owner.observation().get("rows")).get(0),identity=(Map<String,Object>)row.get("identity");
   need(!((Boolean)row.get("inserted")) && identity.get("ownerPackage").equals("org.overte.e2e.snapshotreceiver") && identity.get("storage").equals("documents"));
   if(mode.equals("changed-bytes"))Files.write(file,new byte[]{9,9,9,9,9});
   Thread release=null;if(mode.equals("delayed-callback")){release=new Thread(() -> {try{Thread.sleep(200);resolver.release();}catch(Exception failure){throw new AssertionError(failure);}});release.start();}
   need(owner.remove(REQUEST,DELETE));settled(owner);if(release!=null)release.join();
   if(mode.equals("changed-bytes")){need(resolver.calls==0 && Files.exists(file) && !((Boolean)owner.observation().get("complete")));return;}
   if(mode.equals("lost-return")){need(!owner.retired());need(owner.inspect("eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"));settled(owner);}
   need(owner.retired() && resolver.calls==1 && !Files.exists(file));need(owner.remove(REQUEST,DELETE));settled(owner);need(resolver.calls==1);source.retire(RUN);
  }finally{worker.shutdownNow();clock.shutdownNow();need(worker.awaitTermination(2,TimeUnit.SECONDS) && clock.awaitTermination(2,TimeUnit.SECONDS));}
 }
}'''


class SnapshotDocumentsAccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parent=ROOT/'build/snapshot-documents-access-host';parent.mkdir(parents=True,exist_ok=True)
        cls.temp=tempfile.TemporaryDirectory(prefix='java-',dir=parent);cls.addClassCleanup(cls.temp.cleanup);cls.stage=Path(cls.temp.name)
        sources=[]
        for name,value in STUBS.items():
            path=cls.stage/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(value);sources.append(path)
        harness=cls.stage/'org/overte/snapshot/SnapshotDocumentsAccessHostTest.java';harness.parent.mkdir(parents=True,exist_ok=True);harness.write_text(SOURCE);sources.append(harness)
        sources.extend(ROOT/'android/common/snapshot/java/org/overte/snapshot'/name for name in ('SnapshotOsDestinations.java','SnapshotDestinationOwner.java'))
        sources.extend(ROOT/'tests/device/fixture/android-snapshot-receiver/java/org/overte/snapshot'/name for name in ('SnapshotDocumentsEvidence.java','SnapshotDocumentsProvider.java'))
        provider=cls.stage/'org/overte/snapshot/SnapshotDocumentsProviderHostTest.java';provider.write_text(PROVIDER_SOURCE);sources.append(provider)
        subprocess.run(['javac','--release','8','-d',str(cls.stage),*map(str,sources)],check=True,timeout=30)
    def execute(self,mode):
        with tempfile.TemporaryDirectory(prefix=mode+'-',dir=self.stage) as directory:
            result=subprocess.run(['java','-cp',str(self.stage),'org.overte.snapshot.SnapshotDocumentsAccessHostTest',mode,directory],text=True,capture_output=True,timeout=10)
            self.assertEqual(0,result.returncode,result.stdout+result.stderr)
    def test_actual_documents_provider_normal_callbacks_preserve_fresh_absence_after_expected_missing_open(self):
        with tempfile.TemporaryDirectory(prefix='provider-',dir=self.stage) as directory:
            result=subprocess.run(['java','-cp',str(self.stage),'org.overte.snapshot.SnapshotDocumentsProviderHostTest',directory],text=True,capture_output=True,timeout=10)
            self.assertEqual(0,result.returncode,result.stdout+result.stderr)
    def test_actual_native_document_access_qualifies_original_false_insert_callback_and_one_send_cleanup(self):self.execute('original')
    def test_closed_scope_identity_provider_and_writer_guards_prevent_delete(self):
        for mode in ('wrong-package','same-uid','old-creation','foreign-authority','permission','wrong-writer','changed-bytes'):
            with self.subTest(mode=mode):self.execute(mode)
    def test_real_delayed_close_and_uncertain_delete_return_require_independent_originals(self):
        for mode in ('delayed-callback','lost-return'):
            with self.subTest(mode=mode):self.execute(mode)


if __name__=='__main__':unittest.main()
