import unittest
from xml.dom.minidom import parseString

from urllib.parse import urlencode
from flask import Response, json
from flask.testing import FlaskClient
from flask_jwt_extended import JWTManager, create_access_token

import server


class ApiTestCase(unittest.TestCase):
    """Test case for server API"""

    def setUp(self):
        server.app.testing = True
        self.app = FlaskClient(server.app, Response)
        JWTManager(server.app)

    def tearDown(self):
        pass

    def jwtHeader(self):
        with server.app.test_request_context():
            access_token = create_access_token('test')
        return {'Authorization': 'Bearer {}'.format(access_token)}

    def test_info_db(self):
        params = {
            'service': 'WMS',
            'request': 'GetFeatureInfo',
            'info_format': 'text/xml',
            'version': '1.3.0',
            'layers': 'test_poly',
            'i': 1280,
            'j': 1024,
            'height': 512,
            'width': 640,
            'bbox': "1200000,-4560000,1400000,-4540000",
            'crs': 'EPSG:2056'
        }
        response = self.app.get('/somap?' + urlencode(params), headers=self.jwtHeader())

        doc = parseString(response.data)
        featureInfoResponses = doc.getElementsByTagName("GetFeatureInfoResponse")
        self.assertEqual(len(featureInfoResponses), 1)
        layers = featureInfoResponses[0].getElementsByTagName("Layer")
        self.assertEqual(len(layers), 1)
        features = layers[0].getElementsByTagName("Feature")
        self.assertEqual(len(features), 1)
        self.assertEqual(features[0].getAttribute("id"), "1")
        htmlContents = features[0].getElementsByTagName("HtmlContent")
        self.assertEqual(len(htmlContents), 1)

    def test_info_module(self):
        params = {
            'service': 'WMS',
            'request': 'GetFeatureInfo',
            'info_format': 'text/xml',
            'version': '1.3.0',
            'layers': 'test_point',
            'i': 1280,
            'j': 1024,
            'height': 512,
            'width': 640,
            'bbox': "1200000,-4560000,1400000,-4540000",
            'crs': 'EPSG:2056'
        }
        response = self.app.get('/somap?' + urlencode(params), headers=self.jwtHeader())

        doc = parseString(response.data)
        featureInfoResponses = doc.getElementsByTagName("GetFeatureInfoResponse")
        self.assertEqual(len(featureInfoResponses), 1)
        layers = featureInfoResponses[0].getElementsByTagName("Layer")
        self.assertEqual(len(layers), 1)
        features = layers[0].getElementsByTagName("Feature")
        self.assertEqual(len(features), 1)
        self.assertEqual(features[0].getAttribute("id"), "123")
        htmlContents = features[0].getElementsByTagName("HtmlContent")
        self.assertEqual(len(htmlContents), 1)
