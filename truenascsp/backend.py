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

from os import environ
import traceback
import logging
import json
import urllib3
import requests
from requests.auth import HTTPBasicAuth

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
        self.target_basename = 'iqn.2011-08.org.truenas.ctl'
        self.target_portal = 'hpe-csi'

        self.logger = logging.getLogger('{name}'.format(name=__name__))
        self.logger.setLevel(logging.DEBUG if environ.get(
            'LOG_DEBUG') else logging.INFO)

        self.dataset_defaults = {
            'deduplication': environ.get('DEFAULT_DEDUPLICATION', 'OFF'),
            'compression': environ.get('DEFAULT_COMPRESSION', 'LZ4'),
            'sync': environ.get('DEFAULT_SYNC', 'STANDARD'),
            'sparse': environ.get('DEFAULT_SPARSE', 1),
            'root': environ.get('DEFAULT_ROOT', 'tank'),
            'volblocksize': environ.get('DEFAULT_VOLBLOCKSIZE', '8K'),
            'description': environ.get('DEFAULT_DESCRIPTION', 'Dataset created by HPE CSI Driver for Kubernetes')
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
        If the username is given as "root", assumes
        FreeNAS <v12 that does NOT support API Keys
        """

        if self.token.find("root:") > -1:
            # Support for FreeNAS <v12
            self.logger.debug("Using Basic Auth for authentication")
            return HTTPBasicAuth("root", self.token.split(":")[1])
        else:
            self.logger.debug("API Key detected. Will use token auth.")
            return {
                'Authorization': 'Bearer {token}'.format(token=self.token)
            }

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

    def dataset_has_target(self, dataset):
        target = self.fetch('iscsi/target', field='name',
                            value=self.xlst_name_from_id(dataset))

        if target:
            return True
        return False

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
                'published': self.dataset_has_target(dataset.get('id')),
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

    def snapshot_to_snapshot(self, snapshot):
        try:
            csi_resp = {
                'id': self.xslt_dataset_to_volume(snapshot.get('id')),
                'name': snapshot.get('snapshot_name'),
                'size': int(snapshot.get('properties').get('volsize').get('rawvalue')),
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
        try:
            self.get(resource)

            if self.req_backend.status_code != 200:  # FIXME
                self.logger.debug('TrueNAS GET Request through fetch: %s', self.req_backend.status_code)
                return None

            rset = self.req_backend.json()

            for item in rset:
                if kwargs.get('field') and kwargs.get('value'):
                    if kwargs.get('attr'):
                        value = item.get(kwargs.get('field')).get(
                            kwargs.get('attr'))
                    else:
                        value = item.get(kwargs.get('field'))

                    if not isinstance(kwargs.get('value'), str):
                        if not kwargs.get('value').match(value):
                            continue
                    else:
                        if kwargs.get('value') != value:
                            continue
                results.append(item)
        except Exception:
            self.csp_error('Backend Request (GET) Exception',
                           traceback.format_exc())

        if len(results) == 1:
            self.logger.debug('API fetch caught 1 item')
            return results[0]

        if len(results) > 1:
            self.logger.debug('API fetch caught %d items', len(results))
            return results

        return None

    def uri_id(self, resource, rid):
        if resource in ('zfs/snapshot', 'pool/dataset'):
            uri = '{resource}/id/{rid}'.format(resource=resource,
                                               rid=rid.replace(self.dataset_divider, self.uri_slash))
        else:
            uri = '{resource}/id/{rid}'.format(resource=resource,
                                               rid=rid)
        return uri

    def get(self, uri):
        auth = self._get_auth()
        try:
            self.logger.debug('TrueNAS GET request URI: %s', uri)
            if type(auth) == HTTPBasicAuth:
                self.req_backend = requests.get(self.url_tmpl(uri),
                                    auth=auth, verify=False)
            else:
                self.req_backend = requests.get(self.url_tmpl(uri),
                                    headers=auth, verify=False)
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
            self.csp_error('Backend Request (POST) Exception',
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
            self.csp_error('Backend Request (PUT) Exception',
                           traceback.format_exc())

    def delete(self, uri, **kwargs):
        headers = { 'Content-Type': 'application/json' }
        auth = self._get_auth()
        try:
            self.logger.debug('TrueNAS DELETE request URI: %s', uri)
            body = kwargs.get('body') if kwargs.get('body') else None 
            if type(auth) == HTTPBasicAuth:
                self.req_backend = requests.delete(self.url_tmpl(uri),
                                    json=body, auth=auth, headers=headers, verify=False)
            else:
                auth.update(headers)
                self.req_backend = requests.delete(self.url_tmpl(uri),
                                    json=kwargs.get('body'), headers=auth, verify=False)
            self.resp_msg = '{code} {reason}'.format(
                code=str(self.req_backend.status_code), reason=self.req_backend.reason)
            self.logger.debug('TrueNAS response: %s', self.req_backend.status_code)
            self.req_backend.raise_for_status()
        except Exception:
            self.csp_error('Backend Request (DELETE) Exception',
                           traceback.format_exc())
