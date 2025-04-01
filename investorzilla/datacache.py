import logging
import sqlalchemy
import pandas


# TODO: Convert all queries to SQLAlchemy methods


class DataCache(object):
    """
    Implements a simple generic cache in a local SQLite database or any
    database specified by the SQLAlchemy URL provided in object initialization.

    Time series for market indices, currency converters and even your portfolio
    kept on Google Sheets take a lot of time to load because they are published
    as slow web APIs. To speed up initial data loading, all classes in the
    investzilla framework know how to work with a DataCache.

    A dataset that needs to be cached can have arbitrary columns and is usually
    the raw data as returned by the web API, after column names normalization
    but before cleanup and processing.

    A dataset has a `kind` and `ID`. So for example, the YahooMarketIndex class
    has kind `YahooMarketIndex` and the `ID` might be `^IXIC` or `^GSPC` -- the
    name of the market index you put in your portfolio configuration.

    DataCache will organize tables in the database with names
    `DataCache__{kind}`. And then each table will have columns:

    * __DataCache_id: values for our YahooMarketIndex examples will be `^IXIC`
      or `^GSPC`
    * __DataCache_time: UTC time the cache was set
    * other arbitrary columns found in the data attribute of set() method

    DataCache will keep multiple versions of the dataset, differentiated by
    __DataCache_time and it will always use the last version
    (max(__DataCache_time)). The maximum number of versions kept are defined by
    the __init__()’s recycle attribute. Older versions of data will be
    automatically deleted.
    """

    idCol       = '__DataCache_id'
    timeCol     = '__DataCache_time'
    typeTable   = 'DataCache__{kind}'



    def __init__(self, url='sqlite:///cache.db?check_same_thread=False', recycle=5):
        self.url=url
        self.db=None
        self.recycle=recycle

        # Setup logging
        self.getLogger()

        self.getDB()



    def __repr__(self):
        return 'DataCache(url={url},recycle={recycle})'.format(
            url=self.url,
            recycle=self.recycle
        )



    def __getstate__(self):
        o = self.__dict__
        o.update(
            dict(
                db = None,
                logger = None
            )
        )
        return o



    def getLogger(self):
        if hasattr(self,'logger')==False or self.logger is None:
            self.logger = logging.getLogger(__name__ + '.' + self.__class__.__name__)

        return self.logger



    def getDB(self):
        if hasattr(self,'db') and self.db is not None:
            return self.db

        engine_config_sets=dict(
            # Documentation for all these SQLAlchemy pool control parameters:
            # https://docs.sqlalchemy.org/en/14/core/engines.html#engine-creation-api

            DEFAULT=dict(
                # QueuePool config for a real database
                poolclass         = sqlalchemy.pool.QueuePool,

                # 5 is the default. Reinforce default, which is good
                pool_size         = 5,

                # Default here was 10, which might be low sometimes, so
                # increase to some big number in order to never let the
                # QueuePool be a bottleneck.
                max_overflow      = 50,

                # Debug connection and all queries
                # echo              = True
            ),
            sqlite=dict(
                # SQLite doesn’t support concurrent writes, so we‘ll amend
                # the DEFAULT configuration to make the pool work with only
                # 1 simultaneous connection. Since Investorzilla is agressively
                # parallel and requires a DB service that can be used in
                # parallel (regular DBs), the simplicity and portability
                # offered by SQLite for a light developer laptop has its
                # tradeoffs and we’ll have to tweak it to make it usable in
                # a parallel environment even if SQLite is not parallel.

                # A pool_size of 1 allows only 1 simultaneous connection.
                pool_size         = 1,
                max_overflow      = 0,

                # Since we have only 1 stream of work (pool_size=1),
                # we need to put a hold on other DB requests that arrive
                # from other parallel tasks. We do this putting a high value
                # on pool_timeout, which controls the number of seconds to
                # wait before giving up on getting a connection from the
                # pool.
                pool_timeout      = 3600.0,

                # Debug connection and all queries
                # echo              = True
            ),
        )

        # Start with a default config
        engine_config=engine_config_sets['DEFAULT'].copy()

        # Add engine-specific configs
        for dbtype in engine_config_sets.keys():
            # Extract from engine_config_sets configuration specific
            # for each DB type
            if dbtype in self.url:
                engine_config.update(engine_config_sets[dbtype])

        if hasattr(self,'db')==False or self.db is None:
            self.getLogger().debug(f"Creating a DB engine on {self.url}")

            self.db=sqlalchemy.create_engine(
                url = self.url,
                **engine_config
            )

        return self.db



    def last(self, kind, id):
        """
        Return last time data was updated on cache for this kind and id
        """

        table=self.typeTable.format(kind=kind)

        q='''
            SELECT max({timeCol}) AS last
            FROM {typeTable}
            WHERE {idCol} = '{id}'
        '''

        query=q.format(
            typeTable     = table,
            idCol         = self.idCol,
            timeCol       = self.timeCol,
            id            = id
        )

        try:
            self.getLogger().debug(f'Trying cache as {query}')

            with self.getDB().connect() as db:
                df=pandas.read_sql(query,con=db)

            if df.shape[0]>0:
                self.logger.info(f"Successful cache hit for kind={kind} and id={id} with {df.shape[0]} records.")
                df['last']=pandas.to_datetime(df['last'])
                ret=df['last'][0]
                if ret.tzinfo is None or ret.tzinfo.utcoffset(ret) is None:
                    ret=ret=ret.tz_localize('UTC')
            else:
                self.getLogger().info(f"Cache empty for kind={kind} and id={id}")
                ret=None
        except Exception as e:
            self.getLogger().warning(f"No cache for kind={kind} and id={id}")
            self.getLogger().info(e)
            ret=None


        return ret



    def get(self, kind, id, time=None):
        """
        kind leads to table DataCache_{kind}

        id is written to column __DataCache_id

        time makes it search on column __DataCache_time for entries with id
        recent up to time.

        Returns a tuple with table and time of cache data.
        """

        table=self.typeTable.format(kind=kind)

        if time is None:
            pointInTime='''
            (
                SELECT DISTINCT {timeCol}
                FROM {typeTable}
                WHERE {idCol} = '{id}'
                ORDER BY {timeCol} DESC
                LIMIT 1
            )
            '''
        else:
            pointInTime='''
            (
                SELECT DISTINCT {timeCol}
                FROM {typeTable}
                WHERE
                    {idCol}    = '{id}' AND
                    {timeCol} <= '{time}'
                ORDER BY {timeCol} DESC
                LIMIT 1
            )
            '''

        pointInTime=pointInTime.format(
            timeCol      = self.timeCol,
            time         = time,
            idCol        = self.idCol,
            id           = id,
            typeTable    = table
        )

        query='''
            SELECT *
            FROM {typeTable}
            WHERE
                {idCol}   = '{id}' AND
                {timeCol} = {pointInTime}
        '''

        query=query.format(
            typeTable    = table,
            idCol        = self.idCol,
            timeCol      = self.timeCol,
            id           = id,
            pointInTime  = pointInTime
        )

        try:
            self.getLogger().debug(f'Trying cache as {query}')

            with self.getDB().connect() as db:
                df=pandas.read_sql(query,con=db)

            if df.shape[0]>0:
                age=pandas.Timestamp(df[self.timeCol].max())
                self.getLogger().info(f"Cache for kind={kind} and id={id} has {df.shape[0]} entries and was cached at {age}")
                return (df.drop(columns=[self.timeCol,self.idCol]),age)
            else:
                self.getLogger().info(f"Cache empty for kind={kind} and id={id}")
                return (None,None)

        except Exception as e:
            self.getLogger().info(f"No cache for kind={kind} and id={id}")
            self.getLogger().info(e)

            return (None,None)



    def cleanOld(self, kind, id):
        # Next query is overcomplicated because couldn’t make work its simplest version:
        # cleanQuery='''
        #     DELETE
        #     FROM {typeTable}
        #     WHERE {idCol} = '{id}'
        #     AND {timeCol} <= coalesce(
        #         (
        #             SELECT DISTINCT {timeCol}
        #             FROM {typeTable}
        #             WHERE {idCol} = '{id}'
        #             ORDER BY {timeCol} DESC
        #             limit 1 offset {recycle}
        #         ),
        #         date(0)
        #     )
        # '''

        # This query also doesn’t work flawlessly probably because of dead lock
        # https://stackoverflow.com/a/52467973/367824
        # cleanQuery='''
        #     WITH oldest AS (
        #         SELECT DISTINCT {timeCol}
        #         FROM {typeTable}
        #         WHERE {idCol} = '{id}'
        #         ORDER BY {timeCol} DESC limit 1 offset {recycle}
        #     )
        #     DELETE FROM {typeTable}
        #     WHERE EXISTS (
        #         SELECT 1
        #         FROM oldest
        #         WHERE {typeTable}.{timeCol} <= oldest.{timeCol}
        #     )
        # '''

        versionSelector='''
            SELECT DISTINCT {timeCol} AS deprecated
            FROM {typeTable}
            WHERE {idCol} = '{id}'
            ORDER BY {timeCol} DESC limit 1 offset {recycle}
        '''

        cleaner='''
            DELETE
            FROM {typeTable}
            WHERE {idCol} = '{id}'
            AND {timeCol} <= '{deprecated}'
        '''

        if self.recycle is not None:
            with self.getDB().connect() as db:
                deprecated=pandas.read_sql_query(
                    versionSelector.format(
                        typeTable    = self.typeTable.format(kind=kind),
                        idCol        = self.idCol,
                        timeCol      = self.timeCol,
                        id           = id,
                        recycle      = self.recycle
                    ),
                    con=db
                )

                if deprecated.shape[0]>0:
                    cleanQuery=cleaner.format(
                        typeTable    = self.typeTable.format(kind=kind),
                        idCol        = self.idCol,
                        timeCol      = self.timeCol,
                        id           = id,
                        deprecated   = deprecated.deprecated.iloc[0],
                        recycle      = self.recycle
                    )

                    self.getLogger().debug(f'Clean old cache entries as {cleanQuery}')
                    db.execute(sqlalchemy.text(cleanQuery))
                    db.commit()



    def set(self, kind, id, data):
        """
        kind leads to table DataCache__{kind}

        id is written to column __DataCache_id

        Current time is written to column __DataCache_time

        data is a DataFrame whose columns are the other columns of table DataCache__{kind}
        """

        d=data.copy()

        columns=list(d.columns)

        d[self.idCol]=id
        now=pandas.Timestamp.utcnow()
        d[self.timeCol]=now


        self.getLogger().info(f'Set cache to kind={kind}, id={id}, time={now}')

        with self.getDB().connect() as db:
            d[[self.idCol,self.timeCol] + columns].to_sql(
                self.typeTable.format(kind=kind),
                index       = False,
                if_exists   = 'append',
                chunksize   = 999,
                con         = db,
                method      = 'multi'
            )

        self.cleanOld(kind, id)