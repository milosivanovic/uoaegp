#!/usr/bin/python

"""

Copyright (C) 2011-2013 Milos Ivanovic

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""

import sys, os
import getpass
import ssoapi
import time
import lxml.html
import argparse

class Poller(object):
	
	def __init__(self, config):
		self.config = config
		self.username = None
		self.password = None
		self.semester = None
		self.results = {}
		self.iters = 0
		self.workaround = False
	
	def watchdog(self):
		while True:
			try:
				if not self.iters:
					self._begin()
				else:
					self._create_job(True)
			except KeyboardInterrupt:
				self.iters = 0
				self.semester = None
				sys.stdout.write('\n\n')
			except Exception, e:
				self._log("Unhandled exception %s: %s" % (type(e), repr(e)), 1)
				time.sleep(1)
	
	def _begin(self):
		sys.stdout.write('\n')
		print "    ```````````````         o    o             .oo   .oPYo. .oPYo.  .oPYo.     "
		print "    .`.`:.-`./ -`-:.        8    8            .P 8   8.     8    8  8    8     "
		print "    ...:s.`-/o.`:o-.        8    8 .oPYo.    .P  8   `boo   8      o8YooP'     "
		print "    :NhyhhmyhmhhyhN-        8    8 8    8   oPooo8   .P     8   oo  8          "
		print "    :MMMmhdmmdhmMMM-        8    8 8    8  .P    8   8      8    8  8          "
		print "    `NMs.  ``  -sMm         `YooP' `YooP' .P     8   `YooP' `YooP8  8          "
		print "     -Ny//o//o:+yN.         :.....::.....:..:::::..:::.....::....8 :..:::::    "
		print "      `yMMMmmMMMy`          :::::::::::::::::::::::::::::::::::::8 ::::::::    "
		print "        .oddddo.            :::::::::::::::::::::::::::::::::::::..::::::::    "
		print "           ``                  University of Auckland Exam Grade Poller        "
		print "-------------------------------------------------------------------------------"
		print "        D      I      S      C      L      A      I      M      E      R       "
		print "-------------------------------------------------------------------------------"
		print "1. The information supplied to this program is not stored, sent, or shared"
		print "   in any way."
		print "2. The connection established between this program and the Auckland University"
		print "   servers is secured in the same manner as conventional browsing on"
		print "   student.auckland.ac.nz (HTTP + SSL/TLS). CTRL+C returns to the main menu.\n"
		self._create_job()
	
	def _log(self, message, severity = 0):
		if severity == -1:
			print message
		elif severity == 1:
			print "\n[ !! ] %s\n" % message
		elif severity == 0:
			print "\n[ OK ] %s\n" % message
	
	def _chooser(self, qprefix, aprefix, choices, print_list = True):
		def showopts():
			print qprefix
			for n, c in enumerate(choices):
				print "%d. %s" % (n+1, c)
			sys.stdout.write('\n')
		
		if print_list:
			showopts()
			
		while True:
			try:
				raw_choice = raw_input('%s: ' % aprefix).strip()
				choice = int(raw_choice)
				if choice >= 1 and choice <= len(choices): break
			except ValueError:
				if raw_choice == '?':
					sys.stdout.write('\n')
					showopts()
		return choice
	
	def _create_job(self, resuming = False):
		if not resuming:
			self.job = self._chooser('What would you like to do?', 'Choice', ['Check semester grades', 'Poll latest semester for new grades'])
			if not self.username or not self.password:
				print "\nPlease provide the details below to continue.\n"
				self._get_credentials()
			else:
				sys.stdout.write('\n')
			if not self.api.login_time:
				self._get_credentials(True)
		
		# permanent workaround required as of November 2012
		self.workaround = True
		
		self.semesters = lxml.html.fromstring(self.api.call('SSR_SSENRL_GRADE')).xpath("//span[starts-with(@id, 'TERM_CAR$')]/text()")
		if not self.semesters:
			# Some users have reported accessing 'My Grades' on PeopleSoft and immediately being presented with their current semester
			# grades rather than getting a list of all graded semesters since induction.
			# Clicking 'Change Term' is emulated in the variable overwrite below
			self.semesters = lxml.html.fromstring(self.api.call('SSR_SSENRL_GRADE', 'DERIVED_SSS_SCT_SSS_TERM_LINK')).xpath("//span[starts-with(@id, 'TERM_CAR$')]/text()")
			# self.workaround = True
			
		if self.job == 1:
			while True:
				self._pick_semester_manually(self.semester)
				results = self._get_exam_results(self.semester)
				self._print_grades(results[0], results[1])
		else:
			if not resuming:
				self._log("Auto-detecting earliest semester with pending grades...", -1)
			self._select_pending_semester()
			while True:
				results = self._get_exam_results(self.semester)
				if not self.iters:
					self._print_grades(results[0], results[1])
					self._log("In order to be notified of changes, you must keep this program running.", -1)
					self._log("If there are any changes to your grades, you will be notified below.\n", -1)
				self._compare_grades(results[0], results[1], results[2])
				self._wait(self.config['poll'])
	
	def _get_credentials(self, login_only = False):
		while True:
			if not self.iters and not login_only:
				self.username = raw_input('UPI: ')
				self.password = getpass.getpass('Password (hidden): ')
			self.api = ssoapi.SSOAPI(self.username, self.password)
			if self.api.login():
				self._log('Welcome, %s.' % self.api.current_user)
				break
			else:
				login_only = False
				self._log('Invalid credentials.', 1)
	
	def _pick_semester_manually(self, again = False):
		self.semester = self._chooser('Available semesters:', 'Show me my grades for choice number', self.semesters, True if not again else False)
	
	def _select_pending_semester(self):
		for n in range(1, len(self.semesters)+1):
			self.semester = n
			if 'Pending' not in self._get_exam_results(self.semester, True):
				if self.semester > 1:
					self.semester = n-1
				break
	
	def _get_exam_results(self, semester, return_grades_only = False):
		# self.workaround will always be True (27/11/12)
		if self.workaround:
			# If PeopleSoft presented a set of semester grades immediately upon clicking 'My Grades' instead of
			# giving the choice to pick a semester, an emulated click on 'Change Term' must be performed as
			# the quick access shortcut (SSR_DUMMY_RECV1$sels$0: x) will not register immediately in this scenario
			if self.api.params.get('ICAction') != 'DERIVED_SSS_SCT_SSS_TERM_LINK':
				# This is just to make sure we aren't already on the Change Term page, otherwise we would be
				# calling an invalid link
				self.api.call('SSR_SSENRL_GRADE', 'DERIVED_SSS_SCT_SSS_TERM_LINK')
		sem_grades_et = lxml.html.fromstring(self.api.call('SSR_SSENRL_GRADE', 'DERIVED_SSS_SCT_SSR_PB_GO', {'SSR_DUMMY_RECV1$sels$0': (semester-1)}))
		courses = sem_grades_et.xpath("//a[starts-with(@id, 'CLS_LINK$')]/text()")
		if courses:
			points = sem_grades_et.xpath("//span[starts-with(@id, 'STDNT_ENRL_SSV1_UNT_TAKEN$')]/text()")
			grades = sem_grades_et.xpath("//span[starts-with(@id, 'STDNT_ENRL_SSV1_CRSE_GRADE_OFF$')]/text()")
			gpas = sem_grades_et.xpath("//span[starts-with(@id, 'STDNT_ENRL_SSV1_GRADE_POINTS$')]/text()")
			gpa = sem_grades_et.xpath("//span[starts-with(@id, 'STATS_CUMS$')]/text()")[-1]
			for n in range(len(grades)):
				points[n] = points[n].strip()
				grades[n] = grades[n].strip()
				gpas[n] = gpas[n].strip()
				gpa = gpa.strip()
				if not gpas[n]:
					if not grades[n] or grades[n] in ['CPL', 'NA']:
						gpas[n] = 'N/A'
					else:
						gpas[n] = '0'
				else:
					gpas[n] = '%d/9' % (int(float(gpas[n]))/int(float(points[n])))
				if not grades[n]: grades[n] = gpas[n] = 'Pending'
				
			if return_grades_only:
				return grades
			else:
				return [dict(zip(courses, zip(grades, gpas))), gpa, 'Pending' in grades]
				
	def _compare_grades(self, results, gpa, pending = True):
		if not self.iters:
			self.results = results
		else:
			if results != self.results:
				sys.stdout.write('Disparity detected %s.' % time.strftime("at %H:%M on %d/%m/%Y", time.localtime()))
				self._print_grades(results, gpa, [k for k, v in results.iteritems() if v[0] != self.results[k][0]])
				self.results = results
			else:
				sys.stdout.write('No change.')
				sys.stdout.flush()
				time.sleep(1)
				sys.stdout.write('\r'.ljust(23))
		if not pending:
				self._log("All grades released; job done.", -1)
				self._quit()
	
	def _print_grades(self, results, ogpa, new = []):
			for n, course in enumerate(new):
				if not n: print "\n"
				else: print "- and -".rjust(24)
				print "+******************************************+"
				print "| %s |" % ('%s EXAM GRADE RELEASED' % course).center(40)
				print "+******************************************+"
			if new:
				for n in range(10):
					sys.stdout.write(chr(7))
					time.sleep(1)
			print "\n+%s+" % ("UoA %s Exam Grades" % self.semesters[self.semester-1]).center(42, '-')
			print "+------------------------------------------+"
			print "|      Course      |  Grade  |  GPA Score  |"
			print "+------------------------------------------+"
			for course, (grade, gpa) in results.iteritems():
				print "| %s | %s | %s |" % (course.center(16), grade.center(7), gpa.center(11))
			print "+------------------------------------------+"
			print "| Overall GPA as of chosen semester: %s | " % (ogpa if ogpa else '-.---')
			print "+------------------------------------------+\n"
	
	def _wait(self, interval):
		for n in range(interval):
			sys.stdout.write('\rWaiting %d...' % (interval-n-1))
			sys.stdout.flush()
			time.sleep(1)
		self.iters += 1
	
	def _quit(self, n = None):
		if n:
			sys.stdout.write('\n\n')
			self._log("Caught signal %d, quitting..." % n, -1)
		if sys.platform.startswith('win'):
			os.system('pause')
		elif sys.platform.startswith('linux') or sys.platform.startswith('darwin'):
			os.system('read -n1 -r -p "Press any key to exit."')
			sys.stdout.write('\n')
		sys.exit()

if __name__ == "__main__":
	parser = argparse.ArgumentParser(description='Poll the Auckland University SSO servers for newly released grades')
	parser.add_argument('-p', '--poll', metavar='polling_interval', action='store', type=int, default=300, help='poll for new grades every polling_interval seconds')
	args = parser.parse_args().__dict__
	
	poller = Poller(args)
	poller.watchdog()