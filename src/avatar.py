# Copyright 2005-2006 Daniel Henninger <jadestorm@nc.rr.com>
# Licensed for distribution under the GPL version 2, check COPYING for details

import config
from twisted.internet import reactor
from twisted.words.xish.domish import Element
from debug import LogEvent, INFO, WARN, ERROR
import lang
import sha
import base64
import os
import os.path
import imgmanip

SPOOL_UMASK = 0077

def parsePhotoEl(photo):
	""" Pass the photo element as an avatar, returns the avatar imageData """
	imageData = ""
	imageType = ""
	for e in photo.elements():
		if e.name == "BINVAL":
			imageData = base64.decodestring(e.__str__())
		elif e.name == "TYPE":
			imageType = e.__str__()
	
	if imageType != "image/png":
		imageData = imgmanip.convertToPNG(imageData)
	
	return imageData

def parseIQPhotoEl(photo):
	""" Pass the iq-based photo element as an avatar, returns the avatar imageData """
	imageType = photo.getAttribute("mimetype")
	imageData = base64.decodestring(photo.__str__())

	LogEvent(INFO)
	
	if imageType != "image/png":
		imageData = imgmanip.convertToPNG(imageData)
	
	return imageData



class Avatar:
	""" Represents an Avatar. Does not store the image in memory. """
	def __init__(self, imageData, avatarCache):
		self.__imageHash = sha.sha(imageData).hexdigest()
		self.__avatarCache = avatarCache

	def getImageHash(self):
		""" Returns the SHA1 hash of the avatar. """
		return self.__imageHash

	def getImageData(self):
		""" Returns this Avatar's imageData. This loads data from a file. """
		return self.__avatarCache.getAvatarData(self.__imageHash)
	
	def makePhotoElement(self):
		""" Returns an XML Element that can be put into the vCard. """
		photo = Element((None, "PHOTO"))
		type = photo.addElement("TYPE")
		type.addContent("image/png")
		binval = photo.addElement("BINVAL")
		binval.addContent(base64.encodestring(self.getImageData()).replace("\n", ""))
		return photo

	def makeDataElement(self):
		""" Returns an XML Element that can be put into a jabber:x:avatar IQ stanza. """
		data = Element((None, "data"))
		data["mimetype"] = "image/png"
		data.addContent(base64.encodestring(self.getImageData()).replace("\n", ""))
		return data
	
	def __eq__(self, other):
		return (other and self.__imageHash == other.__imageHash)


class AvatarCache:
	""" Manages avatars on disk. Avatars are stored according to their SHA1 hash.
	The layout is config.spooldir / config.jid / avatars / "first two characters of SHA1 hash" """

	def dir(self, key):
		""" Returns the full path to the directory that a 
		particular key is in. Creates that directory if it doesn't already exist. """
		X = os.path.sep
		d = os.path.abspath(config.spooldir) + X + config.jid + X + "avatars" + X + key[0:3] + X
		prev_umask = os.umask(SPOOL_UMASK)
		if not os.path.exists(d):
			os.makedirs(d)
		os.umask(prev_umask)
		return d
	
	def setAvatar(self, imageData):
		""" Writes an avatar to disk according to its key.
		Returns an Avatar object. """
		avatar = Avatar(imageData, self)
		key = avatar.getImageHash()
		LogEvent(INFO, msg="Setting avatar %r" % (key))
		prev_umask = os.umask(SPOOL_UMASK)
		try:
			f = open(self.dir(key) + key, 'wb')
			f.write(imageData)
			f.close()
		except IOError, e:
			LogEvent(WARN, msg="IOError writing to avatar %r - %r" % (key, str(e)))
		os.umask(prev_umask)
		return avatar
	
	def getAvatar(self, key):
		""" Loads the avatar with SHA1 hash of 'key' from disk and returns an Avatar object """
		imageData = self.getAvatarData(key)
		if imageData:
			return Avatar(imageData, self)

	def getAvatarData(self, key):
		""" Loads the avatar with SHA1 hash of 'key' from disk and returns the data """
		try:
			filename = self.dir(key) + key
			if os.path.isfile(filename):
				LogEvent(INFO, msg="Getting avatar %r" % (key))
				f = open(filename, 'rb')
				data = f.read()
				f.close()
				return data
			else:
				LogEvent(INFO, msg="Avatar not found %r" % (key))
		except IOError, e:
			LogEvent(INFO, msg="IOError reading avatar %r - %r" % (key, str(e)))
