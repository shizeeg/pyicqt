#This scheduler works by creating a separate thread for each class of packets, and letting these threads
#manage the execution of their respective messages. If a thread finds that it has no more messages in its
#queue even after waiting a short while the thread will terminate, saving its state. This is also the exit
#condition for the Scheduler; there is no way to shut down all threads when a user logs out. If another
#message shows up destined for a terminated thread, the thread is recreated from the data it saved when
#it exited.
#
#I believe this will lead to two or three threads per online user after the startup period is over.

import threading
import time
import Queue
import sys

class Scheduler:
    def __init__(self,handler):
        self.freezer={}
        self.handler=handler
        self.bigLock=threading.Lock()
        # Create default class, just in case
        self.threads={'default' : self.QueueThread('default',handler,self.freezer)}
        self.snacs={'default':'default'}

    def enqueue(self,fam,sub,snac):
        snacid=str(fam)+str(sub)
        if (not self.snacs.has_key(snacid)):
            # We don't have a class, so assume class "default"
            snacid='default'
        classid=self.snacs[snacid]
        self.bigLock.acquire()
        if (not self.threads.has_key(classid) or not self.threads[classid].isAlive()):
            self.threads[classid]=self.QueueThread(classid,self.handler,self.freezer)
        self.threads[classid].enqueue(snac)
        self.bigLock.release()
        
    def bindIntoClass(self,fam,sub,classid):
        """
        Messages come in marked with fam and sub; we need to bind them into classes.
        AOL tells us what fam,sub combination goes to which class.
        """
        snacid=str(fam)+str(sub)
        classid=str(classid)
        self.snacs[snacid]=classid

    def setStat(self,classid,window=-1,clear=-1,alert=-1,limit=-1,disconnect=-1,rate=-1,lasttime=-1,maxrate=-1):
        """
        AOL also tells us what our limits are and what our current rate is.
        """
        classid=str(classid)
        target=clear
        self.bigLock.acquire()
        if (not self.threads.has_key(classid) or not self.threads[classid].isAlive()):
            self.threads[classid]=self.QueueThread(classid,self.handler,self.freezer)
        self.threads[classid].setStat(window=window,rate=rate,target=target,lasttime=lasttime,max=maxrate)
        self.bigLock.release()
        
    class QueueThread(threading.Thread):
            
        def __init__(self,name,handler,freezer):
            threading.Thread.__init__(self)
            self.name=name
            self.handler=handler
            self.freezer=freezer
            if (freezer.has_key(name)):
                self.rm=freezer[name]
            else:
                self.rm=Scheduler.RateManager()
                self.freezer[name]=self.rm
            self.q=Queue.Queue()
            self.setDaemon(True)
            self.start()
    
        def run(self):
            while True:
               try:
                    snac=self.q.get(True,self.rm.waithint)
                    delay=self.rm.getDelay()
                    time.sleep(delay)
                    self.__process(snac)
               except Queue.Empty:
                    break

        def setStat(self,window=-1,rate=-1,target=-1,lasttime=-1,max=-1):
            self.rm.setStat(window=window,rate=rate,target=target,lasttime=lasttime,max=max)

        def enqueue(self,snac):
            self.q.put(snac)
                
        def __process(self,snac):
            self.handler(snac)
            self.rm.updateRate()
    
    class RateManager:
        #This class calculates the current rate and delay needed not to overrun a target rate. 
        #Remember, it's not "rate" so much as "average delay". It goes down as traffic increases!
        #
        #This class should be general enough to use with any scheduler.
    
        def __init__(self):
            self.lock=threading.RLock()
            self.waithint=60
            self.rate=-1
            self.target=-1
            self.window=-1
            self.lasttime=-1
            self.max=-1

        def setStat(self,window=-1,rate=-1,target=-1,lasttime=-1,max=-1):
            self.lock.acquire()
            if (window != -1):
                self.ratehint=window
                self.window=window
            if (rate != -1):
                self.rate=rate
            if (target != -1):
                self.target=target
            if (lasttime != -1):
                self.lasttime=lasttime
            if (max != -1):
                self.max=max
            self.lock.release()

        def getDelay(self):
            """
            Get the delay needed not to overrun target rate.
            """
            self.lock.acquire()
            nexttime=(self.window*self.target-(self.window-1)*self.rate)/1000.+self.lasttime
            now=time.time()
            self.lock.release()
            if (nexttime < now or self.rate == -1):
                return 0
            else:
                return (nexttime-now)
              
        def updateRate(self):
            """
            Record that a message has been sent and update data.
            """
            self.lock.acquire()
            if (self.window == -1):
                return
            now=time.time()
            newrate=(self.window-1.)/self.window * self.rate + 1./self.window * (now-self.lasttime)*1000
            if (newrate > self.max):
                self.rate=self.max
            else:
                self.rate=newrate
            self.lasttime=now
            self.lock.release()
