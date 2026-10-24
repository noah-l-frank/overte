"""Ordinary iOS SNAP inputs and original bytes; native UI component scope only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.normal_ui import Locator, NativeUIError
from contracts import validate_operation_arguments
from navigation_observation import viewpoint_urls

OPERATIONS = frozenset({'snapshot.open', 'snapshot.capture', 'snapshot.files', 'snapshot.close'})
PROFILE = 'ios-native-snapshot-v1'
SCOPE = 'NATIVE_UI_COMPONENT_ONLY'
MODES = ('still', 'animated', 'panorama', 'cubemap')
FORMATS = ('png', 'jpg', 'webp')
FIELDS = {'context', 'tabletOwned', 'originalMode', 'originalFormat', 'nonce', 'prefix',
          'preflightEmpty', 'capturePending'}


def configuration(target):
    value = target.get('normalSnapshot')
    if value is None:
        return None
    if (not isinstance(value, dict) or set(value) != {'contractVersion', 'profile', 'sceneUrl'}
            or type(value['contractVersion']) is not int or value['contractVersion'] != 1
            or value['profile'] != PROFILE or target.get('physical') is not True or not target.get('testBuild')
            or target.get('nativeUiObservation') != {'kind': 'uikit-documents', 'version': 1}
            or type(target['nativeUiObservation']['version']) is not int
            or target.get('snapshotFilesObservation') != {'kind': 'ios-documents', 'version': 1}
            or type(target['snapshotFilesObservation']['version']) is not int):
        raise NativeUIError('Normal iOS SNAP requires its explicit native input/file component profile')
    viewpoint_urls(value['sceneUrl'])
    return value


class IOSSnapshot:
    def __init__(self, ui, native, files, profile, state, save):
        self.ui, self.native, self.files, self.state, self.save = ui, native, files, state, save
        observed = native.capture()
        self.context = {'processId': observed['processId'], 'inputInstance': observed['instance'],
                        'nativeSession': native.session, 'sceneUrl': profile['sceneUrl'], 'scope': SCOPE}
        self.value = state.get('iosNormalSnapshot')
        if self.value is not None:
            self.validate(self.value)

    def validate(self, value):
        if (not isinstance(value, dict) or set(value) != FIELDS or value['context'] != self.context
                or type(value['tabletOwned']) is not bool or type(value['preflightEmpty']) is not bool
                or type(value['capturePending']) is not bool or value['originalMode'] not in (None, *MODES)
                or value['originalFormat'] not in (None, *FORMATS)):
            raise NativeUIError('Normal iOS SNAP belongs to a different native UI session')
        if value['prefix'] is not None:
            validate_operation_arguments('snapshot.files', {'prefix': value['prefix']})
            if value['nonce'] != value['prefix'].split('-')[1]:
                raise NativeUIError('Normal iOS SNAP prefix belongs to another run')
        if ((value['capturePending'] or value['preflightEmpty']) and value['prefix'] is None
                or value['nonce'] is not None and (not isinstance(value['nonce'], str)
                    or len(value['nonce']) != 16 or any(c not in '0123456789abcdef' for c in value['nonce']))):
            raise NativeUIError('Normal iOS SNAP ownership state is invalid')

    def mark(self, **changes):
        if self.value is None:
            self.value = dict(context=self.context, tabletOwned=False, originalMode=None, originalFormat=None,
                nonce=None, prefix=None, preflightEmpty=False, capturePending=False)
        elif self.state.get('iosNormalSnapshot') != self.value:
            raise NativeUIError('Normal iOS SNAP ownership changed')
        self.value = self.value | changes
        self.validate(self.value)
        self.state['iosNormalSnapshot'] = self.value
        self.save()

    @staticmethod
    def locator(control):
        return Locator('accessibility id', 'OverteNavigation.' + control)

    @staticmethod
    def control(observed, name, *, enabled=True):
        return next((row for row in observed['controls'] if row['id'] == name
                     and (row['enabled'] or not enabled)), None)

    def observed(self):
        observed = self.native.capture()
        if observed['processId'] != self.context['processId'] or observed['instance'] != self.context['inputInstance']:
            raise NativeUIError('Normal iOS SNAP lost its native input instance')
        return observed

    def wait(self, predicate):
        deadline = self.ui._now() + self.ui.timeout
        for _attempt in range(201):
            observed = self.observed()
            if predicate(observed):
                return observed
            if self.ui._now() >= deadline:
                break
            self.ui.sleep(0.1)
        raise NativeUIError('Normal iOS SNAP did not expose its actual requested control')

    def click(self, control):
        self.wait(lambda observed: self.control(observed, control))
        self.ui.click(self.locator(control))

    def show(self):
        observed = self.observed()
        if self.value is None or not self.value['tabletOwned']:
            if observed['tabletShown'] or self.control(observed, 'address.field', enabled=False):
                raise NativeUIError('Normal iOS SNAP found a pre-existing panel')
            self.mark(tabletOwned=True)
            self.ui.click(Locator('accessibility id', 'OverteTabletOpen'))
        elif not observed['tabletShown']:
            if self.control(observed, 'address.field', enabled=False):
                raise NativeUIError('Normal iOS SNAP is covered by a foreign editor')
            self.ui.click(Locator('accessibility id', 'OverteTabletOpen'))
        observed = self.wait(lambda value: value['tabletShown'])
        if self.control(observed, 'address.field', enabled=False):
            raise NativeUIError('Normal iOS SNAP is covered by a foreign editor')
        if self.control(observed, 'snapshot.name', enabled=False) is None:
            if self.control(observed, 'tablet.home'):
                self.click('tablet.home')
            observed = self.wait(lambda value: self.control(value, 'snapshot.entry')
                or any(row['id'].startswith('tablet.page.') for row in value['controls']))
            pages = sorted((row['id'] for row in observed['controls'] if row['id'].startswith('tablet.page.')),
                           key=lambda name: int(name.rsplit('.', 1)[1]))
            for page in (None, *pages):
                if page is not None:
                    self.click(page)
                found = False
                for _attempt in range(8):
                    if self.control(self.observed(), 'snapshot.entry'):
                        self.click('snapshot.entry'); found = True; break
                    self.ui.sleep(0.1)
                if found:
                    break
            self.wait(lambda value: self.control(value, 'snapshot.name'))
        self.wait(lambda value: self.control(value, 'snapshot.format'))

    def selected(self, control, options):
        self.click(control)
        observed = self.wait(lambda value: self.control(value, control + '.' + options[0]))
        selected = [option for option in options
                    if (row := self.control(observed, control + '.' + option)) and row['checked']]
        if len(selected) != 1:
            raise NativeUIError('Normal iOS SNAP has ambiguous actual radio selection')
        self.click(control + '.' + selected[0])
        return selected[0]

    def choose(self, control, options, option):
        self.click(control)
        self.click(control + '.' + option)
        if self.selected(control, options) != option:
            raise NativeUIError('Normal iOS SNAP ignored its ordinary radio input')

    def open(self):
        self.show()
        self.wait(lambda value: self.control(value, 'snapshot.capture') and self.control(value, 'snapshot.mode'))
        if self.value['originalMode'] is None:
            self.mark(originalMode=self.selected('snapshot.mode', MODES))
        if self.value['originalFormat'] is None:
            self.mark(originalFormat=self.selected('snapshot.format', FORMATS))
        self.mark(prefix=None, preflightEmpty=False, capturePending=False)

    def original_files(self, prefix):
        if self.value is None or not self.value['tabletOwned']:
            raise NativeUIError('Normal iOS SNAP has no owned surface')
        nonce = prefix.split('-')[1]
        if self.value['nonce'] not in (None, nonce) or self.value['prefix'] not in (None, prefix):
            raise NativeUIError('Normal iOS SNAP prefix belongs to another run')
        self.mark(nonce=nonce, prefix=prefix)
        self.observed()
        result = self.files.files(prefix)
        self.observed()
        if not self.value['capturePending']:
            self.mark(preflightEmpty=not result['files'])
        return result

    def take(self, arguments):
        if (self.value is None or not self.value['preflightEmpty'] or self.value['capturePending']
                or self.value['prefix'] != arguments['name']):
            raise NativeUIError('Normal iOS SNAP requires a fresh empty owned prefix')
        if self.files.files(arguments['name'])['files']:
            raise NativeUIError('Normal iOS SNAP prefix already has original output')
        self.show()
        self.wait(lambda value: self.control(value, 'snapshot.capture'))
        self.click('snapshot.name')
        self.native.edit('replace', arguments['name'], field='snapshot.name')
        self.choose('snapshot.mode', MODES, arguments['mode'])
        self.choose('snapshot.format', FORMATS, arguments['format'])
        self.mark(capturePending=True, preflightEmpty=False)
        self.click('snapshot.capture')

    def close(self):
        try:
            if self.value is not None and self.value['tabletOwned']:
                if self.value['capturePending'] or self.value['originalMode'] is not None or self.value['originalFormat'] is not None:
                    self.show()
                    if self.value['capturePending'] and self.control(self.observed(), 'snapshot.cancel'):
                        self.click('snapshot.cancel')
                    self.wait(lambda value: self.control(value, 'snapshot.capture'))
                    if self.value['originalMode'] is not None:
                        self.choose('snapshot.mode', MODES, self.value['originalMode'])
                    if self.value['originalFormat'] is not None:
                        self.choose('snapshot.format', FORMATS, self.value['originalFormat'])
                observed = self.observed()
                if observed['tabletShown']:
                    if self.control(observed, 'address.field', enabled=False):
                        raise NativeUIError('Normal iOS SNAP cannot close a foreign covering editor')
                    self.ui.click(Locator('accessibility id', 'OverteTabletClose'))
                    self.ui.wait_absent(Locator('accessibility id', 'OverteTabletClose'))
                if self.observed()['tabletShown']:
                    raise NativeUIError('Normal iOS SNAP did not actually close its owned tablet')
            self.ui.release_actions()
        except Exception:
            try:
                self.ui.release_actions()
            except Exception:
                pass
            raise
        if self.value is not None:
            del self.state['iosNormalSnapshot']; self.value = None; self.save()

    def invoke(self, operation, values):
        if operation not in OPERATIONS:
            raise NativeUIError('Unknown normal iOS SNAP operation')
        values = validate_operation_arguments(operation, values)
        if operation == 'snapshot.files':
            return self.original_files(values['prefix'])
        if operation == 'snapshot.open': self.open()
        elif operation == 'snapshot.capture': self.take(values)
        else: self.close()
        return {'performed': True}
