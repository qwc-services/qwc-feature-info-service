import locale
import os

from flask import Flask, Response, jsonify
from flask_restx import Api, Resource, reqparse
from jwt.exceptions import InvalidSignatureError

from qwc_services_core.auth import auth_manager, optional_auth, get_identity
from qwc_services_core.api import CaseInsensitiveArgument
from qwc_services_core.tenant_handler import TenantHandler
from feature_info_service import FeatureInfoService


# set locale for value formatting
locale.setlocale(locale.LC_ALL, os.environ.get('LANG', 'C'))

# Flask application
app = Flask(__name__)
# Flask-RESTPlus Api
api = Api(app, version='1.0', title='FeatureInfo service API',
          description="""API for QWC FeatureInfo service.

Query layers at a geographic position using an API based on WMS GetFeatureInfo.
          """,
          default_label='FeatureInfo operations', doc='/api/'
          )
# omit X-Fields header in docs
app.config['RESTPLUS_MASK_SWAGGER'] = False
# disable verbose 404 error message
app.config['ERROR_404_HELP'] = False

# Setup the Flask-JWT-Extended extension
jwt = auth_manager(app, api)

# create tenant handler
tenant_handler = TenantHandler(app.logger)


def info_service_handler():
    """Get or create a FeatureInfoService instance for a tenant."""
    tenant = tenant_handler.tenant()
    handler = tenant_handler.handler('featureInfo', 'info', tenant)
    if handler is None:
        handler = tenant_handler.register_handler(
            'info', tenant, FeatureInfoService(tenant, app.logger))
    return handler


# request parser
info_parser = reqparse.RequestParser(argument_class=CaseInsensitiveArgument)
info_parser.add_argument('layers', required=True)
info_parser.add_argument('i')
info_parser.add_argument('j')
info_parser.add_argument('bbox')
info_parser.add_argument('filter_geom')
info_parser.add_argument('height', required=True)
info_parser.add_argument('width', required=True)
info_parser.add_argument('crs', required=True)
info_parser.add_argument('feature_count', default=1)
info_parser.add_argument('with_geometry', default=1)
info_parser.add_argument('with_maptip', default=1)
info_parser.add_argument('FI_POINT_TOLERANCE', default=16)
info_parser.add_argument('FI_LINE_TOLERANCE', default=8)
info_parser.add_argument('FI_POLYGON_TOLERANCE', default=4)


# routes
@api.route('/<path:service_name>')
@api.param('service_name', 'Service name corresponding to WMS, e.g. `qwc_demo`')
class FeatureInfo(Resource):
    @api.doc('featureinfo')
    @api.param('layers', 'The layer names, e.g. `countries,edit_lines`')
    @api.param('i', 'X ordinate of query point on map, in pixels, e.g. `51`. '
               'Required unless filter_geom is specified.')
    @api.param('j', 'Y ordinate of query point on map, in pixels, e.g. `51`. '
               'Required unless filter_geom is specified.')
    @api.param('filter_geom', 'Filter geometry, as a WKT string. '
               'Required unless i and j and bbox are specified.')
    @api.param('height', 'Height of map output, in pixels, e.g. `101`')
    @api.param('width', 'Width of map output, in pixels, e.g. `101`')
    @api.param('bbox', 'Bounding box for map extent, '
               'e.g. `671639,5694018,1244689,6267068`. '
               'Required unless filter_geom is specified.')
    @api.param('crs', 'CRS for map extent, e.g. `EPSG:3857`')
    @api.param('feature_count', 'Max feature count')
    @api.param('with_geometry', 'Whether to return geometries in response')
    @api.param('with_maptip', 'Whether to return maptip in response')
    @api.param('FI_POINT_TOLERANCE', 'Tolerance for picking points, in pixels')
    @api.param('FI_LINE_TOLERANCE', 'Tolerance for picking lines, in pixels')
    @api.param('FI_POLYGON_TOLERANCE',
               'Tolerance for picking polygons, in pixels')
    @api.expect(info_parser)
    @optional_auth
    def get(self, service_name):
        """Submit query

        Return feature info for specified layers
        """
        args = info_parser.parse_args()
        layers = args['layers'].split(',')
        params = {
            'height': self.to_int(args['height'], 0),
            'width': self.to_int(args['width'], 0),
            'crs': args['crs'],
            'feature_count': self.to_int(args['feature_count'], 1),
            'with_geometry': self.to_int(args['with_geometry'], 1),
            'with_maptip': self.to_int(args['with_maptip'], 1),
            'FI_POINT_TOLERANCE': self.to_int(args['FI_POINT_TOLERANCE'], 16),
            'FI_LINE_TOLERANCE': self.to_int(args['FI_LINE_TOLERANCE'], 8),
            'FI_POLYGON_TOLERANCE': self.to_int(args["FI_POLYGON_TOLERANCE"], 4)
        }
        if 'filter_geom' in args and args['filter_geom']:
            params['filter_geom'] = args['filter_geom']
        elif 'i' in args and args['i'] and 'j' in args and args['j'] and 'bbox' in args and args['bbox']:
            params['i'] = self.to_int(args['i'], 0)
            params['j'] = self.to_int(args['j'], 0)
            params['bbox'] = args['bbox']
        else:
            api.abort(404, "Either filter_geom, or i and j, are required")

        info_service = info_service_handler()
        result = info_service.query(
            get_identity(), service_name, layers, params
        )

        return Response(
            result,
            content_type='text/xml; charset=utf-8',
            status=200
        )

    def to_int(self, value, default):
        """Convert string value to int

        :param str value: Input value
        :param int default: Default value if blank or not parseable
        """
        try:
            return int(value or default)
        except Exception as e:
            return default


""" readyness probe endpoint """
@app.route("/ready", methods=['GET'])
def ready():
    return jsonify({"status": "OK"})


""" liveness probe endpoint """
@app.route("/healthz", methods=['GET'])
def healthz():
    return jsonify({"status": "OK"})


# local webserver
if __name__ == '__main__':
    print("Starting FeatureInfo service...")
    app.run(host='localhost', port=5015, debug=True)
