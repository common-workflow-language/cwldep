import cwltool.factory
import cwltool.context
import subprocess
import json
import hashlib
import os
import urlparse
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

logging.basicConfig(level=logging.INFO)

def download(tgt, url, version, locks, verified, check_only):
    dltgt = tgt + "_download_"

    rel = os.path.relpath(tgt, os.getcwd())

    logging.info("Fetching %s to %s", url, rel)

    if check_only:
        if not os.path.isfile(tgt) or rel not in locks:
            logging.error("Needs install %s", rel)
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

                document_loader, workflowobj, uri = cwltool.load_tool.fetch_document(upstream)

                (sch_document_loader, avsc_names) = \
                    get_schema(workflowobj["cwlVersion"])[:2]

                document, metadata = sch_document_loader.resolve_all(workflowobj, uri, checklinks=False)

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

                visit_class(document, ("http://commonwl.org/cwldep#Dependencies",), do_deps)

            elif spup.path.endswith(".tar.gz") or spup.path.endswith(".tar.bz2") or spup.path.endswith(".zip"):
                download(tgt, upstream, "", locks, verified, operation=="check")
                if spup.path.endswith(".tar.gz") or spup.path.endswith(".tar.bz2"):
                    with tarfile.open(tgt) as t:
                        t.extractall(installTo)
                elif spup.path.endswith(".zip"):
                    with zipfile.ZipFile(tgt) as z:
                        z.extractall(installTo)
                rel = os.path.relpath(tgt, os.getcwd())
                verified[rel]["installed_to"] = [tgt, os.path.relpath(installTo, os.getcwd())]

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

                    head = subprocess.check_output(["git", "rev-parse", "HEAD"])
                    if head != version:
                        if re.match(r"^[0-9a-f]{40}$", version):
                            subprocess.call(["git", "checkout", version], cwd=tgt)
                        else:
                            subprocess.call(["git", "checkout", "origin/"+version], cwd=tgt)
                    commit = subprocess.check_output(["git", "rev-parse", "HEAD"])

                    verified[rel] = {
                        "upstream": upstream,
                        "version": commit,
                        "retrieved_at": datetime.now(tzlocal()).isoformat(),
                        "installed_to": [rel]
                    }

        else:
            logging.error("Scheme %s not supported", spup.scheme)

def main():

    parser = argparse.ArgumentParser(
        description='Reference executor for Common Workflow Language standards.')
    parser.add_argument("operation", type=str, choices=("install", "update", "clean", "check"))
    parser.add_argument("dependencies", type=str)

    args = parser.parse_args()

    document_loader, workflowobj, uri = cwltool.load_tool.fetch_document(args.dependencies)

    (sch_document_loader, avsc_names) = \
        get_schema(workflowobj["cwlVersion"])[:2]

    document, metadata = sch_document_loader.resolve_all(workflowobj, uri, checklinks=False)

    locks = {}
    if os.path.isfile("cwldep.lock"):
        with open("cwldep.lock", "r") as l:
            locks = json.load(l)

    verified = {}

    def do_deps(req):
        cwl_deps(os.getcwd(), req, locks, verified, args.operation)

    visit_class(document, ("http://commonwl.org/cwldep#Dependencies",), do_deps)

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

    with open("cwldep.lock", "w") as l:
        json.dump(verified, l, indent=4, sort_keys=True)

    document, metadata = sch_document_loader.resolve_all(workflowobj, uri, checklinks=True)


main()
