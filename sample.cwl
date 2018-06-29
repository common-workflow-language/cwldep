cwlVersion: v1.0
class: Workflow
$namespaces:
  dep: http://commonwl.org/cwldep#
#hints:
#  dep:Dependencies:
#    dependencies:
#      - upstream: https://raw.githubusercontent.com/common-workflow-language/workflows/master/tools/samtools-faidx.cwl
#       - upstream: https://github.com/common-workflow-language/workflows
#         version: master
#      - upstream: https://github.com/common-workflow-language/workflows/archive/draft2.zip
#      - upstream: https://github.com/common-workflow-language/workflows/archive/draft2.tar.gz
inputs: []
outputs: []
steps:
  step1:
    in: []
    out: []
    run: raw.githubusercontent.com/common-workflow-language/workflows/master/tools/samtools-faidx.cwl
id: file:///home/peter/work/cwldep/sample.cwl
hints:
  dep:Dependencies:
    dependencies:
    - upstream: https://raw.githubusercontent.com/common-workflow-language/workflows/master/tools/samtools-faidx.cwl
#    run: github.com/common-workflow-language/workflows/archive/workflows-draft2/tools/samtools-faidx.cwl
