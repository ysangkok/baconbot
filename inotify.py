# AsyncNotifier example from tutorial
#
# See: http://github.com/seb-m/pyinotify/wiki/Tutorial
#
import asyncore
import pyinotify
import sys

wm = pyinotify.WatchManager()  # Watch Manager
mask = pyinotify.IN_DELETE | pyinotify.IN_CREATE  # watched events

class EventHandler(pyinotify.ProcessEvent):
    def process_IN_CREATE(self, event):
        print("Creating:", event.pathname)

    def process_IN_DELETE(self, event):
        print("Removing:", event.pathname)

notifier = pyinotify.AsyncNotifier(wm, EventHandler())
wdd = wm.add_watch(sys.argv[1], mask, rec=True)

asyncore.loop()
