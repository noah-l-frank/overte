# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
"""Alive task-owned HOST DOM worker; original literals precede every JSON parser.

No network/browser/Qt/device; no expected-value setter/current dead-child result.
Node evaluates unchanged production editor.js against the existing test Input
semantics. The same live Input owns birth, one IME and later fresh snapshots.
"""
import base64,json,os,select,stat,subprocess,time,uuid
from pathlib import Path
from adapters.native_feature_observation import decode,exact,fresh,integer,need
from adapters.native_fd_owner import OriginalDescriptor
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.lifecycle_process_file import LifecycleProcessFile
from adapters.script_journey.history import canonical

WIRE=8192
NODE_WORK=24*65536

class WorldProductDom1:
 def __init__(self,stage,script,editor):
  self.stage=stage;self.scope=stage.host_selection.context
  self.process=None;self.input=self.output=self.error=None;self.rows=[];self.last=self.ready=None
  self.failure=None;self.retention_errors=[];self.sequence=0;self.pending=None;self.buffer=b'';self.stderr=b'';self.start=None;self.closed=False
  need(stage.model_credit>=NODE_WORK and isinstance(script,Path) and isinstance(editor,Path))
  self.script,self.editor=script,editor
  self.executable=Path('/usr/bin/node').resolve(strict=True)
  try:
   self.process=subprocess.Popen(['/usr/bin/node',str(script),str(editor)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0,close_fds=True)
   self._process=self.process;self.pid=self._pid=self.process.pid;self.start=self._start=self.process_stamp()
   for name,stream,flags in (('input',self.process.stdin,os.O_WRONLY),('output',self.process.stdout,os.O_RDONLY),('error',self.process.stderr,os.O_RDONLY)):
    owner=object.__new__(OriginalDescriptor);setattr(self,name,owner)
    OriginalDescriptor.__init__(owner,'/proc/self/fd/'+str(stream.fileno()),flags|os.O_NONBLOCK|os.O_CLOEXEC)
    need(stat.S_ISFIFO(os.fstat(owner.fd).st_mode) and owner.node==(os.fstat(stream.fileno()).st_dev,os.fstat(stream.fileno()).st_ino))
    setattr(self,'_'+name,owner)
    stream.close()  # Newly created builtin FD; only paired owners survive birth.
   c=self.scope
   self.ready=self.query(dict(operation='init',commandId=uuid.uuid4().hex,runId=c.run,ownerToken=c.owner,domInstance=c.dom,responseId=c.response,url=c.url,cancelBeforeInput=stage.host_selection.cancel_dom_beforeinput,controllerFocus=stage.host_selection.controller_focus,ignorePointer=stage.host_selection.controller_no_effect,entityId=c.entity))
   exact(self.ready,{'ready','editor'});need(self.ready['ready'] is True and self.ready['editor']['active'] is (not stage.host_selection.controller_focus)
    and (stage.host_selection.controller_focus or (self.ready['editor']['text']=='' and self.ready['editor']['cursor']==self.ready['editor']['anchor']==0)))
  except BaseException as error:self.fail(error);raise
 def fail(self,error):
  if self.failure is None:self.failure=(error,error.__traceback__)
  self.stage.fail(error)
 def process_stamp(self):
  with open('/proc/'+str(self.process.pid)+'/stat','rb') as stream:raw=stream.read(4097)
  need(len(raw)<=4096);tail=raw.rsplit(b')',1)[1].split();need(int(tail[1])==os.getpid())
  return tail[19]
 def guard(self):
  self.stage.lock.assert_held()
  need(not self.closed and self.failure is None and self.process is self._process and self.process.poll() is None
   and self.pid is self._pid and self.start is self._start
   and self.process.pid==self.pid and self.process_stamp()==self.start
   and os.readlink('/proc/'+str(self.pid)+'/exe')==str(self.executable)
   and self.scope is self.stage.host_selection.context
   and self.input is self._input and self.output is self._output and self.error is self._error)
  for owner in (self.input,self.output,self.error):owner.require(owner.fd)
  self.stage.identity()
 def prepare_literal(self,call):
  self.stage.node_before_literal(self)
  row=dict(call=call,raw=b'',stderr=b'',owner=None,payload=None,confirmed=False)
  self.rows.append(row)
  owner=object.__new__(LifecycleProcessFile);row['owner']=owner
  path=self.stage.root/('pico-world-host-node-%03d.json'%(len(self.rows)-1))
  try:path.lstat()
  except FileNotFoundError:pass
  else:need(False)
  LifecycleProcessFile.__init__(owner,PrivateFeatureState(path));need(owner.file is None)
  return row
 def capture(self,row,raw,stderr):
  # Existing original owner was registered/preheld BEFORE acquisition.
  row['raw'],row['stderr']=raw,stderr
  row['payload']=dict(worldHostNodeLiteralVersion=1,commandId=row['call']['commandId'],rawBase64=base64.b64encode(raw).decode('ascii'),stderrBase64=base64.b64encode(stderr).decode('ascii'))
  owner=row['owner'];owner.write(row['payload'],None);owner.guard();row['confirmed']=True
 def query(self,call):
  need(self.pending is None);self.pending=call
  started=time.monotonic();epoch=time.time_ns()//1000000;row=None;raw=b'';stderr=b''
  try:
   self.stage.node_before_query(self);self.guard();wire=canonical(call)+b'\n';need(len(wire)<=WIRE)
   row=self.prepare_literal(call)
   offset=0
   while offset<len(wire):
    self.guard();need(time.monotonic()-started<=1.5)
    _,w,_=select.select([],[self.input.fd],[],.05)
    if w:offset+=os.write(self.input.fd,wire[offset:])
   raw=self.buffer;stderr=b''
   while b'\n' not in raw:
    self.guard();need(time.monotonic()-started<=1.5)
    reads,_,_=select.select([self.output.fd,self.error.fd],[],[],.05)
    for fd in reads:
     owner=self.output if fd==self.output.fd else self.error;owner.require(fd)
     limit=WIRE+1-len(raw) if fd==self.output.fd else 4097-len(stderr)
     chunk=os.read(fd,limit);owner.require(fd);need(chunk)
     if fd==self.output.fd:raw+=chunk
     else:stderr+=chunk
    need(len(raw)<=WIRE and len(stderr)<=4096)
   line,tail=raw.split(b'\n',1);self.buffer=tail
   self.capture(row,line+b'\n',stderr)  # ACTUAL immutable literal first.
   self.stage.node_literal_ready(self)
   need(len(line)+1<=WIRE and not tail and not stderr)
   self.stage.node_before_parse(self,row)
   packet=decode(line.decode('utf-8'));exact(packet,{'worldHostProductDomVersion','commandId','processId','sequence','capturedEpochMs','status','value'})
   need(type(packet['worldHostProductDomVersion']) is int and packet['worldHostProductDomVersion']==1
    and type(packet['commandId']) is str and packet['commandId']==call['commandId']
    and type(packet['processId']) is int and packet['processId']==self.pid and integer(packet['sequence'],self.sequence+1)
    and packet['status']=='ready');fresh(packet['capturedEpochMs'],time.time_ns()//1000000)
   self.guard();need(time.monotonic()-started<=1.5);fresh(epoch,time.time_ns()//1000000)
   self.sequence=packet['sequence'];self.last=packet;self.pending=None;return packet['value']
  except BaseException as error:
   self.fail(error)  # ORIGINAL error/TB BEFORE any additional IO/refusal.
   if row is not None and not row['confirmed']:
    try:self.capture(row,raw,stderr)
    except BaseException as retained:self.retention_errors.append((retained,retained.__traceback__))
   raise
 def snapshot(self,nonce):
  c=self.scope;return self.query(dict(operation='snapshot',commandId=nonce,runId=c.run,ownerToken=c.owner))
 def ime(self,nonce,editor,product):
  c=self.scope;return self.query(dict(operation='ime',commandId=nonce,runId=c.run,ownerToken=c.owner,
   observedText=editor['text'],cursor=editor['cursor'],anchor=editor['anchor'],product=product))
 def close_host(self):
  # Physical closure only; failure never becomes semantic DOM/Native retirement.
  results=[]
  if self.process is not None:
   try:
    if self.process.poll() is None:self.process.terminate()
    self.process.wait(timeout=2);results.append(self.process.poll() is not None)
   except BaseException as error:
    if self.failure is None:self.failure=(error,error.__traceback__)
    results.append(False)
  for owner in (self.input,self.output,self.error):
   if owner is not None and hasattr(owner,'fd'):results.append(owner.close())
  if self.process is not None:
   for stream in (self.process.stdin,self.process.stdout,self.process.stderr):
    if stream is not None and not stream.closed:stream.close()
  for row in self.rows:
   owner=row['owner']
   if owner is not None and hasattr(owner,'parent'):results.append(owner.close_host())
  self.closed=all(results);return results

 def pointer(self,envelope,pointer):
  need(self.stage.host_selection.controller_focus and type(envelope) is dict
   and self.stage.controller is not None and envelope==self.stage.controller.stream)
  c=self.scope
  with self.stage.lock.held():
   result=self.query(dict(operation='controller-pointer',commandId=uuid.uuid4().hex,runId=c.run,ownerToken=c.owner,pointer=pointer,sessionRef=dict(sessionNonce=envelope['sessionNonce'],sequence=envelope['sequence'],inputId=envelope['commands'][0]['id'])))
  need(result['pointerDispatched'] is True)
  return result

VERSION=1
