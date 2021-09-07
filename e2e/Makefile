E2E=./e2e.test

ifndef KUBECONFIG
 $(error KUBECONFIG is not set)
endif

KUBEVER:=$(shell kubectl --kubeconfig ${KUBECONFIG} version -o json | \
	jq .serverVersion.gitVersion)

ifeq ("$(wildcard $(E2E))","")
  $(shell curl --location https://dl.k8s.io/$(KUBEVER)/kubernetes-test-linux-amd64.tar.gz | \
    tar --strip-components=3 -zxf - kubernetes/test/bin/e2e.test kubernetes/test/bin/ginkgo)
endif

all: rwo rwx
rwo: mkreports
	$(E2E) -ginkgo.v \
             -ginkgo.focus='External.Storage' \
	     -ginkgo.skip='\[Feature:|\[Disruptive\]|\[Serial\]' \
             -storage.testdriver=test-driver-rwo.yaml \
             --non-blocking-taints=node-role.kubernetes.io/controlplane,node-role.kubernetes.io/etcd \
	     -report-dir reports

rwx: mkreports
	$(E2E) -ginkgo.v \
             -ginkgo.focus='External.Storage' \
	     -ginkgo.skip='\[Feature:|\[Disruptive\]|\[Serial\]' \
             -storage.testdriver=test-driver-rwx.yaml \
             --non-blocking-taints=node-role.kubernetes.io/controlplane,node-role.kubernetes.io/etcd \
	     -report-dir reports

mkreports: 
	mkdir -p reports

clean:
	rm -rf e2e.test ginkgo reports
