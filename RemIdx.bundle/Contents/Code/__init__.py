#import datetime
#import re
#import time
#import unicodedata
#import hashlib 

#import urlparse
#import types 
#import urllib
#import shutil
#import sys
import os
#import inspect

VERSION = ' V0.0.0.1'
NAME = L('RemIdx')
PREFIX = '/metadata/remidx'

myURL = 'http://127.0.0.1:32400'

####################################################################################################
def Start():
	print("********  Started %s on %s  **********" %(NAME  + VERSION, Platform.OS))
	Log.Debug("*******  Started %s on %s  ***********" %(NAME  + VERSION, Platform.OS))

####################################################################################################
# Movie agent
####################################################################################################		
class RemIdxMediaMovie(Agent.Movies):
	name = NAME + ' (Movies)'
	languages = [Locale.Language.NoLanguage]
	primary_provider = False
	contributes_to = ['com.plexapp.agents.imdb', 'com.plexapp.agents.themoviedb', 'com.plexapp.agents.none']
  	# Satisfy the framework here
	def search(self, results, media, lang):
		results.Append(MetadataSearchResult(id='null', score = 100))
    
	def update(self, metadata, media, lang, force):
		# Grap the id, so we can check for an existing index
		myMetaDataId = media.id
		# Grap the title, for use in logging
		myTitle = media.title

		GetMediaInfo(media.id, media.title)


####################################################################################################
# TV Show agent
####################################################################################################		
class RemIdxMediaTV(Agent.TV_Shows):
	name = NAME + ' (TV)'
	languages = [Locale.Language.NoLanguage]
	primary_provider = False
	contributes_to = ['com.plexapp.agents.thetvdb', 'com.plexapp.agents.none']
  	# Satisfy the framework here
	def search(self, results, media, lang):
		results.Append(MetadataSearchResult(id='null', score = 100))

	def update(self, metadata, media, lang, force):
		for s in media.seasons:
			if int(s) < 1900:
				for e in media.seasons[s].episodes:
					for i in media.seasons[s].episodes[e].items:
						for part in i.parts:
							print 'Tommy Missing TV part'

####################################################################################################
# GetMediaInfo will grap some info for a media, and decide if futher action is needed
####################################################################################################		
@route(PREFIX + '/GetMediaInfo')
def GetMediaInfo(mediaID, myTitle):
	Log.Debug('Checking media with an ID of : %s, and a title of : %s' %(mediaID, myTitle)) 
	#Get the hash
	myNewURL = myURL + '/library/metadata/' + mediaID + '/tree'
	sections = XML.ElementFromURL(myNewURL).xpath('//MediaPart')
	for section in sections:
		myMediaHash = section.get('hash')
		Log.Debug('The hash for media %s is %s' %(mediaID, myMediaHash))
	# Does an index already exists?
	myIdxFile = Core.app_support_path + '/Media/localhost/' + myMediaHash[:1] + '/' + myMediaHash[1:] + '.bundle/Contents/Indexes/index-sd.bif'
	if os.path.isfile(myIdxFile):
		Log.Debug('Index exists for : %s with ID: %s, so skipping' %(myTitle, mediaID))
		print 'Index exists for : %s with ID: %s, so skipping' %(myTitle, mediaID)
	else:
		Log.Debug('Index is missing for : %s with ID: %s' %(myTitle, mediaID)) 
		print 'Index is missing for : %s with ID: %s' %(myTitle, mediaID)
		#Get media info
		myNewURL = myURL + '/library/metadata/' + mediaID	
		sections = XML.ElementFromURL(myNewURL).xpath('//Media')
		for section in sections:
			myWidth = section.get('width')
			Log.Debug('Media witdh for %s is %s' %(mediaID, myWidth))
			myHeight = section.get('height')
			Log.Debug('Media height for %s is %s' %(mediaID, myHeight))
		#Get streaming info
		sections = XML.ElementFromURL(myNewURL).xpath('//Part')
		for section in sections:
			mySURL =  section.get('key')
		RegIdx(mySURL, myMediaHash, myWidth, myHeight)


####################################################################################################
# ReqIdx will request an index from the remote indexer
####################################################################################################		
@route(PREFIX + '/ReqIdx')
def RegIdx(mySURL, myMediaHash, myWidth, myHeight):
	myURL = 'http://' + Prefs['Remote_Idx_IP'] + ':' + Prefs['Remote_Port']+'/index?hash=' + myMediaHash + '&Stream=http://' + Prefs['This_PMS_IP'] + ':' + Prefs['This_PMS_Port'] + mySURL + '&Height=' + myHeight + '&Width=' + myWidth
	print myURL
	print 'Tommy Need to send request to remote PC'

####################################################################################################
# Validate preferences
####################################################################################################
def ValidatePrefs():
	return

  
  
