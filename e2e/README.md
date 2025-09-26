# Synopsis

Performs CSI e2e tests.

```text
kubectl apply -f resources.yaml
kubectl apply -k .
kubectl label node $(kubectl get nodes -ojsonpath={.items[*].metadata.name}) csi.hpe.com/zone=e2e --overwrite
kubectl rollout restart -n hpe-storage ds
kubectl replace --force -f job-rwo.yaml
kubectl replace --force -f job-rwx.yaml
kubectl logs -n csi-e2e job/csi-e2e -f
```
