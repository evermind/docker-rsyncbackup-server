#!/usr/bin/env python

import sys, os, stat, logging, re, json, datetime, time, math
from threading import Timer
import BaseHTTPServer, urlparse
from SocketServer import ThreadingMixIn

UNSET = object()
def get_env(name,default=UNSET):
	if name in os.environ:
		return os.environ[name]
	if default is not UNSET:
		return default
	logging.error("Missing environment variable %s",name)
	sys.exit(os.EX_USAGE)

def human_size(bytes, units=[' bytes','KB','MB','GB','TB']):
	return str(bytes) + units[0] if bytes < 1024 else human_size(bytes>>10, units[1:])

current_backup_status={}

def check_backup(dir,host,vol,backup,recalculate_size):
	metricsfile = os.path.join(dir,'._backup_metrics')
	if os.path.isfile(metricsfile):
		with open(metricsfile,'r') as mf:
			metrics = json.load(mf)
	else:
		if not recalculate_size:
			logging.debug('(Calculating size later)')
			metrics = {
				'size_total': None,
				'size_delta': None
			}
		else:
			logging.info('Calculating backup size for %s/%s/%s',host,vol,backup)
			size_total = 0
			size_delta = 0
			for root, dirs, files in os.walk(dir):
				for f in files:
					file = os.path.join(root, f)
					size = os.path.getsize(file)
					size_total += size
					if os.stat(file).st_nlink == 1:
						size_delta += size
			metrics = {
				'size_total': size_total,
				'size_delta': size_delta
			}
			with open(metricsfile,'w') as mf:
				mf.write(json.dumps(metrics))
			logging.info('  The backup is %s with %s of changed files', human_size(metrics['size_total']),  human_size(metrics['size_delta']))

	return {
		'host': host,
		'vol': vol,
		'backup': backup,
		'size_total': metrics['size_total'],
		'size_delta': metrics['size_delta']
	}

def find_backup_stats(host,volume):
	if not host in current_backup_status:
		return None
	host_backup_status=current_backup_status[host]
	if not volume in host_backup_status:
		return None

	result = dict(host_backup_status[volume].copy())
	backup_ts=int(time.mktime(time.strptime(result['backup'],'%Y-%m-%d_%H-%M-%S')))
	backup_age_hours=math.floor((time.time()-backup_ts)/36)/100 # hours, round to 2 digits
	result['age_hours']=backup_age_hours

	return result

class RequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
	def do_GET(self):
		url=urlparse.urlparse(self.path)
		if not url.path.startswith('/backups') or url.path.count('/')!=3:
			self.do_send(400,{'status':'CRITICAL','message':'Bad request'})
			return
		(path,host,volume)=filter(None, url.path.split('/'))
		backup_stats=find_backup_stats(host,volume)
		if not backup_stats:
			self.do_send(200,{'status':'CRITICAL','message':'No backup found for %s %s' % (host,volume)})
			return
		qs=urlparse.parse_qs(url.query)
		warn_age=int(qs.get('warn', [26])[0])
		crit_age=int(qs.get('crit', [50])[0])
		age=backup_stats['age_hours']
		message="Last backup %s is %s h old"%(backup_stats['backup'],age)
		if age>crit_age:
			status='CRITICAL'
			message+=' (>%s h)'%crit_age
		elif age>warn_age:
			status='WARNING'
			message+=' (>%s h)'%warn_age
		else:
			status='OK'
		response={'status':status,'message':message,'metrics':[]}
		if backup_stats['size_total'] is not None:
			response['metrics'].append({'name':'size','unit':'B','value':backup_stats['size_total']})
		if backup_stats['size_delta'] is not None:
			response['metrics'].append({'name':'delta','unit':'B','value':backup_stats['size_delta']})
		self.do_send(200,response)
	def do_send(self,status,message):
		self.send_response(status)
		self.send_header("Content-type", "application/json")
		self.end_headers()
		self.wfile.write(json.dumps(message))
	def log_message(self, format, *args):
		return

class ThreadedHTTPServer(ThreadingMixIn, BaseHTTPServer.HTTPServer):
	"""Handle requests in a separate thread."""

def start_http_server():
	port=int(get_env('SERVER_PORT',8080))
	logging.info('Starting HTTP server on port %s',port)
	server=ThreadedHTTPServer(('', port), RequestHandler)
	try:
		server.serve_forever()
	except KeyboardInterrupt:
		pass
	logging.info('Shuting down server')
	server.server_close()

def check_backups(recalculate_size=True):
	global current_backup_status
	backupdir=get_env('BACKUP_DIR')
	logging.debug('Processing %s',backupdir)
	new_backup_status={}
	backup_pattern = re.compile('(\d{4})-(\d{2})-(\d{2})_(\d{2})-(\d{2})-(\d{2})')
	for n1 in os.listdir(backupdir):
		f1 = os.path.join(backupdir,n1)
		if not os.path.isdir(f1):
			continue
		logging.debug('Scanning %s',n1)
		for n2 in os.listdir(f1):
			f2 = os.path.join(f1,n2)
			if not os.path.isdir(f2):
				continue
			logging.debug('Scanning %s/%s',n1,n2)
			last_backup = None
			last_backup_dir = None
			for n3 in os.listdir(f2):
				f3 = os.path.join(f2,n3)
				if not os.path.isdir(f3):
					continue
				match = backup_pattern.match(n3)
				if not match:
					continue
				if last_backup is None or last_backup<n3:
					last_backup = n3
					last_backup_dir = f3
			if last_backup is None:
				logging.debug('  no backup found')
			else:
				logging.debug('  last backup: %s',last_backup)
				try:
					result = check_backup(last_backup_dir,n1,n2,last_backup,recalculate_size)
					if result is not None:
						if not result['host'] in new_backup_status:
							new_backup_status[result['host']]={}
						new_backup_status[result['host']][result['vol']]=result
						old_status=find_backup_stats(result['host'],result['vol'])
						# Add the new status temporary to current_backup_status so that it can be seen as long as the scanning is in progress
						if not result['host'] in current_backup_status:
							current_backup_status[result['host']]={}
						current_backup_status[result['host']][result['vol']]=result
						if old_status is None or old_status['backup']!=result['backup']:
							logging.info("Added new backup: %s/%s/%s",result['host'],result['vol'],result['backup'])
				except:
					logging.exception("Unexpected error")
	current_backup_status=new_backup_status

def check_backups_scheduler():
	try:
		check_backups()
	except:
		logging.warn("Unexpected error: %s", sys.exc_info()[0])
	t=Timer(300, check_backups_scheduler, ())
	t.daemon=True
	t.start()

def start_scheduler():
	t=Timer(5, check_backups_scheduler, ())
	t.daemon=True
	t.start()

def main():
	logging.basicConfig(format='%(asctime)s %(message)s', level=logging.INFO)
	check_backups(False)
	start_scheduler()
	start_http_server()
	return


if __name__ == "__main__":
	main()
