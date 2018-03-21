#!/bin/bash

# This script can be used as wrapper for rsync in authorized_keys. It restricts rsync the following way:
# - restrict target directory to be under /data/backup/${1}/target/ where $1 is an argument from authorized_keys
# - restrict target directory to be exactly 1 level below this directory
# - restrict flags
# - restrict arguments
# - force --fake-super argument

err() {
  echo "--------------------------------------------------------------------" >&2
  echo "ERROR ON REMOTE SIDE:" >&2
  echo "$*" >&2
  echo "--------------------------------------------------------------------" >&2
}

if [ $# -ne 1 ]; then
  err "DIR not set in authorized_keys"
  exit 1
fi

DIR="/data/backup/${1}/"

if [ ! -d "$DIR" ]; then
  err "Client dir not found."
  exit 1
fi

ARGS=( $SSH_ORIGINAL_COMMAND )
ARG_COUNT="${#ARGS[@]}"

shopt -s extglob

do_rsync() {
  CMD="/usr/bin/rsync --fake-super --server"
  if [ $ARG_COUNT -lt  3 ]; then
    err "Supplied rsync command had too few args"
    exit 1
  fi
  ARG_N1="${ARGS[$(( ARG_COUNT - 2 ))]}"
  if [ "$ARG_N1" != "." ]; then
    err "the arg before the last arg must be a dot, not $ARG_N1"
    exit 1
  fi
  PATH="${ARGS[$(( ARG_COUNT - 1 ))]}"
  if ! [[ "$PATH" =~ ^[a-zA-Z0-9_-]+$ ]]; then
    err "The last arg must be a path that matches [a-zA-Z0-9_-]+ , not $PATH"
    exit 1
  fi
  UPLOADING=1
  for ARG in "${ARGS[@]:1:$(( ARG_COUNT - 3 ))}"; do
    case $ARG in
      -+(v|l|o|g|D|t|p|A|X|r|S|e.|i)*(Ls)*(f|x|C) )
        # allowed flags. requires "shopt -s extglob" to be set outside this function
        CMD="$CMD $ARG"
      ;;
      "--delete-during"|"--numeric-ids"|"--delete-excluded")
        # added to command
        CMD="$CMD $ARG"
      ;;
      "--sender")
        # added to command
        CMD="$CMD $ARG"
        UPLOADING=0
      ;;
      "--fake-super"|"--server")
        # silently ignored
      ;;
      *)
        err "rsync arg not allowed: $ARG"
        exit 1
        ;;
    esac
  done
  TARGET="${DIR}${PATH}/in_progress/"
  if [ "$UPLOADING" == "1" ]; then
    /bin/mkdir -p "${TARGET}"
    if [ -e "${DIR}${PATH}/latest" ]; then
      CMD="$CMD --link-dest ${DIR}${PATH}/latest/"
    fi
  fi
  $CMD . "${TARGET}"
  exit $?
}

do_finish_backup() {
  if [ $ARG_COUNT -ne  2 ]; then
    err "USAGE: FINISH_BACKUP path"
    exit 1
  fi
  PATH="${ARGS[1]}"
  if ! [[ "$PATH" =~ ^[a-zA-Z0-9_-]+$ ]]; then
    err "The path must match [a-zA-Z0-9_-]+, not $PATH"
    exit 1
  fi
  TARGET="${DIR}${PATH}/in_progress"
  if [ ! -d "$TARGET" ]; then
    err "There's no current backup!"
    exit 1
  fi
  DATE="$( /bin/date +'%Y-%m-%d_%H-%M-%S' )"
  NEWDIR="${DIR}${PATH}/${DATE}"
  if [ -d "$NEWDIR" ]; then
    err "Backup target dir already exists: ${DATE}"
    exit 1
  fi
  /bin/mv "$TARGET" "$NEWDIR"
  /bin/rm -f "${DIR}${PATH}/latest"
  /bin/ln -s "${DATE}" "${DIR}${PATH}/latest"
}


case "${ARGS[0]}" in
    "rsync")
        do_rsync
        ;;
    "FINISH_BACKUP")
        do_finish_backup
        ;;
    *)
        err "Command denied: $SSH_ORIGINAL_COMMAND"
        exit 1
        ;;
esac
