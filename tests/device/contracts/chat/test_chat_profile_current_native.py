"""Actual Manager/moc/worker/current-owner source; the closed UI is a seam."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import importlib.util
import json
import sys
import unittest

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tests/device'))
from adapters.native_chat_profile_current import validate

spec=importlib.util.spec_from_file_location('original_chat_settings_compiler',Path(__file__).with_name('test_chat_settings_barrier.py'))
compiler=importlib.util.module_from_spec(spec);spec.loader.exec_module(compiler)

CURRENT=r'''
#include "tests/device/native/ChatProfileOwner.h"
#include <QTemporaryDir>
#include <QJsonDocument>
#include <QJsonObject>
#include <cassert>
#include <iostream>
class OwnedManager:public Setting::Manager {public:~OwnedManager(){terminateThread();}};
int main(int argc,char** argv) {
    QCoreApplication app(argc,argv);QTemporaryDir scratch;assert(scratch.isValid());
    QCoreApplication::setOrganizationName("OverteActualCurrentProfile");QCoreApplication::setApplicationName("Settings");
    QSettings::setDefaultFormat(QSettings::IniFormat);QSettings::setPath(QSettings::IniFormat,QSettings::UserScope,scratch.path());
    assert(::chmod(QFile::encodeName(scratch.path()).constData(),0700)==0);
    assert(QDir().mkpath(scratch.path()+"/OverteActualCurrentProfile"));
    const QString run(32,'a');bool focused{false};qint64 sequence{0};
    auto view=[&](const QString& value) {
        return QVariantMap{{"chatViewVersion",2},{"runId",value},{"instance",QString(32,'e')},{"sequence",++sequence},
            {"processId",QCoreApplication::applicationPid()},{"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},
            {"source",QVariantMap{{"editorFocused",focused},{"editorHasDraft",false},
                {"keyboard",QVariantMap{{"available",true},{"visible",false}}},{"ui",QVariantMap{{"present",false}}}}}};
    };
    auto query=[&] {
        return QVariantMap{{"schemaVersion",1},{"commandId",QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')},
            {"runId",run},{"action","feature-chat-profile-current"}};
    };
    QVariantMap expected,oldSettings,packet;QString oldInstance;
    {
        OwnedManager manager;manager.setValue("ArmoredChat-Config",QVariantMap{{"enabled",true},{"privateMarker","original private configuration"}});
        assert(!manager.featureChatSnapshot().isEmpty());int writes{0};
        const auto signal=QObject::connect(&manager,&Setting::Manager::valueChanged,&manager,[&](QString,QVariant){++writes;},Qt::DirectConnection);
        overte::e2e::ChatProfileOwner source(&manager,view);const auto command=query(),value=source.current(command);
        assert(!value.isEmpty());assert(source.current(command).isEmpty());
        assert(value.contains("current") && !value.contains("owned") && !value.contains("original") && !value.contains("restored"));
        assert(!QJsonDocument::fromVariant(value).toJson().contains("original private configuration"));
        auto forbidden=query();forbidden.insert("expected",value.value("current"));assert(source.current(forbidden).isEmpty());
        forbidden=query();forbidden.insert("operation","acquire");assert(source.current(forbidden).isEmpty());
        focused=true;assert(source.current(query()).isEmpty());focused=false;
        const QVariantMap inspect{{"schemaVersion",1},{"commandId",QString(32,'f')},{"runId",run},
            {"action","feature-chat-profile"},{"operation","inspect"}};
        assert(source.request(inspect).isEmpty()); // Passive current never acquired an original owner.
        expected=value.value("current").toMap();oldSettings=value.value("settings").toMap();oldInstance=value.value("instance").toString();
        assert(writes==0);QObject::disconnect(signal);
    }
    {
        OwnedManager manager;overte::e2e::ChatProfileOwner source(&manager,view);const auto before=manager.featureChatSnapshot();
        assert(!before.isEmpty());int writes{0};
        const auto signal=QObject::connect(&manager,&Setting::Manager::valueChanged,&manager,[&](QString,QVariant){++writes;},Qt::DirectConnection);
        packet=source.current(query());assert(!packet.isEmpty());assert(packet.value("current").toMap()==expected);
        const auto current=packet.value("settings").toMap();
        assert(current.value("instance")!=oldSettings.value("instance") && current.value("writerInstance")!=oldSettings.value("writerInstance"));
        assert(packet.value("instance").toString()!=oldInstance);
        assert(manager.featureChatSnapshot().value("mutationSequence")==before.value("mutationSequence"));assert(writes==0);
        manager.setValue("ArmoredChat-Config",QVariantMap{{"enabled",false}});
        const auto changed=source.current(query());assert(!changed.isEmpty() && changed.value("current").toMap()!=expected);
        assert(!changed.contains("restored") && !changed.contains("original"));
        manager.setValue("ArmoredChat-Messages",QVariantList{QString("unowned actual cache and worker history")});
        assert(source.current(query()).isEmpty());manager.remove("ArmoredChat-Messages");assert(!source.current(query()).isEmpty());
        // Independent raw physical mutation: actual cache/worker remain empty.
        // A current packet must not call their emptiness physical-file proof.
        QSettings settingPath;const auto path=settingPath.fileName();QFile file(path);assert(file.open(QIODevice::WriteOnly|QIODevice::Truncate));
        if (QSettings::defaultFormat()==QSettings::IniFormat)file.write("[General]\nArmoredChat-Messages=unowned physical row\n");
        else file.write(QJsonDocument(QJsonObject{{"ArmoredChat-Messages","unowned physical row"}}).toJson(QJsonDocument::Indented));
        file.close();assert(source.current(query()).isEmpty());QObject::disconnect(signal);
    }
    std::cout<<QJsonDocument::fromVariant(packet).toJson(QJsonDocument::Compact).constData()<<std::endl;
}
'''


class CurrentNativeTests(unittest.TestCase):
    def compile_current(self,json_format):
        program=CURRENT.replace('QSettings::IniFormat','JSON_FORMAT') if json_format else CURRENT
        # Keep the INI branch discriminator literal when selecting registered JSON.
        if json_format:program=program.replace('QSettings::defaultFormat()==JSON_FORMAT','QSettings::defaultFormat()==QSettings::IniFormat')
        output=compiler.SettingsBarrierTests().compile_manager(program)
        value=json.loads(output);request=dict(schemaVersion=1,commandId=value['commandId'],runId=value['runId'],action='feature-chat-profile-current')
        validate(value,request,value['processId'],value['capturedEpochMs'])
        self.assertNotIn('original',value);self.assertNotIn('owned',value);self.assertNotIn('restored',value)
    def test_actual_ini_current_profile_cold_manager_worker_and_original_dto(self):self.compile_current(False)
    def test_actual_registered_json_current_profile_cold_manager_worker_and_original_dto(self):self.compile_current(True)


if __name__=='__main__':unittest.main()
