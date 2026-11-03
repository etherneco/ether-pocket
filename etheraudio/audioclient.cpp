#include "audioclient.h"
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusPendingCallWatcher>
#include <QDBusServiceWatcher>
#include <QJsonDocument>
#include <QJsonObject>
#include <QFile>
#include <cmath>
static const QString service="com.etherneco.EtherAudio1",path="/com/etherneco/EtherAudio1";
AudioClient::AudioClient(QObject *parent):QObject(parent){
 m_state={{"ready",false}};
 if(qEnvironmentVariableIntValue("ETHERSHELL_DEVELOPMENT")==1){
  if(qEnvironmentVariableIsSet("ETHERSHELL_MOBILE_TEST_OUTPUT")){QFile snapshot(qEnvironmentVariable("ETHERAUDIO_QA_STATE"));if(snapshot.open(QIODevice::ReadOnly))update(QString::fromUtf8(snapshot.readAll()));}
  return;
 }
 auto bus=QDBusConnection::sessionBus();
 bus.connect(service,path,service,"Changed",this,SLOT(update(QString)));
 bus.connect(service,path,service,"Event",this,SLOT(event(QString,QString)));
 auto *watch=new QDBusServiceWatcher(service,bus,QDBusServiceWatcher::WatchForOwnerChange,this);
 connect(watch,&QDBusServiceWatcher::serviceOwnerChanged,this,[this](QString,QString,QString owner){if(owner.isEmpty()){m_state={{"ready",false}};emit changed();}else refresh();});
 connect(&m_recorder,&QProcess::readyReadStandardOutput,this,[this]{auto data=m_recorder.readAllStandardOutput();m_pcm+=data;double sum=0;for(qsizetype i=0;i+1<data.size();i+=2){auto sample=qint16(quint8(data[i])|(quint16(quint8(data[i+1]))<<8));sum+=double(sample)*sample;}m_level=data.size()>1?std::sqrt(sum/(data.size()/2))/32768.:0;if(m_pcm.size()>120000)m_recorder.kill();emit changed();});
 connect(&m_recorder,qOverload<int,QProcess::ExitStatus>(&QProcess::finished),this,[this](int code,QProcess::ExitStatus){m_recorder.readAllStandardError();m_level=0;
  if(code||m_pcm.size()<8000){m_message="Microphone test failed or produced insufficient data";deleteSample();emit changed();return;}
  m_sample=true;m_deleteTimer.start(60000);m_message="Sample held in memory for playback; cleared after one minute. Data alone does not verify microphone quality.";emit changed();refresh();
 });
 connect(&m_recorder,&QProcess::errorOccurred,this,[this](QProcess::ProcessError){m_message="Managed microphone capture unavailable";emit changed();});
 connect(&m_player,&QProcess::started,this,[this]{m_player.write(m_pcm);m_player.closeWriteChannel();});
 m_deleteTimer.setSingleShot(true);connect(&m_deleteTimer,&QTimer::timeout,this,&AudioClient::deleteSample);
 call("GetState");
}
AudioClient::~AudioClient(){m_recorder.kill();m_recorder.waitForFinished(1000);m_player.kill();m_player.waitForFinished(1000);deleteSample();}
void AudioClient::update(const QString &document){const auto json=QJsonDocument::fromJson(document.toUtf8());if(!json.isObject())return;m_state=json.object().toVariantMap();emit changed();}
void AudioClient::event(const QString &kind,const QString &document){if(kind=="MicrophoneActivity"){auto d=QJsonDocument::fromJson(document.toUtf8()).object();if(d.value("recording").toBool())emit notice("Microphone in use","Open Sound & Notifications to inspect recording applications.");}if(kind=="SuspendRequested"){m_recorder.kill();deleteSample();}}
void AudioClient::call(const QString &method,const QVariantList &args){
 if(qEnvironmentVariableIntValue("ETHERSHELL_DEVELOPMENT")==1)return;
 auto msg=QDBusMessage::createMethodCall(service,path,service,method);msg.setArguments(args);++m_pending;emit changed();
 auto *watch=new QDBusPendingCallWatcher(QDBusConnection::sessionBus().asyncCall(msg,45000),this);
 connect(watch,&QDBusPendingCallWatcher::finished,this,[this,watch,method]{auto reply=watch->reply();--m_pending;
  if(reply.type()==QDBusMessage::ErrorMessage)m_message=reply.errorMessage();
  else if(method=="GetState"&&!reply.arguments().isEmpty())update(reply.arguments().first().toString());
  else if(method=="Command")m_message="Audio request completed; effective values shown below.";
  emit changed();watch->deleteLater();
 });
}
void AudioClient::refresh(){call("GetState");}
void AudioClient::command(const QString &action,const QString &target,const QVariantMap &data){call("Command",{action,target,QString::fromUtf8(QJsonDocument::fromVariant(data).toJson(QJsonDocument::Compact))});}
void AudioClient::recordTest(){if(qEnvironmentVariableIntValue("ETHERSHELL_DEVELOPMENT")==1||m_recorder.state()!=QProcess::NotRunning)return;deleteSample();m_message="Recording three seconds after your confirmation";m_recorder.start("etheraudio",{"capture","--consent","--seconds","3","--purpose","Interactive microphone diagnostic","--source",m_state.value("default-source").toString()});emit changed();}
void AudioClient::playSample(){if(m_sample&&m_player.state()==QProcess::NotRunning)m_player.start("paplay",{"--raw","--format=s16le","--rate=16000","--channels=1"});}
void AudioClient::deleteSample(){m_deleteTimer.stop();m_pcm.fill(0);m_pcm.clear();m_sample=false;emit changed();}
