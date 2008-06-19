# Copyright 2004-2006 Daniel Henninger <jadestorm@nc.rr.com>
# Licensed for distribution under the GPL version 2, check COPYING for details

import config
import os
import langs

def get(stringid, lang=config.lang):
	if not (lang.__class__ == str or lang.__class__ == unicode):
		lang = config.lang
	try:
		lang = lang.replace("-", "_")
		return langs.__dict__[lang].__dict__[stringid]
	except KeyError:
		try:
			return langs.__dict__[config.lang].__dict__[stringid]
		except KeyError:
			return langs.__dict__['en'].__dict__[stringid]
