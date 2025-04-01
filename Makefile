ifndef IMAGE_TAG
	IMAGE_TAG ?= edge
endif

ifndef REPO_NAME
	REPO_NAME ?= quay.io/datamattsson/truenas-csp
endif

username = hpe-csi
csp = http://localhost:8080
curl = curl
curl_args = '-v'

all:
	python3 -m py_compile truenascsp/*.py
	rm -rf truenascsp/__pycache__
	docker build -t $(REPO_NAME):$(IMAGE_TAG) .
push:
	docker buildx build --platform=linux/amd64,linux/arm64 --progress=plain \
                --provenance=false --push -t $(REPO_NAME):$(IMAGE_TAG) .
run:
	docker rm -f truenas-csp || true
	docker run -d -p8080:8080 --name truenas-csp -e LOG_DEBUG=1 \
		--pull=always $(REPO_NAME):$(IMAGE_TAG)

test:

	# Delete host 1
	- $(curl) $(curl_args) -XDELETE -H 'Content-Type: application/json' -H 'X-Auth-Token: $(password)' \
		-H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/hosts/41302701-0196-420f-b319-834a79891db0 -f

	# Delete host 2
	- $(curl) $(curl_args) -XDELETE -H 'Content-Type: application/json' -H 'X-Auth-Token: $(password)' \
		-H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/hosts/41302701-0196-420f-b319-834a79891db1 -f

	# Delete host 3
	- $(curl) $(curl_args) -XDELETE -H 'Content-Type: application/json' \
		-H 'X-Auth-Token: $(password)' -H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/hosts/41302701-0196-420f-b319-834a79891db2 -f

	# Unpublish volume host 1
	- $(curl) $(curl_args) -XPUT -d @tests/csp/unpublish.yaml -H 'Content-Type: application/json' \
		-H 'X-Auth-Token: $(password)' -H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/volumes/tank_my-new-volume16/actions/unpublish -f

	# Unpublish volume host 2
	- $(curl) $(curl_args) -XPUT -d @tests/csp/unpublish-multi.yaml -H 'Content-Type: application/json' \
		-H 'X-Auth-Token: $(password)' -H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/volumes/tank_my-new-volume16/actions/unpublish -f

	# Unpublish CHAP volume
	- $(curl) $(curl_args) -XPUT -d @tests/csp/unpublish-chap.yaml -H 'Content-Type: application/json' \
		-H 'X-Auth-Token: $(password)' -H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/volumes/tank_my-new-volume377/actions/unpublish -f

	# Delete volume
	- $(curl) $(curl_args) -XDELETE -H 'Content-Type: application/json' -H 'X-Auth-Token: $(password)' \
		-H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/volumes/tank_my-new-volume16 -f

	# Delete thick volume
	- $(curl) $(curl_args) -XDELETE -H 'Content-Type: application/json' \
		-H 'X-Auth-Token: $(password)' -H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/volumes/tank_my-new-volume18 -f

	# Delete CHAP volume
	- $(curl) $(curl_args) -XDELETE -H 'Content-Type: application/json' \
		-H 'X-Auth-Token: $(password)' -H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/volumes/tank_my-new-volume377 -f

	# "Create" password
	$(curl) $(curl_args) -XPOST \
		-d '{ "array_ip": "$(backend)", "username": "$(username)", "password": "$(password)"}' \
		-H 'Content-Type: application/json' $(csp)/containers/v1/tokens -f

	# Delete password
	$(curl) $(curl_args) -XDELETE -H 'Content-Type: application/json' $(csp)/containers/v1/tokens/123 -f

	# Fail auth
	$(curl) $(curl_args) -XGET -H 'Content-Type: application/json' $(csp)/containers/v1/tokens/123 -f || true

	# Create host 1
	$(curl) $(curl_args) -XPOST -d @tests/csp/initiator.yaml -H 'Content-Type: application/json' \
		-H 'X-Auth-Token: $(password)' -H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/hosts -f

	# Create host 2
	$(curl) $(curl_args) -XPOST -d @tests/csp/initiator-multi.yaml -H 'Content-Type: application/json' \
		-H 'X-Auth-Token: $(password)' -H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/hosts -f

	# Create volume
	$(curl) $(curl_args) -XPOST -d @tests/csp/volume.yaml -H 'Content-Type: application/json' \
		-H 'X-Auth-Token: $(password)' -H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/volumes -f

        # List snapshots
	- $(curl) $(curl_args) -H 'Content-Type: application/json' \
		-H 'X-Auth-Token: $(password)' -H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/snapshots?volume_id=tank_my-new-volume16 -f

	# Create thick volume
	$(curl) $(curl_args) -XPOST -d @tests/csp/volume-thick.yaml -H 'Content-Type: application/json' \
		-H 'X-Auth-Token: $(password)' -H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/volumes -f

	# Get volume
	$(curl) $(curl_args) -XGET -H 'X-Auth-Token: $(password)' -H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/volumes?name=my-new-volume16 -f

	# Mutate volume
	$(curl) $(curl_args) -XPUT -d @tests/csp/mutator.yaml -H 'Content-Type: application/json' \
		-H 'X-Auth-Token: $(password)' -H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/volumes/tank_my-new-volume16 -f

	$(curl) $(curl_args) -XPUT -d @tests/csp/mutators.yaml -H 'Content-Type: application/json' \
		-H 'X-Auth-Token: $(password)' -H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/volumes/tank_my-new-volume16 -f

	$(curl) $(curl_args) -XPUT -d @tests/csp/mutator-negative.yaml -H 'Content-Type: application/json' \
		-H 'X-Auth-Token: $(password)' -H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/volumes/tank_my-new-volume16 -f || true

	# Publish volume host 1
	$(curl) $(curl_args) -XPUT -d @tests/csp/publish.yaml -H 'Content-Type: application/json' \
		-H 'X-Auth-Token: $(password)' -H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/volumes/tank_my-new-volume16/actions/publish -f

	# Publish volume host 2
	$(curl) $(curl_args) -XPUT -d @tests/csp/publish-multi.yaml -H 'Content-Type: application/json' \
		-H 'X-Auth-Token: $(password)' -H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/volumes/tank_my-new-volume16/actions/publish -f

	# Create snapshots
	$(curl) $(curl_args) -XPOST -d @tests/csp/snapshot1.yaml -H 'Content-Type: application/json' \
		-H 'X-Auth-Token: $(password)' -H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/snapshots -f
	$(curl) $(curl_args) -XPOST -d @tests/csp/snapshot2.yaml -H 'Content-Type: application/json' \
		-H 'X-Auth-Token: $(password)' -H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/snapshots -f

	# List snapshots
	$(curl) $(curl_args) -H 'Content-Type: application/json' \
		-H 'X-Auth-Token: $(password)' -H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/snapshots?volume_id=tank_my-new-volume16 -f

	# Get snapshots from volume
	$(curl) $(curl_args) -XGET -H 'X-Auth-Token: $(password)' -H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/snapshots?volume_id=tank_my-new-volume16 -f
	$(curl) $(curl_args) -XGET -H 'X-Auth-Token: $(password)' -H 'X-Array-IP: $(backend)' \
		'$(csp)/containers/v1/snapshots?volume_id=tank_my-new-volume16&name=my-first-snapshot' -f
	$(curl) $(curl_args) -XGET -H 'Content-Type: application/json' \
		-H 'X-Auth-Token: $(password)' -H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/snapshots/tank_my-new-volume16@my-first-snapshot -f

	# Create clone
	$(curl) $(curl_args) -XPOST -d @tests/csp/clone.yaml -H 'Content-Type: application/json' \
		-H 'X-Auth-Token: $(password)' -H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/volumes -f

	# Delete clone
	$(curl) $(curl_args) -XDELETE -H 'Content-Type: application/json' -H 'X-Auth-Token: $(password)' \
		-H 'X-Array-IP: $(backend)' $(csp)/containers/v1/volumes/tank_my-new-volume17 -f

	# Delete a snapshot
	$(curl) $(curl_args) -XDELETE -H 'Content-Type: application/json' \
		-H 'X-Auth-Token: $(password)' -H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/snapshots/tank_my-new-volume16@my-first-snapshot -f

	# Delete another snapshot
	$(curl) $(curl_args) -XDELETE -H 'Content-Type: application/json' \
		-H 'X-Auth-Token: $(password)' -H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/snapshots/tank_my-new-volume16@my-second-snapshot -f

	# List snapshots
	- $(curl) $(curl_args) -H 'Content-Type: application/json' \
		-H 'X-Auth-Token: $(password)' -H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/snapshots?volume_id=tank_my-new-volume16 -f

	# Unpublish volume host 1
	$(curl) $(curl_args) -XPUT -d @tests/csp/unpublish.yaml -H 'Content-Type: application/json' \
		-H 'X-Auth-Token: $(password)' -H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/volumes/tank_my-new-volume16/actions/unpublish -f

	# Unpublish volume host 2
	$(curl) $(curl_args) -XPUT -d @tests/csp/unpublish-multi.yaml -H 'Content-Type: application/json' \
		-H 'X-Auth-Token: $(password)' -H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/volumes/tank_my-new-volume16/actions/unpublish -f

	# Delete volume
	$(curl) $(curl_args) -XDELETE -H 'Content-Type: application/json' \
		-H 'X-Auth-Token: $(password)' -H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/volumes/tank_my-new-volume16 -f

	# Delete thick volume
	$(curl) $(curl_args) -XDELETE -H 'Content-Type: application/json' \
		-H 'X-Auth-Token: $(password)' -H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/volumes/tank_my-new-volume18 -f

	# Create host 3 CHAP
	$(curl) $(curl_args) -XPOST -d @tests/csp/initiator-chap.yaml -H 'Content-Type: application/json' \
		-H 'X-Auth-Token: $(password)' -H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/hosts -f

	# Create CHAP volume
	$(curl) $(curl_args) -XPOST -d @tests/csp/volume-chap.yaml -H 'Content-Type: application/json' \
		-H 'X-Auth-Token: $(password)' -H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/volumes -f

	# Publish CHAP volume
	$(curl) $(curl_args) -XPUT -d @tests/csp/publish-chap.yaml -H 'Content-Type: application/json' \
		-H 'X-Auth-Token: $(password)' -H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/volumes/tank_my-new-volume377/actions/publish -f


	# Unpublish CHAP volume
	$(curl) $(curl_args) -XPUT -d @tests/csp/unpublish-chap.yaml -H 'Content-Type: application/json' \
		-H 'X-Auth-Token: $(password)' -H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/volumes/tank_my-new-volume377/actions/unpublish -f

	# Delete volume CHAP
	$(curl) $(curl_args) -XDELETE -H 'Content-Type: application/json' \
		-H 'X-Auth-Token: $(password)' -H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/volumes/tank_my-new-volume377 -f

	# Delete host CHAP
	$(curl) $(curl_args) -XDELETE -H 'Content-Type: application/json' \
		-H 'X-Auth-Token: $(password)' -H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/hosts/41302701-0196-420f-b319-834a79891db2 -f

	# Delete host 1
	- $(curl) $(curl_args) -XDELETE -H 'Content-Type: application/json' \
		-H 'X-Auth-Token: $(password)' -H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/hosts/41302701-0196-420f-b319-834a79891db0 -f

	# Delete host 2
	- $(curl) $(curl_args) -XDELETE -H 'Content-Type: application/json' \
		-H 'X-Auth-Token: $(password)' -H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/hosts/41302701-0196-420f-b319-834a79891db1 -f
