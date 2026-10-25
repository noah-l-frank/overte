// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#if !defined(OVERTE_E2E_FEATURE_TESTS)
#error This source belongs only to the separately selected Photos companion.
#endif
#import "PhotosOriginalChunks.h"
#import <CommonCrypto/CommonDigest.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <sys/stat.h>
#include <unistd.h>

static const NSUInteger OVTPhotosChunkBytes=512*1024;
static NSDictionary* OVTChunkClock(void) {
    return @{@"epochMs":@((long long)(NSDate.date.timeIntervalSince1970*1000)),@"monotonicMs":@((long long)(NSProcessInfo.processInfo.systemUptime*1000))};
}
static BOOL OVTChunkMatch(NSString* value,NSString* pattern) {
    return [value isKindOfClass:NSString.class] && [value rangeOfString:pattern options:NSRegularExpressionSearch].location!=NSNotFound;
}
static BOOL OVTChunkSame(struct stat a,struct stat b) {
    return a.st_dev==b.st_dev && a.st_ino==b.st_ino && a.st_mode==b.st_mode && a.st_nlink==b.st_nlink && a.st_size==b.st_size
        && a.st_mtimespec.tv_sec==b.st_mtimespec.tv_sec && a.st_mtimespec.tv_nsec==b.st_mtimespec.tv_nsec
        && a.st_ctimespec.tv_sec==b.st_ctimespec.tv_sec && a.st_ctimespec.tv_nsec==b.st_ctimespec.tv_nsec;
}
static NSString* OVTChunkRevision(struct stat value) {
    NSString* original=[NSString stringWithFormat:@"%llu:%llu:%u:%llu:%lld:%lld:%lld:%lld:%lld",(unsigned long long)value.st_dev,
        (unsigned long long)value.st_ino,(unsigned)value.st_mode,(unsigned long long)value.st_nlink,(long long)value.st_size,
        (long long)value.st_mtimespec.tv_sec,(long long)value.st_mtimespec.tv_nsec,(long long)value.st_ctimespec.tv_sec,(long long)value.st_ctimespec.tv_nsec];
    NSData* bytes=[original dataUsingEncoding:NSUTF8StringEncoding];unsigned char digest[CC_SHA256_DIGEST_LENGTH];CC_SHA256(bytes.bytes,(CC_LONG)bytes.length,digest);
    NSMutableString* hex=[NSMutableString new];for (NSUInteger index=0;index<sizeof(digest);++index) {[hex appendFormat:@"%02x",digest[index]];}return hex;
}
NSDictionary* OVTPhotosOriginalChunk(NSURL* root,NSDictionary* original,NSString* nonce,NSString* offset) {
    if (![NSThread isMainThread] || !root.isFileURL || ![original[@"phase"] isEqual:@"complete"]
            || !OVTChunkMatch(nonce,@"\\Aios-[0-9a-f]{32}\\z") || !OVTChunkMatch(offset,@"\\A(0|[1-9][0-9]{0,8})\\z")) {return nil;}
    unsigned long long position=offset.longLongValue,count=[original[@"byteCount"] unsignedLongLongValue];
    if (!count || count>256*1024*1024 || position>=count || position%OVTPhotosChunkBytes
            || ![root.lastPathComponent isEqual:[@"snapshot-photos-" stringByAppendingString:original[@"runId"]]]) {return nil;}
    NSTimeInterval began=NSProcessInfo.processInfo.systemUptime;NSDictionary* before=OVTChunkClock();
    int directory=open(root.path.fileSystemRepresentation,O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);
    if (directory<0) {return nil;}struct stat originalDirectory,actualDirectory,named,opened,after;
    BOOL okay=fstat(directory,&originalDirectory)==0 && S_ISDIR(originalDirectory.st_mode)
        && lstat(root.path.fileSystemRepresentation,&actualDirectory)==0 && OVTChunkSame(originalDirectory,actualDirectory)
        && fstatat(directory,"original.bytes",&named,AT_SYMLINK_NOFOLLOW)==0 && S_ISREG(named.st_mode) && named.st_nlink==1 && named.st_size==(off_t)count;
    int file=okay?openat(directory,"original.bytes",O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC):-1;
    okay=okay && file>=0 && fstat(file,&opened)==0 && OVTChunkSame(opened,named);
    NSUInteger length=(NSUInteger)MIN((unsigned long long)OVTPhotosChunkBytes,count-position);NSMutableData* bytes=[NSMutableData dataWithLength:length];NSUInteger readBytes=0;
    while (okay && readBytes<length) {
        ssize_t received=pread(file,(char*)bytes.mutableBytes+readBytes,length-readBytes,(off_t)(position+readBytes));
        if (received<0 && errno==EINTR) {continue;}
        if (received<=0 || NSProcessInfo.processInfo.systemUptime-began>=1.5) {okay=NO;break;}readBytes+=(NSUInteger)received;
    }
    okay=okay && fstat(file,&after)==0 && OVTChunkSame(opened,after)
        && fstatat(directory,"original.bytes",&named,AT_SYMLINK_NOFOLLOW)==0 && OVTChunkSame(opened,named)
        && fstat(directory,&actualDirectory)==0 && OVTChunkSame(originalDirectory,actualDirectory)
        && lstat(root.path.fileSystemRepresentation,&actualDirectory)==0 && OVTChunkSame(originalDirectory,actualDirectory);
    if (file>=0 && close(file)!=0) {okay=NO;}if (close(directory)!=0) {okay=NO;}
    NSDictionary* end=OVTChunkClock();if (!okay || NSProcessInfo.processInfo.systemUptime-began>=1.5) {return nil;}
    return @{@"snapshotPhotosChunkVersion":@1,@"nonce":nonce,@"runId":original[@"runId"],@"instance":original[@"instance"],
        @"processId":@(getpid()),@"basename":original[@"basename"],@"clockBefore":before,@"clockAfter":end,
        @"revision":OVTChunkRevision(opened),@"byteCount":@(count),@"sha256":original[@"sha256"],@"offset":@(position),
        @"eof":@(position+length==count),@"readerClosed":@YES,@"data":[bytes base64EncodedStringWithOptions:0]};
}
BOOL OVTPhotosPersistChunk(NSURL* documents,NSDictionary* packet) {
    if (!packet || !documents.isFileURL) {return NO;}NSData* bytes=[NSJSONSerialization dataWithJSONObject:packet options:0 error:nil];
    if (!bytes || bytes.length>720896) {return NO;}
    NSString* temporary=[documents.path stringByAppendingPathComponent:[@".chunk-" stringByAppendingString:NSUUID.UUID.UUIDString]];
    int file=open(temporary.fileSystemRepresentation,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);if (file<0) {return NO;}
    NSUInteger count=0;BOOL okay=YES;
    while (count<bytes.length) {ssize_t result=write(file,(const char*)bytes.bytes+count,bytes.length-count);if (result<0 && errno==EINTR) {continue;}if (result<=0) {okay=NO;break;}count+=(NSUInteger)result;}
    if (fsync(file)!=0) {okay=NO;}if (close(file)!=0) {okay=NO;}
    NSString* destination=[documents.path stringByAppendingPathComponent:@"snapshot-photos-chunk.json"];
    if (okay && rename(temporary.fileSystemRepresentation,destination.fileSystemRepresentation)!=0) {okay=NO;}
    int directory=open(documents.path.fileSystemRepresentation,O_RDONLY|O_DIRECTORY|O_NOFOLLOW);
    if (directory<0) {okay=NO;}else {if (fsync(directory)!=0) {okay=NO;}close(directory);}return okay;
}
