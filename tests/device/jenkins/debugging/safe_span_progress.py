"""Closed projection of existing private spans; never read or issue DUT commands."""
import json,os,re,stat
from pathlib import Path
LABELS={'PhoneAppiumAdapter.installed_identity','PhoneAppiumAdapter.ensure_session','PhoneAppiumAdapter.invoke','PhoneAppiumAdapter.normal_navigation','PhoneAdapter.installed_identity','VerifiedCandidate.verify','AppiumAdapter.semantic_snapshot','AppiumAdapter.probe_snapshot','AppiumAdapter.attest_android_phone_profile','WebDriver.call','AdbTransport.execute'}
CATEGORIES={'fresh-properties','package-path','actual-file-sha256','package-features','app-private-file','native-process','transport-state','other-original-adb','session-POST','session-GET','session-DELETE','fresh-semantic-source','normal-element-click','element-lookup','original-mobile-command','other-original-webdriver','normal-text-clear','normal-text-write','normal-focus-observe','normal-focus-tab-request','normal-go-touch-request','normal-input-release'}
CONTROLS={'PhoneAddressField','Go','Cancel','GoToEntry'}
CLASSES={'NativeUIError','ValueError','RuntimeError','OSError','AssertionError','TimeoutExpired','JSONDecodeError','UnicodeDecodeError','KeyboardInterrupt','SystemExit','FileNotFoundError','PermissionError'}
def exception(error,source_files,codes,depth=0):
 if type(error)is not dict or depth>6:return None
 result={'class':error.get('class')if error.get('class')in CLASSES else'UnknownError','closedCodes':[c for c in error.get('closedCodes',[])if c in codes][:32],'frames':[]}
 for frame in error.get('sourceFrames',[])[:64]:
  if type(frame)is not dict:continue
  name=frame.get('sourceFile');function=frame.get('function');line=frame.get('line')
  if name not in source_files and name not in {'<runtime>','<python-runtime>','<diagnostic-wrapper>','<diagnostic-or-python-runtime>'}:name='<runtime>'
  if type(function)is not str or not re.fullmatch('[A-Za-z_<>][A-Za-z0-9_.<>]{0,95}',function):function='<unknown>'
  if type(line)is not int or not 0<line<1000000:continue
  result['frames'].append({'file':name,'function':function,'line':line})
 for key in('cause','context'):
  child=exception(error.get(key),source_files,codes,depth+1)
  if child is not None:result[key]=child
 return result

def project(row,source_files,codes):
 if type(row)is not dict:return None
 kind=row.get('event')
 if kind in('begin','end','error'):
  if row.get('label')not in LABELS:return None
  result={'event':kind,'label':row['label']}
  if row.get('category')in CATEGORIES:result['category']=row['category']
  if type(row.get('sequence'))is int and row['sequence']>0:result['originalSequence']=row['sequence']
  if kind=='error':result['exception']=exception(row.get('exception'),source_files,codes)
 elif kind=='normal-ui-read':
  if row.get('control')not in CONTROLS or row.get('outcome')not in('actual','invalid','error'):return None
  result={'event':'observation','control':row['control'],'status':row['outcome'],'present':row.get('present')if type(row.get('present'))is bool else None}
 elif kind=='normal-phone-ime-read':result={'event':'observation','category':'normal-ime','status':row.get('outcome')if row.get('outcome')in('actual','invalid','error')else'unknown','visible':row.get('visible')if type(row.get('visible'))is bool else None}
 elif kind=='original-catch-exception':result={'event':'error','exception':exception(row.get('exception'),source_files,codes)}
 elif kind in('normal-go-input-evidence','normal-go-input-evidence-result'):
  result={'event':'observation','category':'normal-go-evidence','inputEffectClaimed':False}
  if kind.endswith('-result'):
   obs=row.get('observation',{});result['captureComplete']=obs.get('captureComplete')if type(obs.get('captureComplete'))is bool else None
   for key,limit in [('actualSdkReads',12),('originalGoRequests',1)]:
    if type(obs.get(key))is int and 0<=obs[key]<=limit:result[key]=obs[key]
  else:
   if row.get('stage')in('before','after','initialize'):result['stage']=row['stage']
   if row.get('status')in('UNKNOWN','SDK_OBSERVATIONS_UNQUALIFIED'):result['status']=row['status']
 else:return None
 for key in('monotonicNs','startedMonotonicNs'):
  if type(row.get(key))is int and row[key]>0:result[key]=row[key]
 return result

class Follower:
 def __init__(self,policy):self.policy=policy;self.root=Path(policy.config['spanRoot']);self.offsets={};self.buffers={};self.contexts={}
 def poll(self):
  if not self.root.exists():return
  s=self.root.lstat();assert self.root.resolve()==self.root and stat.S_ISDIR(s.st_mode)and s.st_uid==os.geteuid()and stat.S_IMODE(s.st_mode)==0o700
  paths=list(self.root.glob('adapter-*.jsonl'));assert len(paths)<=512
  for p in paths:
   assert re.fullmatch('adapter-[0-9]+-[0-9]+[.]jsonl',p.name)
   fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
   with os.fdopen(fd,'rb')as f:
    before=os.fstat(f.fileno());assert stat.S_ISREG(before.st_mode)and before.st_uid==os.geteuid()and before.st_nlink==1 and stat.S_IMODE(before.st_mode)==0o600
    key=(before.st_dev,before.st_ino);offset=self.offsets.get(key,0);assert before.st_size>=offset
    f.seek(offset);raw=f.read(1024*1024);self.offsets[key]=offset+len(raw);after=os.fstat(f.fileno());actual=p.lstat();assert (before.st_dev,before.st_ino)==(after.st_dev,after.st_ino)==(actual.st_dev,actual.st_ino)
   data=self.buffers.get(key,b'')+raw;lines=data.split(b'\n');self.buffers[key]=lines.pop();assert len(self.buffers[key])<=256*1024
   for line in lines:
    assert len(line)<=256*1024;row=json.loads(line)
    if key not in self.contexts:
     assert row.get('event')=='context'and p.name=='adapter-'+str(row['pid'])+'-'+row['birth']+'.jsonl'
     assert all(row.get(k)==v for k,v in self.policy.config['spanContext'].items());self.contexts[key]=True;continue
    safe=project(row,self.policy.inventory,self.policy.codes)
    if safe is not None:self.policy.span_event(safe)

def validate_safe_event(row,modules,source_files,codes):
 allowed={'schemaVersion','sequence','epochMs','monotonicNs','startedMonotonicNs','phase','event','moduleId','status','reason','returncode','durationMs','checkedEpochMs','nativeRunning','nativeExitCode','nativeStatus','nativeOomKilled','nativeStartedAt','nativeFinishedAt','label','category','originalSequence','exception','control','present','visible','inputEffectClaimed','captureComplete','actualSdkReads','originalGoRequests','stage'}
 if type(row)is not dict or set(row)-allowed or row.get('schemaVersion')!=1 or type(row.get('sequence'))is not int:return False
 if row.get('phase')not in('nativePrerequisite','module','adapter','debugHold','terminal')or row.get('event')not in('begin','end','error','observation','hold','terminal'):return False
 if 'moduleId'in row and row['moduleId']not in modules:return False
 if 'label'in row and row['label']not in LABELS:return False
 if 'category'in row and row['category']not in CATEGORIES|{'normal-ime','normal-go-evidence'}:return False
 if 'control'in row and row['control']not in CONTROLS:return False
 if 'reason'in row and (type(row['reason'])is not str or not re.fullmatch('[A-Z][A-Z0-9_]{0,95}',row['reason'])):return False
 if 'status'in row and row['status']not in('checking','inactive','active','held','running','passed','failed','actual','invalid','error','unknown','UNKNOWN','SDK_OBSERVATIONS_UNQUALIFIED'):return False
 if 'nativeStatus'in row and row['nativeStatus']not in('running','exited','paused','created','stopped','configured','dead','removing'):return False
 for key in('present','visible','nativeRunning','nativeOomKilled','captureComplete'):
  if key in row and row[key]is not None and type(row[key])is not bool:return False
 if 'inputEffectClaimed'in row and row['inputEffectClaimed']is not False:return False
 for key in('epochMs','monotonicNs','startedMonotonicNs','sequence','originalSequence','checkedEpochMs','durationMs','returncode','nativeExitCode','actualSdkReads','originalGoRequests'):
  if key in row and type(row[key])is not int:return False
 for key in('nativeStartedAt','nativeFinishedAt'):
  if key in row and(type(row[key])is not str or not re.fullmatch(r'[0-9TZ:.+\-]{1,64}',row[key])):return False
 if 'stage'in row and row['stage']not in('before','after','initialize'):return False
 def safe_exception(value,depth=0):
  if value is None:return True
  if type(value)is not dict or depth>6 or set(value)-{'class','closedCodes','frames','cause','context'}or value.get('class')not in CLASSES|{'UnknownError'}:return False
  if type(value.get('closedCodes'))is not list or any(c not in codes for c in value['closedCodes']):return False
  for f in value.get('frames',[]):
   if type(f)is not dict or set(f)!={'file','function','line'}or f['file']not in source_files|{'<runtime>','<python-runtime>','<diagnostic-wrapper>','<diagnostic-or-python-runtime>'}or type(f['line'])is not int or type(f['function'])is not str or not re.fullmatch('[A-Za-z_<>][A-Za-z0-9_.<>]{0,95}',f['function']):return False
  return all(safe_exception(value.get(k),depth+1)for k in('cause','context'))
 return safe_exception(row.get('exception'))
