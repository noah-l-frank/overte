"""Operation-local immutable Tablet record interpretation, never live facts.

Reuse the committed file-signature/read-membership primitive unchanged. Current
WALs, pending/rejected rows and cross-record history floors remain outside hits.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from contextvars import ContextVar
from adapters.native_feature_observation import need
from adapters.script_feature.history import canonical
from ios.adapters.avatar_record_cache import AvatarRecordCache

_ACTIVE=ContextVar('tablet_web_immutable_records',default=None)
MAX_ENTRIES=512
MAX_BYTES=8*1024*1024


class TabletRecordCache:
    def __init__(self):self.originals=AvatarRecordCache();self.bytes=0
    def read(self,key,decode):
        raw=canonical(key)
        if raw in self.originals.rows:return self.originals.read(key,decode)
        # Large native records still run their complete decoder. No limit on
        # accepted native packets or private original storage is changed.
        if len(raw)>1048576 or len(self.originals.rows)>=MAX_ENTRIES or self.bytes+len(raw)>MAX_BYTES:return decode()
        value=self.originals.read(key,decode);size=len(raw)+len(canonical(value))
        if self.bytes+size>MAX_BYTES:self.originals.rows.pop(raw,None)
        else:self.bytes+=size
        return value


def returned_record(owner,value,index,previous,decode):
    cache=_ACTIVE.get()
    if cache is None or type(value) is not dict or value.get('status')!='returned' or value.get('unsafe') or value.get('readbacks'):
        return decode()
    key=dict(tabletImmutableRecordVersion=1,root=str(owner.root),binding=owner.binding,run=owner.run,role=owner.role,
        fixture=owner.fixture,pid=owner.pid,component=owner.component,module=owner.module.__name__,
        functions=[id(owner.module.original),id(owner.module.validate),id(type(owner)._record)],
        versions=[getattr(owner.module,'VERSION',None),getattr(owner.module,'READS',None),owner.module.LIMIT],
        row=value,index=index,previous=previous)
    # A complete returned record cannot set a pending/rejected side effect.
    # Those records are never memoized and still update the live history floor.
    def checked():
        blocked=owner.blocked;answer=decode();need(owner.blocked==blocked);return answer
    return cache.read(key,checked)


def auxiliary_record(owner,value,index,previous,decode):
    """Only immutable returned auxiliary rows, never their current WAL/floors.

    Deferred-command rows additionally join a separately mutable authority
    owner, so they always retain the original full decoder. Every other kind
    joins only this exact row, previous original and immutable segment bytes.
    The caller's complete history still checks current pending/rejected rows,
    raw numbering, unique queries, clocks and full Script membership history.
    """
    cache=_ACTIVE.get()
    if cache is None or owner.kind=='defer' or type(value) is not dict or value.get('status')!='returned' or value.get('unsafe') or value.get('readbacks'):
        return decode()
    from ios.adapters import tablet_web_native_reads as source
    key=dict(tabletImmutableAuxiliaryVersion=1,root=str(owner.root),binding=owner.binding,run=owner.run,role=owner.role,
        kind=owner.kind,functions=[id(source.original),id(source.joined),id(type(owner)._record)],
        bounds=[source.VERSION,source.LIMITS[owner.kind]],row=value,index=index,previous=previous)
    def checked():
        blocked=owner.blocked;answer=decode();need(owner.blocked==blocked);return answer
    return cache.read(key,checked)


def parent_record(owner,value,index,previous,decode):
    """Historical returned aggregate only; mutable membership stays outside.

    The caller has replayed every current child history before reaching this
    function. Its app-prefix and exact current child-index associations are
    checked again on every hit. Parent phase/admission/native continuation is
    still performed by the caller after this immutable interpretation.
    """
    cache=_ACTIVE.get()
    if cache is None or not owner.historical or type(value) is not dict or value.get('status')!='returned':return decode()
    from ios.adapters import tablet_web_source_owner as source
    from ios.adapters import tablet_web_admission as admission
    from ios.adapters.world_web_measurements import browser_original
    from adapters.native_clock_join import digest
    from adapters.script_feature.history import same
    need(type(value.get('apps')) is list and owner.state['apps'][:len(value['apps'])]==value['apps']
        and type(value.get('components')) is list and len(value['components'])==len(source.ORDER))
    parsers=[]
    for ordinal,part in enumerate(value['components']):
        source.exact(part,{'component','index','reference'});name=source.ORDER[ordinal]
        need(part['component']==name and source.integer(part['index'],1))
        child=owner.children[name]
        need(part['reference'] is not None and same(child.reference(part['index']),part['reference']))
        parsers.append(dict(component=name,module=child.module.__name__,functions=[id(child.module.original),
            id(child.module.validate),id(type(child)._record),id(type(child).record),id(type(child).reference)],
            versions=[getattr(child.module,'VERSION',None),getattr(child.module,'READS',None),child.module.LIMIT]))
    key=dict(tabletImmutableParentVersion=1,root=str(owner.root),binding=owner.binding,run=owner.run,role=owner.role,
        fixture=owner.fixture,pid=owner.pid,row=value,index=index,previous=previous,children=parsers,
        order=source.ORDER,frameKeys=source.FRAME_KEYS,versions=[source.VERSION,source.READS,source.ACQUISITION_VERSION,source.ACQUISITION_READS],
        functions=[id(type(owner)._record),id(type(owner)._clock),id(source.exact),id(source.integer),id(source.number),
            id(source.need),id(source.native_original),id(source.follow_native),id(source.phase_original),
            id(source.active_browser),id(admission.validate),id(browser_original),id(digest),id(same)])
    def checked():
        before=(owner.blocked,tuple(child.blocked for child in owner.children.values()))
        answer=decode()
        need(before==(owner.blocked,tuple(child.blocked for child in owner.children.values())))
        return answer
    return cache.read(key,checked)


@contextmanager
def scope(cache):
    need(cache is None or isinstance(cache,TabletRecordCache));token=_ACTIVE.set(cache)
    try:yield
    finally:_ACTIVE.reset(token)
