"""Replay completed role originals before canonical session teardown.

Only retained host originals are read. Opaque path keys below identify the two
original SDK directories; they are never target selectors or SDK factories.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
from types import SimpleNamespace
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.script_feature.history import unpack,same
from contextlib import ExitStack
from adapters.original_file_reads import scope as read_scope
from ios.adapters.emote_archive_lock import ArchiveSourceLock
from feature_journeys.contract import identifier
from ios.adapters.graphics_configuration import settings
from ios.adapters.emote_feature import IOSEmoteFeature
from ios.adapters.emote_final_archive import IOSEmoteFinalArchive
from ios.adapters.emote_finalization import IOSEmoteFinalization
from ios.adapters.emote_retirement import Frozen


def verify(directory,path,value,*,check=lambda:None,membership=None,report_target=None):
    need(membership is None or type(membership) is set)
    with read_scope(fresh=True) as reads:
        need(same(PrivateFeatureState(path).read(),value))
        result=_verify(directory,path,value,check=check,report_target=report_target)
    if membership is not None:membership.update(reads)
    return result


def _verify(directory,path,value,*,check,report_target):
    need(callable(check));check()
    directory,path=Path(directory),Path(path)
    exact(value,{'iosEmoteFinalArchiveVersion','runId','role','binding','artifactRoot','paths','payload'})
    run=identifier(value['runId']);role=value['role'];binding=context(value['binding'])
    need(role in ('primary','actor') and path==directory/('ios-emote-'+role+'-'+run+'-finalization.json')
        and type(value['paths']) is list and 1<=len(value['paths'])<=256)
    paths=[PrivateFeatureState(Path(item)) for item in value['paths']]
    need(paths[-1].path==directory/('ios-emote-'+role+'-feature.json'))
    roots=[store.path.parent for store in paths if store.path.name=='ios-emote-'+role+'-sources.json']
    need(len(roots)==1);primary_directory=roots[0]
    need((role=='actor')==(primary_directory!=directory))
    own_key,primary_key=object(),object()
    def state_path(key):
        need(key is own_key or key is primary_key)
        return (directory if key is own_key else primary_directory)/'session.json'
    flow=object.__new__(IOSEmoteFeature)
    flow.runtime=SimpleNamespace(state_path=state_path);flow.selector=own_key
    flow.primary_selector=own_key if role=='primary' else primary_key
    flow.role,flow.run,flow.root=role,run,Path(value['artifactRoot'])
    flow.lock=ArchiveSourceLock(directory/'script-feature-sources.lock')
    flow.primary_lock=flow.lock if role=='primary' else ArchiveSourceLock(primary_directory/'script-feature-sources.lock')
    flow.store=paths[-1];flow.state=None
    final=IOSEmoteFinalization(flow)
    archive=IOSEmoteFinalArchive(PrivateFeatureState(path),flow.root,binding,run,role,flow.lock,flow.primary_lock,paths,
        lambda:False,final.decode)
    need(archive.state['phase']=='complete')
    original=archive.copy(archive.state['records'][-1])
    exact(original,{'iosEmoteFeatureVersion','runId','role','artifactRoot','fixtureUrl','imagePolicy','payload'})
    rows=unpack(original['payload']);need(len(rows)==1)
    flow.state=rows[0];flow.policy=original['imagePolicy']
    settings(dict(artifactRoot=str(flow.root),imagePolicy=flow.policy))
    url=original['fixtureUrl'];suffix='/runs/'+run+'/'
    need(type(url) is str and url.endswith(suffix))
    flow.phase=SimpleNamespace(fixture_url=url);flow.client=SimpleNamespace(url=url[:-len(suffix)])
    need(same(original,flow.envelope(flow.state)) and same(binding,flow.state['binding']))
    # qualify() independently replays the complete native/image originals and
    # guards actual inode/history stability; it sends no command and drops none.
    with ExitStack() as held:
        held.enter_context(flow.lock.held())
        if flow.primary_lock is not flow.lock:held.enter_context(flow.primary_lock.held())
        check();flow.store=Frozen(paths[-1].path,original);flow.load()
        archive.qualify();check()
        if report_target is not None and role=='actor':
            report=PrivateFeatureState(flow.root/('emote-worker-failed-'+run+'.json')).read()
            if report is not None:
                from ios.adapters.emote_session_carriers import failure_report
                failure_report(report,root=flow.root,run=run,role=role,fixture_url=flow.phase.fixture_url,policy=flow.policy,target=report_target)
            archive.qualified.guard();check()
        need(all(store.read() is None for store in paths) and same(archive.store.read(),value))
    check();return binding
