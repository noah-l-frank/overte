"""No-build checks of the exact proposed UIKit pass-through hook.

These inspect native source and exercise weak-lifetime semantics on the host;
they neither execute UIKit nor qualify device input delivery.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import gc
import unittest
import weakref

ROOT=Path(__file__).resolve().parents[4]


class UIKitInputNativeSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.header=(ROOT/'ios/web/IOSUIKitInputObservation.h').read_text()

    def test_original_is_called_exactly_once_and_exceptions_only_finish_not_normal_return(self):
        body=self.header.split('inline void intercepted(',1)[1].split('inline bool methodUnchanged()',1)[0]
        self.assertEqual(1,body.count('original(application,selector,event);'))
        self.assertIn('@try { original(application,selector,event);returned=true; }',body)
        self.assertIn('@finally { try { @try { finish(entry,returned); }',body)
        self.assertIn('id __unsafe_unretained application',body)
        self.assertIn('UIEvent* __unsafe_unretained event',body)
        self.assertNotIn('sendEvent:',body)
        # No catch around the original body can replace a product exception.
        original=body.split('@try { original(application,selector,event);returned=true; }',1)[1]
        self.assertTrue(original.lstrip().startswith('@finally'))

    def test_startup_only_actual_runtime_class_and_superclass_not_modified(self):
        body=self.header.split('inline void install()',1)[1].split('inline bool command(',1)[0]
        for fragment in ('actual.attempted=true','QGuiApplication::allWindows().isEmpty()',
                         'app.windows.count!=0','object_getClass(app)','class_copyMethodList(cls,&count)',
                         'class_addMethod(cls,@selector(sendEvent:)',
                         'method_setImplementation(method,reinterpret_cast<IMP>(&intercepted))'):
            self.assertIn(fragment,body)
        self.assertIn('method_getName(methods[i])==@selector(sendEvent:)',body)
        observer=self.header.split('inline QVariantMap observe(',1)[1]
        self.assertNotIn('install(',observer)
        self.assertIn('methodUnchanged()',observer)
        self.assertNotIn('method_exchangeImplementations',self.header)

    def test_event_birth_precedes_actual_entered_clock_for_first_new_event(self):
        body=self.header.split('inline quint64 entered(',1)[1].split('inline void finish(',1)[0]
        self.assertLess(body.index('objectId(event,"event")'),body.index('const auto stamp=clock(actual)'))
        # A first event can cross a millisecond boundary. Capturing entered
        # first would make the genuine newly born object appear from the future.
        entered_before_birth,birth=100,101
        self.assertFalse(birth<=entered_before_birth)
        entered_after_birth=102;self.assertLessEqual(birth,entered_after_birth)

    def test_actual_real_application_initializers_install_before_first_window_not_temp_core(self):
        main=(ROOT/'interface/src/main.cpp').read_text();application=(ROOT/'interface/src/Application.cpp').read_text()
        native=(ROOT/'ios/web/IOSWebView.mm').read_text()
        self.assertLess(main.index('QCoreApplication tempApp'),main.index('Application app('))
        self.assertEqual(2,application.count('overte::ios::uikit_input::startup(),new '))
        self.assertIn('uikit_input::startup(),new MainWindow()',application)
        self.assertIn('uikit_input::startup(),new VKWindow()',application)
        startup=native.split('void registerIOSWebView()',1)[1]
        self.assertNotIn('uikit_input::install()',startup);self.assertNotIn('uikit_input::startup()',startup)
        self.assertIn('void startup() noexcept { install(); }',native)
        self.assertIn('uikit_input::bind(state.view,owner->featureBrowserIdentity());',native)

    def test_no_sensitive_input_or_recognizer_is_read_or_mutated(self):
        forbidden=('locationInView:', 'preciseLocationInView:', 'force', '.key', '.characters',
                   'keyCode', 'scanCode', 'timestamp', 'description]', 'addGestureRecognizer:',
                   'sendActionsForControlEvents:', 'cancelAllTouches', 'removeGestureRecognizer:')
        # Comments explain excluded properties; inspect actual executable lines.
        lines='\n'.join(line for line in self.header.splitlines() if not line.lstrip().startswith('//'))
        for fragment in forbidden:
            with self.subTest(fragment=fragment):self.assertNotIn(fragment,lines)
        self.assertIn('press.phase',lines);self.assertIn('touch.phase',lines)
        self.assertIn('__weak NSObject* object=nil',lines)
        self.assertIn('__weak WKWebView* view=nil',lines)

    def test_temporary_touch_collections_end_before_forward_and_weak_death_is_separate(self):
        entry=self.header.split('inline quint64 entered(',1)[1].split('inline void finish(',1)[0]
        self.assertIn('@autoreleasepool {',entry)
        self.assertIn('for (UITouch* touch in event.allTouches)',entry)
        self.assertIn('if (!row->object && row->expired.isEmpty())',self.header)
        self.assertIn('if (phase==3 || phase==4) { current->active=false;current->ended=clock(actual); }',self.header)
        class NativeObject:pass
        cached=NativeObject();observed=weakref.ref(cached)
        active=True;active=False
        self.assertFalse(active);self.assertIsNotNone(observed())
        del cached;gc.collect();self.assertIsNone(observed())

    def test_unknown_and_nested_dispatches_cannot_reset_or_claim_normal_return(self):
        self.assertIn('actual.pending.insert(entry)',self.header)
        self.assertIn('actual.pending.remove(entry)',self.header)
        self.assertIn('if (returned) { row["returned"]=clock(actual); }',self.header)
        self.assertIn('invalidate("contact-without-began")',self.header)
        self.assertNotIn('actual.pending.clear()',self.header)
        self.assertNotIn('actual.contacts.clear()',self.header)
        self.assertNotIn('actual.complete=true',self.header)
        pending={1,2};pending.remove(2)
        self.assertEqual({1},pending)


if __name__=='__main__':unittest.main()
