# -*- coding: utf-8 -*-
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
										if field.getAttribute('type') == 'text-multi' and field.getAttribute('var') in settings_dict:
											settings_dict[field.getAttribute('var')] += '\n%s' % value.__str__()
										else:
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
			elif settings_page == 'autoanswer_settings':
				self.ApplyAutoanswerSettings(toj, settings_dict) # apply auto-answer settings
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
			elif settings_page == 'autoanswer_settings':
				self.sendAutoanswerSettingsForm(el, sessionid) # send form with auto-answer settings
		else:
			self.sendSettingsClassForm(el, sessionid) # send form
	
	def sendSettingsClassForm(self, el, sessionid=None):
		to = el.getAttribute('from')
		to_jid = internJID(to)
		ID = el.getAttribute('id')
		ulang = utils.getLang(el)

		iq = Element((None, 'iq'))
		iq.attributes = {'to': to, 'from': config.jid, 'type': 'result'}
		if ID:
			iq.attributes['id'] = ID
		command = iq.addElement('command')
		command.attributes = {
			'node': 'settings', 
			'xmlns': globals.COMMANDS, 
			'status': 'executing'
		}
		if sessionid:
			command.attributes['sessionid'] = sessionid
		else:
			command.attributes['sessionid'] = self.pytrans.makeMessageID()
		
		actions = command.addElement('actions')
		actions.attributes['execute'] = 'next'
		actions.addElement('next')

		x = command.addElement('x')
		x.attributes = {'xmlns': 'jabber:x:data', 'type': 'form'}
		x.addElement('title', None, lang.get('command_Settings'))
		x.addElement('instructions', None, lang.get('settings_instructions'))
		
		field = x.addElement('field')
		field.attributes = {
			'var': 'settings_page',
			'type': 'list-single',
			'label': lang.get('settings_category')
		}
		field.addElement('desc', None, lang.get('settings_instructions_Desc'))
		
		option = field.addElement('option')
		option.attributes['label'] = lang.get('settings_category_clist')
		option.addElement('value', None, 'clist_settings')
		
		option = field.addElement('option')
		option.attributes['label'] = lang.get('settings_category_xstatus')
		option.addElement('value', None, 'xstatus_settings')
		
		option = field.addElement('option')
		option.attributes['label'] = lang.get('settings_category_message')
		option.addElement('value', None, 'message_settings')
		
		option = field.addElement('option')
		option.attributes['label'] = lang.get('settings_category_personal_events')
		option.addElement('value', None, 'personal_events_settings')

		option = field.addElement('option')
		option.attributes['label'] = lang.get('settings_category_autoanswer')
		option.addElement('value', None, 'autoanswer_settings')
		
		stage = x.addElement('field')
		stage.attributes = {'type': 'hidden', 'var': 'stage'}
		stage.addElement('value', None, '1')

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

		iq = Element((None, 'iq'))
		iq.attributes = {'to': to, 'from': config.jid, 'type': 'result'}
		if ID:
			iq.attributes['id'] = ID
		command = iq.addElement('command')
		command.attributes = {
			'node': 'settings', 
			'xmlns': globals.COMMANDS, 
			'status': 'executing'
		}
		if sessionid:
			command.attributes['sessionid'] = sessionid
		else:
			command.attributes['sessionid'] = self.pytrans.makeMessageID()

		actions = command.addElement("actions")
		actions.attributes["execute"] = "complete"
		actions.addElement('prev')
		actions.addElement("complete")

		x = command.addElement("x")
		x.attributes = {'xmlns': 'jabber:x:data', 'type': 'form'}
		x.addElement('title', None, lang.get('settings_category_xstatus'))
		
		if config.xstatusessupport:
			field = x.addElement('field')
			field.attributes = {
				'var': 'away_messages_sending',
				'type': 'boolean',
				'label': lang.get('away_messages_sending')
			}
			field.addElement('value', None, str(settings['away_messages_sending']))
			field.addElement('desc', None, lang.get('away_messages_sending_Desc')) 
			
			field = x.addElement('field')
			field.attributes = {
				'var': 'away_messages_receiving',
				'type': 'boolean',
				'label': lang.get('away_messages_receiving')
			}
			field.addElement('value', None, str(settings['away_messages_receiving']))
			field.addElement('desc', None, lang.get('away_messages_receiving_Desc')) 
			
			xstatus_sending = {
				'xstatus_sendmode_none': 0,
				'xstatus_sendmode_ICQ5': 1,
				'xstatus_sendmode_ICQ6': 2,
				'xstatus_sendmode_ICQ5_6': 3
			}
			field = x.addElement('field')
			field.attributes = {
				'var': 'xstatus_sending_mode',
				'type': 'list-single',
				'label': lang.get('xstatus_sendmode')
			}
			for title in xstatus_sending:
				option = field.addElement('option')
				option.attributes['label'] = lang.get(title)
				option.addElement('value', None, str(xstatus_sending[title]))
			field.addElement('value', None, str(settings['xstatus_sending_mode']))
			field.addElement('desc', None, lang.get('xstatus_sendmode_Desc')) 
				
			field = x.addElement('field')
			field.attributes = {
				'var': 'xstatus_saving_enabled',
				'type': 'boolean',
				'label': lang.get('xstatus_restore_after_disconnect')
			}
			field.addElement('value', None, str(settings['xstatus_saving_enabled']))	
			field.addElement('desc', None, lang.get('xstatus_restore_after_disconnect_Desc')) 
			
			xstatus_receiving = {
				'xstatus_recvmode_none': 0,
				'xstatus_recvmode_ICQ5': 1,
				'xstatus_recvmode_ICQ6': 2,
				'xstatus_recvmode_ICQ5_6': 3
			}
			field = x.addElement('field')
			field.attributes = {
				'var': 'xstatus_receiving_mode',
				'type': 'list-single',
				'label': lang.get('xstatus_recvmode')
			}
			for title in xstatus_receiving:
				option = field.addElement('option')
				option.attributes['label'] = lang.get(title)
				option.addElement('value', None, str(xstatus_receiving[title]))
			field.addElement('value', None, str(settings['xstatus_receiving_mode']))
			field.addElement('desc', None, lang.get('xstatus_recvmode_Desc')) 
			
			field = x.addElement('field')
			field.attributes = {
				'var': 'xstatus_option_smooth',
				'type': 'boolean',
				'label': lang.get('xstatus_option_smooth')
			}
			field.addElement('value', None, str(settings['xstatus_option_smooth']))
			field.addElement('desc', None, lang.get('xstatus_option_smooth_Desc')) 
			
			field = x.addElement('field')
			field.attributes = {
				'var': 'xstatus_display_icon_as_PEP',
				'type': 'boolean',
				'label': lang.get('xstatus_display_icon_as_PEP')
			}
			field.addElement('value', None, str(settings['xstatus_display_icon_as_PEP']))
			field.addElement('desc', None, lang.get('xstatus_display_icon_as_PEP_Desc')) 
			
			field = x.addElement('field')
			field.attributes = {
				'var': 'xstatus_display_text_as_PEP',
				'type': 'boolean',
				'label': lang.get('xstatus_display_text_as_PEP')
			}
			field.addElement('value', None, str(settings['xstatus_display_text_as_PEP']))
			field.addElement('desc', None, lang.get('xstatus_display_text_as_PEP_Desc')) 
			
			field = x.addElement('field')
			field.attributes = {
				'var': 'xstatus_icon_for_transport',
				'type': 'boolean',
				'label': lang.get('xstatus_icon_for_transport')
			}
			field.addElement('value', None, str(settings['xstatus_icon_for_transport']))
			field.addElement('desc', None, lang.get('xstatus_icon_for_transport_Desc')) 
			
		field = x.addElement('field')
		field.attributes = {'type': 'hidden', 'var': 'settings_page'}
		field.addElement('value', None, 'xstatus_settings')
		
		stage = x.addElement('field')
		stage.attributes = {'type': 'hidden', 'var': 'stage'}
		stage.addElement('value', None, '2')
		
		self.pytrans.send(iq)
		
	def sendContactListSettingsForm(self, el, sessionid=None):
		to = el.getAttribute("from")
		ID = el.getAttribute("id")
		ulang = utils.getLang(el)
		
		toj = internJID(to)
		jid = toj.userhost()
		
		bos = self.pytrans.sessions[jid].legacycon.bos
		settings = bos.selfSettings
		
		iq = Element((None, 'iq'))
		iq.attributes = {'to': to, 'from': config.jid, 'type': 'result'}
		if ID:
			iq.attributes['id'] = ID
		command = iq.addElement('command')
		command.attributes = {
			'node': 'settings', 
			'xmlns': globals.COMMANDS, 
			'status': 'executing'
		}
		if sessionid:
			command.attributes['sessionid'] = sessionid
		else:
			command.attributes['sessionid'] = self.pytrans.makeMessageID()
	
		actions = command.addElement("actions")
		actions.attributes["execute"] = "complete"
		actions.addElement('prev')
		actions.addElement("complete")

		x = command.addElement("x")
		x.attributes = {'xmlns': 'jabber:x:data', 'type': 'form'}
		
		title = x.addElement('title')
		title.addContent(lang.get('settings_category_clist'))
		
		field = x.addElement('field')
		field.attributes = {
			'var': 'clist_show_phantombuddies',
			'type': 'boolean',
			'label': lang.get('settings_clist_show_phantombuddies') % bos.ssistats['phantombuddies']
		}
		field.addElement('value', None, str(settings['clist_show_phantombuddies']))
		field.addElement('desc', None, lang.get('settings_clist_show_phantombuddies_Desc')) 
		
		field = x.addElement('field')
		field.attributes = {
			'var': 'clist_deny_all_auth_requests',
			'type': 'boolean',
			'label': lang.get('settings_clist_deny_all_auth_requests')
		}
		field.addElement('value', None, str(settings['clist_deny_all_auth_requests']))
		field.addElement('desc', None, lang.get('settings_clist_deny_all_auth_requests_Desc')) 
		
		field = x.addElement('field')
		field.attributes = {'type': 'hidden', 'var': 'settings_page'}
		field.addElement('value', None, 'clist_settings')
		
		stage = x.addElement('field')
		stage.attributes = {'type': 'hidden', 'var': 'stage'}
		stage.addElement('value', None, '2')
		
		self.pytrans.send(iq)
		
	def sendMessageSettingsForm(self, el, sessionid=None):
		to = el.getAttribute("from")
		ID = el.getAttribute("id")
		ulang = utils.getLang(el)
		
		toj = internJID(to)
		jid = toj.userhost()
		
		bos = self.pytrans.sessions[jid].legacycon.bos
		settings = bos.selfSettings

		iq = Element((None, 'iq'))
		iq.attributes = {'to': to, 'from': config.jid, 'type': 'result'}
		if ID:
			iq.attributes['id'] = ID
		command = iq.addElement('command')
		command.attributes = {
			'node': 'settings', 
			'xmlns': globals.COMMANDS, 
			'status': 'executing'
		}
		if sessionid:
			command.attributes['sessionid'] = sessionid
		else:
			command.attributes['sessionid'] = self.pytrans.makeMessageID()
		
		actions = command.addElement("actions")
		actions.attributes["execute"] = "complete"
		actions.addElement('prev')
		actions.addElement("complete")

		x = command.addElement('x')
		x.attributes = {'xmlns': 'jabber:x:data', 'type': 'form'}
		x.addElement('title', None, lang.get('settings_category_message'))

		userencoding_list = {
			'userencoding_list_western_iso': 'iso-8859-1',
			'userencoding_list_western_win': 'cp1252',
			'userencoding_list_ceuropean_iso': 'iso-8859-2',
			'userencoding_list_ceuropean_win': 'cp1250',
			'userencoding_list_seuropean_iso': 'iso-8859-3',
			'userencoding_list_cyrillic_iso': 'iso-8859-5',
			'userencoding_list_cyrillic_win': 'cp1251',
			'userencoding_list_greek_iso': 'iso-8859-7',
			'userencoding_list_greek_win': 'cp1253',
			'userencoding_list_hebrew_iso': 'iso-8859-8',
			'userencoding_list_hebrew_win': 'cp1255',
			'userencoding_list_selected': 'selected'
		}
		field = x.addElement('field')
		field.attributes = {
			'var': 'userencoding_list', 
			'type': 'list-single',
			'label': lang.get('userencoding_list')
		}
		for title in userencoding_list:
			option = field.addElement('option')
			option.attributes['label'] = lang.get(title)
			option.addElement('value', None, str(userencoding_list[title]))
		if str(settings['userencoding_list']) not in userencoding_list.values() and str(settings['userencoding_list']) != config.encoding: # encoding not from list
			option = field.addElement('option')
			option.attributes['label'] = '%s (%s)' % (lang.get('userencoding_list_other'), str(settings['userencoding_list']))
			option.addElement('value', None, str(settings['userencoding_list']))
		if config.encoding not in userencoding_list.values(): # encoding from config
			option = field.addElement('option')
			option.attributes['label'] = '%s (%s)' % (lang.get('userencoding_list_default'), config.encoding)
			option.addElement('value', None, config.encoding)
		field.addElement('value', None, str(settings['userencoding_list']))
		field.addElement('desc', None, lang.get('userencoding_list_Desc'))

		field = x.addElement('field')
		field.attributes = {
			'var': 'userencoding_other', 
			'type': 'text-single',
			'label': lang.get('userencoding_other')
		}
		field.addElement('value', None, str(settings['userencoding_other']))
		field.addElement('desc', None, lang.get('userencoding_other_Desc')) 
		
		utf8_messages_sendmode = {
			'utf8_messages_sendmode_none': 0,
			'utf8_messages_sendmode_as_reply': 1,
			'utf8_messages_sendmode_always': 2
		}
		field = x.addElement('field')
		field.attributes = {
			'var': 'utf8_messages_sendmode',
			'type': 'list-single',
			'label': lang.get('utf8_messages_sendmode')
		}
		for title in utf8_messages_sendmode:
			option = field.addElement('option')
			option.attributes['label'] = lang.get(title)
			option.addElement('value', None, str(utf8_messages_sendmode[title]))
		field.addElement('value', None, str(settings['utf8_messages_sendmode']))
		field.addElement('desc', None, lang.get('utf8_messages_sendmode_Desc')) 
		
		msgconfirm_sendmode = {
			'msgconfirm_sendmode_none': 0,
			'msgconfirm_sendmode_for_utf8': 1,
			'msgconfirm_sendmode_always': 2
		}
		field = x.addElement('field')
		field.attributes = {
			'var': 'msgconfirm_sendmode',
			'type': 'list-single',
			'label': lang.get('msgconfirm_sendmode')
		}
		for title in msgconfirm_sendmode:
			option = field.addElement('option')
			option.attributes['label'] = lang.get(title)
			option.addElement('value', None, str(msgconfirm_sendmode[title]))
		field.addElement('value', None, str(settings['msgconfirm_sendmode']))
		field.addElement('desc', None, lang.get('msgconfirm_sendmode_Desc')) 
		
		field = x.addElement('field')
		field.attributes = {
			'var': 'msgconfirm_recvmode',
			'type': 'boolean',
			'label': lang.get('msgconfirm_recvmode')
		}
		field.addElement('value', None, str(settings['msgconfirm_recvmode']))
		field.addElement('desc', None, lang.get('msgconfirm_recvmode_Desc')) 
		
		offline_messages_sendenc = {
			'offline_messages_sendenc_unicode': 0,
			'offline_messages_sendenc_local': 1,
			'offline_messages_sendenc_auto': 2
		}
		field = x.addElement('field')
		field.attributes = {
			'var': 'offline_messages_sendenc',
			'type': 'list-single',
			'label': lang.get('offline_messages_sendenc')
		}
		for title in offline_messages_sendenc:
			option = field.addElement('option')
			option.attributes['label'] = lang.get(title)
			option.addElement('value', None, str(offline_messages_sendenc[title]))
		field.addElement('value', None, str(settings['offline_messages_sendenc']))
		field.addElement('desc', None, lang.get('offline_messages_sendenc_Desc')) 

		field = x.addElement('field')
		field.attributes = {'type': 'hidden', 'var': 'settings_page'}
		field.addElement('value', None, 'message_settings')
		
		stage = x.addElement('field')
		stage.attributes = {'type': 'hidden', 'var': 'stage'}
		stage.addElement('value', None, '2')
		
		self.pytrans.send(iq)
		
	def sendPersonalEventsSettingsForm(self, el, sessionid=None):
		to = el.getAttribute("from")
		ID = el.getAttribute("id")
		ulang = utils.getLang(el)
		
		toj = internJID(to)
		jid = toj.userhost()
		
		bos = self.pytrans.sessions[jid].legacycon.bos
		settings = bos.selfSettings
		
		iq = Element((None, 'iq'))
		iq.attributes = {'to': to, 'from': config.jid, 'type': 'result'}
		if ID:
			iq.attributes['id'] = ID
		command = iq.addElement('command')
		command.attributes = {
			'node': 'settings', 
			'xmlns': globals.COMMANDS, 
			'status': 'executing'
		}
		if sessionid:
			command.attributes['sessionid'] = sessionid
		else:
			command.attributes['sessionid'] = self.pytrans.makeMessageID()	

		actions = command.addElement("actions")
		actions.attributes["execute"] = "complete"
		actions.addElement('prev')
		actions.addElement("complete")

		x = command.addElement("x")
		x.attributes = {'xmlns': 'jabber:x:data', 'type': 'form'}
		x.addElement('title', None, lang.get('settings_category_personal_events'))
		
		field = x.addElement('field')
		field.attributes = {
			'var': 'user_mood_receiving',
			'type': 'boolean',
			'label': lang.get('user_mood_receiving')
		}
		field.addElement('value', None, str(settings['user_mood_receiving']))
		field.addElement('desc', None, lang.get('user_mood_receiving_Desc')) 
		
		field = x.addElement('field')
		field.attributes = {
			'var': 'user_activity_receiving',
			'type': 'boolean',
			'label': lang.get('user_activity_receiving')
		}
		field.addElement('value', None, str(settings['user_activity_receiving']))
		field.addElement('desc', None, lang.get('user_activity_receiving_Desc')) 
		
		field = x.addElement('field')
		field.attributes = {
			'var': 'user_tune_receiving',
			'type': 'boolean',
			'label': lang.get('user_tune_receiving')
		}
		field.addElement('value', None, settings['user_tune_receiving'])
		field.addElement('desc', None, lang.get('user_tune_receiving_Desc')) 
		
		field = x.addElement('field')
		field.attributes = {'type': 'hidden', 'var': 'settings_page'}
		field.addElement('value', None, 'personal_events_settings')
		
		stage = x.addElement('field')
		stage.attributes = {'type': 'hidden', 'var': 'stage'}
		stage.addElement('value', None, '2')
		
		self.pytrans.send(iq)

	def sendAutoanswerSettingsForm(self, el, sessionid=None):
		to = el.getAttribute("from")
		ID = el.getAttribute("id")
		ulang = utils.getLang(el)
		
		toj = internJID(to)
		jid = toj.userhost()
		
		bos = self.pytrans.sessions[jid].legacycon.bos
		settings = bos.selfSettings
		
		
		iq = Element((None, 'iq'))
		iq.attributes = {'to': to, 'from': config.jid, 'type': 'result'}
		if ID:
			iq.attributes['id'] = ID
		command = iq.addElement('command')
		command.attributes = {
			'node': 'settings', 
			'xmlns': globals.COMMANDS, 
			'status': 'executing'
		}
		if sessionid:
			command.attributes['sessionid'] = sessionid
		else:
			command.attributes['sessionid'] = self.pytrans.makeMessageID()

		actions = command.addElement("actions")
		actions.attributes["execute"] = "complete"
		actions.addElement('prev')
		actions.addElement("complete")

		x = command.addElement("x")
		x.attributes = {'xmlns': 'jabber:x:data', 'type': 'form'}
		
		title = x.addElement('title')
		title.addContent(lang.get('settings_category_autoanswer'))

		field = x.addElement('field')
		field.attributes = {
			'var': 'autoanswer_text',
			'type': 'text-multi',
			'label': lang.get('autoanswer_text')
		}
		value = field.addElement('value')
		if 'autoanswer_text' in settings:
			value.addContent(str(settings['autoanswer_text']))
		else:
			value.addContent(lang.get('autoanswer_text_content'))
		field.addElement('desc', None, lang.get('autoanswer_text_Desc')) 

		field = x.addElement('field')
		field.attributes = {
			'var': 'autoanswer_enable',
			'type': 'boolean',
			'label': lang.get('autoanswer_enable')
		}
		field.addElement('value', None, str(settings['autoanswer_enable']))
		field.addElement('desc', None, lang.get('autoanswer_enable_Desc')) 

		field = x.addElement('field')
		field.attributes = {
			'var': 'autoanswer_hide_dialog',
			'type': 'boolean',
			'label': lang.get('autoanswer_hide_dialog')
		}
		field.addElement('value', None, str(settings['autoanswer_hide_dialog']))
		field.addElement('desc', None, lang.get('autoanswer_hide_dialog_Desc')) 

		field = x.addElement('field')
		field.attributes = {'type': 'hidden', 'var': 'settings_page'}
		field.addElement('value', None, 'autoanswer_settings')

		stage = x.addElement('field')
		stage.attributes = {'type': 'hidden', 'var': 'stage'}
		stage.addElement('value', None, '2')

		self.pytrans.send(iq)
		
	def sendCompletedForm(self, el, sessionid=None):
		to = el.getAttribute('from')
		ID = el.getAttribute('id')
		ulang = utils.getLang(el)
		
		iq = Element((None, 'iq'))
		iq.attributes = {'to': to, 'from': config.jid, 'type': 'result'}
		if ID:
			iq.attributes['id'] = ID
		command = iq.addElement('command')
		command.attributes = {
			'node': 'settings', 
			'xmlns': globals.COMMANDS, 
			'status': 'completed'
		}
		if sessionid:
			command.attributes['sessionid'] = sessionid
		else:
			command.attributes['sessionid'] = self.pytrans.makeMessageID()

		note = command.addElement('note', None, lang.get('settings_changed'))
		note.attributes['type'] = 'info'
		
		x = command.addElement('x')
		x.attributes = {'xmlns': 'jabber:x:data', 'type': 'form'}
		x.addElement('title', None, lang.get('command_Settings'))
		x.addElement('instructions', None, lang.get('settings_changed'))
		
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
		bos.updateUserEncoding()
				
	def ApplyPersonalEventsSettings(self, to_jid, settings):
		jid = to_jid.userhost()
		LogEvent(INFO, jid)
		bos = self.pytrans.sessions[jid].legacycon.bos
		bos.addToSelfSettings(settings)
		if jid in self.pytrans.sessions:
			for key in settings:
				self.pytrans.xdb.setCSetting(jid, key, str(settings[key]))

	def ApplyAutoanswerSettings(self, to_jid, settings):
		jid = to_jid.userhost()
		LogEvent(INFO, jid)
		bos = self.pytrans.sessions[jid].legacycon.bos
		bos.addToSelfSettings(settings)
		if jid in self.pytrans.sessions:
			for key in settings:
				self.pytrans.xdb.setCSetting(jid, key, str(settings[key]))
