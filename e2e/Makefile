E2E=./e2e.test
TEST_PREFIX=External.Storage.\[Driver:.csi.hpe.com\].*
FOCUS=
SYSTEM=$(shell uname -s | tr A-Z a-z)
ARCH=$(shell uname -m)
ifeq ($(ARCH), x86_64)
 ARCH=amd64
endif

all: rwo rwx
dl: kcfg
ifeq ("$(wildcard $(E2E))","")
	$(shell curl --location https://dl.k8s.io/$(KUBEVER)/kubernetes-test-$(SYSTEM)-$(ARCH).tar.gz | \
	tar --strip-components=3 -zxf - kubernetes/test/bin/e2e.test kubernetes/test/bin/ginkgo)
endif

kcfg:
ifeq ("$(wildcard $(KUBECONFIG))","")
	$(error KUBECONFIG is not set)
	exit
endif
ifndef KUBEVER
  KUBEVER:=$(shell kubectl --kubeconfig ${KUBECONFIG} version -o json | jq .serverVersion.gitVersion)
endif

rwo: dl
	mkdir -p reports-rwo
	$(E2E) --ginkgo.v \
	       --ginkgo.timeout=12h \
               --ginkgo.focus='$(TEST_PREFIX)$(FOCUS)' \
	       --ginkgo.skip='\[Disruptive\]|\[Serial\]' \
               --non-blocking-taints=node-role.kubernetes.io/control-plane,node-role.kubernetes.io/etcd,node-role.kubernetes.io/master \
               -storage.testdriver=test-driver-rwo.yaml \
	       -report-dir=reports-rwo

rwx: dl
	mkdir -p reports-rwx
	$(E2E) --ginkgo.v \
	       --ginkgo.timeout=12h \
               --ginkgo.focus='$(TEST_PREFIX)$(FOCUS)' \
	       --ginkgo.skip='\[Feature:|\[Disruptive\]|\[Serial\]' \
	       --ginkgo.skip='.phemeral' \
               --non-blocking-taints=node-role.kubernetes.io/control-plane,node-role.kubernetes.io/etcd,node-role.kubernetes.io/master \
               --ginkgo.timeout=8h \
               -storage.testdriver=test-driver-rwx.yaml \
	       -report-dir=reports-rwx

clean:
	rm -rf e2e.test ginkgo reports-rwo reports-rwx
