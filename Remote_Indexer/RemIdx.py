#!/usr/bin/env python
#******************** Program Info **************************************
#
# This is the Remote Indexer workhorse of the RemIdx plug-in for Plex
# This must be running on a remote PC if possible, to
# avoid draining Plex Media Server for power
#
# Made by dane22, a Plex community member
# http://forums.plex.tv
#
# Code based on https://github.com/anachirino/bifserver, and she
# gracefully allowed me to steal it, and twist it into my needs
#
#***********************************************************************

# Search for TODO to find entry point for work in progress

VERSION = '0.0.1.4'

import logging
import io, json
import os
import sys
import shutil
import Queue
import threading
from urlparse import urlparse, parse_qs
import thread
import subprocess
import shlex
import time
import struct
import glob
import array
from SimpleHTTPServer import SimpleHTTPRequestHandler
from BaseHTTPServer import HTTPServer
import urllib2
import platform
import ConfigParser

# Initialize the Global vars used
PATH_TO_FFMPEG = ""
LOCAL_PORT = ""
FFMPEG_THREADS = ""
LOG_LEVEL = ""

# Enable or disable sending complete to server. Useful for devel.
SLAM = 1

# Loglevel for ffmpeg. Set empty string to load from config file. Valid values:
#	quiet:		Show nothing at all; be silent.
#	fatal:		Only show fatal errors. These are errors after which the process absolutely cannot continue after.
#	error:		Show all errors, including ones which can be recovered from.
#	warning:	Show all warnings and errors. Any message related to possibly incorrect or unexpected events will be shown.
#	info:		Show informative messages during processing. This is in addition to warnings and errors. This is the default value.
#	verbose:	Same as info, except more verbose.
#	debug:		Show everything, including debugging information.
FFMPEG_LOGLEVEL = "" 

# Set process to lowest priority
if sys.platform == 'win32':
	# Windows method
	import psutil
	pid = psutil.Process(os.getpid())
	pid.nice= psutil.IDLE_PRIORITY_CLASS
else:
	# Try the Linux/Mac method, keep on going if it fails.
	try: os.nice(19)
	except: pass

# Set window size. I do this mainly so when FFMPEG_LOGLEVEL is info or higher, it will display properly.
if sys.platform == 'win32':
	try:
		from ctypes import windll, byref, wintypes
		import time
		time.sleep(.5)
		width = 90
		height = 30
		buffer_height = 200
		hdl = windll.kernel32.GetStdHandle(-12)
#		os.system("mode con cols=" + str(width) + " lines=" + str(height)) # Kept here for reference
		rect = wintypes.SMALL_RECT(0, 50, 0+width-1, 50+height-1)  # (left, top, right, bottom)
		windll.kernel32.SetConsoleWindowInfo(hdl, True, byref(rect))
		time.sleep(.5) # Allow time for window size to change before changing buffer size.
		bufsize = wintypes._COORD(width, buffer_height) # columns, rows
		windll.kernel32.SetConsoleScreenBufferSize(hdl, bufsize)
		os.system("cls")
	# Don't panic if the above doesn't work.
	except: pass

#***********************************************************************
# Check FFMEGP location
#***********************************************************************
def CheckFFMPEG():
	if os.path.isfile(PATH_TO_FFMPEG):
		logging.debug('FFMPEG path validated as %s' %(PATH_TO_FFMPEG))
		return True
	else:
		print '***********************************************************************'
		print '*'
		print '*'
		print '*'
		print '*     ERROR!!!! Could not validate the path to the FFMPEG executable!!!'
		print '*     Check above message'
		print '*'
		print '*     Delete the file named RemIdx.ini to configure during next run'
		print '*'
		print '*     Quiting now!'
		print '*'
		print '*'
		print '***********************************************************************'
		logging.critical('FFMPEG not found at %s' %(PATH_TO_FFMPEG))
		return False

#***********************************************************************
# Shutdown Msg
#***********************************************************************
def ShutdownMsg(msg):
	print '***********************************************************************'
	print '* Currently working on item:'
	print '* ' + msg
	print '* Press <ENTER> to quit'
	print '***********************************************************************'

#***********************************************************************
# WebHandler
#***********************************************************************
class WebHandler(SimpleHTTPRequestHandler):
	def do_HEAD(self):
		self.get(False, 503)

	def do_GET(self):
		if self.headers.getheader('X-HTTP-Method-Override') == 'QUEUE':
			logging.debug('Got a Queue Req')
			self.get(False, 200)
		elif self.headers.getheader('X-HTTP-Method-Override') == 'GETBIF':
			logging.debug('Got a GetBif listing Req')
			SimpleHTTPRequestHandler.do_GET(self)
		elif self.headers.getheader('X-HTTP-Method-Override') == 'KILLOUT':
			logging.debug('Got a Kill Req')
			self.Kill_get(False, 200)
		else:
			if self.path.endswith(".bif"):
				logging.debug('Req to download bif file: ' + self.path)
				SimpleHTTPRequestHandler.do_GET(self)
			else:
				logging.critical('Got an invalid Req')
				self.get(True, 200)

	def Kill_get(self, include_body, queue_result):
		try:
			# We only hand requests for bif files..
			if urlparse(self.path).query.endswith(".bif"):
				dict = parse_qs(urlparse(self.path).query)
				self.sMyDir = os.path.realpath(os.path.dirname(sys.argv[0]))
				KillFile = os.path.join(self.sMyDir, 'Out', str(dict['KillIt'])[2:-2])
				logging.debug('About to remove file: ' + KillFile)
				os.remove(KillFile)
			else:
				logging.critical('Not a valid request')
				raise Exception('Not a valid request')
		except IOError:
			self.send_error(404, "Not Found")
			self.end_headers()
		except Exception as error:
			self.send_error(404, error.__str__())
			self.end_headers()
		finally:
			sys.stdout.flush()


	def get(self, include_body, queue_result):
		try:
			# We only hand requests for bif files..
			if urlparse(self.path).query.endswith(".bundle"):
				dict = parse_qs(urlparse(self.path).query)
				# Create Queue Entry
				self.sMyDir = os.path.realpath(os.path.dirname(sys.argv[0]))
				sQueueFile = os.path.join(self.sMyDir, 'Queue', str(dict['Hash'])[2:-2])
				sWorkFile = os.path.join(self.sMyDir, 'Work', str(dict['Hash'])[2:-2])
				if os.path.isfile(sWorkFile):
					#Already working on it
					logging.warning('The queue request recieved was already in progress')
					ShutdownMsg('The queue request recieved was already in progress')
				elif not os.path.isfile(sQueueFile):
					#Create an entry in the queue directory
					with io.open(sQueueFile, 'w', encoding='utf-8') as f:
						f.write(unicode(json.dumps(dict)))
			else:
				logging.critical('Not a valid request')
				raise Exception('Not a valid request')

		except IOError:
			self.send_error(404, "Not Found")
			self.end_headers()
		except Exception as error:
			self.send_error(404, error.__str__())
			self.end_headers()
		finally:
			sys.stdout.flush()

#***********************************************************************
# WebServer
#***********************************************************************
class WebServer(HTTPServer):
	def __init__(self):
		self.server_port = int(LOCAL_PORT)
		self.server_address = '0.0.0.0'
		self.HandlerClass = WebHandler
		self.server = HTTPServer((self.server_address, self.server_port), self.HandlerClass)
		print '* http deamon init okay'
		logging.debug('* http deamon init okay')

	def start(self):
		print '* Starting httpd deamon'	
		thread = threading.Thread(target = self.server.serve_forever)
		thread.deamon = True
		thread.start()
		sa = self.server.socket.getsockname()
		print "* Serving HTTP on", sa[0], "port", sa[1], "..."
		print '***********************************************************************'
		logging.debug('* Serving HTTP on %s port %s ....' %(sa[0],sa[1]))

	def stop(self):
		print 'Stopping httpd deamon.....Please wait'
		logging.info('Shutting down httpd deamon')
		self.server.shutdown()

#***********************************************************************
# Monitoring the Queue directory for work
#***********************************************************************
class BifQueue(threading.Thread):
	#Initialize the thread
	def __init__(self):
		threading.Thread.__init__(self)
		self.stopthread = threading.Event()
		logging.debug('BifQueue class initialized')
	#Running part
	def run(self):
		# Time between checking
		self.Interval = 5
		# Queue Directory
		self.myDir = os.path.realpath(os.path.dirname(sys.argv[0]))
		# Loop will continue until the stopthread event is set
		while not self.stopthread.isSet():
			myQList = glob.glob(os.path.join(self.myDir, 'Queue', '*.bundle'))
			if len(myQList) > 0:
				# Check if Work dir allready has an entry
				myWList = glob.glob(os.path.join(self.myDir, 'Work', '*.bundle'))
				if len(myWList) == 0:
					logging.debug('Need to move ' + myQList[0] + ' from Queue to Work')
					# Nothing to do, but work in queue
					sDestination = os.path.join(self.myDir, 'Work', os.path.basename(myQList[0]))
					# Move to work queue
					shutil.move(myQList[0],sDestination)
					GenJPGs(self.myDir)
			time.sleep(self.Interval)
	#Stop thread
	def stop(self):
		print 'Stopping BifQueue.....Please wait'
		logging.info('Shutting down BifQueue Thread')
		self.stopthread.set()

#***********************************************************************
# Generate the JPG files
#***********************************************************************
def GenJPGs(myDir):
	# Check if Work dir allready has an entry
	myWDir = os.path.join(myDir, 'Work', '*.bundle')
	myWList = glob.glob(myWDir)
	if len(myWList) > 0:
		#If tmp directory already existed, nuke it
		if os.path.exists(os.path.join(myDir, 'Tmp')):
			shutil.rmtree(os.path.join(myDir, 'Tmp'))
		#Create tmp directory
		os.makedirs(os.path.join(myDir, 'Tmp'))
		logging.debug('Started to work on bundle ' + myWList[0])
		try:
			#Extract needed info from work bundle json file
			with open(myWList[0]) as data_file:
				data = json.load(data_file)
				myHash = data["Hash"][0]
				logging.debug('Hash value is ' + myHash)
				myStream = data["Stream"][0]
				logging.debug('Stream URL is ' + myStream)
				myTitle = data["Title"][0]
				logging.debug('Title is ' + myTitle)
				mymediaID = data["mediaID"][0]
				logging.debug('MediaID is ' + mymediaID)
				mySectionID = data["SectionID"][0]
				logging.debug('Section ID is ' + mySectionID)
				try:
					myAspectRatio = data["AspectRatio"][0]
					logging.debug('myAspectRatio is ' + myAspectRatio)
				except:
					logging.debug('AspectRatio is missing')
					myAspectRatio = 'empty'
		except:
			# Bundlefile is invalid, so let's simply delete it
			logging.error('The bundle named %s was invalid, so deleting it' %(myWList[0]))
			os.remove(myWList[0])
			myTitle = '      ****** Idle, waiting for work ******'
			ShutdownMsg(myTitle)
			return

		#Tell my Master what's going on here
		print 'Starting to extract screenshots from %s' %myTitle
		print 'Close the window to terminate'
		# TODO start
		#Find the needed resolution for the jpg's
		if myAspectRatio > 1.5 :
			resolution = "240x136" # SD 16:9 ~ 1.7 ratio
		else :
			resolution = "240x180" # SD 4:3 ~ 1.3 ratio
		#Seems like Plex use this size regardless of media
		resolution = "320x136"
		# TODO end
		#Starting to grap screenshots	
		ffmpeg= [PATH_TO_FFMPEG, '-threads', FFMPEG_THREADS, '-loglevel', FFMPEG_LOGLEVEL, '-i', myStream, '-q', '3', '-s', resolution, '-r', '0.5', myDir + '/Tmp/%016d.jpg']
		if subprocess.call(ffmpeg):
			logging.critical('Could not extract images from video')
			raise Exception('Could not extract images from video')
			sys.exit(1)
		else:
			if MakeBIF(myDir, myHash, mymediaID, mySectionID, myStream):
				# Remove from work queue
				os.remove(myWList[0])
				slamPMS(myStream)
			else:
				logging.critical('MakeBif failed')
				print 'MakeBif failed !!!!!'
				sys.exit(1)
	else:
		myTitle = '      ****** Idle, waiting for work ******'
		ShutdownMsg(myTitle)	

#***********************************************************************
# Generate the bif file
#***********************************************************************
def MakeBIF(myDir, myHash, mymediaID, mySectionID, myStream):
	try:
		magic = [0x89,0x42,0x49,0x46,0x0d,0x0a,0x1a,0x0a]
		version = 0
		interval = 10
		myHash = os.path.splitext(myHash)[0]
		filename = os.path.join(myDir, 'Out', mymediaID + '-' + myHash + '.bif')
		#Create output directory
		if not os.path.exists(os.path.join(myDir, 'Out')):
			os.makedirs(os.path.join(myDir, 'Out'))
		files = os.listdir("%s" %(os.path.join(myDir, 'Tmp')))
		images = []
		for image in files:
			if image[-4:] == '.jpg':
				images.append(image)
		images.sort()
		images = images[1:]

		f = open(filename, "wb")
		array.array('B', magic).tofile(f)
		f.write(struct.pack("<I1", version))
		f.write(struct.pack("<I1", len(images)))
		f.write(struct.pack("<I1", 1000 * interval))
		array.array('B', [0x00 for x in xrange(20,64)]).tofile(f)

		bifTableSize = 8 + (8 * len(images))
		imageIndex = 64 + bifTableSize
		timestamp = 0

		# Get the length of each image
		for image in images:
			statinfo = os.stat("%s/%s" % (os.path.join(myDir, 'Tmp'), image))
			f.write(struct.pack("<I1", timestamp))
			f.write(struct.pack("<I1", imageIndex))

			timestamp += 1
			imageIndex += statinfo.st_size

		f.write(struct.pack("<I1", 0xffffffff))
		f.write(struct.pack("<I1", imageIndex))

		# Now copy the images
		for image in images:
			data = open("%s/%s" % (os.path.join(myDir, 'Tmp'), image), "rb").read()
			f.write(data)

		f.close()
		#Remove Tmp files
		shutil.rmtree(os.path.join(myDir, 'Tmp'))

		myTitle = '****** Idle, waiting for work ******'
		ShutdownMsg(myTitle)
		logging.debug('Bif file created for media hashed %s' %(myHash))
		return True
	except:
		logging.critical('Error in creating a bif for file with a hash of %s' %(myHash))
		return False

#***********************************************************************
# Show Banner
#***********************************************************************
def ShowBanner():
	print ''
	print ''
	print ''
	print ''
	print ''
	print ''
	print '***********************************************************************'
	print '* Welcome to the RemIdx Remote Indexer version ' + VERSION
	print '*'
	print '* Running on ' + platform.system()
	print '*'
	print '* Made by dane22, a Plex community member'
	print '*'
	print '* To reconfigure, either edit the file named RemIdx.ini, or delete it'
	print '*'
	print '***********************************************************************'
	print '* Path to ffmpeg is: ' + PATH_TO_FFMPEG
	print '***********************************************************************'

#***********************************************************************
# Logger
#***********************************************************************
def Logging():
	# Configure logging
	if LOG_LEVEL.upper() == 'NONE':
		logging.basicConfig(filename=None)
	else:		
		log_level = getattr(logging, LOG_LEVEL.upper(), None)		
		if not isinstance(log_level, int):
	    		raise ValueError('Invalid log level: %s' % log_level)
		logging.basicConfig(filename='RemIdx.log',level=log_level,format='%(asctime)s - %(levelname)s - %(funcName)s - %(lineno)d - %(message)s')

#***********************************************************************
# Slam PMS about a Bif-file is ready
#***********************************************************************
def slamPMS(myStream):
	#TODO: This one cause an error on the remote indexer!!!!
	# We sadly always ends up with the exception
	pos = myStream.find('/library/parts')
	PMSURL = myStream[:pos] + '/agents/remidx'
	print ('Slamming PMS @ : %s' %(PMSURL))
	logging.debug('Slamming PMS @ : %s' %(PMSURL))
	#Sending Slam
	request = urllib2.Request(PMSURL)
	try:
		if SLAM:
			response = urllib2.urlopen(request, timeout=60)
			response.close()
	except:
		print 'Slamming okay'
	# Tell my Master I'm falling asleep
	myTitle = '          ****** Idle, waiting for work ******'
	ShutdownMsg(myTitle)

#***********************************************************************
# conf function
#***********************************************************************
class conf():
	def __init__(self, sMyDir):
		if not os.path.isfile(os.path.join(sMyDir,'RemIdx.ini')):
			# No ini file, so let's create one
			with open(os.path.join(sMyDir,'RemIdx.ini'), 'wb') as configfile:
				self.Config = ConfigParser.ConfigParser()
				self.Config.read(os.path.join(sMyDir,'RemIdx.ini'))
				self.Config.add_section('Configuration')
				self.Config.add_section('RemIdx')
			self.SetConf(sMyDir)
		else:
			# Found an ini file			
			self.Config = ConfigParser.ConfigParser()
			self.Config.read(os.path.join(sMyDir,'RemIdx.ini'))
			try:
				if not self.Config.getboolean("Configuration", "IsSet"):
					self.SetConf(sMyDir)
				else:
					self.ReadConf()
			except:
				# During last configuration, my master aborted :-(
				with open(os.path.join(sMyDir,'RemIdx.ini'), 'wb') as configfile:
					self.Config = ConfigParser.ConfigParser()
					self.Config.read(os.path.join(sMyDir,'RemIdx.ini'))
					self.Config.add_section('Configuration')
					self.Config.add_section('RemIdx')
				self.SetConf(sMyDir)

	def ReadConf(self):
		# FFMPEG Path
		global PATH_TO_FFMPEG
		PATH_TO_FFMPEG = self.Config.get('RemIdx', 'PATH_TO_FFMPEG')
		# Port I'm listing to
		global LOCAL_PORT
		LOCAL_PORT = str(self.Config.getint('RemIdx', 'LOCAL_PORT'))
		global FFMPEG_THREADS
		FFMPEG_THREADS = str(self.Config.get('RemIdx', 'FFMPEG_THREADS'))
		global LOG_LEVEL
		LOG_LEVEL = self.Config.get('RemIdx', 'LOG_LEVEL')
		global FFMPEG_LOGLEVEL
		# If FFMPEG_LOGLEVEL is unset then load it from the config file.
		if FFMPEG_LOGLEVEL == '': FFMPEG_LOGLEVEL = self.Config.get('RemIdx', 'FFMPEG_LOGLEVEL')
		# If FFMPEG_LOGLEVEL is still unset then set a value.
		if FFMPEG_LOGLEVEL == '': FFMPEG_LOGLEVEL = 'quiet'


	def SetConf(self, sMyDir):
		print ''
		print ''
		print ''
		print ''
		print ''
		print ''
		print '***********************************************************************'
		print '* Welcome to the RemIdx Remote Indexer version ' + VERSION
		print '*'
		print '* Running on ' + platform.system()
		print '*'
		print '* Made by dane22, a Plex community member'
		print '*'
		print '* This application needs to be configured first' 
		global PATH_TO_FFMPEG
		while not os.path.isfile(PATH_TO_FFMPEG):
			print '*'
			print '* Please enter the full path to the FFMPEG executable, and press <ENTER>'
			PATH_TO_FFMPEG = raw_input('ffmpeg path: ')
		self.Config.set('RemIdx', 'PATH_TO_FFMPEG', PATH_TO_FFMPEG)
		print '*'
		print '* Thanks.....'
		global LOCAL_PORT
		while not ((LOCAL_PORT>32400) and (LOCAL_PORT<32501)):
			print '*'
			print '* Now please enter the port number this application shall be listnening on'
			print '* Remember to open your firewall for this port, and I recommend port 32405'
			print '* Valid range is 32401 to 32500'
			LOCAL_PORT = raw_input('Remote Indexer Port [32405]: ')
			# Allow user to set default by just pressing enter.
			if LOCAL_PORT == '': LOCAL_PORT = 32405
			LOCAL_PORT = int(LOCAL_PORT)
		LOCAL_PORT = str(LOCAL_PORT)
		self.Config.set('RemIdx', 'LOCAL_PORT', LOCAL_PORT)
		print '*'
		print '* Thanks.....'
		VALID_FFMPEG_THREADS = ('auto', '1', '2', '3', '4', '5', '6', '7', '8')
		global FFMPEG_THREADS
		while not (FFMPEG_THREADS in VALID_FFMPEG_THREADS):
			print '*'
			print '* Now please enter the amount of CPU cores to use (type auto to use all cores)'
			print '* If this is a dedicated Indexer, I recommend you type auto'
			print '* Valid options are ' + str(VALID_FFMPEG_THREADS)[1:-1]
			FFMPEG_THREADS = raw_input('Number of cores [auto]: ')
			# Allow user to set default by just pressing enter.
			if FFMPEG_THREADS == '': FFMPEG_THREADS = 'auto'
		self.Config.set('RemIdx', 'FFMPEG_THREADS', FFMPEG_THREADS)
		print '*'
		print '* Thanks.....'
		global LOG_LEVEL
		VALID_LOG_LEVEL = ('none', 'debug', 'info', 'warning', 'error', 'critical')
		while not (LOG_LEVEL in VALID_LOG_LEVEL):
			print '*'
			print '* Now please enter the log level to use'
			print '* Valid levels are ' + str(VALID_LOG_LEVEL)[1:-1]
			LOG_LEVEL = raw_input('Log Level [info]: ')
			# Allow user to set default by just pressing enter.
			if LOG_LEVEL == '': LOG_LEVEL = 'info'
		self.Config.set('RemIdx', 'LOG_LEVEL', LOG_LEVEL)
		self.Config.set('RemIdx', 'FFMPEG_LOGLEVEL', 'quiet')

		# Writing our configuration file to 'RemIdx.ini'
		self.Config.set('Configuration', 'isset', True)
		with open(os.path.join(sMyDir,'RemIdx.ini'), 'wb') as configfile:
			self.Config.write(configfile)

#***********************************************************************
# Main function
#***********************************************************************
def main():
	# Directory I live in
	sMyDir = os.path.realpath(os.path.dirname(sys.argv[0]))
	conf(sMyDir)
	# Configure logging
	Logging()
	logging.info('***********************************************************************')
	logging.info('Starting RemIdx Indexer version %s on %s' %(VERSION, platform.system()))
	# Show banner
	ShowBanner()
	# Check for correct FFMPEG Path
	if not CheckFFMPEG():
		print 'Quitting'
		logging.info('Quitting RemIdx Indexer')
		sys.exit(1)
	logging.debug('Starting from directory named : ' + sMyDir)
	# Create Queue and Work Directory
	myQDir = os.path.join(sMyDir,'Queue')
	if not os.path.exists(myQDir):
		os.makedirs(myQDir)
	myWDir = os.path.join(sMyDir,'Work')
	if not os.path.exists(myWDir):
		os.makedirs(myWDir)
	# Start WebServer
	myWeb = WebServer()
	myWeb.start()
	# Start Queue monitoring
	myQueue = BifQueue()
	myQueue.deamon = True
	myQueue.start()
	# Check if some work is already waiting for us to pick up
	GenJPGs(sMyDir)
	#Wait for my Master is pressing <ENTER>
	raw_input('')	
	myQueue.stop()
	myWeb.stop()
	logging.info('Quitting RemIdx Indexer')
	print 'Quitting.....Please wait'
	sys.exit(0)

if __name__ == '__main__':
	main()

