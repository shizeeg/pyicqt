# Copyright 2005-2006 Daniel Henninger <jadestorm@nc.rr.com>
# Licensed for distribution under the GPL version 2, check COPYING for details

import os

files=os.listdir("src/langs")
for i in range(len(files)):
	if files[i] == "__init__.py": continue
	if files[i].endswith(".py"):
		files[i] = files[i].replace(".py","")
		try:
			exec("from %s import *" % files[i])
		except UnicodeDecodeError:
			print "Unable to import language %s.\n" % files[i]
