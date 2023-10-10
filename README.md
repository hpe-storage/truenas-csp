# TrueNAS Container Storage Provider

The TrueNAS Container Storage Provider (CSP) is an API gateway to provide iSCSI block storage provisioning using the [HPE CSI Driver for Kubernetes](https://github.com/hpe-storage/csi-driver). It allows you to use [TrueNAS](https://www.truenas.com) and [FreeNAS](https://www.freenas.org/) to provide persistent storage using iSCSI to Kubernetes.

CSP API endpoints:

- tokens
- hosts
- volumes
- snapshots
- volume_groups (not implemented)
- snapshot_groups (not implemented)

The [CSP specification](https://github.com/hpe-storage/container-storage-provider) in an open specification that supports iSCSI and Fibre Channel protocols.

As of version 2.2.0 of the HPE CSI Driver, these parts of the CSI spec are currently implemented:

- Dynamic Provisioning
- Raw Block Volume
- Volume Expansion
- Data Sources (`PersistentVolumeClaims` and `VolumeSnapshots`)
- Volume Limits
- Volume Stats
- Ephemeral Local Volumes (not supported by the TrueNAS CSP, see [limitations](#limitations))

Topology is currently not supported by the HPE CSI Driver.

# Releases

Releases will track the upstream versioning of the HPE CSI Driver for Kubernetes and potential bugfixes in the TrueNAS CSP will be pushed to the same image tag matching the HPE CSI Driver version.

* [TrueNAS CSP v2.4.0](https://github.com/hpe-storage/truenas-csp/releases/tag/v2.4.0) for HPE CSI Driver v2.4.0
* [TrueNAS CSP v2.3.10](https://github.com/hpe-storage/truenas-csp/releases/tag/v2.3.10) for HPE CSI Driver v2.3.0
* [TrueNAS CSP v2.3.0](https://github.com/hpe-storage/truenas-csp/releases/tag/v2.3.0) for HPE CSI Driver v2.3.0
* [TrueNAS CSP v2.2.0](https://github.com/hpe-storage/truenas-csp/releases/tag/v2.2.0) for HPE CSI Driver v2.2.0
* [TrueNAS CSP v2.1.1](https://github.com/hpe-storage/truenas-csp/releases/tag/v2.1.1) for HPE CSI Driver v2.1.1
* [TrueNAS CSP v2.1.0](https://github.com/hpe-storage/truenas-csp/releases/tag/v2.1.0) for HPE CSI Driver v2.1.0
* [TrueNAS CORE CSP v2.0.0](https://github.com/hpe-storage/truenas-csp/releases/tag/v2.0.0) for HPE CSI Driver v2.0.0
* [TrueNAS CORE CSP v1.4.0](https://github.com/hpe-storage/truenas-csp/releases/tag/v1.4.0) for HPE CSI Driver v1.4.0
* [TrueNAS CORE CSP v1.3.0](https://github.com/hpe-storage/truenas-csp/releases/tag/v1.3.0) for HPE CSI Driver v1.3.0

# Version schemes

The TrueNAS CSP will track an official release of the HPE CSI Driver for Kubernetes, i.e v2.2.0 and there will be a subsequent release of the TrueNAS CSP v2.2.0. If a patch release of the CSP is needed, the patch position will be incremented by 10. I.e v2.2.10. The last digit will represent the patch version of the CSI driver. The [Helm chart](https://artifacthub.io/packages/helm/truenas-csp/truenas-csp) is it's own deliverable and has its own semantic versioning.

# Install

See [INSTALL](INSTALL.md).

# Building & testing

A Makefile is provided to run the CSP in a local docker container, make sure docker is running and issue:

```
make all run
```

The CSP is now listening on localhost:8080

**Note:** When building and testing the CSP locally it will run with debug logging switched on.

There are a few adhoc tests provided. Make sure you have a TrueNAS/FreeNAS appliance configured with:

- A pool named "tank" 
- iSCSI portal configured as described in the [prerequisites](INSTALL.md#prerequisites).

```
make test backend=<IP address of management interface on the TrueNAS appliance> password=<API key>
```

**Note:** None of the tests are comprehensive nor provide full coverage and should be considered equivalent to "Does the light come on?".

A Kubernetes e2e test `Makefile` is provided in [e2e](e2e) for both RWO and RWX modes. Ensure everything is [installed](INSTALL.md) and a `Secret` named "truenas-secret" exists in the "hpe-storage" `Namespace`. Then run:

```
cd e2e
make rwo
make rwx
make clean
```

**Note:** FreeNAS, TrueNAS CORE and SCALE should pass all tests when configured properly.

# Limitations

These are the known limitations.

- **Ephemeral Local Volumes:** Due to how TrueNAS handles ZVol names internally and the long names generated by the HPE CSI Driver when requesting ephemeral storage, Ephemeral Local Volumes is not compatible with the TrueNAS CSP. Generic Ephemeral Volumes introduced as an Alpha feature in Kubernetes 1.19 works as the volumes are derived from a regular `StorageClass`.
- **Volume sizing:** TrueNAS ZVols "volblocksize" need to be even divisible by the requesting volume size. This is a non-issue if you're working with even "Gi" sizes in the `PersistentVolumeClaims`. It gets hairy if working with "Mi" sizes and large volume block sizes.
- **Dataset naming:** The underscore character `_` is used as an internal separator for naming snapshots and datasets. Do NOT use underscores in your pool or dataset names.
- **FreeNAS ctl_max_luns:** FreeNAS has an internal limit of 1024 LUNs. That number increments for every new LUN created, even if deleted. The iSCSI Target service won't start and it leads to all sorts of problems. This is the log message on the console: `requested LUN ID 1031 is higher than ctl_max_luns` (this system had two iSCSI Targets).
- **FreeNAS iSCSI Target:** On systems with a high degree of churn, especially during e2e testing, the iSCSI Target sometimes croak and needs to be restarted. It's recommended to starve the CSP to ease the API requests against FreeNAS and let failures be handled by CSI driver and Kubernetes (see [Helm chart](https://artifacthub.io/packages/helm/truenas-csp/truenas-csp)).

# Need help?

Please file an [issue](https://github.com/hpe-storage/truenas-csp/issues). This software is not supported by Hewlett Packard Enterprise. It's a voluntary community effort.

# Contributing

Contributing to the TrueNAS CSP is subject to the following [contributing](CONTRIBUTING.md) guidelines.

# Other Container Storage Providers for HPE CSI Driver

There's currently no other open source CSPs, but the official HPE CSI Driver for Kubernetes include:

- [HPE Alletra 5000/6000 and Nimble Storage](https://scod.hpedev.io/container_storage_provider/hpe_nimble_storage/index.html)
- [HPE Alletra 9000 and Primera (including 3PAR)](https://scod.hpedev.io/container_storage_provider/hpe_3par_primera/index.html)

# Similar projects

The TrueNAS CSP is not the only enabler of TrueNAS/FreeNAS for Kubernetes.

- [Democratic CSI](https://github.com/democratic-csi/democratic-csi): A generic OpenZFS CSI driver that supports multiple OpenZFS implementations
- [FreeNAS Provisioner](https://github.com/nmaupu/freenas-provisioner): An external provisioner for FreeNAS NFS exports

# License

TrueNAS(R) (C) 2023 iXsystems, Inc.

TrueNAS CORE(R) (C) 2023 iXsystems, Inc.

TrueNAS SCALE(R) (C) 2023 iXsystems, Inc.

FreeNAS(R) is (C) 2011-2023 iXsystems

TrueNAS CSP is released under the [MIT License](LICENSE).

(C) Copyright 2023 Hewlett Packard Enterprise Development LP.

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
