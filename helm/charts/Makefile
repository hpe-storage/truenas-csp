CHART_TARGET:=../../docs

all: truenas-csp
truenas-csp:
	helm lint $@
	helm package $@ -d .
	helm repo index --merge $(CHART_TARGET)/docs/index.yaml .
	mv *.tgz $(CHART_TARGET)
	mv index.yaml $(CHART_TARGET)
