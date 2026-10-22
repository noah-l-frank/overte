// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include "CreateBrowseSettingOwner.h"
#include <SettingInterface.h>
#include <SettingHandle.h>
#include <QCoreApplication>
#include <QDir>
#include <QFile>
#include <QJsonDocument>
#include <QMutexLocker>
#include <QSettings>
#include <QTextStream>
#include <cassert>
#include <memory>
#include <sys/stat.h>
// Only the application-wide dependency registry's lifetime is supplied here.
// Setting::Manager, its actual worker, locks, map, signals and persistence are
// compiled from the original product implementation.
DependencyManager& DependencyManager::manager(){static auto* value=new DependencyManager;return *value;}
QSharedPointer<Dependency> DependencyManager::safeGet(size_t code)const{QMutexLocker lock(&_instanceHashMutex);return _instanceHash.value(code);}
struct OffscreenUi:Dependency {
    QVariantMap source{{"createDialogSourceVersion",3},{"complete",true},{"dialogs",QVariantList{}}};
    QVariantMap featureCreateDialogs(){return source;}
};
struct Lifecycle {QVariantMap snapshot(){return {{"launches",1}};}};
struct TestScriptingInterface:QObject {
    QVariantMap featureCreateBrowseSetting(const QVariantMap& command);
    QString _testResultsLocation,_featureObservationInstance{QString(32,'9')};
    std::shared_ptr<Lifecycle> _featureLifecycle{std::make_shared<Lifecycle>()};
    quint64 _featureCreateBrowseSettingSequence{0};
    QHash<QString,QVariantMap> _featureCreateBrowseSettingCommands,_featureCreateBrowseSettingResults;
};
#include "OriginalCreateBrowseSetting.inc"
Q_LOGGING_CATEGORY(settings_interface, "settings.interface")
Q_LOGGING_CATEGORY(settings_handle, "settings.handle")
namespace Setting {
#include "OriginalSettingInterface.inc"
}
static const QString LAST_BROWSE_LOCATION_SETTING="LastBrowseLocation",DESKTOP_LOCATION="controlled-desktop-default";
struct WindowScriptingInterface {QString getPreviousBrowseLocation() const;};
#include "OriginalPreviousBrowse.inc"
class SettingsTests {
public:
    static void barrier(Setting::Manager* manager) {
        manager->forceSave();QObject barrier;barrier.moveToThread(&manager->_workerThread);
        assert(QMetaObject::invokeMethod(&barrier,[&]{barrier.moveToThread(QCoreApplication::instance()->thread());},Qt::BlockingQueuedConnection));
    }
    static void registerHandle(Setting::Manager* manager,Setting::Interface* handle){manager->registerHandle(handle);}
    static void removeHandle(Setting::Manager* manager){manager->removeHandle("LastBrowseLocation");}
    static void destroy(Setting::Manager* manager){delete manager;}
    static void stop(Setting::Manager* manager){manager->terminateThread();assert(manager->_workerThread.wait(2000));}
};
class CachedHandle:public Setting::Interface {
public:
    CachedHandle():Interface("LastBrowseLocation"){}void setVariant(const QVariant&)override{}QVariant getVariant()override{return {};}
};
QVariantMap call(QString operation,QString run=QString(32,'a')) {
    return {{"schemaVersion",1},{"commandId",QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')},
        {"action","feature-create-browse-setting"},{"operation",operation},{"runId",run},{"ownerToken",QString(64,'f')}};
}
QVariantMap stage(const QString& root,const QString& run,const QString& ticket) {
    const QByteArray input="{\"DataVersion\":3,\"Entities\":[{\"name\":\"controlled-input\"}]}";
    auto command=QVariantMap{{"schemaVersion",1},{"commandId",QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')},
        {"action","feature-script-files"},{"sourceRole","create-json-v1"},{"operation","stage"},{"runId",run},
        {"ticket",ticket},{"ownerToken",QString(64,'e')},{"files",QVariantMap{{"entity-import.json",QString::fromLatin1(input.toBase64())}}}};
    assert(overte::e2e::PrivateCreateFiles::request(root,command).value("performed").toBool());command.remove("files");command["operation"]="locate";
    const auto location=overte::e2e::PrivateCreateFiles::request(root,command);assert(location.value("exists").toBool());return location;
}
QVariantMap dialog(const QString& path,QString role="import") {
    const auto now=QDateTime::currentMSecsSinceEpoch();const auto suffix=role=="import" ? "/entity-import.json" : "/export.json";
    return {{"createDialogSourceVersion",3},{"instance",QString(32,'b')},{"complete",true},{"dialogs",QVariantList{QVariantMap{
        {"id",QString(32,'c')},{"rootId",QString(32,'d')},{"listenerId",QString(32,'e')},{"contextId",QString(32,'f')},{"windowId",QString(32,'1')},
        {"role",role},{"registeredEpochMs",now},{"returnedEpochMs",now},{"pending",false},{"dispatches",0},
        {"rootAlive",false},{"listenerAlive",false},{"contextAlive",false},
        {"responseSha256",QString::fromLatin1(QCryptographicHash::hash((path+suffix).toUtf8(),QCryptographicHash::Sha256).toHex())}}}}};
}
QVariantMap claim(const QString& run,const QString& ticket,const QVariantMap& source) {
    const auto row=source.value("dialogs").toList().first().toMap();auto command=call("claim",run);
    QVariantMap binding{{"bindingVersion",1},{"sourceInstance",source.value("instance")},{"dialogId",row.value("id")}};
    for(const auto& key:QStringList{"rootId","listenerId","contextId","windowId","role"}){binding[key]=row.value(key);}
    command.insert("ticket",ticket);command.insert("fileOwnerToken",QString(64,'e'));command.insert("dialogBinding",binding);return command;
}
QVariantMap acquireRead(overte::e2e::CreateBrowseSettingOwner& owner,const QString& root,const QString& run,const QString& ticket,const QString& path,const QString& role="import") {
    const auto before=overte::e2e::CreateBrowseSettingOwner::captureRead();
    WindowScriptingInterface window;const auto originalResult=window.getPreviousBrowseLocation();Q_UNUSED(originalResult)
    const auto after=overte::e2e::CreateBrowseSettingOwner::captureRead();auto packet=dialog(path,role);
    auto rows=packet.value("dialogs").toList();auto row=rows.first().toMap();
    row["browseSettingRead"]=QVariantMap{{"before",before},{"after",after}};
    row["pending"]=true;row["rootAlive"]=true;row["listenerAlive"]=true;row["contextAlive"]=true;row["returnedEpochMs"]=0;
    packet["dialogs"]=QVariantList{row};auto command=claim(run,ticket,packet);command["operation"]="claim-read";
    assert(!owner.request(root,command,packet).isEmpty());
    row["pending"]=false;row["rootAlive"]=false;row["listenerAlive"]=false;row["contextAlive"]=false;
    row["returnedEpochMs"]=QDateTime::currentMSecsSinceEpoch();packet["dialogs"]=QVariantList{row};return packet;
}
int main(int argc,char** argv) {
    QCoreApplication app(argc,argv);assert(argc>=2);::umask(0077);const auto root=QString::fromLocal8Bit(argv[1]);
    QCoreApplication::setOrganizationName("OwnedCreateBrowseHost");QCoreApplication::setApplicationName("settings");
    QSettings::setDefaultFormat(QSettings::IniFormat);QSettings::setPath(QSettings::IniFormat,QSettings::UserScope,root);
    TestScriptingInterface getter;getter._testResultsLocation=root;
    assert(getter.featureCreateBrowseSetting(call("reserve")).isEmpty()); // No Offscreen dependency is instantiated.
    assert(!DependencyManager::isSet<OffscreenUi>());
    auto actualUi=DependencyManager::set<OffscreenUi>();
    overte::e2e::CreateBrowseSettingOwner owner;
    assert(owner.request(root,call("reserve"),{}).isEmpty());assert(!DependencyManager::isSet<Setting::Manager>());
    auto manager=DependencyManager::set<Setting::Manager>();const auto actual=manager.data();manager->setValue("unrelated-control",QByteArray("unchanged"));
    if(!app.arguments().contains("--testScript")){assert(getter.featureCreateBrowseSetting(call("reserve")).isEmpty());assert(owner.request(root,call("reserve"),{}).isEmpty());SettingsTests::stop(actual);return 0;}
    auto firstCommand=call("reserve",QString(32,'9'));const auto firstGetter=getter.featureCreateBrowseSetting(firstCommand);
    assert(!firstGetter.value("source").toMap().isEmpty());assert(!manager->contains("LastBrowseLocation"));
    assert(getter.featureCreateBrowseSetting(firstCommand)==firstGetter);
    auto changedCommand=firstCommand;changedCommand["operation"]="restore";assert(getter.featureCreateBrowseSetting(changedCommand).isEmpty());
    QThread stopped;auto foreign=new TestScriptingInterface;foreign->_testResultsLocation=root;foreign->moveToThread(&stopped);
    assert(foreign->featureCreateBrowseSetting(call("observe",QString(32,'9'))).isEmpty());
    stopped.start();assert(QMetaObject::invokeMethod(foreign,[&]{foreign->moveToThread(app.thread());},Qt::BlockingQueuedConnection));
    stopped.quit();assert(stopped.wait(1000));delete foreign;
    assert(!manager->contains("LastBrowseLocation"));const auto reserved=owner.request(root,call("reserve"),{});
    assert(!reserved.isEmpty() && !reserved.value("original").toMap().value("present").toBool());
    assert(!manager->contains("LastBrowseLocation")); // Passive capture never inserts a default/invalid map entry.
    const QString run(32,'a'),ticket(32,'d');const auto directory=QUrl(stage(root,run,ticket).value("directory").toString()).toLocalFile();
    const auto originalDialog=acquireRead(owner,root,run,ticket,directory);manager->setValue("LastBrowseLocation",directory);
    const auto claimed=owner.request(root,claim(run,ticket,originalDialog),originalDialog);assert(!claimed.isEmpty());
    assert(claimed.value("claims").toList().size()==1 && claimed.value("current").toMap().value("stringValue")==directory);
    assert(owner.request(root,claim(run,ticket,originalDialog),originalDialog).isEmpty()); // Never duplicate a claim after uncertain delivery.
    const auto restored=owner.request(root,call("restore"),originalDialog);assert(restored.value("restored").toBool());
    assert(!manager->contains("LastBrowseLocation"));assert(manager->value("unrelated-control")==QVariant(QByteArray("unchanged")));
    SettingsTests::barrier(actual);QSettings disk(manager->fileName(),QSettings::IniFormat);disk.sync();assert(!disk.contains("LastBrowseLocation"));
    assert(owner.request(root,call("release"),originalDialog).value("released").toBool());
    QTextStream(stdout)<<QJsonDocument::fromVariant(restored).toJson(QJsonDocument::Compact)<<'\n';
    const QString secondRun(32,'2'),secondTicket(32,'3');manager->setValue("LastBrowseLocation",QString("/original/selected-location"));
    assert(!owner.request(root,call("reserve",secondRun),{}).isEmpty());const auto secondPath=QUrl(stage(root,secondRun,secondTicket).value("directory").toString()).toLocalFile();
    const auto secondDialog=acquireRead(owner,root,secondRun,secondTicket,secondPath,"export");manager->setValue("LastBrowseLocation",secondPath);
    assert(!owner.request(root,claim(secondRun,secondTicket,secondDialog),secondDialog).isEmpty());
    manager->setValue("LastBrowseLocation",QString("/foreign/current-location"));
    assert(owner.request(root,call("restore",secondRun),secondDialog).isEmpty());
    const auto conflict=owner.request(root,call("observe",secondRun),secondDialog);
    assert(conflict.value("restoreAttempted").toBool() && !conflict.value("restored").toBool());
    assert(manager->value("LastBrowseLocation")==QVariant(QString("/foreign/current-location")));
    assert(owner.request(root,call("release",secondRun),secondDialog).isEmpty());
    QTextStream(stdout)<<QJsonDocument::fromVariant(conflict).toJson(QJsonDocument::Compact)<<'\n';
    const QString thirdRun(32,'4'),thirdTicket(32,'5');manager->setValue("LastBrowseLocation",QString());
    assert(!owner.request(root,call("reserve",thirdRun),{}).isEmpty());const auto thirdPath=QUrl(stage(root,thirdRun,thirdTicket).value("directory").toString()).toLocalFile();
    const auto thirdDialog=acquireRead(owner,root,thirdRun,thirdTicket,thirdPath);manager->setValue("LastBrowseLocation",thirdPath);
    assert(!owner.request(root,claim(thirdRun,thirdTicket,thirdDialog),thirdDialog).isEmpty());
    CachedHandle cached;SettingsTests::registerHandle(actual,&cached);assert(owner.request(root,call("restore",thirdRun),thirdDialog).isEmpty());SettingsTests::removeHandle(actual);
    assert(manager->value("LastBrowseLocation")==QVariant(thirdPath));
    const QString fourthRun(32,'6'),fourthTicket(32,'7');const QByteArray rawOriginal("raw\0original",12);manager->setValue("LastBrowseLocation",rawOriginal);
    const auto rawReserved=owner.request(root,call("reserve",fourthRun),{});assert(rawReserved.value("original").toMap().value("typeId").toInt()==QMetaType::QByteArray);
    const auto fourthPath=QUrl(stage(root,fourthRun,fourthTicket).value("directory").toString()).toLocalFile();const auto fourthDialog=acquireRead(owner,root,fourthRun,fourthTicket,fourthPath);
    assert(manager->value("LastBrowseLocation").userType()==QMetaType::QString); // Original Handle really coerced the raw QByteArray.
    manager->setValue("LastBrowseLocation",fourthPath);assert(!owner.request(root,claim(fourthRun,fourthTicket,fourthDialog),fourthDialog).isEmpty());
    const auto rawRestored=owner.request(root,call("restore",fourthRun),fourthDialog);assert(rawRestored.value("restored").toBool());
    assert(manager->value("LastBrowseLocation").userType()==QMetaType::QByteArray && manager->value("LastBrowseLocation").toByteArray()==rawOriginal);
    SettingsTests::barrier(actual);disk.sync();assert(disk.value("LastBrowseLocation").userType()==QMetaType::QByteArray && disk.value("LastBrowseLocation").toByteArray()==rawOriginal);
    assert(owner.request(root,call("reserve",QString(32,'8')),{}).isEmpty());
    QTextStream(stdout)<<QJsonDocument::fromVariant(rawRestored).toJson(QJsonDocument::Compact)<<'\n';
    for(int count=1;count<512;++count){assert(!getter.featureCreateBrowseSetting(call("observe",QString(32,'9'))).value("source").toMap().isEmpty());}
    assert(getter.featureCreateBrowseSetting(call("observe",QString(32,'9'))).isEmpty());assert(getter.featureCreateBrowseSetting(firstCommand)==firstGetter);
    getter._featureLifecycle.reset();assert(getter.featureCreateBrowseSetting(firstCommand).isEmpty());
    overte::e2e::CreateBrowseSettingOwner canceledRead;const QString canceledRun(32,'8'),canceledTicket(32,'9');
    assert(!canceledRead.request(root,call("reserve",canceledRun),{}).isEmpty());
    const auto canceledPath=QUrl(stage(root,canceledRun,canceledTicket).value("directory").toString()).toLocalFile();
    const auto canceledDialog=acquireRead(canceledRead,root,canceledRun,canceledTicket,canceledPath);
    assert(manager->value("LastBrowseLocation").userType()==QMetaType::QString);
    const auto canceledRestored=canceledRead.request(root,call("restore",canceledRun),canceledDialog);assert(canceledRestored.value("restored").toBool());
    assert(manager->value("LastBrowseLocation").userType()==QMetaType::QByteArray && manager->value("LastBrowseLocation").toByteArray()==rawOriginal);
    assert(canceledRead.request(root,call("release",canceledRun),canceledDialog).isEmpty());
    assert(canceledRestored.value("writer").toMap().value("raw").toMap()!=canceledRestored.value("original").toMap());
    SettingsTests::barrier(actual);disk.sync();
    const auto onDisk=disk.value("LastBrowseLocation");
    QTextStream(stderr)<<"Cancel raw types: manager="<<manager->value("LastBrowseLocation").userType()<<" writer="
        <<canceledRestored.value("writer").toMap().value("raw").toMap().value("typeId").toInt()<<" disk="<<onDisk.userType()<<" bytes="<<onDisk.toByteArray().size()<<'\n';
    assert(onDisk.userType()==QMetaType::QString && onDisk.toByteArray()!=rawOriginal); // Original writer loss is retained, not repaired.
    QTextStream(stdout)<<QJsonDocument::fromVariant(canceledRestored).toJson(QJsonDocument::Compact)<<'\n';
    SettingsTests::stop(actual);manager.reset();DependencyManager::destroy<Setting::Manager>();SettingsTests::destroy(actual);return 0;
}
