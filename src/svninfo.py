# Copyrigh 2004-2006 Daniel Henninger <jadestorm@nc.rr.com>
# Licensed for distribution under the GPL version 2, check COPYING for details

from utils import parseFile
import os, os.path

class SVNVersion:
	def __init__(self):
		self.version = 0

	def calcRevision(self, svndir):
		entriesFile = os.path.join(svndir, "entries")
		doc = parseFile(entriesFile)
		for child in doc.elements():
			try:
				num = int(child.getAttribute("committed-rev"))
				self.version = max(num, self.version)
			except TypeError:
				pass

	def traverseDir(self, dirname):
		for file in os.listdir(dirname):
			if os.path.islink(file):
				continue
			if os.path.isdir(file):
				path = os.path.join(dirname, file)
				if file == ".svn":
					self.calcRevision(path)
				else:
					self.traverseDir(path)

def getSVNVersion(dirname="."):
	x = SVNVersion()
	x.traverseDir(dirname)
	return x.version

if __name__ == "__main__":
	print getSVNVersion()

