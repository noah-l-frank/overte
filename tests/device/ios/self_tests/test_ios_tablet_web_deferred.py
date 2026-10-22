"""Original held callback receipts; no expected stimulus or simulated native execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import tablet_web_deferred as source
from ios.self_tests.test_ios_tablet_web_source import packet as trace
from ios.self_tests.test_ios_tablet_web_sources import stamp,RUN,ROOT,packet as sources


def query(index=1):return dict(schemaVersion=1,action=source.ACTION,commandId='ios-'+format(index,'032x'),runId=RUN,fixtureUrl=ROOT)


def fault(operation,index=1):
    value=dict(query(100+index),action=source.FAULT,operation=operation)
    if operation!='arm':value['recordId']='c'*32
    return value


def original_envelope(sequence=1):
    return json.dumps(dict(type=6,object='eventBridge',method='emitWebEvent',args=[json.dumps(dict(contract='overte-web-parity-v1',action='echo',sequence=sequence))],id=7))


def packet(index=1,phase='captured'):
    epoch={'empty':90450,'armed':90520,'captured':90650,'delivering':90701,'returned':90705,'delivered':90800,'discarded':90800,'overdue':120600}[phase]
    value=dict(iosTabletWebDeferredVersion=1,commandId=query(index)['commandId'],runId=RUN,fixtureUrl=ROOT,instance='b'*32,sequence=index,processId=31,
        clockDomain='native-main-ios-tablet-web-deferred',clockBefore=stamp(epoch),clockAfter=stamp(epoch),complete=True,failure=None,commandSequence=0,records=[],commands=[])
    if phase=='empty':return value
    def receipt(command,status,ordinal,issued,completed=None):
        return dict(iosTabletWebDeferReceiptVersion=1,command=command,instance=value['instance'],sequence=ordinal,issued=stamp(issued),
            completed=stamp(completed) if completed else None,status=status,record='c'*32 if status!='issued' else None)
    row=dict(id='c'*32,identity=deepcopy(trace()['events'][-1]['identity']),armCommand=fault('arm')['commandId'],deliveryCommand=None,discardCommand=None,
        armed=stamp(90500),bufferPending=False,callbackAlive=False,original=None,**{key:None for key in source.CLOCKS})
    value['records']=[row];value['commands']=[receipt(fault('arm'),'armed',1,90499,90501)];value['commandSequence']=1
    if phase=='armed':return value
    raw=original_envelope();row.update(captured=stamp(90600),bufferPending=True,callbackAlive=True,
        original=dict(envelope=raw,envelopeSha256=hashlib.sha256(raw.encode()).hexdigest(),nonce=row['identity']['nonce'],frame=row['identity']['url'],mainFrame=True,generation=row['identity']['grant']))
    if phase in ('delivering','returned','delivered'):
        row.update(deliveryCommand=fault('deliver',2)['commandId'],delivering=stamp(90700),bufferPending=False)
        value['commands'].append(receipt(fault('deliver',2),'issued' if phase=='delivering' else 'delivered',2,90699,None if phase=='delivering' else 90702));value['commandSequence']=2
        if phase!='delivering':row['returned']=stamp(90703);row['finally']=stamp(90704)
        if phase=='delivered':row.update(expired=stamp(90706),callbackAlive=False)
    elif phase=='discarded':
        row.update(discardCommand=fault('discard',2)['commandId'],discarded=stamp(90700),expired=stamp(90701),bufferPending=False,callbackAlive=False)
        value['commands'].append(receipt(fault('discard',2),'discarded',2,90699,90702));value['commandSequence']=2
    elif phase=='overdue':value.update(complete=False,failure='hold-deadline-exceeded');row['overdue']=stamp(120500)
    return value


class TabletDeferredTests(unittest.TestCase):
    def test_actual_original_body_retained_then_once_delivered_and_weakly_destroyed(self):
        empty=packet(1,'empty');armed=packet(2,'armed');captured=packet(3);delivered=packet(4,'delivered')
        source.validate(armed,query(2),31,previous=empty);source.validate(captured,query(3),31,previous=armed)
        original=source.held(captured)['original'];self.assertEqual(original_envelope(),original['envelope'])
        source.validate(delivered,query(4),31,previous=captured);source.drained(captured,delivered)
        self.assertEqual(original,delivered['records'][0]['original'])
        self.assertEqual(fault('deliver',2),delivered['commands'][1]['command'])

    def test_callback_body_return_does_not_imply_actual_capture_destruction(self):
        captured=packet(1);returned=packet(2,'returned');source.validate(returned,query(2),31,previous=captured)
        self.assertIsNotNone(returned['records'][0]['returned']);self.assertTrue(returned['records'][0]['callbackAlive'])
        with self.assertRaises(NativeUIError):source.drained(captured,returned)
        pending=packet(2,'delivering');source.original(pending)
        with self.assertRaises(NativeUIError):source.drained(captured,pending)

    def test_timeout_retains_original_buffer_and_explicit_discard_is_separate(self):
        captured=packet();overdue=packet(2,'overdue');source.validate(overdue,query(2),31,previous=captured)
        self.assertEqual(captured['records'][0]['original'],overdue['records'][0]['original'])
        self.assertTrue(overdue['records'][0]['bufferPending']);self.assertTrue(overdue['records'][0]['callbackAlive'])
        with self.assertRaises(NativeUIError):source.drained(captured,overdue)
        discarded=packet(2,'discarded');source.drained(captured,discarded)
        changed=deepcopy(overdue);changed['records'][0]['bufferPending']=False
        with self.assertRaises(NativeUIError):source.original(changed)

    def test_fault_query_cannot_supply_bytes_results_protocol_or_arbitrary_packet(self):
        source.command(fault('arm'),operation=True)
        for edit in ({'envelope':original_envelope()},{'text':'expected'},{'expectedEchoes':3},{'operation':'replay'},{'schemaVersion':True}):
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):source.command(fault('arm')|edit,operation=True)
        for body in ({'type':3}, {'type':6,'object':'eventBridge','method':'deleteLater','args':[]},
                     {'type':6,'object':'eventBridge','method':'emitWebEvent','args':['secret']},
                     {'type':6,'object':'eventBridge','method':'emitWebEvent','args':[json.dumps(dict(contract='overte-web-parity-v1',action='echo',sequence=True))]}):
            with self.subTest(body=body),self.assertRaises((NativeUIError,ValueError)):source.envelope(json.dumps(body))

    def test_original_args_and_native_nonce_issued_history_cannot_be_rewritten_or_retimed(self):
        before=packet();current=packet(2,'delivered')
        for fault_ in ('envelope','nonce','frame','generation','mainFrame','source','birth','clock','issue','lostCommand','earlyExpiry','reset','resurrect','recordId'):
            value=deepcopy(current);row=value['records'][0]
            if fault_=='envelope':row['original']['envelope']=original_envelope(9);row['original']['envelopeSha256']=hashlib.sha256(row['original']['envelope'].encode()).hexdigest()
            elif fault_=='nonce':row['original']['nonce']='22222222-2222-2222-2222-222222222222'
            elif fault_=='frame':row['original']['frame']+='?expected=1'
            elif fault_=='generation':row['original']['generation']+=1
            elif fault_=='mainFrame':row['original']['mainFrame']=False
            elif fault_=='source':row['identity']['source']['carrier']='9'*32
            elif fault_=='birth':value['instance']='9'*32
            elif fault_=='clock':row['delivering']=stamp(90500)
            elif fault_=='issue':value['commands'][1]['issued']=stamp(90600)
            elif fault_=='lostCommand':value['commands'].pop(0)
            elif fault_=='earlyExpiry':row['expired']=stamp(90601)
            elif fault_=='reset':value['commandSequence']=0
            elif fault_=='recordId':value['commands'][1]['command']['recordId']='9'*32
            else:
                before_=packet(1,'delivered');value=packet(2,'returned')
                with self.assertRaises(NativeUIError):source.validate(value,query(2),31,previous=before_)
                continue
            with self.subTest(fault=fault_),self.assertRaises(NativeUIError):source.validate(value,query(2),31,previous=before)

    def test_genuine_source_frame_join_and_arm_after_carrier_retirement_counterexample(self):
        captured=packet();source.join_sources(captured,sources(),trace())
        for fault_ in ('carrier','page','nonce','retired','pid'):
            value=deepcopy(captured);input_=sources();transcript=trace()
            if fault_=='carrier':value['records'][0]['identity']['source']['carrier']='9'*32
            elif fault_=='page':value['records'][0]['identity']['page']+=1
            elif fault_=='nonce':value['records'][0]['identity']['nonce']='22222222-2222-2222-2222-222222222222';value['records'][0]['original']['nonce']=value['records'][0]['identity']['nonce']
            elif fault_=='pid':input_['processId']=32
            else:
                row=input_['carriers'][0];row.update(alive=False,retired=stamp(90550),retireReturned=stamp(90551),destroyed=stamp(90650))
                row['bindings'][0].update(current=False,pageAlive=False,revoked=stamp(90550))
            with self.subTest(fault=fault_),self.assertRaises(NativeUIError):source.join_sources(value,input_,transcript)

    def test_foreign_record_refusal_preserves_original_buffer_and_unknown_never_resends(self):
        current=packet(2);current['clockBefore']=current['clockAfter']=stamp(90670)
        wrong=fault('discard',2);wrong['recordId']='9'*32
        refused=dict(iosTabletWebDeferReceiptVersion=1,command=wrong,instance=current['instance'],sequence=2,issued=stamp(90660),
            completed=stamp(90661),status='refused',record=None)
        current['commands'].append(refused);current['commandSequence']=2
        source.validate(current,query(2),31,previous=packet())
        self.assertEqual(original_envelope(),source.held(current)['original']['envelope'])
        self.assertEqual(refused,source.IOSTabletWebDefer.resolve(wrong,current))
        calls=[]
        def lost(q):calls.append(deepcopy(q));raise OSError('Native fault command return lost')
        transport=source.IOSTabletWebDefer(lost,lambda:'',lambda:90699,lambda:True,31,monotonic=lambda:0)
        with self.assertRaises(NativeUIError):transport.issue(fault('deliver',2),packet())
        self.assertEqual(1,len(calls))
        pending=packet(3,'delivering');self.assertEqual('issued',transport.resolve(fault('deliver',2),pending)['status'])
        self.assertEqual(1,len(calls))

    def test_real_receipt_decision_clock_can_precede_body_return_and_separate_capture_death(self):
        value=packet(2,'delivered');row=value['records'][0];result=value['commands'][1]
        self.assertLess(result['completed']['monotonicMs'],row['returned']['monotonicMs'])
        self.assertLess(row['finally']['monotonicMs'],row['expired']['monotonicMs'])
        source.original(value);source.drained(packet(),value)

    def test_slow_initial_native_clock_cannot_send_after_original_fault_budget(self):
        calls=[];now=[0.]
        def clock():now[0]=2.;return 90699
        transport=source.IOSTabletWebDefer(lambda q:calls.append(q),lambda:'',clock,lambda:True,31,monotonic=lambda:now[0])
        with self.assertRaises(NativeUIError):transport.issue(fault('deliver',2),packet())
        self.assertEqual([],calls)

    def test_native_issued_unknown_command_is_not_a_delivered_or_empty_result(self):
        captured=packet();pending=packet(2,'delivering');source.original(pending)
        self.assertEqual('issued',pending['commands'][1]['status'])
        with self.assertRaises(NativeUIError):source.drained(captured,pending)
        fake=deepcopy(pending);fake['records'][0]['returned']=stamp(90701)
        with self.assertRaises(NativeUIError):source.original(fake)


if __name__=='__main__':unittest.main()
