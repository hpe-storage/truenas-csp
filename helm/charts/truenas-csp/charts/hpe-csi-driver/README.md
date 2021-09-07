# HPE CSI Driver for Kubernetes Helm chart

The [HPE CSI Driver for Kubernetes](https://scod.hpedev.io/csi_driver/index.html) leverages Hewlett Packard Enterprise storage platforms to provide scalable and persistent storage for stateful applications.

## Prerequisites

- Upstream Kubernetes version >= 1.18
- Most Kubernetes distributions are supported
- Recent Ubuntu, SLES, CentOS or RHEL compute nodes connected to their respective official package repositories
- Helm 3 (Version >= 3.2.0 required)

Depending on which [Container Storage Provider](https://scod.hpedev.io/container_storage_provider/index.html) (CSP) is being used, other prerequisites and requirements may apply, such as storage platform OS and features.

- [HPE Alletra 6000 and Nimble Storage](https://scod.hpedev.io/container_storage_provider/hpe_nimble_storage/index.html)
- [HPE Alletra 9000, Primera and 3PAR](https://scod.hpedev.io/container_storage_provider/hpe_3par_primera/index.html)

## Configuration and installation

The following table lists the configurable parameters of the chart and their default values.

| Parameter                 | Description                                                            | Default          |
|---------------------------|------------------------------------------------------------------------|------------------|
| disable.nimble            | Disable HPE Nimble Storage CSP `Service`.                              | false            |
| disable.primera           | Disable HPE Primera (and 3PAR) CSP `Service`.                          | false            |
| disable.alletra6000       | Disable HPE Alletra 6000 CSP `Service`.                                | false            |
| disable.alletra9000       | Disable HPE Alletra 9000 CSP `Service`.                                | false            |
| disableNodeConformance    | Disable automatic installation of iSCSI/Multipath Packages.            | false            |
| disableNodeGetVolumeStats | Disable NodeGetVolumeStats call to CSI driver.                         | false            |
| imagePullPolicy           | Image pull policy (`Always`, `IfNotPresent`, `Never`).                 | IfNotPresent     |
| iscsi.chapUser            | Username for iSCSI CHAP authentication.                                | ""               |
| iscsi.chapPassword        | Password for iSCSI CHAP authentication.                                | ""               |
| logLevel                  | Log level. Can be one of `info`, `debug`, `trace`, `warn` and `error`. | info             |
| registry                  | Registry to pull HPE CSI Driver container images from.                 | quay.io          |
| kubeletRootDir            | The kubelet root directory path.                                       | /var/lib/kubelet |
| cspClientTimeout          | CSP client timeout for HPE Alletra 9000, Primera and 3PAR (60-360 sec).| 60               |

It's recommended to create a [values.yaml](https://github.com/hpe-storage/co-deployments/blob/master/helm/values/csi-driver) file from the corresponding release of the chart and edit it to fit the environment the chart is being deployed to. Download and edit [a sample file](https://github.com/hpe-storage/co-deployments/blob/master/helm/values/csi-driver).

These are the bare minimum required parameters for a successful deployment to an iSCSI environment if CHAP authentication is required.

```
iscsi:
  chapUser: "<username>"
  chapPassword: "<password>"
```

Tweak any additional parameters to suit the environment or as prescribed by HPE.

### Installing the chart

To install the chart with the name `my-hpe-csi-driver`:

Add HPE helm repo:

```
helm repo add hpe-storage https://hpe-storage.github.io/co-deployments/
helm repo update
```

Install the latest chart:

```
kubectl create ns hpe-storage
helm install my-hpe-csi-driver hpe-storage/hpe-csi-driver -n hpe-storage -f myvalues.yaml
```

**Note**: `myvalues.yaml` is optional if no parameters are overridden from defaults. Also pay attention to what the latest version of the chart is. If it's labeled with `pre-prelease` and a "beta" tag, add `--version X.Y.Z` to install a "stable" chart.

### Upgrading the chart

Due to the [helm limitation](https://helm.sh/docs/chart_best_practices/custom_resource_definitions/#some-caveats-and-explanations) to not support upgrade of CRDs between different chart versions, helm chart upgrade is not supported.

Our recommendation is to uninstall the existing chart and install the chart with the desired version. CRDs will be preserved between uninstall and install.

### Uninstalling the chart

To uninstall the `my-hpe-csi-driver` chart:

```
helm uninstall my-hpe-csi-driver -n hpe-storage
```

**Note**: Due to a limitation in Helm, CRDs are not deleted as part of the chart uninstall.

### Alternative install method

In some cases it's more practical to provide the local configuration via the `helm` CLI directly. Specify each parameter using the `--set key=value[,key=value]` argument to `helm install`. These will take precedence over entries in [values.yaml](https://github.com/hpe-storage/co-deployments/blob/master/helm/values/csi-driver). For example:

```
helm install my-hpe-csi-driver hpe-storage/hpe-csi-driver -n hpe-storage \
  --set iscsi.chapUsername=admin \
  --set iscsi.chapPassword=xxxxxxxx
```

## Using persistent storage with Kubernetes

Enable dynamic provisioning of persistent storage by creating a `StorageClass` API object that references a `Secret` which maps to a supported HPE primary storage backend. Refer to the [HPE CSI Driver for Kubernetes](https://scod.hpedev.io/csi_driver/deployment.html#add_a_hpe_storage_backend) documentation on [HPE Storage Container Orchestration Documentation](https://scod.hpedev.io/). Also, it's helpful to be familiar with [persistent storage concepts](https://kubernetes.io/docs/concepts/storage/volumes/) in Kubernetes prior to deploying stateful workloads.

## Support

The HPE CSI Driver for Kubernetes Helm chart is fully supported by HPE.

Formal support statements for each HPE supported CSP is [available on SCOD](https://scod.hpedev.io/legal/support). Use this facility for formal support of your HPE storage products, including the Helm chart.

## Community

Please file any issues, questions or feature requests you may have [here](https://github.com/hpe-storage/co-deployments/issues) (do not use this facility for support inquiries of your HPE storage product, see [SCOD](https://scod.hpedev.io/legal/support) for support). You may also join our Slack community to chat with HPE folks close to this project. We hang out in `#NimbleStorage`, `#3par-primera`, and `#Kubernetes`. Sign up at [slack.hpedev.io](https://slack.hpedev.io/) and login at [hpedev.slack.com](https://hpedev.slack.com/)

## Contributing

We value all feedback and contributions. If you find any issues or want to contribute, please feel free to open an issue or file a PR. More details in [CONTRIBUTING.md](https://github.com/hpe-storage/co-deployments/blob/master/CONTRIBUTING.md)

## License

This is open source software licensed using the Apache License 2.0. Please see [LICENSE](https://github.com/hpe-storage/co-deployments/blob/master/LICENSE) for details.
