"""Actual asynchronous readback coordinator on explicit Android provider seams.

The source stream/files/threads/clocks are real host operations. ContentResolver,
Uri, descriptor and cancellation are synthetic boundaries, never Android proof.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
import overte_phone_snapshot_readbacks as contract
STUBS={
'android/content/Intent.java':'package android.content; public class Intent {}',
'android/content/ComponentName.java':'package android.content; public class ComponentName {}',
'org/overte/snapshot/SnapshotShareGrants.java':'''package org.overte.snapshot;
final class SnapshotShareGrants {
 SnapshotShareGrants(SnapshotOsDestinations queue){throw new AssertionError();}
 void issued(String request,android.content.Context context,android.net.Uri uri,android.content.Intent chooser){throw new AssertionError();}
 void selected(String request,android.content.ComponentName component){throw new AssertionError();}
 boolean revoke(String request,String id)throws java.io.IOException{throw new AssertionError();}
 boolean inspect(String id)throws java.io.IOException{throw new AssertionError();}
 boolean retired(){throw new AssertionError();}
 java.util.Map<String,Object> observation(){throw new AssertionError();}
}''',

'android/content/Context.java':'package android.content; public abstract class Context {}',
'org/overte/snapshot/SnapshotOsDestinations.java':'''package org.overte.snapshot;
// This file-only harness must never enter Android OS ownership glue.
final class SnapshotOsDestinations {
 SnapshotOsDestinations(java.util.concurrent.ExecutorService worker,java.util.concurrent.ScheduledExecutorService clock){throw new AssertionError("Android glue entered file-only fixture");}
 void destination(String request,android.content.Context context,android.content.ContentResolver resolver,android.net.Uri uri,boolean inserted,String name)throws java.io.IOException{throw new AssertionError();}
 void published(String request)throws java.io.IOException{throw new AssertionError();}
 boolean remove(String request,String id)throws java.io.IOException{throw new AssertionError();}
 boolean inspect(String id)throws java.io.IOException{throw new AssertionError();}
 java.util.Map<String,Object> observation(){throw new AssertionError();}
 boolean retired(){throw new AssertionError();}
 boolean inspectionsTerminated(){throw new AssertionError();}
}''',
'android/net/Uri.java':'''package android.net;
public final class Uri {
 private final java.net.URI value; private Uri(String raw){value=java.net.URI.create(raw);}
 public static Uri parse(String raw){return new Uri(raw);} public String getScheme(){return value.getScheme();}
 public String getAuthority(){return value.getAuthority();} public String toString(){return value.toString();}
 public boolean equals(Object other){return other instanceof Uri && value.equals(((Uri)other).value);}
 public int hashCode(){return value.hashCode();}
}''',
'android/os/CancellationSignal.java':'''package android.os;
public final class CancellationSignal {
 private volatile boolean cancelled; public void cancel(){cancelled=true;}public boolean isCanceled(){return cancelled;}
}''',
'android/content/ContentResolver.java':'''package android.content;
public abstract class ContentResolver {
 public abstract android.content.res.AssetFileDescriptor openAssetFileDescriptor(android.net.Uri uri,String mode,
  android.os.CancellationSignal signal) throws java.io.IOException;
}''',
'android/content/res/AssetFileDescriptor.java':'''package android.content.res;
public abstract class AssetFileDescriptor implements java.io.Closeable {
 public abstract java.io.InputStream createInputStream() throws java.io.IOException;
}''',
}
SOURCE=r'''package org.overte.snapshot;
import android.content.ContentResolver;
import android.content.res.AssetFileDescriptor;
import android.net.Uri;
import android.os.CancellationSignal;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
public final class SnapshotReadbackJobsHostTest {
 static final String REQUEST="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",ONE="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",TWO="cccccccccccccccccccccccccccccccc";
 static void need(boolean value){if(!value)throw new AssertionError("Actual readback job contract");}
 static String json(Object value){
  if(value==null)return "null";
  if(value instanceof String)return "\""+((String)value).replace("\\","\\\\").replace("\"","\\\"")+"\"";
  if(value instanceof Number || value instanceof Boolean)return value.toString();
  StringJoiner result=new StringJoiner(",",value instanceof Map ? "{" : "[",value instanceof Map ? "}" : "]");
  if(value instanceof Map)for(Object raw:((Map<?,?>)value).entrySet()){
   Map.Entry<?,?> row=(Map.Entry<?,?>)raw;result.add(json(row.getKey())+":"+json(row.getValue()));
  }else for(Object row:(List<?>)value)result.add(json(row));return result.toString();
 }
 @SuppressWarnings("unchecked") static List<Map<String,Object>> rows(Map<String,Object> value,String key){return (List<Map<String,Object>>)value.get(key);}
 static class Provider extends ContentResolver {
  byte[] body=new byte[]{9,8,7,6};volatile int opens,closes;boolean failClose,blockOpen,holdDescriptorClose;
  final CountDownLatch entered=new CountDownLatch(1),release=new CountDownLatch(1);
  public AssetFileDescriptor openAssetFileDescriptor(Uri uri,String mode,CancellationSignal signal)throws IOException{
   need(uri.toString().equals("content://media/external/images/media/418") && mode.equals("r"));++opens;
   if(blockOpen){entered.countDown();while(!signal.isCanceled())try{Thread.sleep(2);}catch(InterruptedException e){throw new IOException(e);}throw new IOException("Cancelled real provider wait");}
   final byte[] original=Arrays.copyOf(body,body.length);
   return new AssetFileDescriptor(){
    public InputStream createInputStream(){return new ByteArrayInputStream(original);}
    public void close()throws IOException{++closes;if(holdDescriptorClose){entered.countDown();try{if(!release.await(4,TimeUnit.SECONDS))throw new IOException("Missing close release");}catch(InterruptedException e){throw new IOException(e);}}if(failClose)throw new IOException("Actual descriptor close failure");}
   };
  }
 }
 static Map<String,Object> job(SnapshotExportReadbacks owner,String id)throws IOException{
  for(Map<String,Object> row:rows(owner.observation(),"jobs"))if(row.get("id").equals(id))return row;
  throw new AssertionError("Missing original job");
 }
 static Map<String,Object> terminal(SnapshotExportReadbacks owner,String id)throws Exception{
  long start=System.nanoTime();while(System.nanoTime()-start<5000000000L){Map<String,Object> value=job(owner,id);
   if(value.get("phase").equals("complete")||value.get("phase").equals("failed"))return value;Thread.sleep(2);}
  throw new AssertionError("Readback deadline not terminal");
 }
 static void retire(SnapshotExportReadbacks owner)throws IOException{
  for(Map<String,Object> row:rows(owner.observation(),"files"))owner.removeCopy((String)row.get("id"));
  owner.retireCopies();owner.retireCopies();Map<String,Object> source=owner.observation();
  need(Boolean.TRUE.equals(source.get("copiesRetired"))&&Boolean.TRUE.equals(source.get("workersTerminated"))&&rows(source,"files").isEmpty());
 }
 @SuppressWarnings("unchecked") public static void main(String[] args)throws Exception{
  SnapshotExportReadbacks owner=new SnapshotExportReadbacks(Paths.get(args[1]),true);Provider provider=new Provider();
  Uri uri=Uri.parse("content://media/external/images/media/418");owner.destination(REQUEST,null,provider,uri,true,"original.png");
  String mode=args[0];
  if(mode.equals("admission")){
   need(!owner.read(REQUEST,ONE)&&!owner.read(TWO,ONE));owner.published(REQUEST,uri);
   need(!owner.read("foreign",ONE)&&!owner.read(REQUEST,"foreign"));retire(owner);need(provider.opens==0);return;
  }
  owner.published(REQUEST,uri);
  if(mode.equals("failed-close"))provider.failClose=true;
  if(mode.equals("cancel"))provider.blockOpen=true;
  if(mode.equals("pending-close"))provider.holdDescriptorClose=true;
  need(owner.read(REQUEST,ONE));
  if(mode.equals("cancel")||mode.equals("pending-close")){
   need(provider.entered.await(3,TimeUnit.SECONDS));need(job(owner,ONE).get("phase").equals("reading"));
   boolean refused=false;try{owner.retireCopies();}catch(IOException expected){refused=true;}need(refused);
   if(mode.equals("cancel"))owner.cancel(ONE);
   else{
    for(Map<String,Object> row:rows(owner.observation(),"files")){
     refused=false;try{owner.removeCopy((String)row.get("id"));}catch(IOException expected){refused=true;}need(refused);
    }
    provider.release.countDown();
   }
  }
  Map<String,Object> first=terminal(owner,ONE);
  if(mode.equals("failed-close")||mode.equals("cancel")){
   need(first.get("phase").equals("failed")&&first.get("original")==null);retire(owner);return;
  }
  need(first.get("phase").equals("complete")&&((Number)first.get("completedEpochMs")).longValue()>=((Number)first.get("startedEpochMs")).longValue());
  Map<String,Object> original=(Map<String,Object>)first.get("original");
  need(Arrays.equals(provider.body,Files.readAllBytes(Paths.get((String)original.get("path"))))&&provider.closes==1);
  System.out.println(json(owner.observation()));
  if(mode.equals("fresh")){
   Object firstDigest=original.get("sha256");
   original.put("sha256","foreign");need(!((Map<String,Object>)job(owner,ONE).get("original")).get("sha256").equals("foreign"));
   need(owner.read(REQUEST,ONE)&&provider.opens==1);provider.body=new byte[]{1,2,3,4,5};need(owner.read(REQUEST,TWO));
   Map<String,Object> second=terminal(owner,TWO);need(second.get("phase").equals("complete")&&provider.opens==2);
   need(!firstDigest.equals(((Map<String,Object>)second.get("original")).get("sha256")));
  }
  retire(owner);need(!owner.read(REQUEST,TWO));System.out.println(json(owner.observation()));
 }
}
'''


class SnapshotReadbackJobsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parent=ROOT/'build/snapshot-readback-jobs';parent.mkdir(parents=True,exist_ok=True)
        cls.temporary=tempfile.TemporaryDirectory(prefix='java-',dir=parent);cls.addClassCleanup(cls.temporary.cleanup)
        cls.stage=Path(cls.temporary.name);sources=[]
        for path,raw in STUBS.items():
            target=cls.stage/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(raw);sources.append(target)
        source=cls.stage/'SnapshotReadbackJobsHostTest.java';source.write_text(SOURCE);sources.append(source)
        sources.extend(ROOT/'android/common/snapshot/java/org/overte/snapshot'/name for name in ('SnapshotReadbackFiles.java','SnapshotExportReadbacks.java'))
        subprocess.run(['javac','--release','8','-d',str(cls.stage),*map(str,sources)],check=True,timeout=60)

    def case(self,name):
        with tempfile.TemporaryDirectory(prefix='provider-',dir=self.stage) as parent:
            result=subprocess.run(['java','-cp',str(self.stage),'org.overte.snapshot.SnapshotReadbackJobsHostTest',name,parent],
                check=True,timeout=12,capture_output=True,text=True)
            # Only the path boundary changes to this actual host-private root.
            # Job IDs, times, bytes, hashes and lifecycle are original Java data.
            with patch.object(contract,'ROOTS',{parent+'/'}):
                for line in result.stdout.splitlines():contract.source(dict(accepted=True,source=json.loads(line)))
    def test_new_job_reacquires_actual_provider_bytes_and_old_id_is_only_idempotent(self):self.case('fresh')
    def test_unknown_or_unpublished_request_cannot_open_a_provider(self):self.case('admission')
    def test_original_descriptor_close_failure_prevents_acquisition_success(self):self.case('failed-close')
    def test_cancelled_blocking_provider_retires_before_workers_are_reported_quiet(self):self.case('cancel')
    def test_pending_original_close_blocks_file_and_worker_retirement(self):self.case('pending-close')


if __name__=='__main__':unittest.main()
