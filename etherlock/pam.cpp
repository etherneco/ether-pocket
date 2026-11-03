// Fixed-service, unprivileged PAM conversation. No credentials in argv or logs.
#include <security/pam_appl.h>
#include <pwd.h>
#include <unistd.h>
#include <sys/resource.h>
#include <syslog.h>
#include <cstdlib>
#include <cstring>
#include <cstdio>
#include <QCoreApplication>
#include <QJsonDocument>
#include <QJsonObject>

static void message(const QJsonObject &object) {
    auto line=QJsonDocument(object).toJson(QJsonDocument::Compact)+'\n';
    fwrite(line.constData(),1,line.size(),stdout);fflush(stdout);
}
static int conversation(int count,const pam_message **messages,pam_response **out,void *) {
    if(count<1||count>PAM_MAX_NUM_MSG)return PAM_CONV_ERR;
    auto responses=static_cast<pam_response*>(calloc(count,sizeof(pam_response)));
    if(!responses)return PAM_BUF_ERR;
    for(int i=0;i<count;++i) {
        const auto style=messages[i]->msg_style;
        if(style==PAM_PROMPT_ECHO_OFF||style==PAM_PROMPT_ECHO_ON) {
            // Do not relay module text: third party PAM messages can contain identifiers.
            message({{"event","prompt"},{"echo",style==PAM_PROMPT_ECHO_ON}});
            char buffer[4098]={};
            if(!fgets(buffer,sizeof(buffer),stdin)||!strchr(buffer,'\n'))goto fail;
            {
                auto object=QJsonDocument::fromJson(QByteArray(buffer)).object();
                explicit_bzero(buffer,sizeof(buffer));
                if(!object.value("response").isString())goto fail;
                auto value=object.value("response").toString().toUtf8();
                if(value.size()>1024||value.contains('\0')){value.fill(0);goto fail;}
                responses[i].resp=strdup(value.constData());value.fill(0);
                if(!responses[i].resp)goto fail;
            }
        } else if(style!=PAM_ERROR_MSG&&style!=PAM_TEXT_INFO)goto fail;
    }
    *out=responses;return PAM_SUCCESS;
fail:
    for(int i=0;i<count;++i)if(responses[i].resp){explicit_bzero(responses[i].resp,strlen(responses[i].resp));free(responses[i].resp);}
    free(responses);return PAM_CONV_ERR;
}
int main(int argc,char **argv) {
    QCoreApplication app(argc,argv);
    rlimit limit{0,0};setrlimit(RLIMIT_CORE,&limit);
    if(getuid()==0||geteuid()!=getuid()||argc!=1)return 2;
    auto user=getpwuid(getuid());if(!user)return 2;
    pam_conv conv{conversation,nullptr};pam_handle_t *handle=nullptr;
    int result=pam_start("etherlock",user->pw_name,&conv,&handle);
    if(result==PAM_SUCCESS)result=pam_authenticate(handle,PAM_DISALLOW_NULL_AUTHTOK);
    if(result==PAM_SUCCESS)result=pam_acct_mgmt(handle,0);
    // Expired passwords require passwd through a trusted channel; never unlock.
    const bool success=result==PAM_SUCCESS;
    if(handle)pam_end(handle,result);
    openlog("etherlock-auth",LOG_PID,LOG_AUTHPRIV);
    syslog(success?LOG_NOTICE:LOG_WARNING,"%s uid=%lu",success?"authentication-success":"authentication-failed",static_cast<unsigned long>(getuid()));
    closelog();message({{"event","result"},{"success",success}});return success?0:1;
}
