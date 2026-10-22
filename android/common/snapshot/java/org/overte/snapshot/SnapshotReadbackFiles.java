// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
package org.overte.snapshot;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.nio.file.attribute.BasicFileAttributes;
import java.nio.file.attribute.PosixFilePermissions;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.function.BooleanSupplier;

/** Private copies acquired from a real external stream, never the capture path.
 * The caller owns cancelling/closing a blocked provider stream. This component
 * bounds bytes and checks cancellation/deadline between actual reads.
 */
final class SnapshotReadbackFiles {
    private static final long MAX_BYTES = 256L * 1024 * 1024;
    private static final int LIMIT = 64;
    private final Path directory;
    private final Object directoryKey;
    private final Map<String, Entry> entries = new LinkedHashMap<>();
    private static final class Entry {
        final String id, request;
        final Path path;
        Object fileKey;
        long bytes, capturedEpochMs;
        String sha256 = "", phase = "planned";
        Entry(String id, String request, Path path) { this.id=id; this.request=request; this.path=path; }
        Map<String, Object> view() {
            Map<String, Object> value = new LinkedHashMap<>();
            value.put("id",id); value.put("request",request); value.put("path",path.toString());
            value.put("phase",phase); value.put("bytes",bytes); value.put("sha256",sha256);
            value.put("capturedEpochMs",capturedEpochMs); return value;
        }
    }

    SnapshotReadbackFiles(Path privateFilesRoot) throws IOException {
        Path parent = privateFilesRoot.toRealPath();
        if (!Files.isDirectory(parent, LinkOption.NOFOLLOW_LINKS)) throw new IOException("Private root unavailable");
        directory=parent.resolve("overte-snapshot-e2e-"+UUID.randomUUID().toString().replace("-", ""));
        Files.createDirectory(directory,PosixFilePermissions.asFileAttribute(PosixFilePermissions.fromString("rwx------")));
        directoryKey=attributes(directory).fileKey();
        if (directoryKey==null) throw new IOException("Directory identity unavailable");
    }
    private static BasicFileAttributes attributes(Path path) throws IOException {
        return Files.readAttributes(path,BasicFileAttributes.class,LinkOption.NOFOLLOW_LINKS);
    }
    private void bound() throws IOException {
        BasicFileAttributes actual=attributes(directory);
        if (!actual.isDirectory() || actual.isSymbolicLink() || !directoryKey.equals(actual.fileKey())
                || !Files.getPosixFilePermissions(directory,LinkOption.NOFOLLOW_LINKS)
                    .equals(PosixFilePermissions.fromString("rwx------"))) throw new IOException("Private directory changed");
    }
    private void bound(Entry entry) throws IOException {
        bound();BasicFileAttributes actual=attributes(entry.path);
        if (!actual.isRegularFile() || actual.isSymbolicLink() || entry.fileKey==null || !entry.fileKey.equals(actual.fileKey())
                || ((Number)Files.getAttribute(entry.path,"unix:nlink",LinkOption.NOFOLLOW_LINKS)).longValue()!=1
                || !Files.getPosixFilePermissions(entry.path,LinkOption.NOFOLLOW_LINKS)
                    .equals(PosixFilePermissions.fromString("rw-------"))) throw new IOException("Private original changed");
    }
    private static MessageDigest digest() {
        try { return MessageDigest.getInstance("SHA-256"); }
        catch (NoSuchAlgorithmException impossible) { throw new IllegalStateException(impossible); }
    }
    private static String hex(byte[] bytes) {
        char[] result=new char[bytes.length*2];String digits="0123456789abcdef";
        for(int i=0;i<bytes.length;++i) { result[2*i]=digits.charAt((bytes[i]>>4)&15);result[2*i+1]=digits.charAt(bytes[i]&15); }
        return new String(result);
    }
    private static void deadline(BooleanSupplier cancelled,long start) throws IOException {
        if (cancelled.getAsBoolean() || System.nanoTime()-start>=15000000000L) throw new IOException("Readback cancelled or expired");
    }

    Map<String,Object> copy(String request,InputStream original,BooleanSupplier cancelled) throws IOException {
        Entry entry;
        try {
            synchronized(this) {
                if (request==null || !request.matches("[0-9a-f]{32}") || original==null || cancelled==null || entries.size()>=LIMIT)
                    throw new IOException("Readback authority unavailable");
                bound();String id=UUID.randomUUID().toString().replace("-", "");
                entry=new Entry(id,request,directory.resolve(id+".bin"));entries.put(id,entry);
            }
        } catch(IOException | RuntimeException failure) {
            if(original!=null)try { original.close(); } catch(IOException close) { failure.addSuppressed(close); }
            throw failure;
        }
        long start=System.nanoTime(),total=0;MessageDigest observed=digest();
        try (InputStream input=original) {
            synchronized(this) {
                // Observers must see either the absent planned path or its
                // acquired original identity, never a half-published file.
                Files.createFile(entry.path,PosixFilePermissions.asFileAttribute(PosixFilePermissions.fromString("rw-------")));
                entry.fileKey=attributes(entry.path).fileKey();entry.phase="reading";bound(entry);
            }
            try (OutputStream output=Files.newOutputStream(entry.path,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)) {
                byte[] buffer=new byte[65536];int count;
                while(true) {
                    deadline(cancelled,start);count=input.read(buffer);deadline(cancelled,start);
                    if(count==-1)break;
                    if(count==0 || (total+=count)>MAX_BYTES)throw new IOException("Empty read or oversized destination");
                    output.write(buffer,0,count);observed.update(buffer,0,count);
                }
                if(total==0)throw new IOException("Destination is empty");
                output.flush();
            }
            synchronized(this) {
                deadline(cancelled,start);bound(entry);
                if(attributes(entry.path).size()!=total)throw new IOException("Readback size changed");
                entry.bytes=total;entry.sha256=hex(observed.digest());entry.capturedEpochMs=System.currentTimeMillis();entry.phase="complete";
                return new LinkedHashMap<>(entry.view());
            }
        } catch(IOException | RuntimeException failure) {
            synchronized(this) { entry.phase="failed"; }
            throw failure;
        }
    }

    synchronized List<Map<String,Object>> snapshot() throws IOException {
        bound();List<Map<String,Object>> result=new ArrayList<>();
        for(Entry entry:entries.values()) {
            if(entry.fileKey!=null)bound(entry);
            else if(!Files.notExists(entry.path,LinkOption.NOFOLLOW_LINKS))throw new IOException("Unqualified private original");
            result.add(entry.view());
        }
        return result;
    }
    synchronized byte[] originalBytes(String id) throws IOException {
        Entry entry=entries.get(id);
        if(entry==null || !"complete".equals(entry.phase))throw new IOException("Original is not owned and complete");
        bound(entry);long start=System.nanoTime();
        java.io.ByteArrayOutputStream output=new java.io.ByteArrayOutputStream();MessageDigest actual=digest();long total=0;
        try(InputStream input=Files.newInputStream(entry.path,StandardOpenOption.READ,LinkOption.NOFOLLOW_LINKS)) {
            byte[] data=new byte[65536];int count;
            while((count=input.read(data))!=-1) {
                if(count==0 || (total+=count)>MAX_BYTES || System.nanoTime()-start>=15000000000L)throw new IOException("Original read expired or changed");
                output.write(data,0,count);actual.update(data,0,count);
            }
        }
        bound(entry);
        if(total!=entry.bytes || !hex(actual.digest()).equals(entry.sha256))throw new IOException("Original content changed");
        return output.toByteArray();
    }

    synchronized void remove(String id) throws IOException {
        Entry entry=entries.get(id);
        if(entry==null)throw new IOException("Readback not owned");
        if(entry.fileKey==null) {
            bound();
            if(!"failed".equals(entry.phase) || !Files.notExists(entry.path,LinkOption.NOFOLLOW_LINKS))
                throw new IOException("Unqualified private original");
            entries.remove(id);return;
        }
        bound(entry);
        if("reading".equals(entry.phase))throw new IOException("Readback is still active");
        if("complete".equals(entry.phase)) {
            MessageDigest actual=digest();long count=0;
            try(InputStream input=Files.newInputStream(entry.path,StandardOpenOption.READ,LinkOption.NOFOLLOW_LINKS)) {
                byte[] buffer=new byte[65536];int size;
                while((size=input.read(buffer))!=-1) { count+=size;if(count>MAX_BYTES)throw new IOException("Readback changed");actual.update(buffer,0,size); }
            }
            if(count!=entry.bytes || !hex(actual.digest()).equals(entry.sha256))throw new IOException("Readback content changed");
        }
        bound(entry);Files.delete(entry.path);
        if(Files.exists(entry.path,LinkOption.NOFOLLOW_LINKS))throw new IOException("Readback removal not observed");
        entries.remove(id);
    }
    synchronized void retire() throws IOException {
        bound();if(!entries.isEmpty())throw new IOException("Readbacks remain owned");
        try(java.nio.file.DirectoryStream<Path> actual=Files.newDirectoryStream(directory)) {
            if(actual.iterator().hasNext())throw new IOException("Unknown private files remain");
        }
        Files.delete(directory);
        if(Files.exists(directory,LinkOption.NOFOLLOW_LINKS))throw new IOException("Private directory still exists");
    }
    synchronized void retiredAbsence() throws IOException {
        if(!Files.notExists(directory,LinkOption.NOFOLLOW_LINKS))throw new IOException("Retired private directory returned");
    }
    synchronized void observationAbsence(String id) throws IOException {
        if(id==null || !id.matches("[0-9a-f]{32}") || entries.containsKey(id))throw new IOException("Readback still owned");
        if(!Files.notExists(directory.resolve(id+".bin"),LinkOption.NOFOLLOW_LINKS))throw new IOException("Removed readback returned");
    }
}
