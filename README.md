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
  -e "BACKUP_CLIENTS=client1 client2" \
  -e "BACKUP_CLIENT_KEY_client1=ssh-rsa AAAAB[...]BBCC client1" \
  -e "BACKUP_CLIENT_KEY_client2=ssh-rsa AAAAB[...]BBCC client2" \
  evermind/docker-rsyncbackup-server:latest
```

Volumes:
* /data/ssh-host-keys - location where the server's host keys are stored
* /data/backup - location where backups are stored (for each client, a directory with the client name will be created)
* The backup volume must support XATTR in order to preserve file attributes

Environment variables:
* BACKUP_CLIENTS a list of client names that have access to this backup server
* BACKUP_CLIENT_KEY_[CLIENT_NAME] The ssh public key (per client, dots in CLIENT_NAME will be replaced by two underscores)
* SSHD_LOG_LEVEL (default: info) The log level for ssh daemon (for debuging purposes)

## Current state / Roadmap

* Backup server (SSH) - DONE
* Automatic deletion of old backups - OPEN
* Monitoring - OPEN
* Additional deduplication using http://rmlint.readthedocs.io/en/latest/ - OPEN
