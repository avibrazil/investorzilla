import sqlite3
import logging
import pandas as pd





class DataCache(object):
    idCol       = '__DataCache_id'
    timeCol     = '__DataCache_time'
    typeTable   = 'DataCache__{type}'



    def __init__(self, dbFile='cache.db', recycle=5):
        self.dbFile=dbFile
        self.recycle=recycle

        # Setup logging
        self.logger = logging.getLogger(__name__ + '.' + self.__class__.__name__)



    def __repr__(self):
        return 'DataCache(dbFile={db},recycle={recycle})'.format(db=self.dbFile,recycle=self.recycle)


    def last(self, type, id):
        """
        Return last time data was updated on cache for this type and id
        """

        table=self.typeTable.format(type=type)

        q='''
            SELECT max({timeCol}) AS last
            FROM {typeTable}
            WHERE {idCol} = '{id}'
        '''

        self.db=sqlite3.connect(self.dbFile)

        query=q.format(
            typeTable=table,
            idCol=self.idCol,
            timeCol=self.timeCol,
            id=id
        )

        try:
            self.logger.debug(f'Trying cache as {query}')

            df=pd.read_sql(query,con=self.db)
            self.db.close()

            if df.shape[0]>0:
                self.logger.debug(f"Successful cache hit for type={type} and id={id}")
                df['last']=pd.to_datetime(df['last'])
                ret=df['last'][0]
                if ret.tzinfo is None or ret.tzinfo.utcoffset(ret) is None:
                    ret=ret=ret.tz_localize('UTC')
            else:
                self.logger.info(f"Cache empty for type={type} and id={id}")
                ret=None
        except Exception as e:
            self.logger.info(f"No cache for type={type} and id={id}")
            self.logger.info(e)
            ret=None


        return ret



    def get(self, type, id, time=None):
        """
        type leads to table DataCache_{type}

        id is written to column __DataCache_id

        time makes it search on column __DataCache_time for entries with id recent up to time
        """

        table=self.typeTable.format(type=type)

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

        self.db=sqlite3.connect(self.dbFile)

        try:
            self.logger.debug(f'Trying cache as {query}')

            df=pd.read_sql(query,con=self.db)
            self.db.close()

            if df.shape[0]>0:
                self.logger.debug(f"Successful cache hit for type={type} and id={id}")
                ret=df.drop(columns=[self.timeCol,self.idCol])
            else:
                self.logger.info(f"Cache empty for type={type} and id={id}")
                ret=None
        except Exception as e:
            self.logger.info(f"No cache for type={type} and id={id}")
            self.logger.info(e)
            ret=None


        return ret



    def cleanOld(self, type, id):
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
                typeTable=self.typeTable.format(type=type),
                idCol=self.idCol,
                timeCol=self.timeCol,
                id=id,
                recycle=self.recycle
            )

            self.db.execute(cleanQuery)



    def set(self, type, id, data):
        """
        type leads to table DataCache_{type}

        id is written to column __DataCache_id

        Current time is written to column __DataCache_time
        """

        d=data.copy()

        columns=list(d.columns)

        d[self.idCol]=id
        d[self.timeCol]=pd.Timestamp.utcnow()


        self.db=sqlite3.connect(self.dbFile)

        d[[self.idCol,self.timeCol] + columns].to_sql(
            self.typeTable.format(type=type),
            index=False,
            if_exists='append',
            con=self.db,
            method='multi'
        )

        self.cleanOld(type,id)

        self.db.close()


