// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include "assets-geometry-parser-host.h"
#include <QCryptographicHash>
#include <QFile>
#include <QJsonDocument>
#include <QTest>
#include <hfm/HFM.h>
#include <hfm/ModelFormatRegistry.h>
#include <ModelLoader.h>
#include <GLTFSerializer.h>
#include <Finally.h>
#include <graphics/ShaderConstants.h>
#include <Transform.h>
Q_LOGGING_CATEGORY(modelnetworking,"modelnetworking")
Q_LOGGING_CATEGORY(modelformat,"modelformat")
// Complete original CPU implementations; unsupported GPU-opacity inspection
// aborts rather than manufacturing texture or renderer readiness.
#include "GeometryParserCpuOriginals.inc"
bool graphics::Material::resetOpacityMap()const {qFatal("GPU opacity is outside CPU parser qualification");return false;}
#include "GeometryParserOriginals.inc"
static QJsonObject parsedHandoff;
static QJsonArray loaderOriginals;
// The sole renamed compilation delegate contains the complete original load
// body. This wrapper only archives arguments/result/exception and rethrows;
// it cannot supply a model, retry a parser, or turn failure into success.
hfm::Model::Pointer ModelLoader::load(const hifi::ByteArray& data,const hifi::VariantHash& mapping,
        const hifi::URL& url,const std::string& mediaType)const {
 QJsonObject frame{{"url",url.toString()},{"bytes",data.size()},
  {"sha256",QString::fromLatin1(QCryptographicHash::hash(data,QCryptographicHash::Sha256).toHex())},
  {"mapping",QJsonObject::fromVariantHash(mapping)},{"webMediaType",QString::fromStdString(mediaType)},
  {"thread",QString::number(reinterpret_cast<quintptr>(QThread::currentThread()),16)},
  {"enteredEpochMs",QDateTime::currentMSecsSinceEpoch()}};
 try {
  const auto result=loadOriginal(data,mapping,url,mediaType);
  frame["returnedModel"]=bool(result);frame["meshes"]=result ? QJsonValue(result->meshes.size()) : QJsonValue();
  frame["joints"]=result ? QJsonValue(result->joints.size()) : QJsonValue();
  frame["returnedEpochMs"]=QDateTime::currentMSecsSinceEpoch();loaderOriginals.append(frame);return result;
 }catch(const std::exception& exception){
  frame["exception"]=QString::fromUtf8(exception.what());frame["returnedEpochMs"]=QDateTime::currentMSecsSinceEpoch();loaderOriginals.append(frame);throw;
 }catch(...){frame["exception"]="non-std exception";frame["returnedEpochMs"]=QDateTime::currentMSecsSinceEpoch();loaderOriginals.append(frame);throw;}
}
#include "GeometryParserMaterialMapping.inc"
#if defined(ASSETS_ORIGINAL_MODEL_BAKER)
#include "AssetsOriginalBakerJoin.inc"
#else
namespace baker {
class Baker {
public:
 Baker(const HFMModel::Pointer& model,const QVariantHash&,const QUrl&){
  if(!model || model->meshes.empty() || model->joints.empty()){qFatal("No parsed original HFM at Baker boundary");}
  QJsonArray meshes;
  for(const auto& mesh:model->meshes){
   QJsonArray vertices,indices;
   for(const auto& vertex:mesh.vertices){vertices.append(QJsonArray{vertex.x,vertex.y,vertex.z});}
   for(const auto& part:mesh.parts){for(const auto index:part.triangleIndices){indices.append(index);}}
   QJsonArray normals,texcoords;
   for(const auto& normal:mesh.normals){normals.append(QJsonArray{normal.x,normal.y,normal.z});}
   for(const auto& uv:mesh.texCoords){texcoords.append(QJsonArray{uv.x,uv.y});}
   meshes.append(QJsonObject{{"vertices",vertices},{"indices",indices},{"normals",normals},{"texcoords",texcoords},{"skinningDataValid",mesh.skinningDataValid},
    {"parts",mesh.parts.size()},{"graphicsMeshExists",bool(mesh._mesh)}});
  }
  QJsonArray textures;
  for(const auto& material:model->materials){textures.append(QJsonObject{{"name",material.albedoTexture.name},
   {"url",QString::fromUtf8(material.albedoTexture.filename)},{"embeddedBytes",material.albedoTexture.content.size()}});}
  parsedHandoff=QJsonObject{{"url",model->originalURL},{"meshes",meshes},{"joints",model->joints.size()},
   {"materials",model->materials.size()},{"textures",textures},{"errors",model->loadErrorCount},
   {"thread",QString::number(reinterpret_cast<quintptr>(QThread::currentThread()),16)},
   {"observedEpochMs",QDateTime::currentMSecsSinceEpoch()}};
 }
 void run(){throw QString("Host qualification stops before original Baker processing");}
 HFMModel::Pointer getHFMModel()const{qFatal("Baker did not run");return {};}
 MaterialMapping getMaterialMapping()const{qFatal("Baker did not run");return {};}
};
}
#endif
static const QString SCRIPT_FIELD="script";
bool gunzip(const QByteArray&,QByteArray&){qFatal("Compressed models are outside this parser join");return false;}
#if defined(ASSETS_ORIGINAL_MODEL_BAKER)
#undef PROFILE_RANGE_EX
#endif
#define PROFILE_RANGE_EX(...)
#include "GeometryReaderOriginals.inc"

struct WorkerEvidence {QJsonArray history;std::mutex mutex;};
class ObservedGeometryReader final:public GeometryReader {
 std::shared_ptr<WorkerEvidence> _evidence;
 void record(const QString& phase){std::lock_guard<std::mutex> lock(_evidence->mutex);_evidence->history.append(QJsonObject{
  {"phase",phase},{"id",QString::number(reinterpret_cast<quintptr>(this),16)},
  {"autoDelete",autoDelete()},
  {"thread",QString::number(reinterpret_cast<quintptr>(QThread::currentThread()),16)},
  {"observedEpochMs",QDateTime::currentMSecsSinceEpoch()}});}
public:
 ObservedGeometryReader(const ModelLoader& loader,QWeakPointer<Resource>& resource,const QUrl& url,
   const GeometryMappingPair& mapping,const QByteArray& bytes,std::shared_ptr<WorkerEvidence> evidence):
   GeometryReader(loader,resource,url,mapping,bytes,true,{}),_evidence(std::move(evidence)){record("constructed");}
 void run()override{record("run-enter");GeometryReader::run();record("run-exit");}
 ~ObservedGeometryReader()override{record("destructor-enter");}
};

int main(int argc,char** argv){
 QCoreApplication app(argc,argv);if(argc!=3){return 2;}
 QFile file(QString::fromLocal8Bit(argv[1]));if(!file.open(QIODevice::ReadOnly)){return 3;}
 const auto sourceRaw=file.readAll();const auto packet=QJsonDocument::fromJson(sourceRaw).object();const auto resources=packet.value("resources").toArray();
 if(resources.size()!=3){return 4;}
 auto manager=QSharedPointer<ResourceManager>::create();DependencyManager::set(manager);
 for(const auto& entry:resources){const auto row=entry.toObject();const auto bytes=QByteArray::fromBase64(row.value("base64").toString().toLatin1());
  if(bytes.size()!=row.value("bytes").toInt() || QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex()!=row.value("sha256").toString().toLatin1()){return 5;}
  const QUrl url(row.value("url").toString());if(manager->originalBytes.contains(url)){return 6;}manager->originalBytes.insert(url,bytes);
 }
 auto registry=QSharedPointer<ModelFormatRegistry>::create();DependencyManager::set(registry);registry->addFormat(GLTFSerializer());
 auto stats=QSharedPointer<StatTracker>::create();DependencyManager::set(stats);
 auto target=QSharedPointer<Resource>::create();QWeakPointer<Resource> weak=target;QPointer<Resource> original=target.data();
 const QUrl url(resources.first().toObject().value("url").toString());
 auto evidence=std::make_shared<WorkerEvidence>();ModelLoader loader;QElapsedTimer budget;budget.start();
 QThreadPool pool;pool.setMaxThreadCount(1);
 pool.start(new ObservedGeometryReader(loader,weak,url,{url.resolved(QUrl(".")),{}},manager->originalBytes.value(url),evidence));
 while(!target->completed && budget.elapsed()<1500){QTest::qWait(1);}
 const bool withinBudget=budget.elapsed()<1500;
 const bool workerRetired=withinBudget && pool.waitForDone(1500-int(budget.elapsed()));
 if(!workerRetired){
  // No reads of worker-owned parser/transport state while it can still mutate.
  QJsonArray history;{std::lock_guard<std::mutex> lock(evidence->mutex);history=evidence->history;}
  QFile failed(QString::fromLocal8Bit(argv[2]));if(!failed.open(QIODevice::WriteOnly|QIODevice::NewOnly)){return 9;}
  failed.write(QJsonDocument(QJsonObject{{"geometryParserHostEvidenceVersion",1},{"protocolValid",false},
   {"failure","worker-retirement-unconfirmed"},{"workerOriginals",history}}).toJson(QJsonDocument::Compact));return 7;
 }
 bool protocolValid=workerRetired && budget.elapsed()<1500 && target->completed && !target->success && target->completions==1;
 const QJsonObject receiverOriginal{{"completed",target->completed},{"success",target->success},{"completions",target->completions}};
 // Capture a refusal before interpreting it. No failed acquisition is replayed.
 // The original parser requestData does not delete its parentless request.
 // Keep the host transport objects alive until process exit. They belong to
 // the worker thread; deleting them from the caller would not prove original
 // request retirement and would add an unsafe cross-thread destruction.
 QJsonArray transport=manager->transportOriginals;bool transportAlive=true;
 for(const auto& request:manager->requests){transportAlive=transportAlive && !request.isNull();}
 const auto worker=evidence->history;target.clear();protocolValid=protocolValid && original.isNull();
 QJsonObject result{{"geometryParserHostEvidenceVersion",1},{"sourcePacketSha256",QString::fromLatin1(QCryptographicHash::hash(sourceRaw,QCryptographicHash::Sha256).toHex())},
  {"parsedHandoff",parsedHandoff},{"loaderOriginals",loaderOriginals},{"workerOriginals",worker},{"transportOriginals",transport},
  {"transportAliveBeforeProcessExit",transportAlive},{"transportRetirementQualified",false},{"hostReceiverDead",original.isNull()},
  {"hostReceiverOriginal",receiverOriginal},{"workerRetired",workerRetired},{"protocolValid",protocolValid},
  {"callerThread",QString::number(reinterpret_cast<quintptr>(QThread::currentThread()),16)},
  {"pending",stats->stats.value("PendingProcessing")},{"processing",stats->stats.value("Processing")},
  {"geometryReadinessQualified",false},{"rendererReadinessQualified",false},{"durationMs",double(budget.elapsed())}};
 QFile output(QString::fromLocal8Bit(argv[2]));if(!output.open(QIODevice::WriteOnly|QIODevice::NewOnly)){return 9;}
 const auto encoded=QJsonDocument(result).toJson(QJsonDocument::Compact);if(output.write(encoded)!=encoded.size()){return 10;}return protocolValid ? 0 : 7;
}
