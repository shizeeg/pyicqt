# Copyright 2005-2006 Daniel Henninger <jadestorm@nc.rr.com>
# Licensed for distribution under the GPL version 2, check COPYING for details

import os
from debug import LogEvent, INFO, WARN, ERROR
from config import xdbDriver

try:
	exec("from %s import XDB, housekeep" % xdbDriver)
	LogEvent(INFO, msg="Using XDB driver %s" % xdbDriver, skipargs=True)
except:
	print("No valid XDB driver specified, exiting...")
	raise
	os._exit(-1)
