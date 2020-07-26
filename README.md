# TrueNAS CORE Container Storage Provider

The TrueNAS CORE Container Storage Provider (CSP) is an API gateway to provide block storage provisioning using the [HPE CSI Driver for Kubernetes](https://github.com/hpe-storage/csi-driver). It allows you to use [TrueNAS CORE](https://www.truenas.com) to provide persistent storage using iSCSI to Kubernetes.

CSP API endpoints:

- tokens
- hosts
- volumes
- snapshots
- volume_groups (not implemented)
- snapshot_groups (not implemented)

The [CSP specification](https://github.com/hpe-storage/container-storage-provider) in an open specification that supports iSCSI and Fibre Channel protocols.

As of version 1.2.0 of the HPE CSI Driver, these parts of the CSI spec are currently implemented:

- Dynamic Provisioning
- Raw Block Volume
- Volume Expansion
- Data Sources (PersistentVolumeClaims and VolumeSnapshots)
- Ephemeral Local Volumes
- Volume Limits

Volume stats and topology are the two CSI features currently not supported by the HPE CSI Driver.

# Releases

There are currently no releases. Deployments below references the `:edge` tag which is currently under development. Releases will be tagged after the HPE CSI Driver, expect a 1.3.0 release in the near future.

# Install

See [INSTALL](INSTALL.md).

# Building & testing

A Makefile is provided to run the CSP in a local docker container, make sure docker is running and issue:

```
make all
```

The CSP is now listening on localhost:8080

**Important:** When building and testing the CSP locally it will run with debug logging switched on and it will log your API key on stdout in the container.

There are a few adhoc tests provided. Make sure you have a TrueNAS appliance configured with:

- A pool named "tank" 
- iSCSI portal configured as described in the prerequisites

```
make test backend=<IP address of management interface on the TrueNAS appliance> password=<API key>
```

**Note:** None of the tests are comprehensive nor provide full coverage and should be considered equivalent to "Does the light come on?".

# Need help?

Please file an [issue](https://github.com/hpe-storage/truenas-csp/issues). This software is not supported by Hewlett Packard Enterprise. It's a voluntary community effort.

# Contributing

Contributing to the TrueNAS CORE CSP is subject to the following [contributing](CONTRIBUTING.md) guidelines.

# Other Containter Storage Providers for HPE CSI Driver

There's currently no other open source CSPs, but the official HPE CSI Driver for Kubernetes include:

- [HPE Nimble Storage](https://scod.hpedev.io/container_storage_provider/hpe_nimble_storage/index.html)
- [HPE Primera](https://scod.hpedev.io/container_storage_provider/hpe_3par_primera/index.html) (also works for HPE 3PAR)

# Similar projects

The TrueNAS CORE CSP is not the only enabler of TrueNAS CORE for Kubernetes.

- [Democratic CSI](https://github.com/democratic-csi/democratic-csi): A generic OpenZFS CSI driver that supports multiple OpenZFS implementations
- [FreeNAS Provisioner](https://github.com/nmaupu/freenas-provisioner): An external provisioner for FreeNAS NFS exports

# License

TrueNAS CORE CSP is released under the [MIT License](LICENSE).

(C) Copyright 2020 Hewlett Packard Enterprise Development LP.

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
