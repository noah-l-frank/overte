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
class GetMappingRequest;class GetAllMappingsRequest;class AssetRequest;
using MappingOperationCallback=std::function<void(bool,AssetUtils::AssetServerError,QSharedPointer<ReceivedMessage>)>;
using ReceivedAssetCallback=std::function<void(bool,AssetUtils::AssetServerError,const QByteArray&)>;
using ProgressCallback=std::function<void(qint64,qint64)>;
class AssetClient:public QObject {
public:
 GetMappingRequest* createGetMappingRequest(const AssetUtils::AssetPath&);
 GetAllMappingsRequest* createGetAllMappingsRequest();
 AssetRequest* createRequest(const AssetUtils::AssetHash&,const ByteRange& range=ByteRange());
 MessageID getAllAssetMappings(const MappingOperationCallback& callback){return mapping(callback,false);}
 MessageID getAssetMapping(const QString&,const MappingOperationCallback& callback){return mapping(callback,true);}
 MessageID getAsset(const QString&,qint64,qint64,const ReceivedAssetCallback& callback,const ProgressCallback&){
  assert(QThread::currentThread()==thread());const auto id=++next;pending.insert(id,true);++downloads;
  QTimer::singleShot(10,this,[this,id,callback]{if(!pending.remove(id))return;callback(true,AssetUtils::NoError,content);});return id;
 }
 void cancelMappingRequest(MessageID id){assert(QThread::currentThread()==thread());pending.remove(id);++canceled;}
 void cancelGetAssetRequest(MessageID id){cancelMappingRequest(id);}
 template<class... Args> MessageID setAssetMapping(Args&&...){assert(false);return 0;}
 template<class... Args> MessageID deleteAssetMappings(Args&&...){assert(false);return 0;}
 template<class... Args> MessageID renameAssetMapping(Args&&...){assert(false);return 0;}
 template<class... Args> MessageID setBakingEnabled(Args&&...){assert(false);return 0;}
 QByteArray allReply,mappingReply,content;std::atomic<bool> hold{false},fail{false};std::atomic<int> reads{0},downloads{0},canceled{0};
 QSemaphore callbackReturned,allowDestroy;
private:
 MessageID mapping(const MappingOperationCallback& callback,bool resolve){
  assert(QThread::currentThread()==thread());const auto id=++next;pending.insert(id,true);++reads;
  QTimer::singleShot(10,this,[this,id,callback,resolve]{if(!pending.remove(id))return;
   callback(!fail.load(),AssetUtils::NoError,QSharedPointer<ReceivedMessage>::create(resolve?mappingReply:allReply));
   if(hold.load()){callbackReturned.release();assert(allowDestroy.tryAcquire(1,1000));}
  });return id;
 }
 MessageID next{0};QMap<MessageID,bool> pending;
};
#include "assets-dependency-host.h"
