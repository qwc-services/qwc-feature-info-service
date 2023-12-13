import traceback

from sqlalchemy.sql import text as sql_text


def layer_info(layer, x, y, crs, params, identity, db_engine, database, sql,
               logger):
    """Execute layer query SQL and return info result

    :param str layer: Layer name
    :param float x: X coordinate of query
    :param float y: Y coordinate of query
    :param str crs: CRS of query coordinates
    :param obj params: FeatureInfo service params
    :param str identity: User name or Identity dict
    :param DatabaseEngine db_engine: Database engine with DB connections
    :param str database: Database connection string
    :param str sql: Query SQL
    :param Logger logger: Application logger
    """
    features = []

    try:
        if database:
            # create DB engine
            db = db_engine.db_engine(database)
        else:
            # fallback to default GeoDB
            db = db_engine.geo_db()

        # connect to database and start transaction (for read-only access)
        conn = db.connect()
        trans = conn.begin()

        # execute info query
        sql_params = params.copy()
        try:
            srid = crs.split(':')[-1]
            srid = int(srid)
        except Exception as e:
            srid = 2056
        filter_geom = params.get('filter_geom', "")
        sql_params.update({
            'x': x,
            'y': y,
            'geom': filter_geom or 'POINT({x} {y})'.format(x=x, y=y),
            'srid': srid
        })
        result = conn.execute(sql_text(sql), **sql_params)
        for row in result:
            feature_id = 0
            attributes = []
            geometry = None

            for key in row.keys():
                if key == '_fid_':
                    feature_id = row[key]
                elif key == 'wkt_geom':
                    geometry = row[key]
                else:
                    attributes.append({
                        'name': key,
                        'value': row[key]
                    })

            features.append({
                'id': feature_id,
                'attributes': attributes,
                'geometry': geometry
            })

        # roll back transaction and close database connection
        trans.rollback()
        conn.close()

    except Exception as e:
        logger.error(
            "Exception for layer '%s':\n%s" % (layer, traceback.format_exc())
        )
        return {
            'error': e
        }

    return {
        'features': features
    }
