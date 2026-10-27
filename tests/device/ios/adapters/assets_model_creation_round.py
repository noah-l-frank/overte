"""One synchronous decoder's actual Model result; never a persistent proof.

The original Model and its input frames are decoded first. Every use retains
the actual candidate callback, parent WAL/memory and private directory prefix
guards. Nothing can survive the surrounding decoder or a write/query boundary.
Directory pins protect consistency; they never grant original-file membership.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import stat
from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import same,unpack
from ios.adapters.assets_model_owner import OwnedAssetsModel
from ios.adapters.assets_model_sources import AssetsModelSources
from ios.adapters.assets_upload import OwnedAssetsUpload
from ios.adapters.assets_usage_owner import OwnedAssetsUsage
from ios.adapters import assets_model_facts as facts
from ios.adapters import assets_model_sources as model_sources,assets_model_origin as origin


def function(value):
    value=getattr(value,'__func__',value)
    return value,getattr(value,'__code__',None)


_MODEL=function(OwnedAssetsModel.decode)
_MODEL_FRAME=function(AssetsModelSources.frame)
_MODEL_DECODE=function(AssetsModelSources.decode)
_MODEL_INTERNAL=function(AssetsModelSources._decode_with_frame)
_UPLOAD=function(OwnedAssetsUpload.decode)
_USAGE=function(OwnedAssetsUsage.decode)
_FACTS=tuple(function(value) for value in (facts.owner,facts.accepted,facts.imported))


def parsers():
    return tuple(function(value) for value in (model_sources.decode,model_sources.validate_join,model_sources.native_packet,
        model_sources.create_state.validate,model_sources.create_work.validate,origin.validate))


_PARSERS=parsers()


def eligible(source):
    model=source.model
    return (hasattr(source,'previous') and hasattr(source,'state')
        and type(model) is OwnedAssetsModel and type(model.sources) is AssetsModelSources
        and type(model.usage) is OwnedAssetsUsage and type(model.usage.source) is OwnedAssetsUpload
        and function(model.decode)==_MODEL and function(model.sources.frame)==_MODEL_FRAME
        and function(model.sources.decode)==_MODEL_DECODE and function(model.usage.source.decode)==_UPLOAD
        and function(source._decode_with_frame)==_MODEL_INTERNAL and function(model.sources._decode_with_frame)==_MODEL_INTERNAL
        and function(model.usage.decode)==_USAGE
        and tuple(function(value) for value in (facts.owner,facts.accepted,facts.imported))==_FACTS
        and parsers()==_PARSERS
        # A nested upload capture can legitimately be between its own memory
        # update and CAS. Keep that existing public path, never reuse it.
        and all(getattr(owner,'previous',None) is not None and hasattr(owner,'state')
            and same(unpack(owner.previous['payload']),[owner.state])
            for owner in (model,model.sources,model.usage,model.usage.source)))


class ModelCreationRound:
    def __init__(self,source):
        need(eligible(source));self.source,self.model=source,source.model;self.active=True
        self.parents=(self.model,self.model.sources,self.model.usage,self.model.usage.source)
        self.root=Path(source.store.path.parent)
        need(all(owner.store.path.parent==self.root for owner in self.parents))
        self.guard();self.headers()
        # Reopen actual Model input originals before consuming their cached
        # projections. The ordinary public decoders remain the authority.
        decoded=self.model.sources.decode(self.model.sources.previous)
        need(same(decoded,self.model.sources.state))
        decoded=self.model.decode(self.model.previous);need(same(decoded,self.model.state) and decoded['creation'] is not None)
        for owner in self.parents:
            states=unpack(owner.previous['payload']);need(len(states)==1 and same(states[0],owner.state))
        self.creation=deepcopy(decoded['creation'])
        self.methods=self.method_identity();self.memory=self.memory_identity();self.nodes=self.directory_identity()
        self.check()

    def guard(self):
        for owner in (self.source,*self.parents):
            lock=getattr(owner,'lock',None)
            if lock is not None:lock.assert_held()
        # Invoke the actual callback used by Upload original reads, including
        # its candidate/current-clock guards. Do not memoize its verdict.
        need(self.model.usage.source.originals.guard() is not False)
        PrivateFeatureState(self.source.store.path)._parent()

    def headers(self):
        for owner in (self.source,*self.parents):need(same(owner.store.read(),owner.previous))

    def method_identity(self):
        return parsers()+tuple(function(value) for value in (self.source.frame,self.source._frame_from_creation,
            self.source._origin_source,self.source._origin_frame,self.model.decode,self.model.sources.decode,
            self.source._decode_with_frame,self.model.sources._decode_with_frame,self.model.sources.frame,
            self.model.sources.reader_module,self.source.reader_module,self.model.usage.decode,self.model.usage.source.decode,
            self.model.usage.source.originals.guard,facts.owner,facts.accepted,facts.imported))

    def memory_identity(self):
        upload=self.model.usage.source;model_source=self.model.sources
        return digest([[(owner.store.path.as_posix(),owner.previous,owner.state) for owner in self.parents],
            model_source._cached,upload._cached,upload._validated_refs,upload._projects,
            model_source.raws.manifest(),upload.binding,model_source.binding,model_source.run,model_source.role,
            upload.clock.pid,model_source.native.pid,self.source.previous,self.source.state])

    def directory_identity(self):
        entries=list(self.root.iterdir());need(len(entries)<=4096);result={}
        for path in entries:
            value=path.lstat();need(stat.S_ISREG(value.st_mode) or stat.S_ISDIR(value.st_mode))
            result[path.name]=(value.st_dev,value.st_ino,value.st_mode,value.st_uid,value.st_gid,value.st_nlink,
                value.st_size,value.st_mtime_ns,value.st_ctime_ns)
        value=self.root.stat();return (value.st_dev,value.st_ino),result

    def check(self):
        need(self.active and eligible(self.source));self.guard();self.headers()
        need(self.methods==self.method_identity() and self.memory==self.memory_identity()
            and self.nodes==self.directory_identity())
        self.guard();return True

    def close(self):
        try:self.check()
        finally:self.active=False;self.creation=None
