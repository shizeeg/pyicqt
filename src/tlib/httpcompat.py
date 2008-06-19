# Copyright 2006 Daniel Henninger <jadestorm@nc.rr.com>.
# Licensed for distribution under the GPL version 2, check COPYING for details

try:
	from twisted.web import http
except:
	try:
		from twisted.protocols import http
	except ImportError:
		http = None
