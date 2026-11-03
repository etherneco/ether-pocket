#pragma once
#include "core.h"
#include <QQuickWindow>
#include <QQuickItem>
#include <QTimer>
#include <QJsonObject>
#include <QJsonDocument>
#include <QFile>
#include <QDir>
#include <QStandardPaths>
#include <QQmlComponent>
#include <QQmlEngine>
#include <QEventLoop>

// Exercises actual lazy Settings pages, real search, theme persistence and
// existing keyboard focus on an isolated session. Never changes hardware.
class SettingsUiTest:public QObject {
    Core *core;QQuickWindow *window;QObject *workspace=nullptr;QString output;QJsonObject results;int index=0;
    const QStringList routes=qEnvironmentVariableIsSet("ETHERSHELL_FINGERPRINT_UI_ONLY")?QStringList{"security","fingerprints"}:qEnvironmentVariableIsSet("ETHERSHELL_BACKUP_UI_ONLY")?QStringList{"backup"}:qEnvironmentVariableIsSet("ETHERSHELL_SENSORS_UI_ONLY")?QStringList{"sensors"}:qEnvironmentVariableIsSet("ETHERSHELL_UPDATE_UI_ONLY")?QStringList{"updates"}:qEnvironmentVariableIsSet("ETHERSHELL_LOCATION_UI_ONLY")?QStringList{"location"}:QStringList{"home","backup","sensors","updates","network","calls","camera","location","sharing","hardware","sms","wifi","bluetooth","devices","appearance","sound","power","storage","security","apps","input","system","etherneco"};
    QQuickItem *find(QQuickItem *item,const QString &name){if(item->objectName()==name)return item;for(auto *c:item->childItems())if(auto *p=find(c,name))return p;return nullptr;}
    void go(const QString &route,const QString &key={}){QMetaObject::invokeMethod(workspace,"go",Q_ARG(QVariant,QVariant(route)),Q_ARG(QVariant,QVariant(key)));}
    bool geometry(QQuickItem *root,bool allowTruncated=false){
        bool ok=true;
        for(auto *item:root->childItems()){
            if(!item->isVisible())continue;
            if(item->property("text").isValid()&&!item->property("text").toString().isEmpty()&&item->width()>0){
                const auto rect=item->mapRectToScene(QRectF(0,0,item->width(),item->height()));
                if(rect.left() < -1||rect.right()>window->width()+1||(!allowTruncated&&item->property("truncated").toBool())){ok=false;qWarning()<<"Settings geometry"<<item->objectName()<<item->metaObject()->className()<<rect<<"truncated"<<item->property("truncated");}
            }
            ok&=geometry(item,allowTruncated);
        }return ok;
    }
    void render(){
        if(index==routes.size()*2){
            if(qEnvironmentVariableIsSet("ETHERSHELL_FINGERPRINT_UI_ONLY")||qEnvironmentVariableIsSet("ETHERSHELL_BACKUP_UI_ONLY")||qEnvironmentVariableIsSet("ETHERSHELL_SENSORS_UI_ONLY")||qEnvironmentVariableIsSet("ETHERSHELL_LOCATION_UI_ONLY")||qEnvironmentVariableIsSet("ETHERSHELL_UPDATE_UI_ONLY")){
                QFile f(output+"/results.json");if(f.open(QIODevice::WriteOnly))f.write(QJsonDocument(results).toJson());
                bool ok=true;for(auto i=results.begin();i!=results.end();++i)ok&=i.value().toBool();QCoreApplication::exit(ok?0:8);return;
            }hardwareViews();return;
        }
        const auto route=routes[index%routes.size()];const bool dark=index>=routes.size();core->setting("themeMode",dark?"dark":"light");go(route);
        QTimer::singleShot(400,this,[this,route,dark]{
            const auto label=route+(dark?"-dark":"-light");results[label+"-render"]=window->grabWindow().save(output+"/"+label+".png");
            if(route=="fingerprints"){
                auto *manager=find(window->contentItem(),"fingerprintManager");
                auto *add=find(window->contentItem(),"fingerprintEnroll");
                auto *toggle=find(window->contentItem(),"fingerprintToggle");
                auto *test=find(window->contentItem(),"fingerprintTest");
                results[label+"-blocked-controls"]=manager&&add&&toggle&&test&&!add->isEnabled()&&!toggle->isEnabled()&&!test->isEnabled()&&!toggle->property("checked").toBool();
                auto *count=find(window->contentItem(),"fingerprintCount");
                results[label+"-unknown-enrollment"]=count&&count->property("text").toString()=="Unknown";
                auto *diagnostics=find(window->contentItem(),"fingerprintDiagnostics");
                if(diagnostics)QMetaObject::invokeMethod(diagnostics,"clicked");
                // Allow the newly visible diagnostics layout to wrap at the
                // current viewport width before checking its text geometry.
                QEventLoop settle;QTimer::singleShot(200,&settle,&QEventLoop::quit);settle.exec();
                results[label+"-diagnostics-toggle"]=manager&&manager->property("diagnosticsOpen").toBool();
                results[label+"-diagnostics-render"]=window->grabWindow().save(output+"/"+label+"-diagnostics.png");
            }
            if(route=="updates"){
                auto *field=find(window->contentItem(),"etherUpdateTokenInput");
                auto *save=find(window->contentItem(),"etherUpdateSaveToken");
                results[label+"-token-masked"]=field&&field->property("echoMode").toInt()==2;
                results[label+"-token-never-read-back"]=field&&field->property("text").toString().isEmpty();
                if(field&&save){
                    field->setProperty("text","synthetic_test_value_1234567890");
                    results[label+"-token-display-hidden"]=field->property("displayText").toString()!=field->property("text").toString();
                    QMetaObject::invokeMethod(save,"clicked");
                    results[label+"-token-cleared-after-submit"]=field->property("text").toString().isEmpty();
                }else results[label+"-token-cleared-after-submit"]=false;
            }
            results[label+"-route"]=workspace->property("route").toString()==route;
            auto *scroll=find(window->contentItem(),"settingsPageScroll");results[label+"-geometry"]=scroll&&geometry(scroll);
            ++index;render();
        });
    }
    int hardwareIndex=0;
    const QStringList hardwareCategories={"processor","memory","storage","display","wireless","cellular","usb","audio","camera","sensors","power","drivers"};
    void hardwareViews(){
        if(hardwareIndex==hardwareCategories.size()*2){powerViews();return;}
        go("hardware");auto *hardware=find(window->contentItem(),"hardwarePage");
        if(!hardware){results["hardware-present"]=false;search();return;}
        const auto category=hardwareCategories[hardwareIndex%hardwareCategories.size()];const bool dark=hardwareIndex>=hardwareCategories.size();
        core->setting("themeMode",dark?"dark":"light");
        QMetaObject::invokeMethod(hardware,"choose",Q_ARG(QVariant,QVariant(category)));
        QTimer::singleShot(220,this,[this,hardware,category,dark]{
            const auto label="hardware-"+category+(dark?"-dark":"-light");
            results[label+"-category"]=hardware->property("category").toString()==category;
            auto *scroll=find(window->contentItem(),"settingsPageScroll");results[label+"-geometry"]=scroll&&geometry(scroll);
            results[label+"-render"]=window->grabWindow().save(output+"/"+label+".png");
            auto *device=find(hardware,"hardwareDevice");if(device)QMetaObject::invokeMethod(device,"clicked");
            QTimer::singleShot(140,this,[this,hardware,label,device]{
                auto *sheet=hardware->findChild<QObject*>("hardwareDetailSheet");
                results[label+"-details"]=device&&sheet&&sheet->property("visible").toBool();
                if(sheet){results[label+"-sheet-render"]=window->grabWindow().save(output+"/"+label+"-details.png");QMetaObject::invokeMethod(sheet,"close");}
                ++hardwareIndex;hardwareViews();
            });
        });
    }
    int powerIndex=0;
    const QStringList powerSections={"overview","battery","charging","profiles","display","sleep","thermal","history","advanced"};
    void powerViews(){
        if(powerIndex==powerSections.size()*2){audioViews();return;}
        go("power");auto *power=find(window->contentItem(),"etherPowerPage");
        if(!power){results["power-present"]=false;search();return;}
        const auto section=powerSections[powerIndex%powerSections.size()];const bool dark=powerIndex>=powerSections.size();
        core->setting("themeMode",dark?"dark":"light");
        QMetaObject::invokeMethod(power,"choose",Q_ARG(QVariant,QVariant(section)));
        QTimer::singleShot(250,this,[this,power,section,dark]{
            const auto label="power-"+section+(dark?"-dark":"-light");
            results[label+"-section"]=power->property("section").toString()==section;
            auto *scroll=find(window->contentItem(),"settingsPageScroll");results[label+"-geometry"]=scroll&&geometry(scroll);
            results[label+"-render"]=window->grabWindow().save(output+"/"+label+".png");
            ++powerIndex;powerViews();
        });
    }
    int audioIndex=0;
    const QStringList audioSections={"output","input","volume","routing","applications","advanced"};
    void audioViews(){
        if(audioIndex==audioSections.size()*2){powerMenu();return;}
        go("sound");auto *audio=find(window->contentItem(),"etherAudioPage");
        if(!audio){results["audio-present"]=false;search();return;}
        const auto section=audioSections[audioIndex%audioSections.size()];const bool dark=audioIndex>=audioSections.size();
        core->setting("themeMode",dark?"dark":"light");QMetaObject::invokeMethod(audio,"choose",Q_ARG(QVariant,QVariant(section)));
        QTimer::singleShot(250,this,[this,audio,section,dark]{
            const auto label="audio-"+section+(dark?"-dark":"-light");
            results[label+"-section"]=audio->property("section").toString()==section;
            auto *scroll=find(window->contentItem(),"settingsPageScroll");results[label+"-geometry"]=scroll&&geometry(scroll);
            results[label+"-render"]=window->grabWindow().save(output+"/"+label+".png");++audioIndex;audioViews();
        });
    }
    void powerMenu(){
        window->setProperty("quickVisible",true);
        QTimer::singleShot(300,this,[this]{
            results["power-quick-render"]=window->grabWindow().save(output+"/power-quick.png");window->setProperty("quickVisible",false);
            auto *menu=window->findChild<QObject*>("etherPowerMenu");if(menu)QMetaObject::invokeMethod(menu,"open");
            QTimer::singleShot(250,this,[this,menu]{
                results["power-menu-opens"]=menu&&menu->property("visible").toBool();
                results["power-menu-render"]=window->grabWindow().save(output+"/power-menu.png");
                if(menu)QMetaObject::invokeMethod(menu,"close");search();
            });
        });
    }
    void search(){
        go("home");workspace->setProperty("search","wallpaper");
        QTimer::singleShot(200,this,[this]{
            auto *hit=find(window->contentItem(),"search-setting-wallpaper");if(hit)QMetaObject::invokeMethod(hit,"clicked");
            results["search-direct-navigation"]=hit&&workspace->property("route").toString()=="appearance";
            go("input","setting-keyboard");
            QTimer::singleShot(200,this,[this]{
                auto *input=find(window->contentItem(),"settingsKeyboardTest");if(input)input->forceActiveFocus();
                QTimer::singleShot(500,this,[this,input]{
                    results["keyboard-opens"]=input&&window->property("keyboardVisible").toBool();
                    if(input){const auto rect=input->mapRectToScene(QRectF(0,0,input->width(),input->height()));results["focused-input-visible"]=rect.top()>=0&&rect.bottom()<=window->height()+1;}
                    window->grabWindow().save(output+"/keyboard-focus.png");window->setProperty("keyboardVisible",false);
                    // A plain editor has no SettingsInput keyboardRequested
                    // handler: opening here exercises native Qt focus tracking.
                    QQmlComponent editor(qmlEngine(window));
                    editor.setData("import QtQuick\nTextInput { width: 100; height: 30 }",QUrl());
                    auto *plain=qobject_cast<QQuickItem*>(editor.create());
                    if(plain){plain->setParentItem(window->contentItem());plain->forceActiveFocus();}
                    results["keyboard-native-editor"]=plain&&window->property("keyboardVisible").toBool();
                    core->setting("autoKeyboard",false);
                    results["keyboard-preference-disables"]=!window->property("keyboardVisible").toBool();
                    core->textInputFocus(true);
                    results["keyboard-disabled-focus"]=!window->property("keyboardVisible").toBool();
                    core->setting("autoKeyboard",true);
                    results["keyboard-preference-enables"]=window->property("keyboardVisible").toBool();
                    core->textInputFocus(false);
                    results["keyboard-blur-closes"]=!window->property("keyboardVisible").toBool();
                    window->setProperty("keyboardVisible",true);core->textInputFocus(false);
                    results["keyboard-manual-preserved"]=window->property("keyboardVisible").toBool();
                    window->setProperty("keyboardVisible",false);
                    const auto inputRoot=qEnvironmentVariable("ETHERSHELL_TEST_INPUT_ROOT");
                    if(!inputRoot.isEmpty()){
                        auto settle=[] {QEventLoop loop;QTimer::singleShot(1000,&loop,&QEventLoop::quit);loop.exec();};
                        core->textInputFocus(true);
                        QDir().mkpath(inputRoot+"/event0/device/capabilities");
                        QFile keyboard(inputRoot+"/event0/device/capabilities/key");
                        if(keyboard.open(QIODevice::WriteOnly)){keyboard.write("0200100050000000");keyboard.close();}
                        settle();
                        results["keyboard-hotplug-hides"]=core->physicalKeyboardConnected()&&!window->property("keyboardVisible").toBool();
                        core->textInputFocus(true);
                        results["keyboard-physical-suppresses"]=!window->property("keyboardVisible").toBool();
                        keyboard.remove();settle();
                        results["keyboard-unplug-opens"]=!core->physicalKeyboardConnected()&&window->property("keyboardVisible").toBool();
                        core->textInputFocus(false);
                    }
                    delete plain;
                    const bool contrast=core->preferences().value("highContrast").toBool();core->setting("highContrast",!contrast);
                    QFile file(qEnvironmentVariable("ETHERSHELL_CONFIG_DIR")+"/preferences.json");file.open(QIODevice::ReadOnly);
                    results["preference-readback"]=QJsonDocument::fromJson(file.readAll()).object().value("highContrast").toBool()==!contrast;
                    core->setting("highContrast",contrast);
                    QFile f(output+"/results.json");if(f.open(QIODevice::WriteOnly))f.write(QJsonDocument(results).toJson());
                    bool ok=true;for(auto i=results.begin();i!=results.end();++i)ok&=i.value().toBool();QCoreApplication::exit(ok?0:8);
                });
            });
        });
    }
public:
    SettingsUiTest(Core *c,QQuickWindow *w):QObject(c),core(c),window(w){
        output=qEnvironmentVariable("ETHERSHELL_MOBILE_TEST_OUTPUT");QDir().mkpath(output);
        // Xvfb has no window manager to process requestActivate(). Give only
        // this private test window input focus, as the desktop WM normally does.
        QProcess::execute("xdotool",{"windowfocus",QString::number(window->winId())});
        QTimer::singleShot(2500,this,[this]{
            window->setProperty("page","home");
            QTimer::singleShot(250,this,[this]{
                auto *scroll=find(window->contentItem(),"homeScroll");
                auto *content=find(window->contentItem(),"homeContent");
                results["home-viewport-width"]=scroll&&content&&content->width()<=scroll->width()+1;
                results["home-controls-geometry"]=content&&geometry(content,true);
                results["home-render"]=window->grabWindow().save(output+"/shell-home.png");
                window->setProperty("page","settings");workspace=window->findChild<QObject*>("settingsWorkspace");if(!workspace){QCoreApplication::exit(6);return;}
                if(qEnvironmentVariableIsSet("ETHERSHELL_KEYBOARD_UI_ONLY"))search();else render();
            });
        });
    }
};
