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

"""Tests for the failover segment api."""

import mock
from webob import exc

from masakari import exception
from masakari.ha import api as ha_api
from masakari.objects import base as obj_base
from masakari.objects import segment as segment_obj
from masakari import test
from masakari.tests.unit.api.openstack import fakes
from masakari.tests import uuidsentinel


def _make_segment_obj(segment_dict):
    return segment_obj.FailoverSegment(**segment_dict)


def _make_segments_list(segments_list):
    return segment_obj.FailoverSegment(objects=[
        _make_segment_obj(a) for a in segments_list])

FAILOVER_SEGMENT_LIST = [
    {"name": "segment1", "id": "1", "service_type": "COMPUTE",
     "recovery_method": "auto", "uuid": uuidsentinel.fake_segment,
     "description": "failover_segment for compute"},

    {"name": "segment2", "id": "2", "service_type": "CINDER",
     "recovery_method": "reserved_host", "uuid": uuidsentinel.fake_segment2,
     "description": "failover_segment for cinder"}]

FAILOVER_SEGMENT_LIST = _make_segments_list(FAILOVER_SEGMENT_LIST)

FAILOVER_SEGMENT = {"name": "segment1", "id": "1", "description": "something",
                    "service_type": "COMPUTE", "recovery_method": "auto",
                    "uuid": uuidsentinel.fake_segment}

FAILOVER_SEGMENT = _make_segment_obj(FAILOVER_SEGMENT)


class FailoverSegmentAPITestCase(test.NoDBTestCase):
    """Test Case for failover segment api."""

    def setUp(self):
        super(FailoverSegmentAPITestCase, self).setUp()
        self.segment_api = ha_api.FailoverSegmentAPI()
        self.req = fakes.HTTPRequest.blank('/v1/segments',
                                           use_admin_context=True)
        self.context = self.req.environ['masakari.context']

    def _assert_segment_data(self, expected, actual):
        self.assertTrue(obj_base.obj_equal_prims(expected, actual),
                        "The failover segment objects were not equal")

    @mock.patch.object(segment_obj.FailoverSegmentList, 'get_all')
    def test_get_all(self, mock_get_all):

        mock_get_all.return_value = FAILOVER_SEGMENT_LIST

        result = self.segment_api.get_all(self.context, self.req)
        self._assert_segment_data(FAILOVER_SEGMENT_LIST,
                                  _make_segments_list(result))

    @mock.patch.object(segment_obj.FailoverSegmentList, 'get_all')
    def test_get_all_marker_not_found(self, mock_get_all):

        mock_get_all.side_effect = exception.MarkerNotFound
        self.req = fakes.HTTPRequest.blank('/v1/segments?limit=100',
                                           use_admin_context=True)
        self.assertRaises(exception.MarkerNotFound, self.segment_api.get_all,
                          self.context, self.req)

    def test_get_all_marker_negative(self):

        self.req = fakes.HTTPRequest.blank('/v1/segments?limit=-1',
                                           use_admin_context=True)
        self.assertRaises(exc.HTTPBadRequest, self.segment_api.get_all,
                          self.context, self.req)

    @mock.patch.object(segment_obj.FailoverSegmentList, 'get_all')
    def test_get_all_by_recovery_method(self, mock_get_all):
        self.req = fakes.HTTPRequest.blank('/v1/segments?recovery_method=auto',
                                           use_admin_context=True)
        self.segment_api.get_all(self.context, self.req)
        mock_get_all.assert_called_once_with(self.context, filters={
            'recovery_method': 'auto'}, sort_keys=[
            'name'], sort_dirs=['asc'], limit=1000, marker=None)

    @mock.patch.object(segment_obj.FailoverSegmentList, 'get_all')
    def test_get_all_invalid_sort_dir(self, mock_get_all):

        mock_get_all.side_effect = exception.InvalidInput
        self.req = fakes.HTTPRequest.blank('/v1/segments?sort_dir=abcd',
                                           use_admin_context=True)
        self.assertRaises(exception.InvalidInput, self.segment_api.get_all,
                          self.context, self.req)

    @mock.patch.object(segment_obj, 'FailoverSegment',
                       return_value=_make_segment_obj(FAILOVER_SEGMENT))
    @mock.patch.object(segment_obj.FailoverSegment, 'create')
    def test_create(self, mock_segment_obj, mock_create):
        segment_data = {"name": "segment1",
                        "service_type": "COMPUTE",
                        "recovery_method": "auto",
                        "description": "something"}
        mock_segment_obj.create = mock.Mock()
        result = self.segment_api.create_segment(self.context, segment_data)
        self._assert_segment_data(FAILOVER_SEGMENT, _make_segment_obj(result))

    @mock.patch.object(segment_obj.FailoverSegment, 'get_by_uuid')
    def test_get_segment(self, mock_get_segment):

        mock_get_segment.return_value = FAILOVER_SEGMENT

        result = self.segment_api.get_segment(self.context,
                                              uuidsentinel.fake_segment)
        self._assert_segment_data(FAILOVER_SEGMENT, _make_segment_obj(result))

    @mock.patch.object(segment_obj.FailoverSegment, 'get_by_uuid')
    def test_get_segment_not_found(self, mock_get_segment):

        self.assertRaises(exception.FailoverSegmentNotFound,
                          self.segment_api.get_segment, self.context, '123')

    @mock.patch.object(segment_obj, 'FailoverSegment',
                       return_value=_make_segment_obj(FAILOVER_SEGMENT))
    @mock.patch.object(segment_obj.FailoverSegment, 'save')
    @mock.patch.object(segment_obj.FailoverSegment, 'get_by_uuid')
    def test_update(self, mock_get, mock_update, mock_segment_obj):
        segment_data = {"name": "segment1"}
        mock_get.return_value = _make_segment_obj(FAILOVER_SEGMENT)
        mock_segment_obj.update = mock.Mock()
        result = self.segment_api.update_segment(self.context,
                                                 uuidsentinel.fake_segment,
                                                 segment_data)
        self._assert_segment_data(FAILOVER_SEGMENT, _make_segment_obj(result))