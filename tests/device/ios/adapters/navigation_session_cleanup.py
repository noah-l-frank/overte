"""Retained Worlds originals fence the ordinary installed SDK cleanup path.

Only an already completed original end can return cleaned here. Unfinished or
orphan ownership stays unresolved; this reader cannot issue Stop or DELETE.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path

from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import same
from feature_journeys.contract import identifier
from feature_journeys.graphics_resources import fixture_url
from feature_journeys.witness import Client
from ios.adapters.navigation_feature import IOSNavigationFeature
from ios.adapters.navigation_runtime import IOSNavigationRuntime
from ios.adapters.navigation_terminal import NavigationTerminal

PREFIXES=('ios-navigation-','navigation-','phase-publication-world-navigation-','phase-retirement-world-navigation-')


def no_orphans(directory,config):
    directories={directory}
    if type(config) is dict and 'world-navigation' in config.get('areas',[]):
        from ios.adapters.feature_configuration import validate
        from ios.adapters.navigation_configuration import settings
        validate(config);directories.add(Path(settings(config['worldNavigation'])['artifactRoot']))
    for root in directories:
        try:
            for index,path in enumerate(root.iterdir()):
                need(index<50000 and not path.name.startswith(PREFIXES))
        except FileNotFoundError:continue


def retire_existing(runtime,selector,config):
    """Return None for no owner, cleaned for typed original end, else fail."""
    need(isinstance(runtime,IOSNavigationRuntime));directory=runtime.state_path(selector).parent
    store=PrivateFeatureState(directory/'ios-navigation-feature.json');value=store.read()
    if value is None:no_orphans(directory,config);return None
    exact(value,{'iosNavigationFeatureVersion','runId','artifactRoot','payload'})
    identifier(value['runId'])
    from ios.adapters.navigation_configuration import settings
    chosen=settings(dict(artifactRoot=value['artifactRoot']))
    # These markers select only the pure reader. Missing/forged inner carriers
    # cannot enter a live finalizer or let generic cleanup terminate again.
    need(PrivateFeatureState(directory/'ios-navigation-final-archive.json').read() is not None
        and PrivateFeatureState(directory/'ios-navigation-process-end.json').read() is not None
        and PrivateFeatureState(directory/'ios-navigation-session-end.json').read() is not None)
    publication=PrivateFeatureState(directory/('phase-publication-world-navigation-'+value['runId']+'-actor.json')).read()
    need(type(publication) is dict and type(publication.get('fixtureUrl')) is str)
    fixture_url(publication['fixtureUrl'])
    def forbidden(*_args,**_kwargs):need(False)
    passive=object.__new__(Client);passive.url=publication['fixtureUrl'];passive.request=forbidden
    flow=IOSNavigationFeature(runtime,selector,passive,value['runId'],chosen['artifactRoot'])
    with flow.held():
        flow.load();need(same(flow.previous,value) and same(store.read(),value))
        runtime.adapter._retired_candidate_scope(selector,{key:item for key,item in flow.state['binding'].items() if key!='processIdentity'})
        terminal=NavigationTerminal(flow);need(terminal.state is not None and terminal.state['seal'] is not None)
        terminal.finish(terminal.state['seal']);need(same(store.read(),value))
    return {'cleaned':True}
