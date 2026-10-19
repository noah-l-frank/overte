"""Common bounded feature execution with independent observations and cleanup."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import math
import secrets
from . import evidence as bytes_evidence
from .contract import arguments, exact, identifier, number, result, state as validate_state, typed_equal
from .fixtures import context
from .scenarios import SCENARIOS, VERSION, expand
from .witness import projection


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
                 read_artifact, image_policy, continuity, monotonic, epoch_ms, sleep, report):
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
        return result(operation, self.invoke(operation, request))

    def observe(self, ticket, barrier):
        self.continuity('observe', None)
        value = self.call('observe', dict(afterSequence=self.sequence))
        self.continuity('observed', None)
        if value['runId'] != self.run or value['sequence'] <= self.sequence:
            raise ValueError('Foreign or replayed actual product sample')
        captured, epoch = value['capturedEpochMs'], number(self.epoch_ms(), 1)
        if captured < self.last_epoch or captured < barrier or captured > epoch + 250 or epoch - captured > 1500:
            raise ValueError('Actual product sample is stale or from a different clock context')
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
            source_ticket = (self.recorded_ticket if self.area == 'audio' and (kind == 'file' or value['state']['phase'] == 'completed' and requested == 'audio')
                             else self.capture_ticket if self.area == 'snapshots' and kind == 'file' else ticket)
            key = (requested, digest, source_ticket, self.model_ticket)
            if key in self.evidence_cache:
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
        for _attempt in range(81):
            value = self.observe(ticket, barrier)
            current = self.now()
            okay = matches(value['state'], expected)
            progressing_script = self.area == 'scripts' and bool(expected['running'])
            if progressing_script and initial_effects is not None and value['state']['effects'] < initial_effects:
                raise AssertionError('Active script effect counter regressed without a new engine')
            if label in {'owned-clean-baseline', 'cleanup-restored-baseline'}:
                okay = okay and value['resources'] == []
            if self.required_lifecycle is not None:
                okay = okay and value['lifecycle'] == self.required_lifecycle
            witness = None
            if 'peer' in kinds:
                peer_okay, witness = self.observed_witness(ticket, barrier, projection(self.area, expected))
                okay = okay and peer_okay
            details, subject = [], None
            if okay:
                try:
                    details, subject = self.artifacts(value, ticket, kinds)
                except (AssertionError, OSError, EOFError, SyntaxError) as error:
                    okay, last_problem = False, str(error)
            self.samples.append(dict(phase=label, ticket=ticket, actionBarrierEpochMs=barrier, sequence=value['sequence'], capturedEpochMs=value['capturedEpochMs'],
                                     state=value['state'], resources=value['resources'], lifecycle=value['lifecycle'], witness=witness, evidence=details))
            if okay:
                if progressing_script and initial_effects is None:
                    initial_effects = value['state']['effects']
                if stable_since is None:
                    stable_since = current
                stable_count += 1
                if (stable_count >= 3 and current - stable_since >= duration
                        and (not progressing_script or value['state']['effects'] >= initial_effects + 2)):
                    if subject is not None:
                        self.previous_subject = subject
                    self.lifecycle = value['lifecycle'].copy()
                    self.phases.append(dict(phase=label, advancingSamples=stable_count,
                        stableSeconds=current - stable_since, lastSequence=value['sequence'], evidence=details))
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
        try:
            initial = secrets.token_hex(16)
            self.activate(initial)
            barrier = number(self.epoch_ms(), 1)
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
            self.wait('owned-clean-baseline', initial, barrier, expected_baseline, ['peer'])
            cleanup_enabled = True
            for index, step in enumerate(scenario['steps']):
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
                                expected.update(animation='idle', sit='none', override=False, poseProgress=0.0)
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
                if self.area == 'create' and step['verb'] == 'import-local':
                    self.model_ticket = ticket
                if self.area == 'create' and step['verb'] == 'apply-texture':
                    self.texture_ticket = ticket
                if self.area == 'audio' and step['verb'] == 'record-start' and step['state']['recording']:
                    self.recorded_ticket = ticket
                if self.area == 'snapshots' and step['verb'] == 'capture' and step['state']['files'] == 1:
                    self.capture_ticket = ticket
                # Negative/cancellation/quiet assertions must remain true for a
                # full observation window; an early empty sample is insufficient.
                negative = any(word in step['verb'] for word in ('cancel', 'denied', 'reject', 'stale', 'foreign', 'stop', 'delete', 'discard'))
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
                    self.required_lifecycle = None
                    self.call('cleanup')
                    # Idempotence must be real. Two acknowledgments alone cannot
                    # establish removal or restoration of the initial state.
                    self.call('cleanup')
                    self.wait('cleanup-restored-baseline', ticket, barrier, expected_baseline, ['peer'], duration=3.0)
                    cleanup_okay = True
                except BaseException as error:
                    cleanup_errors.append(error)
            self.report(dict(schemaVersion=1, contractVersion=VERSION, area=self.area, runId=self.run,
                phases=self.phases, samples=self.samples, cleanupEnabled=cleanup_enabled,
                cleanupSucceeded=cleanup_okay, sequenceCompleted=primary is None and cleanup_okay,
                testLogic='implemented', adapter='required-separately', deviceAcceptance=False))
            if primary is None and cleanup_errors:
                raise cleanup_errors[0]
        return self.phases
