#pragma once
#include <QObject>
#include <QProcess>
#include <QTemporaryDir>
#include <QTimer>
#include <QVariantList>
class ISpeechRecognizer:public QObject {
 Q_OBJECT
public:using QObject::QObject;
signals:void transcribed(const QString &text);
};
class Speech final:public ISpeechRecognizer {
 Q_OBJECT
 Q_PROPERTY(QString state READ state NOTIFY changed)
 Q_PROPERTY(double level READ level NOTIFY changed)
 Q_PROPERTY(bool available READ available NOTIFY changed)
 Q_PROPERTY(QVariantList models READ models NOTIFY changed)
public:
 explicit Speech(QObject *parent=nullptr);~Speech();
 QString state()const{return m_state;}double level()const{return m_level;}bool available()const;
 QVariantList models()const;
 Q_INVOKABLE void start(const QString &language,const QString &model,const QString &device);
 Q_INVOKABLE void stop();Q_INVOKABLE void cancel();
signals:void changed();
private:
 void fail(const QString &message);void recognize();void consume();
 QString m_state="Ready",m_language,m_model,m_models,m_device;double m_level=0;QByteArray m_pcm;
 QProcess m_capture,m_recognizer,m_sources;QTemporaryDir m_temp;QTimer m_limit,m_deadline;bool m_stopping=false;
};
