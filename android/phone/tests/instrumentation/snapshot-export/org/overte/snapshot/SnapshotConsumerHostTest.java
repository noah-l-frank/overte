// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
package org.overte.snapshot;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;

/** Actual receiver ownership implementation with explicit synthetic URI/grants. */
public final class SnapshotConsumerHostTest {
    static final String RUN="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",ARM="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
    static void need(boolean value) { if(!value)throw new AssertionError("Actual receiver source contract"); }
    interface Checked { void run() throws Exception; }
    static void rejects(Checked operation)throws Exception { boolean refused=false;try { operation.run(); }catch(IOException expected) { refused=true; }need(refused); }
    static String nonce() { return UUID.randomUUID().toString().replace("-",""); }
    static final class Original implements SnapshotConsumerEvidence.Access {
        final SnapshotConsumerEvidence owner;byte[] bytes={1,2,3,4,5};boolean grant=true,closed=true,failClose,holdClose;
        int opens,closes;final CountDownLatch entered=new CountDownLatch(1),release=new CountDownLatch(1);
        Original(SnapshotConsumerEvidence owner) { this.owner=owner; }
        public Map<String,Object> identity() {
            Map<String,Object> value=new LinkedHashMap<>();value.put("uri","content://io.github.noah_be.overte.phone.snapshot.files/snapshots/original.png");
            value.put("providerPackage","io.github.noah_be.overte.phone");value.put("providerUid",10001);value.put("receiverPackage","org.overte.e2e.snapshotreceiver");
            value.put("receiverUid",10002);value.put("receiverPid",1234);value.put("component","org.overte.e2e.snapshotreceiver/org.overte.snapshot.SnapshotConsumer");
            value.put("readFlag",true);value.put("clipUri",value.get("uri"));value.put("permissionAtOpen",grant);return value;
        }
        public boolean granted() { return grant; }
        public boolean closed() { return closed; }
        public InputStream open() {
            ++opens;closed=false;
            return new ByteArrayInputStream(Arrays.copyOf(bytes,bytes.length)) {
                @Override public void close()throws IOException {
                    ++closes;
                    if(holdClose) { entered.countDown();try { if(!release.await(4,TimeUnit.SECONDS))throw new IOException("Held original close"); }catch(InterruptedException failure) { throw new IOException(failure); } }
                    if(failClose)throw new IOException("Original close failure");closed=true;super.close();
                }
            };
        }
        public void cancel() { release.countDown(); }
        public void finished() { owner.activity(false); }
    }
    static Map<String,Object> source(SnapshotConsumerEvidence owner)throws IOException { return owner.observation(RUN,nonce()); }
    @SuppressWarnings("unchecked") static List<Map<String,Object>> files(SnapshotConsumerEvidence owner)throws IOException { return (List<Map<String,Object>>)source(owner).get("files"); }
    static Map<String,Object> terminal(SnapshotConsumerEvidence owner)throws Exception {
        long start=System.nanoTime();while(System.nanoTime()-start<5000000000L) {
            Map<String,Object> row=source(owner);if(row.get("phase").equals("complete") || row.get("phase").equals("failed"))return row;Thread.sleep(2);
        }throw new AssertionError("Receiver source never terminal");
    }
    static void retire(SnapshotConsumerEvidence owner,Original access)throws Exception {
        access.grant=false;for(Map<String,Object> file:files(owner))owner.remove((String)file.get("id"));
        owner.retire();owner.retire();need(Boolean.TRUE.equals(source(owner).get("workersTerminated")));
    }
    @SuppressWarnings("unchecked") public static void main(String[] args)throws Exception {
        Path root=Paths.get(args[1]);String mode=args[0];
        if(mode.equals("orphan")) { Files.createDirectory(root.resolve("overte-snapshot-e2e-"+nonce()));rejects(() -> new SnapshotConsumerEvidence(root));return; }
        SnapshotConsumerEvidence owner=new SnapshotConsumerEvidence(root);owner.arm(RUN,ARM);Original access=new Original(owner);
        if(mode.equals("unconsumed")) { need(source(owner).get("original")==null);retire(owner,access);return; }
        rejects(() -> owner.arm(RUN,nonce()));rejects(() -> owner.checkRun(nonce()));
        if(mode.equals("missing-grant"))access.grant=false;
        if(mode.equals("failed-close"))access.failClose=true;
        if(mode.equals("pending-close"))access.holdClose=true;
        owner.activity(true);owner.receive(access);
        if(mode.equals("pending-close")) {
            need(access.entered.await(3,TimeUnit.SECONDS));Map<String,Object> current=source(owner);
            need(current.get("phase").equals("reading") && Boolean.FALSE.equals(current.get("originalClosed")));rejects(owner::retire);access.release.countDown();
        }
        Map<String,Object> value=terminal(owner);
        if(mode.equals("failed-close")) { need(value.get("phase").equals("failed") && value.get("original")==null);rejects(owner::retire);return; }
        if(mode.equals("missing-grant")) { need(value.get("phase").equals("failed") && access.opens==0);retire(owner,access);return; }
        need(value.get("phase").equals("complete") && access.opens==1 && access.closes==1 && Boolean.TRUE.equals(value.get("originalClosed")));
        Map<String,Object> original=(Map<String,Object>)value.get("original");String id=(String)original.get("id");Path path=Paths.get((String)original.get("path"));
        byte[] binary=owner.binary(RUN,id,nonce());need(Arrays.equals(binary,access.bytes));
        final String replay=nonce();owner.observation(RUN,replay);rejects(() -> owner.observation(RUN,replay));
        final String used=nonce();owner.binary(RUN,id,used);rejects(() -> owner.binary(RUN,id,used));
        if(mode.equals("changed-bytes")) { Files.write(path,new byte[]{5,4,3,2,1});rejects(() -> owner.binary(RUN,id,nonce()));rejects(() -> owner.remove(id));return; }
        if(mode.equals("changed-inode")) { Files.delete(path);Files.write(path,access.bytes);rejects(() -> owner.binary(RUN,id,nonce()));rejects(() -> owner.remove(id));return; }
        if(mode.equals("pending-transfer")) {
            CountDownLatch entered=new CountDownLatch(1),release=new CountDownLatch(1);
            owner.transfer(() -> { entered.countDown();try { release.await(4,TimeUnit.SECONDS); }catch(InterruptedException ignored) {} },() -> release.countDown());
            need(entered.await(3,TimeUnit.SECONDS));access.grant=false;owner.remove(id);rejects(owner::retire);release.countDown();
            long start=System.nanoTime();while(System.nanoTime()-start<3000000000L) { try { owner.retire();return; }catch(IOException wait) { Thread.sleep(2); } }throw new AssertionError("Transfer never terminated");
        }
        if(mode.equals("late-grant")) { retire(owner,access);access.grant=true;need(Boolean.TRUE.equals(source(owner).get("grantPresent")));rejects(owner::retire);return; }
        if(mode.equals("late-file")) { Path folder=path.getParent();retire(owner,access);Files.createDirectory(folder);Files.write(path,access.bytes);rejects(() -> source(owner));rejects(owner::retire);return; }
        rejects(owner::retire);retire(owner,access);
    }
}
