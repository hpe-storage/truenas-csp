CHART_TARGET:=../../docs

.PHONY: truenas-csp
all: truenas-csp
truenas-csp:
	helm dependency update $@
	helm dependency build $@
	helm lint $@
	helm package $@ -d .
	helm repo index --merge $(CHART_TARGET)/index.yaml .
	mv *.tgz $(CHART_TARGET)
	mv index.yaml $(CHART_TARGET)
