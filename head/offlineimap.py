#!/usr/bin/python2.2 -i

# Copyright (C) 2002 John Goerzen
# <jgoerzen@complete.org>
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

from imapsync import imaplib, imaputil, imapserver, repository, folder
import re, getpass, os, os.path
from ConfigParser import ConfigParser

config = ConfigParser()
config.read("imapsync.conf")
metadatadir = os.path.expanduser(config.get("general", "metadata"))
if not os.path.exists(metadatadir):
    os.mkdir(metadatadir, 0700)

accounts = config.get("general", "accounts")
accounts = accounts.replace(" ", "")
accounts = accounts.split(",")

server = None
remoterepos = None
localrepos = None

for accountname in accounts:
    print "Processing account " + accountname
    accountmetadata = os.path.join(metadatadir, accountname)
    if not os.path.exists(accountmetadata):
        os.mkdir(accountmetadata, 0700)
    host = config.get(accountname, "remotehost")
    user = config.get(accountname, "remoteuser")
    port = None
    if config.has_option(accountname, "remoteport"):
        port = config.getint(accountname, "remoteport")
    password = None
    if config.has_option(accountname, "remotepass"):
        password = config.get(accountname, "remotepass")
    else:
        password = getpass.getpass("Password for %s: " % accountname)
    ssl = config.getboolean(accountname, "ssl")

    # Connect to the remote server.
    server = imapserver.IMAPServer(user, password, host, port, ssl)
    remoterepos = repository.IMAP.IMAPRepository(server)

    # Connect to the Maildirs.
    localrepos = repository.Maildir.MaildirRepository(os.path.expanduser(config.get(accountname, "localfolders")))

    # Connect to the local cache.
    statusrepos = repository.LocalStatus.LocalStatusRepository(accountmetadata)
    
    
    print "Synchronizing folder list..."
    remoterepos.syncfoldersto(localrepos)
    print "Done."
    for remotefolder in remoterepos.getfolders():
        print "*** SYNCHRONIZING FOLDER %s" % remotefolder.getname()
        # Load local folder.
        localfolder = localrepos.getfolder(remotefolder.getname())
        if not localfolder.isuidvalidityok(remotefolder):
            print 'UID validity is a problem for this folder; skipping.'
            continue
        print "Reading local message list...",
        localfolder.cachemessagelist()
        print len(localfolder.getmessagelist().keys()), "messages."

        # Load remote folder.
        print "Reading remote message list...",        
        remotefolder.cachemessagelist()
        print len(remotefolder.getmessagelist().keys()), "messages."

        # Load status folder.
        statusfolder = statusrepos.getfolder(remotefolder.getname())
        
        if statusfolder.isnewfolder():
            print "Local status folder is new; ignoring."
        else:
            print "Synchronizing local changes."
            localfolder.syncmessagesto(statusfolder, [remotefolder, statusfolder])
        
        # Synchronize remote changes.
        print "Synchronizing remote to local..."
        remotefolder.syncmessagesto(localfolder, [localfolder, statusfolder])

        # Make sure the status folder is up-to-date.
        print "Updating local status cache..."
        localfolder.syncmessagesto(statusfolder)
        statusfolder.save()
        
        