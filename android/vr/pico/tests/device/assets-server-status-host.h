// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
// Original server read bodies; assignment/network/worker endpoints remain explicit.
#include <algorithm>
#include <tuple>
#include <QFile>
#include <QJsonArray>
#include <sys/stat.h>
#include "AssetsServerTypes.inc"
Q_DECLARE_LOGGING_CATEGORY(asset_server)
class UnavailableBakeTask {
public:bool isBaking(){qFatal("An oven worker is outside this host qualification");return false;}
};
class NLPacketList {
public:
 QByteArray bytes;
 template<class T>void writePrimitive(T value){bytes.append(reinterpret_cast<const char*>(&value),sizeof(value));}
 void writeString(const QString& value){const auto raw=value.toUtf8();writePrimitive<quint32>(raw.size());bytes+=raw;}
 void write(const QByteArray& value){bytes+=value;}
};
class AssetServer:public QObject {
public:
 AssetUtils::Mappings _fileMappings;QDir _filesDirectory;
 QString instance{QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')};quint64 queries{0};
 QHash<AssetUtils::AssetHash,std::shared_ptr<UnavailableBakeTask>> _pendingBakes;
 std::pair<AssetUtils::BakingStatus,QString> getAssetStatus(const AssetUtils::AssetPath&,const AssetUtils::AssetHash&);
 std::pair<bool,AssetMeta> readMetaFile(AssetUtils::AssetHash);
 void handleGetAllMappingOperation(NLPacketList&);
 QString getPathToAssetHash(const AssetUtils::AssetHash&);
 QByteArray originalWire(){
  assert(QThread::currentThread()==thread() && _pendingBakes.isEmpty());++queries;NLPacketList packet;handleGetAllMappingOperation(packet);
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
