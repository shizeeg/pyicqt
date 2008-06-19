# Copyright 2004-2006 Daniel Henninger <jadestorm@nc.rr.com>
# Licensed for distribution under the GPL version 2, check COPYING for details

from twisted.internet import task
from debug import LogEvent, INFO, WARN, ERROR

class PingService:
	def __init__(self, pytrans):
		self.pytrans = pytrans
		self.pingTask = task.LoopingCall(self.whitespace)

	def whitespace(self):
		self.pytrans.send(" ")
