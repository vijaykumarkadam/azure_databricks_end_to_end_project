# Databricks notebook source
from pyspark.sql.functions import *
from pyspark.sql.types import *

# COMMAND ----------

# MAGIC %md 
# MAGIC ## Create Flag Parameter

# COMMAND ----------

# incremental_flag with default value 0
dbutils.widgets.text('incremental_flag', 'o')

# COMMAND ----------

# get the value of the incremental_flag (will be used for incremental load and intial load)
# incremental flag is a string
# incremental_flad is used to determine if the data is incremental or initial load
incremental_flag = dbutils.widgets.get('incremental_flag')
print(incremental_flag)

# COMMAND ----------

# MAGIC %md 
# MAGIC # Creating Dimenion Model 

# COMMAND ----------

# MAGIC %md 
# MAGIC ### Fetch Relative Columns

# COMMAND ----------

df_src = spark.sql(
    """
    SELECT * 
    FROM PARQUET.`abfss://silver@datalakecarsale.dfs.core.windows.net/carsales`
    """
)


# COMMAND ----------

df_src.display()

# COMMAND ----------

df_src = spark.sql(
    """
    SELECT Dealer_ID
    FROM PARQUET.`abfss://silver@datalakecarsale.dfs.core.windows.net/carsales`
    """
)
df_src.display()

# COMMAND ----------

# MAGIC %md 
# MAGIC ### dim_branch Sink -  Initial & Incremental 
# MAGIC #### (just bring the schema if tabel does not exist)

# COMMAND ----------

# this query is never true, so it will not return any data but it will only return the SCHEMA of the dimension table that we want to create
# this condition is only for initial laod
# if the table does not exist, I want to get the schema
# if the table exists (incremental load), bring all the data (which will be used in the left join)
if not spark.catalog.tableExists('cars_catalog.gold.dim_dealer'):
    df_sink = spark.sql(
        '''
        SELECT 1 as dim_dealer_key, Dealer_ID 
        FROM PARQUET.`abfss://silver@datalakecarsale.dfs.core.windows.net/carsales`
        WHERE 1=0
        '''
    )
else:
    df_sink = spark.sql(
        '''
        SELECT dim_dealer_key, Dealer_ID 
        FROM cars_catalog.gold.dim_dealer
        '''
    )



# COMMAND ----------

df_sink.display()

# COMMAND ----------

# MAGIC %md 
# MAGIC ## Filtering new records & old records

# COMMAND ----------

# df_src is the left table, df_sink left table in the left join. 
df_filter = df_src.join(df_sink, df_src.Dealer_ID  == df_sink.Dealer_ID , 'left').select(df_src.Dealer_ID , df_sink.dim_dealer_key)

# COMMAND ----------

# since all the dim_key are null, we can insert the data
df_filter.display()

# COMMAND ----------

# MAGIC %md 
# MAGIC ### df_filter_old

# COMMAND ----------

df_filter_old = df_filter.filter(df_filter.dim_dealer_key.isNotNull())

# COMMAND ----------

df_filter_old.display()

# COMMAND ----------

# MAGIC %md 
# MAGIC ### df_filter_new

# COMMAND ----------

df_filter_new = df_filter.filter(df_filter.dim_dealer_key.isNull()).select('Dealer_ID')

# COMMAND ----------

df_filter_new.display()

# COMMAND ----------

# MAGIC %md 
# MAGIC ### Create Surrogate Key 
# MAGIC
# MAGIC A surrogate key also called a **synthetic primary key**, is generated when a new record is inserted into a table automatically by a database that can be declared as the primary key of that table.

# COMMAND ----------

# MAGIC %md 
# MAGIC **Fetch the max Surrogate Key from existing table**

# COMMAND ----------

# we will use the incremental flag 
if (incremental_flag == '0'): 
    max_value = 1
else:
    if spark.catalog.tableExists('cars_catalog.gold.dim_dealer'):
        max_value_df = spark.sql("SELECT max(dim_dealer_key) FROM cars_catalog.gold.dim_dealer")
        max_value = max_value_df.collect()[0][0]

# COMMAND ----------

if spark.catalog.tableExists('cars_catalog.gold.dim_dealer'):
    max_value_df = spark.sql("SELECT max(dim_dealer_key) FROM cars_catalog.gold.dim_dealer")
    max_value = max_value_df.collect()[0][0]
else:
    max_value = 1

# COMMAND ----------

# MAGIC %md 
# MAGIC **Create Surrogate key column & ADD the max surrogate key**

# COMMAND ----------

from pyspark.sql import functions as F
df_filer_new = df_filter_new.withColumn('dim_dealer_key', max_value + F.monotonically_increasing_id())

# COMMAND ----------

df_filter_new.display()

# COMMAND ----------

# MAGIC %md
# MAGIC **Create final DF - df_filter_olf + df_filter_new**

# COMMAND ----------

df_final = df_filter_new.union(df_filter_old)

# COMMAND ----------

df_final.display()

# COMMAND ----------

# MAGIC %md 
# MAGIC ## Slowly Changing Dimension (SCD) TYPE - 1 (UPSERT)

# COMMAND ----------

from delta.tables import DeltaTable

# COMMAND ----------

# Incremental RUN 
if spark.catalog.tableExists('cars_catalog.gold.dim_dealer'):
    delta_table = DeltaTable.forPath(spark, "abfss://gold@datalakecarsale.dfs.core.windows.net/dim_dealer")
    # update when the value exists
    # insert when new value 
    delta_table.alias("target").merge(df_final.alias("source"), "target.dim_dealer_key = source.dim_dealer_key")\
        .whenMatchedUpdateAll()\
        .whenNotMatchedInsertAll()\
        .execute()

# Initial RUN 
else: # no table exists
    df_final.write.format("delta")\
        .mode("overwrite")\
        .option("path", "abfss://gold@datalakecarsale.dfs.core.windows.net/dim_dealer")\
        .saveAsTable("cars_catalog.gold.dim_dealer")

# COMMAND ----------

# MAGIC %sql 
# MAGIC SELECT * FROM cars_catalog.gold.dim_dealer

# COMMAND ----------
