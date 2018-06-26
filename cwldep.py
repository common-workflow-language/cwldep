import cwltool.factory
import cwltool.context
import subprocess
import json
import hashlib
import os

keydict = {"packages": [{"package": "arvados-python-client"}]}

keydictstr = json.dumps(keydict, separators=(',', ':'),
                        sort_keys=True)
cachekey = hashlib.md5(keydictstr.encode('utf-8')).hexdigest()

inst = os.getcwd()

config = None

if os.path.isdir(os.path.join(inst, cachekey)):
    if os.path.isfile(os.path.join(inst, cachekey, "cwldep.json")):
        with open(os.path.join(inst, cachekey, "cwldep.json")) as f:
            config = json.load(f)

if not config:
    tgtdir = os.path.join(inst, cachekey)
    if not os.path.isdir(tgtdir):
        os.mkdir(tgtdir)

    ctx = cwltool.context.RuntimeContext()
    ctx.tmp_outdir_prefix = tgtdir+"/"

    f = cwltool.factory.Factory(runtimeContext=ctx)
    pipinstall = f.make("pip.cwl")

    config = pipinstall(**keydict)

    with open(os.path.join(inst, cachekey, "cwldep.json"), "w") as f:
        json.dump(config, f)

print "Target", config["target"]["location"]

env = {}

for ev in config["env"]:
    k = ev["envName"]
    v = ev["envValue"]
    if k in env:
        env[k] = v + ":" + k
    else:
        env[k] = v

subprocess.call("arv-get", env=env)
