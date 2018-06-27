import cwltool.factory
import cwltool.context
import subprocess
import json
import hashlib
import os
import urlparse
from six.moves import urllib
import schema_salad.ref_resolver
from cwltool.process import scandeps
from cwltool.load_tool import load_tool
from cwltool.utils import visit_class
import requests
import logging

def software_reqs(basedir, keydict):
    keydict = {"packages": [{"package": "arvados-python-client"}]}

    keydictstr = json.dumps(keydict, separators=(',', ':'),
                            sort_keys=True)
    cachekey = hashlib.md5(keydictstr.encode('utf-8')).hexdigest()

    inst = basedir

    config = None

    if os.path.isdir(os.path.join(inst, cachekey)):
        if os.path.isfile(os.path.join(inst, cachekey, "cwldep.json")):
            with open(os.path.join(inst, cachekey, "cwldep.json")) as f:
                config = json.load(f)

    if not config:
        tgtdir = os.path.join(inst, cachekey)
        if not os.path.isdir(tgtdir):
            os.makedirs(tgtdir)

        ctx = cwltool.context.RuntimeContext()
        ctx.tmp_outdir_prefix = tgtdir+"/"

        f = cwltool.factory.Factory(runtimeContext=ctx)
        pipinstall = f.make("pip.cwl")

        config = pipinstall(**keydict)

        with open(os.path.join(inst, cachekey, "packages.json"), "w") as f:
            f.write(keydictstr)

        with open(os.path.join(inst, cachekey, "cwldep.json"), "w") as f:
            json.dump(config, f)

    env = {}

    for ev in config["env"]:
        k = ev["envName"]
        v = ev["envValue"]
        if k in env:
            env[k] = v + ":" + k
        else:
            env[k] = v

    with open("wrapper.sh", "w") as f:
        f.write("""#!/bin/sh
%s
cwl-runner %s "$@"
        """ % ("\n".join("export '%s=%s'" % (k,v) for k,v in env.items()),
               " ".join("'--preserve-environment=%s'" % k for k in env)))

def cwl_deps(basedir, dependencies, update=False):
    for d in dependencies["dependencies"]:
        upstream = d["upstream"]
        spup = urllib.parse.urlsplit(upstream)
        if d.get("installTo"):
            installTo = os.path.join(basedir, d.get("installTo"))
        else:
            installTo = os.path.dirname(os.path.join(basedir, spup.netloc, spup.path.lstrip("/")))

        if os.path.isfile(os.path.join(installTo, os.path.basename(spup.path))) and not update:
            continue

        deps = {"class": "File", "location": upstream}  # type: Dict[Text, Any]

        loadctx = cwltool.context.LoadingContext()
        tool = load_tool(upstream, loadctx)

        def loadref(base, uri):
            return tool.doc_loader.fetch(tool.doc_loader.fetcher.urljoin(base, uri))

        tool.doc_loader.idx = {}

        sfs = scandeps(
            upstream, tool.doc_loader.fetch(upstream), {"$import", "run"},
            {"$include", "$schemas", "location"}, loadref)
        if sfs:
            deps["secondaryFiles"] = sfs

        def retrieve(obj):
            sploc = urllib.parse.urlsplit(obj["location"])
            rp = os.path.relpath(sploc.path, os.path.dirname(spup.path))
            tgt = os.path.join(installTo, rp)
            if not os.path.isdir(os.path.dirname(tgt)):
                os.makedirs(os.path.dirname(tgt))
            logging.info("Copying %s to %s", obj["location"], tgt)
            with open(tgt, "wb") as f:
                with requests.get(obj["location"], stream=True) as r:
                    for content in r.iter_content(2**16):
                        f.write(content)

        visit_class(deps, ("File",), retrieve)

        req, _ = tool.get_requirement("http://commonwl.org/cwldep#Dependencies")
        if req:
            cwl_deps(installTo, req)

tool = load_tool("sample.cwl", cwltool.context.LoadingContext())

req, _ = tool.get_requirement("http://commonwl.org/cwldep#Dependencies")
if req:
    cwl_deps(os.getcwd(), req)

req, _ = tool.get_requirement("SoftwareRequirement")
if req:
    software_reqs(os.getcwd()+"/SoftwareRequirement", req)
