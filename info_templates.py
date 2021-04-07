from jinja2 import Template


# template for GetFeatureInfoResponse <Layer> tag
layer_template = Template("""
    <Layer name="{{ layer_title|e }}" layername="{{ layer_name|e }}"
        {{ 'layerinfo="%s"' | format(parent_facade if parent_facade else layer_name) }}
        {{ 'featurereport="%s"' | format(feature_report) if feature_report }}
        {{ 'displayfield="%s"' | format(display_field) if display_field }}>
        {%- for feature in features %}
        <Feature id="{{ feature['fid'] if feature['fid'] }}">
            {{ feature['html_content'] }}
            {% if feature['bbox'] %}
            <BoundingBox CRS="{{ crs }}"
                minx="{{ feature['bbox'][0] }}" miny="{{ feature['bbox'][1] }}"
                maxx="{{ feature['bbox'][2] }}" maxy="{{ feature['bbox'][3] }}"
            />
            {%- endif %}
            {% if feature['wkt_geom'] %}
            <Attribute name="geometry" value="{{ feature['wkt_geom'] }}"
                type="derived" />
            {%- endif %}
            {% for attr in feature.attributes %}
            <Attribute name="{{ attr['alias']|e }}" value="{{ attr['value']|e }}" attrname="{{ attr['name'] }}" />
            {%- endfor %}
        </Feature>
        {% endfor -%}
    </Layer>
""")

# default info template for feature info HTML
default_info_template = """
    <table class="attribute-list">
        <tbody>
        {% for attr in feature._attributes -%}
            {% if attr['type'] == 'list' -%}
                {# attribute is a list #}
                <tr>
                    <td class="identify-attr-title wrap"><i>{{ attr['alias']|e }}</i></td>
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
                                                        <i>{{ alias|e }}</i>
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
                    <td class="identify-attr-title wrap"><i>{{ attr['alias']|e }}</i></td>
                    <td>
                        <table class="identify-attr-subtable">
                            <tbody>
                            {% for key in attr['value'] -%}
                                <tr>
                                    <td class="identify-attr-title wrap">
                                        <i>{{ key|e }}</i>
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
                        <i>{{ attr['alias']|e }}</i>
                    </td>
                    <td class="identify-attr-value wrap">
                        {{ render_value(attr['value']) }}
                    </td>
                </tr>
            {%- endif %}
        {%- endfor %}
        </tbody>
    </table>
"""
