// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
package org.overte.snapshot;
import java.io.IOException;
import java.io.InputStream;
import java.io.FilterInputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;

/** Real host file identity/bytes/deletion. Android resolver operations are fixtures. */
public final class SnapshotDestinationOwnerHostTest {
    static final String REQUEST="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",DELETE="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
    static void check(boolean value) { if(!value)throw new AssertionError("Original destination ownership contract"); }
    static void fails(Work work) throws Exception { try { work.run();throw new AssertionError("Foreign or unproved original accepted"); }catch(IOException expected){} }
    interface Work { void run() throws Exception; }
    static final class Access implements SnapshotDestinationOwner.Access {
        final Path path;int deletions,creationQueries;boolean ignore,lost,deny,closeFails,blocking,originBlocking,originDenied,originFails;
        CountDownLatch entered=new CountDownLatch(1),release=new CountDownLatch(1);
        Access(Path path) { this.path=path; }
        public Map<String,Object> identity() throws IOException {
            BasicFileAttributes actual=Files.readAttributes(path,BasicFileAttributes.class);Map<String,Object> value=new LinkedHashMap<>();
            value.put("uri","content://media/external/images/media/1");value.put("fileKey",actual.fileKey().toString());return value;
        }
        public InputStream open() throws IOException {
            return new FilterInputStream(Files.newInputStream(path)) {
                @Override public int read(byte[] data,int offset,int count) throws IOException {
                    if(blocking) { entered.countDown();try { if(!release.await(5,TimeUnit.SECONDS))throw new IOException("Fixture remained blocked"); }catch(InterruptedException failure) { throw new IOException(failure); } }
                    return super.read(data,offset,count);
                }
                @Override public void close() throws IOException { super.close();if(closeFails)throw new IOException("Actual close failed"); }
            };
        }
        public int delete() throws IOException { ++deletions;if(!ignore)Files.delete(path);if(lost)throw new IOException("Return was lost after actual deletion");return 1; }
        public boolean absent() throws IOException { if(deny)throw new IOException("Provider permission unavailable");return !Files.exists(path); }
        @Override public boolean createdHere() throws IOException {
            ++creationQueries;if(!originBlocking)return false;
            entered.countDown();try { if(!release.await(5,TimeUnit.SECONDS))throw new IOException("Original provider query remained blocked"); }
            catch(InterruptedException failure) { Thread.currentThread().interrupt();throw new IOException(failure); }
            if(originFails)throw new IOException("Original provider creation query failed");return !originDenied;
        }
    }
    public static void main(String[] args) throws Exception {
        String mode=args[0];Path root=Paths.get(args[1]),path=root.resolve("actual-target.bin");Files.write(path,new byte[]{1,2,3,4,5});
        Access access=new Access(path);SnapshotDestinationOwner owner=new SnapshotDestinationOwner();
        if(mode.startsWith("pending-origin")) {
            owner.register(REQUEST,access,false);owner.created(REQUEST);owner.published(REQUEST);
            access.originBlocking=true;access.originDenied=mode.equals("pending-origin-denied");access.originFails=mode.equals("pending-origin-failed");
            ExecutorService threads=Executors.newFixedThreadPool(2);
            Future<?> removal=threads.submit(() -> { try {
                if(access.originDenied || access.originFails)fails(() -> owner.remove(REQUEST,DELETE));else owner.remove(REQUEST,DELETE);
            }catch(Exception failure) { throw new AssertionError(failure); } });
            try {
                check(access.entered.await(2,TimeUnit.SECONDS));
                Future<?> observation=threads.submit(() -> {
                    check(owner.snapshot().get(0).get("phase").equals("checking-delete"));check(!owner.retired());
                    try { fails(() -> owner.remove(REQUEST,DELETE)); }catch(Exception failure) { throw new AssertionError(failure); }
                });
                // A stalled provider is not allowed to own the passive history
                // monitor. This uses actual threads and the actual Java owner.
                observation.get(500,TimeUnit.MILLISECONDS);check(access.deletions==0 && access.creationQueries==1);
            } finally {
                access.release.countDown();removal.get(2,TimeUnit.SECONDS);threads.shutdown();check(threads.awaitTermination(2,TimeUnit.SECONDS));
            }
            if(access.originDenied || access.originFails)check(!owner.retired() && Files.exists(path) && access.deletions==0);
            else check(owner.retired() && !Files.exists(path) && access.deletions==1);
            return;
        }
        owner.register(REQUEST,access,!"foreign".equals(mode));owner.created(REQUEST);
        if("pending-close".equals(mode)) {
            access.blocking=true;Thread worker=new Thread(() -> { try { owner.published(REQUEST); }catch(IOException failure) { throw new AssertionError(failure); } });worker.start();
            check(access.entered.await(2,TimeUnit.SECONDS));long start=System.nanoTime();check(owner.snapshot().get(0).get("phase").equals("created"));check(System.nanoTime()-start<500000000L);
            check(!owner.retired());access.release.countDown();worker.join(2000);check(!worker.isAlive());
        } else if("close-failure".equals(mode)) { access.closeFails=true;fails(() -> owner.published(REQUEST));check(!owner.retired());return; }
        else owner.published(REQUEST);
        if("foreign".equals(mode)) { fails(() -> owner.remove(REQUEST,DELETE));check(access.deletions==0 && Files.exists(path));return; }
        if("changed-bytes".equals(mode)) { Files.write(path,new byte[]{9,9,9,9,9});fails(() -> owner.remove(REQUEST,DELETE));check(access.deletions==0);return; }
        if("changed-inode".equals(mode)) { Files.move(path,root.resolve("old.bin"));Files.write(path,new byte[]{1,2,3,4,5});fails(() -> owner.remove(REQUEST,DELETE));check(access.deletions==0);return; }
        if("early-missing".equals(mode)) { Files.delete(path);fails(owner::inspect);check(!owner.retired());return; }
        if("ignored-delete".equals(mode)) { access.ignore=true;owner.remove(REQUEST,DELETE);check(!owner.retired());owner.remove(REQUEST,DELETE);check(access.deletions==1);return; }
        if("lost-return".equals(mode)) { access.lost=true;fails(() -> owner.remove(REQUEST,DELETE));check(owner.uncertain(REQUEST,DELETE) && !owner.uncertain(REQUEST,"cccccccccccccccccccccccccccccccc"));owner.inspect();owner.remove(REQUEST,DELETE);check(owner.retired() && access.deletions==1);return; }
        if("permission-denied".equals(mode)) { access.deny=true;fails(() -> owner.remove(REQUEST,DELETE));check(!owner.retired());return; }
        owner.remove(REQUEST,DELETE);check(owner.retired() && !Files.exists(path) && access.deletions==1);
        owner.inspect();owner.remove(REQUEST,DELETE);check(access.deletions==1);
        fails(() -> owner.remove(REQUEST,"cccccccccccccccccccccccccccccccc"));
        if("late-file".equals(mode)) { Files.write(path,new byte[]{1,2,3,4,5});fails(owner::inspect);check(access.deletions==1); }
    }
}
