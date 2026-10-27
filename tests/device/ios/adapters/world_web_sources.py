"""Durable original Web/native/DOM/VM/world reads on one guarded iOS app.

The actor owns independent readers. No normalized primary facts are accepted.
Interrupted passive acquisitions retain their native queries and partial raw
originals; recovery starts a distinct read and never replays an input.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import contextmanager
import time
import os
import stat
from adapters.native_clock_join import NativeClockAcquisition,digest,validate_join
from adapters.native_feature_observation import NativeFeatureObservation,exact,integer,need
from adapters.operation_transport_guard import scope as transport_scope
from ios.adapters.emote_original_lease import EmoteOriginalLease
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.original_marker_clock_queries import owned as clock_owned,queries as clock_queries,bracket as clock_bracket
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from feature_journeys.phase_fixture import PhaseFixtureReader,validate as phase_packet
from ios.adapters import world_web_source as ledger,world_web_dom as dom,world_web_work as work,world_web_geometry as geometry
from ios.adapters import emote_world as world
from ios.adapters.world_web_history import current_view
from ios.adapters.world_web_measurements import browser_original,current_document
from ios.adapters.graphics_history import follow_native
from adapters.native_clock_source_history import restore as restore_unbound_native
from ios.adapters.world_web_api_clock import check as api_check
from ios.adapters.world_web_parts import NAMES as LEGACY_NAMES
from ios.adapters.world_web_original_parts import WorldWebOriginalParts
from ios.adapters import world_web_snapshot as snapshot,world_web_whole_snapshot as whole_snapshot,web_script_emissions as emissions
from ios.adapters.native_geometry import OriginalGeometry,validate as uikit_packet
from ios.adapters.normal_input import NativeInput,observation as widgets_packet
from ios.adapters import world_web_keys as keys,pointer_state as pointer,create_entities as entities

from ios.adapters import world_web_surfaces as surfaces,web_closures as closures

NAMES=LEGACY_NAMES|{'surfaces','closures'}
VERSION=5
READS=(3,4,5)
MAX_FRAMES=256


class WorldWebSources:
    PROFILE='worldweb'

    def __init__(self,store,lock,binding,run,role,guard,*,phase,readers=None,historical=False,
                 epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic):
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock) and type(historical) is bool
            and role in ('primary','actor','actor-primary') and all(callable(fn) for fn in (guard,epoch_ms,monotonic)))
        self.store,self.lock,self.binding,self.run,self.role=store,lock,deepcopy(context(binding)),identifier(run),role
        self.guard,self.phase,self.readers,self.historical,self.epoch_ms,self.monotonic=guard,phase,readers,historical,epoch_ms,monotonic
        self.pid=int(binding['processIdentity']);need(self.pid>0 and str(self.pid)==binding['processIdentity']
            and store.path.name=='ios-world-web-'+role+'-sources.json' and lock.path==store.path.with_name('script-feature-sources.lock'))
        self.version=5 if not historical and isinstance(readers.get('snapshot'),whole_snapshot.IOSWorldWebWholeSnapshot) else 4 if not historical and 'snapshot' in readers else 3
        if not historical:
            need(isinstance(phase,PhaseFixtureReader) and phase.run==run and phase.area=='world-web'
                and set(readers)-{'snapshot','surfaces','closures'}=={'native','ledger','document','work','world','geometry','uikit','widgets','keys','pointer','entities'}
                and ('snapshot' not in readers and 'surfaces' not in readers and 'closures' not in readers or isinstance(readers.get('snapshot'),snapshot.IOSWorldWebSnapshot) and isinstance(readers.get('surfaces'),surfaces.IOSWorldWebSurfaces) and isinstance(readers.get('closures'),closures.IOSWebClosures))
                and isinstance(readers['native'],NativeFeatureObservation) and readers['native'].ios and not readers['native'].native_clock_bound
                and isinstance(readers['ledger'],ledger.IOSWorldWebSource) and isinstance(readers['document'],dom.IOSWorldWebDOM)
                and isinstance(readers['work'],work.IOSWorldWebWork) and isinstance(readers['world'],world.IOSEmoteWorld)
                and isinstance(readers['geometry'],geometry.IOSWorldWebGeometry) and isinstance(readers['uikit'],OriginalGeometry)
                and isinstance(readers['widgets'],NativeInput)
                and isinstance(readers['keys'],keys.IOSWorldWebKeys) and isinstance(readers['pointer'],pointer.IOSPointerState)
                and isinstance(readers['entities'],entities.IOSCreateEntities)
                and all(reader.pid==self.pid for name,reader in readers.items() if name not in ('uikit','widgets')))
            self.native=readers['native']
        lock.assert_held();self.previous=store.read();self.frames=[];self._cache={};self._round=None;self._round_pins=None;self._write_round=None;self._round_header=None;self.parts=WorldWebOriginalParts(self);self.state=dict(records=[],pending=None,interrupted=[])
        if self.previous is not None:
            if historical:self.version=self.previous['iosWorldWebSourcesVersion']
            self.state,self.frames=self.decode(self.previous)
        self._saved_records=deepcopy(self.state['records']);self._round_state_sha=None
        self._remember_aux_prefix()
        if not historical and self.frames:
            last=self.frames[-1];raw=last['originals'];restore_unbound_native(self.native,last['clockJoin']['nativeAfter'])
            readers['ledger'].last=deepcopy(raw['ledgerAfter']);readers['work'].last=deepcopy(raw['work'])
            readers['world'].last=deepcopy(raw['world']);readers['geometry'].last=deepcopy(raw['geometry'])
            for name in ('keys','pointer','entities'):readers[name].last=deepcopy(raw[name])
            docs=[frame['originals']['document'] for frame in self.frames if frame['originals']['document'] is not None]
            if docs:readers['document'].last=deepcopy(docs[-1])
            if self.version>=4:
                readers['snapshot'].last=self.parts.snapshot.packet(last['nativeSnapshot']);readers['surfaces'].last=deepcopy(raw['surfaces']);readers['closures'].last=deepcopy(raw['closures'])
            phase.previous=deepcopy(last['phaseAfter'])

    def envelope(self,state):
        return dict(iosWorldWebSourcesVersion=self.version,binding=self.binding,runId=self.run,role=self.role,payload=pack([state]))

    def record_store(self,index):
        need(integer(index,1,MAX_FRAMES));return PrivateFeatureState(self.store.path.with_name('ios-world-web-'+self.role+'-sources-'+str(index)+'.json'))

    def validate_browser(self,value,*,retired,previous=None):
        browser_original(value,previous)
        if self.version==5:
            need(value['browserFixtureVersion']==(2 if retired else 1))
            if retired:need(value['retirement']['runId']==self.run)

    def validate_frame(self,frame,previous=None):
        exact(frame,{'index','label','ticket','phaseBefore','phaseAfter','originals','clockJoin','nativeQueries','widgetQueries','clockFloors'}|({'nativeSnapshot','snapshotQueries','surfaceQueries','closureQueries'} if self.version>=4 else set())|({'geometryQueries'} if self.version==5 else set()))
        need(integer(frame['index'],1,MAX_FRAMES) and type(frame['label']) is str and 1<=len(frame['label'])<=64);identifier(frame['ticket'])
        raw=frame['originals'];exact(raw,(NAMES|{'emissions'} if self.version==5 else NAMES) if self.version>=4 else LEGACY_NAMES)
        join=validate_join(frame['clockJoin'],raw);first,last=join['nativeBefore'],join['nativeAfter'];epoch=last['capturedEpochMs']
        need(first['processId']==last['processId']==self.pid and same(first['lifecycle'],last['lifecycle']))
        clock_bracket(self.PROFILE,frame,self.pid);clock_queries(frame['nativeQueries'],self.pid);self.clock_floors(frame)
        old=None if previous is None else previous['originals'];before,after=raw['ledgerBefore'],raw['ledgerAfter']
        for packet,prior in ((before,None if old is None else old['ledgerAfter']),(after,before)):
            ledger.validate(packet,dict(schemaVersion=1,commandId=packet['commandId'],action=ledger.ACTION,runId=self.run,fixtureUrl=self.phase.fixture_url),self.pid,epoch,prior)
            need(packet['complete'])
        for name,module in (('world',world),('geometry',geometry),('work',work),('keys',keys),('entities',entities))+((('surfaces',surfaces),) if self.version>=4 else ()):
            packet=raw[name];module.validate(packet,dict(schemaVersion=1,commandId=packet['requestId'],action=module.ACTION,runId=self.run),
                self.pid,epoch,None if old is None else old[name])
        if self.version>=4:
            packet=raw['closures'];closures.validate(packet,dict(schemaVersion=1,commandId=packet['commandId'],action='feature-ios-web-closures',runId=self.run,fixtureUrl=self.phase.fixture_url),self.pid,epoch)
            need(packet['iosWebClosureVersion']==5 and packet['complete'])
            if old is not None:closures.continuity(old['closures'],packet,self.pid)
        p=raw['pointer'];pointer.validate(p,dict(schemaVersion=1,commandId=p['requestId'],action=pointer.ACTION,runId=self.run),self.pid,
            previous=None if old is None else old['pointer'])
        keys.privacy_qualified(raw['keys'])
        need(raw['work']['source']['complete'] and raw['geometry']['source']['tree']==raw['world']['source']['tree'])
        document=raw['document'];current=current_view(after)
        if document is not None:
            # decode supplies its already-validated predecessor independently;
            # a previous latest DOM is sufficient only when its document source
            # is the immediately preceding frame. Historical same-doc joins are
            # independently enforced by the full public history decoder.
            prior=None if old is None else old['document']
            dom.validate(document,dict(schemaVersion=1,commandId=document['commandId'],action=dom.ACTION,runId=self.run,fixtureUrl=self.phase.fixture_url),
                self.pid,epoch,prior)
            need(current is not None and ledger.document_key(current)==ledger.document_key(document['source']['nativeView']))
        else:need(current is None)
        self.validate_browser(raw['browser'],retired=frame['phaseBefore']['active'] is False,previous=None if old is None else old['browser'])
        ui,_viewport=uikit_packet(raw['uikit'],raw['uikit']['commandId'],native_epoch_ms=epoch)
        widgets_packet(raw['widgets'],self.pid,epoch)
        self.widget_queries(frame['widgetQueries']);need(len(frame['widgetQueries'])==1)
        receipt=raw['widgetReceipt'];exact(receipt,{'schemaVersion','commandId','observation'})
        need(type(receipt['schemaVersion']) is int and receipt['schemaVersion']==1
            and receipt['commandId']==frame['widgetQueries'][0]['commandId'] and same(receipt['observation'],raw['widgets']))
        times=[first['capturedEpochMs'],before['clockBefore']['epochMs'],before['clockAfter']['epochMs'],raw['world']['clockBefore']['epochMs'],
            raw['world']['clockAfter']['epochMs'],raw['work']['clockBefore']['epochMs'],raw['work']['clockAfter']['epochMs']]
        if document is not None:times.extend([document['source']['dom']['capturedEpochMs'],document['capturedEpochMs']])
        times.extend([raw['widgets']['sampleEpochMs'],ui['sampleEpochMs'],raw['geometry']['clockBefore']['epochMs'],raw['geometry']['clockAfter']['epochMs'],
            raw['keys']['clockBefore']['epochMs'],raw['keys']['clockAfter']['epochMs'],p['clockBefore']['epochMs'],p['clockAfter']['epochMs'],
            raw['entities']['clockBefore']['epochMs'],raw['entities']['clockAfter']['epochMs'],after['clockBefore']['epochMs'],after['clockAfter']['epochMs'],epoch])
        if self.version==5:
            packet=raw['emissions'];emissions.validate(packet,dict(schemaVersion=1,commandId=packet['commandId'],action=emissions.ACTION,runId=self.run,fixtureUrl=self.phase.fixture_url),self.pid,epoch,None if old is None else old['emissions'])
            need(packet['complete'])
        if self.version>=4:
            module=whole_snapshot if self.version==5 else snapshot
            native=self.parts.snapshot.packet(frame['nativeSnapshot']);self.parts.snapshot.matches(frame['nativeSnapshot'],{name:raw[name] for name in module.ACTIONS})
            self.snapshot_queries(frame['snapshotQueries']);need(len(frame['snapshotQueries'])==1 and frame['snapshotQueries'][0]['commandId']==native['commandId'])
            self.surface_queries(frame['surfaceQueries']);need(frame['surfaceQueries']==[] if self.version==5 else len(frame['surfaceQueries'])==1 and frame['surfaceQueries'][0]['commandId']==raw['surfaces']['requestId'])
            self.closure_queries(frame['closureQueries']);need(frame['closureQueries']==[] if self.version==5 else len(frame['closureQueries'])==1 and frame['closureQueries'][0]['commandId']==raw['closures']['commandId'])
            if self.version==5:
                self.geometry_queries(frame['geometryQueries']);need(len(frame['geometryQueries'])==1 and frame['geometryQueries'][0]['commandId']==raw['uikit']['commandId'])
            times=[first['capturedEpochMs'],native['clockBefore']['epochMs'],before['clockBefore']['epochMs'],before['clockAfter']['epochMs']]
            if document is not None:times.extend([document['source']['dom']['capturedEpochMs'],document['capturedEpochMs']])
            for name in ('world','work','geometry','keys','pointer','entities','ledgerAfter'):times.extend([raw[name]['clockBefore']['epochMs'],raw[name]['clockAfter']['epochMs']])
            times.extend([raw['surfaces']['clockBefore']['epochMs'],raw['surfaces']['clockAfter']['epochMs'],raw['closures']['capturedEpochMs'],raw['emissions']['clockBefore']['epochMs'],raw['emissions']['clockAfter']['epochMs'],native['clockAfter']['epochMs'],raw['widgets']['sampleEpochMs'],ui['sampleEpochMs'],epoch] if self.version==5 else [native['clockAfter']['epochMs'],raw['widgets']['sampleEpochMs'],ui['sampleEpochMs'],raw['surfaces']['clockBefore']['epochMs'],raw['surfaces']['clockAfter']['epochMs'],raw['closures']['capturedEpochMs'],epoch])
        need(times==sorted(times))
        a,b=frame['phaseBefore'],frame['phaseAfter']
        phase_packet(a,run=self.run,area='world-web',request=a['requestId'],epoch=join['hostBeforeEpochMs'],previous=None if previous is None else previous['phaseAfter'])
        phase_packet(b,run=self.run,area='world-web',request=b['requestId'],epoch=join['hostAfterEpochMs'],previous=a)
        final=self.version>=4 and frame['label']=='final-fence'
        need((a['active'] if not final else not a['active'] and not b['active']
                and a['activations'][-1]['stimulus']==dict(verb='cleanup',inputs={}))
            and a['activations'] and a['activations'][-1]['ticket']==frame['ticket']
            and a['activations'][-1]['activatedEpochMs']<=join['hostBeforeEpochMs'])
        if previous is not None:
            need(frame['index']==previous['index']+1 and join['hostBeforeMonotonic']>=previous['clockJoin']['hostAfterMonotonic'])
            follow_native(previous['clockJoin']['nativeAfter'],first)
        return b['active'] and b['activations'][-1]['ticket']==frame['ticket']

    def decode(self,value):
        with self.parts.snapshot.validation_round():return self._decode(value,copy_frames=True)

    def _decode(self,value,*,copy_frames):
        with self.parts.snapshot.validation_round():return self._decode_frames(value,copy_frames=copy_frames)

    def _decode_frames(self,value,*,copy_frames):
        exact(value,{'iosWorldWebSourcesVersion','binding','runId','role','payload'});rows=unpack(value['payload'])
        need(len(rows)==1 and type(value['iosWorldWebSourcesVersion']) is int and value['iosWorldWebSourcesVersion'] in READS and value['iosWorldWebSourcesVersion']==self.version
            and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'records','pending','interrupted'})
        need(type(state['records']) is list and len(state['records'])<=MAX_FRAMES and type(state['interrupted']) is list and len(state['interrupted'])<=32)
        frames=[]
        for index,reference in enumerate(state['records'],1):
            exact(reference,{'index','sha256'});need(reference['index']==index);record=self.record_store(index).read()
            need(record is not None and digest(record)==reference['sha256'])
            exact(record,{'iosWorldWebSourceRecordVersion','binding','runId','role','payload'})
            need(type(record['iosWorldWebSourceRecordVersion']) is int and record['iosWorldWebSourceRecordVersion']==self.version
                and same(record['binding'],self.binding) and record['runId']==self.run and record['role']==self.role)
            abandoned=[item for item in state['interrupted'] if item.get('index')==index]
            key=(index,reference['sha256'],None if not frames else state['records'][index-2]['sha256'],digest(abandoned))
            items=unpack(record['payload']);need(len(items)==1 and items[0]['index']==index)
            frame=deepcopy(items[0]);need(all(reference['acquisitionId']==frame['clockJoin']['nativeBefore']['requestId'] for reference in frame['originals'].values()))
            if key not in self._cache:
                frame['originals']=self.expand_originals(frame['originals'])
                self.validate_frame(frame,None if not frames else frames[-1])
                for item in abandoned:
                    floor=clock_queries(item['nativeQueries'],self.pid)
                    if floor is not None:follow_native(floor,frame['clockJoin']['nativeBefore'])
                self._cache[key]=deepcopy(frame)
            else:
                # The actual carrier hash fixes every field/reference. Reopen
                # every original chunk with its original inode and SHA; equal
                # assembled native bytes need no second JSON interpretation.
                self.parts.verify_frame(frame['originals'])
            # Internal rounds borrow only private validated cache objects.
            # Public decode/frame/browser_frames always return independent data.
            frames.append(deepcopy(self._cache[key]) if copy_frames else self._cache[key])
        for partial in state['interrupted']+([] if state['pending'] is None else [state['pending']]):self.partial(partial,len(frames))
        return deepcopy(state),frames

    def bound(self,*,intent_only=False):
        api_check();self.lock.assert_held()
        # An append-only round independently guards every actual query/input
        # send and its exit. Repeating the entire unchanged filesystem walk
        # for each planned/opened/saved metadata transition provides no new
        # observation. CAS, process ownership and durable writes still occur.
        if not intent_only or self._write_round is None:self.guard_originals()
        need(not self.historical and self.guard() is not False and same(self.store.read(),self.previous))

    def partial(self,partial,count,*,strict=True):
        exact(partial,{'index','label','phaseBefore','start','originals','nativeQueries','widgetQueries','storage','clockFloors'}|({'nativeSnapshot','snapshotQueries','surfaceQueries','closureQueries'} if self.version>=4 else set())|({'geometryQueries','auxOriginals'} if self.version==5 else set()))
        need(integer(partial['index'],1,count+1) and type(partial['originals']) is dict and set(partial['originals'])<=((NAMES|{'emissions'} if self.version==5 else NAMES) if self.version>=4 else LEGACY_NAMES)
            and type(partial['storage']) is dict and len(partial['storage'])<=len(NAMES|{'emissions'})*4)
        for name,reference in partial['originals'].items():
            self.parts.validate(reference);need(reference['name']==name and reference['index']==partial['index'])
        for name,value in partial['storage'].items():
            part=name.split('.')[0];need(part in (NAMES|{'emissions'}) or self.version>=4 and part=='snapshot')
            (self.parts.snapshot.store() if part=='snapshot' else self.parts.store(part)).original(value)
        if self.version>=4:
            self.snapshot_queries(partial['snapshotQueries']);self.surface_queries(partial['surfaceQueries']);self.closure_queries(partial['closureQueries'])
            if partial['nativeSnapshot'] is not None:self.parts.snapshot.validate(partial['nativeSnapshot'])
        if self.version==5:
            self.geometry_queries(partial['geometryQueries']);self.aux_originals(partial['auxOriginals'])
        clock_queries(partial['nativeQueries'],self.pid,strict=strict);self.widget_queries(partial['widgetQueries']);self.floor_shape(partial['clockFloors'],len(partial['nativeQueries']),partial['start'])

    def expand_originals(self,originals):
        need(type(originals) is dict and set(originals)<=(NAMES|{'emissions'}))
        return {name:self.parts.read(reference) for name,reference in originals.items()}

    def save(self):
        # These writes retain intent only. Full immutable carriers/chunks are
        # independently reopened on reconstruction, frame() and publication.
        # Reopening the entire growing history for each raw callback would
        # spend the acquisition's original freshness budget on old evidence.
        self.bound(intent_only=True);need(len(self.state['records'])<=MAX_FRAMES)
        # The actual store is CAS-read by bound/write below. This private
        # prefix came from its full decoder or our last successful durable
        # write; decompressing the entire growing raw-query journal merely to
        # get these unchanged references costs the next original's budget.
        old=self._saved_records;current=self.state['records']
        need(len(old)<=len(current)<=len(old)+1 and same(current[:len(old)],old))
        if len(current)>len(old):
            ref=current[-1];packet=self.record_store(ref['index']).read();need(ref['index']==len(current) and packet is not None and digest(packet)==ref['sha256'])
        for partial in self.state['interrupted']+([] if self.state['pending'] is None else [self.state['pending']]):self.partial(partial,len(current),strict=False)
        value=self.envelope(self.state);api_check();self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value);self._saved_records=deepcopy(current)
        self._remember_aux_prefix()
        if self._write_round is not None:
            _packet,_state,frames=self._round
            # Frames need only the validated reference prefix. Retain the
            # exact complete mutable-journal boundary as canonical SHA rather
            # than copying every old raw response on each durable transition.
            self._round=(deepcopy(value),dict(records=deepcopy(current)),frames);self._round_state_sha=digest(self.state)
        api_check()

    def storage_intent(self,name,kind,value):
        need(kind=='original' and name in (NAMES|{'emissions'}) and self.state['pending'] is not None)
        pending=self.state['pending'];index=value['index'];key=name+'.'+str(index)
        self.round_file(self.parts.store(name).path(value),value)
        need((pending['index']-1)*4<index<=pending['index']*4)
        old=pending['storage'].get(key);self.parts.store(name).original(value)
        need(value['phase']=='planned' if old is None else value['phase']=={'planned':'opened','opened':'saved'}.get(old['phase'])
            and all(same(value[field],old[field]) for field in value if field not in ('phase','file')))
        pending['storage'][key]=deepcopy(value);self.save()

    def remember(self,name,value):
        pending=self.state['pending'];need(name not in pending['originals'])
        pending['originals'][name]=self.parts.write(name,pending['index'],value);self.save();return value

    def snapshot_storage_intent(self,kind,value):
        need(self.version>=4 and kind=='original' and self.state['pending'] is not None)
        pending=self.state['pending'];index=value['index'];key='snapshot.'+str(index)
        self.round_file(self.parts.snapshot.store().path(value),value)
        need((pending['index']-1)*4<index<=pending['index']*4)
        old=pending['storage'].get(key);self.parts.snapshot.store().original(value)
        need(value['phase']=='planned' if old is None else value['phase']=={'planned':'opened','opened':'saved'}.get(old['phase'])
            and all(same(value[field],old[field]) for field in value if field not in ('phase','file')))
        pending['storage'][key]=deepcopy(value);self.save()

    @staticmethod
    def original_signature(path):
        value=path.lstat();need(stat.S_ISREG(value.st_mode) and value.st_nlink==1 and value.st_uid==os.geteuid() and stat.S_IMODE(value.st_mode)==0o600)
        return (value.st_dev,value.st_ino,value.st_mode,value.st_uid,value.st_nlink,value.st_size,value.st_mtime_ns,value.st_ctime_ns)

    def original_pins(self,packet):
        # Deterministic retained paths only. Pin before the full byte decoder;
        # its successful reads prove the bytes while these pins prove that
        # none changed during this synchronous validation/use interval.
        paths={self.store.path}
        if packet is not None:
            rows=unpack(packet['payload']);need(len(rows)==1 and type(rows[0]['records']) is list and len(rows[0]['records'])<=MAX_FRAMES)
            for index,reference in enumerate(rows[0]['records'],1):
                need(reference['index']==index);store=self.record_store(index);paths.add(store.path);record=store.read()
                need(record is not None and digest(record)==reference['sha256']);frames=unpack(record['payload']);need(len(frames)==1)
                for part in frames[0]['originals'].values():
                    paths.update(self.parts.paths(part))
        return {path:self.original_signature(path) for path in paths if packet is not None or path.exists()}

    def guard_originals(self):
        self._guard_aux_prefix()
        if self._round_header is not None:need(same(self._round_header,(self.binding,self.run,self.role,self.pid,self.phase.fixture_url,self.version)))
        if self._round_pins is not None:
            for path,signature in self._round_pins.items():need(self.original_signature(path)==signature)
        if self._write_round is not None:
            need(same(self.store.read(),self.previous));continuity,planned=self._write_round;continuity.guard()
            for path,original in planned.items():
                if original is None or original['phase']=='planned':need(not path.exists())
                elif original['phase']=='opened':
                    row=path.lstat();need(stat.S_ISREG(row.st_mode) and row.st_nlink==1 and row.st_uid==os.geteuid()
                        and stat.S_IMODE(row.st_mode)==0o600 and (row.st_dev,row.st_ino)==(original['file']['device'],original['file']['inode'])
                        and row.st_size<=original['bytes'])
                else:need(path in self._round_pins)

    def guard_saved_state(self):
        # Product input may use only the exact latest durably retained state.
        # Passive process preflight during an intentional metadata transition
        # is separate and may run before that transition's CAS write.
        if self._write_round is not None:need(self._round_state_sha==digest(self.state))

    def round_file(self,path,original=None):
        if self._write_round is None:return
        continuity,planned=self._write_round
        if path not in planned:
            need(not path.exists() and path not in self._round_pins);planned[path]=deepcopy(original);continuity.mutable.add(path)
        else:
            old=planned[path];need(old is not None and original is not None and original['phase']=={'planned':'opened','opened':'saved'}.get(old['phase']))
            planned[path]=deepcopy(original)
        if original is not None and original['phase']=='saved':self._round_pins[path]=self.original_signature(path)

    def admit_round_frame(self,frame,reference):
        if self._write_round is None:return
        packet,state,frames=self._round;need(reference['index']==len(frames)+1 and self.state['records'][-1]==reference)
        store=self.record_store(reference['index']);actual=store.read();need(actual is not None and digest(actual)==reference['sha256'])
        retained=unpack(actual['payload']);need(len(retained)==1)
        self._round_pins[store.path]=self.original_signature(store.path);self._write_round[1].pop(store.path,None)
        for part in retained[0]['originals'].values():
            self.parts.verify(part)
            for path in self.parts.paths(part):self._round_pins[path]=self.original_signature(path)
        self._round_pins[store.path]=self.original_signature(store.path)
        # A newly written record was reserved before its atomic write. An
        # interrupted complete record may instead be adopted unchanged.
        self._round=(packet,state,frames+[deepcopy(frame)])

    @contextmanager
    def input_round(self,mutable):
        with self.parts.snapshot.validation_round(),ledger.validation_round():
            with self._input_round(mutable):yield

    @contextmanager
    def _input_round(self,mutable):
        # Only this explicit append path may add acquisitions to a validated
        # original round. It validates the full old byte graph before a fresh
        # query, journals every new carrier before write and admits only the
        # fully validated original frame. No cache survives the call.
        need(self._round is None and self._write_round is None and isinstance(mutable,PrivateFeatureState)
            and mutable.path.parent==self.store.path.parent and mutable.path.name=='ios-world-web-inputs.json')
        self.bound();header=(deepcopy(self.binding),self.run,self.role,self.pid,self.phase.fixture_url,self.version)
        continuity=EmoteOriginalLease(self.store.path.parent,[self.store.path,mutable.path]);packet=self.store.read();pins=self.original_pins(packet)
        pins.pop(self.store.path,None)
        state,frames=(dict(records=[],pending=None,interrupted=[]),[]) if packet is None else self._decode(packet,copy_frames=False)
        need(same(state,self.state));continuity.guard();self._round=(packet,state,frames);self._round_pins=pins;self._write_round=(continuity,{});self._round_header=header;self._round_state_sha=digest(state)
        try:
            with transport_scope(self.guard_originals):self.guard_originals();yield
        finally:
            try:
                self.guard_originals();need(same(self.store.read(),self.previous) and self._round_state_sha==digest(self.state)
                    and same(header,(self.binding,self.run,self.role,self.pid,self.phase.fixture_url,self.version)))
            finally:self._round=None;self._round_pins=None;self._write_round=None;self._round_header=None;self._round_state_sha=None


    @contextmanager
    def validation_round(self):
        if self._round is not None:yield;return
        self.lock.assert_held();header=(deepcopy(self.binding),self.run,self.role,self.pid,self.phase.fixture_url,self.version)
        packet=self.store.read();pins=self.original_pins(packet)
        if packet is None:
            state,frames=dict(records=[],pending=None,interrupted=[]),[];need(self.previous is None)
        else:state,frames=self._decode(packet,copy_frames=False)
        need(same(state,self.state));self._round=(packet,state,frames);self._round_pins=pins;self._round_header=header;self.guard_originals()
        try:yield
        finally:
            try:
                self.guard_originals();need(same(self.store.read(),packet) and same(self.state,state) and same(header,(self.binding,self.run,self.role,self.pid,self.phase.fixture_url,self.version)))
            finally:self._round=None;self._round_pins=None;self._round_header=None

    def input_point(self,frame,entity,control):
        raw=frame['originals'];arguments=(raw['geometry'],raw['document'],raw['world'],raw['uikit'],entity,control)
        if self.version==3:return geometry.point(*arguments)
        original=self.parts.snapshot.packet(frame['nativeSnapshot']);return geometry.point_snapshot(*arguments,original)

    def snapshot_queries(self,rows):
        need(type(rows) is list and len(rows)<=1)
        for query in rows:
            (whole_snapshot if self.version==5 else snapshot).command(query);need(query['runId']==self.run and query['fixtureUrl']==self.phase.fixture_url)

    @staticmethod
    def geometry_queries(rows):
        need(type(rows) is list and len(rows)<=1)
        for query in rows:
            exact(query,{'schemaVersion','commandId','action'})
            need(type(query['schemaVersion']) is int and query['schemaVersion']==1 and query['action']=='native-geometry-snapshot'
                and type(query['commandId']) is str and query['commandId'].startswith('ios-'))
            identifier(query['commandId'][4:])

    def surface_queries(self,rows):
        need(type(rows) is list and len(rows)<=1)
        for query in rows:surfaces.command(query);need(query['runId']==self.run)

    def closure_queries(self,rows):
        need(type(rows) is list and len(rows)<=1)
        for query in rows:closures.command(query);need(query['runId']==self.run and query['fixtureUrl']==self.phase.fixture_url)

    def capture_closures(self):
        reader=self.readers['closures'];send=reader.send;pending=self.state['pending']
        def sending(query):
            closures.command(query);pending['closureQueries'].append(deepcopy(query));self.save();self.guard_originals();return send(query)
        reader.send=sending
        try:return self.remember('closures',reader.read(self.run,self.phase.fixture_url))
        finally:reader.send=send

    @staticmethod
    def widget_queries(rows):
        need(type(rows) is list and len(rows)<=4);seen=set()
        for row in rows:
            exact(row,{'schemaVersion','commandId','action','operation'})
            need(type(row['schemaVersion']) is int and row['schemaVersion']==1 and row['action']=='normal-ui-input' and row['operation']=='observe'
                and type(row['commandId']) is str and row['commandId'].startswith('ios-'))
            identifier(row['commandId'][4:]);need(row['commandId'] not in seen);seen.add(row['commandId'])

    @staticmethod
    def floor_shape(rows,count,start):
        need(type(rows) is list and len(rows)<=9);seen=set()
        for row in rows:
            exact(row,{'name','acquisitionId','floor','beforeQueries','afterQueries'})
            need(row['name'] in ('ledgerBefore','world','work','document','geometry','keys','pointer','entities','ledgerAfter','snapshot','surfaces','uikit') and row['name'] not in seen
                and integer(row['beforeQueries'],1,count) and (row['afterQueries'] is None or integer(row['afterQueries'],row['beforeQueries']+1,count)))
            seen.add(row['name']);need(start is not None and row['acquisitionId']==start['nativeBefore']['requestId'])

    def clock_floors(self,frame):
        rows=frame['clockFloors'];queries=frame['nativeQueries'];self.floor_shape(rows,len(queries),frame['clockJoin'])
        expected=['ledgerBefore','world','work']+([] if frame['originals']['document'] is None else ['document'])+['geometry','keys','pointer','entities','ledgerAfter']
        if self.version>=4:expected=['snapshot']+(['uikit'] if self.version==5 else ['surfaces'])
        need([row['name'] for row in rows]==expected);first=frame['clockJoin']['nativeBefore'];last_count=0
        for row in rows:
            before,after=row['beforeQueries'],row['afterQueries'];need(after is not None and before>=max(1,last_count));last_count=after
            actual=clock_queries([queries[before-1]],self.pid);terminal=clock_queries([queries[after-1]],self.pid)
            need(actual is not None and terminal is not None and same(actual,row['floor']) and actual['sequence']>=first['sequence']
                and actual['instance']==terminal['instance']==first['instance'] and terminal['capturedEpochMs']-actual['capturedEpochMs']<1500)
            follow_native(actual,terminal)
            packet=self.parts.snapshot.packet(frame['nativeSnapshot']) if row['name']=='snapshot' else frame['originals'][row['name']]
            a,b=(packet['observation']['sampleEpochMs'],packet['observation']['sampleEpochMs']) if row['name']=='uikit' else (packet['capturedEpochMs'],packet['capturedEpochMs']) if row['name']=='document' else (packet['clockBefore']['epochMs'],packet['clockAfter']['epochMs'])
            need(actual['capturedEpochMs']<=a<=b<=terminal['capturedEpochMs'])

    def read_floor(self,name,*arguments):
        pending=self.state['pending'];queries=pending['nativeQueries'];need(queries and pending['start'] is not None)
        need(self.monotonic()<pending['start']['hostBeforeMonotonic']+1.5)
        floor=clock_queries([queries[-1]],self.pid);need(floor is not None and floor['sequence']==self.native.sequence
            and floor['instance']==pending['start']['nativeBefore']['instance']==self.native.instance
            and floor['capturedEpochMs']==self.native.captured_epoch and self.native.pid==self.pid
            and same(floor['lifecycle'],self.native.lifecycle))
        # The actual old raw and its nonce already exist durably. This row
        # selects only its BEFORE floor; the terminal query remains new and
        # its own before-send journal includes this selection before returning.
        row=dict(name=name,acquisitionId=pending['start']['nativeBefore']['requestId'],floor=deepcopy(floor),beforeQueries=len(queries),afterQueries=None)
        pending['clockFloors'].append(row);reader=self.readers['ledger' if name.startswith('ledger') else name]
        self.guard_originals()
        if name in ('snapshot','surfaces','uikit'):
            send=reader.send
            def sending(query):
                self.geometry_queries([query]) if name=='uikit' else ((whole_snapshot if self.version==5 else snapshot) if name=='snapshot' else surfaces).command(query)
                pending['snapshotQueries' if name=='snapshot' else 'geometryQueries' if name=='uikit' else 'surfaceQueries'].append(deepcopy(query));self.save();self.guard_originals();return send(query)
            reader.send=sending
            try:value=reader.capture(native_before_floor=floor['capturedEpochMs']) if name=='uikit' else reader.read(*arguments,native_before_floor=deepcopy(floor))
            finally:reader.send=send
        else:value=reader.read(*arguments,native_before_floor=deepcopy(floor))
        row['afterQueries']=len(queries)
        need(row['afterQueries']>row['beforeQueries']);return value

    @staticmethod
    def aux_originals(value):
        from adapters.script_feature.history import canonical
        need(type(value) is dict and set(value)<={'widgetReceipt','uikit','browser'} and all(type(packet) is dict for packet in value.values()))
        # Actual packets stay durably present in the existing bounded journal
        # before another request. PrivateFeatureState also enforces 64 KiB on
        # the complete compressed envelope; oversize never advances a request.
        need(len(canonical(value))<=2*1024*1024)

    def _remember_aux_prefix(self):
        from adapters.script_feature.history import canonical
        pending=self.state['pending']
        self._aux_saved=None if self.version!=5 or pending is None else (pending['index'],
            {name:canonical(value) for name,value in pending['auxOriginals'].items()})

    def _guard_aux_prefix(self):
        from adapters.script_feature.history import canonical
        saved=getattr(self,'_aux_saved',None)
        if saved is None:return
        index,raws=saved;pending=self.state['pending']
        if pending is not None and pending['index']==index and all(name in pending['auxOriginals'] and canonical(pending['auxOriginals'][name])==raw for name,raw in raws.items()):return
        if index>len(self.state['records']):
            need(any(row['index']==index and all(name in row['auxOriginals'] and canonical(row['auxOriginals'][name])==raw
                for name,raw in raws.items()) for row in self.state['interrupted']))

    def remember_aux(self,name,value):
        need(self.version==5 and name in ('widgetReceipt','uikit','browser'))
        pending=self.state['pending'];need(name not in pending['auxOriginals'])
        pending['auxOriginals'][name]=deepcopy(value);self.aux_originals(pending['auxOriginals']);self.save()

    def capture_widgets(self):
        self.guard_originals();reader=self.readers['widgets'];old=getattr(reader,'observe_intent',None)
        def intent(query):
            self.state['pending']['widgetQueries'].append(deepcopy(query));self.save()
            if old is not None:old(query)
        reader.observe_intent=intent
        try:
            original=reader.capture()
            if self.version==5:
                need(same(original,reader.last_receipt['observation']))
                self.remember_aux('widgetReceipt',reader.last_receipt)
            else:self.remember('widgets',original);self.remember('widgetReceipt',reader.last_receipt)
        finally:
            if old is None:del reader.observe_intent
            else:reader.observe_intent=old

    @contextmanager
    def native_query_guard(self):
        # clock_owned durably records each nonce before calling this wrapper.
        # Keep the complete original/inventory guard at the actual Native
        # query boundary even for explicit host SDK models without HTTP.
        send=self.native.send
        def sending(query):
            self.guard_originals()
            pending=self.state['pending'];started=None if pending is None else pending['start']
            if started is not None:need(self.monotonic()<started['hostBeforeMonotonic']+1.5)
            return send(query)
        self.native.send=sending
        try:
            with clock_owned(self):yield
        finally:self.native.send=send

    def capture(self,label,*,retired=False):
        need(type(retired) is bool and (label=='final-fence')==retired and (not retired or self.version>=4))
        with ledger.validation_round(),self.parts.snapshot.validation_round():return self._capture(label,retired=retired)

    def _capture(self,label,*,retired=False):
        self.bound();need(len(self.frames)<MAX_FRAMES)
        if self.state['pending'] is not None:
            # Saved but unindexed originals are adopted, never overwritten.
            extra=self.record_store(len(self.frames)+1).read()
            if extra is not None:
                items=unpack(extra['payload']);need(len(items)==1);frame=items[0]
                need(frame['label']==self.state['pending']['label'] and same(frame['originals'],self.state['pending']['originals'])
                    and same(frame['nativeQueries'],self.state['pending']['nativeQueries']))
                frame['originals']=self.expand_originals(frame['originals'])
                self.validate_frame(frame,None if not self.frames else (self._round[2][-1] if self._round is not None else self.frames[-1]))
                reference=dict(index=frame['index'],sha256=digest(extra));self.state['records'].append(reference);self.state['pending']=None
                self.admit_round_frame(frame,reference);self.save();self.frames.append(deepcopy(frame))
            else:
                need(len(self.state['interrupted'])<32);self.state['interrupted'].append(deepcopy(self.state['pending']));self.state['pending']=None;self.save()
        first=self.phase.status();need(first['activations'] and first['active'] is (not retired))
        if retired:need(first['activations'][-1]['stimulus']==dict(verb='cleanup',inputs={}))
        ticket=first['activations'][-1]['ticket']
        self.state['pending']=dict(index=len(self.frames)+1,label=label,phaseBefore=first,start=None,originals={},nativeQueries=[],widgetQueries=[],storage={},clockFloors=[])
        if self.version>=4:self.state['pending'].update(nativeSnapshot=None,snapshotQueries=[],surfaceQueries=[],closureQueries=[])
        if self.version==5:self.state['pending'].update(geometryQueries=[],auxOriginals={})
        self.round_file(self.record_store(len(self.frames)+1).path);self.save()
        with self.native_query_guard():
            acquisition=NativeClockAcquisition(self.native,epoch_ms=self.epoch_ms,monotonic=self.monotonic)
            acquisition.begin(first['activations'][-1]['activatedEpochMs']);self.state['pending']['start']=deepcopy(acquisition.started);self.save()
            for partial in self.state['interrupted']:
                if partial['index']!=len(self.frames)+1:continue
                floor=clock_queries(partial['nativeQueries'],self.pid)
                if floor is not None:follow_native(floor,acquisition.started['nativeBefore'])
            if self.version>=4:
                captured=self.read_floor('snapshot',self.run,self.phase.fixture_url)
                parent=self.parts.snapshot.write(self.state['pending']['index'],captured)
                self.state['pending']['nativeSnapshot']=parent
                self.state['pending']['originals'].update(self.parts.snapshot.project(parent));self.save()
                self.capture_widgets();self.guard_originals()
                if self.version==5:self.remember_aux('uikit',self.read_floor('uikit'))
                else:self.remember('uikit',self.readers['uikit'].capture())
                if self.version==4:self.remember('surfaces',self.read_floor('surfaces',self.run));self.capture_closures()
            else:
                self.remember('ledgerBefore',self.read_floor('ledgerBefore',self.run,self.phase.fixture_url))
                for name in ('world','work'):self.remember(name,self.read_floor(name,self.run))
                current=current_view(self.parts.read(self.state['pending']['originals']['ledgerBefore']))
                self.remember('document',None if current is None else self.read_floor('document',self.run,self.phase.fixture_url))
                self.capture_widgets()
                self.guard_originals()
                self.remember('uikit',self.readers['uikit'].capture())
                self.remember('geometry',self.read_floor('geometry',self.run))
                for name in ('keys','pointer','entities'):self.remember(name,self.read_floor(name,self.run))
                self.remember('ledgerAfter',self.read_floor('ledgerAfter',self.run,self.phase.fixture_url))
            route='browser-retired' if self.version==5 and retired else 'browser'
            browser=self.phase.client.request('/runs/'+self.run+'/'+route)
            if self.version==5:
                self.remember_aux('browser',browser)
                self.validate_browser(browser,retired=retired,previous=None if not self.frames else self.frames[-1]['originals']['browser'])
                self.state['pending']['originals'].update(self.parts.write_aux(self.state['pending']['index'],self.state['pending']['auxOriginals']));self.save()
            else:self.remember('browser',browser)
            raw=self.expand_originals(self.state['pending']['originals'])
            fields=[(name,field) for name,packet in raw.items() if type(packet) is dict for field in ('capturedEpochMs','sampleEpochMs') if field in packet]
            joined=acquisition.finish(raw,fields)
        after=self.phase.status();frame=dict(index=len(self.frames)+1,label=label,ticket=ticket,phaseBefore=first,phaseAfter=after,
            originals=raw,clockJoin=joined,nativeQueries=deepcopy(self.state['pending']['nativeQueries']),widgetQueries=deepcopy(self.state['pending']['widgetQueries']),clockFloors=deepcopy(self.state['pending']['clockFloors']))
        if self.version>=4:frame.update(nativeSnapshot=deepcopy(self.state['pending']['nativeSnapshot']),snapshotQueries=deepcopy(self.state['pending']['snapshotQueries']),surfaceQueries=deepcopy(self.state['pending']['surfaceQueries']),closureQueries=deepcopy(self.state['pending']['closureQueries']))
        if self.version==5:frame['geometryQueries']=deepcopy(self.state['pending']['geometryQueries'])
        active=self.validate_frame(frame,None if not self.frames else (self._round[2][-1] if self._round is not None else self.frames[-1]))
        # The durable record holds original part references. Do not first
        # clone every large native transcript merely to discard those clones
        # when replacing originals with their already validated references.
        retained=deepcopy({key:value for key,value in frame.items() if key!='originals'})
        retained['originals']=deepcopy(self.state['pending']['originals'])
        record=dict(iosWorldWebSourceRecordVersion=self.version,binding=self.binding,runId=self.run,role=self.role,payload=pack([retained]))
        self.record_store(frame['index']).write(record,None)
        reference=dict(index=frame['index'],sha256=digest(record));self.state['records'].append(reference);self.state['pending']=None
        self.admit_round_frame(frame,reference);self.save()
        # All originals in frame were freshly decoded from actual private
        # parts. The append round already owns its separate private copy; this
        # public history receives the otherwise unexposed local objects.
        self.frames.append(frame)
        need(active if not retired else not active and frame['phaseAfter']['active'] is False);return deepcopy(self.state['records'][-1])

    def retained(self,reference):
        with self.validation_round():need(reference in self._round[1]['records'])

    def frame(self,reference):
        with self.validation_round():
            _packet,state,frames=self._round;need(reference in state['records']);return deepcopy(frames[reference['index']-1])

    def browser_frames(self,until=None):
        with self.validation_round():
            _packet,state,frames=self._round
            if until is not None:need(until in state['records']);frames=frames[:until['index']]
            return deepcopy([dict(ledger=frame['originals']['ledgerAfter'],document=frame['originals']['document'],work=frame['originals']['work'],browser=frame['originals']['browser'],**({'emissions':frame['originals']['emissions']} if self.version==5 else {})) for frame in frames])

    def prewarm_snapshot_history(self):
        """Validate old bytes before fresh acquisition, without a write round.

        Only the existing snapshot-parent memo can survive this read. Pending
        in-memory delivery state is deliberately not replaced: an interrupted
        capture still owns it until normal Source recovery durably retains it.
        """
        self.bound();need(self.parts.snapshot._round is not None)
        header=(deepcopy(self.binding),self.run,self.role,self.pid,self.phase.fixture_url,self.version)
        packet=self.store.read();pins=self.original_pins(packet);pins.pop(self.store.path,None)
        state,_frames=(dict(records=[],pending=None,interrupted=[]),[]) if packet is None else self._decode(packet,copy_frames=False)
        need(same(state['records'],self.state['records']) and same(state['interrupted'],self.state['interrupted']))
        for path,signature in pins.items():need(self.original_signature(path)==signature)
        prefix=deepcopy(state['records'])
        def guard():
            need(same(header,(self.binding,self.run,self.role,self.pid,self.phase.fixture_url,self.version))
                and same(self.state['records'][:len(prefix)],prefix))
            if self.previous is not None:
                need(self.previous['binding']==self.binding and self.previous['runId']==self.run and self.previous['role']==self.role
                    and self.previous['iosWorldWebSourcesVersion']==self.version)
            # Source.bound/save still perform their exact journal CAS read.
            # This additional old-parent guard runs at each such check and
            # native send; it must not read the same growing journal again.
            for path,signature in pins.items():need(self.original_signature(path)==signature)
        guard();return guard

    def derive_browser(self,until=None,*,ownership=None,directory=None,entity=None,origins):
        """Closed pure derivation on private, already byte-validated frames.

        No caller callback or raw frame escapes this boundary. The fixed
        derivation and its callees only read the borrowed originals and own
        all their returned dictionaries; outward results are copied again.
        Original clocks and every source/file guard remain unchanged.
        """
        from ios.adapters.world_web_history import derive
        with self.validation_round():
            self.guard_originals();_packet,state,frames=self._round
            if until is not None:need(until in state['records']);frames=frames[:until['index']]
            original=[dict(ledger=frame['originals']['ledgerAfter'],document=frame['originals']['document'],work=frame['originals']['work'],browser=frame['originals']['browser'],**({'emissions':frame['originals']['emissions']} if self.version==5 else {})) for frame in frames]
            value=derive(original,ownership=deepcopy(ownership),directory=directory,entity=entity,origins=deepcopy(origins))
            self.guard_originals();return deepcopy(value)
