# Install TrueNAS Container Storage Provider

These procedures assumes a running Kubernetes cluster [supported by the HPE CSI Driver](https://scod.hpedev.io/csi_driver/index.html#compatibility_and_support) where the worker nodes have connectivity to a TrueNAS/FreeNAS storage appliance API and networks used for iSCSI traffic. Worker nodes also need their package managers fully functional and connected to their official repos unless iSCSI and multipathing packages have been pre-installed. 

## Prerequisites

- TrueNAS 12.0 or later
- TrueNAS SCALE 22.02 or later
- FreeNAS 11.2-U3 or later
- Helm 3.6 or later (recommended, only needed if using Helm to install the CSP)

### TrueNAS Container Storage Provider Helm Chart

The recommended way to install the CSP is to use Helm, it automatically fulfill all dependencies. Make sure to make it back here to learn [how to configure and use the CSP with the CSI driver](https://github.com/hpe-storage/truenas-csp/blob/master/INSTALL.md#configure-csi-driver).

- Learn more about the Helm chart on [Artifact Hub](https://artifacthub.io/packages/helm/truenas-csp/truenas-csp)

### Install HPE CSI Driver for Kubernetes separately (not recommended)

The HPE CSI Driver may be installed using either a Helm Chart, Operator or directly with manifests. Directly below is the complete procedures for the "[Advanced install](https://scod.hpedev.io/csi_driver/deployment.html#advanced_install)".

**Note:** The [TrueNAS Container Storage Provider Helm Chart](https://artifacthub.io/packages/helm/truenas-csp/truenas-csp) has a dependency on the HPE CSI Driver for Kubernetes Helm Chart and makes it a lot easier to manage configuration during runtime. Consider using Helm to deploy the CSP over the YAML manifests.

Install HPE CSI Driver using manifests (assumes latest supported Kubernetes version of the CSI driver):

```
kubectl create ns hpe-storage
kubectl create -f https://raw.githubusercontent.com/hpe-storage/co-deployments/master/yaml/csi-driver/v2.5.0/hpe-linux-config.yaml
kubectl create -f https://raw.githubusercontent.com/hpe-storage/co-deployments/master/yaml/csi-driver/v2.5.0/hpe-csi-k8s-1.30.yaml
```

Install the TrueNAS CSP using manifests:

```
kubectl create -f https://raw.githubusercontent.com/hpe-storage/truenas-csp/master/K8s/v2.5.1/truenas-csp.yaml
```

**Note:** Replace `hpe-csi-k8s-<version>.yaml` with your version of Kubernetes. Also change the version of the HPE CSI Driver manifests where applicable. Using mismatching versions of the TrueNAS CSP and the HPE CSI Driver will most likely **NOT** work.

### Configure CSI driver

Create a `Secret` that references your TrueNAS/FreeNAS appliance:

```
---
apiVersion: v1
kind: Secret
metadata:
  name: truenas-secret
  namespace: hpe-storage
stringData:
  serviceName: truenas-csp-svc
  servicePort: "8080"
  username: hpe-csi (username is a no-op when using API key)
  password: API key or root password of TrueNAS/FreeNAS appliance
  backend: Management IP address of TrueNAS/FreeNAS appliance
```

**Hint:** Generate an API key by clicking the cog in the upper right corner of the TrueNAS web UI (FreeNAS does NOT support API keys). What you name the key or the `Secret` `{.stringData.username}` does not matter as it's not being used or referenced during runtime. For tracking purposes it might be a good idea to name the key the same as the username put into the `Secret`.

### Configure TrueNAS/FreeNAS

The TrueNAS/FreeNAS appliance require an iSCSI portal to be configured manually with the following characteristics:

![](https://hpe-storage.github.io/truenas-csp/assets/portal.png)

- Description: `hpe-csi`
- IP Address: List of IPs used for iSCSI (do **NOT** use 0.0.0.0)

The Target Global Configuration needs to have an explicit Base Name:

![](https://hpe-storage.github.io/truenas-csp/assets/global-target.png)

- Base Name: `iqn.2011-08.org.truenas.ctl` or `iqn.2005-10.org.freenas.ctl`

**Hint:** If TrueNAS/FreeNAS is not giving you the option to select nothing but 0.0.0.0 in the portal configuration is because DHCP is being used. Only statically assigned addresses can be used in the picker.

Also make sure the iSCSI service is started and enabled at boot on TrueNAS/FreeNAS.

The default location for CSI volumes will be in the root of a pool named `tank`. That is most likely not desirable, instead, create a dataset in any of your pools and make note of that, i.e `zwimming/csi-volumes` and configure `root` in the `StorageClass`.

## Example StorageClass

All the ZVols created on TrueNAS/FreeNAS will by default be created with these parameters:

- volblocksize: 8K
- deduplication: OFF
- compression: LZ4
- sparse: "true"
- sync: STANDARD
- description: "Dataset created by HPE CSI Driver for Kubernetes as {pv} in {namespace} from {pvc}"
- root: tank

These parameters may be overridden in the `StorageClass` or have the defaults altered by passing environment variables to the CSP runtime with the convention of `DEFAULT_COMPRESSION=OFF`. 

Refer to the TrueNAS/FreeNAS documentation what these dataset parameters do.

**Note:** Since the iSCSI volumes are backed by ZVols, `volblocksize` will be immutable.

```
---
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  annotations:
    storageclass.kubernetes.io/is-default-class: "true"
  name: hpe-storageclass
provisioner: csi.hpe.com
parameters:
  csi.storage.k8s.io/controller-expand-secret-name: truenas-secret
  csi.storage.k8s.io/controller-expand-secret-namespace: hpe-storage
  csi.storage.k8s.io/controller-publish-secret-name: truenas-secret
  csi.storage.k8s.io/controller-publish-secret-namespace: hpe-storage
  csi.storage.k8s.io/node-publish-secret-name: truenas-secret
  csi.storage.k8s.io/node-publish-secret-namespace: hpe-storage
  csi.storage.k8s.io/node-stage-secret-name: truenas-secret
  csi.storage.k8s.io/node-stage-secret-namespace: hpe-storage
  csi.storage.k8s.io/provisioner-secret-name: truenas-secret
  csi.storage.k8s.io/provisioner-secret-namespace: hpe-storage
  csi.storage.k8s.io/fstype: xfs
  allowOverrides: sparse,compression,deduplication,volblocksize,sync,description
  root: zwimming/csi-volumes
reclaimPolicy: Delete
allowVolumeExpansion: true
```

Set `root` to a dataset that will serve as the base dataset where the ZVols will be created. The `allowOverrides` parameter will allow users to annotate their PVCs with the values that makes sense for their workload. [Learn more here](https://scod.hpedev.io/csi_driver/using.html#using_pvc_overrides).

**Important:** Do NOT use underscore "`_`" in your root dataset for now, it will most likely break.

Once the `Secret` and `StorageClass` have been created, all functionality is provided by the HPE CSI Driver and is [documented here](https://scod.hpedev.io/csi_driver/using.html).

**Tip:** If `VolumeSnapshots` are needed, follow the guidance in HPE CSI Driver documentation on how to [enable CSI snapshots](https://scod.hpedev.io/csi_driver/using.html#enabling_csi_snapshots) and [how to use them](https://scod.hpedev.io/csi_driver/using.html#using_csi_snapshots).

## CHAP support

From v2.5.1 onwards iSCSI CHAP is supported. Follow the [guidance provided by HPE](https://scod.hpedev.io/csi_driver/index.html#iscsi_chap_considerations). Retrofitting CHAP into an existing cluster is not recommended. Bi-directional CHAP is not supported by the HPE CSI Driver and will not work with the TrueNAS CSP.

CHAP on TrueNAS uses a hardcoded tag (4730274) for the authorization on the appliance. As long as that authorization exist on the appliance, CHAP details will be returned to the CSI driver and attempted to connect to the target. Do not create this tag manually, it will be created by TrueNAS CSP when enabled in the HPE CSI Driver.

**Important:** If you need to rotate the CHAP authorization it's recommended to scale down all workloads, change the `Secret`, and scale the workloads up again. Otherwise existing iSCSI sessions may break.
