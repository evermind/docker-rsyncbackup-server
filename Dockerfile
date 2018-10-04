FROM alpine:3.6

RUN apk add --no-cache --update attr bash openssh-server shadow rsync supervisor python py-requests py-dateutil && \
    useradd -d /home/backup -s /bin/bash backup &&\ 
    usermod -p '*' backup && \
    usermod -p '*' root

ADD docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
ADD backup_shell.sh /usr/local/bin/backup_shell.sh
ADD check_backup.py /usr/local/bin/check_backup.py
ADD cleanup_backups.py /usr/local/bin/cleanup_backups.py
ADD supervisord.conf /etc/supervisord.conf

VOLUME /data
EXPOSE 22

ENV BACKUP_DIR=/data/backup BACKUP_KEEP_INTERVALS="1h 12h 1d 2d 3d 4d 5d 6d 7d 9d 11d 14d 21d 28d 35d" BACKUP_DELETE_SCHEDULE="07:00"

CMD /usr/local/bin/docker-entrypoint.sh
