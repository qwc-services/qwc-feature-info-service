# Sample implementation of a custom layer info module


def layer_info(layer, x, y, crs, params, identity):
    """Query layer and return info result as dict:

        {
            'features': [
                {
                    'id': <feature ID>,  # optional
                    'attributes': [
                        {
                            'name': '<attribute name>',
                            'value': '<attribute value>'
                        }
                    ],
                    'bbox': [<minx>, <miny>, <maxx>, <maxy>],  # optional
                    'geometry': '<WKT geometry>'  # optional
                }
            ]
        }

    :param str layer: Layer name
    :param float x: X coordinate of query
    :param float y: Y coordinate of query
    :param str crs: CRS of query coordinates
    :param obj params: FeatureInfo service params
        {
            'i': <X ordinate of query point on map, in pixels>,
            'j': <Y ordinate of query point on map, in pixels>,
            'height': <Height of map output, in pixels>,
            'width': <Width of map output, in pixels>,
            'bbox': '<Bounding box for map extent as minx,miny,maxx,maxy>',
            'crs': '<CRS for map extent>',
            'feature_count': <Max feature count>,
            'with_geometry': <Whether to return geometries in response
                (default=1)>,
            'with_maptip': <Whether to return maptip in response
                (default=1)>,
            'FI_POINT_TOLERANCE': <Tolerance for picking points, in pixels
                (default=16)>,
            'FI_LINE_TOLERANCE': <Tolerance for picking lines, in pixels
                (default=8)>,
            'FI_POLYGON_TOLERANCE': <Tolerance for picking polygons, in pixels
                (default=4)>,
            'resolution': <Resolution in map units per pixel>
        }
    :param str identity: User name or Identity dict
    """
    features = []

    feature_id = 123
    attributes = [
        {
            'name': 'title',
            'value': 'Feature for Layer %s' % layer
        },
        {
            'name': 'name',
            'value': 'Feature Name'
        }
    ]
    px = round(x)
    py = round(y)
    bbox = [px - 50, py - 50, px + 50, py + 50]
    geometry = "POINT(%s %s)" % (px, py)

    features.append({
        'id': feature_id,
        'attributes': attributes,
        'bbox': bbox,
        'geometry': geometry

    })

    return {
        'features': features
    }
