"""Normal native W3C input primitives; never a feature-state verdict.

Owning adapters supply an actual Appium client, their existing bound session and
an independent process/foreground/installed-candidate continuity check. This
helper advertises no capabilities and discovers or installs no targets.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from dataclasses import dataclass
import math
import re
import time
from urllib.parse import quote

W3C_ELEMENT = 'element-6066-11e4-a52e-4f735466cecf'
REFERENCE = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}')
# W3C WebDriver normalized key table; these are actions, not literal text.
# https://www.w3.org/TR/webdriver/#keyboard-actions
WEBDRIVER_KEYS = frozenset((*range(0xE000, 0xE02A), *range(0xE031, 0xE03E),
                           0xE040, *range(0xE050, 0xE05E)))


class NativeUIError(RuntimeError):
    """Closed public error; selectors, entered text and transport details stay private."""


@dataclass(frozen=True)
class Locator:
    using: str
    value: str

    def __post_init__(self):
        if (not isinstance(self.using, str) or self.using not in {'id', 'accessibility id', 'class name'}
                or not isinstance(self.value, str)
                or not 1 <= len(self.value) <= 256
                or any(ord(char) < 32 or ord(char) == 127 for char in self.value)):
            raise NativeUIError('Normal native input requires a bounded ID locator')
        if self.using == 'class name' and self.value not in {
                'android.widget.EditText', 'XCUIElementTypeTextField'}:
            raise NativeUIError('Normal native input class is not a reviewed text field')


class NativeUI:
    def __init__(self, client, session, check_continuity, *, timeout=10.0,
                 monotonic=time.monotonic, sleep=time.sleep):
        if (not isinstance(session, str) or REFERENCE.fullmatch(session) is None
                or not callable(check_continuity)
                or type(timeout) not in (int, float) or not math.isfinite(timeout)
                or not 0.1 <= timeout <= 20):
            raise NativeUIError('Normal native input session or timeout is invalid')
        self.client = client
        self.base = '/session/' + quote(session, safe='')
        self.check_continuity = check_continuity
        self.timeout = timeout
        self.monotonic, self.sleep = monotonic, sleep
        self.last_clock = None

    def _check(self):
        try:
            if self.check_continuity() is False:
                raise NativeUIError('Continuity check failed')
        except Exception:
            raise NativeUIError('Normal native input lost its bound application state') from None

    def _request(self, method, path, body=None):
        try:
            return self.client.call(method, self.base + path, body)
        except Exception:
            raise NativeUIError('Normal native UI transport failed') from None

    def _now(self):
        value = self.monotonic()
        if (type(value) not in (int, float) or not math.isfinite(value)
                or self.last_clock is not None and value < self.last_clock):
            raise NativeUIError('Normal native input clock is invalid')
        self.last_clock = value
        return value

    @staticmethod
    def _element(value):
        if (not isinstance(value, dict) or not value or set(value) - {W3C_ELEMENT, 'ELEMENT'}):
            raise NativeUIError('Normal native element reference is malformed')
        references = list(value.values())
        if (not all(isinstance(ref, str) and REFERENCE.fullmatch(ref) for ref in references)
                or len(set(references)) != 1):
            raise NativeUIError('Normal native element reference is malformed')
        return '/element/' + quote(references[0], safe='')

    def _find_once(self, locator, *, require_enabled=True):
        if not isinstance(locator, Locator):
            raise NativeUIError('Normal native input requires a validated locator')
        self._check()
        values = self._request('POST', '/elements', {'using': locator.using, 'value': locator.value})
        self._check()
        if not isinstance(values, list):
            raise NativeUIError('Normal native element lookup is malformed')
        if len(values) > 1:
            raise NativeUIError('Normal native control is ambiguous')
        if not values:
            return None
        element = self._element(values[0])
        visible = self._request('GET', element + '/displayed')
        enabled = self._request('GET', element + '/enabled')
        self._check()
        if type(visible) is not bool or type(enabled) is not bool:
            raise NativeUIError('Normal native control state is malformed')
        return element if visible and (enabled or not require_enabled) else None

    def available(self, locator, *, require_enabled=True):
        return self._find_once(locator, require_enabled=require_enabled) is not None

    def wait_control(self, locator):
        self._resolve(locator)

    def wait_absent(self, locator):
        deadline = self._now() + self.timeout
        absent_since = None
        for _attempt in range(math.ceil(self.timeout / 0.1) + 1):
            visible = self._find_once(locator, require_enabled=False) is not None
            captured = self._now()
            absent_since = None if visible else captured if absent_since is None else absent_since
            if absent_since is not None and captured - absent_since >= 0.3:
                return
            if captured >= deadline:
                break
            self.sleep(min(0.1, max(0, deadline - captured)))
        raise NativeUIError('Normal native control did not disappear')

    def _resolve(self, locator):
        deadline = self._now() + self.timeout
        # Bound attempts even if an injected/native clock stalls. Only read
        # operations may be retried; no mutation is automatically replayed.
        for _attempt in range(math.ceil(self.timeout / 0.1) + 1):
            element = self._find_once(locator)
            if element is not None:
                return element
            if self._now() >= deadline:
                break
            self.sleep(min(0.1, max(0, deadline - self._now())))
        raise NativeUIError('Normal native control is unavailable')

    def click(self, locator):
        element = self._resolve(locator)
        self._check()
        self._request('POST', element + '/click', {})
        self._check()

    def replace_text(self, locator, text):
        # Match the public native text providers' UTF-16 bound. Do not smuggle
        # Enter/control keys into text; ordinary submit has its own UI control.
        try:
            valid = (isinstance(text, str) and len(text.encode('utf-16-le')) // 2 <= 4096
                     and not any(ord(char) < 32 or ord(char) == 127 or ord(char) in WEBDRIVER_KEYS
                                 for char in text))
        except UnicodeError:
            valid = False
        if not valid:
            raise NativeUIError('Normal native input text is invalid')
        element = self._resolve(locator)
        self._check()
        self._request('POST', element + '/clear', {})
        self._check()
        self._request('POST', element + '/value', {'text': text, 'value': list(text)})
        self._check()

    def press_enter(self, locator):
        """Submit the actual resolved field through one explicit native key input."""
        element = self._resolve(locator)
        self._check()
        self._request('POST', element + '/value', {'text': '\ue007', 'value': ['\ue007']})
        self._check()

    def text(self, locator):
        element = self._resolve(locator)
        self._check()
        value = self._request('GET', element + '/text')
        self._check()
        if type(value) is not str or len(value.encode('utf-8')) > 16384:
            raise NativeUIError('Normal native text observation is malformed')
        return value

    def replace_ascii_keys(self, locator, text):
        """Edit a real field through ordinary keyboard events (Qt textEdited).

        Accessibility set-value may update text without an actual edit signal.
        Owned Create names/numbers are bounded ASCII and need native key input.
        The selected driver's real W3C keyboard support remains a device check.
        """
        if (type(text) is not str or len(text) > 256
                or any(not 32 <= ord(character) <= 126 for character in text)):
            raise NativeUIError('Normal keyboard replacement requires bounded ASCII text')
        element = self._resolve(locator)
        self._check()
        self._request('POST', element + '/click', {})
        self._check()
        actions = [{'type': 'keyDown', 'value': '\ue009'},
                   {'type': 'keyDown', 'value': 'a'}, {'type': 'keyUp', 'value': 'a'},
                   {'type': 'keyUp', 'value': '\ue009'}]
        for character in text:
            actions.extend(({'type': 'keyDown', 'value': character},
                            {'type': 'keyUp', 'value': character}))
        try:
            self._check()
            self._request('POST', '/actions', {'actions': [
                {'type': 'key', 'id': 'overte-owned-feature-keyboard', 'actions': actions}]})
            self._check()
        finally:
            # Release owned modifiers even if the input response/process was
            # lost. Never replay an uncertain replacement action sequence.
            self.release_actions()
        if self.text(locator) != text:
            raise NativeUIError('Normal keyboard replacement was not observed in its field')

    def release_actions(self):
        # Release only this owned W3C session's inputs, including when its
        # process/foreground guard has failed. Never retry uncertain input.
        self._request('DELETE', '/actions')
