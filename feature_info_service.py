import html
import re
from xml.dom.minidom import Document, Element, Text

from jinja2 import Template, TemplateError, TemplateSyntaxError

from info_modules.wms import layer_info as wms_layer_info
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
        setattr(self, name, value)
        # add to ordered attribute list
        self._attributes.append({
            'name': name,
            'value': value,
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

    def query(self, identity, mapid, layers, params):
        """Query layers and return info result as XML.

        :param str identity: User identity
        :param str mapid: Map ID
        :param list(str): List of query layer names
        :param obj params: FeatureInfo service params
        """

        # calculate query coordinates and resolutions
        try:
            bbox = list(map(float, params["bbox"].split(",")))
            x = 0.5 * (bbox[0] + bbox[2])
            y = 0.5 * (bbox[1] + bbox[3])
            xres = (bbox[2] - bbox[0]) / params['width']
            yres = (bbox[3] - bbox[1]) / params['height']
        except Exception as e:
            x = 0
            y = 0
            xres = 0
            yres = 0

        params['resolution'] = max(xres, yres)
        crs = params['crs']

        # TODO: filter layers by permissions

        # collect layer infos
        layer_infos = []
        for layer in layers:
            info = self.get_layer_info(
                identity, mapid, layer, x, y, crs, params
            )
            if info is not None:
                layer_infos.append(info)

        info_xml = (
            "<GetFeatureInfoResponse>%s</GetFeatureInfoResponse>" %
            ''.join(layer_infos)
        )
        return info_xml

    def get_layer_info(self, identity, mapid, layer, x, y, crs, params):
        """Get info for a layer rendered as info template.

        :param str identity: User identity
        :param str mapid: Map ID
        :param str layer: Layer name
        :param float x: X coordinate of query
        :param float y: Y coordinate of query
        :param str crs: CRS of query coordinates
        :param obj params: FeatureInfo service params
        """

        # TODO: from config
        # TODO: filter by permissions
        layer_title = None
        info_template = None
        display_field = None
        feature_report = None
        parent_facade = None
        permitted_attributes = ['name', 'formal_en', 'pop_est', 'subregion']
        attribute_aliases = {}
        attribute_formats = {}
        json_attribute_aliases = {}

        if info_template is None:
            self.logger.warning("No info template for layer '%s'" % layer)
            # fallback to WMS GetFeatureInfo with default info template
            info_template = {
                'template': default_info_template,
                'type': 'wms'
            }

        info = None
        error_msg = None

        # TODO: other info types
        info_type = info_template.get('type')
        if info_type == 'wms':
            # WMS GetFeatureInfo
            info = wms_layer_info(
                layer, x, y, crs, params, identity, mapid,
                permitted_attributes, attribute_aliases, attribute_formats,
                self.logger
            )

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

        # lookup for attribute aliases from attribute names
        attribute_alias_lookup = {}
        for alias in attribute_aliases:
            attribute_alias_lookup[attribute_aliases.get(alias)] = alias

        features = []
        for feature in info.get('features'):
            # create info feature with attributes
            info_feature = InfoFeature()
            for attr in feature.get('attributes', []):
                name = attr.get('name')
                value = self.parse_value(attr.get('value'))
                alias = attribute_alias_lookup.get(name, name)
                json_aliases = json_attribute_aliases.get(name)
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

    def parse_value(self, value):
        """Parse info result value and convert to dict if JSON.

        :param obj value: Info value
        """
        if isinstance(value, str):
            try:
                if value.startswith('{') or value.startswith('['):
                    # parse JSON with original order of keys
                    value = json.loads(value, object_pairs_hook=OrderedDict)
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
            if htmlEscape:
                value = html.escape(value)
            rules = [(
                # HTML links
                r'^(https?:\/\/.*)$',
                lambda m: m.expand(r'<a href="\1" target="_blank">Link</a>')
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
