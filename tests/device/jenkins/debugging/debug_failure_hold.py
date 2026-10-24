"""Explicit run-bound debug preservation; never a PASS or a device operation.

Only the reviewed focused bootstrap installs these hooks. Original source,
identity/capability checks and normal runner defaults stay untouched.
"""
import hashlib,io,json,os,re,signal,stat,subprocess,sys,time,uuid
from pathlib import Path
from types import SimpleNamespace
import xml.etree.ElementTree as ET

class DebugCleanupRequested(BaseException):pass
class DebugRejected(ValueError):pass

def need(ok,code):
 if not ok:raise DebugRejected(code)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def private_read(path,limit=16*1024*1024):
 path=Path(path);need(path.resolve()==path.absolute(),'DEBUG_INPUT_ALIAS')
 fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
 with os.fdopen(fd,'rb')as f:
  a=os.fstat(f.fileno());need(stat.S_ISREG(a.st_mode)and a.st_uid==os.geteuid()and a.st_nlink==1 and stat.S_IMODE(a.st_mode)==0o600 and a.st_size<=limit,'DEBUG_PRIVATE_INPUT_REQUIRED');raw=f.read(limit+1);b=os.fstat(f.fileno())
 need((a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns,a.st_ctime_ns)==(b.st_dev,b.st_ino,b.st_size,b.st_mtime_ns,b.st_ctime_ns)==(path.lstat().st_dev,path.lstat().st_ino,path.lstat().st_size,path.lstat().st_mtime_ns,path.lstat().st_ctime_ns)and len(raw)<=limit,'DEBUG_INPUT_CHANGED');return raw

def atomic(path,value):
 path=Path(path);need(path.parent.resolve()==path.parent.absolute(),'DEBUG_OUTPUT_ALIAS')
 tmp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
 raw=(json.dumps(value,sort_keys=True,indent=2)+'\n').encode()
 with os.fdopen(os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb')as f:f.write(raw);f.flush();os.fsync(f.fileno())
 if path.exists():need(stat.S_ISREG(path.lstat().st_mode)and path.lstat().st_uid==os.geteuid()and path.lstat().st_nlink==1 and not path.is_symlink(),'DEBUG_OUTPUT_REPLACED')
 os.replace(tmp,path);return raw

def identity(pid):
 try:
  fd=os.open('/proc/'+str(pid),os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
  try:
   raw=Path('/proc/self/fd/'+str(fd)+'/stat').read_text();parts=raw[raw.rfind(')')+2:].split();uid=os.fstat(fd).st_uid
   return dict(pid=pid,birth=parts[19],state=parts[0],ppid=int(parts[1]),pgid=int(parts[2]),sid=int(parts[3]),uid=uid)
  finally:os.close(fd)
 except(FileNotFoundError,ProcessLookupError):return None

def same_owner(a,b):return a is not None and b is not None and all(a[k]==b[k]for k in ('pid','birth','uid','pgid','sid'))and b['state']not in('Z','X')

class Policy:
 def __init__(self,config,config_sha,*,sleeper=time.sleep):
  self.path=Path(config);raw=private_read(self.path);need(sha(raw)==config_sha,'DEBUG_CONFIG_HASH_CHANGED');self.config=json.loads(raw);c=self.config
  need(c.get('schemaVersion')==1 and c.get('enabled')is True and re.fullmatch('[a-z][a-z0-9-]{7,79}',c.get('runId',''))and re.fullmatch('[0-9a-f]{32}',c.get('nonce','')),'DEBUG_EXPLICIT_CONFIG_REQUIRED')
  self.context=config_sha;self.root=Path(c['privateRoot']);self.stage=Path(c['publicStage']);self.source=Path(c['sourceRoot']);self.nonce=c['nonce'];self.sleeper=sleeper
  for p in(self.root,self.stage,self.source):need(p.is_absolute()and p.resolve(strict=False)==p.absolute(),'DEBUG_CONTEXT_PATH_ALIAS')
  need(not self.root.is_relative_to(self.source)and not self.stage.is_relative_to(self.source)and self.root!=self.stage and not self.stage.is_relative_to(self.root),'DEBUG_DISJOINT_OUTPUT_REQUIRED')
  self.root.mkdir(mode=0o700,parents=True,exist_ok=True);s=self.root.lstat();need(s.st_uid==os.geteuid()and stat.S_IMODE(s.st_mode)==0o700,'DEBUG_ROOT_PRIVATE_REQUIRED');self.root_pin=(s.st_dev,s.st_ino)
  context=self.root/'CONTEXT.private.json'
  if context.exists():need(json.loads(private_read(context))=={'contextSha256':self.context,'runId':c['runId'],'nonce':self.nonce},'DEBUG_CONTEXT_FOREIGN')
  else:atomic(context,{'contextSha256':self.context,'runId':c['runId'],'nonce':self.nonce})
  self.events=self.root/'events.private.jsonl';self.sequence=0;self.active=None;self.published=False;self.console_offset=0;self.follower=None;self.inventory={};self.codes=set();self.capture_metadata=[];self.cleanup_authorized=False
 def root_guard(self):
  s=self.root.lstat();need((s.st_dev,s.st_ino)==self.root_pin and stat.S_ISDIR(s.st_mode)and s.st_uid==os.geteuid()and stat.S_IMODE(s.st_mode)==0o700,'DEBUG_ROOT_CHANGED')
 def source_guard(self):
  import ast
  self.root_guard();inventory_path=Path(self.config['inventory']['path']);raw=inventory_path.read_bytes();need(sha(raw)==self.config['inventory']['sha256'],'DEBUG_INVENTORY_CHANGED');inventory=json.loads(raw)
  need(type(inventory)is dict and inventory,'DEBUG_INVENTORY_REQUIRED');self.inventory=inventory;self.codes=set()
  for name,digest in inventory.items():
   p=self.source/name;need(not Path(name).is_absolute()and '..'not in Path(name).parts and p.resolve()==p and p.is_file()and sha(p.read_bytes())==digest,'DEBUG_SOURCE_CHANGED')
  for name in self.config.get('traceSourceFiles',[]):
   need(name in inventory,'DEBUG_TRACE_SOURCE_UNPINNED')
   for node in ast.walk(ast.parse((self.source/name).read_text())):
    if isinstance(node,ast.Constant)and type(node.value)is str and re.fullmatch('(PHONE|OVT)_[A-Z0-9_]+',node.value):self.codes.add(node.value)
 def event(self,phase,event,**values):
  self.root_guard();self.sequence+=1;row=dict(schemaVersion=1,sequence=time.monotonic_ns(),epochMs=time.time_ns()//1000000,monotonicNs=time.monotonic_ns(),phase=phase,event=event)
  allowed={'moduleId','status','returncode','checkedEpochMs','reason','durationMs','nativeRunning','nativeExitCode','nativeStatus','nativeOomKilled','nativeStartedAt','nativeFinishedAt'}
  need(set(values)<=allowed,'DEBUG_EVENT_FIELDS')
  if values.get('moduleId')is None:values.pop('moduleId',None)
  if 'moduleId'in values:need(values['moduleId']in self.config['moduleIds'],'DEBUG_EVENT_MODULE')
  if 'reason'in values:need(re.fullmatch('[A-Z][A-Z0-9_]{0,95}',values['reason']or''),'DEBUG_EVENT_REASON')
  row.update(values);raw=(json.dumps(row,sort_keys=True)+'\n').encode()
  with os.fdopen(os.open(self.events,os.O_WRONLY|os.O_CREAT|os.O_APPEND|os.O_NOFOLLOW,0o600),'ab')as f:f.write(raw);f.flush();os.fsync(f.fileno())
  print('OVERTE_DEBUG_EVENT '+json.dumps(row,sort_keys=True),flush=True)
 def native_gate(self,module_id):
  if module_id not in self.config['domainRequiredModules']:return
  gate=self.config['nativeGate'];launcher=Path(gate['launcher']);active=Path(gate['activeConfig'])
  need(sha(launcher.read_bytes())==gate['launcherSha256']and sha(private_read(active))==gate['activeConfigSha256'],'DEBUG_NATIVE_GATE_BINDING_CHANGED')
  metadata=self.native_metadata(gate)
  started=time.time_ns();self.event('nativePrerequisite','begin',moduleId=module_id,status='checking',checkedEpochMs=started//1000000)
  log=self.root/('native-before-'+module_id+'-'+uuid.uuid4().hex+'.private.log')
  with os.fdopen(os.open(log,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb')as output:
   process=subprocess.run([sys.executable,'-B',str(launcher),'--action','verify','--config',str(active)],stdout=output,stderr=subprocess.STDOUT,timeout=180,check=False)
  finished=time.time_ns();reason='EXACT_LIVE_CONTROLLER_REQUIRED'
  try:
   result=json.loads(private_read(log));need(process.returncode==0 and result.get('status')=='ACTUAL_OWNED_NATIVE_FIXTURE_ACTIVE'and result.get('scope')=='HOST_METADATA_ONLY_NO_DEVICE_OR_FEATURE_VERDICT'and result.get('startResultSha256')==gate['startResultSha256']and type(result.get('checkedEpochNs'))is int and started<=result['checkedEpochNs']<=finished,'EXACT_LIVE_CONTROLLER_REQUIRED')
  except Exception:
   self.event('nativePrerequisite','error',moduleId=module_id,status='inactive',checkedEpochMs=finished//1000000,reason=reason,**metadata);self.hold(reason,module_id=module_id)
  self.event('nativePrerequisite','end',moduleId=module_id,status='active',checkedEpochMs=result['checkedEpochNs']//1000000)
 def publish(self,state,module_id,reason):
  self.root_guard();need(not self.published,'DEBUG_PUBLICATION_ALREADY_FINAL');self.stage.mkdir(mode=0o700,parents=True,exist_ok=True);s=self.stage.lstat();need(stat.S_ISDIR(s.st_mode)and s.st_uid==os.geteuid()and stat.S_IMODE(s.st_mode)==0o700,'DEBUG_STAGE_PRIVATE_REQUIRED')
  summary=dict(schemaVersion=1,status='error'if state=='DEBUG_HOLD'else'passed',debugState=state,runId=self.config['runId'],contextSha256=self.context,moduleId=module_id,reason=reason,cleanupPerformed=False,nextTargetStarted=False)
  atomic(self.stage/'summary.json',summary);suite=ET.Element('testsuite',name='focused-debug-preservation',tests='1',errors='1'if state=='DEBUG_HOLD'else'0');case=ET.SubElement(suite,'testcase',name=module_id or'admission')
  if state=='DEBUG_HOLD':ET.SubElement(case,'error',message=reason).text='Debug hold: original state retained; no PASS.'
  xml=ET.tostring(suite,encoding='utf-8',xml_declaration=True)
  with os.fdopen(os.open(self.stage/'junit.xml',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb')as f:f.write(xml);f.flush();os.fsync(f.fileno())
  raw=self.events.read_bytes()if self.events.exists()else b'';need(len(raw)<=16*1024*1024,'DEBUG_SAFE_EVENTS_LIMIT')
  with os.fdopen(os.open(self.stage/'diagnostic-events.safe.jsonl',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb')as f:f.write(raw);f.flush();os.fsync(f.fileno())
  generation=uuid.uuid4().hex
  publication_error=None
  try:self.publish_full_logs();self.validate_public_data()
  except Exception as error:
   self.record_exception(error,'DEBUG_LOG_CAPTURE_FAILED');publication_error='DEBUG_LOG_CAPTURE_FAILED';summary['status']='error';summary['reason']=publication_error
   atomic(self.stage/'summary.json',summary)
  if self.capture_metadata:
   summary['logSnapshots']=self.capture_metadata;atomic(self.stage/'summary.json',summary)
  files=[]
  for path in sorted(self.stage.rglob('*')):
   if path.is_file():files.append({'path':str(path.relative_to(self.stage)),'sha256':sha(path.read_bytes()),'bytes':path.stat().st_size})
  atomic(self.stage/'artifact-index.json',dict(schemaVersion=1,runId=self.config['runId'],contextSha256=self.context,generation=generation,files=files))
  artifacts={name:{'sha256':sha((self.stage/name).read_bytes()),'bytes':(self.stage/name).stat().st_size}for name in('summary.json','junit.xml','diagnostic-events.safe.jsonl','artifact-index.json')}
  atomic(self.stage/'debug-state.json',dict(schemaVersion=1,state=state,runId=self.config['runId'],contextSha256=self.context,generation=generation,checkedEpochMs=time.time_ns()//1000000,artifacts=artifacts));self.published=True
 def hold(self,reason,*,module_id=None,process=None):
  need(re.fullmatch('[A-Z][A-Z0-9_]{0,95}',reason),'DEBUG_HOLD_REASON');self.root_guard();owner=identity(os.getpid());child=None;stopped=False
  if process is not None and process.poll()is None:
   child=identity(process.pid);need(same_owner(process.debug_owner,child)and child['ppid']==os.getpid()and child['pgid']==child['sid']==child['pid'],'DEBUG_TIMEOUT_OWN_PROCESS_CHANGED')
   os.killpg(process.pid,signal.SIGSTOP);stopped=True
   if getattr(process,'fd',None)is not None:os.fsync(process.fd)
  self.event('debugHold','hold',moduleId=module_id,status='held',reason=reason)
  atomic(self.root/'HOLD.private.json',dict(schemaVersion=1,state='DEBUG_HOLD',contextSha256=self.context,nonce=self.nonce,reason=reason,moduleId=module_id,owner=owner,child=child,ownedProcessGroupStopped=stopped,cleanupPerformed=False,nextTargetStarted=False))
  try:self.publish('DEBUG_HOLD',module_id,reason)
  except Exception:
   try:self.minimal_publication(reason)
   except Exception:print('OVERTE_DEBUG_PUBLICATION_ERROR',flush=True)
  # A generic cancellation is not permission to destroy the preserved state.
  # Only the separately authenticated, exact-context cleanup request exits.
  for sig in(signal.SIGTERM,signal.SIGINT):signal.signal(sig,lambda _s,_f:None)
  while True:
   release=self.root/'RELEASE_REQUEST.private.json'
   if release.exists():
    try:
     value=json.loads(private_read(release));need(value==dict(schemaVersion=1,action='cleanup',contextSha256=self.context,nonce=self.nonce),'DEBUG_RELEASE_FOREIGN')
    except Exception:pass
    else:
     self.cleanup_authorized=True;atomic(self.root/'RELEASE_ACCEPTED.private.json',{'schemaVersion':1,'contextSha256':self.context,'cleanupRequested':True,'checkedEpochMs':time.time_ns()//1000000});raise DebugCleanupRequested()
   self.sleeper(.2)

class CapturedProcess:
 def __init__(self,policy,command,options):
  self.policy=policy;module=policy.active;need(module is not None,'DEBUG_MODULE_SCOPE_REQUIRED');self.module=module
  self.path=policy.root/('module-'+module+'.stdout-stderr.private.log');fd=os.open(self.path,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600);self.fd=fd
  options=dict(options);options['stdout']=fd;options['stderr']=subprocess.STDOUT
  self.process=subprocess.Popen(command,**options);self.debug_owner=identity(self.process.pid);need(self.debug_owner is not None,'DEBUG_MODULE_PROCESS_MISSING')
  atomic(policy.root/('module-'+module+'.owner.private.json'),dict(owner=self.debug_owner,command=command,rawLog=str(self.path)))
 def __getattr__(self,name):return getattr(self.process,name)
 def communicate(self,timeout=None):
  started=time.monotonic()
  deadline=None if timeout is None else started+timeout
  while self.process.poll()is None:
   try:
    if self.policy.follower is not None:self.policy.follower.poll()
   except Exception as error:
    self.policy.record_exception(error,'DEBUG_SPAN_ADMISSION_FAILED');self.policy.hold('DEBUG_SPAN_ADMISSION_FAILED',module_id=self.module,process=self)
   if deadline is not None and time.monotonic()>=deadline:raise subprocess.TimeoutExpired(self.process.args,timeout)
   try:self.process.wait(timeout=.1)
   except subprocess.TimeoutExpired:pass
  if self.policy.follower is not None:self.policy.follower.poll()
  os.fsync(self.fd);os.lseek(self.fd,0,os.SEEK_SET)
  with os.fdopen(os.dup(self.fd),'rb')as raw:
   with io.TextIOWrapper(raw,encoding='utf-8',errors='strict',newline=None)as text:output=text.read()
  self.policy.event('module','end',moduleId=self.module,status='passed'if self.process.returncode==0 else'failed',returncode=self.process.returncode,durationMs=int((time.monotonic()-started)*1000))
  if self.process.returncode!=0:self.policy.hold('MODULE_NONPASS',module_id=self.module)
  os.close(self.fd);self.fd=None;return output,None

def install_run_hooks(module,policy):
 original=module.run_module;real_subprocess=module.subprocess;real_stop=module.stop_process
 class Proxy:
  def __getattr__(self,name):return getattr(real_subprocess,name)
  def Popen(self,command,**options):
   return CapturedProcess(policy,command,options)if policy.active is not None else real_subprocess.Popen(command,**options)
 module.subprocess=Proxy()
 def wrapped(row,*args,**kwargs):
  need(row['id']in policy.config['moduleIds'],'DEBUG_UNREVIEWED_MODULE')
  try:policy.source_guard();policy.native_gate(row['id'])
  except DebugCleanupRequested:raise
  except Exception:policy.hold('PREMODULE_ADMISSION_FAILED',module_id=row['id'])
  if policy.follower is None and policy.config.get('spanRoot'):
   from safe_span_progress import Follower
   policy.follower=Follower(policy)
  policy.active=row['id'];policy.event('module','begin',moduleId=row['id'],status='running')
  try:return original(row,*args,**kwargs)
  except DebugCleanupRequested:raise
  except BaseException as error:
   policy.record_exception(error,'MODULE_EXCEPTION');policy.hold('MODULE_EXCEPTION',module_id=row['id'])
  finally:policy.active=None
 def stop(process):
  if isinstance(process,CapturedProcess):policy.hold('MODULE_TIMEOUT',module_id=policy.active,process=process)
  return real_stop(process)
 module.run_module=wrapped;module.stop_process=stop
 return module

def install_admission_hooks(module,policy):
 """Retain original admission checks; pause before their cleanup can dispatch."""
 original=module.adapter_call;execution=module.execute_prepared.__code__
 def call(command,action,*args,**kwargs):
  if action=='cleanup'and not policy.cleanup_authorized:
   frame=sys._getframe(1)
   if frame.f_code is execution:
    results=frame.f_locals.get('results',[])
    failed=next((r for r in results if r.get('status')!='passed'),None)
    if failed is not None:
     atomic(policy.root/'caught-runner-results.private.json',{'results':results})
     identifier=failed.get('id');identifier=identifier if identifier in policy.config['moduleIds']else None
     policy.hold('RUNNER_FAILURE_BEFORE_CLEANUP',module_id=identifier)
  try:return original(command,action,*args,**kwargs)
  except DebugCleanupRequested:raise
  except BaseException as error:
   policy.record_exception(error,'ADAPTER_CALL_FAILED');policy.hold('ADAPTER_CALL_FAILED',module_id=policy.active)
 module.adapter_call=call
 return module

def _record_exception(self,error,reason):
 import traceback
 value={'reason':reason,'class':type(error).__name__,'traceback':''.join(traceback.TracebackException.from_exception(error).format())}
 atomic(self.root/('exception-'+uuid.uuid4().hex+'.private.json'),value);atomic(self.root/'last-exception.private.json',value)
Policy.record_exception=_record_exception

def _span_event(self,safe):
 self.root_guard();row=dict(schemaVersion=1,sequence=time.monotonic_ns(),epochMs=time.time_ns()//1000000,phase='adapter',**safe)
 raw=(json.dumps(row,sort_keys=True)+'\n').encode()
 with os.fdopen(os.open(self.events,os.O_WRONLY|os.O_CREAT|os.O_APPEND|os.O_NOFOLLOW,0o600),'ab')as f:f.write(raw);f.flush();os.fsync(f.fileno())

def _pump_console(self):
 if not self.events.exists():return
 with self.events.open('rb')as f:
  f.seek(self.console_offset);raw=f.read(1024*1024)
  lines=raw.splitlines(keepends=True)
  for line in lines:
   if not line.endswith(b'\n'):break
   row=json.loads(line)
   from safe_span_progress import validate_safe_event
   need(validate_safe_event(row,set(self.config['moduleIds']),set(self.inventory),self.codes),'DEBUG_SAFE_EVENT_SCHEMA')
   # Producer data is already a closed projection; never forward raw spans.
   print('OVERTE_DEBUG_EVENT '+json.dumps(row,sort_keys=True),flush=True);self.console_offset+=len(line)

def _held(self):
 p=self.root/'HOLD.private.json'
 if not p.exists():return False
 value=json.loads(private_read(p));need(value.get('contextSha256')==self.context and value.get('nonce')==self.nonce and value.get('state')=='DEBUG_HOLD','DEBUG_HOLD_FOREIGN');return True

def _wait_existing(self):
 need(self.held(),'DEBUG_HOLD_REQUIRED')
 for sig in(signal.SIGTERM,signal.SIGINT):signal.signal(sig,lambda _s,_f:None)
 while True:
  self.pump_console()
  release=self.root/'RELEASE_REQUEST.private.json'
  if release.exists():
   try:need(json.loads(private_read(release))==dict(schemaVersion=1,action='cleanup',contextSha256=self.context,nonce=self.nonce),'DEBUG_RELEASE_FOREIGN')
   except Exception:pass
   else:
    self.cleanup_authorized=True;atomic(self.root/'RELEASE_ACCEPTED.private.json',{'schemaVersion':1,'contextSha256':self.context,'cleanupRequested':True,'checkedEpochMs':time.time_ns()//1000000});raise DebugCleanupRequested()
  self.sleeper(.2)
Policy.span_event=_span_event;Policy.pump_console=_pump_console;Policy.held=_held;Policy.wait_existing=_wait_existing

def _native_metadata(self,gate):
 result={}
 try:
  start_path=Path(gate['startResult']);raw=private_read(start_path);need(sha(raw)==gate['startResultSha256'],'DEBUG_NATIVE_START_CHANGED');start=json.loads(raw);container=start['containerId'];need(type(container)is str and re.fullmatch('[0-9a-f]{64}',container),'DEBUG_CONTAINER_ID_REQUIRED')
  query=subprocess.run(['podman','inspect',container],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30,check=False)
  with os.fdopen(os.open(self.root/('native-container-'+uuid.uuid4().hex+'.private.log'),os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb')as f:f.write(query.stdout);f.write(query.stderr)
  need(query.returncode==0,'DEBUG_CONTAINER_METADATA_UNAVAILABLE');rows=json.loads(query.stdout);need(type(rows)is list and len(rows)==1 and rows[0].get('Id')==container,'DEBUG_CONTAINER_ID_CHANGED');state=rows[0]['State']
  for key,out in [('Running','nativeRunning'),('OOMKilled','nativeOomKilled')]:
   if type(state.get(key))is bool:result[out]=state[key]
  if type(state.get('ExitCode'))is int:result['nativeExitCode']=state['ExitCode']
  if state.get('Status')in('running','exited','paused','created','stopped','configured','dead','removing'):result['nativeStatus']=state['Status']
  for key,out in [('StartedAt','nativeStartedAt'),('FinishedAt','nativeFinishedAt')]:
   if type(state.get(key))is str and re.fullmatch(r'[0-9TZ:.+\-]{1,64}',state[key]):result[out]=state[key]
 except Exception:pass
 return result
Policy.native_metadata=_native_metadata

def _publish_full_logs(self):
 """Root's pinned audited producer owns text redaction; never copy raw text."""
 import importlib.util
 ref=self.config.get('diagnosticPublisher');streams=self.config.get('publicLogStreams',{})
 if self.config.get('captureNativeContainerLog')is True:self.capture_container_log()
 if ref:
  path=Path(ref['path']);need(sha(path.read_bytes())==ref['sha256'],'DEBUG_LOG_PUBLISHER_CHANGED');spec=importlib.util.spec_from_file_location('bound_diagnostic_logs',path);publisher=importlib.util.module_from_spec(spec);spec.loader.exec_module(publisher)
  secrets=set(self.config.get('privateValues',[]));secret_refs=self.config.get('privateValuesFile')
  if secret_refs:
   raw=private_read(Path(secret_refs['path']));need(sha(raw)==secret_refs['sha256'],'DEBUG_PRIVATE_VALUES_CHANGED');values=json.loads(raw);need(type(values)is list and all(type(x)is str for x in values),'DEBUG_PRIVATE_VALUES_SCHEMA');secrets.update(values)
  for stream,relative in streams.items():
   need(re.fullmatch('[a-z][a-z0-9-]{0,79}',stream),'DEBUG_STREAM_NAME');source=Path(relative['path'])if type(relative)is dict else self.root/relative
   if type(relative)is not dict:need(source.resolve()==source and source.is_relative_to(self.root),'DEBUG_LOG_PATH_ALIAS')
   if source.exists():
    if type(relative)is dict:source=self.snapshot(stream,relative)
    directory=self.stage/'logs';directory.mkdir(mode=0o700,exist_ok=True);publisher.publish_log(source,directory/stream,secrets,chunk_bytes=1024*1024)
 for relative,reference in self.config.get('publicArtifacts',{}).items():
  destination=self.stage/relative;need(not Path(relative).is_absolute()and '..'not in Path(relative).parts and destination.resolve(strict=False)==destination,'DEBUG_PUBLIC_ARTIFACT_PATH')
  source=Path(reference['path']);raw=private_read(source);need(len(raw)==reference['bytes']and sha(raw)==reference['sha256'],'DEBUG_PUBLIC_ARTIFACT_CHANGED');destination.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
  with os.fdopen(os.open(destination,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb')as f:f.write(raw);f.flush();os.fsync(f.fileno())
Policy.publish_full_logs=_publish_full_logs

def _validate_public_data(self):
 ref=self.config['publicationPolicy'];raw=private_read(Path(ref['path']));need(sha(raw)==ref['sha256'],'DEBUG_PUBLICATION_POLICY_CHANGED');policy=json.loads(raw)
 actual=[]
 for p in self.stage.rglob('*'):
  need(not p.is_symlink()and p.resolve()==p,'DEBUG_PUBLICATION_ALIAS')
  if p.is_dir():need(p.stat().st_uid==os.geteuid()and stat.S_IMODE(p.stat().st_mode)==0o700,'DEBUG_PUBLICATION_DIRECTORY_MODE');continue
  s=p.stat();need(stat.S_ISREG(s.st_mode)and s.st_uid==os.geteuid()and s.st_nlink==1 and stat.S_IMODE(s.st_mode)==0o600,'DEBUG_PUBLICATION_PRIVATE_FILE');name=str(p.relative_to(self.stage));actual.append(name);literal=policy['literalFiles'].get(name)
  if literal:
   need(s.st_size<=literal['maxBytes'],'DEBUG_PUBLICATION_FILE_LIMIT')
   if 'sha256'in literal:need(sha(p.read_bytes())==literal['sha256']and s.st_size==literal['bytes'],'DEBUG_PUBLICATION_LITERAL_CHANGED')
  else:
   matches=[r for r in policy['logDirectories']if Path(name).parent==Path(r['path'])];need(len(matches)==1,'DEBUG_PUBLICATION_UNREVIEWED_FILE');rule=matches[0];base=Path(name).name
   if base=='index.json':need(s.st_size<=rule['indexMaxBytes'],'DEBUG_PUBLICATION_INDEX_LIMIT')
   else:
    matched=re.fullmatch('part-([0-9]{5})[.]log',base);need(matched is not None and 1<=int(matched[1])<=rule['maxParts']and s.st_size<=rule['maxPartBytes'],'DEBUG_PUBLICATION_PART_LIMIT')
 need(len(actual)<=policy['maxFiles']and sum((self.stage/n).stat().st_size for n in actual)<=policy['maxTotalBytes'],'DEBUG_PUBLICATION_TOTAL_LIMIT')
 need(all(not r['required']or name in actual for name,r in policy['literalFiles'].items()),'DEBUG_PUBLICATION_REQUIRED_FILE_MISSING')
 return actual
Policy.validate_public_data=_validate_public_data

def _publish_terminal(self):
 if not self.stage.exists():self.publish('TERMINAL',None,'ORIGINAL_PASS');return
 self.root_guard();need(not(self.stage/'debug-state.json').exists(),'DEBUG_TERMINAL_MARKER_EXISTS')
 for name in('summary.json','junit.xml'):need((self.stage/name).is_file()and not(self.stage/name).is_symlink(),'DEBUG_ORIGINAL_TERMINAL_RESULT_REQUIRED')
 # Original result files are never rewritten by the diagnostic publisher.
 raw=self.events.read_bytes()if self.events.exists()else b''
 with os.fdopen(os.open(self.stage/'diagnostic-events.safe.jsonl',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb')as f:f.write(raw);f.flush();os.fsync(f.fileno())
 self.publish_full_logs();self.validate_public_data();generation=uuid.uuid4().hex
 files=[{'path':str(p.relative_to(self.stage)),'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size}for p in sorted(self.stage.rglob('*'))if p.is_file()]
 atomic(self.stage/'artifact-index.json',dict(schemaVersion=1,runId=self.config['runId'],contextSha256=self.context,generation=generation,files=files))
 refs={n:{'sha256':sha((self.stage/n).read_bytes()),'bytes':(self.stage/n).stat().st_size}for n in('summary.json','junit.xml','diagnostic-events.safe.jsonl','artifact-index.json')}
 atomic(self.stage/'debug-state.json',dict(schemaVersion=1,state='TERMINAL',runId=self.config['runId'],contextSha256=self.context,generation=generation,checkedEpochMs=time.time_ns()//1000000,artifacts=refs));self.published=True
Policy.publish_terminal=_publish_terminal

def _snapshot(self,stream,reference):
 source=Path(reference['path']);scope=Path(reference['scopeRoot']);need(scope.is_absolute()and scope.resolve()==scope and source.resolve()==source and source.is_relative_to(scope),'DEBUG_STREAM_SCOPE_CHANGED')
 started=time.time_ns();fd=os.open(source,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_NOATIME)
 with os.fdopen(fd,'rb')as f:
  a=os.fstat(f.fileno());need(stat.S_ISREG(a.st_mode)and a.st_uid==os.geteuid()and a.st_nlink==1 and stat.S_IMODE(a.st_mode)==0o600 and a.st_size<=reference.get('maxRawBytes',128*1024*1024),'DEBUG_STREAM_PRIVATE_BOUND')
  raw=f.read(a.st_size);f.seek(0);again=f.read(a.st_size);b=os.fstat(f.fileno());c=source.lstat()
 need(len(raw)==a.st_size and raw==again and (a.st_dev,a.st_ino,a.st_uid,a.st_gid,a.st_mode,a.st_nlink)==(b.st_dev,b.st_ino,b.st_uid,b.st_gid,b.st_mode,b.st_nlink)==(c.st_dev,c.st_ino,c.st_uid,c.st_gid,c.st_mode,c.st_nlink)and b.st_size>=a.st_size,'DEBUG_STREAM_PREFIX_CHANGED')
 directory=self.root/'snapshots';directory.mkdir(mode=0o700,exist_ok=True);target=directory/(stream+'.private.log')
 with os.fdopen(os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb')as f:f.write(raw);f.flush();os.fsync(f.fileno())
 receipt={'stream':stream,'scope':'ACTUAL_PREFIX_SNAPSHOT_AT_START_NO_ATOMIC_NATIVE_FRAME_CLAIM','startedEpochNs':started,'completedEpochNs':time.time_ns(),'snapshotBytes':len(raw),'snapshotSha256':sha(raw),'sourceBeforeBytes':a.st_size,'sourceAfterBytes':b.st_size,'sourceGrewDuringCapture':b.st_size>a.st_size,'rawOriginalRetained':True,'sourceBefore':{'dev':a.st_dev,'ino':a.st_ino,'uid':a.st_uid,'mode':a.st_mode,'mtimeNs':a.st_mtime_ns,'ctimeNs':a.st_ctime_ns},'sourceAfter':{'mtimeNs':b.st_mtime_ns,'ctimeNs':b.st_ctime_ns}}
 atomic(directory/(stream+'.receipt.private.json'),receipt);self.capture_metadata.append({k:v for k,v in receipt.items()if k not in('sourceBefore','sourceAfter')})
 if reference.get('kind','text')=='memory':
  public=[]
  for line in raw.splitlines():
   row=json.loads(line);closed={'scope':'NUMERIC_MEMORY_OBSERVATION_NO_CGROUP_OR_ARGV','atomicSnapshotClaimed':False}
   for key in('epochNs','monotonicNs','currentBytes','maxBytes','peakBytes','reserveBytes','thresholdBytes'):
    if type(row.get(key))is int and row[key]>=0:closed[key]=row[key]
   if row.get('phase')in('pre-launch','startup','periodic','on-hold','before-active-verify','after-active-verify'):closed['phase']=row['phase']
   if type(row.get('events'))is dict:closed['events']={k:v for k,v in row['events'].items()if k in('low','high','max','oom','oom_kill','oom_group_kill','sock_throttled')and type(v)is int and v>=0}
   closed['ownRssBytes']=[]
   for process in row.get('ownRssBytes',[]):
    if type(process)is not dict:continue
    item={k:process[k]for k in('pid','uid','pgid','parentPid','rssBytes','returncode')if type(process.get(k))is int}
    if process.get('state')in('R','S','T','D','Z','X','I'):item['state']=process['state']
    if type(process.get('role'))is str and re.fullmatch('(domain-server|assignment-client|assignment-agent|agent|assignment)(-[0-9]{1,3})?',process['role']):item['role']=process['role']
    closed['ownRssBytes'].append(item)
   public.append(json.dumps(closed,sort_keys=True))
  projected=directory/(stream+'.numeric.private.log')
  with os.fdopen(os.open(projected,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb')as f:f.write(('\n'.join(public)+'\n').encode());f.flush();os.fsync(f.fileno())
  return projected
 return target
Policy.snapshot=_snapshot

def _minimal_publication(self,reason):
 """Even an incomplete full-log bundle exposes a closed failing core receipt."""
 self.root_guard();self.stage.mkdir(mode=0o700,parents=True,exist_ok=True);s=self.stage.lstat();need(self.stage.resolve()==self.stage and s.st_uid==os.geteuid()and stat.S_IMODE(s.st_mode)==0o700,'DEBUG_FALLBACK_STAGE_SCOPE')
 def data(name,raw):
  path=self.stage/name
  if path.exists():
   old=path.lstat();need(stat.S_ISREG(old.st_mode)and old.st_uid==os.geteuid()and old.st_nlink==1 and not path.is_symlink(),'DEBUG_FALLBACK_FILE_SCOPE')
  tmp=path.with_name(name+'.'+uuid.uuid4().hex+'.tmp')
  with os.fdopen(os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb')as f:f.write(raw);f.flush();os.fsync(f.fileno())
  os.replace(tmp,path)
 summary={'schemaVersion':1,'status':'error','debugState':'DEBUG_HOLD','reason':'DEBUG_PUBLICATION_FAILED','originalHoldReason':reason,'runId':self.config['runId'],'contextSha256':self.context,'publicationComplete':False,'cleanupPerformed':False,'nextTargetStarted':False}
 data('summary.json',(json.dumps(summary,sort_keys=True,indent=2)+'\n').encode());suite=ET.Element('testsuite',name='debug-publication-failure',tests='1',errors='1');case=ET.SubElement(suite,'testcase',name='debug-publication');ET.SubElement(case,'error',message='DEBUG_PUBLICATION_FAILED').text='State preserved; complete log publication unavailable.'
 data('junit.xml',ET.tostring(suite,encoding='utf-8',xml_declaration=True));raw=self.events.read_bytes()if self.events.exists()else b'';need(len(raw)<=16*1024*1024,'DEBUG_FALLBACK_EVENTS_LIMIT');data('diagnostic-events.safe.jsonl',raw)
 generation=uuid.uuid4().hex;files=[{'path':n,'sha256':sha((self.stage/n).read_bytes()),'bytes':(self.stage/n).stat().st_size}for n in('summary.json','junit.xml','diagnostic-events.safe.jsonl')];atomic(self.stage/'artifact-index.json',{'schemaVersion':1,'runId':self.config['runId'],'contextSha256':self.context,'generation':generation,'files':files})
 refs={n:{'sha256':sha((self.stage/n).read_bytes()),'bytes':(self.stage/n).stat().st_size}for n in('summary.json','junit.xml','diagnostic-events.safe.jsonl','artifact-index.json')};atomic(self.stage/'debug-state.json',{'schemaVersion':1,'state':'DEBUG_HOLD','runId':self.config['runId'],'contextSha256':self.context,'generation':generation,'checkedEpochMs':time.time_ns()//1000000,'artifacts':refs});self.published=True
Policy.minimal_publication=_minimal_publication

def _capture_container_log(self):
 gate=self.config['nativeGate'];raw=private_read(Path(gate['startResult']));need(sha(raw)==gate['startResultSha256'],'DEBUG_CONTAINER_START_CHANGED');container=json.loads(raw)['containerId'];need(type(container)is str and re.fullmatch('[0-9a-f]{64}',container),'DEBUG_CONTAINER_ID_REQUIRED')
 path=self.root/'native-container.stdout-stderr.private.log';started=time.time_ns()
 with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb')as output:
  result=subprocess.run(['podman','logs','--timestamps',container],stdout=output,stderr=subprocess.STDOUT,timeout=30,check=False)
 atomic(self.root/'native-container-log-receipt.private.json',{'scope':'EXACT_PINNED_NATIVE_CONTAINER_READONLY_LOG_SNAPSHOT','containerId':container,'startedEpochNs':started,'completedEpochNs':time.time_ns(),'returncode':result.returncode,'sha256':sha(path.read_bytes()),'bytes':path.stat().st_size})
 need(result.returncode==0,'DEBUG_CONTAINER_LOG_UNAVAILABLE');return path
Policy.capture_container_log=_capture_container_log
