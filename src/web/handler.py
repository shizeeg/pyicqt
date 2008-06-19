# Copyright 2004-2005 Daniel Henninger <jadestorm@nc.rr.com>
# Licensed for distribution under the GPL version 2, check COPYING for details

from nevow import rend, loaders, inevow, static
from nevow import tags as T
#from twisted.protocols import http
from twisted.web import microdom
from twisted.internet import reactor
from twisted.cred import portal, credentials
from debug import LogEvent, INFO, WARN, ERROR
import config
import legacy
import sys, os, os.path
import lang
import string
import avatar
from xmppcred import XMPPRealm, XMPPChecker, IXMPPAvatar
from twisted.words.protocols.jabber.jid import internJID
from tlib.httpcompat import http


X = os.path.sep

# Avatars Node
class WebInterface_avatars(rend.Page):
	def childFactory(self, ctx, name):
		avatarData = avatar.AvatarCache().getAvatarData(name)
		return static.Data(avatarData, "image/png")


# Template Node
class WebInterface_template(rend.Page):
	addSlash = True
	docFactory = loaders.xmlfile('data'+X+'www'+X+'template.html')

	def __init__(self, pytrans):
		self.pytrans = pytrans

	def renderHTTP(self, ctx):
		request = inevow.IRequest(ctx)
		username = request.getUser()
		password = request.getPassword()
		if not username or not password: return self._loginFailed(None, ctx)
		LogEvent(INFO, msg=repr(username))
		jabberPort = 5222
		port_sep = username.find("%")
		if port_sep != -1:
			jabberPort = int(username[port_sep+1:])
			username = username[0:port_sep]
		if username:
			try:
				j = internJID(username)
			except InvalidFormat:
				return self._loginFailed(None, ctx)
			jabberHost = j.host
		else:
			jabberHost = config.mainServer
		LogEvent(INFO, msg="Port = %r" % jabberPort)
		p = portal.Portal(XMPPRealm())
		p.registerChecker(XMPPChecker(jabberHost, jabberPort, tryonce=1))
		creds = credentials.UsernamePassword(username, password)
		return p.login(creds, None, IXMPPAvatar).addCallback(
			self._loginSucceeded, ctx).addErrback(
			self._loginFailed, ctx)

	def _loginSucceeded(self, avatarInfo, ctx):
		return rend.Page.renderHTTP(self, ctx)

	def _loginFailed(self, result, ctx):
		request = inevow.IRequest(ctx)
		request.setHeader('WWW-Authenticate', 'Basic realm="PyICQ-t Web Interface"')
		request.setResponseCode(http.UNAUTHORIZED)
		return "Authorization required."

	def render_version(self, ctx, data):
		return [legacy.version]

	def render_title(self, ctx, data):
		return [legacy.name]

	def render_menu(self, ctx, data):
		request = inevow.IRequest(ctx)
		username = request.getUser()

		ret = T.table(border=0,cellspacing=3,cellpadding=3)
		row = T.tr(valign="middle")
		row[T.td(_class="menuentry",width="150",align="center",onclick="self.location='/account/'",onmouseover="this.className='menuentrypressed';",onmouseout="this.className='menuentry';")[T.a(_class="menuentry",href="/account/")["Account"]]]

		if config.admins.count(username) > 0:
			row[T.td(_class="menuentry",width="150",align="center",onclick="self.location='/status/'",onmouseover="this.className='menuentrypressed';",onmouseout="this.className='menuentry';")[T.a(_class="menuentry",href="/status/")["Status"]]]
			row[T.td(_class="menuentry",width="150",align="center",onclick="self.location='/config/'",onmouseover="this.className='menuentrypressed';",onmouseout="this.className='menuentry';")[T.a(_class="menuentry",href="/config/")["Configuration"]]]
			row[T.td(_class="menuentry",width="150",align="center",onclick="self.location='/controls/'",onmouseover="this.className='menuentrypressed';",onmouseout="this.className='menuentry';")[T.a(_class="menuentry",href="/controls/")["Controls"]]]

		ret[row]

		return ret

	child_images = static.File('data'+X+'www'+X+'images'+X)
	child_css = static.File('data'+X+'www'+X+'css'+X)
	child_avatars = WebInterface_avatars()


# Root Node
class WebInterface(WebInterface_template):
	def childFactory(self, ctx, name):
		LogEvent(INFO, msg="childFactory %s %s" % (ctx, name))

		if name == "account":
			return WebInterface_account(pytrans=self.pytrans)
		if name == "status":
			return WebInterface_status(pytrans=self.pytrans)
		if name == "config":
			return WebInterface_config(pytrans=self.pytrans)
		if name == "controls":
			return WebInterface_controls(pytrans=self.pytrans)
		else:
			pass

	def render_content(self, ctx):
		return loaders.htmlstr("""
<P CLASS="intro">Welcome to the PyICQ-t web interface.  At
present, these interfaces are very limited, mostly providing miscellaneous
information about the transport.  Eventually, this interface will do more,
but for now, enjoy the statistics and such!</P>
""")


# Account Node
class WebInterface_account(WebInterface_template):
	def render_content(self, ctx, data):
		return loaders.htmlstr("""
<B>Your Account</B>
<HR />
<SPAN nevow:render="info" />
<BR /><BR />
<B>Roster</B>
<HR />
<SPAN nevow:render="roster" />
""")

	def render_info(self, ctx, data):
		request = inevow.IRequest(ctx)
		username = request.getUser()
		reg = self.pytrans.xdb.getRegistration(username)
		if not reg:
			return "You are not currently registered with the transport."

		return reg[0]

	def render_roster(self, ctx, data):
		request = inevow.IRequest(ctx)
		username = request.getUser()

		ret = T.table(border = 0,cellspacing=5,cellpadding=2)
		row = T.tr(height=25)[
			T.th["UIN/Screen Name"],
			T.th["Nickname"],
			T.th["Network"],
			T.th["Avatar"],
			T.th["Status"]
		]
		ret[row]
		roster = self.pytrans.xdb.getList("roster", username)
		if not roster:
			return ret
		for item in roster:
			if item[0][0].isdigit():
				network = "ICQ"
			else:
				network = "AIM"
			avatar = "-"
			if not config.disableAvatars and item[1].has_key("shahash"):
				avatar = T.a(href = ("/avatars/%s"%item[1]["shahash"]))[
					T.img(border = 0, height = 25, src = ("/avatars/%s"%item[1]["shahash"]))
				]
			nickname = "-"
			if item[1].has_key("nickname"):
				nickname = item[1]["nickname"]
			else:
				if self.pytrans.sessions.has_key(username) and self.pytrans.sessions[username].ready:
					c = self.pytrans.sessions[username].contactList.getContact("%s@%s" % (item[0],config.jid))
					if c.nickname and c.nickname != "":
						nickname = c.nickname
			status = "-"
			if self.pytrans.sessions.has_key(username) and self.pytrans.sessions[username].ready:
				c = self.pytrans.sessions[username].contactList.getContact("%s@%s" % (item[0],config.jid))
				status = c.ptype
				if not status:
					status = c.show
					if not status:
						status = "available"
			row = T.tr(height=25)[
				T.td(height=25, align = "middle")[item[0]],
				T.td(height=25, align = "middle")[nickname],
				T.td(height=25, align = "middle")[network],
				T.td(height=25, align = "middle")[avatar],
				T.td(height=25, align = "middle")[status]
			]
			ret[row]
		return ret


# Status Node
class WebInterface_status(WebInterface_template):
	def render_content(self, ctx, data):
		request = inevow.IRequest(ctx)
		username = request.getUser()
		if config.admins.count(username) == 0:
			return loaders.htmlstr("""
<B>Access Restricted</B>
""")
		else:
			return loaders.htmlstr("""
<B>Transport Statistics</B>
<HR />
<SPAN nevow:render="statistics" />
<BR /><BR />
<B>Sessions</B>
<HR />
<SPAN nevow:render="sessions" />
""")

	def render_statistics(self, ctx, data):
		ret = T.table(border = 0,width = "100%",cellspacing=5,cellpadding=2)
		for key in self.pytrans.serviceplugins['Statistics'].stats:
			label = lang.get("statistics_%s" % key, config.lang)
			description = lang.get("statistics_%s_Desc" % key, config.lang)

			row = T.tr[
				T.th(align = "right")[label+":"],
				T.td[self.pytrans.serviceplugins['Statistics'].stats[key]],
				T.td[description]
			]
			ret[row]
		return ret

	def render_sessions(self, ctx, data):
		if len(self.pytrans.sessions) <= 0:
			return "No active sessions."

		ret = T.table(border = 0,width = "100%",cellspacing=5,cellpadding=2)
		row = T.tr[
			T.th["User"],
			T.th["Incoming Messages"],
			T.th["Outgoing Messages"],
			T.th["Connections"]
		]
		ret[row]
		for key in self.pytrans.sessions:
			jid = self.pytrans.sessions[key].jabberID
			row = T.tr[
				T.td[jid],
				T.td(align = "center")[self.pytrans.serviceplugins['Statistics'].sessionstats[jid]['IncomingMessages']],
				T.td(align = "center")[self.pytrans.serviceplugins['Statistics'].sessionstats[jid]['OutgoingMessages']],
				T.td(align = "center")[self.pytrans.serviceplugins['Statistics'].sessionstats[jid]['Connections']]
			]
			ret[row]
		return ret


# Configuration Node
class WebInterface_config(WebInterface_template):
	def render_content(self, ctx, data):
		request = inevow.IRequest(ctx)
		username = request.getUser()
		if config.admins.count(username) == 0:
			return loaders.htmlstr("""
<B>Access Restricted</B>
""")
		else:
			return loaders.htmlstr("""
<B>Configuration</B>
<HR />
<SPAN nevow:render="config" />
""")

	def render_config(self, ctx, data):
		table = T.table(border=0)
		for key in config.__dict__.keys():
			if key[0] == "_":
				continue
			if key.find("secret") >= 0:
				setting = "**hidden**"
			else:
				setting = config.__dict__[key]
			row = T.tr[T.td[key], T.td["="], T.td[setting]]
			table[row]
		return table


# Controls Node
class WebInterface_controls(WebInterface_template):
	def render_content(self, ctx, data):
		request = inevow.IRequest(ctx)
		username = request.getUser()
		if config.admins.count(username) == 0:
			return loaders.htmlstr("""
<B>Access Restricted</B>
""")
		else:
			return loaders.htmlstr("""
<B>Controls</B>
<HR />
<SPAN nevow:render="message" />
<SPAN nevow:render="controls" />
""")

	def render_message(self, ctx, data):
		request = inevow.IRequest(ctx)
		if request.args.get('shutdown'):
			return T.b["Server is now shut down.  Attempts to reload this page will fail."]
		return ""

	def render_controls(self, ctx, data):
		request = inevow.IRequest(ctx)
		if request.args.get('shutdown'):
			return ""
		return T.form(method="POST")[
			T.input(type="submit", name="shutdown", value="Shut Down")
		]
