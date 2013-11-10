#!/home/samba-share/nas/www/get_iplayer/get_iplayer/bin
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
LOGFILE_NAME = "get_iplayer.log"
SERIES_FILE = "series.csv"
DROPBOX_USERNAME = "keithamoss"
DATABASE_NAME = "myapp.db"

logging.basicConfig(filename=LOGFILE_NAME,format='%(asctime)s %(message)s',level=logging.DEBUG)

# crontab
# 5 2 * * * /home/samba-share/nas/www/get_iplayer/get_iplayer/bin/python get_iplayer_looter.py

# uwsgi
# tail -f /var/log/uwsgi-getiplayer.log
# sudo /usr/local/bin/uwsgi --reload /tmp/supervisord.pid

def get_db():
    """
    Opens a new database connection if there is none yet for the current application context.
    """
    sqlite_db = sqlite3.connect(os.path.join("instance", DATABASE_NAME))
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
            r = requests.get("http://www.bbc.co.uk/programmes/" + row[0] + "/episodes/upcoming.json")
            pid = r.json()["broadcasts"][0]["programme"]["pid"]
            logging.info("pid %s", pid)
            response = client.search('', pid)
            if len(response) == 0:
                logging.info("pid not found in Dropbox")
                output = subprocess.check_output([GETIPLAYER_DIR, '--modes=flashaaclow,rtspaaclow', '--type=radio', '--subdir', '--output=' + RECORDINGS_DIR, '--file-prefix="<nameshort>-<episodeshort>-<senum>-<pid>"', '--pid=' + pid])
                output = subprocess.check_output(['find', RECORDINGS_DIR, '-name', '-o *.m4a', '-name', '*.mp3']).strip()
                if output != "":
                    logging.info("file downloaded")
                    dirname = os.path.basename(os.path.dirname(output))
                    filename = os.path.basename(output)
                    response = client.put_file('/' + dirname + '/' + filename, open(output))
                    logging.info("file uploaded to Dropbox")
                    logging.debug(response)
                    shutil.rmtree(os.path.dirname(output))
                    logging.info("downloaded files cleaned up")
                else:
                    logging.info("pid not available yet")
        os.remove(SERIES_FILE)
    logging.info('END')

if __name__ == '__main__':
    main()
