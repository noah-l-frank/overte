"""Fixed native timeline slots1..8; read-only bounded lossless-prefix gate."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
# Derived from the reviewed native_log_coverage.py slots8 diagnostic helper.
import hashlib,json,os,stat
from pathlib import Path
FILES={1: 'MEMORY_TIMELINE.private.jsonl', 2: 'MEMORY_TIMELINE.part-000002.private.jsonl', 3: 'MEMORY_TIMELINE.part-000003.private.jsonl', 4: 'MEMORY_TIMELINE.part-000004.private.jsonl', 5: 'MEMORY_TIMELINE.part-000005.private.jsonl', 6: 'MEMORY_TIMELINE.part-000006.private.jsonl', 7: 'MEMORY_TIMELINE.part-000007.private.jsonl', 8: 'MEMORY_TIMELINE.part-000008.private.jsonl'}
INDEX='MEMORY_TIMELINE_INDEX.private.jsonl';LIMIT=8*1024**2;HEADROOM=4*1024**2

def need(ok,code):
 if not ok:raise ValueError(code)
def identity(s):return[s.st_dev,s.st_ino,s.st_uid,s.st_mode,s.st_nlink]
def sample(path,limit):
 with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK),'rb')as f:
  a=os.fstat(f.fileno());need(stat.S_ISREG(a.st_mode)and a.st_uid==os.geteuid()and a.st_nlink==1 and stat.S_IMODE(a.st_mode)==0o600 and 0<a.st_size<=limit,'NATIVE_LOG_PRIVATE_FILE_REQUIRED')
  raw=os.pread(f.fileno(),a.st_size,0);b=os.fstat(f.fileno());c=path.lstat()
  need(identity(a)==identity(b)==identity(c)and b.st_size>=a.st_size and len(raw)==a.st_size and os.pread(f.fileno(),a.st_size,0)==raw,'NATIVE_LOG_PREFIX_CHANGED')
 return raw,{'identity':identity(a),'bytes':a.st_size,'sha256':hashlib.sha256(raw).hexdigest()}
def names(root):return{name for name in os.listdir(root)if name.startswith('MEMORY_TIMELINE')}
def check(expected=None,*,require_headroom=True,root):
 root=Path(root)
 need(root.resolve()==root,'NATIVE_LOG_ROOT_ALIAS');folder=root.lstat();need(stat.S_ISDIR(folder.st_mode)and folder.st_uid==os.geteuid()and stat.S_IMODE(folder.st_mode)==0o700,'NATIVE_LOG_PRIVATE_ROOT_REQUIRED')
 observed=names(root);parts=[p for p,name in FILES.items()if name in observed]
 need(observed=={INDEX}|{FILES[p]for p in parts}and len(parts)>=2 and parts==list(range(1,max(parts)+1)),'NATIVE_LOG_PART_SET_UNCOVERED')
 # Read the index first, so later part reads contain every committed prefix.
 index,index_pin=sample(root/INDEX,16*1024**2);bodies={};pins={}
 for part in parts:bodies[part],pins[str(part)]=sample(root/FILES[part],LIMIT)
 active=max(parts)
 if require_headroom and active==8:need(LIMIT-pins['8']['bytes']>=HEADROOM,'NATIVE_LOG_FINAL_SLOT_HEADROOM_LOW')
 complete=index.splitlines(keepends=True)
 if complete and not complete[-1].endswith(b'\n'):complete.pop()
 rows=[json.loads(line)for line in complete];need(rows and all(type(r)is dict and r.get('schemaVersion')==1 and r.get('part')in parts for r in rows),'NATIVE_LOG_INDEX_PART_SET_UNCOVERED')
 hashes={p:hashlib.sha256()for p in parts};offsets={p:0 for p in parts};last={};contexts=set();sequence=0;seen=[]
 for row in rows:
  part=row['part'];size=row.get('bytes');need(row.get('file')==FILES[part]and type(size)is int and offsets[part]<=size<=len(bodies[part]),'NATIVE_LOG_INDEX_PREFIX_SIZE_INVALID')
  if not seen or seen[-1]!=part:need(part==len(seen)+1,'NATIVE_LOG_INDEX_PART_ORDER_INVALID');seen.append(part)
  segment=bodies[part][offsets[part]:size];hashes[part].update(segment);need(hashes[part].hexdigest()==row.get('sha256'),'NATIVE_LOG_INDEX_PREFIX_HASH_MISMATCH')
  for line in segment.splitlines():
   value=json.loads(line);need(type(value.get('sequence'))is int and value['sequence']==sequence+1,'NATIVE_LOG_SEQUENCE_DISCONTINUITY');sequence=value['sequence']
  need(type(row.get('first'))is dict and type(row.get('last'))is dict and row['last'].get('sequence')==sequence,'NATIVE_LOG_INDEX_SEQUENCE_MISMATCH')
  if part in last:need(row['first']==last[part]['first'],'NATIVE_LOG_FIRST_SEQUENCE_CHANGED')
  else:need(row['first'].get('sequence')==sequence-len(segment.splitlines())+1,'NATIVE_LOG_INDEX_FIRST_MISMATCH')
  offsets[part]=size;last[part]=row;contexts.add((row.get('contextSha256'),row.get('sourceSha256')))
 need(seen==parts and len(contexts)==1,'NATIVE_LOG_ROTATION_CONTEXT_CHANGED')
 for part in parts:
  row=last[part];need(row.get('closed')is(part!=active),'NATIVE_LOG_CLOSED_STATE_CHANGED')
  if part!=active:need(offsets[part]==len(bodies[part]),'NATIVE_LOG_CLOSED_PART_GREW')
 if expected is not None:
  need(set(expected['parts'])<=set(pins)and expected['index']['identity']==index_pin['identity'],'NATIVE_LOG_BASELINE_PART_SET_CHANGED')
  for number,pin in expected['parts'].items():
   body=bodies[int(number)];need(pins[number]['identity']==pin['identity']and len(body)>=pin['bytes']and hashlib.sha256(body[:pin['bytes']]).hexdigest()==pin['sha256'],'NATIVE_LOG_BASELINE_PREFIX_CHANGED')
  pin=expected['index'];need(len(index)>=pin['bytes']and hashlib.sha256(index[:pin['bytes']]).hexdigest()==pin['sha256'],'NATIVE_LOG_INDEX_BASELINE_CHANGED')
 need(names(root)==observed and identity(root.lstat())==identity(folder),'NATIVE_LOG_PART_SET_CHANGED_DURING_READ')
 return{'schemaVersion':1,'scope':'FIXED_NATIVE_TIMELINE_SLOTS_1_THROUGH_8_PREFIX_COVERAGE_NOT_DEVICE_ACCEPTANCE','partSet':[FILES[p]for p in parts],'parts':pins,'index':index_pin,'activePart':active,'activePartRemainingBytes':LIMIT-pins[str(active)]['bytes'],'headroomRequired':require_headroom}
