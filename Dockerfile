FROM alpine:3.6

RUN apk add --no-cache --update attr bash openssh-server shadow rsync supervisor python && \
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

CMD /usr/local/bin/docker-entrypoint.sh
