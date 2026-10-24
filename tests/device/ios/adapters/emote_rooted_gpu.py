"""Join actual current GPU journals to retained Emote parent ownership.

Captured/abandoned parent originals must already be decoded by their existing
readers. This adds current responsibility checks, never new pixels or effects.
No query, release, retry, deletion or clock renewal occurs here.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import need
from adapters.native_vulkan_world_frame import absent
from adapters.normal_feature_state import PrivateFeatureState
from adapters.owned_vulkan_world_frame import VulkanWorldFrameOwner
from adapters.script_feature.history import unpack,same


def parents(parts):
    result={}
    samples=parts['samples'];frames=parts['restoration']
    need(samples.state['phase']=='ready' and frames.state['pending'] is None)
    originals=[samples.record(row) for row in samples.state['rows']]
    originals.extend(frames.original(ref) for ref in frames.state['records'])
    for value in originals:
        request=value['requestId'];owners=unpack(value['owner']);need(len(owners)==1)
        if request in result:need(same(result[request],owners[0]))
        else:result[request]=owners[0]
    return result


def validate(flow,parts):
    flow.lock.assert_held();flow.primary_lock.assert_held();actual={}
    for request,original in parents(parts).items():
        path=flow.store.path.with_name('graphics-world-frame-'+flow.role+'-0-'+request[4:]+'.json')
        store=PrivateFeatureState(path);value=store.read()
        if original is None:
            need(value is None);continue
        need(value is not None and original['phase']=='released' and absent(original['absence']))
        owner=VulkanWorldFrameOwner(store,flow.root,flow.state['binding'],flow.run,flow.role,0,request,
            lambda *_:need(False),lambda:True,source_lock=flow.lock)
        owner.verify_owned_artifact()
        need(same(owner.state,value))
        # The immutable parent retains the actual earlier receipt boundary.
        # Later observations may only inspect that already absent slot.
        fixed=('vulkanWorldOwnerVersion','binding','runId','role','stage','requestId','root','name','ticket','file','frame')
        need(all(same(value[key],original[key]) for key in fixed))
        before,after=unpack(original['transcript']),unpack(value['transcript'])
        need(same(after[:len(before)],before))
        for row in after[len(before):]:
            need(row['command']['operation']=='inspect' and row['receipt'] is not None)
        need(same(store.read(),value));actual[path]=value
    return actual
