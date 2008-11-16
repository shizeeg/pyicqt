# Copyright 2005-2006 Daniel Henninger <jadestorm@nc.rr.com>
# Licensed for distribution under the GPL version 2, check COPYING for details

import os

files=os.listdir("src/langs")
for file in files:
	if file == "__init__.py": continue
	if file.endswith(".py"):
		file = file.replace(".py","")
		try:
			exec("from %s import *" % file)
		except UnicodeDecodeError:
			print "Unable to import language %s.\n" % file
