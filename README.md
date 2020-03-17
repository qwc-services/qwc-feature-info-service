FeatureInfo Service
===================

Query layers at a geographic position using an API based on WMS GetFeatureInfo.

The query is handled for each layer by its layer info provider configured in the config file.

Layer info providers:

* WMS GetFeatureInfo: forward info request to the QGIS Server

The info results are each rendered into customizable HTML templates and returned as a GetFeatureInfoResponse XML.


Configuration
-------------

The static config and permission files are stored as JSON files in `$CONFIG_PATH` with subdirectories for each tenant,
e.g. `$CONFIG_PATH/default/*.json`. The default tenant name is `default`.


### FeatureInfo Service config

* File location: `$CONFIG_PATH/<tenant>/featureInfoConfig.json`

Example:
```json
{
  "service": "feature-info",
  "config": {
  },
  "resources": {
    "maps": [
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
                  "name": "id"
                },
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


Usage
-----

Set the `CONFIG_PATH` environment variable to the path containing the service config and permission files when starting this service (default: `config`).

Base URL:

    http://localhost:5015/

Service API:

    http://localhost:5015/api/

Sample request:

    curl 'http://localhost:5015/qwc_demo?layers=countries,edit_lines&i=51&j=51&height=101&width=101&bbox=671639%2C5694018%2C1244689%2C6267068&crs=EPSG%3A3857'


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
