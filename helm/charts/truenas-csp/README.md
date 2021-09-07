# TrueNAS CORE Container Storage Provider for Kubernetes Helm chart

This Chart provide means to install the dependent [HPE CSI Driver for Kubernetes](https://scod.hpedev.io/csi_driver) to provide persistent storage for Kubernetes workloads using [TrueNAS CORE Container Storage Provider](https://github.com/hpe-storage/truenas-csp).

**Note:** This is a pre-release chart!

## Prerequisites

- Upstream Kubernetes version >= 1.18
- Most Kubernetes distributions are supported
- Recent Ubuntu, SLES, CentOS or RHEL compute nodes connected to their respective official package repositories
- Helm 3 (Version >= 3.6.x required)
- TrueNAS CORE 12 BETA or later
- FreeNAS 11.2-U3 or later

This chart is lock stepped with [HPE CSI Driver for Kubernetes Helm chart](https://artifacthub.io/packages/helm/hpe-storage/hpe-csi-driver) application versions. Other requirements and prerequisites may be found on that chart.

**IMPORTANT:** Do **NOT** install this chart if the HPE CSI Driver for Kubernetes is already installed!

## Configuration and installation

The following table lists the configurable parameters of the chart and their default values.

| Parameter                 | Description                                                            | Default          |
|---------------------------|------------------------------------------------------------------------|------------------|
| logDebug                  | Log extensive debug information on stdout of the CSP                   | false            |

### Installing the chart

To install the chart with the name `my-truenas-csp`:

Add the helm repo:

```
helm repo add truenas-csp https://hpe-storage.github.io/truenas-csp/
helm repo update
```

Install the latest chart:

```
kubectl create ns hpe-storage
helm install my-truenas-csp truenas-csp/truenas-csp -n hpe-storage
```

**Note**: Pay attention to what the latest version of the chart is. If it's labeled with `prerelease` and a "beta" tag, add `--version X.Y.Z` to install a "stable" chart.

### Upgrading the chart

Due to the [helm limitation](https://helm.sh/docs/chart_best_practices/custom_resource_definitions/#some-caveats-and-explanations) to not support upgrade of CRDs between different chart versions, helm chart upgrade is not supported.

Our recommendation is to uninstall the existing chart and install the chart with the desired version. CRDs will be preserved between uninstall and install.

### Uninstalling the chart

To uninstall the `my-truenas-csp` chart:

```
helm uninstall my-truenas-csp -n hpe-storage
```

**Note**: Due to a limitation in Helm, CRDs are not deleted as part of the chart uninstall.

## Using persistent storage to Kubernetes with TrueNAS and FreeNAS

The appliance that is intended to be used with the CSI driver must be configured properly before it can be used. Follow the [INSTALL](https://github.com/hpe-storage/truenas-csp/blob/master/INSTALL.md) document to learn more.

Also, it's helpful to be familiar with [persistent storage concepts](https://kubernetes.io/docs/concepts/storage/volumes/) in Kubernetes prior to deploying stateful workloads.

## Community

Please file any issues, questions or feature requests you may have [here](https://github.com/hpe-storage/truenas-csp/issues) (do not use this facility for support inquiries of your storage product). You may also join our Slack community to chat with some of the HPE folks close to this project. We hang out in `#NimbleStorage`, `#3par-primera`, and `#Kubernetes`. Sign up at [slack.hpedev.io](https://slack.hpedev.io/) and login at [hpedev.slack.com](https://hpedev.slack.com/)

## Contributing

We value all feedback and contributions. If you find any issues or want to contribute, please feel free to open an issue or file a PR. More details in [CONTRIBUTING.md](https://github.com/hpe-storage/truenas-csp/blob/master/CONTRIBUTING.md)

## License

This is open source software licensed using the MIT license. Please see [LICENSE](https://github.com/hpe-storage/truenas-csp/blob/master/LICENSE) for details.
