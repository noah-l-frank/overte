"""Common bounded feature execution with independent observations and cleanup."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import math
import secrets
from . import evidence as bytes_evidence
from . import emote_motion
from .contract import arguments, exact, identifier, number, result, state as validate_state, typed_equal
from .fixtures import context
from .scenarios import SCENARIOS, VERSION, expand, snapshot_profile
from .witness import projection
from .navigation_fixture import configuration as navigation_configuration,validate_status as navigation_status


def matches(actual, expected):
    if type(expected) is dict and set(expected) == {'oneOf'}:
        return any(typed_equal(actual, candidate) for candidate in expected['oneOf'])
    if type(expected) is dict and set(expected) == {'min', 'max'}:
        return type(actual) in (int, float) and expected['min'] <= actual <= expected['max']
    if isinstance(expected, dict):
        return type(actual) is dict and set(actual) == set(expected) and all(matches(actual[k], v) for k, v in expected.items())
    if isinstance(expected, list):
        return type(actual) is list and len(actual) == len(expected) and all(matches(a, b) for a, b in zip(actual, expected))
    if type(expected) is float:
        return type(actual) in (int, float) and math.isfinite(actual) and abs(actual - expected) <= 0.025
    return typed_equal(actual, expected)


class Journey:
    def __init__(self, area, run, fixture_url, *, invoke, witness, activate,
                 read_artifact, image_policy, continuity, monotonic, epoch_ms, sleep, report, navigation_source=None):
        if area not in SCENARIOS:
            raise ValueError('Unknown common feature area')
        self.area, self.run, self.url = area, identifier(run), fixture_url
        self.invoke, self.witness, self.activate = invoke, witness, activate
        self.read_artifact, self.policy, self.continuity = read_artifact, image_policy, continuity
        self.monotonic, self.epoch_ms, self.sleep, self.report = monotonic, epoch_ms, sleep, report
        self.sequence = self.witness_sequence = 0
        self.last_epoch = self.last_actor_epoch = self.last_actor_sequence = 0
        self.last_clock = None
        self.previous_subject = None
        self.phases, self.samples = [], []
        self.recorded_ticket = self.capture_ticket = self.model_ticket = self.texture_ticket = None
        self.evidence_cache = {}
        self.lifecycle = None
        self.required_lifecycle = None
        self.sit_variants = set()
        self.source_profile=None;self.not_applicable=[];self.system_ui=False
        self.last_action = None
        self.snapshot_file_source=None;self.snapshot_digest=None
        self.browser_transition=None
        if area=='world-navigation' and not callable(navigation_source):raise ValueError('Original navigation HTTP source is required')
        self.navigation_source=navigation_source;self.navigation_previous=None;self.navigation_required=None
        self.navigation_instance=self.navigation_inputs=None

    def now(self):
        value = number(self.monotonic())
        if self.last_clock is not None and value < self.last_clock:
            raise ValueError('Feature journey monotonic clock moved backwards')
        self.last_clock = value
        return value

    def call(self, kind, fields=None):
        operation = 'feature.' + self.area + '.' + kind
        request = dict(contractVersion=VERSION, runId=self.run, **(fields or {}))
        arguments(operation, request)
        value = result(operation, self.invoke(operation, request))
        if kind == 'act': self.last_action = deepcopy(request)
        return value

    def observe(self, ticket, barrier):
        self.continuity('observe', None)
        value = self.call('observe', dict(afterSequence=self.sequence))
        self.continuity('observed', None)
        if value['runId'] != self.run or value['sequence'] <= self.sequence:
            raise ValueError('Foreign or replayed actual product sample')
        captured, epoch = value['capturedEpochMs'], number(self.epoch_ms(), 1)
        if captured < self.last_epoch or captured < barrier or captured > epoch + 250 or epoch - captured > 1500:
            raise ValueError('Actual product sample is stale or from a different clock context')
        if (self.area=='lifecycle-input' and self.samples
                and any(value['state'][key]<self.samples[-1]['state'][key] for key in ('worldAttempts','staleAttempts'))):
            raise ValueError('Original native input history was reset or replaced')
        self.sequence, self.last_epoch = value['sequence'], captured
        return value

    def observed_witness(self, ticket, barrier, expected):
        value = self.witness()
        exact(value, {'schemaVersion', 'runId', 'area', 'ticket', 'sampleEpochMs', 'entries'}, 'independent journal')
        if (type(value['schemaVersion']) is not int or value['schemaVersion'] != 1
                or value['runId'] != self.run or value['area'] != self.area or value['ticket'] != ticket):
            raise ValueError('Independent journal belongs to a foreign run, area or ticket')
        epoch = number(self.epoch_ms(), 1)
        captured = number(value['sampleEpochMs'], 1)
        if captured < barrier or captured > epoch + 250 or epoch - captured > 1500:
            raise ValueError('Independent journal snapshot is stale')
        if type(value['entries']) is not list or len(value['entries']) > 512:
            raise ValueError('Invalid bounded independent journal')
        last_sequence = 0
        new = []
        for entry in value['entries']:
            exact(entry, {'ticket', 'actor', 'actorSequence', 'capturedEpochMs', 'facts', 'sequence', 'receivedEpochMs'}, 'independent raw observation')
            seq = entry['sequence']
            if type(seq) is not int or seq <= last_sequence or type(entry['actorSequence']) is not int or entry['actorSequence'] <= 0:
                raise ValueError('Independent journal order is invalid')
            last_sequence = seq
            if seq <= self.witness_sequence or entry['ticket'] != ticket:
                continue
            if entry['actorSequence'] <= self.last_actor_sequence:
                raise ValueError('Independent source sample sequence was replayed')
            if entry['actor'] != 'owned-observer':
                raise ValueError('Independent observation has an unregistered origin')
            observed = number(entry['capturedEpochMs'], 1)
            received = number(entry['receivedEpochMs'], 1)
            # A real actor can publish between activation and the input barrier.
            # Such a sample is valid journal history but cannot prove this action.
            if observed < barrier:
                continue
            if (observed < self.last_actor_epoch or observed > received + 250
                    or received > epoch + 250 or epoch - observed > 1500):
                raise ValueError('Independent actor observation is stale')
            exact(entry['facts'], expected, 'independent fact projection')
            validate_state(self.area, {**SCENARIOS[self.area]['baseline'], **entry['facts']}, self.run)
            self.last_actor_epoch = observed
            self.last_actor_sequence = entry['actorSequence']
            self.witness_sequence = seq
            new.append(entry)
        if not new:
            return False, None
        return all(matches(entry['facts'], expected) for entry in new), new[-1]

    def navigation(self,ticket,barrier):
        if self.area!='world-navigation':return True,[]
        value=self.navigation_source()
        if self.navigation_instance is None:
            self.navigation_instance=identifier(value['instance'])
            self.navigation_inputs,_urls=navigation_configuration(value['inputs'])
        navigation_status(value,instance=self.navigation_instance,run=self.run,inputs=self.navigation_inputs,previous=self.navigation_previous)
        if not value['active'] or value['ticket']!=ticket:raise ValueError('Original navigation provider is retired or belongs to a different challenge')
        self.navigation_previous=deepcopy(value)
        receipts=[row for row in value['responses'] if row['kind']==self.navigation_required
            and (self.navigation_required=='directory' or row['ticket']==ticket and row['completedEpochMs']>=barrier)]
        return self.navigation_required is None or bool(receipts),receipts

    def artifacts(self, value, ticket, kinds):
        observations = []
        subject = None
        by_kind = {item['kind']: item for item in value['artifacts']}
        for requested in kinds:
            if requested == 'peer':
                continue
            kind = {'changed': 'image', 'silence': 'audio'}.get(requested, requested)
            if kind not in by_kind:
                raise AssertionError('Required original ' + kind + ' evidence is missing')
            item = by_kind[kind]
            if kind == 'image' and item['source'] != self.policy['screen']['source']:
                raise AssertionError('Original image source differs from independent target policy')
            if item['ticket'] != ticket:
                raise AssertionError('Artifact was copied from a retired or foreign feature action')
            content = self.read_artifact(item['name'])
            if type(content) is not bytes or not 0 < len(content) <= bytes_evidence.MAX_BYTES:
                raise ValueError('Invalid bounded original artifact bytes')
            digest = hashlib.sha256(content).hexdigest()
            if self.area=='snapshots' and kind=='file':
                if item['source']!=self.snapshot_file_source:
                    raise AssertionError('Snapshot output was acquired from a different original sink')
                if self.snapshot_file_source=='snapshot-private-original':
                    if self.snapshot_digest not in (None,digest):raise AssertionError('Original private capture bytes changed')
                    self.snapshot_digest=digest
                elif self.snapshot_digest is None or digest!=self.snapshot_digest:
                    raise AssertionError('Snapshot destination bytes differ from the original capture')
            source_ticket = (self.recorded_ticket if self.area == 'audio' and (kind == 'file' or value['state']['phase'] == 'completed' and requested == 'audio')
                             else self.capture_ticket if self.area == 'snapshots' and kind == 'file' else ticket)
            key = (requested, digest, source_ticket, self.model_ticket)
            if self.area == 'emotes' and kind == 'file':
                if self.last_action is None or self.last_action['ticket'] != ticket:
                    raise AssertionError('Native Emote motion has no current owned ordinary input')
                observed = emote_motion.read(content, call=self.last_action, role='primary',
                    epoch=number(self.epoch_ms(), 1), captured=item['capturedEpochMs'], state=value['state'])
                cached_subject = None
            elif key in self.evidence_cache:
                observed, cached_subject = self.evidence_cache[key]
            elif kind == 'image':
                observed, cached_subject = bytes_evidence.image_observation(content, self.run, ticket,
                    self.policy['screen'], self.previous_subject, requested == 'changed')
                self.evidence_cache[key] = (observed, cached_subject)
            elif kind == 'audio':
                observed = bytes_evidence.audio_observation(content, self.run, source_ticket, requested == 'silence',
                    profile='recorded-preview-v1' if self.area == 'audio' else 'voice-v1')
                cached_subject = None
                self.evidence_cache[key] = (observed, None)
            else:
                observed = bytes_evidence.file_observation(content, self.area, self.run, source_ticket, self.policy, self.url, self.model_ticket, self.texture_ticket)
                cached_subject = None
                self.evidence_cache[key] = (observed, None)
            if cached_subject is not None:
                subject = cached_subject
            observations.append(dict(kind=requested, artifact=item['name'], acquisition=item.copy(), observed=observed))
        return observations, subject

    def wait(self, label, ticket, barrier, expected, kinds, *, duration=0.5):
        deadline = self.now() + 20
        stable_since = None
        stable_count = 0
        last_problem = 'required product state was not observed'
        initial_effects = None
        actual_lifecycle=None
        release_position=None
        native_motion = self.area == 'emotes' and expected['override'] is True
        if native_motion and not {'file', 'peer'} <= set(kinds):
            raise AssertionError('Active Emote requires original native motion and independent facts')
        for _attempt in range(81):
            value = self.observe(ticket, barrier)
            current = self.now()
            okay = matches(value['state'], expected)
            navigation_okay,navigation_receipts=self.navigation(ticket,barrier)
            okay=okay and navigation_okay
            if self.area=='lifecycle-input' and label.endswith('-release-input'):
                position=tuple(value['state']['positionDelta'][key] for key in ('x','y','z'))
                if release_position is not None and math.dist(position,release_position)>0.025:
                    stable_since=None;stable_count=0
                    release_position=position
                if release_position is None:release_position=position
            if self.browser_transition is not None:
                transition,before=self.browser_transition
                loads=value['state']['documentLoads']
                okay=okay and (loads>before if transition=='replace' else loads==before)
            progressing_script = self.area == 'scripts' and bool(expected['running'])
            if progressing_script and initial_effects is not None and value['state']['effects'] < initial_effects:
                raise AssertionError('Active script effect counter regressed without a new engine')
            if label in {'owned-clean-baseline', 'cleanup-restored-baseline'}:
                okay = okay and value['resources'] == []
            if self.required_lifecycle is not None:
                if self.system_ui:
                    # System UI may deactivate/background and restore the app.
                    # Accept only original monotonic counters, unchanged launches
                    # and a settled final native sample window. PID continuity
                    # remains enforced around every input by the existing owner.
                    prior=actual_lifecycle or self.required_lifecycle
                    if value['lifecycle']['launches']!=prior['launches'] or any(value['lifecycle'][k]<prior[k] for k in ('backgrounds','activations')):
                        raise AssertionError('Owned system UI lost native lifecycle continuity')
                    if actual_lifecycle is not None and value['lifecycle']!=actual_lifecycle:
                        stable_since=None;stable_count=0
                    actual_lifecycle=value['lifecycle'].copy()
                elif label.endswith('-restart-app'):
                    # A normal mobile stop can persist Hidden/Suspended before
                    # process exit. Startup can also receive real visibility
                    # transitions. Keep the exact launch delta, monotonic native
                    # backgrounds/activations and a settled observation window;
                    # never replace original counters with requested increments.
                    prior=actual_lifecycle
                    required=self.required_lifecycle
                    counts=value['lifecycle']
                    if (counts['launches']!=required['launches']
                            or counts['activations']<required['activations']
                            or counts['backgrounds']<required['backgrounds']
                            or prior is not None and any(counts[key]<prior[key] for key in counts)):
                        raise AssertionError('Feature restart lost original native lifecycle continuity')
                    if prior is not None and counts!=prior:
                        stable_since=None;stable_count=0
                    actual_lifecycle=counts.copy()
                else:okay=okay and value['lifecycle']==self.required_lifecycle
            witness = None
            if 'peer' in kinds:
                peer_expected=projection(self.area,expected)
                if self.area in {'world-web','tablet-web'}:
                    # The range permits backend-internal nonce recovery loads,
                    # but both independent reads must agree on the actual
                    # committed-document counter. A forged primary increment
                    # cannot pass with a still-old secondary document.
                    peer_expected['documentLoads']=value['state']['documentLoads']
                peer_okay, witness = self.observed_witness(ticket, barrier, peer_expected)
                okay = okay and peer_okay
            details, subject = [], None
            if okay:
                try:
                    details, subject = self.artifacts(value, ticket, kinds)
                except (AssertionError, OSError, EOFError, SyntaxError) as error:
                    okay, last_problem = False, str(error)
            if okay and native_motion:
                # A single native window replaces later RPC samples only after
                # all original evidence I/O. Primary and actor must still be
                # fresh here; earlier successful reads cannot expire in transit.
                epoch = number(self.epoch_ms(), 1)
                okay = all(-250 <= epoch - captured <= 1500 for captured in
                    (value['capturedEpochMs'], witness['capturedEpochMs']))
                if not okay: last_problem = 'Emote primary or actor expired during original evidence I/O'
            # Fixture, peer and artifact I/O also consume the existing checkpoint
            # budget. A late final source read cannot turn an old sample green.
            current=self.now()
            if current>=deadline:raise AssertionError('Common '+self.area+' '+label+': source/evidence exceeded the checkpoint deadline; '+last_problem)
            self.samples.append(dict(phase=label, ticket=ticket, actionBarrierEpochMs=barrier, sequence=value['sequence'], capturedEpochMs=value['capturedEpochMs'],
                                     state=value['state'], resources=value['resources'], lifecycle=value['lifecycle'], witness=witness, evidence=details, navigationHttp=navigation_receipts))
            if okay:
                if progressing_script and initial_effects is None:
                    initial_effects = value['state']['effects']
                if stable_since is None:
                    stable_since = current
                stable_count += 1
                if (native_motion or stable_count >= 3 and current - stable_since >= duration
                        and (not progressing_script or value['state']['effects'] >= initial_effects + 2)):
                    if subject is not None:
                        self.previous_subject = subject
                    self.lifecycle = value['lifecycle'].copy()
                    phase = dict(phase=label, advancingSamples=stable_count,
                        stableSeconds=current - stable_since, lastSequence=value['sequence'], evidence=details)
                    if native_motion:
                        motion = next(row['observed'] for row in details if row['kind'] == 'file')
                        phase.update(stabilitySource='original-native-motion-v1',
                            nativeSamples=motion['nativeSamples'], nativeSpanMs=motion['nativeSpanMs'],
                            requiredNativeSpanMs=motion['requiredSpanMs'])
                    self.phases.append(phase)
                    return value
            else:
                stable_since, stable_count, initial_effects = None, 0, None
            if self.now() >= deadline:
                break
            self.sleep(0.25)
        raise AssertionError('Common ' + self.area + ' ' + label + ': ' + last_problem)

    def execute(self):
        scenario = SCENARIOS[self.area]
        expected_baseline = expand(scenario['baseline'], context(self.run))
        measured = scenario.get('measuredBaselineFields', [])
        def expected_step(step):
            expected = expand(step['state'], context(self.run))
            expected.update({key: expected_baseline[key] for key in step.get('originalFields', [])})
            return expected
        primary = None
        cleanup_okay = False
        cleanup_enabled = False
        baseline_qualified = False
        try:
            initial = secrets.token_hex(16)
            self.activate(initial)
            barrier = number(self.epoch_ms(), 1)
            # Phone Emote and Navigation baseline acquisition own normal setup.
            # Even a failed first observation can leave partial owned resources.
            # Its cleanup operation distinguishes issued/unissued ownership and
            # never dismisses an unowned initial tablet. Attempt restoration
            # while fixture authority is still active, preserving the failure.
            if self.area in ('emotes','world-navigation'):cleanup_enabled=True
            if measured:
                candidate = self.observe(initial, barrier)
                if not matches({key: candidate['state'][key] for key in expected_baseline if key not in measured},
                               {key: value for key,value in expected_baseline.items() if key not in measured}):
                    raise AssertionError('Original baseline contains a foreign open UI or unowned state')
                expected_baseline.update({key: candidate['state'][key] for key in measured})
                self.samples.append(dict(phase='original-baseline-candidate',ticket=initial,
                    actionBarrierEpochMs=barrier,sequence=candidate['sequence'],capturedEpochMs=candidate['capturedEpochMs'],
                    state=candidate['state'],resources=candidate['resources'],lifecycle=candidate['lifecycle'],
                    witness=None,evidence=[]))
            if self.area=='snapshots':self.source_profile=snapshot_profile(expected_baseline)
            self.wait('owned-clean-baseline', initial, barrier, expected_baseline, ['peer'])
            baseline_qualified = True
            cleanup_enabled = True
            for index, step in enumerate(scenario['steps']):
                if 'backends' in step and self.source_profile not in step['backends']:
                    self.not_applicable.append(dict(index=index+1,verb=step['verb'],sourceProfile=self.source_profile))
                    continue
                self.system_ui=step.get('systemUi',False)
                self.navigation_required={'open':'directory','navigate-missing':'missing-name'}.get(step['verb'])
                if self.area in {'world-web','tablet-web'}:
                    self.browser_transition=(step['documentTransition'],self.samples[-1]['state']['documentLoads'])

                if self.area == 'emotes' and step['verb'] == 'sit':
                    # The shipped UI randomizes Sit1/2/3. Request only ordinary
                    # Stop and Sit inputs; collect actual variants here, never
                    # ask an adapter to return a requested variant as a reading.
                    for attempt in range(24):
                        for verb in ('cancel', 'sit'):
                            ticket = secrets.token_hex(16)
                            self.activate(ticket, verb, {})
                            barrier = number(self.epoch_ms(), 1)
                            self.continuity('before', verb)
                            self.call('act', dict(verb=verb, inputs={}, ticket=ticket, fixtureUrl=self.url))
                            self.continuity('after', verb)
                            expected = expand(step['state'], context(self.run))
                            if verb == 'cancel':
                                expected.update(animation='idle', sit='none', override=False, poseProgress=0.0,
                                                restoredBeforeNominalEnd={'oneOf':[False,True]})
                            observed = self.wait(f'{index + 1:02d}-{verb}-attempt-{attempt + 1}', ticket,
                                barrier, expected, ['peer'] if verb == 'cancel' else step['evidence'])
                        variant = observed['state']['sit']
                        if variant not in self.sit_variants:
                            self.sit_variants.add(variant)
                            break
                    else:
                        raise AssertionError('Normal Sit did not expose all three actual variants within 24 attempts')
                    continue
                ticket = secrets.token_hex(16)
                self.activate(ticket, step['verb'], expand(step['inputs'], context(self.run)))
                # Capture host-side action barrier; no assertion or checkpoint is
                # ever sent to the adapter or independent observer process.
                barrier = number(self.epoch_ms(), 1)
                self.required_lifecycle = self.lifecycle.copy()
                if step['verb'] == 'restart-app':
                    self.required_lifecycle['launches'] += 1
                    self.required_lifecycle['activations'] += 1
                elif step['verb'] == 'background-resume':
                    self.required_lifecycle['backgrounds'] += 1
                    self.required_lifecycle['activations'] += 1
                self.continuity('before', step['verb'])
                self.call('act', dict(verb=step['verb'], inputs=expand(step['inputs'], context(self.run)),
                                     ticket=ticket, fixtureUrl=self.url))
                self.continuity('after', step['verb'])
                if self.area == 'create' and step['verb'] == 'model-create':
                    self.model_ticket = ticket
                if self.area == 'create' and step['verb'] == 'apply-texture':
                    self.texture_ticket = ticket
                if self.area == 'audio' and step['verb'] == 'record-start' and step['state']['recording']:
                    self.recorded_ticket = ticket
                if self.area=='snapshots':
                    if step['verb']=='capture' and step['state']['files']==1:self.capture_ticket=ticket
                    self.snapshot_file_source={'capture':'snapshot-private-original','save':'snapshot-saved-original',
                        'share-select-owned':'snapshot-receiver-original','upload':'snapshot-upload-original'}.get(step['verb'])
                # Negative/cancellation/quiet assertions must remain true for a
                # full observation window; an early empty sample is insufficient.
                negative = (any(word in step['verb'] for word in ('cancel', 'denied', 'reject', 'stale', 'foreign', 'stop', 'delete', 'discard'))
                    or self.area=='lifecycle-input' and step['verb'] in {'back','release-input','close-editor'}
                    or self.area=='scripts' and step['verb'] in {'restart-app','load-url'}
                    or self.area=='world-navigation' and step['verb'] in {'directory-search','navigate-missing','dismiss-error','close'}
                    or self.area=='assets' and step['verb'] in {'inspect-baking-unavailable','upload-picker-accept-unavailable','retire-staged-primary'}
                    or self.area=='chat' and step['verb'] in {'close','peer-send-distant','network-remove-mixer','network-restore-mixer','await-no-replay'}
                    or self.area in {'world-web','tablet-web'} and step['verb'] in {'restore-resource','deliver-retired-inline-message','close'})
                self.wait(f'{index + 1:02d}-{step["verb"]}', ticket, barrier,
                    expected_step(step), step['evidence'], duration=3.0 if negative else 0.5)
        except BaseException as error:
            primary = error
            raise
        finally:
            cleanup_errors = []
            if cleanup_enabled:
                try:
                    ticket = secrets.token_hex(16)
                    self.activate(ticket, 'cleanup', {})
                    barrier = number(self.epoch_ms(), 1)
                    self.required_lifecycle = None;self.system_ui=False;self.browser_transition=None;self.navigation_required=None
                    self.call('cleanup')
                    # Idempotence must be real. Two acknowledgments alone cannot
                    # establish removal or restoration of the initial state.
                    self.call('cleanup')
                    cleanup_baseline=dict(expected_baseline)
                    if self.area=='lifecycle-input':
                        # Original event history remains immutable after its
                        # active owner retires. Cleanup cannot reset a counter.
                        for key in ('worldAttempts','staleAttempts'):
                            cleanup_baseline[key]=self.samples[-1]['state'][key]
                    if baseline_qualified:
                        self.wait('cleanup-restored-baseline', ticket, barrier, cleanup_baseline, ['peer'], duration=3.0)
                        cleanup_okay = True
                    # Failed bootstrap has no qualified baseline/peer evidence.
                    # Restoration ACKs cannot supply a cleanup/product verdict
                    # or start new observation ownership after that failure.
                except BaseException as error:
                    cleanup_errors.append(error)
            self.report(dict(schemaVersion=1, contractVersion=VERSION, area=self.area, runId=self.run,
                phases=self.phases, samples=self.samples, cleanupEnabled=cleanup_enabled,
                cleanupSucceeded=cleanup_okay, sequenceCompleted=primary is None and cleanup_okay,
                testLogic='implemented', adapter='required-separately', deviceAcceptance=False,
                sourceProfile=self.source_profile,notApplicableSteps=self.not_applicable))
            if primary is None and cleanup_errors:
                raise cleanup_errors[0]
        return self.phases
