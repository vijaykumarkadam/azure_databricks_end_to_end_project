# Databricks notebook source
# MAGIC %md
# MAGIC # Data reading 

# COMMAND ----------

df = spark.read.format("parquet")\
    .option('inferSchema', True)\
    .load('abfss://bronze@datalakecarsale.dfs.core.windows.net/raw_data')

# COMMAND ----------

df.display()

# COMMAND ----------

# MAGIC %md 
# MAGIC ## Data transformation

# COMMAND ----------

from pyspark.sql import functions as F

# COMMAND ----------

df = df.withColumn('model_category', F.split(df['Model_ID'], '-')[0])

# COMMAND ----------

df.display()

# COMMAND ----------

df = df.withColumn('revenue_per_unit', df['Revenue']/df['Units_Sold'])

# COMMAND ----------

df.display()

# COMMAND ----------

# MAGIC %md 
# MAGIC ## AD-HOC analysis (data aggregation)
# MAGIC How many units were sold of each branch every year. To know which branch is doing good and which is doing bad. 

# COMMAND ----------

from pyspark.sql.functions import sum as F_sum

df.groupBy('Year', 'BranchName').agg(
    F_sum('Units_Sold').alias('Total_Units_Sold')
).sort('Year', 'Total_Units_Sold', ascending=[True, False]).display()

# COMMAND ----------

# MAGIC %md 
# MAGIC ## Data writing

# COMMAND ----------

df.write.format('parquet')\
    .mode('overwrite')\
    .option('path', 'abfss://silver@datalakecarsale.dfs.core.windows.net/carsales')\
    .save()

# COMMAND ----------

# MAGIC %md 
# MAGIC ## Querying Silver Data

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT * FROM PARQUET.`abfss://silver@datalakecarsale.dfs.core.windows.net/carsales`

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT * FROM PARQUET.`silver@datalakecarsale.dfs.core.windows.net/carsales`
