# -*- coding: utf-8 -*-

nick = "USERNAME"#edit
host = "NETWORK"#edit
port = 6667#no ssl support
password = "PASSWORD"#edit
defChannels = ["#CHAN1","#CHAN2"]#edit
defModes = "+ixB"
enforceOneIP = ["#CHAN1"]#edit
enforceCaps = ["#CHAN2"]#edit
enforceCensored = ["#CHAN1","#CHAN2"]#edit
enforceHello = ["#CHAN2"]#edit
autoRejoin = True
identifiables = {"OWNERNAME":["PASSWORD",10001],"OPNAME":["PASSWORD2",5]}#edit
autoIdentify = {"someuser@somehost.example.com":"OWNERNAME","someoneelse@someotherplace.net":"OPNAME"}
quitMsg = "QUIT"#edit
sleeptime = 1.0
badwords = ["fuck","shit","dick","sex","<censored>"]
rss = {"#CHAN1":"http://blog.chan1.example.com/rss.xml","#CHAN3":"http://blog.chan3.example.com/feed.rss"}
