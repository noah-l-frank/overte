"""Fresh standalone owner for unchanged original sequential_campaign.execute.

The parent may own an unrelated Scene server. Only this fresh single-threaded,
child-free CLI enters original command_owner; parent never becomes a subreaper.
"""
import argparse,hashlib,importlib.util,json,os,signal,stat,subprocess,sys,time,traceback
from pathlib import Path

FILES=('tests/device/jenkins/sequential_campaign.py','tests/device/run_control_plane_tests.py')
class IsolatedExecutionError(RuntimeError):pass

def need(ok,code):
 if not ok:raise IsolatedExecutionError(code)
def read(path):
 with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'rb')as f:
  before=os.fstat(f.fileno());need(stat.S_ISREG(before.st_mode),'OVT_ISOLATED_REGULAR_INPUT');raw=f.read();after=os.fstat(f.fileno())
 signature=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_uid,s.st_gid,s.st_mode,s.st_nlink)
 need(signature(before)==signature(after)==signature(path.lstat()),'OVT_ISOLATED_INPUT_CHANGED');return raw

def sha(path):return hashlib.sha256(read(path)).hexdigest()
def write(path,value):
 with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'w')as f:json.dump(value,f,sort_keys=True,indent=2);f.flush();os.fsync(f.fileno())
 need(json.loads(read(path))==json.loads(json.dumps(value)),'OVT_ISOLATED_OUTPUT_READBACK')
def process(pid):
 try:
  p=Path('/proc')/str(pid);raw=(p/'stat').read_text();v=raw[raw.rfind(')')+2:].split()
  return {'pid':pid,'birth':v[19],'state':v[0],'ppid':int(v[1]),'pgid':os.getpgid(pid),'uid':p.stat().st_uid}
 except (FileNotFoundError,ProcessLookupError):return None

def exact_identity(pid):
 v=process(pid)
 if v is None or v['state']=='Z':return None
 p=Path('/proc')/str(pid);return {k:v[k]for k in('pid','birth','pgid','uid')}|{'executable':os.readlink(p/'exe'),'argvSha256':hashlib.sha256((p/'cmdline').read_bytes()).hexdigest()}
def descendant_snapshot(pid,known,parent=None):
 v=process(pid)
 if v is None:return
 if pid in known:
  if known[pid]['birth']!=v['birth']or known[pid]['uid']!=v['uid']:return
 elif parent is None or v['ppid']!=parent:return
 else:known[pid]=v
 try:children=(Path('/proc')/str(pid)/'task'/str(pid)/'children').read_text().split()
 except FileNotFoundError:return
 for child in children:descendant_snapshot(int(child),known,pid)
def live_known(known):
 return [pid for pid,pin in known.items()if (v:=process(pid))and v['birth']==pin['birth']and v['uid']==pin['uid']and v['state']!='Z']
def group_members(pgid):
 result=[]
 for p in Path('/proc').iterdir():
  if not p.name.isdecimal():continue
  try:
   if os.getpgid(int(p.name))==pgid and (v:=process(int(p.name)))and v['state']!='Z':result.append(v['pid'])
  except (FileNotFoundError,ProcessLookupError):pass
 return result

def source_guard(source,pins):
 need(source.is_absolute()and source.resolve()==source and set(pins)==set(FILES),'OVT_ISOLATED_SOURCE_SCOPE')
 for name,expected in pins.items():need(sha(source/name)==expected,'OVT_ISOLATED_SOURCE_CHANGED')
def load_execute(source):
 spec=importlib.util.spec_from_file_location('unchanged_original_execute',source/FILES[0]);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module.execute

def safe_error(error,source):
 frames=[]
 for f in traceback.extract_tb(error.__traceback__):
  p=Path(f.filename);name=str(p.relative_to(source))if p.is_absolute()and p.is_relative_to(source)else'<diagnostic>/isolated_original_execute.py'if p==Path(__file__)else'<python-runtime>'
  frames.append({'sourceFile':name,'function':f.name,'line':f.lineno})
 return {'class':type(error).__name__,'sourceFrames':frames}

def supervisor_environment():
 env={'PATH':os.environ.get('PATH',''),'HOME':os.environ.get('HOME',''),'PYTHONDONTWRITEBYTECODE':'1','PYTHONNOUSERSITE':'1'}
 if os.environ.get('JENKINS_NODE_COOKIE'):env['JENKINS_NODE_COOKIE']=os.environ['JENKINS_NODE_COOKIE']
 return env

class IsolatedExecutor:
 def __init__(self,source,pins,script,script_sha256,artifact_root):
  self.source=Path(source);self.pins=dict(pins);self.script=Path(script);self.script_sha256=script_sha256;self.root=Path(artifact_root);self.index=0
  need(not self.root.exists()and self.root.parent.resolve()==self.root.parent,'OVT_ISOLATED_FRESH_ROOT');self.root.mkdir(mode=0o700)
  source_guard(self.source,self.pins);need(sha(self.script)==script_sha256,'OVT_ISOLATED_SCRIPT_CHANGED')
 def __call__(self,argv,cwd,env,timeout,log,*,observer=None):
  need(observer is None and Path(cwd)==self.source,'OVT_ISOLATED_ORIGINAL_SCOPE');need(type(timeout)in(int,float)and 0<timeout<=7200,'OVT_ISOLATED_TIMEOUT')
  source_guard(self.source,self.pins);need(sha(self.script)==self.script_sha256,'OVT_ISOLATED_SCRIPT_CHANGED')
  from debug_execute import from_environment,hold_exception
  from debug_failure_hold import DebugCleanupRequested
  debug=from_environment(env)
  try:debug.source_guard()
  except DebugCleanupRequested:raise
  except BaseException as error:hold_exception(debug,error,'ISOLATED_SOURCE_ADMISSION_FAILED',{},lambda:None)
  self.index+=1;call=self.root/('call-'+str(self.index));call.mkdir(mode=0o700)
  request={'schemaVersion':1,'argv':argv,'cwd':str(cwd),'environment':env,'timeout':timeout,'log':str(log),'sourcePins':self.pins,'supervisorSha256':self.script_sha256}
  request_path=call/'request.private.json';write(request_path,request);request_sha=sha(request_path);result_path=call/'result.private.json'
  with os.fdopen(os.open(call/'supervisor.private.log',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb')as output:
   child=subprocess.Popen([sys.executable,'-B',str(self.script),'--request',str(request_path),'--request-sha256',request_sha,'--result',str(result_path),'--self-sha256',self.script_sha256],stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,start_new_session=True,env=supervisor_environment())
  owner=None;known={}
  deadline=time.monotonic()+timeout+30;outer_timed_out=False;forced=False
  try:
   owner=exact_identity(child.pid);need(owner is not None and owner['pgid']==child.pid,'OVT_ISOLATED_SUPERVISOR_OWNER');known={child.pid:process(child.pid)};write(call/'parent-owner.private.json',owner)
   while child.poll()is None:
    descendant_snapshot(child.pid,known)
    debug.pump_console()
    if debug.held():debug.wait_existing()
    if time.monotonic()>=deadline:outer_timed_out=True;break
    try:child.wait(timeout=.05)
    except subprocess.TimeoutExpired:pass
   if child.returncode!=0:debug.hold('ISOLATED_SUPERVISOR_NONPASS')
  except DebugCleanupRequested:raise
  except BaseException as error:
   births={pid:pin['birth']for pid,pin in known.items()}
   def refresh():
    descendant_snapshot(child.pid,known)
    births.update({pid:pin['birth']for pid,pin in known.items()})
   hold_exception(debug,error,'ISOLATED_PARENT_OBSERVER_EXCEPTION',births,refresh)
  finally:
   if child.poll()is None:
    descendant_snapshot(child.pid,known);need(exact_identity(child.pid)==owner,'OVT_ISOLATED_OWNER_CHANGED_BEFORE_TERM');os.kill(child.pid,signal.SIGTERM)
    try:child.wait(timeout=30)
    except subprocess.TimeoutExpired:
     forced=True;descendant_snapshot(child.pid,known);need(exact_identity(child.pid)==owner,'OVT_ISOLATED_OWNER_CHANGED_BEFORE_KILL');os.kill(child.pid,signal.SIGKILL);child.wait(timeout=5)
   survivors=[p for p in live_known(known)if p!=child.pid]
   if survivors:
    # Known lineage only. No global adoption, foreign group or fixture signal.
    for sig in(signal.SIGTERM,signal.SIGKILL):
     for pid in live_known(known):
      if pid!=child.pid:
       try:os.kill(pid,sig)
       except ProcessLookupError:pass
     end=time.monotonic()+5
     while live_known(known)and time.monotonic()<end:time.sleep(.05)
   remaining=live_known(known);groups=group_members(owner['pgid'])
   write(call/'parent-terminal.private.json',{'supervisorOwner':owner,'returncode':child.returncode,'outerTimedOut':outer_timed_out,'forcedKill':forced,'remainingKnown':remaining,'supervisorGroupSurvivors':groups,'knownLineage':known,'resultPresent':result_path.is_file()})
  source_guard(self.source,self.pins);need(sha(self.script)==self.script_sha256 and sha(request_path)==request_sha,'OVT_ISOLATED_CONTEXT_CHANGED')
  need(not outer_timed_out and not forced and not remaining and not groups,'OVT_ISOLATED_CLEANUP_INCOMPLETE')
  need(result_path.is_file(),'OVT_ISOLATED_RESULT_MISSING');result=json.loads(read(result_path))
  need(result['requestSha256']==request_sha and result['supervisorSha256']==self.script_sha256 and result['owner']==owner and result['sourcePins']==self.pins,'OVT_ISOLATED_RESULT_FOREIGN')
  need(child.returncode==0 and result['status']=='ORIGINAL_EXECUTE_RETURNED'and result['sourceGuardsBeforeAfter'],'OVT_ISOLATED_ORIGINAL_EXECUTE_EXCEPTION')
  original=result['originalResult'];need(not original.get('ownedChildrenLeaked'),'OVT_ISOLATED_ORIGINAL_CHILD_LEAK');return original

def child_main():
 p=argparse.ArgumentParser(allow_abbrev=False);p.add_argument('--request',type=Path,required=True);p.add_argument('--request-sha256',required=True);p.add_argument('--result',type=Path,required=True);p.add_argument('--self-sha256',required=True);a=p.parse_args();os.umask(0o077);sys.dont_write_bytecode=True
 need(sha(Path(__file__))==a.self_sha256 and sha(a.request)==a.request_sha256,'OVT_ISOLATED_REQUEST_OR_SELF_CHANGED');raw=read(a.request);request=json.loads(raw);source=Path(request['cwd']);source_guard(source,request['sourcePins']);need(request['supervisorSha256']==a.self_sha256,'OVT_ISOLATED_SELF_BINDING')
 owner=exact_identity(os.getpid());need(owner and owner['pgid']==os.getpid(),'OVT_ISOLATED_NEW_PROCESS_GROUP');tasks={p.name for p in Path('/proc/self/task').iterdir()};children=Path('/proc/self/task')/str(os.getpid())/'children';need(tasks=={str(os.getpid())}and not children.read_text().split(),'OVT_ISOLATED_CHILD_FREE_SINGLE_THREAD')
 write(a.result.with_name('child-start.private.json'),{'owner':owner,'threadCount':len(tasks),'directChildren':[],'requestSha256':a.request_sha256})
 status={'status':'ERROR','owner':owner,'requestSha256':a.request_sha256,'supervisorSha256':a.self_sha256,'sourcePins':request['sourcePins'],'sourceGuardsBeforeAfter':False}
 def cancel(_signum,_frame):raise KeyboardInterrupt()
 signal.signal(signal.SIGTERM,cancel)
 try:
  from debug_execute import from_environment,preserving_execute
  debug=from_environment(request['environment'])
  execute=preserving_execute(load_execute(source),debug);status['originalResult']=execute(request['argv'],source,request['environment'],request['timeout'],Path(request['log']))
  source_guard(source,request['sourcePins']);need(sha(a.request)==a.request_sha256 and sha(Path(__file__))==a.self_sha256,'OVT_ISOLATED_FINAL_CONTEXT_CHANGED');need(not children.read_text().split(),'OVT_ISOLATED_FINAL_CHILDREN');status['sourceGuardsBeforeAfter']=True;status['status']='ORIGINAL_EXECUTE_RETURNED'
 except BaseException as error:status['exception']=safe_error(error,source)
 write(a.result,status);return 0 if status['status']=='ORIGINAL_EXECUTE_RETURNED'else 75
if __name__=='__main__':raise SystemExit(child_main())
