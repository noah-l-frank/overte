"""SDK 26–28 normal DocumentsUI boundary for the public Snapshot host replay.

Android SDK/PackageManager/Binder are explicit synthetic IO seams. The original
Java DocumentsProvider owner runs in a separate process and owns actual files,
FD callbacks, original bytes, inode checks and removal. No scenario or feature
result enters this producer. Ordinary pointer/Back events are its only Save
trigger. This helper does not establish any Android/device acceptance.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
import json
from pathlib import Path
import select
import shlex
import subprocess
import threading
import time
from types import SimpleNamespace
import uuid
from xml.sax.saxutils import quoteattr

from adapters.normal_ui import NativeUI,NativeUIError
from overte_phone_snapshot_documents import PhoneSnapshotDocuments,PACKAGE
from overte_phone_snapshot_documents_ui import (SnapshotDocumentResolution,SnapshotDocumentContext,
    PhoneSnapshotDocumentsUI,RESOLVE)
from overte_phone_snapshot_system_ui import PRIMARY,LABEL

ROOT=Path(__file__).resolve().parents[4]
PICKER='com.android.documentsui/com.android.documentsui.picker.PickActivity'
PICKER_UID=10042
PHONE_UID=10001
PROVIDER_UID=10002
APK_SHA256='e'*64
MAX_BYTES=32*1024*1024

# Only this test wrapper is generated. All ownership/mutation decisions are made
# by the unchanged production fixture class, including one-send delete checks.
JAVA=r'''package org.overte.snapshot;
import java.io.*;
import java.nio.file.*;
import java.util.*;
public final class SnapshotDocumentsJourneyHost {
 static SnapshotDocumentsEvidence owner;
 static String text(String raw) { return new String(Base64.getDecoder().decode(raw),java.nio.charset.StandardCharsets.UTF_8); }
 static long stat(Path p,String key)throws Exception {return ((Number)Files.getAttribute(p,"unix:"+key,LinkOption.NOFOLLOW_LINKS)).longValue();}
 public static void main(String[] args)throws Exception {
  owner=new SnapshotDocumentsEvidence(Paths.get(args[0]));
  BufferedReader lines=new BufferedReader(new InputStreamReader(System.in,java.nio.charset.StandardCharsets.UTF_8));
  String line;
  while((line=lines.readLine())!=null){
   Map<String,Object> reply=new LinkedHashMap<>();
   try{
    String[] raw=line.split("\\t",-1);String[] a=new String[raw.length];for(int i=0;i<a.length;i++)a[i]=text(raw[i]);
    Object result=null;
    if(a[0].equals("arm"))owner.arm(a[1],a[2]);
    else if(a[0].equals("observe"))result=owner.observation(a[1],a[2],owner.retired());
    else if(a[0].equals("write")){
     String doc=owner.create(owner.rootId(),"image/png",a[1],Integer.parseInt(a[3]));
     String fd=owner.reserve(doc,"w",Integer.parseInt(a[4]));Path file=owner.path(fd);
     try(InputStream input=Files.newInputStream(Paths.get(a[2]),StandardOpenOption.READ,LinkOption.NOFOLLOW_LINKS);
         OutputStream output=Files.newOutputStream(file,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)){
      owner.opened(fd,stat(file,"dev"),stat(file,"ino"),stat(file,"uid"),stat(file,"nlink"),Files.isRegularFile(file,LinkOption.NOFOLLOW_LINKS));
      byte[] buffer=new byte[65536];int n;long count=0;while((n=input.read(buffer))!=-1){if(n<=0||(count+=n)>SnapshotDocumentsEvidence.MAX_BYTES)throw new IOException("Copy bound exceeded");output.write(buffer,0,n);}
     }
     if(!a[5].equals("pending"))owner.close(fd,a[5].equals("failed"));
     Map<String,Object> value=new LinkedHashMap<>();value.put("document",owner.metadata(doc));value.put("descriptor",fd);result=value;
    }
    else if(a[0].equals("close"))owner.close(a[1],Boolean.parseBoolean(a[2]));
    else if(a[0].equals("binary"))result=Base64.getEncoder().encodeToString(owner.original(a[1],a[2],a[3]));
    else if(a[0].equals("delete"))owner.delete(a[1]);
    else if(a[0].equals("retire"))owner.retire(a[1]);
    else throw new IOException("Closed helper operation required");
    reply.put("ok",true);reply.put("value",result);
   }catch(Exception failure){reply.put("ok",false);reply.put("error",failure.getClass().getSimpleName()+": "+failure.getMessage());}
   System.out.println(SnapshotDocumentsHostTest.json(reply));System.out.flush();
  }
 }
}
'''


class OriginalDocumentsProcess:
    """Actual original Java owner, with a bounded private command protocol.

    The capture pathname is accepted only by an internal writer hook after the
    target's independently qualified completed capture inventory is checked.
    SDK/provider controls expose IDs only. The process never accepts SHA/bytes
    claims or caller-selected output paths.
    """
    _compile_lock=threading.Lock()

    @classmethod
    def compile(cls,build):
        build=Path(build);build.mkdir(mode=0o700,parents=True,exist_ok=True)
        with cls._compile_lock:
            wrapper=build/'SnapshotDocumentsJourneyHost.java'
            production=ROOT/'tests/device/fixture/android-snapshot-receiver/java/org/overte/snapshot/SnapshotDocumentsEvidence.java'
            serializer=ROOT/'android/phone/tests/instrumentation/snapshot-export/org/overte/snapshot/SnapshotDocumentsHostTest.java'
            digest=hashlib.sha256(JAVA.encode()+production.read_bytes()+serializer.read_bytes()).hexdigest()
            stamp=build/'source.sha256'
            if not stamp.exists() or stamp.read_text()!=digest:
                wrapper.write_text(JAVA)
                subprocess.run(['javac','--release','8','-d',str(build),str(production),str(serializer),str(wrapper)],check=True,capture_output=True,text=True,timeout=30)
                stamp.write_text(digest)
        return build

    def __init__(self,parent,*,build=None):
        self.parent=Path(parent);self.parent.mkdir(mode=0o700,parents=True,exist_ok=False)
        build=self.compile(build or ROOT/'build/snapshot-documents-journey')
        self.lock=threading.Lock();self.calls=[]
        self.process=subprocess.Popen(['java','-cp',str(build),'org.overte.snapshot.SnapshotDocumentsJourneyHost',str(self.parent)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        pid=self.process.pid
        try:
            start=Path('/proc/'+str(pid)+'/stat').read_text().rsplit(')',1)[1].split()[19]
            self.identity_value=dict(package=PACKAGE,apkSha256=APK_SHA256,uid=PROVIDER_UID,processId=pid,processIdentity=str(pid)+':'+start)
        except Exception:
            self.close();raise
        self.run=self.arm=None;self.originals=[]

    def call(self,operation,*args):
        with self.lock:
            if self.process.poll() is not None:raise RuntimeError('Original Documents process exited')
            self.calls.append((operation,*args));wire='\t'.join(base64.b64encode(str(value).encode()).decode() for value in (operation,*args))+'\n'
            self.process.stdin.write(wire.encode());self.process.stdin.flush()
            if not select.select([self.process.stdout],[],[],5)[0]:raise TimeoutError('Original Documents owner deadline')
            raw=self.process.stdout.readline(2*MAX_BYTES)
            if not raw.endswith(b'\n') or len(raw)>2*MAX_BYTES:raise RuntimeError('Original Documents protocol bound')
            reply=json.loads(raw)
            if reply.get('ok') is not True:raise RuntimeError(reply.get('error','Original Documents owner failure'))
            return reply['value']

    def identity(self):
        if self.process.poll() is not None:raise RuntimeError('Original Documents process exited')
        return deepcopy(self.identity_value)

    def control(self,operation,run,arm=''):
        if operation=='arm':
            self.call('arm',run,arm);self.run,self.arm=run,arm
        elif operation=='retire' and run==self.run and not arm:self.call('retire',run)
        else:raise RuntimeError('Foreign Documents control')
        return {'accepted':True}  # Deliberately not an observation.

    def observe(self,run,nonce):
        row=self.call('observe',run,nonce)
        # Explicit host Android namespace and Binder/process metadata seams.
        # Filesystem identities, rows, clocks, FD states and bytes are unchanged.
        row['root']['path']='/data/user/0/'+PACKAGE+'/files/overte-snapshot-documents-'+run
        row.update(processId=self.process.pid,providerUid=PROVIDER_UID,providerPackage=PACKAGE)
        self.originals.append(deepcopy(row));return row

    def read(self,run,nonce):return json.dumps(self.observe(run,nonce)).encode()
    def binary(self,run,document,nonce):return base64.b64decode(self.call('binary',run,document,nonce),validate=True)
    def write_capture(self,name,path,creator,writer,close_mode='closed'):
        return self.call('write',name,str(path),creator,writer,close_mode)
    def close(self):
        if not hasattr(self,'process'):return
        if self.process.stdin:self.process.stdin.close()
        try:self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:self.process.terminate();self.process.wait(timeout=2)
        if self.process.stdout:self.process.stdout.close()
        if self.process.stderr:self.process.stderr.close()


class DocumentsJourneyBoundary:
    """Normal Save event producer around SnapshotTarget's raw input boundary."""
    def __init__(self,model):
        if model.sdk not in (26,27,28):raise ValueError('SDK26–28 Documents boundary required')
        self.model=model;self.provider=OriginalDocumentsProcess(model.root/'documents-provider')
        self.stage='recent';self.request=None;self.ignored=False;self.close_mode='closed';self.inputs=[];self.intents=[]
        self.pm_calls=[];self.picker=PICKER;self.picker_uid=PICKER_UID;self.phone_uid=PHONE_UID;self.writer_uid=PHONE_UID
        self.xml_filter=lambda raw:raw;self.os_rows={};self.pending_descriptor=None
        self._rpc=model.rpc;self._os_sdk=model.os_sdk;self._readback=model.readback_source
        self._now=model.now;self.batch_epoch=None
        # Source time remains actual Java System.currentTimeMillis; sample the
        # host clock independently, rather than copying timestamps from a DTO.
        model.now=self.now
        model.save_image=self.launch;model.os_sdk=self.os_sdk;model.readback_source=self.readback_source;model.rpc=self.rpc
        model.documents_boundary=self

    def now(self):
        return self.batch_epoch if self.batch_epoch is not None else time.time_ns()//1000000

    def tick(self):
        if self.batch_epoch is not None:self.batch_epoch=max(self.batch_epoch,time.time_ns()//1000000)

    def launch(self):
        if self.request is not None:raise RuntimeError('Document request already active')
        self.model.initialize_readbacks();self.model.readbacks['osDestinations']['snapshotOsDestinationsVersion']=2
        self.request=uuid.uuid4().hex;self.stage='recent';self.name=Path(self.model.current_path).name
        self.model.component=self.picker;self.model.app_state=3
        self.event('request-active');self.event('document-launched')

    def event(self,kind,value='',aux=''):
        self.tick();self.model.export_event(kind,value,aux,request=self.request,action='save')

    def node(self,**attrs):
        row=dict(package=self.picker.split('/')[0],enabled='true',displayed='true',clickable='true',bounds='[10,10][200,80]')|attrs
        return '<node '+' '.join(key+'='+quoteattr(str(value)) for key,value in row.items())+'/>'

    def xml(self):
        package=self.picker.split('/')[0]
        if self.stage=='recent':inner=self.node(**{'resource-id':'android:id/home'})
        elif self.stage=='drawer':inner=self.node(text=LABEL,**{'resource-id':package+':id/roots_list','bounds':'[10,100][300,170]'})
        else:inner=(self.node(text=LABEL,**{'resource-id':package+':id/toolbar_title','clickable':'false'})+
            self.node(text=self.name,**{'resource-id':'android:id/title','class':'android.widget.EditText','bounds':'[10,100][300,170]'})+
            self.node(text='Save',**{'resource-id':package+':id/action_menu_save','bounds':'[10,200][200,270]'}))
        return self.xml_filter('<hierarchy>'+inner+'</hierarchy>')

    def os_sdk(self,method,path,body):
        if self.model.component!=self.picker:return self._os_sdk(method,path,body)
        if path.endswith('/current_package'):return self.picker.split('/')[0]
        if path.endswith('/current_activity'):return self.picker.split('/')[1]
        if path.endswith('/source'):return self.xml()
        if method=='DELETE' and path.endswith('/actions'):return None
        if method=='POST' and path.endswith('/back'):
            self.inputs.append((method,path,deepcopy(body)))
            if not self.ignored:
                if self.stage=='drawer':self.stage='recent'
                else:
                    self.event('document-result','','4701:0');self.event('result-ready','cancelled');self.event('delivered','cancelled');self.finish()
            return {'accepted':True}
        if method=='POST' and path.endswith('/actions'):
            self.inputs.append((method,path,deepcopy(body)))
            streams=body.get('actions',[])
            if len(streams)!=1:raise AssertionError('Ordinary single pointer stream required')
            actions=streams[0].get('actions',[]);move=actions[0] if actions else {}
            if [item.get('type') for item in actions]!=['pointerMove','pointerDown','pause','pointerUp']:raise AssertionError('Original pointer sequence required')
            x,y=move.get('x'),move.get('y');bounds={'recent':(10,10,200,80),'drawer':(10,100,300,170),'root':(10,200,200,270)}[self.stage]
            if not isinstance(x,int) or not isinstance(y,int) or not(bounds[0]<x<bounds[2] and bounds[1]<y<bounds[3]):raise AssertionError('Pointer did not hit original control')
            if not self.ignored:
                if self.stage=='recent':self.stage='drawer'
                elif self.stage=='drawer':self.stage='root'
                else:self.save()
            return {'accepted':True}
        raise AssertionError('Unexpected DocumentsUI IO')

    def capture_path(self):
        path=self.model.producer.directory/Path(self.model.current_path).name
        rows=[row for row in self.model.producer.body['rows'] if row['path']==self.model.current_path]
        if len(rows)!=1:raise RuntimeError('Original native capture inventory required')
        row=rows[0];info=path.lstat();raw=path.read_bytes()
        if (not row['opened'] or not row['closed'] or row['phase']!='closed' or row['absent'] or info.st_nlink!=1 or
            path.is_symlink() or row['device']!=info.st_dev or row['inode']!=info.st_ino or row['bytes']!=len(raw) or
            row['sha256']!=hashlib.sha256(raw).hexdigest()):raise RuntimeError('Original native capture changed')
        return path

    def save(self):
        written=self.provider.write_capture(self.name,self.capture_path(),self.picker_uid,self.writer_uid,self.close_mode)
        doc=written['document'];self.pending_descriptor=written['descriptor'] if self.close_mode=='pending' else None
        self.event('document-result',doc['uri'],'4701:-1')
        # Failed/unclosed original write cannot produce a qualified native
        # readback, despite the OS acknowledging its ordinary Save input.
        if not doc['writeClosedEpochMs'] or self.close_mode=='failed':
            self.event('result-ready','error','The snapshot could not be saved.');self.event('delivered','error','The snapshot could not be saved.');self.finish();return
        raw=self.provider.binary(self.provider.run,doc['documentId'],uuid.uuid4().hex)
        self.tick();self.add_readback(doc,raw)
        self.event('destination-copied',doc['uri']);self.event('result-ready','success');self.event('delivered','success');self.finish()

    def finish(self):
        self.model.component=PRIMARY+'/'+PRIMARY+'.MainActivity';self.model.app_state=4;self.request=None

    def add_readback(self,doc,raw):
        request=self.request;copy=uuid.uuid4().hex;job=uuid.uuid4().hex
        directory=self.model.root/'snapshot-app/files'/('overte-snapshot-e2e-'+'e'*32);directory.mkdir(mode=0o700,exist_ok=True)
        path=directory/(copy+'.bin')
        with path.open('xb') as output:output.write(raw)
        path.chmod(0o600);actual=path.read_bytes();info=path.stat()
        original=dict(id=copy,request=request,path='/data/user/0/'+PRIMARY+'/files/'+directory.name+'/'+path.name,phase='complete',
            bytes=info.st_size,sha256=hashlib.sha256(actual).hexdigest(),capturedEpochMs=self.model.now())
        rb=self.model.readbacks
        rb['files'].append(original);rb['files'].sort(key=lambda row:row['id'])
        rb['jobs'].append(dict(id=job,request=request,phase='complete',startedEpochMs=doc['writeClosedEpochMs'],completedEpochMs=self.model.now(),original=deepcopy(original)));rb['jobs'].sort(key=lambda row:row['id'])
        rb['destinations'].append(dict(request=request,uri=doc['uri'],inserted=False,published=True));rb['destinations'].sort(key=lambda row:row['request'])
        identity={key:doc[key] for key in ('uri','displayName','device','inode','documentId','createUid','createdEpochMs')}
        identity.update(providerUid=PROVIDER_UID,ownerPackage=PACKAGE,providerPackage=PACKAGE,storage='documents',runId=doc['runId'],armId=doc['armId'],providerInstance=doc['providerInstance'])
        row=dict(request=request,inserted=False,phase='qualified',identity=identity,original={key:original[key] for key in ('bytes','sha256')},acquiredEpochMs=self.model.now(),deleteId='',deleteIssued=False,deleteCount=-1,checkedEpochMs=0,absent=False)
        rb['osDestinations']['rows'].append(row);rb['osDestinations']['rows'].sort(key=lambda row:row['request']);self.os_rows[request]=row

    def readback_source(self,request):
        row=self.os_rows.get(request.get('exportRequest'))
        if request['operation']=='remove-destination' and row is not None:
            if not row['deleteIssued']:
                row.update(deleteIssued=True,deleteId=request['resourceId'])
                self.provider.call('delete',row['identity']['documentId'])
            elif row['deleteId']!=request['resourceId']:raise RuntimeError('Foreign destination retirement ID')
            current=self.provider.observe(self.provider.run,uuid.uuid4().hex)
            original=next(doc for doc in current['documents'] if doc['documentId']==row['identity']['documentId'])
            row.update(phase='retired',deleteCount=original['deleteCalls'],absent=original['absent'],checkedEpochMs=original['checkedEpochMs'])
            self.tick();return self._readback(dict(request,operation='observe'))
        if request['operation']=='inspect-destinations':
            current=self.provider.observe(self.provider.run,uuid.uuid4().hex)
            for owned in self.os_rows.values():
                doc=next(doc for doc in current['documents'] if doc['documentId']==owned['identity']['documentId'])
                if owned['deleteIssued'] and not doc['absent']:raise RuntimeError('Original Documents absence lost')
            self.tick()
        return self._readback(request)

    def rpc(self,kind,value):
        with self.model.lock:
            previous=self.batch_epoch
            # One independently sampled synthetic native query batch. Java
            # observations keep their actual acquisition times unchanged.
            self.batch_epoch=time.time_ns()//1000000
            try:return self.dispatch(kind,value)
            finally:self.batch_epoch=previous

    def dispatch(self,kind,value):
        with self.model.lock:
            if kind=='documents-scope':
                state=self._rpc('snapshot-state',None)
                # A single SDK query transports the originally acquired status
                # and session together. Context still reads before/after and
                # current component independently; it never adopts an owner.
                return dict(binding=self.model.rpc('binding',None),foreground=state['foreground'],running=True,
                    appState=4 if state['foreground'] else 3,component=state['component'])
            if kind=='documents-pm':
                args=tuple(value);self.pm_calls.append(args)
                if args==RESOLVE:return self.picker
                if args==('cmd','package','list','packages','-U','--user','0',self.picker.split('/')[0]):return 'package:'+self.picker.split('/')[0]+' uid:'+str(self.picker_uid)
                raise RuntimeError('Unapproved PackageManager query')
            if kind=='documents-installed':return self.provider.identity()
            if kind=='documents-control':return self.provider.control(*value)
            if kind=='documents-observe':return self.provider.observe(*value)
            if kind=='documents-binary':return base64.b64encode(self.provider.binary(*value)).decode()
            if kind=='documents-phone-uid':return str(self.phone_uid)
            return self._rpc(kind,value)

    def close(self):self.provider.close()


def install_proxy_documents(proxy_type):
    """Install on the common proxy class before forking its independent actor."""
    if proxy_type.__dict__.get('_documents_journey_installed'):return
    original_context=proxy_type._snapshot_system_context
    def context(self,selector,binding,resolution,authority):
        if 'snapshotDocumentResolutionVersion' not in resolution:return original_context(self,selector,binding,resolution,authority)
        def status():
            row=self.call('documents-scope',None);row.pop('component');return row
        return SnapshotDocumentContext(binding,resolution,status,lambda:self.call('documents-scope',None)['component'],authority)
    def resolution(self,selector):
        class PM:
            def execute(_self,args,*,target,timeout):
                if args[0]!='shell' or timeout!=5:raise RuntimeError('Unexpected resolution transport')
                return self.call('documents-pm',shlex.split(args[1]))
        return SnapshotDocumentResolution(PM(),'synthetic-package-manager',lambda:True,self.clock_ms)
    def ui(self,selector,binding,resolution,intent,authority):
        scope=self._snapshot_system_context(selector,binding,resolution,authority)
        client=SimpleNamespace(call=lambda method,path,body=None:self.call('os-sdk',[method,path,body]))
        return PhoneSnapshotDocumentsUI(NativeUI(client,'synthetic',scope.guard),intent,self.clock_ms,resolution['component'])
    def documents(self,selector,run,arm,sha,binding_context,resolution,authority,*,read_only=True,binding=None):
        scope=self._snapshot_system_context(selector,binding_context,resolution,authority)
        def identity():
            actual=self.call('documents-installed',None)
            if actual['apkSha256']!=sha:raise RuntimeError('Original installed provider APK differs')
            return actual
        class Transport:
            def identity(_self):scope.guard();return identity()
            def read(_self,r,n):scope.guard();return json.dumps(self.call('documents-observe',[r,n])).encode()
            def binary(_self,*args):scope.guard();return base64.b64decode(self.call('documents-binary',args),validate=True)
            def control(_self,*args):
                if read_only:raise RuntimeError('Read-only Documents control')
                scope.guard();before=identity();result=self.call('documents-control',args)
                if identity()!=before:raise RuntimeError('Original provider identity changed')
                return result
        return PhoneSnapshotDocuments(Transport(),self.clock_ms,scope.guard,run,arm,read_only=read_only,binding=binding)
    def system_documents(self,*args,**kwargs):return documents(self,*args,read_only=True,**kwargs)
    def uid(self,selector,binding,resolution,authority):
        scope=self._snapshot_system_context(selector,binding,resolution,authority);scope.guard()
        requested=self.clock_ms();raw=self.call('documents-phone-uid',None);scope.guard();captured=self.clock_ms()
        if not raw.isdecimal() or not 0<int(raw)<=9999999999 or not 0<=captured-requested<=1500:raise RuntimeError('Original Phone UID unavailable')
        return dict(snapshotPhoneUidVersion=1,uid=int(raw),requestedEpochMs=requested,capturedEpochMs=captured)
    proxy_type._snapshot_system_context=context;proxy_type._snapshot_document_resolution=resolution;proxy_type._snapshot_document_ui=ui
    proxy_type._snapshot_documents=documents;proxy_type._snapshot_system_documents=system_documents;proxy_type._snapshot_phone_uid=uid
    proxy_type._documents_journey_installed=True


def install_documents(model,proxy=None):
    """Attach SDK26–28 only; callers close the actual Java process explicitly."""
    boundary=DocumentsJourneyBoundary(model)
    if proxy is not None:install_proxy_documents(proxy if isinstance(proxy,type) else type(proxy))
    return boundary
