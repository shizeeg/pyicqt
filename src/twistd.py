# Copyright (c) 2001-2008 Twisted Matrix Laboratories.
# See LICENSE for details.

import os, sys, errno
from twisted.python import log

def daemonize():
    # See http://www.erlenstar.demon.co.uk/unix/faq_toc.html#TOC16
    if os.fork():   # launch child and...
        os._exit(0) # kill off parent
    os.setsid()
    if os.fork():   # launch child and...
        os._exit(0) # kill off parent again.
    os.umask(077)
    null = os.open('/dev/null', os.O_RDWR)
    for i in range(3):
        try:
            os.dup2(null, i)
        except OSError, e:
            if e.errno != errno.EBADF:
                raise
    os.close(null)
	
def removePID(pidfile):
	# Remove a PID file
	if not pidfile:
		return
	try:
		os.unlink(pidfile)
	except OSError, e:
		if e.errno == errno.EACCES or e.errno == errno.EPERM:
			log.msg("Warning: No permission to delete pid file")
		else:
			log.msg("Failed to unlink PID file:")
			log.deferr()
	except:
		log.msg("Failed to unlink PID file:")
		log.deferr()
		
def checkPID(pidfile):
    if not pidfile:
        return
    if os.path.exists(pidfile):
        try:
            pid = int(open(pidfile).read())
        except ValueError:
            sys.exit('Pidfile %s contains non-numeric value' % pidfile)
        try:
            os.kill(pid, 0)
        except OSError, why:
            if why[0] == errno.ESRCH:
                # The pid doesnt exists.
                log.msg('Removing stale pidfile %s' % pidfile, isError=True)
                os.remove(pidfile)
            else:
                sys.exit("Can't check status of PID %s from pidfile %s: %s" %
                         (pid, pidfile, why[1]))
        else:
            sys.exit("""\
Another PyICQt instance is running, PID %s\n
To start a new one, use the --pidfile and --logfile parameters to avoid clashes.
""" %  pid)