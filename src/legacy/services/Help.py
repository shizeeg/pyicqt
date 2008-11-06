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

		for command in el.elements():
			sessionid = command.getAttribute('sessionid')
			if command.getAttribute('action') == 'cancel':
				self.pytrans.adhoc.sendCancellation('help', el, sessionid)
				return

		self.showHelp(el, sessionid=None)
			
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
		command.attributes['status'] = 'completed'

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
		value = field.addElement('value')
		value.addContent(help_mainwiki)
		desc = field.addElement('desc')
		desc.addContent(lang.get('help_mainwiki_Desc'))
		
		field = x.addElement('field')
		field.attributes['type'] =  'text-single'
		field.attributes['label'] = lang.get('help_maillist')
		value = field.addElement('value')
		value.addContent(help_maillist)
		desc = field.addElement('desc')
		desc.addContent(lang.get('help_maillist_Desc'))
		
		field = x.addElement('field')
		field.attributes['type'] =  'text-single'
		field.attributes['label'] = lang.get('help_mainroom')
		value = field.addElement('value')
		value.addContent(help_mainroom)
		desc = field.addElement('desc')
		desc.addContent(lang.get('help_mainroom_Desc')) 
		
		if config.transportWebsite:
			field = x.addElement('field')
			field.attributes['type'] =  'text-single'
			field.attributes['label'] = lang.get('help_localwebsite')
			value = field.addElement('value')
			value.addContent(config.transportWebsite)
			desc = field.addElement('desc')
			desc.addContent(lang.get('help_localwebsite_Desc')) 
			
		if config.supportRoom:
			field = x.addElement('field')
			field.attributes['type'] =  'text-single'
			field.attributes['label'] = lang.get('help_localroom')
			value = field.addElement('value')
			value.addContent(config.supportRoom)
			desc = field.addElement('desc')
			desc.addContent(lang.get('help_localroom_Desc'))  
			
		if config.supportJid:
			field = x.addElement('field')
			field.attributes['type'] =  'text-single'
			field.attributes['label'] = lang.get('help_localsupportjid')
			value = field.addElement('value')
			value.addContent(config.supportJid)
			desc = field.addElement('desc')
			desc.addContent(lang.get('help_localsupportjid_Desc'))  
		
		self.pytrans.send(iq)
		
help_mainroom = 'pytransports@conference.jabber.modevia.com'
help_maillist = 'http://groups.google.com/group/py-transports'
help_mainwiki = 'http://code.google.com/p/pyicqt/wiki/UserStartPage'

