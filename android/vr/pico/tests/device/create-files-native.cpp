// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include "PrivateCreateFiles.h"
#include <QCoreApplication>
#include <QTemporaryDir>
#include <QFile>
#include <QHash>
#include <QDateTime>
#include <QThread>
#include <memory>
#include <cassert>

using overte::e2e::PrivateCreateFiles;
struct Lifecycle {
    QVariantMap snapshot() const { return {{"present", true}}; }
};
// Substitute only the application lifecycle holder. The original production
// method is extracted at compile time, including its real gates/cache/clocks.
class TestScriptingInterface : public QObject {
public:
    QVariantMap featureCreateFiles(const QVariantMap& command);
    QString _testResultsLocation, _featureObservationInstance {QString(32, 'e')};
    std::shared_ptr<Lifecycle> _featureLifecycle;
    quint64 _featureCreateFilesSequence {0};
    QHash<QString, QVariantMap> _featureCreateFilesCommands, _featureCreateFilesResults;
};
#include "CreateFilesMethod.inc"

int main(int argc, char** argv) {
    QCoreApplication app(argc, argv);
    QTemporaryDir directory; assert(directory.isValid());
    const QString run(32, 'a'), ticket(32, 'b'), owner(64, 'c');
    QVariantMap command{{"schemaVersion",1},{"commandId",QString(32,'d')},{"action","feature-script-files"},
        {"sourceRole","create-json-v1"},{"runId",run},{"ticket",ticket},{"ownerToken",owner},{"operation","locate"}};
    const auto call=[&](const QVariantMap& value){return PrivateCreateFiles::request(directory.path(),value);};
    auto located=call(command); assert(located.value("exists")==QVariant(false));
    const auto root=QUrl(located.value("directory").toString()).toLocalFile();
    const QByteArray input("{\"DataVersion\":3,\"Entities\":[{\"type\":\"Model\",\"name\":\"owned-input\"}]}");
    command["operation"]="stage"; command["files"]=QVariantMap{{"entity-import.json",QString::fromLatin1(input.toBase64())}};
    assert(call(command).value("performed")==QVariant(true));
    assert(call(command).isEmpty()); // Never adopt an uncertain existing stage.
    assert(!QFileInfo::exists(root+"/export.json"));
    command.remove("files"); command["operation"]="observe";
    auto observed=call(command); assert(observed.value("exists")==QVariant(true));
    auto rows=observed.value("files").toList(); assert(rows.size()==2);
    assert(QByteArray::fromBase64(rows[0].toMap().value("base64").toByteArray())==input);
    assert(!rows[0].toMap().value("inode").toString().isEmpty());
    assert(rows[1].toMap().value("exists")==QVariant(false));
    auto foreign=command; foreign["ownerToken"]=QString(64,'f'); assert(call(foreign).isEmpty());
    foreign=command; foreign["sourceRole"]="scripts"; assert(call(foreign).isEmpty());
    foreign=command; foreign["schemaVersion"]=true; assert(call(foreign).isEmpty());
    // Simulate only the product file boundary. The storage implementation never
    // writes these bytes; independent native readback must preserve them exactly.
    const QByteArray output("{\"DataVersion\":0,\"Entities\":[{\"name\":\"actual-export\"}]}\n");
    QFile exported(root+"/export.json"); assert(exported.open(QIODevice::WriteOnly));
    assert(exported.write(output)==output.size()); exported.close();
    observed=call(command); rows=observed.value("files").toList();
    assert(QByteArray::fromBase64(rows[1].toMap().value("base64").toByteArray())==output);
    const auto digest=rows[1].toMap().value("sha256");
    command["operation"]="release"; command["exportSha256"]="";
    assert(call(command).isEmpty()); assert(QFileInfo::exists(root+"/entity-import.json"));
    command["exportSha256"]=QString(64,'0'); assert(call(command).isEmpty());
    command["exportSha256"]=digest; assert(call(command).value("performed")==QVariant(true));
    command.remove("exportSha256"); command["operation"]="observe";
    assert(call(command).value("exists")==QVariant(false));
    assert(!QFileInfo::exists(root));
    // Fresh private role: changed inputs, links and foreign inventories cannot
    // be observed as originals or authorized for deletion.
    command["operation"]="stage"; command["files"]=QVariantMap{{"entity-import.json",QString::fromLatin1(input.toBase64())}};
    assert(call(command).value("performed")==QVariant(true));
    command.remove("files"); command["operation"]="observe";
    QFile changed(root+"/entity-import.json"); assert(changed.open(QIODevice::WriteOnly|QIODevice::Truncate));
    assert(changed.write(input+" ")==input.size()+1); changed.close(); assert(call(command).isEmpty());
    assert(changed.open(QIODevice::WriteOnly|QIODevice::Truncate)); changed.write(input); changed.close();
    assert(::symlink(QFile::encodeName(root+"/entity-import.json").constData(), QFile::encodeName(root+"/export.json").constData())==0);
    assert(call(command).isEmpty()); assert(QFile::remove(root+"/export.json"));
    assert(::link(QFile::encodeName(root+"/entity-import.json").constData(), QFile::encodeName(root+"/export.json").constData())==0);
    assert(call(command).isEmpty()); assert(QFile::remove(root+"/export.json"));
    QFile unexpected(root+"/foreign.txt"); assert(unexpected.open(QIODevice::WriteOnly)); unexpected.write("foreign"); unexpected.close();
    assert(call(command).isEmpty()); assert(QFileInfo::exists(root+"/entity-import.json"));
    QTemporaryDir sourceDirectory; assert(sourceDirectory.isValid());
    TestScriptingInterface source;
    command["operation"]="stage"; command["files"]=QVariantMap{{"entity-import.json",QString::fromLatin1(input.toBase64())}};
    source._testResultsLocation=sourceDirectory.path();
    assert(source.featureCreateFiles(command).isEmpty()); // Real lifecycle guard.
    source._featureLifecycle=std::make_shared<Lifecycle>();
    const auto staged=source.featureCreateFiles(command);
    assert(staged.value("source").toMap().value("performed")==QVariant(true));
    assert(staged.value("processId").toLongLong()==QCoreApplication::applicationPid());
    assert(staged.value("capturedEpochMs").toLongLong()>=staged.value("requestedEpochMs").toLongLong());
    assert(source.featureCreateFiles(command)==staged);
    auto observe=command;observe.remove("files");observe["operation"]="observe";observe["commandId"]=QString(32,'f');
    const auto observedSource=source.featureCreateFiles(observe);
    assert(observedSource.value("sequence").toULongLong()>staged.value("sequence").toULongLong());
    assert(source.featureCreateFiles(command)==staged); // Original bytes/times survive another query.
    auto changedCommand=command;changedCommand["ticket"]=QString(32,'0');
    assert(source.featureCreateFiles(changedCommand).isEmpty());
    for(int index=0;index<510;++index){observe["commandId"]=QString::number(index,16).rightJustified(32,'0');assert(!source.featureCreateFiles(observe).isEmpty());}
    observe["commandId"]=QString(32,'1');assert(source.featureCreateFiles(observe).isEmpty());
    assert(source.featureCreateFiles(command)==staged); // Bound exhaustion never evicts old originals.
    return 0;
}
