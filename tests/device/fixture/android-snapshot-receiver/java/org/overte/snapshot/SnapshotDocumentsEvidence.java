// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
package org.overte.snapshot;

import java.io.Closeable;
import java.io.IOException;
import java.io.InputStream;
import java.nio.file.DirectoryStream;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.nio.file.attribute.BasicFileAttributes;
import java.nio.file.attribute.PosixFilePermissions;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.TimeUnit;

/** Own actual fixture files and FD callbacks. Commands supply IDs only.
 * Android Binder/PFD glue supplies caller identities and real close callbacks;
 * no request can supply an original path, hash, writer or successful result.
 */
final class SnapshotDocumentsEvidence {
    static final long MAX_BYTES=32L*1024*1024;
    static final String AUTHORITY="org.overte.e2e.snapshotreceiver.documents";
    private final Path parent;private final Object parentKey;
    final String instance=nonce();private String run="",arm="";private Path directory;private Object directoryKey;
    private long device,inode,sequence,previousEpoch;private boolean complete=true,retired;
    private final Map<String,Document> documents=new LinkedHashMap<>();
    private final Map<String,Descriptor> descriptors=new LinkedHashMap<>();
    private final Set<String> observations=new HashSet<>(),binaries=new HashSet<>();
    private final List<Thread> transfers=new ArrayList<>();private final List<ScheduledExecutorService> clocks=new ArrayList<>();
    private static String nonce() { return UUID.randomUUID().toString().replace("-",""); }
    private static void nonce(String value) throws IOException { if(value==null || !value.matches("[0-9a-f]{32}"))throw new IOException("Closed document identity required"); }
    private static BasicFileAttributes attributes(Path path) throws IOException { return Files.readAttributes(path,BasicFileAttributes.class,LinkOption.NOFOLLOW_LINKS); }
    private static long unix(Path path,String key) throws IOException { return ((Number)Files.getAttribute(path,"unix:"+key,LinkOption.NOFOLLOW_LINKS)).longValue(); }
    private static long epoch() throws IOException { long value=System.currentTimeMillis();if(value<=0)throw new IOException("Document clock unavailable");return value; }
    static final class Document {
        final String id,name,mime;final Path path;final int creator;final long created;
        String phase="planned",sha="";Object key;long device,inode,bytes,writeOpened,writeClosed,deleted,checked;int writer,deleteCalls;boolean absent,writerReserved;
        Document(String id,String name,String mime,Path path,int creator,long created) { this.id=id;this.name=name;this.mime=mime;this.path=path;this.creator=creator;this.created=created; }
        Map<String,Object> plan() { Map<String,Object> row=new LinkedHashMap<>();row.put("documentId",id);row.put("createUid",creator);row.put("createdEpochMs",created);row.put("displayName",name);row.put("mimeType",mime);row.put("phase",phase);return row; }
        Map<String,Object> view() { Map<String,Object> row=new LinkedHashMap<>(plan());row.remove("phase");row.put("uri","content://"+AUTHORITY+"/document/"+id);
            row.put("device",device);row.put("inode",inode);row.put("bytes",bytes);row.put("sha256",sha);row.put("writerUid",writer);
            row.put("writeOpenedEpochMs",writeOpened);row.put("writeClosedEpochMs",writeClosed);row.put("deleteCalls",deleteCalls);row.put("deletedEpochMs",deleted);row.put("absent",absent);row.put("checkedEpochMs",checked);return row; }
    }
    static final class Descriptor {
        final String id=nonce(),document,mode;final int caller;long opened,closedAt;boolean closed,error;
        Descriptor(String document,String mode,int caller) { this.document=document;this.mode=mode;this.caller=caller; }
        Map<String,Object> view() { Map<String,Object> row=new LinkedHashMap<>();row.put("id",id);row.put("documentId",document);row.put("mode",mode);row.put("callerUid",caller);
            row.put("openedEpochMs",opened);row.put("closedEpochMs",closedAt);row.put("closed",closed);row.put("error",error);return row; }
    }
    SnapshotDocumentsEvidence(Path files) throws IOException {
        parent=files.toRealPath();BasicFileAttributes actual=attributes(parent);parentKey=actual.fileKey();
        if(!actual.isDirectory() || actual.isSymbolicLink() || parentKey==null)throw new IOException("Private fixture parent unavailable");
        try(DirectoryStream<Path> old=Files.newDirectoryStream(parent,"overte-snapshot-documents-*")) { if(old.iterator().hasNext())throw new IOException("Unretired document root exists"); }
    }
    synchronized void arm(String run,String arm) throws IOException {
        nonce(run);nonce(arm);if(!this.run.isEmpty())throw new IOException("Documents already armed");
        parent();Path next=parent.resolve("overte-snapshot-documents-"+run);
        Files.createDirectory(next,PosixFilePermissions.asFileAttribute(PosixFilePermissions.fromString("rwx------")));
        directory=next;directoryKey=attributes(next).fileKey();device=unix(next,"dev");inode=unix(next,"ino");this.run=run;this.arm=arm;root();
    }
    synchronized void checkRun(String value) throws IOException { if(run.isEmpty() || !run.equals(value))throw new IOException("Foreign document run"); }
    synchronized String rootId() throws IOException { checkRun(run);return "root-"+run; }
    private void parent() throws IOException { BasicFileAttributes actual=attributes(parent);if(!actual.isDirectory() || actual.isSymbolicLink() || !parentKey.equals(actual.fileKey()))throw new IOException("Fixture parent changed"); }
    private void root() throws IOException {
        parent();if(directory==null || retired)throw new IOException("Documents root unavailable");BasicFileAttributes actual=attributes(directory);
        if(!actual.isDirectory() || actual.isSymbolicLink() || directoryKey==null || !directoryKey.equals(actual.fileKey()) || device!=unix(directory,"dev") || inode!=unix(directory,"ino")
            || !Files.getPosixFilePermissions(directory,LinkOption.NOFOLLOW_LINKS).equals(PosixFilePermissions.fromString("rwx------")))throw new IOException("Documents root changed");
    }
    private Document owned(String id) throws IOException { Document value=documents.get(id);if(value==null)throw new IOException("Foreign document ID");return value; }
    private void bound(Document value) throws IOException {
        root();BasicFileAttributes actual=attributes(value.path);
        if(!actual.isRegularFile() || actual.isSymbolicLink() || value.key==null || !value.key.equals(actual.fileKey()) || value.device!=unix(value.path,"dev") || value.inode!=unix(value.path,"ino")
            || unix(value.path,"nlink")!=1 || !Files.getPosixFilePermissions(value.path,LinkOption.NOFOLLOW_LINKS).equals(PosixFilePermissions.fromString("rw-------")))throw new IOException("Original document changed");
    }
    synchronized String create(String parentId,String mime,String name,int callerUid) throws IOException {
        root();if(!rootId().equals(parentId) || !"image/png".equals(mime) || name==null || !name.matches("e2e-"+run+"-[A-Za-z0-9_-]{1,160}\\.png") || callerUid<=0 || documents.size()>=64)throw new IOException("Controlled PNG creation required");
        String id="doc-"+run+"-"+arm+"-"+nonce();Document value=new Document(id,name,mime,directory.resolve(id+".png"),callerUid,epoch());documents.put(id,value);
        try { Files.createFile(value.path,PosixFilePermissions.asFileAttribute(PosixFilePermissions.fromString("rw-------")));value.key=attributes(value.path).fileKey();value.device=unix(value.path,"dev");value.inode=unix(value.path,"ino");bound(value);value.phase="created";return id; }
        catch(IOException | RuntimeException failure) { value.phase="failed";complete=false;throw failure; }
    }
    synchronized List<Map<String,Object>> children(String parentId) throws IOException {
        root();if(!rootId().equals(parentId))throw new IOException("Foreign parent document");List<Map<String,Object>> rows=new ArrayList<>();
        for(Document value:documents.values())if(!value.absent)rows.add(metadata(value.id));return rows;
    }
    synchronized Map<String,Object> metadata(String id) throws IOException {
        Document value=owned(id);if(value.absent) { absence(value);return null; }bound(value);
        Map<String,Object> row=value.view();row.put("runId",run);row.put("armId",arm);row.put("providerInstance",instance);int active=0;for(Descriptor fd:descriptors.values())if(fd.document.equals(id) && !fd.closed)++active;row.put("activeDescriptors",active);return row;
    }
    synchronized Path path(String descriptor) throws IOException { Descriptor actual=descriptors.get(descriptor);if(actual==null)throw new IOException("Unknown descriptor");Document value=owned(actual.document);bound(value);return value.path; }
    synchronized String reserve(String id,String mode,int callerUid) throws IOException {
        Document value=owned(id);bound(value);if(callerUid<=0 || descriptors.size()>=4096 || !(mode.equals("r") || mode.equals("w")) || value.deleteCalls!=0)throw new IOException("Document descriptor authority unavailable");
        if(mode.equals("w") && value.writerReserved)throw new IOException("Document writer already consumed");
        Descriptor descriptor=new Descriptor(id,mode,callerUid);descriptors.put(descriptor.id,descriptor);
        if(mode.equals("w"))value.writerReserved=true;return descriptor.id;
    }
    synchronized void opened(String id,long device,long inode,long uid,long links,boolean regular) throws IOException {
        Descriptor value=descriptors.get(id);if(value==null || value.opened!=0 || value.closed)throw new IOException("Descriptor open already recorded");
        Document document=owned(value.document);bound(document);
        if(device!=document.device || inode!=document.inode || uid!=unix(document.path,"uid") || links!=1 || !regular)throw new IOException("Actual descriptor identity changed");
        value.opened=epoch();if(value.mode.equals("w")) { document.writer=value.caller;document.writeOpened=value.opened; }
    }
    synchronized void close(String id,boolean failed) throws IOException {
        Descriptor value=descriptors.get(id);if(value==null || value.closed)throw new IOException("Foreign or repeated close callback");
        value.error=failed;value.closed=true;value.closedAt=epoch();
        if(value.opened==0 || failed) { value.error=true;complete=false;return; }
        Document document=owned(value.document);
        try {
            bound(document);
            if(value.mode.equals("w")) {
                Map<String,Object> content=content(document,false);document.bytes=((Number)content.get("bytes")).longValue();document.sha=(String)content.get("sha256");document.writeClosed=value.closedAt;
            }
        } catch(IOException | RuntimeException failure) { value.error=true;complete=false;throw failure; }
    }
    synchronized void rejected() { complete=false; }
    private static MessageDigest digest() { try { return MessageDigest.getInstance("SHA-256"); }catch(NoSuchAlgorithmException impossible) { throw new IllegalStateException(impossible); } }
    private static String hex(byte[] raw) { StringBuilder value=new StringBuilder();for(byte item:raw)value.append(String.format(java.util.Locale.ROOT,"%02x",item&255));return value.toString(); }
    private Map<String,Object> content(Document value,boolean binary) throws IOException {
        bound(value);long start=System.nanoTime(),total=0;MessageDigest hash=digest();java.io.ByteArrayOutputStream bytes=binary ? new java.io.ByteArrayOutputStream() : null;
        try(InputStream input=Files.newInputStream(value.path,StandardOpenOption.READ,LinkOption.NOFOLLOW_LINKS)) {
            byte[] buffer=new byte[65536];int count;while((count=input.read(buffer))!=-1) {
                if(count==0 || (total+=count)>MAX_BYTES || System.nanoTime()-start>=15000000000L)throw new IOException("Original document byte bound exceeded");hash.update(buffer,0,count);if(bytes!=null)bytes.write(buffer,0,count);
            }
        }
        bound(value);if(total==0 || total!=attributes(value.path).size())throw new IOException("Empty or changing original document");
        Map<String,Object> result=new LinkedHashMap<>();result.put("bytes",total);result.put("sha256",hex(hash.digest()));if(bytes!=null)result.put("binary",bytes.toByteArray());return result;
    }
    private void unchanged(Document value) throws IOException {
        if(value.writer<=0 || value.writeOpened<=0 || value.writeClosed<value.writeOpened || value.bytes<=0 || !value.sha.matches("[0-9a-f]{64}"))throw new IOException("Original writer has not closed");
        Map<String,Object> actual=content(value,false);if(!actual.get("bytes").equals(value.bytes) || !actual.get("sha256").equals(value.sha))throw new IOException("Original document bytes changed");
    }
    private boolean pending(String id) { for(Descriptor fd:descriptors.values())if(fd.document.equals(id) && !fd.closed)return true;return false; }
    synchronized void delete(String id) throws IOException {
        Document value=owned(id);if(value.deleteCalls!=0 || pending(id))throw new IOException("One-send delete unavailable or descriptors active");
        unchanged(value);value.deleteCalls=1;Files.delete(value.path);value.deleted=epoch();absence(value);
    }
    private void absence(Document value) throws IOException {
        parent();if(retired) { if(!Files.notExists(directory,LinkOption.NOFOLLOW_LINKS))throw new IOException("Retired root returned"); }
        else root();
        if(value.deleteCalls!=1 || !Files.notExists(value.path,LinkOption.NOFOLLOW_LINKS))throw new IOException("Original document absence unproved");
        value.checked=epoch();value.absent=true;
    }
    synchronized byte[] original(String run,String id,String observation) throws IOException {
        checkRun(run);nonce(observation);if(retired || binaries.size()>=4096 || !binaries.add(observation))throw new IOException("Original document binary replay");
        Document value=owned(id);if(value.absent || pending(id))throw new IOException("Original document still active");unchanged(value);
        Map<String,Object> original=content(value,true);if(!original.get("bytes").equals(value.bytes) || !original.get("sha256").equals(value.sha))throw new IOException("Original binary changed");return (byte[])original.get("binary");
    }
    synchronized void retire(String run) throws IOException {
        checkRun(run);if(!transfersTerminated())throw new IOException("Document source transfer remains active");
        for(Descriptor fd:descriptors.values())if(!fd.closed)throw new IOException("Document descriptor remains active");
        for(Document value:documents.values())absence(value);
        if(retired)return;root();try(DirectoryStream<Path> rows=Files.newDirectoryStream(directory)) { if(rows.iterator().hasNext())throw new IOException("Unknown document files remain"); }
        Files.delete(directory);retired=true;if(!Files.notExists(directory,LinkOption.NOFOLLOW_LINKS))throw new IOException("Original root absence unproved");
    }
    synchronized boolean retired() { return retired; }
    synchronized Map<String,Object> observation(String run,String observation,boolean callbacksTerminated) throws IOException {
        checkRun(run);nonce(observation);if(observations.size()>=4096 || !observations.add(observation))throw new IOException("Document source replay");long now=epoch();
        if(now<previousEpoch)complete=false;previousEpoch=now;
        parent();if(retired) { if(!Files.notExists(directory,LinkOption.NOFOLLOW_LINKS))throw new IOException("Retired root returned"); }else root();
        List<Map<String,Object>> plans=new ArrayList<>(),docs=new ArrayList<>(),fds=new ArrayList<>();
        for(Document value:documents.values()) { plans.add(value.plan());if(value.key!=null) { if(value.absent)absence(value);else { bound(value);if(value.writeClosed>0)unchanged(value); }docs.add(value.view()); } }
        boolean opened=true;for(Descriptor fd:descriptors.values()) { fds.add(fd.view());if(fd.opened==0)opened=false; }
        now=epoch();previousEpoch=now;
        Map<String,Object> originalRoot=new LinkedHashMap<>();originalRoot.put("rootId",rootId());originalRoot.put("path",directory.toString());originalRoot.put("device",device);originalRoot.put("inode",inode);originalRoot.put("present",!retired);originalRoot.put("checkedEpochMs",now);
        Map<String,Object> result=new LinkedHashMap<>();result.put("snapshotDocumentsVersion",1);result.put("runId",run);result.put("armId",arm);result.put("observationId",observation);result.put("instance",instance);result.put("sequence",++sequence);result.put("capturedEpochMs",now);
        result.put("complete",complete && opened);result.put("root",originalRoot);result.put("plans",plans);result.put("documents",docs);result.put("fdLifetimes",fds);result.put("retired",retired);result.put("workersTerminated",retired && callbacksTerminated && transfersTerminated());return result;
    }
    synchronized void transfer(Runnable write,Closeable close) throws IOException {
        if(transfers.size()>=4096)throw new IOException("Document source transfer inventory full");
        ScheduledExecutorService clock=Executors.newSingleThreadScheduledExecutor(task -> { Thread thread=new Thread(task,"SnapshotDocumentsDeadline");thread.setDaemon(true);return thread; });clocks.add(clock);
        Thread thread=new Thread(() -> { ScheduledFuture<?> timeout=clock.schedule(() -> { try { close.close(); }catch(IOException ignored) { /* Real transfer reports failure. */ } },15,TimeUnit.SECONDS);
            try { write.run(); }finally { timeout.cancel(false);clock.shutdown(); } },"SnapshotDocumentsSource");thread.setDaemon(true);transfers.add(thread);thread.start();
    }
    private boolean transfersTerminated() { for(Thread thread:transfers)if(thread.isAlive())return false;for(ScheduledExecutorService clock:clocks)if(!clock.isTerminated())return false;return true; }
}
