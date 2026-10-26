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
#include <dirent.h>
#include <string.h>
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
    return a.st_dev==b.st_dev && a.st_ino==b.st_ino && a.st_mode==b.st_mode && a.st_nlink==b.st_nlink && a.st_uid==b.st_uid && a.st_gid==b.st_gid && a.st_size==b.st_size
        && a.st_mtimespec.tv_sec==b.st_mtimespec.tv_sec && a.st_mtimespec.tv_nsec==b.st_mtimespec.tv_nsec
        && a.st_ctimespec.tv_sec==b.st_ctimespec.tv_sec && a.st_ctimespec.tv_nsec==b.st_ctimespec.tv_nsec;
}
NSString* OVTPhotosFileRevision(struct stat value) {
    NSString* original=[NSString stringWithFormat:@"%llu:%llu:%u:%llu:%u:%u:%lld:%lld:%lld:%lld:%lld",(unsigned long long)value.st_dev,
        (unsigned long long)value.st_ino,(unsigned)value.st_mode,(unsigned long long)value.st_nlink,(unsigned)value.st_uid,(unsigned)value.st_gid,(long long)value.st_size,
        (long long)value.st_mtimespec.tv_sec,(long long)value.st_mtimespec.tv_nsec,(long long)value.st_ctimespec.tv_sec,(long long)value.st_ctimespec.tv_nsec];
    NSData* bytes=[original dataUsingEncoding:NSUTF8StringEncoding];unsigned char digest[CC_SHA256_DIGEST_LENGTH];CC_SHA256(bytes.bytes,(CC_LONG)bytes.length,digest);
    NSMutableString* hex=[NSMutableString new];for (NSUInteger index=0;index<sizeof(digest);++index) {[hex appendFormat:@"%02x",digest[index]];}return hex;
}
NSDictionary* OVTPhotosOriginalChunk(NSURL* root,NSDictionary* original,NSString* nonce,NSString* offset) {
    if (![NSThread isMainThread] || !root.isFileURL || ![original[@"iosSnapshotDestinationVersion"] isEqual:@2]
            || !OVTChunkMatch(original[@"artifactRevision"],@"\\A[a-f0-9]{64}\\z") || ![original[@"phase"] isEqual:@"complete"]
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
    okay=okay && file>=0 && fstat(file,&opened)==0 && OVTChunkSame(opened,named)
        && opened.st_uid==geteuid() && (opened.st_mode&0777)==0600 && [OVTPhotosFileRevision(opened) isEqual:original[@"artifactRevision"]];
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
        @"revision":OVTPhotosFileRevision(opened),@"byteCount":@(count),@"sha256":original[@"sha256"],@"offset":@(position),
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

static BOOL OVTPhotosRootIdentity(struct stat a,struct stat b) {
    return S_ISDIR(a.st_mode) && S_ISDIR(b.st_mode) && a.st_dev==b.st_dev && a.st_ino==b.st_ino
        && a.st_uid==b.st_uid && a.st_gid==b.st_gid && a.st_mode==b.st_mode && a.st_uid==geteuid() && (a.st_mode&0777)==0700;
}
static NSString* OVTPhotosHash(NSData* value) {
    unsigned char bytes[CC_SHA256_DIGEST_LENGTH];CC_SHA256(value.bytes,(CC_LONG)value.length,bytes);
    NSMutableString* text=[NSMutableString new];for (NSUInteger at=0;at<sizeof(bytes);++at) {[text appendFormat:@"%02x",bytes[at]];}return text;
}
NSDictionary* OVTPhotosRetireOriginal(NSURL* root,struct stat birth,NSDictionary* original) {
    if (![NSThread isMainThread] || !root.isFileURL || ![original[@"iosSnapshotDestinationVersion"] isEqual:@2]
            || ![original[@"phase"] isEqual:@"complete"] || ![original[@"deletion"] isEqual:@{@"phase":@"complete"}]
            || ![root.lastPathComponent isEqual:[@"snapshot-photos-" stringByAppendingString:original[@"runId"]]]) {return nil;}
    NSArray* queries=original[@"queries"];NSDictionary* query=queries.lastObject;
    if (![query[@"authorization"] isEqual:@3] || ![query[@"assetPresent"] isEqual:@NO]
            || ![query[@"operationAlive"] isEqual:@NO] || ![query[@"deletionAlive"] isEqual:@NO]) {return nil;}
    NSDictionary* began=OVTChunkClock();NSTimeInterval started=NSProcessInfo.processInfo.systemUptime;
    int directory=open(root.path.fileSystemRepresentation,O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);
    if (directory<0) {return nil;}struct stat opened,named,fileBefore,fileAfter,journalBefore,journalAfter;
    BOOL okay=fstat(directory,&opened)==0 && OVTPhotosRootIdentity(opened,birth)
        && lstat(root.path.fileSystemRepresentation,&named)==0 && OVTPhotosRootIdentity(named,birth);
    int file=okay?openat(directory,"original.bytes",O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC):-1;
    okay=okay && file>=0 && fstat(file,&fileBefore)==0 && S_ISREG(fileBefore.st_mode) && fileBefore.st_nlink==1
        && fileBefore.st_uid==geteuid() && (fileBefore.st_mode&0777)==0600 && fileBefore.st_size==[original[@"byteCount"] longLongValue]
        && [OVTPhotosFileRevision(fileBefore) isEqual:original[@"artifactRevision"]];
    BOOL fileClosed=file<0 || close(file)==0;if (!fileClosed) {okay=NO;}
    int journal=okay?openat(directory,"photos-original.json",O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC):-1;
    okay=okay && journal>=0 && fstat(journal,&journalBefore)==0 && S_ISREG(journalBefore.st_mode) && journalBefore.st_nlink==1
        && journalBefore.st_uid==geteuid() && (journalBefore.st_mode&0777)==0600 && journalBefore.st_size>0 && journalBefore.st_size<=262144;
    NSMutableData* raw=[NSMutableData new];unsigned char block[65536];
    while (okay) {
        ssize_t bytes=read(journal,block,sizeof(block));if (bytes<0 && errno==EINTR) {continue;}
        if (bytes<0 || raw.length+(NSUInteger)MAX(0,bytes)>262144 || NSProcessInfo.processInfo.systemUptime-started>=1.5) {okay=NO;break;}
        if (!bytes) {break;}[raw appendBytes:block length:(NSUInteger)bytes];
    }
    id parsed=okay?[NSJSONSerialization JSONObjectWithData:raw options:0 error:nil]:nil;
    okay=okay && fstat(journal,&journalAfter)==0 && OVTChunkSame(journalBefore,journalAfter) && parsed && [parsed isEqual:original];
    BOOL journalClosed=journal<0 || close(journal)==0;if (!journalClosed) {okay=NO;}
    int duplicate=okay?dup(directory):-1;DIR* listing=duplicate>=0?fdopendir(duplicate):NULL;NSMutableSet* names=[NSMutableSet new];
    BOOL listingClosed=YES;
    if (!listing) {okay=NO;if (duplicate>=0) {listingClosed=close(duplicate)==0;}}
    else {
        errno=0;struct dirent* entry;
        while ((entry=readdir(listing))) {
            NSString* name=[[NSString alloc] initWithBytes:entry->d_name length:strlen(entry->d_name) encoding:NSASCIIStringEncoding];
            if ([name isEqual:@"."] || [name isEqual:@".."]) {errno=0;continue;}
            if (!name || names.count>=2 || [names containsObject:name]) {okay=NO;break;}[names addObject:name];errno=0;
        }
        if (errno) {okay=NO;}listingClosed=closedir(listing)==0;
        okay=okay && listingClosed && [names isEqual:[NSSet setWithArray:@[@"original.bytes",@"photos-original.json"]]];
    }
    NSMutableArray* steps=[NSMutableArray new];
    okay=okay && fstatat(directory,"original.bytes",&fileAfter,AT_SYMLINK_NOFOLLOW)==0 && OVTChunkSame(fileBefore,fileAfter)
        && fstatat(directory,"photos-original.json",&journalAfter,AT_SYMLINK_NOFOLLOW)==0 && OVTChunkSame(journalBefore,journalAfter)
        && fstat(directory,&named)==0 && OVTChunkSame(opened,named)
        && lstat(root.path.fileSystemRepresentation,&named)==0 && OVTChunkSame(opened,named);
    if (okay) {okay=unlinkat(directory,"original.bytes",0)==0;if (okay) {[steps addObject:@"original-unlinked"];}}
    if (okay) {
        okay=fstatat(directory,"photos-original.json",&journalAfter,AT_SYMLINK_NOFOLLOW)==0 && OVTChunkSame(journalBefore,journalAfter)
            && unlinkat(directory,"photos-original.json",0)==0;if (okay) {[steps addObject:@"journal-unlinked"];}
    }
    if (steps.count && fsync(directory)!=0) {okay=NO;}BOOL directoryClosed=close(directory)==0;if (!directoryClosed) {okay=NO;}
    if (okay) {
        okay=lstat(root.path.fileSystemRepresentation,&named)==0 && OVTPhotosRootIdentity(named,birth)
            && rmdir(root.path.fileSystemRepresentation)==0;if (okay) {[steps addObject:@"run-removed"];}
    }
    NSDictionary* ended=OVTChunkClock();
    if (NSProcessInfo.processInfo.systemUptime-started>=1.5) {okay=NO;}
    return @{@"phase":okay?@"complete":@"failed",@"runId":original[@"runId"],@"instance":original[@"instance"],@"processId":@(getpid()),
        @"artifactRevision":original[@"artifactRevision"],@"artifactSha256":original[@"sha256"],@"byteCount":original[@"byteCount"],
        @"journalSha256":OVTPhotosHash(raw),@"clockBefore":began,@"clockAfter":ended,@"steps":steps,@"readersClosed":@(fileClosed && journalClosed && directoryClosed && listingClosed)};
}
NSDictionary* OVTPhotosRetirementObservation(NSURL* root,struct stat birth,NSDictionary* receipt,NSString* nonce) {
    if (![NSThread isMainThread] || !root.isFileURL || !receipt || !OVTChunkMatch(nonce,@"\\Aios-[0-9a-f]{32}\\z")) {return nil;}
    NSDictionary* before=OVTChunkClock();struct stat actual;BOOL rootAbsent=NO,originalAbsent=NO,journalAbsent=NO;
    if (lstat(root.path.fileSystemRepresentation,&actual)!=0) {
        if (errno!=ENOENT) {return nil;}rootAbsent=originalAbsent=journalAbsent=YES;
    } else {
        if (!OVTPhotosRootIdentity(actual,birth)) {return nil;}
        int directory=open(root.path.fileSystemRepresentation,O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);if (directory<0) {return nil;}
        BOOL okay=fstat(directory,&actual)==0 && OVTPhotosRootIdentity(actual,birth);
        if (okay && fstatat(directory,"original.bytes",&actual,AT_SYMLINK_NOFOLLOW)!=0) {okay=errno==ENOENT;originalAbsent=okay;}
        if (okay && fstatat(directory,"photos-original.json",&actual,AT_SYMLINK_NOFOLLOW)!=0) {okay=errno==ENOENT;journalAbsent=okay;}
        okay=okay && lstat(root.path.fileSystemRepresentation,&actual)==0 && OVTPhotosRootIdentity(actual,birth);
        if (close(directory)!=0) {okay=NO;}if (!okay) {return nil;}
    }
    return @{@"snapshotPhotosRetirementVersion":@1,@"nonce":nonce,@"receipt":receipt,@"clockBefore":before,@"clockAfter":OVTChunkClock(),
        @"runAbsent":@(rootAbsent),@"originalAbsent":@(originalAbsent),@"journalAbsent":@(journalAbsent)};
}
BOOL OVTPhotosPersistRetirement(NSURL* documents,NSDictionary* packet) {
    if (!packet || !documents.isFileURL) {return NO;}NSData* bytes=[NSJSONSerialization dataWithJSONObject:packet options:0 error:nil];
    if (!bytes || bytes.length>16384) {return NO;}
    NSString* temporary=[documents.path stringByAppendingPathComponent:[@".photos-retire-" stringByAppendingString:NSUUID.UUID.UUIDString]];
    int file=open(temporary.fileSystemRepresentation,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);if (file<0) {return NO;}
    NSUInteger count=0;BOOL okay=YES;
    while (count<bytes.length) {ssize_t written=write(file,(const char*)bytes.bytes+count,bytes.length-count);if (written<0 && errno==EINTR) {continue;}if (written<=0) {okay=NO;break;}count+=(NSUInteger)written;}
    if (fsync(file)!=0) {okay=NO;}if (close(file)!=0) {okay=NO;}
    NSString* path=[documents.path stringByAppendingPathComponent:@"snapshot-photos-retire.json"];
    if (okay && rename(temporary.fileSystemRepresentation,path.fileSystemRepresentation)!=0) {okay=NO;}
    int directory=open(documents.path.fileSystemRepresentation,O_RDONLY|O_DIRECTORY|O_NOFOLLOW);
    if (directory<0) {okay=NO;}else {if (fsync(directory)!=0) {okay=NO;}close(directory);}return okay;
}
