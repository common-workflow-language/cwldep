# Common Workflow Language dependency manager

This tool helps you to import tools and workflows from other sources for use in your own workflow.

# Adding dependencies

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

You can also import archives (.tar.gz, .tar.bz2, and .zip):

```
cwldep add myfile.cwl https://github.com/common-workflow-language/workflows/archive/draft2.tar.gz
```

This will download and extract to the local directory `github.com/common-workflow-language/workflows/archive`

You can also import git repositories:

```
cwldep add myfile.cwl https://github.com/common-workflow-language/workflows
```

This will clone into the local directory `github.com/common-workflow-language/workflows`

# Setting git version



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
