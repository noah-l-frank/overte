"""No-build source checks of actual normal app-button and UIKit factory hooks."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import gc
from pathlib import Path
import unittest
import weakref

ROOT=Path(__file__).resolve().parents[4]


class TabletWebButtonsNativeTests(unittest.TestCase):
    def test_actual_model_return_and_removed_uuid_do_not_dereference_destroyed_proxy(self):
        raw=(ROOT/'libraries/ui/src/ui/TabletScriptingInterface.cpp').read_text()
        add=raw.split('TabletButtonProxy* TabletButtonListModel::addButton(',1)[1].split('void TabletButtonListModel::removeButton(',1)[0]
        self.assertLess(add.index('endResetModel();'),add.index('tablet_app_buttons::inserted('))
        self.assertIn('if (overte::e2e::tablet_sources::enabled())',add)
        self.assertIn('button->getProperties(),ScriptManager::featureNativeCallContext()',add)
        self.assertIn('&TabletButtonProxy::clicked',add)
        remove=raw.split('void TabletButtonListModel::removeButton(',1)[1].split('int TabletButtonListModel::computeNewButtonIndex(',1)[0]
        self.assertLess(remove.index('tablet_app_buttons::removing(button)'),remove.index('_buttons.erase(itr)'))
        tail=remove.split('_buttons.erase(itr)',1)[1];self.assertIn('tablet_app_buttons::removed(observedButton)',tail)
        self.assertNotIn('button->',tail);self.assertNotIn('find(button)',tail)

    def test_actual_add_context_crosses_original_blocking_boundary_only_under_test_gate(self):
        raw=(ROOT/'libraries/ui/src/ui/TabletScriptingInterface.cpp').read_text()
        add=raw.split('TabletButtonProxy* TabletProxy::addButton(',1)[1].split('bool TabletProxy::onHomeScreen(',1)[0]
        self.assertIn('ScriptManager::FeatureNativeCallScope original(caller);result=addButton(properties)',add)
        self.assertIn('Qt::BlockingQueuedConnection',add)
        self.assertIn('BLOCKING_INVOKE_METHOD(this, "addButton"',add)
        self.assertLess(add.index('auto* result=_buttons.addButton(properties)'),add.index('tablet_app_buttons::returned(result,this,root,rootBirth)'))
        self.assertIn('tablet_app_buttons::find(result)',add)
        manager=(ROOT/'libraries/script-engine/src/ScriptManager.cpp').read_text()
        self.assertIn('&& method!="addButton"',manager)

    def test_root_registration_observes_same_weak_root_before_ordinary_navigation(self):
        raw=(ROOT/'tests/device/native/IOSTabletSourcesObservation.h').read_text()
        helper=raw.split('inline std::shared_ptr<Root> ensureRoot(',1)[1].split('// Called from the actual native source-navigation entry',1)[0]
        self.assertIn('auto root=findRoot(actual,item);if (root) {return root;}',helper)
        self.assertIn('QObject::connect(item,&QObject::destroyed',helper)
        self.assertNotIn('fixture=',helper);self.assertNotIn('navigations.push_back',helper)
        navigation=raw.split('inline QString navigation(',1)[1].split('inline void returned(',1)[0]
        self.assertIn('root=ensureRoot(actual,item)',navigation)
        observe=raw.split('inline QVariantMap observe(',1)[1]
        self.assertIn('if (rootIds.contains(root->birth))',observe)

    def test_actual_new_generation_rotates_source_token_and_creates_new_native_button(self):
        normal=(ROOT/'ios/ui/IOSNormalUiInput.cpp').read_text();ui=(ROOT/'ios/ui/IOSTouchUiMetrics.mm').read_text()
        self.assertIn('old.item == node && old.window == node->window() && old.source == source ? old.token : nonce()',normal)
        own=(ROOT/'tests/device/native/IOSTabletAppButtonsObservation.h').read_text()
        for field in ('"button",button->id','"control",found->id','"fixtureUrl",button->fixture','"nonce",button->nonce'):
            self.assertIn(field,own)
        update=ui.split('void updateNormalUiButtons(',1)[1].split('\n}\n#endif',1)[0]
        self.assertIn('previous != nil && ![previous.sourceControlToken isEqualToString:sourceToken]',update)
        a=update.index('[previous removeFromSuperview]');b=update.index('[buttons removeObjectForKey:identifier]');c=update.index('tabletE2EAccessibilityButton(window, identifier)')
        self.assertLess(a,b);self.assertLess(b,c)
        factory=ui.split('OverteIOSE2EAccessibilityButton* tabletE2EAccessibilityButton(',1)[1].split('void retainTabletE2EAccessibilityButtons(',1)[0]
        self.assertIn('button = [[OverteIOSE2EAccessibilityButton alloc] initWithFrame:CGRectZero]',factory)
        class Button:pass
        # The genuine factory policy, modeled on host: a retained old contact
        # does not transfer to the new Qt generation or magically become dead.
        cache={};old=Button();old.token='old-original';cache['same-id']=old;held=old;original=weakref.ref(old)
        source_token='new-original'
        if cache['same-id'].token!=source_token:del cache['same-id']
        if 'same-id' not in cache:cache['same-id']=Button()
        cache['same-id'].token=source_token;new=cache['same-id']
        self.assertIsNot(held,new);del old;gc.collect();self.assertIsNotNone(original())
        del held;gc.collect();self.assertIsNone(original());self.assertIs(new,cache['same-id'])

    def test_native_button_binding_requires_actual_qt_original_and_never_invents_WK_target(self):
        raw=(ROOT/'ios/web/IOSUIKitInputObservation.h').read_text()
        body=raw.split('inline void bindControl(',1)[1].split('inline QVariantMap targetOriginal(',1)[0]
        self.assertIn('tablet_app_buttons::control(item)',body);self.assertIn('original!=source',body)
        self.assertIn('target.button=button',body);self.assertNotIn('target.view=',body)
        self.assertIn('invalidate("qt-control-rebound")',body);self.assertIn('__weak UIButton* button=nil',raw)
        ui=(ROOT/'ios/ui/IOSTouchUiMetrics.mm').read_text()
        body=ui.split('if (id.startsWith("tablet-web-app."))',1)[1].split('// Every E2E proxy',1)[0]
        self.assertLess(body.index('normalUiInput().item(id,token)'),body.index('bindTabletButton(control,item,token'))
        self.assertIn('row.value("tabletAppButton").toObject().toVariantMap()',body)


if __name__=='__main__':unittest.main()
