// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include "assets-geometry-resource-host.h"
#include <QBuffer>
#include <QDataStream>
#include <QThreadPool>
#include <QFile>
#include <QJsonDocument>
#include <QTest>
#include "assets-resource-data-host.h"
#include "GeometryResourceParserCore.inc"
#if !defined(ASSETS_ORIGINAL_MODEL_MATERIAL)
Q_LOGGING_CATEGORY(networking,"networking")
#include "GeometryResourceRequestOriginals.inc"
#include "AssetsResourceObserverOriginal.inc"
#endif
#include "GeometryResourceConstantsOriginals.inc"
#if defined(ASSETS_ORIGINAL_MODEL_CACHE)
#include "GeometryModelCacheOriginals.inc"
#else
#include "GeometryResourceExtrasOriginals.inc"
#endif

class ResourceOwnedGeometryReader final:public GeometryReader {
 inline static QPointer<Resource> _boundOwner;
 inline static std::weak_ptr<WorkerEvidence> _boundEvidence;
 inline static bool _attempted{false};
 std::shared_ptr<WorkerEvidence> _originals;
 QString _source;
 void record(const QString& phase){std::lock_guard<std::mutex> lock(_originals->mutex);_originals->history.append(QJsonObject{
  {"phase",phase},{"id",QString::number(reinterpret_cast<quintptr>(this),16)},{"resourceId",_source},{"autoDelete",autoDelete()},
  {"thread",QString::number(reinterpret_cast<quintptr>(QThread::currentThread()),16)},
  {"observedEpochMs",QDateTime::currentMSecsSinceEpoch()}});}
public:
 static void bind(Resource* original,const std::shared_ptr<WorkerEvidence>& evidence){
  if(_attempted || !original || original->thread()!=QThread::currentThread()){qFatal("Original geometry owner can be bound only once on its real thread");}
  _attempted=true;_boundOwner=original;_boundEvidence=evidence;
 }
 ResourceOwnedGeometryReader(const ModelLoader& loader,QWeakPointer<Resource>& resource,const QUrl& url,
        const GeometryMappingPair& mapping,const QByteArray& bytes,bool combineParts,const QString& mediaType):
    GeometryReader(loader,resource,url,mapping,bytes,combineParts,mediaType),_originals(_boundEvidence.lock()) {
  // The original handleReplyFinished self guard still owns this object here.
  // No observer acquires/retains an additional strong Resource reference.
  const auto original=resource.data();
  if(!_originals || !original || _boundOwner.data()!=original || original->thread()!=QThread::currentThread() || original->getURL()!=url){qFatal("GeometryReader birth lost its original owner binding");}
  _source=QString::number(reinterpret_cast<quintptr>(original),16);record("constructed");
 }
 void run()override{record("run-enter");GeometryReader::run();record("run-exit");}
 ~ResourceOwnedGeometryReader()override{record("destructor-enter");}
};

// The complete original method bodies remain byte-for-byte generated. Only
// the constructor spelling at the new-expression is compiled through the
// passive derived reader above; it executes the actual original base ctor/run.
#define GeometryReader ResourceOwnedGeometryReader
#include "GeometryResourceOriginals.inc"
#undef GeometryReader

#if defined(ASSETS_ORIGINAL_MODEL_MATERIAL)
#include "assets-model-material-observer.inc"
#endif

int main(int argc,char** argv){
 QCoreApplication app(argc,argv);if(argc!=3){return 2;}
#include "AssetsResourceDataRegistration.inc"
 QFile file(QString::fromLocal8Bit(argv[1]));if(!file.open(QIODevice::ReadOnly)){return 3;}
 const auto sourceRaw=file.readAll();const auto packet=QJsonDocument::fromJson(sourceRaw).object();const auto resources=packet.value("resources").toArray();
 if(resources.size()!=3){return 4;}
#if defined(ASSETS_ORIGINAL_MODEL_MATERIAL)
 return runAssetsMaterial(app,sourceRaw,resources,QString::fromLocal8Bit(argv[2]));
#else
 auto manager=QSharedPointer<ResourceManager>::create();DependencyManager::set(manager);
 for(const auto& entry:resources){const auto row=entry.toObject();const auto bytes=QByteArray::fromBase64(row.value("base64").toString().toLatin1());
  if(bytes.size()!=row.value("bytes").toInt() || QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex()!=row.value("sha256").toString().toLatin1()){return 5;}
  const QUrl url(row.value("url").toString());if(manager->originalBytes.contains(url)){return 6;}manager->originalBytes.insert(url,bytes);
 }
 auto registry=QSharedPointer<ModelFormatRegistry>::create();DependencyManager::set(registry);registry->addFormat(GLTFSerializer());
 auto stats=QSharedPointer<StatTracker>::create();DependencyManager::set(stats);
 auto observer=QSharedPointer<ResourceRequestObserver>::create();DependencyManager::set(observer);
 QJsonArray observerOriginals;
 QObject::connect(observer.data(),&ResourceRequestObserver::resourceRequestEvent,&app,[&](const QVariantMap& value){observerOriginals.append(QJsonObject::fromVariantMap(value));});
 const QUrl url(resources.first().toObject().value("url").toString());ModelLoader loader;
 QElapsedTimer budget;budget.start();
#if defined(ASSETS_ORIGINAL_MODEL_CACHE)
 ModelCache cache;
 const GeometryMappingPair mapping{QUrl("atp:/original-model/mapping.fst"),QVariantHash{{"picoOriginalMarker",true}}};
 const QUrl textureBase("atp:/original-model/textures/");
 GeometryResource::Pointer owner=cache.getGeometryResource(url,mapping,textureBase);
 QJsonArray cacheOriginals;
 const auto cacheState=[&](const QString& phase){QReadLocker lock(&cache._resourcesLock);int alive=0,entries=0;
  for(const auto& byUrl:cache._resources){for(const auto& weak:byUrl){++entries;if(!weak.isNull()){++alive;}}}
  return QJsonObject{{"phase",phase},{"entries",entries},{"alive",alive},{"totalBytes",double(cache._totalResourcesSize)},
   {"resourceId",owner ? QString::number(reinterpret_cast<quintptr>(owner.data()),16) : QString()},
   {"extraHash",owner ? QString::number(owner->getExtraHash()) : QString()},
   {"actualQtClass",QString::fromLatin1(cache.metaObject()->className())},
   {"observedEpochMs",QDateTime::currentMSecsSinceEpoch()}};};
 cacheOriginals.append(cacheState("acquired"));
 auto same=cache.getGeometryResource(url,mapping,textureBase);
 const bool sameOriginal=owner.data()==same.data();same.clear();cacheOriginals.append(cacheState("same-extra-acquired"));
 if(!sameOriginal || manager->requests.size()!=1){qFatal("Same original cache acquisition duplicated an owner or request");}
 const QPointer<GeometryResource> original=owner.data();
#else
 QSharedPointer<HostGeometryResource> owner(new HostGeometryResource(url,loader),&GeometryResource::deleter);
 owner->setSelf(owner);owner->setExtra(nullptr);
 const QPointer<HostGeometryResource> original=owner.data();
#endif
 const QString originalId=QString::number(reinterpret_cast<quintptr>(owner.data()),16);
 auto evidence=std::make_shared<WorkerEvidence>();ResourceOwnedGeometryReader::bind(owner.data(),evidence);
 QJsonArray ownerOriginals;QByteArray loadedOriginal;QPointer<ResourceRequest> mainRequest;
 const auto state=[&](const QString& phase){const auto object=original.data();return QJsonObject{
  {"phase",phase},{"id",originalId},{"alive",bool(object)},
  {"actualQtClass",object ? QJsonValue(QString::fromLatin1(object->metaObject()->className())) : QJsonValue()},
  {"ownerThread",object ? QJsonValue(object->thread()==QThread::currentThread()) : QJsonValue()},
  {"resourceLoaded",object ? QJsonValue(object->isLoaded()) : QJsonValue()},
  {"resourceFailed",object ? QJsonValue(object->isFailed()) : QJsonValue()},
  {"hfmPresent",object ? QJsonValue(object->isHFMModelLoaded()) : QJsonValue()},
  {"bytes",object ? QJsonValue(double(object->getBytes())) : QJsonValue()},
  {"requestAlive",!mainRequest.isNull()},{"observedEpochMs",QDateTime::currentMSecsSinceEpoch()}};};
#if defined(ASSETS_ORIGINAL_MODEL_CACHE)
 mainRequest=manager->requests.first();
#endif
 ownerOriginals.append(state("constructed"));bool completed=false,success=true;
 QObject::connect(owner.data(),&Resource::loaded,owner.data(),[&](const QByteArray& data){
#if defined(ASSETS_ORIGINAL_MODEL_CACHE)
 mainRequest=manager->requests.first();
#else
 mainRequest=owner->originalRequest();
#endif
 loadedOriginal=data;ownerOriginals.append(state("loaded-signal"));});
 QObject::connect(owner.data(),&Resource::finished,owner.data(),[&](bool value){success=value;completed=true;owner.clear();ownerOriginals.append(state("finished-external-reference-released"));});
#if defined(ASSETS_ORIGINAL_MODEL_CACHE)
 mainRequest=manager->requests.first();
#endif
 owner->ensureLoading();
 while((!completed || original) && budget.elapsed()<1500){QTest::qWait(1);}
 const bool withinBudget=budget.elapsed()<1500;
 const bool workerRetired=withinBudget && QThreadPool::globalInstance()->waitForDone(1500-int(budget.elapsed()));
 ownerOriginals.append(state("retired"));
#if defined(ASSETS_ORIGINAL_MODEL_CACHE)
 cacheOriginals.append(cacheState("retired"));
#endif
 if(!workerRetired){
  // Retain known owner/worker originals before refusal without racing any
  // still-running parser/transport arrays or inventing successful retirement.
  QJsonArray history;{std::lock_guard<std::mutex> lock(evidence->mutex);history=evidence->history;}
  QFile failed(QString::fromLocal8Bit(argv[2]));if(!failed.open(QIODevice::WriteOnly|QIODevice::NewOnly)){return 9;}
  failed.write(QJsonDocument(QJsonObject{{"geometryResourceHostEvidenceVersion",1},{"protocolValid",false},
   {"failure","worker-retirement-unconfirmed"},{"ownerOriginals",ownerOriginals},{"workerOriginals",history},
   {"sourcePacketSha256",QString::fromLatin1(QCryptographicHash::hash(sourceRaw,QCryptographicHash::Sha256).toHex())}}).toJson(QJsonDocument::Compact));return 7;
 }
 const bool protocolValid=budget.elapsed()<1500 && completed && !success && !original && !mainRequest;
 const auto worker=evidence->history;QJsonArray requestPresence;
 for(const auto& request:manager->requests){requestPresence.append(!request.isNull());}
 QJsonObject result{{"geometryResourceHostEvidenceVersion",1},
  {"sourcePacketSha256",QString::fromLatin1(QCryptographicHash::hash(sourceRaw,QCryptographicHash::Sha256).toHex())},
  {"parsedHandoff",parsedHandoff},{"loaderOriginals",loaderOriginals},{"workerOriginals",worker},
  {"ownerOriginals",ownerOriginals},{"resourceObserverOriginals",observerOriginals},
  {"transportOriginals",manager->transportOriginals},{"transportPresenceBeforeProcessExit",requestPresence},
  {"loadedOriginalSha256",QString::fromLatin1(QCryptographicHash::hash(loadedOriginal,QCryptographicHash::Sha256).toHex())},
  {"workerRetired",workerRetired},{"protocolValid",protocolValid},{"cacheCompletions",ResourceCache::completed},
  {"callerThread",QString::number(reinterpret_cast<quintptr>(QThread::currentThread()),16)},
  {"pending",stats->stats.value("PendingProcessing")},{"processing",stats->stats.value("Processing")},
  {"bakerProcessingQualified",false},{"rendererReadinessQualified",false},{"durationMs",double(budget.elapsed())}};
 QFile output(QString::fromLocal8Bit(argv[2]));if(!output.open(QIODevice::WriteOnly|QIODevice::NewOnly)){return 9;}
#if defined(ASSETS_ORIGINAL_MODEL_CACHE)
 result.insert("modelCacheHostEvidenceVersion",1);result.insert("cacheOriginals",cacheOriginals);
 result.insert("sameOriginal",sameOriginal);result.insert("mapping",QJsonObject::fromVariantHash(mapping.second));
 result.insert("mappingUrl",mapping.first.toString());result.insert("textureBaseUrl",textureBase.toString());
#endif
#if defined(ASSETS_ORIGINAL_MODEL_BAKER)
 result.insert("modelBakerHostEvidenceVersion",1);result.insert("bakerOriginals",bakerOriginals);
 result.insert("bakerHandoff",bakerHandoff);result.insert("bakerGraphAlive",!bakerGraphRoot.isNull());
 result.insert("bakerInputAlive",!bakerInput.expired());result.insert("bakerBuffersRemaining",int(gpu::Buffer::getBufferCPUCount()));
 result.insert("bakerProcessingQualified",!bakerHandoff.isEmpty());
#endif
 const auto encoded=QJsonDocument(result).toJson(QJsonDocument::Compact);if(output.write(encoded)!=encoded.size()){return 10;}return protocolValid ? 0 : 7;
#endif // existing pre-material native modes
}
