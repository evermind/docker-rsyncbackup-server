FROM alpine:3.6

RUN apk add --no-cache --update attr bash openssh-server shadow rsync && \
    useradd -d /home/backup -s /bin/bash backup &&\ 
    usermod -p '*' backup && \
    usermod -p '*' root

ADD docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
ADD backup_shell.sh /usr/local/bin/backup_shell.sh

VOLUME /data
EXPOSE 22

CMD /usr/local/bin/docker-entrypoint.sh
