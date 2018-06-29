from __future__ import print_function
import cwltool.factory
import cwltool.context
import subprocess
import json
import hashlib
import os
from six.moves import urllib
import schema_salad.ref_resolver
from cwltool.process import scandeps, get_schema
from cwltool.load_tool import load_tool
from cwltool.utils import visit_class
from cwltool.command_line_tool import CommandLineTool
import requests
import logging
import sys
from cwltool.docker import DockerCommandLineJob
import tempfile
import shellescape
import shutil
import tarfile
import zipfile
from dateutil.tz import tzlocal
from datetime import datetime
import re
import argparse
import ruamel.yaml
from schema_salad.sourceline import cmap

logging.basicConfig(level=logging.INFO)

CWLDEP_URL = "http://commonwl.org/cwldep#"
CWLDEP_DEPENDENCIES_URL = "{}Dependencies".format(CWLDEP_URL)


def download(tgt, url, version, locks, verified, check_only):
    dltgt = tgt + "_download_"

    rel = os.path.relpath(tgt, os.getcwd())

    logging.info("Fetching %s to %s", url, rel)

    if check_only:
        if not os.path.isfile(tgt) or rel not in locks:
            logging.error("Need install %s", rel)
            return

    with open(dltgt, "wb") as f:
        h = hashlib.sha1()
        with requests.get(url, stream=True) as r:
            for content in r.iter_content(2**16):
                h.update(content)
                f.write(content)
        checksum = h.hexdigest()

    if rel in locks:
        if locks[rel]["checksum"] != checksum:
            logging.warn("Upstream has changed: %s", rel)
        else:
            logging.info("Up to date: %s", rel)

    if check_only:
        return

    os.rename(dltgt, tgt)

    rel = os.path.relpath(tgt, os.getcwd())
    verified[rel] = {
        "upstream": url,
        "version": version,
        "checksum": checksum,
        "retrieved_at": datetime.now(tzlocal()).isoformat(),
        "installed_to": [rel]
    }


def verify(tgt, locks, verified):
    rel = os.path.relpath(tgt, os.getcwd())

    if not os.path.isfile(tgt) or rel not in locks:
        return False

    h = hashlib.sha1()
    with open(tgt, "rb") as f:
        content = f.read(2**16)
        while content:
            h.update(content)
            content = f.read(2**16)
    if h.hexdigest() == locks[rel]["checksum"]:
        verified[rel] = locks[rel]
        return True
    else:
        return False


def load_nocheck(upstream):
    document_loader, workflowobj, uri = cwltool.load_tool.fetch_document(upstream)

    (sch_document_loader, avsc_names) = \
        get_schema(workflowobj["cwlVersion"])[:2]

    cp = sch_document_loader.ctx.copy()
    cp["upstream"] = {
        "@type": "@id"
    }
    sch_document_loader = schema_salad.ref_resolver.Loader(cp)

    document, metadata = sch_document_loader.resolve_all(workflowobj, uri, checklinks=False)

    return document, document_loader


def cwl_deps(basedir, dependencies, locks, verified, operation):
    for d in dependencies["dependencies"]:
        upstream = d["upstream"]
        spup = urllib.parse.urlsplit(upstream)

        if d.get("installTo"):
            installTo = os.path.join(basedir, d.get("installTo"))
        else:
            installTo = os.path.dirname(os.path.join(basedir, spup.netloc, spup.path.lstrip("/")))

        if not os.path.isdir(installTo):
            os.makedirs(installTo)

        if spup.scheme == "http" or spup.scheme == "https":
            tgt = os.path.join(installTo, os.path.basename(spup.path))

            if spup.path.endswith(".cwl"):
                deps = {"class": "File", "location": upstream}  # type: Dict[Text, Any]

                document, document_loader = load_nocheck(upstream)

                def loadref(base, uri):
                    return document_loader.fetch(document_loader.fetcher.urljoin(base, uri))

                document_loader.idx = {}

                sfs = scandeps(
                    upstream, document_loader.fetch(upstream), {"$import", "run"},
                    {"$include", "$schemas", "location"}, loadref)
                if sfs:
                    deps["secondaryFiles"] = sfs

                def retrieve(obj):
                    sploc = urllib.parse.urlsplit(obj["location"])
                    rp = os.path.relpath(sploc.path, os.path.dirname(spup.path))
                    tgt = os.path.join(installTo, rp)
                    if not os.path.isdir(os.path.dirname(tgt)):
                        os.makedirs(os.path.dirname(tgt))
                    if verify(tgt, locks, verified) and operation not in ("update", "check"):
                        return
                    download(tgt, obj["location"], "", locks, verified, operation=="check")

                visit_class(deps, ("File",), retrieve)

                def do_deps(req):
                    cwl_deps(installTo, req, locks, verified, operation)

                visit_class(document, (DEP_NAMESPACE_URL,), do_deps)

            elif spup.path.endswith(".tar.gz") or spup.path.endswith(".tar.bz2") or spup.path.endswith(".zip"):
                download(tgt, upstream, "", locks, verified, operation=="check")
                if spup.path.endswith(".tar.gz"):
                    with tarfile.open(tgt) as t:
                        t.extractall(installTo)
                elif spup.path.endswith(".tar.bz2"):
                    with tarfile.open(tgt) as t:
                        t.extractall(installTo)
                elif spup.path.endswith(".zip"):
                    with zipfile.ZipFile(tgt) as z:
                        z.extractall(installTo)
                rel = os.path.relpath(tgt, os.getcwd())
                verified[rel]["installed_to"] = [tgt, os.path.relpath(ex, os.getcwd())]

            else:
                rq = requests.get(upstream+".git/info/refs?service=git-upload-pack")
                if rq.status_code == 200:
                    if os.path.isdir(os.path.join(tgt, ".git")):
                        subprocess.call(["git", "fetch", "--all"])
                    else:
                        subprocess.call(["git", "clone", upstream, tgt])

                    version = d.get("version")
                    rel = os.path.relpath(tgt, os.getcwd())
                    if rel in locks and operation != "update":
                        version = locks[rel]["version"]

                    if version:
                        print(version)
                        co = subprocess.check_output(["git", "rev-parse", version], cwd=tgt).rstrip()
                        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=tgt).rstrip()
                        head = head.rstrip()
                        if head != co:
                            subprocess.call(["git", "checkout", co], cwd=tgt)
                    commit = subprocess.check_output(["git", "rev-parse", "HEAD"]).rstrip()

                    verified[rel] = {
                        "upstream": upstream,
                        "version": commit,
                        "retrieved_at": datetime.now(tzlocal()).isoformat(),
                        "installed_to": [rel]
                    }

        else:
            logging.error("Scheme %s not supported", spup.scheme)


def expand_ns(namespaces, symbol):
    sp = symbol.split(":", 2)
    if sp[0] in namespaces:
        return namespaces[sp[0]]+"".join(sp[1:])
    else:
        return symbol

def add_dep(fn, upstream, set_version, install_to):
    document_loader, workflowobj, uri = cwltool.load_tool.fetch_document(fn)
    namespaces = workflowobj.get("$namespaces", cmap({}))

    document_loader.idx = {}

    def _add(wf):
        hints = wf.setdefault("hints", {})
        obj = cmap({"upstream": upstream})
        if set_version:
            obj["version"] = set_version
        if install_to:
            obj["installTo"] = install_to
        if isinstance(hints, list):
            for h in hints:
                if expand_ns(namespaces, h["class"]) == DEP_NAMESPACE_URL:
                    for u in h["dependencies"]:
                        if u["upstream"] == upstream:
                            u.update(obj)
                            return
                    h["dependencies"].append(cmap(obj))
                    return
            hints.append(cmap({"class": "dep:Dependencies",
                               "dependencies": [obj]}))
        elif isinstance(hints, dict):
            for h in hints:
                if expand_ns(namespaces, h) == DEP_NAMESPACE_URL:
                    for u in hints[h]["dependencies"]:
                        if u["upstream"] == upstream:
                            u.update(obj)
                            return
                    hints[h]["dependencies"].append(cmap(obj))
                    return
            hints["dep:Dependencies"] = cmap({"dependencies": [obj]})

    visit_class(workflowobj, ("Workflow",), _add)

    namespaces["dep"] = CWLDEP_URL
    workflowobj["$namespaces"] = namespaces

    del workflowobj["id"]

    with open("_"+fn+"_", "w") as f:
        ruamel.yaml.round_trip_dump(workflowobj, f)
    os.rename("_"+fn+"_", fn)


def main():

    parser = argparse.ArgumentParser(
        description='Common Workflow Language dependency managager')
    parser.add_argument("operation", type=str, choices=("install", "update", "clean", "check", "add", "search"))
    parser.add_argument("dependencies", type=str)
    parser.add_argument("upstream", type=str, nargs="?")
    parser.add_argument("--set-version", type=str, default=None)
    parser.add_argument("--install-to", type=str, default=None)

    args = parser.parse_args()

    if args.operation == "add":
        add_dep(args.dependencies, args.upstream, args.set_version, args.install_to)

    if args.operation == "search":
        print("WIP")
        return

    document, document_loader = load_nocheck(args.dependencies)

    lockfile = args.dependencies + ".dep.lock"
    locks = {}
    if os.path.isfile(lockfile):
        with open(lockfile, "r") as l:
            locks = json.load(l)

    verified = {}

    def do_deps(req):
        cwl_deps(os.getcwd(), req, locks, verified, args.operation)

    visit_class(document, (CWLDEP_DEPENDENCIES_URL,), do_deps)

    unref = False
    for l in locks:
        if l not in verified:
            if args.operation == "clean":
                for i in locks[l]["installed_to"]:
                    logging.warn("Removing %s", i)
                    if os.path.isfile(i):
                        os.remove(i)
                    else:
                        shutil.rmtree(i)
            else:
                logging.warn("In cwldep.lock but not referenced: %s", l)
                verified[l] = locks[l]
                unref = True

    if unref:
        logging.warn("Use 'cwldep clean' to delete unused dependencies.")

    with open(lockfile, "w") as l:
        json.dump(verified, l, indent=4, sort_keys=True)

    document_loader.resolve_all(document, args.dependencies, checklinks=True)
