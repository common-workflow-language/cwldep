cwlVersion: v1.0
class: CommandLineTool
requirements:
  SchemaDefRequirement:
    types:
      - name: SoftwarePackage
        type: record
        fields:
          package: string
          version: string[]?
          specs: string[]?
      - name: EnvironmentDef
        type: record
        fields:
          envName: string
          envValue: string
  ShellCommandRequirement: {}
  InlineJavascriptRequirement: {}
inputs:
  packages: SoftwarePackage[]
outputs:
  target:
    type: Directory
    outputBinding:
      glob: venv
  env:
    type: EnvironmentDef[]
    outputBinding:
      outputEval: |
        ${
          return [{"envName": "PATH", "envValue": runtime.outdir+"/venv/bin"},
            {"envName": "VIRTUAL_ENV", "envValue": runtime.outdir+"/venv"}];
        }
arguments:
  - virtualenv
  - venv
  - {valueFrom: "&&", shellQuote: false}
  - "."
  - venv/bin/activate
  - {valueFrom: "&&", shellQuote: false}
  - pip
  - install
  - |
    ${
      var r = [];
      for (var i = 0; i < inputs.packages.length; i++) {
        var p = inputs.packages[i];
        var s = p.package;
        if (p.version) {
          s += "==" + p.version[0];
        }
        r.push(s);
      }
      return r;
    }