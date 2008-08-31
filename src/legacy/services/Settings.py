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
		settings_page = 'xstatus_settings'
		return_back = False
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
			elif command.getAttribute('action') == 'prev': # back
				return_back = True
				
			for child in command.elements():
				if child.name == 'x':
					for field in child.elements():
						if field.name == 'field': # extract data
							if field.getAttribute('var') == 'settings_page':
								for value in field.elements():
									if value.name == 'value':
										settings_page = value.__str__()
							elif field.getAttribute('var') == 'stage':
								for value in field.elements():
									if value.name == 'value':
										stage = value.__str__()
										if return_back and int(stage) >= 0:
											stage = int(stage) - 1
							elif field.getAttribute('var'):
								for value in field.elements():
									if value.name == 'value':
										settings_dict[field.getAttribute('var')] = value.__str__()
			
		if jid not in self.pytrans.sessions: # if user not logined
			self.pytrans.adhoc.sendError('settings', el, errormsg=lang.get('command_NoSession', ulang), sessionid=sessionid)
		elif not hasattr(self.pytrans.sessions[toj.userhost()].legacycon, 'bos'):  # if user not connected to ICQ network
			self.pytrans.adhoc.sendError('settings', el, errormsg=lang.get('command_NoSession', ulang), sessionid=sessionid)
		elif do_action == 'cancel':
			self.pytrans.adhoc.sendCancellation("settings", el, sessionid) # correct cancel handling
		elif stage == '2' or do_action == 'done':
			if settings_page == 'xstatus_settings':
				self.ApplyXstatusSettings(toj, settings_dict) # apply x-status settings
			elif settings_page == 'clist_settings':
				self.ApplyContactListSettings(toj, settings_dict) # apply contact list settings
			self.sendCompletedForm(el, sessionid) # send answer
		elif stage == '1':
			if settings_page == 'xstatus_settings':
				self.sendXstatusSettingsForm(el, sessionid) # send form with x-status settings
			elif settings_page == 'clist_settings':
				self.sendContactListSettingsForm(el, sessionid) # send form with contact list settings
		else:
			self.sendSettingsClassForm(el, sessionid) # send form
	
	def sendSettingsClassForm(self, el, sessionid=None):
		to = el.getAttribute('from')
		to_jid = internJID(to)
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
		command.attributes['status'] = 'executing'
		
		actions = command.addElement('actions')
		actions.attributes['execute'] = 'next'
		actions.addElement('next')

		x = command.addElement('x')
		x.attributes['xmlns'] = 'jabber:x:data'
		x.attributes['type'] = 'form'
		
		instructions = x.addElement('instructions')
		instructions.addContent(lang.get('settings_instructions'))
		
		field = x.addElement('field')
		field.attributes['var'] = 'settings_page'
		field.attributes['type'] = 'list-single'
		field.attributes['label'] = lang.get('settings_category')
		
		option = field.addElement('option')
		option.attributes['label'] = lang.get('settings_category_clist')
		value = option.addElement('value')
		value.addContent('clist_settings')
		
		option = field.addElement('option')
		option.attributes['label'] = lang.get('settings_category_xstatus')
		value = option.addElement('value')
		value.addContent('xstatus_settings')
		
		stage = x.addElement('field')
		stage.attributes['type'] = 'hidden'
		stage.attributes['var'] = 'stage'
		value = stage.addElement('value')
		value.addContent('1')

		self.pytrans.send(iq)
		
			
	def sendXstatusSettingsForm(self, el, sessionid=None):
		to = el.getAttribute("from")
		ID = el.getAttribute("id")
		ulang = utils.getLang(el)
		
		toj = internJID(to)
		jid = toj.userhost()
		
		settings = dict([])
		bos = self.pytrans.sessions[jid].legacycon.bos
		if config.xstatusessupport:
			settings = bos.selfSettings

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
		actions.addElement('prev')
		actions.addElement("complete")

		x = command.addElement("x")
		x.attributes["xmlns"] = "jabber:x:data"
		x.attributes["type"] = "form"
		
		if config.xstatusessupport:
			field = x.addElement('field')
			field.attributes['var'] = 'away_messages_receiving'
			field.attributes['type'] = 'boolean'
			field.attributes['label'] = lang.get('away_messages_receiving')
			value = field.addElement('value')
			value.addContent(str(settings['away_messages_receiving']))
			
			xstatus_sending = dict([
			('xstatus_sendmode_none',0),
			('xstatus_sendmode_ICQ5',1),
			('xstatus_sendmode_ICQ6',2),
			('xstatus_sendmode_ICQ5_6',3)
			])
			field = x.addElement('field')
			field.attributes['var'] = 'xstatus_sending_mode'
			field.attributes['type'] =  'list-single'
			field.attributes['label'] = lang.get('xstatus_sendmode')
			for title in xstatus_sending:
				option = field.addElement('option')
				option.attributes['label'] = lang.get(title)
				value = option.addElement('value')
				value.addContent(str(xstatus_sending[title]))
			value = field.addElement('value')
			value.addContent(str(settings['xstatus_sending_mode']))
				
			field = x.addElement('field')
			field.attributes['var'] = 'xstatus_saving_enabled'
			field.attributes['type'] = 'boolean'
			field.attributes['label'] = lang.get('settings_xstatus_restore_after_disconnect')
			value = field.addElement('value')
			value.addContent(str(settings['xstatus_saving_enabled']))	
			
			xstatus_receiving = dict([
			('xstatus_recvmode_none',0),
			('xstatus_recvmode_ICQ5',1),
			('xstatus_recvmode_ICQ6',2),
			('xstatus_recvmode_ICQ5_6',3)
			])
			field = x.addElement('field')
			field.attributes['var'] = 'xstatus_receiving_mode'
			field.attributes['type'] =  'list-single'
			field.attributes['label'] = lang.get('xstatus_recvmode')
			for title in xstatus_receiving:
				option = field.addElement('option')
				option.attributes['label'] = lang.get(title)
				value = option.addElement('value')
				value.addContent(str(xstatus_receiving[title]))
			value = field.addElement('value')
			value.addContent(str(settings['xstatus_receiving_mode']))
			
			field = x.addElement('field')
			field.attributes['var'] = 'xstatus_option_smooth'
			field.attributes['type'] = 'boolean'
			field.attributes['label'] = lang.get('xstatus_option_smooth')
			value = field.addElement('value')
			value.addContent(str(settings['xstatus_option_smooth']))
			
			field = x.addElement('field')
			field.attributes['var'] = 'xstatus_display_icon_as_PEP'
			field.attributes['type'] = 'boolean'
			field.attributes['label'] = lang.get('xstatus_display_icon_as_PEP')
			value = field.addElement('value')
			value.addContent(str(settings['xstatus_display_icon_as_PEP']))
			
			field = x.addElement('field')
			field.attributes['var'] = 'xstatus_display_text_as_PEP'
			field.attributes['type'] = 'boolean'
			field.attributes['label'] = lang.get('xstatus_display_text_as_PEP')
			value = field.addElement('value')
			value.addContent(str(settings['xstatus_display_text_as_PEP']))
		
		stage = x.addElement('field')
		stage.attributes['type'] = 'hidden'
		stage.attributes['var'] = 'stage'
		value = stage.addElement('value')
		value.addContent('2')
		
		self.pytrans.send(iq)
		
	def sendContactListSettingsForm(self, el, sessionid=None):
		to = el.getAttribute("from")
		ID = el.getAttribute("id")
		ulang = utils.getLang(el)
		
		toj = internJID(to)
		jid = toj.userhost()
		
		bos = self.pytrans.sessions[jid].legacycon.bos
		clist_show_phantombuddies = bos.addSelfSettingsByDefault()['clist_show_phantombuddies']
		
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
		actions.addElement('prev')
		actions.addElement("complete")

		x = command.addElement("x")
		x.attributes["xmlns"] = "jabber:x:data"
		x.attributes["type"] = "form"
		
		field = x.addElement('field')
		field.attributes['var'] = 'clist_show_phantombuddies'
		field.attributes['type'] = 'boolean'
		field.attributes['label'] = lang.get('settings_clist_show_phantombuddies') % bos.ssistats['phantombuddies']
		value = field.addElement('value')
		value.addContent(str(clist_show_phantombuddies))
		
		stage = x.addElement('field')
		stage.attributes['type'] = 'hidden'
		stage.attributes['var'] = 'stage'
		value = stage.addElement('value')
		value.addContent('2')
		
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
		
	def ApplyXstatusSettings(self, to_jid, settings):
		jid = to_jid.userhost()
		LogEvent(INFO, jid)
		bos = self.pytrans.sessions[jid].legacycon.bos
		bos.selfSettings = settings
		if jid in self.pytrans.sessions:
			for key in settings:
				self.pytrans.xdb.setCSetting(jid, key, str(settings[key]))
				
				if config.xstatusessupport:
					if key == 'xstatus_sending_mode' and str(settings[key]) == '0': # disable sending of x-statuses 
						del bos.selfCustomStatus # erase CustomStatus struct
						bos.selfCustomStatus = dict([]) # and create empty one
						bos.updateSelfXstatus()
					if key == 'xstatus_receiving_mode' and str(settings[key]) == '0':
						# fast redrawing for all status messages (need exclude x-status information)
						legacycon = self.pytrans.sessions[jid].legacycon
						contacts = legacycon.legacyList.ssicontacts
						for contact in contacts:
							if contacts[contact]['show']:
								saved_snac = legacycon.getSavedSnac(str(contact))
								if saved_snac != '':
									legacycon.bos.updateBuddy(legacycon.bos.parseUser(saved_snac), True)
	def ApplyContactListSettings(self, to_jid, settings):
		jid = to_jid.userhost()
		LogEvent(INFO, jid)
		bos = self.pytrans.sessions[jid].legacycon.bos
		bos.selfSettings = settings
		if jid in self.pytrans.sessions:
			for key in settings:
				self.pytrans.xdb.setCSetting(jid, key, str(settings[key]))
