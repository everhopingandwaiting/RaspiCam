#!/usr/bin/env python
# coding:utf-8
# author TL
""" ctl server for Raspberry Pi vlc stream cam DEMO VERSION! """

import os
import signal
import socket
import threading
import netifaces
import SocketServer
import logging
import subprocess

def loggerinit():
    """ init logger """
    fstr = '%(asctime)s %(levelname)-8s %(funcName)s %(lineno)s %(message)s'
    fomatter = logging.Formatter(fstr)
    _logger = logging.getLogger('ctl_logger')
    _logger.setLevel(logging.DEBUG)
    shandler = logging.StreamHandler()
    fhandler = logging.FileHandler('/home/pi/ctlserver.log')
    shandler.setFormatter(fomatter)
    fhandler.setFormatter(fomatter)
    _logger.addHandler(shandler)
    _logger.addHandler(fhandler)
    return _logger

APPLOGGER = loggerinit()
APPLOGGER.setLevel('INFO')

class AppException(Exception):
    """ AppException """
    def __init__(self, value):
        self.value = value
        Exception.__init__(self)

    def __str__(self):
        return repr(self.value)

class RaspvidCmd(object):
    """ opt the cmd str """
    def __init__(self):
        self.fps = 30
        self.bitrate = 4500000 # 4.5MBit/s
        self.rtsp_port = 9000
        self.width = 1280
        self.height = 720
        self.stime = 0

    def cmd(self):
        """ return cmd str """
        raspvidbase = "raspivid"
        vlcbase = "cvlc"
        cmdstr = ''
        cmdstr += raspvidbase + ' '
        cmdstr += '-w ' + str(self.width) + ' '
        cmdstr += '-h ' + str(self.height) + ' '
        cmdstr += '-b '  + str(self.bitrate) + ' '
        cmdstr += '-fps ' + str(self.fps) + ' '
        cmdstr += '-vf -hf' + ' '
        cmdstr += '-t ' + str(self.stime) + ' '
        cmdstr += '-o -' + ' '

        cmdstr += '|' + ' '
        cmdstr += vlcbase + ' '
        cmdstr += "-vvv stream:///dev/stdin --sout '#rtp{sdp=rtsp://:"
        cmdstr += str(self.rtsp_port) + "/}' :demux=h264"
        return cmdstr

class ThreadedTCPRequestHandler(SocketServer.BaseRequestHandler):
    """ TCPServer RequestHandler """
    vvprocess = None
    def __init__(self, request, client_address, server):
        self.maxbuf = 2048
        self.maxthr = 4
        self.raspcmd = RaspvidCmd()
        SocketServer.BaseRequestHandler.__init__(self, request,
                                                 client_address, server)

    def __start_process(self):
        """ start video process """
        if ThreadedTCPRequestHandler.vvprocess is None:
            self.__sub_call(self.raspcmd.cmd())
            response = 'video process start'
            self.request.sendall(response)
        else:
            if ThreadedTCPRequestHandler.vvprocess.poll() is None:
                APPLOGGER.info('already run subprocess: ' +
                               str(ThreadedTCPRequestHandler.vvprocess.pid))
                response = 'video process already run'
                self.request.sendall(response)
            else:
                APPLOGGER.info('subprocess not running')
        APPLOGGER.info('activeCount is ' + str(threading.activeCount()))

    def __stop_process(self):
        """ __stop_process """
        if ThreadedTCPRequestHandler.vvprocess is None:
            APPLOGGER.warn('no process to stop')
            self.request.sendall('process already stop')
            return
        if ThreadedTCPRequestHandler.vvprocess.poll() is None:
            os.killpg(ThreadedTCPRequestHandler.vvprocess.pid,
                      signal.SIGTERM)
            # ThreadedTCPRequestHandler.vvprocess.terminate()
            APPLOGGER.warn('terminating..')
            ThreadedTCPRequestHandler.vvprocess = None
            self.request.sendall('terminate done') # fake done
        else:
            APPLOGGER.info('process is terminate')
            ThreadedTCPRequestHandler.vvprocess = None
            self.request.sendall('no process to stop')

    def __sysinfo(self):
        """ for get cmd """
        ipaddr, _ = self.server.server_address
        vport = self.raspcmd.rtsp_port
        self.request.sendall(str(ipaddr) + ':' + str(vport))

    def __changevprocss(self, data):
        """ change video process paramters """
        pass
    def __process_req(self, data):
        """ process req """
        data = data.strip(' \n')
        if len(data) <= 0:
            return
        if data.lower() == 'start':
            self.__start_process()
        elif data.lower() == 'stop':
            self.__stop_process()
        elif data.lower() == 'get':
            self.__sysinfo()
        elif data.lower().startwith('change'):
            self.__changevprocss(data)
        else:
            APPLOGGER.info('Cmd not support: ' + data)

    @classmethod
    def __sub_call(cls, cmdstr):
        """ sub_call for vv stream """
        APPLOGGER.info('subcall in porcess')
        child = subprocess.Popen(cmdstr, shell=True, preexec_fn=os.setsid)
        cls.vvprocess = child

    def handle(self):
        if threading.activeCount() > self.maxthr:
            APPLOGGER.warn('theading number exceeded')
            return
        data = self.request.recv(self.maxbuf)
        self.__process_req(data)

class ThreadedTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    """ TCPServer """
    pass


def __get_local_ip():
    """ get local ip address """
    ipaddr = netifaces.ifaddresses('eth0')[netifaces.AF_INET][0]['addr']
    return ipaddr

if __name__ == "__main__":

    LCIP = ''
    try:
        LCIP = __get_local_ip()
        if LCIP is '':
            raise AppException('get local ip exp')
    except AppException as ex:
        APPLOGGER.error(ex)

    HOST, PORT = LCIP, 9999
    try:
        SERVER = ThreadedTCPServer((HOST, PORT), ThreadedTCPRequestHandler)
    except socket.error as ex:
        APPLOGGER.error(ex)
        exit(-1)

    IP, PORT = SERVER.server_address
    SERVER_THR = threading.Thread(target=SERVER.serve_forever)
    # Exit the server thread when the main thread terminates
    SERVER_THR.daemon = True
    SERVER_THR.start()
    APPLOGGER.info('Server Up')
    SERVER.serve_forever()