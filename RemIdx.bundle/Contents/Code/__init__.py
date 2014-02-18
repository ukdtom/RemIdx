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

import urllib2
import urllib

VERSION = ' V0.0.0.2'
NAME = L('RemIdx')
PREFIX = '/agents/remidx'
PLUGIN_NAME = 'remidx'

#myURL = 'http://127.0.0.1:32400'


ART           = 'art-default.jpg'
ICON          = 'icon-default.png'


####################################################################################################
def Start():
	print("********  Started %s on %s  **********" %(NAME  + VERSION, Platform.OS))
	Log.Debug("*******  Started %s on %s  ***********" %(NAME  + VERSION, Platform.OS))
	Plugin.AddPrefixHandler(PREFIX, Update, PLUGIN_NAME, ICON, ART)


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
	myURL = 'http://' +  Prefs['This_PMS_IP'] + ':' + Prefs['This_PMS_Port']
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
		# Grap the Section ID
		MediaContainer = XML.ElementFromURL(myNewURL)
		mySectionID = MediaContainer.get('librarySectionID')
		# Grap Media Info	
		sections = XML.ElementFromURL(myNewURL).xpath('//Media')
		for section in sections:
			myAspectRatio = section.get('aspectRatio')
			Log.Debug('Media AspectRatio for %s is %s' %(mediaID, myAspectRatio))
		#Get streaming info
		sections = XML.ElementFromURL(myNewURL).xpath('//Part')
		for section in sections:
			mySURL =  section.get('key')
		RegIdx(mySURL, myMediaHash, myTitle, mediaID, mySectionID, myAspectRatio)


####################################################################################################
# ReqIdx will request an index from the remote indexer
####################################################################################################		
@route(PREFIX + '/ReqIdx')
def RegIdx(mySURL, myMediaHash, myTitle, mediaID, mySectionID, myAspectRatio):
	myURL = 'http://' + Prefs['Remote_Idx_IP'] + ':' + Prefs['Remote_Port']+'/?Stream=http://' + Prefs['This_PMS_IP'] + ':' + Prefs['This_PMS_Port'] + mySURL + '&AspectRatio=' + myAspectRatio + '&SectionID=' + mySectionID + '&mediaID=' + mediaID + '&Title=' + String.Quote(myTitle) + '&Hash=' + myMediaHash + '.bundle'
	print myURL
	print 'Sending request to remote PC'
	try:
		HTTP.Request(myURL, None, {'X-HTTP-Method-Override': 'QUEUE'}).content()
	except Exception:
		1
####################################################################################################
# Update function called from remote indexer, when a Bif file is ready
####################################################################################################		
@route(PREFIX + '/Update')
def Update():
	print 'Der opdateres'
	myURL = 'http://' + Prefs['Remote_Idx_IP'] + ':' + Prefs['Remote_Port'] + '/Out'
	try:
#		headers = {'X-HTTP-Method-Override': 'GETBIF'}
#		local_filename = '/root/ged.bif'

		request = urllib2.Request(myURL)
		request.add_header('X-HTTP-Method-Override', 'GETBIF')
		response = urllib2.urlopen(request)
		data = response.read()
		print data


#		response = urllib.request.urlopen(myURL)
#		html = response.read()
#		print html





#		data = {}
#		req = urllib2.Request(myURL, '',  headers)
#		response = urllib2.urlopen(req)
#		the_page = response.read()
#		print the_page

	except Exception:
		1
	


#local_filename, headers = urllib.request.urlretrieve('http://python.org/')
#html = open(local_filename)


#response = urllib.request.urlopen('http://python.org/')
#html = response.read()

####################################################################################################
# Validate preferences
####################################################################################################
def ValidatePrefs():
	return

  
  
