E2E=./e2e.test
TEST_PREFIX=External.Storage.\[Driver:.csi.hpe.com\].*
FOCUS=

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
rwo:
	mkdir -p reports-rw0
	$(E2E) --ginkgo.v \
               --ginkgo.focus='$(TEST_PREFIX)$(FOCUS)' \
	       --ginkgo.skip='\[Feature:|\[Disruptive\]|\[Serial\]' \
               --non-blocking-taints=node-role.kubernetes.io/control-plane,node-role.kubernetes.io/etcd,node-role.kubernetes.io/master \
               --ginkgo.timeout=8h \
               -storage.testdriver=test-driver-rwo.yaml \
	       -report-dir=reports-rwo
rwx:
	mkdir -p reports-rwx
	$(E2E) --ginkgo.v \
               --ginkgo.focus='$(TEST_PREFIX)$(FOCUS)' \
	       --ginkgo.skip='\[Feature:|\[Disruptive\]|\[Serial\]' \
	       --ginkgo.skip='.phemeral' \
               --non-blocking-taints=node-role.kubernetes.io/control-plane,node-role.kubernetes.io/etcd,node-role.kubernetes.io/master \
               --ginkgo.timeout=8h \
               -storage.testdriver=test-driver-rwx.yaml \
	       -report-dir=reports-rwx
clean:
	rm -rf e2e.test ginkgo reports-rwo reports-rwx
