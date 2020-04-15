# Various CLI commands for the demo

## Patch image-generator with seconds_wait

```bash
oc patch dc image-generator --type=json -p '[{"op":"replace","path":"/spec/template/spec/containers/0/env/0/value","value":"1"}]'
```

## Update image-generator with seconds_wait (tkn version of previous one)

```bash
tkn task start oc-update-image-generator-dc -p seconds_wait=1
```

## Change risk-assessment service version

```bash
tkn pipeline start knative-service-risk-assessment-refresh -p service-name=risk-assessment -p model-version=v1
```

## Build image-server image

```bash
tkn pipeline start image-build -r git-repo=xrayedge-repo -r push-image=image-server-image -p context=./demos/xrayedge/containers/image-server
```
