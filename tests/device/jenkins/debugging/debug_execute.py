"""Explicit debug-only execute delta: preserve the active stack on first failure."""
import os,signal,subprocess,time
from pathlib import Path
from debug_failure_hold import Policy,DebugCleanupRequested,identity,private_read,sha,need

def from_environment(environment):
 path=environment.get('OVERTE_DEVICE_DEBUG_HOLD_CONFIG');digest=environment.get('OVERTE_DEVICE_DEBUG_HOLD_CONFIG_SHA256')
 need(type(path)is str and type(digest)is str,'DEBUG_EXPLICIT_ENVIRONMENT_REQUIRED');return Policy(path,digest)

def preserving_execute(original,policy):
 g=original.__globals__
 def execute(argv,cwd,env,timeout,log,*,observer=None):
  need(observer is None,'DEBUG_NO_UNREVIEWED_COMPANION')
  try:policy.source_guard()
  except Exception as error:policy.record_exception(error,'EXECUTOR_SOURCE_ADMISSION_FAILED');policy.hold('EXECUTOR_SOURCE_ADMISSION_FAILED')
  started=time.monotonic();owned={};process=None
  path=Path(log);path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
  with g['owner_module'](Path(cwd)).command_owner()as reap:
   with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb')as output:
    try:
     process=subprocess.Popen(argv,cwd=cwd,env=env,stdout=output,stderr=subprocess.STDOUT,start_new_session=True);process.debug_owner=identity(process.pid);g['collect_children'](process.pid,owned,parent=os.getpid())
     deadline=time.monotonic()+timeout
     while process.poll()is None:
      g['collect_children'](process.pid,owned);g['adopted_children'](owned);policy.pump_console()
      if policy.held():policy.wait_existing()
      if time.monotonic()>=deadline:policy.hold('SUPERVISOR_TIMEOUT',process=process)
      try:process.wait(timeout=.1)
      except subprocess.TimeoutExpired:pass
     if process.returncode!=0:policy.hold('SUPERVISED_COMMAND_NONPASS')
     g['adopted_children'](owned)
     if g['live_owned'](owned):policy.hold('OWNED_CHILDREN_REMAIN')
    finally:
     # This block is unreachable while debug-held. It runs on ordinary PASS or
     # the exact explicit cleanup disposition, never a timer/signal ACK.
     g['collect_children'](process.pid,owned)if process is not None else None;g['adopted_children'](owned);g['stop_owned'](owned)
     if process is not None:process.wait(timeout=5)
     g['adopted_children'](owned);reap()
  return {'returncode':process.returncode,'timedOut':False,'ownedChildrenLeaked':False,'debugPreservationMode':True,'durationSeconds':time.monotonic()-started}
 return execute
