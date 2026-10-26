"""Pure exact-prefix join of one saved interruption to its recording parent."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import unpack,same


class RecordedPrefix:
    """Already-owned original prefix, with the full parent's inventory intact.

    This is a codec view, not a source or another recording manager. The caller
    still validates its complete current inventory, including all later files.
    """
    def __init__(self,parent,original,current):
        self.parent=parent;self.previous=deepcopy(original)
        exact(original,{'iosAudioRecordedOwnerVersion','runId','binding','artifactRoot','fixtureUrl','payload'})
        rows=unpack(original['payload']);need(len(rows)==1);old=rows[0]
        need(parent.version>=4 and same(original,parent.envelope(old)))
        exact(old,{'records','operations','pending','observation','background'})
        need(old['background'] is None and old['pending'] is None and old['observation'] is None
            and type(old['records']) is list and 1<=len(old['records'])<=128
            and same(old['records'],current['records'][:len(old['records'])])
            and type(old['operations']) is list and len(old['operations'])<=32
            and same(old['operations'],current['operations'][:len(old['operations'])]))
        self.state=deepcopy(old)
        previous=None
        for index,reference in enumerate(old['records'],1):
            need(reference['index']==index);value=parent.original(reference,state=old)
            need(value.get('background') is None);parent.frame(value,previous,old);previous=value
        parent.operations(old)
        for key in ('root','binding','run','lock','store','monotonic'):setattr(self,key,getattr(parent,key))

    def original(self,reference):
        need(reference in self.state['records']);return self.parent.original(reference,state=self.state)

    def bound(self):return self.parent.bound()


def proof(parent,value,state):
    exact(value,{'iosAudioBackgroundBridgeVersion','before','child','bundle'})
    need(type(value['iosAudioBackgroundBridgeVersion']) is int and value['iosAudioBackgroundBridgeVersion']==1)
    child=value['child'];rows=unpack(child['payload']);need(len(rows)==1)
    prefix=RecordedPrefix(parent,rows[0]['parent'],state)
    need(same(value['before'],prefix.state['records'][-1]))
    from ios.adapters.audio_background import AudioBackground
    archive=AudioBackground.archive(PrivateFeatureState(parent.store.path.with_name('ios-audio-background.json')),prefix,value['bundle'])
    need(same(archive.previous,child) and archive.state['phase']=='observed')
    return archive.read(archive.state['records'][-1])
