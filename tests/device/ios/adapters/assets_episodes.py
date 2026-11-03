"""Preserved Assets output namespaces below the original selected SDK roots.

These originals authorize host storage only. They establish no input delivery,
effective permission, product success, resource absence or whole feature end.
No session, source channel, process or installed-code owner is created here.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import ExitStack, contextmanager
from copy import deepcopy
from pathlib import Path
import os
import stat
import time
from adapters.native_feature_observation import exact, integer, need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from ios.adapters.assets_end_graph import AssetsFinalArchive

VERSION=1
PLAN=(('picker','gltf-bundle/main.gltf'),('upload','gltf-bundle/main.gltf'),
      ('upload','obj-bundle/main.obj'),('upload','asset-stand.fbx'),
      ('picker','gltf-bundle/main.gltf'))


def directory(path):
    path=Path(path);need(path.is_absolute() and path.resolve(strict=True)==path)
    info=path.lstat()
    need(stat.S_ISDIR(info.st_mode) and info.st_uid==os.geteuid() and stat.S_IMODE(info.st_mode)==0o700)
    return dict(device=info.st_dev,inode=info.st_ino,uid=info.st_uid,mode=stat.S_IMODE(info.st_mode))


class AssetsEpisodes:
    """One existing-run journal; each episode retains its actual directories."""
    def __init__(self,selected,locks,*,monotonic=time.monotonic):
        need(type(selected) is AssetsFinalArchive and callable(monotonic));exact(locks,{'primary','actor'})
        self.selected,self.locks,self.monotonic=selected,dict(locks),monotonic
        selected.selected_guard();need(selected.state==dict(phase='selected'))
        self.run=selected.run;self.context=deepcopy(selected.context);self.selection=selected.link()
        self.parents={}
        for role,info in self.context['roles'].items():
            lock=self.locks[role];need(isinstance(lock,ScriptSourceLock) and lock.path==Path(info['stateRoot'])/'script-feature-sources.lock')
            lock.assert_held()
            for kind in ('stateRoot','artifactRoot'):
                path=Path(info[kind]);self.parents[str(path)]=directory(path)
        self.store=PrivateFeatureState(Path(self.context['roles']['primary']['stateRoot'])/('ios-assets-episodes-'+self.run+'.json'))
        self.previous=self.store.read();self.state=dict(entries=[]) if self.previous is None else self.decode(self.previous)
        self.originals=OriginalFrameStore(Path(self.context['roles']['primary']['artifactRoot']),
            self.context['roles']['primary']['binding'],self.run,'primary',self.original_guard,self.intent,
            namespace='assets-episode',schema_prefix='iosAssetsEpisode',monotonic=monotonic)
        self.guard()

    def envelope(self):
        return dict(iosAssetsEpisodesVersion=VERSION,runId=self.run,selectedPair=deepcopy(self.selection),
                    parentDirectories=deepcopy(self.parents),entries=deepcopy(self.state['entries']))

    def decode(self,value):
        exact(value,{'iosAssetsEpisodesVersion','runId','selectedPair','parentDirectories','entries'})
        need(type(value['iosAssetsEpisodesVersion']) is int and value['iosAssetsEpisodesVersion']==VERSION
            and value['runId']==self.run and same(value['selectedPair'],self.selection)
            and same(value['parentDirectories'],self.parents) and type(value['entries']) is list and len(value['entries'])<=len(PLAN))
        for index,entry in enumerate(value['entries'],1):
            exact(entry,{'index','kind','resource','ticket','phase','directories','original'})
            need(type(entry['index']) is int and entry['index']==index and (entry['kind'],entry['resource'])==PLAN[index-1])
            identifier(entry['ticket']);need(entry['phase'] in ('planned','ready'))
            exact(entry['directories'],{'primary','actor'})
            for role,roots in entry['directories'].items():
                exact(roots,{'stateRoot','artifactRoot'})
                for kind,row in roots.items():
                    exact(row,{'path','identity'});need(row['path']==str(self.path(index,role,kind)))
                    if row['identity'] is not None:
                        exact(row['identity'],{'device','inode','uid','mode'})
                        need(integer(row['identity']['device'],0,2**64-1) and integer(row['identity']['inode'],1,2**64-1)
                            and row['identity']['uid']==os.geteuid() and row['identity']['mode']==0o700)
                    if entry['phase']=='ready':need(row['identity'] is not None)
            need(entry['original'] is None or type(entry['original']) is dict)
            if entry['phase']=='ready':need(entry['original'] is not None and entry['original'].get('phase')=='saved')
            else:need(index==len(value['entries']))
        return dict(entries=deepcopy(value['entries']))

    def path(self,index,role,kind):
        need(integer(index,1,len(PLAN)) and role in ('primary','actor') and kind in ('stateRoot','artifactRoot'))
        suffix='state' if kind=='stateRoot' else 'artifacts'
        return Path(self.context['roles'][role][kind])/('assets-episode-'+self.run+'-'+str(index)+'-'+role+'-'+suffix)

    def original_guard(self):
        self.selected.selected_guard();need(same(self.selected.context,self.context) and same(self.selected.link(),self.selection))
        for lock in self.locks.values():lock.assert_held()
        for path,pin in self.parents.items():need(same(directory(Path(path)),pin))
        need(same(self.store.read(),self.previous));return True

    def guard(self):
        self.original_guard()
        known={Path(row['path']) for entry in self.state['entries'] for roots in entry['directories'].values() for row in roots.values()}
        for entry in self.state['entries']:
            wire=entry['original']
            if wire is not None and wire['phase']!='planned':known.add(self.originals.path(wire))
        for parent in self.parents:
            entries=list(Path(parent).iterdir());need(len(entries)<=8192)
            need(all(path in known or not path.name.startswith('assets-episode-') for path in entries))
        for entry in self.state['entries']:
            for roots in entry['directories'].values():
                for row in roots.values():
                    path=Path(row['path'])
                    if row['identity'] is None:need(not os.path.lexists(path))
                    else:need(same(directory(path),row['identity']))
            if entry['original'] is not None:
                wire=entry['original'];self.originals.original(wire);need(wire['index']==entry['index'])
                if wire['phase']=='planned':need(not os.path.lexists(self.originals.path(wire)))
                else:need(same(self.originals.read(wire),self.frame(entry)))
        return True

    def save(self):
        value=self.envelope();self.decode(value)
        self.selected.selected_guard()
        for lock in self.locks.values():lock.assert_held()
        need(same(self.store.read(),self.previous));self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)

    def frame(self,entry):
        return dict(assetsEpisodeSelectionVersion=VERSION,runId=self.run,selectedPair=deepcopy(self.selection),
            index=entry['index'],kind=entry['kind'],resource=entry['resource'],ticket=entry['ticket'],
            directories=deepcopy(entry['directories']))

    def intent(self,event,wire):
        need(event=='original' and self.state['entries']);entry=self.state['entries'][-1]
        need(entry['phase']=='planned' and wire['index']==entry['index'])
        self.originals.original(wire);entry['original']=deepcopy(wire);self.save();return True

    def begin(self,index,ticket):
        """Record intent before mkdir and refuse adoption of uncertain births."""
        self.guard();need(self.selected.state==dict(phase='selected'));identifier(ticket);need(integer(index,1,len(PLAN)) and index==len(self.state['entries'])+1)
        need(not self.state['entries'] or self.state['entries'][-1]['phase']=='ready')
        kind,resource=PLAN[index-1]
        roots={role:{name:dict(path=str(self.path(index,role,name)),identity=None)
                     for name in ('stateRoot','artifactRoot')} for role in ('primary','actor')}
        need(not any(os.path.lexists(row['path']) for values in roots.values() for row in values.values()))
        entry=dict(index=index,kind=kind,resource=resource,ticket=ticket,phase='planned',directories=roots,original=None)
        self.state['entries'].append(entry);self.save()
        return self.finish_birth(index)

    def finish_birth(self,index):
        """Continue only recorded absences/inodes; never assign an orphan inode."""
        self.guard();need(self.selected.state==dict(phase='selected') and integer(index,1,len(self.state['entries'])));entry=self.state['entries'][index-1]
        if entry['phase']=='ready':return AssetsEpisodeScope(self,index)
        need(index==len(self.state['entries']))
        for roots in entry['directories'].values():
            for row in roots.values():
                if row['identity'] is not None:continue
                path=Path(row['path']);need(not os.path.lexists(path));path.mkdir(mode=0o700)
                row['identity']=directory(path);self.save()
        pending=entry['original'];frame=self.frame(entry)
        if pending is None:self.originals.write(index,frame)
        else:
            need(pending['phase'] in ('opened','saved') and same(self.originals.read(pending),frame))
            entry['original']=dict(pending,phase='saved');self.save()
        need(entry['original']['phase']=='saved');entry['phase']='ready';self.save();self.guard()
        return AssetsEpisodeScope(self,index)

    def scope(self,index):
        self.guard();need(integer(index,1,len(self.state['entries'])) and self.state['entries'][index-1]['phase']=='ready')
        return AssetsEpisodeScope(self,index)


class AssetsEpisodeScope:
    """The output path and local lock, retaining the independent SDK lock."""
    def __init__(self,owner,index):
        need(type(owner) is AssetsEpisodes and integer(index,1,len(owner.state['entries'])))
        self.owner,self.index=owner,index;self.locks={}
        owner.guard();entry=owner.state['entries'][index-1];need(entry['phase']=='ready')
        self.original=deepcopy(entry['original']);self.descriptor=owner.frame(entry)
        for role in ('primary','actor'):
            self.locks[role]=ScriptSourceLock(Path(self.descriptor['directories'][role]['stateRoot']['path'])/'script-feature-sources.lock')

    def guard(self):
        self.owner.guard();entry=self.owner.state['entries'][self.index-1]
        need(entry['phase']=='ready' and same(entry['original'],self.original) and same(self.owner.frame(entry),self.descriptor))
        return True

    def role(self,selector):
        self.guard();roles=[role for role,info in self.owner.context['roles'].items() if info['target']==selector]
        need(len(roles)==1);return roles[0]

    def runtime_guard(self,runtime,selector,lock=None,binding=None):
        role=self.role(selector);info=self.owner.context['roles'][role]
        need(self.owner.selected.state==dict(phase='selected')
            and self.owner.state['entries'] and self.owner.state['entries'][-1]['index']==self.index
            and self.owner.state['entries'][-1]['phase']=='ready')
        need(runtime.state_path(selector).parent==Path(info['stateRoot']))
        self.owner.locks[role].assert_held()
        if lock is not None:need(lock is self.locks[role]);lock.assert_held()
        if binding is not None:need(same(binding,info['binding']))
        return True

    def state_path(self,runtime,selector):
        self.runtime_guard(runtime,selector);role=self.role(selector)
        return Path(self.descriptor['directories'][role]['stateRoot']['path'])/runtime.state_path(selector).name

    def artifact_root(self,selector):
        return Path(self.descriptor['directories'][self.role(selector)]['artifactRoot']['path'])

    def link(self):
        self.guard();return dict(episodesPath=str(self.owner.store.path),index=self.index,reference=deepcopy(self.original))

    @contextmanager
    def held(self):
        self.guard()
        with ExitStack() as stack:
            for role in ('actor','primary'):stack.enter_context(self.locks[role].held())
            self.guard();yield self;self.guard()
