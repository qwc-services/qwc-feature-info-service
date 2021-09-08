[![](https://github.com/qwc-services/qwc-feature-info-service/workflows/build/badge.svg)](https://github.com/qwc-services/qwc-feature-info-service/actions)
[![docker](https://img.shields.io/docker/v/sourcepole/qwc-feature-info-service?label=Docker%20image&sort=semver)](https://hub.docker.com/r/sourcepole/qwc-feature-info-service)

QWC FeatureInfo Service
=======================

Query layers at a geographic position using an API based on WMS GetFeatureInfo.

The query is handled for each layer by its layer info provider configured in the config file.

Layer info providers:

* WMS GetFeatureInfo (default): forward info request to the QGIS Server
* DB Query: execute custom query SQL
* Custom info module: custom Python modules returning layer info

The info results are each rendered into customizable HTML templates and returned as a GetFeatureInfoResponse XML.


Setup
-----

The DB query uses a PostgreSQL connection service or connection to a PostGIS database.
This connection's user requires read access to the configured tables.

### qwc_demo example

Uses PostgreSQL connection service `qwc_geodb` (GeoDB).
The user `qwc_service` requires read access to the configured tables
of the data layers from the QGIS project `qwc_demo.qgs`.

Setup PostgreSQL connection service file `~/.pg_service.conf`:

```
[qwc_geodb]
host=localhost
port=5439
dbname=qwc_demo
user=qwc_service
password=qwc_service
sslmode=disable
```


Configuration
-------------

The static config and permission files are stored as JSON files in `$CONFIG_PATH` with subdirectories for each tenant,
e.g. `$CONFIG_PATH/default/*.json`. The default tenant name is `default`.

Environment variables:

- `SKIP_EMPTY_ATTRIBUTES=<boolean>`: Whether to skip empty featureinfo attributes returned by WMS GetFeatureInfo.
- `USE_PERMISSION_ATTRIBUTE_ORDER=<boolean>`: Whether to order the attributes according to order of the permitted attribute names, rather than the order returned by WMS GetFeatureInfo.

### FeatureInfo Service config

* [JSON schema](schemas/qwc-feature-info-service.json)
* File location: `$CONFIG_PATH/<tenant>/featureInfoConfig.json`

Example:
```json
{
  "$schema": "https://raw.githubusercontent.com/qwc-services/qwc-feature-info-service/master/schemas/qwc-feature-info-service.json",
  "service": "feature-info",
  "config": {
    "default_qgis_server_url": "http://localhost:8001/ows/"
  },
  "resources": {
    "wms_services": [
      {
        "name": "qwc_demo",
        "root_layer": {
          "name": "qwc_demo",
          "layers": [
            {
              "name": "edit_demo",
              "title": "Edit Demo",
              "layers": [
                {
                  "name": "edit_points",
                  "title": "Edit Points",
                  "attributes": [
                    {
                      "name": "id"
                    },
                    {
                      "name": "name"
                    },
                    {
                      "name": "description"
                    },
                    {
                      "name": "num"
                    },
                    {
                      "name": "value"
                    },
                    {
                      "name": "type"
                    },
                    {
                      "name": "amount"
                    },
                    {
                      "name": "validated",
                      "format": "{\"t\": \"Yes\", \"f\": \"No\"}"
                    },
                    {
                      "name": "datetime"
                    },
                    {
                      "name": "geometry"
                    },
                    {
                      "name": "maptip"
                    }
                  ]
                }
              ]
            },
            {
              "name": "countries",
              "title": "Countries",
              "attributes": [
                {
                  "name": "name",
                  "alias": "Name"
                },
                {
                  "name": "formal_en",
                  "alias": "Formal name"
                },
                {
                  "name": "pop_est",
                  "alias": "Population"
                },
                {
                  "name": "subregion",
                  "alias": "Subregion"
                },
                {
                  "name": "geometry"
                }
              ],
              "display_field": "name",
              "info_template": {
                "type": "wms",
                "wms_url": "http://localhost:8001/ows/qwc_demo",
                "template": "<div><h2>Demo Template</h2>Pos: {{ x }}, {{ y }}<br>Name: {{ feature.Name }}</div>"
              }
            }
          ]
        }
      }
    ]
  }
}
```

Example `info_template` for WMS GetFeatureInfo:
```json
"info_template": {
  "type": "wms",
  "wms_url": "http://localhost:8001/ows/qwc_demo",
  "template": "<div><h2>Demo Template</h2>Pos: {{ x }}, {{ y }}<br>Name: {{ feature.Name }}</div>"
}
```

Example `info_template` for DB query:
```json
"info_template": {
  "type": "sql",
  "db_url": "postgresql:///?service=qwc_geodb",
  "sql": "SELECT ogc_fid as _fid_, name, formal_en, pop_est, subregion, ST_AsText(wkb_geometry) as wkt_geom FROM qwc_geodb.ne_10m_admin_0_countries WHERE ST_Intersects(wkb_geometry, ST_GeomFromText(:geom, :srid)) LIMIT :feature_count;",
  "template": "<div><h2>Demo Template</h2>Pos: {{ x }}, {{ y }}<br>Name: {{ feature.Name }}</div>"
}
```
Note: `x`, `y` and `geom` are passed as parameters to the SQL query. If a `GetFeatureInfo` request is being processed with a `filter_geom` parameter, `geom` will correspond to that parameter. Otherwise `geom` will be `POINT(x y)`.

Example `info_template` for Custom info module:
```json
"info_template": {
  "type": "module",
  "module": "example",
  "template": "<div><h2>Demo Template</h2>Pos: {{ x }}, {{ y }}<br>Name: {{ feature.Name }}</div>"
}
```


#### Base64 encoded properties

The following config properties may also be set as Base64 encoded values instead:

* Default HTML info template: `default_info_template_base64`
* Formatting expression for converting attribute values: `format_base64`
* HTML template for info result: `template_base64`
* Query SQL for DB query: `sql_base64`

Any plain text properties take precedence over their corresponding Base64 encoded property (e.g. `template_base64` is only used if `template` is not set).


### Permissions

* [JSON schema](https://github.com/qwc-services/qwc-services-core/blob/master/schemas/qwc-services-permissions.json)
* File location: `$CONFIG_PATH/<tenant>/permissions.json`

Example:
```json
{
  "$schema": "https://raw.githubusercontent.com/qwc-services/qwc-services-core/master/schemas/qwc-services-permissions.json",
  "users": [
    {
      "name": "demo",
      "groups": ["demo"],
      "roles": []
    }
  ],
  "groups": [
    {
      "name": "demo",
      "roles": ["demo"]
    }
  ],
  "roles": [
    {
      "role": "public",
      "permissions": {
        "wms_services": [
          {
            "name": "qwc_demo",
            "ows_type": "WMS",
            "layers": [
              {
                "name": "qwc_demo"
              },
              {
                "name": "edit_demo"
              },
              {
                "name": "edit_points",
                "attributes": [
                  "id", "name", "description", "num", "value", "type", "amount", "validated",
                  "datetime", "geometry", "maptip"
                ]
              },
              {
                "name": "countries",
                "attributes": ["name", "formal_en", "pop_est", "subregion", "geometry"],
                "info_template": true
              }
            ]
          }
        ]
      }
    }
  ]
}
```


## HTML template

A HTML template can be provided for a layer in the config file.
The template must only contain the body content (without `head`, `script`, `body`).
The HTML can be styled using inline CSS, otherwise the CSS from the QWC viewer is used.

This template can contain attribute value placeholders, in the form

    {{ feature.attr }}

which are replaced with the respective values when the template is rendered (using [Jinja2](http://jinja.pocoo.org/)).
The following values are available in the template:

* `x`, `y`, `crs`: Coordinates and CRS of info query
* `feature`: Feature with attributes from info result as properties, e.g. `feature.name`
* `fid`: Feature ID (if present)
* `bbox`: Feature bounding box as `[<minx>, <miny>, <maxx>, <maxy>]` (if present)
* `geometry`: Feature geometry as WKT (if present)
* `layer`: Layer name

To automatically detect hyperlinks in values and replace them as HTML links the following helper can be used in the template:

    render_value(value)

Example:

```xml
    <div>Result at coordinates {{ x }}, {{ y }}</div>
    <table>
        <tr>
            <td>Name:</td>
            <td>{{ feature.name }}</td>
        </tr>
        <tr>
            <td>Description:</td>
            <td>{{ feature.description }}</td>
        </tr>
    </table>
```


### Default info template

Layers with no assigned info templates use WMS GetFeatureInfo with a default info template.
The default template can also optionally be configured as `default_info_template` in the config file.

The InfoFeature `feature` available in the template also provides a list of its attributes:

    feature._attributes = [
        'name': <attribute name>,
        'value': <attribute value>,
        'alias': <attribute alias>,
        'type': <attribute value data type as string>,
        'json_aliases': <JSON attribute aliases as {'json_key': 'value'}>
    ]

If an attribute value starts with `{` or `[` the service tries to parse it as JSON before rendering it in the template.

Default info template:

```xml
    <table class="attribute-list">
        <tbody>
        {% for attr in feature._attributes -%}
            {% if attr['type'] == 'list' -%}
                {# attribute is a list #}
                <tr>
                    <td class="identify-attr-title wrap"><i>{{ attr['alias'] }}</i></td>
                    <td>
                        <table class="identify-attr-subtable">
                            <tbody>
                            {%- for item in attr['value'] %}
                                    {%- if item is mapping -%}
                                        {# item is a dict #}
                                        {% for key in item -%}
                                            {% if not attr['json_aliases'] %}
                                                {% set alias = key %}
                                            {% elif key in attr['json_aliases'] %}
                                                {% set alias = attr['json_aliases'][key] %}
                                            {% endif %}
                                            {% if alias %}
                                                <tr>
                                                    <td class="identify-attr-title wrap">
                                                        <i>{{ alias }}</i>
                                                    </td>
                                                    <td class="identify-attr-value wrap">
                                                        {{ render_value(item[key]) }}
                                                    </td>
                                                </tr>
                                            {% endif %}
                                        {%- endfor %}
                                    {%- else -%}
                                        <tr>
                                            <td class="identify-attr-value identify-attr-single-value wrap" colspan="2">
                                                {{ render_value(item) }}
                                            </td>
                                        </tr>
                                    {%- endif %}
                                    <tr>
                                        <td class="identify-attr-spacer" colspan="2"></td>
                                    </tr>
                            {%- endfor %}
                            </tbody>
                        </table>
                    </td>
                </tr>

            {%- elif attr['type'] in ['dict', 'OrderedDict'] -%}
                {# attribute is a dict #}
                <tr>
                    <td class="identify-attr-title wrap"><i>{{ attr['alias'] }}</i></td>
                    <td>
                        <table class="identify-attr-subtable">
                            <tbody>
                            {% for key in attr['value'] -%}
                                <tr>
                                    <td class="identify-attr-title wrap">
                                        <i>{{ key }}</i>
                                    </td>
                                    <td class="identify-attr-value wrap">
                                        {{ render_value(attr['value'][key]) }}
                                    </td>
                                </tr>
                            {%- endfor %}
                            </tbody>
                        </table>
                    </td>
                </tr>

            {%- else -%}
                {# other attributes #}
                <tr>
                    <td class="identify-attr-title wrap">
                        <i>{{ attr['alias'] }}</i>
                    </td>
                    <td class="identify-attr-value wrap">
                        {{ render_value(attr['value']) }}
                    </td>
                </tr>
            {%- endif %}
        {%- endfor %}
        </tbody>
    </table>
```


DB Query
--------

In a DB Query the following values are replaced in the SQL:

* `:x`: X coordinate of query
* `:y`: Y coordinate of query
* `:srid`: SRID of query coordinates
* `:resolution`: Resolution in map units per pixel
* `:FI_POINT_TOLERANCE`: Tolerance for picking points, in pixels (default=16)
* `:FI_LINE_TOLERANCE`: Tolerance for picking lines, in pixels (default=8)
* `:FI_POLYGON_TOLERANCE`: Tolerance for picking polygons, in pixels (default=4)
* `:i`: X ordinate of query point on map, in pixels
* `:j`: Y ordinate of query point on map, in pixels
* `:height`: Height of map output, in pixels
* `:width`: Width of map output, in pixels
* `:bbox`: 'Bounding box for map extent as minx,miny,maxx,maxy'
* `:crs`: 'CRS for map extent'
* `:feature_count`: Max feature count
* `:with_geometry`: Whether to return geometries in response (default=1)
* `:with_maptip`: Whether to return maptip in response (default=1)

The query may return the feature ID as `_fid_` and the WKT geometry as `wkt_geom`. All other selected columns are used as feature attributes.

Sample queries:

```sql
    SELECT ogc_fid as _fid_, name, ...,
      ST_AsText(wkb_geometry) as wkt_geom
    FROM schema.table
    WHERE ST_Intersects(wkb_geometry, ST_GeomFromText('POINT(:x :y)', :srid))
    LIMIT :feature_count;
```

```sql
    SELECT ogc_fid as _fid_, name, ...,
      ST_AsText(wkb_geometry) as wkt_geom
    FROM schema.table
    WHERE ST_Intersects(
        wkb_geometry,
        ST_Buffer(
            ST_GeomFromText('POINT(:x :y)', :srid),
            :resolution * :FI_POLYGON_TOLERANCE
        )
    )
    LIMIT :feature_count;
```


Custom info modules
-------------------

Custom info modules can be placed in `./info_modules/custom/<module name>/` and must provide the following method:
```python
def layer_info(layer, x, y, crs, params, identity)
```

Input parameters:

* `layer` (str): Layer name
* `x` (float): X coordinate of query
* `y` (float): Y coordinate of query
* `crs` (str): CRS of query coordinates
* `params` (obj): FeatureInfo service params

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

* `identity` (str): User name or Identity dict

Return info result as a dict:

    {
        'features': [
            {
                'id': <feature ID>,  # optional
                'attributes': [
                    {
                        'name': '<attribute name>',
                        'value': <attribute value>
                    }
                ],
                'bbox': [<minx>, <miny>, <maxx>, <maxy>],  # optional
                'geometry': '<WKT geometry>'  # optional
            }
        ]
    }

See [`./info_modules/custom/example/`](info_modules/custom/example/) for a sample implementation of a custom layer info module.

The custom info module can then be referenced in the `info_template` by its name (= directory name) in the service config.


Usage
-----

Set the `CONFIG_PATH` environment variable to the path containing the service config and permission files when starting this service (default: `config`).

Base URL:

    http://localhost:5015/

Service API:

    http://localhost:5015/api/

Sample request:

    curl 'http://localhost:5015/qwc_demo?layers=countries,edit_points&i=51&j=51&height=101&width=101&bbox=671639%2C5694018%2C1244689%2C6267068&crs=EPSG%3A3857'

Docker usage
------------

To run this docker image you will need a PostGIS database and a running QGIS Server.

The following steps explain how to download the those services and how to run the `qwc-feature-info-service` with `docker-compose`.

**Step 1: Clone qwc-docker**

    git clone https://github.com/qwc-services/qwc-docker
    cd qwc-docker

**Step 2: Create docker-compose.yml file**

    cp docker-compose-example.yml docker-compose.yml

**Step 3: Start docker containers**

    docker-compose up qwc-feature-info-service

For more information please visit: https://github.com/qwc-services/qwc-docker

Development
-----------

Create a virtual environment:

    virtualenv --python=/usr/bin/python3 --system-site-packages .venv

Without system packages:

    virtualenv --python=/usr/bin/python3 .venv

Activate virtual environment:

    source .venv/bin/activate

Install requirements:

    pip install -r requirements.txt

Start local service:

    CONFIG_PATH=/PATH/TO/CONFIGS/ python server.py
