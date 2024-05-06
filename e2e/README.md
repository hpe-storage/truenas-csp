# Synopsis

Performs CSI e2e tests.

```text
kubectl apply -f resources.yaml
kubectl apply -k .
kubectl replace --force -f job-rwo.yaml
kubectl replace --force -f job-rwx.yaml
kubectl logs -n csi-e2e job/csi-e2e -f
```
