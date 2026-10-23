#!/usr/bin/env python3
"""Run the production pre-decode boundary against real Qt PNG/JPEG readers."""
from pathlib import Path
import shlex
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[4]
package=next((p for p in ['Qt6Gui','Qt5Gui'] if subprocess.run(['pkg-config','--exists',p]).returncode==0),None)
if not package:
    raise SystemExit('Qt Gui development files required for real-codec regression')
flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs',package],text=True))
source=(ROOT/'libraries/image/src/image/TextureProcessing.cpp').read_text()
function=source[source.index('Image readBoundedImage('):source.index('\nImage processRawImageData')]
mip_function=source[source.index('void assignGlesColorMips('):source.index('\nvoid convertImageToLDRTexture(')]
cache_source=(ROOT/'libraries/material-networking/src/material-networking/TextureCache.cpp').read_text()
cache_function=cache_source[cache_source.index('static bool phoneTinyColorPalette('):cache_source.index('\nstatic int phoneLoadingCacheNamespace(')]
header=(ROOT/'libraries/image/src/image/TextureProcessing.h').read_text()
texture_types=header[header.index('enum Type {'):header.index('};',header.index('enum Type {'))+2]
code=r'''
#include <cassert>
#include <atomic>
#include <map>
#include <algorithm>
#include <utility>
#include <QBuffer>
#include <QImage>
#include <QImageReader>
#include <QFile>
#include <QLoggingCategory>
#include "DecodeLimits.h"
Q_LOGGING_CATEGORY(imagelogging,"overte.test.image")
// Storage seam only: conversion/scaling below uses actual Qt pixels.
struct Image:QImage {
    using QImage::QImage;
    Image()=default;
    Image(const QImage& value):QImage(value){}
    unsigned getWidth()const{return width();}
    unsigned getHeight()const{return height();}
    size_t getByteCount()const{return sizeInBytes();}
    const unsigned char* getBits()const{return constBits();}
    Image getConvertedToFormat(Format format)const{return convertToFormat(format);}
    Image getScaled(std::pair<unsigned,unsigned> dims,Qt::AspectRatioMode ratio,Qt::TransformationMode mode)const {
        return scaled(dims.first,dims.second,ratio,mode);
    }
};
namespace gpu {
struct Texture {
    std::map<int,QByteArray> mips;
    int lastFace=-1;
    void assignStoredMip(int level,size_t bytes,const unsigned char* data) {
        mips[level]=QByteArray(reinterpret_cast<const char*>(data),bytes);
    }
    void assignStoredMipFace(int level,int face,size_t bytes,const unsigned char* data) {
        lastFace=face; assignStoredMip(level,bytes,data);
    }
};
}
using image::decodedImageFits;
struct TrackingReader:QImageReader {
    using QImageReader::QImageReader;
    unsigned calls=0;
    inline static unsigned totalCalls=0;
    QImage read(){++calls;++totalCalls;return QImageReader::read();}
};
#define QImageReader TrackingReader
FUNCTION
MIP_FUNCTION
namespace image { namespace TextureUsage { TEXTURE_TYPES } }
CACHE_FUNCTION
int main(int argc,char** argv) {
    assert(argc==2);
    QImage checker(argv[1]); assert(checker.size()==QSize(2,2));
    QFile originalFile(argv[1]); assert(originalFile.open(QIODevice::ReadOnly));
    const QByteArray originalBytes=originalFile.readAll();
    using namespace image::TextureUsage;
    for(auto type : {DEFAULT_TEXTURE,STRICT_TEXTURE,ALBEDO_TEXTURE,EMISSIVE_TEXTURE}) {
        assert(phoneTinyColorPalette(originalBytes,type));
    }
    for(auto type : {NORMAL_TEXTURE,BUMP_TEXTURE,ROUGHNESS_TEXTURE,SKY_TEXTURE,LIGHTMAP_TEXTURE}) {
        assert(!phoneTinyColorPalette(originalBytes,type));
    }
    assert(!phoneTinyColorPalette(QByteArray("invalid image"),DEFAULT_TEXTURE));
    for(int width : {4,5}) {
        QImage image(width,4,QImage::Format_RGB32); image.fill(Qt::cyan);
        QByteArray encoded; QBuffer buffer(&encoded); assert(buffer.open(QIODevice::WriteOnly));
        assert(image.save(&buffer,"PNG"));
        assert(phoneTinyColorPalette(encoded,ALBEDO_TEXTURE)==(width==4));
    }
    assert(TrackingReader::totalCalls==0); // Header inspection never allocates decoded pixels.

    std::atomic<bool> abort(false);
    gpu::Texture texture;
    assignGlesColorMips(&texture,Image(checker.convertToFormat(QImage::Format_ARGB32)),0,true,abort,-1);
    assert(texture.mips.size()==2);
    QImage rgba=checker.convertToFormat(QImage::Format_RGBA8888);
    assert(texture.mips.at(0)==QByteArray(reinterpret_cast<const char*>(rgba.constBits()),16));
    assert(texture.mips.at(1).size()==4);
    // Real RGBA channels and alpha survive; thin palettes retain all tail mips.
    QImage strip(4,1,QImage::Format_ARGB32);
    strip.fill(qRgba(231,17,59,123));
    gpu::Texture face;
    assignGlesColorMips(&face,Image(strip),2,true,abort,3);
    assert(face.lastFace==3 && face.mips.size()==3);
    assert(face.mips.at(2).size()==16 && face.mips.at(3).size()==8 && face.mips.at(4).size()==4);
    assert(static_cast<unsigned char>(face.mips.at(2)[0])==231);
    assert(static_cast<unsigned char>(face.mips.at(2)[1])==17);
    assert(static_cast<unsigned char>(face.mips.at(2)[2])==59);
    assert(static_cast<unsigned char>(face.mips.at(2)[3])==123);
    gpu::Texture single;
    assignGlesColorMips(&single,Image(checker),0,false,abort,-1); assert(single.mips.size()==1);
    abort=true; gpu::Texture canceled;
    assignGlesColorMips(&canceled,Image(checker),0,true,abort,-1); assert(canceled.mips.empty());

    for (const char* format : {"PNG","JPEG"}) {
        for (bool oversized : {false,true}) {
            QImage original(oversized?1025:1024,1024,QImage::Format_RGB32);
            original.fill(0xff184050);
            QByteArray bytes; QBuffer encoded(&bytes); encoded.open(QIODevice::WriteOnly);
            assert(original.save(&encoded,format)); encoded.close(); original=QImage();
            QBuffer input(&bytes); input.open(QIODevice::ReadOnly);
            TrackingReader reader(&input,format); assert(reader.canRead());
            Image result=readBoundedImage(reader,1024ULL*1024);
            assert(reader.calls==(oversized?0u:1u)); assert(result.isNull()==oversized);
            if(!oversized) { assert(result.size()==QSize(1024,1024)); }
        }
    }
}
'''.replace('MIP_FUNCTION',mip_function).replace('CACHE_FUNCTION',cache_function).replace('TEXTURE_TYPES',texture_types).replace('FUNCTION',function)
with tempfile.TemporaryDirectory(prefix='overte-qt-decode-') as tmp:
    cpp=Path(tmp)/'test.cpp';cpp.write_text(code); binary=Path(tmp)/'test'
    subprocess.run(['c++','-std=c++17','-fPIC',str(cpp),'-I'+str(ROOT/'libraries/image/src/image'),'-o',str(binary)]+flags,check=True,timeout=40)
    subprocess.run([str(binary),str(ROOT/'tests/device/fixture/parity/companions/gltf-bundle/textures/checker.png')],check=True,timeout=20)
print('PASS: targeted tiny-color metadata cache selector without pixel decode; original palette RGBA bytes, complete rectangular mip chain, face/base mip and cancellation; actual '+package+' PNG and JPEG decode accepted within budget; oversized images rejected before reader.read()')
