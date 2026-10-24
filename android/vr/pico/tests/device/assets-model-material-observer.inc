// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Independent weak originals in the EXISTING Assets native acquisition mode.
AssetsRecordedInput* assetsMaterialInput{nullptr};
namespace {
QMutex materialObservationMutex;
QList<AssetsMaterialRequestOriginal> materialRequests;
QJsonArray materialRequestBirths,materialRequestFinishes;
QList<AssetsMaterialOriginal> materialOwners;
QJsonArray materialOriginals,textureOriginals,pixelOriginals;
QString pointerId(const void* value){return QString::number(reinterpret_cast<quintptr>(value),16);}
class RecordedMaterialInputRequest final:public ResourceRequest {
 QByteArray bytes;
public:
 RecordedMaterialInputRequest(const QUrl& url,const QByteArray& value,bool observable,qint64 caller,const QString& extra):
  ResourceRequest(url,observable,caller,extra),bytes(value){}
private:
 void doSend()override{
  QTimer::singleShot(0,this,[this]{_data=bytes;_result=Success;_state=Finished;
   emit progress(_data.size(),_data.size());emit finished();});
 }
};
}
void observeAssetsMaterialRequest(ResourceRequest* request,QObject* owner,const QUrl& url){
 if(!request){qFatal("Original Assets request observer received no actual request");}
 const auto parent=request->parent();const auto gui=QCoreApplication::instance()->thread();
 const QVariantMap threads{{"factoryOnGui",QThread::currentThread()==gui},
  {"factoryOwnerOnGui",owner ? QVariant(owner->thread()==gui) : QVariant()},
  {"requestOnGui",request->thread()==gui},{"hasQObjectParent",parent!=nullptr},
  {"qObjectParentIsFactoryOwner",owner && parent==owner}};
 int index;
 {QMutexLocker lock(&materialObservationMutex);if(materialRequests.size()>=3){qFatal("Original input request inventory exhausted");}
  index=materialRequests.size();materialRequests.append({request,owner,parent,url.toString(),owner!=nullptr,threads,{}});
  materialRequestBirths.append(QJsonObject{{"instance",pointerId(request)},{"url",url.toString()},
   {"factoryOwner",owner ? QJsonValue(pointerId(owner)) : QJsonValue()},
   {"threads",QJsonObject::fromVariantMap(threads)},{"observedEpochMs",QDateTime::currentMSecsSinceEpoch()}});
 }
 QObject::connect(request,&ResourceRequest::finished,request,[request,index]{
  const auto instance=pointerId(request);const auto bytes=request->getData();const QVariantMap receipt{{"success",request->getResult()==ResourceRequest::Success},
   {"bytes",bytes.size()},{"sha256",QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex())},
   {"onRequestThread",QThread::currentThread()==request->thread()},{"observedEpochMs",QDateTime::currentMSecsSinceEpoch()}};
  QMetaObject::invokeMethod(QCoreApplication::instance(),[index,receipt,instance]{QMutexLocker lock(&materialObservationMutex);
   materialRequests[index].finished=receipt;
   materialRequestFinishes.append(QJsonObject{{"instance",instance},
    {"url",materialRequests[index].url},{"receipt",QJsonObject::fromVariantMap(receipt)}});
  },Qt::QueuedConnection);
 },Qt::DirectConnection);
}
ResourceRequest* assetsRecordedRequest(QObject* owner,const QUrl& url,bool observable,qint64 caller,const QString& extra){
 if(!assetsMaterialInput || url.scheme()!="atp" || !assetsMaterialInput->originalBytes.contains(url)){
  qFatal("An unsealed ATP input cannot enter the original material path");}
 const auto bytes=assetsMaterialInput->originalBytes.value(url);
 auto request=new RecordedMaterialInputRequest(url,bytes,observable,caller,extra);
 // Original Assets transport endpoint: lifetime connection is NOT a QObject
 // parent. In particular the original glTF mesh caller passes no owner.
 if(owner){QObject::connect(owner,&QObject::destroyed,request,&QObject::deleteLater);}
 {QMutexLocker lock(&assetsMaterialInput->mutex);assetsMaterialInput->requests.append(request);
  assetsMaterialInput->transportOriginals.append(QJsonObject{{"url",url.toString()},{"extra",extra},{"bytes",bytes.size()},
   {"sha256",QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex())},
   {"parented",owner!=nullptr},{"hasQObjectParent",request->parent()!=nullptr},
   {"thread",pointerId(QThread::currentThread())}});
 }
 observeAssetsMaterialRequest(request,owner,url);return request;
}
namespace {
void bindActualMaterials(GeometryResource* geometry){
 if(!geometry || QThread::currentThread()!=geometry->thread() || !materialOwners.isEmpty()){
  qFatal("One actual GUI Geometry publication is required");}
 const auto& originals=geometry->featureCreateMaterials();
 for(const auto& material:originals){
  if(!material){qFatal("Original geometry published a null material");}
  const auto textures=material->getTextures();
  for(const auto& entry:textures){if(!entry.second.texture){continue;}
   const auto texture=entry.second.texture;
   materialOwners.append({material,texture.toWeakRef(),texture.data(),{},geometry->e2eGeometryInstance(),
    pointerId(material.get()),pointerId(texture.data()),texture->getURL().toString(),entry.second.name,int(entry.first),false});
   materialOriginals.append(QJsonObject{{"phase","published"},{"geometry",geometry->e2eGeometryInstance()},
    {"material",pointerId(material.get())},{"channel",int(entry.first)},{"slot",entry.second.name},
    {"texture",pointerId(texture.data())},{"observedEpochMs",QDateTime::currentMSecsSinceEpoch()}});
  }
 }
}
bool actualPixelsLoaded(){
 if(materialOwners.isEmpty()){return false;}
 for(auto& original:materialOwners){auto texture=original.texture.toStrongRef();
  if(!texture || texture->thread()!=QThread::currentThread() || !texture->isLoaded() || texture->isFailed() || !texture->getGPUTexture()){
   return false;}
 }
 return true;
}
void recordActualPixels(const QString& phase){
 for(auto& original:materialOwners){auto texture=original.texture.toStrongRef();
  QJsonObject row{{"phase",phase},{"instance",original.textureId},{"material",original.materialId},
   {"alive",bool(texture)||!original.textureGuard.isNull()},{"url",original.url},{"slot",original.slot},
   {"channel",original.channel},{"observedEpochMs",QDateTime::currentMSecsSinceEpoch()}};
  if(texture){
   if(texture->thread()!=QThread::currentThread()){qFatal("A texture field was read away from its actual owner");}
   const auto pixels=texture->getGPUTexture();
   row.insert("loaded",texture->isLoaded());row.insert("failed",texture->isFailed());
   row.insert("width",texture->getWidth());row.insert("height",texture->getHeight());
   if(pixels){original.pixels=pixels;original.pixelsObserved=true;original.pixelId=pointerId(pixels.get());
    row.insert("storedBytes",double(pixels->getStoredSize()));row.insert("sourceHash",QString::fromStdString(pixels->sourceHash()));}
  }
  textureOriginals.append(row);
  if(original.pixelsObserved){pixelOriginals.append(QJsonObject{{"phase",phase},{"instance",original.pixelId},{"texture",original.textureId},
    {"alive",!original.pixels.expired()},{"observedEpochMs",QDateTime::currentMSecsSinceEpoch()}});}
  if(phase=="released"){materialOriginals.append(QJsonObject{{"phase",phase},{"material",original.materialId},
    {"alive",!original.material.expired()},{"observedEpochMs",QDateTime::currentMSecsSinceEpoch()}});}
 }
}
bool actualMaterialOwnersRetired(){
 for(const auto& original:materialOwners){if(!original.material.expired() || !original.texture.isNull() ||
    !original.textureGuard.isNull() || !original.pixels.expired()){return false;}}
 return true;
}
int runAssetsMaterial(QCoreApplication& app,const QByteArray& sourceRaw,const QJsonArray& resources,const QString& outputPath){
 for(const auto& key:{"XDG_CONFIG_HOME","XDG_CACHE_HOME","XDG_DATA_HOME"}){if(qgetenv(key).isEmpty()){
  qFatal("Original material Settings/cache require a new isolated profile");}}
 app.setOrganizationName("OverteAssetsMaterialPrivateHost");app.setApplicationName("original-material");
 QSettings::setDefaultFormat(JSON_FORMAT);DependencyManager::set<Setting::Manager>();
 auto manager=DependencyManager::set<ResourceManager>(false);
 AssetsRecordedInput inputs;assetsMaterialInput=&inputs;
 for(const auto& entry:resources){const auto row=entry.toObject();const auto bytes=QByteArray::fromBase64(row.value("base64").toString().toLatin1());
  if(bytes.size()!=row.value("bytes").toInt() || QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex()!=row.value("sha256").toString().toLatin1() ||
      inputs.originalBytes.contains(QUrl(row.value("url").toString()))){return 5;}
  inputs.originalBytes.insert(QUrl(row.value("url").toString()),bytes);
 }
 auto registry=DependencyManager::set<ModelFormatRegistry>();registry->addFormat(GLTFSerializer());
 auto stats=DependencyManager::set<StatTracker>();auto observer=DependencyManager::set<ResourceRequestObserver>();
 DependencyManager::set<ResourceCacheSharedItems>();DependencyManager::set<TextureCache>();
 QJsonArray observerRows;QObject::connect(observer.data(),&ResourceRequestObserver::resourceRequestEvent,&app,
  [&](const QVariantMap& row){observerRows.append(QJsonObject::fromVariantMap(row));});
 QElapsedTimer budget;budget.start();ModelCache cache;
 const GeometryMappingPair mapping{QUrl("atp:/original-model/mapping.fst"),QVariantHash{{"picoOriginalMarker",true}}};
 const QUrl textureBase("atp:/original-model/textures/");
 auto owner=cache.getGeometryResource(QUrl(resources.first().toObject().value("url").toString()),mapping,textureBase);
 auto same=cache.getGeometryResource(owner->getURL(),mapping,textureBase);const bool sameOriginal=owner.data()==same.data();same.clear();
 if(!sameOriginal || inputs.requests.size()!=1){qFatal("Same real extra duplicated an original owner/request");}
 const QPointer<GeometryResource> geometry=owner.data();const QString geometryId=pointerId(owner.data());
 auto evidence=std::make_shared<WorkerEvidence>();ResourceOwnedGeometryReader::bind(owner.data(),evidence);
 QJsonArray ownerRows,cacheRows;QByteArray loaded;bool completed=false,success=false;
 const auto cacheState=[&](const QString& phase){return QJsonObject{{"phase",phase},{"numTotal",double(cache.getNumTotalResources())},
  {"numCached",double(cache.getNumCachedResources())},{"unusedLimit",double(cache.getUnusedResourceCacheSize())},
  {"urls",QJsonArray::fromVariantList(cache.getResourceList())},{"observedEpochMs",QDateTime::currentMSecsSinceEpoch()}};};
 const auto state=[&](const QString& phase){const auto original=geometry.data();return QJsonObject{{"phase",phase},{"id",geometryId},
  {"alive",bool(original)},{"resourceLoaded",original ? QJsonValue(original->isLoaded()):QJsonValue()},
  {"resourceFailed",original ? QJsonValue(original->isFailed()):QJsonValue()},
  {"hfmPresent",original ? QJsonValue(original->isHFMModelLoaded()):QJsonValue()},
  {"actualQtClass",original ? QJsonValue(QString::fromLatin1(original->metaObject()->className())):QJsonValue()},
  {"ownerThread",original ? QJsonValue(original->thread()==QThread::currentThread()):QJsonValue()},
  {"bytes",original ? QJsonValue(double(original->getBytes())):QJsonValue()},
  {"observedEpochMs",QDateTime::currentMSecsSinceEpoch()}};};
 ownerRows.append(state("constructed"));cacheRows.append(cacheState("acquired"));
 QObject::connect(owner.data(),&Resource::loaded,owner.data(),[&](const QByteArray& bytes){loaded=bytes;ownerRows.append(state("loaded-signal"));});
 QObject::connect(owner.data(),&Resource::finished,owner.data(),[&](bool result){success=result;completed=true;
  ownerRows.append(state("geometry-callback"));if(result){bindActualMaterials(geometry.data());}});
 while(!completed && budget.elapsed()<1500){QTest::qWait(1);}
 bool workers=budget.elapsed()<1500 && QThreadPool::globalInstance()->waitForDone(1500-int(budget.elapsed()));
 while(success && !actualPixelsLoaded() && budget.elapsed()<1500){QTest::qWait(1);}
 workers=workers && budget.elapsed()<1500 && QThreadPool::globalInstance()->waitForDone(1500-int(budget.elapsed()));
 const bool decoded=success && actualPixelsLoaded();
 if(decoded){recordActualPixels("decoded");}
 owner.clear();ownerRows.append(state("external-reference-released"));
 while(!actualMaterialOwnersRetired() && budget.elapsed()<1500){QTest::qWait(1);}
 // Real default-LRU Geometry/HFM ownership is deliberately left untouched.
 QCoreApplication::sendPostedEvents(nullptr,QEvent::DeferredDelete);QCoreApplication::processEvents();
 recordActualPixels("released");ownerRows.append(state("after-release"));cacheRows.append(cacheState("after-release"));
 QJsonArray requestPresence;bool anyRequest=false;for(const auto& request:inputs.requests){requestPresence.append(!request.isNull());anyRequest=anyRequest || !request.isNull();}
 const bool indexed=!bakerHandoff.isEmpty();
 const bool protocol=budget.elapsed()<1500 && completed && workers && sameOriginal &&
  (indexed ? decoded && actualMaterialOwnersRetired() : !success && !geometry);
 QJsonObject result{{"geometryResourceHostEvidenceVersion",1},{"modelCacheHostEvidenceVersion",1},{"modelBakerHostEvidenceVersion",1},
  {"modelMaterialHostEvidenceVersion",2},{"protocolValid",protocol},{"workerRetired",workers},
  {"sourcePacketSha256",QString::fromLatin1(QCryptographicHash::hash(sourceRaw,QCryptographicHash::Sha256).toHex())},
  {"loadedOriginalSha256",QString::fromLatin1(QCryptographicHash::hash(loaded,QCryptographicHash::Sha256).toHex())},
  {"parsedHandoff",parsedHandoff},{"bakerHandoff",bakerHandoff},{"bakerOriginals",bakerOriginals},
  {"bakerGraphAlive",!bakerGraphRoot.isNull()},{"bakerInputAlive",!bakerInput.expired()},
  {"bakerBuffersRemaining",int(gpu::Buffer::getBufferCPUCount())},{"loaderOriginals",loaderOriginals},
  {"workerOriginals",evidence->history},{"ownerOriginals",ownerRows},{"cacheOriginals",cacheRows},
  {"mapping",QJsonObject::fromVariantHash(mapping.second)},{"mappingUrl",mapping.first.toString()},{"textureBaseUrl",textureBase.toString()},
  {"resourceObserverOriginals",observerRows},{"transportOriginals",inputs.transportOriginals},
  {"transportPresenceBeforeProcessExit",requestPresence},{"materialOriginals",materialOriginals},
  {"textureOriginals",textureOriginals},{"pixelOriginals",pixelOriginals},{"requestBirths",materialRequestBirths},
  {"requestFinishes",materialRequestFinishes},{"sameOriginal",sameOriginal},{"pending",stats->getStat("PendingProcessing").toInt()},
  {"processing",stats->getStat("Processing").toInt()},{"bakerProcessingQualified",indexed},
  {"materialProcessingQualified",decoded},{"rendererReadinessQualified",false},
  {"wholeResourceRetired",!geometry && bakerInput.expired() && !anyRequest && actualMaterialOwnersRetired()},{"durationMs",double(budget.elapsed())}};
 QFile output(outputPath);if(!output.open(QIODevice::WriteOnly|QIODevice::NewOnly)){return 9;}
 const auto encoded=QJsonDocument(result).toJson(QJsonDocument::Compact);if(output.write(encoded)!=encoded.size()){return 10;}
 return protocol ? 0:7;
}
}
