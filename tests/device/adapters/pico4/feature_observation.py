"""Original read-only feature diagnostics on the existing bound Pico session.

No capability is advertised: this is the observation backend for later complete
feature bindings, not a product-state/result synthesizer or native UI fallback.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import uuid

from adapters.normal_create import avatar_entities
from adapters.normal_script_manager import DIAGNOSTIC_FILE, read_native_diagnostic


class PicoFeatureObservation:
    def __init__(self, adapter, target, process_identity):
        self.adapter, self.target, self.identity = adapter, target, process_identity
        self.instance = None
        self.sequence = 0

    def guard(self):
        self.adapter.require_same_process(self.target, self.identity, 'native feature observation')
        if (self.adapter.require_pico_session_identity(self.target) != self.identity
                or self.adapter.adb.foreground_package(self.target) != 'org.overte.pico'):
            raise RuntimeError('OVT_PICO_FEATURE_OBSERVATION_REJECTED')

    def read(self, after_sequence, *, include_avatar_entities=False):
        try:
            if type(after_sequence) is not int or after_sequence < self.sequence or type(include_avatar_entities) is not bool:
                raise ValueError()
            installed = self.adapter._installation(self.target)
            self.guard()
            request = uuid.uuid4().hex
            self.adapter.write_control_command(self.target, self.identity, 'native feature observation',
                dict(schemaVersion=1, commandId=request, action='normal-feature-observe',
                     includeAvatarEntities=include_avatar_entities))
            value, _epoch = read_native_diagnostic(
                lambda: self.adapter.adb.read_debug_app_file(self.target, 'org.overte.pico',
                    'files/overte-e2e/' + DIAGNOSTIC_FILE, attempts=1),
                lambda: self.adapter.adb.epoch_milliseconds(self.target), self.guard,
                after_sequence, expected_request=request)
            if self.instance is not None and value['instance'] != self.instance:
                raise ValueError()
            if include_avatar_entities:
                avatar_entities(value)
            elif {'avatarEntities', 'entitiesComplete'} & set(value):
                raise ValueError()
            self.guard()
            if self.adapter._installation(self.target) != installed:
                raise ValueError()
            self.instance, self.sequence = value['instance'], value['sampleSequence']
            return value
        except Exception:
            raise RuntimeError('OVT_PICO_FEATURE_OBSERVATION_REJECTED') from None
