"""Pure joining of actual ordinary cleanup owners to restored image cuts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import same
from ios.adapters.navigation_whole_feature import NavigationWholeFeature
from ios.adapters.navigation_places_cleanup import NavigationPlacesCleanup
from ios.adapters.navigation_surface_actions import NavigationSurfaceActions
from ios.adapters.navigation_process_return import NavigationProcessReturn
from ios.adapters.navigation_process_context import source_basis
from ios.adapters.normal_input import observation


def archive(owner):
    """Decode typed originals only; no bound/live factory or transport."""
    f=owner.flow;f.lock.assert_held();need(owner.historical and f.state['stage']==1)
    whole=NavigationWholeFeature(f);whole.load();need(whole.state is not None and whole.state['phase']=='cleaned'
        and f.state['phase']=='ready' and (f.state['lastCall'] is None or f.state['lastCall']['phase']=='acknowledged'))
    context=owner.process_context;basis=source_basis(context,owner.owner_files);row=whole.state['cleanup'];call=row['call']
    need(call['ticket']==owner.context['cleanupTicket'])
    fixture=SimpleNamespace(fixture_url=f.fixture.fixture_url,inputs=context['initialAdmission']['providerInputs'],
        instance=context['initialAdmission']['providerInstance'])
    scope=SimpleNamespace(binding=owner.binding,run=f.run,fixture=fixture,owner=owner.transfer,
        archive=lambda:deepcopy(basis),original_admission=lambda:deepcopy(context['initialAdmission']))
    def ui(value):
        observation(value,int(owner.binding['processIdentity']),value.get('sampleEpochMs'));floor=basis['originals']['ui']
        need(value['instance']==floor['instance'] and value['lastSequence']>=floor['lastSequence']
            and value['elapsedMs']>=floor['elapsedMs'] and value['sampleEpochMs']>=floor['sampleEpochMs'])
        for key in ('placesSourceSequence','navigationDialogSourceSequence'):
            if key in floor:need(key in value and value[key]>=floor[key])
        return value
    scope.ui_original=ui
    surface=object.__new__(NavigationSurfaceActions);surface.binding=owner.binding;surface.run=f.run;surface.admission=scope
    def read(stem,key):
        store=PrivateFeatureState(f.store.path.with_name(stem+'-'+owner.binding['processIdentity']+'.json'))
        value=store.read();need(value is not None and digest(value)==row[key]);return value
    surfaces=read('ios-navigation-surface-actions','surfaceSha256');surface_state=surface.decode(surfaces)
    final=surface_state['actions'][-1];need(final['phase']=='acknowledged' and final['surface']=='close' and same(final['call'],call))
    forms=object.__new__(NavigationPlacesCleanup);forms.binding=owner.binding;forms.run=f.run;forms.admission=scope;forms.surface=surface
    normal=read('ios-navigation-places-cleanup','formsSha256');form_state=forms.decode(normal)
    need(form_state['phase']=='delivered' and same(form_state['call'],call))
    returned=object.__new__(NavigationProcessReturn);returned.scope=scope;returned.binding=owner.binding;returned.run=f.run
    original=read('ios-navigation-process-return','returnSha256');return_state=returned.decode(original)
    need(return_state['phase']=='delivered')
    images=owner.images();need(images)
    start=images[0].originals()['baseRead']['before']['epochMs']
    need(final['after']['sampleEpochMs']<=return_state['beforeUi']['sampleEpochMs']
        and return_state['returnedUi']['sampleEpochMs']<=start
        and form_state['after']['controls']['scope']['sampleEpochMs']<=final['after']['sampleEpochMs'])
    return dict(iosNavigationCleanupArchiveVersion=1,runId=f.run,ticket=call['ticket'],wholeSha256=digest(whole.previous),
        formsSha256=digest(normal),surfaceSha256=digest(surfaces),returnSha256=digest(original),
        phaseOriginalSha256=digest(owner.phase_original()))
