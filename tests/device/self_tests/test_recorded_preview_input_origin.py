"""Declared callback metadata models over actual PCM bytes; no native execution.

These codec/transport countercases do not validate C++ ticket lifetime, Qt
source ownership, ADC identity, acoustics or a peer.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import unittest
from adapters.normal_ui import NativeUIError
from adapters.recorded_preview_evidence import INPUT, validate, validate_input_origin
from self_tests.test_recorded_preview_evidence import Boundary


def attach_origin(packet, raw):
    packet['schemaVersion'] = 2
    source = packet['source']; rows = []; middle = len(raw) // 2
    for index, (offset, count) in enumerate(((0, middle), (middle, len(raw) - middle))):
        part = raw[offset:offset + count]
        rows.append(dict(sequence=20 + index, generation=4, readBytes=len(part),
            readSha256=hashlib.sha256(part).hexdigest(), inputRate=8000, inputChannels=1, resamplerUsed=False,
            routeRevision='18446744073709551615', readBeforeEpochMs=14000 + index * 500,
            readAfterEpochMs=14001 + index * 500, tapEpochMs=14002 + index * 500,
            readBeforeMonotonicMs=70000 + index * 500, readAfterMonotonicMs=70001 + index * 500,
            tapMonotonicMs=70002 + index * 500, offset=offset, bytes=count,
            convertedBytes=count, sha256=hashlib.sha256(part).hexdigest()))
    source['inputOrigin'] = dict(originVersion=1, available=True, profile='qt-source-read-to-preview-tap',
        instance=packet['instance'], admissionEpoch=5, coveredBytes=len(raw), rows=rows,
        physicalADCQualified=False, acousticQualified=False, peerQualified=False, resamplerHistoryQualified=False)
    return packet


class RecordedPreviewInputOriginTests(unittest.TestCase):
    def setUp(self):
        self.native = Boundary()
        self.request = 'a' * 32
        self.native.send(dict(schemaVersion=1, commandId=self.request, action='feature-recorded-audio-observe'))
        self.legacy = deepcopy(self.native.value); self.raw = self.native.files[INPUT]
        self.packet = attach_origin(deepcopy(self.legacy), self.raw)

    def admit(self, packet=None, raw=None):
        packet = self.packet if packet is None else packet
        validate(packet, packet['requestId'], 31, 20000)
        return validate_input_origin(packet, self.raw if raw is None else raw, required=True)

    def test_legacy_digital_packet_stays_literal_and_cannot_be_required_as_origin(self):
        original = deepcopy(self.legacy)
        self.assertIs(self.legacy, validate(self.legacy, self.request, 31, 20000))
        self.assertFalse(validate_input_origin(self.legacy, self.raw))
        with self.assertRaises(NativeUIError): validate_input_origin(self.legacy, self.raw, required=True)
        self.assertEqual(original, self.legacy)

    def test_two_original_fragments_rehash_exact_pcm_without_retiming_or_changing_packet(self):
        before = deepcopy(self.packet)
        self.assertTrue(self.admit()); self.assertEqual(before, self.packet)
        self.assertEqual('18446744073709551615', self.packet['source']['inputOrigin']['rows'][0]['routeRevision'])
        for name in ('physicalADCQualified', 'acousticQualified', 'peerQualified', 'resamplerHistoryQualified'):
            self.assertIs(self.packet['source']['inputOrigin'][name], False)

    def test_missing_unknown_and_explicit_unavailable_are_never_upgraded(self):
        packet = deepcopy(self.packet); packet['source']['inputOrigin'] = dict(originVersion=1, available=False)
        validate(packet, self.request, 31, 20000)
        self.assertFalse(validate_input_origin(packet, self.raw))
        with self.assertRaises(NativeUIError): self.admit(packet)
        for change in ('missing', 'unknown-version', 'false-with-extra'):
            packet = deepcopy(self.packet)
            if change == 'missing': del packet['source']['inputOrigin']
            elif change == 'unknown-version': packet['source']['inputOrigin']['originVersion'] = 2
            else: packet['source']['inputOrigin'] = dict(originVersion=1, available=False, rows=[])
            with self.subTest(change=change), self.assertRaises((NativeUIError, KeyError)): self.admit(packet)

    def test_gap_overlap_reused_read_and_changed_generation_route_or_format_are_refused(self):
        for name, value in (('offset', 24002), ('offset', 23998), ('sequence', 20), ('generation', 5),
                            ('routeRevision', '18446744073709551614'), ('inputRate', 16000), ('inputChannels', 2)):
            packet = deepcopy(self.packet); packet['source']['inputOrigin']['rows'][1][name] = value
            with self.subTest(name=name, value=value), self.assertRaises(NativeUIError): self.admit(packet)

    def test_original_clock_regression_retiming_and_revoked_admission_are_refused(self):
        for name, value in (('readBeforeEpochMs', 12999), ('readAfterEpochMs', 13999),
                            ('tapEpochMs', 16001), ('readBeforeMonotonicMs', 70003),
                            ('tapMonotonicMs', 70000)):
            packet = deepcopy(self.packet); packet['source']['inputOrigin']['rows'][0][name] = value
            with self.subTest(name=name), self.assertRaises(NativeUIError): self.admit(packet)
        for name, value in (('admissionEpoch', 7), ('admissionEpoch', True), ('instance', 'd' * 32)):
            packet = deepcopy(self.packet); packet['source']['inputOrigin'][name] = value
            with self.subTest(name=name), self.assertRaises(NativeUIError): self.admit(packet)

    def test_actual_pcm_and_each_fragment_digest_must_both_match(self):
        packet = deepcopy(self.packet); packet['source']['inputOrigin']['rows'][1]['sha256'] = '0' * 64
        with self.assertRaises(NativeUIError): self.admit(packet)
        changed = bytes([self.raw[0] ^ 1]) + self.raw[1:]
        packet = deepcopy(self.packet); packet['source']['input']['sha256'] = hashlib.sha256(changed).hexdigest()
        with self.assertRaises(NativeUIError): self.admit(packet, changed)

    def test_bounds_decimal_precision_unknown_fields_and_physical_claims_are_refused(self):
        mutations = [lambda p: p['source']['inputOrigin']['rows'][0].update(routeRevision=18446744073709551615),
            lambda p: p['source']['inputOrigin']['rows'][0].update(routeRevision='18446744073709551616'),
            lambda p: p['source']['inputOrigin']['rows'][0].update(readBytes=3),
            lambda p: p['source']['inputOrigin']['rows'][0].update(readBytes=16 * 1024 * 1024 + 2),
            lambda p: p['source']['inputOrigin']['rows'][0].update(extra=True),
            lambda p: p['source']['inputOrigin'].update(rows=p['source']['inputOrigin']['rows'] * 193),
            lambda p: p['source']['inputOrigin'].update(physicalADCQualified=True),
            lambda p: p.update(schemaVersion=1)]
        for index, mutate in enumerate(mutations):
            packet = deepcopy(self.packet); mutate(packet)
            with self.subTest(index=index), self.assertRaises(NativeUIError): self.admit(packet)

    def test_existing_json_transport_rehashes_v2_before_advancing_reader_state(self):
        self.native.mutate = lambda packet: attach_origin(packet, self.raw)
        reader = self.native.reader(); packet, original = reader.read(0, after_cycle=6)
        self.assertEqual(self.raw, original['input']); self.assertTrue(validate_input_origin(packet, self.raw, required=True))
        previous = reader.sequence
        def corrupt(packet):
            attach_origin(packet, self.raw); packet['source']['inputOrigin']['rows'][1]['sha256'] = '0' * 64
        self.native.mutate = corrupt
        with self.assertRaises(NativeUIError): reader.read(previous)
        self.assertEqual(previous, reader.sequence)
        self.assertTrue(all(row['action'] == 'feature-recorded-audio-observe' for row in self.native.commands))
