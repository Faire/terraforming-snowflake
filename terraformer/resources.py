import json
import logging
import os
import re
from numbers import Number
from posixpath import supports_unicode_filenames
from typing import Optional

logger = logging.getLogger()
logging.basicConfig(level=logging.WARN)

escape = lambda s: s.encode("unicode_escape").decode("utf-8")

def stringify(obj, surround=True):
    if isinstance(obj, str):
        return (f'"{obj}"' if surround else obj) if obj else ""
    elif isinstance(obj, type(None)):
        return "null"
    elif isinstance(obj, bool):
        return str(obj).lower()
    elif isinstance(obj, Number):
        return str(obj)
    elif isinstance(obj, list):
        return '["' + '","'.join([escape(x) for x in obj]) + '"]' if obj else "[]"
    else:
        raise TypeError(f"Unsupported type: {type(obj)}")


class SnowflakeResource:
    # These get set to something else in the child classes upon instantiation
    tf_filename = ""
    snowflake_provider_resource = ""
    schema = ""
    database = ""
    name = ""
    resource_attributes = {}

    def __init__(self, **kwargs):
        regex_exclusion_rules = (
            kwargs["regex_exclusion_rules"] if "regex_exclusion_rules" in kwargs
            else default_regex_exclusion_rules
        )
        attr_exclusion_rules = (
            kwargs["attr_exclusion_rules"] if "attr_exclusion_rules" in kwargs
            else default_attr_exclusion_rules
        )
        for attr, exclusions in attr_exclusion_rules.items():
            if hasattr(self, attr) and getattr(self, attr).lower() in exclusions:
                # if This item meets the exclusion criteria, skip it.
                self.stop_resource()
        for clas, patterns in regex_exclusion_rules.items():
            for pattern in patterns:
                if isinstance(self, clas) and re.search(pattern, self.name.lower()):
                    self.stop_resource()

    def stop_resource(self):
        """
        stops the resource from doing anything.
           We will do this by neutralizing the append_tf_code_to_file and the
           append_import_command_to_file methods.
        """
        warn = lambda: logger.warn(
            f"{self.snowflake_provider_resource} {self.name} won't be managed by Terraform"
        )
        self.append_tf_code_to_file = lambda *args, **kwargs: warn()  # type: ignore
        self.append_import_command_to_file = lambda *args, **kwargs: warn()  # type: ignore

    def append_tf_code_to_file(self, file_dir=".", filename=None):
        """
        takes all the class attributes and writes them to a terraform file
        ARGUMENTS
            filename = the filename to write to, defaults to self.tf_filename
        """
        if not filename:
            filename = self.tf_filename
        if self.tf_filename:
            nl = "\n"
            nlss = "\n  "
            tfstr = (
                f'resource "{self.snowflake_provider_resource}" "{self.alias_resource}" {{ {nlss}'
                f"{nlss.join([f'{k} = {v}' for k, v in self.resource_attributes.items() if v])}"
                f"{nl}}}"
            )
            with open(os.path.join(file_dir, filename), "a+") as f:
                f.write(tfstr + "\n\n")
        else:
            raise ValueError(f"Resource not initialized properly, name = {self.name}")

    def append_import_command_to_file(self, file_dir = '.', filename=None):
        """
        writes a terraform command to a file
        ARGUMENTS
            filename = the filename to write to, defaults to self.tf_filename
        """
        if not filename:
            filename = self.tf_filename.replace(".tf", ".sh")
        if self.tf_filename:
            with open(os.path.join(file_dir, filename), "a+") as f:
                f.write(self.tf_import_string + "\n")
        else:
            raise ValueError("Resource not initialized properly")

    @property
    def tf_import_string(self):
        if not all(
            [
                os.getenv("SNOWFLAKE_USER"),
                os.getenv("SNOWFLAKE_REGION"),
                os.getenv("SNOWFLAKE_ACCOUNT"),
            ]
        ):
            logger.warn(
                "SNOWFLAKE_USER, SNOWFLAKE_REGION, and SNOWFLAKE_ACCOUNT "
                "environment variables must be set"
            )
        return (
            f"terraform import '{self.snowflake_provider_resource}."
            f'{self.alias_resource}\' "{self.identifier_resource}" '
        )

    @property
    def alias_resource(self):
        """
        alias_resource is the "Terraform Name" for the specific resource.
           i.e. "demo_db". Full name "snowflake_database.demo_db"
        alias_resource defaults to this, but may be overridden by the child class.
        """
        return self.identifier_resource.lower().replace("|", "_")

    @property
    def identifier_resource(self):
        """
        identifier_resource is terraform's way to identify something that exists
        in the remote state (your snowflake instance). It is used as part of the
        terraform import command.
        identifier_resource defaults to this, but usually gets overridden by the
         child class.
        """
        return f"{self.name}"


class SnowflakeDatabase(SnowflakeResource):
    def __init__(self, **kwargs):
        # sample import:
        # tf import snowflake_database.demo_db DEMO_DB
        self.name = kwargs["name"]
        self.owner = kwargs["owner"]
        self.comment = kwargs["comment"]
        self.tf_filename = "generated_database.tf"
        super().__init__(**kwargs)

    @property
    def snowflake_provider_resource(self):
        # snowflake_provider_resource is the Snowflake Resource type
        return "snowflake_database"

    @property
    def resource_attributes(self):
        # These are the Terraform-configurable attributes that go into the 
        # terraform code. Databases have a bit more config than this, but 
        # nothing we're interested in for our initial setup
        return {
            "name": stringify(self.name),
            "comment": stringify(self.comment),
        }


class SnowflakeStage(SnowflakeResource):
    def __init__(self, extra_data=None, **kwargs):
        # sample import:
        # tf import snowflake_stage.raw_adhoc_adhoc_stage 'RAW|ADHOC|ADHOC_STAGE'
        self.name = kwargs["name"]
        self.database = kwargs["database_name"]
        self.comment = kwargs["comment"]
        self.owner = kwargs["owner"]
        self.schema = kwargs["schema_name"]
        self.storage_integration = kwargs["storage_integration"]
        self.url = kwargs["url"]
        self.tf_filename = f"generated__stages_{self.database.lower()}.tf"
        self.extra_data = extra_data
        super().__init__(**kwargs)

    @property
    def identifier_resource(self):
        # non-default identifier_resource
        return f"{self.database}|{self.schema}|{self.name}"

    @property
    def snowflake_provider_resource(self):
        return "snowflake_stage"

    @property
    def resource_attributes(self):
        attrs = {
            "name": stringify(self.name),
            "database": stringify(self.database),
            "schema": stringify(self.schema),
            "comment": stringify(self.comment),
            "storage_integration": stringify(self.storage_integration),
            "url": stringify(self.url),
        }
        if self.extra_data:
            extra_attrs = {}
            """
             extra data would be a dict of dicts, where the outer dict is the
                non-default parent properties fron the command `DESC STAGE <stage_name>`
                and the inner dict is the non-default properties under the parent property
            e.g.
            extra_data = {
                'STAGE_FILE_FORMAT': {
                    'FORMAT_NAME': 'x_loading_file_format_v1',
                    'NULL_IF': []
                }
            }
            This would need to produce the string for the `.tf` file:
                ```file_format = "FORMAT_NAME = x_loading_file_format_v1 NULL_IF = []" ```
            """
            dict_to_str = lambda d: stringify(
                " ".join(
                    [k + " = " + stringify(v, surround=False) for k, v in d.items()]
                )
            )
            for parent, property in self.extra_data.items():
                # supports COPY_OPTIONS and FILE_FORMAT. Warns if parent is not supported
                if parent == "STAGE_COPY_OPTIONS":
                    extra_attrs["copy_options"] = dict_to_str(property)
                elif parent == "STAGE_FILE_FORMAT":
                    extra_attrs["file_format"] = dict_to_str(property)
                else:
                    logger.warn(
                        "-" * 80 + f"{parent} property not supported yet! \n" + "-" * 80
                    )
            attrs.update(extra_attrs)
        return attrs


class SnowflakeWarehouse(SnowflakeResource):
    def __init__(self, **kwargs):
        # sample import:
        # tf import snowflake_warehouse.demo_wh DEMO_WH
        self.tf_filename = "generated_warehouses.tf"
        # turn all values in dict to strings
        for k, v in kwargs.items():
            kwargs[k] = str(v)
        # Get values from kwargs
        self.name = kwargs["name"]
        self.size = kwargs["size"]
        self.min_cluster_count = kwargs["min_cluster_count"]
        self.max_cluster_count = kwargs["max_cluster_count"]
        self.auto_suspend = kwargs["auto_suspend"]
        self.auto_resume = kwargs["auto_resume"]
        self.owner = kwargs["owner"]
        self.comment = kwargs["comment"]
        self.scaling_policy = (
            kwargs["scaling_policy"] if kwargs["scaling_policy"] != "STANDARD" else None
        )
        self.max_concurrency_level = kwargs["max_concurrency_level"]
        self.statement_queued_timeout_in_seconds = kwargs[
            "statement_queued_timeout_in_seconds"
        ]
        self.statement_timeout_in_seconds = kwargs["statement_timeout_in_seconds"]
        super().__init__(**kwargs)

    @property
    def snowflake_provider_resource(self):
        return "snowflake_warehouse"

    @property
    def resource_attributes(self):
        return {
            "name": stringify(self.name),
            "warehouse_size": stringify(self.size),
            "min_cluster_count": stringify(self.min_cluster_count),
            "max_cluster_count": stringify(self.max_cluster_count),
            "auto_suspend": stringify(self.auto_suspend),
            "auto_resume": stringify(self.auto_resume),
            "comment": stringify(self.comment),
            "scaling_policy": stringify(self.scaling_policy)
            if self.scaling_policy
            else None,
            "max_concurrency_level": stringify(self.max_concurrency_level),
            "statement_queued_timeout_in_seconds": stringify(
                self.statement_queued_timeout_in_seconds
            ),
            "statement_timeout_in_seconds": stringify(
                self.statement_timeout_in_seconds
            ),
        }


class SnowflakeRole(SnowflakeResource):
    def __init__(self, **kwargs):
        self.tf_filename = "generated_roles.tf"
        # sample import:
        # terraform import snowflake_role.example roleName
        self.name = kwargs["name"]
        self.comment = kwargs["comment"]
        self.owner = kwargs["owner"]
        self.append_tf_code_to_file = lambda *args, **kwargs: None  # type: ignore
        super().__init__(**kwargs)
        logger.warning(
            "Importing roles didn't work well when this was implemented, use "
            "SnowflakeRole with caution. You *really* don't want Terraform to "
            "accidentally deleting something. Terraform role import statemets "
            "are commented out for extra safety.")

    @property
    def snowflake_provider_resource(self):
        return "snowflake_role"

    @property
    def alias_resource(self):
        return f'role["{self.name.upper()}"]'

    @property
    def identifier_resource(self):
        # non-default identifier_resource
        return f"{self.name}"

    @property
    def resource_attributes(self):
        return {
            "name": stringify(self.name),
            "comment": stringify(self.comment),
        }

    @property
    def tf_import_string(self):
        return (
            f"#terraform import 'snowflake_role.{self.alias_resource}' "
            f"'{self.identifier_resource}'\n"
            f"#terraform import 'snowflake_role_grants.{self.alias_resource}' "
            f"'{self.identifier_resource}'"
        )


class SnowflakeSchema(SnowflakeResource):
    def __init__(self, **kwargs):
        # sample import:
        # terraform import snowflake_schema.example 'dbName|schemaName'
        self.name = kwargs["name"]
        self.database = kwargs["database_name"]
        self.comment = kwargs["comment"]
        self.owner = kwargs["owner"]
        self.tf_filename = f"generated__schemas_{self.database.lower()}.tf"
        super().__init__(**kwargs)

    @property
    def identifier_resource(self):
        return f"{self.database}|{self.name}"

    @property
    def snowflake_provider_resource(self):
        return "snowflake_schema"

    @property
    def resource_attributes(self):
        return {
            "name": stringify(self.name),
            "database": stringify(self.database),
            "comment": stringify(self.comment),
        }


class SnowflakePipe(SnowflakeResource):
    def __init__(self, **kwargs):
        self.tf_filename = "generated_pipes.tf"
        # sample import:
        # tf import snowflake_pipe.raw_kinesis_clicks 'RAW|KINESIS|CLICKS'
        self.name = kwargs["pipe_name"]
        self.database = kwargs["pipe_catalog"]
        self.comment = kwargs["comment"]
        self.schema = kwargs["pipe_schema"]
        self.copy_statement = kwargs["definition"]
        self.auto_ingest = kwargs["is_autoingest_enabled"]
        self.aws_sns_topic_arn = kwargs["notification_channel_name"]
        self.owner = kwargs["pipe_owner"]
        super().__init__(**kwargs)

    @property
    def identifier_resource(self):
        # non-default identifier_resource
        return f"{self.database}|{self.schema}|{self.name}"

    @property
    def snowflake_provider_resource(self):
        return "snowflake_pipe"

    @property
    def resource_attributes(self):
        return {
            "name": stringify(self.name),
            "database": stringify(self.database),
            "schema": stringify(self.schema),
            "comment": stringify(self.comment),
            "auto_ingest": "true" if self.auto_ingest == "YES" else "false",
            "copy_statement": "<<EOT\n" + self.copy_statement + "\nEOT",
        }


class SnowflakeFileFormat(SnowflakeResource):
    def __init__(self, **kwargs):
        self.tf_filename = "generated_file_formats.tf"
        # sample import:
        # tf import snowflake_file_format.raw_adwords_stitch_loading_file_format_v1 'RAW|ADWORDS|STITCH_LOADING_FILE_FORMAT_V1'
        # Required
        self.name = kwargs["name"]
        self.database = kwargs["database_name"]
        self.schema = kwargs["schema_name"]
        self.format_type = kwargs["type"]
        # Optionals
        self.owner = kwargs["owner"]
        self.comment = kwargs["comment"]
        self.format_options = json.loads(kwargs["format_options"])
        self.format_options = {
            k.lower(): self.parse_option(v) for k, v in self.format_options.items()
        }
        super().__init__(**kwargs)

    def parse_option(self, option):
        if isinstance(option, bool):
            return "true" if option else "false"
        elif isinstance(option, int):
            return str(option)
        elif isinstance(option, list):
            return stringify(option)
        elif isinstance(option, type(None)):
            return "null"
        elif isinstance(option, str):
            if option == '"':
                return r'"\""'
            elif option == "\\":
                return '"' + r"\\\\" + '"'
            elif len(option) == 1 and escape(option).startswith(r"\x"):
                # hex digit in string format. Python notation "\x01"
                # Terraform apparently doesnt support ASCII codes
                # hardcode converting them to unicode
                vals = {"\xfe": r'"\u00fe"', "\x01": r'"\u0001"'}
                return vals[option]
            else:
                return '"' + escape(option) + '"'
        else:
            raise NotImplementedError(
                f"Unsupported option type: {type(option)}. It should be implemented. Please implement it."
            )

    @property
    def identifier_resource(self):
        # non-default identifier_resource
        return f"{self.database}|{self.schema}|{self.name}"

    @property
    def snowflake_provider_resource(self):
        return "snowflake_file_format"

    @property
    def resource_attributes(self):
        res_attr = {
            "name": stringify(self.name),
            "database": stringify(self.database),
            "schema": stringify(self.schema),
            "format_type": stringify(self.format_type),
            "comment": stringify(self.comment),
        }
        # add together self.format_options and res_attr
        format_options = self.format_options
        if "type" in format_options:
            format_options["format_type"] = format_options.pop("type")
        res_attr.update(format_options)
        return res_attr

## EXCLUSIONS: 
# These are things you *don't* want Terraform to manage.
# You won't catch all the exclusions, so make sure to review your import statements
# and make sure you are not importing something that you don't want to import.
default_attr_exclusion_rules = {
    # Any class attribute named [key] with a value of [value] will be excluded.
    "owner": ["okta_provisioner"],
    "schema": ["information_schema"],
    "database": ["snowflake"],
}

default_regex_exclusion_rules = {
    # Any class instance [key] with the `name` attribute matching the regex
    #    pattern [value] will be excluded.
    # all regex rules should be in lowercase
    SnowflakeSchema: [
        "information_schema",
        r"\d{4}_\d{2}_\d{2}_\d{2}",  # date format of schemas generated dynamically by our airflow dags
        r"_temp_",
    ],
    SnowflakeRole: [
        "sysadmin",
        "accountadmin",
        "okta_provisioner",
        "securityadmin",
        "useradmin",
        "^public$",
        "reader_demo_db",
        "reader_demo_db_validation",
    ],
    SnowflakeDatabase: ["^snowflake$", "snowflake_sample_data"],
    SnowflakeStage: ["stitch_loading"],
}
