"""Original auxiliary queries used by whole Tablet setup and retirement.

The native DTOs retain their own grammar, nonces and source histories. This
owner saves actual queries before send and matching safe bytes before PID/run/
prefix interpretation. No ACK is a Script, file-absence or input-drain fact.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import time
from adapters.native_feature_observation import decode,exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.original_frame_store import OriginalFrameStore
from adapters.original_packet_segments import OriginalPacketSegments,CHUNK_BYTES,MAX_FRAMES
from adapters.operation_transport_guard import scope as transport_scope
from adapters.script_feature.history import pack,unpack,canonical,same
from adapters.script_feature.lock import ScriptSourceLock
from adapters import native_script_files as files,native_script_observation as scripts,native_script_terminal as terminal,native_feature_observation as native
from ios.adapters import world_web_keys as keys,pointer_state as pointer,script_dialogs as dialogs,native_geometry as geometry
from feature_journeys.contract import identifier

VERSION=1
KINDS=('files','scripts','terminal','keys','pointer','dialogs','geometry','native','widgets','diagnostic','defer')
SUBJECTS={'files':'record','diagnostic':'http','defer':'work',**{kind:kind for kind in KINDS if kind not in ('files','diagnostic','defer')}}
LIMITS={'files':files.LIMIT,'scripts':1048576,'terminal':terminal.LIMIT,'keys':keys.LIMIT,'pointer':pointer.LIMIT,'dialogs':dialogs.LIMIT,'geometry':65536,'native':native.LIMIT,'widgets':98304,'diagnostic':65536,'defer':2097152}
ACTIONS=dict(files='feature-script-files',scripts='feature-script-observe',terminal=terminal.ACTION,keys=keys.ACTION,
    pointer=pointer.ACTION,dialogs=dialogs.ACTION,geometry='native-geometry-snapshot',native='feature-native-observe',widgets='normal-ui-input',diagnostic='normal-feature-observe',defer='feature-ios-tablet-web-defer')


class Parts(OriginalPacketSegments):PROFILE='tabletweb-sources'


def query(kind,value,run=None):
    need(kind in KINDS)
    if kind=='defer':
        from ios.adapters.tablet_web_deferred import command
        command(value,operation=True)
        if run is not None:need(value['runId']==run)
    elif kind=='diagnostic':
        exact(value,{'schemaVersion','commandId','action','includeAvatarEntities'});need(value['includeAvatarEntities'] is False)
        query('geometry',{key:item for key,item in dict(value,action='native-geometry-snapshot').items() if key!='includeAvatarEntities'})
    elif kind=='widgets':
        exact(value,{'schemaVersion','commandId','action','operation'})
        need(value['operation']=='observe');query('geometry',{key:item for key,item in dict(value,action='native-geometry-snapshot').items() if key!='operation'})
    elif kind=='files':files.command(value,ios=True)
    elif kind=='terminal':terminal.command(value,ios=True)
    elif kind in ('keys','pointer','dialogs'):
        dict(keys=keys,pointer=pointer,dialogs=dialogs)[kind].command(value)
        if run is not None:need(value['runId']==run)
    else:
        import re
        exact(value,{'schemaVersion','action','commandId'});need(type(value['schemaVersion']) is int and value['schemaVersion']==1
            and type(value['commandId']) is str and re.fullmatch('ios-[0-9a-f]{32}',value['commandId']))
    need(value['action']==ACTIONS[kind]);return value


def request_id(kind,packet):
    return packet.get('command',{}).get('commandId') if kind=='defer' else packet.get('commandId' if kind in ('terminal','geometry','widgets') else 'requestId')


def original(kind,packet,request):
    """Closed safe shape before storing bytes; expected PID/run joins follow."""
    query(kind,request)
    if kind=='defer':
        from ios.adapters.tablet_web_deferred import receipt
        receipt(packet,packet['command'],packet['instance'],None)
    elif kind=='diagnostic':
        from adapters.normal_script_manager import diagnostic
        diagnostic(packet,packet['sampleEpochMs']);need('requestId' in packet and not {'avatarEntities','entitiesComplete'}&set(packet))
    elif kind=='widgets':
        from ios.adapters.normal_input import observation
        exact(packet,{'schemaVersion','commandId','observation'})
        need(type(packet['schemaVersion']) is int and packet['schemaVersion']==1)
        query('widgets',dict(request,commandId=packet['commandId']))
        body=packet['observation'];observation(body,body['processId'],body['sampleEpochMs'])
    elif kind=='files':
        exact(packet,{'schemaVersion','requestId','instance','sequence','requestedEpochMs','capturedEpochMs','processId','runId','operation','source'})
        need(type(packet['schemaVersion']) is int and packet['schemaVersion']==1 and integer(packet['processId'],1)
            and integer(packet['sequence'],1) and integer(packet['requestedEpochMs'],1)
            and integer(packet['capturedEpochMs'],packet['requestedEpochMs'],packet['requestedEpochMs']+5000))
        identifier(packet['instance']);identifier(packet['runId']);identifier(packet['requestId'][4:])
        need(packet['requestId'].startswith('ios-') and packet['operation'] in ('stage','observe','release','locate'))
        files.NativeScriptFiles.validate_source(packet['source'],packet['operation'],packet['runId'])
    elif kind=='native':native.validate(packet,packet['requestId'],packet['processId'],packet['capturedEpochMs'])
    elif kind=='scripts':
        scripts.validate(packet,packet['requestId'],packet['processId'],packet['capturedEpochMs'])
        safe=scripts.NativeScriptObservation(lambda *_:need(False),lambda:need(False),lambda:need(False),lambda:need(False),packet['processId'],ios=True)
        safe._history_transition(packet,require_code_identity=True,require_membership=True)
    elif kind=='terminal':terminal.validate(packet,dict(request,commandId=packet['commandId']),packet['processId'],packet['capturedEpochMs'])
    elif kind=='keys':keys.privacy_qualified(packet);keys.validate(packet,dict(request,commandId=packet['requestId'],runId=packet['runId']),packet['processId'])
    elif kind=='pointer':pointer.original(packet)
    elif kind=='dialogs':dialogs.validate(packet,dict(request,commandId=packet['requestId'],runId=packet['runId']),packet['processId'])
    else:
        geometry.validate(packet,packet['commandId'],native_epoch_ms=packet['observation']['sampleEpochMs'])
        doc=packet['observation'];metrics=doc['nativeUi'];exact(doc['window'],{'width','height'})
        # Actual producer: Application_Graphics.cpp publishTouchUiMetrics.
        # The legacy viewport reader deliberately accepts wider metrics; this
        # new raw artifact owner admits only the current closed native shape.
        exact(metrics,{'valid','safeInsetLeft','safeInsetTop','safeInsetRight','safeInsetBottom','imeInsetBottom',
            'keyboardVisible','surfaceWidth','surfaceHeight','density','fontScale'})
        need(type(doc['schemaVersion']) is int and doc['schemaVersion']==1 and integer(doc['sampleEpochMs'],1)
            and type(metrics['valid']) is type(metrics['keyboardVisible']) is bool)
        need(all(number(metrics[name],0,10000) for name in metrics if name not in ('valid','keyboardVisible')))
    return packet


def joined(kind,packet,request,pid,run,previous=None):
    original(kind,packet,request);need(request_id(kind,packet)==request['commandId'])
    if kind=='widgets':need(packet['observation']['processId']==pid)
    elif kind not in ('geometry','diagnostic','defer'):need(type(packet['processId']) is int and packet['processId']==pid)
    if kind=='defer':need(packet['command']==request)
    elif kind=='files':need(packet['operation']==request['operation'] and packet['runId']==request['runId'])
    elif kind in ('keys','pointer','dialogs'):need(packet['runId']==run)
    if previous is None:return packet
    if kind=='defer':
        need(packet['instance']==previous['instance'] and packet['sequence']>previous['sequence'] and packet['issued']['epochMs']>=(previous['completed'] or previous['issued'])['epochMs'])
    elif kind=='diagnostic':
        need(packet['instance']==previous['instance'] and packet['sampleSequence']>previous['sampleSequence'] and packet['sampleEpochMs']>=previous['sampleEpochMs'])
    elif kind=='widgets':
        old,current=previous['observation'],packet['observation']
        need(current['instance']==old['instance'] and current['lastSequence']>=old['lastSequence']
            and current['sampleEpochMs']>=old['sampleEpochMs'] and current['elapsedMs']>=old['elapsedMs'])
        if 'scriptInventory' in old:
            need('scriptInventory' in current and current['scriptSourceSequence']>=old['scriptSourceSequence'])
            if old['scriptInventory']['inventoryVersion']==2:
                need(current['scriptInventory']['inventoryVersion']==2)
                from adapters.script_ui_root_ownership import validate as roots
                roots(current['scriptInventory']['rootOwnership'],pid=pid,epoch=current['sampleEpochMs'],previous=old['scriptInventory']['rootOwnership'])
    elif kind=='native':
        from ios.adapters.graphics_history import follow_native
        follow_native(previous,packet)
    elif kind in ('keys','pointer','dialogs'):
        dict(keys=keys,pointer=pointer,dialogs=dialogs)[kind].validate(packet,request,pid,previous=previous)
    elif kind=='terminal':terminal.validate(packet,request,pid,packet['capturedEpochMs'],previous=previous)
    elif kind=='geometry':
        a,b=previous['observation'],packet['observation']
        need(b['sampleSequence']>a['sampleSequence'] and b['sampleEpochMs']>=a['sampleEpochMs'])
    else:
        need(previous['instance']==packet['instance'] and packet['sequence']>previous['sequence']
            and packet['requestedEpochMs']>=previous['capturedEpochMs'])
        if kind=='scripts':
            history=scripts.NativeScriptObservation(lambda *_:need(False),lambda:need(False),lambda:need(False),lambda:need(False),pid,ios=True)
            transition=history._history_transition(previous,require_code_identity=True,require_membership=True);history._commit_history(previous,transition)
            history._history_transition(packet,require_code_identity=True,require_membership=True)
    return packet


class TabletNativeReads:
    def __init__(self,root,binding,run,role,kind,lock,guard,*,epoch_ms=lambda:int(time.time()*1000),monotonic=time.monotonic,historical=False):
        self.root,self.binding,self.run,self.role,self.kind=Path(root),deepcopy(context(binding)),identifier(run),role,kind
        need(kind in KINDS and role in ('primary','actor') and isinstance(lock,ScriptSourceLock)
            and lock.path==self.root/'script-feature-sources.lock' and type(historical) is bool)
        self.lock,self.guard,self.epoch_ms,self.monotonic,self.historical=lock,guard,epoch_ms,monotonic,historical
        need(all(callable(fn) for fn in (guard,epoch_ms,monotonic)))
        self.store=PrivateFeatureState(self.root/('tabletweb-aux-'+kind+'-'+run+'-'+role+'.json'))
        value=self.store.read();self.saved=deepcopy(value)
        if value is None:
            self.live();self.state=dict(records=[],pending=None,nextRaw=1,original=None);self.save()
        else:
            exact(value,{'tabletWebNativeReadsVersion','binding','runId','role','kind','payload'})
            need(type(value['tabletWebNativeReadsVersion']) is int and value['tabletWebNativeReadsVersion']==VERSION
                and same(value['binding'],binding) and value['runId']==run and value['role']==role and value['kind']==kind)
            rows=unpack(value['payload']);need(len(rows)==1);self.state=rows[0]
        self.parts=Parts(root,binding,run,role,SUBJECTS[kind],self.file_guard,self.part_intent,monotonic=monotonic)
        self.frames=OriginalFrameStore(root,binding,run,role,self.file_guard,self.frame_intent,
            namespace='tabletweb-aux-'+kind,schema_prefix='tabletWebAux'+kind.title(),monotonic=monotonic)
        self.history()

    def live(self):need(not self.historical);self.lock.assert_held();need(self.guard() is not False)
    def file_guard(self):
        if not self.historical:self.lock.assert_held()
        return True
    def save(self):
        self.live();value=dict(tabletWebNativeReadsVersion=VERSION,binding=self.binding,runId=self.run,role=self.role,kind=self.kind,payload=pack([self.state]))
        self.store.write(value,self.saved);self.saved=deepcopy(value)
    def clock(self):
        value=dict(epochMs=self.epoch_ms(),monotonic=self.monotonic());need(integer(value['epochMs'],1) and number(value['monotonic'],0,1e15));return value
    def part_intent(self,value):
        self.live();pending=self.state['pending'];need(pending is not None and pending['raws'] and pending['raws'][-1]['outcome']=='unchecked')
        pending['raws'][-1]['parts']=deepcopy(value);self.save()
    def frame_intent(self,kind,value):
        self.live();need(kind=='original' and self.state['pending'] is not None);self.state['original']=deepcopy(value);self.save()
    def authority(self,row):
        if self.kind!='defer':need(row['authority'] is None);return None
        from ios.adapters.tablet_web_packets import TabletWebPackets
        actual=row['authority'];exact(actual,{'fixtureUrl','reference'})
        owner=TabletWebPackets(self.root,self.binding,self.run,self.role,actual['fixtureUrl'],int(self.binding['processIdentity']),
            'deferred',lambda:need(False),monotonic=self.monotonic,epoch_ms=lambda:need(False),historical=True)
        full=owner.originals.expand(actual['reference']);index=full['index']
        need(1<=index<=len(owner.state['records']) and same(owner.state['records'][index-1],actual['reference']))
        record=owner.originals.read(full);need(record['status']=='returned')
        _floor,packets=owner.record(record,index,None);need(packets);return packets[-1]

    def joined(self,row,packet,previous):
        joined(self.kind,packet,row['query'],int(self.binding['processIdentity']),self.run,previous)
        if self.kind=='defer':
            from ios.adapters.tablet_web_deferred import receipt
            from ios.adapters.tablet_web_sources import stamp
            before=self.authority(row);need(row['query']['fixtureUrl']==before['fixtureUrl'])
            receipt(packet,row['query'],before['instance'],None);stamp(packet['issued'],floor=before['clockAfter'])
            if row['query']['operation']!='arm':need(any(item['id']==row['query']['recordId'] for item in before['records']))
        return packet

    def record(self,row,index,previous):
        from ios.adapters.tablet_web_record_cache import auxiliary_record
        return auxiliary_record(self,row,index,previous,lambda:self._record(row,index,previous))

    def _record(self,row,index,previous):
        exact(row,{'tabletWebAuxQueryVersion','index','kind','status','query','authority','before','after','sendReturned','raws','unsafe','resultSha256','failure','readbacks'})
        need(type(row['tabletWebAuxQueryVersion']) is int and row['tabletWebAuxQueryVersion']==VERSION and type(row['index']) is int and row['index']==index
            and row['kind']==self.kind and row['status'] in ('preparing','issued','returned','reconciled','failed') and type(row['sendReturned']) is bool
            and type(row['raws']) is list and len(row['raws'])<=16 and type(row['unsafe']) is list and len(row['unsafe'])<=16)
        for stamp in (row['before'],row['after']):
            if stamp is not None:exact(stamp,{'epochMs','monotonic'});need(integer(stamp['epochMs'],1) and number(stamp['monotonic'],0,1e15))
        if row['after'] is not None:need(row['after']['epochMs']>=row['before']['epochMs'] and row['after']['monotonic']>=row['before']['monotonic'])
        need(type(row['readbacks']) is list and len(row['readbacks'])<=8)
        if row['failure'] is None:need(not row['readbacks'] and row['status']!='reconciled')
        else:
            failure=row['failure'];exact(failure,{'status','after','sendReturned','resultSha256'})
            need(failure['status']=='failed' and same(failure['after'],row['after']) and failure['sendReturned']==row['sendReturned']
                and type(failure['sendReturned']) is bool and failure['resultSha256'] is None and row['after'] is not None)
        clock=row['after'] or row['before'];floor=0
        for readback in row['readbacks']:
            exact(readback,{'mode','status','before','after','startRaw'})
            need(readback['mode'] in ('afc','retained') and readback['status'] in ('issued','returned','failed')
                and integer(readback['startRaw'],floor,len(row['raws'])));floor=readback['startRaw']
            for stamp in (readback['before'],readback['after']):
                if stamp is not None:exact(stamp,{'epochMs','monotonic'});need(integer(stamp['epochMs'],1) and number(stamp['monotonic'],0,1e15))
            need(readback['before'] is not None and readback['before']['epochMs']>=clock['epochMs'] and readback['before']['monotonic']>=clock['monotonic'])
            if readback['after'] is not None:
                need(readback['after']['epochMs']>=readback['before']['epochMs'] and readback['after']['monotonic']>=readback['before']['monotonic'])
            need(readback['status']=='issued' or readback['after'] is not None);clock=readback['after'] or readback['before']
        if row['query'] is None:need(not row['raws'] and not row['sendReturned'])
        else:query(self.kind,row['query'],self.run)
        self.authority(row)
        accepted=[]
        for ref in row['raws']:
            exact(ref,{'parts','inspection','outcome'});need(ref['outcome'] in ('unchecked','accepted','rejected'))
            parent=ref['parts'];self.parts.parent(parent)
            need(parent['label']==SUBJECTS[self.kind] and parent['tag']==hashlib.sha256(canonical(row['query'])).hexdigest())
            inspected=self.parts.inspect(parent)
            if ref['inspection'] is not None:self.parts.retained(parent,ref['inspection'])
            complete=len(inspected)==max(1,(parent['bytes']+CHUNK_BYTES-1)//CHUNK_BYTES) and all(part is not None and part['complete'] for part in inspected)
            if not complete:need(row['status']!='returned' and ref['outcome']=='unchecked');continue
            raw=self.parts.read(parent);need(len(raw)<=LIMITS[self.kind]);packet=decode(raw.decode(),limit=LIMITS[self.kind]);original(self.kind,packet,row['query'])
            try:self.joined(row,packet,previous)
            except (ValueError,RuntimeError,KeyError,TypeError):need(ref['outcome']!='accepted');self.blocked=True
            else:need(ref['outcome']!='rejected');previous=packet;accepted.append(packet)
        for unsafe in row['unsafe']:
            exact(unsafe,{'bytes','sha256'});need(integer(unsafe['bytes'],1,LIMITS[self.kind]) and type(unsafe['sha256']) is str and len(unsafe['sha256'])==64)
        if row['unsafe']:self.blocked=True
        if row['status'] in ('returned','reconciled'):need(row['query'] is not None and (row['sendReturned'] or row['status']=='reconciled') and row['after'] is not None and accepted
            and not row['unsafe'] and row['resultSha256']==hashlib.sha256(canonical(accepted[-1])).hexdigest() and all(ref['outcome']=='accepted' for ref in row['raws']))
        else:need(row['resultSha256'] is None)
        if row['status']=='returned':need(row['failure'] is None)
        if row['status']=='reconciled':need(row['failure'] is not None and row['readbacks'] and row['readbacks'][-1]['status']=='returned')
        return previous,accepted
    def history(self):
        value=self.state;exact(value,{'records','pending','nextRaw','original'})
        need(type(value['records']) is list and len(value['records'])<=128 and integer(value['nextRaw'],1,MAX_FRAMES+1))
        self.blocked=False;previous=None;values=[];floor=1;queries=set();clock=None
        rows=[]
        for index,ref in enumerate(value['records'],1):
            full=self.frames.expand(ref);need(full['index']==index);row=self.frames.read(full);need(row['status'] in ('returned','reconciled'));rows.append(row)
        if value['pending'] is not None:self.blocked=True;rows.append(value['pending'])
        for index,row in enumerate(rows,1):
            previous,accepted=self.record(row,index,previous);values.extend(accepted)
            if clock is not None:need(row['before']['epochMs']>=clock['epochMs'] and row['before']['monotonic']>=clock['monotonic'])
            clock=(row['readbacks'][-1]['after'] or row['readbacks'][-1]['before']) if row['readbacks'] else row['after'] or row['before']
            if row['query'] is not None:need(row['query']['commandId'] not in queries);queries.add(row['query']['commandId'])
            for raw in row['raws']:
                need(raw['parts']['first']==floor);floor+=max(1,(raw['parts']['bytes']+CHUNK_BYTES-1)//CHUNK_BYTES)
        need(floor==value['nextRaw'])
        if value['original'] is not None:
            need(value['pending'] is not None);self.frames.original(value['original'])
            if value['original']['phase']!='planned':
                self.inspect_record()
            else:need(not os.path.lexists(self.frames.path(value['original'])))
        if self.kind=='scripts':
            history=scripts.NativeScriptObservation(lambda *_:need(False),lambda:need(False),lambda:need(False),lambda:need(False),int(self.binding['processIdentity']),ios=True)
            for packet in values:
                transition=history._history_transition(packet,require_code_identity=True,require_membership=True)
                history._commit_history(packet,transition)
        return values
    def through(self,reference):
        """A fully requalified original prefix, never the latest packet by name."""
        need(self.historical);self.history();full=self.frames.expand(reference);index=full['index']
        need(1<=index<=len(self.state['records']) and same(self.state['records'][index-1],reference))
        previous=None;values=[]
        for ordinal,ref in enumerate(self.state['records'][:index],1):
            row=self.frames.read(self.frames.expand(ref));previous,accepted=self.record(row,ordinal,previous);values.extend(accepted)
        need(values);return deepcopy(values)

    def at(self,reference):return self.through(reference)[-1]

    def inspect_record(self):
        ref=self.state['original'];self.frames.original(ref);need(ref['phase'] in ('opened','saved'))
        path=self.frames.path(ref);descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
        with os.fdopen(descriptor,'rb') as stream:
            self.frames.file(path,stream.fileno(),ref);before=os.fstat(stream.fileno());raw=stream.read(ref['bytes']+1)
            self.frames.file(path,stream.fileno(),ref);after=os.fstat(stream.fileno())
        need((before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_size,after.st_mtime_ns,after.st_ctime_ns) and len(raw)<=ref['bytes'])
        from adapters.original_file_reads import record as actual_read
        actual_read(path);complete=len(raw)==ref['bytes'] and hashlib.sha256(raw).hexdigest()==ref['sha256']
        if ref['phase']=='saved':need(complete)
        return dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),complete=complete)

    def recover_record(self):
        self.live();self.history();ref=self.state['original'];row=self.state['pending']
        need(ref is not None and ref['phase'] in ('opened','saved') and self.inspect_record()['complete'] and row['status'] in ('returned','reconciled'))
        actual=self.frames.read(ref);need(same(actual,row) and ref['index']==len(self.state['records'])+1)
        self.state['records'].append(self.frames.compact(dict(ref,phase='saved')));self.state['pending']=self.state['original']=None;self.save()
        return self.history()[-1]

    def reconcile(self,reader):
        """Read only the already-issued response; never send/replay a command.

        This is historical recovery, not a current product observation. The
        caller must acquire a new bounded query before using current facts.
        Native shutdown/weak/callback proofs remain independent obligations.
        """
        self.live();self.history();row=self.state['pending']
        need(row is not None and row['status']=='failed' and row['query'] is not None and self.state['original'] is None
            and row['after'] is not None and not row['unsafe'] and callable(reader.original))
        prior=None
        for index,ref in enumerate(self.state['records'],1):prior,_packets=self.record(self.frames.read(self.frames.expand(ref)),index,prior)
        if row['failure'] is None:row['failure']={key:deepcopy(row[key]) for key in ('status','after','sendReturned','resultSha256')};self.save()
        if row['readbacks'] and row['readbacks'][-1]['status']=='issued':
            row['readbacks'][-1].update(status='failed',after=self.clock());self.save()
        need(len(row['readbacks'])<8);mode='retained' if row['raws'] else 'afc'
        readback=dict(mode=mode,status='issued',before=self.clock(),after=None,startRaw=len(row['raws']));row['readbacks'].append(readback);self.save()
        try:
            if mode=='retained':
                _floor,accepted=self.record(row,row['index'],prior)
                need(accepted and len(accepted)==len(row['raws']))
                for ref in row['raws']:ref['outcome']='accepted'
                packet=accepted[-1]
            else:
                need(reader.guard() is not False)
                raw=reader.original();need(type(raw) is str and len(raw.encode())<=LIMITS[self.kind])
                packet=decode(raw,limit=LIMITS[self.kind]);need(type(packet) is dict and request_id(self.kind,packet)==row['query']['commandId'])
                try:original(self.kind,packet,row['query'])
                except Exception:
                    row['unsafe'].append(dict(bytes=len(raw.encode()),sha256=hashlib.sha256(raw.encode()).hexdigest()));self.save();raise
                first=self.state['nextRaw'];self.state['nextRaw']+=max(1,(len(raw.encode())+CHUNK_BYTES-1)//CHUNK_BYTES)
                need(self.state['nextRaw']<=MAX_FRAMES+1);row['raws'].append(dict(parts=None,inspection=None,outcome='unchecked'))
                self.parts.write(SUBJECTS[self.kind],hashlib.sha256(canonical(row['query'])).hexdigest(),raw.encode(),first)
                row['raws'][-1]['inspection']=self.parts.inspect(row['raws'][-1]['parts']);self.save()
                try:self.joined(row,packet,prior)
                except Exception:row['raws'][-1]['outcome']='rejected';self.save();raise
                row['raws'][-1]['outcome']='accepted'
            readback.update(status='returned',after=self.clock());row.update(status='reconciled',resultSha256=hashlib.sha256(canonical(packet)).hexdigest());self.save()
            self.record(row,row['index'],prior)
            ref=self.frames.write(row['index'],deepcopy(row));self.state['records'].append(ref);self.state['pending']=self.state['original']=None;self.save()
            self.history();return deepcopy(packet)
        except Exception:
            if self.state['original'] is None:
                readback.update(status='failed',after=self.clock());row.update(status='failed',resultSha256=None);self.save()
            raise

    def capture(self,reader,invoke,*,authority=None):
        self.live();previous=self.history();need(not self.blocked and len(self.state['records'])<128 and callable(invoke))
        if self.kind not in ('geometry','widgets'):need(reader.pid==int(self.binding['processIdentity']))
        row=dict(tabletWebAuxQueryVersion=VERSION,index=len(self.state['records'])+1,kind=self.kind,status='preparing',query=None,authority=deepcopy(authority),
            before=self.clock(),after=None,sendReturned=False,raws=[],unsafe=[],resultSha256=None,failure=None,readbacks=[])
        self.authority(row)
        self.state['pending']=row;self.save();send,read=reader.send,reader.original;last=previous[-1] if previous else None;stored=[]
        def issued(request):
            query(self.kind,request,self.run);need(row['query'] is None);row.update(status='issued',query=deepcopy(request));self.save()
            result=send(request)
            if self.kind!='widgets':row['sendReturned']=True;self.save()
            return result
        def received():
            nonlocal last
            raw=read()
            if not raw:return raw
            need(type(raw) is str and len(raw.encode())<=LIMITS[self.kind]);packet=decode(raw,limit=LIMITS[self.kind])
            if type(packet) is not dict or request_id(self.kind,packet)!=row['query']['commandId']:return raw
            try:original(self.kind,packet,row['query'])
            except Exception:
                row['unsafe'].append(dict(bytes=len(raw.encode()),sha256=hashlib.sha256(raw.encode()).hexdigest()));self.save();raise
            if stored and same(stored[-1],packet):return raw
            first=self.state['nextRaw'];self.state['nextRaw']+=max(1,(len(raw.encode())+CHUNK_BYTES-1)//CHUNK_BYTES)
            need(self.state['nextRaw']<=MAX_FRAMES+1);row['raws'].append(dict(parts=None,inspection=None,outcome='unchecked'))
            self.parts.write(SUBJECTS[self.kind],hashlib.sha256(canonical(row['query'])).hexdigest(),raw.encode(),first)
            row['raws'][-1]['inspection']=self.parts.inspect(row['raws'][-1]['parts']);self.save()
            try:self.joined(row,packet,last)
            except Exception:row['raws'][-1]['outcome']='rejected';self.save();raise
            row['raws'][-1]['outcome']='accepted';last=deepcopy(packet);stored.append(deepcopy(packet));self.save();return raw
        reader.send,reader.original=issued,received;started=previous_time=self.monotonic()
        def transport():
            nonlocal previous_time
            now=self.monotonic();need(number(now,previous_time,1e15) and now-started<1.5);previous_time=now
        try:
            with transport_scope(transport):result=invoke(reader)
            need(stored and same(stored[-1]['source'] if self.kind=='files' else stored[-1]['observation'] if self.kind=='widgets' else stored[-1],result))
            if self.kind=='widgets':row['sendReturned']=True  # actual HTTP+SDK path returned
            row.update(status='returned',after=self.clock(),resultSha256=hashlib.sha256(canonical(stored[-1])).hexdigest());self.save()
            self.record(row,row['index'],previous[-1] if previous else None)
            ref=self.frames.write(row['index'],deepcopy(row));self.state['records'].append(ref);self.state['pending']=self.state['original']=None;self.save()
            self.history();return deepcopy(stored[-1])
        except Exception:
            if self.state['original'] is None:
                row.update(status='failed',resultSha256=None,after=self.clock())
                for ref in row['raws']:
                    if ref['parts'] is not None:ref['inspection']=self.parts.inspect(ref['parts'])
                self.save()
            raise
        finally:reader.send,reader.original=send,read
