// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Complete original server status/meta/GetAll and original client request/source.
// Assignment/network, protocol serialization and absent bake workers are explicit
// host boundaries. No Asset Server service, oven or production mutation runs.
#define main unused_original_assets_read_host_main
#include "assets-read-native.cpp"
#undef main
#include <algorithm>
#include <tuple>
#include <QFile>
#include <QJsonArray>
#include <sys/stat.h>
#include "AssetsServerTypes.inc"
Q_LOGGING_CATEGORY(asset_server,"asset-server-state-host")
class UnavailableBakeTask {
public:bool isBaking(){qFatal("An oven worker is outside this host qualification");return false;}
};
class NLPacketList {
public:
 QByteArray bytes;
 template<class T>void writePrimitive(T value){primitive<T>(bytes,value);}
 void writeString(const QString& value){string(bytes,value);}
 void write(const QByteArray& value){bytes+=value;}
};
class AssetServer:public QObject {
public:
 AssetUtils::Mappings _fileMappings;QDir _filesDirectory;
 QHash<AssetUtils::AssetHash,std::shared_ptr<UnavailableBakeTask>> _pendingBakes;
 std::pair<AssetUtils::BakingStatus,QString> getAssetStatus(const AssetUtils::AssetPath&,const AssetUtils::AssetHash&);
 std::pair<bool,AssetMeta> readMetaFile(AssetUtils::AssetHash);
 void handleGetAllMappingOperation(NLPacketList&);
 QString getPathToAssetHash(const AssetUtils::AssetHash&);
 QByteArray originalWire(){
  assert(QThread::currentThread()==thread() && _pendingBakes.isEmpty());NLPacketList packet;handleGetAllMappingOperation(packet);
  assert(!packet.bytes.isEmpty() && packet.bytes.at(0)==char(AssetUtils::NoError));return packet.bytes.mid(1);
 }
 QJsonArray originalFiles() {
  assert(QThread::currentThread()==thread());QSet<QString> hashes;QJsonArray rows;
  for(const auto& item:_fileMappings)hashes.insert(item.second);
  auto sorted=hashes.values();std::sort(sorted.begin(),sorted.end());assert(sorted.size()<=16);
  qint64 total=0;
  for(const auto& hash:sorted) {
   const auto path=getPathToAssetHash(hash);QFile input(path);QJsonObject row{{"hash",hash},{"exists",QFileInfo::exists(path)}};
   if(row["exists"].toBool()) {
    assert(input.open(QIODevice::ReadOnly));struct stat before{},after{};assert(fstat(input.handle(),&before)==0 && S_ISREG(before.st_mode));
    const auto bytes=input.read(1024*1024+1);assert(bytes.size()<=1024*1024 && input.atEnd());total+=bytes.size();assert(total<=1024*1024);
    assert(fstat(input.handle(),&after)==0 && before.st_dev==after.st_dev && before.st_ino==after.st_ino && before.st_size==after.st_size
      && before.st_mtim.tv_sec==after.st_mtim.tv_sec && before.st_mtim.tv_nsec==after.st_mtim.tv_nsec
      && before.st_ctim.tv_sec==after.st_ctim.tv_sec && before.st_ctim.tv_nsec==after.st_ctim.tv_nsec);
    row["bytes"]=bytes.size();row["sha256"]=QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex());
    row["device"]=QString::number(before.st_dev);row["inode"]=QString::number(before.st_ino);
    row["modifiedNs"]=QString::number(before.st_mtim.tv_sec*1000000000LL+before.st_mtim.tv_nsec);
    row["changedNs"]=QString::number(before.st_ctim.tv_sec*1000000000LL+before.st_ctim.tv_nsec);
   }
   rows.append(row);
  }return rows;
 }
};
#include "AssetsServerOriginals.inc"
static QString putOriginal(AssetServer& server,const QByteArray& bytes) {
 const auto hash=QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex());
 QFile file(server.getPathToAssetHash(hash));assert(file.open(QIODevice::WriteOnly) && file.write(bytes)==bytes.size());file.close();return hash;
}
int main(int argc,char** argv) {
 QCoreApplication app(argc,argv);assert(argc==3 && app.arguments().contains("--testScript"));QTemporaryDir directory;assert(directory.isValid());
 AssetServer server;server._filesDirectory=QDir(directory.path());
 QFile fbx(QString::fromLocal8Bit(argv[1]));assert(fbx.open(QIODevice::ReadOnly));const auto fbxBytes=fbx.readAll();assert(!fbxBytes.isEmpty());
 const auto originalHash=putOriginal(server,fbxBytes),gltfHash=putOriginal(server,QByteArray("original glTF protocol/disk fixture bytes"));
 const QString run(32,'b'),prefix="/e2e-"+run+"/",model=prefix+"stand.fbx",primary=prefix+"main.gltf";
 server._fileMappings[primary]=gltfHash;server._fileMappings[model]=originalHash;
 const auto redirect=getBakeMapping(originalHash,BAKED_MODEL_SIMPLE_NAME);server._fileMappings[redirect]=originalHash;
 auto nodes=QSharedPointer<NodeList>::create();DependencyManager::slot<NodeList>()=nodes;
 auto client=QSharedPointer<AssetClient>(new AssetClient,[](AssetClient* object){object->deleteLater();});DependencyManager::slot<AssetClient>()=client;
 client->originalServerAll=[&] {
  QByteArray packet;assert(QThread::currentThread()==client->thread());
  assert(QMetaObject::invokeMethod(&server,[&]{packet=server.originalWire();},Qt::BlockingQueuedConnection));return packet;
 };
 QThread network;client->moveToThread(&network);network.start();TestScriptingInterface source;source._testResultsLocation=directory.path();
 int sequence=0;QJsonArray archive;
 auto sample=[&] {
  const auto command=QVariantMap{{"schemaVersion",1},{"commandId",QString::number(++sequence,16).rightJustified(32,'0')},
   {"action","feature-pico-assets-observe"},{"runId",run}};
  QElapsedTimer elapsed;elapsed.start();QVariantMap packet;
  do{QCoreApplication::processEvents();packet=source.featurePicoAssetsRead(command);if(!packet.value("pending").toBool())break;QThread::msleep(1);}while(elapsed.elapsed()<1000);
  assert(packet.contains("source") && packet["activeRequests"]==QVariant(0) && packet["retainedResults"]==QVariant(0));
  const auto originalFiles=server.originalFiles();archive.append(QJsonObject{{"clientOriginal",QJsonObject::fromVariantMap(packet)},{"serverFiles",originalFiles}});
  QMap<QString,int> statuses;for(const auto& item:packet["source"].toMap()["mappings"].toList()) {const auto row=item.toMap();statuses[row["path"].toString()]=row["bakeStatus"].toInt();}
  return statuses;
 };
 // Actual original GetAll emits unsupported glTF and the original FBX redirect.
 auto status=sample();assert(status[primary]==AssetUtils::Irrelevant && status[model]==AssetUtils::NotBaked);
 const auto before=server.originalFiles();assert(before.size()==2);
 // The mapping/status source does not inspect original blob presence.
 assert(QFile::rename(server.getPathToAssetHash(originalHash),directory.filePath("retained-original-input")));
 status=sample();assert(status[model]==AssetUtils::NotBaked);
 bool originalMissing=false;for(const auto& row:server.originalFiles())if(row.toObject()["hash"]==originalHash)originalMissing=!row.toObject()["exists"].toBool();assert(originalMissing);
 assert(QFile::rename(directory.filePath("retained-original-input"),server.getPathToAssetHash(originalHash)));
 // A baked mapping alone is not an actual oven/current-meta/readable-output receipt.
 const QString absentOutputHash(64,'c');server._fileMappings[redirect]=absentOutputHash;
 status=sample();assert(status[model]==AssetUtils::Baked);
 auto meta=server.readMetaFile(originalHash);assert(!meta.first);
 bool outputMissing=false;for(const auto& row:server.originalFiles())if(row.toObject()["hash"]==absentOutputHash)outputMissing=!row.toObject()["exists"].toBool();assert(outputMissing);
 // Original readMetaFile reads a real file: stale version and actual errors
 // remain separate facts even when the current mapping status says Baked.
 const auto stale=QJsonDocument(QJsonObject{{"bake_version",0},{"failed_last_bake",true},{"last_bake_errors","original fixture failure"},{"redirect_target",redirect}}).toJson();
 const auto metaHash=putOriginal(server,stale);server._fileMappings[getBakeMapping(originalHash,"meta.json")]=metaHash;
 status=sample();meta=server.readMetaFile(originalHash);assert(status[model]==AssetUtils::Baked && meta.first && meta.second.failedLastBake
   && meta.second.bakeVersion<currentBakeVersionForAssetType(BakedAssetType::Model) && meta.second.lastBakeErrors=="original fixture failure");
 // Removing only the fixture's baked redirect exposes the original stored error.
 server._fileMappings.erase(redirect);status=sample();assert(status[model]==AssetUtils::Error);
 assert(server._pendingBakes.isEmpty());
 DependencyManager::slot<AssetClient>().clear();client.clear();network.quit();assert(network.wait(1000));DependencyManager::slot<NodeList>().clear();
 std::cout<<QJsonDocument(archive).toJson(QJsonDocument::Compact).constData()<<std::endl;return 0;
}
