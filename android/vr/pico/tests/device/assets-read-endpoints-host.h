// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
// Declared protocol/cache endpoints only. Production request classes, complete
// mapping decoder, hash checks, thread routing and source getter are unmodified.
#include <QCoreApplication>
#include <QThread>
#include <QMap>
#include <QSharedPointer>
#include <QTimer>
#include <QSemaphore>
#include <QMutex>
#include <QMutexLocker>
#include <QPointer>
#include <QVariant>
#include <functional>
#include <atomic>
#include <cstring>
#include <cassert>
#include "AssetUtils.h"
#include "ByteRange.h"
using MessageID=quint32;constexpr MessageID INVALID_MESSAGE_ID=0;
class ReceivedMessage {
public:
 explicit ReceivedMessage(const QByteArray& bytes):data(bytes){}
 QByteArray read(qint64 size){const auto count=qMin<qint64>(size,data.size()-position);const auto bytes=data.mid(position,count);position+=count;return bytes;}
 QByteArray readWithoutCopy(qint64 size){return read(size);}
 template<class T> qint64 readPrimitive(T* value){const auto raw=read(sizeof(T));if(raw.size()!=sizeof(T))return 0;std::memcpy(value,raw.constData(),sizeof(T));return sizeof(T);}
 QString readString();
private:QByteArray data;qint64 position{0};
};
class GetMappingRequest;class GetAllMappingsRequest;class AssetRequest;class AssetUpload;class SetMappingRequest;
using MappingOperationCallback=std::function<void(bool,AssetUtils::AssetServerError,QSharedPointer<ReceivedMessage>)>;
using ReceivedAssetCallback=std::function<void(bool,AssetUtils::AssetServerError,const QByteArray&)>;
using ProgressCallback=std::function<void(qint64,qint64)>;
class AssetClient:public QObject {
public:
 GetMappingRequest* createGetMappingRequest(const AssetUtils::AssetPath&);
 GetAllMappingsRequest* createGetAllMappingsRequest();
 AssetRequest* createRequest(const AssetUtils::AssetHash&,const ByteRange& range=ByteRange());
#if defined(ASSETS_ORIGINAL_BUNDLE_UPLOADS)
 AssetUpload* createUpload(const QString&);
 SetMappingRequest* createSetMappingRequest(const AssetUtils::AssetPath&,const AssetUtils::AssetHash&);
 // Explicit in-memory protocol endpoint. Original request classes read private
 // file bytes/hash/response and the separate GetAll request decodes this state;
 // these are not an actual Asset Server/disk/oven receipt.
 MessageID uploadAsset(const QByteArray& bytes,std::function<void(bool,AssetUtils::AssetServerError,const QString&)> callback) {
  assert(QThread::currentThread()==thread());const auto id=++next;const auto hash=AssetUtils::hashData(bytes).toHex();
  blobs.insert(hash,bytes);QTimer::singleShot(10,this,[callback,hash]{callback(true,AssetUtils::NoError,QString::fromLatin1(hash));});return id;
 }
 MessageID setAssetMapping(const QString& path,const AssetUtils::AssetHash& hash,MappingOperationCallback callback) {
  assert(QThread::currentThread()==thread());const auto id=++next;mappings.insert(path,hash);
  QTimer::singleShot(10,this,[callback]{callback(true,AssetUtils::NoError,QSharedPointer<ReceivedMessage>::create(QByteArray()));});return id;
 }
 QMap<QString,QString> mappings;QMap<QByteArray,QByteArray> blobs;
#endif
 MessageID getAllAssetMappings(const MappingOperationCallback& callback){return mapping(callback,false);}
 MessageID getAssetMapping(const QString& path,const MappingOperationCallback& callback){return mapping(callback,true,path);}
 MessageID getAsset(const QString& hash,qint64,qint64,const ReceivedAssetCallback& callback,const ProgressCallback&){
  assert(QThread::currentThread()==thread());const auto id=++next;pending.insert(id,true);++downloads;
  QTimer::singleShot(10,this,[this,id,callback,hash]{if(!pending.remove(id))return;
#if defined(ASSETS_ORIGINAL_BUNDLE_UPLOADS)
   callback(true,blobs.contains(hash.toLatin1())?AssetUtils::NoError:AssetUtils::AssetNotFound,blobs.value(hash.toLatin1()));
#else
   callback(true,AssetUtils::NoError,content);
#endif
  });return id;
 }
 void cancelMappingRequest(MessageID id){assert(QThread::currentThread()==thread());pending.remove(id);++canceled;}
 void cancelGetAssetRequest(MessageID id){cancelMappingRequest(id);}
#if !defined(ASSETS_ORIGINAL_BUNDLE_UPLOADS)
 template<class... Args> MessageID setAssetMapping(Args&&...){assert(false);return 0;}
#endif
 template<class... Args> MessageID deleteAssetMappings(Args&&...){assert(false);return 0;}
 template<class... Args> MessageID renameAssetMapping(Args&&...){assert(false);return 0;}
 template<class... Args> MessageID setBakingEnabled(Args&&...){assert(false);return 0;}
 QByteArray allReply,mappingReply,content;std::atomic<bool> hold{false},fail{false};std::atomic<int> reads{0},downloads{0},canceled{0};
 QSemaphore callbackReturned,allowDestroy;
private:
 MessageID mapping(const MappingOperationCallback& callback,bool resolve,const QString& path=QString()){
  assert(QThread::currentThread()==thread());const auto id=++next;pending.insert(id,true);++reads;
  QTimer::singleShot(10,this,[this,id,callback,resolve,path]{if(!pending.remove(id))return;
   auto reply=resolve?mappingReply:allReply;
#if defined(ASSETS_ORIGINAL_BUNDLE_UPLOADS)
   if(resolve) {
    if(!mappings.contains(path)){callback(true,AssetUtils::AssetNotFound,QSharedPointer<ReceivedMessage>::create(QByteArray()));return;}
    reply=QByteArray::fromHex(mappings.value(path).toLatin1());reply.append(char(0));
   } else {
    reply.clear();auto primitive=[&](const auto& value){reply.append(reinterpret_cast<const char*>(&value),sizeof(value));};
    primitive(quint32(mappings.size()));for(auto it=mappings.cbegin();it!=mappings.cend();++it) {
     const auto path=it.key().toUtf8();primitive(quint32(path.size()));reply+=path;reply+=QByteArray::fromHex(it.value().toLatin1());primitive(AssetUtils::Irrelevant);
    }
   }
#endif
   callback(!fail.load(),AssetUtils::NoError,QSharedPointer<ReceivedMessage>::create(reply));
   if(hold.load()){callbackReturned.release();assert(allowDestroy.tryAcquire(1,1000));}
  });return id;
 }
 MessageID next{0};QMap<MessageID,bool> pending;
};
#include "assets-dependency-host.h"
