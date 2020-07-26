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

import falcon
import backend
import truenascsp


class PostLogger:
    def process_response(self, req, resp, resource, req_succeded):
        api = req.context

        api.logger.debug('Falcon Response (to HPE CSI): %s', resp.status)
        api.logger.debug('Last backend requests Response: %s', api.resp_msg)


class TokenHandler:
    def process_request(self, req, resp):
        content = req.media
        token = None
        array = None
        tokens_url = req.url.find('/containers/v1/tokens/')

        api = backend.Handler()
        req.context = api

        if tokens_url != -1 and req.method == 'DELETE':
            req.context = api
            return

        if content:
            token = content.get('password')
            array = content.get('array_ip')

        if None in (token, array):
            token = req.get_header('x-auth-token')
            array = req.get_header('x-array-ip')

        if not token:
            reason = 'Missing token'
            description = 'Missing x-auth-token in header or password in Tokens request'
            api.logger.info('%s: %s', reason, description)
            raise falcon.HTTPUnauthorized(reason, description)

        if not array:
            reason = 'Missing backend array IP'
            description = 'Missing x-array-ip in header or array_ip in Tokens request'
            api.logger.info('%s: %s', reason, description)
            raise falcon.HTTPBadRequest(reason, description)

        api.backend = array
        api.token = token

        api.ping(req)

        if not api.pong:
            reason = 'Authentication failed'
            description = 'Unable to authenticate with provided credentials'
            api.logger.info('%s: %s', reason, description)
            raise falcon.HTTPUnauthorized(reason, description)

# Serve!
SERVE = falcon.API(middleware=[TokenHandler(), PostLogger()])

# Routes
SERVE.add_route('/containers/v1/tokens/{token_id:int}', truenascsp.Tokens())
SERVE.add_route('/containers/v1/tokens', truenascsp.Tokens())

SERVE.add_route('/containers/v1/hosts/{host_id}', truenascsp.Hosts())
SERVE.add_route('/containers/v1/hosts', truenascsp.Hosts())

SERVE.add_route('/containers/v1/volumes/{volume_id}', truenascsp.Volume())
SERVE.add_route('/containers/v1/volumes', truenascsp.Volumes())

SERVE.add_route('/containers/v1/volumes/{volume_id}/actions/publish', truenascsp.Publish())
SERVE.add_route('/containers/v1/volumes/{volume_id}/actions/unpublish', truenascsp.Unpublish())

SERVE.add_route('/containers/v1/snapshots/{snapshot_id}', truenascsp.Snapshot())
SERVE.add_route('/containers/v1/snapshots', truenascsp.Snapshots())
