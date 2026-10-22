"""Places controls over the existing Pico candidate/process/OpenXR input route."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.pico4.navigation import need
from adapters.token_places_ui import control_id, snapshot


def project(original):
    need(type(original.get('placesControlsVersion')) is int and original['placesControlsVersion'] == 1)
    return snapshot(dict(placesControlsVersion=1, open=original['open'], ready=original['ready'], observedEpochMs=original['updatedEpochMs'],
        scope=dict(instance=original['bridgeId'], generation=original['generation'], sequence=original['lastCommandSequence'],
                   elapsedMs=original['elapsedMs'], processId=original['processId']),
        controls=deepcopy([row for row in original['controls'] if control_id(row['id'])])))


class PicoPlacesIO:
    def __init__(self, original):
        self.original = original

    def capture(self):
        return project(self.original.capture())

    def activate(self, identifier, *, reference):
        self.original.navigation.input(identifier, reference=reference)

    def replace(self, identifier, value, *, reference):
        self.original.navigation.input(identifier, 'replace', value, reference=reference)

    def scroll(self, identifier, value, *, reference):
        self.original.navigation.input(identifier, 'scroll', direction=value, reference=reference)
