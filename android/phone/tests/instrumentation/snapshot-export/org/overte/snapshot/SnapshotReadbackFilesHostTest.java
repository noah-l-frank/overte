// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
package org.overte.snapshot;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.attribute.PosixFilePermissions;
import java.util.Arrays;
import java.util.Map;

/** Real private filesystem and stream faults; no Android provider execution. */
public final class SnapshotReadbackFilesHostTest {
    private static final String REQUEST="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
    private interface Work { void run() throws IOException; }
    private static void require(boolean value) { if(!value)throw new AssertionError("Private readback source contract"); }
    private static void fails(Work work) throws IOException {
        try { work.run(); } catch(IOException expected) { return; }throw new AssertionError("Missing readback rejection");
    }
    public static void main(String[] args) throws Exception {
        Path parent=Paths.get(args[1]);SnapshotReadbackFiles files=new SnapshotReadbackFiles(parent);
        byte[] bytes=new byte[262147];for(int i=0;i<bytes.length;++i)bytes[i]=(byte)(i%251);
        String mode=args[0];
        if("original".equals(mode)) {
            long before=System.currentTimeMillis();Map<String,Object> row=files.copy(REQUEST,new ByteArrayInputStream(bytes),()->false);
            Path path=Paths.get((String)row.get("path"));String id=(String)row.get("id");
            require(Arrays.equals(bytes,Files.readAllBytes(path)) && ((Number)row.get("bytes")).longValue()==bytes.length
                && row.get("request").equals(REQUEST) && row.get("phase").equals("complete")
                && ((String)row.get("sha256")).matches("[0-9a-f]{64}")
                && ((Number)row.get("capturedEpochMs")).longValue()>=before);
            row.put("sha256","foreign");require(!files.snapshot().get(0).get("sha256").equals("foreign"));
            fails(files::retire);files.remove(id);require(files.snapshot().isEmpty());files.retire();files.retiredAbsence();
        } else if("mutated".equals(mode) || "alias".equals(mode) || "hardlink".equals(mode) || "mode".equals(mode)) {
            Map<String,Object> row=files.copy(REQUEST,new ByteArrayInputStream(bytes),()->false);
            Path path=Paths.get((String)row.get("path"));String id=(String)row.get("id");
            if("mutated".equals(mode)) { bytes[0]^=1;Files.write(path,bytes); }
            else if("alias".equals(mode)) {
                Path foreign=parent.resolve("foreign.png");Files.write(foreign,bytes);Files.delete(path);Files.createSymbolicLink(path,foreign);
            } else if("hardlink".equals(mode))Files.createLink(parent.resolve("foreign-alias.png"),path);
            else Files.setPosixFilePermissions(path,PosixFilePermissions.fromString("rw-r--r--"));
            fails(()->files.remove(id));require(Files.exists(path));fails(files::retire);
        } else if("partial".equals(mode)) {
            InputStream broken=new InputStream() {
                int reads;boolean closed;
                @Override public int read() throws IOException { throw new IOException("Explicit broken stream"); }
                @Override public int read(byte[] output) throws IOException {
                    if(reads++!=0)throw new IOException("Actual read failure after partial output");
                    Arrays.fill(output,(byte)9);return output.length;
                }
                @Override public void close() { closed=true; }
            };
            fails(()->files.copy(REQUEST,broken,()->false));Map<String,Object> row=files.snapshot().get(0);
            require(row.get("phase").equals("failed") && row.get("sha256").equals(""));
            fails(files::retire);files.remove((String)row.get("id"));files.retire();
        } else if("cancel".equals(mode) || "empty".equals(mode) || "close-failure".equals(mode)) {
            InputStream input="empty".equals(mode) ? new ByteArrayInputStream(new byte[0])
                : new ByteArrayInputStream(bytes) { @Override public void close() throws IOException {
                    if("close-failure".equals(mode))throw new IOException("Actual destination close failure");
                }};
            fails(()->files.copy(REQUEST,input,()->"cancel".equals(mode)));
            Map<String,Object> row=files.snapshot().get(0);require(row.get("phase").equals("failed"));
            files.remove((String)row.get("id"));files.retire();
        } else if("foreign-cleanup".equals(mode)) {
            Map<String,Object> row=files.copy(REQUEST,new ByteArrayInputStream(bytes),()->false);
            Path path=Paths.get((String)row.get("path"));Path foreign=path.getParent().resolve("unowned.txt");
            Files.write(foreign,new byte[]{7});files.remove((String)row.get("id"));
            fails(files::retire);require(Files.exists(foreign));
        } else if("recreated".equals(mode)) {
            Map<String,Object> row=files.copy(REQUEST,new ByteArrayInputStream(bytes),()->false);
            Path directory=Paths.get((String)row.get("path")).getParent();files.remove((String)row.get("id"));files.retire();
            Files.createDirectory(directory);fails(files::retiredAbsence);
        } else if("rejected-stream".equals(mode)) {
            final boolean[] closed={false};InputStream input=new ByteArrayInputStream(bytes) { @Override public void close() { closed[0]=true; }};
            fails(()->files.copy("foreign",input,()->false));require(closed[0] && files.snapshot().isEmpty());files.retire();
        } else throw new AssertionError("Unknown readback host case");
    }
}
