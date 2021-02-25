#!/usr/bin/env python3

#
# (C) Copyright 2020 Hewlett Packard Enterprise Development LP.
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
import re
import traceback
import json
import falcon
import backend

class Unpublish:
    def on_put(self, req, resp, volume_id):
        api = req.context

        try:
            dataset_name = api.xslt_volume_id_to_name(volume_id)

            # get target from volume name
            target = api.fetch('iscsi/target', field='name',
                               value=dataset_name)

            if target:
                api.delete(
                    'iscsi/target/id/{tid}'.format(tid=str(target.get('id'))))

                # get target to extent mapping
                mapping = api.fetch('iscsi/targetextent',
                                    field='target', value=str(target.get('id')))

                if mapping:
                    api.delete(
                        'iscsi/targetextent/id/{teid}'.format(teid=str(mapping.get('id'))))

            # get extent
            extent = api.fetch('iscsi/extent', field='name',
                               value=dataset_name)

            if extent:
                api.delete(
                    'iscsi/extent/id/{eid}'.format(eid=str(extent.get('id'))))

            resp.status = falcon.HTTP_204
            api.logger.info('Volume unpublished: %s', volume_id)
        except Exception:
            resp.body = api.csp_error(
                'Exception during unpublish', traceback.format_exc())
            resp.status = falcon.HTTP_500


class Publish:
    def on_put(self, req, resp, volume_id):
        api = req.context

        # ensure dataset is stripped
        try:
            strip = Unpublish()
            strip.on_put(req, resp, volume_id)
        except Exception:
            api.csp_error('Exception while stripping volume',
                          traceback.format_exc())

        try:
            content = req.media

            dataset_name = api.xslt_volume_id_to_name(volume_id)
            dataset_id = api.xslt_id_to_dataset(volume_id)

            # grab host
            initiator = api.fetch(
                'iscsi/initiator', field='comment', value=content.get('host_uuid'))

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

            # create target
            req_backend = {
                'name': dataset_name,
                'groups': [portal_group]
            }

            api.post('iscsi/target', req_backend)
            target = api.req_backend.json()

            # add extent to dataset
            req_backend = {
                'type': 'DISK',
                'comment': 'Managed by HPE CSI Driver for Kubernetes',
                'name': dataset_name,
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
                    '{base}:{target}'.format(
                        base=api.target_basename, target=dataset_name)
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
        api.logger.debug("Volume PUT request for volume ID %s", volume_id)
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
        api.logger.debug("Volume GET request for volume ID %s", volume_id)
        api = req.context
        try:
            content = req.media
            api.logger.debug("Volume Content %s", content)
            root = content.get('config').get('root', api.dataset_defaults.get('root'))
            api.logger.debug("Volume root %s", root)
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
        api.logger.debug("Volume DELETE request for volume ID %s", volume_id)
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
                    api.delete(api.uri_id('pool/dataset',
                                          dataset.get('name')), body={'recursive': True})
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
        api.logger.debug("Volumes GET request")
        api = req.context
        try:
            content = req.media
            api.logger.debug("Volumes Content %s", content)
            root = content.get('config').get('root', api.dataset_defaults.get('root'))
            api.logger.debug("Volumes root %s", root)
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
        api.logger.debug("Volumes POST request")
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
                    'comments': content.get('description', api.dataset_defaults.get('description')),
                    'name': '{root}/{volume_name}'.format(volume_name=content.get('name'), root=root),
                    'volsize': '{size}'.format(size=int(content.get('size'))),
                    'volblocksize': content.get('config').get('volblocksize', api.dataset_defaults.get('volblocksize')),
                    'sparse': bool(content.get('config').get('sparse', api.dataset_defaults.get('sparse'))),
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
                'auth_network': content.get('networks')
            }

            initiator = api.fetch(
                'iscsi/initiator', field='comment', value=content.get('uuid'))

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
                'networks': payload.get('auth_network'),
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
                                          'No iSCSI portal named {name} with comment {comment} found'.format(name=api.target_basename, comment=api.target_portal))
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
                api.delete(api.uri_id('zfs/snapshot', snapshot.get('id')))
                resp.status = api.resp_msg
                api.logger.info('Snapshot deleted: %s', snapshot_id)
            else:
                api.logger.info('Snapshot not found: %s', snapshot_id)
                resp.status = falcon.HTTP_404
        except Exception:
            resp.body = api.csp_error('Exception', traceback.format_exc())
            resp.status = falcon.HTTP_500
