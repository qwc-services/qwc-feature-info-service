import base64
from collections import OrderedDict
import html
from importlib import import_module
import re
import traceback
from urllib.parse import urljoin
from xml.dom.minidom import Document, Element, Text

from flask import json
from jinja2 import Template, TemplateError, TemplateSyntaxError

from qwc_services_core.database import DatabaseEngine
from qwc_services_core.permissions_reader import PermissionsReader
from qwc_services_core.runtime_config import RuntimeConfig

from info_modules.wms.layer_info import fetch_layer_infos as fetch_wms_layer_infos
from info_modules.wms.layer_info import parse_layer_info as parse_wms_layer_info
from info_modules.sql import layer_info as sql_layer_info
from info_templates import default_info_template, layer_template


class InfoFeature(object):
    """InfoFeature class for dynamic properties"""
    def __init__(self):
        self._attributes = []

    def add(self, name, value, alias, json_aliases):
        """Add attribute and value.

        :param str name: Attribute name
        :param obj value: Attribute value
        :param str alias: Attribute alias
        :param obj json_aliases: JSON attributes config
        """
        # set attribute as class property
        # NOTE: JSON values are not filtered to allow full access from
        #       custom info templates
        setattr(self, name, value)

        filtered_value = value
        if json_aliases and isinstance(value, list):
            # JSON aliases present and JSON value is a list
            # NOTE: filter list items, so that any keys not in JSON aliases
            #       are hidden in the default info templates
            filtered_value = []
            for json_item in value:
                # reorder item keys according to JSON aliases
                item = OrderedDict()
                for key in json_aliases:
                    if key in json_item:
                        item[key] = json_item[key]

                # NOTE: skip any keys not in JSON aliases

                filtered_value.append(item)

        # add to ordered attribute list
        self._attributes.append({
            'name': name,
            'value': filtered_value,
            'alias': alias,
            'type': type(value).__name__,
            'json_aliases': json_aliases
        })


class FeatureInfoService():
    """FeatureInfoService class

    Query layers at a geographic position using different layer info providers.
    """

    def __init__(self, tenant, logger):
        """Constructor

        :param str tenant: Tenant ID
        :param Logger logger: Application logger
        """
        self.tenant = tenant
        self.logger = logger

        config_handler = RuntimeConfig("featureInfo", logger)
        config = config_handler.tenant_config(tenant)

        if config.get('default_info_template'):
            self.default_info_template = config.get('default_info_template')
        elif config.get('default_info_template_base64'):
            self.default_info_template = self.b64decode(
                config.get('default_info_template_base64'),
                default_info_template, "default info template"
            )
        else:
            self.default_info_template = default_info_template

        self.default_wms_url = config.get(
            'default_qgis_server_url', 'http://localhost:8001/ows/')
        self.data_service_url = config.get(
            'data_service_url', '/api/v1/data/').rstrip('/') + '/'

        self.resources = self.load_resources(config)
        self.permissions_handler = PermissionsReader(tenant, logger)

        self.db_engine = DatabaseEngine()

    def query(self, identity, service_name, layers, params):
        """Query layers and return info result as XML.

        :param str identity: User identity
        :param str service_name: Service name
        :param list(str): List of query layer names
        :param obj params: FeatureInfo service params
        """
        if not self.wms_permitted(service_name, identity):
            # map unknown or not permitted
            return self.service_exception(
                'MapNotDefined',
                'Map "%s" does not exist or is not permitted' % service_name
            )

        # calculate query coordinates and resolutions
        try:
            bbox = list(map(float, params["bbox"].split(",")))
            x = 0.5 * (bbox[0] + bbox[2])
            y = 0.5 * (bbox[1] + bbox[3])
            xres = (bbox[2] - bbox[0]) / params['width']
            yres = (bbox[3] - bbox[1]) / params['height']
        except Exception:
            x = 0
            y = 0
            xres = 0
            yres = 0

        params['resolution'] = max(xres, yres)
        crs = params['crs']

        # filter layers by permissions and replace group layers
        # with permitted sublayers
        permitted_layers = self.permitted_layers(service_name, identity)
        group_layers = \
            self.resources['wms_services'][service_name]['group_layers']
        expanded_layers = self.expand_group_layers(
            layers, group_layers, permitted_layers
        )
        self.prefetch_wms_layers(service_name, expanded_layers, params, identity)

        # collect layer infos
        layer_infos = []
        for layer in expanded_layers:
            info = self.get_layer_info(
                identity, service_name, layer, x, y, crs, params
            )
            if info is not None:
                layer_infos.append(info)

        del self._wms_cache

        info_xml = (
            "<GetFeatureInfoResponse>%s</GetFeatureInfoResponse>" %
            ''.join(layer_infos)
        )
        return info_xml

    def service_exception(self, code, message):
        """Create ServiceExceptionReport XML

        :param str code: ServiceException code
        :param str message: ServiceException text
        """
        return (
            '<ServiceExceptionReport version="1.3.0">\n'
            ' <ServiceException code="%s">%s</ServiceException>\n'
            '</ServiceExceptionReport>'
            % (code, message)
        )

    def expand_group_layers(self, requested_layers, group_layers,
                            permitted_layers):
        """Recursively filter layers by permissions and replace group layers
        with permitted sublayers and return resulting layer list.

        :param list(str) requested_layers: List of requested layer names
        :param obj group_layers: Lookup for group layers with sublayers
        :param list(str) permitted_layers: List of permitted layer names
        """
        expanded_layers = []

        for layer in requested_layers:
            if layer in permitted_layers:
                if layer in group_layers:
                    # expand sublayers
                    sublayers = []
                    for sublayer in group_layers.get(layer):
                        if sublayer in permitted_layers:
                            sublayers.append(sublayer)

                    expanded_layers += self.expand_group_layers(
                        sublayers, group_layers, permitted_layers
                    )
                else:
                    # leaf layer
                    expanded_layers.append(layer)

        return expanded_layers

    def prefetch_wms_layers(self, service_name, expanded_layers, params, identity):
        wms_layers = {}
        for layer in expanded_layers:
            config = self.resources['wms_services'][service_name]['layers'][layer]
            info_template = config.get('info_template') or {}
            # TODO: maybe permissions
            if info_template.get('type', 'wms') == 'wms':
                wms_url = info_template.get('wms_url')
                wms_layers.setdefault(wms_url, []).append(layer)

        responses = {}
        default_wms_url = urljoin(self.default_wms_url, service_name)
        for url, layers_list in wms_layers.items():
            responses.update(
                fetch_wms_layer_infos(
                    layers=','.join(layers_list),
                    params=params,
                    identity=identity,
                    wms_url=url or default_wms_url,
                    forward_auth_headers=not url,
                    logger=self.logger
                )
            )

        self._wms_cache = responses
        self.logger.debug(self._wms_cache)

    def get_wms_layer_info(
        self, layer, params, identity, permitted_attributes, attribute_aliases,
        attribute_formats, service_name, info_template
    ):
        return parse_wms_layer_info(
            self._wms_cache.get(layer), permitted_attributes,
            attribute_aliases, attribute_formats, self.logger
        )

    def get_layer_info(self, identity, service_name, layer, x, y, crs, params):
        """Get info for a layer rendered as info template.

        :param str identity: User identity
        :param str service_name: Service name
        :param str layer: Layer name
        :param float x: X coordinate of query
        :param float y: Y coordinate of query
        :param str crs: CRS of query coordinates
        :param obj params: FeatureInfo service params
        """
        # get layer config
        config = self.resources['wms_services'][service_name]['layers'][layer]
        layer_title = config.get('title')
        info_template = config.get('info_template')
        attributes = config.get('attributes', [])
        attribute_aliases = config.get('attribute_aliases', {})
        attribute_formats = config.get('attribute_formats', {})
        json_attribute_aliases = config.get('json_attribute_aliases', {})
        display_field = config.get('display_field')
        feature_report = config.get('feature_report')
        parent_facade = config.get('parent_facade')

        # get layer permissions
        layer_permissions = self.layer_permissions(
            service_name, layer, identity
        )

        # filter by permissions
        if not layer_permissions['info_template']:
            info_template = None
        permitted_attributes = [
            attr for attr in attributes
            if attr in layer_permissions['attributes']
        ]

        if info_template and not info_template.get('template'):
            # use any Base64 encoded info template
            if info_template.get('template_base64'):
                info_template['template'] = self.b64decode(
                    info_template.get('template_base64'), None,
                    "info template of layer '%s'" % layer
                )

        if info_template is None:
            self.logger.info("No info template for layer '%s'" % layer)
            # fallback to WMS GetFeatureInfo with default info template
            info_template = {
                'template': self.default_info_template,
                'type': 'wms'
            }
        elif not info_template.get('template'):
            self.logger.info(
                "Empty template in info template for layer '%s'" % layer
            )
            # use default info template if not specified in config
            info_template['template'] = self.default_info_template

        info = None
        error_msg = None

        info_type = info_template.get('type')
        if info_type == 'wms':
            # WMS GetFeatureInfo
            info = self.get_wms_layer_info(
                layer, params, identity, permitted_attributes, attribute_aliases,
                attribute_formats, service_name, info_template,
            )
        elif info_type == 'sql':
            # DB query
            database = info_template.get('db_url')
            sql = info_template.get('sql')
            if not sql:
                # use any Base64 encoded info SQL
                sql = self.b64decode(
                    info_template.get('sql_base64'), "",
                    "info SQL of layer '%s'" % layer
                )
            info = sql_layer_info(
                layer, x, y, crs, params, identity, self.db_engine, database,
                sql, self.logger
            )
        elif info_type == 'module':
            # custom module
            try:
                # import custom layer info method
                module_name = info_template.get('module')
                custom_module = import_module(
                    'info_modules.custom.%s' % module_name
                )
                layer_info = getattr(custom_module, 'layer_info')

                # call layer info
                info = layer_info(layer, x, y, crs, params, identity)
            except ImportError as e:
                error_msg = "ImportError for layer '%s': %s" % (layer, e)
            except AttributeError as e:
                error_msg = "AttributeError for layer '%s': %s" % (layer, e)
            except Exception as e:
                error_msg = (
                    "Exception in custom info module '%s' "
                    "for layer '%s':\n%s" %
                    (module_name, layer, traceback.format_exc())
                )
            if error_msg is not None:
                self.logger.error(error_msg)
                info = {'error': error_msg}

        if info is None or not isinstance(info, dict):
            # info result failed or not a dict
            return None

        if info.get('error'):
            # render layer template with error message
            error_html = (
                '<span class="info_error" style="color: red">%s</span>' %
                info.get('error')
            )
            features = [{
                'html_content': self.html_content(error_html)
            }]
            return layer_template.render(
                layer_name=layer, layer_title=layer_title,
                features=features, parent_facade=parent_facade
            )

        if not info.get('features'):
            # info result is empty
            return layer_template.render(
                layer_name=layer, layer_title=layer_title,
                parent_facade=parent_facade
            )

        template = info_template.get('template')

        features = []
        for feature in info.get('features'):
            # create info feature with attributes
            info_feature = InfoFeature()
            for attr in feature.get('attributes', []):
                name = attr.get('name')
                json_aliases = json_attribute_aliases.get(name)
                value = self.parse_value(attr.get('value'), json_aliases)
                if isinstance(value, str) and value.startswith("attachment://"):
                    value = "attachment://" + self.data_service_url + "/" + service_name + "." + layer + "/attachment?file=" + value[13:]
                alias = attribute_aliases.get(name, name)
                info_feature.add(name, value, alias, json_aliases)

            fid = feature.get('id')
            bbox = feature.get('bbox')
            geometry = feature.get('geometry')

            info_html = None
            try:
                # render feature template
                feature_template = Template(template)
                info_html = feature_template.render(
                    feature=info_feature, fid=fid, bbox=bbox,
                    geometry=geometry, layer=layer, x=x, y=y, crs=crs,
                    render_value=self.render_value
                )
            except TemplateSyntaxError as e:
                error_msg = (
                    "TemplateSyntaxError on line %d: %s" % (e.lineno, e)
                )
            except TemplateError as e:
                error_msg = "TemplateError: %s" % e
            if error_msg is not None:
                self.logger.error(error_msg)
                info_html = (
                    '<span class="info_error" style="color: red">%s</span>' %
                    error_msg
                )

            features.append({
                'fid': fid,
                'html_content': self.html_content(info_html),
                'bbox': bbox,
                'wkt_geom': geometry,
                'attributes': info_feature._attributes
            })

        # render layer template
        return layer_template.render(
            layer_name=layer, layer_title=layer_title, crs=crs,
            features=features,
            display_field=display_field,
            feature_report=feature_report,
            parent_facade=parent_facade
        )

    def parse_value(self, value, json_aliases):
        """Parse info result value and convert to dict or list if JSON.

        :param obj value: Info value
        :param OrderedDict json_aliases: JSON attributes config
        """
        if isinstance(value, str):
            try:
                if value.startswith('{') or value.startswith('['):
                    # parse JSON with original order of keys
                    json_value = json.loads(
                        value, object_pairs_hook=OrderedDict
                    )

                    if json_aliases and isinstance(json_value, list):
                        # JSON aliases present and JSON value is a list
                        value = []
                        for json_item in json_value:
                            # reorder item keys according to JSON aliases
                            item = OrderedDict()
                            for key in json_aliases:
                                if key in json_item:
                                    item[key] = json_item[key]

                            # add any additional keys not in JSON aliases
                            for key in json_item:
                                if key not in json_aliases:
                                    item[key] = json_item[key]

                            value.append(item)
                    else:
                        # JSON value is a dict or no JSON aliases present
                        value = json_value

            except Exception as e:
                self.logger.error(
                    "Could not parse value as JSON: '%s'\n%s" % (value, e)
                )

        return value

    def render_value(self, value, htmlEscape=True):
        """Escape HTML special characters if requested, and detect
        special value formats in info result values and reformat them.

        :param obj value: Info value
        :param bool htmlEscape: Whether to HTML escape the value
        """
        if isinstance(value, str):
            # If value is already html (i.e. begins with a valid HTML tag), return it as is
            if value.startswith("<") and value.find(">") != -1 and re.match("<(\"[^\"]*\"|'[^']*'|[^'\">])*>", value[0:value.find(">") + 1]):
                return value

            if htmlEscape:
                value = html.escape(value)
            rules = [(
                # HTML links
                r'^(https?:\/\/.*)$',
                lambda m: m.expand(r'<a href="\1" target="_blank">Link</a>')
            ),(
                # Attachments
                r'^attachment://(.+)/([^/]+)$',
                lambda m: m.expand(r'<a href="\1/\2" target="_blank"><img src="\1/\2" alt="\2" style="width: 100%" /></a>')
            )]
            for rule in rules:
                match = re.match(rule[0], value)
                if match:
                    value = rule[1](match)
                    break

        return value

    def html_content(self, info_html):
        """Return <HtmlContent> tag with escaped HTML.

        :param str info_html: Info HTML
        """
        doc = Document()
        el = doc.createElement('HtmlContent')
        el.setAttribute('inline', '1')
        text = Text()
        text.data = info_html
        el.appendChild(text)
        return el.toxml()

    def load_resources(self, config):
        """Load service resources from config.

        :param RuntimeConfig config: Config handler
        """
        wms_services = {}

        # collect service resources
        for wms in config.resources().get('wms_services', []):
            # collect map layers
            layers = {}
            group_layers = {}
            self.collect_layers(wms['root_layer'], layers, group_layers)

            wms_services[wms['name']] = {
                'layers': layers,
                'group_layers': group_layers
            }

        return {
            'wms_services': wms_services
        }

    def collect_layers(self, layer, layers, group_layers, parent_group=None):
        """Recursively collect layer info for layer subtree from config.

        :param obj layer: Layer or group layer
        :param obj layers: Partial lookup for layer configs
        :param obj group_layers: Partial lookup for group layer configs
        :param str parent_group: Name of visible parent group if sublayers are
                                 hidden
        """
        if layer.get('layers'):
            # group layer

            if layer.get('hide_sublayers', False) and parent_group is None:
                parent_group = layer['name']

            # collect sub layers
            sublayers = []
            for sublayer in layer['layers']:
                sublayers.append(sublayer['name'])
                # recursively collect sub layer
                self.collect_layers(
                    sublayer, layers, group_layers, parent_group
                )

            group_layers[layer['name']] = sublayers
        else:
            # layer

            # collect attributes config
            attributes = []
            attribute_aliases = {}
            attribute_formats = {}
            json_aliases = {}
            for attr in layer.get('attributes', []):
                attributes.append(attr['name'])
                if attr.get('alias'):
                    attribute_aliases[attr['name']] = attr['alias']
                if attr.get('format'):
                    attribute_formats[attr['name']] = attr['format']
                elif attr.get('format_base64'):
                    attr_format = self.b64decode(
                        attr.get('format_base64'), None,
                        "format of attribute '%s' in layer '%s'"
                        % (attr['name'], layer['name'])
                    )
                    if attr_format:
                        attribute_formats[attr['name']] = attr_format

                if attr.get('json_attribute_aliases'):
                    # NOTE: keep order of JSON aliases from config
                    json_attribute_aliases = OrderedDict()
                    for entry in attr['json_attribute_aliases']:
                        json_attribute_aliases[entry['name']] = entry['alias']
                    json_aliases[attr['name']] = json_attribute_aliases

            # add layer config
            config = {
                'title': layer.get('title', layer['name']),
                'attributes': attributes
            }
            if layer.get('info_template'):
                config['info_template'] = layer.get('info_template')
            if attribute_aliases:
                config['attribute_aliases'] = attribute_aliases
            if attribute_formats:
                config['attribute_formats'] = attribute_formats
            if json_aliases:
                config['json_attribute_aliases'] = json_aliases
            if layer.get('display_field'):
                config['display_field'] = layer.get('display_field')
            if layer.get('feature_report'):
                config['feature_report'] = layer.get('feature_report')
            if parent_group:
                config['parent_facade'] = parent_group

            layers[layer['name']] = config

    def wms_permitted(self, service_name, identity):
        """Return whether WMS is available and permitted.

        :param str service_name: Service name
        :param obj identity: User identity
        """
        if self.resources['wms_services'].get(service_name):
            # get permissions for WMS
            wms_permissions = self.permissions_handler.resource_permissions(
                'wms_services', identity, service_name
            )
            if wms_permissions:
                return True

        return False

    def permitted_layers(self, service_name, identity):
        """Return permitted layers for a map.

        :param str service_name: Service name
        :param obj identity: User identity
        """
        wms_resources = self.resources['wms_services'][service_name].copy()

        # get available layers
        available_layers = set(
            list(wms_resources['layers'].keys()) +
            list(wms_resources['group_layers'].keys())
        )

        # get permissions for WMS
        wms_permissions = self.permissions_handler.resource_permissions(
            'wms_services', identity, service_name
        )

        # combine permissions
        permitted_layers = set()
        for permission in wms_permissions:
            # collect available and permitted layers
            layers = [
                layer['name'] for layer in permission['layers']
                if layer['name'] in available_layers
            ]
            permitted_layers.update(layers)

        # return sorted layers
        return sorted(list(permitted_layers))

    def layer_permissions(self, service_name, layer, identity):
        """Return permitted layer attributes and info template.

        :param str service_name: Service name
        :param str layer: Layer name
        :param obj identity: User identity
        """
        # get permissions for WMS
        wms_permissions = self.permissions_handler.resource_permissions(
            'wms_services', identity, service_name
        )

        # combine permissions
        permitted_attributes = set()
        info_template_permitted = False
        for permission in wms_permissions:
            # find requested layer
            for l in permission['layers']:
                if l['name'] == layer:
                    # found matching layer
                    permitted_attributes.update(l.get('attributes', []))
                    info_template_permitted |= l.get('info_template', False)
                    break

        return {
            'attributes': sorted(list(permitted_attributes)),
            'info_template': info_template_permitted
        }

    def b64decode(self, base64_value, default, description=""):
        """Return decoded Base64 encoded value or default on error.

        :param str base64_value: Base64 encoded value
        :param str default: Default value returned on decoding error
        :param str description: Description included in error message
        """
        value = default
        try:
            value = base64.b64decode(base64_value).decode('utf-8')
        except Exception as e:
            self.logger.error(
                "Could not decode Base64 encoded value for %s:"
                "\n%s\n%s" % (description, e, base64_value)
            )
            value = default
        return value
