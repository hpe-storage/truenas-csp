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

from os import environ, getpid
from time import sleep
import traceback
import logging
import json
import urllib3
import requests
import re
from requests.auth import HTTPBasicAuth
from ipaddress import IPv4Interface, ip_network

urllib3.disable_warnings()
logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s %(message)s',
                    datefmt='%a, %d %b %Y %H:%M:%S +0000')


class Handler:
    def __init__(self):
        self.backend_schema = 'https'
        self.backend_api = '/api/v2.0/'
        self.backend = None
        self.token = None
        self.pong = None
        self.req_backend = None
        self.volume_divider = '_'
        self.dataset_divider = '/'
        self.uri_slash = '%2f'
        self.resp_msg = '100 Continue'
        self.target_basenames = [ 'iqn.2011-08.org.truenas.ctl', 'iqn.2005-10.org.freenas.ctl' ]
        self.target_portal = 'hpe-csi'
        self.chap_tag = environ.get('DEFAULT_CHAP_TAG', '4730274')
        self.backend_retries = 15
        self.backend_delay = 1.5
        self.access_name = '{dataset_name}'
        self.clone_from_pvc_prefix = 'snap-for-clone-'

        self.logger = logging.getLogger('{name} {pid}'.format(name=__name__, pid=getpid()))
        self.logger.setLevel(logging.DEBUG if environ.get(
            'LOG_DEBUG') else logging.INFO)

        self.dataset_defaults = {
            'deduplication': environ.get('DEFAULT_DEDUPLICATION', 'OFF'),
            'compression': environ.get('DEFAULT_COMPRESSION', 'LZ4'),
            'sync': environ.get('DEFAULT_SYNC', 'STANDARD'),
            'sparse': environ.get('DEFAULT_SPARSE', "true"),
            'root': environ.get('DEFAULT_ROOT', 'tank'),
            'volblocksize': environ.get('DEFAULT_VOLBLOCKSIZE', '8K'),
            'description': environ.get('DEFAULT_DESCRIPTION', 'Dataset created by HPE CSI Driver for Kubernetes as {pv} in {namespace} from {pvc}')
        }

        self.dataset_mutables = [
            'size',
            'description',
            'deduplication',
            'compression',
            'sync',
            'volblocksize'
        ]

    def _get_auth(self):
        """
        Gets Authentication mechanism for all requests.
        If the token has a API key prefix, assume TrueNAS.
        FreeNAS <v12 that does NOT support API Keys.
        """

        p = re.compile('^[0-9]+-[a-zA-Z0-9]{64}')

        if p.match(self.token):
            self.logger.debug("API Key detected. Will use token authentication.")
            return {
                'Authorization': 'Bearer {token}'.format(token=self.token)
            }
        else:
            self.logger.debug("Assume Basic Auth for authentication.")
            return HTTPBasicAuth("root", self.token)

    def ping(self, req):
        content = req.media

        self.pong = self.fetch('core/ping')

        self.logger.debug('HPE CSI Request <==============================>')
        self.logger.debug('         uri: %s', req.uri)
        self.logger.debug('        body: %s', content)
        self.logger.debug('       query: %s', req.query_string)
        self.logger.debug('      method: %s', req.method)
        self.logger.debug('content_type: %s', req.content_type)
        headers = json.dumps(req.headers).replace(self.token, "*****")
        self.logger.debug('     headers: %s', headers)

    def ipaddrs_to_networks(self, ipaddrs):
        interfaces = self.fetch('interface', returnBy=list)

        networks = []

        for ip in ipaddrs:
            for interface in interfaces:
                for alias in interface['aliases']:
                    if alias.get('address') == ip:
                        networks.append(IPv4Interface('{ip}/{nm}'.format(ip=ip,
                            nm=alias.get('netmask'))).network.with_prefixlen)
        return networks

    def cidrs_to_hosts(self, cidrs):

        hosts = []

        for cidr in cidrs:
            hosts.append(str(IPv4Interface(cidr).ip))
        return hosts

    def version(self):
        version = self.fetch('system/version')
        self.logger.debug('Version: %s', version)

        if "TrueNAS-SCALE" in version:
            return "SCALE"
        if "TrueNAS" in version:
            return "CORE"
        if "FreeNAS" in version:
            return "LEGACY"

        return None

    def url_tmpl(self, uri):
        return '{schema}://{backend}{api}{uri}'.format(schema=self.backend_schema,
                                                       backend=self.backend,
                                                       api=self.backend_api, uri=uri)

    def csp_error(self, code, message):
        body = {
            'errors': [{'code': code, 'message': message}]
        }
        self.logger.error('%s: %s', code, message)
        return json.dumps(body)

    def initiator_exists(self, dataset):
        initiator = self.fetch('iscsi/initiator', field='comment',
                            value=self.xlst_name_from_id(dataset), returnBy=dict)
        if isinstance(initiator, dict):
            if initiator.get('initiators'):
                return True
        return False


    def apply_auths(self, chap_user, chap_password):
        # check if auths already exist
        auth = self.fetch('iscsi/auth', field='tag', value=int(self.chap_tag), returnBy=dict)

        # if exists, check credentials
        if auth:
            self.logger.info('CHAP found: %s', self.chap_tag)

            # if different, change them
            if auth.get('user') != chap_user or auth.get('secret') != chap_password:
                req_backend = {
                        'user': chap_user,
                        'secret': chap_password
                        }
                self.put('iscsi/auth/id/{aid}'.format(aid=auth.get('id')), req_backend)
                self.logger.info('CHAP updated: %s', self.chap_tag)
        else:
            # if not, create it
            req_backend = {
                'tag': self.chap_tag,
                'user': chap_user,
                'secret': chap_password
                }
            self.post('iscsi/auth', req_backend)
            self.logger.info('CHAP created: %s', self.chap_tag)

        return self.req_backend.json()


    def apply_initiator(self, name, **kwargs):

        content = {}
        iqns = []
        req_backend = {}

        # content exist when creating a new host initiator
        if kwargs.get('content'):
            content = kwargs.get('content')

        chap_user = content.get('chap_user')
        chap_password = content.get('chap_password')

        if chap_user and chap_password:
            self.apply_auths(chap_user, chap_password)

        current_initiator = self.fetch('iscsi/initiator', field='comment',
                            value=name, returnBy=dict)

        # CORE and FreeNAS
        system_version = self.version()

        if content:
            req_backend = {
                'comment': name,
                'initiators': content.get('iqns'),
            }

            if system_version == "CORE" or system_version == "LEGACY":
                req_backend['auth_network'] = self.cidrs_to_hosts(content.get('networks'))

        else:
            req_backend = {
                'comment': name,
                'initiators': iqns,
            }

        if current_initiator:
            if system_version == "CORE" or system_version == "LEGACY":
                req_backend['auth_network'] = self.cidrs_to_hosts(current_initiator.get('auth_network'))
            self.put(
                'iscsi/initiator/id/{id}'.format(id=current_initiator.get('id')), req_backend)
            self.logger.info('Initiator updated: %s', name)
        else:
            self.post('iscsi/initiator', req_backend)
            self.logger.info('Initiator created: %s', name)

        return self.req_backend.json()


    def xslt_volume_id_to_name(self, csi):
        return csi.split(self.volume_divider)[-1]

    def xlst_name_from_id(self, xslt):
        return xslt.split(self.dataset_divider)[-1]

    def xslt_id_to_dataset(self, xslt):
        return xslt.replace(self.volume_divider, self.dataset_divider)

    def xslt_dataset_to_volume(self, xslt):
        return xslt.replace(self.dataset_divider, self.volume_divider)

    def dataset_to_volume(self, dataset):
        try:
            volume = {
                'base_snapshot_id': self.xslt_dataset_to_volume(dataset.get('origin').get('value')),
                'volume_group_id': '',  # FIXME
                'published': self.initiator_exists(dataset.get('id')),
                'description': dataset.get('comments').get('value') if dataset.get('comments') else '',
                'size': int(dataset.get('volsize').get('rawvalue')),
                'name': self.xlst_name_from_id(dataset.get('id')),
                'id': self.xslt_dataset_to_volume(dataset.get('id')),
                'config': {
                    'compression': dataset.get('compression').get('value'),
                    'deduplication': dataset.get('deduplication').get('value'),
                    'sync': dataset.get('sync').get('value'),
                    'volblocksize': dataset.get('volblocksize').get('value'),
                    'target_scope': 'volume'  # FIXME
                }
            }
            return volume
        except Exception:
            self.csp_error('Exception', traceback.format_exc())

        return {}

    def discovery_ips(self):

        # grab portal IPs
        portal = self.fetch('iscsi/portal', field='comment',
                           value=self.target_portal)

        discovery_ips = []

        if not isinstance(portal, list):
            for listen in portal.get('listen'):
                discovery_ips.append(listen.get('ip'))

        return discovery_ips

    def valid_iscsi_basename(self, basename):
        if basename in self.target_basenames:
            return True

    def snapshot_to_snapshot(self, snapshot):
        try:
            csi_resp = {
                'id': self.xslt_dataset_to_volume(snapshot.get('id')),
                'name': snapshot.get('snapshot_name'),
                #'size': int(snapshot.get('properties').get('volsize').get('rawvalue')),
                'description': 'Snapshot of {parent}'.format(parent=self.xlst_name_from_id(snapshot.get('dataset'))),
                'volume_id': self.xslt_dataset_to_volume(snapshot.get('dataset')),
                'volume_name': self.xlst_name_from_id(snapshot.get('dataset')),
                'creation_time': int(snapshot.get('properties').get('creation').get('rawvalue')),
                'ready_to_use': True,
                'config': {}
            }
            return csi_resp
        except Exception:
            self.csp_error('Exception', traceback.format_exc())

        return {}

    # pool/dataset, field=name, value=foo, attr=rawvalue
    def fetch(self, resource, **kwargs):
        results = []
        options = {}
        query = {}
        filters = []
        operator = kwargs.get('operator', '=')
        attr = kwargs.get('attr')
        field = kwargs.get('field')
        value = kwargs.get('value')
        extras = kwargs.get('extras')
        returnBy = kwargs.get('returnBy')

        if extras:
            options = { "extra": extras }

        if field and value:
            filters.append([ field, operator, value ])

        if filters or options:
            query = {
                        "query-filters": filters,
                        "query-options": options
                    }

        self.logger.debug('Composed query: %s', query)

        try:
            self.get(resource, query)

            if self.req_backend.status_code != 200:  # FIXME
                self.logger.debug('TrueNAS GET Request through fetch: %s', self.req_backend.status_code)
                return None

            rset = self.req_backend.json()

            if not isinstance(rset, list):
                rset = [ rset ]

            for item in rset:
                if field and value:
                    self.logger.debug('Looking for field={field} and value={value}'.format(field=field,
                            value=value))
                    if attr:
                        value = item.get(field).get(attr)
                    else:
                        self.logger.debug('Nope %s', item)
                        value = item.get(field)

                    if not isinstance(value, str) and hasattr(value, 'match'):
                        if not value.match(value):
                            continue
                results.append(item)
        except Exception:
            self.csp_error('Backend Request (GET) Exception',
                           traceback.format_exc())

        if len(results) == 1:
            self.logger.debug('API fetch caught 1 item')

            if returnBy == list:
                return results
            else:
                return results[0]

        if len(results) > 1:
            self.logger.debug('API fetch caught %d items', len(results))

            if returnBy == dict:
                self.logger.debug('Returning first row in result set')
                return results[0]
            else:
                return results

        self.logger.debug('API fetch caught %d items (last resort)', len(results))

        if len(results) == 0:
            if returnBy == dict:
                return {}

        return results

    def uri_id(self, resource, rid):
        if resource in ('zfs/snapshot', 'pool/dataset'):
            uri = '{resource}/id/{rid}'.format(resource=resource,
                                               rid=rid.replace(self.dataset_divider, self.uri_slash))
        else:
            uri = '{resource}/id/{rid}'.format(resource=resource,
                                               rid=rid)
        return uri

    def get(self, uri, query={}):
        auth = self._get_auth()
        try:
            self.logger.debug('TrueNAS GET request URI: %s', uri)
            if type(auth) == HTTPBasicAuth:
                self.req_backend = requests.get(self.url_tmpl(uri),
                                    auth=auth, verify=False, json=query)
            else:
                self.req_backend = requests.get(self.url_tmpl(uri),
                                    headers=auth, verify=False, json=query)
            self.logger.debug('TrueNAS response: %s', self.req_backend.text)
            self.resp_msg = '{code} {reason}'.format(
                code=str(self.req_backend.status_code), reason=self.req_backend.reason)
            self.req_backend.raise_for_status()
        except Exception:
            self.csp_error('Backend Request (GET) Exception',
                           traceback.format_exc())

    def post(self, uri, content):
        auth = self._get_auth()
        try:
            self.logger.debug('TrueNAS POST request URI: %s', uri)
            self.logger.debug('TrueNAS request: %s', content)
            if type(auth) == HTTPBasicAuth:
                self.req_backend = requests.post(self.url_tmpl(uri),
                                    auth=auth, json=content, verify=False)
            else:
                self.req_backend = requests.post(self.url_tmpl(uri),
                                    headers=auth, json=content, verify=False)
            self.logger.debug('TrueNAS response: %s', self.req_backend.json())
            self.resp_msg = '{code} {reason}'.format(
                code=str(self.req_backend.status_code), reason=self.req_backend.reason)
            self.req_backend.raise_for_status()
        except Exception:
            self.csp_error('Backend Request (POST) Exception: {msg}'.format(msg=self.resp_msg),
                           traceback.format_exc())


    def put(self, uri, content):
        auth = self._get_auth()
        try:
            self.logger.debug('TrueNAS PUT request URI: %s', uri)
            self.logger.debug('TrueNAS request: %s', content)
            if type(auth) == HTTPBasicAuth:
                self.req_backend = requests.put(self.url_tmpl(uri),
                                    auth=auth, json=content, verify=False)
            else:
                self.req_backend = requests.put(self.url_tmpl(uri),
                                    headers=auth, json=content, verify=False)
            self.logger.debug('TrueNAS response: %s', self.req_backend.json())
            self.resp_msg = '{code} {reason}'.format(
                code=str(self.req_backend.status_code), reason=self.req_backend.reason)
            self.req_backend.raise_for_status()
        except Exception:
            self.csp_error('Backend Request (PUT) Exception: {msg}'.format(msg=self.resp_msg),
                           traceback.format_exc())


    def delete(self, uri, **kwargs):
        headers = { 'Content-Type': 'application/json' }
        auth = self._get_auth()
        try:
            self.logger.debug('TrueNAS DELETE request URI: %s', uri)
            body = kwargs.get('body') if kwargs.get('body') else None
            self.logger.debug('Embedding content in DELETE body: %s', body)

            # ensure uri
            exist = self.fetch(uri)

            if not exist:
                self.logger.info('{msg} {uri}'.format(msg=self.resp_msg, uri=uri))
                return

            if type(auth) == HTTPBasicAuth:
                self.req_backend = requests.delete(self.url_tmpl(uri),
                                    data=body, auth=auth, headers=headers, verify=False)
            else:
                auth.update(headers)
                self.req_backend = requests.delete(self.url_tmpl(uri),
                                    data=body, headers=auth, verify=False)
            self.resp_msg = '{code} {reason}'.format(
                code=str(self.req_backend.status_code), reason=self.req_backend.reason)
            self.logger.debug('TrueNAS response code: %s', self.req_backend.status_code)
            self.logger.debug('TrueNAS response msg: %s', self.req_backend.content.decode('utf-8'))
            self.req_backend.raise_for_status()
        except Exception:
            self.csp_error('Backend Request (DELETE) Exception: {msg}'.format(msg=self.resp_msg),
                           traceback.format_exc())
        sleep(self.backend_delay) #FIXME


    def get_target(self, access_name, **kwargs):

        results = {}
        targetextent = {}

        target = self.fetch('iscsi/target', field='name', value=access_name)
        extent = self.fetch('iscsi/extent', field='name', value=access_name)

        if extent:
            targetextent = self.fetch('iscsi/targetextent', field='extent',
                    value=extent.get('id'))

        if target and extent and targetextent:
            results = {
                        'target': target,
                        'extent': extent,
                        'targetextent': targetextent
                      }

        return results


    def create_target(self, dataset, **kwargs):
        # content will only be available at provisioning
        content = kwargs.get('content', {})
        config = content.get('config', {})

        self.logger.debug('Content during target creation: %s', content)
        self.logger.debug('Config during target creation: %s', config)

        try:
            dataset_name = self.xlst_name_from_id(dataset.get('id'))
            dataset_id = self.xslt_id_to_dataset(dataset.get('id'))
            access_name = self.access_name.format(dataset_name=dataset_name)

            discovery_ips = self.discovery_ips()

            # grab portal IPs
            portal = self.fetch('iscsi/portal', field='comment',
                               value=self.target_portal)

            # access group
            req_backend = {
                'name': access_name,
            }

            system_version = self.version()

            # treat SCALE
            if system_version == "SCALE":
                custom_networks = config.get('auth_networks')
                if custom_networks:
                    req_backend['auth_networks'] = self.auth_networks_validate(custom_networks)
                    self.logger.debug('Using custom auth_networks: %s', req_backend['auth_networks'])
                else:
                    req_backend['auth_networks'] = self.ipaddrs_to_networks(discovery_ips)
                    self.logger.debug('Using discovery auth_networks: %s', req_backend['auth_networks'])

            target = self.fetch('iscsi/target', field='name', value=access_name)

            if not target:
                target_created = self.backend_retries

                while target_created:
                    self.post('iscsi/target', req_backend)
                    target = self.req_backend.json()
                    if target.get('id'):
                        self.logger.debug('Target created: %s', access_name)
                        break
                    else:
                        self.logger.debug('Target debug: %s',
                                self.req_backend.json())

                    sleep(self.backend_delay)
                    target_created -= 1

            # add extent to dataset
            req_backend = {
                'type': 'DISK',
                'comment': 'Managed by HPE CSI Driver for Kubernetes',
                'name': access_name,
                'disk': 'zvol/{dataset_id}'.format(dataset_id=dataset_id)
            }

            self.post('iscsi/extent', req_backend)
            extent = self.req_backend.json()
            self.logger.debug('Extent created: %s', extent)

            # add target to extent
            req_backend = {
                'target': target.get('id'),
                'extent': extent.get('id'),
                'lunid': 0
            }

            self.post('iscsi/targetextent', req_backend)
            targetextent = self.req_backend.json()
            self.logger.debug('Target Extent created: %s', targetextent)

            results = {
                        'target': target,
                        'extent': extent,
                        'targetextent': targetextent
                      }

            return results

        except Exception:
            self.csp_error('Exception', traceback.format_exc())
            return {}

    def apply_publish(self, access_name, **kwargs):

        content = {}
        publish = {}
        dataset = {}

        if kwargs.get('content') and kwargs.get('dataset'):
            content = kwargs.get('content')
            dataset = kwargs.get('dataset')

        if access_name and content and dataset:

            # check if target already exist
            # needed to preserve pre-2.5.0 functionality
            existing_target = self.get_target(access_name, content=content)

            if not existing_target:
                create_target = self.create_target(dataset, content=content)
                if create_target:
                    publish['target'] = create_target
            else:
                    publish['target'] = existing_target

            # grab host
            host = self.fetch(
                'iscsi/initiator', field='comment', value=content.get('host_uuid'), returnBy=dict)

            if host:
                self.logger.debug('Existing host initiator: %s', host.get('id'))

            # grab initiator
            initiator = self.fetch(
                'iscsi/initiator', field='comment', value=access_name, returnBy=dict)

            if initiator:
                self.logger.debug('Existing target initiator: %s', initiator.get('id'))
            else:
                initiator = self.apply_initiator(access_name)

            # merge host initiators to target initiators
            initiators = list(set(initiator['initiators'] + host.get('initiators')))

            # update initiator
            req_backend = {
                'initiators': initiators,
            }

            # CORE and FreeNAS
            system_version = self.version()

            if system_version == "CORE" or system_version == "LEGACY":
                # merge host networks to target initiator
                networks = list(set(self.cidrs_to_hosts(host.get('auth_network'))
                    + initiator.get('auth_network')))
                req_backend['auth_network'] = networks

            self.put('iscsi/initiator/id/{id}'.format(id=initiator.get('id')), req_backend)
            publish['initiator'] = self.req_backend.json()

            # need portal
            publish['portal'] = self.fetch('iscsi/portal', field='comment',
                               value=self.target_portal)

            # portal grouping
            portal_group = {
                'portal': publish.get('portal').get('id'),
                'initiator': publish.get('initiator', {}).get('id')
            }

            # deal with CHAP
            auth = self.fetch('iscsi/auth', field='tag', value=int(self.chap_tag), returnBy=dict)

            if auth:
                portal_group['auth'] = self.chap_tag
                portal_group['authmethod'] = "CHAP"

            # need global iSCSI config
            publish['iscsi_config'] = self.fetch('iscsi/global')

            # access group
            req_backend = {
                'name': access_name,
                'groups': [ portal_group ]
            }

            target_id = publish.get('target', {}).get('target', {}).get('id')

            if target_id:
                # update target groups
                self.put('iscsi/target/id/{tid}'.format(tid=target_id), req_backend)
                publish['target']['target'] = self.req_backend.json()
            else:
                publish = {}

        return publish


    def auth_networks_validate(self, networks):
        res = []
        cidrs = re.split(r'\s*,\s*', networks)

        for cidr in cidrs:
            if ip_network(cidr):
                res.append(cidr)

        return res

    def dataset_is_busy(self, dataset):
        ds = self.fetch('pool/dataset', field='origin.value',
                value='{name}@'.format(name=dataset.get('id')), operator='^')

        if ds:
            self.logger.debug('ZFS dataset has dependents: %s', dataset)
            return True

        snapshots = self.fetch('zfs/snapshot', field='name',
                value='{name}@'.format(name=dataset.get('id')), operator='^',
                returnBy=list)

        for snapshot in snapshots:
            if snapshot.get('holds') or int(snapshot.get('properties').get('numclones').get('value')) > 0:
                self.logger.debug('ZFS snapshot is busy: %s', snapshot.get('id'))
                return True

        # nothing to see here
        self.logger.debug('ZFS dataset clear for removal: %s', dataset.get('id'))
        return False
