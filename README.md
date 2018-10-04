# Dockerized server for RSYNC based backups

## Backup concept

* Clients push backups, using RSYNC
  * only changed files are transfered
  * Hard links are used to de-duplicate unchanged files
* Clients send a special command to the server to finish backups
  * Once a backup is finished, the client has no was to delete it
* Enhanced security 
  * All communication is done via SSH, using public/private key authentification
  * An attacker with access to the backup server cannot access the clients
  * An attacker with access to a backup client cannot modify already finished backups 
  * A special shell restricts clients to certain commands (rsync / finish backup)
* Easy recovery
  * On the backup server, one directory per backup exists, containing all the files

## USAGE

```
docker run -v /storage/path:/data -p 2201:22 \
  -e "BACKUP_CLIENTS=client1:ssh-rsa:AAAAB[...]BBCC client2:ssh-rsa:AAAAB[...]BBCC client2"
  evermind/docker-rsyncbackup-server:latest
```

Volumes:
* /data/ssh-host-keys - location where the server's host keys are stored
* /data/backup - location where backups are stored (for each client, a directory with the client name will be created)
* The backup volume must support XATTR in order to preserve file attributes

Environment variables:
* BACKUP_CLIENTS a list of whitespace separated "client_name:key_type:ssh_key" entries for all clients access to this backup server
* SSHD_LOG_LEVEL (default: info) The log level for ssh daemon (for debuging purposes)
* BACKUP_DELETE_SCHEDULE (default: 07:00) defines the time when backups are deleted
* BACKUP_KEEP_INTERVALS (default: 1h 12h 1d 2d 3d 4d 5d 6d 7d 9d 11d 14d 21d 28d 35d) defines a list of intervals to keep backups for. Must be in ascending order

### Deleting old backups

Once every day, old backups are deleted. To determine which backups should be kept, an algorithm parses BACKUP_KEEP_INTERVALS and calculates which backups are required so that in each interval exists at least one backup at any time.

### Monitoring

A monitoring endpoint is exposed via http at port 8080 under /backups/CLIENT_NAME/BACKUP_VOLUME. The current backup status is exported as JSON.

TODO: Add link to nagios plugin to read the JSON output

## Current state / Roadmap

* Backup server (SSH) - DONE
* Automatic deletion of old backups - DONE
* Monitoring - DONE
* Additional deduplication using http://rmlint.readthedocs.io/en/latest/ - OPEN
