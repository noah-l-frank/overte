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
#include <QPointer>
#include <QObject>
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
    const Commands&getCommands()const{return commands;}
    const CommandOffsets&getCommandOffsets()const{return offsets;}
};
struct Stereo{bool enabled=true;bool isStereo()const{return enabled;}};
struct Backend{
    CAMERA_STRUCTS
    struct Frame{uint32_t index=4;uint64_t execution=19;Stereo stereo;bool observeCameras=true;}frame;
    static Backend*executing;static Backend*featureExecutingBackend(){return executing;}
    const Frame*featureFrame()const{return &frame;}
};Backend*Backend::executing=nullptr;
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
ORIGINALS
int main(int argc,char**argv){
    QCoreApplication app(argc,argv);GLBackend backend;
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
        pieces=dict(BATCH_ENUM=block(batch,'    enum Command'),
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
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt'+major+'Core'],text=True,env=env))
        with tempfile.TemporaryDirectory(prefix='native-executed-draw-cameras-') as directory:
            path=Path(directory);cpp=path/'test.cpp';cpp.write_text(harness)
            for technique in ('DOUBLED','INSTANCED'):
                binary=path/technique
                subprocess.run(['c++','-std=c++17','-fPIC','-UNDEBUG','-DOVERTE_E2E_FEATURE_TESTS=1',
                    '-DGPU_STEREO_DRAWCALL_'+technique,*(['-DGPU_STEREO_CAMERA_BUFFER'] if technique=='INSTANCED' else []),
                    '-I'+str(glm),str(cpp),'-o',str(binary),*extra,*flags],check=True,timeout=60,env=env)
                subprocess.run([str(binary)],check=True,timeout=10,env=env)


if __name__=='__main__':unittest.main()
