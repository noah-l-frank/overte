// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include "PicoAssetsReadJob.h"
#include <QCoreApplication>
#include <QThread>
#include <QSemaphore>
#include <cassert>
#include <map>
struct Mapping {QString hash;int status;QString bakingErrors;};
int main(int argc,char** argv) {
 QCoreApplication app(argc,argv);using namespace overte::e2e;
 const QString run(32,'a'),instance(32,'b'),domain="12345678-1234-4234-8234-123456789abc";
 QVariantMap command{{"schemaVersion",1},{"commandId",QString(32,'c')},{"runId",run},{"action","feature-pico-assets-observe"}};
 assert(picoAssetsReadCommand(command));auto invalid=command;invalid["schemaVersion"]=true;assert(!picoAssetsReadCommand(invalid));
 const std::map<QString,Mapping> mappings{{"/.baked/real/mesh",{QString(64,'1'),4,{}}},{"/e2e-"+run+"/main.gltf",{QString(64,'2'),0,{}}}};
 const auto original=picoAssetsMappingsOriginal(mappings,true,domain,domain,domain);assert(original.value("mappings").toList().size()==2);
 assert(picoAssetsMappingsOriginal(std::map<QString,Mapping>{{"/../foreign",{QString(64,'1'),0,{}}}},true,domain,domain,domain).isEmpty());
 const QByteArray bytes("actual independent content");const auto hash=QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex());
 assert(!picoAssetsDownloadOriginal(hash,bytes,false,domain,domain,domain).isEmpty());
 assert(picoAssetsDownloadOriginal(hash,bytes+"foreign",false,domain,domain,domain).isEmpty());
 PicoAssetsReadJob job;
 auto callbacks=[&](QObject* request){
  const auto finished=std::make_shared<int>(0),destroyed=std::make_shared<int>(0);
  auto a=QObject::connect(request,&QObject::objectNameChanged,request,[finished]{});
  auto b=QObject::connect(request,&QObject::destroyed,[&job,request,destroyed]{job.destroyed(request);});
  assert(job.callback("finished",a,finished));assert(job.callback("destroyed",b,destroyed));
 };
 QObject* request=new QObject;QObject* cancellation=new QObject;
 assert(job.begin(command,request,cancellation,instance,1,{{"domain",domain}}));callbacks(request);
 // An asserted destroy callback cannot substitute for actual QObject death.
 job.finish(request,original,QDateTime::currentMSecsSinceEpoch());job.destroyed(request);
 assert(job.poll(command).value("pending")==QVariant(true));delete request;
 const auto packet=job.poll(command);assert(packet.value("source").toMap()==original);
 assert(packet.value("activeRequests")==QVariant(0));assert(!job.canBegin(command));assert(job.poll(command).isEmpty());
 QThread worker;worker.start();auto second=command;second["commandId"]=QString(32,'d');
 request=new QObject;request->moveToThread(&worker);cancellation=new QObject;
 assert(job.begin(second,request,cancellation,instance,2,{{"domain",domain}}));callbacks(request);
 QSemaphore copied;QMetaObject::invokeMethod(request,[&job,request,&copied,original]{job.finish(request,original,QDateTime::currentMSecsSinceEpoch());copied.release();},Qt::QueuedConnection);
 assert(copied.tryAcquire(1,1000));assert(job.poll(second).value("pending")==QVariant(true));
 QSemaphore dead;QObject::connect(request,&QObject::destroyed,[&dead]{dead.release();});QMetaObject::invokeMethod(request,"deleteLater",Qt::QueuedConnection);
 assert(dead.tryAcquire(1,1000));QVariantMap delivered;
 for(int attempt=0;attempt<500;++attempt){delivered=job.poll(second);if(!delivered.value("pending").toBool())break;QThread::msleep(1);}
 assert(delivered.value("source").toMap()==original);
 // Wrong-thread source copy is rejected and never becomes a successful packet.
 auto third=command;third["commandId"]=QString(32,'e');request=new QObject;request->moveToThread(&worker);cancellation=new QObject;
 assert(job.begin(third,request,cancellation,instance,3,{}));callbacks(request);job.finish(request,original,QDateTime::currentMSecsSinceEpoch());
 QSemaphore gone;
 QObject::connect(request,&QObject::destroyed,[&gone]{gone.release();});QMetaObject::invokeMethod(request,"deleteLater",Qt::QueuedConnection);
 assert(gone.tryAcquire(1,1000));
 for(int attempt=0;attempt<500;++attempt){delivered=job.poll(third);if(!delivered.value("pending").toBool())break;QThread::msleep(1);}
 assert(delivered.isEmpty());
 worker.quit();assert(worker.wait(1000));return 0;
}
