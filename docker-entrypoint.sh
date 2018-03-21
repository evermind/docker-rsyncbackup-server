#!/bin/bash

set -e

echo -n "* Testing xattr support at /data ... "
cd /data
touch .test_xattr
setfattr -n user.test_xattr -v "success" .test_xattr
getfattr -n user.test_xattr .test_xattr > /dev/null
rm -f .test_xattr
echo "SUCCESS"

echo
echo "* Setting up SSH host keys"
mkdir -p /data/ssh-host-keys
chmod 0700 /data/ssh-host-keys
for keytype in rsa dsa ecdsa ed25519; do
  if [ ! -e /data/ssh-host-keys/ssh_host_${keytype}_key ]; then
    echo "* Generating /data/ssh-host-keys/ssh_host_${keytype}_key"
    ssh-keygen -N "" -t ${keytype} -f /data/ssh-host-keys/ssh_host_${keytype}_key
  fi
  ln -fs /data/ssh-host-keys/ssh_host_${keytype}_key /etc/ssh/ssh_host_${keytype}_key
done

mkdir -p /data/backup /home/backup/.ssh
> /home/backup/.ssh/authorized_keys
chown backup.backup /data/backup /home/backup/.ssh /home/backup/.ssh/authorized_keys

echo
echo "* Setting up client access"
if [ -z "${BACKUP_CLIENTS}" ]; then
  echo "Please set BACKUP_CLIENTS with a list of clients that are allowed to backup to this backup server"
  exit 1
fi

for CLIENT in ${BACKUP_CLIENTS}; do
  KEY_VAR="BACKUP_CLIENT_KEY_${CLIENT//./__}"
  echo "* Adding client ${CLIENT}"
  if [ -z "${!KEY_VAR}" ]; then
    echo "Please set the variable ${KEY_VAR} to contain the ssh public key for this client"
    exit 1
  fi
  echo "command=\"/usr/local/bin/backup_shell.sh ${CLIENT}\",no-port-forwarding,no-X11-forwarding,no-pty ${!KEY_VAR}" >> /home/backup/.ssh/authorized_keys
  mkdir -p /data/backup/${CLIENT}
  chown backup.backup /data/backup/${CLIENT}
done

echo
echo "* Use one of the following keys for your client's known_hosts file"
for keytype in rsa dsa ecdsa ed25519; do
  echo
  echo -n "  "
  cat /data/ssh-host-keys/ssh_host_${keytype}_key.pub
done
echo

echo "Starting sshd"
/usr/sbin/sshd -p 22 -D -E /proc/1/fd/1 -o LogLevel=${SSHD_LOG_LEVEL:-info} -o PasswordAuthentication=no
