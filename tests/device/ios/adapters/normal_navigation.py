"""Normal iOS HUD/dialog/Places flow, with explicitly limited UI-only evidence."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.normal_ui import Locator, NativeUIError
from navigation_observation import OPERATIONS, viewpoint_urls

PROFILE = 'ios-native-qt-input-v1'
SCOPE = 'NATIVE_UI_COMPONENT_ONLY'


def configuration(target):
    profile = target.get('normalNavigation')
    if profile is None:
        return None
    if (not isinstance(profile, dict) or set(profile) != {'contractVersion', 'profile', 'sceneUrl'}
            or type(profile['contractVersion']) is not int or profile['contractVersion'] != 1
            or profile['profile'] != PROFILE or target.get('physical') is not True
            or target.get('nativeUiObservation') != {'kind': 'uikit-documents', 'version': 1}
            or type(target['nativeUiObservation']['version']) is not int or not target.get('testBuild')):
        raise NativeUIError('Normal iOS navigation requires its explicit native UI component profile')
    viewpoint_urls(profile['sceneUrl'])
    return profile


class IOSNavigation:
    def __init__(self, ui, native, profile, state, save):
        self.ui, self.native, self.state, self.save = ui, native, state, save
        self.urls = set(viewpoint_urls(profile['sceneUrl']).values())
        observed = native.capture()
        self.context = {'processId': observed['processId'], 'inputInstance': observed['instance'],
            'sceneUrl': profile['sceneUrl'], 'scope': SCOPE}
        owned = state.get('iosNormalNavigation')
        if owned is not None and (not isinstance(owned, dict)
                or set(owned) != {'context', 'addressOwned', 'tabletOwned'}
                or owned['context'] != self.context
                or type(owned['addressOwned']) is not bool or type(owned['tabletOwned']) is not bool):
            raise NativeUIError('Normal iOS navigation belongs to a different native UI session')
        self.goto = self.locator('hud.goto')
        self.address, self.go, self.cancel = (self.locator('address.' + name) for name in ('field', 'go', 'cancel'))
        self.open_tablet = Locator('accessibility id', 'OverteTabletOpen')
        self.close_tablet = Locator('accessibility id', 'OverteTabletClose')
        self.home, self.places = self.locator('tablet.home'), self.locator('tablet.places')
        self.back, self.forward = self.locator('places.back'), self.locator('places.forward')

    @staticmethod
    def locator(control):
        return Locator('accessibility id', 'OverteNavigation.' + control)

    def owned(self, key):
        return (self.state.get('iosNormalNavigation') or {}).get(key, False)

    def mark(self, key, value):
        if 'iosNormalNavigation' not in self.state:
            self.state['iosNormalNavigation'] = {'context': self.context, 'addressOwned': False, 'tabletOwned': False}
        self.state['iosNormalNavigation'][key] = value
        self.save()

    def close_address(self):
        if self.owned('addressOwned'):
            if self.ui.available(self.address, require_enabled=False):
                self.ui.click(self.cancel)
            self.ui.wait_absent(self.address)
            self.mark('addressOwned', False)

    def close_owned_tablet(self):
        if self.owned('tabletOwned'):
            observed = self.native.capture()
            if observed['tabletShown'] and not self.ui.available(self.close_tablet, require_enabled=False):
                raise NativeUIError('Normal iOS owned tablet is covered by another dialog')
            if self.ui.available(self.close_tablet, require_enabled=False):
                self.ui.click(self.close_tablet)
            self.ui.wait_absent(self.close_tablet)
            if self.native.capture()['tabletShown']:
                raise NativeUIError('Normal iOS owned tablet did not actually close')
            self.mark('tabletOwned', False)

    def open_address(self):
        self.close_owned_tablet()
        if self.ui.available(self.address, require_enabled=False):
            if not self.owned('addressOwned'):
                raise NativeUIError('Normal iOS navigation found a pre-existing address editor')
            self.ui.wait_control(self.address)
            return
        if self.ui.available(self.close_tablet, require_enabled=False):
            raise NativeUIError('Normal iOS navigation found a pre-existing tablet')
        self.mark('addressOwned', True)
        self.ui.click(self.goto)
        self.ui.wait_control(self.address)

    def open_places(self):
        self.close_address()
        if not self.owned('tabletOwned'):
            if self.ui.available(self.close_tablet, require_enabled=False):
                raise NativeUIError('Normal iOS navigation found a pre-existing tablet')
            self.mark('tabletOwned', True)
            self.ui.click(self.open_tablet)
        self.ui.wait_control(self.close_tablet)
        # History controls can be disabled at either endpoint. The particular
        # selected Back/Forward input must be enabled when it is actually used.
        if (self.ui.available(self.back, require_enabled=False)
                and self.ui.available(self.forward, require_enabled=False)):
            return
        if self.ui.available(self.home):
            self.ui.click(self.home)
        observed = self.native.capture()
        pages = sorted((row['id'] for row in observed['controls'] if row['id'].startswith('tablet.page.')),
                       key=lambda value: int(value.rsplit('.', 1)[1]))
        for page in (None, *pages):
            if page is not None:
                self.ui.click(self.locator(page))
            for _attempt in range(8):
                if self.ui.available(self.places):
                    self.ui.click(self.places)
                    return
                self.ui.sleep(0.1)
        raise NativeUIError('Normal iOS navigation did not find the actual Places button')

    def invoke(self, operation, arguments):
        from contracts import validate_operation_arguments
        if operation not in OPERATIONS:
            raise NativeUIError('Unknown normal iOS navigation operation')
        arguments = validate_operation_arguments(operation, arguments)
        if operation == 'places.open':
            self.open_address()
        elif operation == 'places.goto':
            if arguments['url'] not in self.urls:
                raise NativeUIError('Normal iOS navigation requires its exact owned scene viewpoint')
            self.open_address()
            self.ui.click(self.address)
            self.native.edit('replace', arguments['url'])
            self.ui.click(self.go)
            self.ui.wait_absent(self.address)
            self.mark('addressOwned', False)
        elif operation in {'places.back', 'places.forward'}:
            self.open_places()
            self.ui.click(self.back if operation == 'places.back' else self.forward)
        else:
            errors = []
            for close in (self.close_address, self.close_owned_tablet, self.ui.release_actions):
                try:
                    close()
                except Exception as error:
                    errors.append(error)
            if errors:
                raise errors[0]
            if 'iosNormalNavigation' in self.state:
                del self.state['iosNormalNavigation']
                self.save()
        # Only input delivery is acknowledged. The independent journey reads
        # actual scene/viewpoint/presentation state, and still needs code binding.
        return {'performed': True}
