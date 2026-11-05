# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
"""One existing Pico Gesture/Session envelope into a declared World pointer consumer.

No focus setter/Phone coordinates/device claim. Originals and all failed work
stay in the SAME cold Parent resource bill. Only this Session's two paths exist.
"""
from copy import deepcopy
import base64,hashlib,json,math,os,stat,time,uuid
from pathlib import Path
from adapters.native_feature_observation import need
from adapters.native_fd_owner import OriginalDescriptor,require_directory
from adapters.android.input_geometry import _axis,_multiply
from adapters.pico4.world_browser_ray import rotate
from adapters.pico4.world_current_gesture import bind_current_gesture,calibration
from adapters.pico4.world_current_focus_parent import focus_matches
from openxr_input.adapter_session import PicoOpenXrAdapterSession,PROFILE_PATH
from openxr_input.android_transport import AndroidOpenXrTransport,validate_native_status,BUILD_MARKER,CONSUMER,PROFILE_ID,PROFILE_SHA256
from adapters.pico4.lifecycle_process_file import LifecycleProcessFile
from adapters.normal_feature_state import PrivateFeatureState
from openxr_input.controller_protocol import compile_envelope,PrototypeOpenXrInputConsumer

PART=65536
class ControllerSession(PicoOpenXrAdapterSession):
 def __init__(self,owner):
  need(type(owner) is WorldControllerFocus1);self.originals=owner
  need(PROFILE_PATH.stat().st_size==1173) # Exact pinned original configuration, before constructor parser.
  super().__init__(owner.transport,'world-controller-host',owner.path)
 def _load(self):
  owner=self.originals
  try:
   before=owner.capture(self.state_path,absent=True);result=super()._load()
   owner.check_current(self.state_path,before);return result
  except BaseException as error:owner.fail(error);raise
 def _save_path(self,path,value):
  need(path==self.state_path);super()._save_path(path,value)
  row=self.originals.capture(path,written=True)
  need(row['raw']==(json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode())

class ControllerTransport(AndroidOpenXrTransport):
 """Original transport stage/compile/profile/grant algorithm, declared SDK files.

 No actual ADB executable, discovery, service or Native call is constructed.
 The cold subclass implements only the exact modeled SDK I/O seam.
 """
 def __init__(self,owner):
  self.owner=owner;self.envelopes=[];self.status=None;self.profile=None;self.files=[]
 def require_exclusive_target(self):
  need(self.owner.stage.failure is None and not self.envelopes)
 def literal(self,role,raw):
  need(type(role) is str and type(raw) is bytes and len(raw)<=8192 and len(self.files)<3)
  row=dict(role=role,raw=raw,owner=None,payload=None);self.files.append(row)
  file=object.__new__(LifecycleProcessFile);row['owner']=file
  LifecycleProcessFile.__init__(file,PrivateFeatureState(self.owner.path/(role+'.original.json')))
  row['payload']=dict(worldControllerLiteralVersion=1,role=role,rawBase64=base64.b64encode(raw).decode('ascii'))
  file.write(row['payload'],None);file.guard()
  return row
 def _atomic_write(self,name,payload):
  role={'commands.json':'commands','grant.json':'grant'}[name]
  row=self.literal(role,payload) # Actual retained file/OFD before model parser.
  if role=='grant':
   command=next(v for v in self.files if v['role']=='commands');command['owner'].guard();row['owner'].guard()
   envelope=json.loads(command['raw']);grant=json.loads(row['raw'])
   need(grant['sessionNonce']==envelope['sessionNonce'] and grant['sequence']==envelope['sequence']
    and grant['buildMarker']==BUILD_MARKER and grant['bindingProfileSha256']==PROFILE_SHA256
    and grant['expiresEpochMs']>=time.time_ns()//1000000)
   self.envelopes.append(envelope);self.owner.consume(envelope,self.profile)
   sequence=envelope['sequence']
   self.status=dict(schemaVersion=1,buildMarker=BUILD_MARKER,consumer=CONSUMER,profileId=PROFILE_ID,
    bindingProfileSha256=PROFILE_SHA256,enabled=True,acceptedSequence=sequence,acceptedNonce=envelope['sessionNonce'],
    state='active',activeCommandId=envelope['commands'][0]['id'],detail='declared-controller-model',updatedEpochMs=time.time_ns()//1000000,
    viewAppliedSequence=0,viewAppliedYawDegrees=0.,viewAppliedPitchDegrees=0.,vectorAppliedSequence=0,
    leftThumbstickAppliedX=0.,leftThumbstickAppliedY=0.,booleanAppliedSequence=0,leftSecondaryApplied=False,rightSecondaryApplied=False)
 def stage(self,envelope,profile,*,before_publish=None):
  need(not self.envelopes and self.profile is None);self.profile=profile
  return super().stage(envelope,profile,before_publish=before_publish)
 def read_status(self,*,expected_nonce=None,expected_sequence=None):
  need(self.status is not None and len(self.envelopes)==1)
  raw=json.dumps(self.status,sort_keys=True,separators=(',',':')).encode()
  row=self.literal('status',raw)
  packet=json.loads(row['raw'])
  result=validate_native_status(packet,expected_nonce=expected_nonce,expected_sequence=expected_sequence)
  result['acceptedNonce']='[redacted]';return result

class WorldControllerFocus1:
 def __init__(self,stage):
  self.stage=stage;self.path=stage.root.parent/('world-controller-'+uuid.uuid4().hex)
  self.rows=[];self.lock_owner=None;self.session=None;self.transport=None
  self.intent=self.stream=self.publication=self.calibration=self.receipt=self.consumer=self.pointer=None;self.gesture=None
  self.focus_nonce=None;self.failure=None;self.done=False;self.closed=False
  need(stage.controller is None and stage.host_selection.controller_focus and stage.event_owner is None
   and stage.compound is None and stage.failure is None and stage.node is not None)
  stage.controller=stage._controller=self;stage.controller_work=4*PART # Existing16M, ADDITIVE.
  stage.census() # Before directory/profile/Session allocations.
  self.path.mkdir(mode=0o700)
  self.directory=OriginalDescriptor(self.path,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
  self.transport=ControllerTransport(self);self.session=ControllerSession(self)
  self.session.begin(stage.model.process)
  self.lock_owner=OriginalDescriptor(self.session.lock_path,os.O_RDONLY|os.O_CLOEXEC)
  self.physical_bill();stage.census()
 def fail(self,error):
  if self.failure is None:self.failure=(error,error.__traceback__)
  self.stage.fail(error)
 def capture(self,path,*,absent=False,written=False):
  need(self.session is not None and path==self.session.state_path)
  require_directory(self.directory,self.path)
  try:info=path.lstat()
  except FileNotFoundError:
   need(absent and not self.rows);return None
  if self.rows and not written:self.check_current(path,self.rows[-1])
  need(stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode)==0o600 and info.st_uid==os.geteuid() and info.st_nlink==1 and info.st_size<=8192)
  owner=OriginalDescriptor(path,os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW)
  row=dict(owner=owner,raw=None,stamp=None,path=str(path));self.rows.append(row)
  need(len(self.rows)<=4);owner.require(owner.fd);before=os.fstat(owner.fd)
  row['raw']=os.pread(owner.fd,8193,0);owner.require(owner.fd);after=os.fstat(owner.fd)
  signature=lambda s:(s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
  row['stamp']=signature(after)
  need(signature(before)==signature(after)==signature(path.lstat()) and len(row['raw'])==after.st_size<=8192)
  return row
 def check_current(self,path,row):
  if row is None:need(not path.exists());return
  row['owner'].require(row['owner'].fd)
  s=path.lstat();signature=(s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
  need(signature==row['stamp'] and os.pread(row['owner'].fd,8193,0)==row['raw'])
  row['owner'].require(row['owner'].fd)
 def physical_bill(self):
  if not hasattr(self,'directory'):return 0,0
  require_directory(self.directory,self.path)
  if self.session is not None:
   expected={self.session.state_path.name,self.session.lock_path.name}
   if self.transport is not None:expected.update(row['owner'].path.name for row in self.transport.files if row['owner'] is not None and getattr(row['owner'],'file',None) is not None)
   need(set(os.listdir(self.path))==expected)
  total=0
  for row in self.rows:
   owner=row['owner'];owner.require(owner.fd)
   need(os.pread(owner.fd,8193,0)==row['raw']);owner.require(owner.fd);total+=len(row['raw'])
  if self.rows:self.check_current(self.session.state_path,self.rows[-1])
  if self.lock_owner is not None:self.lock_owner.require(self.lock_owner.fd);need(os.fstat(self.lock_owner.fd).st_size==0)
  if self.transport is not None:
   for row in self.transport.files:
    row['owner'].guard();total+=len(row['owner'].raw)
  return total,len(self.rows)+1+(len(self.transport.files) if self.transport is not None else 0)
 def live_size(self,dto):
  v=16384
  for name in ('intent','stream','publication','calibration','receipt','pointer','consumer','focus_nonce'):
   v+=dto(getattr(self,name,None))
  if self.gesture is not None:
   for name in ('envelope','_calibration','_calibration_seal'):
    if hasattr(self.gesture,name):v+=dto(getattr(self.gesture,name))
  if self.transport is not None:
   v+=dto(self.transport.envelopes)+dto(self.transport.status)
   for row in self.transport.files:v+=dto(row['raw'])+dto(row['payload'])+len(row['owner'].raw or b'')+dto(str(row['owner'].path))+2048
  if self.session is not None:v+=dto(self.session.profile)+dto(str(self.session.state_path))+dto(str(self.session.lock_path))
  for row in self.rows:v+=dto(row['raw'])+dto(row['stamp'])+dto(row['path'])+2048
  return v
 def remember_intent(self,value):need(self.intent is None);self.intent=deepcopy(value);self.stage.census()
 def remember_stream(self,value):need(self.stream is None);self.stream=deepcopy(value);self.stage.census()
 def before_publish(self,value):need(value==self.stream and self.stage.failure is None);self.stage.census()
 def consume(self,envelope,profile):
  compiled=compile_envelope(envelope,profile);consumer=PrototypeOpenXrInputConsumer(compiled)
  self.consumer=compiled # Full primitive plan held/accounted, not verdict authority.
  key=profile['controls']['scalars']['right.trigger'];posekey=profile['controls']['poses']['right.grip'];previous=0.;hits=[]
  rotation=_multiply(_axis([0,0,1],math.pi/2),_axis([1,0,0],math.pi/4));inverse=[-rotation[0],-rotation[1],-rotation[2],rotation[3]]
  correction=_multiply(_axis([1,0,0],-math.pi/8),_multiply(inverse,_multiply(_axis([0,1,0],math.pi),_axis([1,0,0],math.pi/2))))
  for event in compiled['events']:
   consumer.sync_actions(event['atMs']);scalar=consumer.query('float',key);pose=consumer.query('pose',posekey)
   value=scalar['currentState'] if scalar and scalar['isActive'] else 0.
   if value>=.95 and previous<.95 and pose and pose['isActive']:
    actual=pose['currentState'];origin=actual['positionMeters'];direction=rotate(_multiply(actual['orientation'],correction),[0,1,0])
    need(abs(direction[2])>1e-9);distance=(-2.5-origin[2])/direction[2];point=[origin[i]+distance*direction[i] for i in range(3)]
    x=((point[0]/1.8)+.5)*640;y=(.5-(point[1]-1.4)/2.2)*480
    hits.append(dict(x=x,y=y,forward=distance>0,entityId=self.stage.host_selection.context.entity))
   previous=value
  need(len(hits)==1);self.pointer=hits[0]
  self.stage.node.pointer(envelope,self.pointer)
  duration=compiled['watchdogDeadlineMs']/1000
  need(2<=duration<=3);time.sleep(duration) # Real bounded pulse wait, original5s includes it.
 def perform(self):
  # The original complete worker really returns before its transient workspace
  # ends. Escaped calibration/receipt/Session/Node data remain independently P/S.
  result=self._perform()
  self.stage.controller_work=0;self.stage.census()
  return result
 def _perform(self):
  need(not self.done and self.calibration is None and self.failure is None)
  s=self.stage;c=s.host_selection.context
  # Constructor's original Session/profile stack has really returned. During
  # source reads only serial paired/full-byte guards run under existing WINDOW.
  s.controller_work=0
  try:
   # Original attempt includes calibration, publication and real2s pulse.
   started=time.monotonic();requested=s.native_epoch_ms()
   s.focus.read(c.run,c.fixture_url,c.owner,'measure-current-ray','text')
   self.calibration=s.focus.original();pose,epochs,_=calibration(self.calibration)
   # Actual existing binder and actual Session.stage, unchanged Gesture code.
   s.controller_work=32*PART;s.census()
   owner=bind_current_gesture(self,'world-controller-host',s.focus,self.remember_intent,self.remember_stream,
    self.before_publish,self.admission,started=started,requested=requested)
   self.gesture=owner;self.receipt=owner.publish();self.publication=self.receipt['publication']
   # Original Gesture/Session/ACK/copy frames actually returned; every escaped
   # byte/DTO/old OFD remains separately in live_size/physical_bill.
   s.controller_work=0;s.census()
   s.archive_controller_calibration()
   focus=s.focus.read(c.run,c.fixture_url,c.owner,'observe-current-focus','text')
   self.done=focus_matches(self.calibration,s.focus.original())
   if self.done:self.focus_nonce=s.focus.last_request['commandId']
   # No publication/ACK can supply a focused result. Caller must refuse IME.
   return self.done
  except BaseException as error:self.fail(error);raise
 def admission(self):self.stage.census()
 def require_pico_session_identity(self,target):need(target=='world-controller-host');return self.stage.model.process
 def pico_input_session(self,target):need(target=='world-controller-host');return self.session
 def close_host(self):
  values=[]
  for row in self.rows:values.append(row['owner'].close())
  if self.transport is not None:
   for row in self.transport.files:values.append(row['owner'].close_host())
  if self.lock_owner is not None:values.append(self.lock_owner.close())
  if hasattr(self,'directory'):values.append(self.directory.close())
  self.closed=True;return values

VERSION=1
