# Copyright (C) 2016-2017 Cuckoo Foundation.
# This file is part of Cuckoo Sandbox - http://www.cuckoosandbox.org
# See the file 'docs/LICENSE' for copying permission.

import os
import platform
import requests
import sys
import thread

sys.path.insert(0, ".")
import agent

# This whole setup is a bit ugly, but oh well.
thread.start_new_thread(agent.app.run, (), {"port": 0})
while not hasattr(agent.app, "s"):
    continue

class TestAgent(object):
    @property
    def port(self):
        _, port = agent.app.s.socket.getsockname()
        return port

    def get(self, uri, *args, **kwargs):
        return requests.get(
            "http://localhost:%s%s" % (self.port, uri), *args, **kwargs
        )

    def post(self, uri, *args, **kwargs):
        return requests.post(
            "http://localhost:%s%s" % (self.port, uri), *args, **kwargs
        )

    @property
    def tempdir(self):
        """Returns a temporary'ish directory path."""
        env = self.get("/environ").json()["environ"]
        return env.get("PWD", env.get("TEMP"))

    def test_index(self):
        assert self.get("/").json()["message"] == "Cuckoo Agent!"
        assert self.get("/").json()["version"] == agent.AGENT_VERSION

    def test_status(self):
        r = self.get("/status")
        assert r.status_code == 200
        assert r.json()["message"] == "Analysis status"
        assert r.json()["status"] is None
        assert r.json()["description"] is None

        assert self.post("/status").status_code == 400
        assert self.get("/status").json()["status"] is None

        assert self.post("/status", data={"status": "foo"}).status_code == 200
        r = self.get("/status").json()
        assert r["status"] == "foo"
        assert r["description"] is None

        assert self.post("/status", data={
            "status": "foo",
            "description": "bar",
        }).status_code == 200
        r = self.get("/status").json()
        assert r["status"] == "foo"
        assert r["description"] == "bar"

    def test_system(self):
        assert self.get("/system").json()["system"] == platform.system()

    def test_environ(self):
        assert self.get("/environ").json()

    def test_mkdir(self):
        assert self.post("/mkdir", data={
            "dirpath": os.path.join(self.tempdir, "mkdir.test"),
        }).status_code == 200

        r = self.post("/remove", data={
            "path": os.path.join(self.tempdir, "mkdir.test"),
        })
        assert r.status_code == 200
        assert r.json()["message"] == "Successfully deleted directory"

        assert self.post("/remove", data={
            "path": os.path.join(self.tempdir, "mkdir.test"),
        }).status_code == 404

    def test_mktemp(self):
        r_fail = self.post("/mktemp", data={
            "dirpath": "/proc/non-existent",
        })
        assert r_fail.status_code == 500
        assert r_fail.json()["message"] == "Error creating temporary file"

        r_ok = self.post("/mktemp", data={
            "dirpath": "",  # this will work for windows test as well as linux
        })
        assert r_ok.status_code == 200
        assert r_ok.json()["message"] == "Successfully created temporary file"

    def test_mkdtemp(self):
        r_fail = self.post("/mkdtemp", data={
            "dirpath": "/proc/non-existent",
        })
        assert r_fail.status_code == 500
        assert r_fail.json()["message"] == "Error creating temporary directory"

        r_ok = self.post("/mkdtemp", data={
            "dirpath": "",  # this will work for windows test as well as linux
        })
        assert r_ok.status_code == 200
        assert r_ok.json()["message"] == "Successfully created temporary directory"

    def test_execute(self):
        assert self.post("/execute").status_code == 400

    def test_zipfile(self):
        assert self.post("/extract").status_code == 400

    def test_store(self):
        filepath = os.path.join(self.tempdir, "store.test")
        if os.path.exists(filepath):
            os.unlink(filepath)

        data = {
            "filepath": filepath,
        }
        files = {
            "file": ("a.txt", "A"*1024*1024),
        }
        assert self.post("/store", data=data, files=files).status_code == 200
        assert open(filepath, "rb").read() == "A"*1024*1024

    def test_store_unicode(self):
        filepath = os.path.join(self.tempdir, u"unic0de\u202e.txt")

        assert self.post("/store", data={
            "filepath": filepath,
        }, files={
            "file": ("a.txt", "A"*1024*1024),
        }).status_code == 200
        assert os.path.exists(filepath)

        r = self.post("/retrieve", data={
            "filepath": filepath,
        })
        assert r.status_code == 200
        assert r.content == "A"*1024*1024
        assert os.path.exists(filepath)

        assert self.post("/remove", data={
            "path": filepath,
        }).status_code == 200
        assert not os.path.exists(filepath)

        assert self.post("/remove", data={
            "path": filepath,
        }).status_code == 404

        assert self.post("/retrieve", data={
            "filepath": filepath,
        }).status_code == 404
