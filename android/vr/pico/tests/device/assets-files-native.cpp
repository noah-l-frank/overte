// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include "PrivateAssetsFiles.h"
#include "AudioSettingsQueue.h"
#include <QTemporaryDir>
#include <QDateTime>
#include <QHash>
#include <QTimer>
#include <cassert>
#include <thread>
#include <iostream>
using overte::e2e::PrivateAssetsFiles;
struct Lifecycle {QVariantMap snapshot() const {return {{"present",true}};}};
class TestScriptingInterface:public QObject {
public:
    QVariantMap featurePicoAssetsFiles(const QVariantMap& command);
    QString _testResultsLocation,_featureObservationInstance{QString(32,'e')};
    std::shared_ptr<Lifecycle> _featureLifecycle;
    std::shared_ptr<overte::e2e::AudioSettingsQueue> _featureAssetsFilesQueue{std::make_shared<overte::e2e::AudioSettingsQueue>()};
    std::shared_ptr<PrivateAssetsFiles> _featureAssetsFiles{std::make_shared<PrivateAssetsFiles>()};
    quint64 _featureAssetsFilesSequence{0};QHash<QString,QVariantMap> _featureAssetsFilesCommands,_featureAssetsFilesResults;
};
#include "AssetsFilesMethod.inc"
int main(int argc,char** argv) {
    QCoreApplication app(argc,argv);QTemporaryDir directory;assert(directory.isValid());
    TestScriptingInterface source;source._testResultsLocation=directory.path();
    if(app.arguments().contains("--serve")) {
        source._featureLifecycle=std::make_shared<Lifecycle>();std::string line;
        while(std::getline(std::cin,line)) {
            const auto command=QJsonDocument::fromJson(QByteArray::fromStdString(line)).object().toVariantMap();
            const auto reply=source.featurePicoAssetsFiles(command);
            std::cout<<QJsonDocument(QJsonObject::fromVariantMap(reply)).toJson(QJsonDocument::Compact).constData()<<std::endl;
        }return 0;
    }
    const QString run(32,'a'),owner(64,'b');int next=0;
    QVariantMap call{{"schemaVersion",1},{"commandId",QString(32,'c')},{"action","feature-pico-assets-files"},
        {"runId",run},{"ownerToken",owner},{"operation","stage"}};
    QVariantMap files;for(const auto& name:PrivateAssetsFiles::inputs()) {files[name]=QString::fromLatin1((name+"-original").toUtf8().toBase64());}
    call["files"]=files;
    assert(source.featurePicoAssetsFiles(call).isEmpty());
    source._featureLifecycle=std::make_shared<Lifecycle>();
    const auto staged=source.featurePicoAssetsFiles(call);assert(!staged.isEmpty());
    const auto original=staged.value("source").toMap();assert(original.value("exists")==QVariant(true));
    assert(original.value("files").toList().size()==7);assert(source.featurePicoAssetsFiles(call)==staged);
    auto altered=call;altered["ownerToken"]=QString(64,'d');assert(source.featurePicoAssetsFiles(altered).isEmpty());
    const auto invoke=[&](const QString& operation,int generation=0) {
        auto command=call;command.remove("files");command["operation"]=operation;
        command["commandId"]=QString::number(++next,16).rightJustified(32,'0');
        if(generation) {command["stage"]=generation;}return source.featurePicoAssetsFiles(command);
    };
    assert(invoke("observe").value("source")==original);
    const auto root=QUrl(original.value("directory").toString()).toLocalFile();
    // Only controlled primary is unlinked. Exact companion originals survive.
    const auto primary=invoke("retire-primary").value("source").toMap();assert(primary.value("primaryRetired")==QVariant(true));
    assert(!QFileInfo::exists(root+"/gltf-bundle/main.gltf"));assert(QFileInfo::exists(root+"/gltf-bundle/mesh/triangle.bin"));
    assert(invoke("observe").value("source")==primary);
    const auto released=invoke("release").value("source").toMap();assert(released.value("retired")==QVariant(true));
    assert(!QFileInfo::exists(root));assert(!invoke("observe").isEmpty());
    auto restage=call;restage["commandId"]=QString(32,'f');assert(source.featurePicoAssetsFiles(restage).isEmpty());
    // Native lifetime cannot adopt an old live inode, even with original token.
    call["stage"]=1;call["commandId"]=QString(32,'d');const auto second=source.featurePicoAssetsFiles(call);
    assert(!second.isEmpty());const auto secondRoot=QUrl(second.value("source").toMap().value("directory").toString()).toLocalFile();
    PrivateAssetsFiles cold;auto read=call;read.remove("files");read["operation"]="observe";
    assert(cold.request(directory.path(),read).isEmpty());
    // Identical bytes on another inode never inherit observation/deletion authority.
    const auto path=secondRoot+"/obj-bundle/main.obj";QFile file(path);assert(file.open(QIODevice::ReadOnly));
    const auto bytes=file.readAll();file.close();assert(QFile::rename(path,directory.path()+"/held-original.obj"));assert(file.open(QIODevice::WriteOnly));
    assert(file.write(bytes)==bytes.size());file.close();assert(QFile::setPermissions(path,QFile::ReadOwner|QFile::WriteOwner));
    assert(invoke("observe",1).isEmpty());assert(invoke("release",1).isEmpty());assert(QFileInfo::exists(path));
    // Blocked GUI dispatch: timed-out queued mutation cannot execute later.
    auto workerCommand=read;workerCommand["stage"]=2;workerCommand["commandId"]=QString(32,'9');
    QVariantMap workerResult;std::thread worker([&]{workerResult=source.featurePicoAssetsFiles(workerCommand);});
    worker.join();assert(workerResult.isEmpty());assert(!source._featureAssetsFilesCommands.contains(workerCommand.value("commandId").toString()));
    QCoreApplication::processEvents();assert(!source._featureAssetsFilesCommands.contains(workerCommand.value("commandId").toString()));
    // Successful original foreign-thread marshaling uses GUI thread, not a moved surrogate.
    workerCommand["commandId"]=QString(32,'8');std::thread delivered([&]{workerResult=source.featurePicoAssetsFiles(workerCommand);});
    // Avoid shared QVariant polling: join only after GUI has serviced the actual callback.
    QTimer::singleShot(50,&app,&QCoreApplication::quit);app.exec();delivered.join();assert(!workerResult.isEmpty());
    assert(source._featureAssetsFilesQueue->settled());
    // Finite producer lifetime never evicts the original successful mutation.
    while(source._featureAssetsFilesCommands.size()<512) {
        workerCommand["commandId"]=QString::number(4096+source._featureAssetsFilesCommands.size(),16).rightJustified(32,'0');
        assert(!source.featurePicoAssetsFiles(workerCommand).isEmpty());
    }
    workerCommand["commandId"]=QString(32,'7');assert(source.featurePicoAssetsFiles(workerCommand).isEmpty());
    auto saved=call;saved.remove("stage");saved["commandId"]=QString(32,'c');assert(source.featurePicoAssetsFiles(saved)==staged);
    return 0;
}
