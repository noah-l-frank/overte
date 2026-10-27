"""Closed original part dispatch; legacy Parts1 remains unchanged."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.script_feature.history import canonical
from copy import deepcopy
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need
from ios.adapters.world_web_parts import WorldWebParts
from ios.adapters.world_web_snapshot_parts import WorldWebSnapshotParts
from ios.adapters.world_web_surfaces_parts import WorldWebSurfacesParts
from adapters.original_frame_store import OriginalFrameStore
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters.world_web_original_membership import OriginalMembership


class WorldWebOriginalParts:
    def __init__(self,owner):self.legacy=WorldWebParts(owner);self.snapshot=WorldWebSnapshotParts(owner);self.surfaces=WorldWebSurfacesParts(owner);self.closures=WorldWebSurfacesParts(owner,name='closures')
    def store(self,name):return getattr(self,name).store() if name in ('surfaces','closures') else self.legacy.store(name)
    def validate(self,value):
        if 'worldWebAuxProjectionVersion' in value:return self.aux_projection(value)
        if 'worldWebClosuresPartVersion' in value:return self.closures.validate(value)
        if 'worldWebSurfacesPartVersion' in value:return self.surfaces.validate(value)
        return self.snapshot.projection(value) if 'worldWebSnapshotProjectionVersion' in value else self.legacy.validate(value)
    def write(self,name,index,original):return getattr(self,name).write(index,original) if name in ('surfaces','closures') else self.legacy.write(name,index,original)
    def read(self,value):
        if 'worldWebAuxProjectionVersion' in value:
            self.aux_projection(value);bundle=self.aux_original(value['parent'])
            return deepcopy(bundle['originals']['widgetReceipt']['observation'] if value['name']=='widgets' else bundle['originals'][value['name']])
        if 'worldWebClosuresPartVersion' in value:return self.closures.read(value)
        if 'worldWebSurfacesPartVersion' in value:return self.surfaces.read(value)
        return self.snapshot.read(value) if 'worldWebSnapshotProjectionVersion' in value else self.legacy.read(value)
    def read_frame(self,originals):
        """Decode each actual auxiliary parent once in this one frame call.

        Every projection remains independently validated and copied. Current
        owner guards and the original file deadlines still run on each use;
        no DTO or actual-read membership survives this call.
        """
        need(type(originals) is dict)
        if not any('worldWebAuxProjectionVersion' in value for value in originals.values()) or not _literal_frame_readers(self):
            return {name:self.read(value) for name,value in originals.items()}
        parents={};result={};owner=self.legacy.owner;aux_store=None
        def header():
            need(self.legacy.owner is owner and self.snapshot.owner is owner)
            return (id(self.legacy),id(self.snapshot),id(owner.store),str(owner.store.path),deepcopy(owner.binding),
                owner.run,owner.role,id(owner.guard),id(owner.monotonic))
        initial=header()
        def guard():
            need(_literal_frame_readers(self) and header()==initial)
            if aux_store is not None:need(self.legacy.store('widgets') is aux_store)
            for _reference,_bundle,pins,_membership in parents.values():self.snapshot.guard(pins)
        try:
            for name,value in originals.items():
                guard()
                if 'worldWebAuxProjectionVersion' not in value:
                    result[name]=self.read(value);guard();continue
                self.aux_projection(value);parent=value['parent'];key=digest(parent)
                # A current guard may change the active actual-read census.
                # Run it before deciding whether this call already read bytes.
                store=self.legacy.store('widgets');started=store.now();store.bound(started);guard()
                if aux_store is None:aux_store=store
                else:need(store is aux_store)
                previous=parents.get(key)
                if previous is not None:need(parent==previous[0])
                if previous is None or not previous[3].matches():
                    pins={path:self.snapshot.signature(path) for path in self.paths(parent)}
                    bundle=self.aux_original(parent);self.snapshot.guard(pins)
                    parents[key]=(deepcopy(parent),bundle,pins,OriginalMembership())
                else:bundle=previous[1]
                # Reusing historical bytes must not reuse a current process
                # check. Keep the same live guard and per-reader five seconds.
                guard()
                result[name]=deepcopy(bundle['originals']['widgetReceipt']['observation'] if value['name']=='widgets' else bundle['originals'][value['name']])
                store.bound(started);guard();need(parents[key][3].matches())
            # A new census cannot inherit even an earlier projection's reads.
            need(all(membership.matches() for _reference,_bundle,_pins,membership in parents.values()))
            return result
        finally:guard()
    def read_bytes(self,value):
        if 'worldWebAuxProjectionVersion' in value:return canonical(self.read(value))
        if 'worldWebClosuresPartVersion' in value:return self.closures.read_bytes(value)
        if 'worldWebSurfacesPartVersion' in value:return self.surfaces.read_bytes(value)
        return canonical(self.snapshot.read(value)) if 'worldWebSnapshotProjectionVersion' in value else self.legacy.read_bytes(value)
    def verify(self,value):
        if 'worldWebAuxProjectionVersion' in value:self.read(value)
        elif 'worldWebClosuresPartVersion' in value:self.closures.read_bytes(value)
        elif 'worldWebSurfacesPartVersion' in value:self.surfaces.read_bytes(value)
        elif 'worldWebSnapshotProjectionVersion' in value:self.snapshot.verify_projection(value)
        else:self.legacy.read_bytes(value)
    def verify_frame(self,originals):
        """Read each actual auxiliary parent once in this synchronous frame.

        Four closed projections can name the same original bundle. Validate
        every projection and the entire typed bundle, retaining only local
        inode pins until this call exits. No result survives this call and a
        later frame/census must execute the original readers again.
        """
        need(type(originals) is dict);parents={}
        def guard():
            for _reference,pins in parents.values():self.snapshot.guard(pins)
        try:
            for value in originals.values():
                if 'worldWebAuxProjectionVersion' not in value:self.verify(value);guard();continue
                self.aux_projection(value);parent=value['parent'];key=digest(parent)
                if key not in parents:
                    pins={path:self.snapshot.signature(path) for path in self.paths(parent)}
                    parents[key]=(deepcopy(parent),pins);self.aux_original(parent)
                else:need(parent==parents[key][0])
                guard()
        finally:guard()
    def paths(self,value):
        if 'worldWebAuxProjectionVersion' in value:
            self.aux_projection(value);return self.paths(value['parent'])
        if 'worldWebClosuresPartVersion' in value:return self.closures.paths(value)
        if 'worldWebSurfacesPartVersion' in value:return self.surfaces.paths(value)
        if 'worldWebSnapshotProjectionVersion' in value:
            self.snapshot.projection(value);return self.snapshot.paths(value['parent'])
        self.legacy.validate(value);store=self.legacy.store(value['name']);return [store.path(store.expand(reference)) for reference in value['chunks']]
    def aux_projection(self,value):
        exact(value,{'worldWebAuxProjectionVersion','name','index','acquisitionId','parent'})
        need(type(value['worldWebAuxProjectionVersion']) is int and value['worldWebAuxProjectionVersion']==1 and value['name'] in ('widgets','widgetReceipt','uikit','browser'))
        self.legacy.validate(value['parent']);need(value['parent']['name']=='widgets' and type(value['index']) is int
            and value['index']==value['parent']['index'] and value['acquisitionId']==value['parent']['acquisitionId'])
        return value
    def aux_original(self,parent):
        value=self.legacy.read(parent);exact(value,{'worldWebAuxOriginalVersion','index','acquisitionId','originals'})
        need(type(value['worldWebAuxOriginalVersion']) is int and value['worldWebAuxOriginalVersion']==1
            and type(value['index']) is int and value['index']==parent['index'] and value['acquisitionId']==parent['acquisitionId'])
        exact(value['originals'],{'widgetReceipt','uikit','browser'})
        receipt=value['originals']['widgetReceipt'];exact(receipt,{'schemaVersion','commandId','observation'})
        need(type(receipt['schemaVersion']) is int and receipt['schemaVersion']==1 and type(receipt['observation']) is dict)
        return value
    def write_aux(self,index,originals):
        owner=self.legacy.owner;exact(originals,{'widgetReceipt','uikit','browser'})
        parent=self.legacy.write('widgets',index,dict(worldWebAuxOriginalVersion=1,index=index,
            acquisitionId=owner.state['pending']['start']['nativeBefore']['requestId'],originals=deepcopy(originals)))
        need(canonical(self.aux_original(parent)['originals'])==canonical(originals))
        return {name:dict(worldWebAuxProjectionVersion=1,name=name,index=index,acquisitionId=parent['acquisitionId'],parent=deepcopy(parent))
            for name in ('widgets','widgetReceipt','uikit','browser')}


def _reader(value):
    function=getattr(value,'__func__',value);wrapped=getattr(function,'__wrapped__',None)
    return function,getattr(function,'__code__',None),wrapped,getattr(wrapped,'__code__',None)


_FRAME_READERS={
    WorldWebOriginalParts:('read','aux_original','aux_projection','paths'),
    WorldWebParts:('store','read','read_bytes','validate'),
    WorldWebSnapshotParts:('signature','guard'),
    OriginalFrameStore:('key','now','bound','read','path','original','file','expand'),
    PrivateFeatureState:('_parent',),
}
_LITERAL_FRAME_READERS={kind:{name:_reader(getattr(kind,name)) for name in names} for kind,names in _FRAME_READERS.items()}


def _literal_frame_readers(parts):
    # A substituted reader may deliberately produce a different second DTO.
    # Such callers retain the literal per-projection dispatch, including code
    # replacement on the same function object and instance-level overrides.
    for kind,names in _LITERAL_FRAME_READERS.items():
        if any(_reader(getattr(kind,name))!=expected for name,expected in names.items()):return False
    for instance,kind in ((parts,WorldWebOriginalParts),(parts.legacy,WorldWebParts),(parts.snapshot,WorldWebSnapshotParts),
            *((store,OriginalFrameStore) for store in parts.legacy._stores.values())):
        if type(instance) is not kind:return False
        if any(_reader(getattr(instance,name))!=expected for name,expected in _LITERAL_FRAME_READERS[kind].items()):return False
    return True
