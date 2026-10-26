"""Fresh native boundary models; no UIKit, compiler or device execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import unittest
import uuid
from adapters.normal_ui import NativeUIError
from ios.adapters import keyboard_source as source

RUN='a'*32
EPOCH=1900000000000


class Boundary:
    def __init__(self):
        self.time=0;self.queries=[];self.sequence=0;self.raw='';self.mutate=None;self.delay=0;self.good=True
        self.registered=self.stamp();self.events=[];self.objects=[];self.windows=[];self.instance=uuid.uuid4().hex
        self.window=uuid.uuid4().hex;self.geometry='b'*64
        self.objects.append(dict(id=self.window,kind='window',born=self.registered,expired=None,alive=True))
        self.windows.append(dict(id=self.window,key=True,visible=True,sceneActive=True,geometrySha256=self.geometry,responder=None))
    def stamp(self):
        self.time+=1;return dict(epochMs=EPOCH+self.time,monotonicMs=self.time)
    def notify(self,kind,*,local=True,screen_matches=None,valid=True,intersects=False):
        self.events.append(dict(sequence=len(self.events)+1,eventId=uuid.uuid4().hex,kind=kind,clock=self.stamp(),local=local,
            screenMatches=screen_matches,window=self.window,geometrySha256=self.geometry,
            frame=dict(valid=valid,intersectsWindow=intersects if valid else None)))
    def send(self,query):
        self.queries.append(deepcopy(query));self.sequence+=1;before=self.stamp()
        packet=dict(iosKeyboardVersion=1,requestId=query['commandId'],runId=query['runId'],instance=self.instance,sequence=self.sequence,
            processId=42,clockDomain='native-main-ios-keyboard',clockBefore=before,clockAfter=self.stamp(),
            source=dict(registered=self.registered,complete=True,ownerAlive=True,applicationActive=True,
                events=deepcopy(self.events),objects=deepcopy(self.objects),windows=deepcopy(self.windows)))
        if self.mutate:self.mutate(packet)
        self.raw=json.dumps(packet);self.time+=self.delay
    def reader(self):return source.IOSKeyboard(self.send,lambda:self.raw,lambda:EPOCH+self.time,lambda:self.good,42,
        monotonic=lambda:self.time/1000,sleep=lambda seconds:setattr(self,'time',self.time+round(seconds*1000)))


class KeyboardSourceTests(unittest.TestCase):
    def test_did_hide_is_actual_settled_absence_and_does_not_erase_notification_history(self):
        b=Boundary();b.notify('did-show',intersects=True);reader=b.reader();first=reader.read(RUN)
        self.assertTrue(source.measured(first)['keyboard']);old=deepcopy(first)
        b.notify('did-hide',valid=False);last=reader.read(RUN)
        self.assertFalse(source.measured(last)['keyboard']);self.assertEqual(old,first)
        self.assertEqual(first['source']['events'],last['source']['events'][:1]);self.assertEqual(2,len(b.queries))
        self.assertNotEqual(b.queries[0]['commandId'],b.queries[1]['commandId'])

    def test_unknown_initial_state_and_will_hide_are_never_invented_absence(self):
        b=Boundary();reader=b.reader()
        with self.assertRaises(NativeUIError):source.measured(reader.read(RUN))
        b.notify('will-hide')
        with self.assertRaises(NativeUIError):source.measured(reader.read(RUN))
        self.assertEqual(1,len(b.events))

    def test_did_change_frame_uses_actual_intersection_including_floating_keyboard(self):
        b=Boundary();reader=b.reader()
        for intersection in (True,False):
            b.notify('did-change-frame',intersects=intersection)
            self.assertIs(intersection,source.measured(reader.read(RUN))['keyboard'])
        b.notify('did-change-frame',valid=False)
        with self.assertRaises(NativeUIError):source.measured(reader.read(RUN))

    def test_foreign_or_ambiguous_os_context_cannot_prove_absence(self):
        for mutation in (
            lambda b:b.events[-1].update(local=False),lambda b:b.events[-1].update(local=None),
            lambda b:b.events[-1].update(screenMatches=False),lambda b:b.windows[0].update(geometrySha256='c'*64),
            lambda b:b.windows[0].update(key=False),lambda b:b.windows[0].update(sceneActive=False)):
            b=Boundary();b.notify('did-hide',valid=False);mutation(b)
            with self.subTest(mutation=mutation),self.assertRaises(NativeUIError):source.measured(b.reader().read(RUN))

    def test_incomplete_dead_owner_background_or_ambiguous_windows_never_qualify(self):
        mutations=(lambda v:v['source'].update(complete=False),lambda v:v['source'].update(ownerAlive=False),
            lambda v:v['source'].update(applicationActive=False))
        for mutation in mutations:
            b=Boundary();b.notify('did-hide',valid=False);b.mutate=mutation;value=b.reader().read(RUN)
            with self.subTest(mutation=mutation),self.assertRaises(NativeUIError):source.measured(value)
        b=Boundary();b.notify('did-hide',valid=False);other=uuid.uuid4().hex
        b.objects.append(dict(b.objects[0],id=other));b.windows.append(dict(b.windows[0],id=other))
        with self.assertRaises(NativeUIError):source.measured(b.reader().read(RUN))

    def test_native_responder_does_not_become_a_qt_field_or_keyboard_request(self):
        b=Boundary();b.notify('did-hide',valid=False);identity=uuid.uuid4().hex
        b.objects.append(dict(id=identity,kind='responder',born=b.stamp(),expired=None,alive=True))
        b.windows[0]['responder']=dict(id=identity,className='DeclaredNativeTextResponder')
        actual=source.measured(b.reader().read(RUN));self.assertFalse(actual['keyboard'])
        self.assertEqual(identity,actual['responder']['id']);self.assertNotIn('editor',actual);self.assertNotIn('focused',actual)

    def test_replayed_nonce_mutated_history_and_rebound_object_do_not_advance_reader(self):
        b=Boundary();b.notify('did-hide',valid=False);reader=b.reader();original=reader.read(RUN);saved=deepcopy(reader.acquisition)
        for mutation in (
            lambda v:v.update(requestId=original['requestId']),lambda v:v.update(sequence=original['sequence']),
            lambda v:v['source']['events'][0].update(local=False),lambda v:v['source']['objects'][0].update(id=uuid.uuid4().hex)):
            b.mutate=mutation
            with self.subTest(mutation=mutation),self.assertRaises(NativeUIError):reader.read(RUN)
            self.assertEqual(original,reader.last);self.assertEqual(saved,reader.acquisition)

    def test_positive_observed_object_death_cannot_later_become_alive_again(self):
        b=Boundary();b.notify('did-hide',valid=False);reader=b.reader();reader.read(RUN)
        b.objects[0].update(alive=False,expired=b.stamp());b.windows=[];dead=reader.read(RUN)
        self.assertFalse(dead['source']['objects'][0]['alive'])
        with self.assertRaises(NativeUIError):source.measured(dead)
        b.objects[0].update(alive=True,expired=None)
        with self.assertRaises(NativeUIError):reader.read(RUN)
        self.assertEqual(dead,reader.last)

    def test_native_clock_pid_boolean_schema_and_private_text_fail_closed(self):
        mutations=(lambda v:v.update(iosKeyboardVersion=True),lambda v:v.update(processId=43),
            lambda v:v['clockAfter'].update(monotonicMs=v['clockBefore']['monotonicMs']-1),
            lambda v:v['source']['events'][0].update(text='Private field content'),
            lambda v:v['source']['events'][0]['frame'].update(valid=True,intersectsWindow=0))
        for mutation in mutations:
            b=Boundary();b.notify('did-hide',valid=False);b.mutate=mutation
            with self.subTest(mutation=mutation),self.assertRaises(NativeUIError):b.reader().read(RUN)

    def test_late_transfer_and_lost_foreground_guard_never_qualify_old_notification(self):
        b=Boundary();b.notify('did-hide',valid=False);b.delay=1600
        with self.assertRaises(NativeUIError):b.reader().read(RUN)
        b=Boundary();b.good=False
        with self.assertRaises(NativeUIError):b.reader().read(RUN)
        self.assertEqual([],b.queries)

    def test_closed_read_command_has_no_input_or_expected_keyboard_parameter(self):
        query=dict(schemaVersion=1,commandId='ios-'+'f'*32,action=source.ACTION,runId=RUN)
        self.assertEqual(query,source.command(query))
        for extra in ('keyboard','focused','text','operation'):
            with self.subTest(extra=extra),self.assertRaises(NativeUIError):source.command(dict(query,**{extra:False}))


if __name__=='__main__':unittest.main()
