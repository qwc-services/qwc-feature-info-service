import locale
import os

from flask import Flask, Response, jsonify, request
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
info_parser.add_argument('layers', required=True, type=str)
info_parser.add_argument('styles', type=str)
info_parser.add_argument('i', type=int)
info_parser.add_argument('j', type=int)
info_parser.add_argument('bbox', type=str)
info_parser.add_argument('filter', type=str)
info_parser.add_argument('filter_geom', type=str)
info_parser.add_argument('height', required=True, type=int)
info_parser.add_argument('width', required=True, type=int)
info_parser.add_argument('crs', required=True, type=str)
info_parser.add_argument('feature_count', default=1, type=int)
info_parser.add_argument('with_geometry', default="true", type=str)
info_parser.add_argument('with_maptip', default="true", type=str)
info_parser.add_argument('FI_POINT_TOLERANCE', default=16, type=int)
info_parser.add_argument('FI_LINE_TOLERANCE', default=8, type=int)
info_parser.add_argument('FI_POLYGON_TOLERANCE', default=4, type=int)
info_parser.add_argument('LAYERATTRIBS', default="", type=str)
info_parser.add_argument('GEOMCENTROID', default="false", type=str)
info_parser.add_argument('with_htmlcontent', default="true", type=str)
info_parser.add_argument('with_bbox', default="true", type=str)


# routes
@api.route('/<path:service_name>')
@api.param('service_name', 'Service name corresponding to WMS, e.g. `qwc_demo`')
class FeatureInfo(Resource):

    @api.doc('featureinfo')
    @api.param('layers', 'The layer names, e.g. `countries,edit_lines`')
    @api.param('styles', 'The layer style')
    @api.param('i', 'X ordinate of query point on map, in pixels, e.g. `51`. '
               'Required unless filter_geom or filter are specified.')
    @api.param('j', 'Y ordinate of query point on map, in pixels, e.g. `51`. '
               'Required unless filter_geom or filter are specified.')
    @api.param('filter', 'Filter expression. '
               'Can be specified instead of i and j.')
    @api.param('filter_geom', 'Filter geometry, as a WKT string. '
               'Can be specified instead of i and j.')
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
        """
        Return feature info for specified layers
        """
        return self.__process_request(request.args, service_name)

    @api.expect(info_parser)
    @optional_auth
    def post(self, service_name):
        """
        Return feature info for specified layers
        """
        return self.__process_request(request.values, service_name)

    def __process_request(self, args, service_name):
        """
        Process a feature info request

        :param list args: The full query, passed either as GET querystring or POST formdata
        :param str service_name: The OGC service name
        """

        # Params from the info_parser RequestParser
        params = info_parser.parse_args()

        # Remove None entries, else they will get encoded as 'None' string values
        # by urlencode when constructing the request
        # https://bugs.python.org/issue18857
        params = {
            key: value for key, value in params.items()
            if value is not None
        }

        # Add extra arguments not handled by info_parser
        for arg in args:
            if not arg in params:
                params[arg] = args[arg]

        layers = params['layers'].split(',')

        if 'filter' in params and params['filter']:
            # OK
            pass
        elif 'filter_geom' in params and params['filter_geom']:
            # OK
            pass
        elif 'i' in params and params['i'] and 'j' in params and params['j'] and 'bbox' in params and params['bbox']:
            # OK
            pass
        else:
            api.abort(404, "Either filter, filter_geom, or i and j, are required")

        info_service = info_service_handler()
        result = info_service.query(
            get_identity(), service_name, layers, params
        )

        return Response(
            result,
            content_type='text/xml; charset=utf-8',
            status=200
        )


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
