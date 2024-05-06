#!/usr/bin/env python3

#
# (C) Copyright 2024 Hewlett Packard Enterprise Development LP.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

from time import time
from time import sleep
import re
import traceback
import json
import falcon
import backend

class Unpublish:
    def on_put(self, req, resp, volume_id):

        api = req.context
        content = req.media

        try:
            dataset_name = api.xslt_volume_id_to_name(volume_id)
            access_name = api.access_name.format(dataset_name=dataset_name)

            # get target from volume name
            target = api.fetch('iscsi/target', field='name',
                               value=access_name)

            api.logger.debug('Target being unpublished: %s', target)

            # get initiator from uuid
            initiator = api.fetch(
                'iscsi/initiator', field='comment', value=content.get('host_uuid'), returnBy=dict)

            api.logger.debug('Initiator requested to be unpublished: %s', initiator)

            # FIXME: Only Unpublish the host being requested and
            #        delete target, target/extent and extent if
            #        groups = []

            if target:

                initiators = target.get('groups')

                # Remove ID from groups, if empty, delete the rest.
                for initiator_removal in initiators:
                    if initiator_removal['initiator'] == initiator.get('id'):
                        initiators.remove(initiator_removal)
                        break

                api.logger.debug('Initiators left intact: %s', initiators)

                if not initiators:
                    api.delete(
                        'iscsi/target/id/{tid}'.format(tid=str(target.get('id'))))

                    target_deletion = api.backend_retries

                    while api.fetch('iscsi/target', field='name',
                                    value=access_name) and target_deletion:
                        sleep(api.backend_delay)
                        target_deletion -= 1
                        api.delete(
                            'iscsi/target/id/{tid}'.format(tid=str(target.get('id'))))
                        api.logger.debug('Target deletion retried: %s', volume_id)

                    # Force deletion
                    if not target_deletion:
                        api.delete(
                            'iscsi/target/id/{tid}'.format(tid=str(target.get('id'))), body='true')

                    # get target to extent mapping
                    mapping = api.fetch('iscsi/targetextent',
                                        field='target', value=str(target.get('id')))

                    if mapping:
                        api.delete(
                            'iscsi/targetextent/id/{teid}'.format(teid=str(mapping.get('id'))))

                        targetextent_deletion = api.backend_retries

                        while api.fetch('iscsi/targetextent',
                                field='target', value=str(target.get('id'))) and targetextent_deletion:
                            sleep(api.backend_delay)
                            targetextent_deletion -= 1
                            api.delete(
                                'iscsi/targetextent/id/{teid}'.format(teid=str(mapping.get('id'))))
                            api.logger.debug('Target/extent deletion retried: %s', volume_id)

                        # Force deletion
                        if not targetextent_deletion:
                            api.delete(
                                'iscsi/targetextent/id/{teid}'.format(teid=str(mapping.get('id'))), body='true')

                    # get extent
                    extent = api.fetch('iscsi/extent', field='name',
                                       value=access_name)

                    if extent:
                        api.delete(
                            'iscsi/extent/id/{eid}'.format(eid=str(extent.get('id'))))

                        extent_deletion = api.backend_retries

                        while api.fetch('iscsi/extent', field='name',
                                        value=access_name) and extent_deletion:
                            sleep(api.backend_delay)
                            extent_deletion -= 1
                            api.delete(
                                'iscsi/extent/id/{eid}'.format(eid=str(extent.get('id'))))
                            api.logger.debug('Extent deletion retried: %s', volume_id)

                        if not extent_deletion:
                            api.delete(
                                'iscsi/extent/id/{eid}'.format(eid=str(extent.get('id'))), body='{"force":true, "remove":true}')
                else:
                    # Replace group list
                    api.logger.debug('Replacing group list on target: %s', 'placeholder')

            resp.status = falcon.HTTP_204
            api.logger.info('Volume unpublished: %s', volume_id)
        except Exception:
            resp.body = api.csp_error(
                'Exception during unpublish', traceback.format_exc())
            resp.status = falcon.HTTP_500


class Publish:
    def on_put(self, req, resp, volume_id):
        api = req.context

        try:
            content = req.media

            dataset_name = api.xslt_volume_id_to_name(volume_id)
            dataset_id = api.xslt_id_to_dataset(volume_id)
            access_name = api.access_name.format(dataset_name=dataset_name)

            # Need to ensure a usable basename
            iscsi_config = api.fetch('iscsi/global')

            if iscsi_config.get('basename') not in api.target_basenames:
                resp.body = api.csp_error('Misconfigured',
                                          '{base} is not a valid basename, use {basenames}'.format(
                                          base=iscsi_config.get('basename'),
                                          basenames=' or '.join(api.target_basenames)))
                resp.status = falcon.HTTP_500
                return

            # grab host
            initiator = api.fetch(
                'iscsi/initiator', field='comment', value=content.get('host_uuid'), returnBy=dict)

            # grab portal IPs
            portal = api.fetch('iscsi/portal', field='comment',
                               value=api.target_portal)

            discovery_ips = []

            for listen in portal.get('listen'):
                if listen.get('ip') == '0.0.0.0':
                    resp.body = api.csp_error('Misconfigured',
                                              'Using 0.0.0.0 as listenining inferface on the portal is not supported.')
                    resp.status = falcon.HTTP_500
                    return

                discovery_ips.append(listen.get('ip'))

            # portal grouping
            portal_group = {
                'portal': portal.get('id'),
                'initiator': initiator.get('id')
            }

            # access group
            req_backend = {
                'name': access_name,
                'groups': [portal_group]
            }

            system_version = api.version()

            # treat SCALE
            if system_version == "SCALE":
                req_backend['auth_networks'] = api.ipaddrs_to_networks(discovery_ips)

            # check if target already exist
            target = api.fetch('iscsi/target', field='name',
                               value=access_name)

            if target:
                # FIXME: merge groups (support RWX block)
                #        see Unpublish and manage auth_nework(s)
                #        req_backend['groups'] += target['groups']

                # update target groups
                api.put('iscsi/target/id/{tid}'.format(tid=target.get('id')), req_backend)
                target_id = api.req_backend.json()
                api.logger.debug('Target updated: %s', target_id.get('name'))

            else:

                api.post('iscsi/target', req_backend)
                target = api.req_backend.json()

            # extent needs to be part of response to CSI driver
            extent = api.fetch('iscsi/extent', field='name',
                               value=access_name)

            # If extent is empty, try create a new extent
            if not extent:
                # add extent to dataset
                req_backend = {
                    'type': 'DISK',
                    'comment': 'Managed by HPE CSI Driver for Kubernetes',
                    'name': access_name,
                    'disk': 'zvol/{dataset_id}'.format(dataset_id=dataset_id)
                }

                api.post('iscsi/extent', req_backend)
                extent = api.req_backend.json()

                # add target to extent
                req_backend = {
                    'target': target.get('id'),
                    'extent': extent.get('id'),
                    'lunid': 0
                }

                api.post('iscsi/targetextent', req_backend)

            # respond to CSI
            csi_resp = {
                'discovery_ips': discovery_ips,
                'access_protocol': 'iscsi',
                'lun_id': 0,
                'serial_number': extent.get('naa').lstrip('0x'),
                'target_names': [
                    '{base}:{access_name}'.format(
                        base=iscsi_config.get('basename'),
                        access_name=access_name)
                ]
            }

            resp.body = json.dumps(csi_resp)
            resp.status = falcon.HTTP_200

            api.logger.debug('CSP response: %s', resp.body)
            api.logger.info('Volume published: %s', volume_id)
        except Exception:
            resp.body = api.csp_error('Exception', traceback.format_exc())
            resp.status = falcon.HTTP_500


class Volume:
    def on_put(self, req, resp, volume_id):
        api = req.context
        try:
            dataset = api.fetch('pool/dataset', field='name',
                                value=api.xslt_id_to_dataset(volume_id))

            if dataset:
                content = req.media

                req_backend = {}

                if content.get('size'):
                    req_backend.update({'volsize': int(content.get('size'))})
                if content.get('description'):
                    req_backend.update({'comments': content.get('description')})

                config = content.get('config')

                if config:
                    for key in config:
                        if key in api.dataset_mutables:
                            req_backend.update({key: config.get(key)})
                        else:
                            resp.body = api.csp_error('Bad Request',
                                                        ('The request could not '
                                                        'be understood by the '
                                                        'server. Unexpected argument '
                                                        '"{key}"'.format(key=key)))
                            resp.status = falcon.HTTP_400
                            return

                api.put(api.uri_id('pool/dataset',
                                   dataset.get('name')), req_backend)

                if api.req_backend.status_code != 200:
                    resp.body = api.csp_error('Bad Request',
                                              'TrueNAS API returned: {content}'.format(content=api.req_backend.content.decode('utf-8')))
                    resp.status = falcon.HTTP_500
                    return

                dataset = api.fetch(
                    'pool/dataset', field='name', value=api.xslt_id_to_dataset(volume_id))
                csi_resp = api.dataset_to_volume(dataset)
                resp.body = json.dumps(csi_resp)

                api.logger.debug('CSP response: %s', resp.body)
                api.logger.info('Volume updated: %s', csi_resp.get('id'))

        except Exception:
            resp.body = api.csp_error('Exception', traceback.format_exc())
            resp.status = falcon.HTTP_500

    def on_get(self, req, resp, volume_id):
        api = req.context
        try:
            dataset = api.fetch('pool/dataset', field='name',
                                value=api.xslt_id_to_dataset(volume_id))

            if dataset:
                csi_resp = api.dataset_to_volume(dataset)
                resp.body = json.dumps(csi_resp)

                api.logger.debug('CSP response: %s', resp.body)
                api.logger.info('Volume found: %s', volume_id)
            else:
                resp.body = api.csp_error(
                    'Not found', 'Volume with id {volume_id} not found.'.format(volume_id=volume_id))
                resp.status = falcon.HTTP_404

        except Exception:
            resp.body = api.csp_error('Exception', traceback.format_exc())
            resp.status = falcon.HTTP_500

    def on_delete(self, req, resp, volume_id):
        api = req.context

        try:
            dataset = api.fetch('pool/dataset', field='name',
                                value=api.xslt_id_to_dataset(volume_id))

            if dataset:
                csi_volume = api.dataset_to_volume(dataset)

                if csi_volume.get('published'):
                    resp.body = api.csp_error(
                        'Bad Request', 'Cannot delete a published volume')
                    resp.status = falcon.HTTP_409
                else:

                    # FIXME: Deal with snapshots
                    api.delete(api.uri_id('pool/dataset',
                                          dataset.get('name')), body='{"recursive": true, "force": true}')

                    # things might be pending
                    dataset_deletion = api.backend_retries

                    while api.fetch('pool/dataset', field='name',
                            value=api.xslt_id_to_dataset(volume_id)) and dataset_deletion:
                        dataset_deletion -= 1
                        sleep(api.backend_delay)
                        api.delete(api.uri_id('pool/dataset',
                          dataset.get('name')), body='{"recursive": true, "force": true}')
                        api.logger.info('Dataset deletion retried: %s', volume_id)

                    resp.status = api.resp_msg
                    api.logger.info('Volume deleted with id: %s', volume_id)
            else:
                resp.status = falcon.HTTP_404

        except Exception:
            resp.body = api.csp_error('Exception', 'Unable to delete {volume_id}: {trace}'.format(
                volume_id=volume_id, trace=traceback.format_exc()))
            resp.status = falcon.HTTP_500


class Volumes:
    def on_get(self, req, resp):
        api = req.context
        try:
            if req.params.get('name'):
                regex = re.compile(
                    '.*/{volume_name}$'.format(volume_name=req.params.get('name')))
                dataset = api.fetch('pool/dataset', field='name', value=regex)

                if dataset:
                    csi_resp = [api.dataset_to_volume(dataset)]
                    resp.body = json.dumps(csi_resp)

                    api.logger.debug('CSP response: %s', resp.body)
                    api.logger.info('Volume found: %s', req.params.get('name'))

                else:
                    resp.body = api.csp_error('Not found', 'Volume with name {volume_name} not found.'.format(
                        volume_name=req.params.get('name')))
                    resp.status = falcon.HTTP_404
            else:
                pass  # FIXME

        except Exception:
            resp.body = api.csp_error('Exception', traceback.format_exc())
            resp.status = falcon.HTTP_500

    def on_post(self, req, resp):
        api = req.context

        try:
            content = req.media
            root = content.get('config').get('root', api.dataset_defaults.get('root'))

            if content.get('clone'):
                req_backend = {
                    'snapshot': api.xslt_id_to_dataset(content.get('base_snapshot_id')),
                    'dataset_dst': '{root}/{volume_name}'.format(volume_name=content.get('name'), root=root),
                }
                api.post('zfs/snapshot/clone', req_backend)

                dataset = api.fetch('pool/dataset', field='name',
                                    value='{root}/{volume_name}'.format(volume_name=content.get('name'), root=root))
            else:
                req_backend = {
                    'type': 'VOLUME',
                    # FIXME
                    'comments': content.get('description', api.dataset_defaults.get('description')).format(
                        pvc=content.get('config').get('csi.storage.k8s.io/pvc/name', 'pvc'),
                        namespace=content.get('config').get('csi.storage.k8s.io/pvc/namespace', 'namespace'),
                        pv=content.get('config').get('csi.storage.k8s.io/pv/name', 'pv')
                        ),
                    'name': '{root}/{volume_name}'.format(volume_name=content.get('name'), root=root),
                    'volsize': '{size}'.format(size=int(content.get('size'))),
                    'volblocksize': content.get('config').get('volblocksize', api.dataset_defaults.get('volblocksize')),
                    'sparse': json.loads(content.get('config').get('sparse', api.dataset_defaults.get('sparse')).lower()),
                    'deduplication': content.get('config').get('deduplication', api.dataset_defaults.get('deduplication')),
                    'sync': content.get('config').get('sync', api.dataset_defaults.get('sync')),
                    'compression':  content.get('config').get('compression', api.dataset_defaults.get('compression'))
                }
                api.post('pool/dataset', req_backend)

                dataset = api.req_backend.json()

            if api.req_backend.status_code != 200:
                resp.body = api.csp_error('Bad Request',
                                          'TrueNAS API returned: {content}'.format(content=api.req_backend.content.decode('utf-8')))
                resp.status = falcon.HTTP_500
                return

            csi_resp = api.dataset_to_volume(dataset)
            resp.body = json.dumps(csi_resp)

            api.logger.debug('CSP response: %s', resp.body)
            api.logger.info('Volume created: %s', csi_resp.get('name'))

        except Exception:
            resp.body = api.csp_error('Exception',
                                      'Unable to create new volume: {trace}'.format(trace=traceback.format_exc()))
            resp.status = falcon.HTTP_500


class Hosts:
    def on_post(self, req, resp):
        api = req.context

        content = req.media

        try:
            req_backend = {
                'comment': content.get('uuid'),
                'initiators': content.get('iqns'),
            }

            # CORE and FreeNAS
            system_version = api.version()

            if system_version == "CORE" or system_version == "LEGACY":
                req_backend['auth_network'] = api.cidrs_to_hosts(content.get('networks'))

            initiator = api.fetch(
                'iscsi/initiator', field='comment', value=content.get('uuid'), returnBy=dict)

            if initiator:
                api.put(
                    'iscsi/initiator/id/{id}'.format(id=initiator.get('id')), req_backend)
                api.logger.info('Host updated: %s', content.get('uuid'))
            else:
                api.post('iscsi/initiator', req_backend)
                api.logger.info('Host created: %s', content.get('uuid'))

            payload = api.req_backend.json()

            csi_resp = {
                'id': payload.get('id'),
                'name': payload.get('comment'),
                'uuid': payload.get('comment'),
                'iqns': payload.get('initiators'),
                'networks': content.get('networks'),
                'wwpns': []
            }

            resp.body = json.dumps(csi_resp)

            api.logger.debug('CSP response: %s', resp.body)
        except Exception:
            resp.body = api.csp_error('Exception', traceback.format_exc())
            resp.status = falcon.HTTP_500

    def on_delete(self, req, resp, host_id):
        api = req.context

        try:
            initiator = api.fetch(
                'iscsi/initiator', field='comment', value=host_id)

            if initiator:
                api.delete(
                    'iscsi/initiator/id/{id}'.format(id=str(initiator.get('id'))))
                resp.status = api.resp_msg
                api.logger.info('Host deleted: %s', initiator.get('comment'))
            else:
                api.logger.info('Host not found: %s', host_id)
                resp.status = falcon.HTTP_404
        except Exception:
            resp.body = api.csp_error('Exception', traceback.format_exc())
            resp.status = falcon.HTTP_500


class Tokens:
    def on_post(self, req, resp):
        api = req.context

        try:
            portal = api.fetch('iscsi/portal', field='comment',
                               value=api.target_portal)

            if portal:
                csi_resp = {
                    'id': str(time()),
                    'session_token': api.token,
                    'array_ip': api.backend,
                    'username': req.params.get('username'),
                    'creation_time': int(time()),
                    'expiry_time': int(time()) + 86400
                }
                resp.body = json.dumps(csi_resp)

                api.logger.debug('CSP response: %s', resp.body)
                api.logger.info('Token created (not logged)')
            else:
                resp.body = api.csp_error('Unconfigured',
                                          'No iSCSI portal named {name} with comment {comment} found'.format(name=' or '.join(api.target_basenames), comment=api.target_portal))
                resp.status = falcon.HTTP_404

        except Exception:
            resp.body = api.csp_error('Exception', traceback.format_exc())
            resp.status = falcon.HTTP_500

    def on_delete(self, req, resp, token_id):
        resp.status = falcon.HTTP_204


class Snapshots:
    def on_post(self, req, resp):
        api = req.context

        content = req.media

        try:
            snapshot_name = content.get('name')
            dataset_name = api.xslt_id_to_dataset(content.get('volume_id'))

            # TrueNAS API is broken
            snapshot = api.fetch('zfs/snapshot', field='name',
                                 value='{dataset_name}@{snapshot_name}'.format(dataset_name=dataset_name,
                                                                               snapshot_name=snapshot_name))

            api.logger.debug('Snapshot exists: %s', snapshot)

            if not snapshot:
                req_backend = {
                    'name': snapshot_name,
                    'dataset': dataset_name,
                }
                api.post('zfs/snapshot', req_backend)

                if api.req_backend.status_code != 200:
                    resp.body = api.csp_error('Bad Request',
                                              'TrueNAS API returned: {content}'.format(content=api.req_backend.content.decode('utf-8')))
                    resp.status = falcon.HTTP_500
                    return

                # TrueNAS API is broken
                snapshot = api.fetch('zfs/snapshot', field='name',
                                     value='{dataset_name}@{snapshot_name}'.format(dataset_name=dataset_name,
                                                                                   snapshot_name=snapshot_name))

            csi_resp = api.snapshot_to_snapshot(snapshot)
            resp.body = json.dumps(csi_resp)

            api.logger.debug('CSP response: %s', resp.body)
            api.logger.info('Snapshot created: %s', csi_resp.get('name'))

        except Exception:
            resp.body = api.csp_error('Exception', traceback.format_exc())
            resp.status = falcon.HTTP_500

    def on_get(self, req, resp):
        api = req.context
        try:
            csi_resp = []

            if req.params.get('name'):
                snapshot = api.fetch('zfs/snapshot', field='snapshot_name',
                                     value=api.xslt_id_to_dataset(req.params.get('name')))

                if snapshot:
                    csi_resp = [api.snapshot_to_snapshot(snapshot)]
            else:
                snapshots = api.fetch('zfs/snapshot', field='dataset',
                                      value=api.xslt_id_to_dataset(req.params.get('volume_id')))

                for snapshot in snapshots:
                    csi_resp.append(api.snapshot_to_snapshot(snapshot))

            if csi_resp:
                resp.body = json.dumps(csi_resp)
                api.logger.debug('CSP response: %s', resp.body)
                api.logger.info('Snapshot(s) found on volume %s',
                                req.params.get('volume_id'))

            else:
                resp.body = api.csp_error('Not found', 'No snapshots found on volume {volume_id}.'.format(
                    volume_id=req.params.get('volume_id')))
                resp.status = falcon.HTTP_404

        except Exception:
            resp.body = api.csp_error('Exception', traceback.format_exc())
            resp.status = falcon.HTTP_500
        return


class Snapshot:
    def on_get(self, req, resp, snapshot_id):
        api = req.context
        try:
            snapshot = api.fetch('zfs/snapshot', field='id',
                                 value=api.xslt_id_to_dataset(snapshot_id))

            if snapshot:
                csi_resp = api.snapshot_to_snapshot(snapshot)
                resp.body = json.dumps(csi_resp)

                api.logger.debug('CSP response: %s', resp.body)
                api.logger.info('Snapshot found %s', snapshot_id)

            else:
                resp.body = api.csp_error(
                    'Not found', 'Snapshot not found {snapshot_id}'.format(snapshot_id=snapshot_id))
                resp.status = falcon.HTTP_404

        except Exception:
            resp.body = api.csp_error('Exception', traceback.format_exc())
            resp.status = falcon.HTTP_500

    def on_delete(self, req, resp, snapshot_id):
        api = req.context

        try:
            snapshot = api.fetch('zfs/snapshot', field='id',
                                 value=api.xslt_id_to_dataset(snapshot_id))

            if snapshot:
                snapshot_clones = api.backend_retries

                # pretend snapshot is deleted if it has clones, but wait first
                while int(snapshot.get('properties').get('numclones').get('value')) > 0 and snapshot_clones:
                    api.logger.info('Snapshot has clones, waiting: %s', snapshot_id)
                    sleep(api.backend_delay)
                    snapshot = api.fetch('zfs/snapshot', field='id',
                                     value=api.xslt_id_to_dataset(snapshot_id))
                    snapshot_clones -= 1

                    if snapshot_clones == 0:
                        api.logger.info('Snapshot had clones, not deleted: %s', snapshot_id)
                        resp.status = falcon.HTTP_204
                        return

                api.delete(api.uri_id('zfs/snapshot', snapshot.get('id')))

                # things might be pending
                snapshot_deletion = api.backend_retries

                while api.fetch('zfs/snapshot', field='id',
                        value=api.xslt_id_to_dataset(snapshot_id)) and snapshot_deletion:
                    snapshot_deletion -= 1
                    sleep(api.backend_delay)
                    api.delete(api.uri_id('zfs/snapshot', snapshot.get('id')))
                    api.logger.info('Snapshot deletion retried: %s', snapshot_id)

                resp.status = api.resp_msg
                api.logger.info('Snapshot deleted: %s', snapshot_id)
            else:
                api.logger.info('Snapshot not found: %s', snapshot_id)
                resp.status = falcon.HTTP_404
        except Exception:
            resp.body = api.csp_error('Exception', traceback.format_exc())
            resp.status = falcon.HTTP_500
