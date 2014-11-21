#ifndef CONTROLCLIENT_H
#define CONTROLCLIENT_H

#include <QObject>
#include <QHostAddress>
#include <QMap>
#include <QStringList>
#include "tcprequest.h"

class ControlClient : public QObject
{
    Q_OBJECT
public:
    explicit ControlClient(QHostAddress server, qint16 port, QObject *parent = 0);
    ~ControlClient();
    void start();
    void stop();
    void change(QString params);
    void record();
signals:
    void routeOut(QMap<QString, QString>);
public slots:
    void servermsg(QString msg);
private:
    void _sig_cmd(const QString &cmd);
    void _para_cmd(const QString &prefix, const QString &params);
private:

    QMap<QString, QString> _parsecmd(QString cmdstr);
    QString _parsepara(QString para);
    QHostAddress _serveraddr;
    qint16 _port;
    TcpRequest *_request;
    QString _raspcmd_prefix;
    QStringList _supportcmds;

};

#endif // CONTROLCLIENT_H
