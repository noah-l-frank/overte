// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#import "ShareArchiveFiles.h"
#import "ShareJournal.h"
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>

NSDictionary* OVTShareArchiveChunk(NSURL* root,NSDictionary* imported,NSString* nonce,NSString* offset) {
    if (![NSThread isMainThread] || !root.isFileURL || ![imported[@"iosSnapshotShareImportVersion"] isEqual:@2]
            || ![imported[@"phase"] isEqual:@"complete"] || !OVTShareMatch(nonce,@"\\Aios-[a-f0-9]{32}\\z")
            || !OVTShareMatch(offset,@"\\A(0|[1-9][0-9]{0,8})\\z")
            || ![root.lastPathComponent isEqual:[@"snapshot-share-" stringByAppendingString:imported[@"runId"]]]) {return nil;}
    unsigned long long position=offset.longLongValue,count=[imported[@"byteCount"] unsignedLongLongValue];NSUInteger limit=512*1024;
    if (!count || count>256*1024*1024 || position>=count || position%limit) {return nil;}
    NSDictionary* before=OVTShareClock();NSTimeInterval began=NSProcessInfo.processInfo.systemUptime;
    int directory=open(root.fileSystemRepresentation,O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);
    if (directory<0) {return nil;}struct stat directoryBefore,directoryAfter,named,opened,after;
    BOOL valid=fstat(directory,&directoryBefore)==0 && [OVTShareRootIdentity(directoryBefore) isEqual:imported[@"archiveRootIdentity"]]
        && lstat(root.fileSystemRepresentation,&named)==0 && [OVTShareFileRevision(named) isEqual:OVTShareFileRevision(directoryBefore)]
        && fstatat(directory,"original.bytes",&named,AT_SYMLINK_NOFOLLOW)==0;
    int file=valid?openat(directory,"original.bytes",O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC):-1;
    valid=valid && file>=0 && fstat(file,&opened)==0 && S_ISREG(opened.st_mode) && opened.st_nlink==1 && opened.st_uid==geteuid()
        && (opened.st_mode&0777)==0600 && opened.st_size==(off_t)count && [OVTShareFileRevision(opened) isEqual:OVTShareFileRevision(named)]
        && [OVTShareFileRevision(opened) isEqual:imported[@"artifactRevision"]];
    NSUInteger length=(NSUInteger)MIN((unsigned long long)limit,count-position),received=0;NSMutableData* raw=[NSMutableData dataWithLength:length];
    while (valid && received<length) {
        ssize_t bytes=pread(file,(char*)raw.mutableBytes+received,length-received,(off_t)(position+received));
        if (bytes<0 && errno==EINTR) {continue;}
        if (bytes<=0 || NSProcessInfo.processInfo.systemUptime-began>=1.5) {valid=NO;break;}received+=(NSUInteger)bytes;
    }
    valid=valid && fstat(file,&after)==0 && [OVTShareFileRevision(after) isEqual:OVTShareFileRevision(opened)]
        && fstatat(directory,"original.bytes",&named,AT_SYMLINK_NOFOLLOW)==0 && [OVTShareFileRevision(named) isEqual:OVTShareFileRevision(opened)]
        && fstat(directory,&directoryAfter)==0 && [OVTShareFileRevision(directoryAfter) isEqual:OVTShareFileRevision(directoryBefore)]
        && lstat(root.fileSystemRepresentation,&named)==0 && [OVTShareFileRevision(named) isEqual:OVTShareFileRevision(directoryBefore)];
    if (file>=0 && close(file)!=0) {valid=NO;}if (close(directory)!=0) {valid=NO;}
    NSDictionary* ended=OVTShareClock();if (!valid || NSProcessInfo.processInfo.systemUptime-began>=1.5) {return nil;}
    return @{@"snapshotShareChunkVersion":@1,@"nonce":nonce,@"runId":imported[@"runId"],@"instance":imported[@"instance"],
        @"processId":@(getpid()),@"basename":imported[@"basename"],@"clockDomain":@"native-share-archive",@"clockBefore":before,@"clockAfter":ended,
        @"revision":OVTShareFileRevision(opened),@"byteCount":@(count),@"sha256":imported[@"sha256"],@"offset":@(position),
        @"eof":@(position+length==count),@"readerClosed":@YES,@"data":[raw base64EncodedStringWithOptions:0]};
}
