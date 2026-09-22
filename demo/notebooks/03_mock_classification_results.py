# Databricks notebook source
# Populate a mock data-classification results table from the committed snapshot.
# Job param: results_table = catalog.schema.table

dbutils.widgets.text("results_table", "")
results_table = dbutils.widgets.get("results_table").strip()
assert results_table.count(".") == 2, f"results_table must be catalog.schema.table, got: {results_table!r}"
catalog, schema, _ = results_table.split(".")

# COMMAND ----------

# The parquet is synced alongside this notebook. Resolve its workspace path
# relative to the notebook location.
nb_path = (dbutils.notebook.entry_point.getDbutils().notebook()
           .getContext().notebookPath().get())
nb_dir = "/".join(nb_path.split("/")[:-1])                       # .../demo/notebooks
parquet_ws = f"/Workspace{nb_dir}/../data/classification_results.parquet"

import pandas as pd
pdf = pd.read_parquet(parquet_ws)

# COMMAND ----------

from pyspark.sql.types import (StructType, StructField, StringType,
                               TimestampType, DoubleType, ArrayType)
spark_schema = StructType([
    StructField("catalog_id", StringType()),
    StructField("table_id", StringType()),
    StructField("latest_detected_time", TimestampType()),
    StructField("first_detected_time", TimestampType()),
    StructField("catalog_name", StringType()),
    StructField("schema_name", StringType()),
    StructField("table_name", StringType()),
    StructField("column_name", StringType()),
    StructField("data_type", StringType()),
    StructField("class_tag", StringType()),
    StructField("class_tag_value", StringType()),
    StructField("samples", ArrayType(StringType())),
    StructField("confidence", StringType()),
    StructField("frequency", DoubleType()),
    StructField("exclusion_state", StringType()),
])
sdf = spark.createDataFrame(pdf, schema=spark_schema)

# COMMAND ----------

spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{catalog}`.`{schema}`")
sdf.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(results_table)
print(f"Wrote {sdf.count()} rows to {results_table}")

