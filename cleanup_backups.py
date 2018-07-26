#!/usr/bin/python

from dateutil import parser as dp
from datetime import timedelta, datetime
import time
import re
import logging as log
import os, sys
import shutil

default_intervals = "1h 12h 1d 2d 3d 4d 5d 6d 7d 9d 11d 14d 21d 28d 35d"
default_format = "%Y-%m-%d_%H-%M-%S"
default_schedule = "07:00"

UNSET = object()
def get_env(name,default=UNSET):
	if name in os.environ:
		return os.environ[name]
	if default is not UNSET:
		return default
	log.error("Missing environment variable %s",name)
	sys.exit(os.EX_USAGE)

def test():
	log.basicConfig(level=log.DEBUG)
	log.debug("Runing tests - no real tests implemented yet, just output for manual debugging")
	backups=[]
	for i in range(1,32):
		backups.append(dp.parse("2017-01-%s 22:00:00"%i))
	for i in range(1,28):
		backups.append(dp.parse("2017-02-%s 22:00:00"%i))
	intervals=parse_intervals(default_intervals)
	for i in range(1,30):
		backups = get_backups_to_keep(backups,intervals,dp.parse("2017-03-%s 06:00:00"%i))
		backups.append(dp.parse("2017-03-%s 22:00:00"%i))
	for b in backups:
		print b

def get_backups_to_keep(backups, intervals, now = None):
	if now is None:
		now = datetime.now()
	# keep at least 1 backup
	if len(backups)<2:
		return backups

	backups=sorted(backups,reverse=True)
	backups_keep=set()

	# always keep most recent backup
	# (we don't know when the next backup will be made, so we cannot judge if we may need it or not)
	backups_keep.add(backups[0])
	log.debug("Keep last recent backup: %s"%backups[0])

	offset = timedelta()
	for dur in range(0,len(intervals)-1):
		i1 = intervals[dur]
		i2 = intervals[dur+1]
		log.debug("Examining period %s-%s"%(i1['s'],i2['s']))

		oldest_backup=backups[-1]

		for backupnum in range(0,len(backups)):
			backup = backups[backupnum]
			age = now-backup
			# Keep first backup that is older than the beginning of the current period
			if age>=(i1['i']+offset):
				backups_keep.add(backup)
				# If the backup is actually too old for this period, make sure that the
				# following intervals are shifted by the same amount
				if age>(i2['i']+offset):
					offset=age-i2['i'];
					log.info("no backup for period %s-%s, choosing next older backup %s with age %s instead",i1['s'],i2['s'],backup,age)
					log.info("using an offset of %s for all older backups",offset)
				else:
					log.debug("backup for period %s-%s found: %s",i1['s'],i2['s'],backup)

				break
			elif backup==oldest_backup:
				# If we didn't find any backup old enough, we take the oldest one instead
				backups_keep.add(backup)
				log.info("no backup for period %s-%s, choosing oldest backup %s with age %s instead",i1['s'],i2['s'],backup,age);

		log.debug("period %s-%s is satisfied by backup %s with age %s",i1['s'],i2['s'],backup,age)

		# The following loop goes forward in time, starting from the backup
		# that at the time of this run satisfies the current period to the
		# most recent backup.

		# For each backup $backup, it is checked if the backup will at some
		# point in the future be needed to satisfy the period. If so, it is
		# marked as 'candidate' for keeping.

		# A backup $prevBackup is required for a period, if the backup that
		# satisfied the period in the last iteration ($keptBackup) is going
		# to run out of the period before the next backup ($backup) is
		# entering the period.

		kept_backup = backup
		expires = i2['i'] - (now - kept_backup)
		log.debug("Backup %s will leave period in %s",backup,expires)

		for i in range(backupnum-1,-1,-1):
			prev_backup = backup
			backup = backups[i]
			# Determine number of seconds until the next more recent backup will be old enough for the period
			remaining = i1['i']-(now-backup)
			if expires < timedelta():
				# If the backup has already expired, then we obviously need the next one
				backups_keep.add(backup)
				kept_backup = backup
				expires = i2['i']-(now-kept_backup)
				log.info("Backup has already left period. Keeping %s. Will leave period in %s",kept_backup,expires)
			elif expires <= remaining:
				# If the backup last marked to keep for this period will be too old before the current
				# backup is old enough, also mark the previous backup for keeping.				
				log.info("Backup %s will enter period in %s - this is too late, trying to keep intermediate backup.",backup,remaining)
				if (kept_backup==prev_backup):
					log.warn("There will be no backup for period %s-%s in %s. This is usually caused by backups not being done regularly enough.",
                                i1['s'],i2['s'],expires)
					backups_keep.add(backup)
					kept_backup = backup
					expires = i2['i']-(now-kept_backup)
					log.debug("Marking %s to minimze gap. Will leave period in %s.",backup,expires)
				else:
					backups_keep.add(prev_backup)
					kept_backup = backup
					expires = i2['i']-(now-kept_backup)
					log.debug("Marking %s. Will leave period in %s.",backup,expires)
			else:
				log.debug("Backup %s will enter period in %s - no need to keep intermediate backup.",backup,remaining);

	return sorted(backups_keep)


def parse_interval(interval):
	m = re.match("(\d+)h",interval)
	if m:
		return {'s':interval,'i':timedelta(hours=int(m.group(1)))}
	m = re.match("(\d+)d",interval)
	if m:
		return {'s':interval,'i':timedelta(days=int(m.group(1)))}
	raise ValueError("Invalid interval: %s"%interval)

def parse_intervals(intervals):
	parsed_intervals=[]
	for i in intervals.split():
		parsed_intervals.append(parse_interval(i))
	return parsed_intervals

def scan_dir(path, format):
	backups=[]
	for f in os.listdir(path):
		if not os.path.isdir(os.path.join(path,f)):
			continue
		try:
			backup = datetime.strptime(f,format)
		except ValueError:
			continue
		backup_from_time = datetime.strftime(backup,format) 
		if backup_from_time != f:
			raise ValueError("%s changed %s after reformating with format %s. Please check the format!" % (f,backup_from_time,format))
		backups.append(backup)
	return backups

def mark_backup_delatable(backupdir):
	log.info("Marking backup %s as deletable",backupdir)
	os.rename(backupdir,"%s.delete"%backupdir)

def delete_old_backups(dir,intervals):
	backups = scan_dir(dir,default_format)
	backups_keep = get_backups_to_keep(backups, intervals)
	deleted_some = False
	for backup in backups:
		if not backup in backups_keep:
			mark_backup_delatable(os.path.join(dir,datetime.strftime(backup,default_format)))
			deleted_some=True
	if not deleted_some:
		log.warn("Nothing to delete.")
	for deldirname in os.listdir(dir):
		if not deldirname.endswith(".delete"):
			continue
		deldir = os.path.join(dir,deldirname)
		if not os.path.isdir(deldir):
			continue
		log.warn("Actually deleting %s",deldir)
		shutil.rmtree(deldir,True)

def get_rancher_host_label(label_name):
	try:
		import requests
		response=requests.get('http://rancher-metadata/latest/self/host/labels/%s' % label_name)
		if response.status_code==200:
			return response.text
	except:
		pass
	return None

def parse_schedule(s, pat=re.compile(r"(\d{1,2}):(\d{2})")):
	time = pat.match(s)
	if not time:
	   log.warn("Invalid time format for BACKUP_DELETE_SCHEDULE: %s - using default schedule at %s",s,default_schedule)
	   time = pat.match(default_schedule)
	return {'hour':int(time.group(1)),'minute':int(time.group(2))}

def get_next_schedule(hour,minute):
	now = datetime.now()
	schedule = now.replace(hour=hour,minute=minute,second=0,microsecond=0)
	while schedule < now:
	  schedule = schedule + timedelta(days=1)
	return schedule

def schedule_cleanup(hour,minute,backupdir,intervals):
	while True:
		schedule = get_next_schedule(hour,minute)
		log.info("Scheduled next cleanup at %s",schedule)
		while schedule > datetime.now():
			time.sleep(10)
		run_cleanup(backupdir,intervals)

def run_cleanup(backupdir,intervals):
	for n1 in os.listdir(backupdir):
		f1 = os.path.join(backupdir,n1)
		if not os.path.isdir(f1):
			continue
		log.debug('Scanning %s',n1)
		for n2 in os.listdir(f1):
			f2 = os.path.join(f1,n2)
			if not os.path.isdir(f2):
				continue
			log.debug('Processing %s/%s',n1,n2)
			delete_old_backups(f2,intervals)

def main():
	logging.basicConfig(format='%(asctime)s %(message)s', level=logging.INFO)
	backupdir=get_env('BACKUP_DIR')
	intervals = parse_intervals(get_env('BACKUP_KEEP_INTERVALS',default_intervals))
	schedule_time = parse_schedule(get_env('BACKUP_DELETE_SCHEDULE',default_schedule))

	schedule_cleanup(schedule_time['hour'],schedule_time['minute'],backupdir,intervals)

if __name__ == "__main__":
	main()

