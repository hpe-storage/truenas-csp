#!/bin/bash

set -xe

if [[ ${ARG_DEBUG} ]]; then
	echo command $@
	exit 0
fi

CUT_DIR=/cut/csi-e2e/tests
PATH=${PATH}:${CUT_DIR}
CUT_SYSTEM=$(uname -s | tr A-Z a-z)
CUT_ARCH=$(uname -m)

if [[ "${FORCE_VERSION}" ]]; then
	CUT_VERSION=${FORCE_VERSION}
else
	CUT_VERSION=$(kubectl version -o json | jq -rM .serverVersion.gitVersion)
fi

if [[ "${CUT_ARCH}" == x86_64 ]]; then
	CUT_ARCH=amd64
fi

if [[ "${CUT_ARCH}" == aarch64 ]]; then
	CUT_ARCH=arm64
fi

if ! [[ -f "e2e.test" ]] || ! [[ -f "ginkgo" ]]; then
	curl --location \
	"https://dl.k8s.io/${CUT_VERSION}/kubernetes-test-${CUT_SYSTEM}-${CUT_ARCH}.tar.gz" | \
	tar --strip-components=3 -zxf - kubernetes/test/bin/e2e.test kubernetes/test/bin/ginkgo
fi

cd tests
../e2e.test $@
