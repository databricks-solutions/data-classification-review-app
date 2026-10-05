# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "6"
# ///
# DBTITLE 1,Upgrade - copy app data from public
# MAGIC %md
# MAGIC # Upgrade: copy app data from `public`
# MAGIC
# MAGIC **Optional.** Only for apps upgraded from a version that kept its tables in the
# MAGIC Postgres `public` schema. The current version keeps them in
# MAGIC `data_classification_review_app` (owned by the app service principal) and does
# MAGIC not touch `public`, so after the upgrade it starts with empty tables. This
# MAGIC notebook copies the old rows over:
# MAGIC
# MAGIC | Table | Contents |
# MAGIC | --- | --- |
# MAGIC | `principals` | Users, groups and admins known to the app |
# MAGIC | `steward_assignments` | Which steward reviews which catalog / schema / table |
# MAGIC | `decisions` | Review decisions (approve / modify / reject) |
# MAGIC | `tag_config`, `tag_policy_cache` | Enabled tags and their cached policy |
# MAGIC
# MAGIC **Before running:** deploy the new version and open the app once, so it creates its
# MAGIC tables. Run as a Lakebase project owner or `databricks_superuser` member (needs
# MAGIC SELECT on the old tables and INSERT on the new ones).
# MAGIC
# MAGIC **Safe to re-run:** rows the app already has are kept, and once the copy has
# MAGIC committed further runs do nothing. Start with `dry_run = true` to see the row counts.
# MAGIC
# MAGIC Usually run from the job *"Data Classification Review App - Migrate legacy schema from
# MAGIC version 1.0.x"* (created by the deploy with `--legacy-upgrade-job`), which prefills the
# MAGIC parameters. Run by hand, the widgets default to this installation's values (written by
# MAGIC the deploy); `endpoint` is `lakebase_endpoint_name` (or `lakebase_host`) in
# MAGIC `databricks.local.yml`.

# COMMAND ----------

# MAGIC %pip install psycopg2-binary --quiet

# COMMAND ----------

# DBTITLE 1,Widgets (defaults from this installation)
import json
import os

# scripts/deploy.sh writes install_defaults.json next to this notebook with this
# installation's values; without it (e.g. a plain repo checkout) the defaults are generic.
_nb_dir = "/Workspace" + os.path.dirname(
    dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get())
try:
    with open(os.path.join(_nb_dir, "install_defaults.json")) as f:
        _defaults = json.load(f)
except (FileNotFoundError, ValueError):
    _defaults = {}

dbutils.widgets.text("endpoint", _defaults.get("endpoint", ""), "Lakebase endpoint")
dbutils.widgets.text("database", _defaults.get("database", "databricks_postgres"), "Postgres database")
dbutils.widgets.text("source_schema", _defaults.get("source_schema", "public"), "Legacy schema")
dbutils.widgets.text("target_schema", _defaults.get("target_schema", "data_classification_review_app"), "App schema")
dbutils.widgets.dropdown("dry_run", "true", ["true", "false"], "Dry run")
dbutils.widgets.dropdown("drop_legacy", "false", ["true", "false"], "Drop legacy tables after copy")

# COMMAND ----------

# DBTITLE 1,Parameters
endpoint = dbutils.widgets.get("endpoint").strip()
database = dbutils.widgets.get("database").strip()
source_schema = dbutils.widgets.get("source_schema").strip()
target_schema = dbutils.widgets.get("target_schema").strip()
dry_run = dbutils.widgets.get("dry_run") == "true"
drop_legacy = dbutils.widgets.get("drop_legacy") == "true"
if not endpoint:
    raise ValueError("Set the `endpoint` widget: lakebase_endpoint_name (or lakebase_host) "
                     "in databricks.local.yml")

# COMMAND ----------

# DBTITLE 1,Connect to Lakebase as yourself
import sys

import psycopg2
from databricks.sdk import WorkspaceClient

# legacy_copy.py sits next to this notebook.
sys.path.insert(0, _nb_dir)
import legacy_copy  # noqa: E402

w = WorkspaceClient()
if endpoint.startswith("projects/"):
    endpoint_name = endpoint
    host = w.postgres.get_endpoint(name=endpoint_name).status.hosts.host
else:
    host = endpoint
    endpoint_name = None
    for project in w.postgres.list_projects(page_size=100):
        for branch in w.postgres.list_branches(parent=project.name):
            for ep in w.postgres.list_endpoints(parent=branch.name):
                if ep.status and ep.status.hosts and ep.status.hosts.host == host:
                    endpoint_name = ep.name
                    break
            if endpoint_name:
                break
        if endpoint_name:
            break
    if not endpoint_name:
        raise ValueError(f"Lakebase endpoint not found for host {host}")

user = w.current_user.me().user_name
conn = psycopg2.connect(
    host=host, port=5432, dbname=database, user=user, sslmode="require",
    password=w.postgres.generate_database_credential(endpoint=endpoint_name).token,
)
print(f"Connected to {database} on {host} as {user}")

# COMMAND ----------

# DBTITLE 1,Copy
result = legacy_copy.copy_legacy_tables(
    conn, source_schema=source_schema, target_schema=target_schema, dry_run=dry_run)

print(f"Status: {result['status']}")
display(spark.createDataFrame(
    [(t, v["source_rows"], v["target_rows"], v["inserted"]) for t, v in result["tables"].items()],
    "table string, source_rows long, target_rows_before long, inserted long",
))

# COMMAND ----------

# DBTITLE 1,Drop legacy tables (optional)
if drop_legacy and dry_run:
    print("drop_legacy is ignored on a dry run")
elif drop_legacy:
    dropped = legacy_copy.drop_legacy_tables(
        conn, source_schema=source_schema, target_schema=target_schema)
    print(f"Dropped from {source_schema}: {', '.join(dropped) or 'nothing'}")
else:
    print(f"Legacy tables left in {source_schema}")
conn.close()
