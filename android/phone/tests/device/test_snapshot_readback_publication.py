"""Actual Java file publication under deterministic concurrent observation.

Only the Files import is redirected to a delegating filesystem boundary that
pauses after actual createFile. Original method bodies, bytes, identity,
threads and cleanup run against the real host filesystem; no Android verdict.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[4]
FILES=r'''package org.overte.snapshot;
import java.io.*;
import java.nio.file.*;
import java.nio.file.attribute.*;
import java.util.*;
import java.util.concurrent.*;
final class Files {
 static final CountDownLatch created=new CountDownLatch(1),release=new CountDownLatch(1);
 static Path createFile(Path path,FileAttribute<?>... attrs)throws IOException {
  Path actual=java.nio.file.Files.createFile(path,attrs);created.countDown();
  try{if(!release.await(3,TimeUnit.SECONDS))throw new IOException("Original create boundary was not released");}
  catch(InterruptedException error){Thread.currentThread().interrupt();throw new IOException(error);}
  return actual;
 }
 static boolean isDirectory(Path p,LinkOption... opts){return java.nio.file.Files.isDirectory(p,opts);}
 static Path createDirectory(Path p,FileAttribute<?>... attrs)throws IOException{return java.nio.file.Files.createDirectory(p,attrs);}
 static <A extends BasicFileAttributes> A readAttributes(Path p,Class<A> type,LinkOption... opts)throws IOException{return java.nio.file.Files.readAttributes(p,type,opts);}
 static Set<PosixFilePermission> getPosixFilePermissions(Path p,LinkOption... opts)throws IOException{return java.nio.file.Files.getPosixFilePermissions(p,opts);}
 static Object getAttribute(Path p,String name,LinkOption... opts)throws IOException{return java.nio.file.Files.getAttribute(p,name,opts);}
 static OutputStream newOutputStream(Path p,OpenOption... opts)throws IOException{return java.nio.file.Files.newOutputStream(p,opts);}
 static InputStream newInputStream(Path p,OpenOption... opts)throws IOException{return java.nio.file.Files.newInputStream(p,opts);}
 static boolean notExists(Path p,LinkOption... opts){return java.nio.file.Files.notExists(p,opts);}
 static boolean exists(Path p,LinkOption... opts){return java.nio.file.Files.exists(p,opts);}
 static void delete(Path p)throws IOException{java.nio.file.Files.delete(p);}
 static DirectoryStream<Path> newDirectoryStream(Path p)throws IOException{return java.nio.file.Files.newDirectoryStream(p);}
}
'''
CHECK=r'''package org.overte.snapshot;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
public final class PublicationCheck {
 public static void main(String[] args)throws Exception {
  SnapshotReadbackFiles owner=new SnapshotReadbackFiles(Paths.get(args[0]));
  ExecutorService threads=Executors.newFixedThreadPool(2);Throwable failed=null;
  try {
   Future<Map<String,Object>> copy=threads.submit(()->owner.copy("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",new ByteArrayInputStream(new byte[]{1,2,3,4}),()->false));
   if(!Files.created.await(2,TimeUnit.SECONDS))throw new AssertionError("Actual file was not created");
   CountDownLatch entered=new CountDownLatch(1);
   Future<List<Map<String,Object>>> observation=threads.submit(()->{entered.countDown();return owner.snapshot();});
   if(!entered.await(2,TimeUnit.SECONDS))throw new AssertionError("Concurrent observation never started");
   try{observation.get(200,TimeUnit.MILLISECONDS);}
   catch(TimeoutException expected){/* Atomic publication keeps observation pending. */}
   catch(ExecutionException actual){failed=actual.getCause();}
   finally{Files.release.countDown();}
   Map<String,Object> original=copy.get(2,TimeUnit.SECONDS);
   if(failed==null)try{List<Map<String,Object>> rows=observation.get(2,TimeUnit.SECONDS);
    if(rows.size()!=1 || !rows.get(0).get("id").equals(original.get("id")))throw new AssertionError("Original identity not published");
   }catch(ExecutionException actual){failed=actual.getCause();}
   List<Map<String,Object>> current=owner.snapshot();
   if(current.size()!=1 || !current.get(0).get("phase").equals("complete") || ((Number)current.get(0).get("bytes")).intValue()!=4)
    throw new AssertionError("Actual copied bytes are unavailable");
   owner.remove((String)original.get("id"));owner.retire();owner.retiredAbsence();
  }finally{Files.release.countDown();threads.shutdownNow();if(!threads.awaitTermination(2,TimeUnit.SECONDS))throw new AssertionError("Original test threads remain");}
  if(failed!=null){System.err.println(failed.getClass().getName()+": "+failed.getMessage());System.exit(12);}
 }
}
'''


class SnapshotReadbackPublicationTests(unittest.TestCase):
    def compile(self,parent,original):
        stage=parent/'classes';stage.mkdir()
        subject=parent/'SnapshotReadbackFiles.java';subject.write_text(original.replace('import java.nio.file.Files;',''))
        boundary=parent/'Files.java';boundary.write_text(FILES)
        check=parent/'PublicationCheck.java';check.write_text(CHECK)
        subprocess.run(['javac','--release','8','-d',str(stage),str(subject),str(boundary),str(check)],check=True,timeout=30,
            capture_output=True,text=True)
        root=parent/'original-files';root.mkdir(mode=0o700)
        return subprocess.run(['java','-cp',str(stage),'org.overte.snapshot.PublicationCheck',str(root)],
            timeout=8,capture_output=True,text=True)

    def test_concurrent_original_observation_cannot_see_file_before_its_identity_is_published(self):
        source=(ROOT/'android/common/snapshot/java/org/overte/snapshot/SnapshotReadbackFiles.java').read_text()
        parent=ROOT/'build/snapshot-readback-publication';parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='atomic-',dir=parent) as raw:
            result=self.compile(Path(raw),source);self.assertEqual(0,result.returncode,result.stderr)

    def test_original_non_atomic_creation_is_rejected_in_the_same_actual_file_window(self):
        source=(ROOT/'android/common/snapshot/java/org/overte/snapshot/SnapshotReadbackFiles.java').read_text()
        start=source.index('            synchronized(this) {\n                // Observers must see either')
        end=source.index('            try (OutputStream output=',start)
        legacy='''            Files.createFile(entry.path,PosixFilePermissions.asFileAttribute(PosixFilePermissions.fromString("rw-------")));
            synchronized(this) { entry.fileKey=attributes(entry.path).fileKey();entry.phase="reading";bound(entry); }
'''
        parent=ROOT/'build/snapshot-readback-publication';parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='original-race-',dir=parent) as raw:
            result=self.compile(Path(raw),source[:start]+legacy+source[end:])
            self.assertEqual(12,result.returncode,result.stderr)
            self.assertIn('Unqualified private original',result.stderr)


if __name__=='__main__':unittest.main()
