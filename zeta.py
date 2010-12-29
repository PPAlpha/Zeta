#!/usr/bin/env python
# -*- coding: utf-8 -*-


import os,sys,signal,atexit
import logging
import operator
import traceback
import cStringIO as StringIO


logging.basicConfig(level=logging.DEBUG,format='%(asctime)s %(levelname)s %(message)s')
handler = logging.handlers.TimedRotatingFileHandler("logs/core.log","midnight")
logging.getLogger("").addHandler(handler)
debug = logging.debug
info = logging.info
warning = logging.warning
error = logging.error
critical = logging.critical
exception = logging.exception
atexit.register(logging.shutdown)


def fork():
    child = os.fork()
    if child != 0:
        print 'Parent exiting, child PID: %s' % child
        os._exit(0)
info('first fork')
fork()
info('setsid')
os.setsid()
info('second fork')
fork()
sys.stdin.close()
info('closing everything')
sys.stdin.close()
sys.stdout.close()
sys.stderr.close()
sys.stdout = StringIO.StringIO()
sys.stderr = StringIO.StringIO()
os.close(0)
os.close(1)
os.close(2)
fd = os.open('/dev/null', os.O_RDWR)
os.dup2(fd, 0)
os.dup2(fd, 1)
os.dup2(fd, 2)
signal.signal(signal.SIGHUP, signal.SIG_IGN)
info('Completed daemonization.  Current PID: %s', os.getpid())

pidFile = 'zeta.pid'
info('writing to pidfile')
if pidFile:
    try:
        fd = file(pidFile, 'w')
        pid = os.getpid()
        fd.write('%s\n' % pid)
        fd.close()
        def removePidFile():
            try:
                os.remove(pidFile)
                info('removed pidfile')
            except EnvironmentError, e:
                error('Could not remove pid file: %s', e)
        atexit.register(removePidFile)
    except EnvironmentError, e:
        fatal('Error opening/writing pid file %s: %s', pidFile, e)
        sys.exit(-1)








info('starting program')





import socket,string,time,textwrap
import thread
import botconfig as config
import subprocess,re
import plugins
try:
    import feedparser
except:
    pass#just make sure to set config.rss = {}
channelLevels = {"a":"admins","h":"halfops","o":"ops","q":"founders","v":"voices"}
defaultChanDict = {"cankick":False,"modeQ":False,
"voices":[],"halfops":[],"ops":[],"admins":[],"founders":[],"users":[],"normals":[],
"userips":{}}

class IRC:
    def __init__(self):
        self.nick = config.nick
        self.host = config.host
        self.port = config.port
        self.password = config.password
        self.defChannels = config.defChannels
        self.debugChan = config.debugChan
        self.defModes = config.defModes
        self.enforceOneIP = config.enforceOneIP
        self.enforceCaps = config.enforceCaps
        self.enforceCensored = config.enforceCensored
        self.enforceHello = config.enforceHello
        self.autoRejoin = config.autoRejoin
        self.identifiables = config.identifiables
        self.autoIdentify = config.autoIdentify
        self.quitMsg = config.quitMsg
        self.sleeptime = config.sleeptime
        self.badwords = config.badwords
        self.rss = config.rss
        self.channelFeeds = {}
        self.identified = False
        self.chanlist = []
        self.chans = {}
        #self.urlHandler = subprocess.Popen('./url', stdin=subprocess.PIPE)
        self.sock=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        self.cron = {}
        self.owners = []
        self.identifiedUsers = {}#stored like /cs access
        self.ignores = []
        self.tmpChan = None#hate to use this...
        self.tmpProcess = None#hate to use this...
        self.tmpNickProcess = None
        self.tmpReplyTo = None
        self.lastUserIp = ""
        self.servicesRunning = True
        self.loadPlugins()
    def debug_msg(self,msg):
        if(self.debugChan in self.chanlist):
            self.raw("PRIVMSG %s :%s"%(self.debugChan,msg))
        debug(msg)
    def on_msg(self,t):
        return
    def on_join(self,t):
        return
    def startup(self):
        self.join(",".join(self.defChannels))
        self.umode(self.defModes)
        #thread.start_new_thread(self.execCron,())
        self.raw("watch +NickServ")
    def raw(self,q):
        self.sock.send("%s\r\n"%q)
        info("<<"+str(q))
    def run(self):
        self.raw("USER %s 0 0 :%s"%(self.nick,self.nick))
        self.raw("NICK %s"% self.nick)
        self.buffer = ""
        while True:
            time.sleep(self.sleeptime)
            r = self.sock.recv(1024)
            if not r: break
            self.buffer += r
            lines = self.buffer.split("\r\n")
            self.buffer = lines.pop()
            for t in lines:
                if not t: continue
                info(">>"+str(t))
                self.handleData(t)
    def ns(self,n):
        self.raw("PRIVMSG NickServ %s"%n)
    def cs(self,n):
        self.raw("PRIVMSG ChanServ %s"%n)
    def umode(self,modes):
        self.raw("MODE %s %s"%(self.nick,modes))
    def mode(self,where,modes):
        self.raw("MODE %s %s"%(where,modes))
    def join(self,channels="0",keys=""):
        self.raw("JOIN %s %s"%(channels,keys))
    def say(self,t,n):
        self.raw("PRIVMSG %s %s"%(t,n))
    def notice(self,t,n):
        self.raw("NOTICE %s %s"%(t,n))
    def kick(self,channel,target,message=""):
        self.raw("KICK %s %s %s"%(channel,target,message))
    def quit(self,message=None):
        if not message:
            message = self.quitMsg
        self.raw("QUIT %s"%message)
    def handleData(self,t):
        if t[:4] == "PING":
            q = "PO"+t[2:]
            self.raw(q)
            return
        p = t.split(" ")
        if len(p) == 1: return
        fuser = p[0][1:]
        user = fuser.split("!")[0]
        command = p[1].upper()
        if command == "376" and not self.identified:
            self.ns("IDENTIFY %s"%self.password)
            self.identified = True
            self.startup()
        if command == "353":# /names
            where = p[4].lower()
            names = t.split(":")[2]
            self.chans[where]["users"] = []
            self.chans[where]["voices"] = []
            self.chans[where]["halfops"] = []
            self.chans[where]["ops"] = []
            self.chans[where]["admins"] = []
            self.chans[where]["founders"] = []
            self.chans[where]["normals"] = []
            for n in names.split(" "):
                name = n.strip("+%@&~!").lower()
                if not name:
                    continue
                if name != n:
                    if n[0] == "+":
                        self.chans[where]["voices"].append(name)
                    elif n[0] == "%":
                        self.chans[where]["halfops"].append(name)
                    elif n[0] == "@":
                        self.chans[where]["ops"].append(name)
                    elif n[0] == "&":
                        self.chans[where]["admins"].append(name)
                    elif n[0] == "~":
                        self.chans[where]["founders"].append(name)
                    else:
                        self.chans[where]["normals"].append(name)
                self.chans[where]["users"].append(name)
            if where in self.enforceOneIP:#really hard to enforce 2 chans
                self.chans[where]["userips"] = {}
                self.tmpChan = where
                self.tmpProcess = "getipfromchan"
                toSend = 0
                namelist = []
                for name in self.chans[where]["users"]:
                    namelist.append(name)
                    toSend += 1
                    if toSend == 5:
                        self.raw("USERIP %s"%' '.join(namelist))
                        namelist = []
                        toSend = 0
                    self.lastUserIp = name
                if toSend != 0:
                    self.raw("USERIP %s"%' '.join(namelist))
        if command == "340" and self.tmpProcess == "getipfromchan":
            where = self.tmpChan.lower()
            userips = t.split(":")[2]
            for userip in userips.split(" "):
                if not userip:
                    continue
                username = userip.split("=")[0]
                name = username.lower().strip("*")
                if name == self.lastUserIp:
                    self.lastUserIp = ""
                    self.tmpProcess = None
                    self.tmpChan = None
                fullhost = userip.split("=")[1]
                ip = fullhost.split("@")[1].strip()
                self.chans[where]["userips"][ip] = name
        if command == "340" and self.tmpProcess == "checkuserinchan":
            where = self.tmpChan.lower()
            userip = t.split(":")[2]
            username = userip.split("=")[0]
            fullhost = userip.split("=")[1]
            ip = fullhost.split("@")[1].strip()
            if where in self.enforceOneIP:
                if ip in self.chans[where]["userips"].keys():
                    if self.chans[where]["cankick"]:
                        target = self.chans[where]["userips"][ip]
                        if target in self.chans[where]["normals"]:
                            self.kick(where,target,"%s :One username per IP"%username.strip("*"))
            self.chans[where]["userips"][ip] = username.lower().strip("*")
            self.tmpProcess = None
            self.tmpChan = None
        if command == "604":
            nick = p[3]
            if nick.lower() == "nickserv":
                self.servicesRunning = True
                self.debug_msg("Services are currently running")
        if command == "600":
            nick = p[3]
            if nick.lower() == "nickserv":
                self.servicesRunning = True
            self.ns("IDENTIFY %s"%self.password)
            self.debug_msg("Services are currently running")
        if command == "601":
            nick = p[3]
            if nick.lower() == "nickserv":
                self.servicesRunning = False
                self.debug_msg("Services have STOPPED running")
        if command == "JOIN" and user!=self.nick:
            where = p[2][1:].lower()
            if self.tmpProcess == None:#give up doing multiple things at the same time
                self.tmpProcess = "checkuserinchan"
                self.tmpChan = where
                self.raw("USERIP %s"%user)
                self.addToChan(where,user)
            if where in self.enforceHello:
                self.say(where,"Hi %s"%user)
        if command == "JOIN" and user==self.nick:
            where = p[2][1:].lower()
            self.chanlist.append(where)
            self.chans[where] = defaultChanDict.copy()
            if where in self.enforceHello:
                self.say(where,"Hello Everyone!")
        if command == "NICK":
            nick = t.split(":")[2]
            nickname = nick.lower()
            if user==self.nick:
                self.nick = nick
            name = user.lower()
            for where in self.chanlist:
                if name in self.chans[where]["users"]:
                    self.chans[where]["users"].remove(name)
                    self.chans[where]["users"].append(nickname)
                if name in self.chans[where]["normals"]:
                    self.chans[where]["normals"].remove(name)
                    self.chans[where]["normals"].append(nickname)
                if name in self.chans[where]["voices"]:
                    self.chans[where]["voices"].remove(name)
                    self.chans[where]["voices"].append(nickname)
                if name in self.chans[where]["halfops"]:
                    self.chans[where]["halfops"].remove(name)
                    self.chans[where]["halfops"].append(nickname)
                if name in self.chans[where]["ops"]:
                    self.chans[where]["ops"].remove(name)
                    self.chans[where]["ops"].append(nickname)
                if name in self.chans[where]["admins"]:
                    self.chans[where]["admins"].remove(name)
                    self.chans[where]["admins"].append(nickname)
                if name in self.chans[where]["founders"]:
                    self.chans[where]["founders"].remove(name)
                    self.chans[where]["founders"].append(nickname)
                for ip in self.chans[where]["userips"].keys():
                    if self.chans[where]["userips"][ip] == name:
                        self.chans[where]["userips"][ip] = nickname
        if command == "KICK":
            where = p[2].lower()
            target = p[3]
            name = target.lower()
            self.removeFromChan(where,name)
            if name == self.nick.lower():
                self.chanlist.remove(where)
                self.join(where)
        if command == "PART":
            where = p[2].lower()
            self.removeFromChan(where,user.lower())
        if command == "QUIT":
            name = user.lower()
            for where in self.chanlist:
                self.removeFromChan(where,name)
        if command == "NOTICE":
            where = p[2].lower()
            message = ":".join(t.split(":")[2:])
            words = message.strip().split(" ")
            if where == self.nick.lower():
                if user=="NickServ" and self.tmpNickProcess == "seen":
                    if words[1] == "is" and words[2] == "currently" and words[3] == "online.":
                        self.notice(self.tmpReplyTo,message)
                        self.tmpNickProcess = None
                        self.tmpReplyTo = None
                    if words[0] == "Last" and words[1] == "seen" and words[2] == "time:":
                        #tm_year=2010, tm_mon=10, tm_mday=16, tm_hour=23, tm_min=32, tm_sec=39, tm_wday=5, tm_yday=289, tm_isdst=1
                        t = time.strptime(" ".join(words[3:-1]),"%b %d %H:%M:%S %Y")
                        now = time.localtime()
                        newmsg = []
                        year = mon = mday = hour = tmin = sec = 0
                        sec += now.tm_sec - t.tm_sec
                        if sec < 0:
                            sec += 60
                            tmin -= 1
                        tmin += now.tm_min - t.tm_min
                        if tmin < 0:
                            tmin += 60
                            hour -= 1
                        hour += now.tm_hour - t.tm_hour
                        if hour < 0:
                            hour += 24
                            mday -= 1
                        mday += now.tm_mday - t.tm_mday
                        if mday < 0:
                            dayofmonth = 31 - (t.tm_mon%2)
                            if mon == 2:
                                if t.tm_year%4: dayofmonth = 28
                                else: dayofmonth = 29
                            mday += dayofmonth
                            mon -= 1
                        mon += now.tm_mon - t.tm_mon
                        if mon < 0:
                            mon += 12
                            year -= 1
                        year += now.tm_year - t.tm_year
                        s = "s"
                        if year:
                            if year == 1: s = ""
                            newmsg.append("%i year%s"%(year,s))
                        s = "s"
                        if mon:
                            if mon == 1: s = ""
                            newmsg.append("%i month%s"%(mon,s))
                        s = "s"
                        if mday:
                            if mday == 1: s = ""
                            newmsg.append("%i day%s"%(mday,s))
                        s = "s"
                        if hour:
                            if hour == 1: s = ""
                            newmsg.append("%i hour%s"%(hour,s))
                        s = "s"
                        if tmin:
                            if tmin == 1: s = ""
                            newmsg.append("%i minute%s"%(tmin,s))
                        s = "s"
                        if sec:
                            if sec == 1: s = ""
                            newmsg.append("%i second%s"%(sec,s))
                        self.notice(self.tmpReplyTo,"Last seen %s ago."%(", ".join(newmsg)))
                        self.tmpNickProcess = None
                        self.tmpReplyTo = None
                    if words[0] == "Nick" and words[-1] == "registered." and words[-2] == "isn't":
                        self.notice(self.tmpReplyTo,message)
                        self.tmpNickProcess = None
                        self.tmpReplyTo = None
        if command == "PRIVMSG":
            where = p[2].lower()
            message = ":".join(t.split(":")[2:])
            words = message.split(" ")
            if where == self.nick.lower():#PM
                lcmd = words[0].lower()
                if lcmd == "autoidentify":
                    if self.makeAutoIdentified(fuser):
                        return self.notice(user,"Operation succeeded! You are now identified.")
                if "identify" == lcmd:
                    if len(words)>1:
                        debug("identify attempt: "+fuser)
                        if self.makeIdentified(fuser,words[1],words[2]):
                            return self.notice(user,"Operation succeeded! You are now identified.")
                if self.getAccess(fuser)==10001:
                    if "quit" == lcmd:
                        self.quit(message[5:])
                    if "raw" == lcmd:
                        self.raw(message[4:])
                    if "reload" == lcmd:
                        self.reloadPlugins()
            if where[0]=="#":
                if message[0]=="!":
                    words[0] = words[0].lower()
                    if words[0] == "!op" and not self.servicesRunning:
                        if self.getAccess(fuser) > 5:
                            if len(words) > 1:
                                self.mode(where,"+o %s"%words[1])
                            else:
                                self.mode(where,"+o %s"%user)
                    if words[0] == "!seen":
                        if self.servicesRunning:
                            if len(words) > 1:
                                self.tmpNickProcess = "seen"
                                self.tmpReplyTo = user
                                self.ns("info %s"%words[1])
                    if words[0] in ("!status","!feed","!news") and self.getAccess(fuser) > 5:
                        thread.start_new_thread(self.checkRSS,(where,))
                if 'http:' in message:
                    url = re.findall("http://([^ \r\n]+)",message)
                    #print url
                    urlHandler = subprocess.Popen(['./url',url[0]],stdout=subprocess.PIPE)
                    tOut = urlHandler.communicate()[0]
                    if "Pokémon Infinity Online | Pokémon Online Game" not in tOut and tOut != "Title: \n":
                        self.say(where,tOut)
                if where in self.enforceCaps:
                    if message.upper()==message and len(message)>8:
                        if self.chans[where]["cankick"]:
                            target = user.lower()
                            if target in self.chans[where]["normals"]:
                                self.kick(where,user,"Turn the caps lock OFF!")
                if where in self.enforceCensored:
                    for badword in self.badwords:
                        if badword in message:
                            if self.chans[where]["cankick"]:
                                target = user.lower()
                                if target in self.chans[where]["normals"]:
                                    self.kick(where,user,"Watch your language!")
            self.on_msg(t)
        if command == "MODE":
            where = p[2].lower()
            if where[0]=="#":
                self.handleChanMode()
                plus = True
                modes = p[3]
                arg = 4
                for mode in modes:
                    if mode == "+":
                        plus = True
                    elif mode == "-":
                        plus = False
                    elif mode == "a":
                        target = p[arg].lower()
                        if plus:
                            self.chans[where]["admins"].append(target)
                            if target in self.chans[where]["normals"]:
                                self.chans[where]["normals"].remove(target)#lets not remove them if they had admin at one point
                        if not plus and target in self.chans[where]["admins"]:#yeah, it CAN sometimes not be in the admin list. ie, user is +qa, and loses -a, how would we have know it to be there?
                            self.chans[where]["admins"].remove(target)
                        arg += 1
                    elif mode == "b":
                        hostname = p[arg].lower()
                        self.handleUserBan(where,hostname,plus)
                        arg += 1
                    elif mode == "c":
                        pass#mirc codes
                        #self.canUseColors[where] = not plus
                    elif mode == "f":
                        #ugly, lets leave this one to the channel to handle
                        arg += 1
                    elif mode == "h":
                        target = p[arg].lower()
                        if plus:
                            self.chans[where]["halfops"].append(target)
                            if target in self.chans[where]["normals"]:
                                self.chans[where]["normals"].remove(target)
                        if not plus and target in self.chans[where]["halfops"]:#see admin note
                            self.chans[where]["halfops"].remove(target)
                        arg += 1
                    elif mode == "i":
                        pass#invite modes
                        #a few things with KNOCKs and whatnot, may need to unset V
                    elif mode == "j":
                        #ugly, lets leave this one to the channel to handle
                        arg += 1
                    elif mode == "k":
                        #key has been [un]set
                        #self.chanKeys[where] = p[arg]
                        arg += 1
                    elif mode == "l":
                        #ugly, lets leave this one to the channel to handle
                        arg += 1
                    elif mode == "m":
                        pass#muted channel
                    elif mode == "n":
                        pass# </facepalm>
                    elif mode == "o":
                        target = p[arg].lower()
                        if plus:
                            self.chans[where]["ops"].append(target)
                            if target in self.chans[where]["normals"]:
                                self.chans[where]["normals"].remove(target)
                        if not plus and target in self.chans[where]["ops"]:#see admin note
                            self.chans[where]["ops"].remove(target)
                        arg += 1
                    elif mode == "p":
                        pass#private
                    elif mode == "q":
                        target = p[arg].lower()
                        if plus:
                            self.chans[where]["ops"].append(target)
                            if target in self.chans[where]["normals"]:
                                self.chans[where]["normals"].remove(target)
                        if not plus and target in self.chans[where]["ops"]:#see admin note
                            self.chans[where]["ops"].remove(target)
                        arg += 1
                    elif mode == "r":
                        pass#who wants to argue with the U:Lines?
                    elif mode == "s":
                        pass#secret
                    elif mode == "t":
                        pass#h+ required to set topic
                    elif mode == "v":
                        target = p[arg].lower()
                        if plus:
                            self.chans[where]["voices"].append(target)
                            if target in self.chans[where]["normals"]:
                                self.chans[where]["normals"].remove(target)
                        if not plus and target in self.chans[where]["voices"]:#see admin note
                            self.chans[where]["voices"].remove(target)
                        arg += 1
                    elif mode == "u":
                        pass#Hide the channel :P (can still see ops)
                    elif mode == "z":
                        pass#SSL only... why?
                    elif mode == "A":
                        pass#meh, I should probably stick around and log for as long as I can
                    elif mode == "C":
                        pass#don't /notice this channel
                    elif mode == "G":
                        pass#no-cussing, it's fucking dickhead shit!
                    elif mode == "K":
                        pass#no knocking
                    elif mode == "L":
                        arg += 1#maybe I should mod the new channel?
                    elif mode == "M":
                        pass#need to be registered to talk, (Which I am)
                    elif mode == "N":
                        pass#leave before changing nick
                    elif mode == "O":
                        pass#meh, I should probably stick around and log for as long as I can
                    elif mode == "Q":
                        self.chans[where]["modeQ"] = not plus
                    elif mode == "R":
                        pass#need to be registered to join, (Which I am)
                    elif mode == "S":
                        pass#colors are stripped
                    elif mode == "T":
                        pass#don't /notice this channel
                    elif mode == "V":
                        pass#I should probably force it back on
                        
                self.handleMyChannelLevel(where)
        if command == "INVITE":
            target = p[2]
            targetchan = t.split(":")[2].lower()
            if target == self.nick and self.getAccess(fuser)>4:
                self.join(targetchan)
    def removeFromChan(self,where,name):
        name = name.lower()
        if name in self.chans[where]["users"]:
            self.chans[where]["users"].remove(name)
        if name in self.chans[where]["voices"]:
            self.chans[where]["voices"].remove(name)
        if name in self.chans[where]["halfops"]:
            self.chans[where]["halfops"].remove(name)
        if name in self.chans[where]["ops"]:
            self.chans[where]["ops"].remove(name)
        if name in self.chans[where]["admins"]:
            self.chans[where]["admins"].remove(name)
        if name in self.chans[where]["founders"]:
            self.chans[where]["founders"].remove(name)
        for ip in self.chans[where]["userips"].copy():
            if self.chans[where]["userips"][ip] == name:
                del self.chans[where]["userips"][ip]
    def addToChan(self,where,name):
        name = name.lower()
        self.chans[where]["users"].append(name)
        self.chans[where]["normals"].append(name)
    def handleChanMode(self):
        return
    def handleUserBan(self,channel,host,isset):
        return
    def handleMyChannelLevel(self,where):
        name = self.nick.lower()
        if name in self.chans[where]["halfops"]:
            self.chans[where]["cankick"] = True
        if name in self.chans[where]["ops"]:
            self.chans[where]["cankick"] = True
        if name in self.chans[where]["admins"]:
            self.chans[where]["cankick"] = True
        if name in self.chans[where]["founders"]:
            self.chans[where]["cankick"] = True
        if self.chans[where]["modeQ"]:
            self.chans[where]["cankick"] = False
    def checkRSS(self,where):
        if where in self.rss.keys():
            feed = feedparser.parse(self.rss[where])
            for text in textwrap.wrap(feed['items'][0]['description'],500):
                self.say(where,text)
    def execCron(self):
        while True:
            tmpCron = {}
            cronKeys = self.cron.keys()[:]
            for when in cronKeys:
                if when < time.time():
                    for cmd in self.cron[when]:
                        exec(cmd)
                    del(self.cron[when])
    def addCron(self,cmd,sec):
        when = time.time() + sec
        if when not in self.cron.keys():
            self.cron[when] = []
        #print "Added: ",cmd," to go off at: ",when," (in ",sec," seconds)"
        self.cron[when].append(cmd)
    def makeOwner(self,user,password):
        if password == self.identifyPassword:
            self.owners.append(user)
            return True
        return False
    def makeIdentified(self,fuser,username,password):
        user = fuser.split("!")[1].lower()
        if username in self.identifiables:
            if password == self.identifiables[username][0]:
                self.identifiedUsers[user] = self.identifiables[username][1]
                return True
            return False
    def makeAutoIdentified(self,fuser):
        host = fuser.split("!")[1].lower()
        if host in self.autoIdentify.keys():
            self.identifiedUsers[host] = self.identifiables[self.autoIdentify[host]][1]
            return True
        return False
    def getAccess(self,fuser):
        user = fuser.split("!")[1].lower()
        if user in self.identifiedUsers:
            return self.identifiedUsers[user]
        return 0
    def isMe(self,name):
        if name.lower() == self.nick.lower():
            return True
        return False
    def isOwner(self,user):
        return user in self.owners
    def reloadPlugins(self):
        print "Reloading...."
        reload(plugins)
        print "Configuring Components"
        self.loadPlugins()
        print "Done."
    def loadPlugins(self):
        self.on_msg = plugins.on_msg
        self.on_join = plugins.on_join
        plugins.on_load()

irc = IRC()
irc.run()
