"""One joined Scene shares only its existing guarded raw manifest-index reader.

Every requested original frame is still reopened, hashed and typed. Appearance,
restoration and quiet/resource results are never cached. The reader cannot
escape its one Scene/Source pair or survive the synchronous join boundary.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path

from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.script_feature.history import same
from ios.adapters import avatar_observation as observation,avatar_cleanup_sources as cleanup
from ios.adapters.avatar_record_cache import AvatarRecordCache
from ios.adapters.avatar_sources import IOSAvatarSources
from ios.adapters.emote_original_lease import EmoteOriginalLease


def method(value):
    return getattr(value,'__self__',None),getattr(value,'__func__',value)


class JoinedManifestReader:
    def __init__(self,scene,original,sources):
        from ios.adapters.avatar_held_scene import IOSAvatarHeldScene
        need(type(scene) is IOSAvatarHeldScene and type(sources) is IOSAvatarSources
            and sources.historical and sources.state['phase']=='ready' and sources.state['pending'] is None
            and sources.lock is scene.lock and sources.root==scene.root and sources.run==scene.run
            and sources.role==scene.role and same(sources.binding,scene.binding))
        self.scene,self.original,self.sources=scene,original,sources
        self.scene_store,self.source_store,self.originals=scene.store,sources.store,sources.originals
        self.frames=sources.frames;self.frame_objects=tuple(map(id,self.frames));self.frame_sha=digest(self.frames)
        self.reader=observation._AppearanceFrames(sources);self.cache=self.reader.cache
        self.active=False;self.closed=False
        self.methods=[]
        slots=[(observation,('appearance','frame','source_history','state_original','_AppearanceFrames')),
            (cleanup,('restored','restored_held','_restored')),
            (scene,('envelope','record','source','joined','_joined','_joined_history','restored_sources')),
            (sources,('envelope','decode','validate_frame','_validate_frame','file_guard')),
            (self.scene_store,('read',)),(self.source_store,('read',)),
            (self.originals,('key','manifest_reference','manifest','manifest_path','expand','read','original','path','file','now','bound','guard')),
            (self.reader,('identity','plain_manifest','manifest','__call__','verify')),
            (type(self.reader),('__init__','identity','plain_manifest','manifest','__call__','verify')),
            (self.cache,('read','check','_read','signatures','absent')),
            (AvatarRecordCache,('read','check','_read','signatures','absent')),
            (self,('identity','guard','verify','__call__','__enter__','__exit__'))]
        for owner,names in slots:
            for name in names:self.methods.append((owner,name,method(getattr(owner,name))))
        self.methods=tuple(self.methods);self.owner=self.identity()
        roots={Path(scene.root),scene.store.path.parent,sources.store.path.parent,sources.lock.path.parent}
        selected=[]
        for root in sorted(roots,key=lambda path:(len(path.parts),str(path))):
            if not any(root.is_relative_to(parent) for parent in selected):selected.append(root)
        self.leases=[EmoteOriginalLease(root,[]) for root in selected]
        need(same(scene.envelope(scene.state),scene.previous)
            and same(sources.envelope(sources.state,version=sources.previous['iosAvatarSourcesVersion']),sources.previous))

    def identity(self):
        scene,source=self.scene,self.sources;store=source.originals
        return (type(scene),type(source),type(scene.store),type(source.store),type(store),type(self.reader),type(self.cache),
            scene.VERSION,id(scene.Marker),id(scene.Samples),id(scene.store),id(source.store),id(source.originals),id(source.lock),id(scene.lock),
            id(source.frames),tuple(map(id,source.frames)),id(self.reader),id(self.cache),id(self.methods),
            id(self.reader.missing),id(self.reader.references),id(self.reader.plain),id(self.reader.parents),id(self.reader.context),id(self.cache.rows),
            digest(dict(scenePrevious=scene.previous,sceneState=scene.state,sourcePrevious=source.previous,
                sourceState=source.state,original=self.original,readerContext=self.reader.context,
                readerParents={str(path):value for path,value in self.reader.parents.items()},
                sceneHeader=dict(root=str(scene.root),store=str(scene.store.path),binding=scene.binding,runId=scene.run,
                    role=scene.role,historical=scene.historical,baseline=scene.baseline,clock=scene.clock,paths={k:str(v) for k,v in scene.paths.items()}),
                sourceHeader=dict(root=str(source.root),store=str(source.store.path),binding=source.binding,
                    runId=source.run,role=source.role,pid=source.pid,historical=source.historical),
                originals=dict(root=str(store.root),binding=store.binding,runId=store.run,role=store.role,
                    namespace=store.namespace,schemaPrefix=store.schema_prefix,kind=store.kind))))

    def guard(self,sources):
        need(self.active and not self.closed and sources is self.sources
            and self.scene.store is self.scene_store and sources.store is self.source_store
            and sources.originals is self.originals and sources.frames is self.frames
            and self.reader.sources is sources and self.reader.cache is self.cache
            and self.identity()==self.owner)
        sources.lock.assert_held();self.scene.lock.assert_held()
        for owner,name,expected in self.methods:
            actual=method(getattr(owner,name));need(actual[0] is expected[0] and actual[1] is expected[1])
        need(same(self.scene_store.read(),self.scene.previous) and same(self.source_store.read(),sources.previous))
        return self

    def __enter__(self):
        need(not self.active and not self.closed);self.active=True
        try:
            self.guard(self.sources);need(digest(self.frames)==self.frame_sha)
            for lease in self.leases:lease.guard()
            return self
        except BaseException:
            self.active=False;self.closed=True;raise

    def __call__(self,index):
        self.guard(self.sources);result=self.reader(index);self.guard(self.sources);return result

    def verify(self):
        self.guard(self.sources);self.reader.verify();self.guard(self.sources)

    def __exit__(self,kind,value,traceback):
        try:
            self.verify();need(digest(self.frames)==self.frame_sha)
            for lease in self.leases:lease.guard()
            need(same(self.scene.envelope(self.scene.state),self.scene.previous)
                and same(self.sources.envelope(self.sources.state,version=self.sources.previous['iosAvatarSourcesVersion']),self.sources.previous))
        finally:self.active=False;self.closed=True


def checked(reader,sources):
    need(type(reader) is JoinedManifestReader);return JoinedManifestReader.guard(reader,sources)
