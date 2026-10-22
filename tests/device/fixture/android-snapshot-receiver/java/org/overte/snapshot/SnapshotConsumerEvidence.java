// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
package org.overte.snapshot;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.DirectoryStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.HashSet;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.Executors;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

/** Actual fixture stream/file/thread ownership; Android supplies original APIs.
 * This class has no URI/path/hash/result command input.
 */
final class SnapshotConsumerEvidence {
    interface Access {
        Map<String,Object> identity() throws IOException;
        InputStream open() throws IOException;
        boolean granted() throws IOException;
        boolean closed();
        void cancel();
        void finished();
    }
    private final SnapshotReadbackFiles files;
    private final String instance=UUID.randomUUID().toString().replace("-","");
    private final ExecutorService worker=Executors.newSingleThreadExecutor(task -> { Thread thread=new Thread(task,"OverteSnapshotConsumer");thread.setDaemon(true);return thread; });
    private final ScheduledExecutorService deadline=Executors.newSingleThreadScheduledExecutor(task -> { Thread thread=new Thread(task,"OverteSnapshotConsumerDeadline");thread.setDaemon(true);return thread; });
    private final Set<String> observations=new HashSet<>(),binaries=new HashSet<>();
    private final List<String> removed=new ArrayList<>();
    private final List<Thread> transfers=new ArrayList<>();
    private final List<ScheduledExecutorService> transferClocks=new ArrayList<>();
    synchronized void transfer(Runnable write,java.io.Closeable close) throws IOException {
        if(transfers.size()>=4096)throw new IOException("Receiver transfer inventory full");
        ScheduledExecutorService clock=Executors.newSingleThreadScheduledExecutor(task -> { Thread thread=new Thread(task,"OverteSnapshotConsumerDeadline");thread.setDaemon(true);return thread; });transferClocks.add(clock);
        Thread thread=new Thread(() -> {
            ScheduledFuture<?> timeout=clock.schedule(() -> { try { close.close(); }catch(IOException ignored) { /* Actual writer/reader retain failure. */ } },15,TimeUnit.SECONDS);
            try { write.run(); }finally { timeout.cancel(false);clock.shutdown(); }
        },"OverteSnapshotReceiverSource");thread.setDaemon(true);transfers.add(thread);thread.start();
    }
    private boolean transfersTerminated() {
        for(Thread thread:transfers)if(thread.isAlive())return false;
        for(ScheduledExecutorService clock:transferClocks)if(!clock.isTerminated())return false;
        return true;
    }
    private final AtomicBoolean cancelled=new AtomicBoolean();
    private String run="",arm="",phase="idle";private Access access;
    private Map<String,Object> identity,original;private boolean complete=true,activity,retired;
    private long sequence,started,completed,previousEpoch;
    SnapshotConsumerEvidence(Path root) throws IOException {
        // A new process cannot hide/adopt private originals from an old process.
        try(DirectoryStream<Path> entries=Files.newDirectoryStream(root,"overte-snapshot-e2e-*")) {
            if(entries.iterator().hasNext())throw new IOException("Unretired receiver originals");
        }
        files=new SnapshotReadbackFiles(root);
    }
    static boolean nonce(String value) { return value!=null && value.matches("[0-9a-f]{32}"); }
    synchronized void arm(String run,String arm) throws IOException {
        if(!this.run.isEmpty() || !nonce(run) || !nonce(arm))throw new IOException("Receiver already armed or unretired");
        this.run=run;this.arm=arm;phase="armed";
    }
    synchronized void checkRun(String run) throws IOException { if(this.run.isEmpty() || !this.run.equals(run))throw new IOException("Foreign receiver run"); }
    synchronized void rejected() { complete=false; }
    synchronized void activity(boolean alive) { activity=alive; }
    void receive(Access actual) {
        synchronized(this) {
            if(!phase.equals("armed") || access!=null || retired) { complete=false;return; }
            access=actual;phase="queued";
        }
        worker.execute(() -> acquire(actual));
    }
    private void acquire(Access actual) {
        synchronized(this) { phase="reading";started=System.currentTimeMillis(); }
        ScheduledFuture<?> timeout=deadline.schedule(this::cancel,15,TimeUnit.SECONDS);
        Map<String,Object> received=null,copy=null;
        try {
            received=actual.identity();
            if(!actual.granted())throw new IOException("Receiver has no original read grant");
            synchronized(this) { identity=new LinkedHashMap<>(received); }
            copy=files.copy(arm,actual.open(),cancelled::get);
            if(!actual.closed())throw new IOException("Original receiver descriptor remains open");
        } catch(IOException | RuntimeException failure) { copy=null; }
        finally {
            timeout.cancel(false);
            synchronized(this) { original=copy;phase=copy!=null && !cancelled.get() ? "complete" : "failed";completed=System.currentTimeMillis(); }
            actual.finished();
        }
    }
    void cancel() { cancelled.set(true);Access value;synchronized(this) { value=access; }if(value!=null)value.cancel(); }
    synchronized void remove(String id) throws IOException {
        if(!nonce(id) || phase.equals("queued") || phase.equals("reading"))throw new IOException("Receiver still owns active I/O");
        if(removed.contains(id)) { files.observationAbsence(id);return; }
        files.remove(id);removed.add(id);
    }
    void retire() throws IOException {
        Access actual;synchronized(this) { actual=access;if(activity || !transfersTerminated() || phase.equals("reading") || phase.equals("queued"))throw new IOException("Receiver still active"); }
        if(actual!=null && (!actual.closed() || actual.granted()))throw new IOException("Receiver original stream/grant remains owned");
        synchronized(this) {
            if(retired)files.retiredAbsence();else { files.retire();retired=true;worker.shutdown();deadline.shutdown(); }
        }
        try { if(!worker.awaitTermination(5,TimeUnit.SECONDS) || !deadline.awaitTermination(5,TimeUnit.SECONDS))throw new IOException("Receiver workers not terminated"); }
        catch(InterruptedException failure) { Thread.currentThread().interrupt();throw new IOException("Receiver retirement interrupted"); }
    }
    Map<String,Object> observation(String run,String nonce) throws IOException {
        Access actual;synchronized(this) {
            if(!this.run.equals(run) || !nonce(nonce) || observations.size()>=4096 || !observations.add(nonce))throw new IOException("Receiver observation scope/replay");
            actual=access;
        }
        boolean grant=actual!=null && actual.granted(),closed=actual==null || actual.closed();
        synchronized(this) {
            long epoch=System.currentTimeMillis();if(epoch<=0 || epoch<previousEpoch)complete=false;previousEpoch=epoch;
            if(retired)files.retiredAbsence();
            Map<String,Object> row=new LinkedHashMap<>();row.put("snapshotConsumerVersion",1);row.put("runId",run);row.put("armId",arm);
            row.put("observationId",nonce);row.put("instance",instance);row.put("sequence",++sequence);row.put("capturedEpochMs",epoch);
            row.put("complete",complete);row.put("phase",phase);row.put("activityAlive",activity);row.put("cancelled",cancelled.get());
            row.put("identity",identity==null ? null : new LinkedHashMap<>(identity));row.put("original",original==null ? null : new LinkedHashMap<>(original));
            row.put("startedEpochMs",started);row.put("completedEpochMs",completed);row.put("grantPresent",grant);row.put("originalClosed",closed);
            row.put("files",retired ? new ArrayList<>() : files.snapshot());row.put("removedCopies",new ArrayList<>(removed));
            row.put("retired",retired);row.put("workersTerminated",worker.isTerminated() && deadline.isTerminated() && transfersTerminated());return row;
        }
    }
    synchronized byte[] binary(String run,String id,String nonce) throws IOException {
        if(!this.run.equals(run) || !nonce(nonce) || binaries.size()>=4096 || !binaries.add(nonce) || retired)throw new IOException("Receiver original scope/replay");
        return files.originalBytes(id);
    }
}
