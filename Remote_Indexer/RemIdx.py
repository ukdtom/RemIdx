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

#***********************************************************************
# CUSTOMIZE BELOW!
#***********************************************************************
# Value must be the full path to ffmpeg executable
#
# Like on my OpenSuse box, it's /usr/bin/ffmpeg
#
PATH_TO_FFMPEG = "/usr/bin/ffmpeg"
#
# This is the port that our webserver listens to, and you must make sure, that it's
# allowed in your firewall, as well as configured in the RemIdx agent on your PMS
#
LOCAL_PORT = "32405"
#
# This is the amout of CPU cores that will be used during FFMPEG Screenshot capture
# As a default, FFMPEG will use all availible CPU power
# If you have like a 4 core  CPU, you might want to set the limit to 3, leaving one core for you
# In below, auto means default, aka. use all CPU
# Valid values are: 'auto', '1', '2',... and so on
FFMPEG_THREADS = '3'

# LOG_LEVEL can be none, debug, info, warning, error and critical
# Switch to debug when doing troubleshooting
LOG_LEVEL = 'debug'
#***********************************************************************
# CUSTOMIZE END!
#***********************************************************************

# Search for TODO to find entry point

VERSION = '0.0.0.7'

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
		#Tell my Master what's going on here
		print 'Starting to extract screenshots from %s' %myTitle
		print 'Close the window to terminate'
		#Find the needed resolution for the jpg's
		if myAspectRatio > 1.5 :
			resolution = "240x136" # SD 16:9 ~ 1.7 ratio
		else :
			resolution = "240x180" # SD 4:3 ~ 1.3 ratio
		# TODO start
		#Seems like Plex use this size regardless of media
		resolution = "320x136"
		# TODO end
		#Starting to grap screenshots	
	    	ffmpeg= [PATH_TO_FFMPEG, '-threads', FFMPEG_THREADS, '-loglevel', 'quiet', '-i', myStream, '-q', '3', '-s', resolution, '-r', '0.5', myDir + '/Tmp/%016d.jpg']
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
		myTitle = '****** Idle, waiting for work ******'
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
	print '* If you have not yet customized me, you need to do so now!'
	print '* Press <ENTER>, and edit lines 23 and 28 before starting me again'
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
	#We sadly always ends up with the exception
	pos = myStream.find('/library/parts')
	PMSURL = myStream[:pos] + '/agents/remidx'
	print ('Slamming PMS @ : %s' %(PMSURL))
	logging.debug('Slamming PMS @ : %s' %(PMSURL))
	#Sending Slam
	request = urllib2.Request(PMSURL)
	try:
		response = urllib2.urlopen(request, timeout=60)
		response.close()
	except:
		print 'Slamming okay'
	# Tell my Master I'm falling asleep
	myTitle = '****** Idle, waiting for work ******'
	ShutdownMsg(myTitle)

#***********************************************************************
# Main function
#***********************************************************************
def main():
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
	# Directory I live in
	sMyDir = os.path.realpath(os.path.dirname(sys.argv[0]))
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
#	print 'Press <ENTER> to quit'
	raw_input('')	
	myQueue.stop()
	myWeb.stop()
	logging.info('Quitting RemIdx Indexer')
	print 'Quitting.....Please wait'
	sys.exit(0)

if __name__ == '__main__':
	main()

