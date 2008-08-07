# Licensed for distribution under the GPL version 2, check COPYING for details

import utils
from twisted.words.xish.domish import Element
from twisted.words.protocols.jabber.jid import internJID
from tlib import oscar
from debug import LogEvent, INFO, WARN, ERROR
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
		jid = toj.userhost()
		ID = el.getAttribute('id')
		ulang = utils.getLang(el)
		
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
			
		if jid not in self.pytrans.sessions: # if user not logined
			self.pytrans.adhoc.sendError('settings', el, errormsg=lang.get('command_NoSession', ulang), sessionid=sessionid)
		elif not hasattr(self.pytrans.sessions[toj.userhost()].legacycon, 'bos'):  # if user not connected to ICQ network
			self.pytrans.adhoc.sendError('settings', el, errormsg=lang.get('command_NoSession', ulang), sessionid=sessionid)
		elif stage == '1' or do_action == 'done':
			self.ApplySettings(toj, settings_dict) # apply settings
			self.sendCompletedForm(el, sessionid) # send answer
		elif do_action == 'cancel':
			self.pytrans.adhoc.sendCancellation("settings", el, sessionid) # correct cancel handling
		else:
			self.sendSettingsForm(el, sessionid) # send form
			
	def sendSettingsForm(self, el, sessionid=None):
		to = el.getAttribute("from")
		ID = el.getAttribute("id")
		ulang = utils.getLang(el)
		
		toj = internJID(to)
		jid = toj.userhost()
		
		if config.xstatusessupport:
			xstatus_receiving_enabled = '1'
			xstatus_sending_enabled = '1'
			xstatus_saving_enabled = '1'
			if jid in self.pytrans.sessions:
				xstatus_receiving_enabled = self.pytrans.xdb.getCSetting(jid, 'xstatus_receiving_enabled')
				if not xstatus_receiving_enabled: # value not saved yet
					xstatus_receiving_enabled = '1' # enable by default
				xstatus_sending_enabled = self.pytrans.xdb.getCSetting(jid, 'xstatus_sending_enabled')
				if not xstatus_sending_enabled: # value not saved yet
					xstatus_sending_enabled = '1' # enable by default
				xstatus_saving_enabled = self.pytrans.xdb.getCSetting(jid, 'xstatus_saving_enabled')
				if not xstatus_saving_enabled: # value not saved yet
					xstatus_saving_enabled = '1' # enable by default

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
		
		if config.xstatusessupport:
			field = x.addElement('field')
			field.attributes['var'] = 'xstatus_receiving_enabled'
			field.attributes['type'] = 'boolean'
			field.attributes['label'] = lang.get('settings_xstatus_recv_support')
			value = field.addElement('value')
			value.addContent(xstatus_receiving_enabled)
			
			field = x.addElement('field')
			field.attributes['var'] = 'xstatus_sending_enabled'
			field.attributes['type'] = 'boolean'
			field.attributes['label'] = lang.get('settings_xstatus_send_support')
			value = field.addElement('value')
			value.addContent(xstatus_sending_enabled)
			
			field = x.addElement('field')
			field.attributes['var'] = 'xstatus_saving_enabled'
			field.attributes['type'] = 'boolean'
			field.attributes['label'] = lang.get('settings_xstatus_restore_after_disconnect')
			value = field.addElement('value')
			value.addContent(xstatus_saving_enabled)
		
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
		note.addContent('Your settings were changed')
		
		self.pytrans.send(iq)
		
	def ApplySettings(self, to_jid, settings):
		jid = to_jid.userhost()
		LogEvent(INFO, jid)
		bos = self.pytrans.sessions[jid].legacycon.bos
		bos.selfSettings = settings
		if jid in self.pytrans.sessions:
			for key in settings:
				self.pytrans.xdb.setCSetting(jid, key, settings[key])
				
				if config.xstatusessupport:
					if key == 'xstatus_sending_enabled' and str(settings[key]) == '0':
						bos.selfCustomStatus['x-status name'] = ''
						bos.updateSelfXstatus()
					if key == 'xstatus_receiving_enabled' and str(settings[key]) == '0':
						# fast redrawing for all status messages (need exclude x-status information)
						legacycon = self.pytrans.sessions[jid].legacycon
						contacts = legacycon.legacyList.ssicontacts
						for contact in contacts:
							if contacts[contact]['show']:
								saved_snac = legacycon.getSavedSnac(str(contact))
								if saved_snac != '':
									legacycon.bos.updateBuddy(legacycon.bos.parseUser(saved_snac), True)
