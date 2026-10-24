"""Pure original Actor publication selection for rooted Emote terminal cuts.

The unchanged publisher reader rederives every original observation and HTTP
receipt. A requested Actor entry can only select an exact committed original.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.phase_witness_publisher import PhaseWitnessPublisher
from adapters.script_feature.history import same
from ios.adapters.emote_rooted_archive import reopen
from ios.adapters.emote_rooted_observation import IOSEmoteRootedObserver
from ios.adapters.emote_archive_round import scope as original_round


def select(snapshot,value,*,store,entries,lock,primary_lock):
    with original_round(snapshot,lock=lock,primary_lock=primary_lock):
        return select_originals(snapshot,value,store=store,entries=entries,lock=lock,primary_lock=primary_lock)


def select_originals(snapshot,value,*,store,entries,lock,primary_lock):
    need(isinstance(store,PrivateFeatureState) and type(entries) is list and 1<=len(entries)<=81
        and type(snapshot) is dict and snapshot.get('role')=='actor' and same(store.read(),value))
    keyed=reopen(snapshot,lock=lock,primary_lock=primary_lock)
    rendered=keyed.rendered_owner;rendered_ref=keyed.original(snapshot['reference'])['renderedReference']
    native=rendered.native_owner;original=native.original(rendered.original(rendered_ref)['nativeReference'])
    sources,peers,decoder=native.owners(original)
    observer=object.__new__(IOSEmoteRootedObserver)
    observer.sources,observer.decoder,observer.binding,observer.run,observer.role=sources,decoder,keyed.binding,keyed.run,'actor'
    observer.root,observer.phase=keyed.root,SimpleNamespace(fixture_url=keyed.fixture_url)
    suffix='/runs/'+keyed.run+'/'
    need(keyed.fixture_url.endswith(suffix));url=keyed.fixture_url[:-len(suffix)]
    state=PhaseWitnessPublisher.archive(value,store=store,binding=keyed.binding,run=keyed.run,area='emotes',fixture_url=url,
        phase_instance=keyed.phase_instance,validate_original=observer.validate_original)
    need(state['pending'] is None)
    publisher=object.__new__(PhaseWitnessPublisher)
    publisher.store,publisher.binding,publisher.run,publisher.area=store,keyed.binding,keyed.run,'emotes'
    publisher.url,publisher.instance,publisher.validate_original,publisher.live=url,keyed.phase_instance,observer.validate_original,False
    records=[(reference,publisher.load(reference)) for reference in state['records']]
    selected=[];seen=set()
    for entry in entries:
        matches=[(reference,row) for reference,row in records if row['mode']=='published' and same(row['entry'],entry)]
        need(len(matches)==1);reference,row=matches[0];need(reference['ordinal'] not in seen);seen.add(reference['ordinal'])
        selected.append(dict(reference=deepcopy(reference),original=deepcopy(row['intent']['original']),
            acquisition=deepcopy(row['intent']['derived']['acquisition']),entry=deepcopy(row['entry']),
            observation=observer.original({key:row['intent']['original'][key] for key in ('index','sha256')})))
    need(same(store.read(),value));return selected
