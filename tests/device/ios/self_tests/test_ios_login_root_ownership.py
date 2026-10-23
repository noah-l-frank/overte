"""Closed Login weak-root originals through the actual repository readers."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import login_root_ownership as login
from adapters import script_ui_root_ownership as original_roots

EPOCH=1700000000000


def packet():
    row=dict(observedIdentity='a'*32,kind='tablet',componentSource='file:///app.bundle/qml/dialogs/TabletLoginDialog.qml',
        firstObservedSequence=1,firstObservedEpochMs=EPOCH,firstObservedMonotonicMs=10,weakAlive=True,
        weakExpiredObservedEpochMs=0,weakExpiredObservedMonotonicMs=0)
    return dict(iosLoginUiRootsVersion=1,complete=True,ownership=dict(iosLoginUiRootOwnershipVersion=1,available=True,instance='b'*32,
        clockDomain='native-main-ios-login-ui-roots',sequence=1,processId=42,capturedEpochMs=EPOCH+10,monotonicMs=20,
        complete=True,wholeTreeReady=True,observationSequence=1,roots=[row]),controls=[dict(id='login.submit',
            token='11111111-1111-4111-8111-111111111111',observedIdentity='a'*32)])


class LoginRootOwnershipTests(unittest.TestCase):
    decoder=original_roots

    def test_positive_control_admits_actual_identity_but_hidden_alive_root_remains_held(self):
        value=packet();observation=dict(controls=[dict(id='login.submit',token=value['controls'][0]['token'])],loginRootOwnership=value)
        original=login.admitted(observation,control_id='login.submit',pid=42,epoch=EPOCH+10)
        hidden=deepcopy(value);hidden['controls']=[];hidden['ownership'].update(sequence=2,capturedEpochMs=EPOCH+100,monotonicMs=110)
        login.validate(hidden,pid=42,previous=value);self.assertTrue(login.follow(original,hidden,pid=42,epoch=EPOCH+100)['weakAlive'])
        ended=deepcopy(hidden);ended['ownership'].update(sequence=3,capturedEpochMs=EPOCH+200,monotonicMs=210)
        ended['ownership']['roots'][0].update(weakAlive=False,weakExpiredObservedEpochMs=EPOCH+150,weakExpiredObservedMonotonicMs=160)
        login.validate(ended,pid=42,previous=hidden);self.assertFalse(login.follow(original,ended,pid=42,epoch=EPOCH+200)['weakAlive'])

    def test_host_weak_operand_retention_distinguishes_hidden_from_actual_expiry(self):
        import gc,weakref
        class ActualRoot:pass
        item=ActualRoot();retained=item;weak=weakref.ref(item);first=packet();original=deepcopy(first['ownership']['roots'][0])
        def observed(sequence):
            value=packet();value['controls']=[];o=value['ownership'];o.update(sequence=sequence,capturedEpochMs=EPOCH+sequence*100,monotonicMs=sequence*100)
            if weak() is None:o['roots'][0].update(weakAlive=False,weakExpiredObservedEpochMs=EPOCH+200,weakExpiredObservedMonotonicMs=200)
            return value
        del item;gc.collect();hidden=observed(2);login.validate(hidden);self.assertTrue(login.follow(original,hidden,pid=42,epoch=EPOCH+200)['weakAlive'])
        del retained;gc.collect();dead=observed(3);login.validate(dead,previous=hidden)
        self.assertFalse(login.follow(original,dead,pid=42,epoch=EPOCH+300)['weakAlive'])

    def test_normal_login_menu_entry_is_not_a_dialog_operand_or_incomplete_inventory(self):
        value=packet();value['controls']=[];value['ownership'].update(roots=[],observationSequence=0)
        observation=dict(controls=[dict(id='login.entry',token='11111111-1111-4111-8111-111111111111')],loginRootOwnership=value)
        self.assertTrue(login.membership(observation,pid=42,epoch=EPOCH+10)['complete'])
        with self.assertRaises(NativeUIError):login.admitted(observation,control_id='login.entry',pid=42,epoch=EPOCH+10)

    def test_unavailable_incomplete_or_wrong_component_can_never_admit_a_root(self):
        for fault in ('missing','incomplete','version','foreign','identity','source','token','extra-secret'):
            value=packet()
            if fault=='missing':value['controls']=[]
            elif fault=='incomplete':value['complete']=False;value['controls']=[]
            elif fault=='version':value['iosLoginUiRootsVersion']=True
            elif fault=='foreign':value['ownership']['processId']=43
            elif fault=='identity':value['controls'][0]['observedIdentity']='c'*32
            elif fault=='source':value['ownership']['roots'][0]['componentSource']='file:///app.bundle/qml/hifi/AvatarApp.qml'
            elif fault=='token':value['controls'][0]['token']='not-an-original-token'
            else:value['controls'][0]['password']='must-not-be-accepted'
            observation=dict(controls=[dict(id='login.submit',token='11111111-1111-4111-8111-111111111111')],loginRootOwnership=value)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):login.admitted(observation,control_id='login.submit',pid=42,epoch=EPOCH+10)

    def test_actual_root_history_cannot_truncate_rebirth_or_return_from_expiry(self):
        before=packet();after=deepcopy(before);after['controls']=[];after['ownership'].update(sequence=2,capturedEpochMs=EPOCH+100,monotonicMs=110)
        after['ownership']['roots'][0].update(weakAlive=False,weakExpiredObservedEpochMs=EPOCH+90,weakExpiredObservedMonotonicMs=100)
        login.validate(after,previous=before)
        for fault in ('truncate','first-time','rebirth','revive'):
            changed=deepcopy(after);changed['ownership'].update(sequence=3,capturedEpochMs=EPOCH+200,monotonicMs=210)
            if fault=='truncate':changed['ownership'].update(roots=[],observationSequence=0)
            elif fault=='first-time':changed['ownership']['roots'][0]['firstObservedEpochMs']+=1
            elif fault=='rebirth':changed['ownership']['instance']='c'*32
            else:changed['ownership']['roots'][0].update(weakAlive=True,weakExpiredObservedEpochMs=0,weakExpiredObservedMonotonicMs=0)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):login.validate(changed,previous=after)

    def test_native_getter_uses_actual_operands_qpointer_and_independent_profile_without_fields(self):
        root=Path(__file__).resolve().parents[4];header=(root/'tests/device/native/IOSLoginUiRootOwnership.h').read_text()
        self.assertIn('defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)',header)
        self.assertIn('script_ui_roots::Profile::Login',header);self.assertIn('return genericLoginRoot(item)',header)
        self.assertIn('context->nameForObject(root)=="root"',header);self.assertIn('context->baseUrl()==PathUtils::qmlUrl(suffix)',header)
        self.assertNotIn('property("text")',header);self.assertNotIn('invokeMethod',header);self.assertNotIn('destroy()',header)
        source=(root/'ios/ui/IOSNormalUiInput.cpp').read_text()
        self.assertLess(source.index('loginInventory.visit(node)'),source.index('QHash<QString, Control> controls'))
        self.assertIn('const auto retainedLoginRoots=_loginRoots.values()',source)
        self.assertIn('loginInventory.control(control.item,id,control.token)',source)
        self.assertIn('_loginRoots.size()>=64) {_loginRootsComplete=false;}',source)
        self.assertIn('if (!_loginRootsComplete || _loginRoots.size()>64)',source)

    def test_shared_default_script_profile_stays_literal_compatible(self):
        from ios.self_tests.world_web_ui_roots_fixture import Root,RootCensus
        source=RootCensus();root=Root('manager');source.observe(root)
        value=source.source();self.decoder.validate(value)
        with self.assertRaises(NativeUIError):self.decoder.validate(value,profile='login')
        with self.assertRaises(NativeUIError):self.decoder.validate(packet()['ownership'])


if __name__=='__main__':unittest.main()
