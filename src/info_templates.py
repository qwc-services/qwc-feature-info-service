from jinja2 import Template


# template for GetFeatureInfoResponse <Layer> tag
layer_template = Template("""
    <Layer name="{{ layer_title|e }}" layername="{{ layer_name|e }}"
        layerinfo="{{ (parent_facade if parent_facade else layer_name)|e }}"
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
