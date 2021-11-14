import logging
import sqlalchemy
import pandas as pd





class DataCache(object):
    idCol       = '__DataCache_id'
    timeCol     = '__DataCache_time'
    typeTable   = 'DataCache__{kind}'



    def __init__(self, url='sqlite:///cache.db', recycle=5):
        self.url=url
        self.db=None
        self.recycle=recycle

        # Setup logging
        self.getLogger()

        self.getDB()


    def __repr__(self):
        return 'DataCache(url={url},recycle={recycle})'.format(url=self.url,recycle=self.recycle)



#     def __del__(self):
#         if hasattr(self,'db') and self.db:
#             self.db.close()
#             self.db=None



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
        sqlite_fake_multithreading=dict(
            poolclass         = sqlalchemy.pool.QueuePool,
            pool_size         = 1,
            max_overflow      = 0,

            # virtually wait forever until the used connection is freed
            pool_timeout      = 3600.0
        )

        if hasattr(self,'db')==False or self.db is None:
            self.db=sqlalchemy.create_engine(
                url = self.url,
                **sqlite_fake_multithreading
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

        self.getDB()

        query=q.format(
            typeTable=table,
            idCol=self.idCol,
            timeCol=self.timeCol,
            id=id
        )

        try:
            self.getLogger().debug(f'Trying cache as {query}')

            df=pd.read_sql(query,con=self.db)

            if df.shape[0]>0:
                self.logger.debug(f"Successful cache hit for kind={kind} and id={id}")
                df['last']=pd.to_datetime(df['last'])
                ret=df['last'][0]
                if ret.tzinfo is None or ret.tzinfo.utcoffset(ret) is None:
                    ret=ret=ret.tz_localize('UTC')
            else:
                self.getLogger().info(f"Cache empty for kind={kind} and id={id}")
                ret=None
        except Exception as e:
            self.getLogger().info(f"No cache for kind={kind} and id={id}")
            self.getLogger().info(e)
            ret=None


        return ret



    def get(self, kind, id, time=None):
        """
        kind leads to table DataCache_{kind}

        id is written to column __DataCache_id

        time makes it search on column __DataCache_time for entries with id recent up to time
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
                    {idCol} = '{id}'
                    AND {timeCol} <= '{time}'
                ORDER BY {timeCol} DESC
                LIMIT 1
            )
            '''

        pointInTime=pointInTime.format(
            timeCol=self.timeCol,
            time=time,
            idCol=self.idCol,
            id=id,
            typeTable=table
        )

        query='''
            SELECT *
            FROM {typeTable}
            WHERE
                {idCol} = '{id}'
                AND {timeCol} = {pointInTime}
        '''

        query=query.format(
            typeTable=table,
            idCol=self.idCol,
            timeCol=self.timeCol,
            id=id,
            pointInTime=pointInTime
        )

        self.getDB()

        try:
            self.getLogger().debug(f'Trying cache as {query}')

            df=pd.read_sql(query,con=self.db)

            if df.shape[0]>0:
                self.getLogger().debug(f"Successful cache hit for kind={kind} and id={id}")
                ret=df.drop(columns=[self.timeCol,self.idCol])
            else:
                self.getLogger().info(f"Cache empty for kind={kind} and id={id}")
                ret=None
        except Exception as e:
            self.getLogger().info(f"No cache for kind={kind} and id={id}")
            self.getLogger().info(e)
            ret=None

        return ret



    def cleanOld(self, kind, id):
        cleanQuery='''
            DELETE
            FROM {typeTable}
            WHERE {idCol} = '{id}'
            AND {timeCol} <= (
                SELECT DISTINCT {timeCol}
                FROM {typeTable}
                WHERE {idCol} = '{id}'
                ORDER BY {timeCol} DESC
                limit 1 offset {recycle}
            )
        '''

        if self.recycle is not None:
            cleanQuery=cleanQuery.format(
                typeTable    = self.typeTable.format(kind=kind),
                idCol        = self.idCol,
                timeCol      = self.timeCol,
                id           = id,
                recycle      = self.recycle
            )

            self.getDB().execute(cleanQuery)



    def set(self, kind, id, data):
        """
        kind leads to table DataCache_{kind}

        id is written to column __DataCache_id

        Current time is written to column __DataCache_time
        """

        d=data.copy()

        columns=list(d.columns)

        d[self.idCol]=id
        d[self.timeCol]=pd.Timestamp.utcnow()


        self.getLogger().info(f'Set cache to kind={kind}, id={id}, time={d[self.timeCol]}')

        d[[self.idCol,self.timeCol] + columns].to_sql(
            self.typeTable.format(kind=kind),
            index       = False,
            if_exists   = 'append',
            chunksize   = 999,
            con         = self.getDB(),
            method      = 'multi'
        )

        self.cleanOld(kind, id)