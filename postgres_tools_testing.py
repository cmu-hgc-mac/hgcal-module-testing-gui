import asyncpg
import asyncio
import yaml

# Load configuration file
configuration = {}
with open('configuration.yaml', 'r') as file:
    configuration = yaml.safe_load(file)


def get_query(table_name):
    if table_name == 'module_pedestal_test':
        pre_query = f""" 
        INSERT INTO {table_name}  
        (module_name, rel_hum, temp_c, bias_vol, chip, channel, channeltype, adc_median, adc_iqr, tot_median, tot_iqr, toa_median, toa_iqr, adc_mean, adc_stdd, tot_mean, tot_stdd, toa_mean, toa_stdd, tot_efficiency, tot_efficiency_error, toa_efficiency, toa_efficiency_error, pad, x, y, count_dead_chan, date_test, time_test, inspector, comment) 
        VALUES   """  ### maintain space
    elif table_name == 'module_iv_test':
        pre_query = f""" 
        INSERT INTO {table_name} 
        (module_name, rel_hum, temp_c, status, status_desc, grade, count_dead_chan, ratio_iv, prog_v, meas_v, meas_i, meas_r, date_test, time_test, inspector, comment)  
        VALUES  """  ### maintain space
    elif table_name == 'hxb_pedestal_test':
        pre_query = f""" 
        INSERT INTO {table_name} 
        (hxb_name, rel_hum, temp_c, chip, channel, channeltype, adc_median, adc_iqr, tot_median, tot_iqr, toa_median, toa_iqr, adc_mean, adc_stdd, tot_mean, tot_stdd, toa_mean, toa_stdd, tot_efficiency, tot_efficiency_error, toa_efficiency, toa_efficiency_error, pad, x, y, count_dead_chan, date_test, time_test, inspector, comment) 
        VALUES  """  ### maintain space
    elif table_name == 'module_pedestal_plots':
        pre_query = f""" 
        INSERT INTO {table_name} 
        (module_name, adc_mean_hexmap, adc_stdd_hexmap, noise_channel_chip0, noise_channel_chip1, noise_channel_chip2, pedestal_channel_chip0, pedestal_channel_chip1, pedestal_channel_chip2, total_noise_chip0, total_noise_chip1, total_noise_chip2, inspector, comment_plot_test) 
        VALUES  """  ### maintain space
    data_placeholder = ', '.join(['${}'.format(i) for i in range(1, len(pre_query.split(','))+1)])
    query = f"""{pre_query} {'({})'.format(data_placeholder)}"""
    return query

async def upload_PostgreSQL(table_name, db_upload_data):
    conn = await asyncpg.connect(
        host = 'cmsmac04.phys.cmu.edu',
        database = 'hgcdb',
        user = 'teststand_user',
        password = confguration['DBPassword'])
    
    print('Connection successful.')

    schema_name = 'public'
    table_exists_query = """
    SELECT EXISTS (
        SELECT 1 
        FROM information_schema.tables 
        WHERE table_schema = $1 
        AND table_name = $2
    );
    """
    table_exists = await conn.fetchval(table_exists_query, schema_name, table_name)  ### Returns True/False
    if table_exists:
        print(f'Executing query: {query}')
        query = get_query(table_name)
        await conn.execute(query, *db_upload_data)
        print(f'Data is successfully uploaded to the {table_name}!')
    else:
        print(f'Table {table_name} does not exist in the database.')
    await conn.close()

def get_query_read(component_type):
    if component_type == 'module_pedestal_test':
        query = """SELECT module_name, rel_hum, temp_c, bias_vol, date_test, time_test, inspector, comment 
            FROM module_pedestal_test
            WHERE inspector = 'acrobert'
            ORDER BY date_test DESC, time_test DESC LIMIT 10;"""
    elif component_type == 'hxb_pedestal_test':
        query = """SELECT hxb_name, rel_hum, temp_c, date_test, time_test, inspector, comment 
            FROM hxb_pedestal_test
            WHERE inspector = 'acrobert'
            ORDER BY date_test DESC, time_test DESC LIMIT 10;"""
    elif component_type == 'module_iv_test':
        query = """SELECT module_name, rel_hum, prog_v, meas_v, meas_i, meas_r, date_test, time_test, inspector, comment 
            FROM module_iv_test
            WHERE inspector = 'acrobert'
            ORDER BY date_test DESC, time_test DESC LIMIT 10;"""    
    elif component_type == 'baseplate':
        query = """SELECT bp_name, thickness, geometry, resolution 
        FROM bp_inspect 
        WHERE geometry = 'full';"""

    else:
        query = None
        print('Table not found. Check argument.')
    return query

async def fetch_PostgreSQL(component_type):
    conn = await asyncpg.connect(
        host='cmsmac04.phys.cmu.edu',
        database='hgcdb',
        user='teststand_user',
        password='hgcal'
    )
    value = await conn.fetch(get_query_read(component_type))
    await conn.close()
    return value


# from datetime import datetime
# date_inspect = datetime.strptime(date, '%Y-%m-%d')
# time_inspect = datetime.strptime(time, '%H:%M:%S.%f')

# from postgres_tools import upload_PostgreSQL
# db_upload_ped = [module_name, rel_hum, temp_c, bias_vol, chip, channel, channeltype, adc_median, adc_iqr, tot_median, tot_iqr, toa_median, toa_iqr, adc_mean, adc_stdd, tot_mean, tot_stdd, toa_mean, toa_stdd, tot_efficiency, tot_efficiency_error, toa_efficiency, toa_efficiency_error, pad, x, y, date_inspect, time_inspect, inspector, comment]
# await upload_PostgreSQL(table_name = 'module_pedestal_test', db_upload_data = db_upload_ped)

# db_upload_iv = [module_name, rel_hum, temp_c, prog_v, meas_v, meas_i, meas_r, date_inspect, time_inspect, inspector, comment]
# await upload_PostgreSQL(table_name = 'module_iv_test', db_upload_data = db_upload_iv)

# db_upload_hxped = [hxb_name, rel_hum, temp_c, chip, channel, channeltype, adc_median, adc_iqr, tot_median, tot_iqr, toa_median, toa_iqr, adc_mean, adc_stdd, tot_mean, tot_stdd, toa_mean, toa_stdd, tot_efficiency, tot_efficiency_error, toa_efficiency, toa_efficiency_error, pad, x, y, date_inspect, time_inspect, inspector, comment]
# await upload_PostgreSQL(table_name = 'hxb_pedestal_test', db_upload_data = db_upload_hxped)
