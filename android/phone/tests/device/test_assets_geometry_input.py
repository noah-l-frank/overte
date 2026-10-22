"""Compile actual GeometryReader/renderer measurement blocks with Qt endpoints.

The immutable input class and unchanged source blocks execute here; model,
geometry and baker endpoints are explicit synthetic objects. This does not
compile the full serializers, renderer, Asset Server or Android application.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[4]
STUB=r'''
#include <QCoreApplication>
#include <QJsonDocument>
#include <QMutex>
#include <QMutexLocker>
#include <QThread>
#include <memory>
#include <thread>
#include <atomic>
#include <iostream>
#include "libraries/shared/src/E2EGeometryInput.h"
struct HFM {QString originalURL;std::shared_ptr<const overte::e2e::GeometryInputOriginal> e2eGeometryInput;};
struct Geometry {std::shared_ptr<HFM>hfm=std::make_shared<HFM>();bool isHFMModelLoaded()const{return true;}
 const HFM&getHFMModel()const{return *hfm;}QString e2eGeometryInstance()const{return QString(32,'c');}
 QVariantMap e2eCreateTextures()const{return {{"complete",true},{"rows",QVariantList{}}};}};
struct Model {std::shared_ptr<Geometry>geometry=std::make_shared<Geometry>();
 std::shared_ptr<Geometry>getGeometry()const{return geometry;}QString e2eModelInstance()const{return QString(32,'d');}
 bool isLoaded()const{return true;}bool isVisible()const{return true;}bool isAddedToScene()const{return true;}};
struct RenderableModelEntityItem {std::shared_ptr<Model>model=std::make_shared<Model>();
 mutable QMutex _e2eCreateModelMutex;QVariantMap _e2eCreateModel;
 std::shared_ptr<Model>getModel()const{return model;}void e2eRecordOriginalModel();
 GETTER
};
void loadOriginal(const QUrl& _url,const QByteArray& _data,const std::shared_ptr<HFM>&processedHFMModel){
 WRITER
}
QVariantMap originalDraw(const std::shared_ptr<Model>&model){QVariantMap _e2eOriginalModel;
 DRAW
 return _e2eOriginalModel;
}
'''
MAIN=r'''
int main(int argc,char**argv){QCoreApplication app(argc,argv);RenderableModelEntityItem entity;
 auto hfm=entity.model->geometry->hfm;const QUrl obj("atp:/e2e-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/main.obj");
 const QByteArray bytes("actual bytes delivered to the reader");loadOriginal(obj,bytes,hfm);
 auto input=hfm->e2eGeometryInput->snapshot();const auto digest=[](const QByteArray& value){return QString::fromLatin1(QCryptographicHash::hash(value,QCryptographicHash::Sha256).toHex());};
 if(input.value("originalSha256")!=digest(bytes)||input.value("originalBytes")!=bytes.size()||input.value("sourceSha256")!=digest(obj.toString().toUtf8())||input.contains("base64"))return 1;
 // The OBJ serializer's truly empty originalURL remains empty. A passive
 // independent reader original qualifies its actual loaded input instead.
 entity.e2eRecordOriginalModel();auto record=entity.e2eOriginalModelObservation();auto geometry=record.value("geometry").toMap();
 if(geometry.value("sourcePresent")!=false||geometry.value("reader").toMap()!=input||!hfm->originalURL.isEmpty())return 2;
 auto draw=originalDraw(entity.model);if(draw.value("loadedSourcePresent")!=true||draw.value("loadedSourceSha256")!=input.value("sourceSha256"))return 3;
 // Existing serializer/trace semantics survive when the serializer has an
 // original URL (including compressed-source URL normalization).
 hfm->originalURL="atp:/actual-serializer-original.fbx";auto legacy=originalDraw(entity.model);
 if(legacy.value("loadedSourceSha256")!=digest(hfm->originalURL.toUtf8()))return 9;hfm->originalURL.clear();
 // An immutable original is not overwritten or retimed at later publication.
 loadOriginal(QUrl("atp:/foreign.fbx"),QByteArray("foreign bytes"),hfm);
 if(hfm->e2eGeometryInput->snapshot()!=input)return 4;
 auto copy=std::make_shared<HFM>(*hfm);if(copy->e2eGeometryInput->snapshot()!=input)return 5;
 auto refreshed=std::make_shared<HFM>();const QUrl baked("atp:/.baked/actual/asset.fbx");
 loadOriginal(baked,QByteArray("actual baked content"),refreshed);auto next=refreshed->e2eGeometryInput->snapshot();
 if(next.value("instance")==input.value("instance")||next.value("sourceSha256")!=digest(baked.toString().toUtf8())||next.value("originalSha256")==input.value("originalSha256"))return 6;
 // Only the established mutex-protected complete renderer copy reaches a
 // second thread. The real immutable original carries no shared mutable body.
 std::atomic<bool>done{false};std::atomic<int>bad{0};std::thread worker([&]{for(int i=0;i<2000;++i)entity.e2eRecordOriginalModel();done=true;});
 while(!done){auto actual=entity.e2eOriginalModelObservation().value("geometry").toMap();if(actual.value("reader").toMap()!=input)++bad;}
 worker.join();if(bad)return 7;
 auto none=std::make_shared<HFM>();loadOriginal(QUrl(),QByteArray(),none);if(!none->e2eGeometryInput->snapshot().isEmpty())return 8;
 std::cout<<QJsonDocument::fromVariant(QVariantMap{{"render",record},{"draw",draw},{"reader",input},{"refresh",next}}).toJson().toStdString();return 0;
}
'''


class AssetsGeometryInputTests(unittest.TestCase):
    def test_actual_reader_publication_renderer_copy_and_draw_source_use_immutable_originals(self):
        model=(ROOT/'libraries/model-networking/src/model-networking/ModelCache.cpp').read_text()
        start=model.index('        if (processedHFMModel && !processedHFMModel->e2eGeometryInput)')
        writer=model[start:model.index('\n#endif',start)]
        source=(ROOT/'libraries/entities-renderer/src/RenderableModelEntityItem.cpp').read_text()
        start=source.index('void RenderableModelEntityItem::e2eRecordOriginalModel()')
        method=source[start:source.index('\n#endif',start)]
        source=(ROOT/'libraries/entities-renderer/src/RenderableModelEntityItem.h').read_text()
        start=source.index('    QVariantMap e2eOriginalModelObservation()')
        getter=source[start:source.index('\nprivate:',start)]
        source=(ROOT/'libraries/render-utils/src/MeshPartPayload.cpp').read_text()
        start=source.index('    const auto& geometry = model->getGeometry();')
        draw=source[start:source.index('\n#endif',start)]
        flags=subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core'],text=True).split()
        build=ROOT/'build/assets-native-contract';build.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='geometry-',dir=build) as temporary:
            stage=Path(temporary);path=stage/'source.cpp'
            path.write_text(STUB.replace(' GETTER',getter).replace(' WRITER',writer).replace(' DRAW',draw)+method+MAIN)
            subprocess.run(['c++','-std=c++17','-fPIC','-pthread','-DOVERTE_E2E_FEATURE_TESTS','-I'+str(ROOT),str(path),'-o',str(stage/'geometry'),*flags],check=True,timeout=60)
            result=subprocess.run([str(stage/'geometry')],check=True,capture_output=True,text=True,timeout=15)
            import json,sys
            sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
            from overte_phone_create_source import render_source
            original=json.loads(result.stdout);render_source(original['render'])
            self.assertNotIn('base64',original['reader']);self.assertNotEqual(original['reader']['instance'],original['refresh']['instance'])


if __name__=='__main__':unittest.main()
