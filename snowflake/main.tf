locals {
  // Leverage workspaces to manage multiple environments
  params = jsondecode(file("params-${terraform.workspace}.json"))
}

terraform {
  required_version = "1.2.3"
  backend "s3" {
    bucket         = "your-s3-bucket"
    key            = "aws/path/to/your/tfstate"
    region         = "your-aws-region"
    dynamodb_table = "your-terraform-dynamodb-table"
  }
  required_providers {
    snowflake = {
      source  = "Snowflake-Labs/snowflake"
      version = "0.36.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

/*
// Use something like this when you want to set up remote tfstate
data "aws_ssm_parameter" "snowflake_terraform_uid" {
  name = local.params.snowflake_terraform_uid_paramstore
}

data "aws_ssm_parameter" "snowflake_terraform_pwd" {
  name = local.params.snowflake_terraform_pwd_paramstore
}
*/

// SYSADMIN is default because it doesn't have an alias
provider "snowflake" {
  role     = "SYSADMIN"
  account  = local.params.snowflake_account
  region   = local.params.snowflake_region
  // When testing locally, comment these out and have the 
  // environment variables SNOWFLAKE_USER and SNOWFLAKE_PASSWORD set
  //username = data.aws_ssm_parameter.snowflake_terraform_uid.value
  //password = data.aws_ssm_parameter.snowflake_terraform_pwd.value
}

// can use `provider = security_admin` in a resource where required (some grants)
provider "snowflake" {
  role     = "SECURITYADMIN"
  alias    = "security_admin"
  account  = local.params.snowflake_account
  region   = local.params.snowflake_region
  // When testing locally, comment these out and have the 
  // environment variables SNOWFLAKE_USER and SNOWFLAKE_PASSWORD set
  //username = data.aws_ssm_parameter.snowflake_terraform_uid.value
  //password = data.aws_ssm_parameter.snowflake_terraform_pwd.value
}
