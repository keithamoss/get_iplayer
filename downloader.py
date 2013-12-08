#!/usr/bin/env /home/samba-share/nas/www/get_iplayer/get_iplayer/bin
# -*- coding: utf-8 -*-

import os
import posixpath
import csv
import requests
import subprocess
import shutil
import logging
from datetime import datetime
from sqlite3 import dbapi2 as sqlite3
from dropbox.client import DropboxClient, DropboxOAuth2Flow

# configuration
RECORDINGS_DIR = "/home/samba-share/nas/www/get_iplayer/recordings"
GETIPLAYER_DIR = "/usr/bin/get_iplayer"
LOGFILE_NAME = "/home/samba-share/nas/www/get_iplayer/get_iplayer.log"
SERIES_FILE = "/home/samba-share/nas/www/get_iplayer/series.csv"
DROPBOX_USERNAME = "keithamoss"
DATABASE_NAME = "/home/samba-share/nas/www/get_iplayer/instance/myapp.db"

logging.basicConfig(filename=LOGFILE_NAME,format='%(asctime)s %(message)s',level=logging.DEBUG)

# crontab
# 5 1 * * * /home/samba-share/nas/www/get_iplayer/get_iplayer/bin/python /home/samba-share/nas/www/get_iplayer/get_iplayer_looter.py

# uwsgi
# tail -f /var/log/uwsgi-getiplayer.log
# sudo /usr/local/bin/uwsgi --reload /tmp/supervisord.pid

def get_db():
    """
    Opens a new database connection if there is none yet for the current application context.
    """
    # sqlite_db = sqlite3.connect(os.path.join("instance", DATABASE_NAME))
    sqlite_db = sqlite3.connect(DATABASE_NAME)
    sqlite_db.row_factory = sqlite3.Row

    return sqlite_db

def get_access_token():
    username = DROPBOX_USERNAME
    if username is None:
        return None
    db = get_db()
    row = db.execute('SELECT access_token FROM users WHERE username = ?', [username]).fetchone()
    if row is None:
        return None
    return row[0]

def download(pid, client):
    subprocess.check_output([GETIPLAYER_DIR, '--modes=flashaaclow,rtspaaclow', '--type=radio', '--subdir', '--force', '--output=' + RECORDINGS_DIR, '--file-prefix="<nameshort>-<episodeshort>-<senum>-<pid>"', '--pid=' + pid])
    recordings = subprocess.check_output(['find', RECORDINGS_DIR, '-name', '*.m4a']).strip()
    if recordings != "":
        logging.info("file downloaded")
        dirname = os.path.basename(os.path.dirname(recordings))
        filename = os.path.basename(recordings)
        response = client.put_file('/' + dirname + '/' + filename, open(recordings))
        logging.info("file uploaded to Dropbox")
        logging.debug(response)
        shutil.rmtree(os.path.dirname(recordings))
        logging.info("pid %s END", pid)
    else:
        logging.info("pid %s not available yet", pid)

def main():
    logging.info('BEGIN')
    access_token = get_access_token()
    if access_token is not None:
        client = DropboxClient(access_token)
        account_info = client.account_info()

        if os.path.exists(SERIES_FILE):
            os.remove(SERIES_FILE)
        out = open(SERIES_FILE, 'a+')
        out.write(client.get_file('/series.csv').read())
        out.close()

        reader = csv.reader(open(SERIES_FILE, 'r'), delimiter=',')
        reader.next()
        for row in reader:
            sid = row[0]
            pid = row[1]
            active = row[4]

            if(active == 0):
                continue

            if(sid == "" and pid != ""):
                logging.info("pid %s (no sid)", pid)
                download(pid, client)
                continue

            logging.info("sid %s", sid)
            r = requests.get("http://www.bbc.co.uk/programmes/" + sid + "/episodes/player.json")
            if(r.status_code == 404):
                logging.info("404 Not Found")
                continue

            for episode in r.json()["episodes"]:
                tpid = episode["programme"]["pid"]
                if(pid != "" and tpid != pid):
                    continue;
                logging.info("pid %s START", tpid)
                response = client.search('', tpid)
                if len(response) == 0:
                    logging.info("pid %s not found in Dropbox", tpid)
                    download(tpid, client)
                    continue
                else:
                    logging.info("pid %s already in Dropbox", tpid)
            continue
            logging.info("sid %s END", sid)
        os.remove(SERIES_FILE)
    logging.info('END')

if __name__ == '__main__':
    main()
