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
from multiprocessing import Lock
import re
import traceback
import json
import falcon
import backend

publish_lock = Lock()
unpublish_lock = Lock()
hosts_lock = Lock()

class Unpublish:
    def on_put(self, req, resp, volume_id):
        unpublish_lock.acquire()
        api = req.context
        content = req.media
        system_version = api.version()

        try:
            dataset_name = api.xslt_volume_id_to_name(volume_id)
            access_name = api.access_name.format(dataset_name=dataset_name)

            # get target from volume name
            target = api.fetch('iscsi/target', field='name', value=access_name)

            api.logger.debug('Target being updated: %s', target)

            # find ID of initiator being removed
            initiator = {}

            if target:
                # get initiators from host
                host = api.fetch('iscsi/initiator', field='comment',
                        value=content.get('host_uuid'), returnBy=dict)

                # get initiators from access_name
                initiator = api.fetch('iscsi/initiator', field='comment',
                        value=access_name, returnBy=dict)

                if host and initiator:
                    api.logger.debug('Initiator host requested to be unpublished: %s', host.get('id'))
                    api.logger.debug('Initiator target requested to be unpublished: %s', initiator.get('id'))

                    new_initiators = []

                    # Remove host initiator from target initiator
                    for initiator_preserve in initiator.get('initiators'):
                        if initiator_preserve not in host.get('initiators'):
                            new_initiators.append(initiator_preserve)
                            api.logger.debug('Initiator to be preserved: %s', initiator_preserve)

                    api.logger.debug('Initiators left intact: %s', new_initiators)

                    req_backend = {'initiators': new_initiators }

                else:
                    req_backend = {'initiators': [] }

                if initiator: # if initiator was deleted manually
                    if req_backend.get('initiators'):
                        api.put('iscsi/initiator/id/{tid}'.format(tid=initiator.get('id')), req_backend)
                        api.logger.info('Updating IQNs on target initiator: %s', access_name)
                    else:
                        api.delete('iscsi/initiator/id/{tid}'.format(tid=initiator.get('id')))
                        api.logger.info('Deleted target initiator: %s', access_name)

                        # FreeNAS
                        if system_version == 'LEGACY':
                            api.delete('iscsi/target/id/{tid}'.format(tid=target.get('id')))
                            api.logger.info('Deleted residual target on FreeNAS: %s', target.get('name'))
                            residual_extent = api.fetch('iscsi/extent', field='name',
                                    value=access_name)
                            if residual_extent:
                                api.delete('iscsi/extent/id/{eid}'.format(eid=residual_extent.get('id')))
                                api.logger.info('Deleted residual extent on FreeNAS: %s', residual_extent.get('name'))

            resp.status = falcon.HTTP_204
            api.logger.info('Volume unpublished: %s', volume_id)

        except Exception:
            resp.body = api.csp_error(
                'Exception during unpublish', traceback.format_exc())
            resp.status = falcon.HTTP_500

        finally:
            unpublish_lock.release()


class Publish:
    def on_put(self, req, resp, volume_id):
        publish_lock.acquire()
        api = req.context

        try:
            content = req.media

            dataset_name = api.xslt_volume_id_to_name(volume_id)
            dataset_id = api.xslt_id_to_dataset(volume_id)
            access_name = api.access_name.format(dataset_name=dataset_name)

            publish = api.apply_publish(access_name, content=content,
                    dataset=api.fetch('pool/dataset', field='id',
                    value=dataset_id))

            api.logger.debug('Backend publish results: %s', publish)
            api.logger.debug('Frontend publish content: %s', content)

            auth = api.fetch('iscsi/auth', field='tag', value=int(api.chap_tag), returnBy=dict)

            # respond to CSI
            if publish.get('target', {}).get('extent', {}).get('naa') and publish.get('iscsi_config', {}).get('basename'):
                csi_resp = {
                    'discovery_ips': api.discovery_ips(),
                    'access_protocol': 'iscsi',
                    'lun_id': 0,
                    'serial_number': publish.get('target').get('extent').get('naa').lstrip('0x'),
                    'chap_user': auth.get('user', ''),
                    'chap_password': auth.get('secret',''),
                    'target_names': [
                        '{base}:{access_name}'.format(
                            base=publish.get('iscsi_config').get('basename'),
                            access_name=access_name)
                    ]
                }

                resp.body = json.dumps(csi_resp)
                resp.status = falcon.HTTP_200
            else:
                resp.body = api.csp_error('Exception',
                                          'Unable to publish volume: {trace}'.format(trace=traceback.format_exc()))
                resp.status = falcon.HTTP_500

            api.logger.debug('CSP response: %s', resp.body)
            api.logger.info('Volume published: %s', volume_id)

        except Exception:
            resp.body = api.csp_error('Exception', traceback.format_exc())
            resp.status = falcon.HTTP_500

        finally:
            publish_lock.release()


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
            dataset_name = api.xslt_volume_id_to_name(volume_id)
            access_name = api.access_name.format(dataset_name=dataset_name)

            # delete dataset
            dataset = api.fetch('pool/dataset', field='name', value=api.xslt_id_to_dataset(volume_id))

            if dataset:
                csi_volume = api.dataset_to_volume(dataset)

                if csi_volume.get('published'):
                    resp.body = api.csp_error(
                        'Bad Request', 'Cannot delete a published volume')
                    resp.status = falcon.HTTP_400
                else:
                    if api.dataset_is_busy(dataset):
                        resp.body = api.csp_error(
                            'Conflict', '{volume_id} has snapshots with holds or dependent clones'.format(volume_id=volume_id))
                        resp.status = falcon.HTTP_409
                    else:
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

                        resp.status = falcon.HTTP_204
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
                dataset = api.fetch('pool/dataset', field='name',
                        value='/{name}'.format(name=req.params.get('name')), operator='$')

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

            # create target
            res = api.create_target(dataset, content=content)

            # respond to CSI driver
            csi_resp = api.dataset_to_volume(dataset)
            resp.body = json.dumps(csi_resp)

            api.logger.debug('Target details: %s', res)
            api.logger.debug('CSP response: %s', resp.body)
            api.logger.info('Volume created: %s', csi_resp.get('name'))

        except Exception:
            resp.body = api.csp_error('Exception',
                                      'Unable to create new volume: {trace}'.format(trace=traceback.format_exc()))
            resp.status = falcon.HTTP_500


class Hosts:
    def on_post(self, req, resp):
        hosts_lock.acquire()
        api = req.context

        content = req.media

        try:
            payload = api.apply_initiator(content.get('uuid'), content=content)

            csi_resp = {
                'id': payload.get('id'),
                'name': payload.get('comment'),
                'uuid': payload.get('comment'),
                'iqns': payload.get('initiators'),
                'networks': content.get('networks'),
                'chap_user': content.get('chap_user', ''),
                'chap_password': content.get('chap_password', ''),
                'wwpns': []
            }

            resp.body = json.dumps(csi_resp)

            api.logger.debug('CSP response: %s', resp.body)
            api.logger.info('Host initiator created: %s', payload.get('comment'))

        except Exception:
            resp.body = api.csp_error('Exception', traceback.format_exc())
            resp.status = falcon.HTTP_500
        finally:
            hosts_lock.release()

    def on_delete(self, req, resp, host_id):
        api = req.context

        try:
            initiator = api.fetch(
                'iscsi/initiator', field='comment', value=host_id)

            if initiator:
                api.delete(
                    'iscsi/initiator/id/{id}'.format(id=str(initiator.get('id'))))
                resp.status = api.resp_msg
                api.logger.info('Host initiator deleted: %s', initiator.get('comment'))
            else:
                api.logger.info('Host initiator not found: %s', host_id)
                resp.status = falcon.HTTP_404
        except Exception:
            resp.body = api.csp_error('Exception', traceback.format_exc())
            resp.status = falcon.HTTP_500


class Tokens:
    def on_post(self, req, resp):
        api = req.context

        try:
            iscsi_config = api.fetch('iscsi/global')

            if not api.valid_iscsi_basename(iscsi_config.get('basename')):
                resp.body = api.csp_error('Unconfigured',
                                          '{base} is not a valid basename, use {basenames}'.format(
                                          base=iscsi_config.get('basename'),
                                          basenames=' or '.join(api.target_basenames)))
                resp.status = falcon.HTTP_400
                return

            portal = api.fetch('iscsi/portal', field='comment',
                               value=api.target_portal)

            if isinstance(portal, list):
                resp.body = api.csp_error('Unconfigured',
                                          'No single iSCSI portal named "{comment}" found (duplicates are not allowed)'.format(comment=api.target_portal))
                resp.status = falcon.HTTP_400
                return

            ips = api.discovery_ips()

            if not ips:
                resp.body = api.csp_error('Unconfigured',
                                          'No IP addresses found on the portal')
                resp.status = falcon.HTTP_400
                return

            if '0.0.0.0' in ips or '::' in ips:
                resp.body = api.csp_error('Unconfigured',
                        'Using "0.0.0.0" or "::" as listenining inferface on the portal is not supported')
                resp.status = falcon.HTTP_400
                return

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

        except Exception:
            resp.body = api.csp_error('Exception', traceback.format_exc())
            resp.status = falcon.HTTP_500

    def on_delete(self, req, resp, token_id):
        resp.status = falcon.HTTP_204


class Snapshots:
    def on_post(self, req, resp):
        api = req.context

        content = req.media
        system_version = api.version()

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

            # create a hold if VolumeSnapshot res
            if api.clone_from_pvc_prefix not in snapshot.get('id') and system_version == 'SCALE':
                req_backend = { 'id': snapshot.get('id') }
                api.post('zfs/snapshot/hold', req_backend)
                api.logger.info('Dataset held: %s', snapshot.get('id'))

        except Exception:
            resp.body = api.csp_error('Exception', traceback.format_exc())
            resp.status = falcon.HTTP_500

    def on_get(self, req, resp):
        api = req.context
        try:
            csi_resp = []

            if req.params.get('name'):
                snapshot = api.fetch('zfs/snapshot', field='snapshot_name',
                        extras={"holds": True}, value=api.xslt_id_to_dataset(req.params.get('name')))

                if snapshot and snapshot.get('holds'):
                    csi_resp = [api.snapshot_to_snapshot(snapshot)]
            else:
                # assuming too much here FIXME
                snapshots = api.fetch('zfs/snapshot', field='dataset',
                        extras={"holds": True }, returnBy=list, value=api.xslt_id_to_dataset(req.params.get('volume_id')))

                for snapshot in snapshots:
                    if snapshot.get('holds'):
                        csi_resp.append(api.snapshot_to_snapshot(snapshot))

            if csi_resp:
                resp.body = json.dumps(csi_resp)
                api.logger.debug('CSP response: %s', resp.body)
                api.logger.info('Snapshot(s) found on volume %s',
                                req.params.get('volume_id'))

            else:
                if req.params.get('name'):
                    resp.status = falcon.HTTP_404
                else:
                    resp.status = falcon.HTTP_200
                resp.body = json.dumps(csi_resp)
                api.logger.debug('No snapshots found on volume %s', req.params.get('volume_id'))

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
        system_version = api.version()

        try:
            snapshot = api.fetch('zfs/snapshot', field='id',
                                 value=api.xslt_id_to_dataset(snapshot_id),
                                 returnBy=dict)

            if snapshot and isinstance(snapshot, dict):
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

                        # release the snapshot hold
                        req_backend = { 'id': snapshot.get('id') }
                        if system_version == 'SCALE':
                            api.post('zfs/snapshot/release', req_backend)
                            api.logger.info('Dataset released: %s', snapshot.get('id'))

                        resp.status = falcon.HTTP_204
                        return

                # FIXME dupe code
                req_backend = { 'id': snapshot.get('id') }
                if system_version == 'SCALE':
                    api.post('zfs/snapshot/release', req_backend)
                    api.logger.info('Dataset released: %s', snapshot.get('id'))

                api.delete(api.uri_id('zfs/snapshot', snapshot.get('id')))

                # things might be pending
                snapshot_deletion = api.backend_retries

                while api.fetch('zfs/snapshot', field='id',
                        value=api.xslt_id_to_dataset(snapshot_id)) and snapshot_deletion:
                    snapshot_deletion -= 1
                    sleep(api.backend_delay)
                    api.delete(api.uri_id('zfs/snapshot', snapshot.get('id')))
                    api.logger.info('Snapshot deletion retried: %s', snapshot_id)

                resp.status = falcon.HTTP_204
                api.logger.info('Snapshot deleted: %s', snapshot_id)
            else:
                api.logger.info('Snapshot not found: %s', snapshot_id)
                resp.status = falcon.HTTP_404
        except Exception:
            resp.body = api.csp_error('Exception', traceback.format_exc())
            resp.status = falcon.HTTP_500
