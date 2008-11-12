# Licensed for distribution under the GPL version 2, check COPYING for details

import config
from twisted.words.xish.domish import Element
from twisted.words.protocols.jabber.jid import internJID
import utils
import lang
import globals
from adhoc import rights_guest, rights_user, rights_admin

class Help:
	def __init__(self, pytrans):
		self.pytrans = pytrans
		self.pytrans.adhoc.addCommand('help', self.incomingIq, 'command_Help', rights_guest)
		
	def incomingIq(self, el):
		to = el.getAttribute('from')
		toj = internJID(to)
		ID = el.getAttribute('id')
		ulang = utils.getLang(el)

		sessionid = None
		help_action = None
		action = None
		stage = '0'

		for command in el.elements():
			sessionid = command.getAttribute('sessionid')
			action = command.getAttribute('action')
			if action == 'cancel':
				self.pytrans.adhoc.sendCancellation('help', el, sessionid)
				return
			for child in command.elements():
				if child.name == 'x':
					for field in child.elements():
						if field.name == 'field':
							if field.getAttribute('var') == 'help_action':
								for value in field.elements():
									if value.name == 'value':
										help_action = value.__str__()
							elif field.getAttribute('var') == 'stage':
								for value in field.elements():
									if value.name == 'value':
										stage = value.__str__()
		if str(stage) == '0':
			self.showHelp(el, sessionid)
		elif str(stage) == '1':
			if not action or action == 'next':
				self.showHelpAction(el, sessionid)
			else:
				self.showHelpDone(el, lang.get('command_Done'), sessionid)
		elif str(stage) == '2':
			self.showHelpDone(el, lang.get('help_invitation_sent'), sessionid)
			if help_action:
				self.sendInvitation(el, help_action, sessionid)
			
	def showHelp(self, el, sessionid=None):
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
		command.attributes['node'] = 'help'
		command.attributes['xmlns'] = globals.COMMANDS
		command.attributes['status'] = 'executing'
		
		actions = command.addElement('actions')
		actions.attributes['execute'] = 'next'
		actions.addElement('next')
		actions.addElement('complete')

		x = command.addElement('x')
		x.attributes['xmlns'] = 'jabber:x:data'
		x.attributes['type'] = 'form'

		title = x.addElement('title')
		title.addContent(lang.get('command_Help'))
		
		instructions = x.addElement('instructions')
		instructions.addContent(lang.get('help_documentation'))
		
		field = x.addElement('field')
		field.attributes['type'] =  'text-single'
		field.attributes['label'] = lang.get('help_mainwiki')
		field.attributes['var'] = 'help_mainwiki'
		value = field.addElement('value')
		value.addContent(help_mainwiki)
		desc = field.addElement('desc')
		desc.addContent(lang.get('help_mainwiki_Desc'))
		
		field = x.addElement('field')
		field.attributes['type'] =  'text-single'
		field.attributes['label'] = lang.get('help_maillist')
		field.attributes['var'] = 'help_maillist'
		value = field.addElement('value')
		value.addContent(help_maillist)
		desc = field.addElement('desc')
		desc.addContent(lang.get('help_maillist_Desc'))
		
		field = x.addElement('field')
		field.attributes['type'] =  'text-single'
		field.attributes['label'] = lang.get('help_mainroom')
		field.attributes['var'] = 'help_mainroom'
		value = field.addElement('value')
		value.addContent(help_mainroom)
		desc = field.addElement('desc')
		desc.addContent(lang.get('help_mainroom_Desc')) 
		
		if config.transportWebsite:
			field = x.addElement('field')
			field.attributes['type'] =  'text-single'
			field.attributes['label'] = lang.get('help_localwebsite')
			field.attributes['var'] = 'help_localwebsite'
			value = field.addElement('value')
			value.addContent(config.transportWebsite)
			desc = field.addElement('desc')
			desc.addContent(lang.get('help_localwebsite_Desc')) 
			
		if config.supportRoom:
			field = x.addElement('field')
			field.attributes['type'] =  'text-single'
			field.attributes['label'] = lang.get('help_localroom')
			field.attributes['var'] = 'help_localroom'
			value = field.addElement('value')
			value.addContent(config.supportRoom)
			desc = field.addElement('desc')
			desc.addContent(lang.get('help_localroom_Desc'))  
			
		if config.supportJid:
			field = x.addElement('field')
			field.attributes['type'] =  'text-single'
			field.attributes['label'] = lang.get('help_localsupportjid')
			field.attributes['var'] = 'help_localsupportjid'
			value = field.addElement('value')
			value.addContent(config.supportJid)
			desc = field.addElement('desc')
			desc.addContent(lang.get('help_localsupportjid_Desc'))
			
		stage = x.addElement('field')
		stage.attributes['type'] = 'hidden'
		stage.attributes['var'] = 'stage'
		value = stage.addElement('value')
		value.addContent('1')
		
		self.pytrans.send(iq)
		
	def showHelpAction(self, el, sessionid=None):
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
		command.attributes['node'] = 'help'
		command.attributes['xmlns'] = globals.COMMANDS
		command.attributes['status'] = 'executing'
		
		actions = command.addElement('actions')
		actions.attributes['execute'] = 'next'
		actions.addElement('next')

		x = command.addElement('x')
		x.attributes['xmlns'] = 'jabber:x:data'
		x.attributes['type'] = 'form'

		title = x.addElement('title')
		title.addContent(lang.get('command_Help'))
		
		instructions = x.addElement('instructions')
		instructions.addContent(lang.get('help_documentation'))
		
		field = x.addElement('field')
		field.attributes['var'] = 'help_action'
		field.attributes['type'] = 'list-single'
		field.attributes['label'] = lang.get('help_action')
		desc = field.addElement('desc')
		desc.addContent(lang.get('help_action_Desc'))
		
		option = field.addElement('option')
		option.attributes['label'] = help_mainroom
		value = option.addElement('value')
		value.addContent(help_mainroom)
		
		if config.supportRoom:
			option = field.addElement('option')
			option.attributes['label'] = config.supportRoom
			value = option.addElement('value')
			value.addContent(config.supportRoom)
			
		stage = x.addElement('field')
		stage.attributes['type'] = 'hidden'
		stage.attributes['var'] = 'stage'
		value = stage.addElement('value')
		value.addContent('2')
		
		self.pytrans.send(iq)
		
	def showHelpDone(self, el, message, sessionid=None):
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
		command.attributes['node'] = 'setxstatus'
		command.attributes['xmlns'] = globals.COMMANDS
		command.attributes['status'] = 'completed'
		
		note = command.addElement('note')
		note.attributes['type'] = 'info'
		note.addContent(message)
		
		x = command.addElement('x')
		x.attributes['xmlns'] = 'jabber:x:data'
		x.attributes['type'] = 'form'

		title = x.addElement('title')
		title.addContent(lang.get('command_Help'))
		
		instructions = x.addElement('instructions')
		instructions.addContent(message)
		
		self.pytrans.send(iq)
		
	def sendInvitation(self, el, help_action, sessionid=None):
		to = el.getAttribute('from')
		ID = el.getAttribute('id')
		ulang = utils.getLang(el)
		
		message = Element((None, 'message'))
		message.attributes['to'] = to
		message.attributes['from'] = config.jid
		if ID:
			message.attributes['id'] = ID
			
		x = message.addElement('x')
		x.attributes['xmlns'] = 'jabber:x:conference'
		x.attributes['jid'] = help_action
		
		self.pytrans.send(message)
		
		
help_mainroom = 'pytransports@conference.jabber.modevia.com'
help_maillist = 'http://groups.google.com/group/py-transports'
help_mainwiki = 'http://code.google.com/p/pyicqt/wiki/UserStartPage'

