import datetime, re, time, unicodedata, hashlib, urlparse, types, urllib
import shutil
import sys
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
#							CheckIdx(part, myMetaDataId, myTitle)
							print 'Tommy ged'

####################################################################################################
# GetMediaInfo will grap some info for a media, and decide if futher action is needed
####################################################################################################		
@route(PREFIX + '/GetMediaInfo')
def GetMediaInfo(mediaID, myTitle):
	Log.Debug('Checking media with an ID of : %s' %(mediaID)) 
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
			mySURL =  myURL + section.get('key')
		print 'Stream URL is: %s' %(mySURL)
		print 'Hash : ' + myMediaHash
		print 'Width : ' + myWidth
		print 'Height : ' + myHeight

####################################################################################################
# ReqIdx will request an index from the remote indexer
####################################################################################################		
@route(PREFIX + '/ReqIdx')
def ReqIdx(mediaID, myTitle):
	return


  
  
