"""Compile original draw loop, GLES indexed call and camera readers.

Qt/GLM are real. Batch storage, GL queries/calls and backend transform storage
are explicit seams: this does not create a GL context or qualify a GPU/device.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import os
import shlex
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[4]


def block(text, marker):
    start=text.index(marker);end=text.index('{',start)+1;depth=1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]


HARNESS=r'''
#include <QCoreApplication>
#include <QThread>
#include <QPointer>
#include <QObject>
#include <QVariantMap>
#include <QImage>
#include <QBuffer>
#include <QCryptographicHash>
#include <QElapsedTimer>
#include <QJsonDocument>
#include <QJsonObject>
#include <QHash>
#include <QMutex>
#include <QMutexLocker>
#include <QDateTime>
#include <QMap>
#include <QSet>
#include <QRegularExpression>
#include <QUuid>
#include <cmath>
#include <memory>
#include <glm/glm.hpp>
#include <cassert>
#include <functional>
#include <vector>
#include <cstdint>
using Mat4=glm::mat4;using Vec4=glm::vec4;using Vec4i=glm::ivec4;using ivec4=Vec4i;
using uint32=uint32_t;using GLenum=unsigned;using GLuint=unsigned;using GLint=int;using GLint64=int64_t;using GLvoid=void;
constexpr unsigned GL_UNIFORM_BUFFER_BINDING=1,GL_UNIFORM_BUFFER_START=2,GL_UNIFORM_BUFFER_SIZE=3,GL_VIEWPORT=4;
namespace slot{namespace buffer{namespace Buffer{constexpr int CameraTransform=0;}}}
namespace gl{constexpr GLenum PRIMITIVE_TO_GL[]={0},ELEMENT_TYPE_TO_GL[]={0};}
enum Primitive{TRIANGLES};constexpr int TYPE_SIZE[]={4};
constexpr size_t INVALID_OFFSET=size_t(-1);
QObject share,otherShare;
struct QOpenGLContext{static QOpenGLContext* currentContext(){static QOpenGLContext c;return present?&c:nullptr;}
    QObject*shareGroup(){return group;}static bool present;static QObject*group;};
bool QOpenGLContext::present=true;QObject*QOpenGLContext::group=&share;
int bound=7;int64_t start=0,boundSize=0;Vec4i viewport(0,0,8,6);int glCalls=0;
bool wrongBinding=false,missingEye=false;int bindingReads=0;
void glGetIntegeri_v(unsigned,int,GLint*v){*v=(wrongBinding||(missingEye&&bindingReads++%2))?99:bound;}
void glGetInteger64i_v(unsigned what,int,GLint64*v){*v=what==GL_UNIFORM_BUFFER_START?start:boundSize;}
void glGetIntegerv(unsigned,GLint*v){for(int i=0;i<4;++i)v[i]=viewport[i];}
void glViewport(int x,int y,int w,int h){viewport={x,y,w,h};}
void glVertexAttribI1i(int,int){}
void glDrawElements(GLenum,uint32,GLenum,GLvoid*){++glCalls;}
void glDrawElementsInstanced(GLenum,uint32,GLenum,GLvoid*,int instances){glCalls+=instances;}
#define CHECK_GL_ERROR() 0
struct Batch{
    BATCH_ENUM;
    using Commands=std::vector<Command>;using CommandOffsets=std::vector<size_t>;
    struct Param{uint32 _uint;};std::vector<Param>_params{{0},{6},{0}};
    Commands commands;CommandOffsets offsets;std::function<void()>lambda;
    void drawIndexed(Primitive,unsigned,unsigned){commands.push_back(COMMAND_drawIndexed);offsets.push_back(0);}
    void runLambda(std::function<void()>fn){commands.push_back(COMMAND_runLambda);offsets.push_back(0);lambda=fn;}
    const Commands&getCommands()const{return commands;}
    const CommandOffsets&getCommandOffsets()const{return offsets;}
};
using TexturePointer=std::shared_ptr<int>;using FramebufferPointer=std::shared_ptr<int>;using Vec2i=glm::ivec2;
struct Stereo{bool enabled=true;Mat4 _eyeProjections[2]{Mat4(1),Mat4(1)},_eyeViews[2]{Mat4(1),Mat4(1)};bool isStereo()const{return enabled;}};
struct Backend{
    CAMERA_STRUCTS
    virtual bool featureTextureExtent(const TexturePointer&,Vec2i&extent){extent={8,6};return true;}
    virtual bool featureReadFramebuffer(const FramebufferPointer&,QImage&image){image=QImage(8,6,QImage::Format_RGBA8888);image.fill(Qt::red);return true;}
    virtual bool featureExecutedBatchCameras(const Batch*,FeatureBatchCameras&)const{return false;}
    virtual bool featureExecutedDrawCameras(const Batch*,size_t,FeatureBatchCameras&)const{return false;}
    struct Frame{uint32_t index=4;uint64_t execution=19;Stereo stereo;bool observeCameras=true;}frame;
    static Backend*executing;static Backend*featureExecutingBackend(){return executing;}
    const Frame*featureFrame()const{return &frame;}
};Backend*Backend::executing=nullptr;
TRACE_CLASS
struct GLBackend:Backend{
    bool featureExecutedBatchCameras(const Batch*,FeatureBatchCameras&)const;
    bool featureExecutedDrawCameras(const Batch*,size_t,FeatureBatchCameras&)const;
    void featureObserveCamera(int);void renderPassDraw(const Batch&);void setupStereoSide(int);
    void do_drawIndexed(const Batch&,size_t);
    using CommandCall=void(GLBackend::*)(const Batch&,size_t);
    CommandCall _commandCalls[Batch::NUM_COMMANDS];
    struct Camera{Mat4 _view{1},_projection{1};Vec4 _viewport{0,0,8,6},_stereoInfo{1,0,.125f,1.f/6};};
    struct TransformStageState{
#ifdef GPU_STEREO_CAMERA_BUFFER
        struct CameraBufferElement{Camera _cams[2];};
#else
        using CameraBufferElement=Camera;
#endif
        std::vector<CameraBufferElement>_cameras;
        std::vector<int>_cameraOffsets;
        std::vector<int>::iterator _camerasItr;
        size_t _cameraUboSize=sizeof(CameraBufferElement),_currentCameraOffset=0;
        unsigned _cameraBuffer=7;Vec4i _viewport{0,0,8,6};
        void bindCurrentCamera(int eye){start=_currentCameraOffset+eye*_cameraUboSize;}
    }_transform;
    struct{int _indexBufferType=0;size_t _indexBufferOffset=0;}_input;
    struct{int _DSNumTriangles=0,_DSNumDrawcalls=0,_DSNumAPIDrawcalls=0;}_stats;
    Stereo _stereo;int _currentDraw=-1;size_t _commandIndex=0;
    CAMERA_MEMBERS
    bool isStereo()const{return _stereo.isStereo();}
    void updateInput(){}void updatePipeline(){}void updateTransform(const Batch&){start=0;}
    void noOp(const Batch&,size_t){}
    void run(const Batch&b,size_t){Backend::executing=this;b.lambda();Backend::executing=nullptr;}
    GLBackend(){for(auto&f:_commandCalls)f=&GLBackend::noOp;
        _commandCalls[Batch::COMMAND_drawIndexed]=&GLBackend::do_drawIndexed;
        _commandCalls[Batch::COMMAND_runLambda]=&GLBackend::run;
        _transform._cameras.resize(2);
#ifdef GPU_STEREO_CAMERA_BUFFER
        _transform._cameras[0]._cams[1]._view[3][0]=.064f;
#else
        _transform._cameras[1]._view[3][0]=.064f;
#endif
        boundSize=sizeof(TransformStageState::CameraBufferElement);_featureCameraShareGroup=&share;}
    void begin(const Batch&batch){
        RENDER_BEGIN
    }
    void end(const Batch&batch){
        RENDER_END
    }
};
struct TestContext{std::shared_ptr<gpu::FeatureWorldRender>state;auto featureWorldRender(){return state;}};
class TestApp:public QCoreApplication{public:using QCoreApplication::QCoreApplication;
    std::shared_ptr<TestContext>context;auto getGPUContext(){return context;}};
#undef qApp
#define qApp static_cast<TestApp*>(QCoreApplication::instance())
struct Lifecycle{bool active=true;QVariantMap snapshot(){return active?QVariantMap{{"original",true}}:QVariantMap{};}};
class TestScriptingInterface:public QObject{public:
    QVariantMap featurePicoWorldModelDrawsObservation(const QVariantMap&);
    QString _testResultsLocation{"private-results"};std::shared_ptr<Lifecycle>_featureLifecycle{new Lifecycle};
};
TSI_GETTER
struct LoadedGeometry{struct HFM{QString originalURL{"file:///actual-original-avatar.fbx"};}hfm;
    const HFM&getHFMModel()const{return hfm;}QString e2eGeometryInstance()const{return QString(32,'b');}};
struct LoadedModel{std::shared_ptr<LoadedGeometry>geometry{new LoadedGeometry};auto getGeometry(){return geometry;}
    QString e2eModelInstance()const{return QString(32,'a');}};
struct RenderArgs{static constexpr int DEFAULT_RENDER_MODE=0;int _renderMode=0;size_t _mirrorDepth=0;bool stereo=true;
    std::shared_ptr<gpu::FeatureRenderTrace>_featureRenderTrace;Batch*_batch;bool isStereo()const{return stereo;}};
struct ModelMeshPartPayload{
    struct Mesh{};std::shared_ptr<const Mesh>_drawMesh{new Mesh};std::weak_ptr<const Mesh>_e2eOriginalDrawMesh;
    QVariantMap _e2eOriginalModel;bool _clusterPaletteValid=true;
    struct{int _numIndices=6,_startIndex=0;}_drawPart;
    struct Bound{glm::vec3 getMinimum()const{return {-1,0,-3};}glm::vec3 getMaximum()const{return {1,2,-1};}};
    Bound getBound(RenderArgs*){return {};}
    void drawCall(Batch&)const;
    void capture(LoadedModel*model){PAYLOAD_IDENTITY _e2eOriginalDrawMesh=_drawMesh;}
    void record(RenderArgs*args){auto&batch=*args->_batch;int drawcallInfo=2;PAYLOAD_RECORD}
};
PAYLOAD_DRAW
ORIGINALS
int main(int argc,char**argv){
    TestApp app(argc,argv);GLBackend backend;
    Batch batch;batch.commands={Batch::COMMAND_drawIndexed,Batch::COMMAND_runLambda};batch.offsets={0,0};
    Backend::FeatureBatchCameras output;int observations=0;
    batch.lambda=[&]{assert(backend.featureExecutedDrawCameras(&batch,0,output));++observations;};
    backend.begin(batch);assert(!backend.featureExecutedDrawCameras(&batch,0,output));backend.renderPassDraw(batch);
    assert(observations==1&&glCalls==2&&output.complete&&output.rawDraws==1&&output.executedDraws==1);
    assert(output.sequence==1&&output.frame==4&&output.execution==19&&output.cameras.size()==2);
    assert(output.cameras[0].eye==0&&output.cameras[1].eye==1&&output.cameras[0].draws==1);
    assert(output.cameras[1].view[3][0]==.064f);
    assert(!backend.featureExecutedDrawCameras(&batch,0,output)); // no executing lambda
    Backend::executing=&backend;assert(!backend.featureExecutedDrawCameras(&batch,1,output));
    Batch foreign=batch;assert(!backend.featureExecutedDrawCameras(&foreign,0,output));Backend::executing=nullptr;
    for(int fault=0;fault<8;++fault){
        backend.begin(batch);batch.lambda=[&]{
            if(fault==0)++backend.frame.execution;
            if(fault==1)++backend.frame.index;
            if(fault==2)backend.frame.stereo.enabled=false;
            if(fault==3)backend.frame.observeCameras=false;
            assert(!backend.featureExecutedDrawCameras(&batch,0,output));
        };
        if(fault==4)wrongBinding=true;
        if(fault==5)QOpenGLContext::group=&otherShare;
        if(fault==6)QOpenGLContext::present=false;
        if(fault==7){missingEye=true;bindingReads=0;}
        backend.renderPassDraw(batch);
        backend.frame=Backend::Frame();wrongBinding=missingEye=false;QOpenGLContext::group=&share;QOpenGLContext::present=true;
    }
    backend.end(batch);assert(!backend.featureExecutedDrawCameras(&batch,0,output));
    // An intervening command or a different draw cannot supply this source.
    batch.commands={Batch::COMMAND_drawIndexed,Batch::COMMAND_setInputFormat,Batch::COMMAND_runLambda};batch.offsets={0,0,0};
    backend.begin(batch);batch.lambda=[&]{assert(!backend.featureExecutedDrawCameras(&batch,0,output));};backend.renderPassDraw(batch);
    batch.commands={Batch::COMMAND_drawIndexed,Batch::COMMAND_draw,Batch::COMMAND_runLambda};
    backend.begin(batch);backend.renderPassDraw(batch);
    // Compile and execute the entire original trace, joining the actual
    // per-draw readings to the completed original batch. No model selector is
    // supplied to native acquisition or used to fabricate either camera.
    auto original=QVariantMap{{"modelInstance",QString(32,'a')},{"geometryInstance",QString(32,'b')},
        {"loadedSourcePresent",true},{"loadedSourceSha256",QString(64,'c')},
        {"minimum",QVariantList{-1.,0.,-1.}},{"maximum",QVariantList{1.,2.,1.}},
        {"indices",qulonglong(6)},{"skinned",true},{"blendshaped",false},{"originalGeometry",true}};
    for(int fault=0;fault<8;++fault){
        gpu::FeatureRenderTrace trace({});Backend::executing=&backend;trace.begin(&backend);Backend::executing=nullptr;
        batch.commands={Batch::COMMAND_drawIndexed,Batch::COMMAND_runLambda};batch.offsets={0,0};
        backend.begin(batch);batch.lambda=[&]{
            auto payload=original;if(fault==1)payload.insert("modelInstance","foreign");
            trace.model(&backend,&batch,0,payload);
            if(fault==2)trace.model(&backend,&batch,0,payload);
            assert(trace.modelSnapshot(&backend).isEmpty());
        };
        backend.renderPassDraw(batch);backend.end(batch);Backend::executing=&backend;
        if(fault==3)backend._featureCompletedCameras.cameras[0].view[3][0]=100;
        if(fault==4)backend._featureCompletedCameras.sequence+=1;
        if(fault==5)backend._featureCompletedCameras.cameras[1].draws=0;
        if(fault==6)backend._featureCompletedCameras.cameras.pop_back();
        trace.batch(&backend,&batch,fault==7,false);
        auto frame=trace.snapshot(&backend),model=trace.modelSnapshot(&backend);assert(!frame.isEmpty());
        if(fault){assert(model.isEmpty());}else{
            assert(model.value("picoModelTraceVersion")==1&&model.value("drawCommands")==qulonglong(1));
            assert(model.value("frameId")==frame.value("frameId")&&model.value("frameIndex")==frame.value("frameIndex"));
            const auto row=model.value("models").toList().first().toMap();
            assert(row.value("indices")==qulonglong(6)&&row.value("skinnedDrawCommands")==qulonglong(1));
            const auto uses=row.value("cameraUses").toList();assert(uses.size()==2);
            assert(uses[0].toMap().value("eye")=="left"&&uses[1].toMap().value("eye")=="right");
            assert(uses[0].toMap().value("batchSequence")==frame.value("cameraBatches").toList().first().toMap().value("sequence"));
        }
        Backend::executing=nullptr;
    }
    auto state=std::make_shared<gpu::FeatureWorldRender>();app.context=std::make_shared<TestContext>();app.context->state=state;
    TestScriptingInterface tsi;
    const QString capture(32,'e');const QVariantMap query{{"schemaVersion",1},{"commandId",QString(32,'f')},
        {"action","feature-pico-world-model-draws-observe"},{"captureRequestId",capture}};
    assert(tsi.featurePicoWorldModelDrawsObservation(query).isEmpty());assert(!state->request(capture).isEmpty());
    auto captureTrace=std::make_shared<gpu::FeatureRenderTrace>(QVariantMap{});
    auto ticket=state->reserve(captureTrace);assert(ticket);
    Backend::executing=&backend;captureTrace->begin(&backend);Backend::executing=nullptr;
    batch.commands={Batch::COMMAND_drawIndexed,Batch::COMMAND_runLambda};batch.offsets={0,0};
    LoadedModel loaded;ModelMeshPartPayload payload;payload.capture(&loaded);
    assert(payload._e2eOriginalModel.value("geometryInstance")==QString(32,'b'));
    assert(payload._e2eOriginalModel.value("loadedSourceSha256")==QString::fromLatin1(QCryptographicHash::hash(
        loaded.geometry->hfm.originalURL.toUtf8(),QCryptographicHash::Sha256).toHex()));
    batch.commands.clear();batch.offsets.clear();RenderArgs args;args._featureRenderTrace=captureTrace;args._batch=&batch;
    payload.drawCall(batch);payload.record(&args);assert(batch.commands.size()==2);
    backend.begin(batch);
    backend.renderPassDraw(batch);backend.end(batch);Backend::executing=&backend;captureTrace->batch(&backend,&batch,false,false);
    ticket->execute(&backend,{}, {},Vec4i(0,0,8,6),true,Mat4(1),captureTrace);Backend::executing=nullptr;
    assert(state->modelObservation(query).isEmpty()); // GPU acquisition is not submission.
    state->submitted(backend.frame.index+1,QVariantList{QVariantMap{},QVariantMap{}});
    assert(state->modelObservation(query).isEmpty());
    state->submitted(backend.frame.index,QVariantList{QVariantMap{},QVariantMap{}});
    const auto captured=state->request(capture),models=tsi.featurePicoWorldModelDrawsObservation(query);assert(!models.isEmpty());
    const auto modelSource=models.value("source").toMap(),pixelSource=captured.value("source").toMap();
    assert(modelSource.value("captureSequence")==captured.value("sequence"));
    assert(modelSource.value("pixelSha256")==pixelSource.value("image").toMap().value("pixelSha256"));
    assert(modelSource.value("captureCapturedEpochMs")==pixelSource.value("capturedEpochMs"));
    tsi._testResultsLocation.clear();assert(tsi.featurePicoWorldModelDrawsObservation(query).isEmpty());tsi._testResultsLocation="private-results";
    tsi._featureLifecycle->active=false;assert(tsi.featurePicoWorldModelDrawsObservation(query).isEmpty());tsi._featureLifecycle->active=true;
    auto context=app.context;app.context.reset();assert(tsi.featurePicoWorldModelDrawsObservation(query).isEmpty());app.context=context;
    auto malformed=query;malformed.insert("expectedModel",QString(32,'a'));assert(state->modelObservation(malformed).isEmpty());
    malformed=query;malformed.insert("captureRequestId",QString(32,'0'));assert(state->modelObservation(malformed).isEmpty());
    assert(!state->storage({{"schemaVersion",1},{"commandId",QString(32,'1')},{"action","feature-world-render-storage"},
        {"requestId",capture},{"operation","release"}}).isEmpty());
    assert(state->modelObservation(query).isEmpty());ticket.reset();
    // Missing model provenance cannot change an otherwise original successful
    // Graphics image into a failed capture or lend it another model's table.
    auto unavailable=std::make_shared<gpu::FeatureWorldRender>();const QString noModelCapture(32,'2');
    unavailable->request(noModelCapture);auto noModelTrace=std::make_shared<gpu::FeatureRenderTrace>(QVariantMap{});
    auto noModelTicket=unavailable->reserve(noModelTrace);assert(noModelTicket);
    Backend::executing=&backend;noModelTrace->begin(&backend);Backend::executing=nullptr;
    backend.begin(batch);batch.lambda=[&]{auto invalid=original;invalid.insert("modelInstance","invalid");noModelTrace->model(&backend,&batch,0,invalid);};
    backend.renderPassDraw(batch);backend.end(batch);Backend::executing=&backend;noModelTrace->batch(&backend,&batch,false,false);
    noModelTicket->execute(&backend,{}, {},Vec4i(0,0,8,6),true,Mat4(1),noModelTrace);Backend::executing=nullptr;
    unavailable->submitted(backend.frame.index,QVariantList{QVariantMap{},QVariantMap{}});
    assert(unavailable->request(noModelCapture).value("source").toMap().value("available")==true);
    auto noModelQuery=query;noModelQuery.insert("captureRequestId",noModelCapture);assert(unavailable->modelObservation(noModelQuery).isEmpty());
    noModelTicket.reset();
    // A cancelled queued callback cannot recreate its retired capture/model
    // evidence; the original ticket still drains independently.
    auto cancelled=std::make_shared<gpu::FeatureWorldRender>();const QString cancelledId(32,'3');
    cancelled->request(cancelledId);auto cancelledTicket=cancelled->reserve();assert(cancelledTicket);
    cancelled->storage({{"schemaVersion",1},{"commandId",QString(32,'4')},{"action","feature-world-render-storage"},
        {"requestId",cancelledId},{"operation","release"}});
    Backend::executing=&backend;cancelledTicket->execute(&backend,{}, {},Vec4i(0,0,8,6),true,Mat4(1),captureTrace);Backend::executing=nullptr;
    cancelled->submitted(backend.frame.index,QVariantList{QVariantMap{},QVariantMap{}});cancelledTicket.reset();
    auto cancelledQuery=query;cancelledQuery.insert("captureRequestId",cancelledId);assert(cancelled->modelObservation(cancelledQuery).isEmpty());
    // A reused camera slot whose original bytes changed cannot borrow an old
    // aggregate row. The second real indexed command fails the source closed.
    batch.commands={Batch::COMMAND_drawIndexed,Batch::COMMAND_runLambda,Batch::COMMAND_drawIndexed,Batch::COMMAND_runLambda};
    batch.offsets={0,0,0,0};int received=0;
    backend.begin(batch);batch.lambda=[&]{if(++received==1){
        assert(backend.featureExecutedDrawCameras(&batch,0,output));
#ifdef GPU_STEREO_CAMERA_BUFFER
        backend._transform._cameras[0]._cams[0]._view[3][0]=1;
#else
        backend._transform._cameras[0]._view[3][0]=1;
#endif
    }else{assert(!backend.featureExecutedDrawCameras(&batch,2,output));}};
    backend.renderPassDraw(batch);assert(received==2);
    // A missing/repeated eye cannot be filled from any prior batch camera.
    batch.commands={Batch::COMMAND_drawIndexed,Batch::COMMAND_runLambda};batch.offsets={0,0};
    backend.begin(batch);backend._featureCameraDraw=true;backend.featureObserveCamera(0);backend.featureObserveCamera(0);
    backend._featureDrawCameras.complete=false;
    Backend::executing=&backend;assert(!backend.featureExecutedDrawCameras(&batch,0,output));Backend::executing=nullptr;
}
'''


class ExecutedDrawCameras(unittest.TestCase):
    def test_original_loop_gles_draw_and_bound_camera_getters(self):
        gl=(ROOT/'libraries/gpu-gl-common/src/gpu/gl/GLBackend.cpp').read_text()
        header=(ROOT/'libraries/gpu-gl-common/src/gpu/gl/GLBackend.h').read_text()
        backend=(ROOT/'libraries/gpu/src/gpu/Backend.h').read_text()
        batch=(ROOT/'libraries/gpu/src/gpu/Batch.h').read_text()
        gles=(ROOT/'libraries/gpu-gl/src/gpu/gles/GLESBackend.cpp').read_text()
        originals='\n'.join(block(gl,marker) for marker in (
            'void GLBackend::renderPassDraw(', 'bool GLBackend::featureExecutedBatchCameras(',
            'bool GLBackend::featureExecutedDrawCameras(', 'void GLBackend::featureObserveCamera('))
        originals+='\n'+block(gles,'void GLESBackend::do_drawIndexed(').replace('GLESBackend::','GLBackend::')
        # setupStereoSide is absent in the instanced build by original design.
        originals+='\n#ifdef GPU_STEREO_DRAWCALL_DOUBLED\n'+block(gl,'void GLBackend::setupStereoSide(')+'\n#endif\n'
        begin=gl[gl.index('    _featureWorkingCameras=FeatureBatchCameras();',gl.index('void GLBackend::render(')):]
        begin=begin[:begin.index('\n#endif\n\n    _transform')]
        end=gl[gl.index('    for (const auto command:batch.getCommands())',gl.index('void GLBackend::render(')):]
        end=end[:end.index('\n#endif')]
        trace=(ROOT/'libraries/gpu/src/gpu/FeatureRenderTrace.h').read_text()
        world=(ROOT/'libraries/gpu/src/gpu/FeatureWorldRender.h').read_text()
        payload=(ROOT/'libraries/render-utils/src/MeshPartPayload.cpp').read_text()
        identity=payload[payload.index('    // Reviewed shared identity fragment'):];identity=identity[:identity.index('\n#endif')]
        record=payload[payload.index('    // Original payload metadata follows'):];record=record[:record.index('\n#endif')]
        pieces=dict(TSI_GETTER=block((ROOT/'interface/src/scripting/TestScriptingInterface.cpp').read_text(),'QVariantMap TestScriptingInterface::featurePicoWorldModelDrawsObservation('),PAYLOAD_IDENTITY=identity,PAYLOAD_RECORD=record,PAYLOAD_DRAW=block(payload,'void ModelMeshPartPayload::drawCall(').replace('gpu::Batch','Batch'),TRACE_CLASS='namespace gpu { using Primitive=::Primitive;constexpr auto TRIANGLES=::TRIANGLES;using Backend=::Backend;using Batch=::Batch;using TexturePointer=::TexturePointer;using FramebufferPointer=::FramebufferPointer;'+block(trace,'class FeatureRenderTrace')+';'+block(world,'class FeatureWorldRender :')+';}\n',BATCH_ENUM=block(batch,'    enum Command'),
            CAMERA_STRUCTS=block(backend,'    struct FeatureCameraUniform')+';\n'+block(backend,'    struct FeatureBatchCameras')+';',
            CAMERA_MEMBERS=header[header.index('    QPointer<QObject> _featureCameraShareGroup;'):header.index('\npublic:\n#endif',header.index('    QPointer<QObject> _featureCameraShareGroup;'))],
            RENDER_BEGIN=begin,RENDER_END=end,ORIGINALS=originals)
        harness=HARNESS
        for key in sorted(pieces,key=len,reverse=True):harness=harness.replace(key,pieces[key])
        env=dict(os.environ);major=env.get('OVERTE_NATIVE_QT_MAJOR','6');self.assertIn(major,('5','6'));extra=[]
        if major=='5' and env.get('OVERTE_QT5_HOST_ROOT'):
            prefix=Path(env['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
            env.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),LD_LIBRARY_PATH=str(prefix/'usr/lib64'))
            extra=['-L'+str(prefix/'usr/lib64')]
        glm=Path(env['OVERTE_TEST_GLM_INCLUDE']).resolve(strict=True)
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt'+major+'Core','Qt'+major+'Gui'],text=True,env=env))
        with tempfile.TemporaryDirectory(prefix='native-executed-draw-cameras-') as directory:
            path=Path(directory);cpp=path/'test.cpp';cpp.write_text(harness)
            for technique in ('DOUBLED','INSTANCED'):
                binary=path/technique
                subprocess.run(['c++','-std=c++17','-fPIC','-UNDEBUG','-DOVERTE_E2E_FEATURE_TESTS=1',
                    '-DGPU_STEREO_DRAWCALL_'+technique,*(['-DGPU_STEREO_CAMERA_BUFFER'] if technique=='INSTANCED' else []),
                    '-I'+str(glm),str(cpp),'-o',str(binary),*extra,*flags],check=True,timeout=60,env=env)
                subprocess.run([str(binary),'--testScript'],check=True,timeout=10,env=env)


if __name__=='__main__':unittest.main()
