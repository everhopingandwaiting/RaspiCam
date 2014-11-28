#!/usr/bin/env python
# coding:utf-8

""" http server for control Rpi video process """

import os
import sys
import cgi
import socket
import threading
import SocketServer
import BaseHTTPServer
from raspiserver.logger import APPLOGGER
from raspiserver.utils import AppException

class HttpCtlServer(SocketServer.ThreadingMixIn, BaseHTTPServer.HTTPServer):
    """ ThreadedHTTPServer """
    def __init__(self, server_address, RequestHandler, cfg, recmng, vvpmng):
        self.allow_reuse_address = True
        self.cfg = cfg
        self.vvpmng = vvpmng
        self.recmng = recmng
        BaseHTTPServer.HTTPServer.__init__(self, server_address, RequestHandler)

class HttpCtlHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    """ HttpHandler for GET and POST """
    def __init__(self, request, client_address, server):
        self.server = server
        self.vvpmng = self.server.vvpmng
        self.recmng = self.server.recmng
        BaseHTTPServer.BaseHTTPRequestHandler.__init__(self, request,
                                                       client_address, server)
    def __sendmsg(self, code, msg):
        """ send msg to client """
        self.send_response(code)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(msg)

    def do_GET(self):
        """ GET """
        if self.path == '/':
            self.path = './www/index.html'
        try:
            # Check the file extension required and
            # set the right mime type
            sendreply = False
            if self.path.endswith('.html'):
                mimetype = 'text/html'
                sendreply = True
            if self.path.endswith('.jpg'):
                mimetype = 'image/jpg'
                sendreply = True
            if self.path.endswith('.gif'):
                mimetype = 'image/gif'
                sendreply = True
            if self.path.endswith('.js'):
                mimetype = 'application/javascript'
                sendreply = True
            if self.path.endswith('.css'):
                mimetype = 'text/css'
                sendreply = True

            if sendreply == True:
                # Open the static file requested and send it
                fhandler = open(os.curdir + os.sep + self.path)
                self.send_response(200)
                self.send_header('Content-type', mimetype)
                self.end_headers()
                self.wfile.write(fhandler.read())
                fhandler.close()
            return

        except IOError:
            self.send_error(404, 'File Not Found: %s' % self.path)

    def __start(self, form):
        """ start the video process """
        _ = form
        self.vvpmng.getlock()
        self.vvpmng.process_cmd.record = False
        self.vvpmng.process_cmd.recordfname = ''
        try:
            if not self.vvpmng.isset():
                self.vvpmng.start()
                self.__sendmsg(200, self.vvpmng.process_cmd.cmd())
                APPLOGGER.info('video server run.')
            else:
                if self.vvpmng.isrun():
                    APPLOGGER.info('already run subprocess: ' +
                                   str(self.vvpmng.currpid()))
                    APPLOGGER.info('video process already run.')
                    self.__sendmsg(200, 'already run')
                else:
                    APPLOGGER.info('subprocess not running')
            APPLOGGER.info('activeCount is ' + str(threading.activeCount()))
        finally:
            self.vvpmng.releaselock()

    def __stop(self, form):
        """ stop the video process """
        _ = form
        self.vvpmng.getlock()
        try:
            if not self.vvpmng.isset():
                APPLOGGER.warn('no process to stop')
                self.__sendmsg(200, 'no process to stop')
                return # jump to finally
            if self.vvpmng.isrun():
                self.vvpmng.stop()
                APPLOGGER.warn('terminating..')
                self.vvpmng.setprocess(None)
                self.__sendmsg(200, 'terminating..')
            else:
                APPLOGGER.info('process is terminate')
                self.vvpmng.setprocess(None)
                self.__sendmsg(200, 'process is terminated')
        finally:
            self.vvpmng.releaselock()

    def __change(self, form):
        """ change video process params """
        self.vvpmng.getlock()
        try:
            def getvalue(src):
                """ set value """
                retval = -1
                try:
                    retval = int(src)
                except ValueError as ex:
                    APPLOGGER.warn(ex)
                return retval
            def setpara(key, form, dst):
                """ set params """
                if key in form.keys():
                    tmpval = -1
                    tmpval = getvalue(form[key].value)
                    if tmpval != -1:
                        dst = tmpval
                return dst

            self.vvpmng.process_cmd.bright = \
                    setpara('para_bright', form, self.vvpmng.process_cmd.bright)
            self.vvpmng.process_cmd.fps = \
                    setpara('para_fps', form, self.vvpmng.process_cmd.fps)
            self.vvpmng.process_cmd.bitrate = \
                    setpara('para_bitrate', form, \
                    self.vvpmng.process_cmd.bitrate)
            self.vvpmng.process_cmd.width = \
                    setpara('para_width', form, self.vvpmng.process_cmd.width)
            self.vvpmng.process_cmd.height = \
                    setpara('para_height', form, self.vvpmng.process_cmd.height)

            APPLOGGER.debug(self.vvpmng.process_cmd.cmd())
            self.__sendmsg(200, self.vvpmng.process_cmd.cmd())

            if not self.vvpmng.isset():
                self.vvpmng.start()
                return
            if self.vvpmng.isrun():
                self.vvpmng.stop()
                self.vvpmng.setprocess(None)
                self.vvpmng.start()
            else:
                self.vvpmng.start()
        finally:
            self.vvpmng.releaselock()

    def __record(self, form):
        """ record video """
        _ = form
        recfname = ''
        can_rec = False
        self.recmng.getlock()
        try:
            if self.recmng.have_space() or self.recmng.cycle == True:
                recfname = self.recmng.gen_recordfname()
                if recfname == '':
                    raise AppException('record file name is null')
                can_rec = True
            else:
                raise AppException('no space to record')
        except AppException as ex:
            APPLOGGER.error(ex)
        finally:
            self.recmng.releaselock()

        if not can_rec:
            return

        self.vvpmng.getlock()
        self.vvpmng.process_cmd.record = True
        self.vvpmng.process_cmd.recordfname = recfname
        APPLOGGER.debug(self.vvpmng.process_cmd.cmd())
        try:
            if not self.vvpmng.isset():
                self.vvpmng.start()
                return
            if self.vvpmng.isrun():
                self.vvpmng.stop()
                self.vvpmng.setprocess(None)
                self.vvpmng.start()
            else:
                self.vvpmng.start()
        finally:
            self.__sendmsg(200, 'record start')
            self.vvpmng.releaselock()

    def do_POST(self):
        """ POST """
        APPLOGGER.debug(self.path)
        try:
            _environ = {'REQUEST_METHOD': 'POST',
                        'CONTENT_TYPE': self.headers['Content-Type'],}
        except KeyError:
            _environ = {}
        form = cgi.FieldStorage(fp=self.rfile,
                                headers=self.headers,
                                environ=_environ)
        action = self.path
        callinfo = action.replace('/', ' ').strip(' ')
        callinfo = '__' + callinfo
        callback = getattr(self, '_' + self.__class__.__name__ + callinfo)
        if callback != None and callable(callback):
            callback(form)
        else:
            APPLOGGER.debug(self.path)
            APPLOGGER.debug(str(form))
            self.send_response(503)
            self.end_headers()

def httpserve(ipaddr, serve_port, cfg, recmng, vvpmng):
    """ httpserve """
    try:
        if ipaddr is '':
            raise AppException('get local ip exp')
        if int(serve_port) <= 0 or int(serve_port) > 65535:
            raise AppException('port num err')
        if cfg == None:
            raise AppException('cfg is null')
        else:
            from utils import ConfigObject
            if type(cfg) != ConfigObject:
                raise AppException('parameter type not correct')
    except AppException as ex:
        APPLOGGER.error(ex)
    APPLOGGER.info('Server Up IP=%s PORT=%s', ipaddr, serve_port)
    server = None
    try:
        server = HttpCtlServer((ipaddr, serve_port), \
                HttpCtlHandler, cfg, recmng, vvpmng)
    except socket.error as ex:
        APPLOGGER.error(ex)
        sys.exit(1)
    if server:
        server.serve_forever()
    else:
        APPLOGGER.error('http server start error')

def __test():
    """ test function """
    from raspiserver.utils import ConfigReader
    from raspiserver.recordmng import RecordMng
    from raspiserver.utils import get_local_ip
    from raspiserver.processmng import VideoProcessMng
    config_parser = ConfigReader('./config/raspicam.cfg')
    cfg = config_parser.parser()
    server, port = get_local_ip(), 8080
    recmng = RecordMng(cfg.record)
    vvpmng = VideoProcessMng(cfg.video)
    httpserve(server, port, cfg, recmng, vvpmng)

if __name__ == '__main__':
    # run test python -m raspiserver.httpserver
    __test()