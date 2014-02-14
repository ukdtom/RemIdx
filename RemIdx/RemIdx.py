#!/usr/bin/env python
#***********************************************************************
#
# This is the workhorse of the RemIdx plug-in for Plex
# This must be running on a remote PC if possible, to
# avoid draining Plex for powers
#
# Made by dane22, a Plex community member
# forums.plex.tv
#
# Code based on https://github.com/anachirino/bifserver, and she
# gracefully allowed be to steal it, and twist it into my needs
#
#***********************************************************************

#***********************************************************************
# CUSTOMIZE BELOW!
#***********************************************************************
# Value must be the full path to ffmpeg executable
PATH_TO_FFMPEG = "/usr/bin/ffmpeg"
# This is the port that our webserer listens to, and you must make sure, that it's
# allowed in your firewall, as well as configured in the RemIdx agent on your PMS
LOCAL_PORT = "32405"
#***********************************************************************
# CUSTOMIZE END!
#***********************************************************************



import io, json
import os
import sys
import shutil
import BaseHTTPServer
import SimpleHTTPServer
import Queue
import threading
from urlparse import urlparse, parse_qs
import thread
import time
import glob

#import traceback
#import re
#import urllib
#import struct
#import subprocess
#import ctypes

devnull=open(os.devnull)
BifQueue = Queue.LifoQueue()

#***********************************************************************
# Monitoring the Queue directory for work
#***********************************************************************
class BifQueue(threading.Thread):
	#Initialize the thread
	def __init__(self):
		threading.Thread.__init__(self)
		self.stopthread = threading.Event()
	#Running part
	def run(self):
		# Time between checking
		self.Interval = 5
		# Queue Directory
		self.myDir = os.path.realpath(os.path.dirname(sys.argv[0]))
		# Loop will continue until the stopthread event is set
		while not self.stopthread.isSet():
			myQList = glob.glob(self.myDir + '/Queue/*.bundle')
			if len(myQList) > 0:
				# Check if Work dir allready has an entry
				myWList = glob.glob(self.myDir + '/Work/*.bundle')
				if len(myWList) == 0:
					# Nothing to do, but work in queue
					sDestination = self.myDir + '/Work/' + os.path.basename(myQList[0])
					# Move to work queue
					shutil.move(myQList[0],sDestination)
					print 'Ingen arbejde: ' + sDestination



				print myQList[0]
			time.sleep(self.Interval)
	#Stop thread
	def stop(self):
		print 'Stopping BifQueue.....Please wait'
		self.stopthread.set()

#***********************************************************************
# Handle http requests
#***********************************************************************
class RequestHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):
	def do_HEAD(self):
		self.get(False, 503)

	def do_GET(self):
		if self.headers.getheader('X-HTTP-Method-Override') == 'QUEUE':
			self.get(False, 200)
		else:
			self.get(True, 503)
			print '503'

	def get(self, include_body, queue_result):
		try:
			# We only hand requests for bif files..
			if urlparse(self.path).query.endswith(".bundle"):
				print 'Got a valid Req'
				dict = parse_qs(urlparse(self.path).query)
				# Create Queue Entry
				self.sMyDir = os.path.realpath(os.path.dirname(sys.argv[0]))
				sQueueFile = self.sMyDir + '/Queue/' + str(dict['Hash'])[2:-2]
				sWorkFile = self.sMyDir + '/Work/' + str(dict['Hash'])[2:-2]
				if not os.path.isfile(sWorkFile):
					#Already working on it
					print 'Already working on it'
				elif not os.path.isfile(sQueueFile):
					#Create an entry in the queue directory
					with io.open(sQueueFile, 'w', encoding='utf-8') as f:
						f.write(unicode(json.dumps([{'name' : k, 'value' : v} for k,v in dict.items()], indent=4)))
			else:
				raise Exception("Not a bif request")




		except IOError:
			self.send_error(404, "Not Found")
			self.end_headers()
		except Exception as error:
			self.send_error(404, error.__str__())
			self.end_headers()
		finally:
#			if bif_file != None:
#				bif_file.close()
			sys.stdout.flush()

#***********************************************************************
# HTTP server
#***********************************************************************
class httpServ(BaseHTTPServer.HTTPServer):

	def server_bind(self):
		BaseHTTPServer.HTTPServer.server_bind(self)
		self.socket.settimeout(1)
		self.run = True

	def get_request(self):
		while self.run:
			try:
				sock, addr = self.socket.accept()
				sock.settimeout(None)
				return (sock, addr)
			except socket.timeout:
				pass

	def stop(self):
		print 'Stopping HTTP Server....Please wait'
		self.run = False

	def serve(self):
		while self.run:
			self.handle_request()

#***********************************************************************
# Main function
#***********************************************************************
def main():
	print ''
	print ''
	print ''
	print ''
	print ''
	print ''
	print '***********************************************************'
	print '* Welcome to the RemIdx WorkHorse'
	print '* If you have not yet customized me, you need to do so now!'
	print '* Press enter, and edit lines 20 and 23 before starting me again'
	print '***********************************************************'
	print '* Path to ffmpeg is: ' + PATH_TO_FFMPEG

	# Directory I live in
	sMyDir = os.path.realpath(os.path.dirname(sys.argv[0]))
	# Create Queue and Work Directory
	if not os.path.exists(sMyDir + '/Queue'):
		os.makedirs(sMyDir + '/Queue')
	if not os.path.exists(sMyDir + '/Work'):
		os.makedirs(sMyDir + '/Work')
	
	# Start the http server
	server = httpServ(("0.0.0.0", int(LOCAL_PORT)), RequestHandler)
	sa = server.socket.getsockname()
	print "* Serving HTTP on", sa[0], "port", sa[1], "..."
	thread.start_new_thread(server.serve, ())

	# Process the bif queue in the background so we don't hang the http requests.
	myQueue = BifQueue()
	myQueue.deamon = True
	myQueue.start()
	print '***********************************************************'
	raw_input("* Press <RETURN> to stop server\n")
	print '***********************************************************'		
	myQueue.stop()
	server.stop()

if __name__ == '__main__':
	main()

