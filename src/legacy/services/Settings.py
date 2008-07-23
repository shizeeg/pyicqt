# Licensed for distribution under the GPL version 2, check COPYING for details

import utils
from twisted.words.xish.domish import Element
from twisted.words.protocols.jabber.jid import internJID
from twisted.python import log
from debug import LogEvent, INFO, WARN, ERROR
from tlib import oscar
import config
import lang
import globals

class Settings:
	def __init__(self, pytrans):
		self.pytrans = pytrans
		self.pytrans.adhoc.addCommand('settings', self.incomingIq, 'command_Settings')
		
	def incomingIq(self, el):
		do_action = ''
		stage = 0
		settings_dict = dict([])
		
		to = el.getAttribute('from')
		toj = internJID(to)
		ID = el.getAttribute('id')
		ulang = utils.getLang(el)
		
		log.msg('Settings: to %s, toj %s, ID %s, ulang %s' % (to,toj,ID,ulang))
		
		for command in el.elements():
			sessionid = command.getAttribute('sessionid')
			if command.getAttribute('action') == 'complete':
				do_action = 'done'
			elif command.getAttribute('action') == 'cancel':
				do_action = 'cancel'
				
			for child in command.elements():
				if child.name == 'x':
					for field in child.elements():
						if field.name == 'field': # extract data
							if field.getAttribute('var') == 'stage':
								for value in field.elements():
									if value.name == 'value':
										stage = value.__str__()
							elif field.getAttribute('var'):
								for value in field.elements():
									if value.name == 'value':
										settings_dict[field.getAttribute('var')] = value.__str__()
			
		if not self.pytrans.sessions.has_key(toj.userhost()): # if user not logined
			self.pytrans.adhoc.sendError('settings', el, errormsg=lang.get('command_NoSession', ulang), sessionid=sessionid)
		elif not hasattr(self.pytrans.sessions[toj.userhost()].legacycon, 'bos'):  # if user not connected to ICQ network
			self.pytrans.adhoc.sendError('settings', el, errormsg=lang.get('command_NoSession', ulang), sessionid=sessionid)
		elif stage == '1' or do_action == 'done':
			self.ApplySettings(toj, settings_dict) # apply settings
			self.sendCompletedForm(el, sessionid) # send answer
		elif do_action == 'cancel':
			self.pytrans.adhoc.sendCancellation("setxstatus", el, sessionid) # correct cancel handling
		else:
			self.sendSettingsForm(toj, el, sessionid) # send form
			
	def sendSettingsForm(self, toj, el, sessionid=None):
		to = el.getAttribute("from")
		ID = el.getAttribute("id")
		ulang = utils.getLang(el)
		
		toj = internJID(to)
		jid = toj.userhost()
		
		xstatus_receiving_enabled = '1'
		xstatus_sending_enabled = '1'
		if self.pytrans.sessions.has_key(jid):
			xstatus_receiving_enabled = self.pytrans.xdb.getCSetting(jid, 'xstatus_receiving_enabled')
			if not xstatus_receiving_enabled: # value not saved yet
				xstatus_receiving_enabled = '1' # enable by default
			xstatus_sending_enabled = self.pytrans.xdb.getCSetting(jid, 'xstatus_sending_enabled')
			if not xstatus_sending_enabled: # value not saved yet
				xstatus_sending_enabled = '1' # enable by default

		iq = Element((None, "iq"))
		iq.attributes["to"] = to
		iq.attributes["from"] = config.jid
		if ID:
			iq.attributes["id"] = ID
		iq.attributes["type"] = "result"

		command = iq.addElement("command")
		if sessionid:
			command.attributes["sessionid"] = sessionid
		else:
			command.attributes["sessionid"] = self.pytrans.makeMessageID()
		command.attributes["node"] = "settings"
		command.attributes["xmlns"] = globals.COMMANDS
		command.attributes["status"] = "executing"

		actions = command.addElement("actions")
		actions.attributes["execute"] = "complete"
		actions.addElement("complete")

		x = command.addElement("x")
		x.attributes["xmlns"] = "jabber:x:data"
		x.attributes["type"] = "form"
		
		field = x.addElement('field')
		field.attributes['var'] = 'xstatus_receiving_enabled'
		field.attributes['type'] = 'boolean'
		field.attributes['label'] = 'Support for x-status receiving'
		value = field.addElement('value')
		value.addContent(xstatus_receiving_enabled)
		
		field = x.addElement('field')
		field.attributes['var'] = 'xstatus_sending_enabled'
		field.attributes['type'] = 'boolean'
		field.attributes['label'] = 'Support for x-status sending'
		value = field.addElement('value')
		value.addContent(xstatus_sending_enabled)
		
		stage = x.addElement('field')
		stage.attributes['type'] = 'hidden'
		stage.attributes['var'] = 'stage'
		value = stage.addElement('value')
		value.addContent('1')
		
		self.pytrans.send(iq)
		
	def sendCompletedForm(self, el, sessionid=None):
		to = el.getAttribute('from')
		ID = el.getAttribute('id')
		ulang = utils.getLang(el)
		
		iq = Element((None, 'iq'))
		iq.attributes['to'] = to
		iq.attributes['from'] = config.jid
		if ID:
			iq.attributes['id'] = ID
		iq.attributes['type'] = 'result'
		
		command = iq.addElement('command')
		if sessionid:
			command.attributes['sessionid'] = sessionid
		else:
			command.attributes['sessionid'] = self.pytrans.makeMessageID()
		command.attributes['node'] = 'settings'
		command.attributes['xmlns'] = globals.COMMANDS
		command.attributes['status'] = 'completed'
		
		note = command.addElement('note')
		note.attributes['type'] = 'info'
		note.addContent('Your setting were changed')
		
		self.pytrans.send(iq)
		
	def ApplySettings(self, to_jid, settings):
		jid = to_jid.userhost()
		log.msg('Settings for %s: %s' % (jid, settings))
		bos = self.pytrans.sessions[jid].legacycon.bos
		bos.selfSettings = settings
		