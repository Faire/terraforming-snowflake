import client as snowflake_client
from resources import (
    SnowflakeDatabase,
    SnowflakeStage,
    SnowflakeWarehouse,
    SnowflakeRole,
    SnowflakeSchema,
    SnowflakePipe,
    SnowflakeFileFormat,
)
import python_terraform
import argparse
import os
import logging
import data_parse_helper as dph


def getLogger(level=logging.INFO):
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=level)
    return logger


def tf_databases(t):
    ## DATABASES
    # Get database info from snowflake, write an outline to terraform files,
    #   and run `terraform import` on each resource.
    db_data = snowflake_client.exec_sql_multi("show databases")
    columns = [
        "created_on",
        "name",
        "is_default",
        "is_current",
        "origin",
        "owner",
        "comment",
        "options",
        "retention_time",
    ]
    db_dicts = [{k: row[i] for i, k in enumerate(columns)} for row in db_data]
    database_names = [db["name"] for db in db_dicts]
    for row in db_dicts:
        tfDatabase = SnowflakeDatabase(
            attr_exclusion_rules=attr_exclusion_rules,
            regex_exclusion_rules=regex_exclusion_rules,
            **row,
        )
        tfDatabase.append_tf_code_to_file(file_dir=t.working_dir)
        tfDatabase.append_import_command_to_file(
            filename="generated_tf_snowflake_import_resources.sh"
        )
    return database_names


def tf_schemas(t, database_names):
    ## SCHEMAS
    # Iterate through all the existing databases, get all the schemas, and turn
    #   them into terraform resources.
    database_schemas = {}
    for db in database_names:
        # We may want to separate tf files by database
        schema_data = snowflake_client.exec_sql_multi(f"show schemas in database {db}")
        columns = [
            "created_on",
            "name",
            "is_default",
            "is_current",
            "database_name",
            "owner",
            "comment",
            "options",
            "retention_time",
        ]
        schema_dicts = [
            {k: row[i] for i, k in enumerate(columns)} for row in schema_data
        ]
        database_schemas[db] = [schema["name"] for schema in schema_dicts]
        for schema in schema_dicts:
            print("'" + schema["database_name"] + "'")
            if schema["database_name"] == "RAW":
                if any(
                    [
                        x in schema["name"]
                        for x in ["PUBLIC", "KINESIS_", "CHARM_EXTERNAL"]
                    ]
                ):
                    # Special inclusion rules only for RAW DB to exclude Stitch schemas.
                    # only process if it's `public`, `kinesis_*`, or `charm_external`
                    # There isn't a clear way to make an exclusion rule for Stitch :(
                    tfSchema = SnowflakeSchema(
                        attr_exclusion_rules=attr_exclusion_rules,
                        regex_exclusion_rules=regex_exclusion_rules,
                        **schema,
                    )
                    tfSchema.append_tf_code_to_file(t.working_dir)
                    tfSchema.append_import_command_to_file(
                        filename="generated_tf_snowflake_import_resources.sh"
                    )
            else:
                # Otherwise proceed as normal
                tfSchema = SnowflakeSchema(**schema)
                tfSchema.append_tf_code_to_file(t.working_dir)
                tfSchema.append_import_command_to_file(
                    filename="generated_tf_snowflake_import_resources.sh"
                )
    return database_schemas


def tf_stages(t, database_names):
    ## STAGES
    #  Iterate through every database, looking at the `information_schema` schema
    # NOTE: We probably want to avoid special autoschemas, like `information_schema`
    for database in database_names:
        # NOTE: We may want to separate schema.tf files by database
        columns = [
            "created_on",
            "name",
            "database_name",
            "schema_name",
            "url",
            "has_credentials",
            "has_encryption_key",
            "owner",
            "comment",
            "region",
            "type",
            "cloud",
            "notification_channel",
            "storage_integration",
        ]
        query = f"show stages in database {database}"
        snowflake_client.DATABASE = database
        stage_data = snowflake_client.exec_sql_multi(query)
        stage_dicts = [{k: row[i] for i, k in enumerate(columns)} for row in stage_data]
        for row in stage_dicts:
            stage_extra_data = snowflake_client.exec_sql_multi(
                f"desc stage {database}.{row['schema_name']}.{row['name']}"
            )
            stage_dict = dph.stage_parser(stage_extra_data)
            tfStage = SnowflakeStage(
                attr_exclusion_rules=attr_exclusion_rules,
                regex_exclusion_rules=regex_exclusion_rules,
                extra_data=stage_dict,
                **row,
            )
            tfStage.append_tf_code_to_file(t.working_dir)
            tfStage.append_import_command_to_file(
                filename="generated_tf_snowflake_import_resources.sh"
            )


def tf_file_format(t, database_names):
    ## FILE_FORMATS
    #  Iterate through every database, looking at the `information_schema` schema
    #  and grabbing the `file_format` table.
    for database in database_names:
        query = f"show file formats"
        snowflake_client.DATABASE = database
        file_format_data = snowflake_client.exec_sql_multi(query)
        columns = [
            "created_on",
            "name",
            "database_name",
            "schema_name",
            "type",
            "owner",
            "comment",
            "format_options",
        ]
        file_format_dicts = [
            {k: row[i] for i, k in enumerate(columns)} for row in file_format_data
        ]
        for row in file_format_dicts:
            tfFileFormat = SnowflakeFileFormat(
                attr_exclusion_rules=attr_exclusion_rules,
                regex_exclusion_rules=regex_exclusion_rules,
                **row,
            )
            tfFileFormat.append_tf_code_to_file(t.working_dir)
            tfFileFormat.append_import_command_to_file(
                filename="generated_tf_snowflake_import_resources.sh"
            )


def tf_warehouses(t):
    ## WAREHOUSES
    wh_data = snowflake_client.exec_sql_multi("show warehouses")
    clustering_columns = [
        "min_cluster_count",
        "max_cluster_count",
        "started_clusters",
        "scaling_policy",
    ]
    columns = [
        "name",
        "state",
        "type",
        "size",
        "running",
        "queued",
        "is_default",
        "is_current",
        "auto_suspend",
        "auto_resume",
        "available",
        "provisioning",
        "quiescing",
        "other",
        "created_on",
        "resumed_on",
        "updated_on",
        "owner",
        "comment",
        "resource_monitor",
        "actives",
        "pendings",
        "failed",
        "suspended",
        "uuid",
    ]
    try:
        wh_dicts = [{k: row[i] for i, k in enumerate(columns + clustering_columns)} for row in wh_data]
    except IndexError:
        wh_dicts = [{k: row[i] for i, k in enumerate(columns)} for row in wh_data]

    for row in wh_dicts:
        addtl_params = snowflake_client.exec_sql_multi(
            f"show parameters in warehouse {row['name']};"
        )
        cols = ["key", "value", "default", "level", "description", "type"]
        addtl_params_dict = {
            row[0].lower(): {k: row[i] for i, k in enumerate(cols)}["value"]
            for row in addtl_params
        }
        row.update(addtl_params_dict)
        tfWarehouse = SnowflakeWarehouse(
            attr_exclusion_rules=attr_exclusion_rules,
            regex_exclusion_rules=regex_exclusion_rules,
            **row,
        )
        tfWarehouse.append_tf_code_to_file(t.working_dir)
        tfWarehouse.append_import_command_to_file(
            filename="generated_tf_snowflake_import_resources.sh"
        )


def tf_roles(t):
    ## ROLES
    role_data = snowflake_client.exec_sql_multi("show roles")
    columns = [
        "created_on",
        "name",
        "is_default",
        "is_current",
        "is_inherited",
        "assigned_to_users",
        "granted_to_roles",
        "granted_roles",
        "owner",
        "comment",
    ]
    role_dicts = [{k: row[i] for i, k in enumerate(columns)} for row in role_data]
    for row in role_dicts:
        tfRole = SnowflakeRole(
            attr_exclusion_rules=attr_exclusion_rules,
            regex_exclusion_rules=regex_exclusion_rules,
            **row,
        )
        tfRole.append_tf_code_to_file(t.working_dir)
        tfRole.append_import_command_to_file(
            filename="generated_tf_snowflake_import_resources.sh"
        )


def tf_pipes(t, database_names):
    ## PIPES
    for database in database_names:
        snowflake_client.DATABASE = database
        query = f"select * from {database}.information_schema.pipes"
        pipe_data = snowflake_client.query_to_df(query)
        for _, row in pipe_data.iterrows():
            tfPipe = SnowflakePipe(
                attr_exclusion_rules=attr_exclusion_rules,
                regex_exclusion_rules=regex_exclusion_rules,
                **dict(row),
            )
            tfPipe.append_tf_code_to_file(t.working_dir)
            tfPipe.append_import_command_to_file(
                filename="generated_tf_snowflake_import_resources.sh"
            )


## EXCLUSIONS:
# These are things you *don't* want Terraform to manage.
# You won't catch all the exclusions, so make sure to review your import statements
# and make sure you are not importing something that you don't want to import.
attr_exclusion_rules = {
    # Any resource with an attribute named [key] with a value of [value] will be excluded.
    "owner": ["okta_provisioner"],
    "schema": ["information_schema"],
    "database": ["snowflake"],
}

regex_exclusion_rules = {
    # Any class instance [key] with the `name` attribute matching the regex
    #    pattern [value] will be excluded.
    # all regex rules should be in lowercase
    SnowflakeSchema: [
        "^information_schema$",
        r"\d{4}_\d{2}_\d{2}_\d{2}",  # date format of schemas generated dynamically by our airflow dags
        r"_temp_",
    ],
    SnowflakeRole: [
        "^sysadmin$",
        "^accountadmin$",
        "^securityadmin$",
        "^useradmin$",
        "^public$",  # ^ and $ prevent regex matching a substring
        "^reader_demo_db$",
    ],
    SnowflakeDatabase: ["^snowflake$", "snowflake_sample_data"],
}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    this_dir = os.path.dirname(os.path.realpath(__file__))
    parser.add_argument("--tf_dir", default=os.path.join(this_dir, "../snowflake"))
    args = parser.parse_args()
    tf_dir = os.path.abspath(args.tf_dir)
    print("note that tf_dir is set to: ", tf_dir)

    t = python_terraform.Terraform(working_dir=tf_dir)
    # t.init()

    database_names = tf_databases(t)
    tf_file_format(t, database_names)
    database_schemas = tf_schemas(t, database_names)
    tf_stages(t, database_names)
    tf_warehouses(t)
    tf_pipes(t, database_names)
