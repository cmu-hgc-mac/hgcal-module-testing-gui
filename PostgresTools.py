import asyncpg
import asyncio
import yaml

# Load configuration file
configuration = {}
with open('configuration.yaml', 'r') as file:
    configuration = yaml.safe_load(file)


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
    conn = await asyncpg.connect(
        host = configuration['DBHostname'],
        database = configuration['DBDatabase'],
        user = configuration['DBUsername'],
        password = configuration['DBPassword']
    )
    
    print(f'  >> Postgres Tools: Connection successful.')

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
    if table_exists:

        # new db uploading scheme
        query = get_query(table_name, db_upload_data.keys())
        print(f'  >> PostgresTools: Executing query: {query}')
        await conn.execute(query, *db_upload_data.values())

        print(f'  >> PostgresTools: Data is successfully uploaded to the {table_name}!')
    else:
        print(f'  >> PostgresTools: Table {table_name} does not exist in the database.')
    await conn.close()

def get_query_read(table_name, part_name = None):
    """
    General function for db read queries. Takes in table name and returns query string. Does not return all columns as don't want to 
    print everything (i.e. don't want to dump all bytes from image)
    """

    # define queries
    if table_name == 'module_pedestal_test':
        query = f"""SELECT module_name, rel_hum, temp_c, bias_vol, date_test, time_test, inspector, comment
            FROM {table_name}
            ORDER BY date_test DESC, time_test DESC LIMIT 10;"""
    elif table_name == 'hxb_pedestal_test':
        query = f"""SELECT hxb_name, rel_hum, temp_c, date_test, time_test, inspector, comment
            FROM {table_name}
            ORDER BY date_test DESC, time_test DESC LIMIT 10;"""
    elif table_name == 'module_iv_test':
        query = f"""SELECT module_name, rel_hum, temp_c, meas_i, date_test, time_test, inspector, comment
            FROM {table_name}
            ORDER BY date_test DESC, time_test DESC LIMIT 10;"""
    elif table_name == 'module_pedestal_plots' and part_name is not None:
        query = f"""SELECT adc_mean_hexmap                                                                                           
            FROM {table_name}   
            WHERE module_name = '{part_name}';"""
    elif table_name == 'module_pedestal_plots':
        query = f"""SELECT module_name, inspector, comment_plot_test                                                                                           
            FROM {table_name}                                                                                                                                                                                
            ORDER BY mod_plottest_no DESC LIMIT 10;"""
    else:
        query = None
        print('Table not found. Check argument.')
    return query

async def fetch_PostgreSQL(table_name, part_name = None):
    """
    General read function. Instantiates the connection to the database and reads the data. Returns the raw data.
    """

    # instantiate db connection
    conn = await asyncpg.connect(
        host = configuration['DBHostname'],
        database = configuration['DBDatabase'],
        user = configuration['DBUsername'],
	password = configuration['DBPassword']
    )

    # fetch and return
    value = await conn.fetch(get_query_read(table_name, part_name))
    await conn.close()
    return value


