from collections import OrderedDict
import re
import os
import time
import traceback
from datetime import datetime, date
from urllib.parse import urlencode

from flask import json
from flask_jwt_extended import create_access_token
import requests
from xml.dom.minidom import parseString


THROTTLE_LAYERS = os.environ.get('THROTTLE_LAYERS', '').split(',')
USE_PERMISSION_ATTRIBUTE_ORDER = os.environ.get('USE_PERMISSION_ATTRIBUTE_ORDER', '0') not in [0, "0", "False", "FALSE"]
SKIP_EMPTY_ATTRIBUTES = os.environ.get('SKIP_EMPTY_ATTRIBUTES', '0') not in [0, "0", "False", "FALSE"]
THROTTLE_TIME = 1.5


def layer_info(layer, x, y, crs, params, identity, wms_url,
               permitted_attributes, attribute_aliases, attribute_formats,
               forward_auth_headers, logger):
    """Forward query to WMS server and return parsed info result.

    :param str layer: Layer name
    :param float x: X coordinate of query
    :param float y: Y coordinate of query
    :param str crs: CRS of query coordinates
    :param obj params: FeatureInfo service params
    :param str identity: User name or Identity dict
    :param str wms_url: WMS URL
    :param list(str) permitted_attributes: Ordered list of permitted attributes
    :param obj attribute_aliases: Lookup for attribute aliases
    :param obj attribute_formats: Lookup for attribute formats
    :param bool forward_auth_headers: Whether to forward authorization headers
    :param Logger logger: Application logger
    """
    features = []

    try:
        # reverse lookup for attribute names from alias
        alias_attributes = {}
        for name, alias in attribute_aliases.items():
            alias_attributes[alias] = name

        headers = {}
        if forward_auth_headers:
            # forward any authorization headers
            access_token = create_access_token(identity)
            if access_token:
                headers['Authorization'] = "Bearer " + access_token

        # forward WMS GetFeatureInfo request
        wms_params = params.copy()
        wms_params.pop('resolution', None)
        wms_params.update({
            'service': 'WMS',
            'version': '1.3.0',
            'request': 'GetFeatureInfo',
            'info_format': 'text/xml',
            'layers': layer,
            'query_layers': layer
        })

        if layer in THROTTLE_LAYERS:
            logger.info("Defer layer %s for %fs" % (layer, THROTTLE_TIME))
            time.sleep(THROTTLE_TIME)

        logger.info(
            "Forward WMS GetFeatureInfo request to %s?%s" %
            (wms_url, urlencode(wms_params))
        )

        response = requests.get(
            wms_url, params=wms_params, headers=headers, timeout=10
        )

        # parse GetFeatureInfo response
        document = parseString(response.content.decode())
        for layerEl in document.getElementsByTagName('Layer'):
            featureEls = layerEl.getElementsByTagName("Feature")
            if len(featureEls) > 0:
                # vector layer
                for featureEl in layerEl.getElementsByTagName('Feature'):
                    feature_id = featureEl.getAttribute('id')
                    attributes = []
                    bbox = None
                    geometry = None

                    # parse attributes
                    info_attributes = OrderedDict()
                    for attrEl in featureEl.getElementsByTagName('Attribute'):
                        # name from GetFeatureInfo may be alias or name
                        info_name = attrEl.getAttribute('name')
                        # lookup attribute name for alias
                        name = alias_attributes.get(info_name, info_name)
                        if name in permitted_attributes:
                            # add permitted attribute
                            value = attrEl.getAttribute('value')
                            if value in ["", "NULL", "null"] and SKIP_EMPTY_ATTRIBUTES:
                                continue
                            elif (name == 'geometry' and
                                    attrEl.getAttribute('type') == 'derived'):
                                geometry = value
                            else:
                                info_attributes[name] = value

                    if USE_PERMISSION_ATTRIBUTE_ORDER:
                        # add info attributes in order of permitted_attributes
                        for name in permitted_attributes:
                            if name in info_attributes:
                                format = attribute_formats.get(name)
                                value = info_attributes.get(name)

                                attributes.append({
                                    'name': name,
                                    'value': formatted_value(value, format, logger)
                                })
                    else:
                        # add info attributes if permitted, preserving featureinfo response order
                        for name in info_attributes:
                            if name in permitted_attributes:
                                format = attribute_formats.get(name)
                                value = info_attributes.get(name)

                                attributes.append({
                                    'name': name,
                                    'value': formatted_value(value, format, logger)
                                })

                    # parse bbox
                    for bboxEl in featureEl.getElementsByTagName('BoundingBox'):
                        bbox = [
                            bboxEl.getAttribute('minx'),
                            bboxEl.getAttribute('miny'),
                            bboxEl.getAttribute('maxx'),
                            bboxEl.getAttribute('maxy')
                        ]
                    if attributes:
                        features.append({
                            'id': feature_id,
                            'attributes': attributes,
                            'bbox': bbox,
                            'geometry': geometry
                        })
            elif len(layerEl.getElementsByTagName('Attribute')) > 0:
                # raster layer (no features)
                attributes = []

                # parse attributes
                for attrEl in layerEl.getElementsByTagName('Attribute'):
                    name = attrEl.getAttribute('name')
                    format = attribute_formats.get(name)
                    value = attrEl.getAttribute('value')

                    attributes.append({
                        'name': name,
                        'value': formatted_value(value, format, logger)
                    })

                features.append({
                    'attributes': attributes
                })

    except Exception as e:
        msg = "Exception for layer '%s':\n%s" % (layer, traceback.format_exc())
        logger.error(msg)
        return {
            'error': msg
        }

    return {
        'features': features
    }


CONVERSION_RULES = [
    (re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{1,6}$'),  # YYYY-MM-DDTHH:mm:ss.micros
     lambda m: datetime.strptime(m.group(0), '%Y-%m-%dT%H:%M:%S.%f')),
    (re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$'),  # YYYY-MM-DDTHH:mm:ss
     lambda m: datetime.strptime(m.group(0), '%Y-%m-%dT%H:%M:%S')),
    (re.compile(r'^\d{4}-\d{2}-\d{2}$'),  # YYYY-MM-DD
     lambda m: datetime.strptime(m.group(0), '%Y-%m-%d').date()),
    (re.compile(r'^NULL$'), lambda m: None),  # NULL
    # (r'^\d+$', lambda m: int(m.group(0))),  # Integer
    # (r'^\d+\.\d+$', lambda m: float(m.group(0))),  # Float
]


def formatted_value(value, formatstr, logger):
    # Detect types and convert value
    for rule in CONVERSION_RULES:
        match = rule[0].match(value)
        if match:
            value = rule[1](match)
            break

    # Convert value according to type spec in format
    # https://docs.python.org/3.4/library/string.html#format-specification-mini-language
    if formatstr and isinstance(value, str):
        try:
            typechar = formatstr[-1]
            if typechar in 'bcdoxXn':
                value = int(value)
            elif typechar in 'eEfFgGn%':
                value = float(value)
        except Exception as e:
            logger.warn("Error converting attribute with format '{}': {}"
                        .format(formatstr, e))

    # Add default formats for some types
    if not formatstr:
        if isinstance(value, datetime):
            formatstr = "%d.%m.%Y %H:%M:%S"
        elif isinstance(value, date):
            formatstr = "%d.%m.%Y"

    # Apply NULL value default format
    if value is None:
        value = '-'

    # Return unformatted
    if not formatstr:
        return value

    if formatstr.startswith('{'):
        # JSON dict as lookup table
        lookup = json.loads(formatstr)
        out = lookup.get(value) or value
    else:
        try:
            out = format(value, formatstr)
        except Exception as e:
            logger.warn("Error converting attribute with format '{}': {}"
                        .format(formatstr, e))
            out = value

    return out
