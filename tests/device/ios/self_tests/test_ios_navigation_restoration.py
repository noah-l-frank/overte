"""Restored role coordinator with actual owners and explicit native models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
import uuid
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack
from ios.adapters.navigation_quiet_image import NavigationQuietImage
from ios.adapters.navigation_restoration import NavigationRestoration
from ios.self_tests import test_ios_navigation_quiet_period as fixture


class NavigationRestorationTests(unittest.TestCase):
    setUp=fixture.NavigationQuietPeriodTests.setUp
    acquire=fixture.NavigationQuietPeriodTests.acquire
    action=fixture.NavigationQuietPeriodTests.action
    ready=fixture.NavigationQuietPeriodTests.ready
    restart_call=fixture.NavigationQuietPeriodTests.restart_call
    install=fixture.NavigationQuietPeriodTests.install
    inputs=fixture.NavigationQuietPeriodTests.inputs

    def configure(self):
        call=self.acquire();self.inputs(call);h=self.h
        self.ticket=uuid.uuid4().hex;h.harness.client.activate(self.ticket,'cleanup',{})
        def image(selector,client,run,role,request,root,lock,*,process_context,owner_files,directory_proof,previous,quiet=False):
            self.assertTrue(quiet)
            return NavigationQuietImage(PrivateFeatureState(h.root/('ios-navigation-quiet-'+role+'-'+request[4:]+'.json')),
                root,process_context['restart']['input']['newBinding'],run,role,request,lock,lambda:self.new.sdk.okay,
                native=self.new.native,sources=self.new.sources,fixture=h.fixture,frame_factory=self.new.gpu.factory,
                epoch_ms=h.now,monotonic=h.mono,sleep=self.new.sdk.gpu.sleep,process_context=process_context,
                owner_files=owner_files,directory=directory_proof,previous=previous,
                input_readers=dict(keys=self.keys.reader(),pointer=self.pointer_reader,geometry=self.keys.geometry()))
        h.flow.runtime._navigation_restored_image=image
        with h.flow.held():baseline=self.baseline_fixture.owner(historical=True)
        return NavigationRestoration(h.flow,baseline)

    def test_actual_restored_fields_images_and_quiet_preserve_live_native_root_responsibility(self):
        owner=self.configure();h=self.h;samples=[]
        for index in range(3):
            if index:self.new.sdk.gpu.sleep(1.6)
            samples.append(owner.advance())
        self.assertEqual(sorted(v['sequence'] for v in samples),[v['sequence'] for v in samples])
        self.assertEqual(3,len({v['sequence'] for v in samples}))
        self.assertTrue(all(v['resources'] and all(r.startswith('panel:navigation-') for r in v['resources']) for v in samples))
        self.assertTrue(all(v['state']==dict(location='A',bookmark=False,bookmarkName='',searchQuery='',searchResults=[],error='none',panel=False,addressDialog=False) for v in samples))
        with h.flow.held():
            owner.load();commands=deepcopy(self.new.gpu.commands);proof=owner.quiet()
            self.assertTrue(proof['lifetimeEndRequired']);self.assertEqual(3,len(proof['originals']))
            self.assertEqual(commands,self.new.gpu.commands)
            reference=owner.reference();derived=owner.validate_original(reference)
            self.assertEqual(samples[-1],derived['public']);self.assertEqual(commands,self.new.gpu.commands)
            for key,value in (('requestId','ios-'+uuid.uuid4().hex),('index',True),('ownerSha256','0'*64)):
                with self.subTest(key=key),self.assertRaises(NativeUIError):owner.validate_original(dict(reference,**{key:value}))
            self.assertEqual(commands,self.new.gpu.commands)
            from ios.adapters.navigation_publications import NavigationPublications
            publications=NavigationPublications(owner.admission,{0:h.flow.prior_observers()['primary'],1:owner.observer},
                transfer=owner.transfer,restoration=owner,guard=h.flow.clock,epoch_ms=h.now,monotonic=h.mono)
            self.assertEqual(derived,publications.validate_original(reference))
            self.assertEqual(commands,self.new.gpu.commands)

    def test_unknown_child_delivery_blocks_another_query_and_preserves_its_pending_owner(self):
        owner=self.configure();write=owner.store.write;lost=[]
        def save(value,previous):
            write(value,previous)
            if unpack(value['payload'])[0]['pending'] is not None and not lost:
                lost.append(True);raise OSError('Actual pre-query return lost')
        with patch.object(owner.store,'write',side_effect=save),self.assertRaises((NativeUIError,OSError)):owner.advance()
        before=deepcopy(self.new.gpu.commands)
        with self.assertRaises(NativeUIError):owner.advance()
        self.assertEqual(before,self.new.gpu.commands)
        with self.h.flow.held():owner.load();self.assertIsNotNone(owner.state['pending'])

    def test_complete_child_after_lost_parent_return_is_adopted_without_new_gpu_query(self):
        owner=self.configure();factory=self.h.flow.runtime._navigation_restored_image;lost=[]
        def image(*args,**kwargs):
            result=factory(*args,**kwargs);acquire=result.acquire
            def read(barrier):
                value=acquire(barrier)
                if not lost:lost.append(True);raise OSError('Actual completed child return lost')
                return value
            result.acquire=read;return result
        self.h.flow.runtime._navigation_restored_image=image
        with self.assertRaises((NativeUIError,OSError)):owner.advance()
        self.h.flow.runtime._navigation_restored_image=factory;before=deepcopy(self.new.gpu.commands)
        value=owner.advance();self.assertTrue(value['resources']);self.assertEqual(before,self.new.gpu.commands)
        self.assertEqual(1,len(owner.state['rows']))


if __name__=='__main__':unittest.main()
