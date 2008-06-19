# Copyright 2004-2006 Daniel Henninger <jadestorm@nc.rr.com>
# Licensed for distribution under the GPL version 2, check COPYING for details

import config

if not config.disableAvatars:
	try:
		import Image
		import StringIO

		def convertToPNG(imageData):
			inbuff = StringIO.StringIO(imageData)
			outbuff = StringIO.StringIO()
			Image.open(inbuff).save(outbuff, "PNG")
			outbuff.seek(0)
			imageData = outbuff.read()
			return imageData

		def convertToJPG(imageData):
			inbuff = StringIO.StringIO(imageData)
			outbuff = StringIO.StringIO()
			img = Image.open(inbuff)
			back = Image.new('RGB', img.size, 'white')
			img = Image.composite(img, back, img)
			if img.size[0] > 64 or img.size[1] > 64:
				img.thumbnail((64,64))
			elif img.size[0] < 15 or img.size[1] < 15:
				img.thumbnail((15,15))
			img.convert('RGB').save(outbuff, 'JPEG')
			outbuff.seek(0)
			imageData = outbuff.read()
			return imageData
	except ImportError:
		import sys
		print "ERROR! PyICQ-t requires the Python Imaging Library to function with avatars.  Either install the Python Imaging Library, or disable avatars using the <disableAvatars/> option in your config file."
		sys.exit(-1)
