# Licensed for distribution under the GPL version 2, check COPYING for details

import utils
from twisted.words.xish.domish import Element
from twisted.words.protocols.jabber.jid import internJID
from tlib import oscar
from debug import LogEvent, INFO, WARN, ERROR
import config
import lang
import globals
from adhoc import rights_guest, rights_user, rights_admin

class Settings:
	def __init__(self, pytrans):
		self.pytrans = pytrans
		self.pytrans.adhoc.addCommand('settings', self.incomingIq, 'command_Settings', rights_user)
		
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
			elif settings_page == 'message_settings':
				self.ApplyMessageSettings(toj, settings_dict) # apply message settings
			elif settings_page == 'personal_events_settings':
				self.ApplyPersonalEventsSettings(toj, settings_dict) # apply personal events settings
			self.sendCompletedForm(el, sessionid) # send answer
		elif stage == '1':
			if settings_page == 'xstatus_settings':
				self.sendXstatusSettingsForm(el, sessionid) # send form with x-status settings
			elif settings_page == 'clist_settings':
				self.sendContactListSettingsForm(el, sessionid) # send form with contact list settings
			elif settings_page == 'message_settings':
				self.sendMessageSettingsForm(el, sessionid) # send form with message settings
			elif settings_page == 'personal_events_settings':
				self.sendPersonalEventsSettingsForm(el, sessionid) # send form with personal events settings
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
		
		title = x.addElement('title')
		title.addContent(lang.get('command_Settings'))
		
		instructions = x.addElement('instructions')
		instructions.addContent(lang.get('settings_instructions'))
		
		field = x.addElement('field')
		field.attributes['var'] = 'settings_page'
		field.attributes['type'] = 'list-single'
		field.attributes['label'] = lang.get('settings_category')
		desc = field.addElement('desc')
		desc.addContent(lang.get('settings_instructions_Desc'))
		
		option = field.addElement('option')
		option.attributes['label'] = lang.get('settings_category_clist')
		value = option.addElement('value')
		value.addContent('clist_settings')
		
		option = field.addElement('option')
		option.attributes['label'] = lang.get('settings_category_xstatus')
		value = option.addElement('value')
		value.addContent('xstatus_settings')
		
		option = field.addElement('option')
		option.attributes['label'] = lang.get('settings_category_message')
		value = option.addElement('value')
		value.addContent('message_settings')
		
		option = field.addElement('option')
		option.attributes['label'] = lang.get('settings_category_personal_events')
		value = option.addElement('value')
		value.addContent('personal_events_settings')
		
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
		
		title = x.addElement('title')
		title.addContent(lang.get('settings_category_xstatus'))
		
		if config.xstatusessupport:
			field = x.addElement('field')
			field.attributes['var'] = 'away_messages_sending'
			field.attributes['type'] = 'boolean'
			field.attributes['label'] = lang.get('away_messages_sending')
			value = field.addElement('value')
			value.addContent(str(settings['away_messages_sending']))
			desc = field.addElement('desc')
			desc.addContent(lang.get('away_messages_sending_Desc')) 
			
			field = x.addElement('field')
			field.attributes['var'] = 'away_messages_receiving'
			field.attributes['type'] = 'boolean'
			field.attributes['label'] = lang.get('away_messages_receiving')
			value = field.addElement('value')
			value.addContent(str(settings['away_messages_receiving']))
			desc = field.addElement('desc')
			desc.addContent(lang.get('away_messages_receiving_Desc')) 
			
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
			desc = field.addElement('desc')
			desc.addContent(lang.get('xstatus_sendmode_Desc')) 
				
			field = x.addElement('field')
			field.attributes['var'] = 'xstatus_saving_enabled'
			field.attributes['type'] = 'boolean'
			field.attributes['label'] = lang.get('xstatus_restore_after_disconnect')
			value = field.addElement('value')
			value.addContent(str(settings['xstatus_saving_enabled']))	
			desc = field.addElement('desc')
			desc.addContent(lang.get('xstatus_restore_after_disconnect_Desc')) 
			
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
			desc = field.addElement('desc')
			desc.addContent(lang.get('xstatus_recvmode_Desc')) 
			
			field = x.addElement('field')
			field.attributes['var'] = 'xstatus_option_smooth'
			field.attributes['type'] = 'boolean'
			field.attributes['label'] = lang.get('xstatus_option_smooth')
			value = field.addElement('value')
			value.addContent(str(settings['xstatus_option_smooth']))
			desc = field.addElement('desc')
			desc.addContent(lang.get('xstatus_option_smooth_Desc')) 
			
			field = x.addElement('field')
			field.attributes['var'] = 'xstatus_display_icon_as_PEP'
			field.attributes['type'] = 'boolean'
			field.attributes['label'] = lang.get('xstatus_display_icon_as_PEP')
			value = field.addElement('value')
			value.addContent(str(settings['xstatus_display_icon_as_PEP']))
			desc = field.addElement('desc')
			desc.addContent(lang.get('xstatus_display_icon_as_PEP_Desc')) 
			
			field = x.addElement('field')
			field.attributes['var'] = 'xstatus_display_text_as_PEP'
			field.attributes['type'] = 'boolean'
			field.attributes['label'] = lang.get('xstatus_display_text_as_PEP')
			value = field.addElement('value')
			value.addContent(str(settings['xstatus_display_text_as_PEP']))
			desc = field.addElement('desc')
			desc.addContent(lang.get('xstatus_display_text_as_PEP_Desc')) 
			
			field = x.addElement('field')
			field.attributes['var'] = 'xstatus_icon_for_transport'
			field.attributes['type'] = 'boolean'
			field.attributes['label'] = lang.get('xstatus_icon_for_transport')
			value = field.addElement('value')
			value.addContent(str(settings['xstatus_icon_for_transport']))
			desc = field.addElement('desc')
			desc.addContent(lang.get('xstatus_icon_for_transport_Desc')) 
			
		field = x.addElement('field')
		field.attributes['type'] = 'hidden'
		field.attributes['var'] = 'settings_page'
		value = field.addElement('value')
		value.addContent('xstatus_settings')
		
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
		
		title = x.addElement('title')
		title.addContent(lang.get('settings_category_clist'))
		
		field = x.addElement('field')
		field.attributes['var'] = 'clist_show_phantombuddies'
		field.attributes['type'] = 'boolean'
		field.attributes['label'] = lang.get('settings_clist_show_phantombuddies') % bos.ssistats['phantombuddies']
		value = field.addElement('value')
		value.addContent(str(settings['clist_show_phantombuddies']))
		desc = field.addElement('desc')
		desc.addContent(lang.get('settings_clist_show_phantombuddies_Desc')) 
		
		field = x.addElement('field')
		field.attributes['var'] = 'clist_deny_all_auth_requests'
		field.attributes['type'] = 'boolean'
		field.attributes['label'] = lang.get('settings_clist_deny_all_auth_requests')
		value = field.addElement('value')
		value.addContent(str(settings['clist_deny_all_auth_requests']))
		desc = field.addElement('desc')
		desc.addContent(lang.get('settings_clist_deny_all_auth_requests_Desc')) 
		
		field = x.addElement('field')
		field.attributes['type'] = 'hidden'
		field.attributes['var'] = 'settings_page'
		value = field.addElement('value')
		value.addContent('clist_settings')
		
		stage = x.addElement('field')
		stage.attributes['type'] = 'hidden'
		stage.attributes['var'] = 'stage'
		value = stage.addElement('value')
		value.addContent('2')
		
		self.pytrans.send(iq)
		
	def sendMessageSettingsForm(self, el, sessionid=None):
		to = el.getAttribute("from")
		ID = el.getAttribute("id")
		ulang = utils.getLang(el)
		
		toj = internJID(to)
		jid = toj.userhost()
		
		bos = self.pytrans.sessions[jid].legacycon.bos
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
		
		title = x.addElement('title')
		title.addContent(lang.get('settings_category_message'))
		
		utf8_messages_sendmode = dict([
			('utf8_messages_sendmode_none',0),
			('utf8_messages_sendmode_as_reply',1),
			('utf8_messages_sendmode_always',2)
			])
		field = x.addElement('field')
		field.attributes['var'] = 'utf8_messages_sendmode'
		field.attributes['type'] =  'list-single'
		field.attributes['label'] = lang.get('utf8_messages_sendmode')
		for title in utf8_messages_sendmode:
			option = field.addElement('option')
			option.attributes['label'] = lang.get(title)
			value = option.addElement('value')
			value.addContent(str(utf8_messages_sendmode[title]))
		value = field.addElement('value')
		value.addContent(str(settings['utf8_messages_sendmode']))
		desc = field.addElement('desc')
		desc.addContent(lang.get('utf8_messages_sendmode_Desc')) 
		
		msgconfirm_sendmode = dict([
			('msgconfirm_sendmode_none',0),
			('msgconfirm_sendmode_for_utf8',1),
			('msgconfirm_sendmode_always',2)
			])
		field = x.addElement('field')
		field.attributes['var'] = 'msgconfirm_sendmode'
		field.attributes['type'] =  'list-single'
		field.attributes['label'] = lang.get('msgconfirm_sendmode')
		for title in msgconfirm_sendmode:
			option = field.addElement('option')
			option.attributes['label'] = lang.get(title)
			value = option.addElement('value')
			value.addContent(str(msgconfirm_sendmode[title]))
		value = field.addElement('value')
		value.addContent(str(settings['msgconfirm_sendmode']))
		desc = field.addElement('desc')
		desc.addContent(lang.get('msgconfirm_sendmode_Desc')) 
		
		field = x.addElement('field')
		field.attributes['var'] = 'msgconfirm_recvmode'
		field.attributes['type'] =  'boolean'
		field.attributes['label'] = lang.get('msgconfirm_recvmode')
		value = field.addElement('value')
		value.addContent(str(settings['msgconfirm_recvmode']))
		desc = field.addElement('desc')
		desc.addContent(lang.get('msgconfirm_recvmode_Desc')) 
		
		offline_messages_sendenc = dict([
			('offline_messages_sendenc_unicode',0),
			('offline_messages_sendenc_local',1),
			('offline_messages_sendenc_auto',2)
			])
		field = x.addElement('field')
		field.attributes['var'] = 'offline_messages_sendenc'
		field.attributes['type'] =  'list-single'
		field.attributes['label'] = lang.get('offline_messages_sendenc')
		for title in offline_messages_sendenc:
			option = field.addElement('option')
			if title == 'offline_messages_sendenc_local':
			    option.attributes['label'] = lang.get(title) % config.encoding
			else:
			    option.attributes['label'] = lang.get(title)
			value = option.addElement('value')
			value.addContent(str(offline_messages_sendenc[title]))
		value = field.addElement('value')
		value.addContent(str(settings['offline_messages_sendenc']))
		desc = field.addElement('desc')
		desc.addContent(lang.get('offline_messages_sendenc_Desc')) 

		field = x.addElement('field')
		field.attributes['type'] = 'hidden'
		field.attributes['var'] = 'settings_page'
		value = field.addElement('value')
		value.addContent('message_settings')
		
		stage = x.addElement('field')
		stage.attributes['type'] = 'hidden'
		stage.attributes['var'] = 'stage'
		value = stage.addElement('value')
		value.addContent('2')
		
		self.pytrans.send(iq)
		
	def sendPersonalEventsSettingsForm(self, el, sessionid=None):
		to = el.getAttribute("from")
		ID = el.getAttribute("id")
		ulang = utils.getLang(el)
		
		toj = internJID(to)
		jid = toj.userhost()
		
		bos = self.pytrans.sessions[jid].legacycon.bos
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
		
		title = x.addElement('title')
		title.addContent(lang.get('settings_category_personal_events'))
		
		field = x.addElement('field')
		field.attributes['var'] = 'user_mood_receiving'
		field.attributes['type'] = 'boolean'
		field.attributes['label'] = lang.get('user_mood_receiving')
		value = field.addElement('value')
		value.addContent(str(settings['user_mood_receiving']))
		desc = field.addElement('desc')
		desc.addContent(lang.get('user_mood_receiving_Desc')) 
		
		field = x.addElement('field')
		field.attributes['var'] = 'user_activity_receiving'
		field.attributes['type'] = 'boolean'
		field.attributes['label'] = lang.get('user_activity_receiving')
		value = field.addElement('value')
		value.addContent(str(settings['user_activity_receiving']))
		desc = field.addElement('desc')
		desc.addContent(lang.get('user_activity_receiving_Desc')) 
		
		field = x.addElement('field')
		field.attributes['var'] = 'user_tune_receiving'
		field.attributes['type'] = 'boolean'
		field.attributes['label'] = lang.get('user_tune_receiving')
		value = field.addElement('value')
		value.addContent(str(settings['user_tune_receiving']))
		desc = field.addElement('desc')
		desc.addContent(lang.get('user_tune_receiving_Desc')) 
		
		field = x.addElement('field')
		field.attributes['type'] = 'hidden'
		field.attributes['var'] = 'settings_page'
		value = field.addElement('value')
		value.addContent('personal_events_settings')
		
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
		note.addContent(lang.get('settings_changed'))
		
		x = command.addElement('x')
		x.attributes['xmlns'] = 'jabber:x:data'
		x.attributes['type'] = 'form'

		title = x.addElement('title')
		title.addContent(lang.get('command_Settings'))
		
		instructions = x.addElement('instructions')
		instructions.addContent(lang.get('settings_changed'))
		
		self.pytrans.send(iq)
		
	def ApplyXstatusSettings(self, to_jid, settings):
		jid = to_jid.userhost()
		LogEvent(INFO, jid)
		bos = self.pytrans.sessions[jid].legacycon.bos
		bos.addToSelfSettings(settings)
		if jid in self.pytrans.sessions:
			for key in settings:
				self.pytrans.xdb.setCSetting(jid, key, str(settings[key]))
				
				if config.xstatusessupport:
					if key == 'xstatus_sending_mode' and str(settings[key]) == '0': # disable sending of x-statuses 
						mask = ('mood', 'activity', 'subactivity', 'text', 'usetune') # keep values for mood/activity
						bos.oscarcon.delSelfCustomStatus(savemask=mask)
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
					if key == 'xstatus_icon_for_transport':
						if str(settings[key]) == '1':
							bos.setStatusIconForTransport() # show icon for transport
						else:
							bos.setStatusIconForTransport(reset=True) # hide icon for transport
	def ApplyContactListSettings(self, to_jid, settings):
		jid = to_jid.userhost()
		LogEvent(INFO, jid)
		bos = self.pytrans.sessions[jid].legacycon.bos
		bos.addToSelfSettings(settings)
		if jid in self.pytrans.sessions:
			for key in settings:
				self.pytrans.xdb.setCSetting(jid, key, str(settings[key]))
				
	def ApplyMessageSettings(self, to_jid, settings):
		jid = to_jid.userhost()
		LogEvent(INFO, jid)
		bos = self.pytrans.sessions[jid].legacycon.bos
		bos.addToSelfSettings(settings)
		if jid in self.pytrans.sessions:
			for key in settings:
				self.pytrans.xdb.setCSetting(jid, key, str(settings[key]))
				
	def ApplyPersonalEventsSettings(self, to_jid, settings):
		jid = to_jid.userhost()
		LogEvent(INFO, jid)
		bos = self.pytrans.sessions[jid].legacycon.bos
		bos.addToSelfSettings(settings)
		if jid in self.pytrans.sessions:
			for key in settings:
				self.pytrans.xdb.setCSetting(jid, key, str(settings[key]))
