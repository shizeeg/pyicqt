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

# TODO: rewrite with better code)
class SetXStatus:
	def __init__(self, pytrans):
		self.pytrans = pytrans
		self.pytrans.adhoc.addCommand('setxstatus', self.incomingIq, 'command_SetXStatus')

	def incomingIq(self, el):
		
		xstatus_name = None
		xstatus_title = None
		xstatus_desc = None
		sessionid = None
		do_action = None
		stage = 0
		changed_message = 'Your x-status has been set'
		disabled_message = 'X-status sending support disabled. Check your settings for details'
		
		to = el.getAttribute('from')
		toj = internJID(to)
		jid = toj.userhost()
		ID = el.getAttribute('id')
		ulang = utils.getLang(el)
		
		log.msg('to %s, toj %s, ID %s, ulang %s' % (to,toj,ID,ulang))
		
		for command in el.elements():
			sessionid = command.getAttribute('sessionid')
			
			if self.pytrans.sessions.has_key(jid):
				if not self.pytrans.sessions[jid].legacycon.bos.settingsOptionEnabled('xstatus_sending_enabled'):
					self.sendXStatusCompleted(el, disabled_message, sessionid)
			
			if command.getAttribute('action') == 'execute':
				pass
			elif command.getAttribute('action') == 'complete':
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
							if field.getAttribute('var') == 'xstatus_name':
								for value in field.elements():
									if value.name == 'value':
										xstatus_name = value.__str__()
							elif field.getAttribute('var') == 'xstatus_title':
								for value in field.elements():
									if value.name == 'value':
										xstatus_title = value.__str__()
							elif field.getAttribute('var') == 'xstatus_desc': 
								for value in field.elements():
									if value.name == 'value':
										xstatus_desc = value.__str__()
			
		if not self.pytrans.sessions.has_key(jid): # if user not logined
			self.pytrans.adhoc.sendError('setxstatus', el, errormsg=lang.get('command_NoSession', ulang), sessionid=sessionid)
		elif not hasattr(self.pytrans.sessions[toj.userhost()].legacycon, 'bos'):  # if user not connected to ICQ network
			self.pytrans.adhoc.sendError('setxstatus', el, errormsg=lang.get('command_NoSession', ulang), sessionid=sessionid)
		elif stage == '1':
			if xstatus_name != 'None':
				self.sendXStatusTextSelectionForm(el, xstatus_name, sessionid) # send second form
			else:
				self.setXStatus(toj, xstatus_name) # set only x-status name (icon)
				self.sendXStatusCompleted(el, changed_message, sessionid) # send ack to user
		elif stage == '2' or do_action == 'done':
			self.setXStatus(toj, xstatus_name, xstatus_title, xstatus_desc) # set x-status name and text
			self.sendXStatusCompleted(el, changed_message, sessionid) # send ack to user
		elif do_action == 'cancel':
			self.pytrans.adhoc.sendCancellation("setxstatus", el, sessionid) # correct cancel handling
		else:
			self.sendXStatusNameSelectionForm(toj, el, sessionid) # send first form
			
	def sendXStatusNameSelectionForm(self, to_jid, el, sessionid=None):
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
		command.attributes['status'] = 'executing'
		
		actions = command.addElement('actions')
		actions.attributes['execute'] = 'next'
		actions.addElement('next')

		x = command.addElement('x')
		x.attributes['xmlns'] = 'jabber:x:data'
		x.attributes['type'] = 'form'

		title = x.addElement('title')
		title.addContent('Set x-status name') # TODO: translate
		
		instructions = x.addElement('instructions')
		instructions.addContent('Select x-status from list below\n\
Note: official clients supports only 24 statuses\n\
(Angry - Typing), support for other could be\n\
depends from ICQ client') # TODO: translate
		
		field = x.addElement('field')
		field.attributes['var'] = 'xstatus_name'
		field.attributes['type'] =  'list-single'
		field.attributes['label'] =  'x-status name'
		
		option = field.addElement('option')
		option.attributes['label'] = 'No x-status'
		value = option.addElement('value')
		value.addContent('None')
		
		current_xstatus_name = self.pytrans.sessions[to_jid.userhost()].legacycon.bos.getSelfXstatusName()
		if current_xstatus_name != '':
			option = field.addElement('option')
			option.attributes['label'] = 'Keep current x-status (%s)' % current_xstatus_name
			value = option.addElement('value')
			value.addContent(current_xstatus_name)
		
		for xstatus_title in oscar.X_STATUS_NAME:
			option = field.addElement('option')
			option.attributes['label'] = xstatus_title
			value = option.addElement('value')
			value.addContent(xstatus_title)
			
		stage = x.addElement('field')
		stage.attributes['type'] = 'hidden'
		stage.attributes['var'] = 'stage'
		value = stage.addElement('value')
		value.addContent('1')

		self.pytrans.send(iq)
		
	def sendXStatusTextSelectionForm(self, el, xstatus_name, sessionid=None):
		# TODO: add check for None and KeepCurrent, save title and desc in conf for user
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
		command.attributes['status'] = 'executing'
		
		actions = command.addElement('actions')
		actions.attributes['execute'] = 'next'
		actions.addElement('prev')
		actions.addElement('complete')

		x = command.addElement('x')
		x.attributes['xmlns'] = 'jabber:x:data'
		x.attributes['type'] = 'form'

		title = x.addElement('title')
		title.addContent('Set x-status title and description') # TODO: translate	
			
		toj = internJID(to)
		jid = toj.userhost()
		xstatus_number = self.pytrans.sessions[jid].legacycon.bos.getXstatusNumberByName(xstatus_name)
		title, desc = self.pytrans.xdb.getXstatusText(jid, xstatus_number)
		if title == '':
			title = xstatus_name	
			
		xstatus_title = x.addElement('field')
		xstatus_title.attributes['type'] = 'text-single'
		xstatus_title.attributes['var'] = 'xstatus_title'
		xstatus_title.attributes['label'] = 'x-status title'
		value = xstatus_title.addElement('value')
		value.addContent(title)
		
		xstatus_desc = x.addElement('field')
		xstatus_desc.attributes['type'] = 'text-multi'
		xstatus_desc.attributes['var'] = 'xstatus_desc'
		xstatus_desc.attributes['label'] = 'x-status description'
		value = xstatus_desc.addElement('value')
		value.addContent(desc)
		
		xstatus_icon = x.addElement('field')
		xstatus_icon.attributes['type'] = 'hidden'
		xstatus_icon.attributes['var'] = 'xstatus_name'
		value = xstatus_icon.addElement('value')
		value.addContent(xstatus_name)
		
		stage = x.addElement('field')
		stage.attributes['type'] = 'hidden'
		stage.attributes['var'] = 'stage'
		value = stage.addElement('value')
		value.addContent('2')
		
		self.pytrans.send(iq)
		
	def sendXStatusCompleted(self, el, message, sessionid=None):
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
		
		self.pytrans.send(iq)
	
	def setXStatus(self, to_jid, xstatus_name, xstatus_title=None, xstatus_desc=None):
		jid = to_jid.userhost()
		bos = self.pytrans.sessions[jid].legacycon.bos
		if xstatus_name == 'None':
			# no x-status
			bos.selfCustomStatus['x-status name'] = ''
		elif xstatus_name == 'KeepCurrent':
			# not do nothing
			pass
		else:
			bos.selfCustomStatus['x-status name'] = xstatus_name
			if xstatus_title:
				bos.selfCustomStatus['x-status title'] = xstatus_title
			else:
				bos.selfCustomStatus['x-status title'] = ''
			if xstatus_desc:
				bos.selfCustomStatus['x-status desc'] = xstatus_desc
			else:
				bos.selfCustomStatus['x-status desc'] = ''
		bos.updateSelfXstatus()
		
		xstatus_number = bos.getXstatusNumberByName(xstatus_name)
		if xstatus_number > -1:
			if self.pytrans.sessions.has_key(jid):
				self.pytrans.xdb.setXstatusText(jid, xstatus_number, xstatus_title, xstatus_desc)
				log.msg('3. x-status desc: %s' % xstatus_desc)
				if self.pytrans.xdb.getCSetting(jid, 'xstatus_saving_enabled'):
					self.pytrans.xdb.setCSetting(jid, 'latest_xstatus_number', str(xstatus_number))
