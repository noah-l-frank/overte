// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include "assets-read-endpoints-host.h"
#include "assets-read-nodes-host.h"
#include "MappingRequest.h"
#include "AssetRequest.h"
#include "PicoAssetsReadJob.h"
#include "AudioSettingsQueue.h"
#include <QDateTime>
#include <QElapsedTimer>
#include <QRegExp>
#include <QFileInfo>
#include <QLoggingCategory>
#include <QThread>
#include <QTemporaryDir>
#include <QJsonDocument>
#include <iostream>
Q_LOGGING_CATEGORY(asset_client,"asset-client-host")
#include "AssetsReadOriginals.inc"
namespace AssetUtils {
// Explicit cache endpoint; original AssetRequest performs its ordinary branch.
QByteArray cache;
QByteArray loadFromCache(const QUrl&){return cache;}
bool saveToCache(const QUrl&,const QByteArray&){return true;}
}
struct AssetsReadHostLifecycle {QVariantMap snapshot()const{return {{"present",true}};}};
class TestScriptingInterface:public QObject {
public:
 QVariantMap featurePicoAssetsRead(const QVariantMap&,bool abort=false);
 QVariantMap featurePicoAssetsReadRetire(const QVariantMap&);
 QString _testResultsLocation,_featureObservationInstance{QString(32,'a')};
 std::shared_ptr<AssetsReadHostLifecycle> _featureLifecycle{std::make_shared<AssetsReadHostLifecycle>()};
 std::shared_ptr<overte::e2e::AudioSettingsQueue> _featureAssetsReadQueue{std::make_shared<overte::e2e::AudioSettingsQueue>()};
 std::shared_ptr<overte::e2e::PicoAssetsReadJob> _featureAssetsRead{std::make_shared<overte::e2e::PicoAssetsReadJob>()};
 quint64 _featureAssetsReadRetireSequence{0};
 QHash<QString,QVariantMap> _featureAssetsReadRetireCommands,_featureAssetsReadRetireResults;QHash<QString,qint64> _featureAssetsReadRetireRequested;
 quint64 _featureAssetsReadSequence{0};QPointer<QObject> _featureAssetsClientObject,_featureAssetsNodesObject,_featureAssetsServerObject;
 QString _featureAssetsClientBirth,_featureAssetsNodesBirth,_featureAssetsServerBirth;
};
#include "AssetsReadMethod.inc"
template<class T>static void primitive(QByteArray& bytes,T value){bytes.append(reinterpret_cast<const char*>(&value),sizeof(value));}
static void string(QByteArray& bytes,const QString& value){const auto raw=value.toUtf8();primitive<quint32>(bytes,raw.size());bytes+=raw;}
int main(int argc,char** argv){
 QCoreApplication app(argc,argv);QTemporaryDir directory;TestScriptingInterface source;source._testResultsLocation=directory.path();
 const QString run(32,'b');int sequence=0;
 auto command=[&](const QString& action="observe"){return QVariantMap{{"schemaVersion",1},{"commandId",QString::number(++sequence,16).rightJustified(32,'0')},
  {"action","feature-pico-assets-"+action},{"runId",run}};};
 assert(source.featurePicoAssetsRead(command()).isEmpty()); // No dependency creation.
 if(!app.arguments().contains("--testScript"))return 0;
 auto nodes=QSharedPointer<NodeList>::create();DependencyManager::slot<NodeList>()=nodes;
 if(app.arguments().contains("--independent-host-actor")) {
  // Actual new host actor/process births; NodeList/network remain declared
  // endpoints. Never adopt an input-requested source generation or identity.
  source._featureObservationInstance=QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');nodes->session=QUuid::createUuid();
 }
 auto client=QSharedPointer<AssetClient>(new AssetClient,[](AssetClient* original){original->deleteLater();});DependencyManager::slot<AssetClient>()=client;
 client->content="original independent asset bytes";const auto hash=QCryptographicHash::hash(client->content,QCryptographicHash::Sha256);
 primitive<quint32>(client->allReply,3);string(client->allReply,"/.baked/real/mesh");client->allReply+=hash;primitive<AssetUtils::BakingStatus>(client->allReply,AssetUtils::Baked);
 string(client->allReply,"/e2e-"+run+"/main.gltf");client->allReply+=hash;primitive<AssetUtils::BakingStatus>(client->allReply,AssetUtils::Irrelevant);
 string(client->allReply,"/other/bake-error");client->allReply+=hash;primitive<AssetUtils::BakingStatus>(client->allReply,AssetUtils::Error);string(client->allReply,"actual first diagnostic\nactual second diagnostic");
 client->mappingReply=hash;primitive<quint8>(client->mappingReply,1);string(client->mappingReply,"/.baked/real/mesh");
 if(app.arguments().contains("--host-shared-server-wire")) {
  assert(app.arguments().contains("--serve") && app.arguments().contains("--independent-host-actor"));
  client->originalServerAll=[] {
   const auto id=QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');
   const QJsonObject request{{"action","host-original-server-wire"},{"requestId",id}};
   std::cout<<QJsonDocument(request).toJson(QJsonDocument::Compact).constData()<<std::endl;
   std::string line;assert(std::getline(std::cin,line));assert(line.size()<=1024*1024);
   const auto reply=QJsonDocument::fromJson(QByteArray::fromStdString(line)).object();
   assert(reply.value("requestId")==id && reply.size()==2 && reply.value("wireBase64").isString());
   const auto encoded=reply.value("wireBase64").toString().toLatin1(),wire=QByteArray::fromBase64(encoded);
   assert(wire.toBase64()==encoded && wire.size()<=1024*1024);return wire;
  };
 }
 QThread network;client->moveToThread(&network);network.start();
 auto complete=[&](const QVariantMap& request){QElapsedTimer elapsed;elapsed.start();QVariantMap value;
  do{QCoreApplication::processEvents();value=source.featurePicoAssetsRead(request);if(!value.value("pending").toBool())return value;QThread::msleep(1);}while(elapsed.elapsed()<1000);
  assert(false);return QVariantMap();};
 if(app.arguments().contains("--serve")) {
  std::string line;
  while(std::getline(std::cin,line)) {
   const auto request=QJsonDocument::fromJson(QByteArray::fromStdString(line)).object().toVariantMap();
   const bool retiring=request.value("action")=="feature-pico-assets-read-retire";QElapsedTimer elapsed;elapsed.start();QVariantMap packet;
   do{QCoreApplication::processEvents();packet=retiring?source.featurePicoAssetsReadRetire(request):source.featurePicoAssetsRead(request);
      if(!packet.value("pending").toBool())break;QThread::msleep(1);}while(elapsed.elapsed()<1000);
   std::cout<<QJsonDocument(QJsonObject::fromVariantMap(packet)).toJson(QJsonDocument::Compact).constData()<<std::endl;
  }
  DependencyManager::slot<AssetClient>().clear();client.clear();network.quit();assert(network.wait(1000));DependencyManager::slot<NodeList>().clear();return 0;
 }
 // Complete original GetAll/decoder callbacks run on actual request thread.
 auto request=command();client->hold=true;assert(source.featurePicoAssetsRead(request).value("pending")==QVariant(true));
 assert(client->callbackReturned.tryAcquire(1,1000));assert(source.featurePicoAssetsRead(request).value("pending")==QVariant(true));
 client->hold=false;client->allowDestroy.release();const auto maps=complete(request);assert(maps.value("source").toMap().value("mappings").toList().size()==3);
 assert(maps.value("activeRequests")==QVariant(0));assert(source.featurePicoAssetsRead(request).isEmpty());
 auto resolve=command("resolve");resolve["path"]="/e2e-"+run+"/main.gltf";
 const auto resolved=complete(resolve).value("source").toMap();assert(resolved.value("requestedPath")==resolve.value("path"));assert(resolved.value("redirected")==QVariant(true));
 auto download=command("download");download["hash"]=QString::fromLatin1(hash.toHex());const auto data=complete(download).value("source").toMap();
 assert(QByteArray::fromBase64(data.value("base64").toByteArray())==client->content);assert(data.value("loadedFromCache")==QVariant(false));
 // Original cache branch and original download hash verification remain real.
 const auto downloadCount=client->downloads.load();AssetUtils::cache=client->content;download["commandId"]=command().value("commandId");
 assert(complete(download).value("source").toMap().value("loadedFromCache")==QVariant(true));assert(client->downloads.load()==downloadCount);
 AssetUtils::cache=QByteArray();download["commandId"]=command().value("commandId");download["hash"]=QString(64,'0');
 assert(complete(download).isEmpty());
 // Same UUID is insufficient: original DomainHandler birth/revision changes.
 request=command();client->hold=true;assert(source.featurePicoAssetsRead(request).value("pending")==QVariant(true));
 assert(client->callbackReturned.tryAcquire(1,1000));nodes->domain.reconnectSameUuid();assert(source.featurePicoAssetsRead(request).value("pending")==QVariant(true));
 client->hold=false;client->allowDestroy.release();assert(complete(request).isEmpty());
 client->fail=true;assert(complete(command()).isEmpty());client->fail=false;
 // An uncertain readonly request is canceled/finalized by exact original
 // command, never by starting another request or inventing an empty mapping.
 request=command();client->hold=true;assert(source.featurePicoAssetsRead(request).value("pending")==QVariant(true));
 assert(client->callbackReturned.tryAcquire(1,1000));const auto issued=client->reads.load();
 QVariantMap retire{{"schemaVersion",1},{"commandId",QString(32,'f')},{"action","feature-pico-assets-read-retire"},{"original",request}};
 assert(source.featurePicoAssetsReadRetire(retire).value("pending")==QVariant(true));
 client->hold=false;client->allowDestroy.release();QElapsedTimer finalized;finalized.start();QVariantMap retirement;
 do{retirement=source.featurePicoAssetsReadRetire(retire);if(!retirement.value("pending").toBool())break;QThread::msleep(1);}while(finalized.elapsed()<1000);
 const auto retired=retirement.value("source").toMap();assert(retired.value("retired")==QVariant(true));
 for(const auto& key:QStringList{"requestAlive","finishedConnected","destroyedConnected","finishedCaptureAlive","destroyedCaptureAlive","cancellationAlive"}) {assert(retired.value(key)==QVariant(false));}
 assert(client->reads.load()==issued);assert(source.featurePicoAssetsReadRetire(retire)==retirement);
 auto foreign=retire;foreign["commandId"]=QString(32,'d');auto wrong=request;wrong["runId"]=QString(32,'e');foreign["original"]=wrong;
 assert(source.featurePicoAssetsReadRetire(foreign).isEmpty());

 // Missing producer/runtime never admits a new request; finite limit never resets.
 const auto count=client->reads.load();source._featureAssetsReadSequence=512;assert(source.featurePicoAssetsRead(command()).isEmpty());assert(client->reads.load()==count);
 QPointer<AssetClient> originalClient(client.data());DependencyManager::slot<AssetClient>().clear();client.clear();
 network.quit();assert(network.wait(1000));assert(originalClient.isNull());DependencyManager::slot<NodeList>().clear();nodes.clear();return 0;
}
