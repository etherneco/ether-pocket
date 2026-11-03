#pragma once
#include "core.h"
#include <QWindow>
#include <QQuickWindow>
#include <QKeyEvent>
#include <QGuiApplication>
#include <QFile>
#include <QJsonDocument>
#include <QDir>
#include <QTimer>
#include <QDebug>
#include <QCursor>

class InputProbe : public QWindow {
public:
    QString typed;
    bool ctrlC=false,arrow=false;
    bool event(QEvent *event) override {
        if(event->type()==QEvent::KeyPress){auto*k=static_cast<QKeyEvent*>(event);if(k->key()==Qt::Key_C && k->modifiers().testFlag(Qt::ControlModifier))ctrlC=true;else if(k->key()==Qt::Key_Left)arrow=true;else typed+=k->text();}
        return QWindow::event(event);
    }
};

// Exercises the real backend and X server in the logged-in ARM64 session.
// Only uses synthetic test text. Leaves user applications and network state intact.
class Integration : public QObject {
public:
    Integration(Core *core,QQuickWindow *root):QObject(core),core(core),root(root){
        dir=QDir::homePath()+"/ethershell-validation";QDir().mkpath(dir);
        QTimer::singleShot(1500,this,[this]{start();});
    }
private:
    Core *core;QQuickWindow *root;InputProbe probe;QVariantMap results;QString dir;QStringList screens={"home","apps","settings","tasks","notices","store","touchpad","gallery"};int stage=0;bool oldTheme=false;
    void start(){
        results["applications_discovered"]=core->apps().size()>5;
        results["battery_readable"]=!core->telemetry()["battery"].toString().isEmpty();
        results["physical_display_discovered"]=core->displays().size()>0;
        oldTheme=core->preferences()["dark"].toBool();core->setting("dark",!oldTheme);
        results["theme_changed"]=core->preferences()["dark"].toBool()!=oldTheme;
        core->setting("dark",oldTheme);
        core->setting("scale",99);results["invalid_scale_rejected"]=core->preferences()["scale"].toDouble()!=99;
        core->notify("Test EtherShell","Rzeczywiste wejście X11 i renderowanie Qt 6");
        screenshot();
    }
    void screenshot(){
        if(stage>=screens.size()){input();return;}
        const QString page=screens[stage++];root->setProperty("page",page);
        QTimer::singleShot(650,this,[this,page]{auto img=root->grabWindow();results["render_"+page]=!img.isNull() && img.save(dir+"/"+page+".png");screenshot();});
    }
    void input(){
        root->setProperty("page","home");probe.setTitle("EtherShell input validation");probe.resize(640,400);probe.show();probe.raise();probe.requestActivate();
        QTimer::singleShot(500,this,[this]{
            root->setProperty("keyboardVisible",true);
            QTimer::singleShot(700,this,[this]{
                results["keyboard_preserves_focus"]=QGuiApplication::focusWindow()==&probe;
                for(auto *w:QGuiApplication::allWindows())if(w->title()=="EtherKeyboard"){auto*q=qobject_cast<QQuickWindow*>(w);if(q){results["render_keyboard"]=q->grabWindow().save(dir+"/keyboard.png");double scale=q->width()/420.;QCursor::setPos(q->x()+25*scale,q->y()+64*scale);core->mouse(1,true);core->mouse(1,false);}}
                QTimer::singleShot(150,this,[this]{core->text(QString::fromUtf8("zażółć gęślą jaźń"));});
                QTimer::singleShot(2000,this,[this]{
                    results["touch_keyboard_key"]=probe.typed.startsWith("q");
                    results["unicode_x11_input"]=probe.typed==QString::fromUtf8("qzażółć gęślą jaźń");
                    qInfo()<<"Synthetic Unicode probe:"<<probe.typed;
                    const auto oldLayout=core->preferences()["layout"];core->setting("layout","PL");
                    for(auto *w:QGuiApplication::allWindows())if(w->title()=="EtherKeyboard"){QMetaObject::invokeMethod(w,"send",Q_ARG(QVariant,QVariant("AltGr")));QMetaObject::invokeMethod(w,"send",Q_ARG(QVariant,QVariant("a")));}
                    core->setting("layout",oldLayout);
                    core->text("abc");core->key("Return");core->key("c",true);core->key("Left");
                    QTimer::singleShot(800,this,[this]{results["ctrl_c"]=probe.ctrlC;results["arrow_key"]=probe.arrow;results["input_order"]=probe.typed.endsWith("abc\r");results["polish_altgr"]=probe.typed.endsWith(QString::fromUtf8("ąabc\r"));root->setProperty("keyboardVisible",false);probe.hide();launch();});
                });
            });
        });
    }
    void launch(){
        // Launch a disposable terminal, close only its unique test window.
        QFile receiver(dir+"/terminal-probe.py");receiver.open(QIODevice::WriteOnly);receiver.write("import os,tty,termios\nfrom pathlib import Path\np=Path.home()/'ethershell-validation/terminal-input.bin'\nold=termios.tcgetattr(0)\ntty.setraw(0)\ndata=b''\ntry:\n while not data.endswith(b'\\r'):\n  data+=os.read(0,1)\n p.write_bytes(data)\nfinally:\n termios.tcsetattr(0,termios.TCSADRAIN,old)\n");receiver.close();
        auto *p=new QProcess(this);p->start("xfce4-terminal",{"--disable-server","--title=EtherShell-validation-terminal","--command=python3 "+dir+"/terminal-probe.py"});
        QTimer::singleShot(2000,this,[this]{
            core->refresh();
            QTimer::singleShot(600,this,[this]{
                bool found=false;for(auto v:core->windows()){auto w=v.toMap();if(w["title"].toString().contains("EtherShell-validation-terminal")){found=true;core->windowAction(w["id"].toString(),"activate");}}
                results["real_terminal_window"]=found;
                QTimer::singleShot(600,this,[this]{core->text(QString::fromUtf8("zażółć"));core->key("Return");
                    QTimer::singleShot(2000,this,[this]{QFile input(dir+"/terminal-input.bin");input.open(QIODevice::ReadOnly);results["terminal_unicode_input"]=input.readAll()==QString::fromUtf8("zażółć\r").toUtf8();finish();});
                });
            });
        });
    }
    void finish(){
        core->diagnose(dir+"/capabilities.json");
        bool passed=true;for(auto v:results)if(!v.toBool())passed=false;
        results["passed"]=passed;
        QFile file(dir+"/results.json");file.open(QIODevice::WriteOnly);file.write(QJsonDocument::fromVariant(results).toJson());file.close();
        qInfo().noquote()<<QJsonDocument::fromVariant(results).toJson();
        QGuiApplication::exit(passed?0:4);
    }
};
