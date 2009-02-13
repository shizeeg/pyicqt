# -*- coding: utf-8 -*-
# Licensed for distribution under the GPL version 2, check COPYING for details
import os.path

def get_git_head():
  """
    get hash of branch HEAD
  """
  head = ''
  try:
    if (os.path.exists('./.git/HEAD')): # HEAD info
      f_head = open('./.git/HEAD', 'r')
      line = f_head.readline()
      if ':' in line: # ref path
	arg, val = line.strip().split(': ')
	if arg == 'ref': # val is HEAD path
	  if (os.path.exists('./.git/info/refs')): # refs info
	    f_refs = open('./.git/info/refs', 'r')
	    for line in f_refs:
	      hash,ref = line.strip().split('\t')
	      if ref == val: # hash is HEAD commit hash
		parts = ref.split('/')
		if parts[1] == 'tags': # ref type is tag
		  head = parts[2] # tag name
		else: # usually if type is head
		  head = hash # hash value
	    f_refs.close()
      else: # pure hash
	head = line.strip() # get it
      f_head. close()
  except:
    pass
  return head
