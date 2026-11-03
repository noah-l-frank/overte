"""Frozen paired Assets graph over existing literal child/Scene/Image readers.

Copies are host metadata interpretations, never source reads or live absence.
External server work is mandatory restored by its original Delete/Blob proof
BEFORE this graph is eligible for local process/SDK retirement.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import stat
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState,context as binding
from adapters.original_file_reads import collect as read_scope
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import pack,unpack
from adapters.script_feature.history import same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from ios.adapters.assets_end_metadata import RecordingAssetsMetadata,FrozenAssetsMetadata
from ios.adapters.assets_image_ownership import ImageInventoryContext
from ios.adapters.assets_session_owners import inspect_directory
from ios.adapters.emote_original_lease import EmoteOriginalLease
from ios.adapters.emote_final_archive import IOSEmoteFinalArchive
from ios.adapters.installed_code import source as source_packet

HELD=frozenset(('usage-model-retirement','model-resource-origin','parsed-resource-retirement','model-removal-resources',
    'scene-peer-resources','peer-resource-retirement','image-originals','marker-originals','image-gpu',
    'image-reader-resource-retirement','image-processing-resource-retirement','image-storage-resource-retirement','image-pool-resource-retirement'))


def selection(value):
    exact(value,{'assetsPairedEndContextVersion','runId','fixtureUrl','initialTicket','inputPhaseOriginal','roles'})
    need(type(value['assetsPairedEndContextVersion']) is int and value['assetsPairedEndContextVersion']==1)
    identifier(value['runId']);identifier(value['initialTicket']);exact(value['roles'],{'primary','actor'})
    from feature_journeys.phase_fixture import validate as phase_packet
    phase=value['inputPhaseOriginal'];phase_packet(phase,run=value['runId'],area='assets',request=phase['requestId'],epoch=phase['capturedEpochMs'])
    need(phase['active'] and phase['activations'] and phase['activations'][-1]['ticket']==value['initialTicket'])
    from feature_journeys.graphics_resources import fixture_url
    suffix='/runs/'+value['runId']+'/'
    need(type(value['fixtureUrl']) is str and value['fixtureUrl'].endswith(suffix))
    fixture_url(value['fixtureUrl'][:-len(suffix)]);roots=[];targets=[]
    for role,info in value['roles'].items():
        exact(info,{'target','artifactRoot','stateRoot','binding','source','bundleId'})
        from ios.adapters.emote_configuration import selector
        selector(info['target']);targets.append(info['target']);binding(info['binding']);source_packet(info['source'])
        need(type(info['bundleId']) is str and bool(info['bundleId']))
        for field in ('artifactRoot','stateRoot'):
            path=Path(info[field]);need(type(info[field]) is str and path.is_absolute() and path.resolve()==path and path.is_dir())
            roots.append((role,path))
    need(len(set(targets))==2)
    for role,path in roots:
        for other,right in roots:
            if role!=other:need(path!=right and not path.is_relative_to(right) and not right.is_relative_to(path))
    p,a=(value['roles'][role]['binding'] for role in ('primary','actor'))
    need(p['targetFingerprint']!=a['targetFingerprint'] and p['sessionId']!=a['sessionId']
        and all(p[key]==a[key] for key in ('sourceRevision','artifactSha256')))
    return deepcopy(value)


def inventory(roots,*,locks=()):
    roots={Path(p) for p in roots};locks=tuple(locks)
    need(all(isinstance(lock,ScriptSourceLock) and lock.path.parent in roots for lock in locks))
    for lock in locks:lock.assert_held()
    ignored={lock.path for lock in locks};result=set()
    for root in roots:
        entries=list(root.rglob('*'));need(len(entries)<=8192)
        for path in entries:
            info=path.lstat();need(stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode))
            if stat.S_ISREG(info.st_mode) and path not in ignored:result.add(path)
    return result


class AssetsOwnership:
    def __init__(self,chosen,copies,locks,selected):
        self.context=selection(chosen);self.run=self.context['runId'];exact(locks,{'primary','actor'});self.locks=dict(locks)
        need(type(selected) is AssetsFinalArchive and same(selected.context,self.context));self.selected=selected;selected.selected_guard()
        for role,lock in self.locks.items():
            need(isinstance(lock,ScriptSourceLock) and lock.path==Path(chosen['roles'][role]['stateRoot'])/'script-feature-sources.lock')
            lock.assert_held()
        self.copies=deepcopy(copies)
    @property
    def roots(self):return {Path(info[field]) for info in self.context['roles'].values() for field in ('artifactRoot','stateRoot')}
    def read(self,*,owned=()):
        view=FrozenAssetsMetadata(self.copies,owned=owned,selection=self.selected);reports=self._read(view)
        need(view.used==set(self.copies));return reports
    def _read(self,view):
        for lock in self.locks.values():lock.assert_held()
        leases=[EmoteOriginalLease(root,[]) for root in self.roots];c=self.context
        reports={};contexts={}
        p=c['roles']['primary']
        images={Path(p['stateRoot']):ImageInventoryContext(Path(p['artifactRoot']),deepcopy(p['binding']),self.run,c['initialTicket'],self.locks['primary'])}
        for role in ('primary','actor'):
            info=c['roles'][role];directory=Path(info['stateRoot'])
            image=ImageInventoryContext(Path(info['artifactRoot']),deepcopy(info['binding']),self.run,c['initialTicket'],self.locks[role]) if role=='primary' else None
            rows=inspect_directory(directory,primary_directory=Path(c['roles']['primary']['stateRoot']) if role=='actor' else None,
                _contexts=contexts,image_context=image,metadata=view,image_contexts=images)
            need(rows and all(row['runId']==self.run and same(row['binding'],info['binding']) for row in rows))
            # Every current child must be known and resolved. Only explicitly
            # retained local native/cache/image responsibilities are allowed.
            # Any active server/read lease/Delete/source-write blocks BEFORE Stop.
            need(all(set(row['responsibilities'])<=HELD for row in rows))
            reports[role]=deepcopy(rows)
        primary=contexts.get((self.run,'primary'));need(primary is not None and primary['parsed'] is not None)
        parsed=primary['parsed'];need(parsed.state['phase']=='observed' and parsed.baking.backend.state['phase']=='restored'
            and parsed.model.usage.source.files.url==self.context['fixtureUrl'])
        # Existing Backend.decode has reopened the normal Delete/mapping/blob
        # baseline and independent worker quiet originals. No new ACK shortcut.
        required=('files','picker','replies','upload','backend','usage','baking','model-sources','model','parsed-sources','parsed','model-removal','baked-tree')
        directory=Path(c['roles']['primary']['stateRoot'])
        for kind in required:need(str(directory/('ios-assets-'+self.run+'-primary-'+kind+'.json')) in view.copies)
        for kind in ('image-reader-lifecycle','image-processing','image-storage','image-pool'):
            need(str(directory/('ios-assets-'+kind+'-'+self.run+'.json')) in view.copies)
        need(any(row['responsibilities']==['peer-resource-retirement'] for row in reports['actor']))
        # Both first-owner grammars must carry the same independently reopened
        # early selected-pair original. Literal legacy children remain readable
        # elsewhere, but cannot be retroactively adopted into this end profile.
        file_copy=view.copies[str(directory/('ios-assets-'+self.run+'-primary-files.json'))]
        need(file_copy['iosAssetsFileOwnerVersion']==3 and same(file_copy['selectedPair'],self.selected.link()))
        for role,subject in (('primary','primary'),('primary','actor-primary'),('actor','actor')):
            path=Path(c['roles'][role]['stateRoot'])/('ios-assets-scene-'+self.run+'-'+subject+'.json')
            need(str(path) in view.copies and view.copies[str(path)]['iosAssetsSceneSourcesVersion']==2
                and same(view.copies[str(path)]['selectedPair'],self.selected.link()))
        for lease in leases:lease.guard()
        return reports

    @classmethod
    def capture(cls,chosen,locks,selected,*,owned=()):
        view=RecordingAssetsMetadata(owned=owned,selection=selected);temporary=cls(chosen,{},locks,selected)
        with read_scope() as reads:
            reports=temporary._read(view);view.guard()
        result=cls(chosen,view.copies,locks,selected)
        need(same(result.read(owned=owned),reports));result.metadata_pins={name:None if pin is None else list(pin) for name,pin in view.pins.items()};return result,reads


class AssetsFinalArchive(IOSEmoteFinalArchive):
    VERSION=1
    READS=(1,)
    COPY_VERSION=1
    PHASE_AREA='assets'
    EXTRA_FIELDS=frozenset({'context','selection','metadataPins'})
    ARCHIVE_KEY='iosAssetsPairedFinalArchiveVersion'
    COPY_KEY='iosAssetsPairedFinalCopyVersion'
    COPY_PREFIX='assets-final-'
    PHASES=('freezing','validated','retiring','complete')
    def __init__(self,*args,chosen,**kwargs):
        self.context=selection(chosen);raw=args[0].read()
        self.metadata_pins=None if raw is None else deepcopy(raw.get('metadataPins'))
        self.selection_state=dict(reference=None,pending=None) if raw is None else deepcopy(raw.get('selection'))
        exact(self.selection_state,{'reference','pending'})
        self.selection_frames=OriginalFrameStore(Path(chosen['roles']['primary']['artifactRoot']),chosen['roles']['primary']['binding'],
            chosen['runId'],'primary',self.selection_file_guard,self.selection_intent,
            namespace='assets-end-selection',schema_prefix='iosAssetsEndSelection')
        super().__init__(*args,**kwargs)
        need(self.role=='primary' and self.run==self.context['runId']
            and self.store.path==Path(self.context['roles']['primary']['stateRoot'])/('ios-assets-'+self.run+'-primary-final.json'))
    def extra_envelope(self):return dict(context=deepcopy(self.context),selection=deepcopy(self.selection_state),metadataPins=deepcopy(self.metadata_pins))
    def selection_file_guard(self):
        self.lock.assert_held();self.primary_lock.assert_held();need(self.guard() is not False and same(self.store.read(),self.previous));return True
    def selection_intent(self,event,value):
        need(event=='original' and self.state==dict(phase='selecting') and value['index']==1 and self.selection_state['reference'] is None)
        self.selection_frames.original(value);self.selection_state['pending']=deepcopy(value);self.save()
    def decode(self,value):
        rows=unpack(value['payload']);need(len(rows)==1)
        if rows[0].get('phase') in ('selecting','selected'):
            exact(value,{self.ARCHIVE_KEY,'runId','role','binding','artifactRoot','paths','payload'}|self.EXTRA_FIELDS)
            exact(rows[0],{'phase'});need(same(value,self.envelope(rows[0])) and self.metadata_pins is None)
            if rows[0]['phase']=='selected':need(self.selection_state['reference'] is not None and self.selection_state['pending'] is None)
            else:need(self.selection_state['reference'] is None)
            if self.selection_state['pending'] is not None:self.selection_frames.original(self.selection_state['pending'])
            return deepcopy(rows[0])
        need(self.selection_state['reference'] is not None and self.selection_state['pending'] is None
            and type(self.metadata_pins) is dict and set(self.metadata_pins)=={str(path.path) for path in self.paths})
        for pin in self.metadata_pins.values():need(pin is None or type(pin) is list and len(pin)==8 and all(type(part) is int for part in pin))
        return super().decode(value)
    def empty_asset_namespace(self):
        own=self.owned_paths()
        for root in {Path(info[field]) for info in self.context['roles'].values() for field in ('stateRoot','artifactRoot')}:
            for path in inventory([root],locks=[lock for lock in (self.lock,self.primary_lock) if lock.path.parent==root]):
                need(path in own or not path.name.startswith(('assets-','ios-assets-')))
    def select(self):
        self.bound()
        if self.state is not None and self.state['phase']!='selecting':self.selected_guard();return
        self.empty_asset_namespace()
        if self.state is None:self.state=dict(phase='selecting');self.save()
        if self.state['phase']=='selected':self.selected_guard();return
        payload=dict(assetsPairedSelectionVersion=1,context=deepcopy(self.context))
        pending=self.selection_state['pending']
        if pending is None:reference=self.selection_frames.write(1,payload)
        else:
            # A planned/orphan write is responsibility, never a successful
            # selection. Recovery can only reopen our recorded actual inode.
            need(pending['phase'] in ('opened','saved') and same(self.selection_frames.read(pending),payload))
            reference=self.selection_frames.compact(dict(pending,phase='saved'))
        self.selection_state=dict(reference=reference,pending=None);self.state=dict(phase='selected');self.save();self.selected_guard()
    def selected_guard(self):
        self.selection_file_guard();reference=self.selection_state['reference'];need(reference is not None and self.selection_state['pending'] is None)
        need(same(self.selection_frames.read(self.selection_frames.expand(reference)),dict(assetsPairedSelectionVersion=1,context=self.context)))
        return True
    def link(self):
        self.selected_guard();return dict(archivePath=str(self.store.path),contextSha256=digest(self.context),reference=deepcopy(self.selection_state['reference']))
    def begin(self,phase):
        self.selected_guard();need(self.state==dict(phase='selected'))
        from feature_journeys.phase_fixture import validate as phase_packet
        phase_packet(phase,run=self.run,area='assets',request=phase['requestId'],epoch=phase['capturedEpochMs'],previous=self.context['inputPhaseOriginal'])
        need(not phase['active']);self.state=None;return super().begin(phase)
    def frozen_identity(self):
        need(self.state is not None and self.state['phase'] in ('validated','retiring','complete'))
        return digest(dict(context=self.context,selection=self.selection_state,paths=[str(path.path) for path in self.paths],
            phaseOriginal=self.state['phaseOriginal'],hashes=self.state['hashes'],records=self.state['records'],metadataPins=self.metadata_pins))
    def retire(self):need(False)  # Only the typed local end CAS index may delete.
    def owned_paths(self):
        result={self.store.path}
        if self.state is not None and 'records' in self.state:
            result|={self.record_store(i).path for i in range(1,len(self.state['records'])+1)}
        for ref in (self.selection_state['reference'],self.selection_state['pending']):
            if ref is None:continue
            wire=ref if 'phase' in ref else self.selection_frames.expand(ref)
            if wire['phase']!='planned':result.add(self.selection_frames.path(wire))
        return result
