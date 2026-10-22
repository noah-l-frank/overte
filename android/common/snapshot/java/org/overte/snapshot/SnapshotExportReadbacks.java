// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
package org.overte.snapshot;

import android.content.ContentResolver;
import android.content.Context;
import android.content.res.AssetFileDescriptor;
import android.net.Uri;
import android.os.CancellationSignal;
import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.Executors;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

/** E2E-only independent ContentResolver acquisition from original Save URIs.
 * No capture path, desired digest, requested byte count or caller URI is read.
 */
final class SnapshotExportReadbacks {
    private final SnapshotReadbackFiles files;
    private final String instance=UUID.randomUUID().toString().replace("-", "");
    private final long startedNanos=System.nanoTime();
    private long sequence,previousEpoch,previousElapsed;
    private final List<String> removedCopies=new ArrayList<>();
    private final Map<String, Destination> destinations = new LinkedHashMap<>();
    private final Map<String, Job> jobs = new LinkedHashMap<>();
    private final ExecutorService worker = Executors.newSingleThreadExecutor(task -> {
        Thread thread=new Thread(task,"OverteSnapshotEvidence");thread.setDaemon(true);return thread;
    });
    private final ScheduledExecutorService watchdog = Executors.newSingleThreadScheduledExecutor(task -> {
        Thread thread=new Thread(task,"OverteSnapshotEvidenceDeadline");thread.setDaemon(true);return thread;
    });
    private boolean complete=true,retired;
    private final SnapshotOsDestinations osDestinations;
    private final SnapshotShareGrants shareGrants;
    private static final class Destination {
        final ContentResolver resolver;final Uri uri;final boolean inserted;
        boolean published;
        Destination(ContentResolver resolver,Uri uri,boolean inserted) { this.resolver=resolver;this.uri=uri;this.inserted=inserted; }
    }
    private static final class Job {
        final String id,request;final CancellationSignal cancelled=new CancellationSignal();
        final AtomicReference<InputStream> opened=new AtomicReference<>();
        String phase="queued";Map<String,Object> original;long started,completed;
        Job(String id,String request) { this.id=id;this.request=request; }
        void cancel() {
            cancelled.cancel();InputStream value=opened.get();
            if(value!=null)try { value.close(); } catch(IOException ignored) { /* The worker retains failure. */ }
        }
        Map<String,Object> view() {
            Map<String,Object> value=new LinkedHashMap<>();value.put("id",id);value.put("request",request);
            value.put("phase",phase);value.put("startedEpochMs",started);value.put("completedEpochMs",completed);
            value.put("original",original==null ? null : new LinkedHashMap<>(original));return value;
        }
    }
    SnapshotExportReadbacks(Path privateFilesRoot) throws IOException { this(privateFilesRoot,false); }
    // Isolate the pre-existing file-copy contract in host tests. This component-
    // only constructor has no native/command entry and reports legacy v1, which
    // cannot qualify original OS destination retirement.
    SnapshotExportReadbacks(Path privateFilesRoot,boolean fileComponentOnly) throws IOException {
        files=new SnapshotReadbackFiles(privateFilesRoot);osDestinations=fileComponentOnly ? null : new SnapshotOsDestinations(worker,watchdog);
        shareGrants=fileComponentOnly ? null : new SnapshotShareGrants(osDestinations);
    }

    synchronized void destination(String request,Context context,ContentResolver resolver,Uri uri,boolean inserted,String name) {
        if(retired || request==null || !request.matches("[0-9a-f]{32}") || resolver==null || uri==null
                || !"content".equals(uri.getScheme()) || uri.getAuthority()==null || destinations.size()>=64) {
            complete=false;return;
        }
        Destination prior=destinations.get(request);
        if(prior!=null) { if(prior.resolver!=resolver || !prior.uri.equals(uri) || prior.inserted!=inserted)complete=false;return; }
        destinations.put(request,new Destination(resolver,uri,inserted));
        try { if(osDestinations!=null)osDestinations.destination(request,context,resolver,uri,inserted,name); }
        catch(IOException | RuntimeException failure) { complete=false; }
    }
    synchronized void published(String request,Uri uri) {
        Destination destination=destinations.get(request);
        if(retired || destination==null || !destination.uri.equals(uri)) { complete=false;return; }
        destination.published=true;
        try { if(osDestinations!=null)osDestinations.published(request); }catch(IOException | RuntimeException failure) { complete=false; }
    }
    synchronized boolean read(String request,String id) {
        if(!complete || retired || request==null || id==null || !request.matches("[0-9a-f]{32}") || !id.matches("[0-9a-f]{32}"))return false;
        Job prior=jobs.get(id);
        if(prior!=null)return prior.request.equals(request);
        if(jobs.size()>=64)return false;
        Destination destination=destinations.get(request);
        if(destination==null || !destination.published)return false;
        Job job=new Job(id,request);jobs.put(id,job);worker.execute(() -> acquire(job,destination));return true;
    }
    private void acquire(Job job,Destination destination) {
        synchronized(this) { job.phase="reading";job.started=System.currentTimeMillis(); }
        ScheduledFuture<?> timeout=watchdog.schedule(job::cancel,15,TimeUnit.SECONDS);
        Map<String,Object> original=null;
        try(AssetFileDescriptor descriptor=destination.resolver.openAssetFileDescriptor(destination.uri,"r",job.cancelled)) {
            if(descriptor==null)throw new IOException("Destination descriptor unavailable");
            InputStream input=descriptor.createInputStream();job.opened.set(input);
            if(job.cancelled.isCanceled()) { input.close();throw new IOException("Readback expired"); }
            original=files.copy(job.request,input,job.cancelled::isCanceled);
        } catch(IOException | RuntimeException failure) {
            original=null;
        } finally {
            job.opened.set(null);timeout.cancel(false);
            synchronized(this) {
                job.original=original;job.phase=original!=null && !job.cancelled.isCanceled() ? "complete" : "failed";
                job.completed=System.currentTimeMillis();
            }
        }
    }
    synchronized Map<String,Object> observation() throws IOException {
        if(retired)files.retiredAbsence();
        long epoch=System.currentTimeMillis(),elapsed=(System.nanoTime()-startedNanos)/1000000;
        if(epoch<=0 || epoch<previousEpoch || elapsed<previousElapsed || sequence==Long.MAX_VALUE)complete=false;
        previousEpoch=epoch;previousElapsed=elapsed;
        Map<String,Object> value=new LinkedHashMap<>();value.put("snapshotExportReadbacksVersion",osDestinations==null ? 1 : 2);
        value.put("instance",instance);value.put("sequence",++sequence);value.put("elapsedMs",elapsed);
        value.put("complete",complete);value.put("copiesRetired",retired);value.put("capturedEpochMs",epoch);
        value.put("workersTerminated",worker.isTerminated() && watchdog.isTerminated() && (osDestinations==null || osDestinations.inspectionsTerminated()));
        if(osDestinations!=null) { value.put("osDestinations",osDestinations.observation());value.put("shareGrants",shareGrants.observation()); }
        List<Map<String,Object>> rows=new ArrayList<>();
        for(Map.Entry<String,Destination> entry:destinations.entrySet()) {
            Map<String,Object> row=new LinkedHashMap<>();row.put("request",entry.getKey());row.put("uri",entry.getValue().uri.toString());
            row.put("inserted",entry.getValue().inserted);row.put("published",entry.getValue().published);rows.add(row);
        }
        value.put("destinations",rows);rows=new ArrayList<>();for(Job job:jobs.values())rows.add(job.view());
        value.put("jobs",rows);value.put("files",retired ? new ArrayList<>() : files.snapshot());
        value.put("removedCopies",new ArrayList<>(removedCopies));return value;
    }
    synchronized void cancel(String id) {
        Job job=jobs.get(id);if(job!=null && !("complete".equals(job.phase) || "failed".equals(job.phase)))job.cancel();
    }
    synchronized void removeCopy(String id) throws IOException {
        for(Job job:jobs.values())if("queued".equals(job.phase) || "reading".equals(job.phase))throw new IOException("Readback still active");
        if(removedCopies.contains(id)) { files.observationAbsence(id);return; }
        files.remove(id);removedCopies.add(id);
    }
    synchronized boolean removeDestination(String request,String id) throws IOException { return osDestinations!=null && osDestinations.remove(request,id); }
    synchronized boolean inspectDestinations(String id) throws IOException { return osDestinations!=null && osDestinations.inspect(id); }
    void shareIssued(String request,Context context,Uri uri,android.content.Intent chooser) { if(shareGrants!=null)shareGrants.issued(request,context,uri,chooser); }
    void shareSelected(String request,android.content.ComponentName component) { if(shareGrants!=null)shareGrants.selected(request,component); }
    synchronized boolean revokeShare(String request,String id) throws IOException { return shareGrants!=null && shareGrants.revoke(request,id); }
    synchronized boolean inspectShares(String id) throws IOException { return shareGrants!=null && shareGrants.inspect(id); }
    void retireCopies() throws IOException {
        synchronized(this) {
            if(osDestinations!=null && !osDestinations.retired())throw new IOException("Original OS destinations remain owned");
            if(shareGrants!=null && !shareGrants.retired())throw new IOException("Original Share URI grants remain owned");
            for(Job job:jobs.values())if("queued".equals(job.phase) || "reading".equals(job.phase))throw new IOException("Readback still active");
            if(retired)files.retiredAbsence();
            else { files.retire();retired=true;worker.shutdown();watchdog.shutdown(); }
        }
        try {
            if(!worker.awaitTermination(5,TimeUnit.SECONDS) || !watchdog.awaitTermination(5,TimeUnit.SECONDS))
                throw new IOException("Readback worker still active");
        } catch(InterruptedException interrupted) { Thread.currentThread().interrupt();throw new IOException("Readback retirement interrupted"); }
    }
}
