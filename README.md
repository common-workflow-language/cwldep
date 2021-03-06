# Common Workflow Language dependency manager

This tool helps you to import tools and workflows from other sources for use in your own workflow.

# Setup
It is highly recommended to setup virtual environment before installing `cwldep`:

```
virtualenv -p python2 venv   # Create a virtual environment, can use `python3` as well
source venv/bin/activate     # Activate environment before installing `cwldep`
```

Install from PyPi:

```
pip install cwldep
```

Install from source:
```
git clone https://github.com/common-workflow-language/cwldep.git # clone cwldep repo
cd cwldep         # Switch to source directory
python setup.py install
cwldep -h  # Check if the installation works correctly
```

# Adding file dependencies

```
cwldep add myfile.cwl https://raw.githubusercontent.com/common-workflow-language/workflows/master/tools/samtools-faidx.cwl
```

This will download the CWL file *and its dependencies* to `raw.githubusercontent.com/common-workflow-language/workflows/master/tools`

Include it in your workflow as a relative file reference:

```
steps:
  step1:
    in: ...
    out: ...
    run: raw.githubusercontent.com/common-workflow-language/workflows/master/tools/samtools-faidx.cwl
```

# Changing the install target

```
cwldep add --install-to samtools myfile.cwl https://raw.githubusercontent.com/common-workflow-language/workflows/master/tools/samtools-faidx.cwl
```

# Using archives

You can also import archives (.tar.gz, .tar.bz2, and .zip):

```
cwldep add myfile.cwl https://github.com/common-workflow-language/workflows/archive/draft2.tar.gz
```

This will download and extract to the local directory `github.com/common-workflow-language/workflows/archive`

# Using git upstream

You can also import git repositories:

```
cwldep add myfile.cwl https://github.com/common-workflow-language/workflows
```

This will clone into the local directory `github.com/common-workflow-language/workflows`

```
cwldep add --set-version=draft-2 myfile.cwl https://github.com/common-workflow-language/workflows
```

# Installing dependencies

This will install any dependencies listed in `myfile.cwl`

```
cwldep install myfile.cwl
```

# Checking if upstream dependencies have changed

This will report if the upstream dependencies listed in `myfile.cwl` have changed

```
cwldep check myfile.cwl
```

# Updating dependencies

This will install updated dependencies:

```
cwldep update myfile.cwl
```

# Deleting unreferenced dependencies

This will delete any dependencies listed in the ".dep.lock" file that are not referenced by `myfile.cwl`.

```
cwldep clean myfile.cwl
```
