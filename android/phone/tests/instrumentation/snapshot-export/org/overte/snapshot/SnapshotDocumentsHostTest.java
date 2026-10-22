// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
package org.overte.snapshot;

import java.io.*;
import java.nio.file.*;
import java.nio.file.attribute.PosixFilePermissions;
import java.util.*;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

/** Actual filesystem/streams and descriptor lifetime owner. Android Binder/PFD
 * calls are explicit synthetic callback seams; no Android provider executes.
 */
public final class SnapshotDocumentsHostTest {
    static final String RUN="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",ARM="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
    static final byte[] PNG={-119,80,78,71,13,10,26,10,1,2,3,4,5};
    interface Work { void run() throws Exception; }
    static void need(boolean value) { if(!value)throw new AssertionError("Original controlled documents contract"); }
    static void fails(Work work) throws Exception { try { work.run();throw new AssertionError("Foreign or incomplete document accepted"); }catch(IOException expected){} }
    static String nonce() { return UUID.randomUUID().toString().replace("-",""); }
    static long stat(Path path,String key) throws IOException { return ((Number)Files.getAttribute(path,"unix:"+key,LinkOption.NOFOLLOW_LINKS)).longValue(); }
    @SuppressWarnings("unchecked") static List<Map<String,Object>> rows(Map<String,Object> value,String key) { return (List<Map<String,Object>>)value.get(key); }
    static String json(Object value) {
        if(value==null)return "null";if(value instanceof String)return "\""+((String)value).replace("\\","\\\\").replace("\"","\\\"")+"\"";
        if(value instanceof Number || value instanceof Boolean)return value.toString();
        StringJoiner result=new StringJoiner(",",value instanceof Map ? "{" : "[",value instanceof Map ? "}" : "]");
        if(value instanceof Map)for(Map.Entry<?,?> row:((Map<?,?>)value).entrySet())result.add(json(row.getKey())+":"+json(row.getValue()));else for(Object row:(List<?>)value)result.add(json(row));return result.toString();
    }
    static void opened(SnapshotDocumentsEvidence source,String fd,Path file) throws IOException { source.opened(fd,stat(file,"dev"),stat(file,"ino"),stat(file,"uid"),stat(file,"nlink"),Files.isRegularFile(file,LinkOption.NOFOLLOW_LINKS)); }
    static Map<String,Object> observed(SnapshotDocumentsEvidence source) throws IOException { Map<String,Object> row=source.observation(RUN,nonce(),source.retired());row.put("processId",123);row.put("providerUid",1002);row.put("providerPackage","org.overte.e2e.snapshotreceiver");return row; }
    public static void main(String[] args) throws Exception {
        String mode=args[0];Path root=Paths.get(args[1]);
        if(mode.equals("stale-root")) { Files.createDirectory(root.resolve("overte-snapshot-documents-"+RUN));fails(() -> new SnapshotDocumentsEvidence(root));return; }
        SnapshotDocumentsEvidence source=new SnapshotDocumentsEvidence(root);source.arm(RUN,ARM);
        if(mode.equals("rearm")) { fails(() -> source.arm(RUN,nonce()));fails(() -> source.arm(nonce(),ARM));return; }
        if(mode.equals("cancel-empty")) { need(rows(observed(source),"documents").isEmpty());source.retire(RUN);need((Boolean)observed(source).get("workersTerminated"));source.retire(RUN);return; }
        if(mode.equals("closed-inputs")) {
            for(String name:new String[]{"../file.png","unowned.png","e2e-"+RUN+"-evil/path.png","e2e-"+RUN+"-wrong.jpg"})fails(() -> source.create(source.rootId(),"image/png",name,1000));
            fails(() -> source.create(source.rootId(),"image/jpeg","e2e-"+RUN+"-original.png",1000));fails(() -> source.create("root-"+ARM,"image/png","e2e-"+RUN+"-original.png",1000));
            need(rows(observed(source),"plans").isEmpty());return;
        }
        String id=source.create(source.rootId(),"image/png","e2e-"+RUN+"-original.png",1000);need(id.matches("doc-"+RUN+"-"+ARM+"-[0-9a-f]{32}"));
        Map<String,Object> before=observed(source),beforeDoc=rows(before,"documents").get(0);need(beforeDoc.get("bytes").equals(0L) && beforeDoc.get("sha256").equals("") && beforeDoc.get("writerUid").equals(0));
        if(mode.equals("prewrite")) { fails(() -> source.original(RUN,id,nonce()));fails(() -> source.delete(id));fails(() -> source.retire(RUN));return; }
        String writer=source.reserve(id,"w",1001);Path file=source.path(writer);
        if(mode.equals("wrong-fd")) { fails(() -> source.opened(writer,stat(file,"dev"),stat(file,"ino")+1,stat(file,"uid"),1,true));fails(() -> source.retire(RUN));return; }
        try(OutputStream output=Files.newOutputStream(file,StandardOpenOption.WRITE)) { opened(source,writer,file);output.write(mode.equals("oversize") ? new byte[33*1024*1024] : PNG); }
        if(mode.equals("oversize")) { fails(() -> source.close(writer,false));need(!(Boolean)observed(source).get("complete"));fails(() -> source.retire(RUN));return; }
        if(mode.equals("pending-writer")) { fails(() -> source.original(RUN,id,nonce()));fails(() -> source.delete(id));fails(() -> source.retire(RUN));need(!(Boolean)observed(source).get("retired"));return; }
        if(mode.equals("failed-close")) { source.close(writer,true);need(!(Boolean)observed(source).get("complete"));fails(() -> source.delete(id));return; }
        source.close(writer,false);Map<String,Object> doc=rows(observed(source),"documents").get(0);
        need(doc.get("writerUid").equals(1001) && doc.get("bytes").equals((long)PNG.length) && ((String)doc.get("sha256")).matches("[0-9a-f]{64}"));
        need(((Number)doc.get("writeClosedEpochMs")).longValue()>=((Number)doc.get("writeOpenedEpochMs")).longValue());
        fails(() -> source.reserve(id,"w",1001));fails(() -> source.reserve(id,"rw",1001));fails(() -> source.metadata("doc-"+ARM+"-"+RUN+"-"+nonce()));
        String binary=nonce();need(Arrays.equals(PNG,source.original(RUN,id,binary)));fails(() -> source.original(RUN,id,binary));
        String observation=nonce();source.observation(RUN,observation,false);fails(() -> source.observation(RUN,observation,false));
        if(mode.equals("changed-bytes")) { Files.write(file,new byte[]{9,9,9});fails(() -> source.original(RUN,id,nonce()));fails(() -> observed(source));fails(() -> source.delete(id));need(Files.exists(file));return; }
        if(mode.equals("changed-inode")) { Files.move(file,root.resolve("retained"));Files.write(file,PNG);Files.setPosixFilePermissions(file,PosixFilePermissions.fromString("rw-------"));fails(() -> observed(source));fails(() -> source.delete(id));need(Files.exists(file));return; }
        if(mode.equals("hard-link")) { Files.createLink(root.resolve("retained"),file);fails(() -> source.original(RUN,id,nonce()));fails(() -> source.delete(id));return; }
        if(mode.equals("symlink")) { Files.move(file,root.resolve("retained"));Files.createSymbolicLink(file,root.resolve("retained"));fails(() -> source.metadata(id));fails(() -> source.delete(id));return; }
        if(mode.equals("changed-mode")) { Files.setPosixFilePermissions(file,PosixFilePermissions.fromString("rw-r--r--"));fails(() -> observed(source));fails(() -> source.delete(id));return; }
        if(mode.equals("early-absence")) { Files.delete(file);fails(() -> source.metadata(id));fails(() -> source.retire(RUN));return; }
        if(mode.equals("pending-reader")) { String reader=source.reserve(id,"r",1001);try(InputStream input=Files.newInputStream(source.path(reader))) { opened(source,reader,file);need(input.read()==(PNG[0]&255));fails(() -> source.delete(id));fails(() -> source.retire(RUN)); }source.close(reader,false); }
        if(mode.equals("source-thread")) {
            CountDownLatch entered=new CountDownLatch(1),release=new CountDownLatch(1);source.transfer(() -> { entered.countDown();try { release.await(2,TimeUnit.SECONDS); }catch(InterruptedException failure) { Thread.currentThread().interrupt(); } },() -> {});
            need(entered.await(1,TimeUnit.SECONDS));source.delete(id);fails(() -> source.retire(RUN));release.countDown();Thread.sleep(100);source.retire(RUN);need((Boolean)observed(source).get("workersTerminated"));return;
        }
        source.delete(id);need(!Files.exists(file));need(source.metadata(id)==null);fails(() -> source.delete(id));
        Map<String,Object> deleted=rows(observed(source),"documents").get(0);need(deleted.get("deleteCalls").equals(1) && (Boolean)deleted.get("absent"));
        if(mode.equals("resurrected-document")) { Files.write(file,PNG);fails(() -> source.metadata(id));fails(() -> source.retire(RUN));return; }
        Path directory=file.getParent();if(mode.equals("foreign-child")) { Path foreign=directory.resolve("foreign");Files.write(foreign,PNG);fails(() -> source.retire(RUN));need(Files.exists(foreign));return; }
        source.retire(RUN);need(!Files.exists(directory));Map<String,Object> retired=observed(source);need((Boolean)retired.get("retired") && (Boolean)retired.get("workersTerminated"));source.retire(RUN);
        if(mode.equals("resurrected-root")) { Files.createDirectory(directory);fails(() -> observed(source));return; }
        need(rows(retired,"fdLifetimes").size()==(mode.equals("pending-reader") ? 2 : 1));System.out.println(json(retired));
    }
}
