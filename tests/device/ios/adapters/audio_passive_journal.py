"""Existing immutable frame/index storage for passive Audio ownership journals.

This is a storage facade, never native freshness or resource absence. Separate
bounded query streams avoid growing a single compressed64KiB ownership header.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import exact,integer,need
from adapters.original_frame_store import OriginalFrameStore,MAX_FRAMES,BLOCK
from adapters.script_feature.history import same

STREAMS=('native','passive','proofs')


class AudioPassiveJournal:
    def __init__(self,owner,stream):
        from ios.adapters.audio_passive_owner import IOSAudioPassiveOwner
        need(type(owner) is IOSAudioPassiveOwner and stream in STREAMS)
        self.owner,self.stream=owner,stream
        self.files=OriginalFrameStore(owner.root,owner.binding,owner.run,'actor',owner.file_guard,
            self.intent,namespace='ios-audio-passive-'+stream,schema_prefix='iosAudioPassive',
            kind='sources' if stream=='proofs' else 'inputs',monotonic=owner.monotonic)

    @property
    def slot(self):return self.owner.state['streams'][self.stream]

    def envelope(self,value):
        return dict(audioPassiveJournalVersion=1,leaseId=self.owner.lease,stream=self.stream,ordinal=self.slot['revision']+1,value=deepcopy(value))

    def frame(self,value,ordinal=None):
        exact(value,{'audioPassiveJournalVersion','leaseId','stream','ordinal','value'})
        need(type(value['audioPassiveJournalVersion']) is int and value['audioPassiveJournalVersion']==1
            and value['leaseId']==self.owner.lease and value['stream']==self.stream
            and integer(value['ordinal'],1,MAX_FRAMES) and (ordinal is None or value['ordinal']==ordinal))
        self.owner.validate_entry(self.stream,value['value'],ordinal=value['ordinal']);return value['value']

    def restore(self):
        slot=self.slot;exact(slot,{'revision','manifests'})
        need(integer(slot['revision'],0,MAX_FRAMES))
        return [self.frame(value,index) for index,value in enumerate(self.files.restore(slot['manifests'],slot['revision']),1)]

    def intent(self,event,wire):
        owner=self.owner;owner.file_guard();pending=owner.state['pending']
        if pending is None:
            need(event=='original' and wire['phase']=='planned')
            pending=dict(stream=self.stream,original=None,manifest=None);owner.state['pending']=pending
        need(pending['stream']==self.stream)
        if event=='original':
            self.files.original(wire);need(wire['index']==self.slot['revision']+1)
            old=pending['original']
            if old is not None:
                need(all(wire[key]==old[key] for key in ('index','sha256','bytes','binding','runId','role','kind')))
            pending['original']=deepcopy(wire)
        else:
            need(event=='manifest' and pending['original'] is not None)
            exact(wire,{'iosAudioPassiveManifestVersion','reference','phase'})
            need(type(wire['iosAudioPassiveManifestVersion']) is int and wire['iosAudioPassiveManifestVersion']==1
                and wire['phase'] in ('planned','saved'))
            self.files.manifest_reference(wire['reference']);pending['manifest']=deepcopy(wire)
        owner.save();return True

    def append(self,value):
        owner=self.owner;owner.file_guard();need(not owner.historical and owner.state['pending'] is None)
        owner.validate_entry(self.stream,value,ordinal=self.slot['revision']+1)
        reference=self.files.write(self.slot['revision']+1,self.envelope(value))
        self.complete(reference);return reference

    def complete(self,reference):
        owner=self.owner;pending=owner.state['pending'];need(pending is not None and pending['stream']==self.stream)
        actual=self.frame(self.files.read(self.files.expand(reference)),reference['index'])
        manifests=self.files.append(self.slot['manifests'],reference)
        owner.admit_storage_paths(self,pending);owner.link_entry(self.stream,actual)
        self.slot.update(revision=self.slot['revision']+1,manifests=manifests)
        owner.state['pending']=None;owner.save()

    def recover(self):
        owner=self.owner;pending=owner.state['pending'];need(not owner.historical)
        if pending is None:return
        need(pending['stream']==self.stream);wire=pending['original'];need(wire is not None)
        # A planned file has no known birth inode and cannot be adopted. Opened
        # files are adopted only after actual complete bytes/FD identity checks.
        need(wire['phase'] in ('opened','saved') and wire['index']==self.slot['revision']+1)
        actual_value=self.frame(self.files.read(wire),wire['index']);reference=self.files.compact(dict(wire,phase='saved'))
        manifest=pending['manifest']
        if manifest is None or not self.files.manifest_path(manifest['reference']).exists():
            self.complete(reference);return
        target=manifest['reference'];actual=self.files.manifest(target)
        block=(reference['index']-1)//BLOCK+1;offset=(reference['index']-1)%BLOCK+1
        previous=deepcopy(self.slot['manifests'])
        if offset==1:
            need(len(previous)==block-1);expected=[reference]
        else:
            need(len(previous)==block and previous[-1]['count']==offset-1)
            expected=self.files.manifest(previous.pop())+[reference]
        need(target['block']==block and target['count']==offset and same(actual,expected))
        owner.admit_storage_paths(self,pending);owner.link_entry(self.stream,actual_value)
        self.slot.update(revision=self.slot['revision']+1,manifests=previous+[deepcopy(target)])
        owner.state['pending']=None;owner.save()

    def reference(self,index):
        need(integer(index,1,self.slot['revision']))
        block=(index-1)//BLOCK
        rows=self.files.manifest(self.slot['manifests'][block])
        result=rows[(index-1)%BLOCK];need(result['index']==index);return result

    def read(self,index):return self.frame(self.files.read(self.files.expand(self.reference(index))),index)

    def inventory(self):
        """Exact retained original/index membership, including older snapshots."""
        expected=set()
        for manifest in self.slot['manifests']:
            rows=self.files.manifest(manifest)
            for row in rows:expected.add(self.files.path(self.files.expand(row)))
            body=dict(iosAudioPassiveManifestVersion=1,kind=self.files.kind,binding=self.owner.binding,
                runId=self.owner.run,role='actor',block=manifest['block'],entries=[])
            from adapters.script_feature.history import canonical
            import hashlib
            for count in range(1,len(rows)+1):
                prefix=dict(body,entries=rows[:count]);raw=canonical(prefix)
                reference=dict(block=manifest['block'],count=count,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
                need(same(self.files.manifest(reference),rows[:count]));expected.add(self.files.manifest_path(reference))
        pending=self.owner.state['pending']
        if pending is not None and pending['stream']==self.stream:
            if pending['original'] is not None:
                expected.add(self.files.path(pending['original']))
            if pending['manifest'] is not None:
                expected.add(self.files.manifest_path(pending['manifest']['reference']))
        return expected
