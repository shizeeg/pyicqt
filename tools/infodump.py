#!/usr/bin/env python
#
# This script dumps information about the python install you use to run
# it.  It can be useful to determine what pieces you have installed that
# the transport(s) may or may not require.  Most likely you will never
# use this script unless the transport maintainer requests that you do.
#

import sys
print "Python Version: " + sys.version
print "Platform: " + sys.platform

try:
	from twisted.copyright import version
	print "Twisted Version: " + version
except:
	print "Twisted Version: Unknown or Not Installed"

try:
	from twisted.words import __version__
	print "Twisted Words Version: " + __version__
except:
	print "Twisted Words Version: Unknown or Not Installed"

try:
	from twisted.xish import __version__
	print "Twisted Xish Version: " + __version__
except:
	print "Twisted Xish Version: Unknown or Not Installed"

try:
	from twisted.web import __version__
	print "Twisted Web Version: " + __version__
except:
	print "Twisted web Version: Unknown or Not Installed"

try:
	from nevow import __version__
	print "Nevow Version: " + __version__
except:
	print "Nevow Version: Unknown or Not Installed"

try:
	from Image import VERSION
	print "Python Imaging Library (PIL) Version: " + VERSION
except:
	print "Python Imaging Library (PIL) Version: Unknown or Not Installed"

try:
	from OpenSSL import __version__
	print "pyOpenSSL Version: " + __version__
except:
	print "pyOpenSSL Version: Unknown or Not Installed"

try:
	from Crypto import __version__
	print "pycrypto Version: " + __version__
except:
	print "pycrypto Version: Unknown or Not Installed"

try:
	from MySQLdb import __version__
	print "MySQLdb Version: " + __version__
except:
	print "MySQLdb Version: Unknown or Not Installed"
