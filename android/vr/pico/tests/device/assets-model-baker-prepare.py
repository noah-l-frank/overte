"""Current original Baker/Task CPU graph in the existing ModelCache route.

One CPU unity translation reduces repeated header parsing without changing
product methods, splitting the compiler clock or loading historical binaries.
GPU backend submission, profiling publication, additional material maps and
Draco execution are explicit closed host boundaries.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
from test_assets_read_native import ROOT, HERE, original
from native_cpu_mesh_originals import CPU_SUPPORT_SOURCES,source_unit,mesh_fragment,buffer_fragment


def prepare(stage, environment, prefix):
    spec=importlib.util.spec_from_file_location('model_baker_cache_prepare',HERE/'assets-model-cache-prepare.py')
    cache=importlib.util.module_from_spec(spec);spec.loader.exec_module(cache)
    stage=Path(stage);command=cache.prepare(stage,environment,prefix)
    provenance={}
    def read(path):
        raw=(ROOT/path).read_bytes();provenance[path]=hashlib.sha256(raw).hexdigest();return raw.decode()
    def write(name,source):
        target=stage/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(source)
    for folder in ('libraries/model-baker/src/model-baker','libraries/task/src/task'):
        for path in sorted((ROOT/folder).glob('*.h')):
            write(Path(folder).name+'/'+path.name,read(str(path.relative_to(ROOT))))
    # The original ModelMath header assumes separate translation units and has
    # no inclusion guard. Preserve all its bytes behind one host-only guard in
    # this unity build; this does not alter an original product file or body.
    math_header=stage/'model-baker/ModelMath.h'
    math_header.write_text('#pragma once\n'+math_header.read_text())
    provenance['compiled-single-inclusion-ModelMath.h']=hashlib.sha256(math_header.read_bytes()).hexdigest()
    # Profiling publication is not measured by this fixture. JobConfig's actual
    # per-job std::chrono measurement remains in the unchanged original engine.
    profile_header=ROOT/'libraries/shared/src/Profile.h'
    read('libraries/shared/src/Profile.h')
    write('Profile.h','#pragma once\n#undef PROFILE_ASYNC_BEGIN\n#undef PROFILE_ASYNC_END\n#include "'+str(profile_header)+'"\n'+'''#undef PROFILE_ASYNC_BEGIN
#undef PROFILE_ASYNC_END
#define PROFILE_ASYNC_BEGIN(...)
#define PROFILE_ASYNC_END(...)
''')
    write('PerfStat.h','''#pragma once
class PerformanceTimer {public:explicit PerformanceTimer(const char*){}};
''')
    # Original declarations and repeated-message calls compile, but the shared
    # workstation logging facility is not used as geometry/worker evidence.
    write('LogHandler.h','''#pragma once
#include <QDebug>
class LogHandler {public:static LogHandler& getInstance(){static LogHandler value;return value;}int newRepeatedMessageID(){return 0;}};
#define HIFI_FCDEBUG_ID(category,id,...) qCDebug(category) << __VA_ARGS__
''')
    baker=read('libraries/model-baker/src/model-baker/Baker.cpp')
    write('AssetsOriginalBakerBody.inc',baker)
    write('AssetsOriginalBakerJoin.inc',(HERE/'assets-model-baker-observer.inc').read_text())
    # The complete original graph is unchanged. Observed derived run throws
    # only AFTER original graph processing, before unqualified materials.
    units=[]
    for name in ('ModelMath','CalculateMeshNormalsTask','CalculateMeshTangentsTask',
            'CalculateBlendshapeNormalsTask','CalculateBlendshapeTangentsTask','PrepareJointsTask',
            'ParseFlowDataTask','BuildGraphicsMeshTask','ModelBakerLogging'):
        text=read('libraries/model-baker/src/model-baker/'+name+'.cpp')
        write('model-baker/'+name+'.cpp',text);units.append('#include "model-baker/'+name+'.cpp"')
    for path in ('libraries/task/src/task/Task.cpp','libraries/task/src/task/Config.cpp',
            'libraries/shared/src/shared/JSONHelpers.cpp','libraries/shared/src/shared/QtHelpers.cpp',*CPU_SUPPORT_SOURCES):
        read(path);units.append(source_unit(path))
    units.append(mesh_fragment(read,write,provenance))
    profile=read('libraries/shared/src/Profile.cpp')
    base_ctor=original(profile,'ProfileDurationBase::ProfileDurationBase(')
    categories='\n'.join(next(line for line in profile.splitlines() if line.startswith('Q_LOGGING_CATEGORY('+name+','))
        for name in ('trace_app','trace_baker'))
    write('AssetsBakerProfileHost.inc',categories+'\n'+base_ctor+'''
// Explicit profiling-publication endpoint: original declarations/base storage,
// no shared tracing singleton. Original Task std::chrono stats remain actual.
ProfileDuration::ProfileDuration(const QLoggingCategory& category,const QString& name,uint32_t,uint64_t,const QVariantMap&):ProfileDurationBase(category,name){}
ProfileDuration::~ProfileDuration(){}
''')
    units.append('#include "AssetsBakerProfileHost.inc"')
    units.append(buffer_fragment(read,write,provenance))
    hfm=read('libraries/hfm/src/hfm/HFM.cpp')
    write('AssetsOriginalBakerHfm.inc',original(hfm,'void HFMModel::computeKdops('))
    units.append('#include "AssetsOriginalBakerHfm.inc"')
    glm=read('libraries/shared/src/GLMHelpers.cpp')
    vectors='\n'.join(line for line in glm.splitlines() if line.startswith('const vec3 Vectors::') and not line.startswith(('const vec3 Vectors::MAX','const vec3 Vectors::MIN')))
    write('AssetsOriginalBakerVectors.inc',vectors+'\n')
    units.append('#include "AssetsOriginalBakerVectors.inc"')
    stream=read('libraries/shared/src/StreamUtils.cpp')
    debug_quaternion=original(stream,'QDebug& operator<<(QDebug& dbg, const glm::quat& q)')
    write('AssetsOriginalBakerStream.inc',debug_quaternion+'\n')
    provenance['original-quaternion-debug-operator']=hashlib.sha256(debug_quaternion.encode()).hexdigest()
    units.append('#include "AssetsOriginalBakerStream.inc"')
    material=read('libraries/model-baker/src/model-baker/ParseMaterialMappingTask.cpp')
    draco=read('libraries/model-baker/src/model-baker/BuildDracoMeshTask.cpp')
    write('AssetsOriginalBakerClosedBranches.inc','''#include "model-baker/ParseMaterialMappingTask.h"
#include "model-baker/BuildDracoMeshTask.h"
void processMaterialMapping(MaterialMapping&,const QJsonObject&,const hifi::URL&){qFatal("Additional material-map acquisition is outside original PBR CPU qualification");}
'''+original(material,'void ParseMaterialMappingTask::run(')+'''
'''+original(draco,'void BuildDracoMeshTask::configure(')+'''
void BuildDracoMeshTask::run(const baker::BakeContextPointer&,const Input&,Output&){qFatal("The original disabled Draco job must not execute");}
''')
    units.append('#include "AssetsOriginalBakerClosedBranches.inc"')
    write('AssetsOriginalBakerCpu.cpp','#include <list>\n#include <algorithm>\n#include <iterator>\n#include <GeometryUtil.h>\n#include <Profile.h>\n'+'\n'.join(units)+'\n')
    moc_outputs=[]
    for name in ('task/Config','model-baker/PrepareJointsTask','model-baker/BuildDracoMeshTask'):
        target=stage/(name.replace('/','-')+'-moc.cpp')
        subprocess.run([str(prefix/'usr/lib64/qt5/bin/moc'),'-I'+str(stage),'-I'+str(ROOT/'libraries/shared/src'),
            str(stage/(name+'.h')),'-o',str(target)],check=True,timeout=20,env=environment)
        moc_outputs.append('#include "'+str(target)+'"')
    write('AssetsOriginalBakerMoc.cpp','\n'.join(moc_outputs)+'\n')
    for name in ('AssetsOriginalBuffer.inc','AssetsOriginalBakerHfm.inc','AssetsOriginalBakerVectors.inc','AssetsOriginalBakerStream.inc',
            'AssetsOriginalBakerClosedBranches.inc','AssetsOriginalBakerMesh.inc','AssetsBakerProfileHost.inc','AssetsOriginalBakerCpu.cpp','AssetsOriginalBakerMoc.cpp',
            'AssetsOriginalBakerBody.inc','AssetsOriginalBakerJoin.inc','Profile.h','PerfStat.h','LogHandler.h'):
        provenance['compiled-'+name]=hashlib.sha256((stage/name).read_bytes()).hexdigest()
    (stage/'model-baker-original-provenance.json').write_text(json.dumps(provenance,sort_keys=True))
    return [*command,'-I'+str(stage/'model-baker'),'-DASSETS_ORIGINAL_MODEL_BAKER',str(stage/'AssetsOriginalBakerCpu.cpp'),str(stage/'AssetsOriginalBakerMoc.cpp')]
