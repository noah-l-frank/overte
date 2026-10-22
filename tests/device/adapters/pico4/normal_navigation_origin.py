"""Directory selection through existing original Pico field and Home input."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0


class PicoNavigationOriginIO:
    def __init__(self, original):
        self.original = original

    def capture(self):
        return self.original.capture()

    def deliver(self, pending, text):
        try:
            self.original.navigation.input(pending['control'], pending['action'], text,
                token=pending['token'], expected_scope=pending['scope'])
        finally:
            if pending['action'] == 'replace':
                self.original.navigation.io.clear_private_input()
