"""One proposed compound focus normal, then separately reviewed finite faults."""
import gc,hashlib,os,time,uuid
from pathlib import Path
from adapters.normal_ui import NativeUIError
from adapters.pico4.world_web_binding import PicoWorldWebBinding
from adapters.pico4.world_current_host_stage import WorldDocumentModelAdapter1,WorldCurrentHostSelection1
from adapters.pico4.world_document_model import WorldDocumentModelContext1
from adapters.pico4.world_current_input import PicoWorldCurrentInput
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client


class Fixture:
    def __init__(self,artifacts,*,delay=0.0,large_paths=False,cancel=False,controller=False,no_effect=False,foreign=False):
        self.parent=self.resources=self.io=None;self.closes=[];self.failure=None
        self.base=artifacts/'namespace';self.base.mkdir(mode=0o700)
        if large_paths:
            # Ordinary real owned paths, not a quota or shape mutation. Every
            # component is<255 and the whole original pathname stays<4096.
            # Choose actual ordinary path bytes, not an assumed RSS charge.
            # The final original Parent path is3920-3921 bytes; no source output
            # path/temporary involved in this ctor-only refusal reaches4096.
            target='namespace-target'
            key=hashlib.sha256(('org.overte.pico\0'+target).encode()).hexdigest()[:32]
            suffix='feature-world-web-'+key
            while len(str(self.base/suffix).encode())<3920:
                room=3920-len(str(self.base/suffix).encode())-1
                self.base=self.base/('p'*max(1,min(175,room)));self.base.mkdir(mode=0o700)
        run=uuid.uuid4().hex
        domain='.'.join(['a'*60]*4)+'.invalid' if large_paths else 'primary.invalid'
        service='https://'+domain+'/feature-fixture/v1'
        url=service+'/runs/'+run+'/'
        self.context=WorldDocumentModelContext1(run,url,*[uuid.uuid4().hex for _ in range(5)],str(uuid.uuid4()),uuid.uuid4().hex)
        self.context.validate()
        self.adapter=WorldDocumentModelAdapter1(self.base,self.context)
        self.config={'OVERTE_PICO_NORMAL_SCRIPTS':'1','OVERTE_ANDROID_E2E_DEBUG':'1',
            'OVERTE_PICO_OPENXR_INPUT':'1','OVERTE_E2E_SCENE_URL':'https://world-resource.invalid/scene.json'}
        self.previous={k:os.environ.get(k) for k in self.config};os.environ.update(self.config)
        self.binding=PicoWorldWebBinding(self.adapter)
        self.source=PhaseFixtureReader(Client(service,'n'*32),run,'world-web')
        self.selection=WorldCurrentHostSelection1(self.context,operation='ime',focus_get_delay=delay,event_return_handback=True,live_string_aliases=True,product_dom=True,cancel_dom_beforeinput=cancel,controller_focus=controller,controller_no_effect=no_effect,controller_foreign_scene=foreign)
    def construct(self):
        try:
            self.parent=self.binding.prefix('namespace-target',self.source,'https://foreign.invalid/feature-fixture/v1',resource_selection=self.selection)
            self.resources=self.parent.resource_participant
        except BaseException as error:
            self.parent=getattr(self.binding,'_resource_parent',None)
            self.resources=getattr(self.parent,'resource_participant',None)
            self.failure=(error,error.__traceback__)
            raise
    def factory(self):
        self.io=self.binding.world_prefix_current_source('namespace-target',self.parent)
        assert type(self.io) is PicoWorldCurrentInput and self.io.resource_provider is self.resources
    def read(self):return self.io.read(self.context.run,self.context.fixture_url,self.context.owner,'observe-current-focus','text')
    def close(self):
        if self.resources is not None:self.closes=self.resources.close_host()
        for k,v in self.previous.items():
            if v is None:os.environ.pop(k,None)
            else:os.environ[k]=v
        return self.closes


def trace(error):
    rows=[];seen=set()
    while error is not None and id(error) not in seen:
        seen.add(id(error));tb=error.__traceback__;frames=[]
        while tb is not None:
            fields={}
            for key in ('decoded','disk','stored','live','logical','n'):
                v=tb.tb_frame.f_locals.get(key)
                if type(v) is int:fields[key]=v
            frames.append(dict(source=tb.tb_frame.f_code.co_filename,line=tb.tb_lineno,name=tb.tb_frame.f_code.co_name,computed=fields));tb=tb.tb_next
        rows.append(dict(type=type(error).__name__,message=str(error),frames=frames))
        error=error.__cause__ or error.__context__
    return rows



def normal_cold_product_dom_current(artifacts):
    f=Fixture(artifacts);report={};business=None
    try:
        f.construct();f.factory();r=f.resources
        began=time.perf_counter();focus=f.read()
        ime,reader=r.create_ime_sources()
        arm=reader.arm()
        text='Grüße 🌍 漢字'
        delivery=ime.commit(text)
        observed=reader.observe(0)
        observed_rows=[observed]
        for sequence in (1,2,3):observed_rows.append(reader.observe(sequence))
        with r.lock.held():r.node.guard()
        before_dom=r.completed[0]['result']
        current_doc=r.reader.read(f.context.run,f.context.fixture_url,f.context.owner)
        elapsed=time.perf_counter()-began
        assert before_dom['source']['dom']['editor']['text']==''
        assert current_doc['source']['dom']['editor']['text']==text and current_doc['source']['dom']['editor']['focused'] is True
        assert current_doc['commandId']!=before_dom['commandId']
        assert current_doc['source']['dom']['requestId']==current_doc['commandId']==r.node.last['commandId']
        assert current_doc['source']['dom']['instance']==before_dom['source']['dom']['instance']==f.context.dom
        assert current_doc['source']['dom']['sequence']>before_dom['source']['dom']['sequence']
        assert current_doc['source']['originalFinish']==before_dom['source']['originalFinish']
        assert r.node.pid!=os.getpid() and r.node.process.poll() is None and len(r.node.rows)==4
        assert all(row['confirmed'] and row['owner'].raw for row in r.node.rows)
        assert [row['call']['operation'] for row in r.node.rows]==['init','snapshot','ime','snapshot']
        assert r.event_model.node_effect['issued'] is True
        assert [event['type'] for event in r.event_model.node_effect['inputEvents']]==['beforeinput','input']
        # All assertions are outside SourceLock normalization.
        assert r.lock._owner is None and r.failure is None
        assert r.compound['done'] and r.compound['work']==65536 and r.compound['entries_closed'] is True
        assert r.event_active is None and not r.event_parse and r.warm_work==0
        assert ime.issued and not ime.failed and not reader.failed
        assert delivery['source']['dispatch']['issued'] and delivery['source']['dispatch']['acceptedQt']
        assert len(r.event_rows)==6 and r.raw.state['reads']==18 and len(r.post_documents)==1 and not r.raw.state['pending']
        assert r.event_model.issued and len(r.event_model.frames)==4
        assert r.event_model.event.commit==text and r.event_model.event.replacement_start==0 and r.event_model.event.replacement_length==0
        assert reader.cursor==4 and observed['source']['availableFrames']==4
        assert r.closed_event_calls==6 and r.event_credit==32768
        assert set(reader.events[r.event_model.event.event_id])=={'native-input','jni-command','java-entry','java-consume'}
        frame=next(v['source']['frame'] for v in observed_rows if v['source']['frame']['kind']=='native-input');event=reader.events[frame['eventId']]['native-input'][1]
        assert frame['kind']=='native-input' and frame['origin']=='qt-ime'
        assert bytes.fromhex(event['commitUtf16Hex']).decode('utf-16-be')==text
        assert frame['eventId']==r.event_model.event.event_id
        assert delivery['focusNonce']==focus['commandId']==arm['source']['focusReference']['commandId']
        assert observed['source']['attemptReference']['nonce']==arm['commandId']
        assert delivery['source']['originalFinish']==focus['source']['originalFinish']
        assert delivery['source']['originalFinish']['finishedEpochMs']==r.model.finished_epoch
        assert delivery['source']['originalFinish']['grant']==1 and observed['source']['nativeAfter']['native']['grant']==2
        refs=[]
        for row in (r.completed[0],r.focus_call,*r.event_rows,*r.post_documents):
            literal=r.raw.literal(row['raw_ref'])
            assert literal is not None and literal==row['raw']
            assert hashlib.sha256(literal.encode()).hexdigest()==row['raw_ref']['sha256']
            refs.append(row['raw_ref'])
        r.intent.guard();assert r.intent.file is not None
        final=r.census();assert final['decodedBytes']<=16777216 and final['storedBytes']<=16777216
        assert f.adapter.sdk_calls==f.adapter.inputs==0 and f.parent.state is f.parent.disk is f.parent.vm is f.parent.history is None
        report=dict(case='normal_cold_product_dom_current',elapsed=elapsed,actualColdParent=True,actualProductEditorJs=True,actualAliveHostDomWorker=True,
            domChildPid=r.node.pid,actualDomQueries=len(r.node.rows),actualOriginalNodeLiteralFiles=len(r.node.rows),
            newCurrentDocumentNonce=current_doc['commandId'],postDomOriginal=r.post_documents[0]['raw_ref'],
            nodeQueryNonce=r.node.last['commandId'],hostModeledDocumentEffect=True,actualChromiumDom=False,
            actualOriginalDocumentFocusAndConsumption=True,actualNewImeReader=True,
            producer='DECLARED_HOST_MODEL',actualRawReceipts=r.raw.state['reads'],rawRefs=refs,
            modelFocusQueries=r.model.sequence,eventTraceQueries=r.event_model.sequence,
            actualIntentFile=str(r.intent.path),actualIntentSha256=hashlib.sha256(r.intent.raw).hexdigest(),
            issuedOnce=True,observedTraceFrames=4,producedModeledFrames=4,unicodeText=text,
            unchangedOriginalFinish=delivery['source']['originalFinish'],globalBill=final,
            compoundPostReturnWork=r.compound['work'],eventCredit=r.event_credit,
            closedOriginalEntryCopyWork=r.compound['entry']+sum(v['entry'] for v in r.completed)+r.focus_call['entry'],
            completedOriginalCallHandbacks=r.closed_event_calls,warmOriginalsRetained=len(r.warm_originals),realSDKCalls=0,realProductInputs=0,
            qtJniJavaQualified=False,nativeDeviceQualified=False,independentDomEffect=False,
            normalPointerFocusQualified=False,parentRetirementQualified=False,wholeClaim=False,
            storageQualification='EXPLICIT_TMPFS_HOST_LOGIC_ONLY')
    except BaseException as error:
        business=error;f.failure=(error,error.__traceback__)
        if f.resources is not None:f.resources.fail(error)
        raise
    finally:
        try:report['knownHostCloses']=f.close()
        except BaseException:
            if business is None:raise
    assert all(report['knownHostCloses'])
    return report


"""Fresh ordinary Host DOM data/source faults, no code/finalizer alteration."""
import base64,gc,hashlib,time
from adapters.normal_ui import NativeUIError


TEXT='Grüße 🌍 漢字'

def prefix(f):
 f.construct();f.factory();r=f.resources;focus=f.read();ime,reader=r.create_ime_sources()
 arm=reader.arm();delivery=ime.commit(TEXT);packets=[]
 for cursor in range(4):packets.append(reader.observe(cursor))
 assert reader.cursor==4 and r.closed_event_calls==6 and not r.raw.state['pending']
 assert {p['source']['frame']['kind'] for p in packets}=={'native-input','jni-command','java-entry','java-consume'}
 # Original correlator, not a new global Qt-native-vs-Android queue ordering.
 assert packets[0]['source']['frame']['kind']=='jni-command'
 return r,focus,delivery,reader

def dom_beforeinput_no_effect(artifacts):
 f=Fixture(artifacts,cancel=True);report={};business=None
 try:
  r,focus,delivery,reader=prefix(f)
  actual=r.reader.read(f.context.run,f.context.fixture_url,f.context.owner)
  assert delivery['source']['dispatch']['issued'] is True and r.event_model.node_effect['issued'] is True
  events=r.event_model.node_effect['inputEvents'];assert [e['type'] for e in events]==['beforeinput']
  assert r.event_model.node_effect['editor']['text']=='' and actual['source']['dom']['editor']['text']==''
  assert actual['source']['dom']['editor']['text']!=TEXT
  assert actual['commandId']==r.node.last['commandId'] and r.node.process.poll() is None
  assert len(r.node.rows)==4 and r.raw.state['reads']==18 and not r.raw.state['pending']
  bill=r.census();assert bill['decodedBytes']<=16777216
  report=dict(case='dom_beforeinput_no_effect',actualProductEditorCalledOnce=True,
   actualCancelableBeforeInputRejected=True,actualInputEvent=False,currentOriginalDomText='',
   successQualified=False,noFalseEffect=True,actualNewDocNonce=actual['commandId'],rawReceipts=18,
   nodeOriginals=len(r.node.rows),globalBill=bill,qtNativeChromiumQualified=False,wholeClaim=False)
 except BaseException as error:
  business=error;f.failure=(error,error.__traceback__)
  if f.resources is not None:f.resources.fail(error)
  raise
 finally:
  try:report['knownHostCloses']=f.close()
  except BaseException:
   if business is None:raise
 assert all(report['knownHostCloses']);return report

def dom_source_child_exit(artifacts):
 f=Fixture(artifacts);report={};business=None
 try:
  r,focus,delivery,reader=prefix(f)
  before=r.raw.state['reads'];rows=len(r.node.rows);sequence=r.node.sequence
  with r.lock.held():r.node.guard()
  r.node.process.terminate();r.node.process.wait(timeout=2)  # GENUINE owned source loss.
  found=False;error_id=None
  try:r.reader.read(f.context.run,f.context.fixture_url,f.context.owner)
  except NativeUIError as error:found=True;error_id=id(error)
  gc.collect()
  assert found and r.failure is not None and id(r.failure[0])==error_id and r.failure[1] is not None
  assert r.raw.state['reads']==before==16 and len(r.node.rows)==rows==3 and r.node.sequence==sequence==3
  assert not r.post_documents and r.current is not None and r.current['request'] is None
  assert r.current['raw'] is None and r.post_work>=64*65536 and not r.raw.state['pending']
  refused=False
  try:r.reader.read(f.context.run,f.context.fixture_url,f.context.owner)
  except NativeUIError:refused=True
  assert refused and r.raw.state['reads']==before and len(r.node.rows)==rows
  assert id(r.failure[0])==error_id and r.node.process.poll() is not None
  originals=[]
  for row in r.node.rows:
   owner=row['owner'];owner.guard();assert base64.b64decode(row['payload']['rawBase64'])==row['raw']
   originals.append(dict(path=str(owner.path),sha256=hashlib.sha256(owner.raw).hexdigest()))
  report=dict(case='dom_source_child_exit',actualOwnedChildExit=True,firstOwnerTBHeldAfterTestRefsAndGC=True,
   originalError=trace(r.failure[0]),rawReceipts=before,newGetterOrRaw=0,newNodeRequest=0,
   noInputReplay=True,sourceOriginals=originals,fullPendingPostWork=r.post_work,
   currentDomQualified=False,qtNativeChromiumQualified=False,wholeClaim=False)
 except BaseException as error:
  business=error;f.failure=(error,error.__traceback__)
  if f.resources is not None:f.resources.fail(error)
  raise
 finally:
  try:report['knownHostCloses']=f.close()
  except BaseException:
   if business is None:raise
 assert all(report['knownHostCloses']);return report
