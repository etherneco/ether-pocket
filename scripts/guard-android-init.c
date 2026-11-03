/* Diagnostic only: prevent an early Android-init failure from rebooting away logs. */
#define _GNU_SOURCE
#include <errno.h>
#include <linux/filter.h>
#include <linux/seccomp.h>
#include <stddef.h>
#include <stdio.h>
#include <sys/prctl.h>
#include <sys/syscall.h>
#include <unistd.h>
int main(int argc,char **argv) {
    struct sock_filter code[] = {
        BPF_STMT(BPF_LD|BPF_W|BPF_ABS,offsetof(struct seccomp_data,nr)),
        BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,__NR_reboot,0,1),
        BPF_STMT(BPF_RET|BPF_K,SECCOMP_RET_ERRNO|EPERM),
        BPF_STMT(BPF_RET|BPF_K,SECCOMP_RET_ALLOW)
    };
    struct sock_fprog p={.len=sizeof(code)/sizeof(code[0]),.filter=code};
    if (argc<2 || prctl(PR_SET_SECCOMP,SECCOMP_MODE_FILTER,&p)) { perror("diagnostic reboot guard"); return 1; }
    execv(argv[1],argv+1); perror("diagnostic exec"); return 1;
}
