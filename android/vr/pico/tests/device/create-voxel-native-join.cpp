// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include "create-voxel-native-join.h"
#include <QCoreApplication>
#include <QEvent>
#include <QFile>
#include <QJsonDocument>
#include <QThread>
#include <thread>
#include <Profile.h>
#include "OriginalCreateVoxelStorage.inc"
Q_LOGGING_CATEGORY(entitiesrenderer,"overte.e2e.create.voxel.renderer")
Q_LOGGING_CATEGORY(entities,"overte.e2e.create.voxel.entities")
#include "OriginalCreateVoxelMethods.inc"
#include "OriginalCreateEntities.inc"
namespace render::entities {
#include "OriginalPolyvoxRenderUpdate.inc"
}
namespace {
NativeCreateVoxelJoin* activeTextureObserver{nullptr};
thread_local NativeCreateVoxelJoin* activeOriginalRender{nullptr};
glm::vec3 point(const QVariantMap& value){
 if(value.size()!=3 || !value.contains("x") || !value.contains("y") || !value.contains("z")){qFatal("Unknown native point fields");}
 const glm::vec3 result(value.value("x").toDouble(),value.value("y").toDouble(),value.value("z").toDouble());
 if(!std::isfinite(result.x)||!std::isfinite(result.y)||!std::isfinite(result.z)){qFatal("Nonfinite native point");}return result;
}
QVariantMap point(const glm::vec3& value){return {{"x",value.x},{"y",value.y},{"z",value.z}};}
}
// Explicit octree/property endpoints around unchanged insertion/getter bodies.
EntityItemPointer EntityTypes::constructEntityItem(EntityType type,const EntityItemID& id,const EntityItemProperties& properties){
 if(type!=PolyVox){qFatal("Only one owned PolyVox factory was admitted");}
 return RenderablePolyVoxEntityItem::factory(id,properties);
}
void EntityTree::recurseTreeWithOperator(AddEntityOperator* operation){
 if(!operation || operation->tree.get()!=this || !operation->entity || objects.contains(operation->entity->getID())){
  qFatal("Foreign or repeated host Octree insertion");}
 objects.insert(operation->entity->getID(),operation->entity);
}
void EntityTree::postAddEntity(const EntityItemPointer& value){value->tree=shared_from_this();}
void RenderablePolyVoxEntityItem::setProperties(const EntityItemProperties& value){
 if(value.type!=EntityTypes::PolyVox || value.host!=entity::HostType::DOMAIN || value.created!=UNKNOWN_CREATED_TIME){
  qFatal("Only the explicitly owned initial property fixture was admitted");}
 name=value.name;host=value.host;editedBy=value.lastEditedBy;position=value.position;dimensions=value.dimensions;orientation=value.rotation;
 _locked=value.locked;visible=value.visible;_voxelVolumeSize=value.voxelVolume;_voxelSurfaceStyle=value.surfaceStyle;
 setXTextureURL(value.textureUrls[0]);setYTextureURL(value.textureUrls[1]);setZTextureURL(value.textureUrls[2]);
}
EntityItemProperties EntityScriptingInterface::getEntityProperties(const QUuid& id){
 EntityItemProperties value;auto object=_entityTree->findEntityByEntityItemID(id);if(!object){return value;}
 const auto subject=std::dynamic_pointer_cast<RenderablePolyVoxEntityItem>(object);
 if(!subject){qFatal("Foreign property source");}
 subject->withReadLock([&]{
  value.type=subject->getType();value.host=subject->getEntityHostType();value.name=subject->getName();
  value.position=subject->position;value.dimensions=subject->dimensions;value.rotation=subject->orientation;
  value.voxelVolume=subject->_voxelVolumeSize;value.surfaceStyle=subject->_voxelSurfaceStyle;
  value.textureUrls={subject->getXTextureURL(),subject->getYTextureURL(),subject->getZTextureURL()};
  value.locked=subject->_locked;value.visible=subject->visible;value.created=subject->getCreated();value.edited=subject->getLastEdited();value.lastEditedBy=subject->editedBy;
 });return value;
}
QVector<QUuid> EntityScriptingInterface::findEntities(const glm::vec3& center,float radius,int mask){
 if(center!=glm::vec3(0,1,0) || radius!=128 || mask!=3){qFatal("Foreign host entity scan");}
 QVector<QUuid> ids;_entityTree->withReadLock([&]{for(auto it=_entityTree->objects.cbegin();it!=_entityTree->objects.cend();++it){ids.append(it.key());}});
 return ids;
}
NativeCreateVoxelJoin::NativeCreateVoxelJoin(QObject* parent):QObject(parent){
 sourceClock.start();
 const auto mode=QString::fromUtf8(qgetenv("OVERTE_CREATE_VOXEL_NATIVE_MODE"));
 if(!QStringList{"","normal","retained-renderer","ignored-controller"}.contains(mode)){qFatal("Unknown private native counterexample");}
 keepRenderer=mode=="retained-renderer";ignoreInput=mode=="ignored-controller";
 if(!QCoreApplication::arguments().contains("--testScript")){qFatal("Original voxel join requires the test gate");}
 if(DependencyManager::isSet<EntityScriptingInterface>()){qFatal("A prior host entity source is still installed");}
 entitiesApi=DependencyManager::set<EntityScriptingInterface>();entitiesApi->_entityTree=tree;
 DependencyManager::set<AvatarManager>();DependencyManager::set<NodeList>();
 if(activeTextureObserver){qFatal("A previous owned request observer remains active");}activeTextureObserver=this;
 // Real cache startup uses only newly private XDG roots supplied by the runner.
 for(const auto& key:{"XDG_CONFIG_HOME","XDG_CACHE_HOME","XDG_DATA_HOME"}){
  if(qgetenv(key).isEmpty()){qFatal("The original texture cache requires an isolated host profile");}
 }
 QCoreApplication::setOrganizationName("OvertePicoCreatePrivateHost");QCoreApplication::setApplicationName("original-add-texture");
 QSettings::setDefaultFormat(JSON_FORMAT);
 DependencyManager::set<Setting::Manager>();DependencyManager::set<StatTracker>();
 DependencyManager::set<ResourceRequestObserver>();DependencyManager::set<ResourceCacheSharedItems>();
 DependencyManager::set<ResourceManager>(false);DependencyManager::set<TextureCache>();
 connect(&scheduler,&QTimer::timeout,this,[this]{drive();});scheduler.setInterval(1);scheduler.start();
 snapshot("before-local-insert");
}
QString NativeCreateVoxelJoin::add(const QVariantMap& input,const QString& host){
 if(!identifier.isNull() || !tree->objects.isEmpty() || host!="domain" || input.value("type")!="PolyVox"){
  qFatal("Only one normal original Add for the owned domain entity is admitted");}
 EntityItemProperties properties;properties.type=EntityTypes::PolyVox;properties.name=input.value("name").toString();
 properties.position=point(input.value("position").toMap());properties.dimensions=point(input.value("dimensions").toMap());
 properties.voxelVolume=point(input.value("voxelVolumeSize").toMap());properties.surfaceStyle=input.value("voxelSurfaceStyle").toInt();
 if(properties.voxelVolume!=glm::vec3(8) || properties.surfaceStyle!=3){qFatal("The original dialog did not provide the owned edged 8-cube");}
 properties.textureUrls={input.value("xTextureURL").toString(),input.value("yTextureURL").toString(),input.value("zTextureURL").toString()};
 for(const auto& url:properties.textureUrls){if(QUrl(url).scheme()!="qrc"){qFatal("Only original preset qrc textures are admitted");}}
 properties.lastEditedBy=DependencyManager::get<NodeList>()->getSessionUUID();addProperties=input;
 if(!entitiesApi->addLocalEntityCopy(properties,identifier,false)){qFatal("Original local insertion failed");}
 auto subject=std::dynamic_pointer_cast<RenderablePolyVoxEntityItem>(tree->findEntityByEntityItemID(identifier));
 if(!subject){qFatal("Normal Add did not return its actual original entity");}original=subject;
 renderer=std::shared_ptr<render::entities::PolyVoxEntityRenderer>(new render::entities::PolyVoxEntityRenderer(),[](auto* object){object->deleteLater();});
 renderer->entityOwner=subject;snapshot("normal-add-local-insert");return entityId();
}
bool NativeCreateVoxelJoin::edit(const QString& id,const QVariantMap& input){
 auto subject=original.lock();if(!subject || id!=entityId()){qFatal("Foreign normal property edit");}
 for(auto it=input.cbegin();it!=input.cend();++it){if(!QStringList{"position","dimensions","name"}.contains(it.key())){qFatal("Unbound original entity-property edit");}}
 subject->withWriteLock([&]{
  if(input.contains("position")){subject->position=point(input.value("position").toMap());}
  if(input.contains("dimensions")){subject->dimensions=point(input.value("dimensions").toMap());}
  if(input.contains("name")){subject->name=input.value("name").toString();}
  subject->_needsRenderUpdate=true;
 });propertyEdits.append(input);snapshot("normal-property-edit");return true;
}
bool NativeCreateVoxelJoin::finishAdd(){
 QElapsedTimer budget;budget.start();
 while(budget.elapsed()<5000){
  drive();bool loaded=textureOriginals.size()==2;
  for(const auto& record:textureOriginals){auto texture=record.object.toStrongRef();loaded=loaded && texture && texture->isLoaded() && !texture->isFailed() && texture->getGPUTexture();}
  if(ready(entityId()) && loaded && settle(1500)){snapshot("baseline");return true;}
  QTest::qWait(1);
 }
 snapshot("normal-add-unresolved");return false;
}

void NativeCreateVoxelJoin::drive(){
 auto subject=original.lock();if(!subject){return;}
 bool updating{false};subject->withReadLock([&]{updating=subject->_updateNeeded;});
 if(updating){subject->update(usecTimestampNow());}
 if(!subject->isVoxelDataReady()){return;}
 graphics::MeshPointer mesh;subject->withReadLock([&]{mesh=subject->_mesh;});
 bool needsRender=false;subject->withWriteLock([&]{needsRender=subject->_needsRenderUpdate;subject->_needsRenderUpdate=false;});
 if(mesh && (needsRender || lastRendered.owner_before(mesh)||mesh.owner_before(lastRendered))){
  snapshot("volume-ready-before-render");render();lastRendered=mesh;snapshot("render-copy-updated");
 }
}
void NativeCreateVoxelJoin::render(){
 auto subject=original.lock();if(!subject || !renderer){qFatal("An absent original cannot be rendered");}
 // Only the original update thread observes renderer-owned fields. Joining the
 // actual worker precedes all subsequent resource observations.
 std::array<NetworkTexturePointer,3> textures;
 std::thread worker([&]{
  activeOriginalRender=this;renderer->doRenderUpdateAsynchronousTyped(subject);activeOriginalRender=nullptr;
  textures=renderer->_xyzTextures;
 });worker.join();
 // GUI-side metadata is read only after original renderer copies have been
 // transferred from their owning worker; observers retain weak references.
 for(const auto& texture:textures){if(!texture){continue;}
  bool known=false;for(const auto& record:textureOriginals){auto held=record.object.toStrongRef();known=known || (held && held.data()==texture.data());}
  if(!known){textureOriginals.append({texture.toWeakRef(),texture.data(),texture->getURL().toString()});}
 }
}
bool NativeCreateVoxelJoin::settle(int milliseconds){
 QElapsedTimer budget;budget.start();
 while(budget.elapsed()<milliseconds){
  drive();auto subject=original.lock();
  bool updating{true};if(subject){subject->withReadLock([&]{updating=subject->_updateNeeded;});}
  if(subject && subject->isVoxelDataReady() && !updating){
   return QThreadPool::globalInstance()->waitForDone(milliseconds-int(budget.elapsed()));
  }
  QTest::qWait(1);
 }
 return false;
}
QVariantMap NativeCreateVoxelJoin::properties(const QString& id){
 auto subject=tree->findEntityByEntityItemID(QUuid(id));if(!subject){return {};}
 auto volume=std::dynamic_pointer_cast<RenderablePolyVoxEntityItem>(subject);if(!volume){qFatal("Unexpected original entity type");}
 QByteArray bytes;volume->withReadLock([&]{bytes=volume->_voxelData;});
 return {{"id",entityId()},{"type","PolyVox"},{"entityHostType","domain"},{"locked",volume->_locked},
  {"voxelData",QString::fromLatin1(bytes.toBase64())},{"name",volume->name},{"position",point(volume->position)},
  {"dimensions",point(volume->dimensions)},{"voxelVolumeSize",point(volume->_voxelVolumeSize)}};
}
QVariantMap NativeCreateVoxelJoin::voxelCoords(const QString& id,const QVariantMap& value){
 auto subject=original.lock();if(!subject || id!=entityId()){qFatal("Foreign voxel conversion");}
 return point(subject->worldCoordsToVoxelCoords(point(value)));
}
QVariantMap NativeCreateVoxelJoin::ray(const QVariantMap& from,const QVariantMap& direction){
 auto subject=original.lock();if(!subject){return {{"intersects",false}};}
 auto origin=point(from),rayDirection=point(direction);float distance{};BoxFace face;glm::vec3 normal;
 QVariantMap extra;OctreeElementPointer element;
 const bool hit=subject->findDetailedRayIntersection(origin,rayDirection,{0,1,0},element,distance,face,normal,extra,true);
 return {{"intersects",hit},{"entityID",entityId()},{"intersection",point(origin+rayDirection*distance)}};
}
bool NativeCreateVoxelJoin::setCuboid(const QString& id,const QVariantMap& low,const QVariantMap& size,int value){
 if(id!=entityId() || (value!=0 && value!=255)){qFatal("Only original owned dialog-fill/remove strokes are admitted");}
 if(value==0){++mutationCalls;}const bool changed=entitiesApi->setVoxelsInCuboid(QUuid(id),point(low),point(size),value);
 snapshot("actual-cuboid-return");return changed;
}
bool NativeCreateVoxelJoin::ready(const QString& id){
 return id==entityId() && entitiesApi->isVoxelDataReady(QUuid(id));
}
QVariantList NativeCreateVoxelJoin::values(){
 auto subject=original.lock();if(!subject){return {};}
 const auto packet=subject->featureCreateVoxels();const auto data=QByteArray::fromBase64(packet.value("valuesBase64").toByteArray());
 QVariantList result;for(auto value:data){result.append(int(uint8_t(value)));}return result;
}
int NativeCreateVoxelJoin::registerTimer(const QJSValue& callback,int interval){
 if(!callback.isCallable() || interval!=100 || timers.size()>=128){qFatal("Unexpected original voxel timer");}
 const int id=++timerSequence;auto timer=new QTimer(this);timer->setInterval(interval);timers.insert(id,{timer,0});
 connect(timer,&QTimer::timeout,this,[this,id,callback=QJSValue(callback)]()mutable{
  if(!timers.contains(id) || timers[id].timer.isNull()){qFatal("Retired original timer invoked");}
  ++timers[id].invocations;const auto result=callback.call();if(result.isError()){qFatal("%s",qPrintable(result.toString()));}
 });timer->start();return id;
}
void NativeCreateVoxelJoin::clearTimer(int id){
 if(!timers.contains(id) || timers[id].timer.isNull()){qFatal("Unknown original timer retirement");}
 timers[id].timer->stop();timers[id].timer->deleteLater();
}
bool NativeCreateVoxelJoin::waitForTimers(){
 QElapsedTimer budget;budget.start();
 while(budget.elapsed()<1500){
  bool alive=false;for(const auto& timer:timers){alive=alive || !timer.timer.isNull();}
  if(!alive && ready(entityId())){snapshot("stroke-timers-retired");return true;}
  QTest::qWait(1);
 }
 snapshot("stroke-unresolved");return false;
}
bool NativeCreateVoxelJoin::remove(const QString& id){
 if(id!=entityId() || !tree->objects.contains(identifier)){qFatal("Foreign or repeated normal Delete");}
 ++deleteCalls;tree->objects.remove(identifier);snapshot("normal-delete-tree-removed");
 // Explicit scene ownership boundary. Only the actual normal Delete schedules
 // release; a retained-scene counterexample leaves every owner observable.
 if(!keepRenderer){QTimer::singleShot(0,this,[this]{renderer.reset();});}
 return true;
}
QVariantMap NativeCreateVoxelJoin::snapshot(const QString& phase){
 if(++sequence>512){qFatal("Original Create snapshot inventory exhausted");}
 const auto command=QVariantMap{{"schemaVersion",1},{"commandId",QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')},
  {"action","feature-create-entities-observe"},{"runId",run}};
 const auto frame=entitySource.featureCreateEntities(command);
 if(frame.isEmpty()){qFatal("Original EntitySource6 refused its actual fixture");}
 const auto source=frame.value("source").toMap();QVariant volume,life;
 for(const auto& item:source.value("entities").toList()){
  const auto row=item.toMap();if(row.value("id")==entityId()){volume=row.value("voxels");}
 }
 for(const auto& item:source.value("entityLifetimes").toList()){
  const auto row=item.toMap();if(row.value("id")==entityId()){life=row;}
 }
 if(!identifier.isNull() && !life.isValid()){qFatal("The actual inserted entity has no original lifetime record");}
 const auto resources=source.value("polyvoxResources").toMap();
 QVariantList actualTimers;for(auto it=timers.cbegin();it!=timers.cend();++it){actualTimers.append(QVariantMap{
  {"id",it.key()},{"alive",!it->timer.isNull()},{"invocations",it->invocations}});}
 QVariantMap result{{"createVoxelNativeJoinVersion",1},{"sequence",sequence},{"phase",phase},
  {"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},{"capturedElapsedMs",sourceClock.elapsed()},{"entityId",entityId()},
  {"entityAlive",life.toMap().value("alive",false)},{"inTree",tree->objects.contains(identifier)},{"volume",volume},
  {"polyvoxResources",resources},{"entityLifetime",life},{"entityFrame",frame},{"retirementSource",source},{"timers",actualTimers},{"mutationCalls",mutationCalls},{"deleteCalls",deleteCalls},
  {"cpuBuffers",int(gpu::Buffer::getBufferCPUCount())},{"textureOriginals",textureSnapshot()},
  {"normalAddProperties",addProperties},{"normalPropertyEdits",propertyEdits},
  {"cpuTextures",int(gpu::Texture::getTextureCPUCount())},{"cpuTextureBytes",qulonglong(gpu::Texture::getTextureCPUMemSize())}};
 originals.append(result);
 const auto trace=qgetenv("OVERTE_CREATE_VOXEL_NATIVE_TRACE");
 if(!trace.isEmpty()){
  const auto raw=QJsonDocument::fromVariant(result).toJson(QJsonDocument::Compact)+'\n';
  traceBytes+=quint64(raw.size());if(traceBytes>16*1024*1024){qFatal("Original Create trace inventory exhausted");}
  QFile file(QString::fromUtf8(trace));if(!file.open(QIODevice::Append) || file.write(raw)!=raw.size() || !file.flush()){
   qFatal("Original Create trace was not persisted");}
 }
 return result;
}

void observeCreateTextureRequest(ResourceRequest* request,QObject* parent,const QUrl& url){
 if(!activeTextureObserver){qFatal("Original qrc factory has no owned observer");}
 activeTextureObserver->observeRequest(request,parent,url);
}
void NativeCreateVoxelJoin::observeRequest(ResourceRequest* request,QObject* parent,const QUrl& url){
 if(activeOriginalRender!=this || !request || !qobject_cast<NetworkTexture*>(parent) || url.scheme()!="qrc"){
  qFatal("Unexpected original texture request owner/caller");}
 const auto objectParent=request->parent();
 const QVariantMap provenance{{"factoryOnGui",QThread::currentThread()==thread()},
  {"factoryOwnerAffinityOnGui",parent->thread()==thread()},{"requestAffinityOnGui",request->thread()==thread()},
  {"hasQObjectParent",objectParent!=nullptr},{"qObjectParentIsFactoryOwner",objectParent==parent},
  {"qObjectParentAffinityOnGui",objectParent ? QVariant(objectParent->thread()==thread()) : QVariant()},
  {"originalRenderCaller",activeOriginalRender==this}};
 int index;
 {QMutexLocker lock(&requestMutex);
  if(requestOriginals.size()>=2){qFatal("Original owned texture request inventory exhausted");}
  index=requestOriginals.size();requestOriginals.append({request,parent,objectParent,url.toString(),provenance,{}});
 }
 connect(request,&ResourceRequest::finished,request,[this,request,index]{
  // Read bytes/state on their actual request thread, then deliver only an
  // immutable receipt to the GUI observer. No ResourceRequest is retained.
  const auto data=request->getData();const QVariantMap receipt{{"success",request->getResult()==ResourceRequest::Success},
   {"bytes",data.size()},{"sha256",QString::fromLatin1(QCryptographicHash::hash(data,QCryptographicHash::Sha256).toHex())},
   {"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},{"onRequestThread",QThread::currentThread()==request->thread()}};
  QMetaObject::invokeMethod(this,[this,index,receipt]{QMutexLocker lock(&requestMutex);requestOriginals[index].finished=receipt;},Qt::QueuedConnection);
 },Qt::DirectConnection);
}
QVariantList NativeCreateVoxelJoin::textureSnapshot(){
 if(QThread::currentThread()!=thread()){qFatal("Texture metadata observed away from its GUI owner");}
 QList<RequestOriginal> requestRecords;{QMutexLocker lock(&requestMutex);requestRecords=requestOriginals;}
 QVariantList rows;
 for(auto& record:textureOriginals){auto texture=record.object.toStrongRef();QVariantMap row{{"url",record.url},
  {"alive",bool(texture)||!record.guard.isNull()}};
  if(texture){
   if(texture->thread()!=thread()){qFatal("Original NetworkTexture has a foreign affinity");}
   row["loaded"]=texture->isLoaded();row["failed"]=texture->isFailed();row["width"]=texture->getWidth();row["height"]=texture->getHeight();
   row["originalWidth"]=texture->getOriginalWidth();row["originalHeight"]=texture->getOriginalHeight();
   const auto pixels=texture->getGPUTexture();if(pixels){record.pixels=pixels;record.pixelsObserved=true;row["sourceHash"]=QString::fromStdString(pixels->sourceHash());row["storedBytes"]=qulonglong(pixels->getStoredSize());}
  }
  row["pixelsObserved"]=record.pixelsObserved;row["pixelsAlive"]=!record.pixels.expired();
  QVariantList requests;for(const auto& request:requestRecords){if(request.url==record.url){requests.append(QVariantMap{
   {"alive",!request.object.isNull()},{"factoryOwnerAlive",!request.factoryOwner.isNull()},
   {"qObjectParentAlive",!request.objectParent.isNull()},{"provenance",request.provenance},{"finished",request.finished}});}}
  row["requests"]=requests;rows.append(row);
 }
 return rows;
}
