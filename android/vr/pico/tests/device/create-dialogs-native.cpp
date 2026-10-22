// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#define OVERTE_E2E_FEATURE_TESTS 1
#define ANDROID_APP_PICO_INTERFACE 1
#include "DialogHarness.h"
#include "PicoCreateFileControls.h"
#include <ui/NativeFieldInput.h>
#include <FileDialogHelper.h>
#include <QApplication>
#include <QQmlComponent>
#include <QSignalSpy>
#include <QTest>
#include <QFile>
#include <QDir>
#include <QTemporaryDir>
#include <QTextStream>
#include <QJsonDocument>
#include <cassert>
#include <atomic>
#include "CreateFileAdmission.inc"
#include "OriginalDialogs.inc"
#include "moc_DialogHarness.cpp"

QQuickItem* named(QQuickItem* root,const QString& name) {
    if (root->objectName()==name) {return root;}
    for (auto child:root->childItems()) {if (auto result=named(child,name)) {return result;}}
    return nullptr;
}
QVariantMap row(const QVariantMap& source,const QString& id) {
    for (const auto& value:source.value("dialogs").toList()) {if (value.toMap().value("id").toString()==id) {return value.toMap();}}
    return {};
}
int main(int argc,char** argv) {
    QApplication app(argc,argv);assert(argc>=3);QQmlEngine engine;engine.addImportPath(QString::fromLocal8Bit(argv[1]));
    QTemporaryDir storage;assert(storage.isValid());const auto leaf="feature-create-"+QString(32,'a')+'-'+QString(32,'b');
    assert(QDir(storage.path()).mkdir(leaf));const auto directory=storage.path()+'/'+leaf;
    QFile input(directory+"/entity-import.json");assert(input.open(QIODevice::WriteOnly));input.write("{\"DataVersion\":3,\"Entities\":[]}");input.close();
    FileDialogHelper helper;engine.rootContext()->setContextProperty("fileDialogHelper",&helper);
    engine.rootContext()->setContextProperty("fixtureDirectory",QUrl::fromLocalFile(directory));
    QQmlComponent component(&engine,QUrl::fromLocalFile(QString::fromLocal8Bit(argv[1])+"/Host.qml"));
    auto host=qobject_cast<QQuickItem*>(component.create());assert(host);
    QQuickWindow window;window.resize(900,1000);host->setParentItem(window.contentItem());host->setWidth(900);host->setHeight(1000);
    window.show();window.requestActivate();QTest::qWait(50);
    offscreen=std::make_shared<OffscreenUi>();tablets=std::make_shared<TabletScriptingInterface>();tablets->tablet.root=host;
    WindowScriptingInterface product;TestScriptingInterface acquisition;QString actualResult;QVariantMap within;
    QList<QVariantMap> packets;
    const auto capture=[&]{const auto original=acquisition.featureCreateDialogs(QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-'));
        packets.append(original);return original.value("source").toMap();};
    QObject::connect(&product,&WindowScriptingInterface::browseChanged,[&](const QString& result){actualResult=result;within=capture();});
    auto& inventory=overte::e2e::createUiInventory();
    product.browseAsync("Select .json to Import","","*.json");QTest::qWait(40);
    QPointer<QQuickItem> picker=named(host,"nativeFileBrowser");assert(picker);
    inventory.observe(host,&window);auto original=capture();assert(original.value("complete").toBool());
    const auto binding=offscreen->featureCreateDialogIdentity(picker);const auto id=binding.value("dialogId").toString();assert(id.size()==32);
    const auto originalUi=inventory.observe(host,&window);
    const auto originalBindings=inventory.dialogBindings([&](QQuickItem* item){return offscreen->featureCreateDialogIdentity(item);});
    assert(originalBindings.value("complete").toBool());assert(originalBindings.value("bindings").toArray().size()==1);
    assert(originalBindings.value("bindings").toArray().first().toObject().value("uiRootId").toString()==inventory.identity(picker));
    assert(originalBindings.value("bindings").toArray().first().toObject().value("native").toObject()==QJsonObject::fromVariantMap(binding));
    auto pending=row(original,id);assert(pending.value("pending").toBool() && pending.value("dispatches").toInt()==0);
    assert(pending.value("listenerAlive").toBool() && pending.value("rootAlive").toBool() && pending.value("contextAlive").toBool());
    assert(binding.value("rootId")==pending.value("rootId"));
    assert(pending.value("browseSettingRead").toMap().value("before").toMap().contains("raw"));
    assert(pending.value("browseSettingRead").toMap().value("after").toMap().contains("raw"));
    assert(original.value("createDialogSourceVersion")==QVariant(3) && pending.value("responseSha256").isNull());
    assert(originalCreateFileInput(named(picker,"fileCancel"),&window,"create-file.cancel","activate",{}).value("performed").toBool());
    const auto running=row(within,id);assert(running.value("pending").toBool() && running.value("dispatches").toInt()==1);
    assert(running.value("enteredEpochMs").toLongLong()>0 && running.value("returnedEpochMs").toLongLong()==0);
    QTest::qWait(60);assert(!picker);const auto canceled=row(capture(),id);
    assert(!canceled.value("pending").toBool() && canceled.value("dispatches").toInt()==0);
    assert(!canceled.value("listenerAlive").toBool() && !canceled.value("rootAlive").toBool());
    assert(canceled.value("returnedEpochMs").toLongLong()>=running.value("enteredEpochMs").toLongLong());
    assert(canceled.value("responseSha256")==QString::fromLatin1(QCryptographicHash::hash(QByteArray(),QCryptographicHash::Sha256).toHex()));
    // The source reports Qt's actual context lifetime; it never destroys an
    // internal context or equates a missing view with complete retirement.
    assert(canceled.value("contextAlive").userType()==QMetaType::Bool);
    product.browseAsync("Select .json to Import",directory,"*.json");QTest::qWait(40);picker=named(host,"nativeFileBrowser");assert(picker);
    inventory.observe(host,&window);const auto acceptedId=offscreen->featureCreateDialogIdentity(picker).value("dialogId").toString();assert(acceptedId!=id);
    assert(originalCreateFileInput(named(picker,"fileNameInput"),&window,"create-file.name","activate",{}).value("performed").toBool());
    assert(originalCreateFileInput(named(picker,"fileNameInput"),&window,"create-file.name","replace",{{"text",directory+"/entity-import.json"}}).value("performed").toBool());
    assert(originalCreateFileInput(named(picker,"fileAccept"),&window,"create-file.accept","activate",{}).value("performed").toBool());
    QTest::qWait(60);assert(actualResult==directory+"/entity-import.json");assert(!picker);
    assert(row(offscreen->featureCreateDialogs(),acceptedId).value("returnedEpochMs").toLongLong()>0);
    assert(row(offscreen->featureCreateDialogs(),acceptedId).value("responseSha256")==QString::fromLatin1(QCryptographicHash::hash(actualResult.toUtf8(),QCryptographicHash::Sha256).toHex()));
    QObject::connect(&product,&WindowScriptingInterface::saveFileChanged,[&](const QString& result){actualResult=result;within=capture();});
    product.saveAsync("Select Where to Save",directory,"*.json");QTest::qWait(40);picker=named(host,"nativeFileBrowser");assert(picker);
    inventory.observe(host,&window);const auto exportId=offscreen->featureCreateDialogIdentity(picker).value("dialogId").toString();
    assert(originalCreateFileInput(named(picker,"fileNameInput"),&window,"create-file.name","activate",{}).value("performed").toBool());
    assert(originalCreateFileInput(named(picker,"fileNameInput"),&window,"create-file.name","replace",{{"text",directory+"/export.json"}}).value("performed").toBool());
    assert(originalCreateFileInput(named(picker,"fileAccept"),&window,"create-file.accept","activate",{}).value("performed").toBool());
    QTest::qWait(60);assert(actualResult==directory+"/export.json" && !QFileInfo::exists(actualResult));assert(!picker);
    const auto exported=row(offscreen->featureCreateDialogs(),exportId);assert(exported.value("role")==QVariant("export") && !exported.value("pending").toBool());
    assert(row(within,exportId).value("dispatches").toInt()==1);
    assert(exported.value("responseSha256")==QString::fromLatin1(QCryptographicHash::hash(actualResult.toUtf8(),QCryptographicHash::Sha256).toHex()));
    assert(offscreen->featureCreateDialogs().value("dialogs").toList().size()==3);
    // Product provenance: Application_Setup creates the shared Window on the
    // GUI thread; Application registers that same object in each Script engine.
    // ScriptObjectV8Proxy invokes void QMetaMethods with DirectConnection from
    // the Script thread. Preserve receiver affinity and use that original route.
    QThread scriptThread;QObject caller;caller.moveToThread(&scriptThread);scriptThread.start();
    assert(product.thread()==app.thread());std::atomic<bool> workerCalled {false},workerAnswered {false};QVariantMap workerWithin;
    QObject::connect(&product,&WindowScriptingInterface::browseChanged,&product,[&](const QString&) {
        assert(QThread::currentThread()==app.thread());workerWithin=capture();workerAnswered.store(true);
    });
    assert(QMetaObject::invokeMethod(&caller,[&]{
        assert(QThread::currentThread()==&scriptThread && product.thread()==app.thread());
        const auto index=product.metaObject()->indexOfMethod("browseAsync(QString,QString,QString)");assert(index>=0);
        const auto method=product.metaObject()->method(index);
        assert(method.invoke(&product,Qt::DirectConnection,Q_ARG(QString,QString("Select .json to Import")),Q_ARG(QString,directory),Q_ARG(QString,QString("*.json"))));
        workerCalled.store(true);
    },Qt::QueuedConnection));
    for(int attempt=0;attempt<100 && !workerCalled.load();++attempt){QTest::qWait(10);}assert(workerCalled.load());
    QTest::qWait(40);picker=named(host,"nativeFileBrowser");assert(picker);inventory.observe(host,&window);
    const auto workerId=offscreen->featureCreateDialogIdentity(picker).value("dialogId").toString();assert(!workerId.isEmpty());
    assert(originalCreateFileInput(named(picker,"fileCancel"),&window,"create-file.cancel","activate",{}).value("performed").toBool());
    assert(workerAnswered.load() && workerWithin.value("complete").toBool());
    assert(row(workerWithin,workerId).value("dispatches").toInt()==1 && row(workerWithin,workerId).value("pending").toBool());
    QTest::qWait(60);assert(!picker);const auto workerAfter=row(capture(),workerId);
    assert(!workerAfter.value("pending").toBool() && workerAfter.value("dispatches").toInt()==0
        && workerAfter.value("returnedEpochMs").toLongLong()>0 && !workerAfter.value("listenerAlive").toBool());
    assert(QMetaObject::invokeMethod(&caller,[&]{caller.moveToThread(app.thread());},Qt::BlockingQueuedConnection));
    scriptThread.quit();assert(scriptThread.wait(1000));
    capture();
    const auto first=packets.first();assert(acquisition.featureCreateDialogs(first.value("requestId").toString())==first);
    const auto beforeGets=offscreenGets;offscreenAvailable=false;
    assert(acquisition.featureCreateDialogs(QString(32,'b')).isEmpty() && offscreenGets==beforeGets);offscreenAvailable=true;
    const auto existing=acquisition._featureCreateDialogsResults.size();
    for(int i=0;i<512-existing;++i){assert(!acquisition.featureCreateDialogs(QString::number(i+1,16).rightJustified(32,'0')).isEmpty());}
    assert(acquisition.featureCreateDialogs(QString(32,'c')).isEmpty());assert(acquisition.featureCreateDialogs(first.value("requestId").toString())==first);
    for(const auto& packet:packets){QTextStream(stdout)<<QJsonDocument::fromVariant(packet).toJson(QJsonDocument::Compact)<<'\n';}
    QTextStream(stdout)<<QJsonDocument(QJsonObject{{"uiInventory",originalUi},{"dialogBindings",originalBindings}}).toJson(QJsonDocument::Compact)<<'\n';
    tablets.reset();offscreen.reset();delete host;return 0;
}
