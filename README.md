FeatureInfo Service
===================

Query layers at a geographic position using an API based on WMS GetFeatureInfo.

The query is handled for each layer by its layer info provider configured in the config file.

Layer info providers:

* WMS GetFeatureInfo: forward info request to the QGIS Server

The info results are each rendered into customizable HTML templates and returned as a GetFeatureInfoResponse XML.


Usage
-----

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

    python server.py
