cwlVersion: v1.0
class: CommandLineTool
$namespaces:
  deps: "http://commonwl.org/cwldep#"
hints:
  SoftwareRequirement:
    packages:
      - package: arvados-python-client
  deps:Dependencies:
    dependencies:
      - upstream: https://raw.githubusercontent.com/common-workflow-language/workflows/master/tools/samtools-faidx.cwl
inputs: []
outputs: []
baseCommand: echo
