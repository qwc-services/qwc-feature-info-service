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

    def test_info_module(self):
        params = {
            'service': 'WMS',
            'request': 'GetFeatureInfo',
            'info_format': 'text/xml',
            'version': '1.3.0',
            'layers': 'edit_points',
            'i': 51,
            'j': 51,
            'height': 101,
            'width': 101,
            'bbox': "671639,5694018,1244689,6267068",
            'crs': 'EPSG:3857'
        }
        response = self.app.get('/qwc_demo?' + urlencode(params), headers=self.jwtHeader())

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
