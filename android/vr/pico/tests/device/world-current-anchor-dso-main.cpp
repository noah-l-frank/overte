// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Root's actual032 hidden/RTLD_LOCAL counter, extended with foreign nonce data.
#include <QCoreApplication>
#include <QVariantMap>
#include <dlfcn.h>
#include <cassert>
#include <cstdio>
int main(int argc,char**argv){
    QCoreApplication app(argc,argv);assert(argc==3);
    auto a=dlopen(argv[1],RTLD_NOW|RTLD_LOCAL),b=dlopen(argv[2],RTLD_NOW|RTLD_LOCAL);assert(a && b);
    using Factory=const void*(*)(const QVariantMap&);
    auto x=reinterpret_cast<Factory>(dlsym(a,"original_anchor")),y=reinterpret_cast<Factory>(dlsym(b,"original_anchor"));assert(x && y);
    QVariantMap command{{"schemaVersion",1},{"commandId",QString(32,'3')},{"action","pico-world-web"},{"operation","observe-current-document"},
        {"ownerToken",QString(32,'2')},{"runId",QString(32,'1')},{"fixtureUrl","http://127.0.0.1/feature-fixture/v1/runs/"+QString(32,'1')+"/"}};
    const auto first=x(command),again=x(command),second=y(command);assert(first && first==again && first==second);
    auto changed=command;changed.insert("ownerToken",QString(32,'4'));assert(!x(changed) && !y(changed));
    assert(x(command)==first && y(command)==first);
    changed=command;changed.insert("commandId",QString(32,'5'));assert(x(changed) && x(changed)!=first && x(changed)==y(changed));
    puts("PASS actual exported factory: same nonce stable/equal across independent hidden RTLD_LOCAL DSOs, foreign command refused");
    auto inputA=reinterpret_cast<Factory>(dlsym(a,"original_input_anchor")),inputB=reinterpret_cast<Factory>(dlsym(b,"original_input_anchor"));assert(inputA && inputB);
    command.insert("commandId",QString(32,'6'));command.insert("operation","measure-current-ray");
    command.insert("documentNonce",QString(32,'3'));command.insert("control","text");
    const auto input=inputA(command);assert(input && input==inputA(command) && input==inputB(command));
    changed=command;changed.insert("control","foreign");assert(!inputA(changed) && !inputB(changed));
    assert(inputA(command)==input && inputB(command)==input);
    changed=command;changed.insert("commandId",QString(32,'7'));changed.insert("operation","observe-current-focus");
    assert(inputA(changed) && inputA(changed)!=input && inputA(changed)==inputB(changed));
    puts("PASS actual exported current-input factory: ray/focus shared across independent hidden DSOs, exact command conflict refused");
    assert(dlclose(b)==0 && dlclose(a)==0);
}
