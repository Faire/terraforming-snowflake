import logging
import os
import sys
import getpass

import pandas as pd  # for type hints
import snowflake.connector
import snowflake.connector.errors
import sqlalchemy
import json
from contextlib import closing, contextmanager
from typing import Iterator, List, Tuple

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Snowflake login credentials
ACCOUNT = "YOUR_ACCOUNT"
WAREHOUSE = "YOUR_WAREHOUSE"
DATABASE = "YOUR_DATABASE"
ROLE = "YOUR_ROLE"
SCHEMA = "PUBLIC"

QUERY_TAGS = {
    "user": os.environ.get("SNOWFLAKE_USER"),
    "unix_user": getpass.getuser(),  # useful backup
    "entrypoint": f"{sys.argv[0]}" if sys.argv[0].endswith(".py") else "adhoc",  # Name of the entrypoint / calling script
    # Add other useful tags that pertain to your tech stack!
}


@contextmanager
def get_snowflake_connection(
    **kwargs,
) -> Iterator[snowflake.connector.SnowflakeConnection]:
    if not (os.environ.get("SNOWFLAKE_USER") and os.environ.get("SNOWFLAKE_PASSWORD")):
        raise OSError("Missing env vars: SNOWFLAKE_USER and/or SNOWFLAKE_PASSWORD")

    # Note that the connection is opened with autocommit set to True
    con = snowflake.connector.connect(
        account=ACCOUNT,
        user=os.environ.get("SNOWFLAKE_USER"),
        password=os.environ.get("SNOWFLAKE_PASSWORD"),
        database=DATABASE,
        schema=SCHEMA,
        warehouse=WAREHOUSE,
        role=ROLE,
        session_parameters={
            "QUERY_TAG": f"{json.dumps(QUERY_TAGS)}"
        },
        **kwargs,
    )

    try:
        yield con
    finally:
        if not kwargs.get("autocommit", False):
            con.commit()  # commits when closing connection, used in cases such as `exec_sql_multi`
        con.close()


@contextmanager
def get_sqlalchemy_engine() -> Iterator[sqlalchemy.engine.base.Engine]:
    """
    Returns a ContextManager wrapped SQLAlchemy Engine - used by Pandas to access Snowflake.
    """
    engine = sqlalchemy.create_engine(
        f"snowflake://{os.environ.get('SNOWFLAKE_USER')}:{os.environ.get('SNOWFLAKE_PASSWORD')}@{ACCOUNT}/{DATABASE}/{SCHEMA}?warehouse={WAREHOUSE}&role={ROLE}"
    )
    try:
        yield engine
    finally:
        engine.dispose()

def exec_sql_multi(sql: str) -> List[Tuple]:
    results = []

    with get_snowflake_connection(
        autocommit=False
    ) as con:  # autocommit=False because multi is typically a transaction command, it's important for all the commands to execute succesfully - if autocommit=True, and only one succeeds, we will have partial execution
        try:
            cursor_list = con.execute_string(sql)
            for cursor in cursor_list:
                logging.debug(f"cursor_list: {cursor_list}")
                with closing(cursor):
                    try:
                        for row in cursor:
                            results.append(row)
                    except TypeError:
                        results.append(None)

        except snowflake.connector.errors.ProgrammingError as e:
            logger.exception(f"Failed to execute query:\n{sql}")
            raise

    return results


def exec_sql(sql: str, autocommit: bool = True) -> List[Tuple]:
    if sql.count(";") > 1:
        # could be a multi line SQL statement that is wrapped in begin/commit clauses
        logging.info(
            "Multiple ; detected in a statement, trying to run exec_sql_multi instead."
        )
        return exec_sql_multi(sql)
    else:
        result = []
        # Note that this opens a new connection on each call, so it's not ideal
        #   for performance executing many queries one after another
        with get_snowflake_connection(autocommit=autocommit) as con:
            with closing(con.cursor()) as cur:
                try:
                    cur.execute(sql)
                    result = cur.fetchall()

                except snowflake.connector.errors.ProgrammingError as e:
                    logging.exception(f"Error executing sql:\n{sql}")
                    raise

        return result  # type: ignore

def query_to_df(sql: str, autocommit: bool = True) -> pd.DataFrame:
    logger.info(sql)

    with get_snowflake_connection(autocommit=autocommit) as con:
        with closing(con.cursor()) as cur:
            try:
                cur.execute(sql)
                df = cur.fetch_pandas_all()
                df.columns = df.columns.str.lower()

            except snowflake.connector.errors.ProgrammingError as e:
                logger.exception(f"Failed to fetch DataFrame using query:\n{sql}")
                raise

    return df

