# CLI commands used in the demo

Before running those, make sure you are connected to the right project!

```bash
oc project xrayedge
```

## Patch image-generator with seconds_wait

Change "value" for the number of seconds to waitr between each image upload. It can be less than a second (e.g. "0.1"). Value "0" stops the image-generator.

```bash
oc patch dc image-generator --type=json -p '[{"op":"replace","path":"/spec/template/spec/containers/0/env/0/value","value":"1"}]'
```

## Patch risk-assessment with revision

Change "value" with the name of the model revision you wan to simulate. It only updates the service annotation, but if a new image has been previously pushed it will use this new one. So that's a way to "force-refresh" your risk-assessment service.

```bash
oc patch service.serving.knative.dev/risk-assessment --type=json -p '[{"op":"replace","path":"/spec/template/metadata/annotations/revisionTimestamp","value":"'"$(date +%F_%T)"'"},{"op":"replace","path":"/spec/template/spec/containers/0/env/0/value","value":"v1"}]'
```

## Update image-generator with seconds_wait (tkn version of the previous one)

```bash
tkn task start oc-update-image-generator-dc -p seconds_wait=1
```

## Change risk-assessment service version (tkn version of the previous one)

```bash
tkn pipeline start knative-service-risk-assessment-refresh -p service-name=risk-assessment -p model-version=v1
```

## Build image-server image

Launches the pipeline that will build the image-server container image.

```bash
tkn pipeline start image-build -r git-repo=xrayedge-repo -r push-image=image-server-image -p context=./demos/xrayedge/containers/image-server
```
