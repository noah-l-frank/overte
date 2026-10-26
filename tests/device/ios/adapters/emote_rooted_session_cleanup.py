"""Completed rooted Emote end before canonical ordinary SDK teardown.

Unfinished responsibility requires the explicit paired terminal protocol.
This path observes historical originals only and cannot issue Stop or DELETE.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import re
import time
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import unpack
from feature_journeys.contract import identifier
from ios.adapters.emote_runtime import IOSEmoteRuntime
from ios.adapters.emote_session_cleanup import budget

ROOTED=re.compile(r'ios-emote-(?:primary|actor)-([a-f0-9]{32})-rooted-(?:final|end|process-end|sdk-end)\.json')


def retire_existing(runtime,selector,config,*,monotonic=time.monotonic):
    need(isinstance(runtime,IOSEmoteRuntime));started=monotonic();directory=runtime.state_path(selector).parent
    if not directory.exists():return None
    entries=list(directory.iterdir());need(len(entries)<=4096)
    runs=set();rooted=False
    for path in entries:
        match=ROOTED.fullmatch(path.name)
        if match:rooted=True;runs.add(match[1])
    for role in ('primary','actor'):
        value=PrivateFeatureState(directory/('ios-emote-'+role+'-feature.json')).read()
        if value is not None:need(type(value) is dict)
        if value is not None and value.get('iosEmoteFeatureVersion')==2:
            need(type(value['iosEmoteFeatureVersion']) is int);rooted=True;runs.add(identifier(value.get('runId')))
    if not rooted:return None
    # Missing/legacy configuration cannot redirect remaining rooted ownership
    # through the old component finalizer or an ordinary SDK teardown.
    from ios.adapters.feature_configuration import validate
    validate(config);need(config['iosFeatureAdapterVersion']>=6 and config['emoteCoordinatorVersion']==2
        and 'emotes' in config['areas'] and selector!=config['emotes']['actorTarget'] and len(runs)==1)
    run=runs.pop();store=PrivateFeatureState(directory/('ios-emote-primary-'+run+'-rooted-end.json'))
    value=store.read();need(type(value) is dict and value.get('runId')==run)
    rows=unpack(value.get('payload'));need(len(rows)==1 and type(rows[0]) is dict and rows[0].get('phase')=='complete')
    with budget(runtime.adapter,selector,monotonic=monotonic,started=started) as work:
        from ios.adapters.emote_rooted_bootstrap import primary
        from ios.adapters.emote_canonical_end import completed
        flow=primary(runtime,selector,run,config['emotes']);work.check()
        result=completed(flow,value['seal']);need(result['stage']=='finish');work.check()
        for target in (selector,config['emotes']['actorTarget']):
            need(runtime.adapter.read_session(target) is None and runtime.adapter._binding_store(target).read() is None
                and runtime.adapter.component_owners_absent(target))
            for path in runtime.state_path(target).parent.iterdir():
                if not path.name.startswith(('ios-emote-','emote-')) and path.name.endswith(('-feature.json','-owner.json','-retirement.json')):
                    need(PrivateFeatureState(path).read() is None)
        work.check();return dict(cleaned=True)
