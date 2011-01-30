#!/usr/bin/env python

import locale
import datetime
import time
import smtplib
import sys
import getopt
import urllib
import urllib2
import re

import ConfigParser
from BeautifulSoup import BeautifulSoup

class UnableToNotify (Exception):
	pass
class TrainTrain (object):
	"""Utilizzo: traintrain treno stazione minuti"""

	BASEURL = "http://mobile.viaggiatreno.it/viaggiatreno/mobile/scheda"
	USERAGENT = "Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; rv:1.8) Gecko/20051111 Firefox/1.5"

	def __init__(self, configuration=None):
		if configuration == None:
			configuration = ".traintraincfg"
		self.config = ConfigParser.ConfigParser()
		try:
			self.config.read(configuration)
		except IOError:
		    print "Errore nella lettura del file"
		    sys.exit(-1)

	def usage():
	    print "Usage: ....."
	    sys.exit(-1)

	def checkTrain(self, trainid, stationname, threshold):
		"""Verifica lo stato del treno rispetto ad una data stazione
		Considera il ritardo superiore alla soglia da segnalare e in tal 
		caso, attende tanti minuti quanto il ritardo prima di ricontrollare"""
		locale.setlocale(locale.LC_ALL, 'it_IT.UTF-8')
		data = self._getTrainInfo(trainid)
		if data != []:
			wait = self._checkStatus(data, stationname, threshold)
			if wait > threshold:
				time.sleep(wait*1000*60)
				checkTrain(trainid, stationname, threshold)
		else:
			print "Nessuna inforamzione disponibile"
	
	def _getTrainInfo(self, trainid):
		data = self._HttpGet (trainid)
		return self._parseHtml (data)

	def _HttpGet (self, trainid):
		"""Effettua la GET HTTP della pagina di dettaglio del treno specificato"""
		params = {"numeroTreno": trainid, "dettaglio": "visualizza"}
		headers = {"User-Agent": self.USERAGENT}
		newurl = "%s?%s" % (self.BASEURL, urllib.urlencode (params))
		req = urllib2.Request (newurl, headers = headers)
		r = urllib2.urlopen (req)
		html = r.read ()
		return html

	def _parseHtml (self, html):
		"""Parse HTML"""
		ret = []
		soup = BeautifulSoup (html)
		for div in soup.findAll ("div", {"class":  "giaeffettuate"}) + soup.findAll ("div", {"class":  "corpocentrale"}):
			station = div.find ("h2")
			station = str (station.contents[0])

			# Now get the time
			prog = None
			real = None
			tag = None
			for p in div.findAll ("p"):
				t = str (p.contents[0])
				time = p.find ("strong")
				if len (time.contents) > 0:
					time = str (time.contents[0])
				else:
					time = "00:00"
				if re.search ("(?i)programmat(a|o)", t):
					prog = time.rstrip().lstrip()
				elif re.search ("(?i)effettiv(a|o)", t):
					real = time.rstrip().lstrip()
					tag = "eff"
				elif re.search ("(?i)previst(a|o)", t):
					real = time.rstrip().lstrip()
					tag = "est"
			assert (prog is not None and real is not None and tag is not None)
			print station
			print prog
			print real
			print tag
			e = (station, prog, real, self.timediff (prog, real), tag)
			ret.append (e)
		return ret
		
	def timediff (self, t1, t2):
		"""Differenza in minuti tra t1 e t2.
		Entrambe devono essere nel formato "%H:%M".
		Se t2 < t1, Il risultato sara' negativo."""
		if t1.rstrip().lstrip() != "" and t2.rstrip().lstrip() != "":
			t1 = datetime.datetime.strptime (t1.rstrip().lstrip(), "%H:%M")
			t2 = datetime.datetime.strptime (t2.rstrip().lstrip(), "%H:%M")
			if t2 < t1:
				diff = (t1 - t2).seconds / -60
				# Here we try to workaround cases like 22:50 - 00:24, assuming the max negative timediff we might get is -10
				if diff < -10:
					diff = (t2 - t1).seconds / 60
			else:
				diff = (t2 - t1).seconds / 60
		else:
			diff = 0
		return diff

	def _checkStatus(self, data, stationname, threshold):
		self.TOADDRS = self.config.get("EMAIL","TOADDR").split(",")
		self.SUBJECT = self.config.get("EMAIL","SUBJECT")
		self.MSG = ("From: %s\r\nTo: %s\r\nSubject: %s" % (FROMADDR, TOADDRS, SUBJECT))
		for t in data:
			if t[0] == stationname:
				late = t[3]
				due = t[2]
				real = t[1]
				est = t[4]
				break
		if t[4] == 'eff':
			msg = self.MSG + "GULP! GASP! IL TRENO E' PASSATO ALLE " + due + "\n\r\n\rSIGH"
		else:
			if late < 0:
				msg = self.MSG + "Treno in anticipo di " + str(late * -1) + " minuti (" + due + ")\n\r\n\rBuon viaggio"
			elif late > threshold:
				msg = self.MSG + "Treno in ritardo di " + str(late) + " minuti (" + due + ")\n\r\n\rBuona attesa"
			else:
				msg = self.MSG + "Treno nei limiti della norma " + str(late) + " minuti di ritardo (" + due + ").\n\r\n\rBuon viaggio"			
		self._sendEmail(msg)
		return late

	def _sendEmail(self, msg):
		# send emial
		print "email: " + msg
		try:
			self.SMTPSERVER = self.config.get("EMAIL","SMTPSERVER")
			self.SMTPUSER = self.config.get("EMAIL","SMTPUSER")
			self.SMTPPASS = self.config.get("EMAIL","SMTPPASS")
			self.FROMADDR = self.config.get("EMAIL","FROMADDR")
			
			server = smtplib.SMTP(self.SMTPSERVER)
			server.set_debuglevel(1)
			server.ehlo()
			server.starttls()
			server.ehlo()
			server.login(self.SMTPUSER, self.SMTPPASS)
			server.sendmail(self.FROMADDR, self.TOADDRS, msg)
		except:
			raise UnableToNotify ()

		try:
			server.quit()
		except:
			pass

def main():
	train_number = station = threshold = config = ''
	try:
		opts, args = getopt.getopt(sys.argv[1:], "ht:s:m:c:")
	except getopt.error, msg:
		print msg
		print "Errore: parametri sbagliati. Prova a richiamare train-train.py -h per l'elenco dei parametri"
		sys.exit(2)
	for o, a in opts:
		if o == '-h':
			usage()
			sys.exit()
		elif o == '-t' and a != '':
			train_number = a
		elif o == '-t' and a == '':
			print 'Errore: il parametro -t esige un argomento'
			sys.exit()
		elif o == '-s' and a != '':
			station = a
		elif o == '-s' and a == '':
			print 'Errore: il parametro -s esige un argomento'
			sys.exit()
		elif o == '-m' and a != '':
			threshold = a
		elif o == '-m' and a == '': 
			print 'Errore: il parametro -m esige un argomento'
		elif o == '-c' and a != '':
			config = a
		elif o == '-c' and a == '': 
			print 'Errore: il parametro -c esige un argomento'
			
	tt = TrainTrain(config)
	tt.checkTrain(train_number, station, threshold)

if __name__ == "__main__":
    main()