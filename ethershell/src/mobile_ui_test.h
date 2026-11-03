#pragma once
#include "core.h"
#include "mobile.h"
#include <QQuickWindow>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QFile>
#include <QDir>
#include <QTimer>
#include <QGuiApplication>
#include <QQuickItem>

// Exercises the REAL shell navigation/shared backend on a private X server.
// No modem mutation, profile save, scan or connection activation is performed.
class MobileUiTest:public QObject{
    Core *core;Mobile *mobile;QQuickWindow *window;QObject *page=nullptr;
    QString output;int index=0;QJsonObject results;
    const QStringList sections={"Mobile Data","SIM Cards","Access Point Names","Network Selection","Preferred Network Type","Data Roaming","Data Usage","Advanced Modem Settings","Diagnostics"};
    QObject *find(const QString &name){
        std::function<QQuickItem*(QQuickItem*)> visit=[&](QQuickItem *item)->QQuickItem*{if(item->objectName()==name)return item;for(auto *child:item->childItems())if(auto *found=visit(child))return found;return nullptr;};
        if(auto *item=visit(window->contentItem()))return item;
        return window->findChild<QObject*>(name);
    }
    bool capture(const QString &name){return window->grabWindow().save(output+"/"+name+".png");}
    bool unobscured(QObject *object){
        auto *item=qobject_cast<QQuickItem*>(object);if(!item||!item->isVisible())return false;
        const auto rect=item->mapRectToScene(QRectF(0,0,item->width(),item->height()));
        QJsonArray geometry;for(auto *p=item;p;p=p->parentItem()){const auto r=p->mapRectToScene(QRectF(0,0,p->width(),p->height()));geometry<<QJsonObject{{"type",p->metaObject()->className()},{"clip",p->clip()},{"x",r.x()},{"y",r.y()},{"width",r.width()},{"height",r.height()}};}QFile diagnostic(output+"/geometry-"+item->objectName()+".json");if(diagnostic.open(QIODevice::WriteOnly))diagnostic.write(QJsonDocument(geometry).toJson());
        if(!QRectF(-2,-2,window->width()+4,window->height()+4).contains(rect))return false;
        for(auto *p=item->parentItem();p;p=p->parentItem())if(p->clip()&&!p->mapRectToScene(QRectF(0,0,p->width(),p->height())).adjusted(-2,-2,2,2).contains(rect))return false;
        return true;
    }
    void render(){
        if(index>=sections.size()*2){quick();return;}
        const bool dark=index>=sections.size();core->setting("themeMode",dark?"dark":"light");
        page->setProperty("section",sections[index%sections.size()]);
        if(sections[index%sections.size()]=="Diagnostics"&&qEnvironmentVariableIsSet("ETHERSHELL_DIAGNOSTICS_QA")){
            auto *first=find("diagnosticStage");
            results["diagnostic-details-expand"]=first&&first->setProperty("expanded",true);
        }
        QTimer::singleShot(180,this,[this,dark]{
            const auto name=QString::number(index%sections.size())+(dark?"-dark":"-light");
            results["render-"+name]=capture(name);++index;render();
        });
    }
    void quick(){
        if(qEnvironmentVariableIsSet("ETHERSHELL_DATA_PROGRESS_QA")&&!results.contains("connection-error-visible")){
            page->setProperty("section","Mobile Data");
            mobile->connectProfile("/invalid-test-profile"); // Local validation only; no service mutation.
            QTimer::singleShot(250,this,[this]{
                auto *label=find("mobileDataStage");
                results["connection-error-visible"]=label&&label->property("text").toString().contains("Wybierz zapisany profil")&&page->property("connectionOperationError").toBool();
                results["connection-error-render"]=capture("connection-error");
                quick();
            });return;
        }
        window->setProperty("quickVisible",true);
        QTimer::singleShot(250,this,[this]{
            auto *toggle=window->findChild<QObject*>("mobileQuickToggle");
            results["quick-shared-state"]=toggle&&toggle->property("selected").toBool()==mobile->snapshot().value("dataActive").toBool();
            for(auto *w:QGuiApplication::allWindows())if(w->title()=="EtherControl 2")if(auto *q=qobject_cast<QQuickWindow*>(w))results["quick-render"]=q->grabWindow().save(output+"/quick.png");
            window->setProperty("quickVisible",false);
            QMetaObject::invokeMethod(page,"edit",Q_ARG(QVariant,QVariant("")),Q_ARG(QVariant,QVariant(false)));
            editor();
        });
    }
    void editor(){
        QTimer::singleShot(350,this,[this]{
            auto *editor=window->findChild<QObject*>("mobileApnEditor");auto *name=window->findChild<QObject*>("mobileApnName");
            results["apn-editor-opens"]=editor&&editor->property("visible").toBool()&&name;
            if(name){name->setProperty("text","unsaved-test-draft");QMetaObject::invokeMethod(name,"textEdited");}
            page->setProperty("section","SIM Cards");page->setProperty("section","Access Point Names");
            results["draft-preserved"]=name&&name->property("text").toString()=="unsaved-test-draft"&&page->property("dirty").toBool();
            results["editor-render"]=capture("apn-editor");
            if(auto *field=qobject_cast<QQuickItem*>(name))field->forceActiveFocus();
            QTimer::singleShot(550,this,[this,editor,name]{
                results["apn-keyboard-opens"]=window->property("keyboardVisible").toBool();
                results["apn-focused-input-visible"]=unobscured(name);
                results["apn-save-visible"]=unobscured(find("mobileApnSave"));
                results["apn-cancel-visible"]=unobscured(find("mobileApnCancel"));
                capture("apn-keyboard");window->setProperty("keyboardVisible",false);
                if(editor)QMetaObject::invokeMethod(editor,"close");
                QFile f(output+"/results.json");if(f.open(QIODevice::WriteOnly))f.write(QJsonDocument(results).toJson());
                bool ok=true;for(auto i=results.begin();i!=results.end();++i)ok&=i.value().toBool();QCoreApplication::exit(ok?0:7);
            });
        });
    }
public:
    MobileUiTest(Core *c,Mobile *m,QQuickWindow *w):QObject(c),core(c),mobile(m),window(w){
        output=qEnvironmentVariable("ETHERSHELL_MOBILE_TEST_OUTPUT");QDir().mkpath(output);
        QTimer::singleShot(2500,this,[this]{
            window->setProperty("page","settings");
            auto *network=find("networkInternetEntry");
            if(network)QMetaObject::invokeMethod(network,"clicked");
            auto *workspace=window->findChild<QObject*>("settingsWorkspace");
            results["settings-network-navigation"]=workspace&&workspace->property("route").toString()=="network";
            auto *entry=find("mobileNetworkEntry");if(entry)QMetaObject::invokeMethod(entry,"clicked");
            results["network-mobile-navigation"]=window->property("page").toString()=="mobile";
            if(qEnvironmentVariableIsSet("ETHERMOBILE_EXPECT_REAL_SIM")){
                results["real-modem-readable"]=mobile->snapshot().value("available").toBool();
                results["real-sim-ready"]=mobile->snapshot().value("simReady").toBool();
                results["real-sim-operator"]=!mobile->snapshot().value("simOperator").toString().isEmpty()&&mobile->snapshot().value("simOperator").toString()!="Unavailable";
                results["persistent-profiles-readable"]=!mobile->profiles().isEmpty();
            }
            page=window->findChild<QObject*>("mobileNetworkSettings");
            if(!page){QCoreApplication::exit(6);return;}
            if(qEnvironmentVariableIsSet("ETHERSHELL_DIAGNOSTICS_QA")){
                mobile->diagnose();
                auto *wait=new QTimer(this);wait->setInterval(250);
                connect(wait,&QTimer::timeout,this,[this,wait]{
                    if(mobile->busy())return;
                    wait->stop();wait->deleteLater();
                    results["real-diagnostic-stages"]=mobile->stages().size()>0;render();
                });wait->start();
            }else render();
        });
    }
};
