"""Original-bound Assets journal retirement after actual actor process exit.

The final immutable archive retains every child header and original reference.
Missing controls alone are never evidence of restored product state or actor exit.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import os
import re

from adapters.native_feature_observation import exact,need,number
from adapters.normal_feature_state import PrivateFeatureState
from fixture.messages_mixer import start_identity
from overte_phone_assets_evidence import AssetsOriginals,AssetsImages,AssetsDownload
from overte_phone_script_history import pack,unpack,same

NAMES=tuple('phone-assets-'+name+'.json' for name in ('feature','primary-originals','actor-originals','actor-lifecycle'))+tuple('phone-assets-files-owner-'+str(stage)+'.json' for stage in range(1,7))


def terminated(process):
    exact(process,{'pid','start'});need(type(process['pid']) is int and process['pid']>0 and type(process['start']) is str and process['start'].isdecimal())
    path=Path('/proc')/str(process['pid'])/'stat'
    try:fields=path.read_text().rsplit(')',1)[1].split()
    except FileNotFoundError:return True
    need(len(fields)>19 and fields[19].isdecimal())
    return fields[19]!=process['start'] or fields[0] in ('Z','X')


def completed_archive(root,binding,run,guard):
    """Find only this run's one immutable final receipt; no absent-owner ACK."""
    reader=AssetsOriginals(root,binding,run,'primary',guard,lambda *_:need(False),kind='assets-retirement')
    prefix='emote-frame-assets-retirement-'+run+'-primary-0001-'
    paths=list(Path(root).glob(prefix+'*.json'));need(len(paths)==1)
    path=paths[0];digest=path.name[len(prefix):-5];need(re.fullmatch('[0-9a-f]{64}',digest) is not None)
    info=path.lstat();value=dict(emoteOriginalVersion=1,kind='assets-retirement',binding=deepcopy(binding),runId=run,role='primary',index=1,
        sha256=digest,bytes=info.st_size,phase='saved',file=dict(device=info.st_dev,inode=info.st_ino))
    return reader.read(value)


class PhoneAssetsRetirement:
    def __init__(self,feature):
        self.feature=feature;self.store=PrivateFeatureState(feature.store.path.with_name('phone-assets-retirement.json'))
        self.previous=self.state=None
        self.originals=AssetsOriginals(feature.root,feature.binding,feature.run,'primary',self.bound,self.intent,kind='assets-retirement')

    def bound(self):
        f=self.feature;f.lock.assert_held();need(f.guard() is not False and same(self.store.read(),self.previous))
        owner=PrivateFeatureState(f.store.path).read()
        need(self.state is None or same(owner,self.state['owner']) or self.state['phase']=='retiring' and owner is None)
        return True

    def save(self):
        self.bound();value=dict(assetsRetirementVersion=1,runId=self.feature.run,binding=self.feature.binding,payload=pack([self.state]))
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def intent(self,kind,value):
        need(kind=='original' and self.state['phase']=='archiving');self.state['original']=deepcopy(value);self.save();return True

    def validate_archive(self,archive):
        f=self.feature;exact(archive,{'owner','controls','proof','closure'})
        need(archive['owner']['runId']==f.run and same(archive['owner']['binding'],f.binding) and not archive['closure']['active'])
        need(set(archive['controls'])==set(NAMES) and same(archive['controls']['phone-assets-feature.json'],archive['owner']))
        for role in ('primary','actor'):
            header=archive['controls']['phone-assets-'+role+'-originals.json'];need(header is not None)
            exact(header,{'assetsRoleVersion','runId','binding','role','payload'})
            need(type(header['assetsRoleVersion']) is int and header['assetsRoleVersion']==1 and header['runId']==f.run and same(header['binding'],f.binding) and header['role']==role)
            state=unpack(header['payload'])[0];need(state['phase']=='ready' and state['pending'] is None)
            originals=AssetsOriginals(f.root,f.binding,f.run,role,lambda:True,lambda *_:need(False),kind='assets')
            frames=originals.restore(state['manifests'],state['sequence']);need(frames)
            for frame in frames:
                image=frame.get('image')
                if image is not None:
                    if image['phase']=='saved':AssetsImages.archive(f.root,image)
                    else:
                        reader=AssetsImages(f.root,f.binding,f.run,role,image['stage'],lambda:True,lambda *_:need(False))
                        need(image['phase']=='planned' and reader.absent(image))
            for frame in frames:
                file=frame.get('downloadFile')
                if file is not None:AssetsDownload.archive(f.root,file)
            need(not frames[-1].get('diagnostic') and frames[-1]['state']['mappings']==[] and not frames[-1]['state']['open'] and not frames[-1]['state']['sceneModel'] and not frames[-1]['state']['picker'] and frames[-1]['uploads']['source']['retired'])
        owner=unpack(archive['owner']['payload'])[0];need(owner['phase']=='cleaned' and owner['current'] is None and owner['inputStorage'] is None)
        inputs=AssetsOriginals(f.root,f.binding,f.run,'primary',lambda:True,lambda *_:need(False),kind='assets-input').restore(owner['inputs'],owner['inputSequence'])
        f.validate_ownership(inputs);f.validate_assets_ownership(inputs)
        actor=archive['controls']['phone-assets-actor-lifecycle.json'];need(actor is not None)
        need(actor['runId']==f.run and same(actor['binding'],f.binding));actor=unpack(actor['payload'])[0]
        need(actor['phase']=='retired' and actor['pending'] is None and actor['last'] is not None and actor['quiet']['complete']
            and actor['process']!=owner['hostProcess'] and terminated(actor['process']))
        return archive

    def finalize(self):
        f=self.feature;started=previous=f.monotonic()
        for attempt in range(241):
            now=f.monotonic();need(number(now,previous,started+60));previous=now
            with f.lock.held(),f.adapter.existing_input_session(f.selector):
                f.load();self.previous=self.store.read()
                if self.previous is not None:
                    exact(self.previous,{'assetsRetirementVersion','runId','binding','payload'})
                    need(type(self.previous['assetsRetirementVersion']) is int and self.previous['assetsRetirementVersion']==1
                        and self.previous['runId']==f.run and same(self.previous['binding'],f.binding))
                    rows=unpack(self.previous['payload']);need(len(rows)==1);self.state=rows[0]
                    exact(self.state,{'phase','owner','archive','original'});need(self.state['phase'] in ('archiving','retiring'))
                    if f.state is None:f.state=unpack(self.state['owner']['payload'])[0]
                    self.bound();archive=self.state['archive']
                else:
                    if f.state is None:
                        archive=completed_archive(f.root,f.binding,f.run,lambda:f.guard() is not False)
                        f.state=unpack(archive['owner']['payload'])[0];self.validate_archive(archive)
                        need(same(archive['owner']['configuration'],f.public_configuration()) and not f.phase.status()['active'])
                        need(all(PrivateFeatureState(f.store.path.with_name(name)).read() is None for name in NAMES))
                        files={str(stage):archive['controls']['phone-assets-files-owner-'+str(stage)+'.json'] for stage in f.state['stages']}
                        f.restored(file_owners=files)
                        for role in ('primary','actor'):need(f.adapter._world_render_capture(f.selector,read_only=True,role=role,require_trace=True,require_frame_view=True).owner.store.read() is None)
                        return {'performed':True}
                    need(f.state['phase']=='cleaned');closure=f.phase.status();need(not closure['active'])
                    actor=PrivateFeatureState(f.store.path.with_name('phone-assets-actor-lifecycle.json')).read();need(actor is not None)
                    actor_state=unpack(actor['payload'])[0]
                    if actor_state['phase']!='retired' or not terminated(actor_state['process']):
                        need(attempt<240);archive=None
                    else:
                        proof=f.restored();controls={name:PrivateFeatureState(f.store.path.with_name(name)).read() for name in NAMES}
                        archive=dict(owner=deepcopy(f.previous),controls=controls,proof=proof,closure=closure)
                        self.validate_archive(archive)
                        self.state=dict(phase='archiving',owner=deepcopy(f.previous),archive=archive,original=None);self.save()
                if archive is not None:
                    self.validate_archive(archive)
                    if self.state['phase']=='archiving':
                        ref=(self.originals.write(1,archive) if self.state['original'] is None else
                             self.originals.resume_write(1,archive,self.state['original']))
                        need(same(self.originals.read(self.originals.expand(ref)),archive))
                        self.state.update(phase='retiring',original=self.originals.expand(ref));self.save()
                    else:need(same(self.originals.read(self.state['original']),archive))
                    files={str(stage):archive['controls']['phone-assets-files-owner-'+str(stage)+'.json'] for stage in f.state['stages']}
                    f.restored(file_owners=files)
                    for role in ('primary','actor'):
                        owned=f.adapter._world_render_capture(f.selector,read_only=True,role=role,require_trace=True,require_frame_view=True)
                        need(owned.owner.store.read() is None)
                    # Owner is pruned last. Every absent child remains justified
                    # by the exact immutable archive retained before the unlink.
                    for name in tuple(name for name in NAMES if name!='phone-assets-feature.json')+('phone-assets-feature.json',):
                        store=PrivateFeatureState(f.store.path.with_name(name));actual=store.read();original=archive['controls'][name]
                        if actual is not None:need(same(actual,original));store.discard(original)
                        need(store.read() is None)
                    f.previous=None;f.restored(file_owners=files);self.bound()
                    metadata=deepcopy(self.previous);self.store.discard(metadata);need(self.store.read() is None)
                    return {'performed':True}
            need(attempt<240 and f.monotonic()-started<60);f.sleep(.25)
        need(False)
