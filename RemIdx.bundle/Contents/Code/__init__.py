import re
import os
from lxml import etree
import urllib2
import urllib

VERSION = ' V0.0.1.0'
NAME = L('RemIdx')
PREFIX = '/agents/remidx'
PLUGIN_NAME = 'remidx'
ART           = 'art-default.jpg'
ICON          = 'icon-default.png'
AGENTNAME = 'com.plexapp.agents.remidx'

####################################################################################################
def Start():
	print("********  Started %s on %s  **********" %(NAME  + VERSION, Platform.OS))
	Log.Debug("*******  Started %s on %s  ***********" %(NAME  + VERSION, Platform.OS))
	# Allow callback from remote indexer
	Plugin.AddPrefixHandler(PREFIX, Update, PLUGIN_NAME, ICON, ART)
	# Switch of auto indexing of libraries, sadly, framework only supports GET, so need to use urllib2
	opener = urllib2.build_opener(urllib2.HTTPHandler)
	request = urllib2.Request('http://127.0.0.1:32400/:/prefs?GenerateIndexFilesDuringAnalysis=0')
	request.get_method = lambda: 'PUT'
	url = opener.open(request)

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
		#Start to work
		GetMediaInfoMovie(media.id, media.title)



####################################################################################################
# TV Show agent
####################################################################################################		
class RemIdxMediaTV(Agent.TV_Shows):
	name = NAME + ' (TV)'
	contributes_to = ['com.plexapp.agents.thetvdb', 'com.plexapp.agents.none']
	primary_provider = False
	contributes_to = ['com.plexapp.agents.none']
  	# Satisfy the framework here
	def search(self, results, media, lang):
		results.Append(MetadataSearchResult(id='null', score = 100))

	def update(self, metadata, media, lang, force):
		GetMediaInfoTV(media.id, media.title)


####################################################################################################
# GetMediaInfo will grap some info for a movie media, and decide if futher action is needed
####################################################################################################		
@route(PREFIX + '/GetMediaInfoMovie')
def GetMediaInfoMovie(mediaID, myTitle):
	Log.Debug('Checking Movie media with an ID of : %s, and a title of : %s' %(mediaID, myTitle)) 
	myURL = 'http://' +  Prefs['This_PMS_IP'] + ':' + Prefs['This_PMS_Port']
	#Get the hash
	myNewURL = myURL + '/library/metadata/' + mediaID + '/tree'
	sections = XML.ElementFromURL(myNewURL).xpath('//MediaPart')
	for section in sections:
		myMediaHash = section.get('hash')
		Log.Debug('The hash for media %s is %s' %(mediaID, myMediaHash))
		# Does an index already exists?
		myIdxFile = os.path.join(Core.app_support_path, 'Media', 'localhost', myMediaHash[:1], myMediaHash[1:] + '.bundle', 'Contents', 'Indexes', 'index-sd.bif')
		Log.Debug('myIdxFile is : ' + myIdxFile)
		if os.path.isfile(myIdxFile):
			Log.Debug('Index exists for : %s with ID: %s, so skipping' %(myTitle, mediaID))
		else:
			Log.Debug('Index is missing for : %s with ID: %s' %(myTitle, mediaID))
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
# GetMediaInfo will grap some info for a TV-Show media, and decide if futher action is needed
####################################################################################################		
@route(PREFIX + '/GetMediaInfoTV')
def GetMediaInfoTV(mediaID, myTitle):
	Log.Debug('Checking TV media with an ID of : %s, and a title of : %s' %(mediaID, myTitle)) 
	myURL = 'http://' +  Prefs['This_PMS_IP'] + ':' + Prefs['This_PMS_Port']

	#Get mySectionID info
	myNewURL = myURL + '/library/metadata/' + mediaID
	MediaContainer = XML.ElementFromURL(myNewURL)
	mySectionID = MediaContainer.get('librarySectionID')
	Log.Debug('mySectionID is %s' %(mySectionID))

	# Get all children from this show
	myNewURL = myNewURL + '/allLeaves'
	Log.Debug('Inspecting URL: %s' %(myNewURL))
	episodes = XML.ElementFromURL(myNewURL).xpath('//Video')
	#Walk each episode
	for episode in episodes:
		myEpisodeTitle = myTitle + ' - ' + episode.get('title')
		Log.Debug('Complete title is %s' %(myEpisodeTitle))		
		mySURL = str(episode.xpath('Media/Part/@key'))[2:-2]
		Log.Debug('Episode stream url is %s' %(mySURL))
		myAspectRatio = str(episode.xpath('Media/@aspectRatio'))[2:-2]
		Log.Debug('AspectRatio is %s' %(myAspectRatio))
		#Get episode tree
		myKey = episode.get('ratingKey')
		myNewURL = myURL + '/library/metadata/' + myKey + '/tree'
		Log.Debug('Tree URL is : %s' %(myNewURL))
		myTree = XML.ElementFromURL(myNewURL).xpath('//MediaPart')
		for section in myTree:
			myMediaHash = section.get('hash')
			Log.Debug('The hash for media %s is %s' %(myKey, myMediaHash))
		# Does an index already exists?
		myIdxFile = os.path.join(Core.app_support_path, 'Media', 'localhost', myMediaHash[:1], myMediaHash[1:] + '.bundle', 'Contents', 'Indexes', 'index-sd.bif')
		Log.Debug('myIdxFile is : ' + myIdxFile)
		if os.path.isfile(myIdxFile):
			Log.Debug('Index exists for : %s with ID: %s, so skipping' %(myEpisodeTitle, myKey))
		else:
			Log.Debug('Index is missing for : %s with ID: %s' %(myEpisodeTitle, myKey))
			RegIdx(mySURL, myMediaHash, myEpisodeTitle, myKey, mySectionID, myAspectRatio)


####################################################################################################
# ReqIdx will request an index from the remote indexer
####################################################################################################		
@route(PREFIX + '/ReqIdx')
def RegIdx(mySURL, myMediaHash, myTitle, mediaID, mySectionID, myAspectRatio):
	myURL = 'http://' + Prefs['Remote_Idx_IP'] + ':' + Prefs['Remote_Port']+'/?Stream=http://' + Prefs['This_PMS_IP'] + ':' + Prefs['This_PMS_Port'] + mySURL + '&AspectRatio=' + myAspectRatio + '&SectionID=' + mySectionID + '&mediaID=' + mediaID + '&Title=' + String.Quote(myTitle) + '&Hash=' + myMediaHash + '.bundle'
	print 'RemIdx is sending a request to remote Indexer for %s' %(mediaID)
	try:
		HTTP.Request(myURL, None, {'X-HTTP-Method-Override': 'QUEUE'}).content()
	except Exception:
		1
####################################################################################################
# Update function called from remote indexer, when a Bif file is ready
####################################################################################################		
@route(PREFIX + '/Update')
def Update():
	myURL = 'http://' + Prefs['Remote_Idx_IP'] + ':' + Prefs['Remote_Port'] + '/Out'
	try:
		#Create a tmp storage directory in the Plug-In Support directory
		if not os.path.exists('Queue'):
			os.makedirs('Queue')

		request = urllib2.Request(myURL)
		# Set header so we can get access to directory listing of /Out on remote indexer
		request.add_header('X-HTTP-Method-Override', 'GETBIF')
		response = urllib2.urlopen(request)
		data = response.read()
		response.close()
		#TODO: Change this into XML		
		#Find string of bif files
		pos = data.find('<ul>') + 4
		pos2 = data.find('</ul>')
		data = data[pos:pos2]
		#Convert to list
		data3 = data.splitlines()
		#Skip first blank line
		data3.pop(0)
		for bif in data3:
			pos = bif.find('href="') + 6
			pos2 = bif.find('">')
			bif = bif[pos:pos2]
			Log.Debug('Got this file from the Remote Indexer: %s' %(bif))
			# Get the Media ID
			pos = bif.find('-')
			myMediaID = bif[:pos]
			Log.Debug('Media ID is : %s' %(myMediaID))
			sTargetDir = os.path.join(Core.app_support_path, 'Media', 'localhost', bif[pos+1:pos+2], os.path.splitext(bif[pos+2:])[0] + '.bundle', 'Contents', 'Indexes')
			Log.Debug('Target Directory is : %s' %(sTargetDir))
			# Create target dir if it doesn't exists
			if not os.path.exists(sTargetDir):
				os.makedirs(sTargetDir)
			myBifURL = myURL + '/' + bif
			Log.Debug('Download URL is %s' %(myBifURL))					
			#TODO: Need to check, if below was a success, before continue
			urllib.urlretrieve(myBifURL, sTargetDir + '/index-sd.bif')
			Add2Db(myMediaID)
			KillOnRemote(bif)

	except Exception:
		1
####################################################################################################
# This will add the newly placed index to the database
####################################################################################################
def Add2Db(myMediaID):
	opener = urllib2.build_opener(urllib2.HTTPHandler)
	#Enable Index Generation
	request = urllib2.Request('http://127.0.0.1:32400/:/prefs?GenerateIndexFilesDuringAnalysis=1')
	request.get_method = lambda: 'PUT'
	url = opener.open(request)
	#Analyze media
	request = urllib2.Request('http://127.0.0.1:32400/library/metadata/' + myMediaID + '/analyze')
	request.get_method = lambda: 'PUT'
	url = opener.open(request)
	#Disable Indexing
	request = urllib2.Request('http://127.0.0.1:32400/:/prefs?GenerateIndexFilesDuringAnalysis=0')
	request.get_method = lambda: 'PUT'
	url = opener.open(request)


####################################################################################################
# This will remove the entry from the remote indexers /Out directory
####################################################################################################
def KillOnRemote(bif):
	myURL = 'http://' + Prefs['Remote_Idx_IP'] + ':' + Prefs['Remote_Port']+'/?KillIt=' + bif
	try:
		HTTP.Request(myURL, None, {'X-HTTP-Method-Override': 'KILLOUT'}).content()
	except Exception:
		1

####################################################################################################
# Validate preferences
####################################################################################################
def ValidatePrefs():
	return

  
  
