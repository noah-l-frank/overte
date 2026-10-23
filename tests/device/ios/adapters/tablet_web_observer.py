"""Actual source acquisitions and original-only same-physical actor publication.

This owner creates no SDK, input, remote view, app Stop or SDK deletion. Active
observations retain actual native and app-scope responsibility. Host worker and
query ownership remains private; whole retirement is a separate owner.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.phase_witness_publisher import PhaseWitnessPublisher
from adapters.script_feature.history import same
from feature_journeys.contract import result
from ios.adapters.tablet_web_source_owner import TabletWebSourceOwner
from ios.adapters.uikit_input import _owned
from ios.adapters.tablet_web_dom import IOSTabletWebDOM

VERSION=1


def forbidden(*_args,**_kwargs):need(False)


def resources(frame,record):
    """Retain actual observed holds and unresolved app-scope responsibility."""
    result=[]
    touches=frame['touches'];views={row['view'] for row in touches['targets'] if _owned(row,touches)}
    contacts={row['id'] for row in touches['contacts'] if row['source'] is not None and row['source']['view'] in views}
    own_dispatches={row['sequence'] for row in touches['dispatches'] if any(phase['contact'] in contacts for phase in row['phases'])}
    # Unowned cached objects are not our resources. Actual foreign activity
    # still prevents admission, including a dispatch with no owned phase.
    need(not any(row['active'] and row['id'] not in contacts for row in touches['contacts'])
        and set(touches['pendingDispatches'])<=own_dispatches)
    if not record['apps']:
        need(not touches['pendingDispatches'] and not any(row['active'] for row in touches['contacts'])
            and not any(row['subtreeResponder'] for row in frame['state']['targets']))
    objects={row['object'] for row in touches['contacts'] if row['id'] in contacts}
    objects.update(row['event'] for row in touches['dispatches'] if row['sequence'] in own_dispatches)
    if record['apps']:result+=['script:tablet-app-scope','file:tablet-app-inputs']
    if any(row['alive'] for row in frame['state']['owners']):result.append('panel:tablet-native-owner')
    if any(row['alive'] for row in frame['state']['targets']):result.append('panel:tablet-native-targets')
    if any(row['alive'] for row in frame['buttons']['buttons']+frame['buttons']['controls']):result.append('panel:tablet-app-controls')
    if any(row['alive'] and row['id'] in objects for row in touches['objects']):result.append('input:tablet-held-input-objects')
    if touches['pendingDispatches'] or any(row['active'] for row in touches['contacts'] if row['id'] in contacts):result.append('input:tablet-active-inputs')
    if any(counter['pending'] for row in frame['closures']['contexts'] for counter in row['callbacks'].values()):result.append('connection:tablet-native-callbacks')
    if any(counter['pending'] for row in frame['closures']['contexts'] for counter in row['resources'].values()):result.append('panel:tablet-native-web-resources')
    if any(row['callbackAlive'] or row['bufferPending'] for row in frame['deferred']['records']):result.append('connection:tablet-deferred-callback')
    if any(binding['contextAlive'] or binding['pageAlive'] for carrier in frame['sources']['carriers'] for binding in carrier['bindings']):result.append('panel:tablet-inline-carrier')
    return result


class TabletWebDOMDisposition(IOSTabletWebDOM):
    """Return a terminal native DOM disposition, including actual unavailable.

    This is not a ready-DOM assertion. Historical facts independently require
    real current State/Trace/UIKit absence when no DOM is available. The normal
    IOSTabletWebDOM ready-document API and its failure semantics stay unchanged.
    """
    @staticmethod
    def _ready(value):return value['status']!='pending'

    @classmethod
    def from_reader(cls,reader):
        need(isinstance(reader,IOSTabletWebDOM) and reader.last is None and reader.accepted is None)
        return cls(reader.send,reader.original,reader.clock_ms,reader.guard,reader.pid,monotonic=reader.monotonic,sleep=reader.sleep)


class TabletWebObserver:
    def __init__(self,source,readers,native,phase,browser,origins):
        need(isinstance(source,TabletWebSourceOwner) and not source.historical)
        self.source,self.readers,self.native,self.phase,self.browser=source,readers,native,phase,browser
        self.origins=deepcopy(origins);self.publisher=None

    def validate_original(self,original):
        """Pure historical decoder: no live process guard, SDK or HTTP calls."""
        exact(original,{'tabletWebObservationOriginalVersion','binding','runId','role','fixtureUrl','hostProcessId','reference'})
        source=self.source
        need(type(original['tabletWebObservationOriginalVersion']) is int and original['tabletWebObservationOriginalVersion']==VERSION
            and same(original['binding'],source.binding) and original['runId']==source.run and original['role']==source.role
            and original['fixtureUrl']==source.fixture and integer(original['hostProcessId'],1))
        historical=TabletWebSourceOwner(source.root,source.binding,source.run,source.role,source.fixture,source.pid,source.lock,forbidden,
            monotonic=source.monotonic,epoch_ms=forbidden,historical=True)
        measured,record,frame=historical.facts_at(original['reference'],self.origins)
        need(record['hostProcessId']==original['hostProcessId'])
        clock=record['clockJoin'];public=dict(schemaVersion=1,contractVersion=16,runId=source.run,sequence=record['index'],
            capturedEpochMs=clock['hostBeforeEpochMs'],state=measured['public'],artifacts=[],resources=resources(frame,record),
            lifecycle=deepcopy(record['nativeAfter']['lifecycle']))
        result('feature.tablet-web.observe',public)
        return dict(ticket=record['phaseAfter']['activations'][-1]['ticket'],public=public,
            acquisition={key:clock[key] for key in ('hostBeforeEpochMs','hostAfterEpochMs','hostBeforeMonotonic','hostAfterMonotonic')})

    def observe(self):
        _parts,record=self.source.capture(self.readers,self.native,self.phase,self.browser)
        original=dict(tabletWebObservationOriginalVersion=VERSION,binding=deepcopy(self.source.binding),runId=self.source.run,role=self.source.role,
            fixtureUrl=self.source.fixture,hostProcessId=record['hostProcessId'],reference=deepcopy(self.source.state['records'][-1]))
        self.validate_original(original);return original

    def actor_publisher(self):
        need(self.source.role=='actor');self.source.bound()
        if self.publisher is None:
            if self.phase.previous is None:self.phase.status()
            self.publisher=PhaseWitnessPublisher(PrivateFeatureState(self.source.root/('phase-publication-tablet-web-'+self.source.run+'-actor.json')),
                self.source.binding,self.phase,self.source.lock,self.source.guard,self.validate_original,epoch_ms=self.source.epoch_ms,monotonic=self.source.monotonic)
        return self.publisher

    def publish(self):
        """The actual actor captures its own sources; unknown POSTs only resolve."""
        publisher=self.actor_publisher()
        if publisher.state['pending'] is not None:return publisher.resolve()
        original=self.observe();return publisher.publish(original)
