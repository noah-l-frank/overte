"""Source-reviewed normal Phone Go To and Places input; no navigation API calls."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import re
from urllib.parse import urlsplit

from adapters.normal_ui import Locator, NativeUIError
from navigation_observation import OPERATIONS, viewpoint_urls

PACKAGE = 'io.github.noah_be.overte.phone'
PROFILE = 'phone-native-v1'


def controlled_domain_url(url, expected_url, expected_host):
    """Validate input scope only; connection/arrival requires fresh probes."""
    from contracts import validate_operation_arguments
    for candidate in (url, expected_url):
        if (type(candidate) is not str or not 1 <= len(candidate) <= 2048
                or any(ord(char) < 33 or ord(char) == 127 for char in candidate)):
            raise NativeUIError('Normal Phone domain URL is invalid')
        validate_operation_arguments('navigation.enter-domain', {'url': candidate})
    parsed = urlsplit(expected_url)
    if (not 1 <= parsed.port <= 65535
            or type(expected_host) is not str or not expected_host or len(expected_host) > 253
            or expected_host.lower() != parsed.hostname.lower() or url != expected_url):
        raise NativeUIError('Normal Phone domain input differs from its controlled environment')
    return url


def validate_profile(value):
    if (not isinstance(value, dict) or set(value) != {'contractVersion', 'profile', 'sceneUrl'}
            or type(value['contractVersion']) is not int or value['contractVersion'] != 1
            or value['profile'] != PROFILE):
        raise ValueError('Normal Phone navigation profile is invalid')
    viewpoint_urls(value['sceneUrl'])
    return value


def validate_state(value):
    fields = {'processIdentity', 'sourceRevision', 'artifactSha256', 'addressOwned', 'tabletOwned'}
    if (not isinstance(value, dict) or set(value) != fields
            or not isinstance(value['processIdentity'], str)
            or not 1 <= len(value['processIdentity']) <= 160
            or any(ord(char) < 33 or ord(char) == 127 for char in value['processIdentity'])
            or not isinstance(value['sourceRevision'], str)
            or re.fullmatch('[0-9a-f]{40}', value['sourceRevision']) is None
            or not isinstance(value['artifactSha256'], str)
            or re.fullmatch('[0-9a-f]{64}', value['artifactSha256']) is None
            or type(value['addressOwned']) is not bool or type(value['tabletOwned']) is not bool):
        raise ValueError('Normal Phone navigation ownership state is invalid')
    return value


class PhoneNavigation:
    def __init__(self, ui, profile, state, identity, process_identity, save):
        self.ui = ui
        self.profile = validate_profile(profile)
        self.urls = set(viewpoint_urls(self.profile['sceneUrl']).values())
        self.state, self.save = state, save
        # A native installed-code binding must already be independently verified.
        if (not isinstance(identity, dict)
                or set(identity) != {'schemaVersion', 'sourceRevision', 'artifactSha256', 'installedCandidateVerified'}
                or type(identity['schemaVersion']) is not int or identity['schemaVersion'] != 1
                or identity['installedCandidateVerified'] is not True):
            raise NativeUIError('Normal Phone navigation requires verified installed code')
        self.context = {'processIdentity': process_identity,
            'sourceRevision': identity['sourceRevision'], 'artifactSha256': identity['artifactSha256']}
        validate_state(self.context | {'addressOwned': False, 'tabletOwned': False})
        owned = state.get('normalNavigation')
        if owned is not None:
            validate_state(owned)
            if any(owned[key] != value for key, value in self.context.items()):
                raise NativeUIError('Normal Phone navigation ownership belongs to a different application')
        self.goto_entry = Locator('accessibility id', 'Go to destination')
        self.address = self.resource('PhoneAddressField')
        self.go = self.resource('PhoneAddressGoButton')
        self.cancel = self.resource('PhoneAddressCancelButton')
        self.tablet_entry = self.resource('tablet.open')
        self.close_tablet = self.resource('nav.close')
        self.home = self.resource('nav.home')
        self.places_entry = Locator('accessibility id', 'PLACES')
        self.back = self.resource('goBack')
        self.forward = self.resource('goForward')

    @staticmethod
    def resource(name):
        return Locator('id', PACKAGE + ':id/' + name)

    def owned(self, field):
        return (self.state.get('normalNavigation') or {}).get(field, False)

    def mark(self, field, value):
        if 'normalNavigation' not in self.state:
            self.state['normalNavigation'] = self.context | {'addressOwned': False, 'tabletOwned': False}
        self.state['normalNavigation'][field] = value
        self.save()

    def close_address(self):
        if self.owned('addressOwned'):
            if self.ui.available(self.address, require_enabled=False):
                self.ui.click(self.cancel)
            self.ui.wait_absent(self.address)
            self.mark('addressOwned', False)

    def close_owned_tablet(self):
        if self.owned('tabletOwned'):
            if self.ui.available(self.close_tablet, require_enabled=False):
                self.ui.click(self.close_tablet)
            self.ui.wait_absent(self.close_tablet)
            self.mark('tabletOwned', False)

    def open_address(self):
        self.close_owned_tablet()
        if self.ui.available(self.address, require_enabled=False):
            if not self.owned('addressOwned'):
                raise NativeUIError('Normal Phone navigation found a pre-existing address editor')
            self.ui.wait_control(self.address)
            return
        if self.ui.available(self.close_tablet, require_enabled=False) and not self.owned('tabletOwned'):
            raise NativeUIError('Normal Phone navigation found a pre-existing tablet panel')
        # Record input intent before click so partial failures retain cleanup.
        self.mark('addressOwned', True)
        self.ui.click(self.goto_entry)
        self.ui.wait_control(self.address)

    def open_places(self):
        self.close_address()
        if not self.owned('tabletOwned'):
            if self.ui.available(self.close_tablet, require_enabled=False):
                raise NativeUIError('Normal Phone navigation found a pre-existing tablet panel')
            self.mark('tabletOwned', True)
            self.ui.click(self.tablet_entry)
        self.ui.wait_control(self.close_tablet)
        if not (self.ui.available(self.back, require_enabled=False)
                and self.ui.available(self.forward, require_enabled=False)):
            if self.ui.available(self.home):
                self.ui.click(self.home)
            self.ui.wait_control(self.places_entry)
            self.ui.click(self.places_entry)
        # A history endpoint disables its unavailable direction. The selected
        # Back/Forward click below resolves one visible enabled control itself.

    def load_scene(self, url):
        """Submit precisely the approved controlled scene through the ordinary dialog.

        This internal foundation path supplies an input receipt only. Existing
        session/modules must independently observe actual departure/arrival.
        """
        from navigation_observation import owned_scene
        owned_scene(url)
        if url!=self.profile['sceneUrl']:
            raise NativeUIError('Normal Phone scene input differs from its approved scene')
        self.open_address()
        self.ui.replace_text(self.address,url)
        if self.ui.text(self.address)!=url:
            raise NativeUIError('Normal Phone scene address did not retain the original input')
        self.ui.click(self.go)
        self.ui.wait_absent(self.address)
        self.mark('addressOwned',False)
        return {'requested':True}

    def enter_domain(self, url, expected_url, expected_host):
        """Submit the exact controlled hifi input through the ordinary editor."""
        controlled_domain_url(url, expected_url, expected_host)
        self.open_address()
        self.ui.replace_text(self.address, url)
        if self.ui.text(self.address) != url:
            raise NativeUIError('Normal Phone domain address did not retain the original input')
        self.ui.click(self.go)
        self.ui.wait_absent(self.address)
        self.mark('addressOwned', False)
        return {'requested': True}

    def invoke(self, operation, arguments):
        if operation not in OPERATIONS:
            raise ValueError('Unknown normal Phone navigation operation')
        from contracts import validate_operation_arguments
        arguments = validate_operation_arguments(operation, arguments)
        if operation == 'places.open':
            self.open_address()
        elif operation == 'places.goto':
            if arguments['url'] not in self.urls:
                raise NativeUIError('Normal Phone navigation URL differs from its configured owned scene')
            self.open_address()
            self.ui.replace_text(self.address, arguments['url'])
            self.ui.click(self.go)
            self.ui.wait_absent(self.address)
            self.mark('addressOwned', False)
        elif operation in {'places.back', 'places.forward'}:
            self.open_places()
            self.ui.click(self.back if operation == 'places.back' else self.forward)
        elif operation == 'places.close':
            errors = []
            for close in (self.close_address, self.close_owned_tablet):
                try:
                    close()
                except Exception as error:
                    errors.append(error)
            try:
                self.ui.release_actions()
            except Exception as error:
                errors.append(error)
            if errors:
                raise errors[0]
            if 'normalNavigation' in self.state:
                del self.state['normalNavigation']
                self.save()
        return {'performed': True}
