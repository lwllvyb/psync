#!/usr/bin/env python

import sys
import time
import toml
import signal
import subprocess
import threading
from watchdog.observers import Observer
from watchdog.events import *
import fire


def load_config(config_file):
    config = toml.load(config_file)
    return config

if sys.hexversion <= 0x03050000:
    run_shell = subprocess.call
else:
    run_shell = subprocess.run

def exclude_sub_cmds(ignores):
    cmds = []
    for ig in ignores:
        cmds += ["--exclude", ig]

    return cmds


class AnyEventHandler(FileSystemEventHandler):
    def __init__(self, state):
        super(AnyEventHandler, self).__init__()
        # A dirty way to emit changes to the outside world.
        # Should try to use other pure way to do this.
        self.state = state

    def on_any_event(self, event):
        super(AnyEventHandler, self).on_any_event(event)
        self.state["dirty"] = True


def sync(project):
    cmds = ["rsync", "-e", "ssh", "-ruaz", "--delete"]
    if len(project['ignores']) > 0:
	    cmds += exclude_sub_cmds(project['ignores'])
    for _, ssh in project['ssh'].items():
        cmdline = cmds + ["--rsync-path", "mkdir -p {} && rsync".format(ssh["remote"]), project["local"]]
        cmdline = cmdline + ["-e ssh -p {}".format(ssh['port']), '{}@{}:{}'.format(ssh['username'], ssh['host'], ssh['remote'])]
        run_shell(cmdline)

class FileEventHandler(FileSystemEventHandler):
    def __init__(self):
        FileSystemEventHandler.__init__(self)

    def on_moved(self, event):
        if event.is_directory:
            sync()
            print("directory moved from {0} to {1}".format(event.src_path,event.dest_path))
        else:
            print("file moved from {0} to {1}".format(event.src_path,event.dest_path))

    def on_created(self, event):
        if event.is_directory:
            sync()
            print("directory created:{0}".format(event.src_path))
        else:
            print("file created:{0}".format(event.src_path))

    def on_deleted(self, event):
        if event.is_directory:
            sync()
            print("directory deleted:{0}".format(event.src_path))
        else:
            print("file deleted:{0}".format(event.src_path))

    def on_modified(self, event):
        if event.is_directory:
            sync()
            print("directory modified:{0}".format(event.src_path))
        else:
            print("file modified:{0}".format(event.src_path))

class WatchThread(threading.Thread):
    def __init__(self, project):
        super(WatchThread, self).__init__()
        self.project = project

    def run(self):
        # sync once
        sync(self.project)
        state = {"dirty": False}
        event_handler = AnyEventHandler(state)
        observer = Observer()
        observer.schedule(event_handler, self.project['local'], recursive=True)
        observer.start()
        try:
            while True:
                if state["dirty"]:
                    sync(self.project)
                    state["dirty"] = False
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()

def main(config_file):
    config = load_config(config_file)
    threads = []
    for _, project in config.items():
        t = WatchThread(project)
        t.setDaemon(True)
        threads.append(t)
    for t in threads:
        t.start()
    while True:
        time.sleep(10000)


if __name__ == "__main__":
    fire.Fire(main)
