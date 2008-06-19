#!/usr/bin/env python
import sys
sys.path.append("../src/tlib")
import oscar
from twisted.internet import protocol, reactor
import getpass
import binascii
import cmd
import os
import getopt

SN = None
PASS = None
opts, args = getopt.getopt(sys.argv[1:], "ds:p:h", ["debug", "screenname", "password", "help"])
for o, v in opts:
	if o in ("-d", "--debug"):
		from twisted.python import log
		log.startLogging(sys.stdout, 0)
	elif o in ("-s", "--screenname"):
		SN = v
	elif o in ("-p", "--password"):
		PASS = v
	elif o in ("-h", "--help"):
		print "Available command line args are:"
		print "   -d/--debug           enable debugging output"
		print "   -s/--screenname      screenname/uin to log in as"
		print "   -p/--password        password to authenticate with"
		print "   -h/--help            display this help output"
		os._exit(0)


if not SN:
	SN = raw_input('Username: ')
if not PASS:
	PASS = getpass.getpass('Password: ')
if SN[0].isdigit():
	icqMode = 1
	#hostport = ('login.icq.com', 5238)
	hostport = ('login.icq.com', 5190)
else:
	hostport = ('login.oscar.aol.com', 5190)
	icqMode = 0

class SSICmd(cmd.Cmd):
	def __init__(self, bos):
		self.bos = bos
		cmd.Cmd.__init__(self)
	def do_delete(self, rest):
		pcs = rest.split()
		if len(pcs) < 1:
			self.help_delete()
		elif pcs[0] == 'buddy':
			if len(pcs) != 3:
				print "You need to specify both a group and buddy id."
				self.help_delete()
			else:
				self.bos.removeBuddy(int(pcs[1]), int(pcs[2]))
		elif pcs[0] == 'group':
			if len(pcs) != 2:
				print "You need to specify a group id."
				self.help_delete()
			else:
				self.bos.removeGroup(int(pcs[1]))
		elif pcs[0] == 'icon':
			if len(pcs) != 2:
				print "You need to specify a icon id."
				self.help_delete()
			else:
				self.bos.removeIcon(int(pcs[1]))
		else:
			self.help_delete()
	def help_delete(self):
		print "delete buddy (group id) (buddy id): removes the specified buddy from the specified group"
		print "delete group (group id): removes the specified group"
		print "delete icon (icon id): removes the specified icon"
	def do_show(self, rest):
		pcs = rest.split()
		if len(pcs) != 1:
			self.help_show()
			return
		if pcs[0] == "buddies":
			self.bos.showBuddyList()
		elif pcs[0] == "icons":
			self.bos.showIconList()
		elif pcs[0] == "visibility":
			self.bos.showVisibility()
		elif pcs[0] == "permissions":
			self.bos.showPermissions()
		else:
			self.help_show()
	def help_show(self):
		print "show (type): displays information for one of the following types"
		print "   buddies       list of groups and buddies"
		print "   icons         list of buddy icons"
		print "   visibility    show visibility setting"
		print "   permissions   show permission setting"
	def do_set(self, rest):
		pcs = rest.split()
		if len(pcs) != 2:
			self.help_set()
			return
		if pcs[0] == "visibility":
			if pcs[1] == "all":
				self.bos.setVisibility('\xff\xff\xff\xff')
			elif pcs[1] == "notaim":
				self.bos.setVisibility('\x00\x00\x00\x04')
			elif pcs[1] == "none":
				self.bos.setVisibility(None)
			else:
				self.help_set()
		elif pcs[0] == "permissions":
			if pcs[1] == "permitall":
				self.bos.setPermissions(0x01)
			elif pcs[1] == "denyall":
				self.bos.setPermissions(0x02)
			elif pcs[1] == "permitsome":
				self.bos.setPermissions(0x03)
			elif pcs[1] == "denysome":
				self.bos.setPermissions(0x04)
			elif pcs[1] == "permitbuddies":
				self.bos.setPermissions(0x05)
			elif pcs[1] == "none":
				self.bos.setPermissions(None)
			else:
				self.help_set()
		else:
			self.help_set()
	def help_set(self):
		print "set (item) (value): sets one of the following items to a supported value"
		print "   visibility    whether others can see you"
		print "      all            visible to anyone"
		print "      notaim         not visible to aim folk"
		print "      none           unset visibility setting"
		print "   permissions   who is permitted to see(?) you"
		print "      permitall      anyone can see(?) you"
		print "      denyall        no one can see(?) you"
		print "      permitsome     specified folk can see(?) you"
		print "      denysome       everyone but specified folk can see(?) you"
		print "      permitbuddies  only permit buddies to see (?) you"
		print "      none           unset permissions setting"
	#def do_reload(self, rest):
	#	self.bos.requestBuddyList()
	#	print "Loading buddy list..."
	#def help_reload(self): print "reload: reloads your ssi"
	def do_quit(self, rest):
		self.bos.stopKeepAlive()
		self.bos.disconnect()
		print "Done."
		os._exit(0)
	def help_quit(self): print "quit: exits the program"
	def help_help(self): print "help (command): explains the specified command"

class B(oscar.BOSConnection):
	capabilities = []
	ssi = []
	def initDone(self):
		self.requestBuddyList()
		self.requestSSI().addCallback(self.gotBuddyList)
	def requestBuddyList(self):
		self.requestSSI().addCallback(self.gotReloadedBuddyList)
	def gotBuddyList(self, l):
		self.ssi = l
		print "SSI: %s" % str(self.ssi)
		self.clientReady()
		SSICmd(self).cmdloop()
	def gotReloadedBuddyList(self, l):
		self.ssi = l
		print "SSI: %s" % str(self.ssi)
	def showBuddyList(self):
		if self.ssi is not None and self.ssi[0] is not None:
			for g in self.ssi[0]:
				print "Group[%0.5d]: %s" % (g.groupID,g.name)
				for u in g.users:
					print "\tMember[%0.5d]: %s (%s)" % (u.buddyID,u.name,u.nick)
	def showIconList(self):
		if self.ssi is not None and self.ssi[5] is not None:
			for i in self.ssi[5]:
				print "Icon[%d,%d,%s]: %s" % (i.groupID,i.buddyID,i.name,binascii.hexlify(i.iconSum))
	def showVisibility(self):
		if self.ssi is not None and self.ssi[4] is not None:
			print "Visibility: %s" % (self.ssi[4])
		else:
			print "Visibility: not set"
	def showPermissions(self):
		if self.ssi is not None and self.ssi[3] is not None:
			print "Permissions: %s" % (self.ssi[3])
		else:
			print "Permissions: not set"
	def setVisibility(self, setting):
		if self.ssi is not None and self.ssi[8] is not None:
			self.ssi[8].visibility = setting
			self.startModifySSI()
			self.modifyItemSSI(self.ssi[8])
			self.endModifySSI()
		else:
			print "Not supported yet, you don't have pdinfo in your ssi at all."
	def setPermissions(self, setting):
		if self.ssi is not None and self.ssi[8] is not None:
			self.ssi[8].permitMode = setting
			self.startModifySSI()
			self.modifyItemSSI(self.ssi[8])
			self.endModifySSI()
		else:
			print "Not supported yet, you don't have pdinfo in your ssi at all."
	def removeBuddy(self, groupid, buddyid):
		savethisuser = None
		savethisgroup = None
		for g in self.ssi[0]:
			if g.groupID == groupid:
				for u in g.users:
					if u.buddyID == buddyid:
						savethisuser = u
						savethisgroup = g
						break
				break
		if savethisuser is None:
			print "Unable to locate buddy id %d in group id %d." % (buddyid, groupid)
			return
		self.startModifySSI()
		de = self.delItemSSI(savethisuser)
		self.endModifySSI()
		savethisgroup.users.remove(savethisuser)
		del savethisgroup.usersToID[savethisuser]
		print "Removed buddy with id %d from group with id %d" % (buddyid, groupid)
	def removeGroup(self, groupid):
		savethisgroup = None
		for g in self.ssi[0]:
			if g.groupID == groupid:
				savethisgroup = g
				break
		if savethisgroup is None:
			print "Unable to locate group id %d." % (groupid)
			return
		self.startModifySSI()
		de = self.delItemSSI(savethisgroup)
		self.endModifySSI()
		self.ssi[0].remove(savethisgroup)
		print "Removed group with id %d" % groupid
	def removeIcon(self, iconid):
		savethisicon = None
		for i in self.ssi[5]:
			if i.buddyID == iconid:
				savethisicon = i
				break
		if savethisicon is None:
			print "Unable to locate icon id %d." % (iconid)
			return
		self.startModifySSI()
		de = self.delItemSSI(savethisicon)
		self.endModifySSI()
		self.ssi[5].remove(savethisicon)
		print "Removed icon with id %d" % iconid

class OA(oscar.OscarAuthenticator):
	BOSClass = B

protocol.ClientCreator(reactor, OA, SN, PASS, icq=icqMode).connectTCP(*hostport)
reactor.run()
print "Done."
