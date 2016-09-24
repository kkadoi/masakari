# Copyright (c) 2016 NTT DATA
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""The Host API extension."""

from webob import exc

from masakari.api.openstack import extensions
from masakari.api.openstack.ha.schemas import hosts as schema
from masakari.api.openstack import wsgi
from masakari.api import validation
from masakari import exception
from masakari.ha import api as host_api

ALIAS = "os-hosts"
authorize = extensions.os_masakari_authorizer(ALIAS)


class HostsController(wsgi.Controller):
    """The Host API controller for the OpenStack API."""

    def __init__(self):
        self.api = host_api.HostAPI()

    @extensions.expected_errors((400, 403, 404))
    def index(self, req, segment_id):
        """Returns a list a hosts."""
        context = req.environ['masakari.context']
        authorize(context)

        try:
            hosts = self.api.get_all(context, req, segment_id)
        except exception.MarkerNotFound as ex:
            raise exc.HTTPBadRequest(explanation=ex.format_message())
        except exception.InvalidInput as e:
            raise exc.HTTPBadRequest(explanation=e.format_message())
        except exception.FailoverSegmentNotFound as ex:
            raise exc.HTTPNotFound(explanation=ex.format_message())

        return {'hosts': hosts}

    @extensions.expected_errors((403, 404, 409))
    @validation.schema(schema.create)
    def create(self, req, segment_id, body):
        """Creates a host."""
        context = req.environ['masakari.context']
        authorize(context)
        host_data = body.get('host')
        try:
            host = self.api.create_host(context, segment_id, host_data)
        except exception.FailoverSegmentNotFound as e:
            raise exc.HTTPNotFound(explanation=e.format_message())
        except exception.HostExists as e:
            raise exc.HTTPConflict(explanation=e.format_message())

        return {'host': host}

    @extensions.expected_errors((403, 404))
    def show(self, req, segment_id, id):
        """Shows the details of a host."""
        context = req.environ['masakari.context']
        authorize(context)
        try:
            host = self.api.get_host(context, segment_id, id)
        except exception.HostNotFound as e:
            raise exc.HTTPNotFound(explanation=e.format_message())
        except exception.FailoverSegmentNotFound as e:
            raise exc.HTTPNotFound(explanation=e.format_message())
        return {'host': host}

    @extensions.expected_errors((403, 404, 409))
    @validation.schema(schema.update)
    def update(self, req, segment_id, id, body):
        """Updates the existing host."""
        context = req.environ['masakari.context']
        authorize(context)
        host_data = body.get('host')
        try:
            host = self.api.update_host(context, segment_id, id, host_data)
        except exception.HostNotFound as e:
            raise exc.HTTPNotFound(explanation=e.format_message())
        except exception.FailoverSegmentNotFound as e:
            raise exc.HTTPNotFound(explanation=e.format_message())
        except exception.HostExists as e:
            raise exc.HTTPConflict(explanation=e.format_message())

        return {'host': host}

    @extensions.expected_errors((403, 404))
    def delete(self, req, segment_id, id):
        """Removes a host by id."""
        context = req.environ['masakari.context']
        authorize(context)
        try:
            self.api.delete_host(context, segment_id, id)
        except exception.FailoverSegmentNotFound as e:
            raise exc.HTTPNotFound(explanation=e.format_message())
        except exception.HostNotFound as e:
            raise exc.HTTPNotFound(explanation=e.format_message())


class Hosts(extensions.V1APIExtensionBase):
    """Hosts controller"""

    name = "Hosts"
    alias = ALIAS
    version = 1

    def get_resources(self):
        parent = {'member_name': 'segment',
                  'collection_name': 'segments'}
        resources = [
            extensions.ResourceExtension(
                'hosts', HostsController(), parent=parent,
                member_name='host')]

        return resources

    def get_controller_extensions(self):
        return []
