import asyncpg
import asyncio
import yaml

# Load configuration file
configuration = {}
with open('configuration.yaml', 'r') as file:
    configuration = yaml.safe_load(file)

# Initiallize connection pool
_pool = None

async def _get_pool():
    """Create the connection pool.
    """

    global _pool

    if _pool is None:
        _pool = await asyncpg.create_pool(
            host=configuration['DBHostname'],
            database=configuration['DBDatabase'],
            user=configuration['DBUsername'],
            password=configuration['DBPassword']
        )

    return _pool

async def close_pool():
    """Close the connection pool.
    """

    global _pool

    if _pool is not None:
        await _pool.close()
        _pool = None


# Functions for uploading/fetching data to PostgreSQL
def get_query_old(table_name):
    """
    General function for db get queries. Defines which columns and what order of columns are used by the db tools functions to 
    upload. Returns formatted query string.
    """

    if table_name == 'module_pedestal_test':
        #pre_query = f""" 
        #INSERT INTO {table_name}  
        #(module_name, rel_hum, temp_c, bias_vol, chip, channel, channeltype, adc_median, adc_iqr, tot_median, tot_iqr, toa_median, toa_iqr, adc_mean, adc_stdd, tot_mean, tot_stdd, toa_mean, toa_stdd, tot_efficiency, tot_efficiency_error, toa_efficiency, toa_efficiency_error, pad, x, y, count_dead_chan, list_dead_pad, date_test, time_test, inspector, comment) 
        #VALUES   """  ### maintain space
        pre_query = f""" 
        INSERT INTO {table_name}  
        (module_name, rel_hum, temp_c, bias_vol, chip, channel, channeltype, adc_median, adc_iqr, tot_median, tot_iqr, toa_median, toa_iqr, adc_mean, adc_stdd, tot_mean, tot_stdd, toa_mean, toa_stdd, tot_efficiency, tot_efficiency_error, toa_efficiency, toa_efficiency_error, pad, x, y, count_dead_chan, date_test, time_test, inspector, comment) 
        VALUES   """  ### maintain space

    elif table_name == 'module_iv_test':
        #pre_query = f""" 
        #INSERT INTO {table_name} 
        #(module_name, rel_hum, temp_c, status, status_desc, grade, ratio_i_at_vs, ratio_at_vs, prog_v, meas_v, meas_i, meas_r, date_test, time_test, inspector, comment)  
        #VALUES  """  ### maintain space
        pre_query = f""" 
        INSERT INTO {table_name} 
        (module_name, rel_hum, temp_c, status, status_desc, grade, ratio_iv, prog_v, meas_v, meas_i, meas_r, date_test, time_test, inspector, comment)  
        VALUES  """  ### maintain space
    elif table_name == 'hxb_pedestal_test':
        pre_query = f""" 
        INSERT INTO {table_name} 
        (hxb_name, rel_hum, temp_c, chip, channel, channeltype, adc_median, adc_iqr, tot_median, tot_iqr, toa_median, toa_iqr, adc_mean, adc_stdd, tot_mean, tot_stdd, toa_mean, toa_stdd, tot_efficiency, tot_efficiency_error, toa_efficiency, toa_efficiency_error, pad, x, y, count_dead_chan, list_dead_pad, date_test, time_test, inspector, comment) 
        VALUES  """  ### maintain space
    elif table_name == 'module_pedestal_plots':
        pre_query = f""" 
        INSERT INTO {table_name} 
        (module_name, adc_mean_hexmap, adc_stdd_hexmap, noise_channel_chip, pedestal_channel_chip, total_noise_chip, inspector, comment_plot_test) 
        VALUES  """  ### maintain space
    data_placeholder = ', '.join(['${}'.format(i) for i in range(1, len(pre_query.split(','))+1)])
    query = f"""{pre_query} {'({})'.format(data_placeholder)}"""
    return query

def get_query(table_name, column_names):
    """
    General function for db get queries. Returns formatted query string.
    """
    pre_query = f""" INSERT INTO {table_name} ({', '.join(column_names)}) VALUES  """ 
    data_placeholder = ', '.join(['${}'.format(i) for i in range(1, len(column_names)+1)])
    query = f"""{pre_query} {'({})'.format(data_placeholder)}"""
    return query

async def upload_PostgreSQL(table_name, db_upload_data):
    """
    General upload function. Instantiates the connection to the database, formats the query, and uploads the data.
    """
    
    # create db connection
    pool = await _get_pool()
    print(f'  >> Postgres Tools: Connection successful.')

    async with pool.acquire() as conn:
        # define query to check if table exists
        schema_name = 'public'
        table_exists_query = """
        SELECT EXISTS (
            SELECT 1 
            FROM information_schema.tables 
            WHERE table_schema = $1 
            AND table_name = $2
        );
        """

        # check table exists and upload
        table_exists = await conn.fetchval(table_exists_query, schema_name, table_name)  ### Returns True/False

        if not table_exists:
            print(f'  >> PostgresTools: Table {table_name} does not exist in the database.')
            await conn.close()
            return

        # remove key-value pairs from dict if not present in database table schema
        col_query = f"""SELECT column_name FROM information_schema.columns WHERE table_name = '{table_name}'; """
        columns = await conn.fetch(col_query)
        valid_columns = [row['column_name'] for row in columns]
        
        keylist = list(db_upload_data.keys())
        for key in keylist:
            if key not in valid_columns:
                db_upload_data.pop(key, None)
                print(f'  >> PostgresTools: upload key {key} not in schema of table {table_name}; removing from upload')

        # don't bother uploading an empty dictionary
        if len(db_upload_data.keys()) == 0:
            print(f'  >> PostgresTools: upload dictionary is empty, not uploading')
            await conn.close()
            return
                
        # new db uploading scheme
        query = get_query(table_name, db_upload_data.keys())
        print(f'  >> PostgresTools: Executing query: {query}')
        await conn.execute(query, *db_upload_data.values())

        print(f'  >> PostgresTools: Data is successfully uploaded to {table_name}!')


def get_query_read(table_name, part_name = None):
    """
    General function for db read queries. Takes in table name and returns query string. Does not return all columns as don't want to 
    print everything (i.e. don't want to dump all bytes from image)
    """

    # define queries
    if table_name == 'module_pedestal_test':
        query = f"""SELECT REPLACE(module_name,'-','') as module_name, rel_hum, temp_c, bias_vol, date_test, time_test, inspector, comment
            FROM {table_name}
            ORDER BY date_test DESC, time_test DESC LIMIT 10;"""
    elif table_name == 'hxb_pedestal_test':
        query = f"""SELECT REPLACE(hxb_name,'-','') as hxb_name, rel_hum, temp_c, date_test, time_test, inspector, comment
            FROM {table_name}
            ORDER BY date_test DESC, time_test DESC LIMIT 10;"""
    elif table_name == 'module_iv_test':
        query = f"""SELECT REPLACE(module_name,'-','') as module_name, rel_hum, temp_c, meas_i, date_test, time_test, inspector, comment
            FROM {table_name}
            ORDER BY date_test DESC, time_test DESC LIMIT 10;"""
    elif table_name == 'module_pedestal_plots' and part_name is not None:
        query = f"""SELECT adc_mean_hexmap                                                                                           
            FROM {table_name}   
            WHERE REPLACE(module_name,'-','') = '{part_name}';"""
    elif table_name == 'module_pedestal_plots':
        query = f"""SELECT REPLACE(module_name,'-','') as module_name, inspector, comment_plot_test                                               
            FROM {table_name}
            ORDER BY mod_plottest_no DESC LIMIT 10;"""
    else:
        query = None
        print('  >> PostgresTools: Table not found. Check argument.')
    return query

async def fetch_PostgreSQL(table_name, part_name = None):
    """
    General read function. Instantiates the connection to the database and reads the data. Returns the raw data.
    """

    # instantiate db connection
    pool = await _get_pool()

    # fetech and return
    query = get_query_read(table_name, part_name)
    async with pool.acquire() as conn:
        return await conn.fetch(query)


async def fetch_serial_PostgreSQL(table_name, part_name):
    """                                                                                                                                                                                                        
    General read function. Instantiates the connection to the database and reads the data. Returns the raw data.                                                                                               
    """

    # instantiate db connection  
    pool = await _get_pool()

    if table_name == 'module_pedestal_test' or table_name == 'module_iv_test':
        query = f"""SELECT *
            FROM {table_name}
            WHERE REPLACE(module_name,'-','') = '{part_name}'
            ORDER BY date_test, time_test;""" 
                    
    elif table_name == 'module_inspect':
        query = f"""SELECT *
            FROM {table_name}
            WHERE REPLACE(module_name,'-','') = '{part_name}'
            ORDER BY date_inspect, time_inspect;""" 

    elif table_name == 'proto_inspect':
        query = f"""SELECT *
            FROM {table_name}
            WHERE REPLACE(proto_name,'-','') = '{part_name}'
            ORDER BY date_inspect, time_inspect;""" 

    elif table_name == 'back_wirebond' or table_name == 'front_wirebond':
        query = f"""SELECT *
            FROM {table_name}
            WHERE REPLACE(module_name,'-','') = '{part_name}'
            ORDER BY date_bond, time_bond;""" 

    elif table_name in ['baseplate', 'bp_inspect']:
        query = f"""SELECT *
            FROM {table_name}
            WHERE REPLACE(bp_name,'-','') = '{part_name}';"""

    elif table_name in ['sensor']:
        query = f"""SELECT *
            FROM {table_name}
            WHERE REPLACE(sen_name,'-','') = '{part_name}';"""

    elif table_name in ['hexaboard', 'hxb_inspect', 'hxb_pedestal_test']:
        query = f"""SELECT *
            FROM {table_name}
            WHERE REPLACE(hxb_name,'-','') = '{part_name}';"""

    elif table_name in ['proto_assembly']:
        query = f"""SELECT *
            FROM {table_name}
            WHERE REPLACE(proto_name,'-','') = '{part_name}';"""

    elif table_name in ['module_info', 'module_assembly', 'back_wirebond', 'back_encap', 'front_wirebond', 'bond_pull_test', 'front_encap']:
        query = f"""SELECT *
            FROM {table_name}
            WHERE REPLACE(module_name,'-','') = '{part_name}';"""
        
    elif table_name == 'sen_iv_data':
        query = f"""SELECT *
            FROM {table_name}
            WHERE REPLACE(scratchpad_id,'-','') = '{part_name}';"""

    # fetch and return
    async with pool.acquire() as conn:
        return await conn.fetch(query)

async def add_bonding_instructions(part_name, list_rebond=[], list_dead_ground=[], list_noisy_ground=[]):
    """
    General read function. Instantiates the connection to the database and reads the data. Returns the raw data.
    """

    # instantiate db connection
    pool = await _get_pool()

    async with pool.acquire() as conn:
        async with conn.transaction():
            if ('320-X' in part_name) or ('320X' in part_name):  # hexaboard
                cmd = await conn.execute(
                    """
                    UPDATE hexaboard
                    SET mac_dead_pad_to_be_ground = $2,
                        mac_noisy_pad_to_be_ground = $3
                    WHERE hxb_name = $1;
                    """,
                    part_name, list_dead_ground, list_noisy_ground
                )
                return cmd

            elif ('320-M' in part_name) or ('320M' in part_name):  # live module
                cmd1 = await conn.execute(
                    """
                    UPDATE module_info
                    SET dead_pad_to_be_ground = $2,
                        noisy_pad_to_be_ground = $3,
                        pad_to_attempt_rebond = $4
                    WHERE module_name = $1;
                    """,
                    part_name, list_dead_ground, list_noisy_ground, list_rebond
                )
                # Update front_wirebond table to mark all wirebonds as not done
                cmd2 = await conn.execute(
                    """
                    UPDATE front_wirebond
                    SET wb_fr_marked_done = FALSE
                    WHERE module_name = $1;
                    """,
                    part_name
                )
                return cmd1 + " & " + cmd2

            else:
                return "UPDATE 0"

def serial_remove_dashes(moduleserial):

    if moduleserial.count('-') == 0:
        return moduleserial
    elif moduleserial.count('-') > 0 and moduleserial.count('-') < 4:
        raise ValueError

    undashedserial = moduleserial[0:3]+moduleserial[4:6]

    if '320M' in undashedserial or '320P' in undashedserial: # live module
        undashedserial += moduleserial[7:11]+moduleserial[12:14]+moduleserial[15:19]
    elif '320X' in undashedserial: # hexaboard
        undashedserial += moduleserial[7:10]+moduleserial[11:13]+moduleserial[14:19]
    else:
        print(undashedserial)
        raise ValueError
        
    return undashedserial


async def get_pedestal(moduleserial, BV, trimBV, modulestatus):
    """Fetches the pedestal data for a given module serial number, bias voltage, trim bias voltage, and module status (text).
    """

    # instantiate db connection  
    pool = await _get_pool()

    undashedserial = serial_remove_dashes(moduleserial)

    query = f"""SELECT *
        FROM module_pedestal_test
        WHERE module_name = '{undashedserial}'
            AND bias_vol = {BV}
            AND trim_bias_voltage = {trimBV}
            AND status_desc = '{modulestatus}'
        ORDER BY date_test, time_test;""" 

    async with pool.acquire() as conn:
        return await conn.fetch(query)


async def get_comments(moduleserial):
    """Fetches all the comments from the related tables for a given module serial number.
    """

    # instantiate db connection  
    pool = await _get_pool()
    undashedserial = serial_remove_dashes(moduleserial)

    # Define the list of tables and their columns to fetch comments from
    TABLES_DICT = {
        'bp_name': ['baseplate', 'bp_inspect'],
        'sen_name': ['sensor'],
        'hxb_name': ['hexaboard', 'hxb_inspect', 'hxb_pedestal_test'],
        'proto_name': ['proto_assembly', 'proto_inspect'],
       'module_name': ['module_assembly', 'module_inspect', 'back_wirebond', 'back_encap', 'front_wirebond', 'bond_pull_test', 'front_encap', 'module_pedestal_test', 'module_iv_test']
    }

    # Initialize the argument list and the union list for the query
    arg_list = []
    union_list = []

    # Loop through the tables and their columns to fetch comments from
    for key, values in TABLES_DICT.items():
        for table in values:
            # Define a new table for fetched comments
            arg = f"""
            {table}_comment AS (
                SELECT DISTINCT ON ({table}.{key})
                    {table}.comment
                FROM {table}
                JOIN mi ON REPLACE({table}.{key},'-','') = mi.{key}
                WHERE 
                    {table}.comment IS NOT NULL 
                    AND {table}.comment != '' 
                    AND {table}.comment != ' '
                    AND {table}.comment != '""'
                    AND {table}.comment != 'NULL'
                    AND REPLACE({table}.{key},'-','') = mi.{key}
            )
            """
            arg_list.append(arg)
            # Add the new table to the union list
            union_list.append(f"""SELECT * FROM {table}_comment""")

    # Construct the query
    query = rf"""
    WITH mi AS (
      SELECT
        REPLACE(module_name,'-','') AS module_name,
        REPLACE(bp_name,'-','')     AS bp_name,
        REPLACE(sen_name,'-','')    AS sen_name,
        REPLACE(hxb_name,'-','')    AS hxb_name,
        REPLACE(proto_name,'-','')  AS proto_name
      FROM module_info
      WHERE REPLACE(module_name,'-','') = $1
      LIMIT 1
    ),

    module_info_comment AS (
        SELECT DISTINCT ON (module_info.module_name)
            module_info.comment
        FROM module_info
        JOIN mi ON REPLACE(module_info.module_name,'-','') = mi.module_name
        WHERE 
            module_info.comment IS NOT NULL 
            AND module_info.comment != '' 
            AND module_info.comment != ' '
            AND module_info.comment != '""'
            AND module_info.comment != 'NULL'
            AND REPLACE(module_info.module_name,'-','') = mi.module_name
    ), 

    {', '.join(arg_list)}

    SELECT *
    FROM (
    SELECT * FROM module_info_comment
    UNION ALL {' UNION ALL '.join(union_list)}
    ) AS all_comments;
    """

    async with pool.acquire() as conn:
        return await conn.fetch(query, undashedserial)

async def async_module_exists(moduleserial):

    # instantiate db connection
    pool = await _get_pool()
    undashedserial = serial_remove_dashes(moduleserial)

    query = f"""SELECT COUNT(1)
                FROM module_info
                WHERE module_name = '{undashedserial}';"""

    async with pool.acquire() as conn:
        return await conn.fetch(query)

def module_exists(moduleserial):

    coro = async_module_exists(moduleserial)
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(coro)

    return result[0][0] > 0

async def async_hxb_exists(hxbserial):

    pool = await _get_pool()
    undashedserial = serial_remove_dashes(hxbserial)

    query = f"""SELECT COUNT(1)
                FROM hexaboard
                WHERE hxb_name = '{undashedserial}';"""

    async with pool.acquire() as conn:
        return await conn.fetch(query)

def hxb_exists(hxbserial):

    coro = async_hxb_exists(hxbserial)
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(coro)

    return result[0][0] > 0
