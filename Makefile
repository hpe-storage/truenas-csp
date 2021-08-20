csp = http://localhost:8080
curl = curl
curl_args = -v

ifndef username
	username = hpe-csi
endif

ifeq ($(username), root)
	auth := Authorization: Bearer $(username):$(password)
else
	auth = X-Auth-Token: $(password)
endif

all:
	python3 -m py_compile truenascsp/*.py
	rm -rf truenascsp/__pycache__
	docker build -t hpestorage/truenas-csp:edge .

run:
	docker rm -f truenas-csp || true
	docker run -d -p8080:8080 --name truenas-csp -e LOG_DEBUG=1 hpestorage/truenas-csp:edge

test:
	# Delete host
	$(curl) $(curl_args) -XDELETE -H 'Content-Type: application/json' -H 'X-Auth-Token: $(password)' \
		-H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/hosts/41302701-0196-420f-b319-834a79891db0 -f || true
	
	# Unpublish volume
	$(curl) $(curl_args) -XPUT -d @tests/csp/unpublish.yaml -H 'Content-Type: application/json' \
		-H 'X-Auth-Token: $(password)' -H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/volumes/tank_my-new-volume16/actions/unpublish -f || true

	# Delete volume
	$(curl) $(curl_args) -XDELETE -H 'Content-Type: application/json' -H 'X-Auth-Token: $(password)' \
		-H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/volumes/tank_my-new-volume16 -f || true

	# "Create" password
	$(curl) $(curl_args) -XPOST \
		-d '{ "array_ip": "$(backend)", "username": "$(username)", "password": "$(password)"}' \
		-H 'Content-Type: application/json' $(csp)/containers/v1/tokens -f

	# Delete password
	$(curl) $(curl_args) -XDELETE -H 'Content-Type: application/json' $(csp)/containers/v1/tokens/123 -f
	
	# Fail auth
	$(curl) $(curl_args) -XGET -H 'Content-Type: application/json' $(csp)/containers/v1/tokens/123 -f || true

	# Create host
	$(curl) $(curl_args) -XPOST -d @tests/csp/initiator.yaml -H 'Content-Type: application/json' \
		-H 'X-Auth-Token: $(password)' -H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/hosts -f

	# Create volume
	$(curl) $(curl_args) -XPOST -d @tests/csp/volume.yaml -H 'Content-Type: application/json' \
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

	# Publish volume
	$(curl) $(curl_args) -XPUT -d @tests/csp/publish.yaml -H 'Content-Type: application/json' \
		-H 'X-Auth-Token: $(password)' -H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/volumes/tank_my-new-volume16/actions/publish -f
	
	# Create snapshots
	$(curl) $(curl_args) -XPOST -d @tests/csp/snapshot1.yaml -H 'Content-Type: application/json' \
		-H 'X-Auth-Token: $(password)' -H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/snapshots -f
	$(curl) $(curl_args) -XPOST -d @tests/csp/snapshot2.yaml -H 'Content-Type: application/json' \
		-H 'X-Auth-Token: $(password)' -H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/snapshots -f

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
	# Unpublish volume
	$(curl) $(curl_args) -XPUT -d @tests/csp/unpublish.yaml -H 'Content-Type: application/json' \
		-H 'X-Auth-Token: $(password)' -H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/volumes/tank_my-new-volume16/actions/unpublish -f

	# Delete volume
	$(curl) $(curl_args) -XDELETE -H 'Content-Type: application/json' \
		-H 'X-Auth-Token: $(password)' -H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/volumes/tank_my-new-volume16 -f

	# Delete host
	$(curl) $(curl_args) -XDELETE -H 'Content-Type: application/json' \
		-H 'X-Auth-Token: $(password)' -H 'X-Array-IP: $(backend)' \
		$(csp)/containers/v1/hosts/41302701-0196-420f-b319-834a79891db0 -f
